"""
Convertitore Plugin - Conversione valute, unità di misura, temperature
"""

import requests
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Tassi di cambio approssimativi (aggiornabili via API)
EXCHANGE_RATES = {
    "EUR": 1.0,
    "USD": 1.08,
    "GBP": 0.85,
    "CHF": 0.95,
    "JPY": 162.0,
    "CNY": 7.8,
    "AUD": 1.65,
    "CAD": 1.47,
}

# Conversioni unità
UNIT_CONVERSIONS = {
    # Lunghezza (base: metri)
    "km_m": 1000,
    "m_cm": 100,
    "m_mm": 1000,
    "mi_km": 1.60934,  # miglia -> km
    "ft_m": 0.3048,     # piedi -> metri
    "in_cm": 2.54,      # pollici -> cm
    "yd_m": 0.9144,     # iarde -> metri

    # Peso (base: kg)
    "kg_g": 1000,
    "lb_kg": 0.453592,  # libbre -> kg
    "oz_g": 28.3495,    # once -> grammi

    # Volume (base: litri)
    "l_ml": 1000,
    "gal_l": 3.78541,   # galloni US -> litri

    # Velocità
    "kmh_mph": 0.621371,  # km/h -> mph
    "mph_kmh": 1.60934,   # mph -> km/h
}

CONVERTITORE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "convertitore",
        "description": (
            "Converte valute, unità di misura, temperature."
            "Usare quando: quanti dollari, converti miglia in km, "
            "fahrenheit in celsius, libbre in kg, euro in dollari"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number",
                    "description": "Valore da convertire"
                },
                "from_unit": {
                    "type": "string",
                    "description": "Unità di partenza (EUR, USD, km, mi, kg, lb, C, F, ecc.)"
                },
                "to_unit": {
                    "type": "string",
                    "description": "Unità di destinazione"
                },
                "type": {
                    "type": "string",
                    "description": "Tipo conversione: currency, length, weight, temperature, speed",
                    "enum": ["currency", "length", "weight", "temperature", "speed", "volume"]
                }
            },
            "required": ["value", "from_unit", "to_unit"],
        },
    },
}


def format_number(n: float, decimals: int = 2) -> str:
    """Formatta numero"""
    if abs(n - round(n)) < 0.01:
        return str(int(round(n)))
    return f"{n:.{decimals}f}"


def convert_currency(value: float, from_curr: str, to_curr: str) -> tuple:
    """Converte valute"""
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    # Alias comuni
    aliases = {
        "EURO": "EUR", "EUROS": "EUR", "€": "EUR",
        "DOLLARO": "USD", "DOLLARI": "USD", "$": "USD",
        "STERLINA": "GBP", "STERLINE": "GBP", "£": "GBP",
        "FRANCO": "CHF", "FRANCHI": "CHF",
        "YEN": "JPY", "¥": "JPY",
        "YUAN": "CNY", "RENMINBI": "CNY",
    }

    from_curr = aliases.get(from_curr, from_curr)
    to_curr = aliases.get(to_curr, to_curr)

    if from_curr not in EXCHANGE_RATES:
        return None, f"Valuta '{from_curr}' non supportata"
    if to_curr not in EXCHANGE_RATES:
        return None, f"Valuta '{to_curr}' non supportata"

    # Converti via EUR
    eur_value = value / EXCHANGE_RATES[from_curr]
    result = eur_value * EXCHANGE_RATES[to_curr]

    return result, None


def convert_temperature(value: float, from_unit: str, to_unit: str) -> tuple:
    """Converte temperature"""
    from_unit = from_unit.upper()[0] if from_unit else ""
    to_unit = to_unit.upper()[0] if to_unit else ""

    if from_unit == "C":
        if to_unit == "F":
            return (value * 9/5) + 32, None
        elif to_unit == "K":
            return value + 273.15, None
    elif from_unit == "F":
        if to_unit == "C":
            return (value - 32) * 5/9, None
        elif to_unit == "K":
            return (value - 32) * 5/9 + 273.15, None
    elif from_unit == "K":
        if to_unit == "C":
            return value - 273.15, None
        elif to_unit == "F":
            return (value - 273.15) * 9/5 + 32, None

    return None, "Conversione temperatura non supportata"


