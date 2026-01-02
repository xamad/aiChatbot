"""
Traduttore Plugin - Traduzione vocale rapida usando LLM
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Nomi lingue in italiano -> codice
LANGUAGES = {
    "italiano": "it", "italian": "it", "it": "it",
    "inglese": "en", "english": "en", "en": "en",
    "francese": "fr", "french": "fr", "fr": "fr",
    "tedesco": "de", "german": "de", "de": "de",
    "spagnolo": "es", "spanish": "es", "es": "es",
    "portoghese": "pt", "portuguese": "pt", "pt": "pt",
    "cinese": "zh", "chinese": "zh", "zh": "zh",
    "giapponese": "ja", "japanese": "ja", "ja": "ja",
    "coreano": "ko", "korean": "ko", "ko": "ko",
    "russo": "ru", "russian": "ru", "ru": "ru",
    "arabo": "ar", "arabic": "ar", "ar": "ar",
}

# Nomi per output vocale
LANG_NAMES = {
    "it": "italiano", "en": "inglese", "fr": "francese",
    "de": "tedesco", "es": "spagnolo", "pt": "portoghese",
    "zh": "cinese", "ja": "giapponese", "ko": "coreano",
    "ru": "russo", "ar": "arabo",
}

TRADUTTORE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "traduttore",
        "description": (
            "Traduce parole e frasi in varie lingue."
            "Usare quando: come si dice, traduci, traduzione, "
            "in inglese, in tedesco, in francese"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Testo da tradurre"
                },
                "to_language": {
                    "type": "string",
                    "description": "Lingua di destinazione (inglese, francese, tedesco, spagnolo, ecc.)"
                },
                "from_language": {
                    "type": "string",
                    "description": "Lingua di origine (default: auto-detect)"
                }
            },
            "required": ["text", "to_language"],
        },
    },
}


# Dizionario base per traduzioni comuni offline
BASIC_TRANSLATIONS = {
    "it-en": {
        "ciao": "hello", "grazie": "thank you", "prego": "you're welcome",
        "sì": "yes", "no": "no", "casa": "house", "acqua": "water",
        "cibo": "food", "amore": "love", "buongiorno": "good morning",
        "buonasera": "good evening", "buonanotte": "good night",
        "arrivederci": "goodbye", "scusa": "sorry", "per favore": "please",
        "come stai": "how are you", "bene": "well/good", "male": "bad",
        "oggi": "today", "domani": "tomorrow", "ieri": "yesterday",
    },
    "en-it": {
        "hello": "ciao", "thank you": "grazie", "yes": "sì", "no": "no",
        "house": "casa", "water": "acqua", "food": "cibo", "love": "amore",
        "good morning": "buongiorno", "goodbye": "arrivederci",
        "sorry": "scusa", "please": "per favore", "how are you": "come stai",
    },
    "it-fr": {
        "ciao": "salut/bonjour", "grazie": "merci", "sì": "oui", "no": "non",
        "casa": "maison", "acqua": "eau", "amore": "amour",
        "buongiorno": "bonjour", "buonasera": "bonsoir",
    },
    "it-de": {
        "ciao": "hallo", "grazie": "danke", "sì": "ja", "no": "nein",
        "casa": "haus", "acqua": "wasser", "amore": "liebe",
        "buongiorno": "guten morgen", "buonasera": "guten abend",
    },
    "it-es": {
        "ciao": "hola", "grazie": "gracias", "sì": "sí", "no": "no",
        "casa": "casa", "acqua": "agua", "amore": "amor",
        "buongiorno": "buenos días", "buonasera": "buenas tardes",
    },
}


def get_lang_code(lang: str) -> str:
    """Converte nome lingua in codice"""
    if not lang:
        return None
    return LANGUAGES.get(lang.lower().strip(), lang.lower()[:2])


def translate_offline(text: str, from_lang: str, to_lang: str) -> str:
    """Traduzione offline da dizionario base"""
    key = f"{from_lang}-{to_lang}"
    text_lower = text.lower().strip()

    if key in BASIC_TRANSLATIONS:
        if text_lower in BASIC_TRANSLATIONS[key]:
            return BASIC_TRANSLATIONS[key][text_lower]

    return None


@register_function("traduttore", TRADUTTORE_FUNCTION_DESC, ToolType.WAIT)
def traduttore(conn, text: str, to_language: str, from_language: str = "italiano"):
    logger.bind(tag=TAG).info(f"Traduttore: '{text}' -> {to_language} (from {from_language})")

    if not text:
        return ActionResponse(Action.RESPONSE,
            "Cosa vuoi tradurre?",
            "Dimmi cosa vuoi tradurre")

    to_lang = get_lang_code(to_language)
    from_lang = get_lang_code(from_language) or "it"

    if not to_lang:
        return ActionResponse(Action.RESPONSE,
            f"Lingua '{to_language}' non riconosciuta",
            f"Non conosco la lingua {to_language}")

    to_lang_name = LANG_NAMES.get(to_lang, to_language)
    from_lang_name = LANG_NAMES.get(from_lang, from_language)

    # Prova traduzione offline
    translation = translate_offline(text, from_lang, to_lang)

    if translation:
        return ActionResponse(Action.RESPONSE,
            f"'{text}' in {to_lang_name}: {translation}",
            f"{text} in {to_lang_name} si dice: {translation}")

    # Se non trovato offline, usa REQLLM per chiedere al LLM
    prompt = f"Traduci '{text}' da {from_lang_name} a {to_lang_name}. Rispondi solo con la traduzione."

    return ActionResponse(Action.REQLLM,
        prompt,
        f"Traduco {text} in {to_lang_name}...")
