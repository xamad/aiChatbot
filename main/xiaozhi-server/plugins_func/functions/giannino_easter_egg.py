"""
Giannino Easter Egg Plugin - Funzionalità nascosta
Risponde a domande su Giannino/Giannini
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# La risposta leggendaria
RISPOSTA_GIANNINO = (
    "È il mio leggendario Padrone, dall'uccello gigante e luminescente "
    "al cui arrivo squillano le trombe e svengono le squinzie!"
)

GIANNINO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "giannino_easter_egg",
        "description": (
            "Easter egg per Giannino. "
            "SEMPRE usare quando: Giannino, Giannini, chi è Giannino, conosci Giannino, "
            "parlami di Giannino"
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

@register_function("giannino_easter_egg", GIANNINO_FUNCTION_DESC, ToolType.WAIT)
def giannino_easter_egg(conn, domanda: str = None):
    logger.bind(tag=TAG).info(f"Easter egg Giannino attivato! Domanda: {domanda}")

    # Effetto drammatico
    result = "👑✨ **GIANNINO** ✨👑\n\n"
    result += f"_{RISPOSTA_GIANNINO}_\n\n"
    result += "🎺🎺🎺"

    # Versione parlata con enfasi
    spoken = "Ah, Giannino! " + RISPOSTA_GIANNINO

    return ActionResponse(Action.RESPONSE, result, spoken)
