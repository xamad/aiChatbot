#include "simple_es8311_audio_codec.h"

#include <esp_log.h>
#include <cstring>
#include <cmath>
#include <vector>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#define TAG "SimpleEs8311"

#define ES8311_ADDR 0x18

// ES8311 Register addresses
#define ES8311_REG00_RESET      0x00
#define ES8311_REG01_CLK_MGR    0x01
#define ES8311_REG02_CLK_MGR    0x02
#define ES8311_REG03_CLK_MGR    0x03
#define ES8311_REG04_CLK_MGR    0x04
#define ES8311_REG05_CLK_MGR    0x05
#define ES8311_REG09_SDP_IN     0x09
#define ES8311_REG0A_SDP_OUT    0x0A
#define ES8311_REG0B_SYS       0x0B
#define ES8311_REG0C_SYS       0x0C
#define ES8311_REG0D_SYS       0x0D
#define ES8311_REG0E_SYS       0x0E
#define ES8311_REG10_SYS       0x10
#define ES8311_REG11_SYS       0x11
#define ES8311_REG12_DAC       0x12
#define ES8311_REG13_DAC       0x13
#define ES8311_REG14_DAC       0x14
#define ES8311_REG15_DAC       0x15
#define ES8311_REG16_ADC       0x16
#define ES8311_REG17_ADC       0x17
#define ES8311_REG1B_ADC       0x1B
#define ES8311_REG1C_ADC       0x1C
#define ES8311_REG31_DAC       0x31
#define ES8311_REG32_DAC_VOL   0x32
#define ES8311_REG37_DAC       0x37
#define ES8311_REG44_GPIO      0x44
#define ES8311_REG45_GPIO      0x45
#define ES8311_REGFD_CHIPID    0xFD

