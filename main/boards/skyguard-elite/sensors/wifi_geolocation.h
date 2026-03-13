#ifndef WIFI_GEOLOCATION_H
#define WIFI_GEOLOCATION_H

#include <cstdint>

// Geolocation result
struct GeoLocation {
    float latitude;
    float longitude;
    float accuracy;       // meters
    const char* source;   // "gps", "wifi_google", "ip", "fallback"
    bool valid;
};

// Fallback chain: GPS → WiFi Google Geolocation → IP Geolocation → Static
class WifiGeolocation {
public:
    WifiGeolocation();

    // Set Google API key (from NVS or config)
    void SetGoogleApiKey(const char* key);

    // Set static fallback coordinates (from config)
    void SetFallbackLocation(float lat, float lon);

    // Try WiFi-based geolocation (Google Geolocation API)
    // Scans nearby APs and sends to Google for positioning
    bool TryWifiGeolocation();

    // Try IP-based geolocation (ip-api.com, no key needed)
    bool TryIpGeolocation();

    // Get result (from any successful method)
    const GeoLocation& GetLocation() const { return location_; }

    // Full fallback chain (call when GPS has no fix)
    // Returns true if any method succeeded
    bool ResolveFallback();

private:
    char google_api_key_[64] = {};
    float fallback_lat_ = 44.9019f;   // Asti default
    float fallback_lon_ = 8.1662f;
    GeoLocation location_ = {};

    // HTTP helper (uses esp_http_client)
    bool HttpPost(const char* url, const char* body, char* response, int max_len);
    bool HttpGet(const char* url, char* response, int max_len);
};

#endif // WIFI_GEOLOCATION_H
