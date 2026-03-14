#include "wifi_board.h"
#include "system_info.h"
#include <wifi_manager.h>
#include "codecs/es8311_audio_codec.h"
#include "display/lcd_display.h"
#include "display/lvgl_display/lvgl_theme.h"
#include "device_state.h"
#include "system_reset.h"
#include "application.h"
#include "assets/lang_config.h"
#include "button.h"
#include "config.h"
#include "led/single_led.h"
#include "mcp_server.h"
#include "settings.h"

// Sensor drivers
#include "sensors/tsl2591_device.h"
#include "sensors/as7341_device.h"
#include "sensors/aht20_device.h"
#include "sensors/gps_device.h"
#include "sensors/wifi_geolocation.h"
#include "skyguard_display.h"
#include "skyguard_weather.h"
#include "skyguard_sky_tracker.h"
#include "skyguard_astro.h"
#include "skyguard_http.h"
#include "star_emoji.h"
#include "skyguard_webui.h"
#include "skyguard_gif_decode.h"

extern "C" {
#include "display/lvgl_display/jpg/jpeg_to_image.h"
}

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
#include <cJSON.h>
#include <esp_netif.h>
#include <esp_wifi.h>
#include <esp_mac.h>
#include <esp_timer.h>
#include <esp_system.h>

#define TAG "SkyGuardAI"

/*
 * SkyGuard AI — Astronomy Copilot
 * ======================================
 * Based on LCDWiki 2.8" ESP32-S3 Display Board
 *
 * I2C_NUM_0 (GPIO 15/16): Touch FT6336G (0x38) + ES8311 Audio (0x18)
 * I2C_NUM_1 (GPIO 14/21): TSL2591 (0x29) + AS7341 (0x39) + AHT20 (0x38)
 * UART1     (GPIO 2/3):   GPS module (9600 baud NMEA)
 *
 * Display:  ILI9341 240x320 SPI
 * Audio:    ES8311 full-duplex + FM8002E PA + MEMS mic
 * LED:      WS2812 RGB
 */

class SkyGuardEliteBoard : public WifiBoard {
private:
    Button boot_button_;

    // I2C buses
    i2c_master_bus_handle_t display_i2c_bus_ = nullptr;   // I2C_NUM_0
    i2c_master_bus_handle_t sensor_i2c_bus_ = nullptr;    // I2C_NUM_1

    // Display
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    esp_lcd_panel_io_handle_t touch_io_ = nullptr;
    esp_lcd_touch_handle_t touch_handle_ = nullptr;
    lv_indev_t* touch_indev_ = nullptr;
    Display* display_ = nullptr;

    // SkyGuard sensors
    Tsl2591Device* tsl2591_ = nullptr;
    As7341Device* as7341_ = nullptr;
    Aht20Device* aht20_ = nullptr;
    GpsDevice* gps_ = nullptr;
    WifiGeolocation* wifi_geo_ = nullptr;
    SkyGuardDisplay* sg_display_ = nullptr;
    esp_timer_handle_t sg_update_timer_ = nullptr;

    // Network data providers
    SkyGuardWeather* weather_ = nullptr;
    SkyGuardSkyTracker* sky_tracker_ = nullptr;
    SkyGuardWebUI* webui_ = nullptr;

    // Periodic fetch counters (incremented each 1s tick)
    uint32_t tick_counter_ = 0;
    uint32_t ai_idle_counter_ = 0;    // Seconds since AI went idle after speaking
    bool ai_was_active_ = false;       // Track previous AI state for edge detection

    // Direct touch polling for AI exit (bypasses LVGL event system)
    bool touch_was_down_ = false;
    uint32_t touch_down_tick_ = 0;     // Tick when touch first detected
    uint16_t touch_start_y_ = 0;       // Y coordinate at touch start (for swipe detection)
    bool pending_ai_exit_ = false;     // Flag: abort speaking done, waiting for listening state to call StopListening

    // Centralized resolved position — ONE source of truth
    // Priority: GPS module → Google WiFi API → NVS fallback (from WebUI config)
    float pos_lat_ = 44.9019f;   // Default: Asti
    float pos_lon_ = 8.1662f;
    float pos_alt_ = 0.0f;
    int pos_gps_sats_ = 0;
    float pos_gps_hdop_ = 99.9f;
    const char* pos_source_ = "nvs";  // "gps", "wifi_google", "nvs"

    // Properly exit chatbot session: handles speaking, listening, and connecting states
    void ExitChatbot() {
        auto& app = Application::GetInstance();
        auto state = app.GetDeviceState();
        if (state == kDeviceStateSpeaking) {
            // Abort speaking first → will transition to listening
            // Then pending_ai_exit_ flag will trigger StopListening on next tick
            app.ToggleChatState();
            pending_ai_exit_ = true;
            ESP_LOGI(TAG, "ExitChatbot: aborting speech, will stop listening on next tick");
        } else if (state == kDeviceStateListening) {
            // Directly stop listening → transitions to idle
            app.StopListening();
            pending_ai_exit_ = false;
            ESP_LOGI(TAG, "ExitChatbot: StopListening → idle");
        } else if (state == kDeviceStateConnecting) {
            // Force close during connection attempt
            app.ToggleChatState();
            pending_ai_exit_ = false;
            ESP_LOGI(TAG, "ExitChatbot: aborting connection");
        }
        ai_idle_counter_ = 0;
        ai_was_active_ = false;
    }

    void UpdatePosition() {
        // 1. GPS module (highest priority)
        if (gps_ && gps_->HasFix()) {
            pos_lat_ = gps_->GetLatitude();
            pos_lon_ = gps_->GetLongitude();
            pos_alt_ = gps_->GetAltitude();
            pos_gps_sats_ = gps_->GetSatellites();
            pos_gps_hdop_ = gps_->GetHdop();
            pos_source_ = "gps";
            return;
        }
        // 2. Google WiFi API (only if resolved and NOT ip-based)
        if (wifi_geo_) {
            const auto& loc = wifi_geo_->GetLocation();
            if (loc.valid && strcmp(loc.source, "wifi_google") == 0) {
                pos_lat_ = loc.latitude;
                pos_lon_ = loc.longitude;
                pos_alt_ = 0;
                pos_gps_sats_ = 0;
                pos_gps_hdop_ = 99.9f;
                pos_source_ = "wifi_google";
                return;
            }
        }
        // 3. NVS fallback (WebUI-configured coordinates, works offline)
        Settings sg_pos("skyguard", false);
        pos_lat_ = std::strtof(sg_pos.GetString("fallback_lat", "44.9019").c_str(), nullptr);
        pos_lon_ = std::strtof(sg_pos.GetString("fallback_lon", "8.1662").c_str(), nullptr);
        pos_alt_ = 0;
        pos_gps_sats_ = gps_ ? gps_->GetSatellites() : 0;
        pos_gps_hdop_ = 99.9f;
        pos_source_ = "nvs";
    }

    // Calibration (loaded from NVS at init)
    float temp_offset_ = -2.4f;
    float hum_offset_ = 0.0f;
    float lux_threshold_ = 1.0f;
    float night_threshold_ = 10.0f;

    // Alert system — previous values + cooldowns
    struct AlertState {
        float prev_sqm = 0;
        float prev_wind = 0;
        int prev_clouds = -1;
        float prev_spread = 99;
        float prev_temp = 99;
        uint32_t last_sqm_alert = 0;
        uint32_t last_wind_alert = 0;
        uint32_t last_cloud_alert = 0;
        uint32_t last_dew_alert = 0;
        uint32_t last_temp_alert = 0;
        bool initialized = false;
    } alerts_;

    // AHT20 validation — reject bogus readings at startup
    bool aht20_validated_ = false;
    int aht20_stable_count_ = 0;
    float aht20_last_temp_ = -999.0f;

    bool ValidateAht20Reading() {
        if (!aht20_) return false;
        float t = aht20_->GetTemperature();
        float h = aht20_->GetHumidity();
        // Range check
        if (t < -40.0f || t > 60.0f || h < 0.0f || h > 100.0f) {
            ESP_LOGW(TAG, "AHT20 out of range: T=%.1f H=%.1f — discarding", t, h);
            aht20_stable_count_ = 0;
            return false;
        }
        // Stability check: reject if >15°C jump from previous reading
        if (aht20_last_temp_ > -900.0f && fabsf(t - aht20_last_temp_) > 15.0f) {
            ESP_LOGW(TAG, "AHT20 unstable: T=%.1f prev=%.1f (diff=%.1f) — discarding", t, aht20_last_temp_, fabsf(t - aht20_last_temp_));
            aht20_last_temp_ = t;
            aht20_stable_count_ = 0;
            return false;
        }
        aht20_last_temp_ = t;
        aht20_stable_count_++;
        if (aht20_stable_count_ >= 2) {
            if (!aht20_validated_) {
                ESP_LOGI(TAG, "AHT20 validated: T=%.1f H=%.1f (2 stable readings)", t, h);
                aht20_validated_ = true;
            }
            return true;
        }
        return false;
    }

    // Dew heater state
    int dew_gpio_ = -1;               // -1 = not configured
    int dew_mode_ = 0;                // 0=off, 1=on, 2=auto
    int dew_power_ = 100;             // PWM duty 0-100%
    float dew_threshold_ = 3.0f;      // Auto mode: turn on if spread < this
    bool dew_heater_active_ = false;   // Current output state
    ledc_channel_t dew_ledc_ch_ = LEDC_CHANNEL_1;  // Channel 0 = backlight

    // =========================================================================
    // READING CACHE — store readings when offline, send when back online
    // =========================================================================
    static constexpr int CACHE_MAX = 288;  // 24h at 5min intervals

    struct CachedReading {
        char* json;       // Heap-allocated JSON string (PSRAM)
        uint32_t timestamp; // Uptime seconds when captured
        bool sent;
    };

    CachedReading* reading_cache_ = nullptr;  // Ring buffer [CACHE_MAX]
    int cache_head_ = 0;    // Next write position
    int cache_count_ = 0;   // Number of unsent entries
    bool cache_initialized_ = false;

    void InitReadingCache() {
        reading_cache_ = (CachedReading*)heap_caps_calloc(CACHE_MAX, sizeof(CachedReading), MALLOC_CAP_SPIRAM);
        if (!reading_cache_) {
            reading_cache_ = (CachedReading*)calloc(CACHE_MAX, sizeof(CachedReading));
        }
        if (reading_cache_) {
            cache_initialized_ = true;
            ESP_LOGI(TAG, "Reading cache ready: %d slots (%d bytes PSRAM)",
                     CACHE_MAX, (int)(CACHE_MAX * sizeof(CachedReading)));
        } else {
            ESP_LOGE(TAG, "Reading cache alloc FAILED");
        }
    }

    // Add a reading to cache. Takes ownership of json string.
    void CacheReading(char* json) {
        if (!cache_initialized_ || !reading_cache_) {
            cJSON_free(json);
            return;
        }
        // Free old entry if overwriting
        if (reading_cache_[cache_head_].json) {
            cJSON_free(reading_cache_[cache_head_].json);
            if (!reading_cache_[cache_head_].sent && cache_count_ > 0) cache_count_--;
        }
        reading_cache_[cache_head_].json = json;
        reading_cache_[cache_head_].timestamp = (uint32_t)(esp_timer_get_time() / 1000000);
        reading_cache_[cache_head_].sent = false;
        cache_head_ = (cache_head_ + 1) % CACHE_MAX;
        cache_count_++;
        ESP_LOGI(TAG, "Reading cached (pending=%d)", cache_count_);
    }

    // Try to send all unsent cached readings
    void FlushReadingCache() {
        if (!cache_initialized_ || !reading_cache_ || cache_count_ == 0) return;
        if (sqm_server_url_.empty()) return;

        char url[128];
        snprintf(url, sizeof(url), "%s/api/readings", sqm_server_url_.c_str());
        const char* api_key = sqm_api_key_.empty() ? nullptr : sqm_api_key_.c_str();

        int sent = 0, failed = 0;
        for (int i = 0; i < CACHE_MAX && sent + failed < cache_count_; i++) {
            auto& entry = reading_cache_[i];
            if (!entry.json || entry.sent) continue;

            char* resp = SkyGuardHttp::AllocBuffer(256);
            if (!resp) break;

            bool ok = SkyGuardHttp::Post(url, entry.json, resp, 256, 10000, api_key);
            free(resp);

            if (ok) {
                entry.sent = true;
                cJSON_free(entry.json);
                entry.json = nullptr;
                sent++;
            } else {
                failed++;
                // Stop on first failure — server probably unreachable
                break;
            }
            // Yield between posts to avoid watchdog
            vTaskDelay(pdMS_TO_TICKS(100));
        }

        cache_count_ -= sent;
        if (cache_count_ < 0) cache_count_ = 0;
        if (sent > 0) {
            ESP_LOGI(TAG, "Cache flush: %d sent, %d remaining", sent, cache_count_);
        }
    }

    // =========================================================================
    // INITIALIZATION METHODS
    // =========================================================================

    void InitializeMclk() {
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

    void ScanI2cBus(i2c_master_bus_handle_t bus, const char* name) {
        ESP_LOGI(TAG, "Scanning %s I2C bus...", name);
        uint8_t found = 0;
        for (uint8_t addr = 0x08; addr < 0x78; addr++) {
            // Yield to watchdog every 16 addresses
            if ((addr & 0x0F) == 0) {
                vTaskDelay(pdMS_TO_TICKS(1));
            }
            i2c_master_dev_handle_t dev;
            i2c_device_config_t cfg = {
                .dev_addr_length = I2C_ADDR_BIT_LEN_7,
                .device_address = addr,
                .scl_speed_hz = 100000,
            };
            if (i2c_master_bus_add_device(bus, &cfg, &dev) != ESP_OK) continue;

            uint8_t reg = 0x00;
            if (i2c_master_transmit(dev, &reg, 1, 20) == ESP_OK) {
                ESP_LOGW(TAG, "[%s] Found device at 0x%02X", name, addr);
                found++;
            }
            i2c_master_bus_rm_device(dev);
        }
        ESP_LOGI(TAG, "[%s] Scan complete: %d device(s)", name, found);
    }

    void InitializeDisplayI2c() {
        ESP_LOGI(TAG, "Initializing Display I2C (I2C_NUM_0)");

        // Reset touch controller — FT6336G needs long reset pulse
        gpio_config_t io_conf = {};
        io_conf.pin_bit_mask = BIT64(TOUCH_RST_PIN);
        io_conf.mode = GPIO_MODE_OUTPUT;
        gpio_config(&io_conf);
        gpio_set_level(TOUCH_RST_PIN, 0);
        vTaskDelay(pdMS_TO_TICKS(50));   // Hold reset low for 50ms (was 10ms)
        gpio_set_level(TOUCH_RST_PIN, 1);
        vTaskDelay(pdMS_TO_TICKS(300));  // Wait 300ms for FT6336G boot (was 100ms)

        i2c_master_bus_config_t cfg = {
            .i2c_port = I2C_NUM_0,
            .sda_io_num = TOUCH_I2C_SDA_PIN,
            .scl_io_num = TOUCH_I2C_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = { .enable_internal_pullup = 1 },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&cfg, &display_i2c_bus_));
        ESP_LOGI(TAG, "Display I2C bus ready");

        // Scan bus to verify ES8311 + FT6336G are present
        ScanI2cBus(display_i2c_bus_, "Display/I2C0");
    }

    void InitializeSensorI2c() {
        // Sensors on SEPARATE I2C_NUM_1 bus (expansion connector GPIO14/GPIO21)
        // This avoids conflict with touch FT6336G (0x38) on I2C_NUM_0
        ESP_LOGI(TAG, "Creating sensor I2C bus: SDA=GPIO%d SCL=GPIO%d port=%d speed=%dHz",
                 SENSOR_I2C_SDA_PIN, SENSOR_I2C_SCL_PIN, SENSOR_I2C_PORT, SENSOR_I2C_SPEED_HZ);

        i2c_master_bus_config_t cfg = {
            .i2c_port = SENSOR_I2C_PORT,
            .sda_io_num = SENSOR_I2C_SDA_PIN,
            .scl_io_num = SENSOR_I2C_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = { .enable_internal_pullup = 1 },
        };
        esp_err_t ret = i2c_new_master_bus(&cfg, &sensor_i2c_bus_);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Sensor I2C bus init FAILED: %s — falling back to shared bus", esp_err_to_name(ret));
            sensor_i2c_bus_ = display_i2c_bus_;
            return;
        }
        ESP_LOGI(TAG, "Sensor I2C bus ready (I2C_NUM_1, separate from touch/audio)");

