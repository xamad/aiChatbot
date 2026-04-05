#include "skyguard_sky_tracker.h"
#include "skyguard_http.h"
#include <esp_log.h>
#include <esp_timer.h>
#include <cJSON.h>
#include <cstring>
#include <cstdio>
#include <cmath>
#include <algorithm>

#define TAG "SkyGuardTracker"

#ifndef DEG_TO_RAD
  #define DEG_TO_RAD 0.017453292519943295
#endif
#ifndef RAD_TO_DEG
  #define RAD_TO_DEG 57.29577951308232
#endif

SkyGuardSkyTracker::SkyGuardSkyTracker() {
    mutex_ = xSemaphoreCreateMutex();
    memset(&flight_data_, 0, sizeof(flight_data_));
    memset(&sat_data_, 0, sizeof(sat_data_));
}

SkyGuardSkyTracker::~SkyGuardSkyTracker() {
    if (mutex_) vSemaphoreDelete(mutex_);
}

void SkyGuardSkyTracker::SetLocation(float lat, float lon, float alt) {
    obs_lat_ = lat;
    obs_lon_ = lon;
    obs_alt_ = alt;
}

// =========================================================================
// HAVERSINE + BEARING
// =========================================================================

float SkyGuardSkyTracker::Haversine(float lat1, float lon1, float lat2, float lon2) {
    float dLat = (lat2 - lat1) * DEG_TO_RAD;
    float dLon = (lon2 - lon1) * DEG_TO_RAD;
    float a = sinf(dLat / 2) * sinf(dLat / 2) +
              cosf(lat1 * DEG_TO_RAD) * cosf(lat2 * DEG_TO_RAD) *
              sinf(dLon / 2) * sinf(dLon / 2);
    float c = 2.0f * atan2f(sqrtf(a), sqrtf(1.0f - a));
    return 6371.0f * c;  // Earth radius in km
}

float SkyGuardSkyTracker::Bearing(float lat1, float lon1, float lat2, float lon2) {
    float dLon = (lon2 - lon1) * DEG_TO_RAD;
    float y = sinf(dLon) * cosf(lat2 * DEG_TO_RAD);
    float x = cosf(lat1 * DEG_TO_RAD) * sinf(lat2 * DEG_TO_RAD) -
              sinf(lat1 * DEG_TO_RAD) * cosf(lat2 * DEG_TO_RAD) * cosf(dLon);
    float brng = atan2f(y, x) * RAD_TO_DEG;
    if (brng < 0) brng += 360.0f;
    return brng;
}

const char* SkyGuardSkyTracker::HeadingArrow(float heading) {
    // 8 directions
    int idx = ((int)(heading + 22.5f) / 45) % 8;
    static const char* arrows[] = {
        "\xe2\x86\x91",   // ↑ N
        "\xe2\x86\x97",   // ↗ NE
        "\xe2\x86\x92",   // → E
        "\xe2\x86\x98",   // ↘ SE
        "\xe2\x86\x93",   // ↓ S
        "\xe2\x86\x99",   // ↙ SW
        "\xe2\x86\x90",   // ← W
        "\xe2\x86\x96"    // ↖ NW
    };
    return arrows[idx];
}

const char* SkyGuardSkyTracker::BearingToCompass(float bearing) {
    int idx = ((int)(bearing + 22.5f) / 45) % 8;
    static const char* dirs[] = { "N", "NE", "E", "SE", "S", "SW", "W", "NW" };
    return dirs[idx];
}

