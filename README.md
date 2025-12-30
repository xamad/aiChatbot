# ESP32-C3 AI Chatbot (Xiaozhi)

Progetto per configurare un chatbot AI su ESP32-C3 con display OLED 0.96".

## Hardware

- ESP32-C3 con display OLED 0.96" integrato
- Supporta modelli AI: Xiaozhi, DeepSeek, Doubao, Qwen, GPT, Claude

## Firmware

Il firmware precompilato si trova in `firmware/merged-binary.bin` (versione v2.1.0, board: xmini-c3).

### Flash del firmware

1. Collega la scheda ESP32-C3 via USB

2. Se necessario, entra in modalità download:
   - Tieni premuto **BOOT**
   - Premi e rilascia **RESET**
   - Rilascia **BOOT**

3. Esegui il comando di flash:
```bash
esptool --chip esp32c3 --port /dev/ttyUSB0 write_flash 0x0 firmware/merged-binary.bin
```

Su Windows, sostituisci `/dev/ttyUSB0` con la porta COM appropriata (es. `COM3`).

## Configurazione Base

Dopo il flash:

1. La scheda creerà un hotspot WiFi per la configurazione
2. Connettiti all'hotspot e configura la rete WiFi
3. Registra un account su [xiaozhi.me](https://xiaozhi.me) per usare i modelli AI gratuiti

## Server Self-Hosted (Opzionale)

Per avere più funzionalità (meteo, ricerca web, radio, ricette), puoi usare il server self-hosted.

### Installazione Server

```bash
cd server/main/xiaozhi-server
pip install -r requirements.txt
```

### Plugin Custom Disponibili

Nella cartella `plugins_custom/` trovi plugin aggiuntivi:

| Plugin | Funzione |
|--------|----------|
| `web_search.py` | Ricerca web con DuckDuckGo (gratis) |
| `meteo_italia.py` | Meteo per TUTTE le città italiane |
| `radio_italia.py` | 17+ stazioni radio italiane in streaming |
| `ricette.py` | Ricette di cucina |

### Installazione Plugin

Copia i plugin nella cartella del server:

```bash
cp plugins_custom/*.py server/main/xiaozhi-server/plugins_func/functions/
```

I plugin sono **indipendenti dal modello AI** - funzionano con DeepSeek, Qwen, GPT, Claude, etc.

### Stazioni Radio Disponibili

- Rai Radio 1, 2, 3
- Radio DeeJay
- RTL 102.5
- Radio 105
- Radio Italia
- Virgin Radio
- Radio Kiss Kiss
- m2o
- Radio Capital
- RDS
- Radio 24
- **Radio Zeta**
- Radio Freccia
- Radio Monte Carlo
- Radio Subasio

## Risorse

- [Repository Xiaozhi ESP32](https://github.com/78/xiaozhi-esp32)
- [Server Python](https://github.com/xinnan-tech/xiaozhi-esp32-server)
- [Releases Firmware](https://github.com/78/xiaozhi-esp32/releases)
