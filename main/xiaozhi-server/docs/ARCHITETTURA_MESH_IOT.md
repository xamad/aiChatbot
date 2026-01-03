# Architettura Mesh IoT - Xiaozhi Chatbot

> Documento di architettura per l'integrazione di sensori ESP32, LoRa/Meshtastic e hub locale con il chatbot vocale Xiaozhi.

**Data**: Gennaio 2025
**Versione**: 1.0

---

## Indice

1. [Hardware Disponibile](#hardware-disponibile)
2. [Architettura Generale](#architettura-generale)
3. [Protocolli di Comunicazione](#protocolli-di-comunicazione)
4. [Architettura Resiliente (VPS + Hub Locale)](#architettura-resiliente)
5. [Progetti Open Source da Riusare](#progetti-open-source)
6. [Piano di Sviluppo in Fasi](#piano-di-sviluppo)
7. [Critiche e Miglioramenti](#critiche-e-miglioramenti)
8. [Struttura MQTT Topics](#struttura-mqtt-topics)
9. [Configurazioni Hardware](#configurazioni-hardware)

---

## Hardware Disponibile

| Dispositivo | Quantità | Ruolo Assegnato | Connettività |
|-------------|----------|-----------------|--------------|
| **ESP32-C3 Mini** | 1 | Chatbot AI (già funzionante) | WiFi → VPS |
| **ESP32-S3** | 1 | Gateway ESP-NOW (master indoor) | WiFi + ESP-NOW |
| **Heltec V3** | 1 | Bridge LoRa + Meshtastic | WiFi + LoRa SX1262 |
| **ESP32-WROOM** | N | Sensori indoor (ESP-NOW) | ESP-NOW |
| **ESP32-WROOM** | N | Sensori outdoor (+ DX-LR-30) | LoRa |
| **DX-LR-30** | 2 | Moduli LoRa per nodi outdoor | LoRa 868MHz |
| **ESP32-CAM** | N | Telecamere | WiFi o ESP-NOW |
| **LuckFox Pico** | 1 | Hub locale Linux | Ethernet/WiFi |
| **Raspberry Pi Pico** | 1 | I2C hub sensori (opzionale) | UART → ESP32 |

### LuckFox Pico Specs

| Modello | CPU | RAM | NPU | Extra |
|---------|-----|-----|-----|-------|
| Pico Pro | Cortex-A7 1.2GHz | 128MB | 0.5 TOPS | Ethernet |
| Pico Ultra | Cortex-A7 1.2GHz | 256MB | 1 TOPS | Ethernet |

**Può eseguire**: Mosquitto, Python, SQLite, Piper TTS

---

## Architettura Generale

```
                              ☁️ VPS HETZNER (Finlandia)
                         ┌─────────────────────────────────┐
                         │       XIAOZHI SERVER FULL       │
                         │  • Groq LLM                     │
                         │  • EdgeTTS                      │
                         │  • Plugins completi             │
                         │  • Database storico             │
                         └───────────────┬─────────────────┘
                                         │
                                         │ MQTT Bridge / REST API
                                         │ (sync bidirezionale)
                                         │
    ═══════════════════════════════════════════════════════════════
                              🌐 INTERNET
    ═══════════════════════════════════════════════════════════════
                                         │
                                         │
   🏠 CASA ──────────────────────────────┼───────────────────────────
                                         │
                         ┌───────────────▼───────────────────┐
                         │   🦊 LUCKFOX PICO (Hub Locale)    │
                         │                                   │
                         │   • Mosquitto MQTT Broker         │
                         │   • Automazioni critiche Python   │
                         │   • Cache SQLite                  │
                         │   • Piper TTS (offline)           │
                         │   • LoRa→MQTT bridge              │
                         └───────────────┬───────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
              UART/USB             UART/USB             UART/USB
                    │                    │                    │
                    ▼                    ▼                    ▼
         ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
         │ 🎤 ESP32-C3      │  │ 🌐 ESP32-S3      │  │ 📡 HELTEC V3     │
         │    CHATBOT       │  │    GATEWAY       │  │    LoRa BRIDGE   │
         │                  │  │    ESP-NOW       │  │                  │
         │ • Online → VPS   │  │ • Master mesh    │  │ • LoRa SX1262    │
         │ • Offline → Pico │  │ • Automazioni FW │  │ • Meshtastic     │
         └──────────────────┘  └────────┬─────────┘  └────────┬─────────┘
                                        │                     │
                                        │ ESP-NOW             │ LoRa 868MHz
                                        │ (indoor <100m)      │ (outdoor 1-15km)
                                        │                     │
              ┌─────────────────────────┼─────────────────────┼────────────────┐
              │                         │                     │                │
              ▼              ▼          │          ▼          ▼          ▼     │
         ┌────────┐    ┌────────┐       │    ┌────────┐  ┌────────┐ ┌────────┐
         │ WROOM  │    │ WROOM  │       │    │WROOM+  │  │WROOM+  │ │MESH    │
         │        │    │        │       │    │DX-LR-30│  │DX-LR-30│ │NODES   │
         │ Cucina │    │Soggiorn│       │    │        │  │        │ │        │
         │ DHT22  │    │ mmWave │       │    │ Serra  │  │ Garage │ │📱Phone │
         │ MQ-2   │    │ CO2    │       │    │ Solare │  │        │ │🏢Office│
         └────────┘    └────────┘       │    └────────┘  └────────┘ └────────┘
              │                         │                     │
              └───── INDOOR ────────────┴────── OUTDOOR ──────┘
```

---

## Protocolli di Comunicazione

### ESP-NOW (Indoor)

| Caratteristica | Valore |
|----------------|--------|
| Frequenza | 2.4 GHz |
| Range | 50-100m indoor |
| Latenza | < 10ms |
| Topologia | Star (consigliata) o Mesh |
| Consumo | ~100mA attivo, ~10µA deep sleep |
| Max payload | 250 bytes |
| Sicurezza | WPA2-PSK + encryption key |

**Quando usare Star vs Mesh:**
- **Star** (consigliato): Appartamento <100mq, più affidabile
- **Mesh**: Casa >150mq, multi-piano (ma painlessMesh è instabile)
- **Alternativa mesh**: Aggiungere repeater ESP32

### LoRa (Outdoor)

| Caratteristica | Valore |
|----------------|--------|
| Frequenza | 868 MHz (Europa) |
| Range | 1-15+ km |
| Latenza | 1-5 secondi |
| Spreading Factor | 7-12 (10 consigliato) |
| Bandwidth | 125 kHz |
| Consumo | ~120mA TX, ~10µA deep sleep |

### MQTT Topics

```
mesh/
├── indoor/
│   ├── {nodo}/
│   │   ├── temperatura      → {"value": 23.5, "ts": "...", "battery": 95}
│   │   ├── umidita
│   │   ├── gas
│   │   └── presenza
│   └── ...
├── outdoor/
│   ├── serra/
│   ├── garage/
│   └── meteo/
├── comandi/
│   ├── indoor/{nodo}/{attuatore}  → {"action": "on"}
│   └── outdoor/{nodo}/{attuatore}
├── gateway/
│   ├── espnow/status
│   └── lora/status
├── meshtastic/
│   ├── tx                   → {"to": "broadcast", "text": "..."}
│   └── rx
└── system/
    ├── alerts
    └── heartbeat
```

---

## Architettura Resiliente

### Scenario: Internet UP vs DOWN

```
╔════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                    ║
║   INTERNET UP ✅                           INTERNET DOWN ❌                        ║
║                                                                                    ║
║   ┌────────────────────┐                   ┌────────────────────┐                 ║
║   │ ☁️ VPS HETZNER      │                   │ 🦊 LUCKFOX PICO    │                 ║
║   │                    │                   │    (AUTONOMO)      │                 ║
║   │ • Xiaozhi FULL     │                   │                    │                 ║
║   │ • Groq LLM         │                   │ • MQTT Broker ✅   │                 ║
║   │ • EdgeTTS          │                   │ • Automazioni ✅   │                 ║
║   │ • DB storico       │                   │ • Cache dati ✅    │                 ║
║   │                    │     ◄── SYNC ──►  │ • Piper TTS ✅     │                 ║
║   │                    │                   │ • Comandi base ✅  │                 ║
║   │ Chatbot: FULL      │                   │                    │                 ║
║   │ "barzelletta" ✅   │                   │ Chatbot: DEGRADATO │                 ║
║   │                    │                   │ "barzelletta" ❌   │                 ║
║   │                    │                   │ "accendi luce" ✅  │                 ║
║   └────────────────────┘                   │                    │                 ║
║                                            │ 📡 LoRa ALERT      │                 ║
║                                            │ → Meshtastic 📱    │                 ║
║                                            └────────────────────┘                 ║
║                                                                                    ║
╚════════════════════════════════════════════════════════════════════════════════════╝
```

### Automazioni Critiche Locali

Le automazioni safety-critical devono funzionare anche offline:

```python
# Sul LuckFox Pico - automations.py

def check_local_automations(topic, data):
    """Automazioni critiche SEMPRE eseguite localmente"""

    # Gas detection → ventola (non aspetta il server!)
    if "cucina/gas" in topic and data["value"] > 800:
        mqtt_publish("comandi/cucina/ventola", '{"action":"on"}')
        speak_local("Attenzione! Gas rilevato in cucina!")
        send_lora_alert("GAS ALTO CUCINA!")

    # Fumo → allarme
    if "cucina/fumo" in topic and data["value"] > 200:
        activate_alarm()
        send_lora_alert("FUMO RILEVATO!")

    # Presenza notte → luce
    if "ingresso/movimento" in topic and is_night() and data["value"]:
        mqtt_publish("comandi/ingresso/luce", '{"action":"on"}')
```

### LoRa come Canale di Emergenza

```
SCENARIO: Internet cade + Rilevato gas

1. Sensore cucina → ESP-NOW → ESP32-S3 Gateway
2. Gateway → MQTT locale → LuckFox
3. LuckFox:
   - Attiva ventola (automazione locale)
   - Parla "Attenzione gas!" (Piper TTS)
   - Pubblica su meshtastic/tx
4. Heltec V3 riceve da MQTT → Trasmette LoRa
5. Telefono con Meshtastic riceve notifica! 📱
```

---

## Progetti Open Source

### Da Riusare (NON reinventare la ruota!)

| Componente | Progetto | URL | Note |
|------------|----------|-----|------|
| Gateway ESP-NOW | ESP-NOW-Gateway | https://github.com/aZholtikov/ESP-NOW-Gateway | Auto-discovery HA |
| Multi-protocollo | OpenMQTTGateway | https://github.com/1technophile/OpenMQTTGateway | LoRa, BLE, 433MHz |
| Sensori indoor | ESPHome | https://esphome.io/ | Config YAML, no codice |
| LoRa Bridge | Meshtastic stock | https://meshtastic.org/ | Firmware già pronto |
| Meshtastic Python | meshtastic-bridge | https://github.com/geoffwhittington/meshtastic-bridge | Bridge MQTT |
| MQTT Broker | Mosquitto | https://mosquitto.org/ | Standard |
| TTS Offline | Piper TTS | https://github.com/rhasspy/piper | Leggero, italiano |
| DB Time-series | InfluxDB | https://www.influxdata.com/ | Per storico |
| Dashboard | Grafana | https://grafana.com/ | Visualizzazione |

### Stima Codice Custom vs Riuso

| Componente | Scrivi | Riusa |
|------------|--------|-------|
| Gateway ESP-NOW | 10% | 90% |
| Nodi sensori indoor | 0% | 100% (ESPHome) |
| Bridge LoRa | 0% | 100% (Meshtastic) |
| MQTT Broker | 0% | 100% |
| TTS locale | 0% | 100% |
| Plugin Xiaozhi | 70% | 30% |
| Automazioni | 80% | 20% |
| Sync VPS↔locale | 60% | 40% |

**Totale: ~30% custom, ~70% integrazione**

---

## Piano di Sviluppo

### Fase 1: Minimo Funzionante (1-2 settimane)

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ ESP32-WROOM │      │ ESP32-S3    │      │ VPS Hetzner │
│ (1 sensore) │─────►│ Gateway     │─────►│ Mosquitto   │
│ DHT22       │ESPNOW│ (fork repo) │ MQTT │ + Xiaozhi   │
└─────────────┘      └─────────────┘      └─────────────┘
```

**Azioni:**
- [ ] Fork/config ESP-NOW-Gateway
- [ ] Installare Mosquitto su VPS
- [ ] Plugin Xiaozhi minimale per MQTT
- [ ] Test con 1 sensore

### Fase 2: Meshtastic (1 settimana)

```
┌─────────────┐      ┌─────────────┐
│ Heltec V3   │─────►│ VPS         │
│ Meshtastic  │ MQTT │ Xiaozhi     │
│ (stock FW)  │      │             │
└─────────────┘      └─────────────┘
```

**Azioni:**
- [ ] Flash Meshtastic su Heltec V3
- [ ] Configurare MQTT gateway in Meshtastic
- [ ] Plugin Xiaozhi per messaggi mesh

### Fase 3: Hub Locale (1 settimana)

```
┌─────────────┐
│ LuckFox     │◄───── Gateway + Heltec
│ Mosquitto   │
│ Automazioni │─────► VPS (sync)
│ Piper TTS   │
└─────────────┘
```

**Azioni:**
- [ ] Setup LuckFox con Linux
- [ ] Installare Mosquitto, Piper TTS
- [ ] Script automazioni Python
- [ ] MQTT bridge verso VPS

### Fase 4: Espansione (iterativo)

- [ ] Più sensori indoor (ESPHome YAML)
- [ ] Sensori outdoor LoRa (ESP32 + DX-LR-30)
- [ ] ESP32-CAM
- [ ] Automazioni avanzate
- [ ] Dashboard Grafana

---

## Critiche e Miglioramenti

### Problemi Identificati

1. **Troppa complessità iniziale**
   - Soluzione: Sviluppo in fasi incrementali

2. **Reinventare la ruota**
   - Soluzione: Usare progetti esistenti (ESP-NOW-Gateway, ESPHome, Meshtastic)

3. **Manca piano di fallback**
   - Soluzione: Test standalone di ogni componente prima di integrare

4. **Sicurezza non considerata**
   - Soluzione: MQTT con TLS + auth, ESP-NOW encryption, firewall VPS

5. **Monitoring assente**
   - Soluzione: Heartbeat, alert, dashboard Grafana

### Test Standalone Consigliati

```
Test 1: ESP-NOW-Gateway → MQTT broker locale → mosquitto_sub
        (senza Xiaozhi, senza VPS)

Test 2: Heltec V3 → Meshtastic app su telefono
        (senza MQTT, senza server)

Test 3: LuckFox → MQTT → Node-RED (visualizza dati)
        (prima di scrivere Python custom)
```

---

## Configurazioni Hardware

### ESP32-S3 Gateway

```yaml
# platformio.ini
[env:esp32-s3]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
lib_deps =
    ESP-NOW-Gateway  # fork da aZholtikov
    PubSubClient
    ArduinoJson
```

### Heltec V3 (Meshtastic)

```yaml
# Configurazione via Meshtastic CLI o App
device:
  role: CLIENT_MUTE  # o ROUTER se serve relay

lora:
  region: EU_868

mqtt:
  enabled: true
  address: mqtt://tuo-vps.hetzner.com:1883
  username: xiaozhi
  password: ****
  encryption_enabled: true
  json_enabled: true
```

### LuckFox Pico

```bash
# Setup iniziale
apt update && apt install -y mosquitto mosquitto-clients python3-pip

# Piper TTS
pip install piper-tts
piper --download-voice it_IT-riccardo-medium

# Automazioni
pip install paho-mqtt

# Avvio servizi
systemctl enable mosquitto
```

### Sensori Indoor (ESPHome)

```yaml
# cucina.yaml
esphome:
  name: cucina

esp32:
  board: esp32dev

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

mqtt:
  broker: 192.168.1.100  # LuckFox

sensor:
  - platform: dht
    pin: GPIO4
    temperature:
      name: "Cucina Temperatura"
    humidity:
      name: "Cucina Umidita"
    update_interval: 30s

  - platform: adc
    pin: GPIO34
    name: "Cucina Gas"
    update_interval: 10s
```

---

## Riferimenti

- [ESP-NOW-Gateway](https://github.com/aZholtikov/ESP-NOW-Gateway)
- [OpenMQTTGateway](https://github.com/1technophile/OpenMQTTGateway)
- [ESPHome](https://esphome.io/)
- [Meshtastic](https://meshtastic.org/)
- [Meshtastic MQTT Integration](https://meshtastic.org/docs/software/integrations/mqtt/)
- [Piper TTS](https://github.com/rhasspy/piper)
- [LuckFox Pico](https://www.luckfox.com/)

---

*Documento generato durante sessione di brainstorming architetturale - Gennaio 2025*
