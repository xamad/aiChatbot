# ESP32-S3 2.8" Touch Display Board

Board configuration for Xiaozhi AI Chatbot.

## Hardware Specifications

- **MCU:** ESP32-S3 dual-core @ 240MHz
- **PSRAM:** 8MB
- **Display:** ILI9341 2.8" TFT 240x320 (SPI)
- **Touch:** FT6336G Capacitive (I2C)
- **Audio:** I2S Speaker (FM8002E) + MEMS Microphone
- **Storage:** MicroSD Card Slot (SDIO 4-bit)
- **LED:** RGB WS2812 NeoPixel
- **Battery:** LiPo with charging circuit
- **Interface:** USB Type-C

## Pinout

### Display (SPI)
| GPIO | Function |
|------|----------|
| 10 | CS |
| 46 | DC |
| 12 | SCK |
| 11 | MOSI |
| 13 | MISO |
| 45 | Backlight |

### Touch (I2C)
| GPIO | Function |
|------|----------|
| 16 | SDA |
| 15 | SCL |
| 18 | RST |
| 17 | INT |

### Audio (I2S)
| GPIO | Function |
|------|----------|
| 1 | PA Enable (LOW=on) |
| 4 | MCLK |
| 5 | BCLK |
| 6 | DOUT (speaker) |
| 7 | WS/LRC |
| 8 | DIN (mic) |

### SD Card (SDIO)
| GPIO | Function |
|------|----------|
| 38 | CLK |
| 40 | CMD |
| 39 | DATA0 |
| 41 | DATA1 |
| 48 | DATA2 |
| 47 | DATA3 |

### Other
| GPIO | Function |
|------|----------|
| 42 | RGB LED |
| 9 | Battery ADC |
| 0 | Boot Button |

## Build

```bash
cd xiaozhi-esp32
idf.py set-target esp32s3
idf.py -D BOARD=esp32s3-28touch build
idf.py flash
```

## Links

- [LCDWiki Documentation](https://www.lcdwiki.com/2.8inch_ESP32-S3_Display)
- [AliExpress Product](https://it.aliexpress.com/item/1005010562103872.html)
