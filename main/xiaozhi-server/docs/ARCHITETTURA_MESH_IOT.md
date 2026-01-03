# Architettura Mesh IoT - Xiaozhi Chatbot

> Documento di architettura per l'integrazione di sensori ESP32, LoRa/Meshtastic e hub locale con il chatbot vocale Xiaozhi.

**Data**: Gennaio 2025
**Versione**: 2.0 (Aggiornato con feedback community)

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
| **ESP32-CAM** | N | Telecamere | WiFi o ESP-NOW |
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
- [ ] ESP32-CAM
- [ ] Automazioni avanzate
- [ ] Dashboard Grafana

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

*Documento aggiornato con feedback community e nuove release progetti open source - Gennaio 2025*
