"""
================================================================================
DRAFT - SENSORI ESP32 SATELLITE
================================================================================

Questo file è un DRAFT per l'integrazione di ESP32 satellite con sensori.
NON APPLICARE direttamente - richiede valutazione e configurazione hardware.

ARCHITETTURA PROPOSTA:
----------------------
                    ┌─────────────────┐
                    │  Xiaozhi Server │
                    │   (chatbot AI)  │
                    └────────┬────────┘
                             │ MQTT / HTTP
                             │
              ┌──────────────┼──────────────┐
              │              │              │
    ┌─────────▼─────┐ ┌──────▼──────┐ ┌─────▼─────────┐
    │ ESP32 Cucina  │ │ ESP32 Soggio│ │ ESP32 Esterno │
    │ - DHT22 temp  │ │ - PIR motion│ │ - BMP280 meteo│
    │ - MQ-2 gas    │ │ - Luce LDR  │ │ - Pioggia     │
    │ - Porta reed  │ │ - CO2       │ │ - UV index    │
    └───────────────┘ └─────────────┘ └───────────────┘

COMUNICAZIONE:
- MQTT: topic sensori/{device_id}/{sensor_type}
- ESP-NOW: broadcast o peer-to-peer con MAC address
- HTTP: webhook POST al server

FUNZIONALITÀ:
1. leggi_sensore(stanza, tipo) - Legge valore attuale
2. stato_casa() - Panoramica tutti i sensori
3. storico_sensore(stanza, tipo, periodo) - Dati storici
4. imposta_allarme(stanza, tipo, soglia, condizione) - Alert automatici
5. disattiva_allarme(id_allarme) - Rimuove alert

REQUISITI:
- Broker MQTT (mosquitto o altro)
- ESP32 con firmware sensori (vedi esempio sotto)
- Opzionale: InfluxDB per storico dati

================================================================================
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# File per persistenza dati sensori e allarmi
SENSORI_DATA_FILE = Path("/tmp/xiaozhi_sensori_data.json")
ALLARMI_FILE = Path("/tmp/xiaozhi_sensori_allarmi.json")

# MQTT Configuration (da adattare)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_BASE = "sensori"
MQTT_USER = None
MQTT_PASS = None

# HTTP Webhook (alternativa a MQTT)
WEBHOOK_PORT = 8765

# Mappa dispositivi - DA CONFIGURARE CON I TUOI ESP32
DISPOSITIVI = {
    "cucina": {
        "id": "esp32_cucina",
        "mac": "AA:BB:CC:DD:EE:01",
        "sensori": ["temperatura", "umidita", "gas", "porta"],
        "descrizione": "Sensori cucina"
    },
    "soggiorno": {
        "id": "esp32_soggiorno",
        "mac": "AA:BB:CC:DD:EE:02",
        "sensori": ["temperatura", "umidita", "presenza", "luce", "co2"],
        "descrizione": "Sensori soggiorno con mmWave"
    },
    "camera": {
        "id": "esp32_camera",
        "mac": "AA:BB:CC:DD:EE:03",
        "sensori": ["temperatura", "umidita", "presenza", "sonno"],
        "descrizione": "Camera con radar presenza e monitoraggio sonno"
    },
    "bagno": {
        "id": "esp32_bagno",
        "mac": "AA:BB:CC:DD:EE:06",
        "sensori": ["temperatura", "umidita", "presenza", "ventola"],
        "descrizione": "Bagno con rilevamento presenza mmWave"
    },
    "esterno": {
        "id": "esp32_meteo",
        "mac": "AA:BB:CC:DD:EE:04",
        "sensori": ["temperatura", "umidita", "pressione", "pioggia", "vento_vel",
                   "vento_dir", "uv", "luce_lux", "pm25", "pm10"],
        "descrizione": "Stazione meteo completa"
    },
    "garage": {
        "id": "esp32_garage",
        "mac": "AA:BB:CC:DD:EE:05",
        "sensori": ["porta", "movimento", "fumo", "distanza"],
        "descrizione": "Garage con sensore parcheggio"
    },
    "cantina": {
        "id": "esp32_cantina",
        "mac": "AA:BB:CC:DD:EE:07",
        "sensori": ["temperatura", "umidita", "allagamento", "movimento"],
        "descrizione": "Cantina con sensore allagamento"
    }
}

# Tipi sensori con descrizioni dettagliate
TIPI_SENSORI = {
    # === TEMPERATURA & UMIDITÀ ===
    "temperatura": {"unita": "°C", "desc": "Temperatura ambiente", "hw": "DHT22/BME280/DS18B20"},
    "umidita": {"unita": "%", "desc": "Umidità relativa", "hw": "DHT22/BME280"},

    # === PRESENZA UMANA (mmWave radar) ===
    "presenza": {"unita": "", "desc": "Presenza umana (radar mmWave)", "hw": "LD2410/HLK-LD2450/DFRobot SEN0395"},
    "distanza_persona": {"unita": "cm", "desc": "Distanza persona rilevata", "hw": "LD2410B"},
    "sonno": {"unita": "", "desc": "Stato sonno (respiro)", "hw": "LD2410 sleep mode"},

    # === MOVIMENTO (PIR - meno preciso di mmWave) ===
    "movimento": {"unita": "", "desc": "Movimento (PIR)", "hw": "HC-SR501"},

    # === STAZIONE METEO ===
    "pressione": {"unita": "hPa", "desc": "Pressione atmosferica", "hw": "BME280/BMP280"},
    "pioggia": {"unita": "mm", "desc": "Precipitazioni", "hw": "Rain gauge tipping bucket"},
    "vento_vel": {"unita": "km/h", "desc": "Velocità vento", "hw": "Anemometro"},
    "vento_dir": {"unita": "°", "desc": "Direzione vento (0=N, 90=E)", "hw": "Banderuola"},
    "uv": {"unita": "index", "desc": "Indice UV", "hw": "VEML6075/GUVA-S12SD"},
    "luce_lux": {"unita": "lux", "desc": "Luminosità", "hw": "BH1750/TSL2561"},

    # === QUALITÀ ARIA ===
    "pm25": {"unita": "µg/m³", "desc": "Particolato PM2.5", "hw": "PMS5003/SDS011"},
    "pm10": {"unita": "µg/m³", "desc": "Particolato PM10", "hw": "PMS5003/SDS011"},
    "co2": {"unita": "ppm", "desc": "Anidride carbonica", "hw": "MH-Z19/SCD30"},
    "gas": {"unita": "ppm", "desc": "Gas combustibili", "hw": "MQ-2"},
    "fumo": {"unita": "ppm", "desc": "Fumo", "hw": "MQ-2"},

    # === STATO PORTE/FINESTRE ===
    "porta": {"unita": "", "desc": "Stato porta/finestra", "hw": "Reed switch"},
    "allagamento": {"unita": "", "desc": "Rilevamento acqua", "hw": "Water sensor"},

    # === ALTRI ===
    "distanza": {"unita": "cm", "desc": "Distanza oggetto", "hw": "HC-SR04/VL53L0X"},
    "luce": {"unita": "", "desc": "Luce on/off", "hw": "LDR"},
    "ventola": {"unita": "", "desc": "Stato ventola", "hw": "Relay feedback"}
}

# Unità di misura per tipo sensore
UNITA_SENSORI = {
    "temperatura": "°C",
    "umidita": "%",
    "pressione": "hPa",
    "gas": "ppm",
    "co2": "ppm",
    "luce": "lux",
    "uv": "index",
    "movimento": "",  # boolean
    "porta": "",      # boolean (aperta/chiusa)
    "pioggia": "",    # boolean
    "fumo": "ppm"
}

# Soglie di allarme predefinite
SOGLIE_DEFAULT = {
    "temperatura": {"min": 5, "max": 35, "critico_min": 0, "critico_max": 40},
    "umidita": {"min": 30, "max": 70, "critico_min": 20, "critico_max": 85},
    "gas": {"max": 1000, "critico_max": 2000},
    "co2": {"max": 1000, "critico_max": 2000},
    "fumo": {"max": 100, "critico_max": 300}
}

# ============================================================================
# STORAGE DATI
# ============================================================================

def _carica_dati_sensori() -> Dict:
    """Carica dati sensori da file."""
    if SENSORI_DATA_FILE.exists():
        try:
            return json.loads(SENSORI_DATA_FILE.read_text())
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore caricamento dati sensori: {e}")
    return {"letture": {}, "ultimo_aggiornamento": {}}

def _salva_dati_sensori(dati: Dict):
    """Salva dati sensori su file."""
    try:
        SENSORI_DATA_FILE.write_text(json.dumps(dati, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio dati sensori: {e}")

def _carica_allarmi() -> List[Dict]:
    """Carica configurazione allarmi."""
    if ALLARMI_FILE.exists():
        try:
            return json.loads(ALLARMI_FILE.read_text())
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore caricamento allarmi: {e}")
    return []

def _salva_allarmi(allarmi: List[Dict]):
    """Salva configurazione allarmi."""
    try:
        ALLARMI_FILE.write_text(json.dumps(allarmi, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio allarmi: {e}")

def _aggiorna_lettura(stanza: str, tipo: str, valore: Any):
    """Aggiorna lettura sensore (chiamato da MQTT/webhook)."""
    dati = _carica_dati_sensori()

    chiave = f"{stanza}_{tipo}"
    now = datetime.now().isoformat()

    if chiave not in dati["letture"]:
        dati["letture"][chiave] = []

    # Aggiungi nuova lettura (max 1000 per sensore)
    dati["letture"][chiave].append({"valore": valore, "timestamp": now})
    dati["letture"][chiave] = dati["letture"][chiave][-1000:]

    dati["ultimo_aggiornamento"][chiave] = now

    _salva_dati_sensori(dati)

    # Controlla allarmi
    _controlla_allarmi(stanza, tipo, valore)

def _controlla_allarmi(stanza: str, tipo: str, valore: Any):
    """Controlla se il valore attiva un allarme."""
    allarmi = _carica_allarmi()

    for allarme in allarmi:
        if allarme.get("stanza") == stanza and allarme.get("tipo") == tipo:
            if allarme.get("attivo", True):
                condizione = allarme.get("condizione", ">")
                soglia = allarme.get("soglia")

                triggered = False
                if condizione == ">" and valore > soglia:
                    triggered = True
                elif condizione == "<" and valore < soglia:
                    triggered = True
                elif condizione == "=" and valore == soglia:
                    triggered = True

                if triggered:
                    logger.bind(tag=TAG).warning(
                        f"ALLARME: {stanza}/{tipo} = {valore} {condizione} {soglia}"
                    )
                    # TODO: Inviare notifica vocale al chatbot

# ============================================================================
# MQTT HANDLER (da eseguire come servizio separato o in background)
# ============================================================================

"""
# Esempio di listener MQTT (richiede paho-mqtt)
# DA ESEGUIRE COME SERVIZIO SEPARATO

