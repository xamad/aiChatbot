"""
================================================================================
DRAFT - HYBRID MESH GATEWAY
================================================================================

Architettura ibrida per sensori indoor (ESP-NOW) e outdoor (LoRa):

INDOOR (ESP-NOW Mesh):
- Comunicazione diretta tra ESP32 senza WiFi infrastructure
- Range: ~50-100m attraverso muri
- Latenza: <10ms
- Consumo: molto basso, ideale per batteria
- Nessuna dipendenza da router

OUTDOOR (LoRa Mesh):
- Lungo raggio: 1-15+ km
- Meshtastic o LoRa raw
- Deep sleep per mesi di batteria
- Ideale per: serra, apiario, garage remoto, trekking

GATEWAY (ESP32 centrale):
- Connesso al server Xiaozhi via WiFi/MQTT
- Master ESP-NOW per rete indoor
- Bridge LoRa per rete outdoor
- Unico dispositivo che richiede WiFi!

================================================================================
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass, field
from enum import Enum
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# File persistenza
DATA_FILE = Path("/tmp/xiaozhi_hybrid_mesh.json")
ALLARMI_FILE = Path("/tmp/xiaozhi_mesh_allarmi.json")

# MQTT al gateway
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_SENSORI = "mesh/sensori"      # Gateway pubblica qui
MQTT_TOPIC_COMANDI = "mesh/comandi"       # Server pubblica qui
MQTT_TOPIC_ALLARMI = "mesh/allarmi"       # Allarmi real-time

# ============================================================================
# ENUMS E DATA CLASSES
# ============================================================================

class TipoRete(Enum):
    ESPNOW = "espnow"      # Indoor mesh
    LORA = "lora"          # Outdoor long range
    WIFI = "wifi"          # Fallback diretto


class StatoNodo(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SLEEPING = "sleeping"
    LOW_BATTERY = "low_battery"


@dataclass
class NodoSensore:
    """Rappresenta un nodo sensore nella rete"""
    id: str
    nome: str
    stanza: str
    tipo_rete: TipoRete
    mac_address: str
    sensori: List[str]
    attuatori: List[str] = field(default_factory=list)

    # Stato
    stato: StatoNodo = StatoNodo.OFFLINE
    batteria: Optional[int] = None  # %
    rssi: Optional[int] = None      # Segnale
    ultimo_contatto: Optional[datetime] = None

    # Configurazione
    intervallo_report: int = 30     # Secondi (ESP-NOW) o minuti (LoRa)
    sleep_enabled: bool = False

    def is_indoor(self) -> bool:
        return self.tipo_rete == TipoRete.ESPNOW

    def is_outdoor(self) -> bool:
        return self.tipo_rete == TipoRete.LORA


@dataclass
class LetturaSensore:
    """Singola lettura da un sensore"""
    nodo_id: str
    tipo: str
    valore: Any
    unita: str
    timestamp: datetime
    qualita: int = 100  # 0-100, qualità segnale/lettura


# ============================================================================
# REGISTRO NODI - CONFIGURAZIONE RETE
# ============================================================================

# Definizione di tutti i nodi della rete
REGISTRO_NODI: Dict[str, NodoSensore] = {

    # ========== INDOOR - ESP-NOW MESH ==========

    "cucina": NodoSensore(
        id="cucina",
        nome="Sensori Cucina",
        stanza="cucina",
        tipo_rete=TipoRete.ESPNOW,
        mac_address="AA:BB:CC:DD:EE:01",
        sensori=["temperatura", "umidita", "gas", "fumo"],
        attuatori=["ventola_cappa"],
        intervallo_report=30
    ),

    "soggiorno": NodoSensore(
        id="soggiorno",
        nome="Sensori Soggiorno",
        stanza="soggiorno",
        tipo_rete=TipoRete.ESPNOW,
        mac_address="AA:BB:CC:DD:EE:02",
        sensori=["temperatura", "umidita", "co2", "presenza", "luce"],
        attuatori=["luce_principale", "luce_lettura"],
        intervallo_report=30
    ),

    "camera": NodoSensore(
        id="camera",
        nome="Camera da Letto",
        stanza="camera",
        tipo_rete=TipoRete.ESPNOW,
        mac_address="AA:BB:CC:DD:EE:03",
        sensori=["temperatura", "umidita", "presenza", "luce"],
        attuatori=["luce_comodino"],
        intervallo_report=60  # Meno frequente
    ),

    "camera_bimbo": NodoSensore(
        id="camera_bimbo",
        nome="Cameretta Bimbo",
        stanza="cameretta",
        tipo_rete=TipoRete.ESPNOW,
        mac_address="AA:BB:CC:DD:EE:04",
        sensori=["temperatura", "umidita", "presenza", "rumore", "respiro"],
        attuatori=["luce_notte", "ninna_nanna"],
        intervallo_report=10  # Più frequente per sicurezza
    ),

    "bagno": NodoSensore(
        id="bagno",
        nome="Bagno",
        stanza="bagno",
        tipo_rete=TipoRete.ESPNOW,
        mac_address="AA:BB:CC:DD:EE:05",
        sensori=["temperatura", "umidita", "presenza"],
        attuatori=["ventola"],
        intervallo_report=30
    ),

    "ingresso": NodoSensore(
        id="ingresso",
        nome="Ingresso",
        stanza="ingresso",
        tipo_rete=TipoRete.ESPNOW,
        mac_address="AA:BB:CC:DD:EE:06",
        sensori=["porta", "movimento", "campanello"],
        attuatori=["luce_ingresso"],
        intervallo_report=5  # Reattivo
    ),

    # ========== OUTDOOR - LoRa MESH ==========

    "garage": NodoSensore(
        id="garage",
        nome="Garage",
        stanza="garage",
        tipo_rete=TipoRete.LORA,
        mac_address="AA:BB:CC:DD:EE:10",
        sensori=["porta", "movimento", "temperatura", "fumo", "distanza_auto"],
        attuatori=["porta_garage", "luce"],
        intervallo_report=5,  # Minuti per LoRa
        sleep_enabled=False   # Sempre attivo per porta
    ),

    "serra": NodoSensore(
        id="serra",
        nome="Serra Orto",
        stanza="esterno",
        tipo_rete=TipoRete.LORA,
        mac_address="AA:BB:CC:DD:EE:11",
        sensori=["temperatura", "umidita", "umidita_terreno_1", "umidita_terreno_2",
                "luce_par", "livello_acqua"],
        attuatori=["pompa_1", "pompa_2", "ventola"],
        intervallo_report=10,  # Minuti
        sleep_enabled=True
    ),

    "apiario": NodoSensore(
        id="apiario",
        nome="Apiario",
        stanza="esterno",
        tipo_rete=TipoRete.LORA,
        mac_address="AA:BB:CC:DD:EE:12",
        sensori=["peso_arnia_1", "peso_arnia_2", "temperatura_arnia_1",
                "temperatura_arnia_2", "umidita"],
        attuatori=[],
        intervallo_report=30,  # Minuti
        sleep_enabled=True
    ),

    "meteo": NodoSensore(
        id="meteo",
        nome="Stazione Meteo",
        stanza="esterno",
        tipo_rete=TipoRete.LORA,
        mac_address="AA:BB:CC:DD:EE:13",
        sensori=["temperatura", "umidita", "pressione", "vento_vel", "vento_dir",
                "pioggia", "uv", "luce", "pm25"],
        attuatori=[],
        intervallo_report=5,
        sleep_enabled=False  # Sempre attivo
    ),

    "pollaio": NodoSensore(
        id="pollaio",
        nome="Pollaio",
        stanza="esterno",
        tipo_rete=TipoRete.LORA,
        mac_address="AA:BB:CC:DD:EE:14",
        sensori=["porta", "movimento", "temperatura", "luce"],
        attuatori=["porta_pollaio", "luce"],
        intervallo_report=15,
        sleep_enabled=True
    ),

    # ========== VEICOLI - LoRa MOBILE ==========

    "auto": NodoSensore(
        id="auto",
        nome="Auto",
        stanza="mobile",
        tipo_rete=TipoRete.LORA,
        mac_address="AA:BB:CC:DD:EE:20",
        sensori=["gps_lat", "gps_lon", "velocita", "batteria_12v", "obd_rpm",
                "obd_temp", "obd_fuel"],
        attuatori=[],
        intervallo_report=1,  # Minuto quando in movimento
        sleep_enabled=True    # Deep sleep quando ferma
    ),
}

# ============================================================================
# UNITÀ DI MISURA
# ============================================================================

UNITA = {
    "temperatura": "°C",
    "umidita": "%",
    "umidita_terreno": "%",
    "pressione": "hPa",
    "co2": "ppm",
    "gas": "ppm",
    "fumo": "ppm",
    "pm25": "µg/m³",
    "luce": "lux",
    "luce_par": "µmol/m²/s",
    "uv": "index",
    "vento_vel": "km/h",
    "vento_dir": "°",
    "pioggia": "mm",
    "peso": "kg",
    "distanza": "cm",
    "batteria": "%",
    "rssi": "dBm",
    "velocita": "km/h",
}

# ============================================================================
# STORAGE
# ============================================================================

def _load_data() -> Dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except:
            pass
    return {"letture": {}, "ultimo_update": {}}

def _save_data(data: Dict):
    DATA_FILE.write_text(json.dumps(data, indent=2, default=str))

def _registra_lettura(nodo_id: str, tipo: str, valore: Any):
    """Registra lettura sensore (chiamato dal gateway via MQTT)"""
    data = _load_data()
    key = f"{nodo_id}_{tipo}"
    now = datetime.now().isoformat()

    if key not in data["letture"]:
        data["letture"][key] = []

    data["letture"][key].append({"v": valore, "t": now})
    data["letture"][key] = data["letture"][key][-500:]  # Max 500 per sensore
    data["ultimo_update"][key] = now

    _save_data(data)

    # Aggiorna stato nodo
    if nodo_id in REGISTRO_NODI:
        REGISTRO_NODI[nodo_id].stato = StatoNodo.ONLINE
        REGISTRO_NODI[nodo_id].ultimo_contatto = datetime.now()

def _get_lettura(nodo_id: str, tipo: str) -> Optional[LetturaSensore]:
    """Ottiene ultima lettura di un sensore"""
    data = _load_data()
    key = f"{nodo_id}_{tipo}"

    if key in data["letture"] and data["letture"][key]:
        ultima = data["letture"][key][-1]
        return LetturaSensore(
            nodo_id=nodo_id,
            tipo=tipo,
            valore=ultima["v"],
            unita=UNITA.get(tipo, ""),
            timestamp=datetime.fromisoformat(ultima["t"])
        )
    return None

# ============================================================================
# MQTT HANDLER (riceve dati dal gateway)
# ============================================================================

"""
Il Gateway ESP32 pubblica su MQTT i dati in questo formato:

