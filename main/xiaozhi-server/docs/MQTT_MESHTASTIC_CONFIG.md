# Configurazione MQTT per Meshtastic/LoRa

## Server MQTT

**Host:** `moschino.xamad.net`

| Servizio | Porta | Protocollo | Autenticazione |
|----------|-------|------------|----------------|
| MQTT TLS | 8883 | `mqtts://` | Username/Password |
| WebSocket TLS | 9001 | `wss://` | Anonymous |
| MQTT Locale | 1883 | `mqtt://` | Anonymous (solo localhost) |

## Credenziali

### Meshtastic Node
- **Username:** `meshtastic`
- **Password:** `mesh2025secure`
- **Permessi:** Read/Write su `msh/#`

### Xiaozhi Chatbot
- **Username:** `xiaozhi`
- **Password:** `xiaozhi2025local`
- **Permessi:** Read/Write su `msh/#` e `xiaozhi/#`

## Configurazione Nodo Meshtastic

Nel menu Settings → MQTT del dispositivo Meshtastic:

```
Enabled:        ON
Server:         moschino.xamad.net
Port:           8883
TLS Enabled:    ON
Username:       meshtastic
Password:       mesh2025secure
Root Topic:     msh/EU_868/2/json
JSON Enabled:   ON
```

## Topic MQTT

Il formato dei topic Meshtastic è:
```
msh/[region]/[channel_num]/json/[channel_name]/[gateway_id]
```

Esempi:
- `msh/EU_868/2/json/Asti/!abcd1234` - Canale Asti
- `msh/EU_868/2/json/MediumFast/!abcd1234` - Canale pubblico
- `msh/EU_868/2/json/DM/!abcd1234` - Messaggi diretti

## Canali Monitorati dal Chatbot

| Canale | Monitoraggio | Note |
|--------|--------------|------|
| **Asti** | Sempre attivo | Canale privato locale |
| **DM** | Sempre attivo | Messaggi diretti prioritari |
| **MediumFast** | Temporaneo (10 min) | Solo dopo invio messaggio |

## Certificati TLS

I certificati Let's Encrypt sono gestiti automaticamente:
- **Path:** `/etc/letsencrypt/live/moschino.xamad.net/`
- **Scadenza:** 90 giorni (rinnovo automatico)
- **Emittente:** Let's Encrypt (ISRG Root X1)

## Test Connessione

### Da linea di comando (con mosquitto-clients):
```bash
# Subscribe a tutti i messaggi Meshtastic
mosquitto_sub -h moschino.xamad.net -p 8883 \
  -u meshtastic -P mesh2025secure \
  --capath /etc/ssl/certs \
  -t "msh/#" -v

# Publish un messaggio di test
mosquitto_pub -h moschino.xamad.net -p 8883 \
  -u meshtastic -P mesh2025secure \
  --capath /etc/ssl/certs \
  -t "msh/EU_868/2/json/test" \
  -m '{"type":"test","payload":"hello"}'
```

### Test TLS con OpenSSL:
```bash
openssl s_client -connect moschino.xamad.net:8883 -servername moschino.xamad.net
```

## Variabili d'Ambiente Plugin

Il plugin `meshtastic_lora.py` richiede:

```bash
# ID del nodo Meshtastic (formato !xxxxxxxx)
MESHTASTIC_NODE_ID=!your_node_id

# Broker MQTT (default: localhost per connessione interna)
MQTT_BROKER=127.0.0.1
MQTT_PORT=1883
```

## Architettura

```
┌─────────────────┐     LoRa 868MHz      ┌─────────────────┐
│  Meshtastic     │◄───────────────────►│  Altri Nodi     │
│  Node           │                      │  Meshtastic     │
└────────┬────────┘                      └─────────────────┘
         │ WiFi
         ▼
┌─────────────────┐     MQTT TLS:8883    ┌─────────────────┐
│  Router/Gateway │────────────────────►│  VPS            │
│                 │                      │  moschino.xamad │
└─────────────────┘                      │                 │
                                         │  ┌───────────┐  │
                                         │  │ Mosquitto │  │
                                         │  │   MQTT    │  │
                                         │  └─────┬─────┘  │
                                         │        │        │
                                         │  ┌─────▼─────┐  │
                                         │  │  Xiaozhi  │  │
                                         │  │  Chatbot  │  │
                                         │  └───────────┘  │
                                         └─────────────────┘
```

## Changelog

- **2026-01-04:** Configurazione iniziale MQTT con TLS Let's Encrypt