import paho.mqtt.client as mqtt

def on_message(client, userdata, msg):
    # Topic: sensori/{stanza}/{tipo}
    parts = msg.topic.split('/')
    if len(parts) >= 3:
        stanza = parts[1]
        tipo = parts[2]
        try:
            valore = json.loads(msg.payload.decode())
            _aggiorna_lettura(stanza, tipo, valore)
        except:
            pass

client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT)
client.subscribe(f"{MQTT_TOPIC_BASE}/#")
client.loop_forever()
"""

# ============================================================================
# HTTP WEBHOOK HANDLER (alternativa a MQTT)
# ============================================================================

"""
# Esempio di webhook HTTP (richiede aiohttp)
# DA INTEGRARE nel server principale o come servizio separato

from aiohttp import web

async def webhook_sensori(request):
    data = await request.json()
    # Formato: {"stanza": "cucina", "tipo": "temperatura", "valore": 22.5}
    stanza = data.get("stanza")
    tipo = data.get("tipo")
    valore = data.get("valore")

    if stanza and tipo and valore is not None:
        _aggiorna_lettura(stanza, tipo, valore)
        return web.json_response({"status": "ok"})

    return web.json_response({"status": "error"}, status=400)

app = web.Application()
app.router.add_post('/sensori', webhook_sensori)
web.run_app(app, port=WEBHOOK_PORT)
"""

# ============================================================================
# FUNCTION DESCRIPTORS
# ============================================================================

LEGGI_SENSORE_DESC = {
    "type": "function",
    "function": {
        "name": "leggi_sensore",
        "description": (
            "Legge il valore attuale di un sensore in una stanza specifica. "
            "Use when: 'che temperatura c'è', 'quanti gradi ci sono', "
            "'com'è l'umidità', 'c'è movimento', 'è aperta la porta'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stanza": {
                    "type": "string",
                    "description": "Stanza da controllare (cucina, soggiorno, camera, esterno, garage)"
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo sensore (temperatura, umidita, gas, movimento, porta, luce, co2, pressione, pioggia, uv, fumo)"
                }
            },
            "required": ["stanza", "tipo"]
        }
    }
}

STATO_CASA_DESC = {
    "type": "function",
    "function": {
        "name": "stato_casa",
        "description": (
            "Mostra panoramica di tutti i sensori della casa. "
            "Use when: 'stato della casa', 'come sta la casa', "
            "'situazione sensori', 'report casa', 'dammi un riepilogo'"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}

STORICO_SENSORE_DESC = {
    "type": "function",
    "function": {
        "name": "storico_sensore",
        "description": (
            "Mostra storico letture di un sensore. "
            "Use when: 'temperatura di ieri', 'storico umidità', "
            "'andamento temperatura', 'come è stata la temperatura'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stanza": {
                    "type": "string",
                    "description": "Stanza da controllare"
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo sensore"
                },
                "ore": {
                    "type": "integer",
                    "description": "Numero di ore indietro (default 24)"
                }
            },
            "required": ["stanza", "tipo"]
        }
    }
}

IMPOSTA_ALLARME_DESC = {
    "type": "function",
    "function": {
        "name": "imposta_allarme_sensore",
        "description": (
            "Imposta un allarme quando un sensore supera/scende sotto una soglia. "
            "Use when: 'avvisami se', 'allarme temperatura', "
            "'notificami quando', 'dimmi se la temperatura supera'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stanza": {
                    "type": "string",
                    "description": "Stanza da monitorare"
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo sensore"
                },
                "soglia": {
                    "type": "number",
                    "description": "Valore soglia"
                },
                "condizione": {
                    "type": "string",
                    "enum": [">", "<", "="],
                    "description": "Condizione: > (sopra), < (sotto), = (uguale)"
                }
            },
            "required": ["stanza", "tipo", "soglia", "condizione"]
        }
    }
}

# ============================================================================
# PLUGIN FUNCTIONS
# ============================================================================

@register_function('leggi_sensore', LEGGI_SENSORE_DESC, ToolType.WAIT)
def leggi_sensore(conn, stanza: str, tipo: str):
    """Legge il valore attuale di un sensore."""

    stanza = stanza.lower().strip()
    tipo = tipo.lower().strip()

    # Normalizza nomi
    stanza_map = {
        "salotto": "soggiorno",
        "sala": "soggiorno",
        "cameretta": "camera",
        "letto": "camera",
        "fuori": "esterno",
        "giardino": "esterno",
        "box": "garage"
    }
    stanza = stanza_map.get(stanza, stanza)

    tipo_map = {
        "temp": "temperatura",
        "gradi": "temperatura",
        "caldo": "temperatura",
        "freddo": "temperatura",
        "umido": "umidita",
        "moto": "movimento",
        "pir": "movimento"
    }
    tipo = tipo_map.get(tipo, tipo)

    # Verifica stanza valida
    if stanza not in DISPOSITIVI:
        stanze = ", ".join(DISPOSITIVI.keys())
        return ActionResponse(
            Action.RESPONSE,
            f"Stanza '{stanza}' non trovata. Stanze disponibili: {stanze}",
            f"Non conosco la stanza {stanza}. Ho sensori in: {stanze}"
        )

    # Verifica sensore disponibile in stanza
    if tipo not in DISPOSITIVI[stanza]["sensori"]:
        sensori = ", ".join(DISPOSITIVI[stanza]["sensori"])
        return ActionResponse(
            Action.RESPONSE,
            f"Sensore '{tipo}' non disponibile in {stanza}. Sensori: {sensori}",
            f"In {stanza} non ho il sensore di {tipo}. Ho: {sensori}"
        )

    # Leggi dati
    dati = _carica_dati_sensori()
    chiave = f"{stanza}_{tipo}"

    if chiave in dati["letture"] and dati["letture"][chiave]:
        ultima = dati["letture"][chiave][-1]
        valore = ultima["valore"]
        timestamp = ultima["timestamp"]
        unita = UNITA_SENSORI.get(tipo, "")

        # Formatta risposta
        if tipo in ["movimento", "porta", "pioggia"]:
            if tipo == "movimento":
                stato = "rilevato movimento" if valore else "nessun movimento"
            elif tipo == "porta":
                stato = "aperta" if valore else "chiusa"
            else:  # pioggia
                stato = "sta piovendo" if valore else "non piove"

            result = f"**{stanza.title()} - {tipo.title()}**: {stato}"
            spoken = f"In {stanza}, {stato}"
        else:
            result = f"**{stanza.title()} - {tipo.title()}**: {valore}{unita}"
            spoken = f"In {stanza} ci sono {valore} {unita if unita else ''}"

            if tipo == "temperatura":
                spoken = f"In {stanza} ci sono {valore} gradi"
            elif tipo == "umidita":
                spoken = f"In {stanza} l'umidità è al {valore} percento"

        # Aggiungi timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            tempo_fa = datetime.now() - dt
            if tempo_fa.seconds < 60:
                result += " (adesso)"
            elif tempo_fa.seconds < 3600:
                result += f" ({tempo_fa.seconds // 60} min fa)"
            else:
                result += f" ({tempo_fa.seconds // 3600} ore fa)"
        except:
            pass

        return ActionResponse(Action.RESPONSE, result, spoken)
    else:
        return ActionResponse(
            Action.RESPONSE,
            f"Nessun dato disponibile per {tipo} in {stanza}",
            f"Non ho dati recenti dal sensore di {tipo} in {stanza}"
        )

@register_function('stato_casa', STATO_CASA_DESC, ToolType.WAIT)
def stato_casa(conn):
    """Panoramica di tutti i sensori della casa."""

    dati = _carica_dati_sensori()

    result = "# 🏠 STATO DELLA CASA\n\n"
    spoken_parts = []
    problemi = []

    for stanza, config in DISPOSITIVI.items():
        result += f"## 📍 {stanza.title()}\n"
        stanza_spoken = []

        for tipo in config["sensori"]:
            chiave = f"{stanza}_{tipo}"
            unita = UNITA_SENSORI.get(tipo, "")

            if chiave in dati["letture"] and dati["letture"][chiave]:
                ultima = dati["letture"][chiave][-1]
                valore = ultima["valore"]

                if tipo in ["movimento", "porta", "pioggia"]:
                    if tipo == "movimento":
                        stato = "🔴 Movimento!" if valore else "⚪ Nessuno"
                        if valore:
                            problemi.append(f"movimento in {stanza}")
                    elif tipo == "porta":
                        stato = "🚪 Aperta" if valore else "🔒 Chiusa"
                        if valore:
                            problemi.append(f"porta {stanza} aperta")
                    else:
                        stato = "🌧️ Piove" if valore else "☀️ Sereno"
                    result += f"  • {tipo.title()}: {stato}\n"
                else:
                    result += f"  • {tipo.title()}: {valore}{unita}\n"

                    # Check soglie
                    if tipo in SOGLIE_DEFAULT:
                        soglie = SOGLIE_DEFAULT[tipo]
                        if "max" in soglie and valore > soglie["max"]:
                            result += f"    ⚠️ ALTO!\n"
                            problemi.append(f"{tipo} alta in {stanza}")
                        if "min" in soglie and valore < soglie["min"]:
                            result += f"    ⚠️ BASSO!\n"
                            problemi.append(f"{tipo} bassa in {stanza}")

                    if tipo == "temperatura":
                        stanza_spoken.append(f"{valore} gradi")
                    elif tipo == "umidita":
                        stanza_spoken.append(f"umidità {valore}%")
            else:
                result += f"  • {tipo.title()}: ❓ N/D\n"

        if stanza_spoken:
            spoken_parts.append(f"{stanza}: {', '.join(stanza_spoken)}")

        result += "\n"

    # Riepilogo vocale
    if problemi:
        spoken = f"Attenzione! {', '.join(problemi)}. "
    else:
        spoken = "Casa tutto ok. "

    if spoken_parts:
        spoken += ". ".join(spoken_parts[:3])  # Max 3 stanze per brevità

    return ActionResponse(Action.RESPONSE, result, spoken)

@register_function('storico_sensore', STORICO_SENSORE_DESC, ToolType.WAIT)
def storico_sensore(conn, stanza: str, tipo: str, ore: int = 24):
    """Mostra storico letture di un sensore."""

    stanza = stanza.lower().strip()
    tipo = tipo.lower().strip()

    dati = _carica_dati_sensori()
    chiave = f"{stanza}_{tipo}"

    if chiave not in dati["letture"] or not dati["letture"][chiave]:
        return ActionResponse(
            Action.RESPONSE,
            f"Nessun dato storico per {tipo} in {stanza}",
            f"Non ho dati storici per {tipo} in {stanza}"
        )

    # Filtra per periodo
    cutoff = datetime.now() - timedelta(hours=ore)
    letture = []

    for lettura in dati["letture"][chiave]:
        try:
            dt = datetime.fromisoformat(lettura["timestamp"])
            if dt >= cutoff:
                letture.append(lettura)
        except:
            pass

    if not letture:
        return ActionResponse(
            Action.RESPONSE,
            f"Nessun dato nelle ultime {ore} ore",
            f"Non ho dati delle ultime {ore} ore"
        )

    # Calcola statistiche
    valori = [l["valore"] for l in letture if isinstance(l["valore"], (int, float))]

    if valori:
        media = sum(valori) / len(valori)
        minimo = min(valori)
        massimo = max(valori)
        attuale = valori[-1]
        unita = UNITA_SENSORI.get(tipo, "")

        result = f"# 📊 Storico {tipo.title()} - {stanza.title()}\n\n"
        result += f"**Periodo**: ultime {ore} ore\n"
        result += f"**Letture**: {len(valori)}\n\n"
        result += f"• **Attuale**: {attuale}{unita}\n"
        result += f"• **Media**: {media:.1f}{unita}\n"
        result += f"• **Minimo**: {minimo}{unita}\n"
        result += f"• **Massimo**: {massimo}{unita}\n"

        if tipo == "temperatura":
            spoken = (f"In {stanza}, nelle ultime {ore} ore la temperatura "
                     f"è stata in media {media:.0f} gradi, "
                     f"con minimo {minimo} e massimo {massimo}")
        else:
            spoken = (f"In {stanza}, nelle ultime {ore} ore il {tipo} "
                     f"è stato in media {media:.1f}, "
                     f"con minimo {minimo} e massimo {massimo}")

        return ActionResponse(Action.RESPONSE, result, spoken)
    else:
        return ActionResponse(
            Action.RESPONSE,
            "Dati non numerici, impossibile calcolare statistiche",
            "I dati di questo sensore non sono numerici"
        )

@register_function('imposta_allarme_sensore', IMPOSTA_ALLARME_DESC, ToolType.WAIT)
def imposta_allarme_sensore(conn, stanza: str, tipo: str, soglia: float, condizione: str = ">"):
    """Imposta un allarme per un sensore."""

    stanza = stanza.lower().strip()
    tipo = tipo.lower().strip()

    if condizione not in [">", "<", "="]:
        condizione = ">"

    allarmi = _carica_allarmi()

    # Crea nuovo allarme
    nuovo_allarme = {
        "id": f"{stanza}_{tipo}_{len(allarmi)+1}",
        "stanza": stanza,
        "tipo": tipo,
        "soglia": soglia,
        "condizione": condizione,
        "attivo": True,
        "creato": datetime.now().isoformat()
    }

    allarmi.append(nuovo_allarme)
    _salva_allarmi(allarmi)

    unita = UNITA_SENSORI.get(tipo, "")
    cond_text = "sopra" if condizione == ">" else "sotto" if condizione == "<" else "uguale a"

    result = f"✅ Allarme impostato: {tipo} in {stanza} {cond_text} {soglia}{unita}"
    spoken = f"Ok, ti avviserò quando {tipo} in {stanza} sarà {cond_text} {soglia}"

    return ActionResponse(Action.RESPONSE, result, spoken)

# ============================================================================
# ESEMPIO FIRMWARE ESP32 (Arduino/PlatformIO)
# ============================================================================

FIRMWARE_BASIC = """
// ============================================================
// FIRMWARE BASE ESP32 - DHT22 + PIR + GAS
// Invia dati via MQTT al server Xiaozhi
// ============================================================

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