Topic: mesh/sensori/{nodo_id}/{tipo_sensore}
Payload: {"value": 23.5, "battery": 85, "rssi": -45}

Topic: mesh/allarmi
Payload: {"nodo": "cucina", "tipo": "gas", "valore": 1500, "messaggio": "Gas alto!"}

Per inviare comandi al gateway:
Topic: mesh/comandi
Payload: {"nodo": "soggiorno", "attuatore": "luce_principale", "azione": "on"}
"""

class MQTTMeshHandler:
    """Gestisce comunicazione MQTT con il gateway"""

    def __init__(self):
        self.client = None
        self.connected = False

    async def connect(self):
        try:
            import paho.mqtt.client as mqtt

            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message

            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()

            logger.bind(tag=TAG).info("Connesso a MQTT per mesh gateway")
            return True
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore MQTT: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            client.subscribe(f"{MQTT_TOPIC_SENSORI}/#")
            client.subscribe(MQTT_TOPIC_ALLARMI)
            logger.bind(tag=TAG).info("Sottoscritto a topic mesh")

    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())

            # Parsing: mesh/sensori/{nodo_id}/{tipo}
            if topic.startswith(MQTT_TOPIC_SENSORI):
                parts = topic.split("/")
                if len(parts) >= 4:
                    nodo_id = parts[2]
                    tipo = parts[3]
                    valore = payload.get("value", payload.get("v"))

                    _registra_lettura(nodo_id, tipo, valore)

                    # Aggiorna info nodo
                    if nodo_id in REGISTRO_NODI:
                        if "battery" in payload:
                            REGISTRO_NODI[nodo_id].batteria = payload["battery"]
                        if "rssi" in payload:
                            REGISTRO_NODI[nodo_id].rssi = payload["rssi"]

            # Allarmi
            elif topic == MQTT_TOPIC_ALLARMI:
                self._handle_allarme(payload)

        except Exception as e:
            logger.bind(tag=TAG).warning(f"Errore parsing MQTT: {e}")

    def _handle_allarme(self, payload: dict):
        """Gestisce allarme ricevuto dal gateway"""
        nodo = payload.get("nodo", "sconosciuto")
        tipo = payload.get("tipo", "")
        valore = payload.get("valore", "")
        messaggio = payload.get("messaggio", f"Allarme {tipo} da {nodo}")

        logger.bind(tag=TAG).warning(f"ALLARME: {messaggio}")

        # TODO: Trigger notifica vocale al chatbot
        # speak_urgente(messaggio)

    def invia_comando(self, nodo_id: str, attuatore: str, azione: str) -> bool:
        """Invia comando a un attuatore"""
        if not self.connected:
            return False

        try:
            payload = {
                "nodo": nodo_id,
                "attuatore": attuatore,
                "azione": azione,
                "timestamp": datetime.now().isoformat()
            }

            self.client.publish(MQTT_TOPIC_COMANDI, json.dumps(payload))
            logger.bind(tag=TAG).info(f"Comando inviato: {nodo_id}/{attuatore} = {azione}")
            return True
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore invio comando: {e}")
            return False


# Handler globale
_mqtt_handler: Optional[MQTTMeshHandler] = None

async def get_mqtt_handler() -> MQTTMeshHandler:
    global _mqtt_handler
    if _mqtt_handler is None:
        _mqtt_handler = MQTTMeshHandler()
        await _mqtt_handler.connect()
    return _mqtt_handler

# ============================================================================
# FUNCTION DESCRIPTORS
# ============================================================================

LEGGI_SENSORE_MESH_DESC = {
    "type": "function",
    "function": {
        "name": "leggi_sensore_mesh",
        "description": (
            "Legge sensore dalla rete mesh (indoor ESP-NOW o outdoor LoRa). "
            "Use when: 'temperatura cucina', 'umidità serra', 'c'è qualcuno in soggiorno', "
            "'com'è l'orto', 'stato garage', 'peso arnie'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nodo": {
                    "type": "string",
                    "description": "ID nodo (cucina, soggiorno, camera, serra, garage, apiario, meteo, auto)"
                },
                "sensore": {
                    "type": "string",
                    "description": "Tipo sensore (temperatura, umidita, presenza, gas, porta, peso, ecc)"
                }
            },
            "required": ["nodo"]
        }
    }
}

STATO_RETE_DESC = {
    "type": "function",
    "function": {
        "name": "stato_rete_mesh",
        "description": (
            "Mostra stato di tutta la rete mesh (nodi online, batterie, segnale). "
            "Use when: 'stato rete', 'nodi online', 'batterie sensori', 'check sistema'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo_rete": {
                    "type": "string",
                    "enum": ["tutti", "indoor", "outdoor"],
                    "description": "Filtra per tipo rete"
                }
            },
            "required": []
        }
    }
}

PANORAMICA_CASA_DESC = {
    "type": "function",
    "function": {
        "name": "panoramica_casa_mesh",
        "description": (
            "Panoramica completa di tutti i sensori casa e esterni. "
            "Use when: 'com'è la situazione', 'stato casa', 'report completo', "
            "'panoramica', 'check tutto'"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

COMANDO_ATTUATORE_DESC = {
    "type": "function",
    "function": {
        "name": "comando_attuatore_mesh",
        "description": (
            "Controlla un attuatore nella rete mesh. "
            "Use when: 'accendi luce soggiorno', 'apri porta garage', "
            "'annaffia serra', 'attiva ventola bagno'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nodo": {
                    "type": "string",
                    "description": "ID nodo"
                },
                "attuatore": {
                    "type": "string",
                    "description": "Nome attuatore"
                },
                "azione": {
                    "type": "string",
                    "enum": ["on", "off", "toggle", "open", "close"],
                    "description": "Azione da eseguire"
                }
            },
            "required": ["nodo", "attuatore", "azione"]
        }
    }
}

# ============================================================================
# PLUGIN FUNCTIONS
# ============================================================================

@register_function('leggi_sensore_mesh', LEGGI_SENSORE_MESH_DESC, ToolType.WAIT)
async def leggi_sensore_mesh(conn, nodo: str, sensore: str = None):
    """Legge sensori da un nodo mesh"""

    nodo = nodo.lower().strip()

    # Trova nodo
    if nodo not in REGISTRO_NODI:
        nodi_disponibili = ", ".join(REGISTRO_NODI.keys())
        return ActionResponse(
            Action.RESPONSE,
            f"Nodo '{nodo}' non trovato. Disponibili: {nodi_disponibili}",
            f"Non conosco il nodo {nodo}. Ho: {nodi_disponibili}"
        )

    nodo_info = REGISTRO_NODI[nodo]
    rete = "🏠 ESP-NOW" if nodo_info.is_indoor() else "📡 LoRa"

    # Se sensore specificato, leggi solo quello
    if sensore:
        sensore = sensore.lower().strip()
        lettura = _get_lettura(nodo, sensore)

        if lettura:
            # Formatta risposta
            if sensore in ["presenza", "movimento", "porta"]:
                if sensore == "porta":
                    stato = "aperta" if lettura.valore else "chiusa"
                else:
                    stato = "rilevata" if lettura.valore else "nessuna"
                result = f"**{nodo_info.nome}** [{rete}]\n• {sensore}: {stato}"
                spoken = f"In {nodo}, {sensore} {stato}"
            else:
                result = f"**{nodo_info.nome}** [{rete}]\n• {sensore}: {lettura.valore}{lettura.unita}"
                spoken = f"In {nodo}, {sensore} è {lettura.valore} {lettura.unita}"

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            return ActionResponse(
                Action.RESPONSE,
                f"Nessun dato per {sensore} in {nodo}",
                f"Non ho dati recenti per {sensore} in {nodo}"
            )

    # Altrimenti leggi tutti i sensori del nodo
    result = f"# {nodo_info.nome} [{rete}]\n\n"
    spoken_parts = []

    for sens in nodo_info.sensori:
        lettura = _get_lettura(nodo, sens)
        if lettura:
            if sens in ["presenza", "movimento", "porta"]:
                stato = "✅" if lettura.valore else "❌"
                result += f"• {sens}: {stato}\n"
            else:
                result += f"• {sens}: {lettura.valore}{lettura.unita}\n"
                if sens == "temperatura":
                    spoken_parts.append(f"{lettura.valore} gradi")
                elif sens == "umidita":
                    spoken_parts.append(f"umidità {lettura.valore}%")
        else:
            result += f"• {sens}: N/D\n"

    # Info stato nodo
    if nodo_info.batteria:
        result += f"\n🔋 Batteria: {nodo_info.batteria}%"
    if nodo_info.rssi:
        result += f" | 📶 RSSI: {nodo_info.rssi}dBm"

    spoken = f"{nodo_info.nome}: " + ", ".join(spoken_parts) if spoken_parts else f"Ecco i dati di {nodo}"

    return ActionResponse(Action.RESPONSE, result, spoken)


@register_function('stato_rete_mesh', STATO_RETE_DESC, ToolType.WAIT)
async def stato_rete_mesh(conn, tipo_rete: str = "tutti"):
    """Mostra stato della rete mesh"""

    result = "# 📡 STATO RETE MESH\n\n"

    indoor_count = 0
    outdoor_count = 0
    offline_count = 0
    low_battery = []

    # Indoor
    if tipo_rete in ["tutti", "indoor"]:
        result += "## 🏠 INDOOR (ESP-NOW)\n"
        for nodo_id, nodo in REGISTRO_NODI.items():
            if nodo.is_indoor():
                indoor_count += 1
                stato_icon = "🟢" if nodo.stato == StatoNodo.ONLINE else "🔴"
                batt = f"🔋{nodo.batteria}%" if nodo.batteria else ""
                rssi = f"📶{nodo.rssi}dB" if nodo.rssi else ""

                result += f"{stato_icon} **{nodo.nome}** ({nodo.stanza}) {batt} {rssi}\n"

                if nodo.stato != StatoNodo.ONLINE:
                    offline_count += 1
                if nodo.batteria and nodo.batteria < 20:
                    low_battery.append(nodo.nome)
        result += "\n"

    # Outdoor
    if tipo_rete in ["tutti", "outdoor"]:
        result += "## 📡 OUTDOOR (LoRa)\n"
        for nodo_id, nodo in REGISTRO_NODI.items():
            if nodo.is_outdoor():
                outdoor_count += 1
                stato_icon = "🟢" if nodo.stato == StatoNodo.ONLINE else "🔴"
                sleep_icon = "💤" if nodo.sleep_enabled else ""
                batt = f"🔋{nodo.batteria}%" if nodo.batteria else ""

                result += f"{stato_icon} **{nodo.nome}** {sleep_icon} {batt}\n"

                if nodo.stato != StatoNodo.ONLINE:
                    offline_count += 1
                if nodo.batteria and nodo.batteria < 20:
                    low_battery.append(nodo.nome)
        result += "\n"

    # Riepilogo
    totale = indoor_count + outdoor_count
    online = totale - offline_count
    result += f"---\n**Totale**: {online}/{totale} online"

    if low_battery:
        result += f"\n⚠️ **Batteria bassa**: {', '.join(low_battery)}"

    spoken = f"Rete mesh: {online} nodi su {totale} online. "
    if low_battery:
        spoken += f"Attenzione, batteria bassa su {', '.join(low_battery)}."

    return ActionResponse(Action.RESPONSE, result, spoken)


@register_function('panoramica_casa_mesh', PANORAMICA_CASA_DESC, ToolType.WAIT)
async def panoramica_casa_mesh(conn):
    """Panoramica completa di tutti i sensori"""

    result = "# 🏠 PANORAMICA COMPLETA\n\n"
    spoken_parts = []
    problemi = []

    # Raggruppa per stanza
    stanze = {}
    for nodo_id, nodo in REGISTRO_NODI.items():
        stanza = nodo.stanza
        if stanza not in stanze:
            stanze[stanza] = []
        stanze[stanza].append((nodo_id, nodo))

    for stanza, nodi in stanze.items():
        rete_icon = "🏠" if nodi[0][1].is_indoor() else "📡"
        result += f"## {rete_icon} {stanza.upper()}\n"

        for nodo_id, nodo in nodi:
            # Temperatura
            temp = _get_lettura(nodo_id, "temperatura")
            if temp:
                result += f"🌡️ {temp.valore}°C "
                if stanza in ["cucina", "soggiorno", "camera"]:
                    spoken_parts.append(f"{stanza} {temp.valore} gradi")

            # Umidità
            hum = _get_lettura(nodo_id, "umidita")
            if hum:
                result += f"💧 {hum.valore}% "

            # Presenza
            pres = _get_lettura(nodo_id, "presenza")
            if pres:
                result += "👤 " if pres.valore else "👻 "

            # Gas/Fumo (problemi)
            gas = _get_lettura(nodo_id, "gas")
            if gas and gas.valore > 500:
                result += "⚠️ GAS! "
                problemi.append(f"gas alto in {stanza}")

            # Porta
            porta = _get_lettura(nodo_id, "porta")
            if porta:
                result += "🚪" if porta.valore else "🔒"

            result += "\n"

        result += "\n"

    # Meteo esterno
    meteo_temp = _get_lettura("meteo", "temperatura")
    meteo_hum = _get_lettura("meteo", "umidita")
    pioggia = _get_lettura("meteo", "pioggia")

    if meteo_temp:
        result += f"## ☁️ METEO ESTERNO\n"
        result += f"🌡️ {meteo_temp.valore}°C "
        if meteo_hum:
            result += f"💧 {meteo_hum.valore}% "
        if pioggia and pioggia.valore > 0:
            result += f"🌧️ {pioggia.valore}mm"
        result += "\n"
        spoken_parts.append(f"fuori {meteo_temp.valore} gradi")

    # Spoken
    if problemi:
        spoken = f"Attenzione! {', '.join(problemi)}. "
    else:
        spoken = "Tutto ok. "

    spoken += ". ".join(spoken_parts[:4])

    return ActionResponse(Action.RESPONSE, result, spoken)


@register_function('comando_attuatore_mesh', COMANDO_ATTUATORE_DESC, ToolType.WAIT)
async def comando_attuatore_mesh(conn, nodo: str, attuatore: str, azione: str):
    """Invia comando a un attuatore"""

    nodo = nodo.lower().strip()
    attuatore = attuatore.lower().strip()
    azione = azione.lower().strip()

    # Verifica nodo
    if nodo not in REGISTRO_NODI:
        return ActionResponse(
            Action.RESPONSE,
            f"Nodo '{nodo}' non trovato",
            f"Non conosco il nodo {nodo}"
        )

    nodo_info = REGISTRO_NODI[nodo]

    # Verifica attuatore
    if attuatore not in nodo_info.attuatori:
        atts = ", ".join(nodo_info.attuatori) if nodo_info.attuatori else "nessuno"
        return ActionResponse(
            Action.RESPONSE,
            f"Attuatore '{attuatore}' non trovato in {nodo}. Disponibili: {atts}",
            f"Non trovo l'attuatore {attuatore} in {nodo}"
        )

    # Invia comando
    handler = await get_mqtt_handler()
    success = handler.invia_comando(nodo, attuatore, azione)

    if success:
        azione_testo = {
            "on": "acceso",
            "off": "spento",
            "toggle": "invertito",
            "open": "aperto",
            "close": "chiuso"
        }.get(azione, azione)

        return ActionResponse(
            Action.RESPONSE,
            f"✅ {attuatore} in {nodo}: {azione_testo}",
            f"Ok, ho {azione_testo} {attuatore} in {nodo}"
        )
    else:
        return ActionResponse(
            Action.RESPONSE,
            f"❌ Errore invio comando a {nodo}",
            f"Non sono riuscito a comandare {attuatore}. Verifico la connessione."
        )


# ============================================================================
# AUTOMAZIONI INTELLIGENTI
# ============================================================================

AUTOMAZIONI = {
    "ventola_bagno_auto": {
        "trigger": {"nodo": "bagno", "sensore": "umidita", "condizione": ">", "soglia": 75},
        "azione": {"nodo": "bagno", "attuatore": "ventola", "comando": "on"},
        "reset": {"condizione": "<", "soglia": 60, "comando": "off"},
        "attiva": True
    },

    "luce_ingresso_presenza": {
        "trigger": {"nodo": "ingresso", "sensore": "movimento", "condizione": "=", "soglia": True},
        "condizione_extra": {"nodo": "ingresso", "sensore": "luce", "condizione": "<", "soglia": 50},
        "azione": {"nodo": "ingresso", "attuatore": "luce_ingresso", "comando": "on"},
        "timeout": 120,  # Spegni dopo 2 minuti senza movimento
        "attiva": True
    },

    "allarme_gas": {
        "trigger": {"nodo": "cucina", "sensore": "gas", "condizione": ">", "soglia": 800},
        "azione": "notifica_vocale_urgente",
        "messaggio": "Attenzione! Rilevato gas in cucina! Valore: {valore} ppm",
        "attiva": True
    },

    "irrigazione_serra": {
        "trigger": {"nodo": "serra", "sensore": "umidita_terreno_1", "condizione": "<", "soglia": 30},
        "condizione_extra": {"nodo": "meteo", "sensore": "pioggia", "condizione": "=", "soglia": 0},
        "orari": ["06:00-09:00", "18:00-21:00"],
        "azione": {"nodo": "serra", "attuatore": "pompa_1", "comando": "on"},
        "durata": 300,
        "attiva": True
    },

    "pollaio_alba_tramonto": {
        "trigger": "alba",
        "azione": {"nodo": "pollaio", "attuatore": "porta_pollaio", "comando": "open"},
        "attiva": True
    },
}


# ============================================================================
# FIRMWARE GATEWAY ESP32
# ============================================================================

FIRMWARE_GATEWAY = """
// ============================================================
// FIRMWARE GATEWAY ESP32
// WiFi + ESP-NOW Master + LoRa Bridge
// ============================================================

