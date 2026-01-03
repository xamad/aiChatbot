"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                      ║
║                    ARCHITETTURA MESH COMPLETA - XIAOZHI IoT                          ║
║                                                                                      ║
║                          Hardware Disponibile & Ruoli                                ║
║                                                                                      ║
╚══════════════════════════════════════════════════════════════════════════════════════╝

INVENTARIO HARDWARE:
====================

┌─────────────────────┬─────────────────────────────────────────────────────────────────┐
│ DISPOSITIVO         │ RUOLO ASSEGNATO                                                 │
├─────────────────────┼─────────────────────────────────────────────────────────────────┤
│ Raspberry Pi 4B     │ 🖥️  HUB CENTRALE: MQTT Broker + Video NVR + DB + Processing     │
│ ESP32-C3 Mini       │ 🎤  CHATBOT AI (già funzionante, non toccare)                   │
│ ESP32-S3            │ 🌐  GATEWAY ESP-NOW (master rete indoor)                        │
│ Heltec V3           │ 📡  BRIDGE LoRa + Meshtastic (gateway outdoor)                  │
│ ESP32-WROOM (x N)   │ 🌡️  SENSORI indoor (ESP-NOW) o outdoor (+ DX-LR-30)             │
│ DX-LR-30 (x 2)      │ 📻  MODULI LoRa per nodi outdoor                                │
│ ESP32-CAM (x N)     │ 📷  TELECAMERE (stream a RPi4)                                  │
│ Raspberry Pi Pico   │ 🔌  SENSORI SEMPLICI (I2C hub, basso costo)                     │
└─────────────────────┴─────────────────────────────────────────────────────────────────┘


ARCHITETTURA DISTRIBUITA:
=========================

                              ☁️ INTERNET (opzionale)
                                       │
                                       │
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                                                                              ║
    ║   🖥️  RASPBERRY PI 4B  -  HUB CENTRALE                                       ║
    ║                                                                              ║
    ║   ┌────────────────────────────────────────────────────────────────────┐    ║
    ║   │                                                                    │    ║
    ║   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │    ║
    ║   │  │ XIAOZHI     │  │ MOSQUITTO   │  │ FRIGATE/    │  │ INFLUXDB  │ │    ║
    ║   │  │ SERVER      │  │ MQTT BROKER │  │ MOTION      │  │ GRAFANA   │ │    ║
    ║   │  │ (Docker)    │  │             │  │ (NVR Video) │  │ (Storico) │ │    ║
    ║   │  │             │  │ Port 1883   │  │             │  │           │ │    ║
    ║   │  │ • Groq LLM  │  │             │  │ • Stream    │  │ • Dati    │ │    ║
    ║   │  │ • EdgeTTS   │  │ • Auth      │  │ • AI detect │  │ • Grafici │ │    ║
    ║   │  │ • Plugins   │  │ • ACL       │  │ • Record    │  │ • Alert   │ │    ║
    ║   │  │             │  │ • Bridge    │  │             │  │           │ │    ║
    ║   │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘ │    ║
    ║   │         │                │                │                │      │    ║
    ║   │         └────────────────┴────────────────┴────────────────┘      │    ║
    ║   │                              │                                     │    ║
    ║   │                         RETE LOCALE                                │    ║
    ║   │                        192.168.x.x                                 │    ║
    ║   │                                                                    │    ║
    ║   └────────────────────────────────────────────────────────────────────┘    ║
    ║                                                                              ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
                                       │
                    ┌──────────────────┼──────────────────┐
                    │ WiFi             │ WiFi             │ WiFi
                    ▼                  ▼                  ▼
    ╔═══════════════════════╗  ╔═══════════════════╗  ╔═══════════════════╗
    ║                       ║  ║                   ║  ║                   ║
    ║  🎤 ESP32-C3 MINI     ║  ║  🌐 ESP32-S3      ║  ║  📡 HELTEC V3     ║
    ║     CHATBOT AI        ║  ║     GATEWAY       ║  ║     LoRa BRIDGE   ║
    ║                       ║  ║     ESP-NOW       ║  ║                   ║
    ║  • Microfono INMP441  ║  ║                   ║  ║  • WiFi → MQTT    ║
    ║  • Speaker MAX98357   ║  ║  • WiFi → MQTT    ║  ║  • LoRa SX1262    ║
    ║  • WebSocket → Server ║  ║  • ESP-NOW Master ║  ║  • Meshtastic FW  ║
    ║                       ║  ║  • Coordina indoor║  ║  • Display OLED   ║
    ║  GIÀ FUNZIONANTE ✅   ║  ║                   ║  ║                   ║
    ║                       ║  ║                   ║  ║                   ║
    ╚═══════════════════════╝  ╚═════════┬═════════╝  ╚═════════┬═════════╝
                                         │                      │
                                         │ ESP-NOW              │ LoRa 868MHz
                                         │ 2.4GHz               │
                    ┌────────────────────┼────────────────────┐ │
                    │                    │                    │ │
                    ▼                    ▼                    ▼ │
    ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────┐
    │                       │ │                   │ │                   │
    │  🌡️ ESP32-WROOM #1    │ │  🌡️ ESP32-WROOM #2│ │  📷 ESP32-CAM     │
    │     CUCINA            │ │     SOGGIORNO     │ │     INGRESSO      │
    │                       │ │                   │ │                   │
    │  • DHT22 (temp/hum)   │ │  • LD2410 mmWave  │ │  • OV2640 Camera  │
    │  • MQ-2 (gas)         │ │  • SCD30 (CO2)    │ │  • PIR motion     │
    │  • Reed (porta)       │ │  • BH1750 (lux)   │ │  • Stream RTSP    │
    │  • Relay (ventola)    │ │  • Relay (luci)   │ │  • → RPi4 NVR     │
    │                       │ │                   │ │                   │
    │  ESP-NOW → Gateway    │ │  ESP-NOW → Gateway│ │  WiFi → RPi4      │
    │  Deep sleep opzionale │ │                   │ │  o ESP-NOW        │
    │                       │ │                   │ │                   │
    └───────────────────────┘ └───────────────────┘ └───────────────────┘

    ┌───────────────────────┐ ┌───────────────────┐
    │                       │ │                   │
    │  🌡️ ESP32-WROOM #3    │ │  🔌 RASPI PICO    │
    │     CAMERA/BAGNO      │ │     I2C HUB       │
    │                       │ │                   │
    │  • LD2410 mmWave      │ │  • BME280 x4      │   ← Connesso via
    │  • DHT22              │ │  • BH1750 x2      │     UART a un
    │  • Relay (ventola)    │ │  • ADS1115 ADC    │     ESP32-WROOM
    │                       │ │                   │
    │  ESP-NOW → Gateway    │ │  UART → WROOM     │
    │                       │ │  (basso costo)    │
    └───────────────────────┘ └───────────────────┘

                                         │
                                         │ LoRa 868MHz (1-15 km)
                                         │
    ┌────────────────────────────────────┼────────────────────────────────────┐
    │                                    │                                    │
    ▼                                    ▼                                    ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