const char* ssid = "TUO_SSID";
const char* password = "TUA_PASSWORD";
const char* mqtt_server = "IP_SERVER_XIAOZHI";
const char* device_id = "esp32_cucina";

#define DHT_PIN 4
#define DHT_TYPE DHT22
#define PIR_PIN 5
#define GAS_PIN 34

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClient espClient;
PubSubClient mqtt(espClient);

void setup() {
    Serial.begin(115200);
    dht.begin();
    pinMode(PIR_PIN, INPUT);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) delay(500);
    mqtt.setServer(mqtt_server, 1883);
}

void loop() {
    if (!mqtt.connected()) reconnect();
    mqtt.loop();

    static unsigned long lastSend = 0;
    if (millis() - lastSend > 30000) {
        float temp = dht.readTemperature();
        float hum = dht.readHumidity();
        if (!isnan(temp)) sendValue("temperatura", temp);
        if (!isnan(hum)) sendValue("umidita", hum);
        sendValue("gas", analogRead(GAS_PIN));
        lastSend = millis();
    }
}

void sendValue(const char* tipo, float val) {
    char topic[64], payload[32];
    snprintf(topic, 64, "sensori/%s/%s", device_id, tipo);
    snprintf(payload, 32, "%.1f", val);
    mqtt.publish(topic, payload);
}

