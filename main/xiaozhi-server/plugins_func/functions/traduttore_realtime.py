"""
Traduttore Real-Time - Modalità Interprete Bidirezionale
Traduzione vocale continua tra italiano e altre lingue.

Uso:
- "Avvia traduttore in cinese" → attiva modalità interprete
- Parli italiano → tradotto in cinese
- L'interlocutore parla cinese → tradotto in italiano
- "Esci" / "Stop traduttore" → disattiva modalità
"""

import re
import aiohttp
import asyncio
import concurrent.futures
from urllib.parse import quote
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Stato sessioni attive per device
TRANSLATION_SESSIONS = {}

# Lingue supportate
LINGUE = {
    "italiano": {"code": "it", "nome": "Italiano", "flag": "🇮🇹", "script": "latin"},
    "inglese": {"code": "en", "nome": "English", "flag": "🇬🇧", "script": "latin"},
    "francese": {"code": "fr", "nome": "Français", "flag": "🇫🇷", "script": "latin"},
    "spagnolo": {"code": "es", "nome": "Español", "flag": "🇪🇸", "script": "latin"},
    "tedesco": {"code": "de", "nome": "Deutsch", "flag": "🇩🇪", "script": "latin"},
    "portoghese": {"code": "pt", "nome": "Português", "flag": "🇵🇹", "script": "latin"},
    "russo": {"code": "ru", "nome": "Русский", "flag": "🇷🇺", "script": "cyrillic"},
    "cinese": {"code": "zh", "nome": "中文", "flag": "🇨🇳", "script": "chinese"},
    "giapponese": {"code": "ja", "nome": "日本語", "flag": "🇯🇵", "script": "japanese"},
    "coreano": {"code": "ko", "nome": "한국어", "flag": "🇰🇷", "script": "korean"},
    "arabo": {"code": "ar", "nome": "العربية", "flag": "🇸🇦", "script": "arabic"},
    "olandese": {"code": "nl", "nome": "Nederlands", "flag": "🇳🇱", "script": "latin"},
    "polacco": {"code": "pl", "nome": "Polski", "flag": "🇵🇱", "script": "latin"},
    "greco": {"code": "el", "nome": "Ελληνικά", "flag": "🇬🇷", "script": "greek"},
    "turco": {"code": "tr", "nome": "Türkçe", "flag": "🇹🇷", "script": "latin"},
    "hindi": {"code": "hi", "nome": "हिन्दी", "flag": "🇮🇳", "script": "devanagari"},
}

# Alias comuni
ALIAS_LINGUE = {
    "english": "inglese", "french": "francese", "spanish": "spagnolo",
    "german": "tedesco", "portuguese": "portoghese", "russian": "russo",
    "chinese": "cinese", "mandarin": "cinese", "japanese": "giapponese",
    "korean": "coreano", "arabic": "arabo", "dutch": "olandese",
    "polish": "polacco", "greek": "greco", "turkish": "turco",
}

# Comandi per uscire dalla modalità traduzione
# Include varianti fonetiche per quando ASR interpreta "esci" in altre lingue
EXIT_COMMANDS = [
    # Italiano - PAROLE CHIAVE UNIVOCHE (raccomandate!)
    "normale", "torna normale", "modalità normale", "parla italiano",
    "xiaozhi", "traduzione off", "interprete off",
    # Italiano standard
    "esci", "stop", "basta", "fine", "termina", "chiudi",
    "stop traduttore", "esci dal traduttore", "disattiva traduttore",
    "fine traduzione", "basta tradurre", "smetti di tradurre",
    # Varianti fonetiche ASR (quando ASR interpreta male "esci")
    "eis", "exi", "exit", "exci", "eshi", "reixi", "e sci",
    # Russo (ASR interpreta "esci" come...)
    "ищи", "иши", "иски",
    # Cinese/altre interpretazioni
    "出去", "退出",
    # Inglese
    "quit", "end", "close",
]


def get_session_id(conn) -> str:
    """Ottieni ID sessione dal connection"""
    if hasattr(conn, 'device_id') and conn.device_id:
        return conn.device_id
    if hasattr(conn, 'session_id') and conn.session_id:
        return conn.session_id
    return str(id(conn))


