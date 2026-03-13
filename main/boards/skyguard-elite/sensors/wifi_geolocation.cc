#include "wifi_geolocation.h"
#include <esp_log.h>
#include <esp_wifi.h>
#include <esp_http_client.h>
#include <cstring>
#include <cstdio>
#include <cstdlib>

#define TAG "WiFiGeo"

// Buffer for HTTP response
static char http_response_buf[2048];
static int http_response_len = 0;

static esp_err_t http_event_handler(esp_http_client_event_t *evt) {
    switch (evt->event_id) {
        case HTTP_EVENT_ON_DATA:
            if (http_response_len + evt->data_len < (int)sizeof(http_response_buf) - 1) {
                memcpy(http_response_buf + http_response_len, evt->data, evt->data_len);
                http_response_len += evt->data_len;
                http_response_buf[http_response_len] = '\0';
            }
            break;
        default:
            break;
    }
    return ESP_OK;
}

WifiGeolocation::WifiGeolocation() {
    memset(&location_, 0, sizeof(location_));
    location_.source = "none";
}

void WifiGeolocation::SetGoogleApiKey(const char* key) {
    strncpy(google_api_key_, key, sizeof(google_api_key_) - 1);
    google_api_key_[sizeof(google_api_key_) - 1] = '\0';
}

void WifiGeolocation::SetFallbackLocation(float lat, float lon) {
    fallback_lat_ = lat;
    fallback_lon_ = lon;
}

bool WifiGeolocation::TryWifiGeolocation() {
    if (google_api_key_[0] == '\0') {
        ESP_LOGW(TAG, "No Google API key configured");
        return false;
    }

    ESP_LOGI(TAG, "Scanning WiFi APs for geolocation...");

    // Scan WiFi access points
    wifi_scan_config_t scan_config = {
        .ssid = nullptr,
        .bssid = nullptr,
        .channel = 0,
        .show_hidden = false,
        .scan_type = WIFI_SCAN_TYPE_ACTIVE,
        .scan_time = {
            .active = { .min = 100, .max = 300 },
        },
    };

    esp_err_t ret = esp_wifi_scan_start(&scan_config, true);  // blocking
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "WiFi scan failed: %s", esp_err_to_name(ret));
        return false;
    }

    uint16_t ap_count = 0;
    esp_wifi_scan_get_ap_num(&ap_count);
    if (ap_count == 0) {
        ESP_LOGW(TAG, "No APs found");
        return false;
    }

    // Get max 10 APs
    uint16_t max_aps = (ap_count > 10) ? 10 : ap_count;
    wifi_ap_record_t* ap_records = (wifi_ap_record_t*)malloc(max_aps * sizeof(wifi_ap_record_t));
    if (!ap_records) return false;

    esp_wifi_scan_get_ap_records(&max_aps, ap_records);

    // Build Google Geolocation API request body
    // Format: {"wifiAccessPoints":[{"macAddress":"XX:XX:XX:XX:XX:XX","signalStrength":-65}, ...]}
    char body[1024];
    int pos = 0;
    pos += snprintf(body + pos, sizeof(body) - pos, "{\"wifiAccessPoints\":[");

    for (int i = 0; i < max_aps; i++) {
        if (i > 0) pos += snprintf(body + pos, sizeof(body) - pos, ",");
        pos += snprintf(body + pos, sizeof(body) - pos,
            "{\"macAddress\":\"%02X:%02X:%02X:%02X:%02X:%02X\",\"signalStrength\":%d}",
            ap_records[i].bssid[0], ap_records[i].bssid[1], ap_records[i].bssid[2],
            ap_records[i].bssid[3], ap_records[i].bssid[4], ap_records[i].bssid[5],
            ap_records[i].rssi);
    }
    pos += snprintf(body + pos, sizeof(body) - pos, "]}");

    free(ap_records);

    ESP_LOGI(TAG, "Sending %d APs to Google Geolocation API", max_aps);

    // Call Google Geolocation API
    char url[128];
    snprintf(url, sizeof(url),
        "https://www.googleapis.com/geolocation/v1/geolocate?key=%s", google_api_key_);

    char response[512];
    if (!HttpPost(url, body, response, sizeof(response))) {
        ESP_LOGE(TAG, "Google API call failed");
        return false;
    }

    // Parse response: {"location":{"lat":44.9019,"lng":8.1662},"accuracy":30.5}
    // Simple JSON parsing without cJSON dependency
    char* lat_str = strstr(response, "\"lat\":");
    char* lng_str = strstr(response, "\"lng\":");
    char* acc_str = strstr(response, "\"accuracy\":");

    if (!lat_str || !lng_str) {
        ESP_LOGE(TAG, "Failed to parse Google response: %s", response);
        return false;
    }

    location_.latitude = strtof(lat_str + 6, nullptr);
    location_.longitude = strtof(lng_str + 6, nullptr);
    location_.accuracy = acc_str ? strtof(acc_str + 11, nullptr) : 100.0f;
    location_.source = "wifi_google";
    location_.valid = true;

    ESP_LOGI(TAG, "WiFi geolocation: %.6f, %.6f (accuracy=%.0fm)",
             location_.latitude, location_.longitude, location_.accuracy);
    return true;
}