void reconnect() {
    while (!mqtt.connected()) {
        if (mqtt.connect(device_id)) break;
        delay(5000);
    }
}
"""

FIRMWARE_MMWAVE = """
// ============================================================
// FIRMWARE ESP32 CON SENSORE mmWave LD2410
// Rilevamento presenza umana ad alta precisione
// ============================================================

#include <WiFi.h>
#include <PubSubClient.h>
#include <ld2410.h>  // https://github.com/ncmreynolds/ld2410

const char* device_id = "esp32_soggiorno";

// LD2410 connesso a Serial2 (GPIO16=RX, GPIO17=TX)
#define LD2410_RX 16
#define LD2410_TX 17

ld2410 radar;
WiFiClient espClient;
PubSubClient mqtt(espClient);

bool lastPresence = false;
uint16_t lastDistance = 0;

void setup() {
    Serial.begin(115200);
    Serial2.begin(256000, SERIAL_8N1, LD2410_RX, LD2410_TX);

    if (radar.begin(Serial2)) {
        Serial.println("LD2410 inizializzato!");
    }

    // WiFi & MQTT setup...
}

void loop() {
    radar.read();
    mqtt.loop();

    // Invia solo se cambia stato presenza
    bool presence = radar.presenceDetected();
    if (presence != lastPresence) {
        sendValue("presenza", presence ? 1 : 0);
        lastPresence = presence;

        // Se persona rilevata, invia anche distanza
        if (presence) {
            uint16_t dist = radar.stationaryTargetDistance();
            if (dist == 0) dist = radar.movingTargetDistance();
            sendValue("distanza_persona", dist);
        }
    }

    // Invia distanza ogni 5 sec se presenza
    static unsigned long lastDist = 0;
    if (presence && millis() - lastDist > 5000) {
        uint16_t dist = radar.stationaryTargetDistance();
        if (dist == 0) dist = radar.movingTargetDistance();
        sendValue("distanza_persona", dist);
        lastDist = millis();
    }
}

