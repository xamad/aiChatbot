#ifndef SKYGUARD_DISPLAY_H
#define SKYGUARD_DISPLAY_H

#include <lvgl.h>
#include <esp_timer.h>
#include <string>
#include <cstdint>

// Forward declarations
class Tsl2591Device;
class As7341Device;
class Aht20Device;
class GpsDevice;
class SkyGuardWeather;
class SkyGuardSkyTracker;

/*
 * SkyGuard AI — Custom LVGL Pages
 * ===================================
 * Full-width overlay on top of XiaoZhi's display (landscape 320x240).
 * During AI conversation (listening/speaking), overlay hides and
 * XiaoZhi's emoji + status text show.
 *
 * Layout 320x240 landscape:
 * ┌──────────────────────────────────────┐
 * │ [WiFi]          [WS][Mute][Batt]   │ 24px — XiaoZhi top_bar_
 * ├──────────────────────────────────────┤
 * │                                      │
 * │     SKYGUARD DATA PAGES (full 320)  │ 200px — sensor data
 * │                                      │
 * │           ● ● ● ○ ● ● ● ● ●       │ 16px — page dots
 * └──────────────────────────────────────┘
 *
 * Pages: SQM | Spectral+LP | Moon | Weather | Aircraft | Satellites | Env | GPS | Commands
 */

// Page index — 9 pages total
enum SkyGuardPage {
    PAGE_SQM = 0,        // Sky quality
    PAGE_SPECTRAL,       // Spectral bars + LP identification
    PAGE_MOON,           // Lunar phase + position
    PAGE_WEATHER,        // 6h forecast (OWM)
    PAGE_AIRCRAFT,       // Nearby aircraft (OpenSky)
    PAGE_SATELLITES,     // Satellite passes (N2YO)
    PAGE_METEOSAT,       // Satellite imagery (EUMETSAT/cloud map)
    PAGE_TELESCOPE,      // Telescope mount status (ASCOM Alpaca + INDI)
    PAGE_CONTROL,        // Remote control buttons (telescope, INDI, Stellarium)
    PAGE_ENVIRONMENT,    // Temp/humidity
    PAGE_GPS,            // GPS position
    PAGE_MEASURE,        // Commands (always last)
    PAGE_COUNT           // = 12
};

class SkyGuardDisplay {
public:
    SkyGuardDisplay();

    void SetSensors(Tsl2591Device* tsl, As7341Device* as7, Aht20Device* aht, GpsDevice* gps);
    void SetWeather(SkyGuardWeather* weather) { weather_ = weather; }
    void SetSkyTracker(SkyGuardSkyTracker* tracker) { sky_tracker_ = tracker; }
    void SetCalibration(float temp_off, float hum_off) { temp_offset_ = temp_off; hum_offset_ = hum_off; }
    void SetFallbackPosition(float lat, float lon, const char* source);
    void SetLocationName(const char* name);

    // Satellite image for Meteosat page
    void SetSatelliteImage(uint16_t* rgb565, int w, int h);
    bool NeedsSatelliteImage() const;

    // GPS mini-map image — pass raw PNG data, decoded under LVGL lock
    // px_x, px_y = pixel position of user's location within the 256x256 tile
    void SetGpsMapPng(uint8_t* png_data, int png_len, float lat, float lon, int px_x, int px_y);
    bool NeedsGpsMapImage(float& lat, float& lon) const;

    // ASCOM Alpaca telescope
    struct AlpacaStatus {
        bool connected = false;
        bool tracking = false;
        bool slewing = false;
        bool at_park = false;
        double ra = 0;       // hours
        double dec = 0;      // degrees
        double alt = 0;      // degrees
        double az = 0;       // degrees
        int pier_side = -1;  // 0=east, 1=west, -1=unknown
        uint32_t last_update = 0;
    };
    void SetAlpacaUrl(const std::string& url) { alpaca_url_ = url; }
    void SetAlpacaStatus(const AlpacaStatus& s) { alpaca_status_ = s; }
    const AlpacaStatus& GetAlpacaStatus() const { return alpaca_status_; }

    // INDI status
    struct IndiStatus {
        bool configured = false;
        bool server_running = false;
        char active_profile[32] = {};
        int driver_count = 0;
        uint32_t last_update = 0;
    };
    void SetIndiUrl(const std::string& url) { indi_url_ = url; }
    void SetIndiStatus(const IndiStatus& s) { indi_status_ = s; }
    const IndiStatus& GetIndiStatus() const { return indi_status_; }