def convert_length(value: float, from_unit: str, to_unit: str) -> tuple:
    """Converte lunghezze"""
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()

    # Normalizza alias
    aliases = {
        "chilometri": "km", "chilometro": "km", "kilometers": "km",
        "metri": "m", "metro": "m", "meters": "m",
        "centimetri": "cm", "centimetro": "cm",
        "millimetri": "mm", "millimetro": "mm",
        "miglia": "mi", "miglio": "mi", "miles": "mi", "mile": "mi",
        "piedi": "ft", "piede": "ft", "feet": "ft", "foot": "ft",
        "pollici": "in", "pollice": "in", "inches": "in", "inch": "in",
        "iarde": "yd", "iarda": "yd", "yards": "yd", "yard": "yd",
    }

    from_unit = aliases.get(from_unit, from_unit)
    to_unit = aliases.get(to_unit, to_unit)

    # Conversioni dirette
    conversions = {
        ("mi", "km"): 1.60934,
        ("km", "mi"): 0.621371,
        ("ft", "m"): 0.3048,
        ("m", "ft"): 3.28084,
        ("in", "cm"): 2.54,
        ("cm", "in"): 0.393701,
        ("yd", "m"): 0.9144,
        ("m", "yd"): 1.09361,
        ("km", "m"): 1000,
        ("m", "km"): 0.001,
        ("m", "cm"): 100,
        ("cm", "m"): 0.01,
    }

    key = (from_unit, to_unit)
    if key in conversions:
        return value * conversions[key], None

    return None, f"Conversione da {from_unit} a {to_unit} non supportata"


def convert_weight(value: float, from_unit: str, to_unit: str) -> tuple:
    """Converte pesi"""
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()

    aliases = {
        "chilogrammi": "kg", "chilogrammo": "kg", "chili": "kg",
        "grammi": "g", "grammo": "g",
        "libbre": "lb", "libbra": "lb", "pounds": "lb", "pound": "lb",
        "once": "oz", "oncia": "oz", "ounces": "oz", "ounce": "oz",
    }

    from_unit = aliases.get(from_unit, from_unit)
    to_unit = aliases.get(to_unit, to_unit)

    conversions = {
        ("lb", "kg"): 0.453592,
        ("kg", "lb"): 2.20462,
        ("oz", "g"): 28.3495,
        ("g", "oz"): 0.035274,
        ("kg", "g"): 1000,
        ("g", "kg"): 0.001,
    }

    key = (from_unit, to_unit)
    if key in conversions:
        return value * conversions[key], None

    return None, f"Conversione da {from_unit} a {to_unit} non supportata"


@register_function("convertitore", CONVERTITORE_FUNCTION_DESC, ToolType.WAIT)
def convertitore(conn, value: float, from_unit: str, to_unit: str, type: str = None):
    logger.bind(tag=TAG).info(f"Convertitore: {value} {from_unit} -> {to_unit} (type={type})")

    from_unit = from_unit.strip()
    to_unit = to_unit.strip()

    result = None
    error = None

    # Auto-detect tipo se non specificato
    currency_units = ["EUR", "USD", "GBP", "CHF", "JPY", "CNY", "EURO", "DOLLARO", "DOLLARI", "STERLINA", "€", "$", "£"]
    temp_units = ["C", "F", "K", "CELSIUS", "FAHRENHEIT", "KELVIN", "GRADI"]
    length_units = ["KM", "M", "CM", "MM", "MI", "FT", "IN", "YD", "MIGLIA", "METRI", "CHILOMETRI", "PIEDI", "POLLICI"]
    weight_units = ["KG", "G", "LB", "OZ", "LIBBRE", "CHILI", "GRAMMI", "ONCE"]

    from_upper = from_unit.upper()

    if type == "currency" or from_upper in currency_units:
        result, error = convert_currency(value, from_unit, to_unit)
        if result is not None:
            spoken = f"{format_number(value)} {from_unit} sono {format_number(result)} {to_unit}"
    elif type == "temperature" or from_upper in temp_units or "GRAD" in from_upper:
        result, error = convert_temperature(value, from_unit, to_unit)
        if result is not None:
            spoken = f"{format_number(value)} gradi {from_unit} sono {format_number(result)} gradi {to_unit}"
    elif type == "length" or from_upper in length_units:
        result, error = convert_length(value, from_unit, to_unit)
        if result is not None:
            spoken = f"{format_number(value)} {from_unit} sono {format_number(result)} {to_unit}"
    elif type == "weight" or from_upper in weight_units:
        result, error = convert_weight(value, from_unit, to_unit)
        if result is not None:
            spoken = f"{format_number(value)} {from_unit} sono {format_number(result)} {to_unit}"
    else:
        # Prova tutte le conversioni
        for converter in [convert_currency, convert_length, convert_weight, convert_temperature]:
            result, error = converter(value, from_unit, to_unit)
            if result is not None:
                spoken = f"{format_number(value)} {from_unit} sono {format_number(result)} {to_unit}"
                break

    if result is not None:
        return ActionResponse(Action.RESPONSE,
            f"{format_number(value)} {from_unit} = {format_number(result)} {to_unit}",
            spoken)
    else:
        return ActionResponse(Action.RESPONSE,
            error or "Conversione non supportata",
            "Mi dispiace, non so fare questa conversione")
