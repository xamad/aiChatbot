# SkyGuard Elite — Wiring & Cablaggio Sensori

## Panoramica Hardware

**Board base:** LCDWiki 2.8" ESP32-S3 (ILI9341 + ES8311 + FT6336G + SD + RGB LED)
**Sensori esterni:** TSL2591 (lux/SQM), AS7341 (spettro 8ch), AHT20 (temp/hum), GPS NMEA

---

## Connettori sulla Board LCDWiki

La board ha **due connettori JST 1.25mm 4-pin** sul lato sinistro:

```
┌─────────────────────────────────────────────────────────┐
│                   LCDWiki 2.8" ESP32-S3                 │
│                                                         │
│  ┌──────────────────────────────────┐                   │
│  │                                  │                   │
│  │        DISPLAY TFT 2.8"         │                   │
│  │        ILI9341 320x240          │                   │
│  │        + Touch FT6336G          │                   │
│  │                                  │                   │
│  └──────────────────────────────────┘                   │
│                                                         │
│  [BOOT]                          [USB-C]                │
│                                                         │
│ ┌─────────┐                                             │
│ │ I2C     │ ← Connettore I2C (condiviso con touch)     │
│ │ 1.25mm  │   Pin 1: VCC (3.3V)                        │
│ │ 4-pin   │   Pin 2: GND                               │
│ │         │   Pin 3: GPIO15 (SCL) — I2C_NUM_0          │
│ │         │   Pin 4: GPIO16 (SDA) — I2C_NUM_0          │
│ └─────────┘                                             │
│                                                         │
│ ┌─────────┐                                             │
│ │ EXP     │ ← Connettore Espansione (NO VCC/GND!)      │
│ │ 1.25mm  │   Pin 1: GPIO2  (UART1 RX — GPS TX)        │
│ │ 4-pin   │   Pin 2: GPIO3  (UART1 TX — GPS RX)        │
│ │         │   Pin 3: GPIO14 (I2C_NUM_1 SCL)             │
│ │         │   Pin 4: GPIO21 (I2C_NUM_1 SDA)             │
│ └─────────┘                                             │
│                                                         │
│  [Speaker]  [Mic MEMS]  [SD Slot]  [Battery]           │
└─────────────────────────────────────────────────────────┘
```

---

## Schema Bus I2C

```
                    I2C_NUM_0 (GPIO15 SCL / GPIO16 SDA)
                    ─────────────────────────────────────
                    │              │              │
                ┌───┴───┐    ┌────┴────┐    ┌────┴────┐
                │FT6336G│    │ ES8311  │    │ TSL2591 │
                │ Touch │    │ Audio   │    │  Lux    │
                │ 0x38  │    │ 0x18    │    │  0x29   │
                └───────┘    └─────────┘    └────┬────┘
                                                 │
                                            ┌────┴────┐
                                            │ AS7341  │
                                            │ Spettro │
                                            │  0x39   │
                                            └─────────┘

                    I2C_NUM_1 (GPIO14 SCL / GPIO21 SDA)
                    ─────────────────────────────────────
                    │
                ┌───┴───┐
                │ AHT20 │  ← Separato perche' 0x38 = stesso del touch!
                │Temp/Hum│
                │ 0x38  │
                └───────┘


                    UART_NUM_1 (GPIO2 RX / GPIO3 TX)
                    ─────────────────────────────────────
                    │
                ┌───┴────────┐
                │ GPS Module │
                │ NMEA 9600  │
                │ (GGA + RMC)│
                └────────────┘
```

---

## Cablaggio Dettagliato — Vista Ortogonale

### Basetta Sensori (su connettore I2C)

TSL2591 e AS7341 vanno montati su una piccola basetta millefori collegata al **connettore I2C** della board. Questa basetta va posizionata **esternamente**, puntando verso il cielo (lo zenit).