    // Control page callback — board sets this to execute commands
    using ControlCallback = void(*)(void* ctx, const char* command, const char* param);
    void SetControlCallback(ControlCallback cb, void* ctx) { ctrl_cb_ = cb; ctrl_ctx_ = ctx; }
    bool HasPosition(float& lat, float& lon) const;
    double GetCurrentJD() const;
    double GetCurrentJD0() const;

    void Setup();
    void Update();

    void NextPage();
    void PrevPage();
    void SetPage(SkyGuardPage page);
    SkyGuardPage GetPage() const { return current_page_; }

    void TriggerMeasurement();
    void TriggerAssistant();
    void ToggleNightMode();
    bool IsNightMode() const { return night_mode_; }
    void SetVisible(bool visible);
    bool IsMeasuring() const { return measuring_; }

    void ShowBootLoader();
    void HideBootLoader();
    bool IsBootLoaderVisible() const { return boot_loader_visible_; }

private:
    // Sensors (not owned)
    Tsl2591Device* tsl2591_ = nullptr;
    As7341Device* as7341_ = nullptr;
    Aht20Device* aht20_ = nullptr;
    GpsDevice* gps_ = nullptr;
    float temp_offset_ = -2.4f;
    float hum_offset_ = 0.0f;

    // Network data providers (not owned)
    SkyGuardWeather* weather_ = nullptr;
    SkyGuardSkyTracker* sky_tracker_ = nullptr;

    // LVGL objects
    lv_obj_t* overlay_ = nullptr;        // Main overlay (full width)
    lv_obj_t* data_area_ = nullptr;      // Data page area
    lv_obj_t* page_indicator_ = nullptr; // Dot indicators
    lv_obj_t* measure_btn_ = nullptr;
    lv_obj_t* assist_btn_ = nullptr;
    lv_obj_t* night_btn_ = nullptr;

    // Page labels (text pages)
    lv_obj_t* data_title_ = nullptr;
    lv_obj_t* title_icon_ = nullptr;        // Colored dot before title
    lv_obj_t* title_accent_ = nullptr;      // Thin colored bar under title
    lv_obj_t* data_lines_[8] = {};
    int data_line_count_ = 0;

    // Dashboard "SkyGuard AI" — modern instrument panel
    // Left card: SQM arc gauge + Bortle bar + mini spectrum
    lv_obj_t* dash_left_card_ = nullptr;    // Rounded container
    lv_obj_t* sqm_arc_ = nullptr;           // 270° arc gauge
    lv_obj_t* sqm_big_value_ = nullptr;     // "19.82" — large font in arc center
    lv_obj_t* sqm_unit_label_ = nullptr;    // "mag/arcsec²"
    lv_obj_t* sqm_bortle_bar_ = nullptr;    // Bortle color bar
    lv_obj_t* sqm_quality_label_ = nullptr; // "Bortle 4 - Buono"
    lv_obj_t* dash_spec_bar_[8] = {};       // Mini spectral bars (colored)
    // Right card: 8 info rows (pixel-art icon + label + value)
    lv_obj_t* dash_right_card_ = nullptr;   // Rounded container
    static constexpr int DASH_ROWS = 8;
    lv_obj_t* dash_dot_[DASH_ROWS] = {};    // 10x10 pixel art icon canvases
    uint8_t* dash_dot_buf_[DASH_ROWS] = {}; // Canvas buffers
    lv_obj_t* dash_lbl_[DASH_ROWS] = {};    // Category text ("Luna", "Temp"...)
    lv_obj_t* dash_val_[DASH_ROWS] = {};    // Value text ("23%", "18°C"...)
    // Bottom bar: location
    lv_obj_t* dash_bottom_bar_ = nullptr;   // Rounded container
    lv_obj_t* dash_location_ = nullptr;     // "Asti, IT"
    lv_obj_t* dash_sensor_status_ = nullptr; // Sensor status icons
    bool dash_built_ = false;
    char location_name_[64] = {};           // Reverse geocoded address
    void BuildDashboard();
    void UpdateDashboard();
    void ShowDashboard();
    void HideDashboard();
    static void DrawDashIcon(lv_obj_t* canvas, int icon_idx, lv_color_t color);

    // Spectral page — card-based layout
    lv_obj_t* spectral_left_card_ = nullptr;   // Bars card container
    lv_obj_t* spectral_bars_[8] = {};          // Colored rectangles
    lv_obj_t* spectral_labels_[8] = {};        // "415" labels below bars
    lv_obj_t* spectral_values_[8] = {};        // Value labels above bars
    lv_obj_t* spectral_container_ = nullptr;   // Legacy (kept for hide/show)
    bool spectral_built_ = false;

