#include "skyguard_weather.h"
#include "skyguard_http.h"
#include "skyguard_astro.h"
#include <esp_log.h>
#include <esp_timer.h>
#include <cJSON.h>
#include <cstring>
#include <cstdio>
#include <cmath>

#define TAG "SkyGuardWeather"

SkyGuardWeather::SkyGuardWeather() {
    mutex_ = xSemaphoreCreateMutex();
    memset(&data_, 0, sizeof(data_));
}

SkyGuardWeather::~SkyGuardWeather() {
    if (mutex_) vSemaphoreDelete(mutex_);
}

void SkyGuardWeather::StartFetchTask() {
    if (fetching_) return;
    if (api_key_.empty()) {
        ESP_LOGW(TAG, "No OWM API key configured");
        return;
    }
    if (lat_ == 0 && lon_ == 0) {
        ESP_LOGW(TAG, "No location set");
        return;
    }

    fetching_ = true;
    xTaskCreate(FetchTaskFunc, "sg_weather", 8192, this, 3, nullptr);
}

void SkyGuardWeather::FetchTaskFunc(void* arg) {
    auto* self = (SkyGuardWeather*)arg;
    self->DoFetch();
    self->fetching_ = false;
    vTaskDelete(nullptr);
}

// Helper: parse one OWM list entry into a ForecastEntry
static void ParseOWMEntry(cJSON* item, ForecastEntry& e) {
    cJSON* dt_txt = cJSON_GetObjectItem(item, "dt_txt");
    if (dt_txt && dt_txt->valuestring) {
        const char* space = strchr(dt_txt->valuestring, ' ');
        if (space) {
            strncpy(e.time_str, space + 1, 5);
            e.time_str[5] = '\0';
        }
    }

    cJSON* main_obj = cJSON_GetObjectItem(item, "main");
    if (main_obj) {
        cJSON* temp = cJSON_GetObjectItem(main_obj, "temp");
        if (temp) e.temp = temp->valuedouble;
        cJSON* hum = cJSON_GetObjectItem(main_obj, "humidity");
        if (hum) e.humidity = hum->valueint;
        cJSON* press = cJSON_GetObjectItem(main_obj, "pressure");
        if (press) e.pressure = press->valuedouble;
        cJSON* sea = cJSON_GetObjectItem(main_obj, "sea_level");
        if (sea) e.sea_level = sea->valuedouble;
    }

    cJSON* clouds = cJSON_GetObjectItem(item, "clouds");
    if (clouds) {
        cJSON* all = cJSON_GetObjectItem(clouds, "all");
        if (all) e.clouds = all->valueint;
    }

    cJSON* wind = cJSON_GetObjectItem(item, "wind");
    if (wind) {
        cJSON* speed = cJSON_GetObjectItem(wind, "speed");
        if (speed) e.wind_speed = speed->valuedouble;
        cJSON* gust = cJSON_GetObjectItem(wind, "gust");
        if (gust) e.wind_gust = gust->valuedouble;
        cJSON* deg = cJSON_GetObjectItem(wind, "deg");
        if (deg) e.wind_deg = deg->valueint;
    }

    cJSON* rain = cJSON_GetObjectItem(item, "rain");
    if (rain) {
        cJSON* r3h = cJSON_GetObjectItem(rain, "3h");
        if (r3h) e.rain_3h = r3h->valuedouble;
    }

    cJSON* snow = cJSON_GetObjectItem(item, "snow");
    if (snow) {
        cJSON* s3h = cJSON_GetObjectItem(snow, "3h");
        if (s3h) e.snow_3h = s3h->valuedouble;
    }

    cJSON* vis = cJSON_GetObjectItem(item, "visibility");
    if (vis) e.visibility = vis->valuedouble;

    cJSON* pop_val = cJSON_GetObjectItem(item, "pop");
    if (pop_val) e.pop = (int)(pop_val->valuedouble * 100 + 0.5);

    cJSON* weather_arr = cJSON_GetObjectItem(item, "weather");
    if (weather_arr && cJSON_GetArraySize(weather_arr) > 0) {
        cJSON* w0 = cJSON_GetArrayItem(weather_arr, 0);
        cJSON* desc = cJSON_GetObjectItem(w0, "description");
        if (desc && desc->valuestring) {
            strncpy(e.description, desc->valuestring, sizeof(e.description) - 1);
        }
    }
}

