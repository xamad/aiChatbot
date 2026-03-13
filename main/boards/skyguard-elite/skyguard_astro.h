/**
 * SkyGuard AI - Calcoli Astronomici
 * Funzioni matematiche pure, nessuna dipendenza hardware.
 *
 * - Fase lunare (periodo sinodico)
 * - Posizione solare (bassa precisione ~0.01 deg)
 * - Orari crepuscolari (civile, nautico, astronomico)
 * - Posizione lunare e sorgere/tramonto luna
 *
 * Angoli in gradi se non specificato. Orari in ore frazionarie UT.
 * Adattato da SkyGuard Pro astro_calc.h con nomi fasi in italiano.
 */

#ifndef SKYGUARD_ASTRO_H
#define SKYGUARD_ASTRO_H

#include <math.h>
#include <cstdint>

#ifndef DEG_TO_RAD
  #define DEG_TO_RAD 0.017453292519943295
#endif
#ifndef RAD_TO_DEG
  #define RAD_TO_DEG 57.29577951308232
#endif
#ifndef TWO_PI_CONST
  #define TWO_PI_CONST 6.283185307179586
#endif

// ============================================
// Structs
// ============================================

struct MoonPhaseData {
  float  age;             // Giorni dalla luna nuova
  float  illumination;    // 0-100 %
  float  phaseAngle;      // 0-360 gradi
  uint8_t phaseIndex;     // 0-7
  const char* phaseName;
  const char* phaseIcon;  // UTF-8 moon icon char
};

struct SolarPosition {
  double ra;        // Ascensione retta (gradi)
  double dec;       // Declinazione (gradi)
  double altitude;  // Altitudine sopra orizzonte (gradi)
  double azimuth;   // Azimut (gradi, 0=N)
};

struct TwilightTimes {
  float sunrise;           // Ore UT
  float sunset;
  float civilDusk;         // Sole a -6 deg
  float civilDawn;
  float nauticalDusk;      // Sole a -12 deg
  float nauticalDawn;
  float astronomicalDusk;  // Sole a -18 deg
  float astronomicalDawn;
  bool  valid;
  bool  polarDay;          // Il sole non tramonta mai
  bool  polarNight;        // Il sole non sorge mai
};

struct LunarPosition {
  double ra;        // Ascensione retta (gradi)
  double dec;       // Declinazione (gradi)
  double altitude;  // Altitudine sopra orizzonte (gradi)
  double azimuth;   // Azimut (gradi, 0=N)
};

struct MoonRiseSet {
  float moonrise;   // Ore UT, -1 se non sorge
  float moonset;    // Ore UT, -1 se non tramonta
  bool  rises;
  bool  sets;
};

namespace AstroCalc {

  // ========== Utility ==========

  inline double normalizeDeg(double deg) {
    deg = fmod(deg, 360.0);
    if (deg < 0) deg += 360.0;
    return deg;
  }

  // ========== Fase Lunare ==========

  inline MoonPhaseData moonPhase(double JD) {
    static const char* names[] = {
      "Luna Nuova", "Crescente", "Primo Quarto", "Gibbosa Crescente",
      "Luna Piena", "Gibbosa Calante", "Ultimo Quarto", "Calante"
    };
    static const char* icons[] = {
      "\xF0\x9F\x8C\x91", "\xF0\x9F\x8C\x92", "\xF0\x9F\x8C\x93", "\xF0\x9F\x8C\x94",
      "\xF0\x9F\x8C\x95", "\xF0\x9F\x8C\x96", "\xF0\x9F\x8C\x97", "\xF0\x9F\x8C\x98"
    };

    MoonPhaseData d;
    const double synodicPeriod = 29.53058868;
    d.age = fmod(JD - 2451550.26, synodicPeriod);
    if (d.age < 0) d.age += synodicPeriod;

    d.phaseAngle = (d.age / synodicPeriod) * 360.0f;
    d.illumination = 0.5f * (1.0f - cosf(TWO_PI_CONST * d.age / synodicPeriod)) * 100.0f;

    d.phaseIndex = (uint8_t)((d.age + synodicPeriod / 16.0) / (synodicPeriod / 8.0)) % 8;
    d.phaseName = names[d.phaseIndex];
    d.phaseIcon = icons[d.phaseIndex];

    return d;
  }

  // ========== Posizione Solare ==========