const char* SkyGuardSkyTracker::IdentifyAircraftType(const char* callsign) {
    if (!callsign || !callsign[0]) return "";

    // Military prefixes (common European/NATO)
    static const char* military[] = {
        "RRR", "BAF", "GAF", "FAF", "MMI", "IAM", "RFR", "CNV",
        "RCH", "DUKE", "VIPER", "HAWK", "NATO", "ARNY", NULL
    };
    for (int i = 0; military[i]; i++) {
        if (strncmp(callsign, military[i], strlen(military[i])) == 0)
            return "Militare";
    }

    // Major airlines — scheduled service (ICAO 3-letter prefixes)
    static const char* airlines[] = {
        "RYR", "EZY", "AZA", "BAW", "DLH", "AFR", "KLM", "IBE",
        "VLG", "WZZ", "SAS", "AUA", "TAP", "SWR", "EIN", "BEL",
        "THY", "UAE", "QTR", "ETH", "RAM", "TUN", "NOZ", "NAX",
        "EWG", "AAL", "DAL", "UAL", "SWA", "JBU", "NKS", "ASA",
        "CPA", "SIA", "ANA", "JAL", "CCA", "CSN", "CES", "AIC",
        NULL
    };
    for (int i = 0; airlines[i]; i++) {
        if (strncmp(callsign, airlines[i], 3) == 0)
            return "Linea";
    }

    // Cargo airlines
    static const char* cargo[] = {
        "FDX", "UPS", "CLX", "GTI", "ABW", "MAS", "CKS", "BOX",
        "ICL", "QAC", "MPH", "GEC", NULL
    };
    for (int i = 0; cargo[i]; i++) {
        if (strncmp(callsign, cargo[i], 3) == 0)
            return "Cargo";
    }

    // Charter / seasonal operators
    static const char* charter[] = {
        "TOM", "NAT", "NVR", "OHY", "PGT", "SXS", "NOS", "TCX",
        "HFY", "AEA", "AGW", NULL
    };
    for (int i = 0; charter[i]; i++) {
        if (strncmp(callsign, charter[i], 3) == 0)
            return "Charter";
    }

    // If callsign has 3 letters + numbers → likely airline (scheduled)
    int letters = 0;
    for (int i = 0; callsign[i] && i < 3; i++) {
        if (callsign[i] >= 'A' && callsign[i] <= 'Z') letters++;
    }
    if (letters == 3 && callsign[3] >= '0' && callsign[3] <= '9')
        return "Linea";

    // Short callsigns or registration-style → private
    if (strlen(callsign) <= 6 && callsign[0] >= 'A' && callsign[0] <= 'Z')
        return "Privato";

    return "";
}

// =========================================================================
// OPENSKY — AIRCRAFT RADAR
// =========================================================================