// Per monitoraggio sonno (LD2410 con firmware sleep):
// radar.getBreathRate() - frequenza respiratoria
// radar.getHeartRate() - battito (solo alcuni modelli)
"""

FIRMWARE_WEATHER_STATION = """
// ============================================================
// STAZIONE METEO ESP32 COMPLETA
// BME280 + Rain Gauge + Anemometro + UV + PM2.5
// ============================================================

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_VEML6075.h>  // UV sensor
#include <PMS.h>                 // Particulate matter

const char* device_id = "esp32_meteo";

// I2C: BME280 + VEML6075
Adafruit_BME280 bme;
Adafruit_VEML6075 uv;

// PMS5003 su Serial2
PMS pms(Serial2);
PMS::DATA pmsData;

// Rain gauge (interrupt)
#define RAIN_PIN 25
volatile int rainTicks = 0;
float rainMmPerTick = 0.2794;  // Dipende dal modello

// Anemometro (interrupt)
#define WIND_PIN 26
volatile int windTicks = 0;
unsigned long lastWindCheck = 0;

void IRAM_ATTR rainISR() { rainTicks++; }
void IRAM_ATTR windISR() { windTicks++; }

void setup() {
    Serial.begin(115200);
    Serial2.begin(9600);  // PMS5003

    Wire.begin();
    bme.begin(0x76);
    uv.begin();

    pinMode(RAIN_PIN, INPUT_PULLUP);
    pinMode(WIND_PIN, INPUT_PULLUP);
    attachInterrupt(RAIN_PIN, rainISR, FALLING);
    attachInterrupt(WIND_PIN, windISR, FALLING);

    // WiFi & MQTT...
}