// Italian day abbreviations
static const char* kDayNames[] = {"Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"};

void SkyGuardWeather::DoFetch() {
    // Fetch ALL entries (up to 40) for both hourly display and daily aggregation
    char url[256];
    snprintf(url, sizeof(url),
        "https://api.openweathermap.org/data/2.5/forecast?lat=%.4f&lon=%.4f"
        "&appid=%s&units=metric&lang=it",
        lat_, lon_, api_key_.c_str());

    // 40 entries need ~32KB
    const int buf_size = 32768;
    char* buf = SkyGuardHttp::AllocBuffer(buf_size);
    if (!buf) {
        ESP_LOGE(TAG, "Failed to allocate response buffer");
        return;
    }

    ESP_LOGI(TAG, "Fetching weather: lat=%.4f lon=%.4f", lat_, lon_);
    if (!SkyGuardHttp::Get(url, buf, buf_size)) {
        // Log first 200 chars of response for debugging (may contain error message)
        if (buf[0]) {
            buf[200] = '\0';
            ESP_LOGE(TAG, "Weather fetch failed. Response: %s", buf);
        } else {
            ESP_LOGE(TAG, "Weather fetch failed (no response)");
        }
        // Keep existing cached data — don't clear
        free(buf);
        return;
    }

    cJSON* root = cJSON_Parse(buf);
    free(buf);

    if (!root) {
        ESP_LOGE(TAG, "JSON parse failed");
        return;
    }

    cJSON* list = cJSON_GetObjectItem(root, "list");
    if (!list || !cJSON_IsArray(list)) {
        ESP_LOGE(TAG, "No 'list' array in response");
        cJSON_Delete(root);
        return;
    }

    ForecastData new_data = {};
    int total = cJSON_GetArraySize(list);

    // --- Hourly: first 5 entries ---
    int hourly_count = (total < 5) ? total : 5;
    new_data.count = hourly_count;
    for (int i = 0; i < hourly_count; i++) {
        cJSON* item = cJSON_GetArrayItem(list, i);
        ParseOWMEntry(item, new_data.entries[i]);
    }

    // --- Daily aggregation: group by date string (YYYY-MM-DD) ---
    // Track up to 6 unique days (skip today partial, keep next 5)
    struct DayAcc {
        char date[11];       // "2026-03-13"
        float temp_min, temp_max, wind_max, rain_total;
        int clouds_sum, hum_sum, pop_max, sample_count;
        char best_desc[32];
        int desc_count;      // count of most common description
    };
    DayAcc days[6] = {};
    int day_count = 0;

    for (int i = 0; i < total; i++) {
        cJSON* item = cJSON_GetArrayItem(list, i);
        cJSON* dt_txt = cJSON_GetObjectItem(item, "dt_txt");
        if (!dt_txt || !dt_txt->valuestring) continue;

        // Extract date part "YYYY-MM-DD"
        char date[11] = {};
        strncpy(date, dt_txt->valuestring, 10);
        date[10] = '\0';

        // Find or create day bucket
        int di = -1;
        for (int d = 0; d < day_count; d++) {
            if (strcmp(days[d].date, date) == 0) { di = d; break; }
        }
        if (di < 0) {
            if (day_count >= 6) continue;
            di = day_count++;
            strncpy(days[di].date, date, 10);
            days[di].temp_min = 999;
            days[di].temp_max = -999;
        }

        // Parse entry values
        cJSON* main_obj = cJSON_GetObjectItem(item, "main");
        float temp = 0;
        int clouds = 0, hum = 0;
        float wind = 0, rain = 0;
        if (main_obj) {
            cJSON* t = cJSON_GetObjectItem(main_obj, "temp");
            if (t) temp = t->valuedouble;
            cJSON* h = cJSON_GetObjectItem(main_obj, "humidity");
            if (h) hum = h->valueint;
        }
        cJSON* cl = cJSON_GetObjectItem(item, "clouds");
        if (cl) { cJSON* a = cJSON_GetObjectItem(cl, "all"); if (a) clouds = a->valueint; }
        cJSON* w = cJSON_GetObjectItem(item, "wind");
        if (w) { cJSON* s = cJSON_GetObjectItem(w, "speed"); if (s) wind = s->valuedouble; }
        cJSON* r = cJSON_GetObjectItem(item, "rain");
        if (r) { cJSON* r3 = cJSON_GetObjectItem(r, "3h"); if (r3) rain = r3->valuedouble; }
        int pop_val = 0;
        cJSON* pop_obj = cJSON_GetObjectItem(item, "pop");
        if (pop_obj) pop_val = (int)(pop_obj->valuedouble * 100 + 0.5);

        // Accumulate
        if (temp < days[di].temp_min) days[di].temp_min = temp;
        if (temp > days[di].temp_max) days[di].temp_max = temp;
        if (wind > days[di].wind_max) days[di].wind_max = wind;
        days[di].clouds_sum += clouds;
        days[di].hum_sum += hum;
        if (pop_val > days[di].pop_max) days[di].pop_max = pop_val;
        days[di].rain_total += rain;
        days[di].sample_count++;

        // Description: keep the one from ~12:00 slot (or last midday-ish)
        const char* time_part = dt_txt->valuestring + 11;  // "HH:MM:SS"
        if (strncmp(time_part, "12:", 3) == 0 || strncmp(time_part, "15:", 3) == 0) {
            cJSON* wa = cJSON_GetObjectItem(item, "weather");
            if (wa && cJSON_GetArraySize(wa) > 0) {
                cJSON* w0 = cJSON_GetArrayItem(wa, 0);
                cJSON* desc = cJSON_GetObjectItem(w0, "description");
                if (desc && desc->valuestring) {
                    strncpy(days[di].best_desc, desc->valuestring, 31);
                }
            }
        }
    }

    // Skip first day if it has fewer than 4 samples (partial today)
    int start_day = 0;
    if (day_count > 1 && days[0].sample_count < 4) start_day = 1;

    new_data.daily_count = 0;
    for (int d = start_day; d < day_count && new_data.daily_count < 5; d++) {
        DailyEntry& de = new_data.daily[new_data.daily_count];
        DayAcc& acc = days[d];
        if (acc.sample_count == 0) continue;

        // Parse day-of-week from date string "YYYY-MM-DD"
        int y = 0, m = 0, dd = 0;
        sscanf(acc.date, "%d-%d-%d", &y, &m, &dd);
        // Zeller-like day of week (Tomohiko Sakamoto's algorithm)
        static const int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
        int yy = y;
        if (m < 3) yy--;
        int dow = (yy + yy/4 - yy/100 + yy/400 + t[m-1] + dd) % 7;
        strncpy(de.day_str, kDayNames[dow], 3);
        de.day_str[3] = '\0';

        de.temp_min = acc.temp_min;
        de.temp_max = acc.temp_max;
        de.wind_max = acc.wind_max;
        de.clouds_avg = acc.clouds_sum / acc.sample_count;
        de.humidity_avg = acc.hum_sum / acc.sample_count;
        de.pop_max = acc.pop_max;
        de.rain_total = acc.rain_total;
        strncpy(de.description, acc.best_desc, 31);

        new_data.daily_count++;
    }

    new_data.fetch_time_ms = (uint32_t)(esp_timer_get_time() / 1000);
    new_data.valid = true;

    // Extract city name
    cJSON* city = cJSON_GetObjectItem(root, "city");
    if (city) {
        cJSON* name = cJSON_GetObjectItem(city, "name");
        if (name && name->valuestring) {
            strncpy(new_data.location, name->valuestring, sizeof(new_data.location) - 1);
        }
    }

    cJSON_Delete(root);

    if (xSemaphoreTake(mutex_, pdMS_TO_TICKS(1000)) == pdTRUE) {
        data_ = new_data;
        xSemaphoreGive(mutex_);
    }

    ESP_LOGI(TAG, "Weather updated: %d hourly, %d daily", hourly_count, new_data.daily_count);
}

