"""
Meshtastic Bridge - Integrazione con rete mesh LoRa
Walkie-Talkie AI via LoRa Mesh

Permette al chatbot vocale di:
- Inviare messaggi alla rete mesh LoRa (dettati vocalmente)
- Ricevere messaggi mesh e leggerli ad alta voce
- Vedere quali nodi sono vicini e a che distanza
- Monitorare lo stato della rete mesh

Architettura (VPS moschino.xamad.net):
1. Nodo LoRa (T-Beam/T-Echo) con Meshtastic → MQTT uplink via WiFi
2. Mosquitto MQTT broker su VPS (porta 8883 esterno, 1883 localhost)
3. Questo plugin si connette al broker MQTT locale
4. Il chatbot vocale invia/riceve messaggi LoRa tramite questo plugin

Requisiti:
- Meshtastic firmware sul satellite ESP32-S3
- MQTT broker (mosquitto) o HTTP API abilitata su Meshtastic
- pip install meshtastic paho-mqtt

Autore: Claude Code
"""

import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from dataclasses import dataclass
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# ============ CONFIGURAZIONE ============

# Modalità connessione: "mqtt", "http", "serial"
MESHTASTIC_MODE = os.environ.get("MESHTASTIC_MODE", "mqtt")

# MQTT Settings (se MESHTASTIC_MODE = "mqtt")
# Broker locale su VPS (moschino.xamad.net)
MQTT_BROKER = os.environ.get("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))  # Porta locale
# Topic Meshtastic: msh/[region]/[channel]/[gateway_id]
# Esempio: msh/EU_868/LongFast/!abcd1234
MQTT_TOPIC_ROOT = os.environ.get("MQTT_TOPIC", "msh")
MQTT_USERNAME = os.environ.get("MQTT_USER", "")  # Locale non richiede auth
MQTT_PASSWORD = os.environ.get("MQTT_PASS", "")

# HTTP Settings (se MESHTASTIC_MODE = "http")
MESHTASTIC_HTTP_HOST = os.environ.get("MESHTASTIC_HTTP", "http://192.168.1.100")

# Serial Settings (se MESHTASTIC_MODE = "serial")
MESHTASTIC_SERIAL_PORT = os.environ.get("MESHTASTIC_SERIAL", "/dev/ttyUSB0")


# ============ DATA STRUCTURES ============

@dataclass
class MeshNode:
    """Rappresenta un nodo nella rete mesh"""
    node_id: str
    short_name: str
    long_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    distance_km: Optional[float] = None
    snr: Optional[float] = None  # Signal-to-Noise Ratio
    last_heard: Optional[datetime] = None
    battery_level: Optional[int] = None
    is_online: bool = False


@dataclass
class MeshMessage:
    """Rappresenta un messaggio mesh"""
    from_node: str
    from_name: str
    to_node: str  # "broadcast" per tutti
    text: str
    timestamp: datetime
    channel: int = 0
    is_read: bool = False


# ============ GLOBAL STATE ============

# Cache dei nodi conosciuti
_known_nodes: Dict[str, MeshNode] = {}

# Coda messaggi ricevuti (non letti)
_message_queue: List[MeshMessage] = []

# Client MQTT (se usato)
_mqtt_client = None


# ============ MQTT HANDLER ============

class MeshtasticMQTTHandler:
    """Gestisce connessione MQTT a Meshtastic"""

    def __init__(self):
        self.client = None
        self.connected = False

    async def connect(self):
        """Connetti al broker MQTT"""
        try:
            import paho.mqtt.client as mqtt

            self.client = mqtt.Client()

            if MQTT_USERNAME:
                self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message

            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()

            logger.bind(tag=TAG).info(f"Connesso a MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
            return True

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore connessione MQTT: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback connessione MQTT"""
        if rc == 0:
            self.connected = True
            # Sottoscrivi a tutti i topic meshtastic
            client.subscribe(f"{MQTT_TOPIC_ROOT}/#")
            logger.bind(tag=TAG).info("Sottoscritto a topic Meshtastic")
        else:
            logger.bind(tag=TAG).error(f"Connessione MQTT fallita: {rc}")

    def _on_message(self, client, userdata, msg):
        """Callback messaggi MQTT"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            # Parsing topic meshtastic
            # Formato: meshtastic/2/json/LongFast/!nodeId
            parts = topic.split("/")

            if "text" in topic.lower() or "message" in str(payload).lower():
                # Messaggio testuale ricevuto
                self._handle_text_message(payload)
            elif "nodeinfo" in topic.lower():
                # Info nodo aggiornata
                self._handle_nodeinfo(payload)
            elif "position" in topic.lower():
                # Posizione nodo
                self._handle_position(payload)

        except Exception as e:
            logger.bind(tag=TAG).warning(f"Errore parsing MQTT: {e}")

    def _handle_text_message(self, payload: dict):
        """Gestisce messaggio testuale ricevuto"""
        global _message_queue

        try:
            msg = MeshMessage(
                from_node=payload.get("from", "unknown"),
                from_name=payload.get("sender", payload.get("from", "Sconosciuto")),
                to_node=payload.get("to", "broadcast"),
                text=payload.get("text", payload.get("payload", "")),
                timestamp=datetime.now(),
                channel=payload.get("channel", 0),
                is_read=False
            )

            _message_queue.append(msg)
            logger.bind(tag=TAG).info(f"Nuovo messaggio mesh da {msg.from_name}: {msg.text[:50]}...")

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore parsing messaggio: {e}")

    def _handle_nodeinfo(self, payload: dict):
        """Gestisce info nodo"""
        global _known_nodes

        try:
            node_id = payload.get("id", payload.get("num", ""))
            if not node_id:
                return

            node = MeshNode(
                node_id=str(node_id),
                short_name=payload.get("shortName", payload.get("short_name", "???")),
                long_name=payload.get("longName", payload.get("long_name", "Nodo sconosciuto")),
                last_heard=datetime.now(),
                is_online=True
            )

            # Aggiorna o aggiungi
            if node_id in _known_nodes:
                # Mantieni dati esistenti
                existing = _known_nodes[node_id]
                node.latitude = existing.latitude
                node.longitude = existing.longitude
                node.distance_km = existing.distance_km

            _known_nodes[str(node_id)] = node

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore parsing nodeinfo: {e}")

    def _handle_position(self, payload: dict):
        """Gestisce posizione nodo"""
        global _known_nodes

        try:
            node_id = str(payload.get("from", payload.get("id", "")))
            if not node_id or node_id not in _known_nodes:
                return

            node = _known_nodes[node_id]
            node.latitude = payload.get("latitude", payload.get("lat"))
            node.longitude = payload.get("longitude", payload.get("lon"))
            node.altitude = payload.get("altitude", payload.get("alt"))

            # Calcola distanza se abbiamo la nostra posizione
            # TODO: ottenere posizione locale

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore parsing position: {e}")

    async def send_message(self, text: str, to_node: str = "broadcast") -> bool:
        """Invia messaggio alla mesh"""
        if not self.connected:
            return False

        try:
            topic = f"{MQTT_TOPIC_ROOT}/2/json/LongFast/!ffffffff"
            payload = {
                "text": text,
                "to": to_node
            }

            self.client.publish(topic, json.dumps(payload))
            logger.bind(tag=TAG).info(f"Messaggio inviato a mesh: {text[:50]}...")
            return True

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore invio messaggio: {e}")
            return False

    def get_nodes(self) -> List[MeshNode]:
        """Restituisce lista nodi conosciuti"""
        # Filtra nodi non più attivi (>30 min)
        cutoff = datetime.now() - timedelta(minutes=30)
        active = [
            n for n in _known_nodes.values()
            if n.last_heard and n.last_heard > cutoff
        ]
        return sorted(active, key=lambda x: x.distance_km or 999)

    def get_unread_messages(self) -> List[MeshMessage]:
        """Restituisce messaggi non letti"""
        return [m for m in _message_queue if not m.is_read]

    def mark_messages_read(self):
        """Segna tutti i messaggi come letti"""
        for m in _message_queue:
            m.is_read = True


# ============ SERIAL HANDLER (LIBRERIA PYTHON UFFICIALE) ============

class MeshtasticSerialHandler:
    """
    Gestisce connessione DIRETTA al dispositivo Meshtastic via USB/Serial.
    USA LA LIBRERIA UFFICIALE: pip install meshtastic

    Questa è la modalità più semplice:
    - Collega T-Beam/Heltec via USB al server
    - Nessun MQTT, nessuna configurazione
    - Accesso diretto a tutte le funzionalità
    """

    def __init__(self):
        self.interface = None
        self.connected = False
        self._message_callbacks = []

    def connect(self) -> bool:
        """Connetti al dispositivo Meshtastic via seriale"""
        try:
            # pip install meshtastic
            import meshtastic
            import meshtastic.serial_interface

            # Auto-detect porta o usa quella configurata
            if MESHTASTIC_SERIAL_PORT == "auto":
                self.interface = meshtastic.serial_interface.SerialInterface()
            else:
                self.interface = meshtastic.serial_interface.SerialInterface(
                    devPath=MESHTASTIC_SERIAL_PORT
                )

            # Registra callback per messaggi in arrivo
            from pubsub import pub
            pub.subscribe(self._on_receive, "meshtastic.receive")

            self.connected = True
            logger.bind(tag=TAG).info(f"Connesso a Meshtastic via {MESHTASTIC_SERIAL_PORT}")
            return True

        except ImportError:
            logger.bind(tag=TAG).error("Libreria 'meshtastic' non installata! pip install meshtastic")
            return False
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore connessione seriale Meshtastic: {e}")
            return False

    def _on_receive(self, packet, interface):
        """Callback quando arriva un messaggio"""
        global _message_queue

        try:
            if packet.get("decoded", {}).get("portnum") == "TEXT_MESSAGE_APP":
                text = packet["decoded"]["payload"].decode("utf-8")
                from_id = packet.get("fromId", "unknown")
                from_name = packet.get("from", from_id)

                # Cerca nome lungo se disponibile
                if self.interface and hasattr(self.interface, 'nodes'):
                    node_info = self.interface.nodes.get(from_id, {})
                    from_name = node_info.get("user", {}).get("longName", from_name)

                msg = MeshMessage(
                    from_node=from_id,
                    from_name=from_name,
                    to_node=packet.get("toId", "broadcast"),
                    text=text,
                    timestamp=datetime.now(),
                    channel=packet.get("channel", 0),
                    is_read=False
                )
                _message_queue.append(msg)
                logger.bind(tag=TAG).info(f"Messaggio mesh ricevuto da {from_name}: {text[:50]}...")

        except Exception as e:
            logger.bind(tag=TAG).warning(f"Errore parsing messaggio seriale: {e}")

    async def send_message(self, text: str, to_node: str = "broadcast") -> bool:
        """Invia messaggio via interfaccia seriale"""
        if not self.connected or not self.interface:
            logger.bind(tag=TAG).error("Non connesso a Meshtastic")
            return False

        try:
            if to_node == "broadcast" or to_node == "^all":
                self.interface.sendText(text)
            else:
                # to_node può essere node_id numerico o nome
                self.interface.sendText(text, destinationId=to_node)

            logger.bind(tag=TAG).info(f"Messaggio inviato via serial: {text[:50]}...")
            return True

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore invio messaggio seriale: {e}")
            return False

    def get_nodes(self) -> List[MeshNode]:
        """Ottiene lista nodi dalla cache locale del dispositivo"""
        if not self.connected or not self.interface:
            return []

        try:
            nodes = []
            for node_id, node_data in self.interface.nodes.items():
                user = node_data.get("user", {})
                position = node_data.get("position", {})

                node = MeshNode(
                    node_id=node_id,
                    short_name=user.get("shortName", "???"),
                    long_name=user.get("longName", "Sconosciuto"),
                    latitude=position.get("latitude"),
                    longitude=position.get("longitude"),
                    altitude=position.get("altitude"),
                    snr=node_data.get("snr"),
                    last_heard=datetime.fromtimestamp(node_data.get("lastHeard", 0))
                        if node_data.get("lastHeard") else None,
                    is_online=True  # Se è nei nodi, è stato visto
                )

                # Calcola distanza se abbiamo posizione
                if position.get("latitude") and position.get("longitude"):
                    # TODO: calcolare distanza dalla nostra posizione
                    pass

                nodes.append(node)

            return nodes

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore get_nodes seriale: {e}")
            return []

    def get_unread_messages(self) -> List[MeshMessage]:
        """Restituisce messaggi non letti"""
        return [m for m in _message_queue if not m.is_read]

    def mark_messages_read(self):
        """Segna tutti i messaggi come letti"""
        for m in _message_queue:
            m.is_read = True

    def close(self):
        """Chiudi connessione"""
        if self.interface:
            self.interface.close()
            self.connected = False


# ============ HTTP HANDLER ============

class MeshtasticHTTPHandler:
    """Gestisce connessione HTTP a Meshtastic (API REST)"""

    def __init__(self):
        self.base_url = MESHTASTIC_HTTP_HOST

    async def get_nodes(self) -> List[MeshNode]:
        """Ottiene lista nodi via HTTP API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/v1/nodes") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        nodes = []
                        for n in data.get("nodes", []):
                            node = MeshNode(
                                node_id=n.get("num", ""),
                                short_name=n.get("user", {}).get("shortName", "???"),
                                long_name=n.get("user", {}).get("longName", "Sconosciuto"),
                                latitude=n.get("position", {}).get("latitude"),
                                longitude=n.get("position", {}).get("longitude"),
                                snr=n.get("snr"),
                                last_heard=datetime.fromtimestamp(n.get("lastHeard", 0)) if n.get("lastHeard") else None,
                                is_online=n.get("isOnline", False)
                            )
                            nodes.append(node)
                        return nodes
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore HTTP get_nodes: {e}")
        return []

    async def send_message(self, text: str, to_node: str = "broadcast") -> bool:
        """Invia messaggio via HTTP API"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"text": text}
                if to_node != "broadcast":
                    payload["to"] = to_node

                async with session.post(
                    f"{self.base_url}/api/v1/sendtext",
                    json=payload
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore HTTP send_message: {e}")
        return False

    async def get_messages(self) -> List[MeshMessage]:
        """Ottiene messaggi via HTTP API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/v1/messages") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        messages = []
                        for m in data.get("messages", []):
                            msg = MeshMessage(
                                from_node=m.get("from", ""),
                                from_name=m.get("fromName", "Sconosciuto"),
                                to_node=m.get("to", "broadcast"),
                                text=m.get("text", ""),
                                timestamp=datetime.fromtimestamp(m.get("timestamp", 0)),
                                is_read=False
                            )
                            messages.append(msg)
                        return messages
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore HTTP get_messages: {e}")
        return []


# ============ MAIN HANDLER ============

# Handler globale (inizializzato al primo uso)
_handler = None

async def get_handler():
    """Ottiene handler appropriato in base alla configurazione"""
    global _handler

    if _handler is None:
        if MESHTASTIC_MODE == "serial":
            # RACCOMANDATO: Connessione diretta USB con libreria ufficiale
            _handler = MeshtasticSerialHandler()
            _handler.connect()
        elif MESHTASTIC_MODE == "mqtt":
            _handler = MeshtasticMQTTHandler()
            await _handler.connect()
        elif MESHTASTIC_MODE == "http":
            _handler = MeshtasticHTTPHandler()
        else:
            raise ValueError(f"Modalità non supportata: {MESHTASTIC_MODE}")

    return _handler


# ============ PLUGIN FUNCTIONS ============

INVIA_MESH_DESC = {
    "type": "function",
    "function": {
        "name": "invia_messaggio_mesh",
        "description": (
            "发送LoRa网状消息 / Invia messaggio alla rete mesh LoRa. "
            "Permette di inviare messaggi radio a lunga distanza via Meshtastic. "
            "Use when: 'invia messaggio mesh', 'manda messaggio lora', 'scrivi sulla mesh', "
            "'dì a tutti sulla mesh', 'trasmetti messaggio radio'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "messaggio": {
                    "type": "string",
                    "description": "Il messaggio da inviare"
                },
                "destinatario": {
                    "type": "string",
                    "description": "Nome o ID del destinatario (opzionale, default: tutti)"
                }
            },
            "required": ["messaggio"]
        }
    }
}

@register_function('invia_messaggio_mesh', INVIA_MESH_DESC, ToolType.WAIT)
async def invia_messaggio_mesh(conn, messaggio: str, destinatario: str = None):
    """Invia messaggio alla rete mesh LoRa"""

    if not messaggio:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Nessun messaggio da inviare",
            response="Cosa vuoi che trasmetta sulla rete mesh?"
        )

    try:
        handler = await get_handler()

        to_node = "broadcast"
        if destinatario:
            # Cerca nodo per nome
            nodes = handler.get_nodes() if hasattr(handler, 'get_nodes') else await handler.get_nodes()
            for node in nodes:
                if destinatario.lower() in node.short_name.lower() or destinatario.lower() in node.long_name.lower():
                    to_node = node.node_id
                    break

        success = await handler.send_message(messaggio, to_node)

        if success:
            dest_text = f"a {destinatario}" if destinatario else "a tutti"
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"✅ Messaggio inviato {dest_text}: {messaggio}",
                response=f"Ok! Ho trasmesso il messaggio {dest_text} sulla rete mesh."
            )
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result="❌ Errore invio messaggio",
                response="Mi dispiace, non sono riuscito a trasmettere il messaggio. Controlla la connessione mesh."
            )

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore invia_messaggio_mesh: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"Errore: {e}",
            response="C'è stato un problema con la rete mesh. Riprova più tardi."
        )


LEGGI_MESH_DESC = {
    "type": "function",
    "function": {
        "name": "leggi_messaggi_mesh",
        "description": (
            "读取LoRa网状消息 / Legge i messaggi ricevuti dalla rete mesh LoRa. "
            "Use when: 'leggi messaggi mesh', 'ci sono messaggi lora', 'cosa hanno scritto', "
            "'messaggi radio', 'nuovi messaggi mesh', 'chi ha scritto'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "solo_nuovi": {
                    "type": "boolean",
                    "description": "Se leggere solo i messaggi non letti"
                }
            },
            "required": []
        }
    }
}

@register_function('leggi_messaggi_mesh', LEGGI_MESH_DESC, ToolType.WAIT)
async def leggi_messaggi_mesh(conn, solo_nuovi: bool = True):
    """Legge messaggi dalla rete mesh"""

    try:
        handler = await get_handler()

        if hasattr(handler, 'get_unread_messages'):
            messages = handler.get_unread_messages() if solo_nuovi else _message_queue
        else:
            messages = await handler.get_messages()
            if solo_nuovi:
                messages = [m for m in messages if not m.is_read]

        if not messages:
            return ActionResponse(
                action=Action.RESPONSE,
                result="📭 Nessun nuovo messaggio",
                response="Non ci sono nuovi messaggi sulla rete mesh."
            )

        # Formatta messaggi
        result = f"📬 **{len(messages)} messaggi mesh:**\n\n"
        spoken_parts = []

        for msg in messages[-5:]:  # Ultimi 5
            time_str = msg.timestamp.strftime("%H:%M")
            result += f"• [{time_str}] **{msg.from_name}**: {msg.text}\n"
            spoken_parts.append(f"{msg.from_name} dice: {msg.text}")

        # Segna come letti
        if hasattr(handler, 'mark_messages_read'):
            handler.mark_messages_read()

        spoken = "Hai " + str(len(messages)) + " messaggi. " + ". ".join(spoken_parts[:3])

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore leggi_messaggi_mesh: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"Errore: {e}",
            response="Non riesco a leggere i messaggi mesh. Controlla la connessione."
        )


NODI_VICINI_DESC = {
    "type": "function",
    "function": {
        "name": "nodi_mesh_vicini",
        "description": (
            "附近的LoRa节点 / Mostra i nodi mesh LoRa vicini e la loro distanza. "
            "Use when: 'nodi vicini', 'chi c'è sulla mesh', 'dispositivi lora', "
            "'quanti nodi vedi', 'a che distanza sono i nodi', 'stato rete mesh'"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

@register_function('nodi_mesh_vicini', NODI_VICINI_DESC, ToolType.WAIT)
async def nodi_mesh_vicini(conn):
    """Mostra nodi mesh vicini con distanza"""

    try:
        handler = await get_handler()

        if hasattr(handler, 'get_nodes'):
            if asyncio.iscoroutinefunction(handler.get_nodes):
                nodes = await handler.get_nodes()
            else:
                nodes = handler.get_nodes()
        else:
            nodes = []

        if not nodes:
            return ActionResponse(
                action=Action.RESPONSE,
                result="📡 Nessun nodo mesh rilevato",
                response="Non vedo nessun nodo sulla rete mesh al momento. Potrebbero essere fuori portata."
            )

        # Ordina per distanza (se disponibile) o per ultimo contatto
        nodes_sorted = sorted(
            nodes,
            key=lambda x: (x.distance_km if x.distance_km else 999, x.last_heard or datetime.min),
            reverse=False
        )

        result = f"📡 **{len(nodes_sorted)} nodi mesh rilevati:**\n\n"
        spoken_parts = []

        for node in nodes_sorted[:10]:  # Max 10 nodi
            status = "🟢" if node.is_online else "🔴"
            dist = f"{node.distance_km:.1f} km" if node.distance_km else "distanza sconosciuta"
            snr = f"SNR: {node.snr:.1f}dB" if node.snr else ""
            last = node.last_heard.strftime("%H:%M") if node.last_heard else "mai"

            result += f"{status} **{node.long_name}** ({node.short_name})\n"
            result += f"   📍 {dist} {snr} | Ultimo: {last}\n\n"

            spoken_parts.append(f"{node.long_name} a {dist}")

        spoken = f"Vedo {len(nodes_sorted)} nodi. " + ", ".join(spoken_parts[:4])
        if len(nodes_sorted) > 4:
            spoken += f" e altri {len(nodes_sorted) - 4}."

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore nodi_mesh_vicini: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"Errore: {e}",
            response="Non riesco a vedere i nodi mesh. Controlla la connessione al satellite."
        )


# ============ INTENT PATTERNS (da aggiungere a intent_llm.py) ============
"""
# ============ MESHTASTIC / LORA MESH ============
if match_any(['messaggio mesh', 'manda lora', 'trasmetti mesh', 'invia mesh',
              'scrivi mesh', 'dì sulla mesh', 'messaggio radio']):
    # Estrai messaggio
    msg_match = re.search(r'(?:mesh|lora|radio)\s+(.+?)$', text_lower)
    messaggio = msg_match.group(1) if msg_match else ""
    return f'{{"function_call": {{"name": "invia_messaggio_mesh", "arguments": {{"messaggio": "{messaggio}"}}}}}}'

if match_any(['leggi mesh', 'messaggi mesh', 'messaggi lora', 'cosa hanno scritto',
              'nuovi messaggi radio', 'chi ha scritto mesh']):
    return '{"function_call": {"name": "leggi_messaggi_mesh"}}'

if match_any(['nodi vicini', 'nodi mesh', 'chi c\'è sulla mesh', 'dispositivi lora',
              'quanti nodi', 'distanza nodi', 'stato mesh', 'rete mesh']):
    return '{"function_call": {"name": "nodi_mesh_vicini"}}'
"""


# ============ ESP-NOW BRIDGE (alternativa a MQTT) ============
"""
Se si vuole usare ESP-NOW invece di MQTT:

1. Il chatbot ESP32 deve includere codice ESP-NOW per comunicare direttamente
   con il satellite, senza passare dal server

2. Il satellite ESP32-S3 deve:
   - Avere ESP-NOW attivo
   - Fare da bridge tra ESP-NOW e Meshtastic
   - Inoltrare messaggi vocali → LoRa e LoRa → chatbot

3. Codice Arduino per satellite:

   #include <esp_now.h>
   #include <WiFi.h>

   // MAC address del chatbot principale
   uint8_t chatbotMAC[] = {0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX};

   void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
       // Messaggio ricevuto dal chatbot
       String msg = String((char*)data);
       // Invia a Meshtastic via Serial
       Serial1.println(msg);
   }

   void onMeshtasticMessage(String msg) {
       // Messaggio ricevuto da Meshtastic
       // Inoltra al chatbot via ESP-NOW
       esp_now_send(chatbotMAC, (uint8_t*)msg.c_str(), msg.length());
   }

4. Pro ESP-NOW:
   - Nessun server necessario
   - Bassa latenza
   - Funziona anche senza WiFi infrastructure

5. Contro ESP-NOW:
   - Range limitato (~100m)
   - Serve modifica firmware chatbot
   - Più complesso da debuggare
"""


# ============ CONFIG EXAMPLE ============
"""
# docker-compose.yml - Aggiungi variabili ambiente:

services:
  xiaozhi-server:
    environment:
      - MESHTASTIC_MODE=mqtt          # o "http"
      - MQTT_BROKER=192.168.1.100     # IP del broker MQTT
      - MQTT_PORT=1883
      - MQTT_TOPIC=meshtastic
      # Oppure per HTTP:
      - MESHTASTIC_HTTP=http://192.168.1.101:80

# Per MQTT, il satellite Meshtastic deve avere MQTT gateway abilitato:
# meshtastic --set mqtt.enabled true
# meshtastic --set mqtt.address mqtt://192.168.1.100:1883
"""
