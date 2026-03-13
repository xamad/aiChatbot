#include "tsl2591_device.h"
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <cmath>
#include <algorithm>

#define TAG "TSL2591"

constexpr float Tsl2591Device::GAIN_MULT[];

Tsl2591Device::Tsl2591Device(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t speed_hz)
    : I2cDevice(bus, addr, speed_hz) {
}

void Tsl2591Device::WriteCommand(uint8_t reg, uint8_t value) {
    WriteReg(TSL2591_CMD_BIT | reg, value);
}

uint8_t Tsl2591Device::ReadCommand(uint8_t reg) {
    return ReadReg(TSL2591_CMD_BIT | reg);
}

void Tsl2591Device::Enable() {
    WriteCommand(TSL2591_REG_ENABLE, TSL2591_ENABLE_PON | TSL2591_ENABLE_AEN);
}

void Tsl2591Device::Disable() {
    WriteCommand(TSL2591_REG_ENABLE, 0x00);
}

bool Tsl2591Device::Initialize() {
    // Verify chip ID
    uint8_t id = ReadCommand(TSL2591_REG_ID);
    if (id != 0x50) {
        ESP_LOGE(TAG, "Invalid chip ID: 0x%02X (expected 0x50)", id);
        return false;
    }
    ESP_LOGI(TAG, "TSL2591 detected (ID=0x%02X)", id);

    // Set default gain and integration for dark sky
    gain_ = TSL2591_GAIN_MAX;
    integration_ = TSL2591_INT_600MS;
    WriteCommand(TSL2591_REG_CONTROL, (uint8_t)gain_ | (uint8_t)integration_);

    Disable();
    ESP_LOGI(TAG, "TSL2591 initialized (gain=MAX, int=600ms)");
    return true;
}

float Tsl2591Device::GetGainMultiplier() {
    switch (gain_) {
        case TSL2591_GAIN_LOW:  return 1.0f;
        case TSL2591_GAIN_MED:  return 25.0f;
        case TSL2591_GAIN_HIGH: return 428.0f;
        case TSL2591_GAIN_MAX:  return 9876.0f;
        default: return 1.0f;
    }
}

float Tsl2591Device::GetIntegrationMs() {
    return 100.0f * ((uint8_t)integration_ + 1);
}

bool Tsl2591Device::ReadRawData(uint16_t& full, uint16_t& ir) {
    Enable();

    // Wait for integration to complete
    int wait_ms = (int)GetIntegrationMs() + 50;
    vTaskDelay(pdMS_TO_TICKS(wait_ms));

    // Check if data is valid
    uint8_t status = ReadCommand(TSL2591_REG_STATUS);
    if (!(status & 0x01)) {
        ESP_LOGW(TAG, "ALS data not valid (status=0x%02X)", status);
        Disable();
        return false;
    }

    // Read CH0 (full spectrum) and CH1 (IR)
    uint8_t buf[4];
    ReadRegs(TSL2591_CMD_BIT | TSL2591_REG_C0DATAL, buf, 4);

    full = buf[0] | (buf[1] << 8);
    ir = buf[2] | (buf[3] << 8);

    Disable();
    return true;
}

bool Tsl2591Device::AutoRange(uint16_t& full, uint16_t& ir, int depth) {
    if (depth > 4) return false;

    // Apply current settings
    WriteCommand(TSL2591_REG_CONTROL, (uint8_t)gain_ | (uint8_t)integration_);

    if (!ReadRawData(full, ir)) return false;

    // Check saturation — reduce gain
    if (full >= SATURATION || ir >= SATURATION) {
        if (gain_ == TSL2591_GAIN_MAX) gain_ = TSL2591_GAIN_HIGH;
        else if (gain_ == TSL2591_GAIN_HIGH) gain_ = TSL2591_GAIN_MED;
        else if (gain_ == TSL2591_GAIN_MED) gain_ = TSL2591_GAIN_LOW;
        else return false;  // Already at lowest gain
        ESP_LOGD(TAG, "Saturated, reducing gain (depth=%d)", depth);
        return AutoRange(full, ir, depth + 1);
    }

    // Check low signal — increase gain
    if (full < MIN_SIGNAL && gain_ != TSL2591_GAIN_MAX) {
        if (gain_ == TSL2591_GAIN_LOW) gain_ = TSL2591_GAIN_MED;
        else if (gain_ == TSL2591_GAIN_MED) gain_ = TSL2591_GAIN_HIGH;
        else if (gain_ == TSL2591_GAIN_HIGH) gain_ = TSL2591_GAIN_MAX;
        ESP_LOGD(TAG, "Low signal, increasing gain (depth=%d)", depth);
        return AutoRange(full, ir, depth + 1);
    }

    return true;
}

float Tsl2591Device::CalculateLux(uint16_t full, uint16_t ir) {
    float gain_mult = GetGainMultiplier();
    float int_time = GetIntegrationMs();

    // Dark current subtraction (use int32_t to avoid underflow)
    int32_t corr_full = (int32_t)full - DARK_CURRENT;
    int32_t corr_ir = (int32_t)ir - DARK_CURRENT;
    if (corr_full < 0) corr_full = 0;
    if (corr_ir < 0) corr_ir = 0;

    // Counts Per Lux (TSL2591 datasheet)
    float cpl = (int_time * gain_mult) / COUNTS_PER_LUX;

    // Dual-channel lux with IR rejection
    float lux1 = ((float)corr_full - 1.64f * (float)corr_ir) / cpl;
    float lux2 = (0.59f * (float)corr_full - 0.86f * (float)corr_ir) / cpl;

    float lux = std::max(std::max(lux1, lux2), 0.0001f);

    // Non-linearity correction at extreme low light
    if (lux < 0.001f && gain_ == TSL2591_GAIN_MAX && integration_ == TSL2591_INT_600MS) {
        lux *= 0.92f;
    }

    return lux;
}