    // Right card — LP analysis panel
    lv_obj_t* spectral_right_card_ = nullptr;  // LP analysis card
    lv_obj_t* spectral_sqi_arc_ = nullptr;     // SQI arc gauge (60px)
    lv_obj_t* spectral_sqi_value_ = nullptr;   // "72%" in arc center
    lv_obj_t* spectral_sqi_label_ = nullptr;   // "Qualita Cielo" under arc
    lv_obj_t* spectral_lp_source_ = nullptr;   // "Sorgente: LED Bianco"
    lv_obj_t* spectral_sqi_ = nullptr;         // "SQI: 72%" (kept for compat)
    lv_obj_t* spectral_ratios_ = nullptr;      // "Blu:0.83 Na:0.42"
    lv_obj_t* spectral_lp_verdict_ = nullptr;  // "Buono" / "Inquinato"

    // Moon page — phase visualization
    lv_obj_t* moon_canvas_ = nullptr;
    uint8_t* moon_canvas_buf_ = nullptr;
    static constexpr int MOON_SIZE = 48;

    // Weather page — 6-column forecast
    lv_obj_t* weather_container_ = nullptr;
    lv_obj_t* weather_time_[6] = {};
    lv_obj_t* weather_icon_canvas_[6] = {};   // 20x20 drawn weather icons
    lv_obj_t* weather_cloud_bar_[6] = {};
    lv_obj_t* weather_cloud_val_[6] = {};
    lv_obj_t* weather_wind_[6] = {};
    lv_obj_t* weather_temp_[6] = {};
    lv_obj_t* weather_hum_[6] = {};           // Humidity %
    lv_obj_t* weather_seeing_[6] = {};        // Seeing estimate
    lv_obj_t* weather_desc_[6] = {};          // Short description text
    lv_obj_t* weather_verdict_ = nullptr;      // Astronomy verdict at bottom
    lv_obj_t* weather_location_ = nullptr;     // Location name from OWM
    // Daily forecast row (5 days)
    lv_obj_t* weather_daily_day_[5] = {};      // "Gio", "Ven"...
    lv_obj_t* weather_daily_temp_[5] = {};     // "8/22"
    lv_obj_t* weather_daily_cloud_[5] = {};    // "45%"
    lv_obj_t* weather_daily_icon_[5] = {};     // Mini icon canvas
    uint8_t* weather_daily_icon_bufs_[5] = {};
    lv_obj_t* weather_daily_sep_ = nullptr;    // Separator line
    uint8_t* weather_icon_bufs_[6] = {};
    bool weather_built_ = false;
    static constexpr int WICON_SIZE = 32;
    static constexpr int WICON_MINI = 20;

    static void DrawWeatherIcon(lv_obj_t* canvas, int clouds, const char* desc);

    // Radar display for aircraft page
    lv_obj_t* radar_container_ = nullptr;     // Container for radar circle
    lv_obj_t* radar_bg_ = nullptr;            // Background circle
    lv_obj_t* radar_cross_h_ = nullptr;       // Horizontal crosshair
    lv_obj_t* radar_cross_v_ = nullptr;       // Vertical crosshair
    lv_obj_t* radar_ring_mid_ = nullptr;      // Middle range ring
    lv_obj_t* radar_dots_[8] = {};            // Aircraft dots (max 8)
    lv_obj_t* radar_trails_[8] = {};          // Heading trail lines (thin rects)
    lv_obj_t* radar_callsigns_[8] = {};       // Callsign labels near dots
    lv_obj_t* radar_info_lines_[4] = {};      // Info text right side
    lv_obj_t* radar_range_label_ = nullptr;   // Range label ("50km")
    lv_obj_t* radar_legend_ = nullptr;        // Color legend
    bool radar_built_ = false;

    // Satellite sky dome
    lv_obj_t* sat_dome_container_ = nullptr;
    lv_obj_t* sat_dome_bg_ = nullptr;           // Sky dome circle
    lv_obj_t* sat_dome_cross_h_ = nullptr;
    lv_obj_t* sat_dome_cross_v_ = nullptr;
    lv_obj_t* sat_dome_ring_ = nullptr;          // 45° elevation ring
    lv_obj_t* sat_dots_[6] = {};                 // Satellite dots
    lv_obj_t* sat_trail_dots_[6][5] = {};        // Trail dots for pass arc (5 points)
    lv_obj_t* sat_labels_[6] = {};               // Satellite name labels
    lv_obj_t* sat_info_lines_[3] = {};           // Info text right side
    lv_obj_t* sat_legend_ = nullptr;              // Color legend
    bool sat_dome_built_ = false;
    void HideSatDome();
    void ShowSatDome();