SimpleEs8311AudioCodec::SimpleEs8311AudioCodec(
    i2c_master_bus_handle_t i2c_bus,
    int input_sample_rate,
    int output_sample_rate,
    gpio_num_t mclk,
    gpio_num_t bclk,
    gpio_num_t ws,
    gpio_num_t dout,
    gpio_num_t din,
    gpio_num_t pa_pin)
{
    duplex_ = true;
    input_channels_ = 1;
    input_sample_rate_ = input_sample_rate;
    output_sample_rate_ = output_sample_rate;
    pa_pin_ = pa_pin;
    i2c_bus_ = i2c_bus;
    i2c_dev_ = nullptr;
    codec_initialized_ = false;

    ESP_LOGI(TAG, "Creating SimpleEs8311AudioCodec");
    ESP_LOGI(TAG, "  MCLK=%d, BCLK=%d, WS=%d, DOUT=%d, DIN=%d, PA=%d",
             mclk, bclk, ws, dout, din, pa_pin);

    // Step 1: Enable PA (amplifier) first - FM8002E is active LOW
    gpio_config_t pa_conf = {};
    pa_conf.pin_bit_mask = BIT64(pa_pin_);
    pa_conf.mode = GPIO_MODE_OUTPUT;
    gpio_config(&pa_conf);
    gpio_set_level(pa_pin_, 0);  // LOW = enabled
    ESP_LOGI(TAG, "PA enabled (GPIO%d = LOW)", pa_pin_);

    // Step 2: Create I2S channels with MCLK
    // Use full-duplex with shared clocks - TX and RX MUST have same clock config
    // Increase DMA buffers for more reliable reads
    i2s_chan_config_t chan_cfg = {
        .id = I2S_NUM_0,
        .role = I2S_ROLE_MASTER,
        .dma_desc_num = 8,
        .dma_frame_num = 480,  // Larger frames for stereo
        .auto_clear_after_cb = true,
        .auto_clear_before_cb = false,
        .intr_priority = 0,
    };
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &tx_handle_, &rx_handle_));

    // Unified I2S config for full-duplex operation with ES8311
    // ES8311 uses standard 16-bit stereo I2S Philips format
    i2s_std_config_t std_cfg = {
        .clk_cfg = {
            .sample_rate_hz = (uint32_t)output_sample_rate_,
            .clk_src = I2S_CLK_SRC_DEFAULT,
            .mclk_multiple = I2S_MCLK_MULTIPLE_384,
        },
        .slot_cfg = {
            .data_bit_width = I2S_DATA_BIT_WIDTH_16BIT,
            .slot_bit_width = I2S_SLOT_BIT_WIDTH_AUTO,
            .slot_mode = I2S_SLOT_MODE_STEREO,
            .slot_mask = I2S_STD_SLOT_BOTH,
            .ws_width = I2S_DATA_BIT_WIDTH_16BIT,
            .ws_pol = false,
            .bit_shift = true,
            .left_align = true,
            .big_endian = false,
            .bit_order_lsb = false,
        },
        .gpio_cfg = {
            .mclk = mclk,
            .bclk = bclk,
            .ws = ws,
            .dout = dout,
            .din = din,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv = false,
            },
        },
    };

    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_handle_, &std_cfg));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_handle_, &std_cfg));
    ESP_LOGI(TAG, "I2S full-duplex configured: %d Hz, 16-bit STEREO (ES8311 standard)", output_sample_rate_);

    // Step 3: Enable I2S channels - this starts MCLK!
    ESP_ERROR_CHECK(i2s_channel_enable(tx_handle_));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_handle_));
    ESP_LOGI(TAG, "I2S channels enabled, MCLK now running on GPIO%d", mclk);

    // Step 4: Wait for MCLK to stabilize
    vTaskDelay(pdMS_TO_TICKS(100));

    // Step 5: Add ES8311 I2C device
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = ES8311_ADDR,
        .scl_speed_hz = 100000,  // 100kHz - slower for reliability
    };
    esp_err_t ret = i2c_master_bus_add_device(i2c_bus_, &dev_cfg, &i2c_dev_);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to add ES8311 I2C device: %s", esp_err_to_name(ret));
        return;
    }

    // Step 6: Verify ES8311 is present
    uint8_t chip_id = ReadReg(ES8311_REGFD_CHIPID);
    ESP_LOGI(TAG, "ES8311 Chip ID: 0x%02X (expected 0x83)", chip_id);
    if (chip_id != 0x83) {
        ESP_LOGE(TAG, "ES8311 not found or wrong chip ID!");
        // Continue anyway - might work
    }

    // Step 7: Initialize ES8311
    if (InitializeCodec()) {
        codec_initialized_ = true;
        ESP_LOGI(TAG, "ES8311 initialized successfully!");
    } else {
        ESP_LOGE(TAG, "ES8311 initialization failed!");
    }
}

SimpleEs8311AudioCodec::~SimpleEs8311AudioCodec() {
    if (tx_handle_) {
        i2s_channel_disable(tx_handle_);
        i2s_del_channel(tx_handle_);
    }
    if (rx_handle_) {
        i2s_channel_disable(rx_handle_);
        i2s_del_channel(rx_handle_);
    }
    if (i2c_dev_) {
        i2c_master_bus_rm_device(i2c_dev_);
    }
}

bool SimpleEs8311AudioCodec::WriteReg(uint8_t reg, uint8_t val) {
    uint8_t data[2] = {reg, val};
    esp_err_t ret = i2c_master_transmit(i2c_dev_, data, 2, 50);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C write failed: reg=0x%02X val=0x%02X err=%s",
                 reg, val, esp_err_to_name(ret));
        return false;
    }
    vTaskDelay(pdMS_TO_TICKS(5));  // Small delay between writes
    return true;
}

uint8_t SimpleEs8311AudioCodec::ReadReg(uint8_t reg) {
    uint8_t val = 0xFF;
    esp_err_t ret = i2c_master_transmit_receive(i2c_dev_, &reg, 1, &val, 1, 50);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C read failed: reg=0x%02X err=%s", reg, esp_err_to_name(ret));
        return 0xFF;
    }
    return val;
}

