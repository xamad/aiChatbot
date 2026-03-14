#include "as7341_device.h"
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <cmath>
#include <algorithm>

#define TAG "AS7341"

As7341Device::As7341Device(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t speed_hz)
    : I2cDevice(bus, addr, speed_hz) {
}

bool As7341Device::Initialize() {
    // Verify chip ID (lower nibble should be 0x09)
    uint8_t id = ReadReg(AS7341_REG_ID);
    if ((id & 0xFC) != 0x24) {  // AS7341 part number
        ESP_LOGE(TAG, "Invalid chip ID: 0x%02X", id);
        return false;
    }
    ESP_LOGI(TAG, "AS7341 detected (ID=0x%02X)", id);

    // Power on
    WriteReg(AS7341_REG_ENABLE, 0x01);  // PON
    vTaskDelay(pdMS_TO_TICKS(10));

    // Set integration time: ATIME
    WriteReg(AS7341_REG_ATIME, atime_);

    // Set ASTEP (16-bit)
    WriteReg(AS7341_REG_ASTEP_L, astep_ & 0xFF);
    WriteReg(AS7341_REG_ASTEP_H, (astep_ >> 8) & 0xFF);

    // Set gain
    WriteReg(AS7341_REG_CFG1, (uint8_t)gain_);

    ESP_LOGI(TAG, "AS7341 initialized (gain=%dx, atime=%d, astep=%d)",
             1 << gain_, atime_, astep_);
    return true;
}

void As7341Device::SmuxConfigF1F4() {
    // Configure SMUX to route F1, F2, F3, F4, Clear, NIR to ADC channels
    // This follows the AS7341 datasheet SMUX configuration for first bank
    WriteReg(0x00, 0x30);  // F3 left -> ADC2
    WriteReg(0x01, 0x01);  // F1 left -> ADC0
    WriteReg(0x02, 0x00);
    WriteReg(0x03, 0x00);
    WriteReg(0x04, 0x00);
    WriteReg(0x05, 0x42);  // F4 left -> ADC3, NIR -> connect
    WriteReg(0x06, 0x00);
    WriteReg(0x07, 0x00);
    WriteReg(0x08, 0x50);  // F2 left -> ADC1
    WriteReg(0x09, 0x00);
    WriteReg(0x0A, 0x00);
    WriteReg(0x0B, 0x00);
    WriteReg(0x0C, 0x20);  // F1 right -> ADC0
    WriteReg(0x0D, 0x04);  // F3 right -> ADC2
    WriteReg(0x0E, 0x00);
    WriteReg(0x0F, 0x30);  // F2 right -> ADC1
    WriteReg(0x10, 0x01);  // Clear -> ADC4
    WriteReg(0x11, 0x50);  // F4 right -> ADC3
    WriteReg(0x12, 0x00);
    WriteReg(0x13, 0x06);  // NIR -> ADC5
}

void As7341Device::SmuxConfigF5F8() {
    // Configure SMUX to route F5, F6, F7, F8, Clear, NIR to ADC channels
    WriteReg(0x00, 0x00);
    WriteReg(0x01, 0x00);
    WriteReg(0x02, 0x00);
    WriteReg(0x03, 0x40);  // F7 left -> ADC2
    WriteReg(0x04, 0x02);  // F5 left -> ADC0
    WriteReg(0x05, 0x00);
    WriteReg(0x06, 0x10);  // F6 left -> ADC1
    WriteReg(0x07, 0x03);  // F8 left -> ADC3
    WriteReg(0x08, 0x00);
    WriteReg(0x09, 0x00);
    WriteReg(0x0A, 0x00);
    WriteReg(0x0B, 0x00);
    WriteReg(0x0C, 0x00);
    WriteReg(0x0D, 0x00);
    WriteReg(0x0E, 0x24);  // F5 right -> ADC0, F7 right -> ADC2
    WriteReg(0x0F, 0x00);
    WriteReg(0x10, 0x00);
    WriteReg(0x11, 0x50);  // F6 right -> ADC1, F8 right -> ADC3
    WriteReg(0x12, 0x00);
    WriteReg(0x13, 0x06);  // Clear -> ADC4, NIR -> ADC5
}

bool As7341Device::StartSmuxCommand() {
    // Enable SMUX command
    WriteReg(AS7341_REG_ENABLE, 0x01);  // PON only
    WriteReg(AS7341_REG_CFG6, 0x10);    // SMUX command = 2 (write to RAM)

    // Enable SMUX execution
    uint8_t enable = ReadReg(AS7341_REG_ENABLE);
    WriteReg(AS7341_REG_ENABLE, enable | 0x10);  // SMUXEN

    // Wait for SMUX to complete
    for (int i = 0; i < 100; i++) {
        vTaskDelay(pdMS_TO_TICKS(1));
        enable = ReadReg(AS7341_REG_ENABLE);
        if (!(enable & 0x10)) return true;
    }
    ESP_LOGE(TAG, "SMUX command timeout");
    return false;
}