#include <WiFi.h>
#include <esp_now.h>
#include <PubSubClient.h>
#include <LoRa.h>
#include <ArduinoJson.h>

// WiFi per connessione a MQTT
const char* ssid = "TUO_SSID";
const char* password = "TUA_PASSWORD";
const char* mqtt_server = "IP_XIAOZHI_SERVER";

// LoRa pins (adatta al tuo modulo)
#define LORA_SCK 5
#define LORA_MISO 19
#define LORA_MOSI 27
#define LORA_SS 18
#define LORA_RST 14
#define LORA_DIO0 26

WiFiClient espClient;
PubSubClient mqtt(espClient);

// Struttura dati ESP-NOW
typedef struct {
    char nodo_id[16];
    char sensor[16];
    float value;
    uint8_t battery;
    int8_t rssi;
} SensorData;

// ============ SETUP ============

void setup() {
    Serial.begin(115200);

    // 1. WiFi per MQTT
    WiFi.mode(WIFI_AP_STA);  // AP+STA per ESP-NOW + WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }
    Serial.println("WiFi connected");

    // 2. MQTT
    mqtt.setServer(mqtt_server, 1883);
    mqtt.setCallback(mqttCallback);
    reconnectMQTT();

    // 3. ESP-NOW
    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW init failed");
        return;
    }
    esp_now_register_recv_cb(onEspNowReceive);
    Serial.println("ESP-NOW ready");

    // 4. LoRa
    SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
    LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
    if (!LoRa.begin(868E6)) {  // 868 MHz per Europa
        Serial.println("LoRa init failed");
    } else {
        LoRa.setSpreadingFactor(10);
        LoRa.setSignalBandwidth(125E3);
        Serial.println("LoRa ready");
    }
}

