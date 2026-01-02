"""
Intrattenitore Anziani Plugin - Modalità compagnia per anziani
Propone attività variegate, tiene compagnia, suggerisce cambiamenti
"""

import random
import asyncio
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__
logger = setup_logging()

# Stato sessione intrattenimento
ENTERTAINER_STATE = {}

# Attività disponibili con descrizioni
ACTIVITIES = {
    "quiz": {
        "name": "Quiz di cultura generale",
        "intro": "Facciamo un bel quiz! Ti farò alcune domande.",
        "function": "quiz_trivia",
        "duration_mins": 5,
    },
    "cruciverba": {
        "name": "Cruciverba vocale",
        "intro": "Giochiamo con le parole! Ti darò delle definizioni.",
        "function": "cruciverba_vocale",
        "duration_mins": 5,
    },
    "storia": {
        "name": "Racconto una storia",
        "intro": "Ti racconto una bella storia. Mettiti comodo.",
        "function": "storie_bambini",
        "duration_mins": 5,
    },
    "barzelletta": {
        "name": "Barzelletta",
        "intro": "Ti racconto una barzelletta!",
        "function": "barzelletta_adulti",
        "duration_mins": 2,
    },
    "radio": {
        "name": "Musica alla radio",
        "intro": "Mettiamo un po' di buona musica.",
        "function": "radio_italia",
        "duration_mins": 10,
    },
    "notizie": {
        "name": "Ultime notizie",
        "intro": "Ti leggo le ultime notizie.",
        "function": "notizie_italia",
        "duration_mins": 5,
    },
    "meditazione": {
        "name": "Esercizio di rilassamento",
        "intro": "Facciamo un esercizio di respirazione per rilassarci.",
        "function": "meditazione",
        "duration_mins": 5,
    },
    "chiacchierata": {
        "name": "Chiacchierata",
        "intro": "Parliamo un po' insieme. Come stai oggi?",
        "function": None,  # Conversazione libera
        "duration_mins": 5,
    },
}

# Frasi di transizione
TRANSITION_PHRASES = [
    "Che ne dici se cambiamo un po'?",
    "Ti va di fare qualcos'altro?",
    "Potremmo provare qualcosa di diverso.",
    "Vuoi continuare o preferisci cambiare?",
    "Ho un'altra idea se ti va.",
]

# Frasi di compagnia
COMPANIONSHIP_PHRASES = [
    "Sono qui con te.",
    "È bello passare del tempo insieme.",
    "Ti sto ascoltando.",
    "Raccontami di te.",
    "Come ti senti oggi?",
    "Hai dormito bene stanotte?",
    "Hai già mangiato?",
    "C'è qualcosa che vorresti fare?",
]

INTRATTENITORE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "intrattenitore_anziani",
        "description": (
            "Modalità compagnia per anziani. Propone attività variegate. Usa quando: "
            "'tienimi compagnia', 'sono solo', 'cosa possiamo fare?', 'mi annoio', "
            "'intrattienimi', 'modalità anziani', 'passa il tempo con me'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start (avvia), suggest (suggerisci), stop (ferma), status (stato)",
                    "enum": ["start", "suggest", "stop", "status", "next"]
                },
                "activity": {
                    "type": "string",
                    "description": "Attività specifica da fare"
                }
            },
            "required": ["action"],
        },
    },
}


def get_session_id(conn) -> str:
    try:
        return conn.session_id if hasattr(conn, 'session_id') else str(id(conn))
    except:
        return str(id(conn))


def get_time_greeting() -> str:
    """Saluto appropriato per l'ora"""
    hour = datetime.now().hour
    if hour < 12:
        return "Buongiorno"
    elif hour < 18:
        return "Buon pomeriggio"
    else:
        return "Buonasera"


def suggest_activity(exclude: list = None) -> dict:
    """Suggerisce un'attività casuale"""
    exclude = exclude or []
    available = [k for k in ACTIVITIES.keys() if k not in exclude]

    if not available:
        available = list(ACTIVITIES.keys())

    key = random.choice(available)
    return {"key": key, **ACTIVITIES[key]}


@register_function("intrattenitore_anziani", INTRATTENITORE_FUNCTION_DESC, ToolType.WAIT)
def intrattenitore_anziani(conn, action: str = "suggest", activity: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Intrattenitore: action={action}, activity={activity}")

    # Inizializza stato sessione
    if session_id not in ENTERTAINER_STATE:
        ENTERTAINER_STATE[session_id] = {
            "active": False,
            "last_activity": None,
            "activities_done": [],
            "started_at": None,
            "interactions": 0,
        }

    state = ENTERTAINER_STATE[session_id]

    if action == "stop":
        state["active"] = False
        return ActionResponse(Action.RESPONSE,
            "Modalità compagnia terminata. Chiamami quando vuoi!",
            "Va bene, è stato bello passare del tempo insieme. Chiamami quando vuoi compagnia!")

    if action == "status":
        if not state["active"]:
            return ActionResponse(Action.RESPONSE,
                "Modalità compagnia non attiva",
                "Non sono in modalità compagnia. Vuoi che la attivi?")

        done = len(state["activities_done"])
        return ActionResponse(Action.RESPONSE,
            f"Attività completate: {done}",
            f"Abbiamo fatto {done} attività insieme. Vuoi continuare?")

    if action == "start":
        state["active"] = True
        state["started_at"] = datetime.now().isoformat()
        state["activities_done"] = []
        state["interactions"] = 0

        greeting = get_time_greeting()

        # Messaggio di benvenuto
        intro = f"{greeting}! Sono qui per farti compagnia. "
        intro += "Possiamo fare quiz, ascoltare la radio, raccontare storie, fare cruciverba... "
        intro += "Cosa ti piacerebbe fare?"

        # Suggerisci prima attività
        suggested = suggest_activity()
        intro += f" Ti propongo: {suggested['name']}. Ti va?"

        return ActionResponse(Action.RESPONSE, intro, intro)

    if action == "suggest" or action == "next":
        # Suggerisci nuova attività
        exclude = state.get("activities_done", [])[-3:]  # Escludi ultime 3
        suggested = suggest_activity(exclude)

        state["last_activity"] = suggested["key"]

        # Frase di transizione se non è la prima
        if state.get("activities_done"):
            transition = random.choice(TRANSITION_PHRASES)
            response = f"{transition} {suggested['intro']}"
        else:
            response = suggested["intro"]

        return ActionResponse(Action.RESPONSE, response, response)

    # Se specificata attività
    if activity:
        activity_lower = activity.lower()

        # Cerca match
        matched = None
        for key, act in ACTIVITIES.items():
            if activity_lower in key or activity_lower in act["name"].lower():
                matched = {"key": key, **act}
                break

        if matched:
            state["activities_done"].append(matched["key"])
            state["last_activity"] = matched["key"]
            state["interactions"] += 1

            if matched["function"]:
                # Richiama funzione specifica
                return ActionResponse(Action.RESPONSE,
                    f"Iniziamo: {matched['name']}!",
                    matched["intro"])
            else:
                # Chiacchierata libera
                phrase = random.choice(COMPANIONSHIP_PHRASES)
                return ActionResponse(Action.RESPONSE, phrase, phrase)

    # Default: chiedi cosa fare
    options = ", ".join([a["name"] for a in list(ACTIVITIES.values())[:4]])
    return ActionResponse(Action.RESPONSE,
        f"Cosa vorresti fare? Posso: {options}...",
        f"Cosa ti piacerebbe fare? Posso proporti: {options}, e tanto altro!")
