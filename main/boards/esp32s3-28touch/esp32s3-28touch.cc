#include "wifi_board.h"
#include "codecs/simple_es8311_audio_codec.h"
#include "display/lcd_display.h"
#include "system_reset.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "led/single_led.h"

#include <esp_log.h>
#include <esp_lcd_ili9341.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_touch_ft5x06.h>
#include <esp_lcd_panel_io_additions.h>
#include <esp_lvgl_port.h>
#include <driver/spi_master.h>
#include <driver/i2c_master.h>
#include <driver/gpio.h>
#include <driver/ledc.h>

#define TAG "ESP32S3_28Touch"

/*
 * ESP32-S3 2.8" Touch Display Board
 * - ILI9341 2.8" TFT 240x320 (SPI)
 * - FT6336G Capacitive Touch (I2C)
 * - I2S Audio: Speaker + Microphone
 * - RGB LED
 */

class ESP32S3_28TouchBoard : public WifiBoard {
private:
    Button boot_button_;
    i2c_master_bus_handle_t i2c_bus_ = nullptr;  // Shared I2C for touch and ES8311
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    esp_lcd_panel_io_handle_t touch_io_ = nullptr;
    esp_lcd_touch_handle_t touch_handle_ = nullptr;
    lv_indev_t* touch_indev_ = nullptr;
    Display* display_ = nullptr;

    void InitializeMclk() {
        // NOTE: MCLK and PA are now handled by SimpleEs8311AudioCodec
        // This function is kept for potential future use but does nothing
        ESP_LOGI(TAG, "Audio (MCLK/PA) will be initialized by SimpleEs8311AudioCodec");
    }

    void InitializeBacklight() {
        ESP_LOGI(TAG, "Initializing backlight on GPIO %d", DISPLAY_BL_PIN);

        ledc_timer_config_t timer_conf = {
            .speed_mode = LEDC_LOW_SPEED_MODE,
            .duty_resolution = LEDC_TIMER_8_BIT,
            .timer_num = LEDC_TIMER_0,
            .freq_hz = 5000,
            .clk_cfg = LEDC_AUTO_CLK,
        };
        ledc_timer_config(&timer_conf);

        ledc_channel_config_t channel_conf = {
            .gpio_num = DISPLAY_BL_PIN,
            .speed_mode = LEDC_LOW_SPEED_MODE,
            .channel = LEDC_CHANNEL_0,
            .intr_type = LEDC_INTR_DISABLE,
            .timer_sel = LEDC_TIMER_0,
            .duty = 200,
            .hpoint = 0,
        };
        ledc_channel_config(&channel_conf);
    }

    void InitializeSpi() {
        ESP_LOGI(TAG, "Initializing SPI bus for display");

        spi_bus_config_t bus_cfg = {
            .mosi_io_num = DISPLAY_SPI_MOSI_PIN,
            .miso_io_num = DISPLAY_SPI_MISO_PIN,
            .sclk_io_num = DISPLAY_SPI_SCLK_PIN,
            .quadwp_io_num = -1,
            .quadhd_io_num = -1,
            .max_transfer_sz = DISPLAY_WIDTH * DISPLAY_HEIGHT * 2,
        };
        ESP_ERROR_CHECK(spi_bus_initialize(DISPLAY_SPI_HOST, &bus_cfg, SPI_DMA_CH_AUTO));
    }