        // Scan to verify sensors are present
        ScanI2cBus(sensor_i2c_bus_, "Sensor/I2C1");
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
            .flags = {},
        };
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(DISPLAY_SPI_HOST, &io_config, &panel_io_));

        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = DISPLAY_RST_PIN;
        panel_config.rgb_ele_order = LCD_RGB_ELEMENT_ORDER_BGR;
        panel_config.bits_per_pixel = 16;

        ESP_ERROR_CHECK(esp_lcd_new_panel_ili9341(panel_io_, &panel_config, &panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        ESP_ERROR_CHECK(esp_lcd_panel_init(panel_));
        // ILI9341 on LCDWiki board has inverted colors by default.
        // Without this, black(0x0000) shows as white and vice versa.
        ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel_, true));
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));
        ESP_LOGI(TAG, "ILI9341 color inversion ENABLED");

        display_ = new SpiLcdDisplay(panel_io_, panel_,
                                      DISPLAY_WIDTH, DISPLAY_HEIGHT,
                                      0, 0,
                                      DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y,
                                      DISPLAY_SWAP_XY);

        // Show XiaoZhi's bottom subtitle bar — displays AI response text
        // (was hidden, but user needs to see transcribed responses)

        // Patch dark theme colors to SkyGuard palette.
        // This ensures ANY call to SetTheme("dark") from assets.cc or MCP
        // will use our dark gray-blue instead of pure black.
        auto& tm = LvglThemeManager::GetInstance();
        auto* dark = static_cast<LvglTheme*>(tm.GetTheme("dark"));
        if (dark) {
            dark->set_background_color(lv_color_hex(0x1A1A2E));
            dark->set_chat_background_color(lv_color_hex(0x1A1A2E));
            dark->set_text_color(lv_color_hex(0xE0E0E0));
            ESP_LOGI(TAG, "Patched dark theme: bg=0x1A1A2E, text=0xE0E0E0");
        }
    }

    void InitializeTouch() {
        ESP_LOGI(TAG, "Initializing FT6336G touch");

        // Probe touch controller first — avoid crash if not responding
        if (!ProbeI2cDevice(display_i2c_bus_, TOUCH_I2C_ADDR)) {
            ESP_LOGW(TAG, "Touch controller not found at 0x%02X — touch disabled", TOUCH_I2C_ADDR);
            return;
        }
        ESP_LOGI(TAG, "Touch controller found at 0x%02X", TOUCH_I2C_ADDR);

        esp_lcd_panel_io_i2c_config_t touch_io_config = {
            .dev_addr = TOUCH_I2C_ADDR,
            .control_phase_bytes = 1,
            .dc_bit_offset = 0,
            .lcd_cmd_bits = 8,
            .lcd_param_bits = 8,
            .flags = { .disable_control_phase = 1 },
            .scl_speed_hz = 400000,
        };
        esp_err_t ret = esp_lcd_new_panel_io_i2c_v2(display_i2c_bus_, &touch_io_config, &touch_io_);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Touch I2C panel IO failed: %s — touch disabled", esp_err_to_name(ret));
            return;
        }

        // Touch config — use POLLING mode (GPIO_NUM_NC for INT) to avoid
        // interrupt conflicts. LVGL port polls touch periodically anyway.
        // Flags MUST match display orientation.
        // x_max/y_max must be PRE-SWAP (portrait) dimensions.
        // Raw FT6336G: x=0..240, y=0..320. After swap_xy → landscape 320x240.
        esp_lcd_touch_config_t touch_config = {
            .x_max = DISPLAY_HEIGHT,         // 240 = native sensor width (portrait)
            .y_max = DISPLAY_WIDTH,          // 320 = native sensor height (portrait)
            .rst_gpio_num = GPIO_NUM_NC,     // Already reset manually above
            .int_gpio_num = GPIO_NUM_NC,     // POLLING mode — no interrupt
            .levels = { .reset = 0, .interrupt = 0 },
            .flags = {
                .swap_xy = TOUCH_SWAP_XY ? 1 : 0,
                .mirror_x = TOUCH_MIRROR_X ? 1 : 0,
                .mirror_y = TOUCH_MIRROR_Y ? 1 : 0,
            },
            .process_coordinates = nullptr,
            .interrupt_callback = nullptr,
            .user_data = nullptr,
        };
        ESP_LOGI(TAG, "Touch config: POLLING mode, swap_xy=%d, mirror_x=%d, mirror_y=%d",
                 touch_config.flags.swap_xy, touch_config.flags.mirror_x, touch_config.flags.mirror_y);

        ret = esp_lcd_touch_new_i2c_ft5x06(touch_io_, &touch_config, &touch_handle_);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Touch controller init failed: %s — touch disabled", esp_err_to_name(ret));
            return;
        }

        lvgl_port_touch_cfg_t touch_cfg = {
            .disp = lv_display_get_default(),
            .handle = touch_handle_,
        };
        touch_indev_ = lvgl_port_add_touch(&touch_cfg);
        if (touch_indev_) {
            ESP_LOGI(TAG, "Touch initialized OK (swap=%d mirX=%d mirY=%d)",
                     DISPLAY_SWAP_XY, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
        } else {
            ESP_LOGE(TAG, "Failed to add touch to LVGL!");
        }
    }

    // Probe I2C address without ESP_ERROR_CHECK — returns true if device ACKs
    bool ProbeI2cDevice(i2c_master_bus_handle_t bus, uint8_t addr) {
        i2c_master_dev_handle_t dev;
        i2c_device_config_t cfg = {
            .dev_addr_length = I2C_ADDR_BIT_LEN_7,
            .device_address = addr,
            .scl_speed_hz = 100000,
        };
        esp_err_t add_ret = i2c_master_bus_add_device(bus, &cfg, &dev);
        if (add_ret != ESP_OK) {
            ESP_LOGW(TAG, "  Probe 0x%02X: add_device failed: %s", addr, esp_err_to_name(add_ret));
            return false;
        }
        // Use i2c_master_probe instead of transmit — more reliable for device detection
        esp_err_t ret = i2c_master_probe(bus, addr, 200);
        i2c_master_bus_rm_device(dev);
        if (ret != ESP_OK) {
            ESP_LOGD(TAG, "  Probe 0x%02X: no ACK (%s)", addr, esp_err_to_name(ret));
        }
        return (ret == ESP_OK);
    }

    // Try to find a sensor on either bus (display first, then expansion)
    i2c_master_bus_handle_t FindSensorBus(uint8_t addr) {
        // Try display bus first (I2C_NUM_0, GPIO15/16)
        if (display_i2c_bus_ && ProbeI2cDevice(display_i2c_bus_, addr)) {
            ESP_LOGI(TAG, "  0x%02X found on display bus (I2C_NUM_0)", addr);
            return display_i2c_bus_;
        }
        // Try expansion bus (I2C_NUM_1, GPIO14/21)
        if (sensor_i2c_bus_ && sensor_i2c_bus_ != display_i2c_bus_ &&
            ProbeI2cDevice(sensor_i2c_bus_, addr)) {
            ESP_LOGI(TAG, "  0x%02X found on expansion bus (I2C_NUM_1)", addr);
            return sensor_i2c_bus_;
        }
        ESP_LOGW(TAG, "  0x%02X not found on any bus", addr);
        return nullptr;
    }

    void InitializeSensors() {
        ESP_LOGI(TAG, "Initializing SkyGuard sensors");

        // Wait for I2C bus to settle after touch/audio init
        vTaskDelay(pdMS_TO_TICKS(100));

        // TSL2591 — Sky Brightness
        // Hardware: physically on I2C connector (GPIO15/16 = display bus)
        // Fallback: try expansion bus if not found on display bus
        {
            i2c_master_bus_handle_t bus = nullptr;
            // Try display bus first (where it's physically wired)
            if (display_i2c_bus_) {
                ESP_LOGI(TAG, "Probing TSL2591 (0x%02X) on display bus...", TSL2591_I2C_ADDR);
                if (ProbeI2cDevice(display_i2c_bus_, TSL2591_I2C_ADDR)) {
                    bus = display_i2c_bus_;
                    ESP_LOGI(TAG, "  TSL2591 found on display bus (I2C_NUM_0)");
                }
            }
            // Try expansion bus as fallback
            if (!bus && sensor_i2c_bus_ && sensor_i2c_bus_ != display_i2c_bus_) {
                ESP_LOGI(TAG, "Probing TSL2591 (0x%02X) on expansion bus...", TSL2591_I2C_ADDR);
                if (ProbeI2cDevice(sensor_i2c_bus_, TSL2591_I2C_ADDR)) {
                    bus = sensor_i2c_bus_;
                    ESP_LOGI(TAG, "  TSL2591 found on expansion bus (I2C_NUM_1)");
                }
            }
            if (bus) {
                // 400kHz OK on display bus (external pullups); 100kHz on expansion bus
                uint32_t spd = (bus == display_i2c_bus_) ? 400000 : SENSOR_I2C_SPEED_HZ;
                tsl2591_ = new Tsl2591Device(bus, TSL2591_I2C_ADDR, spd);
                if (!tsl2591_->Initialize()) {
                    ESP_LOGW(TAG, "TSL2591 init failed — SQM disabled");
                    delete tsl2591_;
                    tsl2591_ = nullptr;
                } else {
                    ESP_LOGI(TAG, "TSL2591 OK — SQM enabled");
                }
            } else {
                ESP_LOGW(TAG, "TSL2591 NOT FOUND on any bus — SQM disabled");
            }
        }

        // AS7341 — Spectral Analysis
        // Hardware: physically on I2C connector (GPIO15/16 = display bus)
        {
            i2c_master_bus_handle_t bus = nullptr;
            if (display_i2c_bus_) {
                ESP_LOGI(TAG, "Probing AS7341 (0x%02X) on display bus...", AS7341_I2C_ADDR);
                if (ProbeI2cDevice(display_i2c_bus_, AS7341_I2C_ADDR)) {
                    bus = display_i2c_bus_;
                    ESP_LOGI(TAG, "  AS7341 found on display bus (I2C_NUM_0)");
                }
            }
            if (!bus && sensor_i2c_bus_ && sensor_i2c_bus_ != display_i2c_bus_) {
                ESP_LOGI(TAG, "Probing AS7341 (0x%02X) on expansion bus...", AS7341_I2C_ADDR);
                if (ProbeI2cDevice(sensor_i2c_bus_, AS7341_I2C_ADDR)) {
                    bus = sensor_i2c_bus_;
                    ESP_LOGI(TAG, "  AS7341 found on expansion bus (I2C_NUM_1)");
                }
            }
            if (bus) {
                uint32_t spd = (bus == display_i2c_bus_) ? 400000 : SENSOR_I2C_SPEED_HZ;
                as7341_ = new As7341Device(bus, AS7341_I2C_ADDR, spd);
                if (!as7341_->Initialize()) {
                    ESP_LOGW(TAG, "AS7341 init failed — spectral disabled");
                    delete as7341_;
                    as7341_ = nullptr;
                } else {
                    ESP_LOGI(TAG, "AS7341 OK — spectral enabled");
                }
            } else {
                ESP_LOGW(TAG, "AS7341 NOT FOUND on any bus — spectral disabled");
            }
        }

        // AHT20 — Temp/Humidity (0x38 conflicts with touch on display bus)
        // MUST use expansion bus only to avoid FT6336G conflict
        if (sensor_i2c_bus_ && sensor_i2c_bus_ != display_i2c_bus_) {
            ESP_LOGI(TAG, "Probing AHT20 (0x%02X) on expansion bus...", AHT20_I2C_ADDR);
            if (ProbeI2cDevice(sensor_i2c_bus_, AHT20_I2C_ADDR)) {
                aht20_ = new Aht20Device(sensor_i2c_bus_, AHT20_I2C_ADDR, SENSOR_I2C_SPEED_HZ);
                if (!aht20_->Initialize()) {
                    ESP_LOGW(TAG, "AHT20 init failed — environment disabled");
                    delete aht20_;
                    aht20_ = nullptr;
                } else {
                    ESP_LOGI(TAG, "AHT20 OK — environment enabled (expansion bus)");
                }
            } else {
                ESP_LOGW(TAG, "AHT20 not found at 0x%02X on expansion bus", AHT20_I2C_ADDR);
                aht20_ = nullptr;
            }
        } else {
            ESP_LOGW(TAG, "AHT20 SKIPPED — no separate bus (0x38 = touch conflict)");
            aht20_ = nullptr;
        }

        ESP_LOGI(TAG, "Sensor init done: TSL=%p AS=%p AHT=%p", tsl2591_, as7341_, aht20_);
    }

    void InitializeGps() {
        ESP_LOGI(TAG, "Initializing GPS on UART%d", GPS_UART_NUM);
        gps_ = new GpsDevice(GPS_UART_NUM, GPS_UART_TX_PIN, GPS_UART_RX_PIN,
                              GPS_UART_BAUD, GPS_UART_BUF_SIZE);
        if (!gps_->Initialize()) {
            ESP_LOGW(TAG, "GPS UART init failed");
            delete gps_;
            gps_ = nullptr;
        } else {
            gps_->StartTask();
        }

        // WiFi Geolocation fallback
        wifi_geo_ = new WifiGeolocation();
        {
            Settings geo_settings("skyguard", false);
            std::string google_key = geo_settings.GetString("google_key", "");
            if (!google_key.empty()) {
                wifi_geo_->SetGoogleApiKey(google_key.c_str());
                google_api_key_ = google_key;
                ESP_LOGI(TAG, "Google Geolocation API key loaded (len=%d)", (int)google_key.size());
            } else {
                ESP_LOGW(TAG, "No Google API key — WiFi geolocation disabled, using NVS fallback");
            }
        }
        // Set WiFi geolocation fallback from NVS (WebUI-configured coords)
        Settings fb_pos("skyguard", false);
        float fb_lat = std::strtof(fb_pos.GetString("fallback_lat", "44.9019").c_str(), nullptr);
        float fb_lon = std::strtof(fb_pos.GetString("fallback_lon", "8.1662").c_str(), nullptr);
        wifi_geo_->SetFallbackLocation(fb_lat, fb_lon);
        ESP_LOGI(TAG, "WiFi geolocation NVS fallback: %.4f, %.4f", fb_lat, fb_lon);
    }

    void InitializeButtons() {
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            auto state = app.GetDeviceState();
            ESP_LOGW(TAG, ">>> BOOT BUTTON pressed! DeviceState=%d <<<", (int)state);
            if (state == kDeviceStateStarting) {
                ESP_LOGW(TAG, "Device still starting — entering WiFi config mode");
                EnterWifiConfigMode();
                return;
            }
            // If AI is active (listening/speaking/connecting), ALWAYS exit
            // If AI is idle, toggle to start chatbot
            if (state == kDeviceStateListening ||
                state == kDeviceStateSpeaking ||
                state == kDeviceStateConnecting) {
                ESP_LOGI(TAG, "BOOT press → exiting chatbot");
                ExitChatbot();
            } else {
                ESP_LOGI(TAG, "BOOT press → starting chatbot");
                app.ToggleChatState();
            }
        });
    }

    // =========================================================================
    // MCP TOOL REGISTRATION
    // =========================================================================

    void RegisterMcpTools() {
        auto& mcp = McpServer::GetInstance();

        // --- device.sqm.read ---
        mcp.AddTool("device.sqm.read",
            "Leggi qualita' del cielo: MPSAS, NELM, Bortle, confidenza, rapporto IR",
            PropertyList({
                Property("with_corrections", kPropertyTypeBoolean, true)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                if (!tsl2591_) return false; //"TSL2591 not available");

                float temp = 25.0f, hum = 50.0f, press = 1013.25f;
                if (aht20_) {
                    aht20_->Measure();
                    temp = aht20_->GetTemperature();
                    hum = aht20_->GetHumidity();
                }

                if (!tsl2591_->Measure(temp, hum, press)) {
                    return false; //"Measurement failed");
                }

                char buf[256];
                snprintf(buf, sizeof(buf),
                    "MPSAS=%.2f, NELM=%.1f, Bortle=%d (%s), "
                    "Confidenza=%d%%, IR_ratio=%.3f, Lux=%.4f, "
                    "Raw_full=%u, Raw_IR=%u",
                    tsl2591_->GetMpsas(), tsl2591_->GetNelm(),
                    tsl2591_->GetBortle(), tsl2591_->GetQuality(),
                    tsl2591_->GetConfidence(), tsl2591_->GetIrRatio(),
                    tsl2591_->GetLux(),
                    tsl2591_->GetRawFull(), tsl2591_->GetRawIR());

                return std::string(buf);
            });

        // --- device.sqm.spectral ---
        mcp.AddTool("device.sqm.spectral",
            "Analisi spettrale 8 canali AS7341: identifica sorgente inquinamento luminoso",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                if (!as7341_) return false; //"AS7341 not available");

                if (!as7341_->Measure()) {
                    return false; //"Spectral measurement failed");
                }

                auto& r = as7341_->GetReading();
                char buf[512];
                snprintf(buf, sizeof(buf),
                    "F1_415nm=%u, F2_445nm=%u, F3_480nm=%u, F4_515nm=%u, "
                    "F5_555nm=%u, F6_590nm=%u, F7_630nm=%u, F8_680nm=%u, "
                    "Clear=%u, NIR=%u, "
                    "LP_source=%s, LP_correction=%.2f MPSAS, "
                    "Blue_ratio=%.3f, Sodium_ratio=%.3f, SQI=%d%%",
                    r.f1_415nm, r.f2_445nm, r.f3_480nm, r.f4_515nm,
                    r.f5_555nm, r.f6_590nm, r.f7_630nm, r.f8_680nm,
                    r.clear, r.nir,
                    as7341_->GetLpSourceName(), as7341_->GetLpCorrection(),
                    as7341_->GetBlueRatio(), as7341_->GetSodiumRatio(),
                    as7341_->GetSpectralQuality());

                return std::string(buf);
            });

        // --- device.environment.read ---
        mcp.AddTool("device.environment.read",
            "Leggi temperatura, umidita', punto di rugiada, rischio condensa",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                if (!aht20_) return false;
                if (!aht20_validated_) {
                    return std::string("{\"error\":\"sensor_initializing\",\"message\":\"Sensore in fase di inizializzazione\"}");
                }

                if (!aht20_->Measure()) {
                    return false;
                }

                char buf[256];
                float temp = aht20_->GetTemperature() + temp_offset_;
                float hum = aht20_->GetHumidity() + hum_offset_;
                if (hum > 100.0f) hum = 100.0f;
                if (hum < 0.0f) hum = 0.0f;
                float dew = aht20_->GetDewPoint();
                snprintf(buf, sizeof(buf),
                    "Temperatura=%.1f°C, Umidita=%.1f%%, "
                    "Punto_rugiada=%.1f°C, Spread=%.1f°C, "
                    "Rischio_condensa=%s, "
                    "Countdown_rugiada=%d min, "
                    "Rate_temp=%.2f °C/h",
                    temp, hum, dew, temp - dew,
                    aht20_->GetCondensationRisk() ? "SI" : "NO",
                    aht20_->GetDewCountdownMin(),
                    aht20_->GetTempRate());

                return std::string(buf);
            });

        // --- device.gps.position ---
        mcp.AddTool("device.gps.position",
            "Posizione GPS con fallback WiFi/IP: lat, lon, altitudine, ora UTC, tempo siderale, sorgente",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                UpdatePosition();
                char buf[320];
                if (gps_ && gps_->HasFix()) {
                    snprintf(buf, sizeof(buf),
                        "Lat=%.6f, Lon=%.6f, Alt=%.1fm, "
                        "Sats=%d, HDOP=%.1f, "
                        "UTC=%04d-%02d-%02d %02d:%02d:%02d, "
                        "JD=%.4f, LST=%.2fh, "
                        "Source=gps",
                        pos_lat_, pos_lon_, pos_alt_,
                        pos_gps_sats_, pos_gps_hdop_,
                        gps_->GetYear(), gps_->GetMonth(), gps_->GetDay(),
                        gps_->GetHour(), gps_->GetMinute(), gps_->GetSecond(),
                        gps_->GetJulianDate(), gps_->GetLST());
                } else {
                    snprintf(buf, sizeof(buf),
                        "Lat=%.6f, Lon=%.6f, Alt=%.1fm, "
                        "GPS_sats=%d (no fix), "
                        "Source=%s",
                        pos_lat_, pos_lon_, pos_alt_,
                        pos_gps_sats_, pos_source_);
                }
                return std::string(buf);
            });

        // --- device.geo.configure ---
        mcp.AddTool("device.geo.configure",
            "Configura geolocalizzazione: imposta Google API key per WiFi geolocation",
            PropertyList({
                Property("google_api_key", kPropertyTypeString)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                if (!wifi_geo_) return false; //"WiFi geolocation not initialized");

                std::string api_key = props["google_api_key"].value<std::string>();
                if (api_key.empty()) {
                    return false; //"Google API key cannot be empty");
                }

                wifi_geo_->SetGoogleApiKey(api_key.c_str());
                ESP_LOGI(TAG, "Google Geolocation API key configured (length=%d)", (int)api_key.size());

                return std::string("Google API key configured successfully");
            });

        // --- device.config.api_keys ---
        mcp.AddTool("device.config.api_keys",
            "Configura API keys e URL: OWM (meteo), N2YO (satelliti), Google (geolocalizzazione), "
            "NINA (sequencer, es. http://192.168.1.100:1888), "
            "PHD2 (autoguida, es. http://192.168.1.100:4400), "
            "Stellarium (planetario, es. http://192.168.1.100:8090), "
            "INDI (strumenti Linux, es. http://192.168.1.100:8624). "
            "Salva in NVS persistente.",
            PropertyList({
                Property("owm_key", kPropertyTypeString, std::string("")),
                Property("n2yo_key", kPropertyTypeString, std::string("")),
                Property("google_key", kPropertyTypeString, std::string("")),
                Property("nina_url", kPropertyTypeString, std::string("")),
                Property("phd2_url", kPropertyTypeString, std::string("")),
                Property("stellarium_url", kPropertyTypeString, std::string("")),
                Property("indi_url", kPropertyTypeString, std::string("")),
            }),
            [this](const PropertyList& props) -> ReturnValue {
                Settings sg_settings("skyguard", true);
                int configured = 0;

                std::string owm = props["owm_key"].value<std::string>();
                if (!owm.empty()) {
                    sg_settings.SetString("owm_key", owm);
                    if (weather_) weather_->SetApiKey(owm);
                    configured++;
                    ESP_LOGI(TAG, "OWM API key saved");
                }

                std::string n2yo = props["n2yo_key"].value<std::string>();
                if (!n2yo.empty()) {
                    sg_settings.SetString("n2yo_key", n2yo);
                    if (sky_tracker_) sky_tracker_->SetN2yoApiKey(n2yo);
                    configured++;
                    ESP_LOGI(TAG, "N2YO API key saved");
                }

                std::string google = props["google_key"].value<std::string>();
                if (!google.empty()) {
                    if (wifi_geo_) wifi_geo_->SetGoogleApiKey(google.c_str());
                    configured++;
                    ESP_LOGI(TAG, "Google API key configured");
                }

                std::string nina = props["nina_url"].value<std::string>();
                if (!nina.empty()) {
                    sg_settings.SetString("nina_url", nina);
                    configured++;
                    ESP_LOGI(TAG, "NINA URL saved: %s", nina.c_str());
                }

                std::string phd2 = props["phd2_url"].value<std::string>();
                if (!phd2.empty()) {
                    sg_settings.SetString("phd2_url", phd2);
                    configured++;
                    ESP_LOGI(TAG, "PHD2 URL saved: %s", phd2.c_str());
                }

                std::string stel = props["stellarium_url"].value<std::string>();
                if (!stel.empty()) {
                    sg_settings.SetString("stellarium_url", stel);
                    configured++;
                    ESP_LOGI(TAG, "Stellarium URL saved: %s", stel.c_str());
                }

                std::string indi = props["indi_url"].value<std::string>();
                if (!indi.empty()) {
                    sg_settings.SetString("indi_url", indi);
                    configured++;
                    ESP_LOGI(TAG, "INDI URL saved: %s", indi.c_str());
                }

                char buf[64];
                snprintf(buf, sizeof(buf), "%d configurazione/i salvate", configured);
                return std::string(buf);
            });

        // --- device.weather.forecast ---
        mcp.AddTool("device.weather.forecast",
            "Previsioni meteo prossime 6 ore: nuvole, vento, temperatura per pianificazione osservazioni",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                if (!weather_) return false;
                if (!weather_->HasData()) {
                    weather_->StartFetchTask();
                    return std::string("Fetch in corso, riprova tra qualche secondo");
                }
                return weather_->GetForecastText();
            });

        // --- device.radar.aircraft ---
        mcp.AddTool("device.radar.aircraft",
            "Aerei in zona (OpenSky): callsign, distanza, direzione, altitudine",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                if (!sky_tracker_) return false;
                if (!sky_tracker_->HasFlights()) {
                    return std::string("Dati non disponibili, fetch in corso");
                }
                return sky_tracker_->GetFlightsText();
            });

        // --- device.radar.satellites ---
        mcp.AddTool("device.radar.satellites",
            "Passaggi satelliti visibili (N2YO): ISS e altri, orario, elevazione, magnitudine",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                if (!sky_tracker_) return false;
                if (!sky_tracker_->HasSatellites()) {
                    return std::string("Dati non disponibili, fetch in corso");
                }
                return sky_tracker_->GetSatellitesText();
            });

        // --- device.telescope.status ---
        mcp.AddTool("device.telescope.status",
            "Stato telescopio ASCOM Alpaca: RA, DEC, alt, az, tracking, pier side, slewing, park",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                if (!sg_display_ || sg_display_->GetAlpacaStatus().last_update == 0) {
                    return std::string("Telescopio non connesso. Configura ASCOM Alpaca URL nella WebUI.");
                }
                const auto& s = sg_display_->GetAlpacaStatus();
                char buf[320];
                snprintf(buf, sizeof(buf),
                    "Stato=%s, RA=%.4fh (%.6f°), DEC=%.4f°, "
                    "Alt=%.1f°, Az=%.1f°, Tracking=%s, "
                    "PierSide=%s, Slewing=%s, AtPark=%s",
                    s.at_park ? "PARK" : s.slewing ? "SLEWING" : s.tracking ? "TRACKING" : "IDLE",
                    s.ra, s.ra * 15.0, s.dec,
                    s.alt, s.az,
                    s.tracking ? "ON" : "OFF",
                    s.pier_side == 0 ? "East" : s.pier_side == 1 ? "West" : "N/A",
                    s.slewing ? "SI" : "NO",
                    s.at_park ? "SI" : "NO");
                return std::string(buf);
            });

        // --- device.telescope.command ---
        mcp.AddTool("device.telescope.command",
            "Comanda telescopio ASCOM Alpaca: slew (RA/DEC), park, unpark, "
            "tracking on/off, abort, home. Per slew: action=slew, ra_hours='18.6156', dec_degrees='38.7836' (stringhe). "
            "Esempio: Vega ra=18.6156 dec=38.7836, M42 ra=5.59 dec=-5.45.",
            PropertyList({
                Property("action", kPropertyTypeString),
                Property("ra_hours", kPropertyTypeString, std::string("")),
                Property("dec_degrees", kPropertyTypeString, std::string("")),
            }),
            [this](const PropertyList& props) -> ReturnValue {
                Settings s("skyguard", false);
                std::string alpaca = s.GetString("alpaca_url", "");
                if (alpaca.empty()) {
                    return std::string("ASCOM Alpaca URL non configurato. Configura nella WebUI.");
                }

                std::string action = props["action"].value<std::string>();
                char url[256];
                char body[128];
                char resp[256];
                static int tx_id = 1;

                if (action == "slew") {
                    double ra = std::strtod(props["ra_hours"].value<std::string>().c_str(), nullptr);
                    double dec = std::strtod(props["dec_degrees"].value<std::string>().c_str(), nullptr);
                    snprintf(url, sizeof(url), "%s/api/v1/telescope/0/slewtocoordinatesasync", alpaca.c_str());
                    snprintf(body, sizeof(body), "ClientID=1&ClientTransactionID=%d&RightAscension=%.6f&Declination=%.6f", tx_id++, ra, dec);
                } else if (action == "park") {
                    snprintf(url, sizeof(url), "%s/api/v1/telescope/0/park", alpaca.c_str());
                    snprintf(body, sizeof(body), "ClientID=1&ClientTransactionID=%d", tx_id++);
                } else if (action == "unpark") {
                    snprintf(url, sizeof(url), "%s/api/v1/telescope/0/unpark", alpaca.c_str());
                    snprintf(body, sizeof(body), "ClientID=1&ClientTransactionID=%d", tx_id++);
                } else if (action == "abort") {
                    snprintf(url, sizeof(url), "%s/api/v1/telescope/0/abortslew", alpaca.c_str());
                    snprintf(body, sizeof(body), "ClientID=1&ClientTransactionID=%d", tx_id++);
                } else if (action == "tracking_on") {
                    snprintf(url, sizeof(url), "%s/api/v1/telescope/0/tracking", alpaca.c_str());
                    snprintf(body, sizeof(body), "ClientID=1&ClientTransactionID=%d&Tracking=true", tx_id++);
                } else if (action == "tracking_off") {
                    snprintf(url, sizeof(url), "%s/api/v1/telescope/0/tracking", alpaca.c_str());
                    snprintf(body, sizeof(body), "ClientID=1&ClientTransactionID=%d&Tracking=false", tx_id++);
                } else if (action == "home") {
                    snprintf(url, sizeof(url), "%s/api/v1/telescope/0/findhome", alpaca.c_str());
                    snprintf(body, sizeof(body), "ClientID=1&ClientTransactionID=%d", tx_id++);
                } else {
                    return std::string("Azione non valida. Usa: slew, park, unpark, abort, tracking_on, tracking_off, home");
                }

                ESP_LOGI(TAG, "Alpaca command: %s → %s", action.c_str(), url);
                bool ok = SkyGuardHttp::Put(url, body, resp, sizeof(resp), 10000);
                if (ok) {
                    char result[128];
                    snprintf(result, sizeof(result), "Comando %s inviato OK", action.c_str());
                    return std::string(result);
                }
                return std::string("Errore: comando " + action + " fallito. Verifica connessione Alpaca.");
            });

        // --- device.nina.command ---
        // NINA Advanced Sequencer HTTP API bridge
        mcp.AddTool("device.nina.command",
            "Controlla NINA Advanced Sequencer: status, start/stop sequenza, "
            "cattura singola, platesolve, center, autofocus. "
            "Richiede URL NINA configurato (es. http://192.168.1.100:1888). "
            "Per cattura: action=capture, exposure='10' (secondi), filter='L' (opzionale), gain='100' (opzionale). "
            "Per load_sequence: action=load_sequence, path='C:\\\\Sequences\\\\M42.json'.",
            PropertyList({
                Property("action", kPropertyTypeString),
                Property("exposure", kPropertyTypeString, std::string("")),
                Property("filter", kPropertyTypeString, std::string("")),
                Property("gain", kPropertyTypeString, std::string("")),
                Property("path", kPropertyTypeString, std::string("")),
            }),
            [this](const PropertyList& props) -> ReturnValue {
                Settings s("skyguard", false);
                std::string nina_url = s.GetString("nina_url", "");
                if (nina_url.empty()) {
                    return std::string("NINA URL non configurato. Usa device.config.api_keys con nina_url.");
                }

                std::string action = props["action"].value<std::string>();
                char url[512];
                char* resp = SkyGuardHttp::AllocBuffer(4096);
                if (!resp) return std::string("Errore allocazione memoria");

                bool ok = false;
                std::string result;

                if (action == "status") {
                    // Query multiple NINA endpoints for complete status
                    cJSON* status_json = cJSON_CreateObject();
                    // Camera info
                    snprintf(url, sizeof(url), "%s/api/v2/equipment/camera/info", nina_url.c_str());
                    ok = SkyGuardHttp::Get(url, resp, 4096, 3000);
                    if (ok) {
                        cJSON* cam = cJSON_Parse(resp);
                        if (cam) {
                            const char* name = cJSON_GetStringValue(cJSON_GetObjectItem(cam, "Name"));
                            cJSON* connected = cJSON_GetObjectItem(cam, "Connected");
                            cJSON_AddStringToObject(status_json, "camera", name ? name : "N/A");
                            cJSON_AddBoolToObject(status_json, "connected", connected && cJSON_IsTrue(connected));
                            cJSON* temp_item = cJSON_GetObjectItem(cam, "Temperature");
                            if (temp_item) cJSON_AddNumberToObject(status_json, "sensor_temp", temp_item->valuedouble);
                            cJSON_Delete(cam);
                        }
                    }
                    // Imaging status
                    snprintf(url, sizeof(url), "%s/api/v2/imaging/status", nina_url.c_str());
                    if (SkyGuardHttp::Get(url, resp, 4096, 3000)) {
                        cJSON* img = cJSON_Parse(resp);
                        if (img) {
                            const char* st = cJSON_GetStringValue(cJSON_GetObjectItem(img, "Status"));
                            cJSON_AddStringToObject(status_json, "status", st ? st : "Idle");
                            cJSON* prog = cJSON_GetObjectItem(img, "Progress");
                            if (prog) cJSON_AddNumberToObject(status_json, "progress", prog->valuedouble * 100);
                            const char* filt = cJSON_GetStringValue(cJSON_GetObjectItem(img, "Filter"));
                            if (filt) cJSON_AddStringToObject(status_json, "filter", filt);
                            cJSON* exp = cJSON_GetObjectItem(img, "ExposureTime");
                            if (exp) cJSON_AddNumberToObject(status_json, "exposure", exp->valuedouble);
                            cJSON* hfr = cJSON_GetObjectItem(img, "HFR");
                            if (hfr) cJSON_AddNumberToObject(status_json, "hfr", hfr->valuedouble);
                            cJSON* stars = cJSON_GetObjectItem(img, "Stars");
                            if (stars) cJSON_AddNumberToObject(status_json, "stars", stars->valueint);
                            cJSON_Delete(img);
                        }
                    } else {
                        cJSON_AddStringToObject(status_json, "status", "Idle");
                    }
                    char* json_str = cJSON_PrintUnformatted(status_json);
                    result = json_str ? std::string(json_str) : "{\"error\":\"timeout\",\"message\":\"NINA non raggiungibile\"}";
                    free(json_str);
                    cJSON_Delete(status_json);
                    ok = true;
                } else if (action == "start_sequence") {
                    snprintf(url, sizeof(url), "%s/api/v2/sequence/start", nina_url.c_str());
                    ok = SkyGuardHttp::Post(url, "{}", resp, 4096, 10000);
                    result = ok ? "Sequenza avviata" : "Errore avvio sequenza";
                } else if (action == "stop_sequence") {
                    snprintf(url, sizeof(url), "%s/api/v2/sequence/stop", nina_url.c_str());
                    ok = SkyGuardHttp::Post(url, "{}", resp, 4096, 10000);
                    result = ok ? "Sequenza fermata" : "Errore stop sequenza";
                } else if (action == "capture") {
                    std::string exposure = props["exposure"].value<std::string>();
                    std::string filter = props["filter"].value<std::string>();
                    std::string gain = props["gain"].value<std::string>();
                    if (exposure.empty()) exposure = "5";
                    cJSON* body = cJSON_CreateObject();
                    cJSON_AddNumberToObject(body, "Duration", std::strtod(exposure.c_str(), nullptr));
                    if (!filter.empty()) cJSON_AddStringToObject(body, "Filter", filter.c_str());
                    if (!gain.empty()) cJSON_AddNumberToObject(body, "Gain", std::strtod(gain.c_str(), nullptr));
                    char* json = cJSON_PrintUnformatted(body);
                    snprintf(url, sizeof(url), "%s/api/v2/imaging/capture", nina_url.c_str());
                    ok = SkyGuardHttp::Post(url, json, resp, 4096, 30000);
                    char buf[128];
                    snprintf(buf, sizeof(buf), "Cattura %ss %s%s: %s",
                        exposure.c_str(),
                        filter.empty() ? "" : filter.c_str(),
                        filter.empty() ? "" : " ",
                        ok ? "OK" : "FALLITA");
                    result = buf;
                    free(json);
                    cJSON_Delete(body);
                } else if (action == "platesolve") {
                    snprintf(url, sizeof(url), "%s/api/v2/platesolve/solve", nina_url.c_str());
                    ok = SkyGuardHttp::Post(url, "{}", resp, 4096, 60000);
                    if (ok) {
                        cJSON* root = cJSON_Parse(resp);
                        if (root) {
                            cJSON* ra_j = cJSON_GetObjectItem(root, "RaJ2000");
                            cJSON* dec_j = cJSON_GetObjectItem(root, "DecJ2000");
                            cJSON* success = cJSON_GetObjectItem(root, "Success");
                            char buf[128];
                            snprintf(buf, sizeof(buf), "Platesolve %s — RA=%.4f° DEC=%.4f°",
                                (success && cJSON_IsTrue(success)) ? "OK" : "FALLITO",
                                ra_j ? ra_j->valuedouble : 0.0,
                                dec_j ? dec_j->valuedouble : 0.0);
                            result = buf;
                            cJSON_Delete(root);
                        } else {
                            result = std::string("Risposta: ") + resp;
                        }
                    }
                } else if (action == "center") {
                    snprintf(url, sizeof(url), "%s/api/v2/platesolve/center", nina_url.c_str());
                    ok = SkyGuardHttp::Post(url, "{}", resp, 4096, 120000);
                    result = ok ? "Center completato" : "Errore center";
                } else if (action == "autofocus") {
                    snprintf(url, sizeof(url), "%s/api/v2/autofocus/start", nina_url.c_str());
                    ok = SkyGuardHttp::Post(url, "{}", resp, 4096, 120000);
                    result = ok ? "Autofocus avviato" : "Errore autofocus";
                } else if (action == "load_sequence") {
                    std::string path = props["path"].value<std::string>();
                    if (path.empty()) { free(resp); return std::string("Parametro 'path' mancante"); }
                    cJSON* body = cJSON_CreateObject();
                    cJSON_AddStringToObject(body, "FilePath", path.c_str());
                    char* json = cJSON_PrintUnformatted(body);
                    snprintf(url, sizeof(url), "%s/api/v2/sequence/load", nina_url.c_str());
                    ok = SkyGuardHttp::Post(url, json, resp, 4096, 10000);
                    result = ok ? ("Sequenza caricata: " + path) : "Errore caricamento sequenza";
                    free(json);
                    cJSON_Delete(body);
                } else {
                    free(resp);
                    return std::string("Azione non valida. Usa: status, start_sequence, stop_sequence, "
                                       "capture, platesolve, center, autofocus, load_sequence");
                }

                if (!ok && result.empty()) result = "Errore HTTP. Verifica connessione NINA.";
                free(resp);
                return result;
            });

        // --- device.phd2.command ---
        // PHD2 JSON-RPC bridge via HTTP (PHD2 v2.6.11+ has HTTP server)
        mcp.AddTool("device.phd2.command",
            "Controlla PHD2 autoguida: status, start/stop guida, dither, pausa. "
            "Richiede URL PHD2 configurato (es. http://192.168.1.100:4400). "
            "PHD2 v2.6.11+ con server HTTP attivo.",
            PropertyList({
                Property("action", kPropertyTypeString),
                Property("settle_pixels", kPropertyTypeString, std::string("1.5")),
                Property("settle_time", kPropertyTypeString, std::string("10")),
                Property("settle_timeout", kPropertyTypeString, std::string("60")),
                Property("dither_pixels", kPropertyTypeString, std::string("5")),
            }),
            [this](const PropertyList& props) -> ReturnValue {
                Settings s("skyguard", false);
                std::string phd2_url = s.GetString("phd2_url", "");
                if (phd2_url.empty()) {
                    return std::string("PHD2 URL non configurato. Usa device.config.api_keys con phd2_url.");
                }

                std::string action = props["action"].value<std::string>();
                char url[256];
                char resp[2048];
                static int rpc_id = 1;
                bool ok = false;
                std::string result;

                // PHD2 JSON-RPC over HTTP: POST to /json-rpc
                auto phd2_rpc = [&](const char* method, cJSON* params_arr) -> bool {
                    cJSON* rpc = cJSON_CreateObject();
                    cJSON_AddStringToObject(rpc, "jsonrpc", "2.0");
                    cJSON_AddStringToObject(rpc, "method", method);
                    if (params_arr) {
                        cJSON_AddItemToObject(rpc, "params", params_arr);
                    } else {
                        cJSON_AddArrayToObject(rpc, "params");
                    }
                    cJSON_AddNumberToObject(rpc, "id", rpc_id++);
                    char* json = cJSON_PrintUnformatted(rpc);
                    snprintf(url, sizeof(url), "%s/json-rpc", phd2_url.c_str());
                    bool r = SkyGuardHttp::Post(url, json, resp, sizeof(resp), 15000);
                    free(json);
                    cJSON_Delete(rpc);
                    return r;
                };

                if (action == "status") {
                    cJSON* status_json = cJSON_CreateObject();
                    // Get app state
                    ok = phd2_rpc("get_app_state", nullptr);
                    if (ok) {
                        cJSON* root = cJSON_Parse(resp);
                        if (root) {
                            cJSON* res = cJSON_GetObjectItem(root, "result");
                            const char* state = (res && res->valuestring) ? res->valuestring : "Unknown";
                            cJSON_AddStringToObject(status_json, "status", state);
                            cJSON_Delete(root);
                        }
                    } else {
                        cJSON_Delete(status_json);
                        return std::string("{\"error\":\"timeout\",\"message\":\"PHD2 non raggiungibile\"}");
                    }
                    // Get guide stats (RMS)
                    if (phd2_rpc("get_guide_stats", nullptr)) {
                        cJSON* gs = cJSON_Parse(resp);
                        if (gs) {
                            cJSON* res = cJSON_GetObjectItem(gs, "result");
                            if (res) {
                                cJSON* rms_ra = cJSON_GetObjectItem(res, "rms_ra");
                                cJSON* rms_dec = cJSON_GetObjectItem(res, "rms_dec");
                                cJSON* rms_tot = cJSON_GetObjectItem(res, "rms_tot");
                                if (rms_ra) cJSON_AddNumberToObject(status_json, "rms_ra", rms_ra->valuedouble);
                                if (rms_dec) cJSON_AddNumberToObject(status_json, "rms_dec", rms_dec->valuedouble);
                                if (rms_tot) cJSON_AddNumberToObject(status_json, "rms_total", rms_tot->valuedouble);
                            }
                            cJSON_Delete(gs);
                        }
                    }
                    // Get pixel scale
                    if (phd2_rpc("get_pixel_scale", nullptr)) {
                        cJSON* ps = cJSON_Parse(resp);
                        if (ps) {
                            cJSON* ps_r = cJSON_GetObjectItem(ps, "result");
                            if (ps_r && cJSON_IsNumber(ps_r))
                                cJSON_AddNumberToObject(status_json, "pixel_scale", ps_r->valuedouble);
                            cJSON_Delete(ps);
                        }
                    }
                    char* json_str = cJSON_PrintUnformatted(status_json);
                    result = json_str ? std::string(json_str) : "{}";
                    free(json_str);
                    cJSON_Delete(status_json);
                    ok = true;
                } else if (action == "start_guide" || action == "guide") {
                    float settle_px = std::strtof(props["settle_pixels"].value<std::string>().c_str(), nullptr);
                    float settle_t = std::strtof(props["settle_time"].value<std::string>().c_str(), nullptr);
                    float settle_to = std::strtof(props["settle_timeout"].value<std::string>().c_str(), nullptr);
                    cJSON* params = cJSON_CreateArray();
                    cJSON* settle = cJSON_CreateObject();
                    cJSON_AddNumberToObject(settle, "pixels", settle_px);
                    cJSON_AddNumberToObject(settle, "time", settle_t);
                    cJSON_AddNumberToObject(settle, "timeout", settle_to);
                    cJSON_AddItemToArray(params, settle);
                    cJSON_AddItemToArray(params, cJSON_CreateFalse());  // recalibrate = false
                    ok = phd2_rpc("guide", params);
                    result = ok ? "Guida avviata" : "Errore avvio guida";
                } else if (action == "stop_guide" || action == "stop") {
                    ok = phd2_rpc("stop_capture", nullptr);
                    result = ok ? "Guida fermata" : "Errore stop guida";
                } else if (action == "dither") {
                    float dither_px = std::strtof(props["dither_pixels"].value<std::string>().c_str(), nullptr);
                    float settle_px = std::strtof(props["settle_pixels"].value<std::string>().c_str(), nullptr);
                    float settle_t = std::strtof(props["settle_time"].value<std::string>().c_str(), nullptr);
                    float settle_to = std::strtof(props["settle_timeout"].value<std::string>().c_str(), nullptr);
                    cJSON* params = cJSON_CreateArray();
                    cJSON_AddItemToArray(params, cJSON_CreateNumber(dither_px));
                    cJSON_AddItemToArray(params, cJSON_CreateFalse());  // raOnly = false
                    cJSON* settle = cJSON_CreateObject();
                    cJSON_AddNumberToObject(settle, "pixels", settle_px);
                    cJSON_AddNumberToObject(settle, "time", settle_t);
                    cJSON_AddNumberToObject(settle, "timeout", settle_to);
                    cJSON_AddItemToArray(params, settle);
                    ok = phd2_rpc("dither", params);
                    result = ok ? "Dither avviato" : "Errore dither";
                } else if (action == "pause") {
                    cJSON* params = cJSON_CreateArray();
                    cJSON_AddItemToArray(params, cJSON_CreateTrue());  // pause = true
                    ok = phd2_rpc("set_paused", params);
                    result = ok ? "Guida in pausa" : "Errore pausa";
                } else if (action == "resume") {
                    cJSON* params = cJSON_CreateArray();
                    cJSON_AddItemToArray(params, cJSON_CreateFalse());  // pause = false
                    ok = phd2_rpc("set_paused", params);
                    result = ok ? "Guida ripresa" : "Errore ripresa";
                } else if (action == "loop") {
                    ok = phd2_rpc("loop", nullptr);
                    result = ok ? "Looping avviato" : "Errore loop";
                } else {
                    return std::string("Azione non valida. Usa: status, start_guide, stop_guide, "
                                       "dither, pause, resume, loop");
                }

                if (!ok && result.empty()) result = "Errore HTTP. Verifica connessione PHD2.";
                return result;
            });

        // --- device.dew_heater ---
        // GPIO relay/PWM control for dew heater band
        mcp.AddTool("device.dew_heater",
            "Controlla fascia anticondensa (dew heater). Modi: off, on (potenza fissa), "
            "auto (accende se spread < soglia basandosi su AHT20). "
            "Configura GPIO e soglia con action=configure. "
            "GPIO va configurato prima dell'uso (default: nessuno).",
            PropertyList({
                Property("action", kPropertyTypeString),
                Property("power", kPropertyTypeString, std::string("100")),
                Property("threshold", kPropertyTypeString, std::string("3.0")),
                Property("gpio", kPropertyTypeString, std::string("")),
            }),
            [this](const PropertyList& props) -> ReturnValue {
                std::string action = props["action"].value<std::string>();

                if (action == "configure") {
                    std::string gpio_str = props["gpio"].value<std::string>();
                    std::string thresh_str = props["threshold"].value<std::string>();
                    if (!gpio_str.empty()) {
                        int pin = std::atoi(gpio_str.c_str());
                        if (pin < 0 || pin > 48) {
                            return std::string("GPIO non valido (0-48)");
                        }
                        dew_gpio_ = pin;
                        Settings s("skyguard", true);
                        s.SetInt("dew_gpio", pin);

                        // Configure LEDC PWM on this GPIO
                        ledc_timer_config_t timer_cfg = {
                            .speed_mode = LEDC_LOW_SPEED_MODE,
                            .duty_resolution = LEDC_TIMER_8_BIT,
                            .timer_num = LEDC_TIMER_1,  // Timer 0 = backlight
                            .freq_hz = 1000,
                            .clk_cfg = LEDC_AUTO_CLK,
                            .deconfigure = false,
                        };
                        ledc_timer_config(&timer_cfg);

                        ledc_channel_config_t ch_cfg = {
                            .gpio_num = pin,
                            .speed_mode = LEDC_LOW_SPEED_MODE,
                            .channel = dew_ledc_ch_,
                            .intr_type = LEDC_INTR_DISABLE,
                            .timer_sel = LEDC_TIMER_1,
                            .duty = 0,
                            .hpoint = 0,
                            .flags = { .output_invert = 0 },
                        };
                        ledc_channel_config(&ch_cfg);
                        ESP_LOGI(TAG, "Dew heater configured on GPIO %d", pin);
                    }
                    if (!thresh_str.empty()) {
                        dew_threshold_ = std::strtof(thresh_str.c_str(), nullptr);
                        Settings s("skyguard", true);
                        s.SetString("dew_threshold", thresh_str);
                    }
                    char buf[128];
                    snprintf(buf, sizeof(buf), "Dew heater: GPIO=%d, soglia=%.1f°C",
                        dew_gpio_, dew_threshold_);
                    return std::string(buf);
                }

                if (dew_gpio_ < 0) {
                    return std::string("Dew heater non configurato. Usa action=configure, gpio='17'");
                }

                if (action == "status") {
                    float temp_val = 0, dew_val = 0, spread = 99;
                    if (aht20_ && aht20_validated_) {
                        aht20_->Measure();
                        temp_val = aht20_->GetTemperature() + temp_offset_;
                        dew_val = aht20_->GetDewPoint();
                        spread = temp_val - dew_val;
                    }
                    const char* status_str = dew_heater_active_ ? "on" : "off";
                    const char* mode_str = dew_mode_ == 0 ? "manual" : dew_mode_ == 1 ? "manual" : "auto";
                    char buf[256];
                    snprintf(buf, sizeof(buf),
                        "{\"status\":\"%s\",\"mode\":\"%s\",\"power_pct\":%d,"
                        "\"temp\":%.1f,\"dew_point\":%.1f,\"dew_margin\":%.1f,"
                        "\"threshold\":%.1f,\"gpio\":%d}",
                        status_str, mode_str, dew_power_,
                        temp_val, dew_val, spread,
                        dew_threshold_, dew_gpio_);
                    return std::string(buf);
                } else if (action == "on") {
                    std::string pwr = props["power"].value<std::string>();
                    dew_power_ = std::atoi(pwr.c_str());
                    if (dew_power_ < 0) dew_power_ = 0;
                    if (dew_power_ > 100) dew_power_ = 100;
                    dew_mode_ = 1;
                    dew_heater_active_ = true;
                    int duty = (dew_power_ * 255) / 100;
                    ledc_set_duty(LEDC_LOW_SPEED_MODE, dew_ledc_ch_, duty);
                    ledc_update_duty(LEDC_LOW_SPEED_MODE, dew_ledc_ch_);
                    char buf[64];
                    snprintf(buf, sizeof(buf), "Dew heater ON al %d%%", dew_power_);
                    return std::string(buf);
                } else if (action == "off") {
                    dew_mode_ = 0;
                    dew_heater_active_ = false;
                    ledc_set_duty(LEDC_LOW_SPEED_MODE, dew_ledc_ch_, 0);
                    ledc_update_duty(LEDC_LOW_SPEED_MODE, dew_ledc_ch_);
                    return std::string("Dew heater OFF");
                } else if (action == "auto") {
                    std::string pwr = props["power"].value<std::string>();
                    std::string thresh = props["threshold"].value<std::string>();
                    dew_power_ = std::atoi(pwr.c_str());
                    if (dew_power_ < 0) dew_power_ = 0;
                    if (dew_power_ > 100) dew_power_ = 100;
                    if (!thresh.empty()) dew_threshold_ = std::strtof(thresh.c_str(), nullptr);
                    dew_mode_ = 2;
                    // Auto logic runs in the periodic update timer
                    char buf[128];
                    snprintf(buf, sizeof(buf),
                        "Dew heater AUTO: potenza=%d%%, soglia=%.1f°C — si attiva quando spread < soglia",
                        dew_power_, dew_threshold_);
                    return std::string(buf);
                } else {
                    return std::string("Azione non valida. Usa: status, on, off, auto, configure");
                }
            });

        // --- device.stellarium.command ---
        mcp.AddTool("device.stellarium.command",
            "Controlla Stellarium Remote (planetario desktop) via HTTP API porta 8090. "
            "Azioni: status (info vista corrente), goto (punta oggetto per nome), "
            "search (cerca oggetto), fov (imposta campo visivo gradi), "
            "time (imposta data/ora simulazione). "
            "Richiede Stellarium in esecuzione con Remote Control plugin attivo.",
            PropertyList({
                Property("action", kPropertyTypeString, std::string("status")),
                Property("object_name", kPropertyTypeString, std::string("")),
                Property("fov_degrees", kPropertyTypeString, std::string("")),
                Property("datetime", kPropertyTypeString, std::string("")),
            }),
            [this](const PropertyList& props) -> ReturnValue {
                Settings sg("skyguard", false);
                std::string stel_url = sg.GetString("stellarium_url", "");
                if (stel_url.empty()) {
                    return std::string("Stellarium non configurato. Usa device.config.api_keys con stellarium_url (es. http://192.168.1.100:8090)");
                }

                std::string action = props["action"].value<std::string>();
                char url[256];
                char* resp = SkyGuardHttp::AllocBuffer(4096);
                if (!resp) return std::string("Errore: memoria insufficiente");
                std::string result;

                if (action == "status") {
                    // GET /api/main/status — returns current view info
                    snprintf(url, sizeof(url), "%s/api/main/status", stel_url.c_str());
                    if (SkyGuardHttp::Get(url, resp, 4096, 5000)) {
                        result = std::string("Stellarium status: ") + resp;
                    } else {
                        result = "Errore: Stellarium non raggiungibile su " + stel_url;
                    }
                } else if (action == "goto") {
                    // POST /api/main/focus — focus on object by name
                    std::string obj = props["object_name"].value<std::string>();
                    if (obj.empty()) { free(resp); return std::string("Specifica object_name (es. M31, Jupiter, Vega)"); }
                    snprintf(url, sizeof(url), "%s/api/main/focus", stel_url.c_str());
                    char body[128];
                    snprintf(body, sizeof(body), "target=%s", obj.c_str());
                    if (SkyGuardHttp::Post(url, body, resp, 4096, 5000)) {
                        result = "Stellarium puntato su: " + obj;
                    } else {
                        result = "Errore goto " + obj;
                    }
                } else if (action == "search") {
                    // GET /api/objects/find — search for object
                    std::string obj = props["object_name"].value<std::string>();
                    if (obj.empty()) { free(resp); return std::string("Specifica object_name per la ricerca"); }
                    snprintf(url, sizeof(url), "%s/api/objects/find?str=%s", stel_url.c_str(), obj.c_str());
                    if (SkyGuardHttp::Get(url, resp, 4096, 5000)) {
                        result = std::string("Risultati ricerca: ") + resp;
                    } else {
                        result = "Ricerca fallita";
                    }
                } else if (action == "fov") {
                    // POST /api/main/fov — set field of view
                    std::string fov_str = props["fov_degrees"].value<std::string>();
                    double fov = fov_str.empty() ? 0 : std::strtod(fov_str.c_str(), nullptr);
                    if (fov <= 0) { free(resp); return std::string("Specifica fov_degrees (es. 5.0)"); }
                    snprintf(url, sizeof(url), "%s/api/main/fov", stel_url.c_str());
                    char body[64];
                    snprintf(body, sizeof(body), "fov=%.2f", fov);
                    SkyGuardHttp::Post(url, body, resp, 4096, 5000);
                    char msg[64]; snprintf(msg, sizeof(msg), "FOV impostato a %.1f gradi", fov);
                    result = msg;
                } else if (action == "time") {
                    // POST /api/main/time — set simulation time
                    std::string dt = props["datetime"].value<std::string>();
                    if (dt.empty()) { free(resp); return std::string("Specifica datetime (ISO 8601, es. 2026-03-15T22:00:00)"); }
                    snprintf(url, sizeof(url), "%s/api/main/time", stel_url.c_str());
                    char body[128];
                    snprintf(body, sizeof(body), "time=%s", dt.c_str());
                    SkyGuardHttp::Post(url, body, resp, 4096, 5000);
                    result = "Tempo simulazione impostato a: " + dt;
                } else {
                    free(resp);
                    return std::string("Azione non valida. Usa: status, goto, search, fov, time");
                }

                free(resp);
                return result;
            });

        // --- device.indi.command ---
        mcp.AddTool("device.indi.command",
            "Controlla strumenti astronomici via INDI Web Manager (Linux, porta 8624). "
            "Azioni: status (lista driver attivi), drivers (lista driver disponibili), "
            "start (avvia profilo/driver), stop (ferma driver), "
            "profiles (lista profili salvati), start_profile (avvia profilo per nome). "
            "Alternativa a ASCOM per setup Linux/Raspberry Pi.",
            PropertyList({
                Property("action", kPropertyTypeString, std::string("status")),
                Property("profile_name", kPropertyTypeString, std::string("")),
                Property("driver_name", kPropertyTypeString, std::string("")),
            }),
            [this](const PropertyList& props) -> ReturnValue {
                Settings sg("skyguard", false);
                std::string indi_url = sg.GetString("indi_url", "");
                if (indi_url.empty()) {
                    return std::string("INDI non configurato. Usa device.config.api_keys con indi_url (es. http://192.168.1.100:8624)");
                }

                std::string action = props["action"].value<std::string>();
                char url[256];
                char* resp = SkyGuardHttp::AllocBuffer(4096);
                if (!resp) return std::string("Errore: memoria insufficiente");
                std::string result;

                if (action == "status") {
                    // GET /api/server/status — INDI server status + running drivers
                    snprintf(url, sizeof(url), "%s/api/server/status", indi_url.c_str());
                    if (SkyGuardHttp::Get(url, resp, 4096, 5000)) {
                        result = std::string("INDI status: ") + resp;
                    } else {
                        result = "Errore: INDI Web Manager non raggiungibile su " + indi_url;
                    }
                } else if (action == "drivers") {
                    // GET /api/server/drivers — available drivers
                    snprintf(url, sizeof(url), "%s/api/server/drivers", indi_url.c_str());
                    if (SkyGuardHttp::Get(url, resp, 4096, 5000)) {
                        result = std::string("Driver disponibili: ") + resp;
                    } else {
                        result = "Errore lettura driver";
                    }
                } else if (action == "profiles") {
                    // GET /api/profiles — saved equipment profiles
                    snprintf(url, sizeof(url), "%s/api/profiles", indi_url.c_str());
                    if (SkyGuardHttp::Get(url, resp, 4096, 5000)) {
                        result = std::string("Profili: ") + resp;
                    } else {
                        result = "Errore lettura profili";
                    }
                } else if (action == "start_profile") {
                    // POST /api/server/start — start profile
                    std::string prof = props["profile_name"].value<std::string>();
                    if (prof.empty()) { free(resp); return std::string("Specifica profile_name"); }
                    snprintf(url, sizeof(url), "%s/api/server/start/%s", indi_url.c_str(), prof.c_str());
                    if (SkyGuardHttp::Post(url, "", resp, 4096, 10000)) {
                        result = "Profilo INDI avviato: " + prof;
                    } else {
                        result = "Errore avvio profilo: " + prof;
                    }
                } else if (action == "stop") {
                    // POST /api/server/stop — stop INDI server
                    snprintf(url, sizeof(url), "%s/api/server/stop", indi_url.c_str());
                    if (SkyGuardHttp::Post(url, "", resp, 4096, 5000)) {
                        result = "INDI server fermato";
                    } else {
                        result = "Errore stop INDI";
                    }
                } else {
                    free(resp);
                    return std::string("Azione non valida. Usa: status, drivers, profiles, start_profile, stop");
                }

                free(resp);
                return result;
            });

        // device.astrometry.solve REMOVED — plate solving is done locally via NINA (ASTAP)

        ESP_LOGI(TAG, "Registered 16 SkyGuard MCP tools");
    }

    // =========================================================================
    // WebUI Status Provider — generates JSON for /api/status
    // =========================================================================
    static std::string ProvideWebUIStatus(void* ctx) {
        auto* board = (SkyGuardEliteBoard*)ctx;
        cJSON* root = cJSON_CreateObject();

        // --- SQM (TSL2591) ---
        if (board->tsl2591_) {
            cJSON_AddNumberToObject(root, "sqm", board->tsl2591_->GetMpsas());
            cJSON_AddNumberToObject(root, "nelm", board->tsl2591_->GetNelm());
            cJSON_AddNumberToObject(root, "bortle", board->tsl2591_->GetBortle());
            cJSON_AddNumberToObject(root, "lux", board->tsl2591_->GetLux());
            cJSON_AddNumberToObject(root, "ir", board->tsl2591_->GetIrRatio());
            cJSON_AddStringToObject(root, "sqm_quality", board->tsl2591_->GetQuality());
            cJSON_AddNumberToObject(root, "tsl", 1);
        } else {
            cJSON_AddNumberToObject(root, "tsl", 0);
        }

        // --- Spectral (AS7341) ---
        if (board->as7341_) {
            auto& r = board->as7341_->GetReading();
            cJSON* spec = cJSON_CreateArray();
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f1_415nm));
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f2_445nm));
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f3_480nm));
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f4_515nm));
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f5_555nm));
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f6_590nm));
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f7_630nm));
            cJSON_AddItemToArray(spec, cJSON_CreateNumber(r.f8_680nm));
            cJSON_AddItemToObject(root, "spectral", spec);
            cJSON_AddStringToObject(root, "lp_source", board->as7341_->GetLpSourceName());
            cJSON_AddNumberToObject(root, "sqi", board->as7341_->GetSpectralQuality());
            cJSON_AddNumberToObject(root, "as7", 1);
        } else {
            cJSON_AddNumberToObject(root, "as7", 0);
        }

        // --- Environment (AHT20 + calibration offsets) ---
        if (board->aht20_) {
            float temp = board->aht20_->GetTemperature() + board->temp_offset_;
            float hum = board->aht20_->GetHumidity() + board->hum_offset_;
            if (hum > 100.0f) hum = 100.0f;
            if (hum < 0.0f) hum = 0.0f;
            float dew = board->aht20_->GetDewPoint();
            cJSON_AddNumberToObject(root, "temp", temp);
            cJSON_AddNumberToObject(root, "hum", hum);
            cJSON_AddNumberToObject(root, "dew", dew);
            cJSON_AddNumberToObject(root, "spread", temp - dew);
            cJSON_AddBoolToObject(root, "condensation", board->aht20_->GetCondensationRisk());
            cJSON_AddNumberToObject(root, "aht", 1);
        } else {
            cJSON_AddNumberToObject(root, "aht", 0);
        }

        // --- GPS / Position (centralized) ---
        board->UpdatePosition();
        cJSON_AddBoolToObject(root, "gps_ok", board->gps_ && board->gps_->HasFix());
        cJSON_AddNumberToObject(root, "lat", board->pos_lat_);
        cJSON_AddNumberToObject(root, "lon", board->pos_lon_);
        cJSON_AddNumberToObject(root, "gps_alt", board->pos_alt_);
        cJSON_AddNumberToObject(root, "gps_sats", board->pos_gps_sats_);
        cJSON_AddStringToObject(root, "gps_source", board->pos_source_);

        // --- Moon & Twilight (computed from centralized position) ---
        float lat = board->pos_lat_, lon = board->pos_lon_;
        {
            double jd = board->sg_display_ ? board->sg_display_->GetCurrentJD() : 2460000.0;
            double jd0 = board->sg_display_ ? board->sg_display_->GetCurrentJD0() : jd;

            auto moon = AstroCalc::moonPhase(jd);
            cJSON_AddStringToObject(root, "moon_phase", moon.phaseName);
            cJSON_AddNumberToObject(root, "moon_illum", moon.illumination * 100.0);
            cJSON_AddNumberToObject(root, "moon_age", moon.age);

            auto lunar_pos = AstroCalc::lunarPosition(jd, lat, lon);
            cJSON_AddNumberToObject(root, "moon_alt", lunar_pos.altitude);

            auto tw = AstroCalc::twilightTimes(jd0, lat, lon);
            char buf[8];
            int ss_h = (int)tw.sunset;
            int ss_m = (int)((tw.sunset - ss_h) * 60);
            snprintf(buf, sizeof(buf), "%02d:%02d", ss_h, ss_m);
            cJSON_AddStringToObject(root, "sunset", buf);
            int ad_h = (int)tw.astronomicalDusk;
            int ad_m = (int)((tw.astronomicalDusk - ad_h) * 60);
            snprintf(buf, sizeof(buf), "%02d:%02d", ad_h, ad_m);
            cJSON_AddStringToObject(root, "astro_dark", buf);
        }

        // --- Weather forecast (hourly + daily) ---
        if (board->weather_ && board->weather_->HasData()) {
            auto fc = board->weather_->GetForecast();
            // Hourly (5 entries)
            cJSON* wx = cJSON_CreateArray();
            for (int i = 0; i < fc.count && i < 5; i++) {
                cJSON* e = cJSON_CreateObject();
                cJSON_AddStringToObject(e, "time", fc.entries[i].time_str);
                cJSON_AddNumberToObject(e, "temp", fc.entries[i].temp);
                cJSON_AddNumberToObject(e, "wind", fc.entries[i].wind_speed);
                cJSON_AddNumberToObject(e, "clouds", fc.entries[i].clouds);
                cJSON_AddStringToObject(e, "desc", fc.entries[i].description);
                cJSON_AddItemToArray(wx, e);
            }
            cJSON_AddItemToObject(root, "weather", wx);
            // Visibility from first entry
            if (fc.count > 0) {
                char vis_buf[16];
                float vis_km = fc.entries[0].visibility / 1000.0f;
                snprintf(vis_buf, sizeof(vis_buf), "%.1f km", vis_km);
                cJSON_AddStringToObject(root, "visibility", vis_buf);
            }
            // Daily (5 entries)
            cJSON* wd = cJSON_CreateArray();
            for (int i = 0; i < fc.daily_count && i < 5; i++) {
                cJSON* e = cJSON_CreateObject();
                cJSON_AddStringToObject(e, "day", fc.daily[i].day_str);
                cJSON_AddNumberToObject(e, "tmin", fc.daily[i].temp_min);
                cJSON_AddNumberToObject(e, "tmax", fc.daily[i].temp_max);
                cJSON_AddNumberToObject(e, "wind", fc.daily[i].wind_max);
                cJSON_AddNumberToObject(e, "clouds", fc.daily[i].clouds_avg);
                cJSON_AddStringToObject(e, "desc", fc.daily[i].description);
                cJSON_AddItemToArray(wd, e);
            }
            cJSON_AddItemToObject(root, "weather_daily", wd);
            // Verdict — same logic as display
            int n = fc.count < 5 ? fc.count : 5;
            float avg_clouds = 0, avg_wind = 0, avg_hum = 0, total_rain = 0;
            for (int i = 0; i < n; i++) {
                avg_clouds += fc.entries[i].clouds;
                avg_wind += fc.entries[i].wind_speed;
                avg_hum += fc.entries[i].humidity;
                total_rain += fc.entries[i].rain_3h + fc.entries[i].snow_3h;
            }
            if (n > 0) { avg_clouds /= n; avg_wind /= n; avg_hum /= n; }
            const char* verdict;
            if (total_rain > 0.5f) verdict = "PIOGGIA PREVISTA";
            else if (avg_clouds > 50) verdict = "NON FAVOREVOLE";
            else if (avg_clouds > 30) verdict = "PARZIALE";
            else if (avg_wind > 10) verdict = "VENTO FORTE";
            else verdict = "CIELO FAVOREVOLE";
            cJSON_AddStringToObject(root, "wx_verdict", verdict);
        }

        // --- Flights ---
        if (board->sky_tracker_ && board->sky_tracker_->HasFlights()) {
            auto fd = board->sky_tracker_->GetFlights();
            cJSON* fl = cJSON_CreateArray();
            for (int i = 0; i < fd.count && i < 8; i++) {
                cJSON* f = cJSON_CreateObject();
                cJSON_AddStringToObject(f, "cs", fd.flights[i].callsign);
                cJSON_AddStringToObject(f, "dir", SkyGuardSkyTracker::BearingToCompass(fd.flights[i].bearing));
                cJSON_AddNumberToObject(f, "dist", fd.flights[i].distance_km);
                cJSON_AddNumberToObject(f, "fl", (int)(fd.flights[i].altitude_m / 30.48));
                cJSON_AddStringToObject(f, "type", SkyGuardSkyTracker::IdentifyAircraftType(fd.flights[i].callsign));
                cJSON_AddItemToArray(fl, f);
            }
            cJSON_AddItemToObject(root, "flights", fl);
        } else {
            cJSON_AddItemToObject(root, "flights", cJSON_CreateArray());
        }

        // --- Satellites ---
        if (board->sky_tracker_ && board->sky_tracker_->HasSatellites()) {
            auto sd = board->sky_tracker_->GetSatellites();
            cJSON* sl = cJSON_CreateArray();
            for (int i = 0; i < sd.count && i < 6; i++) {
                cJSON* s = cJSON_CreateObject();
                cJSON_AddStringToObject(s, "name", sd.passes[i].name);
                char tbuf[8];
                snprintf(tbuf, sizeof(tbuf), "%02d:%02d", sd.passes[i].start_hour, sd.passes[i].start_min);
                cJSON_AddStringToObject(s, "time", tbuf);
                cJSON_AddNumberToObject(s, "elev", sd.passes[i].max_elevation);
                cJSON_AddNumberToObject(s, "mag", sd.passes[i].magnitude);
                cJSON_AddNumberToObject(s, "dur", sd.passes[i].duration_sec / 60);
                cJSON_AddItemToArray(sl, s);
            }
            cJSON_AddItemToObject(root, "satellites", sl);
        } else {
            cJSON_AddItemToObject(root, "satellites", cJSON_CreateArray());
        }

        // --- System info ---
        // IP address
        esp_netif_t* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
        if (netif) {
            esp_netif_ip_info_t ip_info;
            if (esp_netif_get_ip_info(netif, &ip_info) == ESP_OK) {
                char ip_str[16];
                snprintf(ip_str, sizeof(ip_str), IPSTR, IP2STR(&ip_info.ip));
                cJSON_AddStringToObject(root, "ip", ip_str);
            }
        }

        // MAC
        uint8_t mac[6];
        if (esp_wifi_get_mac(WIFI_IF_STA, mac) == ESP_OK) {
            char mac_str[18];
            snprintf(mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
            cJSON_AddStringToObject(root, "mac", mac_str);
        }

        // RSSI
        wifi_ap_record_t ap_info;
        if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
            cJSON_AddNumberToObject(root, "rssi", ap_info.rssi);
        }

        // Uptime & heap
        cJSON_AddNumberToObject(root, "uptime", (uint32_t)(esp_timer_get_time() / 1000000));
        cJSON_AddNumberToObject(root, "heap", esp_get_free_heap_size());

        // --- Telescope / ASCOM Alpaca ---
        if (board->sg_display_ && board->sg_display_->GetAlpacaStatus().last_update > 0) {
            const auto& as = board->sg_display_->GetAlpacaStatus();
            const char* state = as.at_park ? "PARK" : as.slewing ? "SLEWING" :
                                as.tracking ? "TRACKING" : "IDLE";
            cJSON_AddStringToObject(root, "scope_status", state);
            char ra_str[16], dec_str[16];
            snprintf(ra_str, sizeof(ra_str), "%.4fh", as.ra);
            snprintf(dec_str, sizeof(dec_str), "%.4f°", as.dec);
            cJSON_AddStringToObject(root, "scope_ra", ra_str);
            cJSON_AddStringToObject(root, "scope_dec", dec_str);
            cJSON_AddBoolToObject(root, "scope_tracking", as.tracking);
            cJSON_AddNumberToObject(root, "scope_alt", as.alt);
            cJSON_AddNumberToObject(root, "scope_az", as.az);
        }

        // --- Dew heater ---
        if (board->dew_gpio_ >= 0) {
            const char* dew_mode = board->dew_mode_ == 0 ? "OFF" :
                                   board->dew_mode_ == 1 ? "ON" : "AUTO";
            cJSON_AddStringToObject(root, "dew_mode", dew_mode);
            cJSON_AddBoolToObject(root, "dew_active", board->dew_heater_active_);
            cJSON_AddNumberToObject(root, "dew_power", board->dew_power_);
            cJSON_AddNumberToObject(root, "dew_gpio", board->dew_gpio_);
            cJSON_AddNumberToObject(root, "dew_threshold", board->dew_threshold_);
        }

        // Forecast sync status
        if (board->weather_) {
            uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000);
            uint32_t last_ms = board->weather_->LastPostTimeMs();
            if (last_ms > 0) {
                int ago_s = (now_ms - last_ms) / 1000;
                char ago_buf[32];
                if (ago_s < 60) snprintf(ago_buf, sizeof(ago_buf), "%ds fa", ago_s);
                else if (ago_s < 3600) snprintf(ago_buf, sizeof(ago_buf), "%dm fa", ago_s / 60);
                else snprintf(ago_buf, sizeof(ago_buf), "%dh %dm fa", ago_s / 3600, (ago_s % 3600) / 60);
                cJSON_AddStringToObject(root, "fc_last", ago_buf);
                // Next post in ~3h from last
                int next_s = 10800 - ago_s;
                if (next_s < 0) next_s = 0;
                char next_buf[32];
                if (next_s < 60) snprintf(next_buf, sizeof(next_buf), "tra %ds", next_s);
                else if (next_s < 3600) snprintf(next_buf, sizeof(next_buf), "tra %dm", next_s / 60);
                else snprintf(next_buf, sizeof(next_buf), "tra %dh %dm", next_s / 3600, (next_s % 3600) / 60);
                cJSON_AddStringToObject(root, "fc_next", next_buf);
            } else {
                cJSON_AddStringToObject(root, "fc_last", "Mai");
                cJSON_AddStringToObject(root, "fc_next", "In attesa GPS...");
            }
            cJSON_AddNumberToObject(root, "fc_slots", board->weather_->LastPostSlots());
            const char* fc_st = board->weather_->IsPostingForecast() ? "Fetching" :
                                board->weather_->LastPostOk() ? "OK" :
                                (last_ms > 0) ? "Errore" : "In attesa";
            cJSON_AddStringToObject(root, "fc_status", fc_st);
        }

        // Stellarium / INDI URLs and status for display cards
        {
            Settings sg("skyguard", false);
            std::string stel = sg.GetString("stellarium_url", "");
            if (!stel.empty()) cJSON_AddStringToObject(root, "stellarium_url", stel.c_str());
            std::string indi = sg.GetString("indi_url", "");
            if (!indi.empty()) cJSON_AddStringToObject(root, "indi_url", indi.c_str());
        }

        // INDI server status (from display's cached IndiStatus)
        if (board->sg_display_) {
            auto indi_s = board->sg_display_->GetIndiStatus();
            if (indi_s.configured) {
                cJSON_AddBoolToObject(root, "indi_running", indi_s.server_running);
                cJSON_AddStringToObject(root, "indi_profile", indi_s.active_profile);
                cJSON_AddNumberToObject(root, "indi_drivers", indi_s.driver_count);
            }
        }

        // Equipment from NVS (full schema)
        Settings eq_s("skyguard", false);
        std::string eq_json = eq_s.GetString("equipment", "");
        if (!eq_json.empty()) {
            cJSON* eq = cJSON_Parse(eq_json.c_str());
            if (eq) {
                cJSON_AddItemToObject(root, "equipment", eq);
            }
        }

        // Serialize
        char* json = cJSON_PrintUnformatted(root);
        std::string result(json);
        free(json);
        cJSON_Delete(root);
        return result;
    }

    void InitializeNetworkServices() {
        ESP_LOGI(TAG, "Initializing network data services (Weather + SkyTracker)");

        // Load API keys from NVS
        Settings sg_settings("skyguard", false);
        std::string owm_key = sg_settings.GetString("owm_key", "c52cc3a156e8d8556f1394fc999a3418");
        std::string n2yo_key = sg_settings.GetString("n2yo_key", "");

        // Weather — OpenWeatherMap forecast
        weather_ = new SkyGuardWeather();
        if (!owm_key.empty()) {
            weather_->SetApiKey(owm_key);
            ESP_LOGI(TAG, "OWM API key loaded (len=%d)", (int)owm_key.size());
        }
        if (!sqm_server_url_.empty()) {
            weather_->SetServerConfig(sqm_server_url_, sqm_api_key_);
        }

        // Sky Tracker — OpenSky + N2YO
        sky_tracker_ = new SkyGuardSkyTracker();
        if (!n2yo_key.empty()) {
            sky_tracker_->SetN2yoApiKey(n2yo_key);
            ESP_LOGI(TAG, "N2YO API key loaded (len=%d)", (int)n2yo_key.size());
        }

        // Set initial location from centralized resolver (GPS → NVS)
        // WiFi Google geolocation will be tried later from timer when WiFi connects
        UpdatePosition();
        weather_->SetLocation(pos_lat_, pos_lon_);
        sky_tracker_->SetLocation(pos_lat_, pos_lon_, pos_alt_);
        ESP_LOGI(TAG, "Initial position: %s (%.4f, %.4f)", pos_source_, pos_lat_, pos_lon_);

        // WebUI — created here, started later when WiFi connects (from timer tick)
        webui_ = new SkyGuardWebUI();
        webui_->SetStatusProvider(ProvideWebUIStatus, this);
        webui_->SetConfigSavedCallback(OnConfigSaved, this);

        // SQM server URL for posting readings
        sqm_server_url_ = sg_settings.GetString("sqm_server_url", "https://sqm.xamad.net");
        sqm_api_key_ = sg_settings.GetString("sqm_api_key", "24db809d-5e66-4aa5-8ff0-1db188c9e190");
        if (!sqm_server_url_.empty()) {
            ESP_LOGI(TAG, "SQM server URL: %s (key len=%d)", sqm_server_url_.c_str(), (int)sqm_api_key_.size());
        }

        // Alpaca URL for telescope control
        alpaca_url_ = sg_settings.GetString("alpaca_url", "");
        if (!alpaca_url_.empty()) {
            ESP_LOGI(TAG, "ASCOM Alpaca URL: %s", alpaca_url_.c_str());
        }

        // INDI URL for telescope control
        indi_url_ = sg_settings.GetString("indi_url", "");
        if (!indi_url_.empty()) {
            ESP_LOGI(TAG, "INDI Web Manager URL: %s", indi_url_.c_str());
        }

        // Load calibration values from NVS
        temp_offset_ = std::strtof(sg_settings.GetString("temp_offset", "-2.4").c_str(), nullptr);
        hum_offset_ = std::strtof(sg_settings.GetString("hum_offset", "0").c_str(), nullptr);
        lux_threshold_ = std::strtof(sg_settings.GetString("lux_threshold", "1.0").c_str(), nullptr);
        night_threshold_ = std::strtof(sg_settings.GetString("night_threshold", "10.0").c_str(), nullptr);
        ESP_LOGI(TAG, "Calibration: temp_off=%.1f hum_off=%.1f lux_thr=%.1f night_thr=%.1f",
                 temp_offset_, hum_offset_, lux_threshold_, night_threshold_);

        // Dew heater config from NVS
        dew_gpio_ = sg_settings.GetInt("dew_gpio", -1);
        dew_threshold_ = std::strtof(sg_settings.GetString("dew_threshold", "3.0").c_str(), nullptr);
        if (dew_gpio_ >= 0) {
            ESP_LOGI(TAG, "Dew heater GPIO=%d, threshold=%.1f°C", dew_gpio_, dew_threshold_);
        }

        ESP_LOGI(TAG, "Network services initialized (lat=%.4f, lon=%.4f, src=%s)", pos_lat_, pos_lon_, pos_source_);
    }

    bool sg_setup_done_ = false;
    bool boot_ready_fired_ = false;
    uint32_t ready_sound_tick_ = 0;  // Tick to play "SkyGuard AI is ready!" (0=disabled)
    std::string sqm_server_url_;
    std::string sqm_api_key_;
    std::string alpaca_url_;
    std::string indi_url_;
    std::string google_api_key_;
    bool geocode_done_ = false;
    bool equipment_synced_ = false;  // True after boot POST to server

    void CheckAlerts() {
        uint32_t now = tick_counter_;
        constexpr uint32_t COOLDOWN = 600; // 10 min between same alert type

        // --- SQM change ---
        if (tsl2591_ && tsl2591_->GetLux() < lux_threshold_) {
            float sqm = tsl2591_->GetMpsas();
            if (alerts_.initialized && alerts_.prev_sqm > 0 && (now - alerts_.last_sqm_alert) > COOLDOWN) {
                float delta = sqm - alerts_.prev_sqm;
                if (delta < -0.5f) {
                    // SQM dropped significantly (sky got worse)
                    char msg[128];
                    snprintf(msg, sizeof(msg),
                        "Avviso: la qualita del cielo e' peggiorata, SQM sceso da %.1f a %.1f MPSAS",
                        alerts_.prev_sqm, sqm);
                    Application::GetInstance().SendChatMessage(msg);
                    alerts_.last_sqm_alert = now;
                } else if (delta > 0.5f) {
                    char msg[128];
                    snprintf(msg, sizeof(msg),
                        "Buone notizie: il cielo e' migliorato, SQM salito da %.1f a %.1f MPSAS",
                        alerts_.prev_sqm, sqm);
                    Application::GetInstance().SendChatMessage(msg);
                    alerts_.last_sqm_alert = now;
                }
            }
            alerts_.prev_sqm = sqm;
        }

        // --- Wind change (from weather) ---
        if (weather_ && weather_->HasData()) {
            ForecastData fc = weather_->GetForecast();
            if (fc.count > 0) {
                float wind_kmh = fc.entries[0].wind_speed * 3.6f;
                int clouds = fc.entries[0].clouds;

                if (alerts_.initialized && (now - alerts_.last_wind_alert) > COOLDOWN) {
                    if (wind_kmh > 20 && alerts_.prev_wind <= 20) {
                        char msg[128];
                        snprintf(msg, sizeof(msg),
                            "Attenzione: il vento e' aumentato a %.0f km/h, valuta se parkare la montatura",
                            wind_kmh);
                        Application::GetInstance().SendChatMessage(msg);
                        alerts_.last_wind_alert = now;
                    } else if (wind_kmh > 35 && (now - alerts_.last_wind_alert) > 300) {
                        char msg[128];
                        snprintf(msg, sizeof(msg),
                            "Allarme vento forte: %.0f km/h! Consiglio di mettere in sicurezza l'attrezzatura",
                            wind_kmh);
                        Application::GetInstance().SendChatMessage(msg);
                        alerts_.last_wind_alert = now;
                    }
                }
                alerts_.prev_wind = wind_kmh;

                // --- Cloud change ---
                if (alerts_.initialized && alerts_.prev_clouds >= 0 && (now - alerts_.last_cloud_alert) > COOLDOWN) {
                    if (clouds > 60 && alerts_.prev_clouds <= 40) {
                        char msg[96];
                        snprintf(msg, sizeof(msg),
                            "Avviso: nuvole in aumento, copertura ora al %d%%", clouds);
                        Application::GetInstance().SendChatMessage(msg);
                        alerts_.last_cloud_alert = now;
                    } else if (clouds < 20 && alerts_.prev_clouds >= 50) {
                        char msg[96];
                        snprintf(msg, sizeof(msg),
                            "Il cielo si sta aprendo, nuvole scese al %d%%", clouds);
                        Application::GetInstance().SendChatMessage(msg);
                        alerts_.last_cloud_alert = now;
                    }
                }
                alerts_.prev_clouds = clouds;
            }
        }

        // --- Dew risk (from AHT20) ---
        if (aht20_) {
            float temp = aht20_->GetTemperature() + temp_offset_;
            float dew = aht20_->GetDewPoint();
            float spread = temp - dew;

            if (alerts_.initialized && (now - alerts_.last_dew_alert) > COOLDOWN) {
                if (spread < 2.0f && alerts_.prev_spread >= 2.0f) {
                    char msg[128];
                    snprintf(msg, sizeof(msg),
                        "Attenzione condensa: spread sceso a %.1f gradi, rischio rugiada sulle ottiche",
                        spread);
                    Application::GetInstance().SendChatMessage(msg);
                    alerts_.last_dew_alert = now;
                } else if (spread < 0.5f && (now - alerts_.last_dew_alert) > 300) {
                    Application::GetInstance().SendChatMessage(
                        "Allarme rugiada imminente! Spread quasi zero, attiva le fasce anticondensa");
                    alerts_.last_dew_alert = now;
                }
            }
            alerts_.prev_spread = spread;

            // --- Temperature drop ---
            if (alerts_.initialized && (now - alerts_.last_temp_alert) > COOLDOWN) {
                if (alerts_.prev_temp - temp > 3.0f) {
                    char msg[96];
                    snprintf(msg, sizeof(msg),
                        "La temperatura e' scesa rapidamente da %.0f a %.0f gradi",
                        alerts_.prev_temp, temp);
                    Application::GetInstance().SendChatMessage(msg);
                    alerts_.last_temp_alert = now;
                    alerts_.prev_temp = temp;
                }
            }
            // Update prev_temp slowly (every 5 min) to detect trend
            if (now % 300 == 0) alerts_.prev_temp = temp;
        }

        alerts_.initialized = true;
    }

    static void OnConfigSaved(void* ctx) {
        auto* board = (SkyGuardEliteBoard*)ctx;
        board->ReloadConfigFromNvs();
        // Sync equipment to server in background task
        xTaskCreate([](void* arg) {
            auto* b = (SkyGuardEliteBoard*)arg;
            b->PostEquipmentToServer();
            vTaskDelete(nullptr);
        }, "sg_eq_sync", 6144, board, 2, nullptr);
    }

    void ReloadConfigFromNvs() {
        Settings sg("skyguard", false);
        ESP_LOGI(TAG, "Reloading config from NVS (WebUI save)");

        // API keys
        std::string owm = sg.GetString("owm_key", "");
        if (!owm.empty() && weather_) {
            weather_->SetApiKey(owm);
            ESP_LOGI(TAG, "OWM key reloaded (len=%d)", (int)owm.size());
        }
        std::string n2yo = sg.GetString("n2yo_key", "");
        if (!n2yo.empty() && sky_tracker_) {
            sky_tracker_->SetN2yoApiKey(n2yo);
            ESP_LOGI(TAG, "N2YO key reloaded (len=%d)", (int)n2yo.size());
        }
        std::string google = sg.GetString("google_key", "");
        if (!google.empty() && wifi_geo_) {
            wifi_geo_->SetGoogleApiKey(google.c_str());
        }

        // SQM server URL + API key
        sqm_server_url_ = sg.GetString("sqm_server_url", "https://sqm.xamad.net");
        sqm_api_key_ = sg.GetString("sqm_api_key", "24db809d-5e66-4aa5-8ff0-1db188c9e190");

        // Alpaca URL
        alpaca_url_ = sg.GetString("alpaca_url", "");
        if (sg_display_) sg_display_->SetAlpacaUrl(alpaca_url_);

        // INDI URL
        indi_url_ = sg.GetString("indi_url", "");
        if (sg_display_) sg_display_->SetIndiUrl(indi_url_);

        // Calibration
        temp_offset_ = std::strtof(sg.GetString("temp_offset", "-2.4").c_str(), nullptr);
        hum_offset_ = std::strtof(sg.GetString("hum_offset", "0").c_str(), nullptr);
        lux_threshold_ = std::strtof(sg.GetString("lux_threshold", "1.0").c_str(), nullptr);
        night_threshold_ = std::strtof(sg.GetString("night_threshold", "10.0").c_str(), nullptr);
        if (sg_display_) sg_display_->SetCalibration(temp_offset_, hum_offset_);

        ESP_LOGI(TAG, "Config reloaded OK");
    }

    void FetchSatelliteImage() {
        ESP_LOGI(TAG, "Fetching satellite IR image...");
        uint8_t* gif_data = nullptr;
        int gif_len = 0;

        // Try IR color first, fallback to IR grayscale
        static const char* urls[] = {
            "https://neige.meteociel.fr/satellite/latest-ir-color.gif",
            "https://neige.meteociel.fr/satellite/latest-ir.gif"
        };

        bool ok = false;
        for (int i = 0; i < 2 && !ok; i++) {
            ok = SkyGuardHttp::GetBinary(urls[i], &gif_data, &gif_len, 512 * 1024, 20000);
            if (ok) {
                ESP_LOGI(TAG, "Satellite image downloaded: %d bytes from %s", gif_len, urls[i]);
            }
        }

        if (!ok || !gif_data) {
            ESP_LOGW(TAG, "Failed to download satellite image");
            return;
        }

        // Decode GIF first frame to RGB565 at display size
        GifDecode::GifFrame frame;
        if (GifDecode::DecodeFirstFrame(gif_data, gif_len, SkyGuardDisplay::METEO_W,
                                         SkyGuardDisplay::METEO_H, frame)) {
            ESP_LOGI(TAG, "GIF decoded: %dx%d -> %dx%d", frame.width, frame.height, frame.out_w, frame.out_h);
            sg_display_->SetSatelliteImage(frame.pixels, frame.out_w, frame.out_h);
        } else {
            ESP_LOGW(TAG, "GIF decode failed (len=%d)", gif_len);
        }

        free(gif_data);
    }

    void FetchGpsMap(float lat, float lon) {
        // Download a PNG map tile and pass raw PNG data to display
        // (display decodes it under LVGL lock to avoid SPIRAM cache issues)

        // OSM tile: convert lat/lon to tile coordinates at zoom 15 (street level)
        int zoom = 15;
        double n = (1 << zoom);
        double x_exact = (lon + 180.0) / 360.0 * n;
        double lat_rad = lat * M_PI / 180.0;
        double y_exact = (1.0 - log(tan(lat_rad) + 1.0 / cos(lat_rad)) / M_PI) / 2.0 * n;
        int xtile = (int)x_exact;
        int ytile = (int)y_exact;

        // Pixel position of user within the 256x256 tile
        int px_x = (int)((x_exact - xtile) * 256);
        int px_y = (int)((y_exact - ytile) * 256);

        char url[256];
        snprintf(url, sizeof(url), "https://tile.openstreetmap.org/%d/%d/%d.png",
                 zoom, xtile, ytile);

        ESP_LOGI(TAG, "Fetching GPS map tile for (%.4f, %.4f) tile(%d,%d) px(%d,%d): %s",
                 lat, lon, xtile, ytile, px_x, px_y, url);

        uint8_t* img_data = nullptr;
        int img_len = 0;
        if (!SkyGuardHttp::GetBinary(url, &img_data, &img_len, 128 * 1024, 20000)) {
            ESP_LOGW(TAG, "GPS map tile download failed");
            return;
        }

        // Verify it's a PNG
        if (img_len < 8 || img_data[0] != 0x89 || img_data[1] != 0x50) {
            ESP_LOGW(TAG, "Downloaded data is not PNG (first bytes: %02X %02X)", img_data[0], img_data[1]);
            free(img_data);
            return;
        }

        ESP_LOGI(TAG, "GPS map tile downloaded: %d bytes PNG", img_len);

        // Copy to SPIRAM for persistence (GetBinary may have used DRAM)
        uint8_t* png_copy = (uint8_t*)heap_caps_malloc(img_len, MALLOC_CAP_SPIRAM);
        if (png_copy) {
            memcpy(png_copy, img_data, img_len);
            free(img_data);
            sg_display_->SetGpsMapPng(png_copy, img_len, lat, lon, px_x, px_y);
        } else {
            sg_display_->SetGpsMapPng(img_data, img_len, lat, lon, px_x, px_y);
        }
    }

    void FetchReverseGeocode(float lat, float lon) {
        // Google Geocoding API — reverse geocode lat/lon to street address
        if (google_api_key_.empty()) {
            ESP_LOGW(TAG, "No Google API key for reverse geocoding");
            return;
        }

        char url[512];
        snprintf(url, sizeof(url),
            "https://maps.googleapis.com/maps/api/geocode/json"
            "?latlng=%.6f,%.6f&key=%s&language=it&result_type=street_address|route|locality",
            lat, lon, google_api_key_.c_str());

        const int buf_size = 4096;
        char* buf = SkyGuardHttp::AllocBuffer(buf_size);
        if (!buf) return;

        if (!SkyGuardHttp::Get(url, buf, buf_size, 15000)) {
            ESP_LOGW(TAG, "Reverse geocoding failed");
            free(buf);
            return;
        }

        // Parse JSON — extract first result's formatted_address
        cJSON* root = cJSON_Parse(buf);
        free(buf);
        if (!root) return;

        cJSON* results = cJSON_GetObjectItem(root, "results");
        if (results && cJSON_IsArray(results) && cJSON_GetArraySize(results) > 0) {
            cJSON* first = cJSON_GetArrayItem(results, 0);
            cJSON* addr = cJSON_GetObjectItem(first, "formatted_address");
            if (addr && addr->valuestring) {
                // Truncate to reasonable display length
                char short_addr[64];
                strncpy(short_addr, addr->valuestring, sizeof(short_addr) - 1);
                short_addr[sizeof(short_addr) - 1] = '\0';
                // Remove country suffix (", Italia" or ", Italy")
                char* comma = strrchr(short_addr, ',');
                if (comma) *comma = '\0';
                sg_display_->SetLocationName(short_addr);
                ESP_LOGI(TAG, "Reverse geocoded: %s", short_addr);
            }
        }
        cJSON_Delete(root);
    }

    void PollAlpaca() {
        if (alpaca_url_.empty()) return;

        SkyGuardDisplay::AlpacaStatus status;
        char resp[256];
        char url[256];

        // Helper: read a single Alpaca bool/double property
        auto getBool = [&](const char* prop) -> int {
            snprintf(url, sizeof(url), "%s/api/v1/telescope/0/%s?ClientID=1", alpaca_url_.c_str(), prop);
            if (SkyGuardHttp::Get(url, resp, sizeof(resp), 3000)) {
                cJSON* r = cJSON_Parse(resp);
                if (r) {
                    cJSON* v = cJSON_GetObjectItem(r, "Value");
                    int ret = (v && cJSON_IsBool(v)) ? (cJSON_IsTrue(v) ? 1 : 0) : -1;
                    cJSON_Delete(r);
                    return ret;
                }
            }
            return -1;
        };

        auto getDouble = [&](const char* prop) -> double {
            snprintf(url, sizeof(url), "%s/api/v1/telescope/0/%s?ClientID=1", alpaca_url_.c_str(), prop);
            if (SkyGuardHttp::Get(url, resp, sizeof(resp), 3000)) {
                cJSON* r = cJSON_Parse(resp);
                if (r) {
                    cJSON* v = cJSON_GetObjectItem(r, "Value");
                    double ret = (v && cJSON_IsNumber(v)) ? v->valuedouble : 0;
                    cJSON_Delete(r);
                    return ret;
                }
            }
            return 0;
        };

        auto getInt = [&](const char* prop) -> int {
            snprintf(url, sizeof(url), "%s/api/v1/telescope/0/%s?ClientID=1", alpaca_url_.c_str(), prop);
            if (SkyGuardHttp::Get(url, resp, sizeof(resp), 3000)) {
                cJSON* r = cJSON_Parse(resp);
                if (r) {
                    cJSON* v = cJSON_GetObjectItem(r, "Value");
                    int ret = (v && cJSON_IsNumber(v)) ? (int)v->valuedouble : -1;
                    cJSON_Delete(r);
                    return ret;
                }
            }
            return -1;
        };

        // Test connectivity with 'connected' property
        int conn = getBool("connected");
        if (conn < 0) {
            status.connected = false;
            if (sg_display_) sg_display_->SetAlpacaStatus(status);
            return;
        }
        status.connected = (conn == 1);
        if (!status.connected) {
            if (sg_display_) sg_display_->SetAlpacaStatus(status);
            return;
        }

        status.ra = getDouble("rightascension");
        status.dec = getDouble("declination");
        status.alt = getDouble("altitude");
        status.az = getDouble("azimuth");
        status.tracking = (getBool("tracking") == 1);
        status.slewing = (getBool("slewing") == 1);
        status.at_park = (getBool("atpark") == 1);
        status.pier_side = getInt("sideofpier");
        status.last_update = (uint32_t)(esp_timer_get_time() / 1000000);

        ESP_LOGI(TAG, "Alpaca: RA=%.4f DEC=%.2f Alt=%.1f Track=%d Slew=%d Park=%d",
                 status.ra, status.dec, status.alt, status.tracking, status.slewing, status.at_park);

        if (sg_display_) sg_display_->SetAlpacaStatus(status);
    }

    void PollIndi() {
        if (indi_url_.empty()) return;

        SkyGuardDisplay::IndiStatus status;
        status.configured = true;
        char resp[512] = {};
        char url[256];

        // GET /api/server/status
        snprintf(url, sizeof(url), "%s/api/server/status", indi_url_.c_str());
        if (SkyGuardHttp::Get(url, resp, sizeof(resp), 3000)) {
            cJSON* r = cJSON_Parse(resp);
            if (r) {
                // INDI Web Manager returns: [{"status": "running/stopped", ...}] or similar
                cJSON* st = cJSON_GetObjectItem(r, "status");
                if (st && cJSON_IsString(st)) {
                    status.server_running = (strcmp(st->valuestring, "running") == 0);
                }
                cJSON* prof = cJSON_GetObjectItem(r, "active_profile");
                if (prof && cJSON_IsString(prof)) {
                    strncpy(status.active_profile, prof->valuestring, sizeof(status.active_profile) - 1);
                }
                // Try array format: [{"status":"running","active_profile":"..."}]
                if (cJSON_IsArray(r)) {
                    cJSON* first = cJSON_GetArrayItem(r, 0);
                    if (first) {
                        st = cJSON_GetObjectItem(first, "status");
                        if (st && cJSON_IsString(st))
                            status.server_running = (strcmp(st->valuestring, "running") == 0);
                        prof = cJSON_GetObjectItem(first, "active_profile");
                        if (prof && cJSON_IsString(prof))
                            strncpy(status.active_profile, prof->valuestring, sizeof(status.active_profile) - 1);
                    }
                }
                cJSON_Delete(r);
            }
        }

        // Count drivers if server running
        if (status.server_running) {
            snprintf(url, sizeof(url), "%s/api/server/drivers", indi_url_.c_str());
            resp[0] = '\0';
            if (SkyGuardHttp::Get(url, resp, sizeof(resp), 3000)) {
                cJSON* r = cJSON_Parse(resp);
                if (r && cJSON_IsArray(r)) {
                    status.driver_count = cJSON_GetArraySize(r);
                }
                if (r) cJSON_Delete(r);
            }
        }

        status.last_update = (uint32_t)(esp_timer_get_time() / 1000000);
        ESP_LOGI(TAG, "INDI: running=%d profile=%s drivers=%d",
                 status.server_running, status.active_profile, status.driver_count);
        if (sg_display_) sg_display_->SetIndiStatus(status);
    }

    void PostReadingToServer() {
        if (sqm_server_url_.empty()) return;

        // Skip posting when MPSAS is out of valid range (daytime/indoor)
        if (tsl2591_ && tsl2591_->GetMpsas() < 10.0f) {
            ESP_LOGI(TAG, "SQM POST skipped: mpsas=%.2f < 10 (daytime/indoor)", tsl2591_->GetMpsas());
            return;
        }

        // Check privacy flag
        Settings sg_priv("skyguard", false);
        bool privacy_enabled = (sg_priv.GetString("sqm_privacy", "0") == "1");

        // Use centralized position (updated by timer: GPS → WiFi Google → NVS)
        UpdatePosition();
        float lat = pos_lat_, lon = pos_lon_, alt = pos_alt_;
        int gps_sats = pos_gps_sats_;
        float gps_hdop = pos_gps_hdop_;
        ESP_LOGI(TAG, "SQM POST position: %s (%.4f, %.4f)", pos_source_, lat, lon);

        // Astro calculations
        double jd = sg_display_ ? sg_display_->GetCurrentJD() : 2460384.5;
        double jd0 = sg_display_ ? sg_display_->GetCurrentJD0() : 2460384.0;
        MoonPhaseData moon = AstroCalc::moonPhase(jd);
        LunarPosition moon_pos = AstroCalc::lunarPosition(jd, lat, lon);
        MoonRiseSet mrs = AstroCalc::moonRiseSet(jd0, lat, lon);
        TwilightTimes twi = AstroCalc::twilightTimes(jd0, lat, lon);
        SolarPosition sun = AstroCalc::solarPosition(jd, lat, lon);

        // Build nested JSON using cJSON
        cJSON* root = cJSON_CreateObject();
        if (!root) { ESP_LOGE(TAG, "OOM cJSON root"); return; }

        // --- flat root fields (server-expected format) ---
        if (tsl2591_) {
            cJSON_AddNumberToObject(root, "mpsas", tsl2591_->GetMpsas());
            cJSON_AddNumberToObject(root, "nelm", tsl2591_->GetNelm());
        }
        if (aht20_ && aht20_validated_) {
            cJSON_AddNumberToObject(root, "temperature", aht20_->GetTemperature() + temp_offset_);
            float hum_flat = aht20_->GetHumidity() + hum_offset_;
            if (hum_flat > 100.0f) hum_flat = 100.0f;
            if (hum_flat < 0.0f) hum_flat = 0.0f;
            cJSON_AddNumberToObject(root, "humidity", hum_flat);
        }
        if (privacy_enabled) {
            cJSON_AddNumberToObject(root, "latitude", 0);
            cJSON_AddNumberToObject(root, "longitude", 0);
        } else {
            cJSON_AddNumberToObject(root, "latitude", lat);
            cJSON_AddNumberToObject(root, "longitude", lon);
        }
        // cloud_cover from weather forecast or 0
        int cloud_cover = 0;
        if (weather_ && weather_->HasData()) {
            ForecastData fc_flat = weather_->GetForecast();
            if (fc_flat.count > 0) cloud_cover = fc_flat.entries[0].clouds;
        }
        cJSON_AddNumberToObject(root, "cloud_cover", cloud_cover);
        cJSON_AddNumberToObject(root, "altitude", alt);
        // Sky condition from cloud cover
        const char* sky_cond = "clear";
        if (cloud_cover > 80) sky_cond = "overcast";
        else if (cloud_cover > 50) sky_cond = "cloudy";
        else if (cloud_cover > 20) sky_cond = "partly_cloudy";
        cJSON_AddStringToObject(root, "sky_condition", sky_cond);
        // Dew point and spread
        if (aht20_) {
            float dew_flat = aht20_->GetDewPoint();
            float temp_flat = aht20_->GetTemperature() + temp_offset_;
            cJSON_AddNumberToObject(root, "dew_point", dew_flat);
            cJSON_AddNumberToObject(root, "spread", temp_flat - dew_flat);
        }
        // Wind speed from weather forecast if available
        if (weather_ && weather_->HasData()) {
            ForecastData fc_w = weather_->GetForecast();
            if (fc_w.count > 0) cJSON_AddNumberToObject(root, "wind_speed", fc_w.entries[0].wind_speed);
        }
        // SQM confidence and bortle
        if (tsl2591_) {
            cJSON_AddNumberToObject(root, "sqm_confidence", tsl2591_->GetConfidence());
            cJSON_AddNumberToObject(root, "bortle", tsl2591_->GetBortle());
        }
        cJSON_AddStringToObject(root, "firmware_version", "2.2.0");
        cJSON_AddStringToObject(root, "position_source", pos_source_);

        // --- device ---
        cJSON* dev = cJSON_AddObjectToObject(root, "device");
        cJSON_AddStringToObject(dev, "type", "elite");
        // MAC address
        uint8_t mac[6];
        esp_wifi_get_mac(WIFI_IF_STA, mac);
        char mac_str[18];
        snprintf(mac_str, sizeof(mac_str), "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        cJSON_AddStringToObject(dev, "mac", mac_str);
        wifi_ap_record_t ap;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            cJSON_AddNumberToObject(dev, "rssi", ap.rssi);
        }
        cJSON_AddNumberToObject(dev, "uptime", (int)(esp_timer_get_time() / 1000000));
        cJSON_AddStringToObject(dev, "firmware", "2.1.0");
        cJSON_AddNumberToObject(dev, "freeHeap", (int)esp_get_free_heap_size());

        // --- sqm ---
        if (tsl2591_) {
            cJSON* sqm = cJSON_AddObjectToObject(root, "sqm");
            cJSON_AddNumberToObject(sqm, "mpsas", tsl2591_->GetMpsas());
            cJSON_AddNumberToObject(sqm, "nelm", tsl2591_->GetNelm());
            cJSON_AddNumberToObject(sqm, "bortle", tsl2591_->GetBortle());
            cJSON_AddStringToObject(sqm, "quality", tsl2591_->GetQuality());
            cJSON_AddNumberToObject(sqm, "confidence", tsl2591_->GetConfidence());
            cJSON_AddNumberToObject(sqm, "irRatio", tsl2591_->GetIrRatio());
            cJSON_AddNumberToObject(sqm, "lux", tsl2591_->GetLux());
            cJSON_AddNumberToObject(sqm, "rawFull", (int)tsl2591_->GetRawFull());
            cJSON_AddNumberToObject(sqm, "rawIR", (int)tsl2591_->GetRawIR());
            cJSON_AddNumberToObject(sqm, "vis", (int)(tsl2591_->GetRawFull() - tsl2591_->GetRawIR()));
            cJSON_AddNumberToObject(sqm, "gain", tsl2591_->GetGainSetting());
            cJSON_AddNumberToObject(sqm, "integration", tsl2591_->GetIntegrationSetting());
        }

        // --- spectral (same format as Pro board) ---
        if (as7341_) {
            auto& r = as7341_->GetReading();
            cJSON* sp = cJSON_AddObjectToObject(root, "spectral");
            // Channels as array of {name, value} — matches Pro format
            cJSON* ch_arr = cJSON_AddArrayToObject(sp, "channels");
            const struct { const char* name; uint16_t value; } ch_data[] = {
                {"F1_415nm", r.f1_415nm}, {"F2_445nm", r.f2_445nm},
                {"F3_480nm", r.f3_480nm}, {"F4_515nm", r.f4_515nm},
                {"F5_555nm", r.f5_555nm}, {"F6_590nm", r.f6_590nm},
                {"F7_630nm", r.f7_630nm}, {"F8_680nm", r.f8_680nm},
            };
            for (auto& c : ch_data) {
                cJSON* item = cJSON_CreateObject();
                cJSON_AddStringToObject(item, "name", c.name);
                cJSON_AddNumberToObject(item, "value", c.value);
                cJSON_AddItemToArray(ch_arr, item);
            }
            cJSON_AddNumberToObject(sp, "clear", r.clear);
            cJSON_AddNumberToObject(sp, "nir", r.nir);
            cJSON_AddNumberToObject(sp, "blueRatio", as7341_->GetBlueRatio());
            cJSON_AddNumberToObject(sp, "sodiumRatio", as7341_->GetSodiumRatio());
            cJSON_AddNumberToObject(sp, "spectralIndex", as7341_->GetSpectralQuality());
            cJSON_AddStringToObject(sp, "lpSource", as7341_->GetLpSourceName());
        }

        // --- environment ---
        if (aht20_) {
            float temp = aht20_->GetTemperature() + temp_offset_;
            float hum = aht20_->GetHumidity() + hum_offset_;
            if (hum > 100.0f) hum = 100.0f;
            if (hum < 0.0f) hum = 0.0f;
            float dew = aht20_->GetDewPoint();

            cJSON* env = cJSON_AddObjectToObject(root, "environment");
            cJSON_AddNumberToObject(env, "temperature", temp);
            cJSON_AddNumberToObject(env, "humidity", hum);
            cJSON_AddNumberToObject(env, "dew_point", dew);
            cJSON_AddNumberToObject(env, "aht20_temp", temp);
            cJSON_AddNumberToObject(env, "aht20_hum", hum);
            cJSON_AddNumberToObject(env, "temp_rate", aht20_->GetTempRate());
        }

        // --- gps ---
        cJSON* gps_obj = cJSON_AddObjectToObject(root, "gps");
        if (privacy_enabled) {
            // Privacy mode: send zeroed coords + flag so server knows not to map
            cJSON_AddNumberToObject(gps_obj, "latitude", 0);
            cJSON_AddNumberToObject(gps_obj, "longitude", 0);
            cJSON_AddBoolToObject(gps_obj, "privacy", 1);
        } else {
            cJSON_AddNumberToObject(gps_obj, "latitude", lat);
            cJSON_AddNumberToObject(gps_obj, "longitude", lon);
        }
        cJSON_AddNumberToObject(gps_obj, "altitude", alt);
        cJSON_AddNumberToObject(gps_obj, "satellites", gps_sats);
        cJSON_AddNumberToObject(gps_obj, "hdop", gps_hdop);

        // --- astro ---
        cJSON* astro = cJSON_AddObjectToObject(root, "astro");
        cJSON_AddNumberToObject(astro, "moonPhase", moon.illumination / 100.0);
        cJSON_AddNumberToObject(astro, "moonIllumination", (int)moon.illumination);
        cJSON_AddNumberToObject(astro, "moonAltitude", moon_pos.altitude);
        cJSON_AddNumberToObject(astro, "moonAzimuth", moon_pos.azimuth);
        cJSON_AddNumberToObject(astro, "sunAltitude", sun.altitude);
        cJSON_AddStringToObject(astro, "moon_phase_name", moon.phaseName);
        // Twilight state
        const char* twi_state = "day";
        if (sun.altitude < -18) twi_state = "astronomical";
        else if (sun.altitude < -12) twi_state = "nautical";
        else if (sun.altitude < -6) twi_state = "civil";
        else if (sun.altitude < 0) twi_state = "twilight";
        cJSON_AddStringToObject(astro, "twilight", twi_state);

        char time_buf[8];
        if (mrs.rises) {
            snprintf(time_buf, sizeof(time_buf), "%02d:%02d", (int)mrs.moonrise, (int)((mrs.moonrise - (int)mrs.moonrise) * 60));
            cJSON_AddStringToObject(astro, "moonRise", time_buf);
        }
        if (mrs.sets) {
            snprintf(time_buf, sizeof(time_buf), "%02d:%02d", (int)mrs.moonset, (int)((mrs.moonset - (int)mrs.moonset) * 60));
            cJSON_AddStringToObject(astro, "moonSet", time_buf);
        }
        if (twi.valid) {
            if (twi.astronomicalDawn >= 0) {
                snprintf(time_buf, sizeof(time_buf), "%02d:%02d", (int)twi.astronomicalDawn, (int)((twi.astronomicalDawn - (int)twi.astronomicalDawn) * 60));
                cJSON_AddStringToObject(astro, "astroDawn", time_buf);
            }
            if (twi.astronomicalDusk >= 0) {
                snprintf(time_buf, sizeof(time_buf), "%02d:%02d", (int)twi.astronomicalDusk, (int)((twi.astronomicalDusk - (int)twi.astronomicalDusk) * 60));
                cJSON_AddStringToObject(astro, "astroDusk", time_buf);
            }
        }

        // --- weather ---
        if (weather_ && weather_->HasData()) {
            ForecastData fc = weather_->GetForecast();
            if (fc.count > 0) {
                auto& w = fc.entries[0];
                float spread = 0;
                if (aht20_) spread = (aht20_->GetTemperature() + temp_offset_) - aht20_->GetDewPoint();

                cJSON* wx = cJSON_AddObjectToObject(root, "weather");
                cJSON_AddNumberToObject(wx, "wind_speed_kmh", w.wind_speed * 3.6f);
                cJSON_AddNumberToObject(wx, "wind_gust_kmh", w.wind_gust * 3.6f);
                cJSON_AddBoolToObject(wx, "rain_detected", w.rain_3h > 0 ? 1 : 0);
                cJSON_AddNumberToObject(wx, "rain_intensity", w.rain_3h);
                cJSON_AddNumberToObject(wx, "sea_level_pressure", w.sea_level > 0 ? w.sea_level : w.pressure);
                cJSON_AddNumberToObject(wx, "spread", spread);
                cJSON_AddStringToObject(wx, "pressure_trend", "stabile");
                cJSON_AddNumberToObject(wx, "transparency_pct",
                    (int)((100 - w.clouds) * (100 - w.humidity) / 100));
                if (aht20_) {
                    cJSON_AddNumberToObject(wx, "dew_countdown_min", aht20_->GetDewCountdownMin());
                }
            }
        }

        // --- cloud --- (no MLX90614, use OWM clouds)
        if (weather_ && weather_->HasData()) {
            ForecastData fc = weather_->GetForecast();
            if (fc.count > 0) {
                cJSON* cl = cJSON_AddObjectToObject(root, "cloud");
                cJSON_AddStringToObject(cl, "condition", fc.entries[0].description);
                if (aht20_) cJSON_AddNumberToObject(cl, "ambient_temp", aht20_->GetTemperature() + temp_offset_);
                cJSON_AddNumberToObject(cl, "cover_pct", fc.entries[0].clouds);
            }
        }

        // --- alerts ---
        cJSON* alerts = cJSON_AddObjectToObject(root, "alerts");
        float spread_val = 99;
        if (aht20_) spread_val = (aht20_->GetTemperature() + temp_offset_) - aht20_->GetDewPoint();
        cJSON_AddBoolToObject(alerts, "dew_warning", spread_val < 2.0f ? 1 : 0);
        if (weather_ && weather_->HasData()) {
            ForecastData fc = weather_->GetForecast();
            if (fc.count > 0) {
                cJSON_AddBoolToObject(alerts, "wind_warning", fc.entries[0].wind_speed * 3.6f > 20 ? 1 : 0);
                cJSON_AddBoolToObject(alerts, "cloud_warning", fc.entries[0].clouds > 60 ? 1 : 0);
                cJSON_AddBoolToObject(alerts, "rain_warning", fc.entries[0].rain_3h > 0 ? 1 : 0);
            }
        }

        // --- metrics ---
        cJSON* metrics = cJSON_AddObjectToObject(root, "metrics");
        cJSON_AddNumberToObject(metrics, "stability", tsl2591_ ? (tsl2591_->GetConfidence() / 100.0f) : 0);

        // Equipment is synced separately via POST /api/my/equipment
        // (at boot and on config save — not on every reading)

        // Serialize
        char* json = cJSON_PrintUnformatted(root);
        cJSON_Delete(root);
        if (!json) { ESP_LOGE(TAG, "cJSON print failed"); return; }

        // Try to POST immediately
        char url[128];
        snprintf(url, sizeof(url), "%s/api/readings", sqm_server_url_.c_str());

        char* resp = SkyGuardHttp::AllocBuffer(512);
        bool posted = false;
        if (resp) {
            posted = SkyGuardHttp::Post(url, json, resp, 512, 15000,
                                         sqm_api_key_.empty() ? nullptr : sqm_api_key_.c_str());
            if (posted) {
                ESP_LOGI(TAG, "Reading posted OK → %s", resp);
            } else {
                ESP_LOGW(TAG, "Failed to post reading — caching for later");
            }
            free(resp);
        }

        if (posted) {
            // Sent OK — free json and try flushing any cached readings
            cJSON_free(json);
            if (cache_count_ > 0) {
                ESP_LOGI(TAG, "Server reachable — flushing %d cached readings", cache_count_);
                FlushReadingCache();
            }
        } else {
            // Failed — cache the reading for later (takes ownership of json)
            CacheReading(json);
        }
    }

    // POST equipment to server — called at boot + when user saves config
    void PostEquipmentToServer() {
        if (sqm_server_url_.empty()) return;

        Settings sg("skyguard", false);
        std::string eq_json = sg.GetString("equipment", "");
        if (eq_json.empty()) {
            ESP_LOGI(TAG, "Equipment POST skipped: no equipment in NVS");
            return;
        }

        // Build wrapper: {"equipment": {...}}
        cJSON* wrapper = cJSON_CreateObject();
        if (!wrapper) return;
        cJSON* eq = cJSON_Parse(eq_json.c_str());
        if (eq) {
            cJSON_AddItemToObject(wrapper, "equipment", eq);
        } else {
            cJSON_Delete(wrapper);
            ESP_LOGW(TAG, "Equipment JSON parse failed");
            return;
        }

        char* json = cJSON_PrintUnformatted(wrapper);
        cJSON_Delete(wrapper);
        if (!json) return;

        char url[128];
        snprintf(url, sizeof(url), "%s/api/my/equipment", sqm_server_url_.c_str());

        char* resp = SkyGuardHttp::AllocBuffer(512);
        if (resp) {
            bool ok = SkyGuardHttp::Post(url, json, resp, 512, 15000,
                                          sqm_api_key_.empty() ? nullptr : sqm_api_key_.c_str());
            if (ok) {
                ESP_LOGI(TAG, "Equipment synced to server OK");
                equipment_synced_ = true;
            } else {
                ESP_LOGW(TAG, "Equipment POST failed: %s", resp);
            }
            free(resp);
        }
        cJSON_free(json);
    }

    void InitializeSkyGuardDisplay() {
        ESP_LOGI(TAG, "Scheduling SkyGuard display pages (deferred to LVGL ready)");
        sg_display_ = new SkyGuardDisplay();
        sg_display_->SetSensors(tsl2591_, as7341_, aht20_, gps_);
        sg_display_->SetWeather(weather_);
        sg_display_->SetSkyTracker(sky_tracker_);
        sg_display_->SetCalibration(temp_offset_, hum_offset_);
        sg_display_->SetAlpacaUrl(alpaca_url_);
        sg_display_->SetIndiUrl(indi_url_);

        // Control callback — executes ASCOM/INDI commands from touch buttons
        sg_display_->SetControlCallback([](void* ctx, const char* command, const char* param) {
            auto* board = (SkyGuardEliteBoard*)ctx;
            ESP_LOGI(TAG, "Control button: %s %s", command, param);

            struct CtrlCmd {
                SkyGuardEliteBoard* b;
                char cmd[32];
                char par[32];
            };
            auto* cc = new CtrlCmd();
            cc->b = board;
            strncpy(cc->cmd, command, sizeof(cc->cmd) - 1);
            cc->cmd[sizeof(cc->cmd) - 1] = '\0';
            strncpy(cc->par, param, sizeof(cc->par) - 1);
            cc->par[sizeof(cc->par) - 1] = '\0';

            xTaskCreate([](void* arg) {
                auto* c = (CtrlCmd*)arg;
                char url[256];
                char resp[256] = {};

                // --- INDI commands ---
                if (strcmp(c->cmd, "indi_start") == 0) {
                    if (!c->b->indi_url_.empty()) {
                        snprintf(url, sizeof(url), "%s/api/server/start/default", c->b->indi_url_.c_str());
                        SkyGuardHttp::Post(url, "", resp, sizeof(resp));
                        ESP_LOGI(TAG, "INDI start: %s", resp);
                    }
                } else if (strcmp(c->cmd, "indi_stop") == 0) {
                    if (!c->b->indi_url_.empty()) {
                        snprintf(url, sizeof(url), "%s/api/server/stop", c->b->indi_url_.c_str());
                        SkyGuardHttp::Post(url, "", resp, sizeof(resp));
                        ESP_LOGI(TAG, "INDI stop: %s", resp);
                    }
                }
                // --- PHD2 commands ---
                else if (strcmp(c->cmd, "phd2_guide") == 0) {
                    // PHD2 uses JSON-RPC on port 4400
                    Settings sg("skyguard", false);
                    std::string phd2_host = sg.GetString("phd2_host", "192.168.1.100");
                    snprintf(url, sizeof(url), "http://%s:4400", phd2_host.c_str());
                    char body[128];
                    if (strcmp(c->par, "start") == 0) {
                        snprintf(body, sizeof(body), "{\"method\":\"guide\",\"params\":[{\"settle\":{\"pixels\":1.5,\"time\":8,\"timeout\":40}}],\"id\":1}");
                    } else {
                        snprintf(body, sizeof(body), "{\"method\":\"stop_capture\",\"params\":[],\"id\":1}");
                    }
                    SkyGuardHttp::Post(url, body, resp, sizeof(resp));
                    ESP_LOGI(TAG, "PHD2 %s: %s", c->par, resp);
                } else if (strcmp(c->cmd, "phd2_dither") == 0) {
                    Settings sg("skyguard", false);
                    std::string phd2_host = sg.GetString("phd2_host", "192.168.1.100");
                    snprintf(url, sizeof(url), "http://%s:4400", phd2_host.c_str());
                    SkyGuardHttp::Post(url, "{\"method\":\"dither\",\"params\":[5,false,{\"pixels\":1.5,\"time\":8,\"timeout\":30}],\"id\":1}", resp, sizeof(resp));
                    ESP_LOGI(TAG, "PHD2 dither: %s", resp);
                } else if (strcmp(c->cmd, "phd2_calib") == 0) {
                    Settings sg("skyguard", false);
                    std::string phd2_host = sg.GetString("phd2_host", "192.168.1.100");
                    snprintf(url, sizeof(url), "http://%s:4400", phd2_host.c_str());
                    SkyGuardHttp::Post(url, "{\"method\":\"clear_calibration\",\"params\":[\"both\"],\"id\":1}", resp, sizeof(resp));
                    ESP_LOGI(TAG, "PHD2 calibrate: %s", resp);
                }
                // --- NINA commands ---
                else if (strcmp(c->cmd, "nina_seq") == 0) {
                    Settings sg("skyguard", false);
                    std::string nina_host = sg.GetString("nina_host", "192.168.1.100");
                    if (strcmp(c->par, "start") == 0) {
                        snprintf(url, sizeof(url), "http://%s:1888/api/v2/sequence/start", nina_host.c_str());
                    } else if (strcmp(c->par, "stop") == 0) {
                        snprintf(url, sizeof(url), "http://%s:1888/api/v2/sequence/stop", nina_host.c_str());
                    } else {
                        snprintf(url, sizeof(url), "http://%s:1888/api/v2/sequence/pause", nina_host.c_str());
                    }
                    SkyGuardHttp::Post(url, "", resp, sizeof(resp));
                    ESP_LOGI(TAG, "NINA seq %s: %s", c->par, resp);
                } else if (strcmp(c->cmd, "nina_af") == 0) {
                    Settings sg("skyguard", false);
                    std::string nina_host = sg.GetString("nina_host", "192.168.1.100");
                    snprintf(url, sizeof(url), "http://%s:1888/api/v2/focuser/autofocus", nina_host.c_str());
                    SkyGuardHttp::Post(url, "", resp, sizeof(resp));
                    ESP_LOGI(TAG, "NINA autofocus: %s", resp);
                }
                // --- Stellarium commands ---
                else if (strcmp(c->cmd, "stell_slew") == 0) {
                    Settings sg("skyguard", false);
                    std::string stell_host = sg.GetString("stellarium_host", "192.168.1.100");
                    snprintf(url, sizeof(url), "http://%s:8090/api/main/focus", stell_host.c_str());
                    SkyGuardHttp::Post(url, "target=selection", resp, sizeof(resp));
                    ESP_LOGI(TAG, "Stellarium slew: %s", resp);
                } else if (strcmp(c->cmd, "stell_sync") == 0) {
                    Settings sg("skyguard", false);
                    std::string stell_host = sg.GetString("stellarium_host", "192.168.1.100");
                    snprintf(url, sizeof(url), "http://%s:8090/api/stelaction/do", stell_host.c_str());
                    SkyGuardHttp::Post(url, "id=actionSync_Telescope_With_Selected_Object", resp, sizeof(resp));
                    ESP_LOGI(TAG, "Stellarium sync: %s", resp);
                }
                // --- Dew heater ---
                else if (strcmp(c->cmd, "dew") == 0) {
                    if (strcmp(c->par, "on") == 0) c->b->dew_mode_ = 1;
                    else if (strcmp(c->par, "off") == 0) c->b->dew_mode_ = 0;
                    else if (strcmp(c->par, "auto") == 0) c->b->dew_mode_ = 2;
                    // Apply immediately
                    if (c->b->dew_gpio_ >= 0) {
                        if (c->b->dew_mode_ == 1) {
                            int duty = (c->b->dew_power_ * 255) / 100;
                            ledc_set_duty(LEDC_LOW_SPEED_MODE, c->b->dew_ledc_ch_, duty);
                            ledc_update_duty(LEDC_LOW_SPEED_MODE, c->b->dew_ledc_ch_);
                            c->b->dew_heater_active_ = true;
                        } else if (c->b->dew_mode_ == 0) {
                            ledc_set_duty(LEDC_LOW_SPEED_MODE, c->b->dew_ledc_ch_, 0);
                            ledc_update_duty(LEDC_LOW_SPEED_MODE, c->b->dew_ledc_ch_);
                            c->b->dew_heater_active_ = false;
                        }
                    }
                    ESP_LOGI(TAG, "Dew heater mode: %d", c->b->dew_mode_);
                }
                // --- SQM measure from control page ---
                else if (strcmp(c->cmd, "sqm_measure") == 0) {
                    if (c->b->sg_display_ && !c->b->sg_display_->IsMeasuring()) {
                        if (lvgl_port_lock(200)) {
                            c->b->sg_display_->TriggerMeasurement();
                            lvgl_port_unlock();
                        }
                    }
                }
                // --- ASCOM Alpaca mount ---
                else if (!c->b->alpaca_url_.empty()) {
                    const char* base = c->b->alpaca_url_.c_str();
                    if (strcmp(c->cmd, "tracking") == 0) {
                        snprintf(url, sizeof(url), "%s/api/v1/telescope/0/tracking", base);
                        char body[64];
                        snprintf(body, sizeof(body), "Tracking=%s&ClientID=1",
                                 strcmp(c->par, "on") == 0 ? "true" : "false");
                        SkyGuardHttp::Put(url, body, resp, sizeof(resp));
                    } else if (strcmp(c->cmd, "park") == 0) {
                        snprintf(url, sizeof(url), "%s/api/v1/telescope/0/park", base);
                        SkyGuardHttp::Put(url, "ClientID=1", resp, sizeof(resp));
                    } else if (strcmp(c->cmd, "unpark") == 0) {
                        snprintf(url, sizeof(url), "%s/api/v1/telescope/0/unpark", base);
                        SkyGuardHttp::Put(url, "ClientID=1", resp, sizeof(resp));
                    } else if (strcmp(c->cmd, "abortslew") == 0) {
                        snprintf(url, sizeof(url), "%s/api/v1/telescope/0/abortslew", base);
                        SkyGuardHttp::Put(url, "ClientID=1", resp, sizeof(resp));
                    } else if (strcmp(c->cmd, "findhome") == 0) {
                        snprintf(url, sizeof(url), "%s/api/v1/telescope/0/findhome", base);
                        SkyGuardHttp::Put(url, "ClientID=1", resp, sizeof(resp));
                    }
                    ESP_LOGI(TAG, "Alpaca %s: %s", c->cmd, resp);
                }
                delete c;
                vTaskDelete(nullptr);
            }, "sg_ctrl", 6144, cc, 2, nullptr);
        }, this);

        // Set initial position from centralized resolver (GPS → NVS)
        UpdatePosition();
        sg_display_->SetFallbackPosition(pos_lat_, pos_lon_, pos_source_);
        if (weather_) weather_->SetLocation(pos_lat_, pos_lon_);
        if (sky_tracker_) sky_tracker_->SetLocation(pos_lat_, pos_lon_, pos_alt_);
        ESP_LOGI(TAG, "Initial position: %s (%.4f, %.4f)", pos_source_, pos_lat_, pos_lon_);

        // Don't call Setup() here — LVGL screen not ready yet in constructor
        // Setup will be called on first timer tick

        // Timer: first tick does setup, then periodic update + data fetch
        esp_timer_create_args_t timer_args = {
            .callback = [](void* arg) {
                auto* board = (SkyGuardEliteBoard*)arg;
                if (!board->sg_display_) return;

                if (!board->sg_setup_done_) {
                    // First tick: LVGL is ready now, do setup
                    ESP_LOGI(TAG, "LVGL ready — setting up SkyGuard pages");
                    board->sg_display_->Setup();
                    board->sg_display_->ShowBootLoader();

                    // Touch screen during AI conversation → exit chatbot
                    // Both swipe-down and single tap work as exit
                    if (lvgl_port_lock(50)) {
                        lv_obj_t* scr = lv_screen_active();
                        if (scr) {
                            lv_obj_add_flag(scr, LV_OBJ_FLAG_CLICKABLE);
                            // Swipe-down exit
                            lv_obj_add_event_cb(scr, [](lv_event_t* e) {
                                lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_active());
                                if (dir != LV_DIR_BOTTOM) return;
                                auto* b = (SkyGuardEliteBoard*)lv_event_get_user_data(e);
                                auto state = Application::GetInstance().GetDeviceState();
                                if (state == kDeviceStateListening ||
                                    state == kDeviceStateSpeaking ||
                                    state == kDeviceStateConnecting) {
                                    ESP_LOGI("SkyGuardUI", "Swipe-down → exiting chatbot");
                                    b->ExitChatbot();
                                }
                            }, LV_EVENT_GESTURE, board);
                            // Single tap exit (tap anywhere on emoji screen)
                            lv_obj_add_event_cb(scr, [](lv_event_t* e) {
                                auto* b = (SkyGuardEliteBoard*)lv_event_get_user_data(e);
                                auto state = Application::GetInstance().GetDeviceState();
                                if (state == kDeviceStateListening ||
                                    state == kDeviceStateSpeaking ||
                                    state == kDeviceStateConnecting) {
                                    ESP_LOGI("SkyGuardUI", "Screen tap → exiting chatbot");
                                    b->ExitChatbot();
                                }
                            }, LV_EVENT_CLICKED, board);
                        }
                        lvgl_port_unlock();
                    }

                    board->sg_setup_done_ = true;
                    return;
                }

                board->tick_counter_++;

                // Toggle between SkyGuard overlay and AI emoji face
                auto state = Application::GetInstance().GetDeviceState();
                bool ai_active = (state == kDeviceStateListening ||
                                  state == kDeviceStateSpeaking ||
                                  state == kDeviceStateConnecting);

                // Pending exit: speaking was aborted, now check if state became listening
                if (board->pending_ai_exit_ && state == kDeviceStateListening) {
                    ESP_LOGI(TAG, "Pending exit: speaking→listening transition, calling StopListening");
                    Application::GetInstance().StopListening();
                    board->pending_ai_exit_ = false;
                    board->ai_idle_counter_ = 0;
                    board->ai_was_active_ = false;
                }

                // Direct touch polling for AI exit — bypasses LVGL event system
                // which may not deliver events when emoji overlay is active
                if (ai_active && board->touch_handle_) {
                    uint16_t tx[1], ty[1];
                    uint16_t strength[1];
                    uint8_t count = 0;
                    esp_lcd_touch_read_data(board->touch_handle_);
                    bool got = esp_lcd_touch_get_coordinates(board->touch_handle_, tx, ty, strength, &count, 1);
                    if (got && count > 0) {
                        if (!board->touch_was_down_) {
                            // Touch just started
                            board->touch_was_down_ = true;
                            board->touch_down_tick_ = board->tick_counter_;
                            board->touch_start_y_ = ty[0];
                            ESP_LOGI(TAG, "Touch down during AI: x=%d y=%d", tx[0], ty[0]);
                        }
                    } else if (board->touch_was_down_) {
                        // Touch released — check for tap or swipe
                        board->touch_was_down_ = false;
                        uint32_t hold_ticks = board->tick_counter_ - board->touch_down_tick_;
                        ESP_LOGI(TAG, "Touch up during AI: hold=%lds start_y=%d", (long)hold_ticks, board->touch_start_y_);
                        if (hold_ticks <= 2) {  // Tap (held < 2 seconds)
                            ESP_LOGI(TAG, "Touch TAP → exiting chatbot");
                            board->ExitChatbot();
                        }
                    }
                } else if (!ai_active) {
                    board->touch_was_down_ = false;  // Reset when not in AI mode
                }

                // Auto-exit chatbot: if AI stays in listening for 5s without voice → exit
                // This prevents ghost mic activations from keeping chatbot active
                if (ai_active) {
                    board->ai_was_active_ = true;
                    if (state == kDeviceStateListening) {
                        board->ai_idle_counter_++;
                        if (board->ai_idle_counter_ >= 5 &&
                            !Application::GetInstance().IsVoiceDetected()) {
                            ESP_LOGI(TAG, "Auto-exit chatbot: 5s no voice in listening");
                            board->ExitChatbot();
                        }
                    } else if (state == kDeviceStateConnecting) {
                        // Connecting for too long (no WiFi?) → exit after 10s
                        board->ai_idle_counter_++;
                        if (board->ai_idle_counter_ >= 10) {
                            ESP_LOGI(TAG, "Auto-exit chatbot: 10s stuck in connecting");
                            board->ExitChatbot();
                        }
                    } else {
                        board->ai_idle_counter_ = 0;  // Reset counter while speaking
                    }
                } else {
                    board->ai_idle_counter_ = 0;
                    board->ai_was_active_ = false;
                }

                // Boot ready: hide loader on first idle OR after 15s timeout
                // (was 30s — reduced so offline mode shows SkyGuard dashboard faster)
                if (!board->boot_ready_fired_ &&
                    (state == kDeviceStateIdle || board->tick_counter_ > 15)) {
                    board->boot_ready_fired_ = true;
                    board->sg_display_->HideBootLoader();
                    ESP_LOGI(TAG, "SkyGuard AI is ready!");

                    // Replace round Twemoji with star emoji AFTER assets have loaded
                    {
                        auto star_emoji = std::make_shared<StarEmoji32>();
                        auto& tm = LvglThemeManager::GetInstance();
                        auto* dark = tm.GetTheme("dark");
                        auto* light = tm.GetTheme("light");
                        auto* nature = tm.GetTheme("nature");
                        if (dark) dark->set_emoji_collection(star_emoji);
                        if (light) light->set_emoji_collection(star_emoji);
                        if (nature) nature->set_emoji_collection(star_emoji);
                        ESP_LOGI(TAG, "Star emoji collection installed (post-assets)");
                    }

                    // Play boot beep, then schedule ready announcement
                    Application::GetInstance().PlaySound(Lang::Sounds::OGG_SKYGUARD);
                    if (state == kDeviceStateIdle) {
                        board->ready_sound_tick_ = board->tick_counter_ + 2;  // Play 2s later
                    }
                }

                // Play "SkyGuard AI is ready!" voice after boot beep
                if (board->ready_sound_tick_ > 0 && board->tick_counter_ >= board->ready_sound_tick_) {
                    board->ready_sound_tick_ = 0;
                    Application::GetInstance().PlaySound(Lang::Sounds::OGG_SKYGUARD_READY);
                }

                board->sg_display_->SetVisible(!ai_active);

                // Toggle emoji_box + bottom_bar visibility
                if (lvgl_port_lock(50)) {
                    lv_obj_t* screen = lv_screen_active();
                    if (screen && lv_obj_get_child_count(screen) > 1) {
                        lv_obj_t* emoji_box = lv_obj_get_child(screen, 1);
                        if (emoji_box) {
                            if (ai_active) {
                                lv_obj_clear_flag(emoji_box, LV_OBJ_FLAG_HIDDEN);
                            } else {
                                lv_obj_add_flag(emoji_box, LV_OBJ_FLAG_HIDDEN);
                            }
                        }
                        if (lv_obj_get_child_count(screen) > 4) {
                            lv_obj_t* bottom_bar = lv_obj_get_child(screen, 4);
                            if (bottom_bar) {
                                if (ai_active) {
                                    lv_obj_clear_flag(bottom_bar, LV_OBJ_FLAG_HIDDEN);
                                } else {
                                    lv_obj_add_flag(bottom_bar, LV_OBJ_FLAG_HIDDEN);
                                }
                            }
                        }
                    }
                    lvgl_port_unlock();
                }

                board->sg_display_->Update();

                // ============================================================
                // PERIODIC DATA FETCH (tick_counter_ increments every 1s)
                // ============================================================

                // Start WebUI when WiFi is connected (one-shot)
                if (board->webui_ && !board->webui_->IsRunning() && board->tick_counter_ > 5) {
                    auto& wifi = WifiManager::GetInstance();
                    if (!wifi.IsConfigMode() && !wifi.GetIpAddress().empty()) {
                        board->webui_->Start();
                    }
                }

                // Sync equipment to server at boot (one-shot, after WiFi)
                if (!board->equipment_synced_ && board->tick_counter_ == 12) {
                    auto& wifi = WifiManager::GetInstance();
                    if (!wifi.IsConfigMode() && !wifi.GetIpAddress().empty()) {
                        xTaskCreate([](void* arg) {
                            auto* b = (SkyGuardEliteBoard*)arg;
                            b->PostEquipmentToServer();
                            vTaskDelete(nullptr);
                        }, "sg_eq_boot", 6144, board, 2, nullptr);
                    }
                }

                // Update centralized position every 60s: GPS → WiFi Google → NVS
                if (board->tick_counter_ % 60 == 30) {
                    const char* prev_source = board->pos_source_;
                    board->UpdatePosition();

                    // Try WiFi Google fallback every 5 min if no GPS fix
                    if (strcmp(board->pos_source_, "nvs") == 0 &&
                        board->wifi_geo_ && board->tick_counter_ % 300 == 30) {
                        ESP_LOGI(TAG, "No GPS fix — trying WiFi Google geolocation");
                        xTaskCreate([](void* arg) {
                            auto* board = (SkyGuardEliteBoard*)arg;
                            if (board->wifi_geo_->ResolveFallback()) {
                                board->UpdatePosition();  // Re-evaluate after resolve
                            }
                            // Propagate position to all consumers
                            if (board->weather_) board->weather_->SetLocation(board->pos_lat_, board->pos_lon_);
                            if (board->sky_tracker_) board->sky_tracker_->SetLocation(board->pos_lat_, board->pos_lon_, board->pos_alt_);
                            if (board->sg_display_) board->sg_display_->SetFallbackPosition(board->pos_lat_, board->pos_lon_, board->pos_source_);
                            vTaskDelete(nullptr);
                        }, "sg_geoloc", 8192, board, 3, nullptr);
                    } else {
                        // Propagate to all consumers
                        if (board->weather_) board->weather_->SetLocation(board->pos_lat_, board->pos_lon_);
                        if (board->sky_tracker_) board->sky_tracker_->SetLocation(board->pos_lat_, board->pos_lon_, board->pos_alt_);
                        if (board->sg_display_) board->sg_display_->SetFallbackPosition(board->pos_lat_, board->pos_lon_, board->pos_source_);
                    }

                    if (strcmp(board->pos_source_, prev_source) != 0) {
                        ESP_LOGI(TAG, "Position source changed: %s → %s (%.4f, %.4f)",
                                 prev_source, board->pos_source_, board->pos_lat_, board->pos_lon_);
                    }
                }

                // Weather forecast — every 30 min (1800s)
                if (board->tick_counter_ % 1800 == 10) {
                    if (board->weather_) {
                        ESP_LOGI(TAG, "Periodic weather fetch");
                        board->weather_->StartFetchTask();
                    }
                }

                // Aircraft radar — every 8 min (480s) to stay under OpenSky 400/day limit
                if (board->tick_counter_ % 480 == 20) {
                    if (board->sky_tracker_) {
                        ESP_LOGI(TAG, "Periodic flight fetch");
                        // Run in background to avoid blocking timer
                        xTaskCreate([](void* arg) {
                            auto* t = (SkyGuardSkyTracker*)arg;
                            t->FetchFlights();
                            vTaskDelete(nullptr);
                        }, "sg_flights", 8192, board->sky_tracker_, 3, nullptr);
                    }
                }

                // Satellite passes — every 10 min (600s)
                if (board->tick_counter_ % 600 == 40) {
                    if (board->sky_tracker_) {
                        ESP_LOGI(TAG, "Periodic satellite fetch");
                        xTaskCreate([](void* arg) {
                            auto* t = (SkyGuardSkyTracker*)arg;
                            t->FetchSatellites();
                            vTaskDelete(nullptr);
                        }, "sg_sats", 8192, board->sky_tracker_, 3, nullptr);
                    }
                }

                // Auto SQM measurement — every 5 min at night (when visible, not measuring, not in AI)
                if (board->tick_counter_ % 300 == 0 && board->tick_counter_ > 0) {
                    if (!ai_active && board->sg_display_->IsMeasuring() == false) {
                        // Only auto-measure if it's nighttime (check TSL2591 lux)
                        if (board->tsl2591_ && board->tsl2591_->GetLux() < board->lux_threshold_) {
                            ESP_LOGI(TAG, "Auto SQM measurement (nighttime)");
                            if (lvgl_port_lock(200)) {
                                board->sg_display_->TriggerMeasurement();
                                lvgl_port_unlock();
                            }
                        }
                    }
                }

                // Post full reading to SQM server — every 5 min (300s), first at 60s
                if (board->tick_counter_ % 300 == 50 && board->tick_counter_ >= 50) {
                    xTaskCreate([](void* arg) {
                        auto* board = (SkyGuardEliteBoard*)arg;
                        board->PostReadingToServer();
                        vTaskDelete(nullptr);
                    }, "sg_post", 8192, board, 2, nullptr);
                }

                // Post full 5-day forecast to server — first at 30s, then every 3h (10800s)
                if ((board->tick_counter_ == 30) ||
                    (board->tick_counter_ % 10800 == 70 && board->tick_counter_ > 30)) {
                    if (board->weather_) {
                        board->weather_->StartForecastPostTask();
                    }
                }

                // Voice alerts — check every 5 minutes (300s)
                if (board->tick_counter_ % 300 == 30 && board->tick_counter_ > 120) {
                    board->CheckAlerts();
                }

                // Satellite image fetch — every 30 min (or first load), skip during AI
                if (!ai_active && (board->tick_counter_ % 1800 == 60 || (board->tick_counter_ == 15 && board->sg_display_))) {
                    if (board->sg_display_ && board->sg_display_->NeedsSatelliteImage()) {
                        xTaskCreate([](void* arg) {
                            auto* board = (SkyGuardEliteBoard*)arg;
                            board->FetchSatelliteImage();
                            vTaskDelete(nullptr);
                        }, "sg_sat_img", 16384, board, 1, nullptr);
                    }
                }

                // GPS map tile fetch — every 30s for first 5 min, then every 10 min
                {
                    bool gps_try = false;
                    if (board->tick_counter_ <= 300) {
                        gps_try = (board->tick_counter_ % 30 == 20);  // Every 30s during boot
                    } else {
                        gps_try = (board->tick_counter_ % 600 == 20);  // Every 10 min later
                    }
                    if (!ai_active && gps_try && board->sg_display_) {
                        float lat = 0, lon = 0;
                        if (board->sg_display_->NeedsGpsMapImage(lat, lon)) {
                            ESP_LOGI(TAG, "GPS map needed for (%.4f, %.4f), starting fetch...", lat, lon);
                            struct GpsMapCtx { SkyGuardEliteBoard* b; float lat; float lon; };
                            auto* ctx = new GpsMapCtx{board, lat, lon};
                            xTaskCreate([](void* arg) {
                                auto* c = (GpsMapCtx*)arg;
                                c->b->FetchGpsMap(c->lat, c->lon);
                                delete c;
                                vTaskDelete(nullptr);
                            }, "sg_gps_map", 12288, ctx, 1, nullptr);
                        } else {
                            ESP_LOGD(TAG, "GPS map not needed (no position or already valid)");
                        }

                        // Reverse geocode once when position is available
                        if (!board->geocode_done_ && !board->google_api_key_.empty()) {
                            float rlat = 0, rlon = 0;
                            if (board->sg_display_->HasPosition(rlat, rlon)) {
                                board->geocode_done_ = true;
                                struct GeoCtx { SkyGuardEliteBoard* b; float lat; float lon; };
                                auto* gctx = new GeoCtx{board, rlat, rlon};
                                xTaskCreate([](void* arg) {
                                    auto* c = (GeoCtx*)arg;
                                    c->b->FetchReverseGeocode(c->lat, c->lon);
                                    delete c;
                                    vTaskDelete(nullptr);
                                }, "sg_geocode", 8192, gctx, 1, nullptr);
                            }
                        }
                    }
                }

                // Alpaca telescope polling — every 5 seconds
                if (board->tick_counter_ % 5 == 0 && !board->alpaca_url_.empty()) {
                    xTaskCreate([](void* arg) {
                        auto* board = (SkyGuardEliteBoard*)arg;
                        board->PollAlpaca();
                        vTaskDelete(nullptr);
                    }, "sg_alpaca", 6144, board, 2, nullptr);
                }

                // INDI polling — every 10 seconds
                if (board->tick_counter_ % 10 == 3 && !board->indi_url_.empty()) {
                    xTaskCreate([](void* arg) {
                        auto* board = (SkyGuardEliteBoard*)arg;
                        board->PollIndi();
                        vTaskDelete(nullptr);
                    }, "sg_indi", 6144, board, 2, nullptr);
                }

                // Periodic sensor measurements — every 2 min, with countdown overlay
                // TriggerMeasurement() shows countdown on display, then measures TSL+AS together
                if ((board->tsl2591_ || board->as7341_) &&
                    board->tick_counter_ >= 120 && board->tick_counter_ % 120 == 5) {
                    if (board->sg_display_ && !board->sg_display_->IsMeasuring()) {
                        if (lvgl_port_lock(200)) {
                            board->sg_display_->TriggerMeasurement();
                            lvgl_port_unlock();
                            ESP_LOGI(TAG, "Auto-measure triggered (every 2 min)");
                        }
                    }
                }
                // AHT20 (Temp/Hum) — every 10s, with validation at boot
                if (board->aht20_ && board->tick_counter_ % 10 == 0) {
                    board->aht20_->Measure();
                    board->ValidateAht20Reading();
                }

                // Dew heater auto mode — check every 30s
                if (board->dew_mode_ == 2 && board->dew_gpio_ >= 0 && board->tick_counter_ % 30 == 15) {
                    if (board->aht20_) {
                        board->aht20_->Measure();
                        float temp = board->aht20_->GetTemperature() + board->temp_offset_;
                        float dew = board->aht20_->GetDewPoint();
                        float spread = temp - dew;
                        bool should_heat = spread < board->dew_threshold_;
                        if (should_heat && !board->dew_heater_active_) {
                            int duty = (board->dew_power_ * 255) / 100;
                            ledc_set_duty(LEDC_LOW_SPEED_MODE, board->dew_ledc_ch_, duty);
                            ledc_update_duty(LEDC_LOW_SPEED_MODE, board->dew_ledc_ch_);
                            board->dew_heater_active_ = true;
                            ESP_LOGI(TAG, "Dew heater AUTO ON (spread=%.1f < %.1f)", spread, board->dew_threshold_);
                        } else if (!should_heat && board->dew_heater_active_) {
                            ledc_set_duty(LEDC_LOW_SPEED_MODE, board->dew_ledc_ch_, 0);
                            ledc_update_duty(LEDC_LOW_SPEED_MODE, board->dew_ledc_ch_);
                            board->dew_heater_active_ = false;
                            ESP_LOGI(TAG, "Dew heater AUTO OFF (spread=%.1f >= %.1f)", spread, board->dew_threshold_);
                        }
                    }
                }
            },
            .arg = this,
            .dispatch_method = ESP_TIMER_TASK,
            .name = "sg_update",
            .skip_unhandled_events = true,
        };
        esp_timer_create(&timer_args, &sg_update_timer_);
        // Tick every 1 second
        esp_timer_start_periodic(sg_update_timer_, 1000000);
        ESP_LOGI(TAG, "SkyGuard display timer started (1s tick, 9 pages, periodic fetch)");
    }