```
              Connettore I2C (1.25mm 4-pin)
              ┌──┬──┬──┬──┐
              │V │G │SC│SD│
              │C │N │L │A │
              │C │D │  │  │
              └┬─┴┬─┴┬─┴┬─┘
               │  │  │  │
    ═══════════╪══╪══╪══╪═══════════════ Cavo piatto 4 fili (~15-30cm)
               │  │  │  │
    ┌──────────┼──┼──┼──┼──────────────┐
    │ BASETTA  │  │  │  │  SENSORI     │
    │ MILLEFORI│  │  │  │              │
    │          │  │  │  │              │
    │    VCC ──┤  │  │  │              │
    │    GND ──┼──┤  │  │              │
    │    SCL ──┼──┼──┤  │              │
    │    SDA ──┼──┼──┼──┤              │
    │          │  │  │  │              │
    │  ┌───────┼──┼──┼──┼───────┐      │
    │  │ TSL2591 (Breakout)     │      │
    │  │                        │      │
    │  │  VIN ── VCC            │      │  Lux / SQM
    │  │  GND ── GND            │      │  Sky brightness
    │  │  SCL ── SCL (GPIO15)   │      │  Addr: 0x29
    │  │  SDA ── SDA (GPIO16)   │      │
    │  └────────────────────────┘      │
    │                                  │
    │  ┌────────────────────────┐      │
    │  │ AS7341 (Breakout)      │      │
    │  │                        │      │
    │  │  VIN ── VCC            │      │  Spettro 8 canali
    │  │  GND ── GND            │      │  415-680nm
    │  │  SCL ── SCL (GPIO15)   │      │  Addr: 0x39
    │  │  SDA ── SDA (GPIO16)   │      │
    │  └────────────────────────┘      │
    │                                  │
    │  ╔══════════════════════════╗    │
    │  ║    ↑↑↑ VERSO ZENIT ↑↑↑  ║    │
    │  ║  Finestra sensori verso  ║    │
    │  ║  il cielo (foro nel box) ║    │
    │  ╚══════════════════════════╝    │
    └──────────────────────────────────┘
```

### AHT20 — Vicino alla Board (connettore EXP)

L'AHT20 va posizionato **vicino alla board** ma NON sulla basetta sensori, perche':
1. Indirizzo 0x38 = stesso del touch FT6336G → deve stare su bus I2C_NUM_1 separato
2. Misura temperatura ambiente → non deve stare sotto al sole/zenit
3. Il connettore EXP **non ha VCC/GND** → va preso dal connettore I2C

```
    Connettore EXP (1.25mm 4-pin)        Connettore I2C
    ┌──┬──┬──┬──┐                         ┌──┬──┬──┬──┐
    │G2│G3│G │G │                         │V │G │  │  │
    │  │  │14│21│                         │C │N │  │  │
    └┬─┴┬─┴┬─┴┬─┘                         │C │D │  │  │
     │  │  │  │                           └┬─┴┬─┘  │  │
     │  │  │  │                            │  │
     │  │  │  │    ┌────────────────┐      │  │
     │  │  │  └────┤ SDA            │      │  │
     │  │  └───────┤ SCL    AHT20   │      │  │
     │  │          │         0x38   │      │  │
     │  │          │ VIN ───────────┼──────┘  │
     │  │          │ GND ───────────┼─────────┘
     │  │          └────────────────┘
     │  │
     │  │  (GPIO2/GPIO3 vanno al GPS, vedi sotto)
     │  │
     └──┘
```

**Nota importante:** L'AHT20 va a circa 3-5cm dalla board, in zona ventilata ma protetta dal sole diretto. Il firmware applica un offset di -2.4°C per compensare il calore del SoC.

### GPS — Vicino alla Board (connettore EXP)

Il modulo GPS va posizionato **vicino alla board** con antenna verso il cielo. Usa i pin UART del connettore EXP.

```
    Connettore EXP                        Connettore I2C
    ┌──┬──┬──┬──┐                         ┌──┬──┬──┬──┐
    │G2│G3│  │  │                         │V │G │  │  │
    └┬─┴┬─┘  │  │                         │C │N │  │  │
     │  │    │  │                         │C │D │  │  │
     │  │    │  │                         └┬─┴┬─┘
     │  │    │  │                          │  │
     │  │    │  │  ┌──────────────────┐    │  │
     │  └────┼──┼──┤ RX    GPS NMEA  │    │  │
     └───────┼──┼──┤ TX    (9600 bd) │    │  │
             │  │  │                  │    │  │
             │  │  │ VCC ─────────────┼────┘  │
             │  │  │ GND ─────────────┼───────┘
             │  │  │                  │
             │  │  │  [Antenna GPS]   │
             │  │  │  verso il cielo  │
             │  │  └──────────────────┘
             │  │
             └──┘  (GPIO14/GPIO21 vanno ad AHT20)
```

---

## Schema Cablaggio Completo — Vista Ortogonale