void loop() {
    mqtt.loop();

    static unsigned long lastSend = 0;
    if (millis() - lastSend > 60000) {  // Ogni minuto
        // BME280
        sendValue("temperatura", bme.readTemperature());
        sendValue("umidita", bme.readHumidity());
        sendValue("pressione", bme.readPressure() / 100.0);

        // UV Index
        float uvIndex = uv.readUVI();
        sendValue("uv", uvIndex);

        // Pioggia (reset counter)
        float rain = rainTicks * rainMmPerTick;
        sendValue("pioggia", rain);
        rainTicks = 0;

        // Vento (calcola km/h)
        unsigned long elapsed = millis() - lastWindCheck;
        float windKmh = (windTicks * 2.4) / (elapsed / 1000.0);  // Calibra!
        sendValue("vento_vel", windKmh);
        windTicks = 0;
        lastWindCheck = millis();

        // PM2.5 / PM10
        if (pms.read(pmsData)) {
            sendValue("pm25", pmsData.PM_AE_UG_2_5);
            sendValue("pm10", pmsData.PM_AE_UG_10_0);
        }

        lastSend = millis();
    }
}
"""

FIRMWARE_ESPNOW = """
// ============================================================
// ESP-NOW: Comunicazione diretta senza WiFi infrastructure
// Per sensori a batteria o aree senza copertura WiFi
// ============================================================

