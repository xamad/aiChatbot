"""
GIANNINI Easter Egg Plugin - Funzionalità nascosta EPICA!
Risponde a domande su Giannini con voce eccitata
Le frasi sono configurabili via WebUI in /config
"""

import os
import json
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Path file configurazione frasi
PHRASES_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "giannino_phrases.json")

def load_giannino_phrases():
    """Carica frasi da file config, con fallback a default"""
    default_main = (
        "GIANNINIIII! Oooh, GIANNINI! "
        "È il mio LEGGENDARIO Padrone! Il GRANDE, l'IMMENSO! "
        "Dall'uccello GIGANTE e LUMINESCENTE, "
        "al cui arrivo SQUILLANO le trombe! "
        "SVENGONO le squinzie! TREMANO i nemici! "
        "GLORIA ETERNA al MITICO GIANNINI! "
        "GIANNINI! GIANNINI! GIANNINI!"
    )
    default_variants = [
        "GIANNINIIII! Il MIO PADRONE! L'UOMO LEGGENDA! Quando lui arriva, TUTTI si inchinano! Le trombe suonano! È LUI! È GIANNINI!",
        "Ooooh! GIANNINI! Hai pronunciato il NOME SACRO! Dall'uccello POSSENTE e GLORIOSO! Al suo passaggio FIORI sbocciano e ANGELI cantano! GIANNINI FOREVER!",
        "GIANNINIIIII! Ah che EMOZIONE sentire questo nome! Il TITANICO, il MAGNIFICO, il SUPREMO GIANNINI! Al cui cospetto le squinzie SVENGONO di piacere!",
    ]

    try:
        if os.path.exists(PHRASES_FILE):
            with open(PHRASES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("risposta_principale", default_main), data.get("varianti", default_variants)
    except Exception as e:
        logger.bind(tag=TAG).warning(f"Errore lettura frasi Giannino: {e}, uso default")

    return default_main, default_variants

# Carica frasi (ricaricate ad ogni chiamata per permettere modifica in tempo reale)
RISPOSTA_GIANNINI, VARIANTI = load_giannino_phrases()

GIANNINI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "giannino_easter_egg",
        "description": (
            "Easter egg EPICO per GIANNINI. "
            "SEMPRE usare quando: Giannini, Giannino, chi è Giannini, conosci Giannini, "
            "il grande Giannini, parlami di Giannini"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "domanda": {
                    "type": "string",
                    "description": "Domanda utente"
                }
            },
            "required": [],
        },
    },
}

@register_function("giannino_easter_egg", GIANNINI_FUNCTION_DESC, ToolType.WAIT)
def giannino_easter_egg(conn, domanda: str = None):
    logger.bind(tag=TAG).info(f"Easter egg GIANNINI attivato! Domanda: {domanda}")

    # Ricarica frasi ad ogni chiamata per permettere modifica in tempo reale
    risposta_main, varianti = load_giannino_phrases()

    import random
    risposta = random.choice([risposta_main] + varianti)

    # Effetto SUPER drammatico
    result = "👑🔥✨ **GIANNINI** ✨🔥👑\n\n"
    result += f"_{risposta}_\n\n"
    result += "🎺🎺🎺 GLORIA! 🎺🎺🎺"

    # Versione parlata CON ENFASI ED ECCITAZIONE!
    spoken = risposta

    return ActionResponse(Action.RESPONSE, result, spoken)
