# XAMAD ESP32-S3 DIY Board

Custom XiaoZhi AI Voice Assistant board for ESP32-S3-N8R8 with DIY hardware.

## Server Configuration

- **OTA URL:** `https://chatai.xamad.net/xiaozhi/ota/`
- **WebSocket:** `wss://chatai.xamad.net/xiaozhi/v1/`

## Components

| Component | Model | Interface |
|-----------|-------|-----------|
| MCU | ESP32-S3-N8R8 (8MB PSRAM) | - |
| Display | TFT 1.8" ST7735 128x160 | SPI |
| Microphone | INMP441 | I2S |
| Amplifier | MAX98357A | I2S |
| Speaker | 8 ohm 2W | via MAX98357A |

## Pinout

### TFT Display 1.8" ST7735 (8 pins)

| Pin | Function | ESP32-S3 GPIO |
|-----|----------|---------------|
| VCC | 3.3V | 3.3V |
| GND | Ground | GND |
| CS | Chip Select | GPIO 10 |
| RESET | Reset | GPIO 9 |
| DC/A0 | Data/Command | GPIO 8 |
| SDA/MOSI | SPI Data | GPIO 11 |
| SCK/SCL | SPI Clock | GPIO 12 |
| LED/BL | Backlight | GPIO 13 |

### INMP441 Microphone (6 pins)

| Pin | Function | ESP32-S3 GPIO |
|-----|----------|---------------|
| VDD | 3.3V | 3.3V |
| GND | Ground | GND |
| SD | Serial Data | GPIO 14 |
| WS | Word Select | GPIO 15 |
| SCK | Bit Clock | GPIO 16 |
| L/R | Channel | GND (Left) |

### MAX98357A Amplifier (7 pins)

| Pin | Function | ESP32-S3 GPIO |
|-----|----------|---------------|
| VIN | 5V | 5V |
| GND | Ground | GND |
| SD | Shutdown/Enable | GPIO 17 |
| GAIN | Gain (9dB) | Float (NC) |
| DIN | Data In | GPIO 18 |
| BCLK | Bit Clock | **GPIO 5** |
| LRC | L/R Clock | **GPIO 6** |

> **Note:** Do NOT use GPIO 45/46 for I2S - they are strapping pins and cause audio screeching.

### Boot Button

| Function | ESP32-S3 GPIO |
|----------|---------------|
| BOOT | GPIO 0 |

## Wiring Diagram

```
                    ESP32-S3
                 +------------+
    TFT CS ------| GPIO10     |
    TFT DC ------| GPIO8      |
   TFT RST ------| GPIO9      |
  TFT MOSI ------| GPIO11     |
   TFT SCK ------| GPIO12     |
    TFT BL ------| GPIO13     |
                 |            |
  MIC DATA ------| GPIO14     |
    MIC WS ------| GPIO15     |
   MIC SCK ------| GPIO16     |
                 |            |
   AMP DIN ------| GPIO18     |
  AMP BCLK ------| GPIO5      |
   AMP LRC ------| GPIO6      |
    AMP SD ------| GPIO17     |
                 |            |
      BOOT ------| GPIO0      |
                 |            |
       3.3V -----| 3V3        |
         5V -----| 5V (USB)   |
        GND -----| GND        |
                 +------------+
```

## Build Configuration

```ini
CONFIG_BOARD_TYPE_XAMAD_S3_DIY=y
CONFIG_LANGUAGE_IT_IT=y
CONFIG_USE_EMOTE_MESSAGE_STYLE=y
CONFIG_LV_THEME_DEFAULT_DARK=y
CONFIG_SR_WN_WN9_SOPHIA_TTS=y
CONFIG_OTA_URL="https://chatai.xamad.net/xiaozhi/ota/"
```

## Features

- **Wake word:** "Sophia"
- **Language:** Italian (IT)
- **Display style:** Emote animation
- **Theme:** Dark

## Build Instructions

```bash
cd xiaozhi-esp32
idf.py set-target esp32s3
idf.py -D BOARD=xamad-s3-diy build
idf.py flash monitor
```

## Flash from Windows

```cmd
python -m esptool --chip esp32s3 -p COM15 -b 460800 write_flash @flash_args
```

## First Boot

1. Press BOOT button to enter WiFi config mode
2. Connect to AP "XiaoZhi-XXXX"
3. Configure WiFi credentials
4. Device will connect to chatai.xamad.net

## Audio Troubleshooting

If you experience crackling audio:

1. Add **100uF capacitor** between MAX98357A VIN and GND
2. Use **separate 5V power supply** for amplifier (not from ESP32 USB)
3. Keep I2S wires **short (<10cm)**
4. Consider **4 ohm speaker** for better efficiency
5. Use a **larger speaker** for cleaner bass

## Notes

- Use ESP32-S3 with PSRAM (N8R8 or N16R8) for best performance
- Connect speaker to MAX98357A output (+ and -)
- INMP441 L/R pin to GND for left channel mono
- MAX98357A GAIN pin floating = 9dB gain (connect to GND for 3dB)
- Backlight is active-HIGH on this display
