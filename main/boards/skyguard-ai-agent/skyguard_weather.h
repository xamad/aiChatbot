#ifndef SKYGUARD_WEATHER_H
#define SKYGUARD_WEATHER_H

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <cstdint>
#include <string>

/**
 * SkyGuard AI - Previsioni Meteo (OpenWeatherMap)
 *
 * Fetch 6 ore di previsioni orarie da OWM Forecast API.
 * Thread-safe: mutex protegge dati tra task fetch e display.
 */

struct ForecastEntry {
    char time_str[6];    // "21:00"
    float temp;          // Celsius
    float wind_speed;    // m/s
    float wind_gust;     // m/s (gust)
    int wind_deg;        // Wind direction 0-360
    float rain_3h;       // Rain mm in 3h
    float snow_3h;       // Snow mm in 3h
    float pressure;      // hPa
    float sea_level;     // Sea-level pressure hPa
    int clouds;          // 0-100%
    int humidity;        // 0-100%
    int pop;             // Probability of precipitation 0-100%
    float visibility;    // meters
    char description[32]; // "cielo sereno"
};

struct DailyEntry {
    char day_str[4];         // "Gio", "Ven", "Sab"...
    float temp_min;          // Min temp of day
    float temp_max;          // Max temp of day
    float wind_max;          // Max wind m/s
    int clouds_avg;          // Average cloud cover 0-100%
    int humidity_avg;        // Average humidity 0-100%
    int pop_max;             // Max probability of precipitation 0-100%
    float rain_total;        // Total rain mm
    char description[32];    // Most common description
};

struct ForecastData {
    ForecastEntry entries[6];
    int count;
    DailyEntry daily[5];     // Next 5 days aggregated
    int daily_count;
    uint32_t fetch_time_ms;  // esp_timer tick when fetched
    bool valid;
    char location[32];       // City name from OWM (e.g. "Asti")
};

class SkyGuardWeather {
public:
    SkyGuardWeather();
    ~SkyGuardWeather();

    void SetApiKey(const std::string& key) { api_key_ = key; }
    void SetLocation(float lat, float lon) { lat_ = lat; lon_ = lon; }
    void SetServerConfig(const std::string& url, const std::string& api_key) {
        server_url_ = url;
        server_api_key_ = api_key;
    }

    /**
     * Start a background FreeRTOS task to fetch weather (6 entries for display).
     * Safe to call repeatedly — ignores if already fetching.
     */
    void StartFetchTask();

    /**
     * Start a background task to fetch full 5-day forecast from OWM (40 slots)
     * and POST to SQM server at /api/device/forecast.
     */
    void StartForecastPostTask();

    /**
     * Get current forecast data (thread-safe copy).
     */
    ForecastData GetForecast();

    /**
     * Get forecast as text string for AI/MCP.
     */
    std::string GetForecastText();

    bool HasData() const { return data_.valid; }
    bool IsFetching() const { return fetching_; }
    bool IsPostingForecast() const { return posting_forecast_; }
    int LastPostSlots() const { return last_post_slots_; }
    uint32_t LastPostTimeMs() const { return last_post_time_ms_; }
    bool LastPostOk() const { return last_post_ok_; }

private:
    static void FetchTaskFunc(void* arg);
    static void ForecastPostTaskFunc(void* arg);
    void DoFetch();
    void DoForecastPost();

    std::string api_key_;
    std::string server_url_;
    std::string server_api_key_;
    float lat_ = 0;
    float lon_ = 0;

    ForecastData data_ = {};
    SemaphoreHandle_t mutex_ = nullptr;
    volatile bool fetching_ = false;
    volatile bool posting_forecast_ = false;
    int last_post_slots_ = 0;
    uint32_t last_post_time_ms_ = 0;
    bool last_post_ok_ = false;
};

#endif // SKYGUARD_WEATHER_H