ForecastData SkyGuardWeather::GetForecast() {
    ForecastData copy = {};
    if (xSemaphoreTake(mutex_, pdMS_TO_TICKS(500)) == pdTRUE) {
        copy = data_;
        xSemaphoreGive(mutex_);
    }
    return copy;
}

std::string SkyGuardWeather::GetForecastText() {
    ForecastData d = GetForecast();
    if (!d.valid || d.count == 0) {
        return "Previsioni non disponibili";
    }

    std::string text = "Previsioni prossime ore:\n";
    for (int i = 0; i < d.count; i++) {
        auto& e = d.entries[i];
        char line[128];
        snprintf(line, sizeof(line),
            "%s: %.0fC, nuvole %d%%, vento %.1fm/s, %s\n",
            e.time_str, e.temp, e.clouds, e.wind_speed, e.description);
        text += line;
    }
    return text;
}

// ==========================================================================
// Full 5-day forecast POST to SQM server
// ==========================================================================

void SkyGuardWeather::StartForecastPostTask() {
    if (posting_forecast_) return;
    if (api_key_.empty()) {
        ESP_LOGW(TAG, "No OWM API key — cannot post forecast");
        return;
    }
    if (server_url_.empty() || server_api_key_.empty()) {
        ESP_LOGW(TAG, "No server URL/key — cannot post forecast");
        return;
    }
    if (lat_ == 0 && lon_ == 0) {
        ESP_LOGW(TAG, "No location set — cannot post forecast");
        return;
    }

    posting_forecast_ = true;
    xTaskCreate(ForecastPostTaskFunc, "sg_fcst_post", 12288, this, 2, nullptr);
}

