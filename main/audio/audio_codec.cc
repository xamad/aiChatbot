#include "audio_codec.h"
#include "board.h"
#include "settings.h"

#include <esp_log.h>
#include <cstring>
#include <driver/i2s_common.h>

#define TAG "AudioCodec"

AudioCodec::AudioCodec() {
}

AudioCodec::~AudioCodec() {
}

void AudioCodec::OutputData(std::vector<int16_t>& data) {
    static int output_count = 0;
    if (output_count < 5) {
        ESP_LOGI(TAG, "OutputData called: %d samples, output_enabled=%d", (int)data.size(), output_enabled_ ? 1 : 0);
        output_count++;
    }
    Write(data.data(), data.size());
}

bool AudioCodec::InputData(std::vector<int16_t>& data) {
    int samples = Read(data.data(), data.size());
    if (samples > 0) {
        return true;
    }
    return false;
}

void AudioCodec::Start() {
    ESP_LOGI(TAG, "AudioCodec::Start() called");

    Settings settings("audio", false);
    output_volume_ = settings.GetInt("output_volume", output_volume_);
    if (output_volume_ <= 0) {
        ESP_LOGW(TAG, "Output volume value (%d) is too small, setting to default (10)", output_volume_);
        output_volume_ = 10;
    }
    ESP_LOGI(TAG, "Output volume: %d", output_volume_);

    if (tx_handle_ != nullptr) {
        ESP_LOGI(TAG, "Enabling TX I2S channel...");
        esp_err_t ret = i2s_channel_enable(tx_handle_);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Failed to enable TX channel: %s", esp_err_to_name(ret));
        } else {
            ESP_LOGI(TAG, "TX channel enabled OK");
        }
    } else {
        ESP_LOGW(TAG, "TX handle is NULL!");
    }

    if (rx_handle_ != nullptr) {
        ESP_LOGI(TAG, "Enabling RX I2S channel...");
        esp_err_t ret = i2s_channel_enable(rx_handle_);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Failed to enable RX channel: %s", esp_err_to_name(ret));
        } else {
            ESP_LOGI(TAG, "RX channel enabled OK");
        }
    } else {
        ESP_LOGW(TAG, "RX handle is NULL!");
    }

    EnableInput(true);
    EnableOutput(true);
    ESP_LOGI(TAG, "Audio codec started successfully");
}

void AudioCodec::SetOutputVolume(int volume) {
    output_volume_ = volume;
    ESP_LOGI(TAG, "Set output volume to %d", output_volume_);
    
    Settings settings("audio", true);
    settings.SetInt("output_volume", output_volume_);
}

void AudioCodec::SetInputGain(float gain) {
    input_gain_ = gain;
    ESP_LOGI(TAG, "Set input gain to %.1f", input_gain_);
}

void AudioCodec::EnableInput(bool enable) {
    if (enable == input_enabled_) {
        return;
    }
    input_enabled_ = enable;
    ESP_LOGI(TAG, "Set input enable to %s", enable ? "true" : "false");
}

void AudioCodec::EnableOutput(bool enable) {
    if (enable == output_enabled_) {
        return;
    }
    output_enabled_ = enable;
    ESP_LOGI(TAG, "Set output enable to %s", enable ? "true" : "false");
}