public:
    SkyGuardEliteBoard() : boot_button_(BOOT_BUTTON_GPIO) {
        ESP_LOGI(TAG, "=============================================");
        ESP_LOGI(TAG, "  SkyGuard AI — Astronomy Copilot");
        ESP_LOGI(TAG, "=============================================");

        // === Force dark mode BEFORE display init ===
        {
            Settings display_settings("display", true);
            display_settings.SetString("theme", "dark");
            ESP_LOGI(TAG, "Forced dark theme in NVS");
        }

        // === Standard board init (same as esp32s3-28touch) ===
        InitializeMclk();
        InitializeBacklight();
        InitializeSpi();
        InitializeDisplayI2c();
        InitializeDisplay();
        InitializeTouch();
        InitializeButtons();

        // === SkyGuard-specific init ===
        InitReadingCache();
        InitializeSensorI2c();
        InitializeSensors();
        InitializeGps();
        InitializeNetworkServices();
        RegisterMcpTools();
        InitializeSkyGuardDisplay();

        ESP_LOGI(TAG, "=============================================");
        ESP_LOGI(TAG, "  SkyGuard AI initialization complete");
        ESP_LOGI(TAG, "  TSL2591:  %s", tsl2591_ ? "OK" : "N/A");
        ESP_LOGI(TAG, "  AS7341:   %s", as7341_  ? "OK" : "N/A");
        ESP_LOGI(TAG, "  AHT20:    %s", aht20_   ? "OK" : "N/A");
        ESP_LOGI(TAG, "  GPS:      %s", gps_     ? "OK" : "N/A");
        ESP_LOGI(TAG, "  WiFiGeo:  %s", wifi_geo_ ? "OK" : "N/A");
        ESP_LOGI(TAG, "  Weather:  %s", weather_ ? "OK" : "N/A");
        ESP_LOGI(TAG, "  Tracker:  %s", sky_tracker_ ? "OK" : "N/A");
        ESP_LOGI(TAG, "  Pages:    %d", PAGE_COUNT);
        ESP_LOGI(TAG, "=============================================");
    }

    virtual Led* GetLed() override {
        static SingleLed led(RGB_LED_PIN);
        return &led;
    }

    virtual AudioCodec* GetAudioCodec() override {
        static Es8311AudioCodec* codec = nullptr;
        if (codec == nullptr) {
            // Use Es8311AudioCodec (official esp_codec_dev driver).
            // Read() extracts mono from stereo I2S + vTaskDelay(1) throttle.
            // PA (FM8002E) is active LOW → pa_inverted = true
            ESP_LOGI(TAG, "Creating Es8311AudioCodec (esp_codec_dev driver)");
            codec = new Es8311AudioCodec(
                (void*)display_i2c_bus_,     // I2C bus handle
                I2C_NUM_0,                    // I2C port
                AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
                AUDIO_I2S_GPIO_MCLK, AUDIO_I2S_GPIO_BCLK, AUDIO_I2S_GPIO_WS,
                AUDIO_I2S_GPIO_DOUT, AUDIO_I2S_GPIO_DIN,
                AUDIO_CODEC_PA_PIN,
                ES8311_I2C_ADDR,              // 0x30 (8-bit); esp_codec_dev does >>1 = 0x18
                true,                         // use_mclk = true
                true                          // pa_inverted = true (FM8002E active LOW)
            );
            // Set high output volume (default 30 is too low for small speaker)
            codec->SetOutputVolume(90);
        }
        return codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }

    virtual std::string GetBoardJson() override {
        auto& wifi = WifiManager::GetInstance();
        // Send "skyguard-ai" as type to webhook
        std::string json = R"({"type":"skyguard-ai",)";
        json += R"("name":")" + std::string(BOARD_NAME) + R"(",)";

        if (!wifi.IsConfigMode()) {
            json += R"("ssid":")" + wifi.GetSsid() + R"(",)";
            json += R"("rssi":)" + std::to_string(wifi.GetRssi()) + R"(,)";
            json += R"("channel":)" + std::to_string(wifi.GetChannel()) + R"(,)";
            json += R"("ip":")" + wifi.GetIpAddress() + R"(",)";
        }

        json += R"("mac":")" + SystemInfo::GetMacAddress() + R"("})";
        return json;
    }
};

DECLARE_BOARD(SkyGuardEliteBoard);
