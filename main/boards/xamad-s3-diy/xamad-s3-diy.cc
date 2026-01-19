#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/oled_display.h"
#include "system_reset.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "led/led.h"

#include <esp_log.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <driver/i2c_master.h>
#include <driver/gpio.h>

#define TAG "XamadS3DiyBoard"

/*
 * XAMAD ESP32-S3 DIY Board
 * ========================
 * Custom board with:
 * - OLED 0.96" SSD1306 128x64 display (I2C)
 * - INMP441 I2S microphone
 * - MAX98357A I2S amplifier
 *
 * Pinout:
 * - Display: SDA=11, SCL=12
 * - Mic:     WS=15, SCK=16, DATA=14
 * - Speaker: BCLK=5, LRC=6, DATA=18, SD=17
 * - Boot:    GPIO0
 */

class XamadS3DiyBoard : public WifiBoard {
private:
    Button boot_button_;
    i2c_master_bus_handle_t display_i2c_bus_ = nullptr;
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    Display* display_ = nullptr;

    void InitializeAmplifier() {
        ESP_LOGI(TAG, "Initializing MAX98357A amplifier on GPIO %d...", AUDIO_CODEC_PA_PIN);
        // Configure MAX98357A SD (shutdown) pin
        gpio_config_t io_conf = {};
        io_conf.pin_bit_mask = BIT64(AUDIO_CODEC_PA_PIN);
        io_conf.mode = GPIO_MODE_OUTPUT;
        io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
        io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
        io_conf.intr_type = GPIO_INTR_DISABLE;
        esp_err_t ret = gpio_config(&io_conf);
        ESP_LOGI(TAG, "GPIO config result: %s", esp_err_to_name(ret));

        // Enable amplifier (HIGH = enabled for MAX98357A SD pin)
        ret = gpio_set_level(AUDIO_CODEC_PA_PIN, 1);
        ESP_LOGI(TAG, "GPIO set level result: %s", esp_err_to_name(ret));

        // Verify GPIO state
        int level = gpio_get_level(AUDIO_CODEC_PA_PIN);
        ESP_LOGI(TAG, "MAX98357A SD pin (GPIO %d) = %d (should be 1)", AUDIO_CODEC_PA_PIN, level);

        // Small delay for amplifier to stabilize
        vTaskDelay(pdMS_TO_TICKS(100));
        ESP_LOGI(TAG, "Amplifier enabled and ready");
    }

    void InitializeDisplayI2c() {
        ESP_LOGI(TAG, "Initializing I2C bus for OLED display");
        i2c_master_bus_config_t i2c_bus_cfg = {
            .i2c_port = I2C_NUM_0,
            .sda_io_num = DISPLAY_I2C_SDA_PIN,
            .scl_io_num = DISPLAY_I2C_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = {
                .enable_internal_pullup = 1,
            },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&i2c_bus_cfg, &display_i2c_bus_));
        ESP_LOGI(TAG, "I2C bus initialized: SDA=%d, SCL=%d", DISPLAY_I2C_SDA_PIN, DISPLAY_I2C_SCL_PIN);
    }

    void InitializeOledDisplay() {
        ESP_LOGI(TAG, "Initializing SSD1306 128x64 OLED display");

        esp_lcd_panel_io_i2c_config_t io_config = {
            .dev_addr = DISPLAY_I2C_ADDR,
            .on_color_trans_done = nullptr,
            .user_ctx = nullptr,
            .control_phase_bytes = 1,
            .dc_bit_offset = 6,
            .lcd_cmd_bits = 8,
            .lcd_param_bits = 8,
            .flags = {
                .dc_low_on_data = 0,
                .disable_control_phase = 0,
            },
            .scl_speed_hz = 400 * 1000,
        };

        ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c_v2(display_i2c_bus_, &io_config, &panel_io_));

        ESP_LOGI(TAG, "Installing SSD1306 driver");
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = -1;
        panel_config.bits_per_pixel = 1;

        esp_lcd_panel_ssd1306_config_t ssd1306_config = {
            .height = static_cast<uint8_t>(DISPLAY_HEIGHT),
        };
        panel_config.vendor_config = &ssd1306_config;

        ESP_ERROR_CHECK(esp_lcd_new_panel_ssd1306(panel_io_, &panel_config, &panel_));
        ESP_LOGI(TAG, "SSD1306 driver installed");

        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        if (esp_lcd_panel_init(panel_) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to initialize display");
            display_ = new NoDisplay();
            return;
        }

        ESP_LOGI(TAG, "Turning display on");
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

        display_ = new OledDisplay(panel_io_, panel_, DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
        ESP_LOGI(TAG, "OLED Display initialized: %dx%d", DISPLAY_WIDTH, DISPLAY_HEIGHT);
    }

    void InitializeButtons() {
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });
        ESP_LOGI(TAG, "Boot button configured on GPIO %d", BOOT_BUTTON_GPIO);
    }

