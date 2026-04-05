#ifndef SKYGUARD_SKY_TRACKER_H
#define SKYGUARD_SKY_TRACKER_H

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <cstdint>
#include <string>

/**
 * SkyGuard AI - Sky Tracker (Aerei + Satelliti)
 *
 * Aerei: OpenSky Network API (anonimo, no key)
 * Satelliti: N2YO API (richiede key)
 */

struct Flight {
    char callsign[10];      // "RYR1234"
    float lat;
    float lon;
    float altitude_m;       // Geometric altitude meters
    float velocity_ms;      // Ground speed m/s
    float heading;          // Track angle 0-360
    float distance_km;      // From observer (haversine)
    float bearing;          // From observer 0-360
};

struct SatPass {
    char name[20];          // "ISS" / "STARLINK-1234"
    float start_utc;        // Start time hours UT
    float max_elevation;    // Max elevation degrees
    float magnitude;        // Brightness (negative = bright)
    float start_az;         // Start azimuth (0=N, 90=E, 180=S, 270=W)
    float max_az;           // Max elevation azimuth
    float end_az;           // End azimuth
    int duration_sec;       // Pass duration
    int start_hour;         // For display
    int start_min;
};

struct FlightData {
    Flight flights[8];      // Max 8 nearest
    int count;
    uint32_t fetch_time_ms;
    bool valid;
};

struct SatelliteData {
    SatPass passes[6];      // Max 6 passes
    int count;
    uint32_t fetch_time_ms;
    bool valid;
};

class SkyGuardSkyTracker {
public:
    SkyGuardSkyTracker();
    ~SkyGuardSkyTracker();

    void SetN2yoApiKey(const std::string& key) { n2yo_key_ = key; }
    void SetLocation(float lat, float lon, float alt = 0);

    /**
     * Fetch nearby flights from OpenSky (no API key needed).
     * Blocking call — run from timer task or FreeRTOS task.
     */
    void FetchFlights();

    /**
     * Fetch satellite passes from N2YO.
     * Blocking call.
     */
    void FetchSatellites();

    FlightData GetFlights();
    SatelliteData GetSatellites();

    std::string GetFlightsText();
    std::string GetSatellitesText();

    bool HasFlights() const { return flight_data_.valid; }
    bool HasSatellites() const { return sat_data_.valid; }

    /**
     * Direction arrow character based on heading.
     */
    static const char* HeadingArrow(float heading);

    /**
     * Compass direction string (N, NE, E, etc.) from bearing.
     */
    static const char* BearingToCompass(float bearing);

    /**
     * Identify aircraft type from callsign prefix.
     * Returns "Linea", "Charter", "Cargo", "Privato", "Militare", or "".
     */
    static const char* IdentifyAircraftType(const char* callsign);

private:
    // Haversine distance in km
    static float Haversine(float lat1, float lon1, float lat2, float lon2);
    // Initial bearing in degrees
    static float Bearing(float lat1, float lon1, float lat2, float lon2);

    std::string n2yo_key_;
    float obs_lat_ = 0;
    float obs_lon_ = 0;
    float obs_alt_ = 0;

    FlightData flight_data_ = {};
    SatelliteData sat_data_ = {};
    SemaphoreHandle_t mutex_ = nullptr;
};

#endif // SKYGUARD_SKY_TRACKER_H
