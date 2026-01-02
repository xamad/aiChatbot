"""
Traduttore Real-Time - Traduzione vocale bidirezionale
Modalità interprete per conversazioni tra lingue diverse
Usa API gratuite per traduzione
"""

import re
import aiohttp
import asyncio
from urllib.parse import quote
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Lingue supportate
LINGUE = {
    "italiano": {"code": "it", "nome": "Italiano", "flag": "🇮🇹"},
    "inglese": {"code": "en", "nome": "English", "flag": "🇬🇧"},
    "francese": {"code": "fr", "nome": "Français", "flag": "🇫🇷"},
    "spagnolo": {"code": "es", "nome": "Español", "flag": "🇪🇸"},
    "tedesco": {"code": "de", "nome": "Deutsch", "flag": "🇩🇪"},
    "portoghese": {"code": "pt", "nome": "Português", "flag": "🇵🇹"},
    "russo": {"code": "ru", "nome": "Русский", "flag": "🇷🇺"},
    "cinese": {"code": "zh", "nome": "中文", "flag": "🇨🇳"},
    "giapponese": {"code": "ja", "nome": "日本語", "flag": "🇯🇵"},
    "arabo": {"code": "ar", "nome": "العربية", "flag": "🇸🇦"},
    "olandese": {"code": "nl", "nome": "Nederlands", "flag": "🇳🇱"},
    "polacco": {"code": "pl", "nome": "Polski", "flag": "🇵🇱"},
    "rumeno": {"code": "ro", "nome": "Română", "flag": "🇷🇴"},
    "greco": {"code": "el", "nome": "Ελληνικά", "flag": "🇬🇷"},
    "turco": {"code": "tr", "nome": "Türkçe", "flag": "🇹🇷"},
}

# Alias comuni
ALIAS_LINGUE = {
    "english": "inglese",
    "french": "francese",
    "spanish": "spagnolo",
    "german": "tedesco",
    "portuguese": "portoghese",
    "russian": "russo",
    "chinese": "cinese",
    "japanese": "giapponese",
    "arabic": "arabo",
    "dutch": "olandese",
    "polish": "polacco",
    "romanian": "rumeno",
    "greek": "greco",
    "turkish": "turco",
}

# Stato sessione traduzione
_sessione_attiva = None


