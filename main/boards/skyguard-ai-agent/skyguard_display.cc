#include "skyguard_display.h"
#include "star_emoji.h"
#include "sensors/tsl2591_device.h"
#include "sensors/as7341_device.h"
#include "sensors/aht20_device.h"
#include "sensors/gps_device.h"
#include "skyguard_astro.h"
#include "skyguard_weather.h"
#include "skyguard_sky_tracker.h"
#include "application.h"

#include <esp_log.h>
#include <esp_lvgl_port.h>
#include <esp_heap_caps.h>
#include <driver/ledc.h>
#include <cstdio>

#include <cmath>
#include <ctime>
#include <cstring>
#include <inttypes.h>
#include <esp_netif.h>

// Private LVGL header — needed to adjust gesture_limit and gesture_min_velocity
// fields on lv_indev_t struct (no public setter API in LVGL v9)
#include "indev/lv_indev_private.h"

#define TAG "SkyGuardUI"

// ==========================================================================
// COLOR PALETTE — Pure black background, high-contrast text
// ==========================================================================

// Normal mode — dark gray background + white text = dark mode
#define SG_BG_COLOR         lv_color_hex(0x1A1A2E)  // Dark gray-blue
#define SG_TEXT_COLOR        lv_color_hex(0xE0E0E0)  // Light gray (near white)
#define SG_TITLE_COLOR       lv_color_hex(0x55AAFF)  // Bright sky blue
#define SG_VALUE_COLOR       lv_color_hex(0xFFFFFF)  // White
#define SG_GOOD_COLOR        lv_color_hex(0x00DD66)  // Bright green
#define SG_WARN_COLOR        lv_color_hex(0xFFBB00)  // Amber
#define SG_BAD_COLOR         lv_color_hex(0xFF3333)  // Red
#define SG_DIM_COLOR         lv_color_hex(0x556677)  // Dim secondary
#define SG_BTN_COLOR         lv_color_hex(0x1A3366)  // Button blue
#define SG_BTN_PRESS_COLOR   lv_color_hex(0x2255AA)  // Button pressed
#define SG_DOT_ACTIVE        lv_color_hex(0x55AAFF)  // Active page dot
#define SG_DOT_INACTIVE      lv_color_hex(0x222244)  // Inactive page dot

// Night mode (astronomy red)
#define SG_NIGHT_BG          lv_color_hex(0x000000)
#define SG_NIGHT_TEXT        lv_color_hex(0x771111)
#define SG_NIGHT_TITLE       lv_color_hex(0xBB2222)
#define SG_NIGHT_VALUE       lv_color_hex(0x991111)
#define SG_NIGHT_DOT_ACTIVE  lv_color_hex(0xBB2222)
#define SG_NIGHT_DOT_INACTIVE lv_color_hex(0x220000)
#define SG_NIGHT_BTN         lv_color_hex(0x331111)
#define SG_NIGHT_CARD_BG     lv_color_hex(0x0A0000)
#define SG_NIGHT_CARD_BORDER lv_color_hex(0x220000)
#define SG_NIGHT_DIM         lv_color_hex(0x440808)
#define SG_NIGHT_ARC_BG      lv_color_hex(0x110000)
#define SG_NIGHT_ARC_IND     lv_color_hex(0x771111)

// Wavelength colors for AS7341 spectral bars
static const lv_color_t kWavelengthColors[8] = {
    lv_color_hex(0x7700EE),  // F1 415nm — violet
    lv_color_hex(0x0044FF),  // F2 445nm — blue
    lv_color_hex(0x00BBFF),  // F3 480nm — cyan
    lv_color_hex(0x00CC44),  // F4 515nm — green
    lv_color_hex(0x99CC00),  // F5 555nm — yellow-green
    lv_color_hex(0xFF8800),  // F6 590nm — orange
    lv_color_hex(0xFF2200),  // F7 630nm — red
    lv_color_hex(0xBB0000),  // F8 680nm — deep red
};

static const char* kWavelengthNames[8] = {
    "415", "445", "480", "515", "555", "590", "630", "680"
};

// ==========================================================================
// FONTS
// ==========================================================================

const lv_font_t* SkyGuardDisplay::GetLargeFont() {
    return &lv_font_montserrat_28;
}

const lv_font_t* SkyGuardDisplay::GetMediumFont() {
    return &lv_font_montserrat_20;
}

const lv_font_t* SkyGuardDisplay::GetSmallFont() {
    return &lv_font_montserrat_14;
}

const lv_font_t* SkyGuardDisplay::GetTinyFont() {
    return &lv_font_montserrat_10;
}

// ==========================================================================
// CONSTRUCTOR
// ==========================================================================

SkyGuardDisplay::SkyGuardDisplay() {}

void SkyGuardDisplay::SetSensors(Tsl2591Device* tsl, As7341Device* as7,
                                  Aht20Device* aht, GpsDevice* gps) {
    tsl2591_ = tsl;
    as7341_ = as7;
    aht20_ = aht;
    gps_ = gps;
}

void SkyGuardDisplay::SetFallbackPosition(float lat, float lon, const char* source) {
    fallback_lat_ = lat;
    fallback_lon_ = lon;
    fallback_valid_ = true;
    strncpy(fallback_source_, source ? source : "fallback", sizeof(fallback_source_) - 1);
    fallback_source_[sizeof(fallback_source_) - 1] = '\0';
}

bool SkyGuardDisplay::HasPosition(float& lat, float& lon) const {
    // GPS first
    if (gps_ && gps_->HasFix()) {
        lat = gps_->GetLatitude();
        lon = gps_->GetLongitude();
        return true;
    }
    // WiFi geolocation fallback
    if (fallback_valid_) {
        lat = fallback_lat_;
        lon = fallback_lon_;
        return true;
    }
    return false;
}

// Calculate Julian Date from system time (when GPS unavailable)
double SkyGuardDisplay::GetCurrentJD() const {
    if (gps_ && gps_->HasFix()) {
        return gps_->GetJulianDate();
    }
    // Use system clock (NTP-synced via XiaoZhi server connection)
    time_t now;
    time(&now);
    struct tm* utc = gmtime(&now);
    if (!utc || utc->tm_year < 100) {
        // System time not set — use a reasonable default
        return 2460384.5;  // ~2024-03-10
    }
    int y = utc->tm_year + 1900;
    int m = utc->tm_mon + 1;
    int d = utc->tm_mday;
    if (m <= 2) { y--; m += 12; }
    int A = y / 100;
    int B = 2 - A + A / 4;
    double jd = (int)(365.25 * (y + 4716)) + (int)(30.6001 * (m + 1)) + d + B - 1524.5;
    jd += (utc->tm_hour + utc->tm_min / 60.0 + utc->tm_sec / 3600.0) / 24.0;
    return jd;
}

double SkyGuardDisplay::GetCurrentJD0() const {
    if (gps_ && gps_->HasFix()) {
        return gps_->GetJulianDate0();
    }
    // JD at 0h UT = floor(JD - 0.5) + 0.5
    double jd = GetCurrentJD();
    return floor(jd - 0.5) + 0.5;
}

// ==========================================================================
// SETUP — Build full-width LVGL overlay below XiaoZhi top_bar
// ==========================================================================