void SkyGuardSkyTracker::FetchFlights() {
    if (obs_lat_ == 0 && obs_lon_ == 0) return;

    // Bounding box ±0.5° (~50km)
    float lamin = obs_lat_ - 0.5f;
    float lamax = obs_lat_ + 0.5f;
    float lomin = obs_lon_ - 0.5f;
    float lomax = obs_lon_ + 0.5f;

    char url[256];
    snprintf(url, sizeof(url),
        "https://opensky-network.org/api/states/all?"
        "lamin=%.2f&lomin=%.2f&lamax=%.2f&lomax=%.2f",
        lamin, lomin, lamax, lomax);

    const int buf_size = 8192;
    char* buf = SkyGuardHttp::AllocBuffer(buf_size);
    if (!buf) {
        ESP_LOGE(TAG, "Failed to allocate flight buffer");
        return;
    }

    if (!SkyGuardHttp::Get(url, buf, buf_size, 15000)) {
        ESP_LOGW(TAG, "OpenSky fetch failed");
        free(buf);
        return;
    }

    cJSON* root = cJSON_Parse(buf);
    free(buf);

    if (!root) {
        ESP_LOGE(TAG, "OpenSky JSON parse failed");
        return;
    }

    cJSON* states = cJSON_GetObjectItem(root, "states");
    if (!states || !cJSON_IsArray(states)) {
        ESP_LOGW(TAG, "No 'states' in OpenSky response");
        cJSON_Delete(root);
        return;
    }

    int total = cJSON_GetArraySize(states);
    ESP_LOGI(TAG, "OpenSky: %d aircraft in range", total);

    // Parse all flights and compute distance
    struct TempFlight {
        Flight f;
        float dist;
    };
    int parsed = 0;
    TempFlight* temp = (TempFlight*)malloc(sizeof(TempFlight) * (total < 64 ? total : 64));
    if (!temp) {
        cJSON_Delete(root);
        return;
    }

    for (int i = 0; i < total && parsed < 64; i++) {
        cJSON* state = cJSON_GetArrayItem(states, i);
        if (!cJSON_IsArray(state)) continue;

        int arr_size = cJSON_GetArraySize(state);
        if (arr_size < 11) continue;

        // Index: 1=callsign, 5=lon, 6=lat, 7=baro_alt, 9=velocity, 10=heading
        cJSON* callsign_j = cJSON_GetArrayItem(state, 1);
        cJSON* lon_j = cJSON_GetArrayItem(state, 5);
        cJSON* lat_j = cJSON_GetArrayItem(state, 6);
        cJSON* alt_j = cJSON_GetArrayItem(state, 7);  // baro_altitude
        cJSON* vel_j = cJSON_GetArrayItem(state, 9);
        cJSON* hdg_j = cJSON_GetArrayItem(state, 10);

        if (!lon_j || !lat_j || cJSON_IsNull(lon_j) || cJSON_IsNull(lat_j)) continue;

        TempFlight& tf = temp[parsed];
        memset(&tf, 0, sizeof(tf));

        // Callsign — trim whitespace
        if (callsign_j && callsign_j->valuestring) {
            strncpy(tf.f.callsign, callsign_j->valuestring, sizeof(tf.f.callsign) - 1);
            // Trim trailing spaces
            int len = strlen(tf.f.callsign);
            while (len > 0 && tf.f.callsign[len-1] == ' ') tf.f.callsign[--len] = '\0';
        } else {
            strcpy(tf.f.callsign, "???");
        }

        tf.f.lat = (float)lat_j->valuedouble;
        tf.f.lon = (float)lon_j->valuedouble;
        tf.f.altitude_m = (alt_j && !cJSON_IsNull(alt_j)) ? (float)alt_j->valuedouble : 0;
        tf.f.velocity_ms = (vel_j && !cJSON_IsNull(vel_j)) ? (float)vel_j->valuedouble : 0;
        tf.f.heading = (hdg_j && !cJSON_IsNull(hdg_j)) ? (float)hdg_j->valuedouble : 0;

        // Distance and bearing from observer
        tf.dist = Haversine(obs_lat_, obs_lon_, tf.f.lat, tf.f.lon);
        tf.f.distance_km = tf.dist;
        tf.f.bearing = Bearing(obs_lat_, obs_lon_, tf.f.lat, tf.f.lon);

        parsed++;
    }

    cJSON_Delete(root);

    // Sort by distance (nearest first)
    std::sort(temp, temp + parsed, [](const TempFlight& a, const TempFlight& b) {
        return a.dist < b.dist;
    });

    // Copy nearest 8
    FlightData new_data = {};
    new_data.count = (parsed < 8) ? parsed : 8;
    for (int i = 0; i < new_data.count; i++) {
        new_data.flights[i] = temp[i].f;
    }
    new_data.fetch_time_ms = (uint32_t)(esp_timer_get_time() / 1000);
    new_data.valid = true;

    free(temp);

    if (xSemaphoreTake(mutex_, pdMS_TO_TICKS(1000)) == pdTRUE) {
        flight_data_ = new_data;
        xSemaphoreGive(mutex_);
    }

    ESP_LOGI(TAG, "Flights updated: %d nearest of %d", new_data.count, total);
}

// =========================================================================
// N2YO — SATELLITE PASSES
// =========================================================================

