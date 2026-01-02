"""
Routine Mattutina Plugin - Briefing giornaliero personalizzato
Combina meteo, notizie, agenda in un unico comando
"""

import asyncio
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType
from core.handle.sendAudioHandle import send_stt_message
from core.utils.dialogue import Message

TAG = __name__
logger = setup_logging()

# Frasi di saluto per ora del giorno
GREETINGS = {
    "morning": [
        "Buongiorno! Ecco il tuo briefing mattutino.",
        "Buongiorno! Iniziamo bene questa giornata.",
        "Buongiorno! Ecco cosa c'è da sapere oggi.",
    ],
    "afternoon": [
        "Buon pomeriggio! Ecco un aggiornamento.",
        "Ciao! Ecco le ultime novità.",
    ],
    "evening": [
        "Buonasera! Ecco il riepilogo della giornata.",
        "Buonasera! Come è andata oggi?",
    ],
}

ROUTINE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "routine_mattutina",
        "description": (
            "Fornisce briefing giornaliero con meteo, data, notizie. Usa quando l'utente dice: "
            "'buongiorno', 'com'è la giornata?', 'briefing mattutino', 'cosa c'è oggi?', "
            "'aggiornamento giornaliero', 'riassunto del giorno'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "include_weather": {
                    "type": "boolean",
                    "description": "Includere meteo (default: true)"
                },
                "include_news": {
                    "type": "boolean",
                    "description": "Includere notizie (default: true)"
                },
                "city": {
                    "type": "string",
                    "description": "Città per il meteo"
                }
            },
            "required": [],
        },
    },
}


def get_time_of_day() -> str:
    """Determina momento della giornata"""
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 18:
        return "afternoon"
    else:
        return "evening"


def get_day_info() -> str:
    """Restituisce info su data e giorno"""
    now = datetime.now()
    days = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    months = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
              "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

    day_name = days[now.weekday()]
    day_num = now.day
    month_name = months[now.month - 1]
    year = now.year

    return f"Oggi è {day_name} {day_num} {month_name} {year}"


def get_motivational_quote() -> str:
    """Frase motivazionale casuale"""
    import random
    quotes = [
        "Ogni giorno è una nuova opportunità.",
        "Fai del tuo meglio, il resto verrà.",
        "Un passo alla volta, raggiungerai grandi traguardi.",
        "Oggi sarà una bella giornata!",
        "Sorridi, il mondo sorriderà con te.",
        "La positività attira cose positive.",
        "Sei più forte di quanto pensi.",
        "Affronta oggi con coraggio e determinazione.",
    ]
    return random.choice(quotes)


@register_function("routine_mattutina", ROUTINE_FUNCTION_DESC, ToolType.WAIT)
def routine_mattutina(conn, include_weather: bool = True, include_news: bool = True, city: str = None):
    logger.bind(tag=TAG).info(f"Routine: weather={include_weather}, news={include_news}, city={city}")

    import random

    # Costruisci il briefing
    time_of_day = get_time_of_day()
    greeting = random.choice(GREETINGS[time_of_day])

    # Info data
    day_info = get_day_info()

    # Componi risposta
    parts = [greeting, day_info]

    # Se mattina, aggiungi frase motivazionale
    if time_of_day == "morning":
        parts.append(get_motivational_quote())

    response_text = " ".join(parts)

    # Suggerisci di chiedere meteo/notizie
    if include_weather and city:
        response_text += f" Vuoi che ti dica il meteo a {city}?"
    elif include_weather:
        response_text += " Vuoi sapere che tempo fa?"

    if include_news:
        response_text += " Posso anche leggerti le ultime notizie."

    return ActionResponse(Action.RESPONSE, response_text, response_text)