bool As7341Device::WaitForData() {
    // Enable spectral measurement
    uint8_t enable = ReadReg(AS7341_REG_ENABLE);
    WriteReg(AS7341_REG_ENABLE, enable | 0x02);  // SP_EN

    // Wait for data ready (integration time + margin)
    float int_ms = (float)(atime_ + 1) * (float)(astep_ + 1) * 2.78f / 1000.0f;
    int wait_ms = (int)int_ms + 500;

    for (int elapsed = 0; elapsed < wait_ms; elapsed += 50) {
        vTaskDelay(pdMS_TO_TICKS(50));
        uint8_t status = ReadReg(AS7341_REG_STATUS2);
        if (status & 0x40) {  // AVALID
            return true;
        }
    }
    ESP_LOGE(TAG, "Data ready timeout");
    return false;
}

void As7341Device::ReadChannels(uint16_t* data, int count) {
    for (int i = 0; i < count && i < 6; i++) {
        uint8_t lo = ReadReg(AS7341_REG_CH0_L + i * 2);
        uint8_t hi = ReadReg(AS7341_REG_CH0_L + i * 2 + 1);
        data[i] = lo | (hi << 8);
    }
}

bool As7341Device::Measure() {
    uint16_t data[6];

    // === First bank: F1, F2, F3, F4, Clear, NIR ===
    SmuxConfigF1F4();
    if (!StartSmuxCommand()) return false;
    if (!WaitForData()) return false;
    ReadChannels(data, 6);

    reading_.f1_415nm = data[0];
    reading_.f2_445nm = data[1];
    reading_.f3_480nm = data[2];
    reading_.f4_515nm = data[3];
    reading_.clear = data[4];
    reading_.nir = data[5];

    // Disable spectral
    uint8_t enable = ReadReg(AS7341_REG_ENABLE);
    WriteReg(AS7341_REG_ENABLE, enable & ~0x02);

    // === Second bank: F5, F6, F7, F8, Clear, NIR ===
    SmuxConfigF5F8();
    if (!StartSmuxCommand()) return false;
    if (!WaitForData()) return false;
    ReadChannels(data, 6);

    reading_.f5_555nm = data[0];
    reading_.f6_590nm = data[1];
    reading_.f7_630nm = data[2];
    reading_.f8_680nm = data[3];
    // Clear and NIR from second bank (use average if desired)

    // Disable spectral
    enable = ReadReg(AS7341_REG_ENABLE);
    WriteReg(AS7341_REG_ENABLE, enable & ~0x02);

    // Analyze LP
    AnalyzeLightPollution();

    ESP_LOGI(TAG, "Spectral: F1=%u F2=%u F3=%u F4=%u F5=%u F6=%u F7=%u F8=%u Clr=%u NIR=%u",
             reading_.f1_415nm, reading_.f2_445nm, reading_.f3_480nm, reading_.f4_515nm,
             reading_.f5_555nm, reading_.f6_590nm, reading_.f7_630nm, reading_.f8_680nm,
             reading_.clear, reading_.nir);
    ESP_LOGI(TAG, "LP source: %s, correction=%.2f MPSAS, SQI=%d%%",
             GetLpSourceName(), lp_correction_, spectral_quality_);

    return true;
}