void SkyGuardDisplay::Setup() {
    ESP_LOGI(TAG, "Setting up SkyGuard display (full-width, dark mode, %d pages)", PAGE_COUNT);

    if (!lvgl_port_lock(3000)) {
        ESP_LOGE(TAG, "Failed to lock LVGL port");
        return;
    }

    lv_obj_t* screen = lv_screen_active();
    if (!screen) {
        ESP_LOGE(TAG, "LVGL screen not ready");
        lvgl_port_unlock();
        return;
    }

    // Force dark background on screen + log current state
    lv_color_t cur_bg = lv_obj_get_style_bg_color(screen, 0);
    lv_opa_t cur_opa = lv_obj_get_style_bg_opa(screen, 0);
    ESP_LOGW(TAG, "Screen bg BEFORE: color=0x%04X opa=%d", lv_color_to_u16(cur_bg), cur_opa);

    lv_obj_set_style_bg_color(screen, SG_BG_COLOR, 0);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, 0);
    lv_obj_set_style_text_color(screen, SG_TEXT_COLOR, 0);

    // Force container (child 0) + top_bar (child 3) to dark bg
    uint32_t child_count = lv_obj_get_child_count(screen);
    ESP_LOGI(TAG, "Screen has %lu children", (unsigned long)child_count);

    for (uint32_t i = 0; i < child_count; i++) {
        lv_obj_t* child = lv_obj_get_child(screen, i);
        if (child) {
            lv_color_t cbg = lv_obj_get_style_bg_color(child, 0);
            lv_opa_t copa = lv_obj_get_style_bg_opa(child, 0);
            ESP_LOGI(TAG, "  child[%lu] bg=0x%04X opa=%d", (unsigned long)i, lv_color_to_u16(cbg), copa);
        }
    }

    // Container (child 0) — main background, full screen
    if (child_count > 0) {
        lv_obj_t* container = lv_obj_get_child(screen, 0);
        if (container) {
            lv_obj_set_style_bg_color(container, SG_BG_COLOR, 0);
            lv_obj_set_style_bg_opa(container, LV_OPA_COVER, 0);
            lv_obj_set_style_bg_image_src(container, nullptr, 0);
            lv_obj_set_style_text_color(container, SG_TEXT_COLOR, 0);
        }
    }

    // Top bar (child 3) — status icons
    if (child_count > 3) {
        lv_obj_t* top_bar = lv_obj_get_child(screen, 3);
        if (top_bar) {
            lv_obj_set_style_bg_color(top_bar, SG_BG_COLOR, 0);
            lv_obj_set_style_text_color(top_bar, SG_TEXT_COLOR, 0);
        }
    }

    // Hide XiaoZhi bottom_bar (child[4]) when SkyGuard is active
    if (child_count > 4) {
        lv_obj_t* bottom_bar = lv_obj_get_child(screen, 4);
        if (bottom_bar) {
            lv_obj_add_flag(bottom_bar, LV_OBJ_FLAG_HIDDEN);
        }
    }

    // Hide emoji_box (child[1]) in idle — SkyGuard data takes priority
    if (child_count > 1) {
        lv_obj_t* emoji_box = lv_obj_get_child(screen, 1);
        if (emoji_box) {
            lv_obj_add_flag(emoji_box, LV_OBJ_FLAG_HIDDEN);
        }
    }

    int top_y = 24;   // Below XiaoZhi top_bar
    int w = 320;
    int h = 240;
    int data_h = h - top_y;  // 216px available

    // Main overlay container — full width
    overlay_ = lv_obj_create(screen);
    lv_obj_remove_style_all(overlay_);
    lv_obj_set_size(overlay_, w, data_h);
    lv_obj_set_pos(overlay_, 0, top_y);
    lv_obj_set_style_bg_color(overlay_, SG_BG_COLOR, 0);
    lv_obj_set_style_bg_opa(overlay_, LV_OPA_COVER, 0);
    lv_obj_clear_flag(overlay_, LV_OBJ_FLAG_SCROLLABLE);

    // Data area — inside overlay, with padding
    int data_area_h = data_h - 20;  // minus page dots
    data_area_ = lv_obj_create(overlay_);
    lv_obj_remove_style_all(data_area_);
    lv_obj_set_size(data_area_, w - 16, data_area_h);
    lv_obj_set_pos(data_area_, 8, 2);
    lv_obj_set_style_bg_opa(data_area_, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(data_area_, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(data_area_, LV_OBJ_FLAG_CLICKABLE);

    // =========================================================================
    // CRITICAL: LVGL v9 gesture fix
    // =========================================================================
    lv_obj_clear_flag(data_area_, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_clear_flag(data_area_, LV_OBJ_FLAG_SCROLL_CHAIN_HOR);
    lv_obj_clear_flag(data_area_, LV_OBJ_FLAG_SCROLL_CHAIN_VER);
    lv_obj_clear_flag(overlay_, LV_OBJ_FLAG_GESTURE_BUBBLE);
    lv_obj_clear_flag(overlay_, LV_OBJ_FLAG_SCROLL_CHAIN_HOR);
    lv_obj_clear_flag(overlay_, LV_OBJ_FLAG_SCROLL_CHAIN_VER);
    lv_obj_clear_flag(screen, LV_OBJ_FLAG_SCROLLABLE);

    // Title icon dot (colored circle before title)
    title_icon_ = lv_obj_create(data_area_);
    lv_obj_remove_style_all(title_icon_);
    lv_obj_set_size(title_icon_, 8, 8);
    lv_obj_set_pos(title_icon_, 0, 4);
    lv_obj_set_style_radius(title_icon_, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(title_icon_, SG_TITLE_COLOR, 0);
    lv_obj_set_style_bg_opa(title_icon_, LV_OPA_COVER, 0);

    // Title label (offset right for icon dot)
    data_title_ = lv_label_create(data_area_);
    lv_obj_set_style_text_font(data_title_, GetSmallFont(), 0);
    lv_obj_set_style_text_color(data_title_, SG_TITLE_COLOR, 0);
    lv_label_set_text(data_title_, "");
    lv_obj_set_pos(data_title_, 12, 0);

    // Title accent bar (thin colored line under title)
    title_accent_ = lv_obj_create(data_area_);
    lv_obj_remove_style_all(title_accent_);
    lv_obj_set_size(title_accent_, w - 32, 2);
    lv_obj_set_pos(title_accent_, 0, 16);
    lv_obj_set_style_bg_color(title_accent_, SG_TITLE_COLOR, 0);
    lv_obj_set_style_bg_opa(title_accent_, 80, 0);
    lv_obj_set_style_radius(title_accent_, 1, 0);

    // Data lines (for text-based pages)
    for (int i = 0; i < 8; i++) {
        data_lines_[i] = lv_label_create(data_area_);
        lv_obj_set_style_text_font(data_lines_[i], GetSmallFont(), 0);
        lv_obj_set_style_text_color(data_lines_[i], SG_TEXT_COLOR, 0);
        lv_label_set_text(data_lines_[i], "");
        lv_obj_set_pos(data_lines_[i], 0, 18 + i * 22);
        lv_obj_set_width(data_lines_[i], w - 32);
        lv_label_set_long_mode(data_lines_[i], LV_LABEL_LONG_WRAP);
        lv_obj_add_flag(data_lines_[i], LV_OBJ_FLAG_HIDDEN);
    }

    // =====================================================================
    // Dashboard "SkyGuard AI" — Modern instrument panel
    // Left card:  Arc gauge + SQM value + Bortle bar + mini spectrum
    // Right card: 8 rows with pixel-art icons + category + value
    // Bottom bar: Location name (reverse geocoded)
    // =====================================================================
    {
        // Card background color constant
        lv_color_t card_bg = lv_color_hex(0x111122);
        lv_color_t card_border = lv_color_hex(0x2A2A44);

        // --- LEFT CARD: SQM gauge + mini spectrum ---
        dash_left_card_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(dash_left_card_);
        lv_obj_set_size(dash_left_card_, 138, 158);
        lv_obj_set_pos(dash_left_card_, 2, 16);
        lv_obj_set_style_bg_color(dash_left_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(dash_left_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(dash_left_card_, 10, 0);
        lv_obj_set_style_border_color(dash_left_card_, card_border, 0);
        lv_obj_set_style_border_width(dash_left_card_, 1, 0);
        lv_obj_set_style_border_opa(dash_left_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(dash_left_card_, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_add_flag(dash_left_card_, LV_OBJ_FLAG_HIDDEN);

        // Arc gauge — 270° sweep, 96px diameter
        sqm_arc_ = lv_arc_create(dash_left_card_);
        lv_obj_set_size(sqm_arc_, 96, 96);
        lv_obj_set_pos(sqm_arc_, 21, 2);
        lv_arc_set_rotation(sqm_arc_, 135);
        lv_arc_set_bg_angles(sqm_arc_, 0, 270);
        lv_arc_set_range(sqm_arc_, 0, 100);
        lv_arc_set_value(sqm_arc_, 0);
        lv_obj_set_style_arc_color(sqm_arc_, lv_color_hex(0x222244), LV_PART_MAIN);
        lv_obj_set_style_arc_width(sqm_arc_, 7, LV_PART_MAIN);
        lv_obj_set_style_arc_color(sqm_arc_, SG_GOOD_COLOR, LV_PART_INDICATOR);
        lv_obj_set_style_arc_width(sqm_arc_, 7, LV_PART_INDICATOR);
        lv_obj_set_style_arc_rounded(sqm_arc_, true, LV_PART_INDICATOR);
        lv_obj_set_style_bg_opa(sqm_arc_, LV_OPA_TRANSP, LV_PART_KNOB);
        lv_obj_set_style_pad_all(sqm_arc_, 0, LV_PART_KNOB);
        lv_obj_clear_flag(sqm_arc_, LV_OBJ_FLAG_CLICKABLE);

        // Big SQM value — centered in the arc
        sqm_big_value_ = lv_label_create(dash_left_card_);
        lv_obj_set_style_text_font(sqm_big_value_, &lv_font_montserrat_28, 0);
        lv_obj_set_style_text_color(sqm_big_value_, lv_color_white(), 0);
        lv_label_set_text(sqm_big_value_, "--.-");
        lv_obj_set_pos(sqm_big_value_, 25, 30);

        // Unit label
        sqm_unit_label_ = lv_label_create(dash_left_card_);
        lv_obj_set_style_text_font(sqm_unit_label_, &lv_font_montserrat_10, 0);
        lv_obj_set_style_text_color(sqm_unit_label_, SG_DIM_COLOR, 0);
        lv_label_set_text(sqm_unit_label_, "mag/arcsec\xC2\xB2");
        lv_obj_set_pos(sqm_unit_label_, 30, 60);

        // Bortle bar
        sqm_bortle_bar_ = lv_obj_create(dash_left_card_);
        lv_obj_remove_style_all(sqm_bortle_bar_);
        lv_obj_set_size(sqm_bortle_bar_, 100, 4);
        lv_obj_set_pos(sqm_bortle_bar_, 19, 100);
        lv_obj_set_style_bg_color(sqm_bortle_bar_, SG_GOOD_COLOR, 0);
        lv_obj_set_style_bg_opa(sqm_bortle_bar_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(sqm_bortle_bar_, 2, 0);

        // Quality label
        sqm_quality_label_ = lv_label_create(dash_left_card_);
        lv_obj_set_style_text_font(sqm_quality_label_, &lv_font_montserrat_10, 0);
        lv_obj_set_style_text_color(sqm_quality_label_, SG_GOOD_COLOR, 0);
        lv_label_set_text(sqm_quality_label_, "");
        lv_obj_set_pos(sqm_quality_label_, 19, 107);

        // Mini spectrum — 8 colored bars (AS7341 wavelengths)
        {
            int spec_y = 122;    // Below quality label
            int spec_h = 28;     // Max bar height
            int bar_w = 12;
            int gap = 1;
            int total_w = 8 * bar_w + 7 * gap;  // 103px
            int start_x = (138 - total_w) / 2;  // Center in card

            for (int i = 0; i < 8; i++) {
                dash_spec_bar_[i] = lv_obj_create(dash_left_card_);
                lv_obj_remove_style_all(dash_spec_bar_[i]);
                lv_obj_set_size(dash_spec_bar_[i], bar_w, 4);  // Start small
                lv_obj_set_pos(dash_spec_bar_[i], start_x + i * (bar_w + gap),
                               spec_y + spec_h - 4);  // Bottom-aligned
                lv_obj_set_style_bg_color(dash_spec_bar_[i], kWavelengthColors[i], 0);
                lv_obj_set_style_bg_opa(dash_spec_bar_[i], LV_OPA_COVER, 0);
                lv_obj_set_style_radius(dash_spec_bar_[i], 1, 0);
            }
        }

        // --- RIGHT CARD: 8 info rows with pixel-art icons ---
        dash_right_card_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(dash_right_card_);
        lv_obj_set_size(dash_right_card_, 156, 158);
        lv_obj_set_pos(dash_right_card_, 144, 16);
        lv_obj_set_style_bg_color(dash_right_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(dash_right_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(dash_right_card_, 10, 0);
        lv_obj_set_style_border_color(dash_right_card_, card_border, 0);
        lv_obj_set_style_border_width(dash_right_card_, 1, 0);
        lv_obj_set_style_border_opa(dash_right_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(dash_right_card_, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_add_flag(dash_right_card_, LV_OBJ_FLAG_HIDDEN);

        static const char* row_labels[] = {
            "Luna", "Temp", "Umidita", "Nuvole",
            "Vento", "Seeing", "Aerei", "Satelliti"
        };
        static const lv_color_t dot_colors[] = {
            lv_color_hex(0xCCCC66),  // Moon — gold
            lv_color_hex(0xFF5544),  // Temp — red-orange
            lv_color_hex(0x44AAFF),  // Humidity — blue
            lv_color_hex(0x8899BB),  // Clouds — steel
            lv_color_hex(0x55DD99),  // Wind — mint
            lv_color_hex(0xFFAA33),  // Seeing — amber
            lv_color_hex(0xFF7744),  // Aircraft — orange
            lv_color_hex(0x33CCFF),  // Satellites — cyan
        };
        int rh = 18;  // Row height
        int ry = 6;   // Start Y inside card

        for (int i = 0; i < DASH_ROWS; i++) {
            // Pixel-art icon canvas (10x10)
            int buf_sz = LV_CANVAS_BUF_SIZE(10, 10, 16, LV_DRAW_BUF_STRIDE_ALIGN);
            dash_dot_buf_[i] = (uint8_t*)heap_caps_calloc(1, buf_sz, MALLOC_CAP_DEFAULT);
            if (dash_dot_buf_[i]) {
                dash_dot_[i] = lv_canvas_create(dash_right_card_);
                lv_canvas_set_buffer(dash_dot_[i], dash_dot_buf_[i], 10, 10, LV_COLOR_FORMAT_RGB565);
                lv_obj_set_pos(dash_dot_[i], 6, ry + i * rh + 2);
                lv_canvas_fill_bg(dash_dot_[i], card_bg, LV_OPA_COVER);
                DrawDashIcon(dash_dot_[i], i, dot_colors[i]);
            }

            // Category label
            dash_lbl_[i] = lv_label_create(dash_right_card_);
            lv_obj_set_style_text_font(dash_lbl_[i], &lv_font_montserrat_10, 0);
            lv_obj_set_style_text_color(dash_lbl_[i], SG_DIM_COLOR, 0);
            lv_label_set_text(dash_lbl_[i], row_labels[i]);
            lv_obj_set_pos(dash_lbl_[i], 20, ry + i * rh + 1);

            // Value label
            dash_val_[i] = lv_label_create(dash_right_card_);
            lv_obj_set_style_text_font(dash_val_[i], &lv_font_montserrat_14, 0);
            lv_obj_set_style_text_color(dash_val_[i], SG_TEXT_COLOR, 0);
            lv_label_set_text(dash_val_[i], "--");
            lv_obj_set_pos(dash_val_[i], 80, ry + i * rh - 1);
        }

        // --- BOTTOM BAR: Location ---
        dash_bottom_bar_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(dash_bottom_bar_);
        lv_obj_set_size(dash_bottom_bar_, 298, 20);
        lv_obj_set_pos(dash_bottom_bar_, 2, 176);
        lv_obj_set_style_bg_color(dash_bottom_bar_, lv_color_hex(0x111122), 0);
        lv_obj_set_style_bg_opa(dash_bottom_bar_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(dash_bottom_bar_, 8, 0);
        lv_obj_set_style_border_color(dash_bottom_bar_, lv_color_hex(0x2A2A44), 0);
        lv_obj_set_style_border_width(dash_bottom_bar_, 1, 0);
        lv_obj_set_style_border_opa(dash_bottom_bar_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(dash_bottom_bar_, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_add_flag(dash_bottom_bar_, LV_OBJ_FLAG_HIDDEN);

        // GPS symbol + location text
        dash_location_ = lv_label_create(dash_bottom_bar_);
        lv_obj_set_style_text_font(dash_location_, &lv_font_montserrat_10, 0);
        lv_obj_set_style_text_color(dash_location_, SG_TEXT_COLOR, 0);
        lv_label_set_text(dash_location_, LV_SYMBOL_GPS " --");
        lv_obj_set_pos(dash_location_, 8, 4);

        // Sensor status icons (right-aligned in bottom bar)
        dash_sensor_status_ = lv_label_create(dash_bottom_bar_);
        lv_obj_set_style_text_font(dash_sensor_status_, &lv_font_montserrat_10, 0);
        lv_obj_set_style_text_color(dash_sensor_status_, SG_DIM_COLOR, 0);
        lv_label_set_text(dash_sensor_status_, "");
        lv_obj_set_pos(dash_sensor_status_, 150, 4);

        dash_built_ = true;
    }

    // =====================================================================
    // Moon canvas (built once, hidden until PAGE_MOON)
    // =====================================================================
    {
        int buf_size = LV_CANVAS_BUF_SIZE(MOON_SIZE, MOON_SIZE, 16, LV_DRAW_BUF_STRIDE_ALIGN);
        moon_canvas_buf_ = (uint8_t*)heap_caps_calloc(1, buf_size, MALLOC_CAP_DEFAULT);
        if (moon_canvas_buf_) {
            moon_canvas_ = lv_canvas_create(data_area_);
            lv_canvas_set_buffer(moon_canvas_, moon_canvas_buf_, MOON_SIZE, MOON_SIZE, LV_COLOR_FORMAT_RGB565);
            lv_obj_set_pos(moon_canvas_, 220, 4);
            lv_obj_add_flag(moon_canvas_, LV_OBJ_FLAG_HIDDEN);
        }
    }

    // =====================================================================
    // Spectral page — card-based layout (built once, hidden until PAGE_SPECTRAL)
    // =====================================================================
    {
        lv_color_t card_bg = lv_color_hex(0x111122);
        lv_color_t card_border = lv_color_hex(0x2A2A44);

        // Wrapper container for hide/show
        spectral_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(spectral_container_);
        lv_obj_set_size(spectral_container_, w - 16, data_area_h - 16);
        lv_obj_set_pos(spectral_container_, 0, 16);
        lv_obj_set_style_bg_opa(spectral_container_, LV_OPA_TRANSP, 0);
        lv_obj_clear_flag(spectral_container_, LV_OBJ_FLAG_SCROLLABLE);

        // ── Left card: spectral bars (190x158) ──
        spectral_left_card_ = lv_obj_create(spectral_container_);
        lv_obj_remove_style_all(spectral_left_card_);
        lv_obj_set_size(spectral_left_card_, 190, 158);
        lv_obj_set_pos(spectral_left_card_, 0, 0);
        lv_obj_set_style_bg_color(spectral_left_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(spectral_left_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(spectral_left_card_, 10, 0);
        lv_obj_set_style_border_color(spectral_left_card_, card_border, 0);
        lv_obj_set_style_border_width(spectral_left_card_, 1, 0);
        lv_obj_set_style_border_opa(spectral_left_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(spectral_left_card_, LV_OBJ_FLAG_SCROLLABLE);

        int bar_w = 18;
        int bar_spacing = 4;
        int total_bar_w = 8 * bar_w + 7 * bar_spacing;  // 172px
        int bar_start_x = (190 - total_bar_w) / 2;
        int bar_max_h = 100;  // Max bar height
        int bar_top_y = 10;   // Top margin inside card

        for (int i = 0; i < 8; i++) {
            int x = bar_start_x + i * (bar_w + bar_spacing);

            // Colored bar (grows upward from bottom)
            spectral_bars_[i] = lv_obj_create(spectral_left_card_);
            lv_obj_remove_style_all(spectral_bars_[i]);
            lv_obj_set_size(spectral_bars_[i], bar_w, 10);
            lv_obj_set_pos(spectral_bars_[i], x, bar_top_y + bar_max_h - 10);
            lv_obj_set_style_bg_color(spectral_bars_[i], kWavelengthColors[i], 0);
            lv_obj_set_style_bg_opa(spectral_bars_[i], LV_OPA_COVER, 0);
            lv_obj_set_style_radius(spectral_bars_[i], 3, 0);

            // Value above bar
            spectral_values_[i] = lv_label_create(spectral_left_card_);
            lv_obj_set_style_text_font(spectral_values_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(spectral_values_[i], SG_VALUE_COLOR, 0);
            lv_obj_set_style_text_align(spectral_values_[i], LV_TEXT_ALIGN_CENTER, 0);
            lv_obj_set_width(spectral_values_[i], bar_w + 6);
            lv_label_set_text(spectral_values_[i], "--");
            lv_obj_set_pos(spectral_values_[i], x - 3, bar_top_y + bar_max_h - 22);

            // Wavelength label below bar
            spectral_labels_[i] = lv_label_create(spectral_left_card_);
            lv_obj_set_style_text_font(spectral_labels_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(spectral_labels_[i], kWavelengthColors[i], 0);
            lv_obj_set_style_text_align(spectral_labels_[i], LV_TEXT_ALIGN_CENTER, 0);
            lv_obj_set_width(spectral_labels_[i], bar_w + 6);
            lv_label_set_text(spectral_labels_[i], kWavelengthNames[i]);
            lv_obj_set_pos(spectral_labels_[i], x - 3, bar_top_y + bar_max_h + 4);
        }

        // Ratios line at bottom of left card
        spectral_ratios_ = lv_label_create(spectral_left_card_);
        lv_obj_set_style_text_font(spectral_ratios_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(spectral_ratios_, SG_DIM_COLOR, 0);
        lv_label_set_text(spectral_ratios_, "Blu:-- Na:--");
        lv_obj_set_pos(spectral_ratios_, 8, 140);

        // ── Right card: LP analysis panel (100x158) ──
        spectral_right_card_ = lv_obj_create(spectral_container_);
        lv_obj_remove_style_all(spectral_right_card_);
        lv_obj_set_size(spectral_right_card_, 104, 158);
        lv_obj_set_pos(spectral_right_card_, 194, 0);
        lv_obj_set_style_bg_color(spectral_right_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(spectral_right_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(spectral_right_card_, 10, 0);
        lv_obj_set_style_border_color(spectral_right_card_, card_border, 0);
        lv_obj_set_style_border_width(spectral_right_card_, 1, 0);
        lv_obj_set_style_border_opa(spectral_right_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(spectral_right_card_, LV_OBJ_FLAG_SCROLLABLE);

        // SQI arc gauge (60px diameter)
        spectral_sqi_arc_ = lv_arc_create(spectral_right_card_);
        lv_obj_set_size(spectral_sqi_arc_, 64, 64);
        lv_obj_set_pos(spectral_sqi_arc_, 20, 6);
        lv_arc_set_rotation(spectral_sqi_arc_, 135);
        lv_arc_set_bg_angles(spectral_sqi_arc_, 0, 270);
        lv_arc_set_range(spectral_sqi_arc_, 0, 100);
        lv_arc_set_value(spectral_sqi_arc_, 0);
        lv_obj_set_style_arc_width(spectral_sqi_arc_, 6, LV_PART_MAIN);
        lv_obj_set_style_arc_color(spectral_sqi_arc_, lv_color_hex(0x222244), LV_PART_MAIN);
        lv_obj_set_style_arc_width(spectral_sqi_arc_, 6, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(spectral_sqi_arc_, SG_GOOD_COLOR, LV_PART_INDICATOR);
        lv_obj_set_style_arc_rounded(spectral_sqi_arc_, true, LV_PART_INDICATOR);
        lv_obj_remove_style(spectral_sqi_arc_, nullptr, LV_PART_KNOB);

        // SQI value in arc center
        spectral_sqi_value_ = lv_label_create(spectral_right_card_);
        lv_obj_set_style_text_font(spectral_sqi_value_, GetMediumFont(), 0);
        lv_obj_set_style_text_color(spectral_sqi_value_, SG_VALUE_COLOR, 0);
        lv_obj_set_style_text_align(spectral_sqi_value_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(spectral_sqi_value_, 64);
        lv_label_set_text(spectral_sqi_value_, "--");
        lv_obj_set_pos(spectral_sqi_value_, 20, 24);

        // "Sky Quality" label under arc
        spectral_sqi_label_ = lv_label_create(spectral_right_card_);
        lv_obj_set_style_text_font(spectral_sqi_label_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(spectral_sqi_label_, SG_DIM_COLOR, 0);
        lv_obj_set_style_text_align(spectral_sqi_label_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(spectral_sqi_label_, 104);
        lv_label_set_text(spectral_sqi_label_, "Qualita Cielo");
        lv_obj_set_pos(spectral_sqi_label_, 0, 72);

        // LP source type
        spectral_lp_source_ = lv_label_create(spectral_right_card_);
        lv_obj_set_style_text_font(spectral_lp_source_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(spectral_lp_source_, SG_TEXT_COLOR, 0);
        lv_label_set_text(spectral_lp_source_, "Sorgente: --");
        lv_obj_set_pos(spectral_lp_source_, 6, 88);

        // SQI text (hidden — kept for compat, we use arc now)
        spectral_sqi_ = lv_label_create(spectral_right_card_);
        lv_obj_set_style_text_font(spectral_sqi_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(spectral_sqi_, SG_TEXT_COLOR, 0);
        lv_label_set_text(spectral_sqi_, "");
        lv_obj_add_flag(spectral_sqi_, LV_OBJ_FLAG_HIDDEN);

        // Verdict label ("Buono", "Inquinato", etc.)
        spectral_lp_verdict_ = lv_label_create(spectral_right_card_);
        lv_obj_set_style_text_font(spectral_lp_verdict_, GetSmallFont(), 0);
        lv_obj_set_style_text_color(spectral_lp_verdict_, SG_GOOD_COLOR, 0);
        lv_obj_set_style_text_align(spectral_lp_verdict_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(spectral_lp_verdict_, 104);
        lv_label_set_text(spectral_lp_verdict_, "--");
        lv_obj_set_pos(spectral_lp_verdict_, 0, 106);

        // Thin separator line
        lv_obj_t* sep = lv_obj_create(spectral_right_card_);
        lv_obj_remove_style_all(sep);
        lv_obj_set_size(sep, 80, 1);
        lv_obj_set_pos(sep, 12, 126);
        lv_obj_set_style_bg_color(sep, card_border, 0);
        lv_obj_set_style_bg_opa(sep, LV_OPA_COVER, 0);

        // LP type detail below separator
        lv_obj_t* lp_icon = lv_label_create(spectral_right_card_);
        lv_obj_set_style_text_font(lp_icon, GetTinyFont(), 0);
        lv_obj_set_style_text_color(lp_icon, SG_DIM_COLOR, 0);
        lv_label_set_text(lp_icon, LV_SYMBOL_EYE_OPEN " Inquin.");
        lv_obj_set_pos(lp_icon, 6, 132);

        // Source detail line
        lv_obj_t* src_detail = lv_label_create(spectral_right_card_);
        lv_obj_set_style_text_font(src_detail, GetTinyFont(), 0);
        lv_obj_set_style_text_color(src_detail, SG_DIM_COLOR, 0);
        lv_label_set_text(src_detail, "8 canali AS7341");
        lv_obj_set_pos(src_detail, 6, 144);
    }

    spectral_built_ = true;
    HideSpectralBars();

    // =====================================================================
    // Environment page — dual arc gauges + details card
    // =====================================================================
    {
        lv_color_t card_bg = lv_color_hex(0x111122);
        lv_color_t card_border = lv_color_hex(0x2A2A44);

        env_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(env_container_);
        lv_obj_set_size(env_container_, w - 16, data_area_h - 16);
        lv_obj_set_pos(env_container_, 0, 16);
        lv_obj_set_style_bg_opa(env_container_, LV_OPA_TRANSP, 0);
        lv_obj_clear_flag(env_container_, LV_OBJ_FLAG_SCROLLABLE);

        // Left card: Temperature + Humidity arcs (148x158)
        env_left_card_ = lv_obj_create(env_container_);
        lv_obj_remove_style_all(env_left_card_);
        lv_obj_set_size(env_left_card_, 148, 158);
        lv_obj_set_pos(env_left_card_, 0, 0);
        lv_obj_set_style_bg_color(env_left_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(env_left_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(env_left_card_, 10, 0);
        lv_obj_set_style_border_color(env_left_card_, card_border, 0);
        lv_obj_set_style_border_width(env_left_card_, 1, 0);
        lv_obj_set_style_border_opa(env_left_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(env_left_card_, LV_OBJ_FLAG_SCROLLABLE);

        // Temperature arc (left side)
        env_temp_arc_ = lv_arc_create(env_left_card_);
        lv_obj_set_size(env_temp_arc_, 64, 64);
        lv_obj_set_pos(env_temp_arc_, 6, 6);
        lv_arc_set_rotation(env_temp_arc_, 135);
        lv_arc_set_bg_angles(env_temp_arc_, 0, 270);
        lv_arc_set_range(env_temp_arc_, -10, 50);
        lv_arc_set_value(env_temp_arc_, 20);
        lv_obj_set_style_arc_width(env_temp_arc_, 6, LV_PART_MAIN);
        lv_obj_set_style_arc_color(env_temp_arc_, lv_color_hex(0x222244), LV_PART_MAIN);
        lv_obj_set_style_arc_width(env_temp_arc_, 6, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(env_temp_arc_, lv_color_hex(0xFF5544), LV_PART_INDICATOR);
        lv_obj_set_style_arc_rounded(env_temp_arc_, true, LV_PART_INDICATOR);
        lv_obj_remove_style(env_temp_arc_, nullptr, LV_PART_KNOB);

        env_temp_value_ = lv_label_create(env_left_card_);
        lv_obj_set_style_text_font(env_temp_value_, GetMediumFont(), 0);
        lv_obj_set_style_text_color(env_temp_value_, SG_VALUE_COLOR, 0);
        lv_obj_set_style_text_align(env_temp_value_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(env_temp_value_, 64);
        lv_label_set_text(env_temp_value_, "--");
        lv_obj_set_pos(env_temp_value_, 6, 26);

        env_temp_label_ = lv_label_create(env_left_card_);
        lv_obj_set_style_text_font(env_temp_label_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(env_temp_label_, SG_DIM_COLOR, 0);
        lv_obj_set_style_text_align(env_temp_label_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(env_temp_label_, 70);
        lv_label_set_text(env_temp_label_, "Temperatura");
        lv_obj_set_pos(env_temp_label_, 3, 72);

        // Humidity arc (right side)
        env_hum_arc_ = lv_arc_create(env_left_card_);
        lv_obj_set_size(env_hum_arc_, 64, 64);
        lv_obj_set_pos(env_hum_arc_, 78, 6);
        lv_arc_set_rotation(env_hum_arc_, 135);
        lv_arc_set_bg_angles(env_hum_arc_, 0, 270);
        lv_arc_set_range(env_hum_arc_, 0, 100);
        lv_arc_set_value(env_hum_arc_, 50);
        lv_obj_set_style_arc_width(env_hum_arc_, 6, LV_PART_MAIN);
        lv_obj_set_style_arc_color(env_hum_arc_, lv_color_hex(0x222244), LV_PART_MAIN);
        lv_obj_set_style_arc_width(env_hum_arc_, 6, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(env_hum_arc_, lv_color_hex(0x00BBFF), LV_PART_INDICATOR);
        lv_obj_set_style_arc_rounded(env_hum_arc_, true, LV_PART_INDICATOR);
        lv_obj_remove_style(env_hum_arc_, nullptr, LV_PART_KNOB);

        env_hum_value_ = lv_label_create(env_left_card_);
        lv_obj_set_style_text_font(env_hum_value_, GetMediumFont(), 0);
        lv_obj_set_style_text_color(env_hum_value_, SG_VALUE_COLOR, 0);
        lv_obj_set_style_text_align(env_hum_value_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(env_hum_value_, 64);
        lv_label_set_text(env_hum_value_, "--");
        lv_obj_set_pos(env_hum_value_, 78, 26);

        env_hum_label_ = lv_label_create(env_left_card_);
        lv_obj_set_style_text_font(env_hum_label_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(env_hum_label_, SG_DIM_COLOR, 0);
        lv_obj_set_style_text_align(env_hum_label_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(env_hum_label_, 70);
        lv_label_set_text(env_hum_label_, "Umidita");
        lv_obj_set_pos(env_hum_label_, 75, 72);

        // Sensor label at bottom of left card
        env_sensor_lbl_ = lv_label_create(env_left_card_);
        lv_obj_set_style_text_font(env_sensor_lbl_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(env_sensor_lbl_, SG_DIM_COLOR, 0);
        lv_obj_set_style_text_align(env_sensor_lbl_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(env_sensor_lbl_, 148);
        lv_label_set_text(env_sensor_lbl_, "AHT20");
        lv_obj_set_pos(env_sensor_lbl_, 0, 142);

        // Right card: Dew point details (146x158)
        env_right_card_ = lv_obj_create(env_container_);
        lv_obj_remove_style_all(env_right_card_);
        lv_obj_set_size(env_right_card_, 146, 158);
        lv_obj_set_pos(env_right_card_, 152, 0);
        lv_obj_set_style_bg_color(env_right_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(env_right_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(env_right_card_, 10, 0);
        lv_obj_set_style_border_color(env_right_card_, card_border, 0);
        lv_obj_set_style_border_width(env_right_card_, 1, 0);
        lv_obj_set_style_border_opa(env_right_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(env_right_card_, LV_OBJ_FLAG_SCROLLABLE);

        // Dew point
        lv_obj_t* dew_icon = lv_label_create(env_right_card_);
        lv_obj_set_style_text_font(dew_icon, GetTinyFont(), 0);
        lv_obj_set_style_text_color(dew_icon, SG_DIM_COLOR, 0);
        lv_label_set_text(dew_icon, "Punto Rugiada");
        lv_obj_set_pos(dew_icon, 8, 10);

        env_dew_val_ = lv_label_create(env_right_card_);
        lv_obj_set_style_text_font(env_dew_val_, GetSmallFont(), 0);
        lv_obj_set_style_text_color(env_dew_val_, SG_VALUE_COLOR, 0);
        lv_label_set_text(env_dew_val_, "--");
        lv_obj_set_pos(env_dew_val_, 8, 24);

        // Separator
        lv_obj_t* sep1 = lv_obj_create(env_right_card_);
        lv_obj_remove_style_all(sep1);
        lv_obj_set_size(sep1, 120, 1);
        lv_obj_set_pos(sep1, 8, 48);
        lv_obj_set_style_bg_color(sep1, card_border, 0);
        lv_obj_set_style_bg_opa(sep1, LV_OPA_COVER, 0);

        // Spread
        lv_obj_t* spread_icon = lv_label_create(env_right_card_);
        lv_obj_set_style_text_font(spread_icon, GetTinyFont(), 0);
        lv_obj_set_style_text_color(spread_icon, SG_DIM_COLOR, 0);
        lv_label_set_text(spread_icon, "Spread (T - Dew)");
        lv_obj_set_pos(spread_icon, 8, 56);

        env_spread_val_ = lv_label_create(env_right_card_);
        lv_obj_set_style_text_font(env_spread_val_, GetMediumFont(), 0);
        lv_obj_set_style_text_color(env_spread_val_, SG_GOOD_COLOR, 0);
        lv_label_set_text(env_spread_val_, "--");
        lv_obj_set_pos(env_spread_val_, 8, 70);

        // Separator
        lv_obj_t* sep2 = lv_obj_create(env_right_card_);
        lv_obj_remove_style_all(sep2);
        lv_obj_set_size(sep2, 120, 1);
        lv_obj_set_pos(sep2, 8, 98);
        lv_obj_set_style_bg_color(sep2, card_border, 0);
        lv_obj_set_style_bg_opa(sep2, LV_OPA_COVER, 0);

        // Condensation risk
        lv_obj_t* cond_icon = lv_label_create(env_right_card_);
        lv_obj_set_style_text_font(cond_icon, GetTinyFont(), 0);
        lv_obj_set_style_text_color(cond_icon, SG_DIM_COLOR, 0);
        lv_label_set_text(cond_icon, "Condensa");
        lv_obj_set_pos(cond_icon, 8, 106);

        env_cond_val_ = lv_label_create(env_right_card_);
        lv_obj_set_style_text_font(env_cond_val_, GetSmallFont(), 0);
        lv_obj_set_style_text_color(env_cond_val_, SG_GOOD_COLOR, 0);
        lv_label_set_text(env_cond_val_, "--");
        lv_obj_set_pos(env_cond_val_, 8, 120);

        env_built_ = true;
        lv_obj_add_flag(env_container_, LV_OBJ_FLAG_HIDDEN);
    }

    // =====================================================================
    // Moon page — card layout with moon canvas + night timing
    // =====================================================================
    {
        lv_color_t card_bg = lv_color_hex(0x111122);
        lv_color_t card_border = lv_color_hex(0x2A2A44);

        moon_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(moon_container_);
        lv_obj_set_size(moon_container_, w - 16, data_area_h - 16);
        lv_obj_set_pos(moon_container_, 0, 16);
        lv_obj_set_style_bg_opa(moon_container_, LV_OPA_TRANSP, 0);
        lv_obj_clear_flag(moon_container_, LV_OBJ_FLAG_SCROLLABLE);

        // Left card: Moon phase vis + basic info (120x158)
        moon_left_card_ = lv_obj_create(moon_container_);
        lv_obj_remove_style_all(moon_left_card_);
        lv_obj_set_size(moon_left_card_, 120, 158);
        lv_obj_set_pos(moon_left_card_, 0, 0);
        lv_obj_set_style_bg_color(moon_left_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(moon_left_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(moon_left_card_, 10, 0);
        lv_obj_set_style_border_color(moon_left_card_, card_border, 0);
        lv_obj_set_style_border_width(moon_left_card_, 1, 0);
        lv_obj_set_style_border_opa(moon_left_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(moon_left_card_, LV_OBJ_FLAG_SCROLLABLE);

        // Moon phase name (below canvas at y~50)
        moon_phase_lbl_ = lv_label_create(moon_left_card_);
        lv_obj_set_style_text_font(moon_phase_lbl_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(moon_phase_lbl_, SG_TEXT_COLOR, 0);
        lv_obj_set_style_text_align(moon_phase_lbl_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(moon_phase_lbl_, 110);
        lv_label_set_text(moon_phase_lbl_, "--");
        lv_obj_set_pos(moon_phase_lbl_, 5, 50);

        // Moon illumination (large %)
        moon_illum_lbl_ = lv_label_create(moon_left_card_);
        lv_obj_set_style_text_font(moon_illum_lbl_, GetMediumFont(), 0);
        lv_obj_set_style_text_color(moon_illum_lbl_, SG_VALUE_COLOR, 0);
        lv_obj_set_style_text_align(moon_illum_lbl_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(moon_illum_lbl_, 120);
        lv_label_set_text(moon_illum_lbl_, "--");
        lv_obj_set_pos(moon_illum_lbl_, 0, 64);

        // Night duration arc — outer ring (dark hours 0-12h)
        moon_night_arc_ = lv_arc_create(moon_left_card_);
        lv_obj_set_size(moon_night_arc_, 56, 56);
        lv_obj_set_pos(moon_night_arc_, 4, 90);
        lv_arc_set_rotation(moon_night_arc_, 135);
        lv_arc_set_bg_angles(moon_night_arc_, 0, 270);
        lv_arc_set_range(moon_night_arc_, 0, 120);  // 0-12h in tenths
        lv_arc_set_value(moon_night_arc_, 0);
        lv_obj_set_style_arc_width(moon_night_arc_, 5, LV_PART_MAIN);
        lv_obj_set_style_arc_color(moon_night_arc_, lv_color_hex(0x222244), LV_PART_MAIN);
        lv_obj_set_style_arc_width(moon_night_arc_, 5, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(moon_night_arc_, lv_color_hex(0x3355AA), LV_PART_INDICATOR);
        lv_obj_set_style_arc_rounded(moon_night_arc_, true, LV_PART_INDICATOR);
        lv_obj_remove_style(moon_night_arc_, nullptr, LV_PART_KNOB);

        moon_night_val_ = lv_label_create(moon_left_card_);
        lv_obj_set_style_text_font(moon_night_val_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(moon_night_val_, lv_color_hex(0x3355AA), 0);
        lv_obj_set_style_text_align(moon_night_val_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(moon_night_val_, 56);
        lv_label_set_text(moon_night_val_, "Notte\n--");
        lv_obj_set_pos(moon_night_val_, 4, 104);

        // Moonless arc — second gauge (moonless dark hours)
        moon_moonless_arc_ = lv_arc_create(moon_left_card_);
        lv_obj_set_size(moon_moonless_arc_, 56, 56);
        lv_obj_set_pos(moon_moonless_arc_, 60, 90);
        lv_arc_set_rotation(moon_moonless_arc_, 135);
        lv_arc_set_bg_angles(moon_moonless_arc_, 0, 270);
        lv_arc_set_range(moon_moonless_arc_, 0, 120);
        lv_arc_set_value(moon_moonless_arc_, 0);
        lv_obj_set_style_arc_width(moon_moonless_arc_, 5, LV_PART_MAIN);
        lv_obj_set_style_arc_color(moon_moonless_arc_, lv_color_hex(0x222244), LV_PART_MAIN);
        lv_obj_set_style_arc_width(moon_moonless_arc_, 5, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(moon_moonless_arc_, SG_GOOD_COLOR, LV_PART_INDICATOR);
        lv_obj_set_style_arc_rounded(moon_moonless_arc_, true, LV_PART_INDICATOR);
        lv_obj_remove_style(moon_moonless_arc_, nullptr, LV_PART_KNOB);

        moon_moonless_val_ = lv_label_create(moon_left_card_);
        lv_obj_set_style_text_font(moon_moonless_val_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(moon_moonless_val_, SG_GOOD_COLOR, 0);
        lv_obj_set_style_text_align(moon_moonless_val_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(moon_moonless_val_, 56);
        lv_label_set_text(moon_moonless_val_, "No Luna\n--");
        lv_obj_set_pos(moon_moonless_val_, 60, 104);

        // Right card: Night timing details (172x158)
        moon_right_card_ = lv_obj_create(moon_container_);
        lv_obj_remove_style_all(moon_right_card_);
        lv_obj_set_size(moon_right_card_, 172, 158);
        lv_obj_set_pos(moon_right_card_, 124, 0);
        lv_obj_set_style_bg_color(moon_right_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(moon_right_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(moon_right_card_, 10, 0);
        lv_obj_set_style_border_color(moon_right_card_, card_border, 0);
        lv_obj_set_style_border_width(moon_right_card_, 1, 0);
        lv_obj_set_style_border_opa(moon_right_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(moon_right_card_, LV_OBJ_FLAG_SCROLLABLE);

        // 6 info lines in right card
        for (int i = 0; i < 6; i++) {
            moon_info_[i] = lv_label_create(moon_right_card_);
            lv_obj_set_style_text_font(moon_info_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(moon_info_[i], SG_TEXT_COLOR, 0);
            lv_obj_set_width(moon_info_[i], 160);
            lv_label_set_long_mode(moon_info_[i], LV_LABEL_LONG_CLIP);
            lv_label_set_text(moon_info_[i], "");
            lv_obj_set_pos(moon_info_[i], 6, 8 + i * 24);
        }

        moon_cards_built_ = true;
        lv_obj_add_flag(moon_container_, LV_OBJ_FLAG_HIDDEN);
    }

    // =====================================================================
    // GPS page — card layout with coordinates + map
    // =====================================================================
    {
        lv_color_t card_bg = lv_color_hex(0x111122);
        lv_color_t card_border = lv_color_hex(0x2A2A44);

        gps_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(gps_container_);
        lv_obj_set_size(gps_container_, w - 16, data_area_h - 16);
        lv_obj_set_pos(gps_container_, 0, 16);
        lv_obj_set_style_bg_opa(gps_container_, LV_OPA_TRANSP, 0);
        lv_obj_clear_flag(gps_container_, LV_OBJ_FLAG_SCROLLABLE);

        // Left card: GPS data (155x158)
        gps_left_card_ = lv_obj_create(gps_container_);
        lv_obj_remove_style_all(gps_left_card_);
        lv_obj_set_size(gps_left_card_, 152, 158);
        lv_obj_set_pos(gps_left_card_, 0, 0);
        lv_obj_set_style_bg_color(gps_left_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(gps_left_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(gps_left_card_, 10, 0);
        lv_obj_set_style_border_color(gps_left_card_, card_border, 0);
        lv_obj_set_style_border_width(gps_left_card_, 1, 0);
        lv_obj_set_style_border_opa(gps_left_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(gps_left_card_, LV_OBJ_FLAG_SCROLLABLE);

        for (int i = 0; i < 7; i++) {
            gps_info_[i] = lv_label_create(gps_left_card_);
            lv_obj_set_style_text_font(gps_info_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(gps_info_[i], SG_TEXT_COLOR, 0);
            lv_obj_set_width(gps_info_[i], 140);
            lv_label_set_long_mode(gps_info_[i], LV_LABEL_LONG_CLIP);
            lv_label_set_text(gps_info_[i], "");
            lv_obj_set_pos(gps_info_[i], 6, 6 + i * 21);
        }

        // Right card: Map placeholder (140x158)
        gps_right_card_ = lv_obj_create(gps_container_);
        lv_obj_remove_style_all(gps_right_card_);
        lv_obj_set_size(gps_right_card_, 142, 158);
        lv_obj_set_pos(gps_right_card_, 156, 0);
        lv_obj_set_style_bg_color(gps_right_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(gps_right_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(gps_right_card_, 10, 0);
        lv_obj_set_style_border_color(gps_right_card_, card_border, 0);
        lv_obj_set_style_border_width(gps_right_card_, 1, 0);
        lv_obj_set_style_border_opa(gps_right_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(gps_right_card_, LV_OBJ_FLAG_SCROLLABLE);

        gps_cards_built_ = true;
        lv_obj_add_flag(gps_container_, LV_OBJ_FLAG_HIDDEN);
    }

    // =====================================================================
    // Telescope page — card layout with mount status
    // =====================================================================
    {
        lv_color_t card_bg = lv_color_hex(0x111122);
        lv_color_t card_border = lv_color_hex(0x2A2A44);

        scope_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(scope_container_);
        lv_obj_set_size(scope_container_, w - 16, data_area_h - 16);
        lv_obj_set_pos(scope_container_, 0, 16);
        lv_obj_set_style_bg_opa(scope_container_, LV_OPA_TRANSP, 0);
        lv_obj_clear_flag(scope_container_, LV_OBJ_FLAG_SCROLLABLE);

        // Left card: Status + main state (130x158)
        scope_left_card_ = lv_obj_create(scope_container_);
        lv_obj_remove_style_all(scope_left_card_);
        lv_obj_set_size(scope_left_card_, 130, 158);
        lv_obj_set_pos(scope_left_card_, 0, 0);
        lv_obj_set_style_bg_color(scope_left_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(scope_left_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(scope_left_card_, 10, 0);
        lv_obj_set_style_border_color(scope_left_card_, card_border, 0);
        lv_obj_set_style_border_width(scope_left_card_, 1, 0);
        lv_obj_set_style_border_opa(scope_left_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(scope_left_card_, LV_OBJ_FLAG_SCROLLABLE);

        // Big status label
        scope_status_lbl_ = lv_label_create(scope_left_card_);
        lv_obj_set_style_text_font(scope_status_lbl_, GetMediumFont(), 0);
        lv_obj_set_style_text_color(scope_status_lbl_, SG_GOOD_COLOR, 0);
        lv_obj_set_style_text_align(scope_status_lbl_, LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(scope_status_lbl_, 120);
        lv_label_set_text(scope_status_lbl_, "--");
        lv_obj_set_pos(scope_status_lbl_, 5, 20);

        // Additional info lines in left card
        for (int i = 0; i < 3; i++) {
            scope_info_[i] = lv_label_create(scope_left_card_);
            lv_obj_set_style_text_font(scope_info_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(scope_info_[i], SG_TEXT_COLOR, 0);
            lv_obj_set_width(scope_info_[i], 118);
            lv_label_set_long_mode(scope_info_[i], LV_LABEL_LONG_CLIP);
            lv_label_set_text(scope_info_[i], "");
            lv_obj_set_pos(scope_info_[i], 6, 50 + i * 22);
        }

        // Right card: Coordinates (162x158)
        scope_right_card_ = lv_obj_create(scope_container_);
        lv_obj_remove_style_all(scope_right_card_);
        lv_obj_set_size(scope_right_card_, 162, 158);
        lv_obj_set_pos(scope_right_card_, 134, 0);
        lv_obj_set_style_bg_color(scope_right_card_, card_bg, 0);
        lv_obj_set_style_bg_opa(scope_right_card_, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(scope_right_card_, 10, 0);
        lv_obj_set_style_border_color(scope_right_card_, card_border, 0);
        lv_obj_set_style_border_width(scope_right_card_, 1, 0);
        lv_obj_set_style_border_opa(scope_right_card_, LV_OPA_COVER, 0);
        lv_obj_clear_flag(scope_right_card_, LV_OBJ_FLAG_SCROLLABLE);

        for (int i = 3; i < 6; i++) {
            scope_info_[i] = lv_label_create(scope_right_card_);
            lv_obj_set_style_text_font(scope_info_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(scope_info_[i], SG_TEXT_COLOR, 0);
            lv_obj_set_width(scope_info_[i], 150);
            lv_label_set_long_mode(scope_info_[i], LV_LABEL_LONG_CLIP);
            lv_label_set_text(scope_info_[i], "");
            lv_obj_set_pos(scope_info_[i], 6, 8 + (i - 3) * 48);
        }

        scope_cards_built_ = true;
        lv_obj_add_flag(scope_container_, LV_OBJ_FLAG_HIDDEN);
    }

    // =====================================================================
    // Weather bars (built once, hidden until PAGE_WEATHER)
    // =====================================================================
    weather_container_ = lv_obj_create(data_area_);
    lv_obj_remove_style_all(weather_container_);
    lv_obj_set_size(weather_container_, w - 16, data_area_h - 16);
    lv_obj_set_pos(weather_container_, 0, 14);
    lv_obj_set_style_bg_color(weather_container_, lv_color_hex(0x111122), 0);
    lv_obj_set_style_bg_opa(weather_container_, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(weather_container_, 10, 0);
    lv_obj_set_style_border_width(weather_container_, 1, 0);
    lv_obj_set_style_border_color(weather_container_, lv_color_hex(0x2A2A44), 0);
    lv_obj_set_style_pad_all(weather_container_, 6, 0);
    lv_obj_clear_flag(weather_container_, LV_OBJ_FLAG_SCROLLABLE);

    // Location label at top
    weather_location_ = lv_label_create(weather_container_);
    lv_obj_set_style_text_font(weather_location_, GetTinyFont(), 0);
    lv_obj_set_style_text_color(weather_location_, SG_DIM_COLOR, 0);
    lv_obj_set_width(weather_location_, 200);
    lv_label_set_text(weather_location_, "");
    lv_obj_set_pos(weather_location_, 0, 0);

    int content_w = w - 16 - 12;
    // 5 columns for both hourly and daily
    int col_w = 56;
    int col_spacing = 2;
    int total_5col_w = 5 * col_w + 4 * col_spacing;
    int col_start_x = (content_w - total_5col_w) / 2;
    if (col_start_x < 0) col_start_x = 0;

    // ========== HOURLY SECTION (5 columns) ==========
    // y=0:   time
    // y=10:  icon (32x32)
    // y=44:  temperature (large)
    // y=58:  rain info
    // y=68:  wind

    int icon_buf_size = LV_CANVAS_BUF_SIZE(WICON_MINI, WICON_MINI, 16, LV_DRAW_BUF_STRIDE_ALIGN);

    for (int i = 0; i < 5; i++) {
        int cx = col_start_x + i * (col_w + col_spacing);

        weather_time_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_time_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_time_[i], SG_TITLE_COLOR, 0);
        lv_obj_set_style_text_align(weather_time_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_time_[i], col_w);
        lv_label_set_text(weather_time_[i], "--:--");
        lv_obj_set_pos(weather_time_[i], cx, 0);

        weather_icon_bufs_[i] = (uint8_t*)heap_caps_calloc(1, icon_buf_size, MALLOC_CAP_DEFAULT);
        if (weather_icon_bufs_[i]) {
            weather_icon_canvas_[i] = lv_canvas_create(weather_container_);
            lv_canvas_set_buffer(weather_icon_canvas_[i], weather_icon_bufs_[i],
                                 WICON_MINI, WICON_MINI, LV_COLOR_FORMAT_RGB565);
            lv_obj_set_pos(weather_icon_canvas_[i], cx + (col_w - WICON_MINI) / 2, 10);
            // Make icon clickable for details popup
            lv_obj_add_flag(weather_icon_canvas_[i], LV_OBJ_FLAG_CLICKABLE);
            lv_obj_add_event_cb(weather_icon_canvas_[i], [](lv_event_t* e) {
                auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
                lv_obj_t* target = (lv_obj_t*)lv_event_get_target(e);
                for (int j = 0; j < 5; j++) {
                    if (self->weather_icon_canvas_[j] == target) {
                        self->ShowWeatherPopup(j, false);
                        return;
                    }
                }
            }, LV_EVENT_CLICKED, this);
        }

        weather_temp_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_temp_[i], GetSmallFont(), 0);
        lv_obj_set_style_text_color(weather_temp_[i], SG_VALUE_COLOR, 0);
        lv_obj_set_style_text_align(weather_temp_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_temp_[i], col_w);
        lv_label_set_text(weather_temp_[i], "--");
        lv_obj_set_pos(weather_temp_[i], cx, 44);

        // Cloud bar (thicker: 4px)
        weather_cloud_bar_[i] = lv_obj_create(weather_container_);
        lv_obj_remove_style_all(weather_cloud_bar_[i]);
        lv_obj_set_size(weather_cloud_bar_[i], col_w - 6, 4);
        lv_obj_set_pos(weather_cloud_bar_[i], cx + 3, 58);
        lv_obj_set_style_bg_color(weather_cloud_bar_[i], SG_GOOD_COLOR, 0);
        lv_obj_set_style_bg_opa(weather_cloud_bar_[i], LV_OPA_COVER, 0);
        lv_obj_set_style_radius(weather_cloud_bar_[i], 2, 0);

        weather_cloud_val_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_cloud_val_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_cloud_val_[i], SG_DIM_COLOR, 0);
        lv_obj_set_style_text_align(weather_cloud_val_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_cloud_val_[i], col_w);
        lv_label_set_text(weather_cloud_val_[i], "");
        lv_obj_set_pos(weather_cloud_val_[i], cx, 62);
        lv_obj_add_flag(weather_cloud_val_[i], LV_OBJ_FLAG_HIDDEN);  // Hidden, shown in popup

        // Rain: probability + mm
        weather_rain_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_rain_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_rain_[i], lv_color_hex(0x55AAFF), 0);
        lv_obj_set_style_text_align(weather_rain_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_rain_[i], col_w);
        lv_label_set_text(weather_rain_[i], "");
        lv_obj_set_pos(weather_rain_[i], cx, 63);

        weather_wind_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_wind_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_wind_[i], SG_DIM_COLOR, 0);
        lv_obj_set_style_text_align(weather_wind_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_wind_[i], col_w);
        lv_label_set_text(weather_wind_[i], "");
        lv_obj_set_pos(weather_wind_[i], cx, 73);

        // Hidden data slots (used by popup)
        weather_hum_[i] = lv_label_create(weather_container_);
        lv_label_set_text(weather_hum_[i], "");
        lv_obj_add_flag(weather_hum_[i], LV_OBJ_FLAG_HIDDEN);

        weather_seeing_[i] = lv_label_create(weather_container_);
        lv_label_set_text(weather_seeing_[i], "");
        lv_obj_add_flag(weather_seeing_[i], LV_OBJ_FLAG_HIDDEN);

        weather_desc_[i] = lv_label_create(weather_container_);
        lv_label_set_text(weather_desc_[i], "");
        lv_obj_add_flag(weather_desc_[i], LV_OBJ_FLAG_HIDDEN);
    }
    // 6th column slots (unused — set null-safe)
    weather_time_[5] = nullptr;
    weather_icon_canvas_[5] = nullptr;
    weather_temp_[5] = nullptr;
    weather_cloud_bar_[5] = nullptr;
    weather_cloud_val_[5] = nullptr;
    weather_rain_[5] = nullptr;
    weather_wind_[5] = nullptr;
    weather_hum_[5] = nullptr;
    weather_seeing_[5] = nullptr;
    weather_desc_[5] = nullptr;
    weather_icon_bufs_[5] = nullptr;

    // ========== SEPARATOR LINE ==========
    weather_daily_sep_ = lv_obj_create(weather_container_);
    lv_obj_remove_style_all(weather_daily_sep_);
    lv_obj_set_size(weather_daily_sep_, content_w - 8, 1);
    lv_obj_set_pos(weather_daily_sep_, 4, 84);
    lv_obj_set_style_bg_color(weather_daily_sep_, lv_color_hex(0x2A2A44), 0);
    lv_obj_set_style_bg_opa(weather_daily_sep_, LV_OPA_COVER, 0);

    // ========== DAILY SECTION (5 columns) ==========
    // y=86:  day name
    // y=96:  icon (32x32)
    // y=130: min/max temp
    // y=144: rain

    int mini_buf_size = LV_CANVAS_BUF_SIZE(WICON_MINI, WICON_MINI, 16, LV_DRAW_BUF_STRIDE_ALIGN);

    for (int i = 0; i < 5; i++) {
        int cx = col_start_x + i * (col_w + col_spacing);

        weather_daily_day_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_daily_day_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_daily_day_[i], SG_TITLE_COLOR, 0);
        lv_obj_set_style_text_align(weather_daily_day_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_daily_day_[i], col_w);
        lv_label_set_text(weather_daily_day_[i], "--");
        lv_obj_set_pos(weather_daily_day_[i], cx, 86);

        weather_daily_icon_bufs_[i] = (uint8_t*)heap_caps_calloc(1, mini_buf_size, MALLOC_CAP_DEFAULT);
        if (weather_daily_icon_bufs_[i]) {
            weather_daily_icon_[i] = lv_canvas_create(weather_container_);
            lv_canvas_set_buffer(weather_daily_icon_[i], weather_daily_icon_bufs_[i],
                                 WICON_MINI, WICON_MINI, LV_COLOR_FORMAT_RGB565);
            lv_obj_set_pos(weather_daily_icon_[i], cx + (col_w - WICON_MINI) / 2, 96);
            // Clickable for details popup
            lv_obj_add_flag(weather_daily_icon_[i], LV_OBJ_FLAG_CLICKABLE);
            lv_obj_add_event_cb(weather_daily_icon_[i], [](lv_event_t* e) {
                auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
                lv_obj_t* target = (lv_obj_t*)lv_event_get_target(e);
                for (int j = 0; j < 5; j++) {
                    if (self->weather_daily_icon_[j] == target) {
                        self->ShowWeatherPopup(j, true);
                        return;
                    }
                }
            }, LV_EVENT_CLICKED, this);
        }

        weather_daily_temp_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_daily_temp_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_daily_temp_[i], SG_VALUE_COLOR, 0);
        lv_obj_set_style_text_align(weather_daily_temp_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_daily_temp_[i], col_w);
        lv_label_set_text(weather_daily_temp_[i], "--");
        lv_obj_set_pos(weather_daily_temp_[i], cx, 130);

        weather_daily_cloud_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_daily_cloud_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_daily_cloud_[i], SG_DIM_COLOR, 0);
        lv_obj_set_style_text_align(weather_daily_cloud_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_daily_cloud_[i], col_w);
        lv_label_set_text(weather_daily_cloud_[i], "");
        lv_obj_set_pos(weather_daily_cloud_[i], cx, 142);

        weather_daily_rain_[i] = lv_label_create(weather_container_);
        lv_obj_set_style_text_font(weather_daily_rain_[i], GetTinyFont(), 0);
        lv_obj_set_style_text_color(weather_daily_rain_[i], lv_color_hex(0x55AAFF), 0);
        lv_obj_set_style_text_align(weather_daily_rain_[i], LV_TEXT_ALIGN_CENTER, 0);
        lv_obj_set_width(weather_daily_rain_[i], col_w);
        lv_label_set_text(weather_daily_rain_[i], "");
        lv_obj_set_pos(weather_daily_rain_[i], cx, 152);
    }

    // Astronomy verdict at bottom
    weather_verdict_ = lv_label_create(weather_container_);
    lv_obj_set_style_text_font(weather_verdict_, GetTinyFont(), 0);
    lv_obj_set_style_text_color(weather_verdict_, SG_GOOD_COLOR, 0);
    lv_label_set_text(weather_verdict_, "");
    lv_obj_set_width(weather_verdict_, content_w);
    lv_obj_set_style_text_align(weather_verdict_, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_set_pos(weather_verdict_, 0, 163);

    weather_built_ = true;
    HideWeatherBars();

    // =====================================================================
    // Radar display for aircraft page (built once, hidden)
    // =====================================================================
    {
        int radar_size = 140;  // Diameter
        int radar_r = radar_size / 2;
        int radar_cx = radar_r + 4;   // Center X in container
        int radar_cy = (data_area_h - 20) / 2;  // Center Y

        radar_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(radar_container_);
        lv_obj_set_size(radar_container_, w - 32, data_area_h - 20);
        lv_obj_set_pos(radar_container_, 0, 18);
        lv_obj_set_style_bg_opa(radar_container_, LV_OPA_TRANSP, 0);
        lv_obj_clear_flag(radar_container_, LV_OBJ_FLAG_SCROLLABLE);

        // Outer ring (border circle)
        radar_bg_ = lv_obj_create(radar_container_);
        lv_obj_remove_style_all(radar_bg_);
        lv_obj_set_size(radar_bg_, radar_size, radar_size);
        lv_obj_set_pos(radar_bg_, radar_cx - radar_r, radar_cy - radar_r);
        lv_obj_set_style_radius(radar_bg_, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(radar_bg_, lv_color_hex(0x0D0D1A), 0);
        lv_obj_set_style_bg_opa(radar_bg_, LV_OPA_COVER, 0);
        lv_obj_set_style_border_color(radar_bg_, SG_DIM_COLOR, 0);
        lv_obj_set_style_border_width(radar_bg_, 1, 0);
        lv_obj_clear_flag(radar_bg_, LV_OBJ_FLAG_SCROLLABLE);

        // Middle range ring (25km)
        radar_ring_mid_ = lv_obj_create(radar_bg_);
        lv_obj_remove_style_all(radar_ring_mid_);
        int mid_size = radar_size / 2;
        lv_obj_set_size(radar_ring_mid_, mid_size, mid_size);
        lv_obj_center(radar_ring_mid_);
        lv_obj_set_style_radius(radar_ring_mid_, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(radar_ring_mid_, LV_OPA_TRANSP, 0);
        lv_obj_set_style_border_color(radar_ring_mid_, lv_color_hex(0x222244), 0);
        lv_obj_set_style_border_width(radar_ring_mid_, 1, 0);

        // Crosshair horizontal
        radar_cross_h_ = lv_obj_create(radar_bg_);
        lv_obj_remove_style_all(radar_cross_h_);
        lv_obj_set_size(radar_cross_h_, radar_size - 4, 1);
        lv_obj_center(radar_cross_h_);
        lv_obj_set_style_bg_color(radar_cross_h_, lv_color_hex(0x222244), 0);
        lv_obj_set_style_bg_opa(radar_cross_h_, LV_OPA_COVER, 0);

        // Crosshair vertical
        radar_cross_v_ = lv_obj_create(radar_bg_);
        lv_obj_remove_style_all(radar_cross_v_);
        lv_obj_set_size(radar_cross_v_, 1, radar_size - 4);
        lv_obj_center(radar_cross_v_);
        lv_obj_set_style_bg_color(radar_cross_v_, lv_color_hex(0x222244), 0);
        lv_obj_set_style_bg_opa(radar_cross_v_, LV_OPA_COVER, 0);

        // Center dot (observer position)
        lv_obj_t* center_dot = lv_obj_create(radar_bg_);
        lv_obj_remove_style_all(center_dot);
        lv_obj_set_size(center_dot, 6, 6);
        lv_obj_center(center_dot);
        lv_obj_set_style_radius(center_dot, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(center_dot, SG_GOOD_COLOR, 0);
        lv_obj_set_style_bg_opa(center_dot, LV_OPA_COVER, 0);

        // Aircraft dots + heading trails (positioned dynamically)
        for (int i = 0; i < 8; i++) {
            // Trail line (drawn behind dot, showing heading direction)
            radar_trails_[i] = lv_obj_create(radar_bg_);
            lv_obj_remove_style_all(radar_trails_[i]);
            lv_obj_set_size(radar_trails_[i], 2, 12);  // Thin line, rotated via position
            lv_obj_set_style_bg_color(radar_trails_[i], SG_WARN_COLOR, 0);
            lv_obj_set_style_bg_opa(radar_trails_[i], 100, 0);
            lv_obj_add_flag(radar_trails_[i], LV_OBJ_FLAG_HIDDEN);

            radar_dots_[i] = lv_obj_create(radar_bg_);
            lv_obj_remove_style_all(radar_dots_[i]);
            lv_obj_set_size(radar_dots_[i], 6, 6);
            lv_obj_set_style_radius(radar_dots_[i], LV_RADIUS_CIRCLE, 0);
            lv_obj_set_style_bg_color(radar_dots_[i], SG_WARN_COLOR, 0);
            lv_obj_set_style_bg_opa(radar_dots_[i], LV_OPA_COVER, 0);
            lv_obj_add_flag(radar_dots_[i], LV_OBJ_FLAG_HIDDEN);

            radar_callsigns_[i] = lv_label_create(radar_bg_);
            lv_obj_set_style_text_font(radar_callsigns_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(radar_callsigns_[i], SG_TEXT_COLOR, 0);
            lv_label_set_text(radar_callsigns_[i], "");
            lv_obj_add_flag(radar_callsigns_[i], LV_OBJ_FLAG_HIDDEN);
        }

        // Range label
        radar_range_label_ = lv_label_create(radar_container_);
        lv_obj_set_style_text_font(radar_range_label_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(radar_range_label_, SG_DIM_COLOR, 0);
        lv_label_set_text(radar_range_label_, "50km");
        lv_obj_set_pos(radar_range_label_, radar_cx + radar_r - 20, radar_cy + radar_r + 2);

        // Info lines on the right side
        int info_x = radar_cx + radar_r + 12;
        for (int i = 0; i < 4; i++) {
            radar_info_lines_[i] = lv_label_create(radar_container_);
            lv_obj_set_style_text_font(radar_info_lines_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(radar_info_lines_[i], SG_TEXT_COLOR, 0);
            lv_label_set_text(radar_info_lines_[i], "");
            lv_obj_set_pos(radar_info_lines_[i], info_x, 4 + i * 38);
            lv_obj_set_width(radar_info_lines_[i], w - 32 - info_x);
            lv_label_set_long_mode(radar_info_lines_[i], LV_LABEL_LONG_CLIP);
        }

        // Legend at bottom
        radar_legend_ = lv_label_create(radar_container_);
        lv_obj_set_style_text_font(radar_legend_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(radar_legend_, SG_DIM_COLOR, 0);
        lv_label_set_text(radar_legend_, "Verde >20km  Giallo 10-20km  Rosso <10km");
        lv_obj_set_pos(radar_legend_, 0, data_area_h - 34);
        lv_obj_set_width(radar_legend_, w - 32);
        lv_obj_set_style_text_align(radar_legend_, LV_TEXT_ALIGN_CENTER, 0);

        // Location footer
        radar_location_ = lv_label_create(radar_container_);
        lv_obj_set_style_text_font(radar_location_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(radar_location_, SG_DIM_COLOR, 0);
        lv_label_set_text(radar_location_, LV_SYMBOL_GPS " --");
        lv_obj_set_pos(radar_location_, 0, data_area_h - 22);
        lv_obj_set_width(radar_location_, w - 32);
        lv_obj_set_style_text_align(radar_location_, LV_TEXT_ALIGN_CENTER, 0);

        radar_built_ = true;
        lv_obj_add_flag(radar_container_, LV_OBJ_FLAG_HIDDEN);
    }

    // =====================================================================
    // Satellite sky dome (built once, hidden until PAGE_SATELLITES)
    // =====================================================================
    {
        int dome_size = 130;
        int dome_r = dome_size / 2;
        int dome_cx = dome_r + 4;
        int dome_cy = (data_area_h - 20) / 2;

        sat_dome_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(sat_dome_container_);
        lv_obj_set_size(sat_dome_container_, w - 32, data_area_h - 20);
        lv_obj_set_pos(sat_dome_container_, 0, 18);
        lv_obj_set_style_bg_opa(sat_dome_container_, LV_OPA_TRANSP, 0);
        lv_obj_clear_flag(sat_dome_container_, LV_OBJ_FLAG_SCROLLABLE);

        // Sky dome circle (dark blue = sky)
        sat_dome_bg_ = lv_obj_create(sat_dome_container_);
        lv_obj_remove_style_all(sat_dome_bg_);
        lv_obj_set_size(sat_dome_bg_, dome_size, dome_size);
        lv_obj_set_pos(sat_dome_bg_, dome_cx - dome_r, dome_cy - dome_r);
        lv_obj_set_style_radius(sat_dome_bg_, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(sat_dome_bg_, lv_color_hex(0x050520), 0);
        lv_obj_set_style_bg_opa(sat_dome_bg_, LV_OPA_COVER, 0);
        lv_obj_set_style_border_color(sat_dome_bg_, SG_DIM_COLOR, 0);
        lv_obj_set_style_border_width(sat_dome_bg_, 1, 0);
        lv_obj_clear_flag(sat_dome_bg_, LV_OBJ_FLAG_SCROLLABLE);

        // 45° elevation ring (inner circle = high elevation)
        sat_dome_ring_ = lv_obj_create(sat_dome_bg_);
        lv_obj_remove_style_all(sat_dome_ring_);
        int ring_size = dome_size / 2;
        lv_obj_set_size(sat_dome_ring_, ring_size, ring_size);
        lv_obj_center(sat_dome_ring_);
        lv_obj_set_style_radius(sat_dome_ring_, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_opa(sat_dome_ring_, LV_OPA_TRANSP, 0);
        lv_obj_set_style_border_color(sat_dome_ring_, lv_color_hex(0x151540), 0);
        lv_obj_set_style_border_width(sat_dome_ring_, 1, 0);

        // Crosshairs
        sat_dome_cross_h_ = lv_obj_create(sat_dome_bg_);
        lv_obj_remove_style_all(sat_dome_cross_h_);
        lv_obj_set_size(sat_dome_cross_h_, dome_size - 4, 1);
        lv_obj_center(sat_dome_cross_h_);
        lv_obj_set_style_bg_color(sat_dome_cross_h_, lv_color_hex(0x151540), 0);
        lv_obj_set_style_bg_opa(sat_dome_cross_h_, LV_OPA_COVER, 0);

        sat_dome_cross_v_ = lv_obj_create(sat_dome_bg_);
        lv_obj_remove_style_all(sat_dome_cross_v_);
        lv_obj_set_size(sat_dome_cross_v_, 1, dome_size - 4);
        lv_obj_center(sat_dome_cross_v_);
        lv_obj_set_style_bg_color(sat_dome_cross_v_, lv_color_hex(0x151540), 0);
        lv_obj_set_style_bg_opa(sat_dome_cross_v_, LV_OPA_COVER, 0);

        // Zenith dot
        lv_obj_t* zenith = lv_obj_create(sat_dome_bg_);
        lv_obj_remove_style_all(zenith);
        lv_obj_set_size(zenith, 4, 4);
        lv_obj_center(zenith);
        lv_obj_set_style_radius(zenith, LV_RADIUS_CIRCLE, 0);
        lv_obj_set_style_bg_color(zenith, SG_DIM_COLOR, 0);
        lv_obj_set_style_bg_opa(zenith, LV_OPA_COVER, 0);

        // Satellite dots + trajectory trail dots
        for (int i = 0; i < 6; i++) {
            // Trail dots (5 points along pass arc: start→mid→end)
            for (int j = 0; j < 5; j++) {
                sat_trail_dots_[i][j] = lv_obj_create(sat_dome_bg_);
                lv_obj_remove_style_all(sat_trail_dots_[i][j]);
                lv_obj_set_size(sat_trail_dots_[i][j], 3, 3);
                lv_obj_set_style_radius(sat_trail_dots_[i][j], LV_RADIUS_CIRCLE, 0);
                lv_obj_set_style_bg_color(sat_trail_dots_[i][j], SG_DIM_COLOR, 0);
                lv_obj_set_style_bg_opa(sat_trail_dots_[i][j], 100, 0);
                lv_obj_add_flag(sat_trail_dots_[i][j], LV_OBJ_FLAG_HIDDEN);
            }

            sat_dots_[i] = lv_obj_create(sat_dome_bg_);
            lv_obj_remove_style_all(sat_dots_[i]);
            lv_obj_set_size(sat_dots_[i], 6, 6);
            lv_obj_set_style_radius(sat_dots_[i], LV_RADIUS_CIRCLE, 0);
            lv_obj_set_style_bg_color(sat_dots_[i], SG_GOOD_COLOR, 0);
            lv_obj_set_style_bg_opa(sat_dots_[i], LV_OPA_COVER, 0);
            lv_obj_add_flag(sat_dots_[i], LV_OBJ_FLAG_HIDDEN);

            sat_labels_[i] = lv_label_create(sat_dome_bg_);
            lv_obj_set_style_text_font(sat_labels_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(sat_labels_[i], SG_TEXT_COLOR, 0);
            lv_label_set_text(sat_labels_[i], "");
            lv_obj_add_flag(sat_labels_[i], LV_OBJ_FLAG_HIDDEN);
        }

        // NSEW labels on dome edge
        const char* dirs[] = {"N", "E", "S", "W"};
        int dir_offsets[][2] = {{dome_r-4, 2}, {dome_size-12, dome_r-5}, {dome_r-4, dome_size-14}, {2, dome_r-5}};
        for (int i = 0; i < 4; i++) {
            lv_obj_t* dl = lv_label_create(sat_dome_bg_);
            lv_obj_set_style_text_font(dl, GetTinyFont(), 0);
            lv_obj_set_style_text_color(dl, SG_DIM_COLOR, 0);
            lv_label_set_text(dl, dirs[i]);
            lv_obj_set_pos(dl, dir_offsets[i][0], dir_offsets[i][1]);
        }

        // Info lines right side
        int info_x = dome_cx + dome_r + 10;
        for (int i = 0; i < 3; i++) {
            sat_info_lines_[i] = lv_label_create(sat_dome_container_);
            lv_obj_set_style_text_font(sat_info_lines_[i], GetTinyFont(), 0);
            lv_obj_set_style_text_color(sat_info_lines_[i], SG_TEXT_COLOR, 0);
            lv_label_set_text(sat_info_lines_[i], "");
            lv_obj_set_pos(sat_info_lines_[i], info_x, 4 + i * 50);
            lv_obj_set_width(sat_info_lines_[i], w - 32 - info_x);
            lv_label_set_long_mode(sat_info_lines_[i], LV_LABEL_LONG_WRAP);
        }

        // Legend at bottom
        sat_legend_ = lv_label_create(sat_dome_container_);
        lv_obj_set_style_text_font(sat_legend_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(sat_legend_, SG_DIM_COLOR, 0);
        lv_label_set_text(sat_legend_, "Verde Mag<0  Giallo Mag 0-3  Grigio Mag>3");
        lv_obj_set_pos(sat_legend_, 0, data_area_h - 34);
        lv_obj_set_width(sat_legend_, w - 32);
        lv_obj_set_style_text_align(sat_legend_, LV_TEXT_ALIGN_CENTER, 0);

        // Location footer
        sat_location_ = lv_label_create(sat_dome_container_);
        lv_obj_set_style_text_font(sat_location_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(sat_location_, SG_DIM_COLOR, 0);
        lv_label_set_text(sat_location_, LV_SYMBOL_GPS " --");
        lv_obj_set_pos(sat_location_, 0, data_area_h - 22);
        lv_obj_set_width(sat_location_, w - 32);
        lv_obj_set_style_text_align(sat_location_, LV_TEXT_ALIGN_CENTER, 0);

        sat_dome_built_ = true;
        lv_obj_add_flag(sat_dome_container_, LV_OBJ_FLAG_HIDDEN);
    }

    // =====================================================================
    // Meteosat satellite canvas (built once, hidden) — fullscreen
    // =====================================================================
    {
        int canvas_buf_size = LV_CANVAS_BUF_SIZE(METEO_W, METEO_H, 16, LV_DRAW_BUF_STRIDE_ALIGN);
        meteosat_canvas_buf_ = (uint8_t*)heap_caps_calloc(1, canvas_buf_size, MALLOC_CAP_SPIRAM);
        if (meteosat_canvas_buf_) {
            meteosat_canvas_ = lv_canvas_create(data_area_);
            lv_canvas_set_buffer(meteosat_canvas_, meteosat_canvas_buf_,
                                 METEO_W, METEO_H, LV_COLOR_FORMAT_RGB565);
            // Fill data area, right below title
            lv_obj_set_pos(meteosat_canvas_, 0, 18);
            lv_obj_add_flag(meteosat_canvas_, LV_OBJ_FLAG_HIDDEN);

            // Overlay text labels on top of the image (small white, semi-transparent bg)
            meteosat_overlay_status_ = lv_label_create(data_area_);
            lv_obj_set_style_text_font(meteosat_overlay_status_, GetTinyFont(), 0);
            lv_obj_set_style_text_color(meteosat_overlay_status_, lv_color_white(), 0);
            lv_obj_set_style_bg_color(meteosat_overlay_status_, lv_color_black(), 0);
            lv_obj_set_style_bg_opa(meteosat_overlay_status_, LV_OPA_50, 0);
            lv_obj_set_style_pad_all(meteosat_overlay_status_, 2, 0);
            lv_obj_set_pos(meteosat_overlay_status_, 2, METEO_H + 18 - 14);  // bottom-left of canvas
            lv_label_set_text(meteosat_overlay_status_, "");
            lv_obj_add_flag(meteosat_overlay_status_, LV_OBJ_FLAG_HIDDEN);

            meteosat_overlay_source_ = lv_label_create(data_area_);
            lv_obj_set_style_text_font(meteosat_overlay_source_, GetTinyFont(), 0);
            lv_obj_set_style_text_color(meteosat_overlay_source_, lv_color_white(), 0);
            lv_obj_set_style_bg_color(meteosat_overlay_source_, lv_color_black(), 0);
            lv_obj_set_style_bg_opa(meteosat_overlay_source_, LV_OPA_50, 0);
            lv_obj_set_style_pad_all(meteosat_overlay_source_, 2, 0);
            lv_obj_set_pos(meteosat_overlay_source_, METEO_W - 100, METEO_H + 18 - 14);  // bottom-right
            lv_label_set_text(meteosat_overlay_source_, "meteociel.fr");
            lv_obj_add_flag(meteosat_overlay_source_, LV_OBJ_FLAG_HIDDEN);

            meteosat_built_ = true;
        }
    }

    // =====================================================================
    // GPS mini-map image widget (built once, hidden) — 140x140 on right side
    // Uses LVGL's built-in LodePNG decoder — no manual pixel conversion
    // =====================================================================
    {
        gps_map_img_ = lv_image_create(data_area_);
        lv_obj_set_size(gps_map_img_, GPS_MAP_W, GPS_MAP_H);
        lv_obj_set_pos(gps_map_img_, w - 32 - GPS_MAP_W, 18);
        lv_obj_add_flag(gps_map_img_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_style_radius(gps_map_img_, 4, 0);
        lv_obj_set_style_clip_corner(gps_map_img_, true, 0);
        lv_obj_set_style_border_width(gps_map_img_, 1, 0);
        lv_obj_set_style_border_color(gps_map_img_, SG_DIM_COLOR, 0);
        lv_image_set_inner_align(gps_map_img_, LV_IMAGE_ALIGN_CENTER);
        gps_map_built_ = true;
    }

    // =====================================================================
    // Countdown measurement overlay (built once, hidden)
    // =====================================================================
    // Countdown is on overlay_ (not data_area_) so it covers everything including buttons
    countdown_container_ = lv_obj_create(overlay_);
    lv_obj_remove_style_all(countdown_container_);
    lv_obj_set_size(countdown_container_, lv_pct(100), lv_pct(100));
    lv_obj_set_pos(countdown_container_, 0, 0);
    lv_obj_set_style_bg_color(countdown_container_, SG_BG_COLOR, 0);
    lv_obj_set_style_bg_opa(countdown_container_, LV_OPA_COVER, 0);
    lv_obj_clear_flag(countdown_container_, LV_OBJ_FLAG_SCROLLABLE);

    countdown_title_ = lv_label_create(countdown_container_);
    lv_obj_set_style_text_font(countdown_title_, GetSmallFont(), 0);
    lv_obj_set_style_text_color(countdown_title_, SG_TITLE_COLOR, 0);
    lv_label_set_text(countdown_title_, "MISURAZIONE SQM");
    lv_obj_align(countdown_title_, LV_ALIGN_TOP_MID, 0, 4);

    countdown_text_ = lv_label_create(countdown_container_);
    lv_obj_set_style_text_font(countdown_text_, GetTinyFont(), 0);
    lv_obj_set_style_text_color(countdown_text_, SG_WARN_COLOR, 0);
    lv_label_set_text(countdown_text_, "Punta allo Zenit - Resta fermo");
    lv_obj_align(countdown_text_, LV_ALIGN_TOP_MID, 0, 24);

    countdown_arc_ = lv_arc_create(countdown_container_);
    lv_obj_set_size(countdown_arc_, 120, 120);
    lv_obj_align(countdown_arc_, LV_ALIGN_CENTER, 0, 10);
    lv_arc_set_range(countdown_arc_, 0, 100);
    lv_arc_set_value(countdown_arc_, 100);
    lv_arc_set_bg_angles(countdown_arc_, 0, 360);
    lv_obj_set_style_arc_width(countdown_arc_, 8, LV_PART_MAIN);
    lv_obj_set_style_arc_width(countdown_arc_, 8, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(countdown_arc_, SG_DIM_COLOR, LV_PART_MAIN);
    lv_obj_set_style_arc_color(countdown_arc_, SG_TITLE_COLOR, LV_PART_INDICATOR);
    lv_obj_remove_style(countdown_arc_, nullptr, LV_PART_KNOB);
    lv_obj_clear_flag(countdown_arc_, LV_OBJ_FLAG_CLICKABLE);

    countdown_label_ = lv_label_create(countdown_container_);
    lv_obj_set_style_text_font(countdown_label_, GetSmallFont(), 0);  // montserrat_14
    lv_obj_set_style_text_color(countdown_label_, SG_VALUE_COLOR, 0);
    lv_label_set_text(countdown_label_, "10");
    lv_obj_align(countdown_label_, LV_ALIGN_CENTER, 0, 10);

    lv_obj_add_flag(countdown_container_, LV_OBJ_FLAG_HIDDEN);

    // =====================================================================
    // Page indicator dots — 9 dots for 9 pages
    // =====================================================================
    page_indicator_ = lv_obj_create(overlay_);
    lv_obj_remove_style_all(page_indicator_);
    lv_obj_set_size(page_indicator_, w, 16);
    lv_obj_set_pos(page_indicator_, 0, data_h - 18);
    lv_obj_set_style_bg_opa(page_indicator_, LV_OPA_TRANSP, 0);
    lv_obj_set_flex_flow(page_indicator_, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(page_indicator_, LV_FLEX_ALIGN_CENTER,
                          LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(page_indicator_, 8, 0);
    lv_obj_clear_flag(page_indicator_, LV_OBJ_FLAG_SCROLLABLE);

    for (int i = 0; i < PAGE_COUNT; i++) {
        lv_obj_t* dot = lv_obj_create(page_indicator_);
        lv_obj_remove_style_all(dot);
        lv_obj_set_size(dot, 8, 8);
        lv_obj_set_style_radius(dot, 4, 0);
        lv_obj_set_style_bg_opa(dot, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(dot,
            (i == 0) ? SG_DOT_ACTIVE : SG_DOT_INACTIVE, 0);
    }

    // Fix 3: Lower gesture thresholds for 320x240 screen
    lv_indev_t* touch_indev = lv_indev_active();
    if (!touch_indev) {
        touch_indev = lv_indev_get_next(nullptr);
        while (touch_indev && lv_indev_get_type(touch_indev) != LV_INDEV_TYPE_POINTER) {
            touch_indev = lv_indev_get_next(touch_indev);
        }
    }
    if (touch_indev) {
        touch_indev->gesture_limit = 15;
        touch_indev->gesture_min_velocity = 1;
        touch_indev->scroll_limit = 30;
        ESP_LOGI(TAG, "Touch thresholds: gesture_limit=15, min_velocity=1, scroll_limit=30");
    } else {
        ESP_LOGW(TAG, "No pointer indev found — gesture thresholds not adjusted");
    }

    // Touch gesture on data area — swipe left/right to change pages
    lv_obj_add_event_cb(data_area_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        if (self->measuring_) return;  // Ignore during countdown
        lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_active());
        ESP_LOGI("SkyGuardUI", "Touch GESTURE detected, dir=%d (L=%d R=%d)", dir, LV_DIR_LEFT, LV_DIR_RIGHT);
        if (dir == LV_DIR_LEFT) self->NextPage();
        else if (dir == LV_DIR_RIGHT) self->PrevPage();
    }, LV_EVENT_GESTURE, this);

    // Tap fallback
    lv_obj_add_event_cb(data_area_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        if (self->measuring_) return;
        lv_point_t p;
        lv_indev_get_point(lv_indev_active(), &p);
        ESP_LOGI("SkyGuardUI", "Touch CLICKED at x=%" PRId32 " y=%" PRId32, p.x, p.y);
        if (p.x < 80) {
            self->PrevPage();
        } else if (p.x > 240) {
            self->NextPage();
        }
    }, LV_EVENT_CLICKED, this);

    // Touch on overlay too
    lv_obj_add_flag(overlay_, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(overlay_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        if (self->measuring_) return;
        lv_dir_t dir = lv_indev_get_gesture_dir(lv_indev_active());
        if (dir == LV_DIR_LEFT) self->NextPage();
        else if (dir == LV_DIR_RIGHT) self->PrevPage();
    }, LV_EVENT_GESTURE, this);

    // =====================================================================
    // MIC MUTE button — always visible overlay (top-right, below status bar)
    // Created on screen (not overlay) so it stays visible during AI chat
    // =====================================================================
    mic_mute_btn_ = lv_obj_create(screen);
    lv_obj_remove_style_all(mic_mute_btn_);
    lv_obj_set_size(mic_mute_btn_, 32, 24);
    lv_obj_set_pos(mic_mute_btn_, 286, 0);  // Top-right, inside status bar area
    lv_obj_set_style_bg_color(mic_mute_btn_, lv_color_hex(0x1A3366), 0);
    lv_obj_set_style_bg_opa(mic_mute_btn_, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(mic_mute_btn_, 6, 0);
    lv_obj_add_flag(mic_mute_btn_, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(mic_mute_btn_, LV_OBJ_FLAG_SCROLLABLE);

    mic_mute_icon_ = lv_label_create(mic_mute_btn_);
    lv_label_set_text(mic_mute_icon_, "MIC");
    lv_obj_set_style_text_font(mic_mute_icon_, GetTinyFont(), 0);
    lv_obj_set_style_text_color(mic_mute_icon_, lv_color_white(), 0);
    lv_obj_center(mic_mute_icon_);

    lv_obj_add_event_cb(mic_mute_btn_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        self->ToggleMicMute();
    }, LV_EVENT_CLICKED, this);

    // Floating star avatar — draggable, tap to talk
    CreateFloatingStar();

    // Build initial page
    SetPage(PAGE_SQM);

    lvgl_port_unlock();
    ESP_LOGI(TAG, "SkyGuard display ready (full-width, %d pages)", PAGE_COUNT);
}

// ==========================================================================
// SPECTRAL BAR HELPERS
// ==========================================================================

// =========================================================================
// WEATHER ICON DRAWING (20x20 canvas)
// =========================================================================

void SkyGuardDisplay::DrawWeatherIcon(lv_obj_t* canvas, int clouds, const char* desc) {
    if (!canvas) return;

    const int S = WICON_MINI;  // 20
    lv_color_t bg = lv_color_hex(0x1A1A2E);
    lv_canvas_fill_bg(canvas, bg, LV_OPA_COVER);

    // Detect weather conditions from description keywords
    bool has_rain = false, has_snow = false, has_thunder = false, is_clear = false;
    if (desc && desc[0] != '\0') {
        has_rain = (strstr(desc, "piog") || strstr(desc, "rain") ||
                    strstr(desc, "shower") || strstr(desc, "drizzle"));
        has_snow = (strstr(desc, "neve") || strstr(desc, "snow") || strstr(desc, "sleet"));
        has_thunder = (strstr(desc, "temporale") || strstr(desc, "thunder"));
        if (has_thunder) has_rain = true;
        // Detect clear/sunny from Italian OWM descriptions
        is_clear = (strstr(desc, "sereno") || strstr(desc, "clear") ||
                    strstr(desc, "sole") || strstr(desc, "sun"));
    }
    // Override clouds threshold when description says it's clear
    if (is_clear) clouds = 0;

    lv_color_t sun_core = lv_color_hex(0xFFDD00);
    lv_color_t sun_glow = lv_color_hex(0xFFAA00);
    lv_color_t cloud_hi = lv_color_hex(0xCCDDEE);
    lv_color_t cloud_lo = lv_color_hex(0x8899AA);
    lv_color_t dark_cloud = lv_color_hex(0x556677);
    lv_color_t rain_col = lv_color_hex(0x55AAFF);
    lv_color_t snow_col = lv_color_hex(0xEEF4FF);
    lv_color_t bolt_col = lv_color_hex(0xFFFF00);

    // Helper: draw filled circle
    auto fillCircle = [&](int cx, int cy, float r, lv_color_t col) {
        int ri = (int)(r + 1.5f);
        for (int py = cy - ri; py <= cy + ri; py++)
            for (int px = cx - ri; px <= cx + ri; px++) {
                if (px < 0 || px >= S || py < 0 || py >= S) continue;
                float d = sqrtf((float)(px-cx)*(px-cx) + (float)(py-cy)*(py-cy));
                if (d <= r) lv_canvas_set_px(canvas, px, py, col, LV_OPA_COVER);
                else if (d <= r + 1.0f)
                    lv_canvas_set_px(canvas, px, py, col, (lv_opa_t)((r + 1.0f - d) * 255));
            }
    };

    // Helper: draw cloud shape (3 merged circles)
    auto drawCloud = [&](int ox, int oy, float scale, lv_color_t top_col, lv_color_t bot_col) {
        for (int py = oy - (int)(10*scale); py <= oy + (int)(8*scale); py++)
            for (int px = ox - (int)(12*scale); px <= ox + (int)(12*scale); px++) {
                if (px < 0 || px >= S || py < 0 || py >= S) continue;
                float d1 = sqrtf((float)(px-ox)*(px-ox) + (float)(py-oy)*(py-oy));
                float d2 = sqrtf((float)(px-(ox-5*scale))*(px-(ox-5*scale)) + (float)(py-(oy+2*scale))*(py-(oy+2*scale)));
                float d3 = sqrtf((float)(px-(ox+5*scale))*(px-(ox+5*scale)) + (float)(py-(oy+1*scale))*(py-(oy+1*scale)));
                float min_d = d1;
                if (d2 < min_d) min_d = d2;
                if (d3 < min_d) min_d = d3;
                float r_main = 7.0f * scale;
                float r_side = 6.0f * scale;
                if (d1 <= r_main || d2 <= r_side || d3 <= r_side) {
                    // Gradient: lighter on top, darker on bottom
                    float t = (float)(py - (oy - 8*scale)) / (16.0f * scale);
                    if (t < 0) t = 0;
                    if (t > 1) t = 1;
                    int r_t = ((top_col.red >> 3) * (int)((1-t)*255) + (bot_col.red >> 3) * (int)(t*255)) / 255;
                    int g_t = ((top_col.green >> 2) * (int)((1-t)*255) + (bot_col.green >> 2) * (int)(t*255)) / 255;
                    int b_t = ((top_col.blue >> 3) * (int)((1-t)*255) + (bot_col.blue >> 3) * (int)(t*255)) / 255;
                    lv_color_t c = lv_color_make(r_t << 3, g_t << 2, b_t << 3);
                    lv_canvas_set_px(canvas, px, py, c, LV_OPA_COVER);
                } else if (d1 <= r_main + 1 || d2 <= r_side + 1 || d3 <= r_side + 1) {
                    float edge = (d1 <= r_main + 1) ? (r_main + 1 - d1) :
                                 (d2 <= r_side + 1) ? (r_side + 1 - d2) : (r_side + 1 - d3);
                    lv_canvas_set_px(canvas, px, py, bot_col, (lv_opa_t)(edge * 200));
                }
            }
    };

    if (clouds < 25 && !has_rain && !has_snow) {
        // ===== CLEAR SKY — bright sun with rays =====
        int cx = S/2, cy = S/2;
        fillCircle(cx, cy, S*0.40f, sun_glow);
        fillCircle(cx, cy, S*0.28f, sun_core);
        fillCircle(cx-2, cy-2, S*0.12f, lv_color_hex(0xFFFFCC));
        // 8 rays (scaled)
        for (int a = 0; a < 8; a++) {
            float angle = a * 3.14159f / 4.0f;
            for (int k = (int)(S*0.38f); k <= (int)(S*0.48f); k++) {
                int rx = cx + (int)(k * cosf(angle));
                int ry = cy + (int)(k * sinf(angle));
                if (rx >= 0 && rx < S && ry >= 0 && ry < S) {
                    lv_opa_t opa = (lv_opa_t)(255 - (k - (int)(S*0.38f)) * 40);
                    lv_canvas_set_px(canvas, rx, ry, sun_core, opa);
                    if (rx+1 < S) lv_canvas_set_px(canvas, rx+1, ry, sun_glow, opa/2);
                    if (ry+1 < S) lv_canvas_set_px(canvas, rx, ry+1, sun_glow, opa/2);
                }
            }
        }
    } else if (clouds < 50 && !has_rain && !has_snow) {
        // ===== PARTLY CLOUDY — sun peeking + cloud =====
        int sx = S*3/10, sy = S*3/10;
        fillCircle(sx, sy, S*0.28f, sun_glow);
        fillCircle(sx, sy, S*0.20f, sun_core);
        fillCircle(sx-1, sy-1, S*0.08f, lv_color_hex(0xFFFFCC));
        for (int a = 0; a < 5; a++) {
            float angle = a * 3.14159f / 4.0f - 0.4f;
            for (int k = (int)(S*0.28f); k <= (int)(S*0.38f); k++) {
                int rx = sx + (int)(k * cosf(angle));
                int ry = sy + (int)(k * sinf(angle));
                if (rx >= 0 && rx < S && ry >= 0 && ry < S)
                    lv_canvas_set_px(canvas, rx, ry, sun_core, 180);
            }
        }
        drawCloud(S*9/16, S*5/8, 1.2f, cloud_hi, cloud_lo);
    } else {
        // ===== CLOUDY / OVERCAST / RAIN / SNOW =====
        lv_color_t top = (clouds > 70) ? cloud_lo : cloud_hi;
        lv_color_t bot = (clouds > 70) ? dark_cloud : cloud_lo;
        drawCloud(S/2, S*3/8, 1.5f, top, bot);

        if (has_rain) {
            int dy = S*3/4;
            const int drops[][2] = {{S*2/8,dy},{S*3/8,dy+2},{S*4/8,dy-1},{S*5/8,dy+3},{S*6/8,dy+1},
                                    {S*3/10,dy+5},{S*5/10,dy+6},{S*7/10,dy+4}};
            for (auto& dp : drops) {
                if (dp[0] >= 0 && dp[0] < S && dp[1] >= 0 && dp[1]+2 < S) {
                    lv_canvas_set_px(canvas, dp[0], dp[1], rain_col, LV_OPA_COVER);
                    lv_canvas_set_px(canvas, dp[0], dp[1]+1, rain_col, 220);
                    lv_canvas_set_px(canvas, dp[0], dp[1]+2, rain_col, 140);
                }
            }
            if (has_thunder) {
                int bx = S*7/16;
                const int bolt[][2] = {{bx,S*5/8},{bx-1,S*11/16},{bx+1,S*3/4},{bx-1,S*13/16},{bx-2,S*7/8},{bx,S*15/16}};
                for (auto& bp : bolt) {
                    if (bp[0] >= 0 && bp[0]+1 < S && bp[1] >= 0 && bp[1] < S) {
                        lv_canvas_set_px(canvas, bp[0], bp[1], bolt_col, LV_OPA_COVER);
                        lv_canvas_set_px(canvas, bp[0]+1, bp[1], bolt_col, 180);
                    }
                }
            }
        } else if (has_snow) {
            int dy = S*3/4;
            const int flakes[][2] = {{S*2/8,dy},{S*4/8,dy+2},{S*6/8,dy},{S*3/8,dy+5},{S*5/8,dy+4}};
            for (auto& fp : flakes) {
                int fx = fp[0], fy = fp[1];
                if (fx >= 1 && fx+1 < S && fy >= 1 && fy+1 < S) {
                    lv_canvas_set_px(canvas, fx, fy, snow_col, LV_OPA_COVER);
                    lv_canvas_set_px(canvas, fx-1, fy, snow_col, 160);
                    lv_canvas_set_px(canvas, fx+1, fy, snow_col, 160);
                    lv_canvas_set_px(canvas, fx, fy-1, snow_col, 160);
                    lv_canvas_set_px(canvas, fx, fy+1, snow_col, 160);
                }
            }
        }
    }
}

// ==========================================================================
// DASHBOARD PIXEL-ART ICONS (10x10 bitmaps, 1 byte per row)
// ==========================================================================

// 8x8 pixel art bitmaps — each byte is one row, MSB = leftmost pixel
// Icons: 0=moon, 1=thermometer, 2=drop, 3=cloud, 4=wind, 5=eye, 6=plane, 7=satellite
static const uint8_t kDashIcons[8][8] = {
    // 0: Moon crescent (C-shape)
    { 0x30, 0x40, 0x80, 0x80, 0x80, 0x80, 0x40, 0x30 },
    // 1: Thermometer (vertical bar + bulb)
    { 0x18, 0x18, 0x18, 0x18, 0x18, 0x3C, 0x3C, 0x18 },
    // 2: Water droplet (teardrop)
    { 0x10, 0x38, 0x38, 0x7C, 0x7C, 0x7C, 0x38, 0x10 },
    // 3: Cloud (bumpy top, flat bottom)
    { 0x00, 0x30, 0x78, 0xFE, 0xFE, 0x7C, 0x00, 0x00 },
    // 4: Wind (3 horizontal lines, staggered)
    { 0x00, 0x7C, 0x00, 0xFC, 0x00, 0x3E, 0x00, 0x00 },
    // 5: Eye / seeing
    { 0x00, 0x3C, 0x42, 0x99, 0x99, 0x42, 0x3C, 0x00 },
    // 6: Airplane (top view)
    { 0x10, 0x10, 0x38, 0x7C, 0xFF, 0x10, 0x38, 0x10 },
    // 7: Satellite (body + solar panels)
    { 0x82, 0x44, 0x38, 0x38, 0x38, 0x44, 0x82, 0x00 },
};

void SkyGuardDisplay::DrawDashIcon(lv_obj_t* canvas, int icon_idx, lv_color_t color) {
    if (!canvas || icon_idx < 0 || icon_idx >= 8) return;
    const uint8_t* bmp = kDashIcons[icon_idx];
    // Draw 8x8 bitmap centered in 10x10 canvas (1px offset)
    for (int y = 0; y < 8; y++) {
        uint8_t row = bmp[y];
        for (int x = 0; x < 8; x++) {
            if (row & (0x80 >> x)) {
                lv_canvas_set_px(canvas, x + 1, y + 1, color, LV_OPA_COVER);
            }
        }
    }
}

void SkyGuardDisplay::SetLocationName(const char* name) {
    if (name) {
        strncpy(location_name_, name, sizeof(location_name_) - 1);
        location_name_[sizeof(location_name_) - 1] = '\0';
    }
}

void SkyGuardDisplay::HideDashboard() {
    // Hide card containers (children are hidden automatically by LVGL)
    if (dash_left_card_) lv_obj_add_flag(dash_left_card_, LV_OBJ_FLAG_HIDDEN);
    if (dash_right_card_) lv_obj_add_flag(dash_right_card_, LV_OBJ_FLAG_HIDDEN);
    if (dash_bottom_bar_) lv_obj_add_flag(dash_bottom_bar_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowDashboard() {
    if (dash_left_card_) lv_obj_clear_flag(dash_left_card_, LV_OBJ_FLAG_HIDDEN);
    if (dash_right_card_) lv_obj_clear_flag(dash_right_card_, LV_OBJ_FLAG_HIDDEN);
    if (dash_bottom_bar_) lv_obj_clear_flag(dash_bottom_bar_, LV_OBJ_FLAG_HIDDEN);
}

// Keep legacy names for any external references
void SkyGuardDisplay::HideSqmBig() { HideDashboard(); }
void SkyGuardDisplay::ShowSqmBig() { ShowDashboard(); }

void SkyGuardDisplay::HideMoonCanvas() {
    if (moon_canvas_) lv_obj_add_flag(moon_canvas_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowMoonCanvas() {
    if (moon_canvas_) {
        // Position centered in moon left card area (card is at x=0, y=16, size 120x158)
        lv_obj_set_pos(moon_canvas_, 36, 22);  // Center 48px canvas in 120px card
        lv_obj_clear_flag(moon_canvas_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_move_foreground(moon_canvas_);   // Draw on top of card containers
    }
}

void SkyGuardDisplay::DrawMoonPhase(float illumination, uint8_t phaseIndex) {
    if (!moon_canvas_ || !moon_canvas_buf_) return;

    const int R = MOON_SIZE / 2 - 1;  // 22
    const int cx = MOON_SIZE / 2;
    const int cy = MOON_SIZE / 2;

    // Clear to black
    lv_canvas_fill_bg(moon_canvas_, lv_color_hex(0x000000), LV_OPA_COVER);

    // Draw full moon disc (dark gray base)
    lv_draw_arc_dsc_t arc_dsc;
    lv_draw_arc_dsc_init(&arc_dsc);

    // Draw lit portion using pixel-by-pixel for accuracy
    float frac = illumination / 100.0f;
    bool waxing = (phaseIndex >= 1 && phaseIndex <= 4);

    lv_color_t lit_color = lv_color_hex(0xEEDD88);   // Warm moon yellow
    lv_color_t dark_color = lv_color_hex(0x333333);   // Dark side

    for (int y = 0; y < MOON_SIZE; y++) {
        for (int x = 0; x < MOON_SIZE; x++) {
            float dx = x - cx;
            float dy = y - cy;
            float dist = sqrtf(dx * dx + dy * dy);
            if (dist > R) continue;  // Outside moon

            // Determine if pixel is lit based on phase
            // The terminator is an ellipse with semi-minor axis = R * |2*frac - 1|
            float rel_x = dx / (float)R;  // -1 to 1
            float terminator_x = (2.0f * frac - 1.0f);  // -1 (new) to 1 (full)

            bool lit;
            if (waxing) {
                lit = (rel_x >= -terminator_x);  // Right side lit for waxing
            } else {
                lit = (rel_x <= terminator_x);   // Left side lit for waning
            }

            // Edge anti-aliasing via opacity
            lv_color_t col = lit ? lit_color : dark_color;
            lv_opa_t opa = LV_OPA_COVER;
            if (dist > R - 1.0f) {
                float edge = R - dist;  // 0..1
                opa = (lv_opa_t)(edge * 255);
            }

            lv_canvas_set_px(moon_canvas_, x, y, col, opa);
        }
    }
}

void SkyGuardDisplay::HideSpectralBars() {
    if (spectral_container_) lv_obj_add_flag(spectral_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowSpectralBars() {
    if (spectral_container_) lv_obj_clear_flag(spectral_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::HideWeatherBars() {
    if (weather_container_) {
        lv_obj_add_flag(weather_container_, LV_OBJ_FLAG_HIDDEN);
    }
}

void SkyGuardDisplay::ShowWeatherBars() {
    if (weather_container_) {
        lv_obj_clear_flag(weather_container_, LV_OBJ_FLAG_HIDDEN);
    }
}

void SkyGuardDisplay::HideRadar() {
    if (radar_container_) {
        lv_obj_add_flag(radar_container_, LV_OBJ_FLAG_HIDDEN);
    }
}

void SkyGuardDisplay::ShowRadar() {
    if (radar_container_) {
        lv_obj_clear_flag(radar_container_, LV_OBJ_FLAG_HIDDEN);
    }
}

void SkyGuardDisplay::HideSatDome() {
    if (sat_dome_container_) {
        lv_obj_add_flag(sat_dome_container_, LV_OBJ_FLAG_HIDDEN);
    }
}

void SkyGuardDisplay::ShowSatDome() {
    if (sat_dome_container_) {
        lv_obj_clear_flag(sat_dome_container_, LV_OBJ_FLAG_HIDDEN);
    }
}

void SkyGuardDisplay::HideMeteosat() {
    if (meteosat_canvas_) lv_obj_add_flag(meteosat_canvas_, LV_OBJ_FLAG_HIDDEN);
    if (meteosat_overlay_status_) lv_obj_add_flag(meteosat_overlay_status_, LV_OBJ_FLAG_HIDDEN);
    if (meteosat_overlay_source_) lv_obj_add_flag(meteosat_overlay_source_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowMeteosat() {
    if (meteosat_canvas_) lv_obj_clear_flag(meteosat_canvas_, LV_OBJ_FLAG_HIDDEN);
    if (meteosat_overlay_status_) lv_obj_clear_flag(meteosat_overlay_status_, LV_OBJ_FLAG_HIDDEN);
    if (meteosat_overlay_source_) lv_obj_clear_flag(meteosat_overlay_source_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::HideGpsMap() {
    if (gps_map_img_) lv_obj_add_flag(gps_map_img_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowGpsMap() {
    if (gps_map_img_) {
        // Position inside GPS right card area (card at x=156, y=16, size 142x158)
        lv_obj_set_pos(gps_map_img_, 157, 25);  // Center 140px map in 142px card
        lv_obj_clear_flag(gps_map_img_, LV_OBJ_FLAG_HIDDEN);
    }
}

void SkyGuardDisplay::HideEnvCards() {
    if (env_container_) lv_obj_add_flag(env_container_, LV_OBJ_FLAG_HIDDEN);
}
void SkyGuardDisplay::ShowEnvCards() {
    if (env_container_) lv_obj_clear_flag(env_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::HideMoonCards() {
    if (moon_container_) lv_obj_add_flag(moon_container_, LV_OBJ_FLAG_HIDDEN);
}
void SkyGuardDisplay::ShowMoonCards() {
    if (moon_container_) lv_obj_clear_flag(moon_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::HideGpsCards() {
    if (gps_container_) lv_obj_add_flag(gps_container_, LV_OBJ_FLAG_HIDDEN);
}
void SkyGuardDisplay::ShowGpsCards() {
    if (gps_container_) lv_obj_clear_flag(gps_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::HideScopeCards() {
    if (scope_container_) lv_obj_add_flag(scope_container_, LV_OBJ_FLAG_HIDDEN);
}
void SkyGuardDisplay::ShowScopeCards() {
    if (scope_container_) lv_obj_clear_flag(scope_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::SetGpsMapPng(uint8_t* png_data, int png_len, float lat, float lon, int px_x, int px_y) {
    if (gps_map_png_data_) {
        free(gps_map_png_data_);
    }
    gps_map_png_data_ = png_data;
    gps_map_png_len_ = png_len;
    gps_map_valid_ = (png_data != nullptr && png_len > 0);
    gps_map_lat_ = lat;
    gps_map_lon_ = lon;

    if (gps_map_valid_ && gps_map_img_) {
        // Set up LVGL image descriptor pointing to raw PNG data
        memset(&gps_map_dsc_, 0, sizeof(gps_map_dsc_));
        gps_map_dsc_.header.magic = LV_IMAGE_HEADER_MAGIC;
        gps_map_dsc_.header.w = 256;
        gps_map_dsc_.header.h = 256;
        gps_map_dsc_.header.cf = LV_COLOR_FORMAT_RAW;
        gps_map_dsc_.data_size = png_len;
        gps_map_dsc_.data = png_data;

        // Calculate offset to center user's position in the 140x140 widget
        int off_x = px_x - GPS_MAP_W / 2;
        int off_y = px_y - GPS_MAP_H / 2;
        // Clamp so we don't go past tile edges
        if (off_x < 0) off_x = 0;
        if (off_y < 0) off_y = 0;
        if (off_x > 256 - GPS_MAP_W) off_x = 256 - GPS_MAP_W;
        if (off_y > 256 - GPS_MAP_H) off_y = 256 - GPS_MAP_H;

        lvgl_port_lock(0);
        lv_image_set_src(gps_map_img_, &gps_map_dsc_);
        lv_image_set_offset_x(gps_map_img_, -off_x);
        lv_image_set_offset_y(gps_map_img_, -off_y);
        lvgl_port_unlock();

        ESP_LOGI(TAG, "GPS map: px(%d,%d) offset(%d,%d) at (%.4f, %.4f)",
                 px_x, px_y, off_x, off_y, lat, lon);
    }
}

bool SkyGuardDisplay::NeedsGpsMapImage(float& lat, float& lon) const {
    if (!gps_map_built_) return false;
    // Need image if we don't have one yet, or position changed significantly
    float cur_lat = 0, cur_lon = 0;
    if (gps_ && gps_->HasFix()) {
        cur_lat = gps_->GetLatitude();
        cur_lon = gps_->GetLongitude();
    } else if (fallback_valid_) {
        cur_lat = fallback_lat_;
        cur_lon = fallback_lon_;
    } else {
        return false;  // No position at all
    }
    lat = cur_lat;
    lon = cur_lon;
    if (!gps_map_valid_) return true;
    // Re-fetch if position moved > ~1km (~0.01°)
    float dlat = cur_lat - gps_map_lat_;
    float dlon = cur_lon - gps_map_lon_;
    return (dlat * dlat + dlon * dlon) > 0.0001f;
}

// ==========================================================================
// PAGE NAVIGATION
// ==========================================================================

void SkyGuardDisplay::NextPage() {
    int next = (current_page_ + 1) % PAGE_COUNT;
    SetPage((SkyGuardPage)next);
}

void SkyGuardDisplay::PrevPage() {
    int prev = (current_page_ - 1 + PAGE_COUNT) % PAGE_COUNT;
    SetPage((SkyGuardPage)prev);
}

void SkyGuardDisplay::SetPage(SkyGuardPage page) {
    if (measuring_) return;  // Don't switch during countdown
    current_page_ = page;
    last_page_change_ms_ = (uint32_t)(esp_timer_get_time() / 1000);
    ClearDataArea();

    switch (page) {
        case PAGE_SQM:         BuildPageSqm(); break;
        case PAGE_SPECTRAL:    BuildPageSpectral(); break;
        case PAGE_MOON:        BuildPageMoon(); break;
        case PAGE_WEATHER:     BuildPageWeather(); break;
        case PAGE_WIND:        BuildPageWind(); break;
        case PAGE_AIRCRAFT:    BuildPageAircraft(); break;
        case PAGE_SATELLITES:  BuildPageSatellites(); break;
        case PAGE_METEOSAT:    BuildPageMeteosat(); break;
        case PAGE_TELESCOPE:   BuildPageTelescope(); break;
        case PAGE_CONTROL:     BuildPageControl(); break;
        case PAGE_QUICKCMD:    BuildPageQuickCmd(); break;
        case PAGE_ENVIRONMENT: BuildPageEnvironment(); break;
        case PAGE_GPS:         BuildPageGps(); break;
        case PAGE_MEASURE:     BuildPageMeasure(); break;
        default: break;
    }
    UpdatePageIndicator();
    Update();

    // Apply night/normal mode AFTER page is fully built+updated
    if (night_mode_) ApplyNightMode();
    else ApplyNormalMode();
}

void SkyGuardDisplay::ClearDataArea() {
    // Hide buttons
    if (measure_btn_) lv_obj_add_flag(measure_btn_, LV_OBJ_FLAG_HIDDEN);
    if (assist_btn_) lv_obj_add_flag(assist_btn_, LV_OBJ_FLAG_HIDDEN);
    if (night_btn_) lv_obj_add_flag(night_btn_, LV_OBJ_FLAG_HIDDEN);

    // Hide text lines and reset positions
    for (int i = 0; i < 8; i++) {
        lv_obj_add_flag(data_lines_[i], LV_OBJ_FLAG_HIDDEN);
        lv_label_set_text(data_lines_[i], "");
        lv_obj_set_pos(data_lines_[i], 0, 18 + i * 22);  // Default position
        lv_obj_set_style_text_color(data_lines_[i],
            night_mode_ ? SG_NIGHT_TEXT : SG_TEXT_COLOR, 0);
    }
    data_line_count_ = 0;

    // Hide all custom containers
    HideDashboard();
    HideSpectralBars();
    HideWeatherBars();
    DismissWeatherPopup();
    HideWindPage();
    HideRadar();
    HideSatDome();
    HideMoonCanvas();
    HideMeteosat();
    HideGpsMap();
    HideEnvCards();
    HideMoonCards();
    HideGpsCards();
    HideScopeCards();
    HideControlBtns();
    HideQuickCmdBtns();
    HideCountdown();
}

void SkyGuardDisplay::UpdatePageIndicator() {
    uint32_t cnt = lv_obj_get_child_count(page_indicator_);
    for (uint32_t i = 0; i < cnt; i++) {
        lv_obj_t* dot = lv_obj_get_child(page_indicator_, i);
        if (night_mode_) {
            lv_obj_set_style_bg_color(dot,
                (i == current_page_) ? SG_NIGHT_DOT_ACTIVE : SG_NIGHT_DOT_INACTIVE, 0);
        } else {
            lv_obj_set_style_bg_color(dot,
                (i == current_page_) ? SG_DOT_ACTIVE : SG_DOT_INACTIVE, 0);
        }
    }
}

// ==========================================================================
// PAGE BUILDERS
// ==========================================================================

// Set page-specific accent color for title icon + bar
static void SetPageAccent(lv_obj_t* icon, lv_obj_t* accent, lv_color_t color) {
    if (icon) lv_obj_set_style_bg_color(icon, color, 0);
    if (accent) lv_obj_set_style_bg_color(accent, color, 0);
}

void SkyGuardDisplay::BuildPageSqm() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x55FF55));  // Green — sky quality
    lv_label_set_text(data_title_, "SKYGUARD AI");
    BuildDashboard();
}

void SkyGuardDisplay::BuildDashboard() {
    if (!dash_built_) return;
    ShowDashboard();
}

void SkyGuardDisplay::BuildPageSpectral() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x7700EE));  // Violet — spectral
    lv_label_set_text(data_title_, "SPETTRO / LP");
    ShowSpectralBars();
}

void SkyGuardDisplay::BuildPageMoon() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0xCCCC88));  // Moon gold
    lv_label_set_text(data_title_, "LUNA & NOTTE");
    ShowMoonCanvas();
    ShowMoonCards();
}

void SkyGuardDisplay::BuildPageWeather() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x55AAFF));  // Sky blue — weather
    // Show location in title if available
    if (weather_ && weather_->HasData()) {
        ForecastData fd = weather_->GetForecast();
        if (fd.location[0] != '\0') {
            char title_buf[48];
            snprintf(title_buf, sizeof(title_buf), "PREVISIONI \xE2\x80\x94 %s", fd.location);
            lv_label_set_text(data_title_, title_buf);
        } else {
            lv_label_set_text(data_title_, "PREVISIONI");
        }
    } else {
        lv_label_set_text(data_title_, "PREVISIONI");
    }
    ShowWeatherBars();
}

void SkyGuardDisplay::BuildPageAircraft() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0xFF8800));  // Orange — radar
    lv_label_set_text(data_title_, "RADAR AEREI");
    if (radar_built_) {
        ShowRadar();
    }
}

void SkyGuardDisplay::BuildPageSatellites() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x00CCFF));  // Cyan — satellites
    lv_label_set_text(data_title_, "SATELLITI VISIBILI");
    if (sat_dome_built_) {
        ShowSatDome();
    }
}

void SkyGuardDisplay::BuildPageMeteosat() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x4488CC));  // Steel blue — satellite
    lv_label_set_text(data_title_, "SATELLITE IR");
    ShowMeteosat();
    // No data_lines — overlay labels on the image itself
}

void SkyGuardDisplay::BuildPageTelescope() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0xCC55FF));  // Purple — telescope
    // Dynamic title based on what's configured
    if (!alpaca_url_.empty() && !indi_url_.empty())
        lv_label_set_text(data_title_, "TELESCOPIO ASCOM+INDI");
    else if (!indi_url_.empty())
        lv_label_set_text(data_title_, "TELESCOPIO / INDI");
    else
        lv_label_set_text(data_title_, "TELESCOPIO / ASCOM");
    ShowScopeCards();
}

// ==========================================================================
// CONTROL PAGE — 8 touch buttons for telescope/INDI commands
// ==========================================================================

// Button definitions: label, command, param, group (0=mount, 1=phd2, 2=nina, 3=utility)
struct CtrlBtnDef {
    const char* label;
    const char* command;
    const char* param;
    int group;  // 0=Mount, 1=PHD2, 2=NINA, 3=Stellarium, 4=Utility
};
static const CtrlBtnDef kCtrlButtons[] = {
    // --- Mount (ASCOM/INDI) ---
    {"Track ON",    "tracking",     "on",       0},
    {"Track OFF",   "tracking",     "off",      0},
    {"Park",        "park",         "",         0},
    {"Unpark",      "unpark",       "",         0},
    {"Stop Slew",   "abortslew",    "",         0},
    {"Find Home",   "findhome",     "",         0},
    {"INDI Start",  "indi_start",   "",         0},
    {"INDI Stop",   "indi_stop",    "",         0},
    // --- PHD2 ---
    {"PHD Guide",   "phd2_guide",   "start",    1},
    {"PHD Stop",    "phd2_guide",   "stop",     1},
    {"PHD Dither",  "phd2_dither",  "",         1},
    {"PHD Calib",   "phd2_calib",   "",         1},
    // --- NINA ---
    {"NINA Start",  "nina_seq",     "start",    2},
    {"NINA Stop",   "nina_seq",     "stop",     2},
    {"NINA Pause",  "nina_seq",     "pause",    2},
    {"NINA Focus",  "nina_af",      "",         2},
    // --- Stellarium ---
    {"Stell Slew",  "stell_slew",   "",         3},
    {"Stell Sync",  "stell_sync",   "",         3},
    // --- Utility ---
    {"Dew ON",      "dew",          "on",       4},
    {"Dew OFF",     "dew",          "off",      4},
    {"Dew Auto",    "dew",          "auto",     4},
    {"SQM Misura",  "sqm_measure",  "",         4},
};
static constexpr int kCtrlButtonCount = sizeof(kCtrlButtons) / sizeof(kCtrlButtons[0]);

void SkyGuardDisplay::HideControlBtns() {
    if (ctrl_scroll_container_) lv_obj_add_flag(ctrl_scroll_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowControlBtns() {
    if (ctrl_scroll_container_) lv_obj_clear_flag(ctrl_scroll_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::BuildPageControl() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0xFF8800));  // Orange — controls
    lv_label_set_text(data_title_, "CONTROLLI");

    if (!ctrl_built_) {
        // Group colors: Mount=blue, PHD2=green, NINA=purple, Stellarium=cyan, Utility=amber
        static const lv_color_t kGroupColors[] = {
            lv_color_hex(0x113355),  // 0: Mount
            lv_color_hex(0x115533),  // 1: PHD2
            lv_color_hex(0x331155),  // 2: NINA
            lv_color_hex(0x115555),  // 3: Stellarium
            lv_color_hex(0x443300),  // 4: Utility
        };
        static const lv_color_t kGroupPressColors[] = {
            lv_color_hex(0x224466),
            lv_color_hex(0x228844),
            lv_color_hex(0x552288),
            lv_color_hex(0x228888),
            lv_color_hex(0x665500),
        };
        static const char* kGroupNames[] = {
            "MONTATURA", "PHD2", "N.I.N.A.", "STELLARIUM", "UTILITA"
        };

        // Scrollable container inside data_area
        ctrl_scroll_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(ctrl_scroll_container_);
        lv_obj_set_size(ctrl_scroll_container_, lv_pct(100), lv_pct(100));
        lv_obj_set_pos(ctrl_scroll_container_, 0, 18);  // below title
        lv_obj_set_style_bg_opa(ctrl_scroll_container_, LV_OPA_TRANSP, 0);
        lv_obj_set_flex_flow(ctrl_scroll_container_, LV_FLEX_FLOW_ROW_WRAP);
        lv_obj_set_flex_align(ctrl_scroll_container_, LV_FLEX_ALIGN_START,
                              LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
        lv_obj_set_style_pad_row(ctrl_scroll_container_, 3, 0);
        lv_obj_set_style_pad_column(ctrl_scroll_container_, 3, 0);
        lv_obj_set_style_pad_left(ctrl_scroll_container_, 2, 0);
        lv_obj_add_flag(ctrl_scroll_container_, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_scroll_dir(ctrl_scroll_container_, LV_DIR_VER);
        // Block horizontal gesture from triggering page swipe
        lv_obj_clear_flag(ctrl_scroll_container_, LV_OBJ_FLAG_GESTURE_BUBBLE);
        lv_obj_clear_flag(ctrl_scroll_container_, LV_OBJ_FLAG_SCROLL_CHAIN_HOR);

        int last_group = -1;
        ctrl_btn_count_ = 0;

        for (int i = 0; i < kCtrlButtonCount && ctrl_btn_count_ < CTRL_BTN_MAX; i++) {
            // Add group header label when group changes
            if (kCtrlButtons[i].group != last_group) {
                last_group = kCtrlButtons[i].group;
                lv_obj_t* header = lv_label_create(ctrl_scroll_container_);
                lv_obj_set_width(header, lv_pct(100));
                lv_obj_set_style_text_font(header, GetTinyFont(), 0);
                lv_obj_set_style_text_color(header, SG_DIM_COLOR, 0);
                lv_label_set_text(header, kGroupNames[last_group]);
                lv_obj_set_style_pad_top(header, (i == 0) ? 0 : 4, 0);
            }

            int grp = kCtrlButtons[i].group;
            lv_obj_t* btn = lv_btn_create(ctrl_scroll_container_);
            lv_obj_set_size(btn, 68, 30);
            lv_obj_set_style_bg_color(btn, kGroupColors[grp], 0);
            lv_obj_set_style_bg_color(btn, kGroupPressColors[grp], LV_STATE_PRESSED);
            lv_obj_set_style_radius(btn, 6, 0);

            lv_obj_t* lbl = lv_label_create(btn);
            lv_label_set_text(lbl, kCtrlButtons[i].label);
            lv_obj_set_style_text_font(lbl, GetTinyFont(), 0);
            lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
            lv_obj_center(lbl);

            // Event callback with button index
            struct CtrlBtnData {
                SkyGuardDisplay* disp;
                int idx;
            };
            auto* cbd = (CtrlBtnData*)heap_caps_malloc(sizeof(CtrlBtnData), MALLOC_CAP_DEFAULT);
            cbd->disp = this;
            cbd->idx = i;

            lv_obj_add_event_cb(btn, [](lv_event_t* e) {
                lv_event_stop_bubbling(e);
                auto* cbd = (CtrlBtnData*)lv_event_get_user_data(e);
                if (cbd && cbd->disp) {
                    cbd->disp->ShowConfirmDialog(cbd->idx);
                }
            }, LV_EVENT_CLICKED, cbd);

            ctrl_btns_[ctrl_btn_count_++] = btn;
        }
        ctrl_built_ = true;
    }
    ShowControlBtns();
}

void SkyGuardDisplay::ShowConfirmDialog(int btn_idx) {
    if (btn_idx < 0 || btn_idx >= kCtrlButtonCount) return;
    DismissConfirmDialog();  // Remove any existing

    confirm_pending_idx_ = btn_idx;

    // Dark semi-transparent backdrop on overlay
    confirm_box_ = lv_obj_create(overlay_);
    lv_obj_set_size(confirm_box_, 280, 120);
    lv_obj_center(confirm_box_);
    lv_obj_set_style_bg_color(confirm_box_, lv_color_hex(0x1a1a2e), 0);
    lv_obj_set_style_bg_opa(confirm_box_, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(confirm_box_, lv_color_hex(0x4488ff), 0);
    lv_obj_set_style_border_width(confirm_box_, 2, 0);
    lv_obj_set_style_radius(confirm_box_, 12, 0);
    lv_obj_set_style_pad_all(confirm_box_, 12, 0);
    lv_obj_remove_flag(confirm_box_, LV_OBJ_FLAG_SCROLLABLE);

    // Title: "Conferma"
    lv_obj_t* title = lv_label_create(confirm_box_);
    lv_label_set_text(title, "CONFERMA");
    lv_obj_set_style_text_color(title, lv_color_hex(0x4488ff), 0);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_14, 0);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 0);

    // Action label
    lv_obj_t* msg = lv_label_create(confirm_box_);
    char msg_buf[64];
    snprintf(msg_buf, sizeof(msg_buf), "%s?", kCtrlButtons[btn_idx].label);
    lv_label_set_text(msg, msg_buf);
    lv_obj_set_style_text_color(msg, lv_color_hex(0xe0e0e0), 0);
    lv_obj_set_style_text_font(msg, &lv_font_montserrat_14, 0);
    lv_obj_align(msg, LV_ALIGN_TOP_MID, 0, 22);

    // OK button
    lv_obj_t* btn_ok = lv_button_create(confirm_box_);
    lv_obj_set_size(btn_ok, 100, 36);
    lv_obj_align(btn_ok, LV_ALIGN_BOTTOM_LEFT, 10, -4);
    lv_obj_set_style_bg_color(btn_ok, lv_color_hex(0x238636), 0);
    lv_obj_set_style_radius(btn_ok, 6, 0);
    lv_obj_t* lbl_ok = lv_label_create(btn_ok);
    lv_label_set_text(lbl_ok, "OK");
    lv_obj_set_style_text_color(lbl_ok, lv_color_white(), 0);
    lv_obj_center(lbl_ok);

    lv_obj_add_event_cb(btn_ok, [](lv_event_t* e) {
        auto* disp = (SkyGuardDisplay*)lv_event_get_user_data(e);
        int idx = disp->confirm_pending_idx_;
        if (idx >= 0 && idx < kCtrlButtonCount && disp->ctrl_cb_) {
            ESP_LOGI("CTRL", "Confirmed button %d: %s %s", idx,
                     kCtrlButtons[idx].command, kCtrlButtons[idx].param);
            disp->ctrl_cb_(disp->ctrl_ctx_,
                           kCtrlButtons[idx].command,
                           kCtrlButtons[idx].param);
        }
        disp->DismissConfirmDialog();
    }, LV_EVENT_CLICKED, this);

    // Cancel button
    lv_obj_t* btn_cancel = lv_button_create(confirm_box_);
    lv_obj_set_size(btn_cancel, 100, 36);
    lv_obj_align(btn_cancel, LV_ALIGN_BOTTOM_RIGHT, -10, -4);
    lv_obj_set_style_bg_color(btn_cancel, lv_color_hex(0x6e4040), 0);
    lv_obj_set_style_radius(btn_cancel, 6, 0);
    lv_obj_t* lbl_cancel = lv_label_create(btn_cancel);
    lv_label_set_text(lbl_cancel, "Annulla");
    lv_obj_set_style_text_color(lbl_cancel, lv_color_white(), 0);
    lv_obj_center(lbl_cancel);

    lv_obj_add_event_cb(btn_cancel, [](lv_event_t* e) {
        auto* disp = (SkyGuardDisplay*)lv_event_get_user_data(e);
        disp->DismissConfirmDialog();
    }, LV_EVENT_CLICKED, this);
}

void SkyGuardDisplay::DismissConfirmDialog() {
    if (confirm_box_) {
        lv_obj_delete(confirm_box_);
        confirm_box_ = nullptr;
    }
    confirm_pending_idx_ = -1;
}

// ==========================================================================
// QUICK COMMANDS PAGE — AI chat buttons organized by category
// ==========================================================================

struct QCmdDef {
    const char* label;
    const char* text;     // Text sent via SendChatMessage
    int group;            // Category index
};

static const char* kQCmdGroupNames[] = {
    "CIELO", "AMBIENTE", "PIANIFICAZIONE", "ASTRONOMIA", "METEO",
    "IMAGING", "STORICO", "MONITORAGGIO", "PLANETARIO", "UTILITY", "PROFILO"
};

static const lv_color_t kQCmdGroupColors[] = {
    lv_color_hex(0x112244),  // 0: Cielo — deep blue
    lv_color_hex(0x113322),  // 1: Ambiente — green
    lv_color_hex(0x332211),  // 2: Pianificazione — amber
    lv_color_hex(0x221133),  // 3: Astronomia — purple
    lv_color_hex(0x112233),  // 4: Meteo — steel blue
    lv_color_hex(0x331122),  // 5: Imaging — magenta
    lv_color_hex(0x223311),  // 6: Storico — olive
    lv_color_hex(0x333311),  // 7: Monitoraggio — yellow-dark
    lv_color_hex(0x331133),  // 8: Planetario — dark magenta
    lv_color_hex(0x113333),  // 9: Utility — teal
    lv_color_hex(0x222233),  // 10: Profilo — slate
};

static const QCmdDef kQCmdButtons[] = {
    // 0: CIELO
    {"Qualita cielo",       "Com'e il cielo stasera?",              0},
    {"Leggi SQM",           "Leggi il sensore SQM",                 0},
    {"Analisi spettrale",   "Analisi spettrale inquinamento",       0},
    {"Safety check",        "Safety check sessione",                0},
    // 1: AMBIENTE
    {"Temp e umidita",      "Temperatura e umidita",                1},
    {"Rischio condensa",    "Rischio condensa e punto rugiada",     1},
    {"Posizione GPS",       "Posizione GPS attuale",                1},
    // 2: PIANIFICAZIONE
    {"Cosa fotografo?",     "Cosa fotografo stasera?",              2},
    {"Pianifica serata",    "Pianifica la serata di imaging",       2},
    {"Quanto al buio?",     "Quanto manca al buio astronomico?",    2},
    {"Timing flat",         "Quando fare i flat frame?",            2},
    {"Quale setup?",        "Quale setup uso stasera?",             2},
    // 3: ASTRONOMIA
    {"Stato luna",          "Stato della luna stasera",             3},
    {"Satelliti in zona",   "Satelliti visibili in zona",           3},
    {"Aerei in zona",       "Aerei in zona adesso",                3},
    {"Cos'e quella luce?",  "Che cos'e quella luce nel cielo?",    3},
    {"Dove Polaris?",       "Dove metto Polaris nel polare?",      3},
    // 4: METEO
    {"Meteo stasera",       "Previsioni meteo per stasera",        4},
    {"Previsioni seeing",   "Previsioni seeing astronomico",       4},
    {"Notte migliore?",     "Notte migliore questa settimana",     4},
    {"Meteo Italia",        "Previsioni meteo Italia",             4},
    // 5: IMAGING
    {"Quanti frame?",       "Quanti frame servono per lo stacking?",5},
    {"Quanti dark?",        "Quanti dark frame devo fare?",        5},
    {"Come sono i frame?",  "Come sono i frame catturati?",        5},
    // 6: STORICO
    {"Ultima settimana",    "Storico ultima settimana",            6},
    {"Trend LP",            "Trend inquinamento luminoso",         6},
    {"Stato connessione",   "Stato connessione WiFi e latenza",   6},
    // 7: MONITORAGGIO
    {"Attiva allarmi",      "Attiva allarmi proattivi",            7},
    {"Disattiva allarmi",   "Disattiva allarmi",                   7},
    {"Attiva monitoring",   "Attiva monitoraggio condizioni",      7},
    {"Stop monitoring",     "Disattiva monitoraggio condizioni",   7},
    // 8: PLANETARIO
    {"Giove",               "Sessione planetaria Giove",           8},
    {"Saturno",             "Sessione planetaria Saturno",         8},
    {"Luna HD",             "Sessione planetaria Luna",            8},
    {"Solare",              "Sessione imaging solare",             8},
    {"Guida planetario",    "Guida imaging planetario",            8},
    // 9: UTILITY
    {"Metti la radio",      "Metti la radio",                      9},
    {"Ferma la radio",      "Ferma la radio",                      9},
    {"Che ore sono?",       "Che ore sono?",                       9},
    {"Cosa sai fare?",      "Cosa sai fare?",                      9},
    // 10: PROFILO
    {"Mio profilo",         "Il mio profilo AstroBin",             10},
    {"Strumentazione",      "La mia strumentazione",               10},
};
static constexpr int kQCmdButtonCount = sizeof(kQCmdButtons) / sizeof(kQCmdButtons[0]);

void SkyGuardDisplay::HideQuickCmdBtns() {
    if (qcmd_scroll_container_) lv_obj_add_flag(qcmd_scroll_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowQuickCmdBtns() {
    if (qcmd_scroll_container_) lv_obj_clear_flag(qcmd_scroll_container_, LV_OBJ_FLAG_HIDDEN);
}

// Callback data for quick command buttons
struct QCmdBtnData {
    const char* text;
};

void SkyGuardDisplay::BuildPageQuickCmd() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x55FF88));  // Green — AI commands
    lv_label_set_text(data_title_, "COMANDI AI");

    if (!qcmd_built_) {
        // Scrollable container
        qcmd_scroll_container_ = lv_obj_create(data_area_);
        lv_obj_remove_style_all(qcmd_scroll_container_);
        lv_obj_set_size(qcmd_scroll_container_, lv_pct(100), lv_pct(100));
        lv_obj_set_pos(qcmd_scroll_container_, 0, 18);
        lv_obj_set_style_bg_opa(qcmd_scroll_container_, LV_OPA_TRANSP, 0);
        lv_obj_set_flex_flow(qcmd_scroll_container_, LV_FLEX_FLOW_ROW_WRAP);
        lv_obj_set_flex_align(qcmd_scroll_container_, LV_FLEX_ALIGN_START,
                              LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
        lv_obj_set_style_pad_row(qcmd_scroll_container_, 3, 0);
        lv_obj_set_style_pad_column(qcmd_scroll_container_, 3, 0);
        lv_obj_set_style_pad_left(qcmd_scroll_container_, 2, 0);
        lv_obj_add_flag(qcmd_scroll_container_, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_scroll_dir(qcmd_scroll_container_, LV_DIR_VER);
        lv_obj_clear_flag(qcmd_scroll_container_, LV_OBJ_FLAG_GESTURE_BUBBLE);
        lv_obj_clear_flag(qcmd_scroll_container_, LV_OBJ_FLAG_SCROLL_CHAIN_HOR);

        int last_group = -1;
        qcmd_btn_count_ = 0;

        for (int i = 0; i < kQCmdButtonCount && qcmd_btn_count_ < QCMD_BTN_MAX; i++) {
            // Group header
            if (kQCmdButtons[i].group != last_group) {
                last_group = kQCmdButtons[i].group;
                lv_obj_t* hdr = lv_label_create(qcmd_scroll_container_);
                lv_obj_set_width(hdr, 300);
                lv_obj_set_style_text_font(hdr, GetTinyFont(), 0);
                lv_obj_set_style_text_color(hdr, lv_color_hex(0x88AACC), 0);
                lv_label_set_text(hdr, kQCmdGroupNames[last_group]);
                lv_obj_set_style_pad_top(hdr, last_group == 0 ? 0 : 4, 0);
            }

            int grp = kQCmdButtons[i].group;
            lv_color_t bg_color = (grp < 11) ? kQCmdGroupColors[grp] : lv_color_hex(0x222233);

            lv_obj_t* btn = lv_button_create(qcmd_scroll_container_);
            lv_obj_set_size(btn, 148, 26);
            lv_obj_set_style_bg_color(btn, bg_color, 0);
            lv_obj_set_style_bg_color(btn, lv_color_hex(0x334455), LV_STATE_PRESSED);
            lv_obj_set_style_radius(btn, 6, 0);
            lv_obj_set_style_border_width(btn, 1, 0);
            lv_obj_set_style_border_color(btn, lv_color_hex(0x3A3A5A), 0);
            lv_obj_set_style_pad_all(btn, 2, 0);

            lv_obj_t* lbl = lv_label_create(btn);
            lv_obj_set_style_text_font(lbl, GetTinyFont(), 0);
            lv_obj_set_style_text_color(lbl, lv_color_hex(0xCCDDEE), 0);
            lv_label_set_text(lbl, kQCmdButtons[i].label);
            lv_obj_center(lbl);

            // Store text pointer in user_data for click handler
            auto* cbd = (QCmdBtnData*)lv_malloc(sizeof(QCmdBtnData));
            cbd->text = kQCmdButtons[i].text;

            lv_obj_add_event_cb(btn, [](lv_event_t* e) {
                lv_event_stop_bubbling(e);
                auto* data = (QCmdBtnData*)lv_event_get_user_data(e);
                if (data && data->text) {
                    ESP_LOGI("SkyGuardUI", "Quick cmd: %s", data->text);
                    Application::GetInstance().SendChatMessage(data->text);
                }
            }, LV_EVENT_CLICKED, cbd);

            qcmd_btns_[qcmd_btn_count_++] = btn;
        }

        qcmd_built_ = true;
    }
    ShowQuickCmdBtns();
}

void SkyGuardDisplay::BuildPageEnvironment() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0xFF5544));  // Red-orange — temp
    lv_label_set_text(data_title_, "AMBIENTE");
    ShowEnvCards();
}

void SkyGuardDisplay::BuildPageGps() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x00DD66));  // Green — GPS
    lv_label_set_text(data_title_, "GPS / POSIZIONE");
    ShowGpsCards();
    ShowGpsMap();
}

void SkyGuardDisplay::BuildPageMeasure() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0xFFBB00));  // Amber — commands
    lv_label_set_text(data_title_, "COMANDI");

    if (!measure_btn_) {
        measure_btn_ = lv_btn_create(data_area_);
        lv_obj_set_size(measure_btn_, 260, 40);
        lv_obj_set_pos(measure_btn_, 20, 28);
        lv_obj_set_style_bg_color(measure_btn_, SG_BTN_COLOR, 0);
        lv_obj_set_style_bg_color(measure_btn_, SG_BTN_PRESS_COLOR, LV_STATE_PRESSED);
        lv_obj_set_style_radius(measure_btn_, 8, 0);

        lv_obj_t* lbl = lv_label_create(measure_btn_);
        lv_label_set_text(lbl, "MISURA SQM");
        lv_obj_set_style_text_font(lbl, GetSmallFont(), 0);
        lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
        lv_obj_center(lbl);

        lv_obj_add_event_cb(measure_btn_, [](lv_event_t* e) {
            ESP_LOGI("BTN", ">>> MEASURE btn clicked <<<");
            lv_event_stop_bubbling(e);
            ((SkyGuardDisplay*)lv_event_get_user_data(e))->TriggerMeasurement();
        }, LV_EVENT_CLICKED, this);
    }
    lv_obj_clear_flag(measure_btn_, LV_OBJ_FLAG_HIDDEN);

    if (!assist_btn_) {
        assist_btn_ = lv_btn_create(data_area_);
        lv_obj_set_size(assist_btn_, 260, 40);
        lv_obj_set_pos(assist_btn_, 20, 78);
        lv_obj_set_style_bg_color(assist_btn_, lv_color_hex(0x113355), 0);
        lv_obj_set_style_bg_color(assist_btn_, lv_color_hex(0x224466), LV_STATE_PRESSED);
        lv_obj_set_style_radius(assist_btn_, 8, 0);

        lv_obj_t* lbl = lv_label_create(assist_btn_);
        lv_label_set_text(lbl, "Chiedi a Sofia");
        lv_obj_set_style_text_font(lbl, GetSmallFont(), 0);
        lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
        lv_obj_center(lbl);

        lv_obj_add_event_cb(assist_btn_, [](lv_event_t* e) {
            ESP_LOGI("BTN", ">>> ASSIST btn clicked <<<");
            lv_event_stop_bubbling(e);
            ((SkyGuardDisplay*)lv_event_get_user_data(e))->TriggerAssistant();
        }, LV_EVENT_CLICKED, this);
    }
    lv_obj_clear_flag(assist_btn_, LV_OBJ_FLAG_HIDDEN);

    if (!night_btn_) {
        night_btn_ = lv_btn_create(data_area_);
        lv_obj_set_size(night_btn_, 260, 40);
        lv_obj_set_pos(night_btn_, 20, 128);
        lv_obj_set_style_bg_color(night_btn_, lv_color_hex(0x332200), 0);
        lv_obj_set_style_bg_color(night_btn_, lv_color_hex(0x443300), LV_STATE_PRESSED);
        lv_obj_set_style_radius(night_btn_, 8, 0);

        lv_obj_t* lbl = lv_label_create(night_btn_);
        lv_label_set_text(lbl, night_mode_ ? "Modo Normale" : "Modo Notte");
        lv_obj_set_style_text_font(lbl, GetSmallFont(), 0);
        lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
        lv_obj_center(lbl);

        lv_obj_add_event_cb(night_btn_, [](lv_event_t* e) {
            ESP_LOGI("BTN", ">>> NIGHT btn clicked <<<");
            lv_event_stop_bubbling(e);
            ((SkyGuardDisplay*)lv_event_get_user_data(e))->ToggleNightMode();
        }, LV_EVENT_CLICKED, this);
    } else {
        lv_obj_t* lbl = lv_obj_get_child(night_btn_, 0);
        if (lbl) lv_label_set_text(lbl, night_mode_ ? "Modo Normale" : "Modo Notte");
    }
    lv_obj_clear_flag(night_btn_, LV_OBJ_FLAG_HIDDEN);
}

// ==========================================================================
// UPDATE — Refresh data on current page
// ==========================================================================

void SkyGuardDisplay::Update() {
    if (!overlay_) return;

    // Skip page updates while boot loader is showing
    if (boot_loader_visible_) return;

    // Auto-scroll pages (skip interactive pages: commands, quick cmd, control)
    if (auto_scroll_enabled_ && visible_ && !measuring_ &&
        current_page_ != PAGE_MEASURE && current_page_ != PAGE_QUICKCMD && current_page_ != PAGE_CONTROL) {
        uint32_t now = (uint32_t)(esp_timer_get_time() / 1000);
        if (last_page_change_ms_ == 0) {
            last_page_change_ms_ = now;
        } else if ((now - last_page_change_ms_) >=
                   (current_page_ == PAGE_SQM ? auto_scroll_interval_ms_ * 2 : auto_scroll_interval_ms_)) {
            last_page_change_ms_ = now;
            int next = (current_page_ + 1);
            // Skip interactive pages in auto-scroll
            while (next == PAGE_CONTROL || next == PAGE_QUICKCMD || next >= PAGE_MEASURE) {
                if (next >= PAGE_MEASURE) { next = PAGE_SQM; break; }
                next++;
            }
            if (!lvgl_port_lock(100)) return;
            SetPage((SkyGuardPage)next);
            lvgl_port_unlock();
            return;
        }
    }

    if (!lvgl_port_lock(100)) return;

    // === NUCLEAR dark mode: force on EVERY tick ===
    lv_obj_t* screen = lv_screen_active();
    if (screen) {
        lv_obj_set_style_bg_color(screen, SG_BG_COLOR, 0);
        lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, 0);
        lv_obj_set_style_text_color(screen, SG_TEXT_COLOR, 0);

        lv_obj_t* container = lv_obj_get_child(screen, 0);
        if (container) {
            lv_obj_set_style_bg_color(container, SG_BG_COLOR, 0);
            lv_obj_set_style_bg_opa(container, LV_OPA_COVER, 0);
            lv_obj_set_style_bg_image_src(container, nullptr, 0);
            lv_obj_set_style_text_color(container, SG_TEXT_COLOR, 0);
        }

        lv_obj_t* top_bar = lv_obj_get_child(screen, 3);
        if (top_bar) {
            lv_obj_set_style_bg_color(top_bar, SG_BG_COLOR, 0);
            lv_obj_set_style_text_color(top_bar, SG_TEXT_COLOR, 0);
        }
    }

    switch (current_page_) {
        case PAGE_SQM:         UpdatePageSqm(); break;
        case PAGE_SPECTRAL:    UpdatePageSpectral(); break;
        case PAGE_MOON:        UpdatePageMoon(); break;
        case PAGE_WEATHER:     UpdatePageWeather(); break;
        case PAGE_WIND:        UpdatePageWind(); break;
        case PAGE_AIRCRAFT:    UpdatePageAircraft(); break;
        case PAGE_SATELLITES:  UpdatePageSatellites(); break;
        case PAGE_METEOSAT:    UpdatePageMeteosat(); break;
        case PAGE_TELESCOPE:   UpdatePageTelescope(); break;
        case PAGE_ENVIRONMENT: UpdatePageEnvironment(); break;
        case PAGE_GPS:         UpdatePageGps(); break;
        case PAGE_MEASURE:     break;
        default: break;
    }

    lvgl_port_unlock();
}

// ==========================================================================
// UPDATE HELPERS
// ==========================================================================

// Build compact location string for page footers (e.g. "GPS Asti" or "44.90N 8.17E")
static void BuildLocationString(char* buf, int buflen,
                                const char* location_name, SkyGuardWeather* weather,
                                float fallback_lat, float fallback_lon, bool fallback_valid) {
    if (location_name && location_name[0]) {
        snprintf(buf, buflen, LV_SYMBOL_GPS " %s", location_name);
    } else if (weather && weather->HasData()) {
        ForecastData fc = weather->GetForecast();
        if (fc.location[0]) {
            snprintf(buf, buflen, LV_SYMBOL_GPS " %s", fc.location);
        } else if (fallback_valid) {
            snprintf(buf, buflen, LV_SYMBOL_GPS " %.2f%c %.2f%c",
                fabsf(fallback_lat), fallback_lat >= 0 ? 'N' : 'S',
                fabsf(fallback_lon), fallback_lon >= 0 ? 'E' : 'W');
        } else {
            snprintf(buf, buflen, LV_SYMBOL_GPS " --");
        }
    } else if (fallback_valid) {
        snprintf(buf, buflen, LV_SYMBOL_GPS " %.2f%c %.2f%c",
            fabsf(fallback_lat), fallback_lat >= 0 ? 'N' : 'S',
            fabsf(fallback_lon), fallback_lon >= 0 ? 'E' : 'W');
    } else {
        snprintf(buf, buflen, LV_SYMBOL_GPS " --");
    }
}

void SkyGuardDisplay::UpdatePageSqm() {
    UpdateDashboard();
}

void SkyGuardDisplay::UpdateDashboard() {
    if (!dash_built_) return;
    char buf[80];

    // === LEFT CARD: SQM arc gauge ===
    if (tsl2591_) {
        float mpsas = tsl2591_->GetMpsas();
        uint8_t bortle = tsl2591_->GetBortle();

        snprintf(buf, sizeof(buf), "%.2f", mpsas);
        lv_label_set_text(sqm_big_value_, buf);

        // Color by Bortle class (arc + bar only, text stays white for contrast)
        lv_color_t qc = (bortle <= 3) ? SG_GOOD_COLOR :
                         (bortle <= 5) ? SG_WARN_COLOR : SG_BAD_COLOR;
        lv_obj_set_style_text_color(sqm_big_value_, lv_color_white(), 0);

        // Arc gauge: map MPSAS 10..22 → 0..100%
        int arc_val = (int)((mpsas - 10.0f) / 12.0f * 100.0f);
        if (arc_val < 0) arc_val = 0;
        if (arc_val > 100) arc_val = 100;
        lv_arc_set_value(sqm_arc_, arc_val);
        lv_obj_set_style_arc_color(sqm_arc_, qc, LV_PART_INDICATOR);

        // Bortle bar width proportional to quality
        int bar_w = (bortle <= 2) ? 100 : (bortle <= 4) ? 75 : (bortle <= 6) ? 50 : 30;
        lv_obj_set_width(sqm_bortle_bar_, bar_w);
        lv_obj_set_style_bg_color(sqm_bortle_bar_, qc, 0);

        // Quality text
        snprintf(buf, sizeof(buf), "Bortle %d - %s", bortle, tsl2591_->GetQuality());
        lv_label_set_text(sqm_quality_label_, buf);
        lv_obj_set_style_text_color(sqm_quality_label_, qc, 0);
    } else {
        lv_label_set_text(sqm_big_value_, "--.-");
        lv_obj_set_style_text_color(sqm_big_value_, SG_DIM_COLOR, 0);
        lv_arc_set_value(sqm_arc_, 0);
        lv_label_set_text(sqm_quality_label_, "Sensore N/A");
        lv_obj_set_style_text_color(sqm_quality_label_, SG_DIM_COLOR, 0);
    }

    // === RIGHT CARD: 8 info rows ===

    // Row 0: Moon illumination % + rise/set
    {
        float lat, lon;
        if (HasPosition(lat, lon)) {
            double jd = GetCurrentJD();
            double jd0 = GetCurrentJD0();
            auto moon = AstroCalc::moonPhase(jd);
            auto mrs = AstroCalc::moonRiseSet(jd0, lat, lon);
            auto lpos = AstroCalc::lunarPosition(jd, lat, lon);
            // Show illumination + altitude (compact)
            if (lpos.altitude > 0) {
                snprintf(buf, sizeof(buf), "%.0f%% +%.0f\xC2\xB0", moon.illumination, lpos.altitude);
            } else {
                snprintf(buf, sizeof(buf), "%.0f%% sotto", moon.illumination);
            }
            lv_label_set_text(dash_val_[0], buf);
            lv_color_t mc = (moon.illumination < 30) ? SG_GOOD_COLOR :
                            (moon.illumination < 60) ? SG_WARN_COLOR : SG_BAD_COLOR;
            lv_obj_set_style_text_color(dash_val_[0], mc, 0);
        } else {
            lv_label_set_text(dash_val_[0], "--");
            lv_obj_set_style_text_color(dash_val_[0], SG_DIM_COLOR, 0);
        }
    }

    // Row 1: Temperature
    if (aht20_) {
        float t = aht20_->GetTemperature() + temp_offset_;
        snprintf(buf, sizeof(buf), "%.1f\xC2\xB0""C", t);
        lv_label_set_text(dash_val_[1], buf);
        lv_obj_set_style_text_color(dash_val_[1], SG_TEXT_COLOR, 0);
    } else {
        lv_label_set_text(dash_val_[1], "--");
        lv_obj_set_style_text_color(dash_val_[1], SG_DIM_COLOR, 0);
    }

    // Row 2: Humidity
    if (aht20_) {
        float h = aht20_->GetHumidity() + hum_offset_;
        snprintf(buf, sizeof(buf), "%d%%", (int)h);
        lv_label_set_text(dash_val_[2], buf);
        lv_color_t hc = (h > 80) ? SG_BAD_COLOR : (h > 60) ? SG_WARN_COLOR : SG_GOOD_COLOR;
        lv_obj_set_style_text_color(dash_val_[2], hc, 0);
    } else {
        lv_label_set_text(dash_val_[2], "--");
        lv_obj_set_style_text_color(dash_val_[2], SG_DIM_COLOR, 0);
    }

    // Row 3: Clouds %
    // Row 4: Wind speed
    // Row 5: Seeing estimate
    if (weather_ && weather_->HasData()) {
        ForecastData fc = weather_->GetForecast();
        if (fc.count > 0) {
            auto& e = fc.entries[0];

            // Clouds
            snprintf(buf, sizeof(buf), "%d%%", e.clouds);
            lv_label_set_text(dash_val_[3], buf);
            lv_color_t cc = (e.clouds > 60) ? SG_BAD_COLOR :
                            (e.clouds > 30) ? SG_WARN_COLOR : SG_GOOD_COLOR;
            lv_obj_set_style_text_color(dash_val_[3], cc, 0);

            // Wind
            snprintf(buf, sizeof(buf), "%.0f m/s", e.wind_speed);
            lv_label_set_text(dash_val_[4], buf);
            lv_color_t wc = (e.wind_speed > 10) ? SG_BAD_COLOR :
                            (e.wind_speed > 5) ? SG_WARN_COLOR : SG_GOOD_COLOR;
            lv_obj_set_style_text_color(dash_val_[4], wc, 0);

            // Seeing estimate
            float seeing = 2.0f + e.wind_speed * 0.15f;
            if (e.humidity > 70) seeing += (e.humidity - 70) * 0.03f;
            if (e.clouds > 50) seeing += (e.clouds - 50) * 0.02f;
            if (seeing > 5.0f) seeing = 5.0f;
            snprintf(buf, sizeof(buf), "%.1f\"", seeing);
            lv_label_set_text(dash_val_[5], buf);
            lv_color_t sc = (seeing > 3.5f) ? SG_BAD_COLOR :
                            (seeing > 2.5f) ? SG_WARN_COLOR : SG_GOOD_COLOR;
            lv_obj_set_style_text_color(dash_val_[5], sc, 0);
        }
    } else {
        lv_label_set_text(dash_val_[3], "--");
        lv_label_set_text(dash_val_[4], "--");
        lv_label_set_text(dash_val_[5], "--");
        lv_obj_set_style_text_color(dash_val_[3], SG_DIM_COLOR, 0);
        lv_obj_set_style_text_color(dash_val_[4], SG_DIM_COLOR, 0);
        lv_obj_set_style_text_color(dash_val_[5], SG_DIM_COLOR, 0);
    }

    // Row 6: Aircraft count
    {
        int n_aircraft = 0;
        if (sky_tracker_ && sky_tracker_->HasFlights()) {
            FlightData fl = sky_tracker_->GetFlights();
            n_aircraft = fl.count;
        }
        snprintf(buf, sizeof(buf), "%d", n_aircraft);
        lv_label_set_text(dash_val_[6], buf);
        lv_obj_set_style_text_color(dash_val_[6], SG_TEXT_COLOR, 0);
    }

    // Row 7: Satellite passes count
    {
        int n_sats = 0;
        if (sky_tracker_ && sky_tracker_->HasSatellites()) {
            SatelliteData sd = sky_tracker_->GetSatellites();
            n_sats = sd.count;
        }
        snprintf(buf, sizeof(buf), "%d", n_sats);
        lv_label_set_text(dash_val_[7], buf);
        lv_obj_set_style_text_color(dash_val_[7], SG_TEXT_COLOR, 0);
    }

    // === MINI SPECTRUM BARS (left card) ===
    if (as7341_) {
        auto& r = as7341_->GetReading();
        uint16_t vals[8] = { r.f1_415nm, r.f2_445nm, r.f3_480nm, r.f4_515nm,
                             r.f5_555nm, r.f6_590nm, r.f7_630nm, r.f8_680nm };
        uint16_t max_val = 1;
        for (int i = 0; i < 8; i++) {
            if (vals[i] > max_val) max_val = vals[i];
        }
        int spec_y = 122;
        int spec_h = 28;
        for (int i = 0; i < 8; i++) {
            int h = (int)((float)vals[i] / max_val * spec_h);
            if (h < 2) h = 2;
            lv_obj_set_height(dash_spec_bar_[i], h);
            lv_obj_set_y(dash_spec_bar_[i], spec_y + spec_h - h);
        }
    }

    // === BOTTOM BAR: Location ===
    // Priority: reverse geocoded name > OWM city > GPS coords
    if (location_name_[0]) {
        snprintf(buf, sizeof(buf), LV_SYMBOL_GPS " %s", location_name_);
        lv_label_set_text(dash_location_, buf);
    } else if (weather_ && weather_->HasData()) {
        ForecastData fc = weather_->GetForecast();
        if (fc.location[0]) {
            snprintf(buf, sizeof(buf), LV_SYMBOL_GPS " %s", fc.location);
            lv_label_set_text(dash_location_, buf);
        } else {
            lv_label_set_text(dash_location_, LV_SYMBOL_GPS " --");
        }
    } else {
        float lat, lon;
        if (HasPosition(lat, lon)) {
            snprintf(buf, sizeof(buf), LV_SYMBOL_GPS " %.3f%c %.3f%c",
                fabsf(lat), lat >= 0 ? 'N' : 'S',
                fabsf(lon), lon >= 0 ? 'E' : 'W');
            lv_label_set_text(dash_location_, buf);
        } else {
            lv_label_set_text(dash_location_, LV_SYMBOL_GPS " GPS...");
        }
    }

    // === SENSOR STATUS ICONS ===
    if (dash_sensor_status_) {
        bool gps_ok = (gps_ && gps_->HasFix());

        snprintf(buf, sizeof(buf), "%s SQM %s SP %s TH %s GPS",
                 tsl2591_ ? LV_SYMBOL_OK : LV_SYMBOL_CLOSE,
                 as7341_  ? LV_SYMBOL_OK : LV_SYMBOL_CLOSE,
                 aht20_   ? LV_SYMBOL_OK : LV_SYMBOL_CLOSE,
                 gps_ok   ? LV_SYMBOL_OK : LV_SYMBOL_CLOSE);
        lv_label_set_text(dash_sensor_status_, buf);
    }
}

void SkyGuardDisplay::UpdatePageSpectral() {
    if (!spectral_built_) return;

    if (!as7341_) {
        for (int i = 0; i < 8; i++) {
            lv_label_set_text(spectral_values_[i], "--");
            lv_obj_set_size(spectral_bars_[i], 18, 4);
        }
        lv_label_set_text(spectral_lp_source_, "Sensore N/A");
        lv_label_set_text(spectral_ratios_, "Blu:-- Na:--");
        lv_label_set_text(spectral_sqi_value_, "--");
        lv_label_set_text(spectral_lp_verdict_, "--");
        lv_arc_set_value(spectral_sqi_arc_, 0);
        return;
    }

    auto& r = as7341_->GetReading();
    uint16_t values[8] = {
        r.f1_415nm, r.f2_445nm, r.f3_480nm, r.f4_515nm,
        r.f5_555nm, r.f6_590nm, r.f7_630nm, r.f8_680nm
    };

    uint16_t max_val = 1;
    uint32_t total = 0;
    for (int i = 0; i < 8; i++) {
        if (values[i] > max_val) max_val = values[i];
        total += values[i];
    }

    // If all channels are essentially zero, sensor has no valid data
    if (total < 10) {
        for (int i = 0; i < 8; i++) {
            lv_label_set_text(spectral_values_[i], "0");
            lv_obj_set_size(spectral_bars_[i], 18, 4);
        }
        lv_label_set_text(spectral_ratios_, "Blu:-- Na:--");
        lv_label_set_text(spectral_sqi_value_, "--");
        lv_label_set_text(spectral_lp_source_, "In attesa dati...");
        lv_obj_set_style_text_color(spectral_lp_source_, SG_DIM_COLOR, 0);
        lv_label_set_text(spectral_lp_verdict_, "Misura necessaria");
        lv_obj_set_style_text_color(spectral_lp_verdict_, SG_DIM_COLOR, 0);
        lv_arc_set_value(spectral_sqi_arc_, 0);
        lv_obj_set_style_arc_color(spectral_sqi_arc_, SG_DIM_COLOR, LV_PART_INDICATOR);
        return;
    }

    // ── Left card: spectral bars ──
    int bar_w = 18;
    int bar_spacing = 4;
    int bar_start_x = (190 - (8 * bar_w + 7 * bar_spacing)) / 2;
    int bar_max_h = 100;
    int bar_top_y = 10;

    for (int i = 0; i < 8; i++) {
        int x = bar_start_x + i * (bar_w + bar_spacing);
        int bar_h = (max_val > 0) ? (int)((float)values[i] / max_val * bar_max_h) : 4;
        if (bar_h < 4) bar_h = 4;

        lv_obj_set_size(spectral_bars_[i], bar_w, bar_h);
        lv_obj_set_pos(spectral_bars_[i], x, bar_top_y + bar_max_h - bar_h);

        char buf[8];
        snprintf(buf, sizeof(buf), "%u", values[i]);
        lv_label_set_text(spectral_values_[i], buf);
        lv_obj_set_pos(spectral_values_[i], x - 3, bar_top_y + bar_max_h - bar_h - 14);
    }

    // Ratios at bottom of left card
    char lp_buf[48];
    snprintf(lp_buf, sizeof(lp_buf), "Blu:%.2f  Na:%.2f",
        as7341_->GetBlueRatio(), as7341_->GetSodiumRatio());
    lv_label_set_text(spectral_ratios_, lp_buf);

    // ── Right card: LP analysis ──
    uint8_t sqi = as7341_->GetSpectralQuality();
    LpSourceType lp = as7341_->GetLpSource();

    // SQI arc gauge
    lv_arc_set_value(spectral_sqi_arc_, sqi);
    lv_color_t sqi_color = (sqi >= 70) ? SG_GOOD_COLOR : (sqi >= 40) ? SG_WARN_COLOR : SG_BAD_COLOR;
    lv_obj_set_style_arc_color(spectral_sqi_arc_, sqi_color, LV_PART_INDICATOR);

    // SQI value text
    snprintf(lp_buf, sizeof(lp_buf), "%d%%", sqi);
    lv_label_set_text(spectral_sqi_value_, lp_buf);
    lv_obj_set_style_text_color(spectral_sqi_value_, sqi_color, 0);

    // Context-aware labels based on ambient light level
    float mpsas_check = tsl2591_ ? tsl2591_->GetMpsas() : 0;
    lv_color_t lp_color;
    const char* verdict;

    if (mpsas_check < 16.0f) {
        // === DAYTIME / BRIGHT — atmospheric analysis mode ===
        lv_label_set_text(spectral_sqi_label_, "Trasparenza");
        // LP source → sky condition (Rayleigh scattering analysis)
        lv_label_set_text(spectral_lp_source_, as7341_->GetSkyCondition());
        int clarity = as7341_->GetAtmosphericClarity();
        lp_color = (clarity >= 60) ? SG_GOOD_COLOR : (clarity >= 30) ? SG_WARN_COLOR : SG_BAD_COLOR;
        lv_obj_set_style_text_color(spectral_lp_source_, lp_color, 0);

        // SQI arc → atmospheric clarity %
        lv_arc_set_value(spectral_sqi_arc_, clarity);
        lv_obj_set_style_arc_color(spectral_sqi_arc_, lp_color, LV_PART_INDICATOR);
        snprintf(lp_buf, sizeof(lp_buf), "%d%%", clarity);
        lv_label_set_text(spectral_sqi_value_, lp_buf);
        lv_obj_set_style_text_color(spectral_sqi_value_, lp_color, 0);

        // Verdict → solar photography conditions
        verdict = as7341_->GetSolarPhotoVerdict();
        snprintf(lp_buf, sizeof(lp_buf), "Solare: %s", verdict);
        lv_label_set_text(spectral_lp_verdict_, lp_buf);
        sqi_color = (clarity >= 60) ? SG_GOOD_COLOR : (clarity >= 30) ? SG_WARN_COLOR : SG_BAD_COLOR;
    } else {
        // === NIGHTTIME — light pollution analysis mode ===
        lv_label_set_text(spectral_sqi_label_, "Qualita Cielo");
        // LP source label
        snprintf(lp_buf, sizeof(lp_buf), "%s", as7341_->GetLpSourceName());
        lv_label_set_text(spectral_lp_source_, lp_buf);
        lp_color = SG_GOOD_COLOR;
        if (lp == LP_LED) lp_color = SG_WARN_COLOR;
        else if (lp == LP_HPS || lp == LP_MERCURY) lp_color = SG_BAD_COLOR;
        else if (lp == LP_MIXED) lp_color = SG_WARN_COLOR;
        lv_obj_set_style_text_color(spectral_lp_source_, lp_color, 0);

        // Verdict — SQI + MPSAS cross-reference
        if (mpsas_check < 18.0f) {
            if (sqi >= 60) verdict = "Discreto (urbano)";
            else if (sqi >= 30) verdict = "Inquinato";
            else verdict = "Molto inquinato";
            sqi_color = (sqi >= 60) ? SG_WARN_COLOR : SG_BAD_COLOR;
        } else {
            if (sqi >= 80) verdict = "Eccellente";
            else if (sqi >= 60) verdict = "Buono";
            else if (sqi >= 40) verdict = "Discreto";
            else if (sqi >= 20) verdict = "Inquinato";
            else verdict = "Molto inquinato";
        }
        lv_label_set_text(spectral_lp_verdict_, verdict);
    }
    lv_obj_set_style_text_color(spectral_lp_verdict_, sqi_color, 0);
}

void SkyGuardDisplay::UpdatePageMoon() {
    if (!moon_cards_built_) return;

    float flat, flon;
    if (!HasPosition(flat, flon)) {
        lv_label_set_text(moon_phase_lbl_, "Pos. non disponibile");
        lv_label_set_text(moon_illum_lbl_, "--");
        for (int i = 0; i < 6; i++) lv_label_set_text(moon_info_[i], "");
        return;
    }

    double jd = GetCurrentJD();
    double jd0 = GetCurrentJD0();

    MoonPhaseData phase = AstroCalc::moonPhase(jd);
    LunarPosition pos = AstroCalc::lunarPosition(jd, (double)flat, (double)flon);
    MoonRiseSet mrs = AstroCalc::moonRiseSet(jd0, (double)flat, (double)flon);
    TwilightTimes twi = AstroCalc::twilightTimes(jd0, (double)flat, (double)flon);

    DrawMoonPhase(phase.illumination, phase.phaseIndex);

    char buf[64];

    // Left card: phase name + illumination
    lv_label_set_text(moon_phase_lbl_, phase.phaseName);
    snprintf(buf, sizeof(buf), "%.0f%%", phase.illumination);
    lv_label_set_text(moon_illum_lbl_, buf);
    lv_obj_set_style_text_color(moon_illum_lbl_,
        (phase.illumination < 30) ? SG_GOOD_COLOR :
        (phase.illumination < 60) ? SG_WARN_COLOR : SG_BAD_COLOR, 0);

    // Right card info lines
    // 0: Age + new moon countdown
    float days_to_new = 29.53f - phase.age;
    snprintf(buf, sizeof(buf), "Eta: %.1f gg / Nuova: %.0f gg", phase.age, days_to_new);
    lv_label_set_text(moon_info_[0], buf);

    // 1: Moon rise/set
    char rise_s[8] = "---", set_s[8] = "---";
    if (mrs.rises) { int h=(int)mrs.moonrise, m=(int)((mrs.moonrise-h)*60); snprintf(rise_s,8,"%02d:%02d",h,m); }
    if (mrs.sets) { int h=(int)mrs.moonset, m=(int)((mrs.moonset-h)*60); snprintf(set_s,8,"%02d:%02d",h,m); }
    snprintf(buf, sizeof(buf), "Luna: %s - %s UT", rise_s, set_s);
    lv_label_set_text(moon_info_[1], buf);

    // 2: Altitude + azimuth
    snprintf(buf, sizeof(buf), "Alt: %.1f  Az: %.1f", pos.altitude, pos.azimuth);
    lv_label_set_text(moon_info_[2], buf);
    lv_obj_set_style_text_color(moon_info_[2],
        (pos.altitude < 0) ? SG_GOOD_COLOR : SG_WARN_COLOR, 0);

    // 3: Sunset / astronomical dusk
    if (twi.valid && !twi.polarDay) {
        char ss[8]="---", ad[8]="---";
        if (twi.sunset>=0) { int h=(int)twi.sunset,m=(int)((twi.sunset-h)*60); snprintf(ss,8,"%02d:%02d",h,m); }
        if (twi.astronomicalDusk>=0) { int h=(int)twi.astronomicalDusk,m=(int)((twi.astronomicalDusk-h)*60); snprintf(ad,8,"%02d:%02d",h,m); }
        snprintf(buf, sizeof(buf), "Tram: %s  Buio: %s", ss, ad);
    } else {
        snprintf(buf, sizeof(buf), "Tramonto: N/A");
    }
    lv_label_set_text(moon_info_[3], buf);

    // 4: Dawn / dark hours
    if (twi.valid && !twi.polarDay) {
        char sr[8]="---";
        if (twi.sunrise>=0) { int h=(int)twi.sunrise,m=(int)((twi.sunrise-h)*60); snprintf(sr,8,"%02d:%02d",h,m); }
        float dark_h = 0;
        if (twi.astronomicalDusk>=0 && twi.astronomicalDawn>=0)
            dark_h = (24.0f - twi.astronomicalDusk) + twi.astronomicalDawn;
        snprintf(buf, sizeof(buf), "Alba: %s  Notte: %.1fh", sr, dark_h);
    } else {
        snprintf(buf, sizeof(buf), "Alba: N/A");
    }
    lv_label_set_text(moon_info_[4], buf);

    // 5: Dark window quality
    if (pos.altitude < 0) {
        lv_label_set_text(moon_info_[5], "Cielo scuro senza luna");
        lv_obj_set_style_text_color(moon_info_[5], SG_GOOD_COLOR, 0);
    } else if (phase.illumination < 15) {
        lv_label_set_text(moon_info_[5], "Luna trascurabile (<15%)");
        lv_obj_set_style_text_color(moon_info_[5], SG_GOOD_COLOR, 0);
    } else {
        snprintf(buf, sizeof(buf), "Luna: %.0f%% disturbo", phase.illumination);
        lv_label_set_text(moon_info_[5], buf);
        lv_obj_set_style_text_color(moon_info_[5],
            (phase.illumination < 40) ? SG_WARN_COLOR : SG_BAD_COLOR, 0);
    }

    // ── Night + Moonless arcs in left card ──
    if (twi.valid && !twi.polarDay && twi.astronomicalDusk >= 0 && twi.astronomicalDawn >= 0) {
        // Dark hours: astro dusk → astro dawn (next day)
        float dark_h = (24.0f - (float)twi.astronomicalDusk) + (float)twi.astronomicalDawn;
        int dark_tenths = (int)(dark_h * 10);
        if (dark_tenths > 120) dark_tenths = 120;
        lv_arc_set_value(moon_night_arc_, dark_tenths);
        snprintf(buf, sizeof(buf), "Notte\n%.1fh", dark_h);
        lv_label_set_text(moon_night_val_, buf);

        // Moonless hours estimate:
        // If moon below horizon now → full dark window is moonless (simplified)
        // If moon above → estimate based on moonset time vs dark window
        float moonless_h = 0;
        if (phase.illumination < 10) {
            moonless_h = dark_h;  // New moon → all dark is moonless
        } else if (pos.altitude < 0) {
            // Moon is below horizon — estimate hours until moonrise
            if (mrs.rises && mrs.moonrise > twi.astronomicalDusk) {
                moonless_h = (float)mrs.moonrise - (float)twi.astronomicalDusk;
            } else if (mrs.rises && mrs.moonrise < twi.astronomicalDawn) {
                moonless_h = dark_h - (float)mrs.moonrise;
            } else {
                moonless_h = dark_h;  // Moon doesn't rise during dark
            }
        } else {
            // Moon is above horizon — moonless starts at moonset
            if (mrs.sets && mrs.moonset > twi.astronomicalDusk) {
                moonless_h = dark_h - ((float)mrs.moonset - (float)twi.astronomicalDusk);
            } else {
                moonless_h = 0;  // Moon up all night
            }
        }
        if (moonless_h < 0) moonless_h = 0;
        if (moonless_h > dark_h) moonless_h = dark_h;

        int moonless_tenths = (int)(moonless_h * 10);
        if (moonless_tenths > 120) moonless_tenths = 120;
        lv_arc_set_value(moon_moonless_arc_, moonless_tenths);
        snprintf(buf, sizeof(buf), "No Luna\n%.1fh", moonless_h);
        lv_label_set_text(moon_moonless_val_, buf);

        // Color moonless arc based on quality
        lv_color_t ml_col = (moonless_h >= 4) ? SG_GOOD_COLOR :
                            (moonless_h >= 2) ? SG_WARN_COLOR : SG_BAD_COLOR;
        lv_obj_set_style_arc_color(moon_moonless_arc_, ml_col, LV_PART_INDICATOR);
        lv_obj_set_style_text_color(moon_moonless_val_, ml_col, 0);
    } else {
        lv_arc_set_value(moon_night_arc_, 0);
        lv_label_set_text(moon_night_val_, "Notte\nN/A");
        lv_arc_set_value(moon_moonless_arc_, 0);
        lv_label_set_text(moon_moonless_val_, "No Luna\nN/A");
    }
}

void SkyGuardDisplay::UpdatePageWeather() {
    if (!weather_built_) return;

    if (!weather_ || !weather_->HasData()) {
        for (int i = 0; i < 5; i++) {
            if (weather_time_[i]) lv_label_set_text(weather_time_[i], "--:--");
            if (weather_cloud_val_[i]) lv_label_set_text(weather_cloud_val_[i], "--%");
            if (weather_rain_[i]) lv_label_set_text(weather_rain_[i], "--");
            if (weather_wind_[i]) lv_label_set_text(weather_wind_[i], "--");
            if (weather_temp_[i]) lv_label_set_text(weather_temp_[i], "--");
            if (weather_daily_day_[i]) lv_label_set_text(weather_daily_day_[i], "--");
            if (weather_daily_temp_[i]) lv_label_set_text(weather_daily_temp_[i], "--");
            if (weather_daily_cloud_[i]) lv_label_set_text(weather_daily_cloud_[i], "--%");
            if (weather_daily_rain_[i]) lv_label_set_text(weather_daily_rain_[i], "--");
        }
        return;
    }

    ForecastData forecast = weather_->GetForecast();
    int col_w = 52;

    // Location name
    if (weather_location_ && forecast.location[0] != '\0') {
        lv_label_set_text(weather_location_, forecast.location);
    }

    // ========== HOURLY (5 columns) ==========
    for (int i = 0; i < forecast.count && i < 5; i++) {
        auto& e = forecast.entries[i];

        DrawWeatherIcon(weather_icon_canvas_[i], e.clouds, e.description);
        if (weather_time_[i]) lv_label_set_text(weather_time_[i], e.time_str);

        char val_buf[24];
        snprintf(val_buf, sizeof(val_buf), "%.0f\xC2\xB0", e.temp);
        if (weather_temp_[i]) {
            lv_label_set_text(weather_temp_[i], val_buf);
            lv_obj_set_style_text_color(weather_temp_[i],
                e.temp < 0 ? lv_color_hex(0x6688FF) :
                e.temp < 10 ? lv_color_hex(0x88BBFF) :
                e.temp < 20 ? SG_GOOD_COLOR :
                e.temp < 30 ? SG_WARN_COLOR : SG_BAD_COLOR, 0);
        }

        // Cloud bar
        if (weather_cloud_bar_[i]) {
            int bar_h = (int)(e.clouds / 100.0f * 8);
            if (bar_h < 2) bar_h = 2;
            lv_obj_set_size(weather_cloud_bar_[i], col_w - 8, bar_h);
            lv_color_t bar_color = (e.clouds > 60) ? SG_BAD_COLOR :
                                   (e.clouds > 30) ? SG_WARN_COLOR : SG_GOOD_COLOR;
            lv_obj_set_style_bg_color(weather_cloud_bar_[i], bar_color, 0);
        }

        snprintf(val_buf, sizeof(val_buf), "%d%%", e.clouds);
        if (weather_cloud_val_[i]) lv_label_set_text(weather_cloud_val_[i], val_buf);

        snprintf(val_buf, sizeof(val_buf), "%.0fm/s", e.wind_speed);
        if (weather_wind_[i]) {
            lv_label_set_text(weather_wind_[i], val_buf);
            lv_obj_set_style_text_color(weather_wind_[i],
                (e.wind_speed > 10) ? SG_BAD_COLOR :
                (e.wind_speed > 5) ? SG_WARN_COLOR : SG_GOOD_COLOR, 0);
        }

        // Rain: probability + mm
        if (weather_rain_[i]) {
            if (e.pop > 0 || e.rain_3h > 0.05f) {
                if (e.rain_3h > 0.05f) {
                    snprintf(val_buf, sizeof(val_buf), "%d%% %.1f", e.pop, e.rain_3h);
                } else {
                    snprintf(val_buf, sizeof(val_buf), "%d%%", e.pop);
                }
                lv_label_set_text(weather_rain_[i], val_buf);
                lv_obj_set_style_text_color(weather_rain_[i],
                    (e.pop > 60 || e.rain_3h > 2.0f) ? SG_BAD_COLOR :
                    (e.pop > 30 || e.rain_3h > 0.5f) ? SG_WARN_COLOR :
                    lv_color_hex(0x55AAFF), 0);
            } else {
                lv_label_set_text(weather_rain_[i], "--");
                lv_obj_set_style_text_color(weather_rain_[i], SG_DIM_COLOR, 0);
            }
        }
    }

    // ========== DAILY (5 columns) ==========
    for (int i = 0; i < forecast.daily_count && i < 5; i++) {
        auto& d = forecast.daily[i];
        char val_buf[24];

        if (weather_daily_day_[i]) lv_label_set_text(weather_daily_day_[i], d.day_str);

        // Draw daily icon
        DrawWeatherIcon(weather_daily_icon_[i], d.clouds_avg, d.description);

        // Min/Max temperature
        snprintf(val_buf, sizeof(val_buf), "%.0f/%.0f", d.temp_min, d.temp_max);
        if (weather_daily_temp_[i]) {
            lv_label_set_text(weather_daily_temp_[i], val_buf);
            float avg_temp = (d.temp_min + d.temp_max) / 2.0f;
            lv_obj_set_style_text_color(weather_daily_temp_[i],
                avg_temp < 0 ? lv_color_hex(0x6688FF) :
                avg_temp < 10 ? lv_color_hex(0x88BBFF) :
                avg_temp < 20 ? SG_GOOD_COLOR :
                avg_temp < 30 ? SG_WARN_COLOR : SG_BAD_COLOR, 0);
        }

        snprintf(val_buf, sizeof(val_buf), "%d%%", d.clouds_avg);
        if (weather_daily_cloud_[i]) {
            lv_label_set_text(weather_daily_cloud_[i], val_buf);
            lv_obj_set_style_text_color(weather_daily_cloud_[i],
                (d.clouds_avg > 60) ? SG_BAD_COLOR :
                (d.clouds_avg > 30) ? SG_WARN_COLOR : SG_GOOD_COLOR, 0);
        }

        // Daily rain: max probability + total mm
        if (weather_daily_rain_[i]) {
            if (d.pop_max > 0 || d.rain_total > 0.05f) {
                if (d.rain_total > 0.05f) {
                    snprintf(val_buf, sizeof(val_buf), "%d%% %.0f", d.pop_max, d.rain_total);
                } else {
                    snprintf(val_buf, sizeof(val_buf), "%d%%", d.pop_max);
                }
                lv_label_set_text(weather_daily_rain_[i], val_buf);
                lv_obj_set_style_text_color(weather_daily_rain_[i],
                    (d.pop_max > 60 || d.rain_total > 5.0f) ? SG_BAD_COLOR :
                    (d.pop_max > 30 || d.rain_total > 1.0f) ? SG_WARN_COLOR :
                    lv_color_hex(0x55AAFF), 0);
            } else {
                lv_label_set_text(weather_daily_rain_[i], "--");
                lv_obj_set_style_text_color(weather_daily_rain_[i], SG_DIM_COLOR, 0);
            }
        }
    }

    // Astronomy verdict — based on ALL hourly entries
    // For astronomy: clouds are the #1 killer, rain is instant-fail,
    // wind matters for scopes, humidity for dew
    if (weather_verdict_ && forecast.count > 0) {
        int n = forecast.count < 5 ? forecast.count : 5;
        float avg_clouds = 0, max_clouds = 0, avg_wind = 0, avg_hum = 0;
        float total_rain = 0, total_snow = 0;
        for (int i = 0; i < n; i++) {
            avg_clouds += forecast.entries[i].clouds;
            if (forecast.entries[i].clouds > max_clouds)
                max_clouds = forecast.entries[i].clouds;
            avg_wind += forecast.entries[i].wind_speed;
            avg_hum += forecast.entries[i].humidity;
            total_rain += forecast.entries[i].rain_3h;
            total_snow += forecast.entries[i].snow_3h;
        }
        avg_clouds /= n; avg_wind /= n; avg_hum /= n;

        const char* verdict;
        lv_color_t vcolor;

        // Instant-fail conditions
        if (total_rain > 0.5f || total_snow > 0.1f) {
            verdict = "Pioggia/neve prevista";
            vcolor = SG_BAD_COLOR;
        } else if (avg_clouds > 80) {
            verdict = "Cielo coperto";
            vcolor = SG_BAD_COLOR;
        } else if (avg_clouds > 50) {
            // Mostly cloudy — not viable for deep sky, maybe planets
            if (avg_wind > 8) {
                verdict = "Nubi + vento forte";
                vcolor = SG_BAD_COLOR;
            } else {
                verdict = "Troppo nuvoloso";
                vcolor = SG_BAD_COLOR;
            }
        } else if (avg_clouds > 30) {
            // Partly cloudy — marginal
            if (avg_wind > 10) {
                verdict = "Vento forte";
                vcolor = SG_BAD_COLOR;
            } else if (avg_hum > 85) {
                verdict = "Umidita alta, rischio condensa";
                vcolor = SG_WARN_COLOR;
            } else {
                verdict = "Parzialmente nuvoloso";
                vcolor = SG_WARN_COLOR;
            }
        } else {
            // Clear skies (<30% clouds)
            if (avg_wind > 10) {
                verdict = "Sereno ma vento forte";
                vcolor = SG_WARN_COLOR;
            } else if (avg_hum > 85) {
                verdict = "Sereno, attenzione condensa";
                vcolor = SG_WARN_COLOR;
            } else if (avg_clouds < 15 && avg_wind < 5) {
                verdict = "* Condizioni eccellenti *";
                vcolor = SG_GOOD_COLOR;
            } else {
                verdict = "Buono per osservare";
                vcolor = SG_GOOD_COLOR;
            }
        }
        lv_label_set_text(weather_verdict_, verdict);
        lv_obj_set_style_text_color(weather_verdict_, vcolor, 0);
    }
}

// ==========================================================================
// WEATHER DETAIL POPUP (on tap)
// ==========================================================================

void SkyGuardDisplay::DismissWeatherPopup() {
    if (weather_popup_) {
        lv_obj_delete(weather_popup_);
        weather_popup_ = nullptr;
    }
}

void SkyGuardDisplay::ShowWeatherPopup(int idx, bool is_daily) {
    DismissWeatherPopup();
    if (!weather_ || !weather_->HasData()) return;

    ForecastData fc = weather_->GetForecast();
    char buf[256];

    weather_popup_ = lv_obj_create(lv_screen_active());
    lv_obj_set_size(weather_popup_, 260, 140);
    lv_obj_center(weather_popup_);
    lv_obj_set_style_bg_color(weather_popup_, lv_color_hex(0x111133), 0);
    lv_obj_set_style_bg_opa(weather_popup_, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(weather_popup_, 12, 0);
    lv_obj_set_style_border_color(weather_popup_, SG_TITLE_COLOR, 0);
    lv_obj_set_style_border_width(weather_popup_, 2, 0);
    lv_obj_set_style_pad_all(weather_popup_, 10, 0);
    lv_obj_clear_flag(weather_popup_, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(weather_popup_, LV_OBJ_FLAG_CLICKABLE);

    // Tap to dismiss
    lv_obj_add_event_cb(weather_popup_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        self->DismissWeatherPopup();
    }, LV_EVENT_CLICKED, this);

    if (is_daily && idx < fc.daily_count) {
        auto& d = fc.daily[idx];
        snprintf(buf, sizeof(buf),
            "%s\n"
            "Temp: %.0f\xC2\xB0 / %.0f\xC2\xB0\n"
            "Nubi: %d%%  Umidita: %d%%\n"
            "Pioggia: %d%% (%.1fmm)\n"
            "Vento max: %.0f km/h\n"
            "%s",
            d.day_str,
            d.temp_min, d.temp_max,
            d.clouds_avg, d.humidity_avg,
            d.pop_max, d.rain_total,
            d.wind_max * 3.6f,
            d.description);
    } else if (!is_daily && idx < fc.count) {
        auto& e = fc.entries[idx];
        float wk = e.wind_speed * 3.6f;
        float gk = e.wind_gust * 3.6f;
        static const char* dirNames[] = {"N","NNE","NE","ENE","E","ESE","SE","SSE",
                                         "S","SSW","SW","WSW","W","WNW","NW","NNW"};
        int di = ((e.wind_deg + 11) % 360) / 22;
        if (di > 15) di = 0;

        snprintf(buf, sizeof(buf),
            "%s\n"
            "Temp: %.1f\xC2\xB0  Umidita: %d%%\n"
            "Nubi: %d%%  Visibilita: %.0fkm\n"
            "Pioggia: %d%% (%.1fmm)\n"
            "Vento: %.0f km/h %s  Raff: %.0f\n"
            "Pressione: %.0f hPa\n"
            "%s",
            e.time_str,
            e.temp, e.humidity,
            e.clouds, e.visibility / 1000.0f,
            e.pop, e.rain_3h,
            wk, dirNames[di], gk,
            e.pressure,
            e.description);
    } else {
        snprintf(buf, sizeof(buf), "Nessun dato");
    }

    lv_obj_t* lbl = lv_label_create(weather_popup_);
    lv_obj_set_style_text_font(lbl, GetTinyFont(), 0);
    lv_obj_set_style_text_color(lbl, SG_TEXT_COLOR, 0);
    lv_label_set_text(lbl, buf);
    lv_obj_set_width(lbl, 240);
    lv_label_set_long_mode(lbl, LV_LABEL_LONG_WRAP);
    lv_obj_align(lbl, LV_ALIGN_TOP_LEFT, 0, 0);

    ESP_LOGI(TAG, "Weather popup: %s idx=%d", is_daily ? "daily" : "hourly", idx);
}

// ==========================================================================
// WIND PAGE — Compass rose + speed + forecast table
// ==========================================================================

void SkyGuardDisplay::HideWindPage() {
    if (wind_container_) lv_obj_add_flag(wind_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::ShowWindPage() {
    if (!wind_container_) {
        // Create container
        wind_container_ = lv_obj_create(data_area_);
        lv_obj_set_size(wind_container_, 320, 195);
        lv_obj_set_style_bg_opa(wind_container_, LV_OPA_TRANSP, 0);
        lv_obj_set_style_border_width(wind_container_, 0, 0);
        lv_obj_set_style_pad_all(wind_container_, 0, 0);
        lv_obj_align(wind_container_, LV_ALIGN_TOP_LEFT, 0, 0);
        lv_obj_clear_flag(wind_container_, LV_OBJ_FLAG_SCROLLABLE);

        // Left side: compass canvas (130x130)
        int canvas_bytes = LV_CANVAS_BUF_SIZE(WIND_COMPASS_SIZE, WIND_COMPASS_SIZE, 16, LV_DRAW_BUF_STRIDE_ALIGN);
        wind_compass_buf_ = (uint8_t*)heap_caps_malloc(canvas_bytes, MALLOC_CAP_SPIRAM);
        if (wind_compass_buf_) {
            wind_compass_canvas_ = lv_canvas_create(wind_container_);
            lv_canvas_set_buffer(wind_compass_canvas_, wind_compass_buf_, WIND_COMPASS_SIZE, WIND_COMPASS_SIZE, LV_COLOR_FORMAT_RGB565);
            lv_obj_set_pos(wind_compass_canvas_, 8, 10);
        }

        // Right side: labels (compass is 76px, starts at x=8)
        int rx = 92;
        wind_dir_lbl_ = lv_label_create(wind_container_);
        lv_obj_set_style_text_font(wind_dir_lbl_, GetSmallFont(), 0);
        lv_obj_set_style_text_color(wind_dir_lbl_, SG_TITLE_COLOR, 0);
        lv_obj_set_pos(wind_dir_lbl_, rx, 12);

        wind_speed_lbl_ = lv_label_create(wind_container_);
        lv_obj_set_style_text_font(wind_speed_lbl_, GetMediumFont(), 0);
        lv_obj_set_style_text_color(wind_speed_lbl_, SG_VALUE_COLOR, 0);
        lv_obj_set_pos(wind_speed_lbl_, rx, 28);

        wind_gust_lbl_ = lv_label_create(wind_container_);
        lv_obj_set_style_text_font(wind_gust_lbl_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(wind_gust_lbl_, SG_DIM_COLOR, 0);
        lv_obj_set_pos(wind_gust_lbl_, rx, 52);

        wind_beaufort_lbl_ = lv_label_create(wind_container_);
        lv_obj_set_style_text_font(wind_beaufort_lbl_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(wind_beaufort_lbl_, SG_DIM_COLOR, 0);
        lv_obj_set_pos(wind_beaufort_lbl_, rx, 64);

        // Separator
        lv_obj_t* sep = lv_obj_create(wind_container_);
        lv_obj_set_size(sep, 290, 1);
        lv_obj_set_style_bg_color(sep, SG_DIM_COLOR, 0);
        lv_obj_set_style_bg_opa(sep, LV_OPA_50, 0);
        lv_obj_set_style_border_width(sep, 0, 0);
        lv_obj_set_pos(sep, 15, 100);

        // Header row
        static const char* headers[] = {"Ora", "km/h", "Raff", "Dir"};
        static const int hx[] = {18, 90, 155, 220};
        for (int i = 0; i < 4; i++) {
            lv_obj_t* h = lv_label_create(wind_container_);
            lv_label_set_text(h, headers[i]);
            lv_obj_set_style_text_font(h, GetTinyFont(), 0);
            lv_obj_set_style_text_color(h, SG_DIM_COLOR, 0);
            lv_obj_set_pos(h, hx[i], 105);
        }

        // Forecast rows (5 entries)
        for (int i = 0; i < 5; i++) {
            wind_forecast_[i] = lv_label_create(wind_container_);
            lv_obj_set_style_text_font(wind_forecast_[i], GetSmallFont(), 0);
            lv_obj_set_style_text_color(wind_forecast_[i], SG_TEXT_COLOR, 0);
            lv_obj_set_pos(wind_forecast_[i], 18, 118 + i * 15);
            lv_label_set_text(wind_forecast_[i], "");
        }

        // Location footer
        wind_location_ = lv_label_create(wind_container_);
        lv_obj_set_style_text_font(wind_location_, GetTinyFont(), 0);
        lv_obj_set_style_text_color(wind_location_, SG_DIM_COLOR, 0);
        lv_label_set_text(wind_location_, LV_SYMBOL_GPS " --");
        lv_obj_set_pos(wind_location_, 92, 78);  // Right side, under beaufort
        lv_obj_set_width(wind_location_, 170);

        wind_built_ = true;
    }

    lv_obj_clear_flag(wind_container_, LV_OBJ_FLAG_HIDDEN);
}

void SkyGuardDisplay::BuildPageWind() {
    SetPageAccent(title_icon_, title_accent_, lv_color_hex(0x44BBAA));  // Teal — wind
    lv_label_set_text(data_title_, "VENTO");
    ShowWindPage();
}

// Bresenham line drawing on canvas (S = canvas dimension)
static void CanvasLine(lv_obj_t* canvas, int x0, int y0, int x1, int y1, lv_color_t col, int thick, int S = 76) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    int half = thick / 2;
    while (true) {
        for (int ox = -half; ox <= half; ox++)
            for (int oy = -half; oy <= half; oy++) {
                int px = x0 + ox, py = y0 + oy;
                if (px >= 0 && px < S && py >= 0 && py < S)
                    lv_canvas_set_px(canvas, px, py, col, LV_OPA_COVER);
            }
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

// Bresenham circle on canvas (S = canvas dimension)
static void CanvasCircle(lv_obj_t* canvas, int cx, int cy, int r, lv_color_t col, int thick, int S = 76) {
    int x = 0, y = r, d = 3 - 2 * r;
    auto plot = [&](int px, int py) {
        int half = thick / 2;
        for (int ox = -half; ox <= half; ox++)
            for (int oy = -half; oy <= half; oy++) {
                int ppx = px + ox, ppy = py + oy;
                if (ppx >= 0 && ppx < S && ppy >= 0 && ppy < S)
                    lv_canvas_set_px(canvas, ppx, ppy, col, LV_OPA_COVER);
            }
    };
    while (x <= y) {
        plot(cx+x,cy+y); plot(cx-x,cy+y); plot(cx+x,cy-y); plot(cx-x,cy-y);
        plot(cx+y,cy+x); plot(cx-y,cy+x); plot(cx+y,cy-x); plot(cx-y,cy-x);
        if (d < 0) { d += 4 * x + 6; } else { d += 4 * (x - y) + 10; y--; }
        x++;
    }
}

static void DrawCompassRose(lv_obj_t* canvas, int size, int wind_deg, float wind_speed) {
    lv_canvas_fill_bg(canvas, lv_color_hex(0x1A1A2E), LV_OPA_COVER);

    int cx = size / 2, cy = size / 2, r = size / 2 - 4;
    lv_color_t ring_col = lv_color_hex(0x334455);
    lv_color_t dim_col = lv_color_hex(0x222233);

    // Outer + inner rings
    CanvasCircle(canvas, cx, cy, r, ring_col, 2, size);
    CanvasCircle(canvas, cx, cy, r / 2, dim_col, 1, size);

    // Crosshairs
    CanvasLine(canvas, cx - r, cy, cx + r, cy, dim_col, 1, size);
    CanvasLine(canvas, cx, cy - r, cx, cy + r, dim_col, 1, size);

    // Cardinal labels via set_px (simple 3x5 pixel font approximation)
    // N at top
    lv_color_t lbl_col = lv_color_hex(0x88AACC);
    for (int i = -1; i <= 1; i++)
        lv_canvas_set_px(canvas, cx + i, cy - r - 2, lbl_col, LV_OPA_COVER);
    // S at bottom
    for (int i = -1; i <= 1; i++)
        lv_canvas_set_px(canvas, cx + i, cy + r + 2, lbl_col, LV_OPA_COVER);
    // E at right
    for (int i = -1; i <= 1; i++)
        lv_canvas_set_px(canvas, cx + r + 2, cy + i, lbl_col, LV_OPA_COVER);
    // W at left
    for (int i = -1; i <= 1; i++)
        lv_canvas_set_px(canvas, cx - r - 2, cy + i, lbl_col, LV_OPA_COVER);

    // Wind arrow
    float rad = wind_deg * M_PI / 180.0f;
    int tipX = cx + (int)(sinf(rad) * (r - 8));
    int tipY = cy - (int)(cosf(rad) * (r - 8));

    lv_color_t arrowCol = (wind_speed > 40) ? lv_color_hex(0xFF3333) :
                          (wind_speed > 20) ? lv_color_hex(0xFFBB00) :
                                              lv_color_hex(0x00CCFF);
    // Main shaft
    CanvasLine(canvas, cx, cy, tipX, tipY, arrowCol, 2, size);

    // Arrowhead
    float aR1 = rad + 2.7f, aR2 = rad - 2.7f;
    int ah1x = cx + (int)(sinf(aR1) * 10);
    int ah1y = cy - (int)(cosf(aR1) * 10);
    int ah2x = cx + (int)(sinf(aR2) * 10);
    int ah2y = cy - (int)(cosf(aR2) * 10);
    CanvasLine(canvas, tipX, tipY, ah1x, ah1y, arrowCol, 2, size);
    CanvasLine(canvas, tipX, tipY, ah2x, ah2y, arrowCol, 2, size);

    // Center dot
    CanvasCircle(canvas, cx, cy, 2, arrowCol, 1, size);
    lv_canvas_set_px(canvas, cx, cy, arrowCol, LV_OPA_COVER);
}

void SkyGuardDisplay::UpdatePageWind() {
    if (!wind_built_) return;

    // Update location footer
    if (wind_location_) {
        char loc_buf[64];
        float lat, lon;
        bool has_pos = HasPosition(lat, lon);
        BuildLocationString(loc_buf, sizeof(loc_buf), location_name_, weather_,
                            has_pos ? lat : 0, has_pos ? lon : 0, has_pos);
        lv_label_set_text(wind_location_, loc_buf);
    }

    if (!weather_ || !weather_->HasData()) {
        lv_label_set_text(wind_dir_lbl_, "--");
        lv_label_set_text(wind_speed_lbl_, "-- km/h");
        lv_label_set_text(wind_gust_lbl_, "");
        lv_label_set_text(wind_beaufort_lbl_, "");
        return;
    }

    ForecastData forecast = weather_->GetForecast();
    if (forecast.count == 0) return;

    auto& now_e = forecast.entries[0];
    float windKmh = now_e.wind_speed * 3.6f;
    float gustKmh = now_e.wind_gust * 3.6f;
    int deg = now_e.wind_deg;

    // Draw compass
    if (wind_compass_canvas_) {
        DrawCompassRose(wind_compass_canvas_, WIND_COMPASS_SIZE, deg, windKmh);
        lv_obj_invalidate(wind_compass_canvas_);
    }

    // Direction name
    static const char* dirNames[] = {"N","NNE","NE","ENE","E","ESE","SE","SSE",
                                     "S","SSW","SW","WSW","W","WNW","NW","NNW"};
    int dirIdx = ((deg + 11) % 360) / 22;
    if (dirIdx > 15) dirIdx = 0;

    char buf[40];
    snprintf(buf, sizeof(buf), "%s %d\xC2\xB0", dirNames[dirIdx], deg);
    lv_label_set_text(wind_dir_lbl_, buf);

    // Speed
    lv_color_t spdCol = windKmh > 40 ? SG_BAD_COLOR : (windKmh > 20 ? SG_WARN_COLOR : SG_GOOD_COLOR);
    snprintf(buf, sizeof(buf), "%.0f km/h", windKmh);
    lv_label_set_text(wind_speed_lbl_, buf);
    lv_obj_set_style_text_color(wind_speed_lbl_, spdCol, 0);

    // Gusts
    if (gustKmh > windKmh + 2) {
        snprintf(buf, sizeof(buf), "Raffiche %.0f km/h", gustKmh);
        lv_label_set_text(wind_gust_lbl_, buf);
        lv_obj_set_style_text_color(wind_gust_lbl_,
            gustKmh > 50 ? SG_BAD_COLOR : (gustKmh > 30 ? SG_WARN_COLOR : SG_DIM_COLOR), 0);
    } else {
        lv_label_set_text(wind_gust_lbl_, "");
    }

    // Beaufort
    float ws = now_e.wind_speed;
    int beau = 0;
    if (ws >= 20.8f) beau = 9; else if (ws >= 17.2f) beau = 8;
    else if (ws >= 13.9f) beau = 7; else if (ws >= 10.8f) beau = 6;
    else if (ws >= 8.0f) beau = 5; else if (ws >= 5.5f) beau = 4;
    else if (ws >= 3.4f) beau = 3; else if (ws >= 1.6f) beau = 2;
    else if (ws >= 0.3f) beau = 1;
    snprintf(buf, sizeof(buf), "Beaufort %d", beau);
    lv_label_set_text(wind_beaufort_lbl_, buf);

    // Forecast table (5 rows)
    int maxR = forecast.count < 5 ? forecast.count : 5;
    for (int i = 0; i < 5; i++) {
        if (i >= maxR) {
            lv_label_set_text(wind_forecast_[i], "");
            continue;
        }
        auto& e = forecast.entries[i];
        float wk = e.wind_speed * 3.6f;
        float gk = e.wind_gust * 3.6f;
        int di = ((e.wind_deg + 11) % 360) / 22;
        if (di > 15) di = 0;

        if (gk > wk + 2) {
            snprintf(buf, sizeof(buf), "%-5s   %3.0f       %3.0f      %s",
                     e.time_str, wk, gk, dirNames[di]);
        } else {
            snprintf(buf, sizeof(buf), "%-5s   %3.0f        -       %s",
                     e.time_str, wk, dirNames[di]);
        }
        lv_label_set_text(wind_forecast_[i], buf);

        // Color speed
        lv_obj_set_style_text_color(wind_forecast_[i],
            wk > 40 ? SG_BAD_COLOR : (wk > 20 ? SG_WARN_COLOR : SG_TEXT_COLOR), 0);
    }
}

// ==========================================================================
// MIC MUTE
// ==========================================================================

void SkyGuardDisplay::ToggleMicMute() {
    mic_muted_ = !mic_muted_;
    ESP_LOGI(TAG, "Mic mute toggled: %s", mic_muted_ ? "MUTED" : "UNMUTED");

    // Update button visual
    if (mic_mute_btn_ && lvgl_port_lock(50)) {
        if (mic_muted_) {
            lv_obj_set_style_bg_color(mic_mute_btn_, lv_color_hex(0xCC2222), 0);
            if (mic_mute_icon_) lv_label_set_text(mic_mute_icon_, "MUT");
        } else {
            lv_obj_set_style_bg_color(mic_mute_btn_, lv_color_hex(0x1A3366), 0);
            if (mic_mute_icon_) lv_label_set_text(mic_mute_icon_, "MIC");
        }
        lvgl_port_unlock();
    }

    // Notify board to enable/disable codec input
    if (mic_mute_cb_) {
        mic_mute_cb_(mic_mute_ctx_, mic_muted_);
    }
}

void SkyGuardDisplay::UpdatePageAircraft() {
    if (!radar_built_) return;

    // Update location footer
    if (radar_location_) {
        char loc_buf[64];
        float lat, lon;
        bool has_pos = HasPosition(lat, lon);
        BuildLocationString(loc_buf, sizeof(loc_buf), location_name_, weather_,
                            has_pos ? lat : 0, has_pos ? lon : 0, has_pos);
        lv_label_set_text(radar_location_, loc_buf);
    }

    // Hide all dots + trails first
    for (int i = 0; i < 8; i++) {
        lv_obj_add_flag(radar_dots_[i], LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(radar_trails_[i], LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(radar_callsigns_[i], LV_OBJ_FLAG_HIDDEN);
    }

    if (!sky_tracker_ || !sky_tracker_->HasFlights()) {
        lv_label_set_text(radar_info_lines_[0], "In attesa dati...");
        lv_obj_set_style_text_color(radar_info_lines_[0], SG_DIM_COLOR, 0);
        for (int i = 1; i < 4; i++) lv_label_set_text(radar_info_lines_[i], "");
        return;
    }

    FlightData flights = sky_tracker_->GetFlights();

    if (flights.count == 0) {
        lv_label_set_text(radar_info_lines_[0], "Nessun aereo");
        lv_obj_set_style_text_color(radar_info_lines_[0], SG_DIM_COLOR, 0);
        for (int i = 1; i < 4; i++) lv_label_set_text(radar_info_lines_[i], "");
        return;
    }

    // Find max distance for scaling (min 10km, max 50km)
    float max_dist = 10.0f;
    for (int i = 0; i < flights.count; i++) {
        if (flights.flights[i].distance_km > max_dist) {
            max_dist = flights.flights[i].distance_km;
        }
    }
    max_dist = max_dist * 1.2f;  // 20% margin
    if (max_dist > 50.0f) max_dist = 50.0f;

    // Range label
    char range_buf[16];
    snprintf(range_buf, sizeof(range_buf), "%.0fkm", max_dist);
    lv_label_set_text(radar_range_label_, range_buf);

    // Radar geometry: 140px diameter, center at (70, ~88)
    const int radar_r = 65;  // usable radius (inside border)
    const int radar_cx = 70; // center X in radar_bg_
    const int radar_cy = 70; // center Y in radar_bg_

    int show = (flights.count < 8) ? flights.count : 8;
    char buf[80];

    for (int i = 0; i < show; i++) {
        auto& f = flights.flights[i];

        // Convert bearing (0=N) + distance to radar XY
        // Bearing: 0=top, 90=right, 180=bottom, 270=left
        float angle_rad = f.bearing * 3.14159f / 180.0f;
        float norm_dist = f.distance_km / max_dist;
        if (norm_dist > 1.0f) norm_dist = 1.0f;

        int dx = (int)(sinf(angle_rad) * norm_dist * radar_r);
        int dy = (int)(-cosf(angle_rad) * norm_dist * radar_r); // negative: N is up

        // Position dot (center it on the calculated point)
        lv_obj_set_pos(radar_dots_[i], radar_cx + dx - 3, radar_cy + dy - 3);
        lv_obj_clear_flag(radar_dots_[i], LV_OBJ_FLAG_HIDDEN);

        // Color by distance
        lv_color_t dot_color = (f.distance_km > 20) ? SG_GOOD_COLOR :
                               (f.distance_km > 10) ? SG_WARN_COLOR : SG_BAD_COLOR;
        lv_obj_set_style_bg_color(radar_dots_[i], dot_color, 0);

        // Heading trail — longer line showing aircraft direction
        // Heading: 0=N, 90=E, 180=S, 270=W
        float head_rad = f.heading * 3.14159f / 180.0f;
        int trail_len = 16;  // Longer for better visibility
        int tx = (int)(sinf(head_rad) * trail_len);
        int ty = (int)(-cosf(head_rad) * trail_len);
        // Position trail from dot center toward heading direction
        int trail_x = radar_cx + dx + tx / 2;
        int trail_y = radar_cy + dy + ty / 2;
        // Determine trail rectangle orientation: use abs dx/dy to set w/h
        int tw = (abs(tx) > abs(ty)) ? trail_len : 3;
        int th = (abs(tx) > abs(ty)) ? 3 : trail_len;
        lv_obj_set_size(radar_trails_[i], tw, th);
        lv_obj_set_pos(radar_trails_[i], trail_x - tw/2, trail_y - th/2);
        lv_obj_set_style_bg_color(radar_trails_[i], dot_color, 0);
        lv_obj_set_style_bg_opa(radar_trails_[i], 180, 0);
        lv_obj_clear_flag(radar_trails_[i], LV_OBJ_FLAG_HIDDEN);

        // Callsign label with heading arrow near dot
        char cs_buf[24];
        snprintf(cs_buf, sizeof(cs_buf), "%s %s", f.callsign,
            SkyGuardSkyTracker::HeadingArrow(f.heading));
        lv_label_set_text(radar_callsigns_[i], cs_buf);
        lv_obj_set_pos(radar_callsigns_[i], radar_cx + dx + 5, radar_cy + dy - 5);
        lv_obj_set_style_text_color(radar_callsigns_[i], dot_color, 0);
        lv_obj_clear_flag(radar_callsigns_[i], LV_OBJ_FLAG_HIDDEN);
    }

    // Right side info: nearest 4 aircraft details
    int info_show = (show < 4) ? show : 4;
    for (int i = 0; i < info_show; i++) {
        auto& f = flights.flights[i];
        int fl = (int)(f.altitude_m / 30.48f);
        const char* type = SkyGuardSkyTracker::IdentifyAircraftType(f.callsign);
        if (type[0]) {
            snprintf(buf, sizeof(buf), "%s (%s)\n%s %.1fkm FL%03d %s",
                f.callsign, type,
                SkyGuardSkyTracker::BearingToCompass(f.bearing),
                f.distance_km, fl,
                SkyGuardSkyTracker::HeadingArrow(f.heading));
        } else {
            snprintf(buf, sizeof(buf), "%s\n%s %.1fkm FL%03d %s",
                f.callsign,
                SkyGuardSkyTracker::BearingToCompass(f.bearing),
                f.distance_km, fl,
                SkyGuardSkyTracker::HeadingArrow(f.heading));
        }
        lv_label_set_text(radar_info_lines_[i], buf);
        lv_obj_set_style_text_color(radar_info_lines_[i],
            (f.distance_km > 20) ? SG_GOOD_COLOR :
            (f.distance_km > 10) ? SG_WARN_COLOR : SG_BAD_COLOR, 0);
    }
    for (int i = info_show; i < 4; i++) {
        // Status on last line
        if (i == info_show) {
            uint32_t now = (uint32_t)(esp_timer_get_time() / 1000);
            int age_min = (now - flights.fetch_time_ms) / 60000;
            snprintf(buf, sizeof(buf), "%d aerei\n%d min fa", flights.count, age_min);
            lv_label_set_text(radar_info_lines_[i], buf);
            lv_obj_set_style_text_color(radar_info_lines_[i], SG_DIM_COLOR, 0);
        } else {
            lv_label_set_text(radar_info_lines_[i], "");
        }
    }
}

void SkyGuardDisplay::UpdatePageSatellites() {
    if (!sat_dome_built_) return;

    // Update location footer
    if (sat_location_) {
        char loc_buf[64];
        float lat, lon;
        bool has_pos = HasPosition(lat, lon);
        BuildLocationString(loc_buf, sizeof(loc_buf), location_name_, weather_,
                            has_pos ? lat : 0, has_pos ? lon : 0, has_pos);
        lv_label_set_text(sat_location_, loc_buf);
    }

    // Hide all dots + trail dots first
    for (int i = 0; i < 6; i++) {
        lv_obj_add_flag(sat_dots_[i], LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(sat_labels_[i], LV_OBJ_FLAG_HIDDEN);
        for (int j = 0; j < 5; j++)
            lv_obj_add_flag(sat_trail_dots_[i][j], LV_OBJ_FLAG_HIDDEN);
    }

    if (!sky_tracker_ || !sky_tracker_->HasSatellites()) {
        lv_label_set_text(sat_info_lines_[0], "In attesa\ndati N2YO...");
        lv_obj_set_style_text_color(sat_info_lines_[0], SG_DIM_COLOR, 0);
        for (int i = 1; i < 3; i++) lv_label_set_text(sat_info_lines_[i], "");
        return;
    }

    SatelliteData sats = sky_tracker_->GetSatellites();

    if (sats.count == 0) {
        lv_label_set_text(sat_info_lines_[0], "Nessun\npassaggio\nprevisto");
        lv_obj_set_style_text_color(sat_info_lines_[0], SG_DIM_COLOR, 0);
        for (int i = 1; i < 3; i++) lv_label_set_text(sat_info_lines_[i], "");
        return;
    }

    // Dome geometry: 130px diameter, center at (65, 65) inside dome_bg_
    const int dome_r = 60;  // usable radius
    const int dome_cx = 65;
    const int dome_cy = 65;

    int show = (sats.count < 6) ? sats.count : 6;
    char buf[80];

    for (int i = 0; i < show; i++) {
        auto& s = sats.passes[i];

        // Position satellite at max_az (azimuth) and max_elevation
        // In sky dome: elevation 90=center, 0=edge
        // Distance from center = dome_r * (1 - elevation/90)
        float elev_frac = s.max_elevation / 90.0f;
        if (elev_frac > 1.0f) elev_frac = 1.0f;
        float dist = dome_r * (1.0f - elev_frac);

        // Azimuth: 0=N(top), 90=E(right), 180=S(bottom), 270=W(left)
        float az_rad = s.max_az * 3.14159f / 180.0f;
        int dx = (int)(sinf(az_rad) * dist);
        int dy = (int)(-cosf(az_rad) * dist);  // N is up

        lv_obj_set_pos(sat_dots_[i], dome_cx + dx - 3, dome_cy + dy - 3);
        lv_obj_clear_flag(sat_dots_[i], LV_OBJ_FLAG_HIDDEN);

        // Color by magnitude
        lv_color_t dot_col = (s.magnitude < 0) ? SG_GOOD_COLOR :
                             (s.magnitude < 3) ? SG_WARN_COLOR : SG_DIM_COLOR;
        lv_obj_set_style_bg_color(sat_dots_[i], dot_col, 0);

        // Label near dot — with direction arrow showing pass direction
        {
            // Arrow from start_az toward end_az (general pass direction)
            const char* dir_arrow = "";
            if (s.start_az >= 0 && s.end_az >= 0) {
                // Average heading from start to end
                float mid_az = (s.start_az + s.end_az) / 2.0f;
                // Use heading arrow based on mid azimuth
                if (mid_az < 22.5f || mid_az >= 337.5f) dir_arrow = "\xe2\x86\x91";       // ↑ N
                else if (mid_az < 67.5f)  dir_arrow = "\xe2\x86\x97";  // ↗ NE
                else if (mid_az < 112.5f) dir_arrow = "\xe2\x86\x92";  // → E
                else if (mid_az < 157.5f) dir_arrow = "\xe2\x86\x98";  // ↘ SE
                else if (mid_az < 202.5f) dir_arrow = "\xe2\x86\x93";  // ↓ S
                else if (mid_az < 247.5f) dir_arrow = "\xe2\x86\x99";  // ↙ SW
                else if (mid_az < 292.5f) dir_arrow = "\xe2\x86\x90";  // ← W
                else dir_arrow = "\xe2\x86\x96";  // ↖ NW
            }
            char sat_lbl[32];
            snprintf(sat_lbl, sizeof(sat_lbl), "%s %s", s.name, dir_arrow);
            lv_label_set_text(sat_labels_[i], sat_lbl);
        }
        lv_obj_set_pos(sat_labels_[i], dome_cx + dx + 5, dome_cy + dy - 5);
        lv_obj_set_style_text_color(sat_labels_[i], dot_col, 0);
        lv_obj_clear_flag(sat_labels_[i], LV_OBJ_FLAG_HIDDEN);

        // Draw pass direction trail — single line through satellite dot
        // showing trajectory from start_az to end_az (like aircraft heading)
        if (s.start_az >= 0 && s.end_az >= 0) {
            // Direction: from start toward end, passing through current position
            // Use the end_az direction as the "heading" of the satellite
            float pass_heading = s.end_az;  // Where satellite is heading
            float head_rad = pass_heading * 3.14159f / 180.0f;
            int trail_len = 18;
            int tx = (int)(sinf(head_rad) * trail_len);
            int ty = (int)(-cosf(head_rad) * trail_len);

            // Use first trail rect as the main direction line
            int trail_x = dome_cx + dx + tx / 2;
            int trail_y = dome_cy + dy + ty / 2;
            int tw = (abs(tx) > abs(ty)) ? trail_len : 3;
            int th = (abs(tx) > abs(ty)) ? 3 : trail_len;
            lv_obj_set_size(sat_trail_dots_[i][0], tw, th);
            lv_obj_set_pos(sat_trail_dots_[i][0], trail_x - tw/2, trail_y - th/2);
            lv_obj_set_style_bg_color(sat_trail_dots_[i][0], dot_col, 0);
            lv_obj_set_style_bg_opa(sat_trail_dots_[i][0], 180, 0);
            lv_obj_clear_flag(sat_trail_dots_[i][0], LV_OBJ_FLAG_HIDDEN);

            // Tail (opposite direction, dimmer)
            int tail_x = dome_cx + dx - tx / 2;
            int tail_y = dome_cy + dy - ty / 2;
            lv_obj_set_size(sat_trail_dots_[i][1], tw, th);
            lv_obj_set_pos(sat_trail_dots_[i][1], tail_x - tw/2, tail_y - th/2);
            lv_obj_set_style_bg_color(sat_trail_dots_[i][1], dot_col, 0);
            lv_obj_set_style_bg_opa(sat_trail_dots_[i][1], 80, 0);
            lv_obj_clear_flag(sat_trail_dots_[i][1], LV_OBJ_FLAG_HIDDEN);

            // Hide unused trail dots (2-4)
            for (int j = 2; j < 5; j++) {
                lv_obj_add_flag(sat_trail_dots_[i][j], LV_OBJ_FLAG_HIDDEN);
            }
        }
    }

    // Info lines right side — detailed pass info
    int info_show = (show < 3) ? show : 3;
    for (int i = 0; i < info_show; i++) {
        auto& s = sats.passes[i];
        snprintf(buf, sizeof(buf), "%s\n%02d:%02d %dmin\nMax %.0f%c Mag%.1f",
            s.name, s.start_hour, s.start_min,
            s.duration_sec / 60,
            s.max_elevation, 0xB0, s.magnitude);
        lv_label_set_text(sat_info_lines_[i], buf);
        lv_obj_set_style_text_color(sat_info_lines_[i],
            (s.magnitude < 0) ? SG_GOOD_COLOR :
            (s.magnitude < 3) ? SG_WARN_COLOR : SG_DIM_COLOR, 0);
    }
    for (int i = info_show; i < 3; i++) {
        if (i == info_show) {
            snprintf(buf, sizeof(buf), "%d passaggi", sats.count);
            lv_label_set_text(sat_info_lines_[i], buf);
            lv_obj_set_style_text_color(sat_info_lines_[i], SG_DIM_COLOR, 0);
        } else {
            lv_label_set_text(sat_info_lines_[i], "");
        }
    }
}

void SkyGuardDisplay::UpdatePageMeteosat() {
    if (!meteosat_built_ || !meteosat_canvas_) {
        if (meteosat_overlay_status_)
            lv_label_set_text(meteosat_overlay_status_, "Canvas non disponibile");
        return;
    }

    int row_bytes = METEO_W * 2;  // RGB565 = 2 bytes/pixel
    int align = LV_DRAW_BUF_STRIDE_ALIGN > 1 ? LV_DRAW_BUF_STRIDE_ALIGN : 1;
    int buf_stride = (row_bytes + align - 1) & ~(align - 1);

    if (sat_image_valid_ && sat_image_rgb565_) {
        // Fast blit: copy RGB565 directly into canvas buffer
        if (meteosat_canvas_buf_) {
            for (int y = 0; y < METEO_H; y++) {
                memcpy(meteosat_canvas_buf_ + y * buf_stride,
                       sat_image_rgb565_ + y * METEO_W,
                       row_bytes);
            }
            lv_obj_invalidate(meteosat_canvas_);
        }

        // Overlay status text on the image
        if (meteosat_overlay_status_) {
            char buf[48];
            uint32_t age_s = ((uint32_t)(esp_timer_get_time() / 1000) - sat_image_fetch_ms_) / 1000;
            if (age_s < 60) {
                snprintf(buf, sizeof(buf), "Aggiornato %lus fa", (unsigned long)age_s);
            } else {
                snprintf(buf, sizeof(buf), "Aggiornato %lum fa", (unsigned long)(age_s / 60));
            }
            lv_label_set_text(meteosat_overlay_status_, buf);
        }
    } else {
        // No image yet — fill canvas with dark blue
        if (meteosat_canvas_buf_) {
            uint16_t dark = ((0x0A >> 3) << 11) | ((0x14 >> 2) << 5) | (0x28 >> 3);
            for (int y = 0; y < METEO_H; y++) {
                uint16_t* row = (uint16_t*)(meteosat_canvas_buf_ + y * buf_stride);
                for (int x = 0; x < METEO_W; x++) row[x] = dark;
            }
            lv_obj_invalidate(meteosat_canvas_);
        }
        if (meteosat_overlay_status_) {
            lv_label_set_text(meteosat_overlay_status_, "Download satellite...");
            lv_obj_set_style_text_color(meteosat_overlay_status_, lv_color_hex(0xFFAA00), 0);
        }
    }
}

void SkyGuardDisplay::SetSatelliteImage(uint16_t* rgb565, int w, int h) {
    if (sat_image_rgb565_) {
        free(sat_image_rgb565_);
    }
    sat_image_rgb565_ = rgb565;
    sat_image_valid_ = (rgb565 != nullptr);
    sat_image_fetch_ms_ = (uint32_t)(esp_timer_get_time() / 1000);
}

bool SkyGuardDisplay::NeedsSatelliteImage() const {
    if (!sat_image_valid_) return true;
    // Refresh every 30 minutes
    uint32_t now = (uint32_t)(esp_timer_get_time() / 1000);
    return (now - sat_image_fetch_ms_) > 30 * 60 * 1000;
}

void SkyGuardDisplay::UpdatePageTelescope() {
    if (!scope_cards_built_) return;
    char buf[64];

    bool has_alpaca = !alpaca_url_.empty();
    bool has_indi = !indi_url_.empty();

    // --- Neither configured ---
    if (!has_alpaca && !has_indi) {
        lv_label_set_text(scope_status_lbl_, "N/A");
        lv_obj_set_style_text_color(scope_status_lbl_, SG_DIM_COLOR, 0);
        lv_label_set_text(scope_info_[0], "Nessun telescopio");
        lv_label_set_text(scope_info_[1], "Configura ASCOM o");
        lv_label_set_text(scope_info_[2], "INDI nella WebUI");
        lv_label_set_text(scope_info_[3], "");
        lv_label_set_text(scope_info_[4], "");
        lv_label_set_text(scope_info_[5], "");
        return;
    }

    // --- Left card: ASCOM or combined status ---
    if (has_alpaca) {
        if (!alpaca_status_.connected) {
            lv_label_set_text(scope_status_lbl_, "OFFLINE");
            lv_obj_set_style_text_color(scope_status_lbl_, SG_BAD_COLOR, 0);
            lv_label_set_text(scope_info_[0], "ASCOM: Offline");
            lv_obj_set_style_text_color(scope_info_[0], SG_BAD_COLOR, 0);
            lv_label_set_text(scope_info_[1], "In attesa...");
            lv_label_set_text(scope_info_[2], "");
        } else {
            const char* state = alpaca_status_.at_park ? "PARK" :
                                alpaca_status_.slewing ? "SLEWING" :
                                alpaca_status_.tracking ? "TRACKING" : "FERMA";
            lv_color_t state_col = alpaca_status_.at_park ? SG_WARN_COLOR :
                                   alpaca_status_.slewing ? SG_TITLE_COLOR :
                                   alpaca_status_.tracking ? SG_GOOD_COLOR : SG_DIM_COLOR;
            lv_label_set_text(scope_status_lbl_, state);
            lv_obj_set_style_text_color(scope_status_lbl_, state_col, 0);

            const char* pier = alpaca_status_.pier_side == 0 ? "Est" :
                               alpaca_status_.pier_side == 1 ? "Ovest" : "N/D";
            snprintf(buf, sizeof(buf), "Pier: %s  Track: %s", pier,
                     alpaca_status_.tracking ? "ON" : "OFF");
            lv_label_set_text(scope_info_[0], buf);
            lv_obj_set_style_text_color(scope_info_[0], alpaca_status_.tracking ? SG_GOOD_COLOR : SG_WARN_COLOR, 0);

            snprintf(buf, sizeof(buf), "Alt: %.1f Az: %.1f", alpaca_status_.alt, alpaca_status_.az);
            lv_label_set_text(scope_info_[1], buf);
            lv_obj_set_style_text_color(scope_info_[1], SG_TEXT_COLOR, 0);

            // INDI status in line 2 if both configured
            if (has_indi) {
                if (indi_status_.server_running) {
                    snprintf(buf, sizeof(buf), "INDI: %s (%d drv)",
                             indi_status_.active_profile[0] ? indi_status_.active_profile : "ON",
                             indi_status_.driver_count);
                    lv_label_set_text(scope_info_[2], buf);
                    lv_obj_set_style_text_color(scope_info_[2], SG_GOOD_COLOR, 0);
                } else {
                    lv_label_set_text(scope_info_[2], "INDI: Offline");
                    lv_obj_set_style_text_color(scope_info_[2], SG_DIM_COLOR, 0);
                }
            } else {
                lv_label_set_text(scope_info_[2], "");
            }
        }
    } else {
        // INDI only (no ASCOM)
        if (indi_status_.server_running) {
            lv_label_set_text(scope_status_lbl_, "INDI ON");
            lv_obj_set_style_text_color(scope_status_lbl_, SG_GOOD_COLOR, 0);
            snprintf(buf, sizeof(buf), "Profilo: %s",
                     indi_status_.active_profile[0] ? indi_status_.active_profile : "default");
            lv_label_set_text(scope_info_[0], buf);
            snprintf(buf, sizeof(buf), "Driver: %d", indi_status_.driver_count);
            lv_label_set_text(scope_info_[1], buf);
            lv_label_set_text(scope_info_[2], "");
        } else {
            lv_label_set_text(scope_status_lbl_, "INDI OFF");
            lv_obj_set_style_text_color(scope_status_lbl_, SG_BAD_COLOR, 0);
            lv_label_set_text(scope_info_[0], "Server non attivo");
            lv_label_set_text(scope_info_[1], "Avvia da Controlli");
            lv_label_set_text(scope_info_[2], "");
        }
    }

    // --- Right card: RA/DEC/AltAz (from ASCOM if available) ---
    if (has_alpaca && alpaca_status_.connected) {
        int ra_h = (int)alpaca_status_.ra;
        int ra_m = (int)((alpaca_status_.ra - ra_h) * 60);
        int ra_s = (int)(((alpaca_status_.ra - ra_h) * 60 - ra_m) * 60);
        snprintf(buf, sizeof(buf), "RA  %02dh %02dm %02ds", ra_h, ra_m, ra_s);
        lv_label_set_text(scope_info_[3], buf);
        lv_obj_set_style_text_color(scope_info_[3], SG_VALUE_COLOR, 0);

        int dec_sign = alpaca_status_.dec >= 0 ? 1 : -1;
        double dec_abs = alpaca_status_.dec * dec_sign;
        int dec_d = (int)dec_abs;
        int dec_m = (int)((dec_abs - dec_d) * 60);
        int dec_s = (int)(((dec_abs - dec_d) * 60 - dec_m) * 60);
        snprintf(buf, sizeof(buf), "DEC %c%02d %02d' %02d\"", dec_sign > 0 ? '+' : '-', dec_d, dec_m, dec_s);
        lv_label_set_text(scope_info_[4], buf);
        lv_obj_set_style_text_color(scope_info_[4], SG_VALUE_COLOR, 0);

        snprintf(buf, sizeof(buf), "Alt %.1f  Az %.1f", alpaca_status_.alt, alpaca_status_.az);
        lv_label_set_text(scope_info_[5], buf);
        lv_obj_set_style_text_color(scope_info_[5], SG_DIM_COLOR, 0);
    } else {
        // No ASCOM coordinates — show INDI info or placeholder
        for (int i = 3; i < 6; i++) lv_label_set_text(scope_info_[i], "");
        if (has_indi && !has_alpaca && indi_status_.server_running) {
            lv_label_set_text(scope_info_[3], "Coordinate via INDI");
            lv_obj_set_style_text_color(scope_info_[3], SG_DIM_COLOR, 0);
            lv_label_set_text(scope_info_[4], "non disponibili");
            lv_obj_set_style_text_color(scope_info_[4], SG_DIM_COLOR, 0);
        }
    }
}

void SkyGuardDisplay::UpdatePageEnvironment() {
    if (!env_built_) return;

    if (!aht20_) {
        lv_label_set_text(env_temp_value_, "--");
        lv_label_set_text(env_hum_value_, "--");
        lv_label_set_text(env_dew_val_, "Sensore N/A");
        lv_label_set_text(env_spread_val_, "--");
        lv_label_set_text(env_cond_val_, "--");
        return;
    }
    char buf[32];

    float temp = aht20_->GetTemperature() + temp_offset_;
    float hum = aht20_->GetHumidity() + hum_offset_;
    if (hum > 100.0f) hum = 100.0f;
    if (hum < 0.0f) hum = 0.0f;
    float dew = aht20_->GetDewPoint();
    float spread = temp - dew;

    // Temperature arc + value
    lv_arc_set_value(env_temp_arc_, (int)temp);
    snprintf(buf, sizeof(buf), "%.1f", temp);
    lv_label_set_text(env_temp_value_, buf);
    lv_color_t t_col = (temp > 35 || temp < 0) ? SG_BAD_COLOR :
                        (temp > 30 || temp < 5) ? SG_WARN_COLOR : SG_VALUE_COLOR;
    lv_obj_set_style_text_color(env_temp_value_, t_col, 0);
    lv_obj_set_style_arc_color(env_temp_arc_, t_col, LV_PART_INDICATOR);

    // Humidity arc + value
    lv_arc_set_value(env_hum_arc_, (int)hum);
    snprintf(buf, sizeof(buf), "%.0f%%", hum);
    lv_label_set_text(env_hum_value_, buf);
    lv_color_t h_col = (hum > 85) ? SG_BAD_COLOR : (hum > 70) ? SG_WARN_COLOR : lv_color_hex(0x00BBFF);
    lv_obj_set_style_text_color(env_hum_value_, h_col, 0);
    lv_obj_set_style_arc_color(env_hum_arc_, h_col, LV_PART_INDICATOR);

    // Dew point
    snprintf(buf, sizeof(buf), "%.1f C", dew);
    lv_label_set_text(env_dew_val_, buf);

    // Spread
    snprintf(buf, sizeof(buf), "%.1f C", spread);
    lv_label_set_text(env_spread_val_, buf);
    lv_obj_set_style_text_color(env_spread_val_,
        (spread > 5.0f) ? SG_GOOD_COLOR : (spread > 2.0f) ? SG_WARN_COLOR : SG_BAD_COLOR, 0);

    // Condensation
    bool risk = aht20_->GetCondensationRisk();
    lv_label_set_text(env_cond_val_, risk ? "RISCHIO!" : "OK");
    lv_obj_set_style_text_color(env_cond_val_, risk ? SG_BAD_COLOR : SG_GOOD_COLOR, 0);
}

void SkyGuardDisplay::UpdatePageGps() {
    if (!gps_cards_built_) return;
    char buf[64];

    if (gps_ && gps_->HasFix()) {
        snprintf(buf, sizeof(buf), "Lat: %.6f", gps_->GetLatitude());
        lv_label_set_text(gps_info_[0], buf);
        snprintf(buf, sizeof(buf), "Lon: %.6f", gps_->GetLongitude());
        lv_label_set_text(gps_info_[1], buf);
        snprintf(buf, sizeof(buf), "Alt: %.1f m", gps_->GetAltitude());
        lv_label_set_text(gps_info_[2], buf);
        snprintf(buf, sizeof(buf), "Satelliti: %d", gps_->GetSatellites());
        lv_label_set_text(gps_info_[3], buf);
        lv_obj_set_style_text_color(gps_info_[3], SG_GOOD_COLOR, 0);
        snprintf(buf, sizeof(buf), "HDOP: %.1f", gps_->GetHdop());
        lv_label_set_text(gps_info_[4], buf);
        lv_label_set_text(gps_info_[5], "Sorgente: GPS");
        lv_obj_set_style_text_color(gps_info_[5], SG_GOOD_COLOR, 0);
    } else if (fallback_valid_) {
        snprintf(buf, sizeof(buf), "Lat: %.6f", fallback_lat_);
        lv_label_set_text(gps_info_[0], buf);
        snprintf(buf, sizeof(buf), "Lon: %.6f", fallback_lon_);
        lv_label_set_text(gps_info_[1], buf);
        lv_label_set_text(gps_info_[2], "Alt: N/A");
        int sats = gps_ ? gps_->GetSatellites() : 0;
        snprintf(buf, sizeof(buf), "GPS sats: %d (no fix)", sats);
        lv_label_set_text(gps_info_[3], buf);
        lv_label_set_text(gps_info_[4], "");
        snprintf(buf, sizeof(buf), "Sorgente: %s", fallback_source_);
        lv_label_set_text(gps_info_[5], buf);
        lv_obj_set_style_text_color(gps_info_[5], SG_WARN_COLOR, 0);
    } else {
        int sats = gps_ ? gps_->GetSatellites() : 0;
        lv_label_set_text(gps_info_[0], "Lat: --");
        lv_label_set_text(gps_info_[1], "Lon: --");
        lv_label_set_text(gps_info_[2], "Alt: --");
        snprintf(buf, sizeof(buf), "Satelliti: %d (no fix)", sats);
        lv_label_set_text(gps_info_[3], buf);
        lv_label_set_text(gps_info_[4], "HDOP: --");
        lv_label_set_text(gps_info_[5], gps_ ? "In attesa fix..." : "GPS non collegato");
        lv_obj_set_style_text_color(gps_info_[5], gps_ ? SG_WARN_COLOR : SG_DIM_COLOR, 0);
    }

    // IP address
    esp_netif_t* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    esp_netif_ip_info_t ip_info;
    if (netif && esp_netif_get_ip_info(netif, &ip_info) == ESP_OK && ip_info.ip.addr != 0) {
        snprintf(buf, sizeof(buf), "WebUI: " IPSTR, IP2STR(&ip_info.ip));
        lv_label_set_text(gps_info_[6], buf);
        lv_obj_set_style_text_color(gps_info_[6], SG_TITLE_COLOR, 0);
    } else {
        lv_label_set_text(gps_info_[6], "WebUI: --");
        lv_obj_set_style_text_color(gps_info_[6], SG_DIM_COLOR, 0);
    }
}

// ==========================================================================
// COUNTDOWN MEASUREMENT
// ==========================================================================

void SkyGuardDisplay::TriggerMeasurement() {
    ESP_LOGI(TAG, "Measurement triggered — starting countdown");
    if (!tsl2591_) {
        ESP_LOGW(TAG, "No TSL2591 sensor — cannot measure");
        return;
    }
    if (measuring_) return;

    StartCountdown();
}

void SkyGuardDisplay::StartCountdown() {
    measuring_ = true;
    countdown_remaining_ = 10;

    if (!lvgl_port_lock(200)) return;

    // Show countdown overlay, hide regular content
    lv_obj_clear_flag(countdown_container_, LV_OBJ_FLAG_HIDDEN);
    lv_arc_set_value(countdown_arc_, 100);
    lv_label_set_text(countdown_label_, "10");
    lv_label_set_text(countdown_text_, "Punta allo Zenit - Resta fermo");

    if (night_mode_) {
        lv_obj_set_style_bg_color(countdown_container_, SG_NIGHT_BG, 0);
        lv_obj_set_style_arc_color(countdown_arc_, lv_color_hex(0x551111), LV_PART_INDICATOR);
        lv_obj_set_style_text_color(countdown_label_, SG_NIGHT_VALUE, 0);
        lv_obj_set_style_text_color(countdown_title_, SG_NIGHT_TITLE, 0);
        lv_obj_set_style_text_color(countdown_text_, lv_color_hex(0x884411), 0);
    } else {
        lv_obj_set_style_bg_color(countdown_container_, SG_BG_COLOR, 0);
        lv_obj_set_style_arc_color(countdown_arc_, SG_TITLE_COLOR, LV_PART_INDICATOR);
        lv_obj_set_style_text_color(countdown_label_, SG_VALUE_COLOR, 0);
        lv_obj_set_style_text_color(countdown_title_, SG_TITLE_COLOR, 0);
        lv_obj_set_style_text_color(countdown_text_, SG_WARN_COLOR, 0);
    }

    lvgl_port_unlock();

    // Create 1-second timer
    if (!countdown_timer_) {
        esp_timer_create_args_t args = {
            .callback = CountdownTickCb,
            .arg = this,
            .dispatch_method = ESP_TIMER_TASK,
            .name = "sg_countdown",
            .skip_unhandled_events = true,
        };
        esp_timer_create(&args, &countdown_timer_);
    }
    esp_timer_start_periodic(countdown_timer_, 1000000);  // 1 second
}

void SkyGuardDisplay::CountdownTickCb(void* arg) {
    auto* self = (SkyGuardDisplay*)arg;
    self->CountdownTick();
}

void SkyGuardDisplay::CountdownTick() {
    countdown_remaining_--;

    if (countdown_remaining_ <= 0) {
        esp_timer_stop(countdown_timer_);
        FinishMeasurement();
        return;
    }

    if (!lvgl_port_lock(100)) return;

    int pct = (countdown_remaining_ * 100) / 10;
    lv_arc_set_value(countdown_arc_, pct);

    char num[4];
    snprintf(num, sizeof(num), "%d", countdown_remaining_);
    lv_label_set_text(countdown_label_, num);

    lvgl_port_unlock();
}

void SkyGuardDisplay::FinishMeasurement() {
    ESP_LOGI(TAG, "Countdown complete — executing measurement");

    float temp = 25.0f, hum = 50.0f, press = 1013.25f;
    if (aht20_) {
        aht20_->Measure();
        temp = aht20_->GetTemperature();
        hum = aht20_->GetHumidity();
    }

    bool ok = false;
    if (tsl2591_) ok = tsl2591_->Measure(temp, hum, press);
    if (as7341_) as7341_->Measure();

    if (!lvgl_port_lock(200)) {
        measuring_ = false;
        return;
    }

    if (ok) {
        char buf[64];
        snprintf(buf, sizeof(buf), "%.2f MPSAS | Bortle %d",
            tsl2591_->GetMpsas(), tsl2591_->GetBortle());
        lv_label_set_text(countdown_label_, "");
        lv_label_set_text(countdown_text_, buf);
        lv_obj_set_style_text_color(countdown_text_, SG_GOOD_COLOR, 0);
        lv_arc_set_value(countdown_arc_, 0);
    } else {
        lv_label_set_text(countdown_label_, "!");
        lv_label_set_text(countdown_text_, "Misurazione fallita");
        lv_obj_set_style_text_color(countdown_text_, SG_BAD_COLOR, 0);
    }

    lvgl_port_unlock();

    // Show result for 3 seconds, then return to SQM page
    vTaskDelay(pdMS_TO_TICKS(3000));

    measuring_ = false;

    if (lvgl_port_lock(200)) {
        HideCountdown();
        SetPage(PAGE_SQM);
        lvgl_port_unlock();
    }
}

void SkyGuardDisplay::HideCountdown() {
    if (countdown_container_) {
        lv_obj_add_flag(countdown_container_, LV_OBJ_FLAG_HIDDEN);
    }
}

// ==========================================================================
// ACTIONS
// ==========================================================================

void SkyGuardDisplay::TriggerAssistant() {
    // Safety: only activate from PAGE_MEASURE to prevent accidental activation
    if (current_page_ != PAGE_MEASURE) {
        ESP_LOGW(TAG, "Assistant blocked — not on COMANDI page (page=%d)", current_page_);
        return;
    }
    ESP_LOGI(TAG, "Assistant triggered via touch button");
    auto& app = Application::GetInstance();
    auto state = app.GetDeviceState();
    if (state == kDeviceStateStarting) return;
    // If already active, exit instead of toggling
    if (state == kDeviceStateListening || state == kDeviceStateSpeaking ||
        state == kDeviceStateConnecting) {
        ESP_LOGI(TAG, "Chatbot already active — exiting");
        app.ToggleChatState();
    } else {
        app.ToggleChatState();
    }
}

// ==========================================================================
// NIGHT MODE
// ==========================================================================

void SkyGuardDisplay::ToggleNightMode() {
    night_mode_ = !night_mode_;
    ESP_LOGI(TAG, "Night mode %s", night_mode_ ? "ON" : "OFF");

    if (night_btn_) {
        lv_obj_t* lbl = lv_obj_get_child(night_btn_, 0);
        if (lbl) lv_label_set_text(lbl, night_mode_ ? "Modo Normale" : "Modo Notte");
    }
    // SetPage rebuilds everything; ApplyNightMode is called at the end of SetPage
    SetPage(current_page_);
}

// Helper: set card bg + border to night/normal colors
static void SetCardNight(lv_obj_t* card, bool night) {
    if (!card) return;
    if (night) {
        lv_obj_set_style_bg_color(card, SG_NIGHT_CARD_BG, 0);
        lv_obj_set_style_border_color(card, SG_NIGHT_CARD_BORDER, 0);
    } else {
        lv_obj_set_style_bg_color(card, lv_color_hex(0x111122), 0);
        lv_obj_set_style_border_color(card, lv_color_hex(0x2A2A44), 0);
    }
}

static void SetArcNight(lv_obj_t* arc, bool night) {
    if (!arc) return;
    if (night) {
        lv_obj_set_style_arc_color(arc, SG_NIGHT_ARC_BG, LV_PART_MAIN);
        lv_obj_set_style_arc_color(arc, SG_NIGHT_ARC_IND, LV_PART_INDICATOR);
    }
    // Normal colors are set by page builders, no need to restore here
}

static void SetLabelNight(lv_obj_t* lbl, bool night, lv_color_t night_color, lv_color_t normal_color) {
    if (!lbl) return;
    lv_obj_set_style_text_color(lbl, night ? night_color : normal_color, 0);
}

void SkyGuardDisplay::ApplyNightMode() {
    // Backlight 40%
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 102);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);

    // Backgrounds
    if (overlay_) lv_obj_set_style_bg_color(overlay_, SG_NIGHT_BG, 0);
    lv_obj_t* screen = lv_screen_active();
    if (screen) lv_obj_set_style_bg_color(screen, SG_NIGHT_BG, 0);

    // Title and data lines
    if (data_title_) lv_obj_set_style_text_color(data_title_, SG_NIGHT_TITLE, 0);
    if (title_icon_) lv_obj_set_style_bg_color(title_icon_, SG_NIGHT_TITLE, 0);
    if (title_accent_) lv_obj_set_style_bg_color(title_accent_, SG_NIGHT_TITLE, 0);
    for (int i = 0; i < 8; i++) {
        if (data_lines_[i]) lv_obj_set_style_text_color(data_lines_[i], SG_NIGHT_TEXT, 0);
    }

    // Buttons
    if (measure_btn_) {
        lv_obj_set_style_bg_color(measure_btn_, SG_NIGHT_BTN, 0);
        lv_obj_t* lbl = lv_obj_get_child(measure_btn_, 0);
        if (lbl) lv_obj_set_style_text_color(lbl, SG_NIGHT_VALUE, 0);
    }
    if (assist_btn_) {
        lv_obj_set_style_bg_color(assist_btn_, SG_NIGHT_BTN, 0);
        lv_obj_t* lbl = lv_obj_get_child(assist_btn_, 0);
        if (lbl) lv_obj_set_style_text_color(lbl, SG_NIGHT_VALUE, 0);
    }
    if (night_btn_) {
        lv_obj_set_style_bg_color(night_btn_, lv_color_hex(0x221100), 0);
        lv_obj_t* lbl = lv_obj_get_child(night_btn_, 0);
        if (lbl) lv_obj_set_style_text_color(lbl, SG_NIGHT_VALUE, 0);
    }

    // Control buttons
    for (int i = 0; i < ctrl_btn_count_; i++) {
        if (ctrl_btns_[i]) {
            lv_obj_set_style_bg_color(ctrl_btns_[i], SG_NIGHT_BTN, 0);
            lv_obj_t* lbl = lv_obj_get_child(ctrl_btns_[i], 0);
            if (lbl) lv_obj_set_style_text_color(lbl, SG_NIGHT_VALUE, 0);
        }
    }

    // Dashboard cards
    SetCardNight(dash_left_card_, true);
    SetCardNight(dash_right_card_, true);
    SetCardNight(dash_bottom_bar_, true);
    if (sqm_arc_) SetArcNight(sqm_arc_, true);
    if (sqm_big_value_) lv_obj_set_style_text_color(sqm_big_value_, SG_NIGHT_VALUE, 0);
    if (sqm_unit_label_) lv_obj_set_style_text_color(sqm_unit_label_, SG_NIGHT_DIM, 0);
    if (sqm_quality_label_) lv_obj_set_style_text_color(sqm_quality_label_, SG_NIGHT_TEXT, 0);
    if (dash_location_) lv_obj_set_style_text_color(dash_location_, SG_NIGHT_TEXT, 0);
    for (int i = 0; i < DASH_ROWS; i++) {
        if (dash_lbl_[i]) lv_obj_set_style_text_color(dash_lbl_[i], SG_NIGHT_DIM, 0);
        if (dash_val_[i]) lv_obj_set_style_text_color(dash_val_[i], SG_NIGHT_TEXT, 0);
    }

    // Spectral cards
    SetCardNight(spectral_left_card_, true);
    SetCardNight(spectral_right_card_, true);
    if (spectral_sqi_arc_) SetArcNight(spectral_sqi_arc_, true);
    if (spectral_sqi_value_) lv_obj_set_style_text_color(spectral_sqi_value_, SG_NIGHT_VALUE, 0);
    if (spectral_sqi_label_) lv_obj_set_style_text_color(spectral_sqi_label_, SG_NIGHT_DIM, 0);
    if (spectral_lp_source_) lv_obj_set_style_text_color(spectral_lp_source_, SG_NIGHT_TEXT, 0);
    if (spectral_sqi_) lv_obj_set_style_text_color(spectral_sqi_, SG_NIGHT_TEXT, 0);
    if (spectral_ratios_) lv_obj_set_style_text_color(spectral_ratios_, SG_NIGHT_DIM, 0);
    if (spectral_lp_verdict_) lv_obj_set_style_text_color(spectral_lp_verdict_, SG_NIGHT_VALUE, 0);
    for (int i = 0; i < 8; i++) {
        if (spectral_labels_[i]) lv_obj_set_style_text_color(spectral_labels_[i], SG_NIGHT_DIM, 0);
        if (spectral_values_[i]) lv_obj_set_style_text_color(spectral_values_[i], SG_NIGHT_VALUE, 0);
        // Spectral bars: dim them to dark red
        if (spectral_bars_[i]) lv_obj_set_style_bg_color(spectral_bars_[i], SG_NIGHT_ARC_IND, 0);
    }

    // Environment cards
    SetCardNight(env_left_card_, true);
    SetCardNight(env_right_card_, true);
    if (env_temp_arc_) SetArcNight(env_temp_arc_, true);
    if (env_hum_arc_) SetArcNight(env_hum_arc_, true);
    if (env_temp_value_) lv_obj_set_style_text_color(env_temp_value_, SG_NIGHT_VALUE, 0);
    if (env_temp_label_) lv_obj_set_style_text_color(env_temp_label_, SG_NIGHT_DIM, 0);
    if (env_hum_value_) lv_obj_set_style_text_color(env_hum_value_, SG_NIGHT_VALUE, 0);
    if (env_hum_label_) lv_obj_set_style_text_color(env_hum_label_, SG_NIGHT_DIM, 0);
    if (env_dew_val_) lv_obj_set_style_text_color(env_dew_val_, SG_NIGHT_VALUE, 0);
    if (env_spread_val_) lv_obj_set_style_text_color(env_spread_val_, SG_NIGHT_VALUE, 0);
    if (env_cond_val_) lv_obj_set_style_text_color(env_cond_val_, SG_NIGHT_VALUE, 0);
    if (env_sensor_lbl_) lv_obj_set_style_text_color(env_sensor_lbl_, SG_NIGHT_DIM, 0);

    // Moon cards
    SetCardNight(moon_left_card_, true);
    SetCardNight(moon_right_card_, true);
    if (moon_phase_lbl_) lv_obj_set_style_text_color(moon_phase_lbl_, SG_NIGHT_TEXT, 0);
    if (moon_illum_lbl_) lv_obj_set_style_text_color(moon_illum_lbl_, SG_NIGHT_VALUE, 0);
    if (moon_night_arc_) SetArcNight(moon_night_arc_, true);
    if (moon_night_val_) lv_obj_set_style_text_color(moon_night_val_, SG_NIGHT_VALUE, 0);
    if (moon_moonless_arc_) SetArcNight(moon_moonless_arc_, true);
    if (moon_moonless_val_) lv_obj_set_style_text_color(moon_moonless_val_, SG_NIGHT_VALUE, 0);
    for (int i = 0; i < 6; i++) {
        if (moon_info_[i]) lv_obj_set_style_text_color(moon_info_[i], SG_NIGHT_TEXT, 0);
    }

    // GPS cards
    SetCardNight(gps_left_card_, true);
    SetCardNight(gps_right_card_, true);
    for (int i = 0; i < 7; i++) {
        if (gps_info_[i]) lv_obj_set_style_text_color(gps_info_[i], SG_NIGHT_TEXT, 0);
    }

    // Telescope cards
    SetCardNight(scope_left_card_, true);
    SetCardNight(scope_right_card_, true);
    if (scope_status_lbl_) lv_obj_set_style_text_color(scope_status_lbl_, SG_NIGHT_VALUE, 0);
    for (int i = 0; i < 6; i++) {
        if (scope_info_[i]) lv_obj_set_style_text_color(scope_info_[i], SG_NIGHT_TEXT, 0);
    }

    // Weather
    if (weather_built_) {
        SetCardNight(weather_container_, true);
        for (int i = 0; i < 5; i++) {
            if (weather_time_[i]) lv_obj_set_style_text_color(weather_time_[i], SG_NIGHT_TITLE, 0);
            if (weather_cloud_val_[i]) lv_obj_set_style_text_color(weather_cloud_val_[i], SG_NIGHT_TEXT, 0);
            if (weather_wind_[i]) lv_obj_set_style_text_color(weather_wind_[i], SG_NIGHT_DIM, 0);
            if (weather_temp_[i]) lv_obj_set_style_text_color(weather_temp_[i], SG_NIGHT_VALUE, 0);
            if (weather_cloud_bar_[i]) lv_obj_set_style_bg_color(weather_cloud_bar_[i], SG_NIGHT_ARC_IND, 0);
            // Daily
            if (weather_daily_day_[i]) lv_obj_set_style_text_color(weather_daily_day_[i], SG_NIGHT_TITLE, 0);
            if (weather_daily_temp_[i]) lv_obj_set_style_text_color(weather_daily_temp_[i], SG_NIGHT_VALUE, 0);
            if (weather_daily_cloud_[i]) lv_obj_set_style_text_color(weather_daily_cloud_[i], SG_NIGHT_TEXT, 0);
        }
        if (weather_location_) lv_obj_set_style_text_color(weather_location_, SG_NIGHT_DIM, 0);
        if (weather_verdict_) lv_obj_set_style_text_color(weather_verdict_, SG_NIGHT_VALUE, 0);
        if (weather_daily_sep_) lv_obj_set_style_bg_color(weather_daily_sep_, SG_NIGHT_CARD_BORDER, 0);
    }

    // Radar
    if (radar_built_) {
        if (radar_bg_) {
            lv_obj_set_style_bg_color(radar_bg_, SG_NIGHT_BG, 0);
            lv_obj_set_style_border_color(radar_bg_, SG_NIGHT_CARD_BORDER, 0);
        }
        if (radar_range_label_) lv_obj_set_style_text_color(radar_range_label_, SG_NIGHT_DIM, 0);
        if (radar_legend_) lv_obj_set_style_text_color(radar_legend_, SG_NIGHT_DIM, 0);
        for (int i = 0; i < 8; i++) {
            if (radar_callsigns_[i]) lv_obj_set_style_text_color(radar_callsigns_[i], SG_NIGHT_TEXT, 0);
        }
        for (int i = 0; i < 4; i++) {
            if (radar_info_lines_[i]) lv_obj_set_style_text_color(radar_info_lines_[i], SG_NIGHT_TEXT, 0);
        }
    }

    // Satellites
    if (sat_dome_built_) {
        if (sat_dome_bg_) {
            lv_obj_set_style_bg_color(sat_dome_bg_, SG_NIGHT_BG, 0);
            lv_obj_set_style_border_color(sat_dome_bg_, SG_NIGHT_CARD_BORDER, 0);
        }
        for (int i = 0; i < 6; i++) {
            if (sat_labels_[i]) lv_obj_set_style_text_color(sat_labels_[i], SG_NIGHT_TEXT, 0);
        }
        for (int i = 0; i < 3; i++) {
            if (sat_info_lines_[i]) lv_obj_set_style_text_color(sat_info_lines_[i], SG_NIGHT_TEXT, 0);
        }
        if (sat_legend_) lv_obj_set_style_text_color(sat_legend_, SG_NIGHT_DIM, 0);
    }
}

void SkyGuardDisplay::ApplyNormalMode() {
    // Backlight 80%
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 200);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);

    // Normal mode just needs to restore backgrounds + backlight.
    // Page colors are already set correctly by Build/Update functions.
    // We only need to fix elements that ApplyNightMode changed.

    if (overlay_) lv_obj_set_style_bg_color(overlay_, SG_BG_COLOR, 0);
    lv_obj_t* screen = lv_screen_active();
    if (screen) lv_obj_set_style_bg_color(screen, SG_BG_COLOR, 0);

    if (data_title_) lv_obj_set_style_text_color(data_title_, SG_TITLE_COLOR, 0);
    if (title_icon_) lv_obj_set_style_bg_color(title_icon_, SG_TITLE_COLOR, 0);
    if (title_accent_) lv_obj_set_style_bg_color(title_accent_, SG_TITLE_COLOR, 0);
    for (int i = 0; i < 8; i++) {
        if (data_lines_[i]) lv_obj_set_style_text_color(data_lines_[i], SG_TEXT_COLOR, 0);
    }

    // Buttons
    if (measure_btn_) {
        lv_obj_set_style_bg_color(measure_btn_, SG_BTN_COLOR, 0);
        lv_obj_t* lbl = lv_obj_get_child(measure_btn_, 0);
        if (lbl) lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
    }
    if (assist_btn_) {
        lv_obj_set_style_bg_color(assist_btn_, lv_color_hex(0x113355), 0);
        lv_obj_t* lbl = lv_obj_get_child(assist_btn_, 0);
        if (lbl) lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
    }
    if (night_btn_) {
        lv_obj_set_style_bg_color(night_btn_, lv_color_hex(0x332200), 0);
        lv_obj_t* lbl = lv_obj_get_child(night_btn_, 0);
        if (lbl) lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
    }

    // Control buttons restore — use group colors from kCtrlButtons
    for (int i = 0; i < ctrl_btn_count_; i++) {
        if (ctrl_btns_[i]) {
            // Restore original group color (approximate — just use SG_BTN_COLOR)
            lv_obj_set_style_bg_color(ctrl_btns_[i], SG_BTN_COLOR, 0);
            lv_obj_t* lbl = lv_obj_get_child(ctrl_btns_[i], 0);
            if (lbl) lv_obj_set_style_text_color(lbl, lv_color_white(), 0);
        }
    }

    // Cards restore
    SetCardNight(dash_left_card_, false);
    SetCardNight(dash_right_card_, false);
    SetCardNight(dash_bottom_bar_, false);
    SetCardNight(spectral_left_card_, false);
    SetCardNight(spectral_right_card_, false);
    SetCardNight(env_left_card_, false);
    SetCardNight(env_right_card_, false);
    SetCardNight(moon_left_card_, false);
    SetCardNight(moon_right_card_, false);
    SetCardNight(gps_left_card_, false);
    SetCardNight(gps_right_card_, false);
    SetCardNight(scope_left_card_, false);
    SetCardNight(scope_right_card_, false);
    SetCardNight(weather_container_, false);

    // The rest of normal colors are already set by Build/Update, which ran
    // via SetPage() before this function is called from ToggleNightMode().
    // No need to individually restore every label — SetPage already did it.
}

void SkyGuardDisplay::SetVisible(bool visible) {
    if (visible_ == visible) return;
    visible_ = visible;
    if (!overlay_) return;
    if (!lvgl_port_lock(100)) return;

    if (visible) {
        lv_obj_clear_flag(overlay_, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(overlay_, LV_OBJ_FLAG_HIDDEN);
    }

    lvgl_port_unlock();
}

// ==========================================================================
// FLOATING STAR AVATAR — Draggable mini star, tap to invoke Sophia
// ==========================================================================

void SkyGuardDisplay::CreateFloatingStar() {
    lv_obj_t* screen = lv_screen_active();
    if (!screen) return;

    // Generate a mini neutral star using StarEmoji32's static helpers
    // We reuse the same 64x64 format but display at 50% zoom (32x32 visual)
    static constexpr int SZ = 64;
    static constexpr int STRIDE = SZ * 2;
    static constexpr int RGB_SZ = SZ * STRIDE;
    static constexpr int ALPHA_SZ = SZ * SZ;
    static constexpr int TOTAL = RGB_SZ + ALPHA_SZ;

    floating_star_buf_ = (uint8_t*)heap_caps_calloc(1, TOTAL, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!floating_star_buf_) {
        floating_star_buf_ = (uint8_t*)heap_caps_calloc(1, TOTAL, MALLOC_CAP_8BIT);
    }
    if (!floating_star_buf_) {
        ESP_LOGE(TAG, "Floating star: OOM");
        return;
    }

    uint8_t* alpha = floating_star_buf_ + RGB_SZ;
    uint8_t* rgb = floating_star_buf_;

    // Generate star shape mask (reuse StarEmoji32 static method)
    StarEmoji32::GenerateStarMask(alpha);
    StarEmoji32::FillStarColor(rgb, alpha);

    // Draw simple neutral eyes (small dots)
    // Left eye at (22,29), right eye at (41,29) — StarEmoji32 constants
    StarEmoji32::DrawCuteEye(rgb, 22, 29, 4);
    StarEmoji32::DrawCuteEye(rgb, 41, 29, 4);
    // Neutral mouth — small line
    StarEmoji32::DrawMouthNeutral(rgb);

    // Build LVGL image descriptor
    floating_star_dsc_.header.w = SZ;
    floating_star_dsc_.header.h = SZ;
    floating_star_dsc_.header.cf = LV_COLOR_FORMAT_RGB565A8;
    floating_star_dsc_.header.stride = STRIDE;
    floating_star_dsc_.data = floating_star_buf_;
    floating_star_dsc_.data_size = TOTAL;

    // Create image widget on screen (above everything)
    floating_star_ = lv_image_create(screen);
    lv_image_set_src(floating_star_, &floating_star_dsc_);
    lv_image_set_scale(floating_star_, 128);  // 50% = 32x32 visual

    // Position bottom-left (above page dots, away from buttons)
    lv_obj_set_pos(floating_star_, 8, 190);

    // Make clickable and draggable
    lv_obj_add_flag(floating_star_, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_clear_flag(floating_star_, LV_OBJ_FLAG_SCROLLABLE);

    // Drag events — track drag vs tap
    lv_obj_add_event_cb(floating_star_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        self->star_dragging_ = false;
    }, LV_EVENT_PRESSED, this);

    lv_obj_add_event_cb(floating_star_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        lv_indev_t* indev = lv_indev_active();
        if (!indev) return;
        lv_point_t vect;
        lv_indev_get_vect(indev, &vect);
        if (vect.x != 0 || vect.y != 0) {
            self->star_dragging_ = true;
            // Move the star
            lv_obj_t* star = lv_event_get_target(e);
            lv_coord_t x = lv_obj_get_x(star) + vect.x;
            lv_coord_t y = lv_obj_get_y(star) + vect.y;
            // Clamp to screen bounds (32x32 visual size due to 50% zoom)
            if (x < 0) x = 0;
            if (y < 0) y = 0;
            if (x > 288) x = 288;  // 320 - 32
            if (y > 208) y = 208;  // 240 - 32
            lv_obj_set_pos(star, x, y);
        }
    }, LV_EVENT_PRESSING, this);

    lv_obj_add_event_cb(floating_star_, [](lv_event_t* e) {
        auto* self = (SkyGuardDisplay*)lv_event_get_user_data(e);
        if (!self->star_dragging_) {
            // TAP (not drag) → trigger talk callback
            ESP_LOGI("SkyGuardStar", "Star tapped → invoking Sophia");
            if (self->star_tap_cb_) {
                self->star_tap_cb_(self->star_tap_ctx_);
            }
        }
    }, LV_EVENT_RELEASED, this);

    ESP_LOGI(TAG, "Floating star avatar created (32x32 visual, draggable)");
}

void SkyGuardDisplay::SetFloatingStarVisible(bool visible) {
    if (!floating_star_) return;
    if (!lvgl_port_lock(50)) return;
    if (visible) {
        lv_obj_clear_flag(floating_star_, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(floating_star_, LV_OBJ_FLAG_HIDDEN);
    }
    lvgl_port_unlock();
}

// ==========================================================================
// BOOT LOADER — Spinner overlay during startup/connection
// ==========================================================================

void SkyGuardDisplay::ShowBootLoader() {
    if (boot_loader_visible_) return;
    if (!overlay_) return;
    if (!lvgl_port_lock(200)) return;

    // Hide data area and page indicator during boot
    if (data_area_) lv_obj_add_flag(data_area_, LV_OBJ_FLAG_HIDDEN);
    if (page_indicator_) lv_obj_add_flag(page_indicator_, LV_OBJ_FLAG_HIDDEN);

    // Create boot loader container (full overlay area)
    boot_loader_container_ = lv_obj_create(overlay_);
    lv_obj_remove_style_all(boot_loader_container_);
    lv_obj_set_size(boot_loader_container_, 320, 216);
    lv_obj_set_pos(boot_loader_container_, 0, 0);
    lv_obj_set_style_bg_color(boot_loader_container_, SG_BG_COLOR, 0);
    lv_obj_set_style_bg_opa(boot_loader_container_, LV_OPA_COVER, 0);
    lv_obj_set_flex_flow(boot_loader_container_, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(boot_loader_container_, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_row(boot_loader_container_, 12, 0);

    // Title: "SKYGUARD AI"
    boot_title_ = lv_label_create(boot_loader_container_);
    lv_label_set_text(boot_title_, "SKYGUARD AI");
    lv_obj_set_style_text_font(boot_title_, GetSmallFont(), 0);
    lv_obj_set_style_text_color(boot_title_, SG_TITLE_COLOR, 0);
    lv_obj_set_style_text_align(boot_title_, LV_TEXT_ALIGN_CENTER, 0);

    // Animated arc (manual spinner — lv_spinner may not be enabled)
    boot_spinner_ = lv_arc_create(boot_loader_container_);
    lv_obj_set_size(boot_spinner_, 60, 60);
    lv_arc_set_rotation(boot_spinner_, 0);
    lv_arc_set_bg_angles(boot_spinner_, 0, 360);
    lv_arc_set_angles(boot_spinner_, 0, 90);
    lv_obj_remove_style(boot_spinner_, nullptr, LV_PART_KNOB);
    lv_obj_set_style_arc_width(boot_spinner_, 5, 0);
    lv_obj_set_style_arc_color(boot_spinner_, SG_DIM_COLOR, 0);
    lv_obj_set_style_arc_width(boot_spinner_, 5, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(boot_spinner_, SG_TITLE_COLOR, LV_PART_INDICATOR);
    lv_obj_clear_flag(boot_spinner_, LV_OBJ_FLAG_CLICKABLE);

    // Rotate the arc indicator with an LVGL animation
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, boot_spinner_);
    lv_anim_set_values(&a, 0, 360);
    lv_anim_set_duration(&a, 1200);
    lv_anim_set_repeat_count(&a, LV_ANIM_REPEAT_INFINITE);
    lv_anim_set_exec_cb(&a, [](void* obj, int32_t v) {
        lv_arc_set_rotation((lv_obj_t*)obj, (int16_t)v);
    });
    lv_anim_start(&a);

    // Status text: "Connessione in corso..."
    boot_status_ = lv_label_create(boot_loader_container_);
    lv_label_set_text(boot_status_, "Connessione in corso...");
    lv_obj_set_style_text_font(boot_status_, GetTinyFont(), 0);
    lv_obj_set_style_text_color(boot_status_, SG_DIM_COLOR, 0);
    lv_obj_set_style_text_align(boot_status_, LV_TEXT_ALIGN_CENTER, 0);

    boot_loader_visible_ = true;
    lvgl_port_unlock();
    ESP_LOGI(TAG, "Boot loader shown");
}

void SkyGuardDisplay::HideBootLoader() {
    if (!boot_loader_visible_) return;
    if (!lvgl_port_lock(200)) return;

    if (boot_loader_container_) {
        lv_obj_delete(boot_loader_container_);
        boot_loader_container_ = nullptr;
        boot_spinner_ = nullptr;
        boot_title_ = nullptr;
        boot_status_ = nullptr;
    }

    // Restore data area and page indicator
    if (data_area_) lv_obj_clear_flag(data_area_, LV_OBJ_FLAG_HIDDEN);
    if (page_indicator_) lv_obj_clear_flag(page_indicator_, LV_OBJ_FLAG_HIDDEN);

    boot_loader_visible_ = false;
    // Reset auto-scroll timer so dashboard gets full display time
    last_page_change_ms_ = (uint32_t)(esp_timer_get_time() / 1000);
    lvgl_port_unlock();
    ESP_LOGI(TAG, "Boot loader hidden");
}