void SkyGuardWeather::ForecastPostTaskFunc(void* arg) {
    auto* self = (SkyGuardWeather*)arg;
    self->DoForecastPost();
    self->posting_forecast_ = false;
    vTaskDelete(nullptr);
}

// Helper: parse "YYYY-MM-DD HH:MM:SS" to Julian Date (UTC)
static double dtTxtToJD(const char* dt_txt) {
    int Y, M, D, h, m, s;
    if (sscanf(dt_txt, "%d-%d-%d %d:%d:%d", &Y, &M, &D, &h, &m, &s) != 6) return 0;
    // Julian Date from calendar date (Meeus)
    if (M <= 2) { Y--; M += 12; }
    int A = Y / 100;
    int B = 2 - A + A / 4;
    double JD = (int)(365.25 * (Y + 4716)) + (int)(30.6001 * (M + 1)) + D + B - 1524.5;
    JD += (h + m / 60.0 + s / 3600.0) / 24.0;
    return JD;
}

void SkyGuardWeather::DoForecastPost() {
    // 1. Fetch full 40-slot forecast from OWM (no cnt= limit)
    char url[256];
    snprintf(url, sizeof(url),
        "https://api.openweathermap.org/data/2.5/forecast?lat=%.4f&lon=%.4f"
        "&appid=%s&units=metric&lang=it",
        lat_, lon_, api_key_.c_str());

    // OWM 5-day response can be ~50KB, allocate generously from PSRAM
    const int buf_size = 65536;
    char* buf = SkyGuardHttp::AllocBuffer(buf_size);
    if (!buf) {
        ESP_LOGE(TAG, "ForecastPost: failed to allocate %d bytes", buf_size);
        return;
    }

    ESP_LOGI(TAG, "Fetching full 5-day forecast from OWM...");
    if (!SkyGuardHttp::Get(url, buf, buf_size, 20000)) {
        ESP_LOGE(TAG, "ForecastPost: OWM fetch failed");
        free(buf);
        return;
    }

    // 2. Parse OWM response
    cJSON* root = cJSON_Parse(buf);
    free(buf);  // Free raw response ASAP

    if (!root) {
        ESP_LOGE(TAG, "ForecastPost: JSON parse failed");
        return;
    }

    cJSON* list = cJSON_GetObjectItem(root, "list");
    if (!list || !cJSON_IsArray(list)) {
        ESP_LOGE(TAG, "ForecastPost: no 'list' array");
        cJSON_Delete(root);
        return;
    }

    int slot_count = cJSON_GetArraySize(list);
    if (slot_count > 40) slot_count = 40;  // OWM free = max 40
    ESP_LOGI(TAG, "ForecastPost: %d slots from OWM", slot_count);

    // 3. Build output JSON: { "source": "owm", "forecast": [...] }
    cJSON* out_root = cJSON_CreateObject();
    cJSON_AddStringToObject(out_root, "source", "owm");
    cJSON* out_arr = cJSON_AddArrayToObject(out_root, "forecast");

    for (int i = 0; i < slot_count; i++) {
        cJSON* item = cJSON_GetArrayItem(list, i);
        cJSON* out_slot = cJSON_CreateObject();

        // forecast_time = dt_txt
        cJSON* dt_txt = cJSON_GetObjectItem(item, "dt_txt");
        const char* dt_str = (dt_txt && dt_txt->valuestring) ? dt_txt->valuestring : "";
        cJSON_AddStringToObject(out_slot, "forecast_time", dt_str);

        // main → temp, humidity, pressure
        float temp_c = 0, pressure = 0;
        int humidity = 0;
        cJSON* main_obj = cJSON_GetObjectItem(item, "main");
        if (main_obj) {
            cJSON* t = cJSON_GetObjectItem(main_obj, "temp");
            if (t) { temp_c = t->valuedouble; cJSON_AddNumberToObject(out_slot, "temp_c", temp_c); }
            cJSON* h = cJSON_GetObjectItem(main_obj, "humidity");
            if (h) { humidity = h->valueint; cJSON_AddNumberToObject(out_slot, "humidity_pct", humidity); }
            cJSON* p = cJSON_GetObjectItem(main_obj, "pressure");
            if (p) { pressure = p->valuedouble; cJSON_AddNumberToObject(out_slot, "pressure_hpa", pressure); }
        }

        // clouds
        int clouds = 0;
        cJSON* clouds_obj = cJSON_GetObjectItem(item, "clouds");
        if (clouds_obj) {
            cJSON* all = cJSON_GetObjectItem(clouds_obj, "all");
            if (all) { clouds = all->valueint; cJSON_AddNumberToObject(out_slot, "clouds_pct", clouds); }
        }

        // wind → speed*3.6, gust*3.6, deg
        float wind_kmh = 0, gust_kmh = 0;
        int wind_deg = 0;
        cJSON* wind_obj = cJSON_GetObjectItem(item, "wind");
        if (wind_obj) {
            cJSON* spd = cJSON_GetObjectItem(wind_obj, "speed");
            if (spd) { wind_kmh = spd->valuedouble * 3.6f; }
            cJSON* gst = cJSON_GetObjectItem(wind_obj, "gust");
            if (gst) { gust_kmh = gst->valuedouble * 3.6f; }
            cJSON* dg = cJSON_GetObjectItem(wind_obj, "deg");
            if (dg) { wind_deg = dg->valueint; }
        }
        cJSON_AddNumberToObject(out_slot, "wind_speed_kmh", wind_kmh);
        cJSON_AddNumberToObject(out_slot, "wind_gust_kmh", gust_kmh);
        cJSON_AddNumberToObject(out_slot, "wind_direction", wind_deg);

        // rain
        float rain_mm = 0;
        cJSON* rain_obj = cJSON_GetObjectItem(item, "rain");
        if (rain_obj) {
            cJSON* r3h = cJSON_GetObjectItem(rain_obj, "3h");
            if (r3h) rain_mm = r3h->valuedouble;
        }
        cJSON_AddNumberToObject(out_slot, "rain_mm", rain_mm);

        // pop (probability of precipitation) → rain_probability_pct
        cJSON* pop = cJSON_GetObjectItem(item, "pop");
        int rain_prob = pop ? (int)(pop->valuedouble * 100 + 0.5) : 0;
        cJSON_AddNumberToObject(out_slot, "rain_probability_pct", rain_prob);

        // weather[0] → description, icon
        cJSON* weather_arr = cJSON_GetObjectItem(item, "weather");
        if (weather_arr && cJSON_GetArraySize(weather_arr) > 0) {
            cJSON* w0 = cJSON_GetArrayItem(weather_arr, 0);
            cJSON* desc = cJSON_GetObjectItem(w0, "description");
            cJSON* icon = cJSON_GetObjectItem(w0, "icon");
            cJSON_AddStringToObject(out_slot, "description",
                (desc && desc->valuestring) ? desc->valuestring : "");
            cJSON_AddStringToObject(out_slot, "icon",
                (icon && icon->valuestring) ? icon->valuestring : "");
        }

        // visibility
        cJSON* vis = cJSON_GetObjectItem(item, "visibility");
        cJSON_AddNumberToObject(out_slot, "visibility_m", vis ? vis->valueint : 10000);

        // seeing_arcsec — empirical formula: max(1.5, 0.976 * (wind_kmh/10)^(2/3) + 1.0)
        float seeing = 0.976f * powf(wind_kmh / 10.0f, 0.667f) + 1.0f;
        if (seeing < 1.5f) seeing = 1.5f;
        cJSON_AddNumberToObject(out_slot, "seeing_arcsec", (int)(seeing * 10 + 0.5f) / 10.0f);

        // transparency_pct — from cloud cover
        int transparency;
        if (clouds < 20) transparency = 90;
        else if (clouds < 50) transparency = 70;
        else if (clouds < 80) transparency = 40;
        else transparency = 20;
        cJSON_AddNumberToObject(out_slot, "transparency_pct", transparency);

        // Optional: moon/sun altitude from ephemeris
        double jd = dtTxtToJD(dt_str);
        if (jd > 0 && (lat_ != 0 || lon_ != 0)) {
            MoonPhaseData mp = AstroCalc::moonPhase(jd);
            cJSON_AddNumberToObject(out_slot, "moon_illumination", (int)(mp.illumination * 10 + 0.5f) / 10.0f);

            LunarPosition lp = AstroCalc::lunarPosition(jd, lat_, lon_);
            cJSON_AddNumberToObject(out_slot, "moon_altitude", (int)(lp.altitude * 10 + 0.5) / 10.0);

            SolarPosition sp = AstroCalc::solarPosition(jd, lat_, lon_);
            cJSON_AddNumberToObject(out_slot, "sun_altitude", (int)(sp.altitude * 10 + 0.5) / 10.0);
        }

        cJSON_AddItemToArray(out_arr, out_slot);
    }

    cJSON_Delete(root);  // Done with OWM data

    // 4. Serialize and POST to server
    char* json_str = cJSON_PrintUnformatted(out_root);
    cJSON_Delete(out_root);

    if (!json_str) {
        ESP_LOGE(TAG, "ForecastPost: failed to serialize JSON");
        return;
    }

    int json_len = strlen(json_str);
    ESP_LOGI(TAG, "ForecastPost: %d slots, %d bytes JSON", slot_count, json_len);

    char post_url[128];
    snprintf(post_url, sizeof(post_url), "%s/api/device/forecast", server_url_.c_str());

    char* resp = SkyGuardHttp::AllocBuffer(512);
    if (resp) {
        bool ok = SkyGuardHttp::Post(post_url, json_str, resp, 512, 20000,
                                      server_api_key_.c_str());
        last_post_ok_ = ok;
        last_post_slots_ = slot_count;
        last_post_time_ms_ = (uint32_t)(esp_timer_get_time() / 1000);
        if (ok) {
            ESP_LOGI(TAG, "ForecastPost: OK → %s", resp);
        } else {
            ESP_LOGW(TAG, "ForecastPost: POST failed to %s", post_url);
        }
        free(resp);
    }

    cJSON_free(json_str);
}
