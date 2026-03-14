#ifndef AS7341_DEVICE_H
#define AS7341_DEVICE_H

#include "i2c_device.h"
#include <cstdint>

// AS7341 Register Map
#define AS7341_REG_ENABLE       0x80
#define AS7341_REG_ATIME        0x81
#define AS7341_REG_WTIME        0x83
#define AS7341_REG_ASTEP_L      0xCA
#define AS7341_REG_ASTEP_H      0xCB
#define AS7341_REG_CFG0         0xA9
#define AS7341_REG_CFG1         0xAA  // Gain
#define AS7341_REG_CFG6         0xAF
#define AS7341_REG_STATUS       0x71
#define AS7341_REG_STATUS2      0xA3
#define AS7341_REG_CH0_L        0x95
#define AS7341_REG_ID           0x92

// SMUX configuration registers
#define AS7341_REG_CFG10        0x65

// Gain values
enum As7341Gain {
    AS7341_GAIN_0_5X  = 0,
    AS7341_GAIN_1X    = 1,
    AS7341_GAIN_2X    = 2,
    AS7341_GAIN_4X    = 3,
    AS7341_GAIN_8X    = 4,
    AS7341_GAIN_16X   = 5,
    AS7341_GAIN_32X   = 6,
    AS7341_GAIN_64X   = 7,
    AS7341_GAIN_128X  = 8,
    AS7341_GAIN_256X  = 9,
    AS7341_GAIN_512X  = 10,
};

// Light pollution source types
enum LpSourceType {
    LP_NATURAL = 0,
    LP_LED     = 1,
    LP_HPS     = 2,     // High Pressure Sodium
    LP_MERCURY = 3,
    LP_MIXED   = 4,
};

struct SpectralReading {
    uint16_t f1_415nm;    // Violet (Mercury indicator)
    uint16_t f2_445nm;    // Blue (LED indicator)
    uint16_t f3_480nm;    // Cyan
    uint16_t f4_515nm;    // Green (Mercury indicator)
    uint16_t f5_555nm;    // Lime (peak human vision, reference)
    uint16_t f6_590nm;    // Orange (HPS sodium indicator)
    uint16_t f7_630nm;    // Red
    uint16_t f8_680nm;    // Deep Red
    uint16_t clear;       // Clear (broadband)
    uint16_t nir;         // Near-IR
};

class As7341Device : public I2cDevice {
public:
    As7341Device(i2c_master_bus_handle_t bus, uint8_t addr = 0x39,
                  uint32_t speed_hz = 100000);

    bool Initialize();
    bool Measure();

    // Results
    const SpectralReading& GetReading() const { return reading_; }
    LpSourceType GetLpSource() const { return lp_source_; }
    const char* GetLpSourceName() const;
    float GetLpCorrection() const { return lp_correction_; }
    uint8_t GetSpectralQuality() const { return spectral_quality_; }

    // Ratios
    float GetBlueRatio() const { return blue_ratio_; }
    float GetSodiumRatio() const { return sodium_ratio_; }

    // Daytime atmospheric analysis (valid when ambient light is bright)
    int GetAtmosphericClarity() const;          // 0-100% (Rayleigh blue/red ratio)
    const char* GetSkyCondition() const;        // "Sereno", "Coperto", "Foschia", etc.
    const char* GetSolarPhotoVerdict() const;    // "Eccellente", "Buono", "Mediocre", "Scadente"

private:
    // LP detection thresholds
    static constexpr float LED_BLUE_THRESHOLD = 0.6f;
    static constexpr float HPS_SODIUM_THRESHOLD = 1.8f;
    static constexpr float LED_CORRECTION_MAX = 0.3f;
    static constexpr float HPS_CORRECTION_MAX = 0.2f;

    // SMUX configuration for F1-F4+Clear+NIR
    void SmuxConfigF1F4();
    // SMUX configuration for F5-F8+Clear+NIR
    void SmuxConfigF5F8();
    bool StartSmuxCommand();
    bool WaitForData();
    void ReadChannels(uint16_t* data, int count);

    void AnalyzeLightPollution();

    // Settings
    As7341Gain gain_ = AS7341_GAIN_256X;
    uint8_t atime_ = 29;      // (29+1) * 2.78ms ~= 83ms per step
    uint16_t astep_ = 999;    // Total ~8.3s integration

    // Results
    SpectralReading reading_ = {};
    LpSourceType lp_source_ = LP_NATURAL;
    float lp_correction_ = 0;
    uint8_t spectral_quality_ = 0;
    float blue_ratio_ = 0;
    float sodium_ratio_ = 0;
};

#endif // AS7341_DEVICE_H
