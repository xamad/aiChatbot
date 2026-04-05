#ifndef TSL2591_DEVICE_H
#define TSL2591_DEVICE_H

#include "i2c_device.h"
#include <cstdint>

// TSL2591 Register Map
#define TSL2591_REG_ENABLE      0x00
#define TSL2591_REG_CONTROL     0x01
#define TSL2591_REG_ID          0x12
#define TSL2591_REG_STATUS      0x13
#define TSL2591_REG_C0DATAL     0x14  // CH0 (Full spectrum)
#define TSL2591_REG_C0DATAH     0x15
#define TSL2591_REG_C1DATAL     0x16  // CH1 (IR only)
#define TSL2591_REG_C1DATAH     0x17

// TSL2591 Command bits
#define TSL2591_CMD_BIT         0xA0  // Command + Normal
#define TSL2591_CMD_SPECIAL     0xE0  // Special function

// Enable register bits
#define TSL2591_ENABLE_NPIEN    0x80
#define TSL2591_ENABLE_AIEN     0x10
#define TSL2591_ENABLE_AEN      0x02  // ALS Enable
#define TSL2591_ENABLE_PON      0x01  // Power ON

// Gain settings
enum Tsl2591Gain {
    TSL2591_GAIN_LOW  = 0x00,   // 1x
    TSL2591_GAIN_MED  = 0x10,   // 25x
    TSL2591_GAIN_HIGH = 0x20,   // 428x
    TSL2591_GAIN_MAX  = 0x30,   // 9876x
};

// Integration time settings
enum Tsl2591Integration {
    TSL2591_INT_100MS = 0x00,
    TSL2591_INT_200MS = 0x01,
    TSL2591_INT_300MS = 0x02,
    TSL2591_INT_400MS = 0x03,
    TSL2591_INT_500MS = 0x04,
    TSL2591_INT_600MS = 0x05,
};

class Tsl2591Device : public I2cDevice {
public:
    Tsl2591Device(i2c_master_bus_handle_t bus, uint8_t addr = 0x29,
                   uint32_t speed_hz = 100000);

    bool Initialize();
    bool Measure(float ambient_temp = 25.0f, float humidity = 50.0f,
                 float pressure = 1013.25f);

    // Results
    float GetMpsas() const { return mpsas_; }
    float GetMpsasRaw() const { return mpsas_raw_; }
    float GetNelm() const { return nelm_; }
    uint8_t GetBortle() const { return bortle_; }
    float GetLux() const { return lux_; }
    float GetIrRatio() const { return ir_ratio_; }
    uint8_t GetConfidence() const { return confidence_; }
    uint16_t GetRawFull() const { return raw_full_; }
    uint16_t GetRawIR() const { return raw_ir_; }
    const char* GetQuality() const { return quality_; }
    int GetGainSetting() const { return (int)gain_; }
    int GetIntegrationSetting() const { return (int)integration_; }

private:
    // Calibration constants
    static constexpr float MPSAS_ZERO_POINT = 12.93f;
    static constexpr float COUNTS_PER_LUX = 408.0f;
    static constexpr int DARK_CURRENT = 3;
    static constexpr float TEMP_COEFF = 0.010f;
    static constexpr float HUMIDITY_COEFF_LINEAR = 0.0008f;
    static constexpr float HUMIDITY_COEFF_NONLIN = 0.003f;
    static constexpr float HUMIDITY_THRESHOLD = 70.0f;
    static constexpr float PRESSURE_REF = 1013.25f;
    static constexpr float PRESSURE_COEFF = 0.0004f;
    static constexpr uint16_t SATURATION = 65000;
    static constexpr uint16_t MIN_SIGNAL = 10;
    static constexpr float MPSAS_MAX = 22.0f;
    static constexpr float MPSAS_MIN = 10.0f;

    // Gain multipliers
    static constexpr float GAIN_MULT[] = {1.0f, 25.0f, 428.0f, 9876.0f};

    // Internal methods
    void WriteCommand(uint8_t reg, uint8_t value);
    uint8_t ReadCommand(uint8_t reg);
    void Enable();
    void Disable();
    bool ReadRawData(uint16_t& full, uint16_t& ir);
    bool AutoRange(uint16_t& full, uint16_t& ir, int depth = 0);
    float CalculateLux(uint16_t full, uint16_t ir);
    float LuxToMpsas(float lux);
    float CalculateNelm(float mpsas);
    uint8_t CalculateBortle(float mpsas);
    float ApplyTempComp(float mpsas, float temp);
    float ApplyHumidityComp(float mpsas, float humidity);
    float ApplyPressureComp(float mpsas, float pressure);
    uint8_t CalculateConfidence(uint16_t full, uint16_t ir);
    const char* BortleToQuality(uint8_t bortle);

    float GetGainMultiplier();
    float GetIntegrationMs();

    // Current settings
    Tsl2591Gain gain_ = TSL2591_GAIN_MAX;
    Tsl2591Integration integration_ = TSL2591_INT_600MS;

    // Results
    float mpsas_ = 0;
    float mpsas_raw_ = 0;
    float nelm_ = 0;
    float lux_ = 0;
    float ir_ratio_ = 0;
    uint8_t bortle_ = 9;
    uint8_t confidence_ = 0;
    uint16_t raw_full_ = 0;
    uint16_t raw_ir_ = 0;
    const char* quality_ = "Unknown";
};

#endif // TSL2591_DEVICE_H