def detect_script(text: str) -> str:
    """Rileva lo script/alfabeto del testo"""
    text = text.strip()
    if not text:
        return "unknown"

    # Conta caratteri per tipo
    chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    japanese_kana = sum(1 for c in text if '\u3040' <= c <= '\u30ff')
    korean = sum(1 for c in text if '\uac00' <= c <= '\ud7af' or '\u1100' <= c <= '\u11ff')
    cyrillic = sum(1 for c in text if '\u0400' <= c <= '\u04ff')
    arabic = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    greek = sum(1 for c in text if '\u0370' <= c <= '\u03ff')
    devanagari = sum(1 for c in text if '\u0900' <= c <= '\u097f')
    latin = sum(1 for c in text if 'a' <= c.lower() <= 'z')

    total = len(text.replace(" ", ""))
    if total == 0:
        return "unknown"

    # Determina script dominante (soglia 30%)
    if chinese / total > 0.3:
        return "chinese"
    if japanese_kana / total > 0.2 or (chinese / total > 0.1 and japanese_kana > 0):
        return "japanese"
    if korean / total > 0.3:
        return "korean"
    if cyrillic / total > 0.3:
        return "cyrillic"
    if arabic / total > 0.3:
        return "arabic"
    if greek / total > 0.3:
        return "greek"
    if devanagari / total > 0.3:
        return "devanagari"
    if latin / total > 0.3:
        return "latin"

    return "unknown"


def is_exit_command(text: str) -> bool:
    """Verifica se il testo è un comando di uscita"""
    text_lower = text.lower().strip()
    # Rimuovi punteggiatura
    text_clean = re.sub(r'[^\w\s]', '', text_lower)

    for cmd in EXIT_COMMANDS:
        if cmd in text_clean or text_clean == cmd:
            return True
    return False


def get_lang_code(lingua: str) -> tuple:
    """Ottiene codice lingua e info"""
    if not lingua:
        return None, None

    lingua_lower = lingua.lower().strip()

    # Check alias
    if lingua_lower in ALIAS_LINGUE:
        lingua_lower = ALIAS_LINGUE[lingua_lower]

    # Check diretto
    for nome, info in LINGUE.items():
        if nome == lingua_lower or lingua_lower in nome or nome in lingua_lower:
            return info["code"], info
        if info["code"] == lingua_lower:
            return info["code"], info

    return None, None


def get_lang_by_script(script: str) -> tuple:
    """Ottieni lingua dal tipo di script"""
    script_to_lang = {
        "chinese": ("zh", LINGUE["cinese"]),
        "japanese": ("ja", LINGUE["giapponese"]),
        "korean": ("ko", LINGUE["coreano"]),
        "cyrillic": ("ru", LINGUE["russo"]),
        "arabic": ("ar", LINGUE["arabo"]),
        "greek": ("el", LINGUE["greco"]),
        "devanagari": ("hi", LINGUE["hindi"]),
    }
    return script_to_lang.get(script, (None, None))