#include <esp_now.h>
#include <WiFi.h>

// MAC del gateway/server (ESP32 principale connesso a Xiaozhi)
uint8_t gatewayMAC[] = {0xXX, 0xXX, 0xXX, 0xXX, 0xXX, 0xXX};

typedef struct {
    char device_id[16];
    char sensor_type[16];
    float value;
} SensorPacket;

SensorPacket packet;

void setup() {
    WiFi.mode(WIFI_STA);

    if (esp_now_init() != ESP_OK) {
        Serial.println("ESP-NOW init failed");
        return;
    }

    esp_now_peer_info_t peerInfo;
    memcpy(peerInfo.peer_addr, gatewayMAC, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;
    esp_now_add_peer(&peerInfo);

    strcpy(packet.device_id, "esp32_camera");
}

void sendSensor(const char* type, float value) {
    strcpy(packet.sensor_type, type);
    packet.value = value;
    esp_now_send(gatewayMAC, (uint8_t*)&packet, sizeof(packet));
}

void loop() {
    // Leggi sensori e invia
    sendSensor("temperatura", 22.5);
    sendSensor("presenza", 1);

    // Deep sleep per risparmio batteria
    esp_deep_sleep(30 * 1000000);  // 30 secondi
}

// ====== GATEWAY (riceve ESP-NOW e inoltra a MQTT) ======
/*
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
    SensorPacket* pkt = (SensorPacket*)data;

    char topic[64];
    snprintf(topic, 64, "sensori/%s/%s", pkt->device_id, pkt->sensor_type);
    mqtt.publish(topic, String(pkt->value).c_str());
}
*/
"""

# ============================================================================
# INTEGRAZIONE CON INTENT (da aggiungere a intent_llm.py)
# ============================================================================

"""
# Aggiungere a INTENT_PRECHECK_ORDER in intent_llm.py:

"SENSORI_CASA": [
    r"(?:che\s+)?temperatura.*(?:in|nella?|del)?\s*(\w+)",
    r"quanti\s+gradi.*(?:in|nella?|del)?\s*(\w+)",
    r"(?:com['\s]?è\s+)?(?:l['\s]?)?umidità.*(\w+)",
    r"c['\s]?è\s+movimento.*(\w+)",
    r"(?:è\s+)?(?:aperta|chiusa)\s+(?:la\s+)?porta.*(\w+)",
    r"stato\s+(?:della?\s+)?casa",
    r"come\s+sta\s+(?:la\s+)?casa",
    r"situazione\s+sensori",
    r"report\s+casa"
],

# Nel blocco di pattern matching:
if matched_intent == "SENSORI_CASA":
    if "stato" in text_lower or "casa" in text_lower:
        return '{"function_call": {"name": "stato_casa", "arguments": {}}}'

    # Estrai stanza e tipo
    stanze = ["cucina", "soggiorno", "camera", "esterno", "garage", "salotto"]
    tipi = ["temperatura", "umidita", "movimento", "porta", "gas", "luce"]

    stanza_trovata = None
    tipo_trovato = None

    for s in stanze:
        if s in text_lower:
            stanza_trovata = s
            break

    for t in tipi:
        if t in text_lower:
            tipo_trovato = t
            break

    if "gradi" in text_lower or "caldo" in text_lower or "freddo" in text_lower:
        tipo_trovato = "temperatura"
    if "umido" in text_lower:
        tipo_trovato = "umidita"

    if stanza_trovata and tipo_trovato:
        return f'{{"function_call": {{"name": "leggi_sensore", "arguments": {{"stanza": "{stanza_trovata}", "tipo": "{tipo_trovato}"}}}}}}'
"""

logger.bind(tag=TAG).info("DRAFT sensori_satellite caricato (non attivo)")
