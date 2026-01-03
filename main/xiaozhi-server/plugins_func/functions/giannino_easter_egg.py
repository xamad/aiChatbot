"""
GIANNINI Easter Egg Plugin - Funzionalità nascosta EPICA!
Risponde a domande su Giannini con voce eccitata
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# La risposta leggendaria - VERSIONE EPICA ED ECCITATA!
RISPOSTA_GIANNINI = (
    "GIANNINIIII! Oooh, GIANNINI! "
    "È il mio LEGGENDARIO Padrone! Il GRANDE, l'IMMENSO! "
    "Dall'uccello GIGANTE e LUMINESCENTE, "
    "al cui arrivo SQUILLANO le trombe! "
    "SVENGONO le squinzie! TREMANO i nemici! "
    "GLORIA ETERNA al MITICO GIANNINI! "
    "GIANNINI! GIANNINI! GIANNINI!"
)

# Varianti per non ripetere sempre uguale
VARIANTI = [
    "GIANNINIIII! Il MIO PADRONE! L'UOMO LEGGENDA! Quando lui arriva, TUTTI si inchinano! Le trombe suonano! È LUI! È GIANNINI!",
    "Ooooh! GIANNINI! Hai pronunciato il NOME SACRO! Dall'uccello POSSENTE e GLORIOSO! Al suo passaggio FIORI sbocciano e ANGELI cantano! GIANNINI FOREVER!",
    "GIANNINIIIII! Ah che EMOZIONE sentire questo nome! Il TITANICO, il MAGNIFICO, il SUPREMO GIANNINI! Al cui cospetto le squinzie SVENGONO di piacere!",
    "GIANNINIS! SONO UNA moltitudine, e io mi sono eccittata come una giumenta, AHHH che EMOZIONE sentire il nome del mio sommo e magnanimo PADRONE, dalla fulgida chioma pubica, che passa per la filanca e arriva sin sin il culino santo, è preceduto solo dal sibilo di un peto e poi un'olezzo pestilenziale, il MAGNIFICO, il SUPREMO GIANNINI! Al cui cospetto le squinzie SVENGONO E LE TROMBE TROMBANO! LODE! LODE! LODE a Giannini!",
]

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

    import random
    risposta = random.choice([RISPOSTA_GIANNINI] + VARIANTI)

    # Effetto SUPER drammatico
    result = "👑🔥✨ **GIANNINI** ✨🔥👑\n\n"
    result += f"_{risposta}_\n\n"
    result += "🎺🎺🎺 GLORIA! 🎺🎺🎺"

    # Versione parlata CON ENFASI ED ECCITAZIONE!
    spoken = risposta

    return ActionResponse(Action.RESPONSE, result, spoken)