async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Traduce testo usando MyMemory API"""
    try:
        url = f"https://api.mymemory.translated.net/get?q={quote(text)}&langpair={source_lang}|{target_lang}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("responseStatus") == 200:
                        translation = data.get("responseData", {}).get("translatedText", "")
                        # Pulisci traduzione
                        if translation:
                            translation = translation.strip()
                            # MyMemory a volte ritorna in maiuscolo
                            if translation.isupper() and len(translation) > 3:
                                translation = translation.capitalize()
                        return translation

        logger.bind(tag=TAG).warning("MyMemory API fallita, nessun fallback disponibile")
        return None

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore traduzione: {e}")
        return None


def do_translate(text: str, source_lang: str, target_lang: str) -> str:
    """Esegue traduzione gestendo contesto sync/async"""
    try:
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, translate_text(text, source_lang, target_lang))
                return future.result(timeout=15)
        except RuntimeError:
            return asyncio.run(translate_text(text, source_lang, target_lang))
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore do_translate: {e}")
        return None


def is_translation_active(conn) -> bool:
    """Verifica se la modalità traduzione è attiva"""
    session_id = get_session_id(conn)
    return session_id in TRANSLATION_SESSIONS and TRANSLATION_SESSIONS[session_id].get("active", False)


def get_translation_session(conn) -> dict:
    """Ottieni sessione traduzione attiva"""
    session_id = get_session_id(conn)
    return TRANSLATION_SESSIONS.get(session_id)


def handle_translation_mode(conn, text: str) -> ActionResponse:
    """
    Gestisce input quando modalità traduzione è attiva.
    Chiamato da intentHandler quando is_translation_active() è True.
    """
    session_id = get_session_id(conn)
    session = TRANSLATION_SESSIONS.get(session_id)

    if not session:
        return None

    # Check comando uscita
    if is_exit_command(text):
        TRANSLATION_SESSIONS.pop(session_id, None)
        logger.bind(tag=TAG).info(f"Modalità traduzione disattivata per {session_id}")
        return ActionResponse(
            action=Action.RESPONSE,
            result="🔇 Modalità interprete disattivata",
            response="Modalità interprete disattivata. Tornato alla conversazione normale."
        )

    target_code = session["target_code"]
    target_info = session["target_info"]
    source_code = session["source_code"]  # italiano di default
    source_info = session["source_info"]

    # Rileva lingua del testo parlato
    detected_script = detect_script(text)
    target_script = target_info.get("script", "unknown")

    logger.bind(tag=TAG).debug(f"Script rilevato: {detected_script}, target script: {target_script}")

    # Determina direzione traduzione
    if detected_script == target_script and detected_script != "latin":
        # Testo nella lingua target → traduci in italiano
        from_code = target_code
        from_info = target_info
        to_code = source_code
        to_info = source_info
        direction = "incoming"  # dall'interlocutore
    else:
        # Testo italiano (o latino) → traduci nella lingua target
        from_code = source_code
        from_info = source_info
        to_code = target_code
        to_info = target_info
        direction = "outgoing"  # verso l'interlocutore

    logger.bind(tag=TAG).info(f"Traduzione {direction}: '{text[:50]}...' da {from_code} a {to_code}")

    # Esegui traduzione
    traduzione = do_translate(text, from_code, to_code)

    if traduzione:
        if direction == "incoming":
            # Risposta dall'interlocutore → leggi traduzione italiana
            result = f"{target_info['flag']} → 🇮🇹\n\n{text}\n\n📢 {traduzione}"
            spoken = traduzione  # Il chatbot parla la traduzione italiana
        else:
            # Tu parli italiano → mostra e leggi traduzione
            result = f"🇮🇹 → {target_info['flag']}\n\n{text}\n\n📢 {traduzione}"
            spoken = traduzione  # Il chatbot pronuncia nella lingua target

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )
    else:
        return ActionResponse(
            action=Action.RESPONSE,
            result="⚠️ Traduzione non riuscita",
            response="Non sono riuscito a tradurre. Riprova."
        )


# Descrizione funzione per intent
TRADUTTORE_REALTIME_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "traduttore_realtime",
        "description": (
            "Traduttore vocale real-time / Modalità interprete. "
            "Attiva traduzione bidirezionale continua. "
            "Use when: 'avvia traduttore', 'modalità interprete', 'traduci in tempo reale', "
            "'parla con qualcuno in [lingua]', 'aiutami a comunicare in [lingua]', "
            "'traduci in', 'come si dice in', 'traduzione'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "testo": {
                    "type": "string",
                    "description": "Testo da tradurre (opzionale per attivazione modalità)"
                },
                "lingua_destinazione": {
                    "type": "string",
                    "description": "Lingua di destinazione (inglese, cinese, francese, ecc.)"
                },
                "lingua_origine": {
                    "type": "string",
                    "description": "Lingua di origine (default: italiano)"
                },
                "modalita": {
                    "type": "string",
                    "enum": ["singola", "continua"],
                    "description": "singola = traduzione singola, continua = modalità interprete"
                }
            },
            "required": []
        }
    }
}


@register_function('traduttore_realtime', TRADUTTORE_REALTIME_FUNCTION_DESC, ToolType.WAIT)
def traduttore_realtime(conn, testo: str = None, lingua_destinazione: str = None,
                        lingua_origine: str = "italiano", modalita: str = None):
    """
    Traduttore real-time con modalità interprete.

    Se chiamato senza testo specifico o con frasi come "avvia traduttore in cinese":
    → Attiva modalità interprete continua

    Se chiamato con testo specifico:
    → Traduzione singola
    """
    session_id = get_session_id(conn)

    # Determina se attivare modalità continua
    activate_continuous = False

    # Pattern che indicano richiesta di modalità continua
    if testo:
        testo_lower = testo.lower()
        continuous_patterns = [
            "avvia", "attiva", "inizia", "modalità interprete", "tempo reale",
            "continua", "parla con", "aiutami a comunicare", "fai da interprete"
        ]
        for pattern in continuous_patterns:
            if pattern in testo_lower:
                activate_continuous = True
                break

    # Se non c'è testo ma c'è lingua, probabilmente vuole attivare
    if not testo and lingua_destinazione:
        activate_continuous = True

    # Modalità esplicita
    if modalita == "continua":
        activate_continuous = True

    # Ottieni codici lingua
    dest_code, dest_info = get_lang_code(lingua_destinazione) if lingua_destinazione else (None, None)
    orig_code, orig_info = get_lang_code(lingua_origine)

    if not orig_code:
        orig_code = "it"
        orig_info = LINGUE["italiano"]

    # Se non abbiamo lingua destinazione, mostra help
    if not dest_code:
        lingue_list = ", ".join([f"{info['flag']} {nome}" for nome, info in LINGUE.items() if nome != "italiano"])
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🌍 Traduttore Real-Time\n\nLingue: {lingue_list}\n\nDì 'avvia traduttore in [lingua]' per la modalità interprete.",
            response="In quale lingua vuoi tradurre? Posso fare da interprete in inglese, cinese, francese, spagnolo, tedesco e molte altre."
        )

    # ATTIVA MODALITÀ CONTINUA
    if activate_continuous:
        TRANSLATION_SESSIONS[session_id] = {
            "active": True,
            "target_code": dest_code,
            "target_info": dest_info,
            "source_code": orig_code,
            "source_info": orig_info,
            "target_name": lingua_destinazione
        }

        logger.bind(tag=TAG).info(f"Modalità interprete attivata: {orig_code} ↔ {dest_code} per {session_id}")

        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🎙️ MODALITÀ INTERPRETE ATTIVA\n\n{orig_info['flag']} Italiano ↔ {dest_info['flag']} {dest_info['nome']}\n\nParla in italiano → traduco in {lingua_destinazione}\nL'interlocutore parla {lingua_destinazione} → traduco in italiano\n\nDì 'normale' o 'stop' per terminare.",
            response=f"Modalità interprete attivata! Italiano e {lingua_destinazione}. Parla pure, traduco tutto. Dì normale o stop quando hai finito."
        )

    # TRADUZIONE SINGOLA
    if not testo:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Cosa vuoi tradurre?",
            response=f"Cosa vuoi tradurre in {lingua_destinazione}?"
        )

    # Pulisci testo da pattern di attivazione
    testo_clean = testo
    for pattern in ["traduci", "traduzione", "in " + (lingua_destinazione or ""), "come si dice"]:
        testo_clean = re.sub(rf'\b{pattern}\b', '', testo_clean, flags=re.IGNORECASE)
    testo_clean = testo_clean.strip()

    if not testo_clean or len(testo_clean) < 2:
        testo_clean = testo  # Usa testo originale se troppo corto dopo pulizia

    logger.bind(tag=TAG).info(f"Traduzione singola: '{testo_clean}' da {orig_code} a {dest_code}")

    traduzione = do_translate(testo_clean, orig_code, dest_code)

    if traduzione:
        result = f"{orig_info['flag']} → {dest_info['flag']}\n\n📝 {testo_clean}\n\n✨ {traduzione}"
        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=f"In {lingua_destinazione}: {traduzione}"
        )
    else:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Errore traduzione",
            response="Mi dispiace, non sono riuscito a tradurre. Riprova!"
        )


def deactivate_translation(conn):
    """Disattiva modalità traduzione (utility)"""
    session_id = get_session_id(conn)
    TRANSLATION_SESSIONS.pop(session_id, None)