    void ScanI2cBus() {
        ESP_LOGI(TAG, "======================================");
        ESP_LOGI(TAG, "Scanning I2C bus for devices...");
        ESP_LOGI(TAG, "SDA=GPIO%d, SCL=GPIO%d", TOUCH_I2C_SDA_PIN, TOUCH_I2C_SCL_PIN);
        ESP_LOGI(TAG, "======================================");

        uint8_t found_count = 0;
        for (uint8_t addr = 0x08; addr < 0x78; addr++) {
            i2c_master_dev_handle_t dev_handle;
            i2c_device_config_t dev_cfg = {
                .dev_addr_length = I2C_ADDR_BIT_LEN_7,
                .device_address = addr,
                .scl_speed_hz = 100000,
            };

            esp_err_t ret = i2c_master_bus_add_device(i2c_bus_, &dev_cfg, &dev_handle);
            if (ret != ESP_OK) {
                continue;
            }

            // Try write probe (more compatible than read for many devices)
            uint8_t reg = 0x00;
            ret = i2c_master_transmit(dev_handle, &reg, 1, 50);

            if (ret == ESP_OK) {
                ESP_LOGW(TAG, ">>> FOUND: I2C device at 0x%02X <<<", addr);
                found_count++;

                // Identify common devices
                if (addr == 0x18) {
                    ESP_LOGW(TAG, "    -> ES8311 audio codec (AD0=LOW)");
                } else if (addr == 0x19) {
                    ESP_LOGW(TAG, "    -> ES8311 audio codec (AD0=HIGH)");
                } else if (addr == 0x38) {
                    ESP_LOGW(TAG, "    -> FT6336G touch controller");
                } else if (addr >= 0x10 && addr <= 0x13) {
                    ESP_LOGW(TAG, "    -> Possible audio codec");
                } else if (addr >= 0x48 && addr <= 0x4B) {
                    ESP_LOGW(TAG, "    -> Possible ADC/DAC chip");
                }
            }

            i2c_master_bus_rm_device(dev_handle);
        }

        ESP_LOGI(TAG, "======================================");
        ESP_LOGW(TAG, "I2C SCAN COMPLETE: Found %d device(s)", found_count);
        ESP_LOGI(TAG, "======================================");

        if (found_count == 1) {
            ESP_LOGE(TAG, "WARNING: Only touch found! ES8311 NOT detected!");
            ESP_LOGE(TAG, "Audio will NOT work without ES8311 codec!");
        }
    }

    void InitializeI2c() {
        ESP_LOGI(TAG, "Initializing I2C bus for touch and ES8311 codec");

        // Reset touch controller (before I2C init)
        gpio_config_t io_conf = {};
        io_conf.pin_bit_mask = BIT64(TOUCH_RST_PIN);
        io_conf.mode = GPIO_MODE_OUTPUT;
        gpio_config(&io_conf);
        gpio_set_level(TOUCH_RST_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(10));
        gpio_set_level(TOUCH_RST_PIN, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        ESP_LOGI(TAG, "Touch controller reset complete");

        i2c_master_bus_config_t i2c_bus_cfg = {
            .i2c_port = I2C_NUM_0,
            .sda_io_num = TOUCH_I2C_SDA_PIN,
            .scl_io_num = TOUCH_I2C_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = {
                .enable_internal_pullup = 1,
            },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&i2c_bus_cfg, &i2c_bus_));

        // Scan I2C bus to see what's connected
        ScanI2cBus();
    }

    void InitializeDisplay() {
        ESP_LOGI(TAG, "Initializing ILI9341 display");

        esp_lcd_panel_io_spi_config_t io_config = {
            .cs_gpio_num = DISPLAY_SPI_CS_PIN,
            .dc_gpio_num = DISPLAY_DC_PIN,
            .spi_mode = 0,
            .pclk_hz = DISPLAY_SPI_SPEED_HZ,
            .trans_queue_depth = 10,
            .on_color_trans_done = nullptr,
            .user_ctx = nullptr,
            .lcd_cmd_bits = 8,
            .lcd_param_bits = 8,
            .flags = {
                .dc_low_on_data = 0,
                .octal_mode = 0,
                .sio_mode = 0,
                .lsb_first = 0,
                .cs_high_active = 0,
            },
        };
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(DISPLAY_SPI_HOST, &io_config, &panel_io_));

        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = DISPLAY_RST_PIN;
        panel_config.rgb_ele_order = LCD_RGB_ELEMENT_ORDER_BGR;
        panel_config.bits_per_pixel = 16;