│                           │ │                           │ │                           │
│  🌱 ESP32-WROOM + DX-LR-30│ │  🚗 ESP32-WROOM + DX-LR-30│ │  📱 MESHTASTIC NODES      │
│     SERRA / ORTO          │ │     GARAGE REMOTO         │ │     (altri utenti)        │
│                           │ │                           │ │                           │
│  • DHT22 (temp/hum)       │ │  • Reed switch (porta)    │ │  • T-Beam                 │
│  • Soil moisture x3       │ │  • HC-SR04 (distanza)     │ │  • Heltec                 │
│  • DS18B20 (terreno)      │ │  • MQ-2 (fumo)            │ │  • RAK                    │
│  • Float switch (acqua)   │ │  • PIR motion             │ │                           │
│  • Relay x3 (pompe)       │ │  • Relay (porta garage)   │ │  Messaggi LoRa            │
│                           │ │                           │ │  bidirezionali            │
│  LoRa → Heltec V3         │ │  LoRa → Heltec V3         │ │                           │
│  Solare + 18650           │ │  Solare + 18650           │ │                           │
│  Deep sleep 10 min        │ │  Deep sleep 5 min         │ │                           │
│                           │ │                           │ │                           │
└───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘


PROTOCOLLI E FLUSSI:
====================

1. INDOOR (ESP-NOW Mesh)
   ┌──────────┐    ESP-NOW     ┌──────────┐     MQTT      ┌──────────┐
   │ WROOM    │ ──────────────►│ ESP32-S3 │ ─────────────►│ RPi4     │
   │ Sensori  │◄────────────── │ Gateway  │◄───────────── │ Broker   │
   └──────────┘    (2.4GHz)    └──────────┘   (WiFi)      └──────────┘

   - Latenza: < 10ms
   - Range: 50-100m indoor
   - Consumo: ~100mA attivo, ~10µA deep sleep
   - Bidirezionale: query + comandi