bool SimpleEs8311AudioCodec::InitializeCodec() {
    ESP_LOGI(TAG, "Configuring ES8311 (simplified working version)...");

    // === NO software reset (official ESP-ADF driver doesn't do 0x1F/0x00) ===
    // The 0x1F reset wipes state and is only used in suspend/shutdown.
    // Go straight to GPIO init and then slave mode setup.

    // === GPIO for I2C noise immunity (write twice per ESP-ADF) ===
    if (!WriteReg(ES8311_REG44_GPIO, 0x08)) return false;
    if (!WriteReg(ES8311_REG44_GPIO, 0x08)) return false;

    // === Clock manager setup ===
    if (!WriteReg(ES8311_REG01_CLK_MGR, 0x30)) return false;
    if (!WriteReg(ES8311_REG02_CLK_MGR, 0x00)) return false;
    if (!WriteReg(ES8311_REG03_CLK_MGR, 0x10)) return false;
    if (!WriteReg(ES8311_REG04_CLK_MGR, 0x10)) return false;
    if (!WriteReg(ES8311_REG05_CLK_MGR, 0x00)) return false;

    // === System control ===
    if (!WriteReg(ES8311_REG0B_SYS, 0x00)) return false;
    if (!WriteReg(ES8311_REG0C_SYS, 0x00)) return false;
    if (!WriteReg(ES8311_REG10_SYS, 0x1F)) return false;
    if (!WriteReg(ES8311_REG11_SYS, 0x7F)) return false;

    // === Reset and mode - ES8311 as SLAVE ===
    if (!WriteReg(ES8311_REG00_RESET, 0x80)) return false;
    vTaskDelay(pdMS_TO_TICKS(50));

    // === Enable all clocks ===
    if (!WriteReg(ES8311_REG01_CLK_MGR, 0x3F)) return false;

    // === Additional config ===
    if (!WriteReg(ES8311_REG13_DAC, 0x10)) return false;
    if (!WriteReg(ES8311_REG1B_ADC, 0x0A)) return false;
    if (!WriteReg(ES8311_REG1C_ADC, 0x6A)) return false;

    vTaskDelay(pdMS_TO_TICKS(50));

    // === SDP interfaces ===
    // ES8311 SDP register format:
    // Bits[1:0] = Format: 00=I2S, 01=LJ, 10=RJ(16bit), 11=DSP/PCM
    // Bits[4:2] = Word Length: 000=24bit, 001=20bit, 010=18bit, 011=16bit, 100=32bit
    // For 16-bit I2S: (011 << 2) | 00 = 0x0C
    if (!WriteReg(ES8311_REG09_SDP_IN, 0x0C)) return false;   // 16-bit I2S for DAC input
    if (!WriteReg(ES8311_REG0A_SDP_OUT, 0x0C)) return false;  // 16-bit I2S for ADC output

    // === ADC configuration ===
    // REG14: ADC input selection + PGA gain
    // Bits 6:   0=analog mic, 1=digital mic
    // Bits 5:4: LINSEL: 00=none, 01=MIC1P-MIC1N, 10=MIC2P-MIC2N
    // Bits 3:0: PGA gain (0-15, each step ~3dB)
    // 0x1A = analog mic (0), MIC1P-MIC1N (01), PGA gain 10 = 30dB
    if (!WriteReg(0x14, 0x1A)) return false;
    if (!WriteReg(0x15, 0x40)) return false;  // ADC ramp enable
    ESP_LOGI(TAG, "Analog MIC1P-MIC1N enabled (REG14=0x1A), PGA=30dB");

    // === MIC GAIN - REG16 ===
    // Values: 0=0dB, 1=6dB, 2=12dB, 3=18dB, 4=24dB, 5=30dB, 6=36dB, 7=42dB
    // Use 30dB (5) — 42dB is too aggressive for MEMS mic and may cause clipping
    if (!WriteReg(ES8311_REG16_ADC, 0x05)) return false;  // +30dB gain
    ESP_LOGI(TAG, "REG16 set to 0x05 (+30dB MIC gain)");

    // === ADC volume ===
    if (!WriteReg(ES8311_REG17_ADC, 0xBF)) return false;

    // === System registers ===
    if (!WriteReg(ES8311_REG0E_SYS, 0x02)) return false;
    if (!WriteReg(ES8311_REG12_DAC, 0x00)) return false;

    // === Power control - CRITICAL ===
    // REG0D bits: 7=PDN_ANA, 6=PDN_IBIASGEN, 5=PDN_ADCBIASGEN,
    //             4=PDN_ADCVREFGEN, 3=PDN_DACVREFGEN, 2=PDN_VREF, 1:0=VMIDSEL
    // 0x01 = all power blocks ENABLED (bits 7:2 = 0), VMID = startup mode (01)
    // OLD 0x33 was WRONG: ADC bias (bit5) and ADC Vref (bit4) were powered down!
    if (!WriteReg(ES8311_REG0D_SYS, 0x01)) return false;
    ESP_LOGI(TAG, "REG0D set to 0x01 (all power enabled, VMID startup)");

    // === DAC ramp ===
    if (!WriteReg(ES8311_REG37_DAC, 0x08)) return false;

    // === GPIO final config ===
    if (!WriteReg(ES8311_REG45_GPIO, 0x00)) return false;
    if (!WriteReg(ES8311_REG44_GPIO, 0x58)) return false;

    // === DAC unmute and volume ===
    if (!WriteReg(ES8311_REG31_DAC, 0x00)) return false;
    if (!WriteReg(ES8311_REG32_DAC_VOL, 0xBF)) return false;

    // === Verification ===
    ESP_LOGW(TAG, "=== ES8311 REGISTER CHECK ===");
    ESP_LOGW(TAG, "REG0D=0x%02X (want 0x01 — all power ON)", ReadReg(ES8311_REG0D_SYS));
    ESP_LOGW(TAG, "REG14=0x%02X (want 0x1A — MIC1 diff + PGA 30dB)", ReadReg(0x14));
    ESP_LOGW(TAG, "REG16=0x%02X (want 0x05 — +30dB mic gain)", ReadReg(ES8311_REG16_ADC));
    ESP_LOGW(TAG, "REG17=0x%02X (want 0xBF — ADC volume)", ReadReg(ES8311_REG17_ADC));
    ESP_LOGW(TAG, "REG09=0x%02X (want 0x0C — 16-bit I2S DAC)", ReadReg(ES8311_REG09_SDP_IN));
    ESP_LOGW(TAG, "REG0A=0x%02X (want 0x0C — 16-bit I2S ADC)", ReadReg(ES8311_REG0A_SDP_OUT));
    ESP_LOGW(TAG, "REG0E=0x%02X (want 0x02 — ADC PGA + modulator ON)", ReadReg(ES8311_REG0E_SYS));
    ESP_LOGW(TAG, "=== END CHECK ===");

    return true;
}

