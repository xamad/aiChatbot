"""
Oracolo Plugin - Risposte mistiche alle domande
Stile Magic 8-Ball italiano
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Risposte dell'oracolo
RISPOSTE_POSITIVE = [
    "Certamente sì! ✨",
    "Le stelle dicono di sì!",
    "Senza alcun dubbio.",
    "Puoi contarci!",
    "I segni sono favorevoli.",
    "Assolutamente sì!",
    "Il destino ti sorride.",
    "Sì, le energie sono positive.",
    "La risposta è sì, fidati.",
    "Il futuro dice sì!",
]

RISPOSTE_NEUTRE = [
    "Forse... concentrati e riprova.",
    "Non è chiaro, ripeti la domanda.",
    "Le nebbie del futuro sono dense...",
    "Difficile dire, il destino è incerto.",
    "Potrebbe essere, ma non è sicuro.",
    "I segni sono confusi.",
    "Meglio riflettere ancora.",
    "Non ora, forse più tardi.",
    "La risposta verrà col tempo.",
    "Ni... né sì né no.",
]

RISPOSTE_NEGATIVE = [
    "No, le stelle dicono no.",
    "Non contarci questa volta.",
    "I segni non sono favorevoli.",
    "Meglio lasciar perdere.",
    "Il destino dice no.",
    "Non è il momento giusto.",
    "Le energie sono negative per questo.",
    "Purtroppo no.",
    "Non è scritto nelle stelle.",
    "Evita, non porterà bene.",
]

# Frasi mistiche di apertura
APERTURE = [
    "L'oracolo ha parlato...",
    "Guardo nella sfera di cristallo...",
    "Le carte rivelano...",
    "Consulto le stelle...",
    "I tarocchi dicono...",
    "Leggo il tuo destino...",
    "Le rune sussurrano...",
    "Il pendolo oscilla e...",
]

ORACOLO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "oracolo",
        "description": (
            "Risponde a domande con risposte mistiche tipo Magic 8 Ball."
            "Usare quando: oracolo, devo fare, dimmi il futuro, cosa mi consigli, "
            "dovrei, andrà bene, magic 8 ball, predizione"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "domanda": {
                    "type": "string",
                    "description": "La domanda da fare all'oracolo"
                }
            },
            "required": [],
        },
    },
}

@register_function("oracolo", ORACOLO_FUNCTION_DESC, ToolType.WAIT)
def oracolo(conn, domanda: str = None):
    logger.bind(tag=TAG).info(f"Oracolo: domanda={domanda}")

    if not domanda:
        return ActionResponse(Action.RESPONSE,
            "🔮 Cosa vuoi chiedere all'oracolo?",
            "Sono l'oracolo. Fammi una domanda e ti rivelerò la risposta.")

    # Scegli tipo risposta casualmente (leggermente positivo)
    rand = random.random()
    if rand < 0.4:
        risposta = random.choice(RISPOSTE_POSITIVE)
        tipo = "positiva"
    elif rand < 0.7:
        risposta = random.choice(RISPOSTE_NEUTRE)
        tipo = "neutra"
    else:
        risposta = random.choice(RISPOSTE_NEGATIVE)
        tipo = "negativa"

    apertura = random.choice(APERTURE)

    # Effetti speciali in base al tipo
    emoji = {"positiva": "✨", "neutra": "🌙", "negativa": "🌑"}[tipo]

    result = f"🔮 **L'ORACOLO PARLA**\n\n"
    result += f"_{apertura}_\n\n"
    result += f"{emoji} **{risposta}**"

    spoken = f"{apertura} {risposta}"

    # Aggiungi consiglio casuale
    consigli = [
        "Ricorda, il destino è nelle tue mani.",
        "Le stelle guidano, ma tu decidi.",
        "Ascolta il tuo cuore.",
        "Il tempo rivelerà la verità.",
    ]

    if random.random() > 0.5:
        consiglio = random.choice(consigli)
        result += f"\n\n_{consiglio}_"
        spoken += f" {consiglio}"

    return ActionResponse(Action.RESPONSE, result, spoken)