```
                            ┌─── Antenna GPS (verso cielo) ───┐
                            │                                  │
                            │     ┌────────────────────┐       │
                            │     │    GPS Module      │       │
                            │     │    NMEA 9600       │       │
                            │     │                    │       │
                            │     │ TX ──→ GPIO2 (RX)  │       │
                            │     │ RX ←── GPIO3 (TX)  │       │
                            │     │ VCC ── VCC (I2C)   │       │
                            │     │ GND ── GND (I2C)   │       │
                            │     └────────────────────┘       │
                            │                                  │
   ┌─── Verso Zenit ───┐   │     ┌────────────────────┐       │
   │                    │   │     │    AHT20           │       │
   │ ┌────────────┐     │   │     │    Temp/Hum 0x38   │       │
   │ │  TSL2591   │     │   │     │                    │       │
   │ │  Lux 0x29  │     │   │     │ SCL ── GPIO14      │       │
   │ │            │     │   │     │ SDA ── GPIO21      │       │
   │ └────────────┘     │   │     │ VCC ── VCC (I2C)   │       │
   │                    │   │     │ GND ── GND (I2C)   │       │
   │ ┌────────────┐     │   │     └────────────────────┘       │
   │ │  AS7341    │     │   │                                  │
   │ │  Spectral  │     │   │                                  │
   │ │  0x39      │     │   │                                  │
   │ └────────────┘     │   │                                  │
   │    BASETTA         │   │                                  │
   │    SENSORI         │   │                                  │
   └─────┬──────────────┘   │                                  │
         │                  │                                  │
         │ Cavo 4 fili     │                                  │
         │ (15-30cm)        │                                  │
         │                  │                                  │
   ┌─────┴──────────────────┴──────────────────────────────────┘
   │
   │  ┌─────────────────────────────────────────────────────┐
   │  │              LCDWiki 2.8" ESP32-S3                  │
   │  │                                                     │
   │  │  ┌──────────────────────────────┐                   │
   │  │  │     DISPLAY TFT 2.8"        │                   │
   │  │  │     ILI9341 320x240         │                   │
   │  │  │     + FT6336G Touch         │                   │
   │  │  └──────────────────────────────┘                   │
   │  │                                                     │
   │  │  [BOOT]                           [USB-C]           │
   │  │                                                     │
   ├──┤ [I2C] VCC GND SCL(15) SDA(16)                       │
   │  │        │   │    │       │                           │
   │  │        │   │    │       └── TSL2591.SDA + AS7341.SDA│
   │  │        │   │    └────────── TSL2591.SCL + AS7341.SCL│
   │  │        │   └── TSL/AS/GPS/AHT GND                  │
   │  │        └────── TSL/AS/GPS/AHT VCC                  │
   │  │                                                     │
   │  │ [EXP] G2   G3   G14  G21                           │
   │  │       │    │     │    │                             │
   │  │       │    │     │    └── AHT20.SDA                 │
   │  │       │    │     └─────── AHT20.SCL                 │
   │  │       │    └───────────── GPS.RX                    │
   │  │       └────────────────── GPS.TX                    │
   │  │                                                     │
   │  │  [Speaker] [Mic] [SD] [Battery] [RGB LED]          │
   │  └─────────────────────────────────────────────────────┘
   │
   └── Cavo I2C (4 fili) alla basetta sensori
```

---

## Tabella Connessioni

### Basetta Sensori (verso zenit, cavo 15-30cm)

| Sensore | Pin | Connessione | GPIO | Bus |
|---------|-----|-------------|------|-----|
| **TSL2591** | VIN | VCC (conn. I2C) | — | — |
| | GND | GND (conn. I2C) | — | — |
| | SCL | SCL (conn. I2C) | GPIO15 | I2C_NUM_0 |
| | SDA | SDA (conn. I2C) | GPIO16 | I2C_NUM_0 |
| **AS7341** | VIN | VCC (conn. I2C) | — | — |
| | GND | GND (conn. I2C) | GPIO15 | I2C_NUM_0 |
| | SCL | SCL (conn. I2C) | GPIO15 | I2C_NUM_0 |
| | SDA | SDA (conn. I2C) | GPIO16 | I2C_NUM_0 |

### Vicino alla Board

| Sensore | Pin | Connessione | GPIO | Bus |
|---------|-----|-------------|------|-----|
| **AHT20** | VIN | VCC (conn. I2C) | — | — |
| | GND | GND (conn. I2C) | — | — |
| | SCL | Pin 3 (conn. EXP) | GPIO14 | I2C_NUM_1 |
| | SDA | Pin 4 (conn. EXP) | GPIO21 | I2C_NUM_1 |
| **GPS** | TX→RX | Pin 1 (conn. EXP) | GPIO2 | UART1 RX |
| | RX←TX | Pin 2 (conn. EXP) | GPIO3 | UART1 TX |
| | VCC | VCC (conn. I2C) | — | — |
| | GND | GND (conn. I2C) | — | — |

