#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/lcd_display.h"
#include "system_reset.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "led/led.h"

#include <esp_log.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <driver/spi_common.h>
#include <driver/gpio.h>

#define TAG "XamadS3DiyBoard"

/*
 * XAMAD ESP32-S3 DIY Board
 * ========================
 * Custom board with:
 * - TFT 1.8" ST7735 128x160 display
 * - INMP441 I2S microphone
 * - MAX98357A I2S amplifier
 *
 * Pinout:
 * - Display: CS=10, DC=8, RST=9, MOSI=11, SCK=12, BL=13
 * - Mic:     WS=15, SCK=16, DATA=14
 * - Speaker: BCLK=5, LRC=6, DATA=18, SD=17
 * - Boot:    GPIO0
 */

class XamadS3DiyBoard : public WifiBoard {
private:
    Button boot_button_;
    LcdDisplay* display_;

    void InitializeAmplifier() {
        // Configure MAX98357A SD (shutdown) pin
        gpio_config_t io_conf = {};
        io_conf.pin_bit_mask = BIT64(AUDIO_CODEC_PA_PIN);
        io_conf.mode = GPIO_MODE_OUTPUT;
        io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
        io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
        io_conf.intr_type = GPIO_INTR_DISABLE;
        gpio_config(&io_conf);
        // Enable amplifier (HIGH = enabled)
        gpio_set_level(AUDIO_CODEC_PA_PIN, 1);
        ESP_LOGI(TAG, "MAX98357A amplifier enabled on GPIO %d", AUDIO_CODEC_PA_PIN);
    }

    void InitializeBacklightGpio() {
        // Force backlight ON via direct GPIO control
        gpio_config_t bl_conf = {};
        bl_conf.pin_bit_mask = BIT64(DISPLAY_BACKLIGHT_PIN);
        bl_conf.mode = GPIO_MODE_OUTPUT;
        bl_conf.pull_up_en = GPIO_PULLUP_DISABLE;
        bl_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
        bl_conf.intr_type = GPIO_INTR_DISABLE;
        gpio_config(&bl_conf);
        // Set backlight HIGH (most displays are active-high)
        gpio_set_level(DISPLAY_BACKLIGHT_PIN, 1);
        ESP_LOGI(TAG, "Backlight GPIO %d set HIGH", DISPLAY_BACKLIGHT_PIN);
    }

    void InitializeSpi() {
        spi_bus_config_t buscfg = {};
        buscfg.mosi_io_num = DISPLAY_MOSI_PIN;
        buscfg.miso_io_num = GPIO_NUM_NC;
        buscfg.sclk_io_num = DISPLAY_CLK_PIN;
        buscfg.quadwp_io_num = GPIO_NUM_NC;
        buscfg.quadhd_io_num = GPIO_NUM_NC;
        buscfg.max_transfer_sz = DISPLAY_WIDTH * DISPLAY_HEIGHT * sizeof(uint16_t);
        ESP_ERROR_CHECK(spi_bus_initialize(SPI3_HOST, &buscfg, SPI_DMA_CH_AUTO));
        ESP_LOGI(TAG, "SPI bus initialized for display");
    }

    void InitializeLcdDisplay() {
        esp_lcd_panel_io_handle_t panel_io = nullptr;
        esp_lcd_panel_handle_t panel = nullptr;

        ESP_LOGI(TAG, "Initializing ST7735 128x160 display");

        // LCD panel IO configuration
        esp_lcd_panel_io_spi_config_t io_config = {};
        io_config.cs_gpio_num = DISPLAY_CS_PIN;
        io_config.dc_gpio_num = DISPLAY_DC_PIN;
        io_config.spi_mode = DISPLAY_SPI_MODE;
        io_config.pclk_hz = 40 * 1000 * 1000;
        io_config.trans_queue_depth = 10;
        io_config.lcd_cmd_bits = 8;
        io_config.lcd_param_bits = 8;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI3_HOST, &io_config, &panel_io));

        // LCD panel configuration
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = DISPLAY_RST_PIN;
        panel_config.rgb_ele_order = DISPLAY_RGB_ORDER;
        panel_config.bits_per_pixel = 16;

        // Use ST7789 driver (compatible with ST7735)
        ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(panel_io, &panel_config, &panel));

        esp_lcd_panel_reset(panel);
        esp_lcd_panel_init(panel);
        esp_lcd_panel_invert_color(panel, DISPLAY_INVERT_COLOR);
        esp_lcd_panel_swap_xy(panel, DISPLAY_SWAP_XY);
        esp_lcd_panel_mirror(panel, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);

        // Turn on display
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel, true));

        display_ = new SpiLcdDisplay(panel_io, panel,
                                    DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                    DISPLAY_OFFSET_X, DISPLAY_OFFSET_Y,
                                    DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y, DISPLAY_SWAP_XY);

        ESP_LOGI(TAG, "Display initialized: %dx%d", DISPLAY_WIDTH, DISPLAY_HEIGHT);
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
        ESP_LOGI(TAG, "Initializing XAMAD ESP32-S3 DIY Board");
        InitializeBacklightGpio();  // Turn on backlight first!
        InitializeAmplifier();
        InitializeSpi();
        InitializeLcdDisplay();
        InitializeButtons();
        ESP_LOGI(TAG, "Board initialization complete!");
    }

    virtual Led* GetLed() override {
        static NoLed led;
        return &led;
    }

    virtual AudioCodec* GetAudioCodec() override {
        static NoAudioCodecSimplex audio_codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK,
            AUDIO_I2S_SPK_GPIO_LRCK,
            AUDIO_I2S_SPK_GPIO_DOUT,
            AUDIO_I2S_MIC_GPIO_SCK,
            AUDIO_I2S_MIC_GPIO_WS,
            AUDIO_I2S_MIC_GPIO_DIN
        );
        return &audio_codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }

    virtual Backlight* GetBacklight() override {
        // Using direct GPIO control for backlight, not PWM
        return nullptr;
    }
};

DECLARE_BOARD(XamadS3DiyBoard);
