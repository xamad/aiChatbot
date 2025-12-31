"""
Meteo Italia Plugin - Funziona per TUTTE le città italiane (anche Asti!)
Usa Open-Meteo (gratuito, senza API key)
"""

import requests
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

METEO_ITALIA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "meteo_italia",
        "description": (
            "获取意大利城市天气 / Ottieni il meteo per qualsiasi città italiana. "
            "当用户询问意大利任何城市的天气时使用。"
            "Use when user asks: 'che tempo fa a...', 'meteo...', 'weather in Italy...'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Nome della città, es: Asti, Torino, Roma",
                },
            },
            "required": ["city"],
        },
    },
}

WMO_CODES = {
    0: "Sereno", 1: "Prevalentemente sereno", 2: "Parzialmente nuvoloso",
    3: "Coperto", 45: "Nebbia", 48: "Nebbia con brina",
    51: "Pioggerella leggera", 53: "Pioggerella", 55: "Pioggerella intensa",
    61: "Pioggia leggera", 63: "Pioggia", 65: "Pioggia intensa",
    71: "Neve leggera", 73: "Neve", 75: "Neve intensa",
    80: "Rovesci leggeri", 81: "Rovesci", 82: "Rovesci violenti",
    95: "Temporale", 96: "Temporale con grandine", 99: "Temporale forte",
}


def geocode_city(city: str) -> dict:
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city, "count": 3, "language": "it"}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if not data.get("results"):
            return None

        # Preferisci Italia
        for r in data["results"]:
            if "Italia" in r.get("country", "") or "Italy" in r.get("country", ""):
                return {"name": r["name"], "region": r.get("admin1", ""),
                        "lat": r["latitude"], "lon": r["longitude"]}

        r = data["results"][0]
        return {"name": r["name"], "region": r.get("admin1", ""),
                "lat": r["latitude"], "lon": r["longitude"]}
    except Exception as e:
        logger.bind(tag=TAG).error(f"Geocoding error: {e}")
        return None


def get_weather(lat: float, lon: float) -> dict:
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat, "longitude": lon,
            "current": ["temperature_2m", "weather_code", "wind_speed_10m"],
            "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min"],
            "timezone": "Europe/Rome", "forecast_days": 5
        }
        response = requests.get(url, params=params, timeout=10)
        return response.json()
    except:
        return None


@register_function("meteo_italia", METEO_ITALIA_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def meteo_italia(conn, city: str):
    if not city:
        return ActionResponse(Action.REQLLM, "Specifica una città", None)

    location = geocode_city(city)
    if not location:
        return ActionResponse(Action.REQLLM, f"Città '{city}' non trovata", None)

    weather = get_weather(location["lat"], location["lon"])
    if not weather:
        return ActionResponse(Action.REQLLM, "Errore meteo, riprova", None)

    current = weather.get("current", {})
    daily = weather.get("daily", {})

    temp = current.get("temperature_2m", "?")
    code = current.get("weather_code", 0)
    desc = WMO_CODES.get(code, "Sconosciuto")
    wind = current.get("wind_speed_10m", "?")

    loc_name = f"{location['name']}, {location['region']}"

    report = f"**Meteo {loc_name}**\n\n"
    report += f"Ora: {desc}, {temp}°C, vento {wind} km/h\n\n"
    report += "Prossimi giorni:\n"

    days = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    for i, date in enumerate(daily.get("time", [])[:5]):
        from datetime import datetime
        dt = datetime.strptime(date, "%Y-%m-%d")
        day = days[dt.weekday()]
        tmin = daily["temperature_2m_min"][i]
        tmax = daily["temperature_2m_max"][i]
        code = daily["weather_code"][i]
        desc = WMO_CODES.get(code, "")
        report += f"- {day}: {desc}, {tmin}°-{tmax}°C\n"

    return ActionResponse(Action.REQLLM, report, None)