2. OUTDOOR (LoRa)
   ┌──────────┐     LoRa       ┌──────────┐     MQTT      ┌──────────┐
   │ WROOM +  │ ──────────────►│ Heltec   │ ─────────────►│ RPi4     │
   │ DX-LR-30 │◄────────────── │ V3       │◄───────────── │ Broker   │
   └──────────┘   (868MHz)     └──────────┘   (WiFi)      └──────────┘

   - Latenza: 1-5 sec
   - Range: 1-15+ km
   - Consumo: ~120mA TX, ~10µA deep sleep
   - Deep sleep per mesi con solare

3. VIDEO (ESP32-CAM)
   ┌──────────┐     RTSP       ┌──────────┐    Storage    ┌──────────┐
   │ ESP32-CAM│ ──────────────►│ Frigate/ │ ─────────────►│ NAS/SD   │
   │          │                │ Motion   │               │          │
   └──────────┘   (WiFi)       └──────────┘   (RPi4)      └──────────┘

   - Stream continuo o motion-triggered
   - AI object detection su RPi4
   - Notifiche push + vocali


MQTT TOPIC STRUCTURE:
=====================

mesh/
├── indoor/
│   ├── cucina/
│   │   ├── temperatura      → {"value": 23.5, "ts": "...", "battery": 95}
│   │   ├── umidita          → {"value": 55, "ts": "..."}
│   │   ├── gas              → {"value": 120, "alert": false}
│   │   └── porta            → {"value": true, "ts": "..."}
│   ├── soggiorno/
│   │   ├── temperatura
│   │   ├── presenza         → {"value": true, "distance": 250}
│   │   └── co2              → {"value": 650}
│   └── ...
├── outdoor/
│   ├── serra/
│   │   ├── temperatura
│   │   ├── umidita_terreno_1
│   │   └── pompa_1/status
│   ├── garage/
│   │   ├── porta
│   │   └── distanza_auto
│   └── meteo/
│       ├── temperatura
│       ├── pressione
│       └── pioggia
├── comandi/
│   ├── indoor/{nodo}/{attuatore}  → {"action": "on"}
│   └── outdoor/{nodo}/{attuatore} → {"action": "open"}
├── gateway/
│   ├── espnow/status        → {"online": true, "nodes": 5}
│   └── lora/status          → {"online": true, "nodes": 3}
├── meshtastic/
│   ├── tx                   → {"to": "broadcast", "text": "Ciao!"}
│   └── rx                   → {"from": "Marco", "text": "Arrivo!"}
└── system/
    ├── alerts               → {"node": "cucina", "type": "gas", "msg": "..."}
    └── heartbeat            → {"node": "gateway_espnow", "ts": "..."}


RASPBERRY PI 4B - SERVIZI:
==========================

Docker Compose:
├── xiaozhi-server      (già esistente)
├── mosquitto           (MQTT broker)
├── influxdb            (time-series DB)
├── grafana             (dashboard)
├── frigate             (NVR con AI) [opzionale, richiede Coral TPU per best performance]
└── zigbee2mqtt         (futuro, se vuoi Zigbee)

Risorse stimate:
├── RAM: ~2GB usata / 4GB disponibili
├── CPU: 20-40% medio
├── Storage: SD 32GB+ o SSD USB
└── Network: Gigabit consigliato


FILES DA CREARE:
================

Repository structure (da aggiungere a github.com/xamad/aiChatbot):

firmware/
├── gateway_espnow/
│   ├── platformio.ini
│   └── src/
│       └── main.cpp          # ESP32-S3 Gateway ESP-NOW
├── bridge_lora/
│   ├── platformio.ini
│   └── src/
│       └── main.cpp          # Heltec V3 LoRa Bridge (custom FW)
├── node_indoor/
│   ├── platformio.ini
│   └── src/
│       ├── main.cpp          # ESP32-WROOM sensore indoor
│       └── config.h          # Configurazione sensori
├── node_outdoor_lora/
│   ├── platformio.ini
│   └── src/
│       ├── main.cpp          # ESP32-WROOM + DX-LR-30
│       └── config.h
├── camera_node/
│   ├── platformio.ini
│   └── src/
│       └── main.cpp          # ESP32-CAM
└── pico_i2c_hub/
    └── main.py               # Raspberry Pi Pico (MicroPython)

