#include "aht20_device.h"
#include <esp_log.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <cmath>
#include <algorithm>

#define TAG "AHT20"

Aht20Device::Aht20Device(i2c_master_bus_handle_t bus, uint8_t addr, uint32_t speed_hz)
    : I2cDevice(bus, addr, speed_hz) {
}

bool Aht20Device::Initialize() {
    // Soft reset
    uint8_t cmd = AHT20_CMD_SOFTRESET;
    i2c_master_transmit(i2c_device_, &cmd, 1, 100);
    vTaskDelay(pdMS_TO_TICKS(20));

    // Check calibration status
    uint8_t status = 0;
    cmd = AHT20_CMD_STATUS;
    i2c_master_transmit_receive(i2c_device_, &cmd, 1, &status, 1, 100);

    if (!(status & 0x08)) {
        // Not calibrated, send init command
        uint8_t init_cmd[] = {AHT20_CMD_INIT, 0x08, 0x00};
        i2c_master_transmit(i2c_device_, init_cmd, 3, 100);
        vTaskDelay(pdMS_TO_TICKS(10));
        ESP_LOGI(TAG, "AHT20 calibration initiated");
    }

    ESP_LOGI(TAG, "AHT20 initialized (status=0x%02X)", status);
    return true;
}

bool Aht20Device::Measure() {
    // Trigger measurement
    uint8_t trigger[] = {AHT20_CMD_TRIGGER, 0x33, 0x00};
    esp_err_t ret = i2c_master_transmit(i2c_device_, trigger, 3, 100);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Trigger measurement failed");
        return false;
    }

    // Wait for measurement (AHT20 needs ~80ms)
    vTaskDelay(pdMS_TO_TICKS(100));

    // Read 6 bytes: status + 20-bit humidity + 20-bit temperature
    uint8_t data[6];
    ret = i2c_master_receive(i2c_device_, data, 6, 100);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Read data failed");
        return false;
    }

    // Check busy flag
    if (data[0] & 0x80) {
        ESP_LOGW(TAG, "Sensor still busy");
        return false;
    }

    // Parse humidity (20-bit, upper part)
    uint32_t raw_hum = ((uint32_t)data[1] << 12) |
                       ((uint32_t)data[2] << 4) |
                       ((uint32_t)data[3] >> 4);
    humidity_ = (float)raw_hum * 100.0f / 1048576.0f;

    // Parse temperature (20-bit, lower part)
    uint32_t raw_temp = (((uint32_t)data[3] & 0x0F) << 16) |
                        ((uint32_t)data[4] << 8) |
                        ((uint32_t)data[5]);
    temperature_ = (float)raw_temp * 200.0f / 1048576.0f - 50.0f;

    // Apply calibration offset
    temperature_ += temp_offset_;

    // Calculate dew point (Alduchov & Eskridge 1996 — Magnus formula)
    dew_point_ = CalculateDewPoint(temperature_, humidity_);

    // Condensation risk
    float spread = temperature_ - dew_point_;
    condensation_risk_ = spread < 2.0f;

    // Dew countdown
    if (temp_rate_ < 0 && spread >= 2.0f) {
        float hours_to_risk = (spread - 2.0f) / (-temp_rate_);
        dew_countdown_min_ = (int)(hours_to_risk * 60.0f);
    } else if (spread < 2.0f) {
        dew_countdown_min_ = 0;  // Already at risk
    } else {
        dew_countdown_min_ = -1; // No risk (not cooling)
    }

    ESP_LOGI(TAG, "T=%.1f°C (offset=%.1f), RH=%.1f%%, Td=%.1f°C, spread=%.1f°C",
             temperature_, temp_offset_, humidity_, dew_point_, spread);

    // Update rate tracking
    UpdateTempRate();

    return true;
}

float Aht20Device::CalculateDewPoint(float t, float rh) {
    // Alduchov & Eskridge (1996) — accurate at cold temperatures
    if (rh <= 0) rh = 0.01f;
    float alpha = (17.625f * t) / (243.04f + t) + logf(rh / 100.0f);
    return (243.04f * alpha) / (17.625f - alpha);
}

void Aht20Device::UpdateTempRate() {
    uint32_t now = (uint32_t)(esp_timer_get_time() / 1000000ULL);  // seconds

    if (prev_temp_time_ > 0) {
        uint32_t dt = now - prev_temp_time_;
        if (dt >= 60) {  // Update rate every minute minimum
            float delta_t = temperature_ - prev_temp_;
            float hours = (float)dt / 3600.0f;
            temp_rate_ = delta_t / hours;  // C/hour
            prev_temp_ = temperature_;
            prev_temp_time_ = now;
        }
    } else {
        // First reading
        prev_temp_ = temperature_;
        prev_temp_time_ = now;
    }
}
