"""
Cambia Profilo - Gestione profili skill del chatbot

Permette di cambiare il "tipo" di assistente attivo,
caricando solo le funzioni rilevanti per quel profilo.

Comandi vocali:
- "Cambia profilo in anziani"
- "Attiva modalità bambini"
- "Che profilo sono?"
- "Quali profili ci sono?"
"""

import json
import os
from config.logger import setup_logging

# Import skill profiles from data directory (mounted in Docker)
try:
    from data.config.skill_profiles import SKILL_PROFILES, get_profile_functions, get_all_profiles, get_profile_info, CORE_FUNCTIONS
except ImportError:
    # Fallback: definizioni inline minime
    SKILL_PROFILES = {"generale": {"nome": "Generale", "descrizione": "Profilo base", "icona": "🏠", "functions": []}}
    CORE_FUNCTIONS = ["risposta_ai", "web_search", "meteo_italia", "cambia_profilo"]
    def get_profile_functions(p): return CORE_FUNCTIONS
    def get_all_profiles(): return {"generale": {"nome": "Generale", "descrizione": "Base", "icona": "🏠", "num_functions": 4}}
    def get_profile_info(p): return {"nome": "Generale", "descrizione": "Profilo base", "icona": "🏠", "total_functions": 4}
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# File per persistenza profilo per device
PROFILES_STATE_FILE = "data/device_profiles.json"


def load_device_profiles() -> dict:
    """Carica i profili salvati per device"""
    try:
        if os.path.exists(PROFILES_STATE_FILE):
            with open(PROFILES_STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento profili: {e}")
    return {}


def save_device_profiles(profiles: dict):
    """Salva i profili per device"""
    try:
        os.makedirs(os.path.dirname(PROFILES_STATE_FILE), exist_ok=True)
        with open(PROFILES_STATE_FILE, 'w') as f:
            json.dump(profiles, f, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio profili: {e}")


def get_device_profile(device_id: str) -> str:
    """Ottieni profilo corrente per un device"""
    profiles = load_device_profiles()
    return profiles.get(device_id, "generale")


def set_device_profile(device_id: str, profile_name: str) -> bool:
    """Imposta profilo per un device"""
    if profile_name not in SKILL_PROFILES:
        return False

    profiles = load_device_profiles()
    profiles[device_id] = profile_name
    save_device_profiles(profiles)
    return True


def get_session_id(conn) -> str:
    """Ottieni ID device/session"""
    if hasattr(conn, 'device_id') and conn.device_id:
        return conn.device_id
    if hasattr(conn, 'session_id') and conn.session_id:
        return conn.session_id
    return "default"


# Alias profili per riconoscimento vocale
PROFILE_ALIASES = {
    # Generale
    "generale": "generale", "normal": "generale", "standard": "generale",
    "base": "generale", "default": "generale",

    # Anziani
    "anziani": "anziani", "anziano": "anziani", "nonno": "anziani",
    "nonna": "anziani", "senior": "anziani", "compagnia": "anziani",

    # Bambini
    "bambini": "bambini", "bambino": "bambini", "kids": "bambini",
    "bimbi": "bambini", "bimbo": "bambini", "piccoli": "bambini",

    # Intrattenimento
    "intrattenimento": "intrattenimento", "giochi": "intrattenimento",
    "gioco": "intrattenimento", "divertimento": "intrattenimento",
    "gaming": "intrattenimento", "svago": "intrattenimento",

    # Produttività
    "produttivita": "produttivita", "produttività": "produttivita",
    "lavoro": "produttivita", "ufficio": "produttivita",
    "organizzazione": "produttivita", "business": "produttivita",

    # Cultura italiana
    "cultura_italiana": "cultura_italiana", "cultura": "cultura_italiana",
    "italia": "cultura_italiana", "italiano": "cultura_italiana",

    # Benessere
    "benessere": "benessere", "relax": "benessere", "salute": "benessere",
    "meditazione": "benessere", "wellness": "benessere",

    # Smart home
    "smart_home": "smart_home", "domotica": "smart_home", "casa": "smart_home",
    "iot": "smart_home", "automazione": "smart_home",

    # Interprete
    "interprete": "interprete", "traduttore": "interprete",
    "traduzione": "interprete", "lingue": "interprete",

    # Cucina
    "cucina": "cucina", "chef": "cucina", "ricette": "cucina",
    "cucinare": "cucina", "cooking": "cucina",

    # Notte
    "notte": "notte", "notturno": "notte", "dormire": "notte",
    "sonno": "notte", "sera": "notte", "buonanotte": "notte",
}


def resolve_profile_name(text: str) -> str:
    """Risolvi nome profilo da testo"""
    text_lower = text.lower().strip()

    # Check alias diretto
    if text_lower in PROFILE_ALIASES:
        return PROFILE_ALIASES[text_lower]

    # Check parziale
    for alias, profile in PROFILE_ALIASES.items():
        if alias in text_lower:
            return profile

    return None


CAMBIA_PROFILO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "cambia_profilo",
        "description": (
            "Cambia il profilo/modalità del chatbot. "
            "Profili disponibili: generale, anziani, bambini, intrattenimento, "
            "produttivita, cultura_italiana, benessere, smart_home, interprete, cucina, notte. "
            "Use when: 'cambia profilo', 'attiva modalità', 'che profilo sono', "
            "'quali profili ci sono', 'modalità bambini', 'modalità notte'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "azione": {
                    "type": "string",
                    "enum": ["cambia", "stato", "lista"],
                    "description": "cambia=cambia profilo, stato=profilo corrente, lista=mostra tutti"
                },
                "profilo": {
                    "type": "string",
                    "description": "Nome del profilo da attivare"
                }
            },
            "required": []
        }
    }
}