  inline SolarPosition solarPosition(double JD, double lat, double lon) {
    SolarPosition s;

    double T = (JD - 2451545.0) / 36525.0;
    double M = normalizeDeg(357.5291092 + 35999.0502909 * T);
    double Mrad = M * DEG_TO_RAD;
    double C = 1.9146 * sin(Mrad) + 0.02 * sin(2.0 * Mrad) + 0.0003 * sin(3.0 * Mrad);
    double Lsun = normalizeDeg(M + C + 180.0 + 102.9372);
    double Lrad = Lsun * DEG_TO_RAD;
    double eps = (23.4393 - 0.0130 * T) * DEG_TO_RAD;

    s.ra = normalizeDeg(atan2(cos(eps) * sin(Lrad), cos(Lrad)) * RAD_TO_DEG);
    s.dec = asin(sin(eps) * sin(Lrad)) * RAD_TO_DEG;

    double GMST = normalizeDeg(280.46061837 + 360.98564736629 * (JD - 2451545.0));
    double LST = normalizeDeg(GMST + lon);
    double HA = (LST - s.ra) * DEG_TO_RAD;

    double latRad = lat * DEG_TO_RAD;
    double decRad = s.dec * DEG_TO_RAD;

    s.altitude = asin(sin(latRad) * sin(decRad) + cos(latRad) * cos(decRad) * cos(HA)) * RAD_TO_DEG;
    s.azimuth = normalizeDeg(atan2(sin(HA), cos(HA) * sin(latRad) - tan(decRad) * cos(latRad)) * RAD_TO_DEG + 180.0);

    return s;
  }

  // ========== Orari Crepuscolari ==========

  inline float riseSetTime(double JD0, double lat, double lon, double altThreshold, bool isRise) {
    double JDnoon = JD0 + 0.5;
    SolarPosition noon = solarPosition(JDnoon, lat, lon);

    double latRad = lat * DEG_TO_RAD;
    double decRad = noon.dec * DEG_TO_RAD;
    double altRad = altThreshold * DEG_TO_RAD;

    double cosH = (sin(altRad) - sin(latRad) * sin(decRad)) / (cos(latRad) * cos(decRad));

    if (cosH > 1.0) return -1.0f;
    if (cosH < -1.0) return -2.0f;

    double H = acos(cosH) * RAD_TO_DEG;

    double T = (JDnoon - 2451545.0) / 36525.0;
    double M = normalizeDeg(357.5291092 + 35999.0502909 * T);
    double Mrad = M * DEG_TO_RAD;
    double C = 1.9146 * sin(Mrad) + 0.02 * sin(2.0 * Mrad);
    double Lsun = normalizeDeg(M + C + 180.0 + 102.9372);
    double RAsun = normalizeDeg(atan2(cos((23.4393 - 0.0130 * T) * DEG_TO_RAD) * sin(Lsun * DEG_TO_RAD), cos(Lsun * DEG_TO_RAD)) * RAD_TO_DEG);

    double transit = (RAsun - normalizeDeg(280.46061837 + 360.98564736629 * (JD0 - 2451545.0) + lon)) / 15.0;
    transit = fmod(transit, 24.0);
    if (transit < 0) transit += 24.0;

    float result;
    if (isRise) {
      result = (float)(transit - H / 15.0);
    } else {
      result = (float)(transit + H / 15.0);
    }

    if (result < 0) result += 24.0f;
    if (result >= 24.0f) result -= 24.0f;

    return result;
  }

  inline TwilightTimes twilightTimes(double JD0, double lat, double lon) {
    TwilightTimes t;
    t.valid = true;
    t.polarDay = false;
    t.polarNight = false;

    float sr = riseSetTime(JD0, lat, lon, -0.833, true);
    float ss = riseSetTime(JD0, lat, lon, -0.833, false);

    if (sr == -1.0f && ss == -1.0f) {
      t.polarNight = true;
    } else if (sr == -2.0f && ss == -2.0f) {
      t.polarDay = true;
    }

    t.sunrise = (sr >= 0) ? sr : -1;
    t.sunset  = (ss >= 0) ? ss : -1;

    t.civilDawn = riseSetTime(JD0, lat, lon, -6.0, true);
    t.civilDusk = riseSetTime(JD0, lat, lon, -6.0, false);
    if (t.civilDawn < 0) t.civilDawn = -1;
    if (t.civilDusk < 0) t.civilDusk = -1;

    t.nauticalDawn = riseSetTime(JD0, lat, lon, -12.0, true);
    t.nauticalDusk = riseSetTime(JD0, lat, lon, -12.0, false);
    if (t.nauticalDawn < 0) t.nauticalDawn = -1;
    if (t.nauticalDusk < 0) t.nauticalDusk = -1;

    t.astronomicalDawn = riseSetTime(JD0, lat, lon, -18.0, true);
    t.astronomicalDusk = riseSetTime(JD0, lat, lon, -18.0, false);
    if (t.astronomicalDawn < 0) t.astronomicalDawn = -1;
    if (t.astronomicalDusk < 0) t.astronomicalDusk = -1;

    return t;
  }