void SkyGuardSkyTracker::FetchSatellites() {
    if (n2yo_key_.empty()) {
        ESP_LOGW(TAG, "No N2YO API key");
        return;
    }
    if (obs_lat_ == 0 && obs_lon_ == 0) return;

    // ISS = NORAD 25544, min elevation 10°, 1 day ahead
    char url[256];
    snprintf(url, sizeof(url),
        "https://api.n2yo.com/rest/v1/satellite/visualpasses/25544/"
        "%.4f/%.4f/%.0f/1/10/&apiKey=%s",
        obs_lat_, obs_lon_, obs_alt_, n2yo_key_.c_str());

    const int buf_size = 4096;
    char* buf = SkyGuardHttp::AllocBuffer(buf_size);
    if (!buf) return;

    if (!SkyGuardHttp::Get(url, buf, buf_size, 15000)) {
        ESP_LOGW(TAG, "N2YO fetch failed");
        free(buf);
        return;
    }

    cJSON* root = cJSON_Parse(buf);
    free(buf);

    if (!root) {
        ESP_LOGE(TAG, "N2YO JSON parse failed");
        return;
    }

    // Get satellite name from "info" object
    char sat_name[20] = "ISS";
    cJSON* info = cJSON_GetObjectItem(root, "info");
    if (info) {
        cJSON* name_j = cJSON_GetObjectItem(info, "satname");
        if (name_j && name_j->valuestring) {
            strncpy(sat_name, name_j->valuestring, sizeof(sat_name) - 1);
        }
    }

    cJSON* passes = cJSON_GetObjectItem(root, "passes");
    if (!passes || !cJSON_IsArray(passes)) {
        ESP_LOGW(TAG, "No passes in N2YO response");
        cJSON_Delete(root);
        return;
    }

    SatelliteData new_data = {};
    int count = cJSON_GetArraySize(passes);
    if (count > 6) count = 6;
    new_data.count = count;

    for (int i = 0; i < count; i++) {
        cJSON* pass = cJSON_GetArrayItem(passes, i);
        SatPass& sp = new_data.passes[i];

        strncpy(sp.name, sat_name, sizeof(sp.name) - 1);

        cJSON* startUTC = cJSON_GetObjectItem(pass, "startUTC");
        cJSON* maxEl = cJSON_GetObjectItem(pass, "maxEl");
        cJSON* mag = cJSON_GetObjectItem(pass, "mag");
        cJSON* duration = cJSON_GetObjectItem(pass, "duration");

        if (startUTC) {
            // Convert Unix timestamp to hours UT
            uint32_t ts = (uint32_t)startUTC->valuedouble;
            uint32_t day_seconds = ts % 86400;
            sp.start_hour = day_seconds / 3600;
            sp.start_min = (day_seconds % 3600) / 60;
            sp.start_utc = sp.start_hour + sp.start_min / 60.0f;
        }
        if (maxEl) sp.max_elevation = (float)maxEl->valuedouble;
        if (mag) sp.magnitude = (float)mag->valuedouble;
        if (duration) sp.duration_sec = duration->valueint;

        cJSON* startAz = cJSON_GetObjectItem(pass, "startAz");
        cJSON* maxAz = cJSON_GetObjectItem(pass, "maxAz");
        cJSON* endAz = cJSON_GetObjectItem(pass, "endAz");
        if (startAz) sp.start_az = (float)startAz->valuedouble;
        if (maxAz) sp.max_az = (float)maxAz->valuedouble;
        if (endAz) sp.end_az = (float)endAz->valuedouble;
    }

    new_data.fetch_time_ms = (uint32_t)(esp_timer_get_time() / 1000);
    new_data.valid = true;

    cJSON_Delete(root);

    if (xSemaphoreTake(mutex_, pdMS_TO_TICKS(1000)) == pdTRUE) {
        sat_data_ = new_data;
        xSemaphoreGive(mutex_);
    }

    ESP_LOGI(TAG, "Satellite passes updated: %d", count);
}

// =========================================================================
// GETTERS (thread-safe)
// =========================================================================

FlightData SkyGuardSkyTracker::GetFlights() {
    FlightData copy = {};
    if (xSemaphoreTake(mutex_, pdMS_TO_TICKS(500)) == pdTRUE) {
        copy = flight_data_;
        xSemaphoreGive(mutex_);
    }
    return copy;
}

SatelliteData SkyGuardSkyTracker::GetSatellites() {
    SatelliteData copy = {};
    if (xSemaphoreTake(mutex_, pdMS_TO_TICKS(500)) == pdTRUE) {
        copy = sat_data_;
        xSemaphoreGive(mutex_);
    }
    return copy;
}

std::string SkyGuardSkyTracker::GetFlightsText() {
    FlightData d = GetFlights();
    if (!d.valid || d.count == 0) {
        return "Nessun aereo rilevato";
    }

    std::string text;
    for (int i = 0; i < d.count; i++) {
        auto& f = d.flights[i];
        char line[128];
        int fl = (int)(f.altitude_m / 30.48f);  // meters to flight level (×100ft)
        snprintf(line, sizeof(line),
            "%s %s %.1fkm FL%03d %s\n",
            f.callsign, BearingToCompass(f.bearing),
            f.distance_km, fl, HeadingArrow(f.heading));
        text += line;
    }
    return text;
}

std::string SkyGuardSkyTracker::GetSatellitesText() {
    SatelliteData d = GetSatellites();
    if (!d.valid || d.count == 0) {
        return "Nessun passaggio satelliti previsto";
    }

    std::string text;
    for (int i = 0; i < d.count; i++) {
        auto& s = d.passes[i];
        char line[128];
        snprintf(line, sizeof(line),
            "%s %02d:%02d Max %.0f Mag %.1f %dmin\n",
            s.name, s.start_hour, s.start_min,
            s.max_elevation, s.magnitude, s.duration_sec / 60);
        text += line;
    }
    return text;
}