    // Meteosat page — satellite IR image from meteociel.fr
    lv_obj_t* meteosat_canvas_ = nullptr;
    uint8_t* meteosat_canvas_buf_ = nullptr;
    lv_obj_t* meteosat_overlay_status_ = nullptr;  // "Aggiornato Xm fa" overlay
    lv_obj_t* meteosat_overlay_source_ = nullptr;  // "meteociel.fr" overlay
public:
    static constexpr int METEO_W = 304;
    static constexpr int METEO_H = 178;
    static constexpr int GPS_MAP_W = 140;
    static constexpr int GPS_MAP_H = 140;
private:
    bool meteosat_built_ = false;
    uint16_t* sat_image_rgb565_ = nullptr;  // Decoded satellite frame (METEO_W * METEO_H)
    bool sat_image_valid_ = false;
    uint32_t sat_image_fetch_ms_ = 0;
    void HideMeteosat();
    void ShowMeteosat();

    // GPS mini-map — lv_image widget with LVGL's built-in PNG decoder
    lv_obj_t* gps_map_img_ = nullptr;       // lv_image widget
    uint8_t* gps_map_png_data_ = nullptr;    // Raw PNG data (SPIRAM, persistent)
    int gps_map_png_len_ = 0;
    lv_image_dsc_t gps_map_dsc_ = {};        // LVGL image descriptor
    bool gps_map_valid_ = false;
    float gps_map_lat_ = 0;
    float gps_map_lon_ = 0;
    bool gps_map_built_ = false;
    void HideGpsMap();
    void ShowGpsMap();

    // Telescope — Alpaca + INDI data (private storage)
    AlpacaStatus alpaca_status_;
    std::string alpaca_url_;
    IndiStatus indi_status_;
    std::string indi_url_;

    // Control page — scrollable button list for all commands
    ControlCallback ctrl_cb_ = nullptr;
    void* ctrl_ctx_ = nullptr;
    static constexpr int CTRL_BTN_MAX = 24;
    lv_obj_t* ctrl_btns_[CTRL_BTN_MAX] = {};
    lv_obj_t* ctrl_scroll_container_ = nullptr;
    int ctrl_btn_count_ = 0;
    bool ctrl_built_ = false;
    void HideControlBtns();
    void ShowControlBtns();

    // Confirmation dialog for control buttons
    lv_obj_t* confirm_box_ = nullptr;
    int confirm_pending_idx_ = -1;  // Button index pending confirmation
    void ShowConfirmDialog(int btn_idx);
    void DismissConfirmDialog();

    // Environment page — card layout with arc gauges
    lv_obj_t* env_container_ = nullptr;      // Wrapper for hide/show
    lv_obj_t* env_left_card_ = nullptr;      // Temp+Hum arcs card
    lv_obj_t* env_right_card_ = nullptr;     // Dew point details card
    lv_obj_t* env_temp_arc_ = nullptr;       // Temperature arc (0..50°C)
    lv_obj_t* env_temp_value_ = nullptr;     // "22.3°"
    lv_obj_t* env_temp_label_ = nullptr;     // "Temperatura"
    lv_obj_t* env_hum_arc_ = nullptr;        // Humidity arc (0..100%)
    lv_obj_t* env_hum_value_ = nullptr;      // "58%"
    lv_obj_t* env_hum_label_ = nullptr;      // "Umidita"
    lv_obj_t* env_dew_val_ = nullptr;        // "Rugiada: 12.3°C"
    lv_obj_t* env_spread_val_ = nullptr;     // "Spread: 10.0°C"
    lv_obj_t* env_cond_val_ = nullptr;       // "Condensa: OK"
    lv_obj_t* env_sensor_lbl_ = nullptr;     // "AHT20"
    bool env_built_ = false;
    void HideEnvCards();
    void ShowEnvCards();

    // Moon page — card layout
    lv_obj_t* moon_container_ = nullptr;     // Wrapper for cards
    lv_obj_t* moon_left_card_ = nullptr;     // Moon canvas + phase info
    lv_obj_t* moon_right_card_ = nullptr;    // Night timing details
    lv_obj_t* moon_phase_lbl_ = nullptr;     // "Gibbosa Cresc."
    lv_obj_t* moon_illum_lbl_ = nullptr;     // "78%"
    lv_obj_t* moon_night_arc_ = nullptr;     // Dark hours arc (0-12h)
    lv_obj_t* moon_night_val_ = nullptr;     // "8.2h" in arc
    lv_obj_t* moon_moonless_arc_ = nullptr;  // Moonless hours arc (inner)
    lv_obj_t* moon_moonless_val_ = nullptr;  // "5.1h" in arc
    lv_obj_t* moon_info_[6] = {};            // 6 info lines in right card
    bool moon_cards_built_ = false;
    void HideMoonCards();
    void ShowMoonCards();