void As7341Device::AnalyzeLightPollution() {
    // Normalize ratios to F5 (555nm — peak human vision)
    if (reading_.f5_555nm == 0) {
        lp_source_ = LP_NATURAL;
        lp_correction_ = 0;
        spectral_quality_ = 0;
        return;
    }

    float f5 = (float)reading_.f5_555nm;
    blue_ratio_ = (float)reading_.f2_445nm / f5;
    sodium_ratio_ = (float)reading_.f6_590nm / f5;
    float f1_ratio = (float)reading_.f1_415nm / f5;
    float f5f4_ratio = f5 / std::max((float)reading_.f4_515nm, 1.0f);

    // Detect LP source
    bool is_led = blue_ratio_ > LED_BLUE_THRESHOLD;
    bool is_hps = sodium_ratio_ > HPS_SODIUM_THRESHOLD;
    bool is_mercury = f1_ratio > 0.8f && blue_ratio_ > 0.6f && f5f4_ratio > 1.3f;

    if (is_mercury) {
        lp_source_ = LP_MERCURY;
        lp_correction_ = 0.15f;
    } else if (is_led && is_hps) {
        lp_source_ = LP_MIXED;
        lp_correction_ = (LED_CORRECTION_MAX + HPS_CORRECTION_MAX) / 2.0f;
    } else if (is_led) {
        lp_source_ = LP_LED;
        // Scale correction by how far above threshold
        float excess = (blue_ratio_ - LED_BLUE_THRESHOLD) / LED_BLUE_THRESHOLD;
        lp_correction_ = std::min(excess * LED_CORRECTION_MAX, LED_CORRECTION_MAX);
    } else if (is_hps) {
        lp_source_ = LP_HPS;
        float excess = (sodium_ratio_ - HPS_SODIUM_THRESHOLD) / HPS_SODIUM_THRESHOLD;
        lp_correction_ = std::min(excess * HPS_CORRECTION_MAX, HPS_CORRECTION_MAX);
    } else {
        lp_source_ = LP_NATURAL;
        lp_correction_ = 0;
    }

    // Spectral Quality Index (0-100%): how "natural" the spectrum is
    // Natural sky should have smooth curve, LP creates spikes
    float variance = 0;
    float channels[] = {
        (float)reading_.f1_415nm, (float)reading_.f2_445nm, (float)reading_.f3_480nm,
        (float)reading_.f4_515nm, (float)reading_.f5_555nm, (float)reading_.f6_590nm,
        (float)reading_.f7_630nm, (float)reading_.f8_680nm
    };

    float mean = 0;
    for (int i = 0; i < 8; i++) mean += channels[i];
    mean /= 8.0f;

    if (mean > 0) {
        for (int i = 0; i < 8; i++) {
            float diff = (channels[i] / mean) - 1.0f;
            variance += diff * diff;
        }
        variance /= 8.0f;
        // Low variance = natural, high variance = LP contaminated
        spectral_quality_ = std::clamp((int)(100.0f - variance * 200.0f), 0, 100);
    } else {
        spectral_quality_ = 0;
    }
}

// --- Daytime atmospheric analysis ---
// Clear sky has strong Rayleigh scattering: blue >> red
// Overcast sky scatters uniformly: blue ≈ red
// Haze/aerosols scatter blue away: red >> blue

int As7341Device::GetAtmosphericClarity() const {
    float blue_sum = (float)(reading_.f1_415nm + reading_.f2_445nm + reading_.f3_480nm);
    float red_sum = (float)(reading_.f7_630nm + reading_.f8_680nm);
    if (red_sum < 1.0f) return 0;

    float ratio = blue_sum / red_sum;
    // Typical values: clear sky ≈ 2.5-4.0, overcast ≈ 0.8-1.2, haze ≈ 0.5-0.8
    // Map ratio 0.5-3.5 → 0-100%
    int clarity = std::clamp((int)((ratio - 0.5f) / 3.0f * 100.0f), 0, 100);
    return clarity;
}

const char* As7341Device::GetSkyCondition() const {
    float blue_sum = (float)(reading_.f1_415nm + reading_.f2_445nm + reading_.f3_480nm);
    float red_sum = (float)(reading_.f7_630nm + reading_.f8_680nm);
    if (red_sum < 1.0f) return "N/D";

    float ratio = blue_sum / red_sum;
    float nir_ratio = (reading_.clear > 0) ? (float)reading_.nir / (float)reading_.clear : 0;

    // NIR/Clear high + low blue/red = haze/aerosols
    if (ratio < 0.8f || nir_ratio > 0.6f) return "Foschia";
    if (ratio < 1.2f) return "Coperto";
    if (ratio < 1.8f) return "Poco nuvoloso";
    if (ratio < 2.5f) return "Parz. sereno";
    return "Sereno";
}

const char* As7341Device::GetSolarPhotoVerdict() const {
    int clarity = GetAtmosphericClarity();
    float nir_ratio = (reading_.clear > 0) ? (float)reading_.nir / (float)reading_.clear : 0;

    // Solar photography needs clear sky, low aerosols
    if (clarity >= 70 && nir_ratio < 0.4f) return "Eccellente";
    if (clarity >= 50) return "Buono";
    if (clarity >= 30) return "Mediocre";
    return "Scadente";
}

const char* As7341Device::GetLpSourceName() const {
    switch (lp_source_) {
        case LP_NATURAL: return "Naturale";
        case LP_LED:     return "LED";
        case LP_HPS:     return "Sodio (HPS)";
        case LP_MERCURY: return "Mercurio";
        case LP_MIXED:   return "Misto";
        default:         return "Sconosciuto";
    }
}