@register_function('cambia_profilo', CAMBIA_PROFILO_FUNCTION_DESC, ToolType.WAIT)
def cambia_profilo(conn, azione: str = None, profilo: str = None):
    """Gestisce cambio profilo chatbot"""
    device_id = get_session_id(conn)

    # Se non c'è azione, determina da contesto
    if not azione:
        if profilo:
            azione = "cambia"
        else:
            azione = "stato"

    # === LISTA PROFILI ===
    if azione == "lista":
        all_profiles = get_all_profiles()
        lista = []
        for name, info in all_profiles.items():
            lista.append(f"{info['icona']} {info['nome']} ({info['num_functions']} funzioni)")

        result = "🎭 PROFILI DISPONIBILI\n\n" + "\n".join(lista)
        result += "\n\nDì 'cambia profilo in [nome]' per attivare."

        spoken = "Ecco i profili disponibili: " + ", ".join([
            SKILL_PROFILES[name]["nome"] for name in SKILL_PROFILES.keys()
        ])

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )

    # === STATO CORRENTE ===
    if azione == "stato":
        current = get_device_profile(device_id)
        info = get_profile_info(current)

        if info:
            result = f"{info['icona']} Profilo attivo: {info['nome']}\n\n"
            result += f"📝 {info['descrizione']}\n"
            result += f"🔧 {info['total_functions']} funzioni attive"

            spoken = f"Hai attivo il profilo {info['nome']}. {info['descrizione']}"
        else:
            result = "Profilo: generale"
            spoken = "Hai attivo il profilo generale."

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )

    # === CAMBIA PROFILO ===
    if azione == "cambia":
        if not profilo:
            return ActionResponse(
                action=Action.RESPONSE,
                result="In quale profilo vuoi cambiare?",
                response="Quale profilo vuoi attivare? Puoi dire anziani, bambini, intrattenimento, produttività, e altri."
            )

        # Risolvi nome profilo
        resolved = resolve_profile_name(profilo)

        if not resolved:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Profilo '{profilo}' non trovato",
                response=f"Non conosco il profilo {profilo}. Prova con: generale, anziani, bambini, intrattenimento, benessere, cucina, notte."
            )

        # Imposta nuovo profilo
        if set_device_profile(device_id, resolved):
            info = get_profile_info(resolved)

            # Aggiorna le funzioni attive nella sessione
            # (Questo richiede integrazione con il sistema di intent)
            if hasattr(conn, 'active_profile'):
                conn.active_profile = resolved

            result = f"✅ Profilo cambiato!\n\n"
            result += f"{info['icona']} {info['nome']}\n"
            result += f"📝 {info['descrizione']}\n"
            result += f"🔧 {info['total_functions']} funzioni attive"

            spoken = f"Perfetto! Ho attivato il profilo {info['nome']}. {info['descrizione']}"

            logger.bind(tag=TAG).info(f"Profilo cambiato per {device_id}: {resolved}")

            return ActionResponse(
                action=Action.RESPONSE,
                result=result,
                response=spoken
            )
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Errore nel cambio profilo",
                response="Mi dispiace, c'è stato un errore. Riprova."
            )

    return ActionResponse(
        action=Action.RESPONSE,
        result="Comando non riconosciuto",
        response="Non ho capito. Vuoi vedere i profili disponibili o cambiare profilo?"
    )


# === FUNZIONE HELPER PER ALTRI MODULI ===

def get_active_functions_for_device(device_id: str) -> list:
    """
    Ritorna la lista di funzioni attive per un device.
    Usato dall'intent system per filtrare le funzioni.
    """
    profile = get_device_profile(device_id)
    return get_profile_functions(profile)


def is_function_active_for_device(device_id: str, function_name: str) -> bool:
    """
    Verifica se una funzione è attiva per un device.
    """
    active = get_active_functions_for_device(device_id)
    return function_name in active