    // GPS page — card layout
    lv_obj_t* gps_container_ = nullptr;      // Wrapper for cards
    lv_obj_t* gps_left_card_ = nullptr;      // Coordinates + sats card
    lv_obj_t* gps_right_card_ = nullptr;     // Map card (wraps gps_map_img_)
    lv_obj_t* gps_info_[7] = {};             // 7 info lines in left card
    bool gps_cards_built_ = false;
    void HideGpsCards();
    void ShowGpsCards();

    // Telescope page — card layout
    lv_obj_t* scope_container_ = nullptr;    // Wrapper for cards
    lv_obj_t* scope_left_card_ = nullptr;    // Status + mount state
    lv_obj_t* scope_right_card_ = nullptr;   // Coordinates card
    lv_obj_t* scope_status_lbl_ = nullptr;   // "TRACKING" big
    lv_obj_t* scope_info_[6] = {};           // 6 info lines
    bool scope_cards_built_ = false;
    void HideScopeCards();
    void ShowScopeCards();

    // Countdown measurement overlay
    bool measuring_ = false;
    int countdown_remaining_ = 0;
    esp_timer_handle_t countdown_timer_ = nullptr;
    lv_obj_t* countdown_container_ = nullptr; // Full overlay for countdown
    lv_obj_t* countdown_arc_ = nullptr;
    lv_obj_t* countdown_label_ = nullptr;     // "10", "9"...
    lv_obj_t* countdown_text_ = nullptr;      // "Punta allo Zenit"
    lv_obj_t* countdown_title_ = nullptr;     // "MISURAZIONE SQM"

    // Boot loader overlay
    lv_obj_t* boot_loader_container_ = nullptr;
    lv_obj_t* boot_spinner_ = nullptr;
    lv_obj_t* boot_title_ = nullptr;
    lv_obj_t* boot_status_ = nullptr;
    bool boot_loader_visible_ = false;

    // Fallback position (from WiFi geolocation)
    float fallback_lat_ = 0;
    float fallback_lon_ = 0;
    bool fallback_valid_ = false;
    char fallback_source_[16] = {};

    SkyGuardPage current_page_ = PAGE_SQM;
    bool visible_ = true;
    bool night_mode_ = false;

    // Auto-scroll
    bool auto_scroll_enabled_ = true;
    uint32_t auto_scroll_interval_ms_ = 5000;
    uint32_t last_page_change_ms_ = 0;

    void ApplyNightMode();
    void ApplyNormalMode();

    // Page builders
    void BuildPageSqm();
    void BuildPageSpectral();
    void BuildPageMoon();
    void BuildPageWeather();
    void BuildPageAircraft();
    void BuildPageSatellites();
    void BuildPageMeteosat();
    void BuildPageTelescope();
    void BuildPageEnvironment();
    void BuildPageGps();
    void BuildPageControl();
    void BuildPageMeasure();
    void ClearDataArea();

    // Page updaters
    void UpdatePageSqm();
    void UpdatePageSpectral();
    void UpdatePageMoon();
    void UpdatePageWeather();
    void UpdatePageAircraft();
    void UpdatePageSatellites();
    void UpdatePageMeteosat();
    void UpdatePageTelescope();
    void UpdatePageEnvironment();
    void UpdatePageGps();

    void UpdatePageIndicator();
    void HideSqmBig();
    void ShowSqmBig();
    void HideSpectralBars();
    void ShowSpectralBars();
    void HideMoonCanvas();
    void ShowMoonCanvas();
    void DrawMoonPhase(float illumination, uint8_t phaseIndex);
    void HideWeatherBars();
    void ShowWeatherBars();
    void HideRadar();
    void ShowRadar();

    // Countdown measurement
    void StartCountdown();
    static void CountdownTickCb(void* arg);
    void CountdownTick();
    void FinishMeasurement();
    void HideCountdown();

    static const lv_font_t* GetLargeFont();
    static const lv_font_t* GetMediumFont();
    static const lv_font_t* GetSmallFont();
    static const lv_font_t* GetTinyFont();
};

#endif // SKYGUARD_DISPLAY_H