// ============ ESP-NOW CALLBACK ============

void onEspNowReceive(const uint8_t *mac, const uint8_t *data, int len) {
    SensorData* pkt = (SensorData*)data;

    // Forward to MQTT
    char topic[64];
    snprintf(topic, sizeof(topic), "mesh/sensori/%s/%s", pkt->nodo_id, pkt->sensor);

    StaticJsonDocument<128> doc;
    doc["value"] = pkt->value;
    doc["battery"] = pkt->battery;
    doc["rssi"] = pkt->rssi;

    char payload[128];
    serializeJson(doc, payload);
    mqtt.publish(topic, payload);

    Serial.printf("ESP-NOW: %s/%s = %.2f\\n", pkt->nodo_id, pkt->sensor, pkt->value);
}

// ============ LORA RECEIVE ============

void checkLoRa() {
    int packetSize = LoRa.parsePacket();
    if (packetSize) {
        String incoming = "";
        while (LoRa.available()) {
            incoming += (char)LoRa.read();
        }

        // Parse JSON: {"n":"serra","s":"temp","v":25.5}
        StaticJsonDocument<256> doc;
        if (deserializeJson(doc, incoming) == DeserializationError::Ok) {
            const char* nodo = doc["n"];
            const char* sensor = doc["s"];
            float value = doc["v"];

            char topic[64];
            snprintf(topic, sizeof(topic), "mesh/sensori/%s/%s", nodo, sensor);

            char payload[64];
            snprintf(payload, sizeof(payload), "{\"value\":%.2f,\"rssi\":%d}",
                    value, LoRa.packetRssi());

            mqtt.publish(topic, payload);
            Serial.printf("LoRa: %s/%s = %.2f\\n", nodo, sensor, value);
        }
    }
}

