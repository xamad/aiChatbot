#ifndef AHT20_DEVICE_H
#define AHT20_DEVICE_H

#include "i2c_device.h"
#include <cstdint>

// AHT20 Commands
#define AHT20_CMD_INIT          0xBE
#define AHT20_CMD_TRIGGER       0xAC
#define AHT20_CMD_SOFTRESET     0xBA
#define AHT20_CMD_STATUS        0x71

class Aht20Device : public I2cDevice {
public:
    Aht20Device(i2c_master_bus_handle_t bus, uint8_t addr = 0x38,
                 uint32_t speed_hz = 100000);

    bool Initialize();
    bool Measure();

    float GetTemperature() const { return temperature_; }
    float GetHumidity() const { return humidity_; }
    float GetDewPoint() const { return dew_point_; }
    bool GetCondensationRisk() const { return condensation_risk_; }
    int GetDewCountdownMin() const { return dew_countdown_min_; }

    // For SQM temperature compensation
    void SetTempOffset(float offset) { temp_offset_ = offset; }

    // Temperature rate tracking
    void UpdateTempRate();
    float GetTempRate() const { return temp_rate_; }  // C/hour

private:
    float CalculateDewPoint(float t, float rh);

    float temperature_ = 0;
    float humidity_ = 0;
    float dew_point_ = 0;
    float temp_offset_ = 0;    // Calibration offset
    bool condensation_risk_ = false;
    int dew_countdown_min_ = -1;

    // Temperature rate tracking
    float temp_rate_ = 0;       // C/hour (negative = cooling)
    float prev_temp_ = 0;
    uint32_t prev_temp_time_ = 0;
};

#endif // AHT20_DEVICE_H