        ESP_ERROR_CHECK(esp_lcd_new_panel_ili9341(panel_io_, &panel_config, &panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_init(panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

        display_ = new SpiLcdDisplay(panel_io_, panel_,
                                      DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                      0, 0,  // offset x, y
                                      DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y,
                                      DISPLAY_SWAP_XY);
    }

    void InitializeTouch() {
        ESP_LOGI(TAG, "Initializing FT6336G touch panel (FT5x06 compatible)");

        // Create I2C panel IO for touch using v2 API with bus handle
        esp_lcd_panel_io_i2c_config_t touch_io_config = {
            .dev_addr = TOUCH_I2C_ADDR,
            .control_phase_bytes = 1,
            .dc_bit_offset = 0,
            .lcd_cmd_bits = 8,
            .lcd_param_bits = 8,
            .flags = {
                .disable_control_phase = 1,
            },
            .scl_speed_hz = 400000,
        };

        ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c_v2(i2c_bus_, &touch_io_config, &touch_io_));

        // Configure the touch controller
        esp_lcd_touch_config_t touch_config = {
            .x_max = DISPLAY_WIDTH,
            .y_max = DISPLAY_HEIGHT,
            .rst_gpio_num = GPIO_NUM_NC,  // Already reset in InitializeI2c
            .int_gpio_num = TOUCH_INT_PIN,
            .levels = {
                .reset = 0,
                .interrupt = 0,
            },
            .flags = {
                .swap_xy = DISPLAY_SWAP_XY ? 1 : 0,
                .mirror_x = DISPLAY_MIRROR_X ? 1 : 0,
                .mirror_y = DISPLAY_MIRROR_Y ? 1 : 0,
            },
            .process_coordinates = nullptr,
            .interrupt_callback = nullptr,
            .user_data = nullptr,
        };

        ESP_ERROR_CHECK(esp_lcd_touch_new_i2c_ft5x06(touch_io_, &touch_config, &touch_handle_));
        ESP_LOGI(TAG, "Touch panel initialized successfully");

        // Add touch to LVGL
        lvgl_port_touch_cfg_t touch_cfg = {
            .disp = nullptr,  // Will use default display
            .handle = touch_handle_,
        };
        touch_indev_ = lvgl_port_add_touch(&touch_cfg);
        if (touch_indev_ == nullptr) {
            ESP_LOGE(TAG, "Failed to add touch input device to LVGL");
            return;
        }
        ESP_LOGI(TAG, "Touch input device added to LVGL");

        // Register touch callback to toggle chat state on touch
        lv_indev_add_event_cb(touch_indev_, [](lv_event_t* e) {
            if (lv_event_get_code(e) == LV_EVENT_CLICKED) {
                ESP_LOGI("Touch", "Screen touched - toggling chat state");
                auto& app = Application::GetInstance();
                if (app.GetDeviceState() == kDeviceStateStarting) {
                    // Can't enter WiFi config mode from touch
                    return;
                }
                app.ToggleChatState();
            }
        }, LV_EVENT_CLICKED, nullptr);
    }

    void InitializeButtons() {
        ESP_LOGI(TAG, "Initializing boot button on GPIO%d", BOOT_BUTTON_GPIO);
        boot_button_.OnClick([this]() {
            ESP_LOGW(TAG, ">>> BOOT BUTTON CLICKED! <<<");
            auto& app = Application::GetInstance();
            ESP_LOGI(TAG, "Device state: %d", (int)app.GetDeviceState());
            if (app.GetDeviceState() == kDeviceStateStarting) {
                ESP_LOGI(TAG, "Entering WiFi config mode");
                EnterWifiConfigMode();
                return;
            }
            ESP_LOGI(TAG, "Toggling chat state");
            app.ToggleChatState();
        });
        ESP_LOGI(TAG, "Boot button initialized");
    }

public:
    ESP32S3_28TouchBoard() : boot_button_(BOOT_BUTTON_GPIO) {
        ESP_LOGI(TAG, "===========================================");
        ESP_LOGI(TAG, "Initializing ESP32-S3 2.8\" Touch Board");
        ESP_LOGI(TAG, "===========================================");

        InitializeMclk();    // Start MCLK FIRST - ES8311 needs it for I2C
        InitializeBacklight();
        InitializeSpi();
        InitializeI2c();
        InitializeDisplay();
        // InitializeTouch();  // TODO: Fix touch crash - disabled for now
        InitializeButtons();
    }

    virtual Led* GetLed() override {
        static SingleLed led(RGB_LED_PIN);
        return &led;
    }

    virtual AudioCodec* GetAudioCodec() override {
        static SimpleEs8311AudioCodec* codec = nullptr;
        if (codec == nullptr) {
            ESP_LOGI(TAG, "Creating SimpleEs8311AudioCodec");
            codec = new SimpleEs8311AudioCodec(
                i2c_bus_,                    // I2C master handle
                AUDIO_INPUT_SAMPLE_RATE,     // 16000
                AUDIO_OUTPUT_SAMPLE_RATE,    // 16000
                AUDIO_I2S_GPIO_MCLK,         // GPIO4 - MCLK
                AUDIO_I2S_GPIO_BCLK,         // GPIO5 - Bit Clock
                AUDIO_I2S_GPIO_WS,           // GPIO7 - Word Select (LRC)
                AUDIO_I2S_GPIO_DOUT,         // GPIO8 - Data to speaker
                AUDIO_I2S_GPIO_DIN,          // GPIO6 - Data from microphone
                AUDIO_CODEC_PA_PIN           // GPIO1 - PA enable (active LOW)
            );
        }
        return codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }
};

DECLARE_BOARD(ESP32S3_28TouchBoard);