// ============ MQTT CALLBACK (comandi) ============

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    // mesh/comandi -> {"nodo":"soggiorno","attuatore":"luce","azione":"on"}

    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, payload, length) == DeserializationError::Ok) {
        const char* nodo = doc["nodo"];
        const char* attuatore = doc["attuatore"];
        const char* azione = doc["azione"];

        // Determina se indoor (ESP-NOW) o outdoor (LoRa)
        // TODO: lookup tabella nodi

        // Se indoor: invia via ESP-NOW
        // sendEspNowCommand(nodo, attuatore, azione);

        // Se outdoor: invia via LoRa
        // sendLoRaCommand(nodo, attuatore, azione);
    }
}

// ============ LOOP ============

void loop() {
    if (!mqtt.connected()) reconnectMQTT();
    mqtt.loop();

    checkLoRa();

    // Heartbeat ogni 30 sec
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 30000) {
        mqtt.publish("mesh/gateway/status", "online");
        lastHB = millis();
    }
}

void reconnectMQTT() {
    while (!mqtt.connected()) {
        if (mqtt.connect("mesh_gateway")) {
            mqtt.subscribe("mesh/comandi");
        } else {
            delay(5000);
        }
    }
}
"""

FIRMWARE_NODO_ESPNOW = """
// ============================================================
// FIRMWARE NODO ESP-NOW (Indoor)
// Sensori + invio dati al gateway
// ============================================================