bool WifiGeolocation::TryIpGeolocation() {
    ESP_LOGI(TAG, "Trying IP-based geolocation...");

    char response[512];
    if (!HttpGet("http://ip-api.com/json/?fields=lat,lon,city,status", response, sizeof(response))) {
        ESP_LOGE(TAG, "IP geolocation API call failed");
        return false;
    }

    // Parse: {"status":"success","lat":44.9019,"lon":8.1662,"city":"Asti"}
    if (!strstr(response, "\"success\"")) {
        ESP_LOGE(TAG, "IP geolocation failed: %s", response);
        return false;
    }

    char* lat_str = strstr(response, "\"lat\":");
    char* lon_str = strstr(response, "\"lon\":");

    if (!lat_str || !lon_str) return false;

    location_.latitude = strtof(lat_str + 6, nullptr);
    location_.longitude = strtof(lon_str + 6, nullptr);
    location_.accuracy = 5000.0f;  // ~5km typical IP accuracy
    location_.source = "ip";
    location_.valid = true;

    ESP_LOGI(TAG, "IP geolocation: %.4f, %.4f (accuracy ~5km)", location_.latitude, location_.longitude);
    return true;
}

bool WifiGeolocation::ResolveFallback() {
    // Chain: WiFi Google → IP → Static fallback
    ESP_LOGI(TAG, "Starting geolocation fallback chain...");

    // 1. Try WiFi (most accurate, ~20-50m)
    if (TryWifiGeolocation()) {
        ESP_LOGI(TAG, "Resolved via WiFi Google (%s, accuracy=%.0fm)",
                 location_.source, location_.accuracy);
        return true;
    }

    // 2. Try IP (less accurate, ~5km)
    if (TryIpGeolocation()) {
        ESP_LOGI(TAG, "Resolved via IP geolocation (%s)", location_.source);
        return true;
    }

    // 3. Static fallback
    ESP_LOGW(TAG, "All geolocation methods failed — using static fallback");
    location_.latitude = fallback_lat_;
    location_.longitude = fallback_lon_;
    location_.accuracy = 10000.0f;
    location_.source = "fallback";
    location_.valid = true;
    return true;  // Always "succeeds" with fallback
}

bool WifiGeolocation::HttpPost(const char* url, const char* body, char* response, int max_len) {
    http_response_len = 0;
    memset(http_response_buf, 0, sizeof(http_response_buf));

    esp_http_client_config_t config = {
        .url = url,
        .method = HTTP_METHOD_POST,
        .timeout_ms = 10000,
        .event_handler = http_event_handler,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) return false;

    esp_http_client_set_header(client, "Content-Type", "application/json");
    esp_http_client_set_post_field(client, body, strlen(body));

    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    if (err != ESP_OK || status != 200) {
        ESP_LOGE(TAG, "HTTP POST failed: err=%s, status=%d", esp_err_to_name(err), status);
        return false;
    }

    int copy_len = (http_response_len < max_len - 1) ? http_response_len : max_len - 1;
    memcpy(response, http_response_buf, copy_len);
    response[copy_len] = '\0';
    return true;
}

bool WifiGeolocation::HttpGet(const char* url, char* response, int max_len) {
    http_response_len = 0;
    memset(http_response_buf, 0, sizeof(http_response_buf));

    esp_http_client_config_t config = {
        .url = url,
        .method = HTTP_METHOD_GET,
        .timeout_ms = 10000,
        .event_handler = http_event_handler,
    };

    esp_http_client_handle_t client = esp_http_client_init(&config);
    if (!client) return false;

    esp_err_t err = esp_http_client_perform(client);
    int status = esp_http_client_get_status_code(client);
    esp_http_client_cleanup(client);

    if (err != ESP_OK || status != 200) {
        ESP_LOGE(TAG, "HTTP GET failed: err=%s, status=%d", esp_err_to_name(err), status);
        return false;
    }

    int copy_len = (http_response_len < max_len - 1) ? http_response_len : max_len - 1;
    memcpy(response, http_response_buf, copy_len);
    response[copy_len] = '\0';
    return true;
}