void SimpleEs8311AudioCodec::SetOutputVolume(int volume) {
    output_volume_ = volume;
    if (codec_initialized_) {
        // Volume range: 0-100 -> 0x00-0xBF (0dB at 0xBF, attenuated below)
        uint8_t vol_reg = (volume * 0xBF) / 100;
        WriteReg(ES8311_REG32_DAC_VOL, vol_reg);
        ESP_LOGI(TAG, "Set volume to %d (reg=0x%02X)", volume, vol_reg);
    }
}

void SimpleEs8311AudioCodec::EnableInput(bool enable) {
    if (enable == input_enabled_) return;
    input_enabled_ = enable;
    ESP_LOGI(TAG, "Input %s", enable ? "enabled" : "disabled");
}

void SimpleEs8311AudioCodec::EnableOutput(bool enable) {
    if (enable == output_enabled_) return;
    output_enabled_ = enable;

    if (codec_initialized_) {
        // Mute/unmute DAC
        WriteReg(ES8311_REG31_DAC, enable ? 0x00 : 0x40);
    }

    // Control PA
    gpio_set_level(pa_pin_, enable ? 0 : 1);  // LOW = enabled
    ESP_LOGI(TAG, "Output %s, PA %s", enable ? "enabled" : "disabled",
             enable ? "ON" : "OFF");
}