#include <esp_now.h>
#include <WiFi.h>
#include <DHT.h>

// MAC del gateway - MODIFICARE!
uint8_t gatewayMAC[] = {0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX};

const char* NODO_ID = "cucina";  // Cambia per ogni nodo

#define DHT_PIN 4
DHT dht(DHT_PIN, DHT22);

typedef struct {
    char nodo_id[16];
    char sensor[16];
    float value;
    uint8_t battery;
    int8_t rssi;
} SensorData;

SensorData data;

void setup() {
    Serial.begin(115200);
    dht.begin();

    WiFi.mode(WIFI_STA);

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW failed");
        return;
    }

    esp_now_peer_info_t peerInfo;
    memcpy(peerInfo.peer_addr, gatewayMAC, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    esp_now_add_peer(&peerInfo);

    strcpy(data.nodo_id, NODO_ID);
    data.battery = 100;  // TODO: leggere da ADC
}

void sendData(const char* sensor, float value) {
    strcpy(data.sensor, sensor);
    data.value = value;
    data.rssi = WiFi.RSSI();

    esp_now_send(gatewayMAC, (uint8_t*)&data, sizeof(data));
}

void loop() {
    float temp = dht.readTemperature();
    float hum = dht.readHumidity();

    if (!isnan(temp)) sendData("temperatura", temp);
    if (!isnan(hum)) sendData("umidita", hum);

    delay(30000);  // 30 secondi

    // Oppure deep sleep per batteria:
    // esp_deep_sleep(30 * 1000000);
}
"""

FIRMWARE_NODO_LORA = """
// ============================================================
// FIRMWARE NODO LoRa (Outdoor)
// Deep sleep + invio periodico
// ============================================================