---

## Note Importanti

### Alimentazione (VCC/GND)
Il connettore EXP **non fornisce VCC/GND**. Tutti i sensori prendono alimentazione dal **connettore I2C**:
- VCC = 3.3V (regolato dalla board)
- Corrente disponibile: ~200mA totali per tutti i sensori
- TSL2591: ~0.4mA, AS7341: ~10mA (durante misura), AHT20: ~0.3mA, GPS: ~30-50mA

### Pullup I2C
- **I2C_NUM_0** (GPIO15/16): Pullup interni 45kΩ (sufficienti a 100kHz)
- **I2C_NUM_1** (GPIO14/21): Pullup interni 45kΩ. Per AHT20 a 100kHz sono sufficienti. Per velocita' maggiori aggiungere pullup esterni 4.7kΩ.

### Conflitto Indirizzi
- **AHT20 (0x38)** = stesso indirizzo di **FT6336G Touch (0x38)**
- Soluzione: AHT20 su bus separato I2C_NUM_1 (GPIO14/21)
- **Non mettere mai AHT20 sullo stesso bus del touch!**

### Posizionamento Fisico

```
              ┌─────────────────────────┐
              │        BOX/CASE         │
              │                         │
              │  ┌─────────┐            │
              │  │ Basetta │ ← Foro     │  ← ALTO (verso cielo)
              │  │ TSL2591 │   zenit    │
              │  │ AS7341  │            │
              │  └────┬────┘            │
              │       │ cavo            │
              │       │                 │
              │  ┌────┴────────────┐    │
              │  │  LCDWiki Board  │    │  ← CENTRO
              │  │  (display verso │    │
              │  │   l'utente)     │    │
              │  └──┬──────────┬───┘    │
              │     │          │        │
              │  ┌──┴──┐  ┌───┴───┐    │
              │  │AHT20│  │  GPS  │    │  ← VICINO alla board
              │  │     │  │       │    │    (ventilato, non al sole)
              │  └─────┘  └───────┘    │
              │                         │
              └─────────────────────────┘
                       ↓
                   [USB-C] per alimentazione e debug
```

- **TSL2591 + AS7341**: In alto, verso zenit, dietro finestra trasparente (vetro ottico o foro aperto)
- **AHT20**: Vicino alla board, in zona ventilata, lontano dal display (calore SoC)
- **GPS**: Vicino alla board, antenna patch verso l'alto, lontano da metallo
- **Board**: Display verso l'utente, USB-C accessibile dal basso

---

## Lista Materiali

| # | Componente | Quantita' | Note |
|---|-----------|-----------|------|
| 1 | LCDWiki 2.8" ESP32-S3 | 1 | Board base con display, audio, touch |
| 2 | TSL2591 breakout | 1 | Adafruit o clone, sensore lux/SQM |
| 3 | AS7341 breakout | 1 | Adafruit o clone, spettro 8 canali |
| 4 | AHT20 breakout | 1 | Sensore temperatura + umidita' |
| 5 | GPS NMEA module | 1 | NEO-6M, NEO-7M, o simile (9600 baud) |
| 6 | Basetta millefori | 1 | ~3x4cm per TSL2591 + AS7341 |
| 7 | Cavo JST 1.25mm 4-pin | 2 | Per connettore I2C e connettore EXP |
| 8 | Cavo piatto 4 fili | 1 | 15-30cm, dalla board alla basetta sensori |
| 9 | Filo singolo 24AWG | 4 | Per collegare VCC/GND da I2C a EXP devices |
| 10 | Case/box stampato 3D | 1 | Con foro zenit per sensori e foro display |

---

## Indirizzi I2C — Riepilogo Scansione

```
Bus I2C_NUM_0 (GPIO15/16):
  0x18 — ES8311 Audio Codec (sulla board)
  0x29 — TSL2591 Sky Brightness (basetta esterna)
  0x38 — FT6336G Touch (sulla board)
  0x39 — AS7341 Spectral (basetta esterna)

Bus I2C_NUM_1 (GPIO14/21):
  0x38 — AHT20 Temp/Hum (vicino alla board)
```