float Tsl2591Device::LuxToMpsas(float lux) {
    if (lux < 0.0001f) lux = 0.0001f;
    return MPSAS_ZERO_POINT - 2.5f * log10f(lux);
}

float Tsl2591Device::CalculateNelm(float mpsas) {
    // Schaefer (1990) / Cinzano formula
    float exp_term = powf(10.0f, (21.58f - mpsas) / 5.0f);
    float nelm = 7.93f - 5.0f * log10f(exp_term + 1.0f);
    return std::clamp(nelm, 0.0f, 8.0f);
}

uint8_t Tsl2591Device::CalculateBortle(float mpsas) {
    if (mpsas >= 21.99f) return 1;  // Excellent dark site
    if (mpsas >= 21.89f) return 2;  // Typical dark site
    if (mpsas >= 21.69f) return 3;  // Rural sky
    if (mpsas >= 21.25f) return 4;  // Rural/Suburban transition
    if (mpsas >= 20.49f) return 5;  // Suburban sky
    if (mpsas >= 19.50f) return 6;  // Bright suburban
    if (mpsas >= 18.94f) return 7;  // Suburban/Urban transition
    if (mpsas >= 18.38f) return 8;  // City sky
    return 9;                         // Inner-city sky
}

const char* Tsl2591Device::BortleToQuality(uint8_t bortle) {
    switch (bortle) {
        case 1: return "Eccellente";
        case 2: return "Molto Scuro";
        case 3: return "Rurale";
        case 4: return "Rurale/Suburbano";
        case 5: return "Suburbano";
        case 6: return "Suburbano Luminoso";
        case 7: return "Sub/Urbano";
        case 8: return "Citta'";
        case 9: return "Centro Citta'";
        default: return "Sconosciuto";
    }
}

float Tsl2591Device::ApplyTempComp(float mpsas, float temp) {
    float delta_t = temp - 25.0f;
    return mpsas + (delta_t * TEMP_COEFF);
}

float Tsl2591Device::ApplyHumidityComp(float mpsas, float humidity) {
    float comp = 0;
    if (humidity <= HUMIDITY_THRESHOLD) {
        comp = (humidity - 50.0f) * HUMIDITY_COEFF_LINEAR;
    } else {
        float linear_part = (HUMIDITY_THRESHOLD - 50.0f) * HUMIDITY_COEFF_LINEAR;
        float excess = humidity - HUMIDITY_THRESHOLD;
        float nonlin_part = excess * HUMIDITY_COEFF_NONLIN * (1.0f + excess / 30.0f);
        comp = linear_part + nonlin_part;
    }
    return mpsas - comp;  // Higher humidity = brighter sky = lower MPSAS
}

float Tsl2591Device::ApplyPressureComp(float mpsas, float pressure) {
    float delta_p = PRESSURE_REF - pressure;
    return mpsas + (delta_p * PRESSURE_COEFF);
}

uint8_t Tsl2591Device::CalculateConfidence(uint16_t full, uint16_t ir) {
    uint8_t conf = 100;

    // Penalize low signal
    if (full < 50) conf -= 30;
    else if (full < 200) conf -= 15;

    // Penalize near-saturation
    if (full > 60000) conf -= 20;

    // Penalize high IR ratio (clouds or sensor issue)
    float ratio = (full > 0) ? (float)ir / (float)full : 0;
    if (ratio > 0.35f) conf -= 25;
    else if (ratio > 0.25f) conf -= 10;

    return std::clamp((int)conf, 0, 100);
}

bool Tsl2591Device::Measure(float ambient_temp, float humidity, float pressure) {
    uint16_t full = 0, ir = 0;

    if (!AutoRange(full, ir)) {
        ESP_LOGE(TAG, "Measurement failed (auto-range exhausted)");
        confidence_ = 0;
        return false;
    }

    raw_full_ = full;
    raw_ir_ = ir;

    // IR ratio for cloud detection
    ir_ratio_ = (full > 0) ? (float)ir / (float)full : 0;

    // Core calculation
    lux_ = CalculateLux(full, ir);
    mpsas_raw_ = LuxToMpsas(lux_);

    // Environmental corrections
    mpsas_ = mpsas_raw_;
    mpsas_ = ApplyTempComp(mpsas_, ambient_temp);
    mpsas_ = ApplyHumidityComp(mpsas_, humidity);
    mpsas_ = ApplyPressureComp(mpsas_, pressure);

    // Clamp to physical limits
    mpsas_ = std::clamp(mpsas_, MPSAS_MIN, MPSAS_MAX);

    // Derived values
    nelm_ = CalculateNelm(mpsas_);
    bortle_ = CalculateBortle(mpsas_);
    quality_ = BortleToQuality(bortle_);
    confidence_ = CalculateConfidence(full, ir);

    ESP_LOGI(TAG, "SQM: %.2f MPSAS, NELM=%.1f, Bortle=%d (%s), Conf=%d%%",
             mpsas_, nelm_, bortle_, quality_, confidence_);
    ESP_LOGD(TAG, "Raw: full=%u ir=%u, lux=%.4f, gain=%d, int=%dms",
             full, ir, lux_, (int)gain_, (int)GetIntegrationMs());

    return true;
}
