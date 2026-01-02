"""
Complimenti Plugin - Genera complimenti casuali
Per tirare su il morale
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Complimenti generici
COMPLIMENTI_GENERICI = [
    "Sei una persona speciale!",
    "Il tuo sorriso illumina la giornata!",
    "Hai un cuore d'oro!",
    "Sei più forte di quanto pensi!",
    "La tua presenza rende tutto migliore!",
    "Sei unico/a e prezioso/a!",
    "Hai un talento speciale per rendere felici gli altri!",
    "Sei una fonte d'ispirazione!",
    "Il mondo è più bello con te!",
    "Sei fantastico/a così come sei!",
    "Hai una luce interiore che brilla!",
    "Sei coraggioso/a e determinato/a!",
    "La tua gentilezza non passa inosservata!",
    "Sei più importante di quanto credi!",
    "Hai il potere di cambiare le cose!",
]

# Complimenti sulla personalità
COMPLIMENTI_PERSONALITA = [
    "Hai una personalità magnetica!",
    "La tua intelligenza è ammirevole!",
    "Sei una persona di grande sensibilità!",
    "La tua creatività è sorprendente!",
    "Hai un senso dell'umorismo fantastico!",
    "Sei incredibilmente paziente!",
    "La tua determinazione è invidiabile!",
    "Hai una grande empatia!",
    "Sei una persona molto affidabile!",
    "La tua onestà è rara e preziosa!",
]

# Complimenti motivazionali
COMPLIMENTI_MOTIVAZIONALI = [
    "Ce la farai, credici!",
    "Ogni ostacolo ti rende più forte!",
    "Il tuo meglio è sempre abbastanza!",
    "Non arrenderti, sei quasi al traguardo!",
    "Hai già superato sfide peggiori!",
    "Oggi è un nuovo giorno pieno di possibilità!",
    "Il successo ti aspetta, continua così!",
    "Sei capace di cose straordinarie!",
    "La perseveranza ti porterà lontano!",
    "Ogni passo conta, stai andando benissimo!",
]

# Complimenti per anziani
COMPLIMENTI_ANZIANI = [
    "La tua saggezza è un tesoro prezioso!",
    "Sei un esempio per tutti noi!",
    "I tuoi racconti sono affascinanti!",
    "Hai una memoria incredibile!",
    "La tua esperienza di vita è preziosa!",
    "Sei giovane dentro, e si vede!",
    "La tua compagnia è sempre piacevole!",
    "Hai ancora tanto da dare al mondo!",
    "Sei una persona meravigliosa!",
    "Il tempo ti ha reso ancora più speciale!",
]

COMPLIMENTI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "complimenti",
        "description": (
            "Genera complimenti per tirare su il morale."
            "Usare quando: fammi un complimento, dimmi qualcosa di carino, "
            "tirami su il morale, ho bisogno di incoraggiamento, sono giù, mi sento triste"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "description": "Tipo: generico, personalita, motivazionale, anziani",
                    "enum": ["generico", "personalita", "motivazionale", "anziani", "random"]
                }
            },
            "required": [],
        },
    },
}

@register_function("complimenti", COMPLIMENTI_FUNCTION_DESC, ToolType.WAIT)
def complimenti(conn, tipo: str = "random"):
    logger.bind(tag=TAG).info(f"Complimenti: tipo={tipo}")

    pool_map = {
        "generico": COMPLIMENTI_GENERICI,
        "personalita": COMPLIMENTI_PERSONALITA,
        "motivazionale": COMPLIMENTI_MOTIVAZIONALI,
        "anziani": COMPLIMENTI_ANZIANI,
    }

    if tipo == "random" or tipo not in pool_map:
        # Mix di tutti
        pool = (COMPLIMENTI_GENERICI + COMPLIMENTI_PERSONALITA +
                COMPLIMENTI_MOTIVAZIONALI + COMPLIMENTI_ANZIANI)
    else:
        pool = pool_map[tipo]

    complimento = random.choice(pool)

    # Emoji appropriati
    emoji_list = ["💖", "🌟", "✨", "💫", "🌈", "☀️", "💪", "🤗", "😊", "💝"]
    emoji = random.choice(emoji_list)

    # Aggiunta speciale
    aggiunte = [
        "Ricordalo sempre!",
        "E lo penso davvero!",
        "Non dimenticarlo mai!",
        "È la verità!",
        "Credici!",
        "",
        "",
        "",  # Alcune volte niente aggiunta
    ]
    aggiunta = random.choice(aggiunte)

    result = f"{emoji} **{complimento}**"
    if aggiunta:
        result += f"\n\n_{aggiunta}_"

    spoken = complimento
    if aggiunta:
        spoken += f" {aggiunta}"

    return ActionResponse(Action.RESPONSE, result, spoken)
