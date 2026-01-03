# Architettura Mesh IoT - Xiaozhi Chatbot

> Documento di architettura per l'integrazione di sensori ESP32, LoRa/Meshtastic e hub locale con il chatbot vocale Xiaozhi.

**Data**: Gennaio 2025
**Versione**: 2.2 (Firmware, OS, integrazione Xiaozhi, alert push)

---

## Indice

1. [Hardware Disponibile](#hardware-disponibile)
2. [Architettura Generale](#architettura-generale)
3. [Protocolli di Comunicazione](#protocolli-di-comunicazione)
4. [Architettura Resiliente (VPS + Hub Locale)](#architettura-resiliente)
5. [Progetti Open Source da Riusare](#progetti-open-source)
6. [Piano di Sviluppo in Fasi](#piano-di-sviluppo)
7. [Sicurezza](#sicurezza)
8. [Critiche e Miglioramenti](#critiche-e-miglioramenti)
9. [Struttura MQTT Topics](#struttura-mqtt-topics)
10. [Configurazioni Hardware](#configurazioni-hardware)

---

## Hardware Disponibile

| Dispositivo | Quantità | Ruolo Assegnato | Connettività |
|-------------|----------|-----------------|--------------|
| **ESP32-C3 Mini** | 1 | Chatbot AI (già funzionante) | WiFi → VPS |
| **ESP32-S3** | 1 | Gateway ESP-NOW (master indoor) | Ethernet + ESP-NOW |
| **Heltec V3** | 1 | Bridge LoRa + Meshtastic | WiFi + LoRa SX1262 |
| **ESP32-WROOM** | N | Sensori indoor (ESP-NOW) | ESP-NOW |
| **ESP32-WROOM** | N | Sensori outdoor (+ DX-LR-30) | LoRa |
| **DX-LR-30** | 2 | Moduli LoRa per nodi outdoor | LoRa 868MHz |
| **ESP32-CAM** | N | Telecamere sicurezza | **Solo WiFi** (no ESP-NOW/LoRa) |
| **LuckFox Pico** | 1 | Hub locale Linux | Ethernet/WiFi |
| **Raspberry Pi Pico** | 1 | I2C hub sensori (opzionale) | UART → ESP32 |

### LuckFox Pico Specs e Raccomandazioni

| Modello | CPU | RAM | NPU | Uso Consigliato |
|---------|-----|-----|-----|-----------------|
| Pico Pro | Cortex-A7 1.2GHz | 128MB | 0.5 TOPS | Mosquitto + automazioni + cache |
| Pico Ultra | Cortex-A7 1.2GHz | 256MB | 1 TOPS | **Preferito** se computer vision o AI locale |

**Può eseguire**: Mosquitto, NanoMQ (alternativa ultra-leggera), Python, SQLite, Piper TTS

> **Test confermati dalla community**: LuckFox Pico Ultra W gestisce efficacemente traffico MQTT real-time su reti IoT domestiche.

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
                                         │ MQTT Bridge TLS + Auth
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
                         │   • Mosquitto MQTT Broker (auth)  │
                         │   • Automazioni critiche Python   │
                         │   • Cache SQLite                  │
                         │   • Piper TTS (offline)           │
                         │   • LoRa→MQTT bridge              │
                         └───────────────┬───────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
              ETHERNET            UART/USB             UART/USB
                    │                    │                    │
                    ▼                    ▼                    ▼
         ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
         │ 🎤 ESP32-C3      │  │ 🌐 ESP32-S3      │  │ 📡 HELTEC V3     │
         │    CHATBOT       │  │    GATEWAY       │  │    LoRa BRIDGE   │
         │                  │  │    ESP-NOW       │  │                  │
         │ • Online → VPS   │  │ • zh_gateway     │  │ • LoRa SX1262    │
         │ • Offline → Pico │  │ • LAN mode (ETH) │  │ • Meshtastic     │
         └──────────────────┘  └────────┬─────────┘  └────────┬─────────┘
                                        │                     │
                                        │ ESP-NOW             │ LoRa 868MHz
                                        │ (indoor <100m)      │ (outdoor 1-15km)
                                        │                     │
              ┌─────────────────────────┼─────────────────────┼────────────────┐
              │                         │                     │                │
              ▼              ▼          │          ▼          ▼          ▼     │
         ┌────────┐    ┌────────┐       │    ┌────────┐  ┌────────┐ ┌────────┐
         │ESPHome │    │ESPHome │       │    │WROOM+  │  │WROOM+  │ │MESH    │
         │2025.8+ │    │2025.8+ │       │    │DX-LR-30│  │DX-LR-30│ │NODES   │
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
- **Mesh**: Casa >150mq, multi-piano
  - **ZHNetwork** (consigliato): Più stabile di painlessMesh secondo community MySensors
  - **ESPHome 2025.8+**: Supporto nativo ESP-NOW mesh via YAML!

### ⚠️ CRITICO: WiFi Channel Lock

Se il gateway ESP32-S3 usa **WiFi + ESP-NOW simultaneamente**:
- Il router WiFi **DEVE** essere sullo stesso canale di ESP-NOW (solitamente canale 1)
- **Soluzione raccomandata**: Usa modalità **ESP_NOW_LAN** (Ethernet) invece di WiFi

```
MODALITÀ GATEWAY DISPONIBILI (zh_gateway):
├── ESP_NOW      → Solo nodo ESP-NOW (no internet)
├── ESP_NOW_WIFI → Gateway via WiFi (vincolo canale!)
└── ESP_NOW_LAN  → Gateway via Ethernet (PREFERITA ✅)
```

### LoRa (Outdoor)

| Caratteristica | Valore |
|----------------|--------|
| Frequenza | 868 MHz (Europa) |
| Range | 1-15+ km |
| Latenza | 1-5 secondi |
| Spreading Factor | 7-12 (10 consigliato) |
| Bandwidth | 125 kHz |
| Consumo | ~120mA TX, ~10µA deep sleep |

### ⚠️ Meshtastic MQTT: Policy "Zero-Hop" (Luglio 2024)

Il server pubblico Meshtastic ha implementato una policy **zero-hop** per ridurre il traffico:
- Con PSK di default, i messaggi MQTT **NON** popoleranno la mesh locale
- **Soluzione**: Configura un **PSK personalizzato** per pieno controllo

```yaml
# meshtastic config
lora:
  psk: "LA_TUA_CHIAVE_PERSONALIZZATA_BASE64"  # NON usare default!
```

---

## Struttura MQTT Topics

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
├── sync/                    ← NUOVO: Sincronizzazione VPS ↔ LuckFox
│   ├── vps_to_local/
│   │   ├── automations_update    → Aggiornamenti regole automazione
│   │   ├── config_update         → Nuove configurazioni
│   │   └── commands_queue        → Comandi in coda quando offline
│   └── local_to_vps/
│       ├── events_buffer         → Eventi bufferizzati durante offline
│       ├── offline_logs          → Log periodo disconnesso
│       └── heartbeat             → Keep-alive locale
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

### Aggiornamenti Importanti (Gennaio 2025)

#### ESP-NOW Gateway - Evoluzione

| Progetto | Framework | Caratteristiche | Raccomandazione |
|----------|-----------|-----------------|-----------------|
| **ESP-NOW-Gateway** | Arduino | v1.42, bug fix restart/update, 3 modalità | Buono per iniziare |
| **zh_gateway** | ESP-IDF | Mesh + diretta, OTA remoto, NTP, Syslog | **PREFERITO per produzione** |

```
zh_gateway vantaggi:
├── OTA firmware update via ESP-NOW per dispositivi remoti!
├── Sincronizzazione NTP integrata
├── Supporto Syslog per debugging distribuito
└── Maggiore stabilità su ESP32-S3
```

#### ESPHome 2025.8.0 - ESP-NOW Nativo!

**NOVITÀ**: ESPHome ha introdotto il supporto nativo per **ESP-NOW mesh communication**.

```yaml
# cucina.yaml - ESPHome 2025.8+
esphome:
  name: cucina

esp32:
  board: esp32dev

# NUOVO! ESP-NOW nativo senza codice custom
esp_now:
  peers:
    - mac_address: "AA:BB:CC:DD:EE:FF"  # Gateway

sensor:
  - platform: dht
    pin: GPIO4
    temperature:
      name: "Cucina Temperatura"
      on_value:
        - esp_now.send:
            mac_address: "AA:BB:CC:DD:EE:FF"
            data: !lambda 'return id(temp).state;'
```

### Tabella Progetti Aggiornata

| Componente | Progetto | URL | Note |
|------------|----------|-----|------|
| Gateway ESP-NOW | **zh_gateway** | https://github.com/aZholtikov/zh_gateway | **ESP-IDF, OTA, preferito** |
| Gateway Arduino | ESP-NOW-Gateway | https://github.com/aZholtikov/ESP-NOW-Gateway | v1.42, più semplice |
| Mesh Library | **ZHNetwork** | https://github.com/aZholtikov/ZHNetwork | Più stabile di painlessMesh |
| Sensori indoor | **ESPHome 2025.8+** | https://esphome.io/ | **ESP-NOW nativo!** |
| Multi-protocollo | OpenMQTTGateway | https://github.com/1technophile/OpenMQTTGateway | LoRa, BLE, 433MHz |
| LoRa Bridge | Meshtastic stock | https://meshtastic.org/ | Config PSK custom! |
| Meshtastic Python | meshtastic-bridge | https://github.com/geoffwhittington/meshtastic-bridge | Bridge MQTT |
| MQTT Broker | Mosquitto | https://mosquitto.org/ | Standard |
| MQTT Leggero | **NanoMQ** | https://nanomq.io/ | Alternativa ultra-leggera |
| TTS Offline | Piper TTS | https://github.com/rhasspy/piper | Leggero, italiano |
| DB Time-series | InfluxDB | https://www.influxdata.com/ | Per storico |
| Dashboard | Grafana | https://grafana.com/ | Visualizzazione |

### Stima Codice Custom vs Riuso (Aggiornata)

| Componente | Scrivi | Riusa |
|------------|--------|-------|
| Gateway ESP-NOW | 5% | 95% (zh_gateway) |
| Nodi sensori indoor | **0%** | **100% (ESPHome 2025.8+)** |
| Bridge LoRa | 0% | 100% (Meshtastic) |
| MQTT Broker | 0% | 100% |
| TTS locale | 0% | 100% |
| Plugin Xiaozhi | 70% | 30% |
| Automazioni | 80% | 20% |
| Sync VPS↔locale | 60% | 40% |

**Totale: ~25% custom, ~75% integrazione** (migliorato con ESPHome ESP-NOW)

---

## Piano di Sviluppo

### Fase 1: Minimo Funzionante

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ ESPHome     │      │ ESP32-S3    │      │ VPS Hetzner │
│ (1 sensore) │─────►│ zh_gateway  │─────►│ Mosquitto   │
│ DHT22       │ESPNOW│ (LAN mode)  │ MQTT │ + Xiaozhi   │
└─────────────┘      └─────────────┘      └─────────────┘
```

**Azioni:**
- [ ] Scegliere gateway: zh_gateway (ESP-IDF) vs ESPHome 2025.8+ puro
- [ ] Configurare ESP32-S3 in modalità **ESP_NOW_LAN** (Ethernet)
- [ ] Installare Mosquitto su VPS con TLS
- [ ] Plugin Xiaozhi minimale per MQTT
- [ ] Test: quanti nodi ESP-NOW simultanei gestisce l'ESP32-S3?

### Fase 1.5: Test Resilienza (NUOVO!)

**Prima di espandere, validare il failover:**

```
┌─────────────────────────────────────────────────────────┐
│                    TEST RESILIENZA                       │
├─────────────────────────────────────────────────────────┤
│ □ Simula caduta internet (stacca ethernet dal LuckFox)  │
│ □ Verifica automazioni critiche continuano              │
│ □ Conferma Piper TTS risponde senza latenza             │
│ □ Testa alert LoRa → Meshtastic su telefono             │
│ □ Verifica sync eventi quando internet torna            │
└─────────────────────────────────────────────────────────┘
```

### Fase 2: Meshtastic

```
┌─────────────┐      ┌─────────────┐
│ Heltec V3   │─────►│ VPS         │
│ Meshtastic  │ MQTT │ Xiaozhi     │
│ (PSK custom)│      │             │
└─────────────┘      └─────────────┘
```

**Azioni:**
- [ ] Flash Meshtastic su Heltec V3
- [ ] Configurare **PSK personalizzato** (NON default!)
- [ ] Configurare MQTT gateway in Meshtastic
- [ ] Plugin Xiaozhi per messaggi mesh

### Fase 3: Hub Locale + Sicurezza

```
┌─────────────┐
│ LuckFox     │◄───── Gateway + Heltec
│ Mosquitto   │
│ Automazioni │─────► VPS (sync TLS)
│ Piper TTS   │
└─────────────┘
```

**Azioni:**
- [ ] Setup LuckFox con Linux
- [ ] Installare Mosquitto con **autenticazione** (file passwd)
- [ ] Abilitare **TLS/SSL** per connessione VPS ↔ LuckFox
- [ ] Script automazioni Python
- [ ] MQTT bridge verso VPS

### Fase 4: Espansione (iterativo)

- [ ] Più sensori indoor (ESPHome YAML con ESP-NOW)
- [ ] Sensori outdoor LoRa (ESP32 + DX-LR-30)
- [ ] ESP32-CAM su WiFi dedicato (RTSP → NVR/Frigate)
- [ ] Automazioni avanzate
- [ ] Dashboard Grafana

> **Nota ESP32-CAM**: Le telecamere richiedono banda elevata, incompatibile con ESP-NOW (250 byte max) o LoRa. Mantenerle su rete WiFi dedicata con RTSP stream verso NVR locale (es. Frigate, MotionEye).

---

## Sicurezza

### Checklist Sicurezza (OBBLIGATORIA)

```
┌─────────────────────────────────────────────────────────┐
│                    SICUREZZA MQTT                        │
├─────────────────────────────────────────────────────────┤
│ □ Mosquitto con autenticazione (file passwd)            │
│ □ TLS/SSL per connessione VPS ↔ LuckFox                 │
│ □ Firewall VPS: porta MQTT solo da IP LuckFox           │
├─────────────────────────────────────────────────────────┤
│                    SICUREZZA ESP-NOW                     │
├─────────────────────────────────────────────────────────┤
│ □ Encryption key univoca (NON default!)                 │
│ □ Lista MAC address autorizzati                         │
├─────────────────────────────────────────────────────────┤
│                    SICUREZZA MESHTASTIC                  │
├─────────────────────────────────────────────────────────┤
│ □ PSK personalizzato (NON default!)                     │
│ □ Encryption MQTT abilitata                             │
└─────────────────────────────────────────────────────────┘
```

### Configurazione Mosquitto Sicura

```bash
# /etc/mosquitto/mosquitto.conf sul LuckFox

listener 1883 localhost
listener 8883
certfile /etc/mosquitto/certs/server.crt
keyfile /etc/mosquitto/certs/server.key
cafile /etc/mosquitto/certs/ca.crt

password_file /etc/mosquitto/passwd
allow_anonymous false
```

### ESP-NOW Encryption

```cpp
// zh_gateway o firmware custom
uint8_t esp_now_key[16] = {
    0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0,
    0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88
};
esp_now_set_pmk(esp_now_key);
```

---

## Critiche e Miglioramenti

### Problemi Identificati e Soluzioni

| Problema | Soluzione |
|----------|-----------|
| Troppa complessità iniziale | Sviluppo in fasi + Fase 1.5 resilienza |
| Reinventare la ruota | ESPHome 2025.8+, zh_gateway |
| Manca piano di fallback | Test standalone ogni componente |
| Sicurezza non considerata | Checklist sicurezza obbligatoria |
| Monitoring assente | Heartbeat, alert, Grafana |
| WiFi channel conflict | Usa ESP_NOW_LAN (Ethernet) |
| Meshtastic zero-hop | PSK personalizzato |

### Test Standalone Consigliati

```
Test 1: zh_gateway → MQTT broker locale → mosquitto_sub
        (senza Xiaozhi, senza VPS)

Test 2: Heltec V3 → Meshtastic app su telefono
        (senza MQTT, senza server, PSK custom)

Test 3: LuckFox → MQTT → Node-RED (visualizza dati)
        (prima di scrivere Python custom)

Test 4: Failover completo (stacca internet, verifica automazioni)
```

---

## Configurazioni Hardware

### ESP32-S3 Gateway (zh_gateway - PREFERITO)

```yaml
# menuconfig o sdkconfig
CONFIG_ZH_GATEWAY_MODE=ESP_NOW_LAN  # Ethernet preferito!
CONFIG_ZH_GATEWAY_NTP_ENABLED=y
CONFIG_ZH_GATEWAY_SYSLOG_ENABLED=y
CONFIG_ZH_GATEWAY_OTA_ENABLED=y

# MQTT settings
CONFIG_ZH_MQTT_BROKER="192.168.1.100"  # LuckFox
CONFIG_ZH_MQTT_PORT=1883
CONFIG_ZH_MQTT_USERNAME="gateway"
CONFIG_ZH_MQTT_PASSWORD="****"
```

### Heltec V3 (Meshtastic)

```yaml
# Configurazione via Meshtastic CLI o App
device:
  role: CLIENT_MUTE  # o ROUTER se serve relay

lora:
  region: EU_868
  psk: "BASE64_CHIAVE_PERSONALIZZATA"  # IMPORTANTE!

mqtt:
  enabled: true
  address: mqtts://tuo-vps.hetzner.com:8883  # TLS!
  username: meshtastic
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

# Sicurezza Mosquitto
mosquitto_passwd -c /etc/mosquitto/passwd xiaozhi
mosquitto_passwd /etc/mosquitto/passwd gateway
mosquitto_passwd /etc/mosquitto/passwd meshtastic

# Avvio servizi
systemctl enable mosquitto
```

### Sensori Indoor (ESPHome 2025.8+ con ESP-NOW)

```yaml
# cucina.yaml
esphome:
  name: cucina
  platform: ESP32
  board: esp32dev

# ESP-NOW nativo! (ESPHome 2025.8+)
esp_now:
  encryption_key: "la_tua_chiave_16_bytes"
  peers:
    - mac_address: "AA:BB:CC:DD:EE:FF"  # Gateway ESP32-S3

sensor:
  - platform: dht
    pin: GPIO4
    temperature:
      name: "Cucina Temperatura"
      on_value:
        then:
          - esp_now.send:
              peer: "AA:BB:CC:DD:EE:FF"
              data: !lambda |-
                char buf[32];
                sprintf(buf, "{\"temp\":%.1f}", x);
                return std::vector<uint8_t>(buf, buf + strlen(buf));
    humidity:
      name: "Cucina Umidita"
    update_interval: 30s

  - platform: adc
    pin: GPIO34
    name: "Cucina Gas"
    update_interval: 10s
    on_value_range:
      - above: 800
        then:
          - esp_now.send:
              peer: "AA:BB:CC:DD:EE:FF"
              data: "ALERT:GAS"
```

---

## Ottimizzazione Energetica

### Deep Sleep per Nodi Battery-Powered

Il consumo in deep sleep su ESP32 può scendere a **10-30µA**, permettendo operatività per **mesi o anni** con batterie.

**Calcolo autonomia**: Con batteria 18650 da 3000mAh e rilevazioni ogni 5 minuti → **8-12 mesi** di autonomia teorica.

#### ESPHome Deep Sleep Pattern

```yaml
# sensore_outdoor.yaml - Nodo a batteria
esphome:
  name: serra_outdoor
  on_boot:
    priority: -100
    then:
      - wait_until:
          condition:
            mqtt.connected:
      - delay: 5s
      - deep_sleep.enter:

deep_sleep:
  run_duration: 20s          # Tempo massimo attivo
  sleep_duration: 5min       # Intervallo letture
  wakeup_pin: GPIO33         # Wake-up da interrupt (opzionale)
  wakeup_pin_mode: KEEP_AWAKE

sensor:
  - platform: adc
    pin: GPIO35
    name: "Battery Voltage"
    attenuation: 11db
    filters:
      - multiply: 2.0        # Voltage divider (R1=R2)
    on_value_range:
      - below: 3.3           # Allarme batteria scarica
        then:
          - mqtt.publish:
              topic: "mesh/system/alerts"
              payload: "BATT_LOW_serra"
```

### ⚠️ ESP-NOW e Deep Sleep - Pattern Critico

**Problema**: ESP-NOW richiede che il **ricevitore (gateway) sia sempre attivo**.

**Soluzione**:
- Nodo si sveglia → Invia dato → Attende conferma → Torna in sleep (2-3 sec totali)
- Gateway ESP32-S3 rimane **sempre attivo** (alimentato da rete)

```cpp
// Nodo sensore ESP-NOW - pattern ottimizzato
#include <esp_now.h>
#include <esp_sleep.h>

volatile bool ackReceived = false;

void OnDataSent(const uint8_t *mac, esp_now_send_status_t status) {
    ackReceived = (status == ESP_NOW_SEND_SUCCESS);
}

void setup() {
    // Configura wake-up timer (5 minuti)
    esp_sleep_enable_timer_wakeup(5 * 60 * 1000000ULL);

    // Init WiFi + ESP-NOW
    WiFi.mode(WIFI_STA);
    esp_now_init();
    esp_now_register_send_cb(OnDataSent);

    // Aggiungi peer (gateway)
    esp_now_peer_info_t peer = {};
    memcpy(peer.peer_addr, gateway_mac, 6);
    esp_now_add_peer(&peer);

    // Leggi sensore
    float temp = readTemperature();
    float battery = readBattery();

    // Prepara payload
    SensorData data = {temp, battery, millis()};

    // Invia via ESP-NOW
    esp_now_send(gateway_mac, (uint8_t*)&data, sizeof(data));

    // Attendi conferma (max 3 sec)
    unsigned long start = millis();
    while (!ackReceived && millis() - start < 3000) {
        delay(10);
    }

    // Log errore se non confermato
    if (!ackReceived) {
        // Salva in RTC memory per retry
        rtc_data.failed_sends++;
    }

    // DORMI - loop() non viene mai eseguito
    esp_deep_sleep_start();
}

void loop() {
    // Mai raggiunto
}
```

---

## Gestione Code Offline

### Problema Critico

**Scenario**: LuckFox perde connessione VPS per 2 ore. Accumula 1000+ messaggi MQTT. Riconnessione → **flood di messaggi**.

### Soluzione: Buffer con Aggregazione

```python
# luckfox_queue_manager.py
import sqlite3
import json
from datetime import datetime, timedelta

class OfflineBuffer:
    def __init__(self, db_path='mqtt_buffer.db', max_size=5000):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.max_size = max_size
        self._init_db()

    def _init_db(self):
        """Crea tabelle se non esistono"""
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS sensor_buffer (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                value REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS event_buffer (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                payload TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_sensor_topic ON sensor_buffer(topic);
        ''')

    def add_message(self, topic, payload):
        """Aggiungi a buffer quando offline"""
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload

            # Aggrega sensori (temperatura, umidità, etc.)
            if any(x in topic for x in ['temperatura', 'umidita', 'gas', 'battery']):
                value = data.get('value', data) if isinstance(data, dict) else data
                self.db.execute(
                    "INSERT INTO sensor_buffer (topic, value) VALUES (?, ?)",
                    (topic, float(value))
                )
            else:
                # Eventi non aggregabili (alert, comandi)
                self.db.execute(
                    "INSERT INTO event_buffer (topic, payload) VALUES (?, ?)",
                    (topic, json.dumps(data))
                )
            self.db.commit()
            self._cleanup_old()
        except Exception as e:
            print(f"Buffer error: {e}")

    def _cleanup_old(self):
        """Rimuovi dati vecchi > 24h o se troppi"""
        self.db.execute(
            "DELETE FROM sensor_buffer WHERE timestamp < datetime('now', '-24 hours')"
        )
        # Mantieni solo ultimi max_size
        self.db.execute(f'''
            DELETE FROM sensor_buffer WHERE id NOT IN (
                SELECT id FROM sensor_buffer ORDER BY timestamp DESC LIMIT {self.max_size}
            )
        ''')
        self.db.commit()

    def sync_to_vps(self, mqtt_client):
        """Sync intelligente quando torna online"""
        # 1. Invia aggregati sensori (media per topic)
        cursor = self.db.execute('''
            SELECT topic,
                   AVG(value) as avg_val,
                   MIN(value) as min_val,
                   MAX(value) as max_val,
                   COUNT(*) as samples,
                   MIN(timestamp) as first_ts,
                   MAX(timestamp) as last_ts
            FROM sensor_buffer
            GROUP BY topic
        ''')

        for row in cursor:
            topic, avg_val, min_val, max_val, samples, first_ts, last_ts = row
            payload = {
                "type": "aggregated",
                "avg": round(avg_val, 2),
                "min": round(min_val, 2),
                "max": round(max_val, 2),
                "samples": samples,
                "period": {"from": first_ts, "to": last_ts}
            }
            mqtt_client.publish(f"mesh/sync/local_to_vps/{topic}", json.dumps(payload))

        # 2. Invia eventi critici (non aggregati)
        events = self.db.execute(
            "SELECT topic, payload, timestamp FROM event_buffer ORDER BY timestamp"
        ).fetchall()

        for topic, payload, ts in events:
            mqtt_client.publish(topic, payload)

        # 3. Pulisci buffer dopo sync
        self.db.execute("DELETE FROM sensor_buffer")
        self.db.execute("DELETE FROM event_buffer")
        self.db.commit()

        return len(events)

# Uso nel main loop
buffer = OfflineBuffer()

def on_message(client, userdata, msg):
    if not is_vps_connected():
        buffer.add_message(msg.topic, msg.payload)
    else:
        # Forward normale al VPS
        vps_client.publish(msg.topic, msg.payload)

def on_vps_reconnect():
    """Chiamato quando VPS torna online"""
    synced = buffer.sync_to_vps(vps_client)
    print(f"Synced {synced} buffered events to VPS")
```

---

## Monitoring e Alerting

### Heartbeat System

```
# Topics heartbeat - ogni dispositivo pubblica ogni 60 sec
mesh/system/heartbeat/{dispositivo}
  Payload: {
    "uptime": 3600,
    "rssi": -65,
    "free_heap": 45000,
    "battery": 3.7,        # Solo per nodi a batteria
    "wifi_channel": 1,
    "version": "1.0.2"
  }
```

### Watchdog su LuckFox

```python
# luckfox_watchdog.py
import time
import json
from datetime import datetime, timedelta
from threading import Thread

class DeviceWatchdog:
    def __init__(self, mqtt_client, alert_callback):
        self.devices = {}  # {device_id: last_seen_datetime}
        self.timeouts = {
            "gateway": timedelta(minutes=2),     # Gateway sempre attivo
            "sensor_indoor": timedelta(minutes=10),  # Sensori indoor
            "sensor_outdoor": timedelta(minutes=15), # Outdoor (deep sleep)
            "heltec": timedelta(minutes=5),      # Bridge LoRa
        }
        self.mqtt = mqtt_client
        self.alert = alert_callback
        self.running = True

    def on_heartbeat(self, topic, payload):
        """Callback per messaggi heartbeat"""
        device = topic.split('/')[-1]
        data = json.loads(payload)

        self.devices[device] = {
            "last_seen": datetime.now(),
            "data": data
        }

        # Check batteria scarica
        if data.get("battery", 4.2) < 3.3:
            self.alert(f"BATT_LOW: {device} @ {data['battery']}V")

        # Check heap basso (memory leak?)
        if data.get("free_heap", 100000) < 20000:
            self.alert(f"LOW_HEAP: {device} @ {data['free_heap']} bytes")

    def check_devices(self):
        """Controlla dispositivi offline - chiamare ogni 60 sec"""
        now = datetime.now()
        offline = []

        for device, info in self.devices.items():
            last_seen = info["last_seen"]
            device_type = self._get_device_type(device)
            timeout = self.timeouts.get(device_type, timedelta(minutes=10))

            if now - last_seen > timeout:
                offline.append(device)

        for device in offline:
            self.alert(f"OFFLINE: {device} (last seen: {self.devices[device]['last_seen']})")
            # Invia alert LoRa per dispositivi critici
            if "gateway" in device:
                self.send_lora_emergency(f"Gateway {device} OFFLINE!")

    def _get_device_type(self, device_name):
        if "gateway" in device_name.lower():
            return "gateway"
        if "outdoor" in device_name.lower() or "serra" in device_name.lower():
            return "sensor_outdoor"
        if "heltec" in device_name.lower() or "lora" in device_name.lower():
            return "heltec"
        return "sensor_indoor"

    def send_lora_emergency(self, message):
        """Invia alert via LoRa/Meshtastic"""
        self.mqtt.publish("meshtastic/tx", json.dumps({
            "to": "broadcast",
            "text": f"🚨 {message}",
            "priority": "high"
        }))

    def run(self):
        """Thread watchdog"""
        while self.running:
            self.check_devices()
            time.sleep(60)

    def start(self):
        Thread(target=self.run, daemon=True).start()

# Uso
def send_alert(msg):
    print(f"[ALERT] {msg}")
    # Invia push notification, email, etc.

watchdog = DeviceWatchdog(mqtt_client, send_alert)
watchdog.start()

# Subscribe a heartbeat
mqtt_client.subscribe("mesh/system/heartbeat/#")
mqtt_client.message_callback_add("mesh/system/heartbeat/#", watchdog.on_heartbeat)
```

### ESPHome Heartbeat Config

```yaml
# Aggiungi a ogni dispositivo ESPHome
interval:
  - interval: 60s
    then:
      - mqtt.publish:
          topic: !lambda |-
            return "mesh/system/heartbeat/" + App.get_name();
          payload: !lambda |-
            char buf[200];
            snprintf(buf, sizeof(buf),
              "{\"uptime\":%d,\"rssi\":%d,\"free_heap\":%d,\"version\":\"%s\"}",
              millis()/1000,
              WiFi.RSSI(),
              ESP.getFreeHeap(),
              App.get_compilation_time().c_str()
            );
            return std::string(buf);
```

---

## Dashboard Minimale LuckFox

Webserver Flask ultra-leggero per status locale (funziona **senza internet**):

```python
# luckfox_dashboard.py
from flask import Flask, jsonify, render_template_string
import sqlite3
import json
import subprocess

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🦊 LuckFox Status</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { font-family: monospace; background: #1a1a2e; color: #eee; padding: 20px; }
        .card { background: #16213e; padding: 15px; margin: 10px 0; border-radius: 8px; }
        .online { color: #4ade80; }
        .offline { color: #f87171; }
        .warning { color: #fbbf24; }
        h1 { color: #818cf8; }
        table { width: 100%; border-collapse: collapse; }
        td, th { padding: 8px; text-align: left; border-bottom: 1px solid #333; }
    </style>
</head>
<body>
    <h1>🦊 LuckFox Pico - Hub Status</h1>

    <div class="card">
        <h3>🌐 Connettività</h3>
        <p>Internet: <span class="{{ 'online' if status.internet else 'offline' }}">
            {{ '✅ Online' if status.internet else '❌ Offline' }}</span></p>
        <p>VPS MQTT: <span class="{{ 'online' if status.vps_mqtt else 'offline' }}">
            {{ '✅ Connected' if status.vps_mqtt else '❌ Disconnected' }}</span></p>
        <p>Messaggi in buffer: {{ status.buffered_messages }}</p>
    </div>

    <div class="card">
        <h3>📡 Dispositivi ({{ devices|length }})</h3>
        <table>
            <tr><th>Device</th><th>Ultimo contatto</th><th>RSSI</th><th>Batteria</th></tr>
            {% for d in devices %}
            <tr>
                <td>{{ d.name }}</td>
                <td class="{{ 'online' if d.online else 'warning' }}">{{ d.last_seen }}</td>
                <td>{{ d.rssi }} dBm</td>
                <td>{{ d.battery if d.battery else 'N/A' }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <div class="card">
        <h3>🌡️ Ultime Letture</h3>
        <table>
            <tr><th>Sensore</th><th>Valore</th><th>Timestamp</th></tr>
            {% for r in readings %}
            <tr>
                <td>{{ r.device }}</td>
                <td>{{ r.value }}</td>
                <td>{{ r.timestamp }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>

    <p style="color:#666;font-size:12px;">Auto-refresh ogni 30 sec |
       Uptime: {{ status.uptime }}</p>
</body>
</html>
'''

def is_internet_up():
    """Check connettività internet"""
    try:
        subprocess.check_call(
            ['ping', '-c', '1', '-W', '2', '8.8.8.8'],
            stdout=subprocess.DEVNULL
        )
        return True
    except:
        return False

def get_system_status():
    """Raccoglie status sistema"""
    db = sqlite3.connect('sensors.db')

    buffered = db.execute(
        "SELECT COUNT(*) FROM sensor_buffer"
    ).fetchone()[0]

    # Uptime sistema
    with open('/proc/uptime') as f:
        uptime_sec = int(float(f.read().split()[0]))
        hours, rem = divmod(uptime_sec, 3600)
        mins, secs = divmod(rem, 60)
        uptime = f"{hours}h {mins}m"

    return {
        "internet": is_internet_up(),
        "vps_mqtt": mqtt_connected,  # Variabile globale
        "buffered_messages": buffered,
        "uptime": uptime
    }

def get_devices():
    """Lista dispositivi dal watchdog"""
    devices = []
    for name, info in watchdog.devices.items():
        devices.append({
            "name": name,
            "last_seen": info["last_seen"].strftime("%H:%M:%S"),
            "online": (datetime.now() - info["last_seen"]).seconds < 300,
            "rssi": info["data"].get("rssi", "N/A"),
            "battery": info["data"].get("battery")
        })
    return devices

def get_latest_readings(limit=10):
    """Ultime letture sensori"""
    db = sqlite3.connect('sensors.db')
    rows = db.execute('''
        SELECT device, temperature, humidity, timestamp
        FROM sensors ORDER BY timestamp DESC LIMIT ?
    ''', (limit,)).fetchall()

    return [{
        "device": r[0],
        "value": f"{r[1]}°C / {r[2]}%",
        "timestamp": r[3]
    } for r in rows]

@app.route('/')
def dashboard():
    """Dashboard HTML"""
    return render_template_string(HTML_TEMPLATE,
        status=get_system_status(),
        devices=get_devices(),
        readings=get_latest_readings()
    )

@app.route('/api/status')
def api_status():
    """API REST per status sistema"""
    return jsonify({
        "status": get_system_status(),
        "devices": get_devices(),
        "readings": get_latest_readings(20)
    })

@app.route('/api/devices')
def api_devices():
    """API REST lista dispositivi"""
    return jsonify(get_devices())

if __name__ == '__main__':
    # Accessibile da rete locale anche senza internet
    app.run(host='0.0.0.0', port=5000, debug=False)
```

**Accesso**: `http://luckfox.local:5000` o `http://192.168.1.100:5000`

### Systemd Service per Dashboard

```bash
# /etc/systemd/system/luckfox-dashboard.service
[Unit]
Description=LuckFox IoT Dashboard
After=network.target mosquitto.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/iot
ExecStart=/usr/bin/python3 luckfox_dashboard.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Abilitazione
systemctl enable luckfox-dashboard
systemctl start luckfox-dashboard
```

---

## Meshtastic Security - Generazione PSK

```bash
# 1. Genera PSK casuale (32 bytes base64)
meshtastic --set-default-channel
meshtastic --ch-set psk random --ch-index 0

# 2. Configura regione EU
meshtastic --set lora.region EU_868

# 3. Visualizza PSK per condividerlo
meshtastic --ch-get --ch-index 0

# Output esempio:
# Channel 0:
#   PSK: base64:YWJjZGVmZ2hpamtsbW5vcA==
#   Name: LongFast

# 4. Applica stesso PSK su tutti i nodi Meshtastic
meshtastic --ch-set psk base64:YWJjZGVmZ2hpamtsbW5vcA== --ch-index 0
```

### Meshtastic Config Completa

```yaml
# Configurazione sicura Heltec V3
device:
  role: ROUTER           # Relay messaggi
  serial_enabled: true   # Debug via USB

lora:
  region: EU_868
  hop_limit: 3           # Max hop per mesh
  tx_power: 20           # dBm (max EU)

channel:
  - index: 0
    name: "IoTHome"
    psk: "base64:YOUR_RANDOM_PSK_HERE"
    uplink_enabled: true
    downlink_enabled: true

mqtt:
  enabled: true
  address: mqtts://vps.example.com:8883
  username: meshtastic
  password: "****"
  encryption_enabled: true
  json_enabled: true
  tls_enabled: true      # IMPORTANTE!
```

---

## Firmware e Sistemi Operativi

### Tabella Firmware per Dispositivo

| Dispositivo | Firmware | Versione | Note |
|-------------|----------|----------|------|
| **ESP32-C3 Mini** (Chatbot) | [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) | main | Client vocale AI |
| **ESP32-S3** (Gateway) | [zh_gateway](https://github.com/aZholtikov/zh_gateway) | latest | ESP-IDF, preferito |
| **ESP32-S3** (Gateway alt.) | [ESP-NOW-Gateway](https://github.com/aZholtikov/ESP-NOW-Gateway) | v1.42+ | Arduino, più semplice |
| **ESP32-WROOM** (Sensori) | [ESPHome](https://esphome.io/) | 2025.8+ | ESP-NOW nativo YAML |
| **ESP32-WROOM** (Sensori alt.) | [ZHNetwork](https://github.com/aZholtikov/ZHNetwork) | latest | Mesh custom |
| **ESP32 + DX-LR-30** (LoRa) | Custom Arduino | - | Vedi sezione sotto |
| **Heltec V3** | [Meshtastic](https://meshtastic.org/downloads) | 2.5+ | Firmware ufficiale |
| **ESP32-CAM** | [ESPHome camera](https://esphome.io/components/esp32_camera.html) | latest | RTSP stream |

### Sistemi Operativi Hub Locale

#### LuckFox Pico (Consigliato)

| OS | Download | Note |
|----|----------|------|
| **Buildroot Linux** (ufficiale) | [LuckFox SDK](https://github.com/LuckfoxTECH/luckfox-pico) | Leggero, consigliato |
| **Ubuntu 22.04** | [LuckFox Images](https://github.com/LuckfoxTECH/luckfox-pico/releases) | Più pesante ma familiare |

```bash
# Setup Buildroot LuckFox
# 1. Download immagine
wget https://github.com/LuckfoxTECH/luckfox-pico/releases/download/v1.3/LuckFox_Pico_Ultra_Buildroot.img.xz

# 2. Flash su SD card
xzcat LuckFox_Pico_Ultra_Buildroot.img.xz | sudo dd of=/dev/sdX bs=4M status=progress

# 3. Boot e connetti via SSH
ssh root@192.168.1.xxx  # Password: luckfox

# 4. Installa dipendenze IoT
opkg update
opkg install mosquitto mosquitto-client python3 python3-pip
pip3 install paho-mqtt flask piper-tts
```

#### Raspberry Pi (Alternativa)

| OS | Download | Note |
|----|----------|------|
| **Raspberry Pi OS Lite** | [Official](https://www.raspberrypi.com/software/) | Headless, consigliato |
| **DietPi** | [DietPi.com](https://dietpi.com/) | Ultra-leggero |
| **Home Assistant OS** | [HA](https://www.home-assistant.io/) | Se usi già HA |

```bash
# Setup Raspberry Pi per IoT Hub
sudo apt update && sudo apt install -y \
    mosquitto mosquitto-clients \
    python3-pip python3-venv \
    sqlite3

# Piper TTS
pip3 install piper-tts
piper --download-voice it_IT-riccardo-medium

# Servizi
sudo systemctl enable mosquitto
```

### Firmware Custom LoRa (ESP32 + DX-LR-30)

```cpp
// lora_sensor_node.ino - Nodo outdoor con DX-LR-30
#include <SPI.h>
#include <LoRa.h>
#include <esp_sleep.h>
#include <ArduinoJson.h>

// Pin DX-LR-30 → ESP32
#define LORA_SCK   18
#define LORA_MISO  19
#define LORA_MOSI  23
#define LORA_SS    5
#define LORA_RST   14
#define LORA_DIO0  26

// Configurazione EU868
#define LORA_FREQ  868E6
#define LORA_SF    10      // Spreading Factor
#define LORA_BW    125E3   // Bandwidth
#define LORA_TX_POWER 17   // dBm

// Sleep
#define SLEEP_MINUTES 5

void setup() {
    Serial.begin(115200);

    // Init LoRa
    LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
    if (!LoRa.begin(LORA_FREQ)) {
        Serial.println("LoRa init failed!");
        esp_deep_sleep_start();
    }

    LoRa.setSpreadingFactor(LORA_SF);
    LoRa.setSignalBandwidth(LORA_BW);
    LoRa.setTxPower(LORA_TX_POWER);

    // Leggi sensori
    float temp = readTemperature();
    float humidity = readHumidity();
    float battery = readBattery();

    // Prepara JSON
    StaticJsonDocument<200> doc;
    doc["node"] = "serra";
    doc["temp"] = temp;
    doc["hum"] = humidity;
    doc["bat"] = battery;
    doc["ts"] = millis();

    String payload;
    serializeJson(doc, payload);

    // Invia via LoRa
    LoRa.beginPacket();
    LoRa.print(payload);
    LoRa.endPacket(true);  // async

    // Attendi TX completato
    delay(100);

    // Deep sleep
    esp_sleep_enable_timer_wakeup(SLEEP_MINUTES * 60 * 1000000ULL);
    esp_deep_sleep_start();
}

void loop() {
    // Mai raggiunto
}
```

---

## Integrazione Xiaozhi Chatbot

### Architettura Plugin Domotica

Il chatbot Xiaozhi integra funzioni vocali per il controllo della rete IoT mesh:

```
┌─────────────────────────────────────────────────────────────────┐
│                    XIAOZHI SERVER (VPS)                          │
├─────────────────────────────────────────────────────────────────┤
│  plugins_func/functions/                                         │
│  ├── domotica.py           → Controllo dispositivi Tuya/MQTT    │
│  ├── hass_control.py       → Integrazione Home Assistant        │
│  ├── mesh_iot_monitor.py   → Monitor sensori mesh (NUOVO)       │
│  ├── mesh_alerts.py        → Gestione allarmi IoT (NUOVO)       │
│  └── automazioni_vocali.py → Trigger automazioni (NUOVO)        │
└─────────────────────────────────────────────────────────────────┘
```

### Plugin: Monitor Sensori Mesh

```python
# plugins_func/functions/mesh_iot_monitor.py
"""
Monitor vocale per rete sensori Mesh IoT
Trigger: "temperatura serra", "stato sensori", "batteria nodi"
"""

import json
import asyncio
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Client MQTT globale (inizializzato all'avvio)
mqtt_client = None
sensor_cache = {}  # Cache ultime letture

MESH_MONITOR_DESC = {
    "type": "function",
    "function": {
        "name": "mesh_iot_monitor",
        "description": (
            "Legge stato sensori dalla rete mesh IoT. "
            "Trigger: temperatura serra, umidità cucina, stato sensori, "
            "batteria nodi, quanti gradi ci sono in garage"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Posizione sensore: cucina, soggiorno, serra, garage, esterno"
                },
                "sensor_type": {
                    "type": "string",
                    "enum": ["temperatura", "umidita", "gas", "movimento", "batteria", "tutti"],
                    "description": "Tipo di dato richiesto"
                },
                "action": {
                    "type": "string",
                    "enum": ["read", "status", "history"],
                    "description": "Azione: lettura singola, stato sistema, storico"
                }
            },
            "required": ["action"]
        }
    }
}


def get_sensor_data(location: str = None, sensor_type: str = None) -> dict:
    """Recupera dati sensori dalla cache MQTT"""
    results = {}

    for topic, data in sensor_cache.items():
        # Filtra per location
        if location and location.lower() not in topic.lower():
            continue

        # Filtra per tipo sensore
        if sensor_type and sensor_type != "tutti":
            if sensor_type not in topic.lower():
                continue

        age = (datetime.now() - data['timestamp']).seconds
        results[topic] = {
            **data,
            'age_seconds': age,
            'stale': age > 600  # >10 min = dato vecchio
        }

    return results


def format_sensor_response(data: dict, location: str = None) -> tuple:
    """Formatta risposta per TTS"""
    if not data:
        text = f"Non ho dati recenti per {location or 'i sensori'}."
        return text, text

    spoken_parts = []
    display_parts = []

    for topic, info in data.items():
        node = topic.split('/')[-2] if '/' in topic else topic
        sensor = topic.split('/')[-1] if '/' in topic else 'valore'
        value = info.get('value', 'N/A')

        if 'temperatura' in sensor.lower() or 'temp' in sensor.lower():
            spoken_parts.append(f"{node}: {value} gradi")
            display_parts.append(f"🌡️ {node}: {value}°C")
        elif 'umidita' in sensor.lower() or 'hum' in sensor.lower():
            spoken_parts.append(f"{node}: {value} percento di umidità")
            display_parts.append(f"💧 {node}: {value}%")
        elif 'gas' in sensor.lower():
            spoken_parts.append(f"{node}: livello gas {value}")
            display_parts.append(f"⚠️ {node} gas: {value}")
        elif 'battery' in sensor.lower() or 'bat' in sensor.lower():
            spoken_parts.append(f"{node}: batteria al {value} percento")
            display_parts.append(f"🔋 {node}: {value}%")
        else:
            spoken_parts.append(f"{node} {sensor}: {value}")
            display_parts.append(f"📊 {node} {sensor}: {value}")

        if info.get('stale'):
            display_parts[-1] += " ⚠️(vecchio)"

    spoken = ". ".join(spoken_parts[:5])  # Max 5 per TTS
    display = "\n".join(display_parts)

    return display, spoken


@register_function('mesh_iot_monitor', MESH_MONITOR_DESC, ToolType.WAIT)
def mesh_iot_monitor(conn, action: str = "read", location: str = None, sensor_type: str = None):
    """Legge stato sensori mesh"""
    logger.bind(tag=TAG).info(f"Mesh monitor: action={action}, location={location}, type={sensor_type}")

    if action == "status":
        # Stato generale sistema
        total = len(sensor_cache)
        stale = sum(1 for d in sensor_cache.values()
                   if (datetime.now() - d['timestamp']).seconds > 600)
        online = total - stale

        display = f"**Stato Rete Mesh IoT**\n\n"
        display += f"📡 Sensori totali: {total}\n"
        display += f"✅ Online: {online}\n"
        display += f"⚠️ Non risponde: {stale}\n"

        spoken = f"La rete mesh ha {total} sensori, {online} online"
        if stale > 0:
            spoken += f", attenzione {stale} non rispondono"

        return ActionResponse(Action.RESPONSE, display, spoken)

    elif action == "read":
        data = get_sensor_data(location, sensor_type)
        display, spoken = format_sensor_response(data, location)

        if location:
            intro = f"**Sensori {location.title()}**\n\n"
        else:
            intro = "**Letture Sensori**\n\n"

        return ActionResponse(Action.RESPONSE, intro + display, spoken)

    elif action == "history":
        # TODO: Implementare storico da SQLite
        return ActionResponse(
            Action.RESPONSE,
            "Storico non ancora implementato",
            "La funzione storico sarà disponibile presto"
        )

    return ActionResponse(Action.RESPONSE, "Comando non riconosciuto", "Non ho capito la richiesta")


# === MQTT Callback per popolare cache ===
def on_mesh_message(client, userdata, msg):
    """Callback MQTT per aggiornare cache sensori"""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        sensor_cache[topic] = {
            'value': payload.get('value', payload),
            'timestamp': datetime.now(),
            'raw': payload
        }

        logger.bind(tag=TAG).debug(f"Sensor update: {topic} = {payload}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"MQTT parse error: {e}")


def init_mqtt_listener(broker: str, port: int = 1883):
    """Inizializza listener MQTT per sensori mesh"""
    import paho.mqtt.client as mqtt

    global mqtt_client
    mqtt_client = mqtt.Client()
    mqtt_client.on_message = on_mesh_message
    mqtt_client.connect(broker, port)
    mqtt_client.subscribe("mesh/#")
    mqtt_client.loop_start()

    logger.bind(tag=TAG).info(f"MQTT listener started for mesh sensors")
```

### Plugin: Gestione Allarmi IoT

```python
# plugins_func/functions/mesh_alerts.py
"""
Gestione allarmi dalla rete mesh IoT
Riceve alert (gas, fumo, intrusione) e notifica vocalmente
"""

import json
import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

# Storico allarmi
alert_history = []
active_alerts = {}

# Configurazione soglie
ALERT_THRESHOLDS = {
    "gas": {"warning": 500, "critical": 800, "emergency": 1000},
    "fumo": {"warning": 100, "critical": 200, "emergency": 300},
    "temperatura": {"warning": 35, "critical": 45, "emergency": 60},
    "batteria": {"warning": 20, "critical": 10, "emergency": 5},
}

MESH_ALERTS_DESC = {
    "type": "function",
    "function": {
        "name": "mesh_alerts",
        "description": (
            "Gestisce allarmi dalla rete IoT mesh. "
            "Trigger: ci sono allarmi, stato allarmi, silenzia allarme, "
            "storico allarmi, emergenze attive"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "history", "silence", "test"],
                    "description": "Azione: stato, storico, silenzia, test"
                },
                "alert_id": {
                    "type": "string",
                    "description": "ID allarme da silenziare"
                }
            },
            "required": ["action"]
        }
    }
}


def process_alert(topic: str, value: float, node: str) -> Optional[dict]:
    """Processa un valore e genera allarme se necessario"""
    sensor_type = None
    for t in ALERT_THRESHOLDS.keys():
        if t in topic.lower():
            sensor_type = t
            break

    if not sensor_type:
        return None

    thresholds = ALERT_THRESHOLDS[sensor_type]
    level = None

    # Batteria ha logica invertita
    if sensor_type == "batteria":
        if value <= thresholds["emergency"]:
            level = AlertLevel.EMERGENCY
        elif value <= thresholds["critical"]:
            level = AlertLevel.CRITICAL
        elif value <= thresholds["warning"]:
            level = AlertLevel.WARNING
    else:
        if value >= thresholds["emergency"]:
            level = AlertLevel.EMERGENCY
        elif value >= thresholds["critical"]:
            level = AlertLevel.CRITICAL
        elif value >= thresholds["warning"]:
            level = AlertLevel.WARNING

    if level:
        alert = {
            "id": f"{node}_{sensor_type}_{datetime.now().strftime('%H%M%S')}",
            "node": node,
            "sensor": sensor_type,
            "value": value,
            "level": level.value,
            "timestamp": datetime.now(),
            "acknowledged": False
        }
        return alert

    return None


def get_alert_message(alert: dict) -> tuple:
    """Genera messaggio vocale per allarme"""
    level = alert["level"]
    node = alert["node"]
    sensor = alert["sensor"]
    value = alert["value"]

    if level == "emergency":
        prefix = "🚨 EMERGENZA!"
        spoken_prefix = "Attenzione! Emergenza!"
    elif level == "critical":
        prefix = "⚠️ ALLARME CRITICO"
        spoken_prefix = "Allarme critico!"
    else:
        prefix = "⚡ Avviso"
        spoken_prefix = "Avviso."

    messages = {
        "gas": (f"{prefix} Gas elevato in {node}: {value}",
                f"{spoken_prefix} Rilevato gas elevato in {node}. Valore {value}. Verifica immediatamente!"),
        "fumo": (f"{prefix} Fumo rilevato in {node}: {value}",
                 f"{spoken_prefix} Fumo rilevato in {node}! Controlla subito!"),
        "temperatura": (f"{prefix} Temperatura alta in {node}: {value}°C",
                        f"{spoken_prefix} Temperatura troppo alta in {node}. {value} gradi."),
        "batteria": (f"{prefix} Batteria scarica {node}: {value}%",
                     f"{spoken_prefix} La batteria di {node} è quasi scarica. {value} percento."),
    }

    return messages.get(sensor, (f"{prefix} {sensor} in {node}: {value}",
                                  f"{spoken_prefix} {sensor} anomalo in {node}"))


@register_function('mesh_alerts', MESH_ALERTS_DESC, ToolType.WAIT)
def mesh_alerts(conn, action: str = "status", alert_id: str = None):
    """Gestisce allarmi mesh"""
    logger.bind(tag=TAG).info(f"Mesh alerts: action={action}")

    if action == "status":
        if not active_alerts:
            return ActionResponse(
                Action.RESPONSE,
                "✅ **Nessun allarme attivo**\n\nTutti i sensori sono nella norma.",
                "Nessun allarme attivo. Tutti i sensori sono nella norma."
            )

        display = "**🚨 ALLARMI ATTIVI**\n\n"
        spoken_parts = [f"Ci sono {len(active_alerts)} allarmi attivi."]

        for aid, alert in active_alerts.items():
            level_icon = {"emergency": "🚨", "critical": "⚠️", "warning": "⚡"}.get(alert["level"], "ℹ️")
            display += f"{level_icon} **{alert['node']}** - {alert['sensor']}: {alert['value']}\n"
            display += f"   Ora: {alert['timestamp'].strftime('%H:%M:%S')}\n\n"

            if alert["level"] in ["emergency", "critical"]:
                spoken_parts.append(f"{alert['sensor']} in {alert['node']}")

        return ActionResponse(Action.RESPONSE, display, " ".join(spoken_parts))

    elif action == "history":
        if not alert_history:
            return ActionResponse(
                Action.RESPONSE,
                "📜 Nessun allarme nello storico recente",
                "Non ci sono allarmi nello storico recente"
            )

        display = "**📜 Storico Allarmi (ultime 24h)**\n\n"
        for alert in alert_history[-10:]:  # Ultimi 10
            level_icon = {"emergency": "🚨", "critical": "⚠️", "warning": "⚡"}.get(alert["level"], "ℹ️")
            display += f"{level_icon} {alert['timestamp'].strftime('%H:%M')} - {alert['node']}: {alert['sensor']} ({alert['value']})\n"

        return ActionResponse(
            Action.RESPONSE,
            display,
            f"Ci sono {len(alert_history)} allarmi nello storico recente"
        )

    elif action == "silence":
        if alert_id and alert_id in active_alerts:
            alert = active_alerts.pop(alert_id)
            alert["acknowledged"] = True
            alert_history.append(alert)
            return ActionResponse(
                Action.RESPONSE,
                f"✅ Allarme {alert_id} silenziato",
                f"Allarme {alert['node']} silenziato"
            )
        elif not alert_id and active_alerts:
            # Silenzia tutti
            count = len(active_alerts)
            for a in active_alerts.values():
                a["acknowledged"] = True
                alert_history.append(a)
            active_alerts.clear()
            return ActionResponse(
                Action.RESPONSE,
                f"✅ {count} allarmi silenziati",
                f"Ho silenziato {count} allarmi"
            )
        else:
            return ActionResponse(
                Action.RESPONSE,
                "Nessun allarme da silenziare",
                "Non ci sono allarmi da silenziare"
            )

    elif action == "test":
        # Test allarme
        test_alert = {
            "id": "test_001",
            "node": "test",
            "sensor": "gas",
            "value": 850,
            "level": "critical",
            "timestamp": datetime.now(),
            "acknowledged": False
        }
        active_alerts["test_001"] = test_alert
        display, spoken = get_alert_message(test_alert)
        return ActionResponse(Action.RESPONSE, display, spoken)

    return ActionResponse(Action.RESPONSE, "Comando non riconosciuto", "Non ho capito")


# === Callback MQTT per allarmi ===
def on_alert_message(client, userdata, msg):
    """Callback per messaggi di allarme"""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        # Estrai nodo dal topic
        parts = topic.split('/')
        node = parts[2] if len(parts) > 2 else "unknown"

        value = payload.get('value', payload)
        if isinstance(value, (int, float)):
            alert = process_alert(topic, value, node)

            if alert:
                active_alerts[alert["id"]] = alert
                alert_history.append(alert)

                # Trigger notifica vocale immediata per emergenze
                if alert["level"] in ["emergency", "critical"]:
                    display, spoken = get_alert_message(alert)
                    logger.bind(tag=TAG).warning(f"ALERT: {spoken}")
                    # TODO: Invia a tutti i client connessi
                    # broadcast_to_clients(spoken)

    except Exception as e:
        logger.bind(tag=TAG).error(f"Alert processing error: {e}")
```

### Plugin: Automazioni Vocali

```python
# plugins_func/functions/automazioni_vocali.py
"""
Trigger automazioni IoT tramite comandi vocali
Trigger: "modalità notte", "scenario cinema", "risparmio energetico"
"""

import json
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Definizione scenari/automazioni
AUTOMAZIONI = {
    "notte": {
        "nome": "Modalità Notte",
        "descrizione": "Spegne luci, attiva sensori movimento, abbassa tapparelle",
        "azioni": [
            {"topic": "mesh/comandi/soggiorno/luce", "payload": {"action": "off"}},
            {"topic": "mesh/comandi/cucina/luce", "payload": {"action": "off"}},
            {"topic": "mesh/comandi/camera/luce", "payload": {"action": "off", "brightness": 5}},
            {"topic": "mesh/comandi/ingresso/sensore_movimento", "payload": {"action": "arm"}},
            {"topic": "mesh/comandi/tapparelle/tutte", "payload": {"action": "close"}},
        ],
        "spoken": "Modalità notte attivata. Luci spente, sensori armati, tapparelle chiuse."
    },
    "giorno": {
        "nome": "Modalità Giorno",
        "descrizione": "Alza tapparelle, disattiva allarme movimento",
        "azioni": [
            {"topic": "mesh/comandi/tapparelle/tutte", "payload": {"action": "open"}},
            {"topic": "mesh/comandi/ingresso/sensore_movimento", "payload": {"action": "disarm"}},
        ],
        "spoken": "Buongiorno! Tapparelle aperte, sensori disattivati."
    },
    "cinema": {
        "nome": "Scenario Cinema",
        "descrizione": "Abbassa luci soggiorno, chiude tapparelle",
        "azioni": [
            {"topic": "mesh/comandi/soggiorno/luce", "payload": {"action": "dim", "brightness": 10}},
            {"topic": "mesh/comandi/soggiorno/tapparella", "payload": {"action": "close"}},
        ],
        "spoken": "Scenario cinema attivato. Luci soffuse, tapparelle chiuse. Buona visione!"
    },
    "risparmio": {
        "nome": "Risparmio Energetico",
        "descrizione": "Spegne dispositivi non essenziali",
        "azioni": [
            {"topic": "mesh/comandi/standby/tv", "payload": {"action": "off"}},
            {"topic": "mesh/comandi/standby/console", "payload": {"action": "off"}},
            {"topic": "mesh/comandi/luci/tutte", "payload": {"action": "off"}},
        ],
        "spoken": "Modalità risparmio energetico. Ho spento TV, console e tutte le luci."
    },
    "emergenza": {
        "nome": "Emergenza",
        "descrizione": "Accende tutte le luci, apre tapparelle, invia alert",
        "azioni": [
            {"topic": "mesh/comandi/luci/tutte", "payload": {"action": "on", "brightness": 100}},
            {"topic": "mesh/comandi/tapparelle/tutte", "payload": {"action": "open"}},
            {"topic": "mesh/system/alerts", "payload": {"type": "emergency", "source": "voice"}},
            {"topic": "meshtastic/tx", "payload": {"to": "broadcast", "text": "🚨 EMERGENZA ATTIVATA DA VOCE"}},
        ],
        "spoken": "Emergenza! Ho acceso tutte le luci, aperto le tapparelle e inviato un allarme."
    },
    "esco": {
        "nome": "Uscita Casa",
        "descrizione": "Spegne tutto, arma sensori, chiude tapparelle",
        "azioni": [
            {"topic": "mesh/comandi/luci/tutte", "payload": {"action": "off"}},
            {"topic": "mesh/comandi/prese/non_essenziali", "payload": {"action": "off"}},
            {"topic": "mesh/comandi/tapparelle/tutte", "payload": {"action": "close"}},
            {"topic": "mesh/comandi/allarme", "payload": {"action": "arm", "mode": "away"}},
        ],
        "spoken": "Casa in modalità assente. Luci spente, allarme attivo. Buona giornata!"
    },
    "arrivo": {
        "nome": "Arrivo Casa",
        "descrizione": "Disarma allarme, accende luci ingresso",
        "azioni": [
            {"topic": "mesh/comandi/allarme", "payload": {"action": "disarm"}},
            {"topic": "mesh/comandi/ingresso/luce", "payload": {"action": "on"}},
        ],
        "spoken": "Bentornato a casa! Allarme disattivato, luce ingresso accesa."
    },
}

AUTOMAZIONI_DESC = {
    "type": "function",
    "function": {
        "name": "automazioni_vocali",
        "description": (
            "Attiva scenari e automazioni domotiche. "
            "Trigger: modalità notte, scenario cinema, risparmio energetico, "
            "esco di casa, sono a casa, emergenza, quali automazioni hai"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "scenario": {
                    "type": "string",
                    "enum": list(AUTOMAZIONI.keys()) + ["lista"],
                    "description": "Nome scenario da attivare o 'lista' per elencare"
                }
            },
            "required": ["scenario"]
        }
    }
}


@register_function('automazioni_vocali', AUTOMAZIONI_DESC, ToolType.SYSTEM)
def automazioni_vocali(conn, scenario: str):
    """Attiva automazione/scenario"""
    logger.bind(tag=TAG).info(f"Automazione richiesta: {scenario}")

    if scenario == "lista":
        display = "**🏠 Automazioni Disponibili**\n\n"
        spoken_list = []

        for key, auto in AUTOMAZIONI.items():
            display += f"• **{auto['nome']}**: {auto['descrizione']}\n"
            display += f"  _Dì: \"{key}\"_\n\n"
            spoken_list.append(auto['nome'])

        spoken = "Le automazioni disponibili sono: " + ", ".join(spoken_list)
        return ActionResponse(Action.RESPONSE, display, spoken)

    if scenario not in AUTOMAZIONI:
        return ActionResponse(
            Action.RESPONSE,
            f"Automazione '{scenario}' non trovata. Dì 'quali automazioni hai' per l'elenco.",
            f"Non conosco l'automazione {scenario}. Chiedimi quali automazioni ho."
        )

    auto = AUTOMAZIONI[scenario]

    # Esegui azioni MQTT
    executed = 0
    for azione in auto["azioni"]:
        try:
            # mqtt_client.publish(azione["topic"], json.dumps(azione["payload"]))
            logger.bind(tag=TAG).info(f"MQTT publish: {azione['topic']} = {azione['payload']}")
            executed += 1
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore azione: {e}")

    display = f"**{auto['nome']}** ✅\n\n"
    display += f"{auto['descrizione']}\n\n"
    display += f"_Eseguite {executed}/{len(auto['azioni'])} azioni_"

    return ActionResponse(Action.RESPONSE, display, auto["spoken"])
```

### Pattern Intent per Domotica

Aggiungi a `intent_llm.py`:

```python
# ============ MESH IOT MONITOR ============
if match_any(['temperatura serra', 'umidità cucina', 'stato sensori',
              'sensori mesh', 'batteria nodi', 'quanti gradi']):
    location = None
    for loc in ['cucina', 'soggiorno', 'serra', 'garage', 'camera', 'bagno', 'esterno']:
        if loc in text_lower:
            location = loc
            break

    sensor_type = "tutti"
    for st in ['temperatura', 'umidita', 'gas', 'movimento', 'batteria']:
        if st in text_lower:
            sensor_type = st
            break

    if location:
        return f'{{"function_call": {{"name": "mesh_iot_monitor", "arguments": {{"action": "read", "location": "{location}", "sensor_type": "{sensor_type}"}}}}}}'
    return '{"function_call": {"name": "mesh_iot_monitor", "arguments": {"action": "status"}}}'

# ============ ALLARMI MESH ============
if match_any(['ci sono allarmi', 'stato allarmi', 'allarmi attivi',
              'emergenze', 'silenzia allarme', 'storico allarmi']):
    if 'silenzia' in text_lower:
        return '{"function_call": {"name": "mesh_alerts", "arguments": {"action": "silence"}}}'
    if 'storico' in text_lower:
        return '{"function_call": {"name": "mesh_alerts", "arguments": {"action": "history"}}}'
    return '{"function_call": {"name": "mesh_alerts", "arguments": {"action": "status"}}}'

# ============ AUTOMAZIONI VOCALI ============
automazioni_trigger = {
    'notte': ['modalità notte', 'buonanotte', 'vado a dormire'],
    'giorno': ['modalità giorno', 'buongiorno', 'sveglia'],
    'cinema': ['scenario cinema', 'modalità film', 'voglio guardare un film'],
    'risparmio': ['risparmio energetico', 'risparmia energia', 'spegni tutto'],
    'emergenza': ['emergenza', 'aiuto emergenza', 'allarme'],
    'esco': ['esco di casa', 'vado via', 'uscita'],
    'arrivo': ['sono a casa', 'sono arrivato', 'torno a casa'],
    'lista': ['quali automazioni', 'elenco automazioni', 'scenari disponibili']
}

for scenario, triggers in automazioni_trigger.items():
    if match_any(triggers):
        return f'{{"function_call": {{"name": "automazioni_vocali", "arguments": {{"scenario": "{scenario}"}}}}}}'
```

### Comandi Vocali Domotica - Riepilogo

| Comando | Funzione | Risposta |
|---------|----------|----------|
| "Temperatura serra" | mesh_iot_monitor | "Serra: 24 gradi" |
| "Stato sensori" | mesh_iot_monitor | Report tutti i sensori |
| "Batteria nodi" | mesh_iot_monitor | Stato batterie |
| "Ci sono allarmi?" | mesh_alerts | Allarmi attivi |
| "Silenzia allarme" | mesh_alerts | Silenzia alert |
| "Modalità notte" | automazioni_vocali | Spegne luci, arma sensori |
| "Esco di casa" | automazioni_vocali | Chiude tutto, arma allarme |
| "Emergenza!" | automazioni_vocali | Accende tutto, invia alert |
| "Scenario cinema" | automazioni_vocali | Abbassa luci, chiude tapparelle |

---

## Wakeword e Alert Push

### Configurazione Wakeword

Il chatbot ESP32 si attiva con una **wakeword** configurabile. Di default usa rilevamento locale:

```yaml
# config.yaml (server)
wakeword:
  type: "local"           # local | server | always_on
  word: "xiao zhi"        # Parola di attivazione
  sensitivity: 0.5        # 0.0-1.0
  timeout_ms: 5000        # Timeout ascolto dopo wakeword
```

**Wakeword italiane consigliate** (foneticamente riconoscibili):
- "Ehi casa"
- "Ok casa"
- "Ciao Gino"
- "Assistente"

### Alert Push: Server → Chatbot

Il server Xiaozhi può **inviare messaggi proattivi** ai chatbot connessi quando riceve allarmi dalla rete mesh:

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUSSO ALERT PUSH                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Sensore Gas → ESP-NOW → Gateway → MQTT → VPS Server           │
│                                                                  │
│   VPS Server:                                                    │
│   1. Riceve alert su mesh/indoor/cucina/gas                     │
│   2. Processa con mesh_alerts.py                                │
│   3. Se CRITICAL/EMERGENCY → broadcast_alert()                  │
│                                                                  │
│   broadcast_alert():                                             │
│   - Genera TTS audio "Attenzione! Gas rilevato in cucina!"      │
│   - Invia a TUTTI i chatbot ESP32 connessi via WebSocket        │
│   - I chatbot riproducono l'audio IMMEDIATAMENTE                │
│                                                                  │
│   ESP32 Chatbot → Speaker: "🔊 Attenzione! Gas rilevato..."     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementazione Alert Broadcast

```python
# core/utils/alert_broadcaster.py
"""
Broadcast alert vocali a tutti i chatbot connessi
"""

import asyncio
import json
from typing import Set
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# Set di connessioni WebSocket attive
active_connections: Set = set()


def register_connection(websocket):
    """Registra nuova connessione chatbot"""
    active_connections.add(websocket)
    logger.bind(tag=TAG).info(f"Chatbot registered. Total: {len(active_connections)}")


def unregister_connection(websocket):
    """Rimuovi connessione chatbot"""
    active_connections.discard(websocket)
    logger.bind(tag=TAG).info(f"Chatbot disconnected. Total: {len(active_connections)}")


async def broadcast_alert(message: str, level: str = "critical", audio_data: bytes = None):
    """
    Invia alert a tutti i chatbot connessi

    Args:
        message: Testo da pronunciare
        level: info, warning, critical, emergency
        audio_data: Audio TTS pre-generato (opzionale)
    """
    if not active_connections:
        logger.bind(tag=TAG).warning("No chatbots connected for alert broadcast")
        return 0

    # Genera audio TTS se non fornito
    if audio_data is None:
        from core.providers.tts.edge import EdgeTTS
        tts = EdgeTTS()
        audio_data = await tts.text_to_audio(message)

    # Prepara payload
    payload = {
        "type": "alert",
        "level": level,
        "message": message,
        "audio": audio_data.hex() if audio_data else None,
        "timestamp": datetime.now().isoformat()
    }

    # Broadcast a tutti i client
    sent_count = 0
    failed = []

    for ws in active_connections.copy():
        try:
            await ws.send(json.dumps(payload))
            sent_count += 1
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to send alert: {e}")
            failed.append(ws)

    # Rimuovi connessioni fallite
    for ws in failed:
        active_connections.discard(ws)

    logger.bind(tag=TAG).info(f"Alert broadcast to {sent_count} chatbots: {message[:50]}...")
    return sent_count


async def broadcast_emergency(message: str):
    """Shortcut per emergenze - massima priorità"""
    # Aggiungi prefisso vocale
    emergency_message = f"Attenzione! Emergenza! {message}"

    # Invia con priorità alta
    return await broadcast_alert(
        message=emergency_message,
        level="emergency"
    )


# === Integrazione con mesh_alerts.py ===

def on_critical_alert(alert: dict):
    """Callback chiamato quando si verifica un alert critico"""
    message = get_alert_message(alert)[1]  # Versione spoken

    # Broadcast async
    asyncio.create_task(
        broadcast_alert(message, level=alert["level"])
    )

    # Log
    logger.bind(tag=TAG).warning(f"BROADCAST ALERT: {message}")
```

### Modifica mesh_alerts.py per Push

```python
# In mesh_alerts.py, aggiungi alla callback MQTT:

from core.utils.alert_broadcaster import broadcast_alert, broadcast_emergency

def on_alert_message(client, userdata, msg):
    """Callback per messaggi di allarme CON BROADCAST"""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())

        parts = topic.split('/')
        node = parts[2] if len(parts) > 2 else "unknown"

        value = payload.get('value', payload)
        if isinstance(value, (int, float)):
            alert = process_alert(topic, value, node)

            if alert:
                active_alerts[alert["id"]] = alert
                alert_history.append(alert)

                # === NUOVO: BROADCAST A CHATBOT ===
                if alert["level"] == "emergency":
                    # Emergenza: broadcast immediato!
                    display, spoken = get_alert_message(alert)
                    asyncio.create_task(broadcast_emergency(spoken))

                elif alert["level"] == "critical":
                    # Critico: broadcast con messaggio
                    display, spoken = get_alert_message(alert)
                    asyncio.create_task(broadcast_alert(spoken, "critical"))

                # Warning: solo log, no broadcast
                logger.bind(tag=TAG).warning(f"ALERT [{alert['level']}]: {alert}")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Alert processing error: {e}")
```

### Firmware ESP32: Ricezione Alert

Il firmware xiaozhi-esp32 deve gestire i messaggi alert in arrivo:

```cpp
// xiaozhi-esp32/src/alert_handler.cpp

#include "alert_handler.h"
#include "audio_player.h"

void handleServerMessage(const char* json) {
    StaticJsonDocument<2048> doc;
    deserializeJson(doc, json);

    const char* type = doc["type"];

    if (strcmp(type, "alert") == 0) {
        // Messaggio di alert dal server
        const char* level = doc["level"];
        const char* message = doc["message"];
        const char* audioHex = doc["audio"];

        Serial.printf("[ALERT] Level: %s, Message: %s\n", level, message);

        // Interrompi qualsiasi audio in corso
        AudioPlayer::stop();

        // Riproduci alert
        if (audioHex != nullptr) {
            // Audio pre-generato dal server
            size_t audioLen = strlen(audioHex) / 2;
            uint8_t* audioData = new uint8_t[audioLen];
            hexToBytes(audioHex, audioData, audioLen);

            // Riproduci con priorità alta
            AudioPlayer::playPriority(audioData, audioLen);
            delete[] audioData;
        }

        // LED rosso per emergenza
        if (strcmp(level, "emergency") == 0) {
            LED::setColor(255, 0, 0);  // Rosso
            LED::blink(500);           // Lampeggia
        } else if (strcmp(level, "critical") == 0) {
            LED::setColor(255, 165, 0);  // Arancione
        }
    }
}

// Nel loop WebSocket principale
void onWebSocketMessage(uint8_t* payload, size_t length) {
    char* json = (char*)payload;
    handleServerMessage(json);
}
```

### Configurazione Alert Soglie

```yaml
# config.yaml - Soglie alert mesh
mesh_alerts:
  enabled: true
  mqtt_broker: "localhost"
  mqtt_port: 1883
  mqtt_topics:
    - "mesh/#"

  thresholds:
    gas:
      warning: 500
      critical: 800
      emergency: 1000
    fumo:
      warning: 100
      critical: 200
      emergency: 300
    temperatura:
      warning: 35
      critical: 45
      emergency: 60
    batteria:
      warning: 20
      critical: 10
      emergency: 5

  broadcast:
    enabled: true
    levels: ["critical", "emergency"]  # Solo questi livelli fanno broadcast
    cooldown_seconds: 60               # Anti-spam: min 60s tra alert stesso tipo
    max_per_hour: 10                   # Max 10 alert/ora per tipo
```

### Flusso Completo Alert

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ESEMPIO: ALERT GAS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Sensore MQ-2 cucina rileva gas = 850                                │
│     └─► ESPHome pubblica: mesh/indoor/cucina/gas {"value": 850}         │
│                                                                          │
│  2. Gateway ESP-NOW → MQTT LuckFox → MQTT VPS                           │
│                                                                          │
│  3. VPS - mesh_alerts.py:                                               │
│     └─► process_alert() → level = "critical" (>800)                     │
│     └─► get_alert_message() → "Allarme critico! Gas elevato in cucina"  │
│     └─► asyncio.create_task(broadcast_alert(...))                       │
│                                                                          │
│  4. VPS - alert_broadcaster.py:                                         │
│     └─► EdgeTTS genera audio italiano                                   │
│     └─► WebSocket.send() a tutti i chatbot connessi                     │
│                                                                          │
│  5. ESP32 Chatbot (cucina, soggiorno, camera...):                       │
│     └─► Riceve JSON {"type":"alert", "audio":"..."}                     │
│     └─► AudioPlayer::playPriority() - INTERROMPE tutto                  │
│     └─► Speaker: "🔊 Allarme critico! Gas elevato in cucina!"           │
│     └─► LED arancione lampeggiante                                      │
│                                                                          │
│  6. Contemporaneamente:                                                  │
│     └─► LuckFox → Meshtastic → LoRa → Telefono 📱                       │
│     └─► active_alerts["cucina_gas_123456"] = {...}                      │
│                                                                          │
│  7. Utente: "Silenzia allarme"                                          │
│     └─► mesh_alerts(action="silence") → Alert rimosso                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Riepilogo Sistema Alert

| Livello | Soglia Gas | Azione | Broadcast | LED |
|---------|------------|--------|-----------|-----|
| **Info** | < 500 | Solo log | No | - |
| **Warning** | 500-800 | Log + storico | No | Giallo |
| **Critical** | 800-1000 | Log + storico + broadcast | Sì | Arancione |
| **Emergency** | > 1000 | Tutto + LoRa + automazioni | Sì (priorità) | Rosso lampeggiante |

---

## Riferimenti

### Progetti Principali
- [zh_gateway (ESP-IDF)](https://github.com/aZholtikov/zh_gateway) - **Gateway preferito**
- [ZHNetwork](https://github.com/aZholtikov/ZHNetwork) - Mesh stabile
- [ESP-NOW-Gateway (Arduino)](https://github.com/aZholtikov/ESP-NOW-Gateway) - Alternativa semplice
- [ESPHome](https://esphome.io/) - **ESP-NOW nativo dal 2025.8**
- [OpenMQTTGateway](https://github.com/1technophile/OpenMQTTGateway)

### Meshtastic
- [Meshtastic](https://meshtastic.org/)
- [Meshtastic MQTT Integration](https://meshtastic.org/docs/software/integrations/mqtt/)
- [meshtastic-bridge](https://github.com/geoffwhittington/meshtastic-bridge)

### Infrastruttura
- [Mosquitto](https://mosquitto.org/)
- [NanoMQ](https://nanomq.io/) - MQTT ultra-leggero
- [Piper TTS](https://github.com/rhasspy/piper)
- [LuckFox Pico](https://www.luckfox.com/)

---

## Changelog

### v2.2 (Gennaio 2025)
- **Firmware per dispositivo**: Tabella completa firmware ufficiali/custom
- **Sistemi Operativi**: LuckFox Buildroot/Ubuntu, Raspberry Pi OS/DietPi
- **Firmware LoRa custom**: Codice Arduino per ESP32 + DX-LR-30
- **Plugin Xiaozhi IoT**: mesh_iot_monitor, mesh_alerts, automazioni_vocali
- **Intent patterns**: Trigger vocali per domotica mesh
- **Wakeword config**: Parole attivazione italiane consigliate
- **Alert Push**: Server → Chatbot broadcast per emergenze
- **alert_broadcaster.py**: Implementazione broadcast WebSocket
- **Firmware ESP32**: Gestione ricezione alert con priorità
- **Flusso completo alert**: Diagramma sensore → chatbot vocale

### v2.1 (Gennaio 2025)
- **Ottimizzazione Energetica**: Deep sleep pattern per nodi a batteria (8-12 mesi autonomia)
- **ESP-NOW + Deep Sleep**: Pattern critico con callback conferma
- **Gestione Code Offline**: Buffer SQLite con aggregazione intelligente
- **Monitoring/Heartbeat**: Watchdog system con alert LoRa
- **Dashboard LuckFox**: Web UI Flask locale (funziona offline)
- **Meshtastic Security**: Guida generazione PSK custom
- **ESP32-CAM**: Chiarito che resta su WiFi (no ESP-NOW/LoRa per video)

### v2.0 (Gennaio 2025)
- Aggiunto zh_gateway come alternativa preferita (ESP-IDF)
- ESPHome 2025.8+ supporto ESP-NOW nativo
- Struttura MQTT sync/ per resilienza VPS↔locale
- Sezione sicurezza completa
- Fase 1.5 test resilienza
- Warning WiFi channel lock
- Warning Meshtastic zero-hop policy
- ZHNetwork come alternativa a painlessMesh
- NanoMQ come alternativa leggera a Mosquitto
- LuckFox Pico Ultra consigliato

### v1.0 (Gennaio 2025)
- Documento iniziale

---

*Documento v2.2 - Completo con firmware, OS, integrazione Xiaozhi e sistema alert push - Gennaio 2025*