#include <LoRa.h>
#include <ArduinoJson.h>
#include <DHT.h>

// LoRa pins - adatta al modulo (es. TTGO LoRa32, Heltec)
#define LORA_SCK 5
#define LORA_MISO 19
#define LORA_MOSI 27
#define LORA_SS 18
#define LORA_RST 14
#define LORA_DIO0 26

const char* NODO_ID = "serra";

#define DHT_PIN 4
DHT dht(DHT_PIN, DHT22);

#define SOIL_PIN 34  // Sensore umidità terreno

void setup() {
    Serial.begin(115200);
    dht.begin();
    pinMode(SOIL_PIN, INPUT);

    SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
    LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);

    if (!LoRa.begin(868E6)) {
        Serial.println("LoRa failed");
        return;
    }

    LoRa.setSpreadingFactor(10);
    LoRa.setTxPower(17);
}

void sendLoRa(const char* sensor, float value) {
    StaticJsonDocument<64> doc;
    doc["n"] = NODO_ID;
    doc["s"] = sensor;
    doc["v"] = value;

    String json;
    serializeJson(doc, json);

    LoRa.beginPacket();
    LoRa.print(json);
    LoRa.endPacket();

    Serial.printf("Sent: %s\\n", json.c_str());
}

void loop() {
    float temp = dht.readTemperature();
    float hum = dht.readHumidity();
    int soil = map(analogRead(SOIL_PIN), 4095, 0, 0, 100);

    if (!isnan(temp)) sendLoRa("temperatura", temp);
    delay(100);
    if (!isnan(hum)) sendLoRa("umidita", hum);
    delay(100);
    sendLoRa("umidita_terreno_1", soil);

    // Deep sleep 10 minuti
    esp_sleep_enable_timer_wakeup(10 * 60 * 1000000);
    esp_deep_sleep_start();
}
"""


logger.bind(tag=TAG).info("DRAFT hybrid_mesh_gateway caricato (non attivo)")