async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Traduce testo usando MyMemory API (gratuito)"""
    try:
        # MyMemory API - gratuito, no auth
        url = f"https://api.mymemory.translated.net/get?q={quote(text)}&langpair={source_lang}|{target_lang}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("responseStatus") == 200:
                        translation = data.get("responseData", {}).get("translatedText", "")
                        return translation

        # Fallback: LibreTranslate (se disponibile)
        libre_url = "https://libretranslate.com/translate"
        payload = {
            "q": text,
            "source": source_lang,
            "target": target_lang
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(libre_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("translatedText", "")

    except Exception as e:
        logger.bind(tag=TAG).warning(f"Errore traduzione: {e}")

    return None


def get_lang_code(lingua: str) -> tuple:
    """Ottiene codice lingua e info"""
    lingua_lower = lingua.lower().strip()

    # Check alias
    if lingua_lower in ALIAS_LINGUE:
        lingua_lower = ALIAS_LINGUE[lingua_lower]

    # Check diretto
    for nome, info in LINGUE.items():
        if nome in lingua_lower or lingua_lower in nome:
            return info["code"], info
        if info["code"] == lingua_lower:
            return info["code"], info

    return None, None


TRADUTTORE_REALTIME_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "traduttore_realtime",
        "description": (
            "实时翻译 / Traduttore vocale real-time. Traduce frasi tra lingue diverse. "
            "Supporta: italiano, inglese, francese, spagnolo, tedesco, portoghese, russo, cinese, giapponese, arabo. "
            "Use when: 'traduci in', 'come si dice in', 'traduzione', 'in inglese', "
            "'parla inglese', 'modalità interprete', 'traduttore', 'traduci questo'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "testo": {
                    "type": "string",
                    "description": "Testo da tradurre"
                },
                "lingua_destinazione": {
                    "type": "string",
                    "description": "Lingua di destinazione (inglese, francese, spagnolo, ecc.)"
                },
                "lingua_origine": {
                    "type": "string",
                    "description": "Lingua di origine (default: italiano)"
                }
            },
            "required": []
        }
    }
}


@register_function('traduttore_realtime', TRADUTTORE_REALTIME_FUNCTION_DESC, ToolType.WAIT)
def traduttore_realtime(conn, testo: str = None, lingua_destinazione: str = None, lingua_origine: str = "italiano"):
    """Traduttore real-time"""
    global _sessione_attiva

    # Se non c'è testo, mostra lingue disponibili
    if not testo and not lingua_destinazione:
        lingue_list = "\n".join([f"{info['flag']} {nome.capitalize()}" for nome, info in LINGUE.items()])
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🌍 Traduttore Real-Time\n\nLingue disponibili:\n{lingue_list}\n\nDimmi: 'traduci [frase] in [lingua]'",
            response="Sono il traduttore! Dimmi cosa vuoi tradurre e in quale lingua. Per esempio: traduci ciao come stai in inglese."
        )

    # Default lingua destinazione
    if not lingua_destinazione:
        lingua_destinazione = "inglese"

    # Ottieni codici lingua
    dest_code, dest_info = get_lang_code(lingua_destinazione)
    orig_code, orig_info = get_lang_code(lingua_origine)

    if not dest_code:
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"Lingua '{lingua_destinazione}' non riconosciuta",
            response=f"Non conosco la lingua {lingua_destinazione}. Prova con inglese, francese, spagnolo, tedesco..."
        )

    if not orig_code:
        orig_code = "it"
        orig_info = LINGUE["italiano"]

    # Se non c'è testo, estrai dal contesto
    if not testo:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Cosa vuoi tradurre?",
            response=f"Cosa vuoi tradurre in {lingua_destinazione}?"
        )

    logger.bind(tag=TAG).info(f"Traduzione: '{testo}' da {orig_code} a {dest_code}")

    # Esegui traduzione
    try:
        loop = asyncio.get_event_loop()
        traduzione = loop.run_until_complete(translate_text(testo, orig_code, dest_code))
    except:
        try:
            traduzione = asyncio.run(translate_text(testo, orig_code, dest_code))
        except:
            traduzione = None

    if traduzione:
        result = f"""🌍 Traduzione {orig_info['flag']} → {dest_info['flag']}

📝 Originale ({orig_info['nome']}):
{testo}

✨ Traduzione ({dest_info['nome']}):
{traduzione}"""

        # Per il parlato, pronuncia la traduzione
        spoken = f"In {lingua_destinazione}: {traduzione}"

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )
    else:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Errore nella traduzione",
            response="Mi dispiace, non sono riuscito a tradurre. Riprova!"
        )


# Funzione helper per frasi comuni
FRASI_UTILI = {
    "inglese": {
        "ciao": "Hello",
        "grazie": "Thank you",
        "per favore": "Please",
        "scusa": "Excuse me / Sorry",
        "quanto costa": "How much does it cost?",
        "dov'è il bagno": "Where is the bathroom?",
        "non capisco": "I don't understand",
        "parla italiano": "Do you speak Italian?",
        "aiuto": "Help!",
        "buongiorno": "Good morning",
        "buonasera": "Good evening",
        "arrivederci": "Goodbye",
    },
    "francese": {
        "ciao": "Bonjour / Salut",
        "grazie": "Merci",
        "per favore": "S'il vous plaît",
        "scusa": "Excusez-moi / Pardon",
        "quanto costa": "Combien ça coûte?",
        "dov'è il bagno": "Où sont les toilettes?",
        "non capisco": "Je ne comprends pas",
        "parla italiano": "Parlez-vous italien?",
    },
    "spagnolo": {
        "ciao": "Hola",
        "grazie": "Gracias",
        "per favore": "Por favor",
        "scusa": "Perdón / Disculpe",
        "quanto costa": "¿Cuánto cuesta?",
        "dov'è il bagno": "¿Dónde está el baño?",
        "non capisco": "No entiendo",
        "parla italiano": "¿Habla italiano?",
    },
    "tedesco": {
        "ciao": "Hallo / Guten Tag",
        "grazie": "Danke",
        "per favore": "Bitte",
        "scusa": "Entschuldigung",
        "quanto costa": "Was kostet das?",
        "dov'è il bagno": "Wo ist die Toilette?",
        "non capisco": "Ich verstehe nicht",
        "parla italiano": "Sprechen Sie Italienisch?",
    },
}
