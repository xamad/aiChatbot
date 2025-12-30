# ESP32-C3 AI Chatbot (Xiaozhi)

Progetto per configurare un chatbot AI su ESP32-C3 con display OLED 0.96".

## Hardware

- ESP32-C3 con display OLED 0.96" integrato
- Supporta modelli AI: Xiaozhi, DeepSeek, Doubao, Qwen

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

## Configurazione

Dopo il flash:

1. La scheda creerà un hotspot WiFi per la configurazione
2. Connettiti all'hotspot e configura la rete WiFi
3. Registra un account su [xiaozhi.me](https://xiaozhi.me) per usare i modelli AI gratuiti

## Risorse

- [Repository Xiaozhi ESP32](https://github.com/78/xiaozhi-esp32)
- [Documentazione](https://github.com/78/xiaozhi-esp32/blob/main/README.md)
- [Releases](https://github.com/78/xiaozhi-esp32/releases)