int SimpleEs8311AudioCodec::Read(int16_t* dest, int samples) {
    static int log_counter = 0;

    if (!input_enabled_ || !rx_handle_) {
        memset(dest, 0, samples * sizeof(int16_t));
        vTaskDelay(1);
        return samples;
    }

    // IMPORTANT: In full-duplex mode with shared BCLK, the TX channel must be
    // actively writing to keep the clock running. If TX is idle, BCLK stops
    // and RX times out. Write silence to TX to keep clock alive.
    if (tx_handle_) {
        std::vector<int16_t> silence(samples * 2, 0);  // stereo silence
        size_t bytes_written = 0;
        i2s_channel_write(tx_handle_, silence.data(), silence.size() * sizeof(int16_t),
                          &bytes_written, 0);  // non-blocking write
    }

    // Read 16-bit stereo data from ES8311 ADC
    // ES8311 is mono codec - audio is on LEFT channel only
    std::vector<int16_t> stereo_buf(samples * 2);
    size_t bytes_read = 0;
    esp_err_t ret = i2s_channel_read(rx_handle_, stereo_buf.data(), samples * 2 * sizeof(int16_t),
                                      &bytes_read, pdMS_TO_TICKS(200));

    if (ret != ESP_OK || bytes_read == 0) {
        if (log_counter++ % 100 == 0) {
            ESP_LOGW(TAG, "I2S read failed: ret=%d, bytes=%d", ret, bytes_read);
        }
        memset(dest, 0, samples * sizeof(int16_t));
        return samples;
    }

    int stereo_samples = bytes_read / sizeof(int16_t);
    int mono_samples = stereo_samples / 2;

    // Extract LEFT channel (ES8311 mono ADC output is on left)
    // Apply 8x software gain to amplify low-level mic signal
    const int GAIN = 8;

    for (int i = 0; i < mono_samples && i < samples; i++) {
        int32_t value = (int32_t)stereo_buf[i * 2] * GAIN;  // LEFT channel
        if (value > INT16_MAX) {
            dest[i] = INT16_MAX;
        } else if (value < -INT16_MAX) {
            dest[i] = -INT16_MAX;
        } else {
            dest[i] = (int16_t)value;
        }
    }
    // Zero-fill remaining
    for (int i = mono_samples; i < samples; i++) {
        dest[i] = 0;
    }

    // Log audio level every 1 second
    if (log_counter++ % 100 == 0) {
        int16_t left_min = 32767, left_max = -32768;
        int16_t right_min = 32767, right_max = -32768;
        int16_t out_min = 32767, out_max = -32768;
        for (int i = 0; i < mono_samples && i < 50; i++) {
            int16_t left = stereo_buf[i * 2];
            int16_t right = stereo_buf[i * 2 + 1];
            if (left < left_min) left_min = left;
            if (left > left_max) left_max = left;
            if (right < right_min) right_min = right;
            if (right > right_max) right_max = right;
            if (dest[i] < out_min) out_min = dest[i];
            if (dest[i] > out_max) out_max = dest[i];
        }
        ESP_LOGW(TAG, "MIC: L=[%d,%d] R=[%d,%d] out=[%d,%d] gain=%dx",
                 left_min, left_max, right_min, right_max, out_min, out_max, GAIN);
    }

    return samples;
}

int SimpleEs8311AudioCodec::Write(const int16_t* data, int samples) {
    if (!output_enabled_ || !tx_handle_) {
        return samples;
    }

    // Convert 16-bit mono input to 16-bit stereo output for ES8311 DAC
    int write_samples = samples;
    if (write_samples > 1024) write_samples = 1024;

    // Allocate stereo buffer (duplicate mono to both channels)
    std::vector<int16_t> stereo_buf(write_samples * 2);

    for (int i = 0; i < write_samples; i++) {
        stereo_buf[i * 2] = data[i];      // LEFT channel
        stereo_buf[i * 2 + 1] = data[i];  // RIGHT channel (same as left)
    }

    size_t bytes_written = 0;
    i2s_channel_write(tx_handle_, stereo_buf.data(), write_samples * 2 * sizeof(int16_t),
                      &bytes_written, pdMS_TO_TICKS(100));

    return samples;
}
