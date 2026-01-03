# Architettura Mesh IoT - Xiaozhi Chatbot

> Documento di architettura per l'integrazione di sensori ESP32, LoRa/Meshtastic e hub locale con il chatbot vocale Xiaozhi.

**Data**: Gennaio 2025
**Versione**: 2.1 (Deep sleep, monitoring, gestione offline)

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

*Documento v2.1 - Aggiornato con ottimizzazione energetica, monitoring e gestione offline - Gennaio 2025*