  // ========== Posizione Lunare & Sorgere/Tramonto ==========

  inline LunarPosition lunarPosition(double JD, double lat, double lon) {
    LunarPosition m;

    double T = (JD - 2451545.0) / 36525.0;

    double L0 = normalizeDeg(218.3165 + 481267.8813 * T);
    double M  = normalizeDeg(134.9634 + 477198.8676 * T);
    double F  = normalizeDeg(93.2721  + 483202.0175 * T);
    double D  = normalizeDeg(297.8502 + 445267.1115 * T);
    double Ms = normalizeDeg(357.5291 + 35999.0503 * T);

    double Mrad  = M  * DEG_TO_RAD;
    double Frad  = F  * DEG_TO_RAD;
    double Drad  = D  * DEG_TO_RAD;
    double MsRad = Ms * DEG_TO_RAD;

    double eclLon = L0
      + 6.289 * sin(Mrad)
      + 1.274 * sin(2.0 * Drad - Mrad)
      + 0.658 * sin(2.0 * Drad)
      + 0.214 * sin(2.0 * Mrad)
      - 0.186 * sin(MsRad)
      - 0.114 * sin(2.0 * Frad);
    eclLon = normalizeDeg(eclLon);

    double eclLat = 5.128 * sin(Frad)
      + 0.281 * sin(Mrad + Frad)
      + 0.278 * sin(Mrad - Frad)
      + 0.173 * sin(2.0 * Drad - Frad);

    double eclLonRad = eclLon * DEG_TO_RAD;
    double eclLatRad = eclLat * DEG_TO_RAD;
    double eps = (23.4393 - 0.0130 * T) * DEG_TO_RAD;

    double sinEclLon = sin(eclLonRad);
    double cosEclLon = cos(eclLonRad);
    double cosEclLat = cos(eclLatRad);

    m.ra = normalizeDeg(atan2(
      sinEclLon * cos(eps) - tan(eclLatRad) * sin(eps),
      cosEclLon
    ) * RAD_TO_DEG);

    m.dec = asin(sin(eclLatRad) * cos(eps) + cosEclLat * sin(eps) * sinEclLon) * RAD_TO_DEG;

    double GMST = normalizeDeg(280.46061837 + 360.98564736629 * (JD - 2451545.0));
    double LST = normalizeDeg(GMST + lon);
    double HA = (LST - m.ra) * DEG_TO_RAD;

    double latRad = lat * DEG_TO_RAD;
    double decRad = m.dec * DEG_TO_RAD;

    m.altitude = asin(sin(latRad) * sin(decRad) + cos(latRad) * cos(decRad) * cos(HA)) * RAD_TO_DEG;
    m.azimuth = normalizeDeg(atan2(sin(HA), cos(HA) * sin(latRad) - tan(decRad) * cos(latRad)) * RAD_TO_DEG + 180.0);

    return m;
  }

  inline MoonRiseSet moonRiseSet(double JD0, double lat, double lon) {
    MoonRiseSet mrs;
    mrs.moonrise = -1;
    mrs.moonset = -1;
    mrs.rises = false;
    mrs.sets = false;

    const double threshold = 0.125;

    double alt[25];
    for (int h = 0; h <= 24; h++) {
      double JD = JD0 + h / 24.0;
      LunarPosition lp = lunarPosition(JD, lat, lon);
      alt[h] = lp.altitude - threshold;
    }

    for (int h = 0; h < 24; h++) {
      if (alt[h] <= 0 && alt[h + 1] > 0) {
        double frac = -alt[h] / (alt[h + 1] - alt[h]);
        mrs.moonrise = h + frac;
        mrs.rises = true;
      }
      if (alt[h] > 0 && alt[h + 1] <= 0) {
        double frac = alt[h] / (alt[h] - alt[h + 1]);
        mrs.moonset = h + frac;
        mrs.sets = true;
      }

      if (mrs.rises && mrs.sets) break;
    }

    return mrs;
  }

} // namespace AstroCalc

#endif // SKYGUARD_ASTRO_H