public:
    XamadS3DiyBoard() : boot_button_(BOOT_BUTTON_GPIO) {
        ESP_LOGI(TAG, "Initializing XAMAD ESP32-S3 DIY Board (OLED version)");
        InitializeDisplayI2c();
        InitializeOledDisplay();
        InitializeButtons();
        ESP_LOGI(TAG, "Board initialization complete!");
    }

    virtual Led* GetLed() override {
        static NoLed led;
        return &led;
    }

    virtual AudioCodec* GetAudioCodec() override {
        // 10-param constructor: SPK=LEFT, MIC=RIGHT
        // Order: sample_rates, spk_bclk, spk_ws, spk_dout, SPK_SLOT, mic_sck, mic_ws, mic_din, MIC_SLOT
        static NoAudioCodecSimplex audio_codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK,
            AUDIO_I2S_SPK_GPIO_LRCK,
            AUDIO_I2S_SPK_GPIO_DOUT,
            I2S_STD_SLOT_LEFT,        // SPK slot (MAX98357A = LEFT)
            AUDIO_I2S_MIC_GPIO_SCK,
            AUDIO_I2S_MIC_GPIO_WS,
            AUDIO_I2S_MIC_GPIO_DIN,
            I2S_STD_SLOT_LEFT         // MIC slot - LEFT (INMP441 L/R=GND)
        );

        // Initialize amplifier AFTER I2S is configured
        static bool amp_initialized = false;
        if (!amp_initialized) {
            ESP_LOGI(TAG, "Enabling MAX98357A amplifier AFTER I2S init...");

            // Configure PA pin as output with push-pull
            gpio_config_t io_conf = {};
            io_conf.pin_bit_mask = BIT64(AUDIO_CODEC_PA_PIN);
            io_conf.mode = GPIO_MODE_OUTPUT;
            io_conf.pull_up_en = GPIO_PULLUP_ENABLE;  // Add pull-up
            io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
            io_conf.intr_type = GPIO_INTR_DISABLE;
            gpio_config(&io_conf);

            // Set HIGH to enable amplifier
            gpio_set_level(AUDIO_CODEC_PA_PIN, 1);
            vTaskDelay(pdMS_TO_TICKS(50));

            // Set again to be sure
            gpio_set_level(AUDIO_CODEC_PA_PIN, 1);

            ESP_LOGI(TAG, "MAX98357A amplifier enabled on GPIO %d", AUDIO_CODEC_PA_PIN);
            ESP_LOGI(TAG, "Audio codec configured: SPK=LEFT, MIC=LEFT, out=%dHz, in=%dHz",
                     AUDIO_OUTPUT_SAMPLE_RATE, AUDIO_INPUT_SAMPLE_RATE);
            amp_initialized = true;
        }

        return &audio_codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }
};

DECLARE_BOARD(XamadS3DiyBoard);