raspberry/
├── docker-compose.yml        # Tutti i servizi
├── mosquitto/
│   └── mosquitto.conf        # Config MQTT
├── influxdb/
│   └── init.iql              # Schema DB
└── scripts/
    ├── setup.sh              # Installazione automatica
    └── backup.sh             # Backup dati

plugins_func/functions/
├── mesh_gateway.py           # Plugin unificato (sostituisce i draft)
└── mesh_automations.py       # Automazioni


PROSSIMI PASSI:
===============

1. [x] Architettura definita (questo file)
2. [ ] Setup Raspberry Pi 4B (MQTT + Docker)
3. [ ] Firmware ESP32-S3 Gateway ESP-NOW
4. [ ] Firmware Heltec V3 LoRa Bridge
5. [ ] Firmware ESP32-WROOM indoor
6. [ ] Firmware ESP32-WROOM + DX-LR-30 outdoor
7. [ ] Plugin Python unificato
8. [ ] Test integrazione
9. [ ] Push GitHub

"""

# ============================================================================
# COSTANTI CONFIGURAZIONE
# ============================================================================

# Raspberry Pi 4B
RPI4_IP = "192.168.1.100"  # Configurare
MQTT_BROKER = RPI4_IP
MQTT_PORT = 1883
MQTT_USER = "xiaozhi"
MQTT_PASS = "changeme"

# Gateway ESP-NOW (ESP32-S3)
GATEWAY_ESPNOW_MAC = "AA:BB:CC:DD:EE:01"

# Bridge LoRa (Heltec V3)
HELTEC_V3_MAC = "AA:BB:CC:DD:EE:02"
LORA_FREQUENCY = 868E6  # Europa
LORA_SF = 10            # Spreading Factor (7-12)
LORA_BW = 125E3         # Bandwidth

# Nodi indoor (ESP-NOW)
INDOOR_NODES = {
    "cucina": {
        "mac": "AA:BB:CC:DD:EE:10",
        "sensors": ["temperatura", "umidita", "gas", "porta"],
        "actuators": ["ventola"],
        "interval": 30,  # secondi
    },
    "soggiorno": {
        "mac": "AA:BB:CC:DD:EE:11",
        "sensors": ["temperatura", "umidita", "co2", "presenza", "luce"],
        "actuators": ["luce_principale", "luce_lettura"],
        "interval": 30,
    },
    "camera": {
        "mac": "AA:BB:CC:DD:EE:12",
        "sensors": ["temperatura", "umidita", "presenza"],
        "actuators": ["luce_comodino"],
        "interval": 60,
    },
    "bagno": {
        "mac": "AA:BB:CC:DD:EE:13",
        "sensors": ["temperatura", "umidita", "presenza"],
        "actuators": ["ventola"],
        "interval": 30,
    },
    "ingresso": {
        "mac": "AA:BB:CC:DD:EE:14",
        "sensors": ["porta", "movimento"],
        "actuators": ["luce"],
        "interval": 5,
    },
}

# Nodi outdoor (LoRa)
OUTDOOR_NODES = {
    "serra": {
        "sensors": ["temperatura", "umidita", "umidita_terreno_1", "umidita_terreno_2",
                   "umidita_terreno_3", "livello_acqua"],
        "actuators": ["pompa_1", "pompa_2", "pompa_3"],
        "interval": 10,  # minuti
        "solar": True,
    },
    "garage": {
        "sensors": ["porta", "movimento", "distanza_auto", "fumo"],
        "actuators": ["porta_garage"],
        "interval": 5,
        "solar": False,  # Alimentazione fissa
    },
    "meteo": {
        "sensors": ["temperatura", "umidita", "pressione", "vento_vel",
                   "vento_dir", "pioggia", "uv", "luce"],
        "actuators": [],
        "interval": 5,
        "solar": True,
    },
}

# ESP32-CAM
CAMERAS = {
    "ingresso": {
        "ip": "192.168.1.50",
        "stream_port": 81,
        "motion_detect": True,
    },
    "giardino": {
        "ip": "192.168.1.51",
        "stream_port": 81,
        "motion_detect": True,
    },
}

# ============================================================================
# DA SVILUPPARE: Vedi file separati per implementazione
# ============================================================================

from config.logger import setup_logging
logger = setup_logging()
TAG = __name__
logger.bind(tag=TAG).info("Architettura mesh completa definita - vedi commenti per dettagli")
