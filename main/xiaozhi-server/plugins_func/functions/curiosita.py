"""
Curiosità Plugin - Fatti interessanti e curiosi
Lo sapevi che...
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

CURIOSITA = [
    # Animali
    {"fatto": "Le lumache possono dormire fino a 3 anni", "categoria": "animali"},
    {"fatto": "Un polpo ha tre cuori e sangue blu", "categoria": "animali"},
    {"fatto": "Le formiche non dormono mai", "categoria": "animali"},
    {"fatto": "I fenicotteri sono rosa perché mangiano gamberetti", "categoria": "animali"},
    {"fatto": "Le mucche hanno migliori amiche e si stressano se separate", "categoria": "animali"},
    {"fatto": "I delfini dormono con un occhio aperto", "categoria": "animali"},
    {"fatto": "Le api possono riconoscere i volti umani", "categoria": "animali"},
    {"fatto": "Un gruppo di gufi si chiama parlamento", "categoria": "animali"},

    # Scienza
    {"fatto": "Il fulmine è 5 volte più caldo della superficie del Sole", "categoria": "scienza"},
    {"fatto": "Il DNA umano è identico al 50% a quello di una banana", "categoria": "scienza"},
    {"fatto": "Un anno su Venere dura meno di un giorno su Venere", "categoria": "scienza"},
    {"fatto": "La luce del Sole impiega 8 minuti per raggiungerci", "categoria": "scienza"},
    {"fatto": "Il corpo umano contiene abbastanza carbonio per fare 9000 matite", "categoria": "scienza"},
    {"fatto": "L'acqua calda congela più velocemente di quella fredda", "categoria": "scienza"},
    {"fatto": "Gli astronauti non possono piangere nello spazio perché le lacrime galleggiano", "categoria": "scienza"},

    # Storia
    {"fatto": "Cleopatra visse più vicina nel tempo allo sbarco sulla Luna che alla costruzione delle piramidi", "categoria": "storia"},
    {"fatto": "Oxford è più antica dell'Impero Azteco", "categoria": "storia"},
    {"fatto": "Napoleone non era basso, era alto 1.70m, nella media del tempo", "categoria": "storia"},
    {"fatto": "Gli antichi romani usavano l'urina come collutorio", "categoria": "storia"},
    {"fatto": "La Grande Muraglia Cinese non è visibile dallo spazio a occhio nudo", "categoria": "storia"},

    # Italia
    {"fatto": "In Italia ci sono più di 350 tipi diversi di pasta", "categoria": "italia"},
    {"fatto": "Il Vaticano è il paese più piccolo del mondo", "categoria": "italia"},
    {"fatto": "La pizza margherita fu inventata nel 1889 a Napoli", "categoria": "italia"},
    {"fatto": "L'Università di Bologna è la più antica del mondo occidentale, fondata nel 1088", "categoria": "italia"},
    {"fatto": "L'Italia ha più siti UNESCO di qualsiasi altro paese", "categoria": "italia"},

    # Corpo umano
    {"fatto": "Il naso può distinguere oltre 1 trilione di odori diversi", "categoria": "corpo"},
    {"fatto": "Le impronte digitali di un koala sono indistinguibili da quelle umane", "categoria": "corpo"},
    {"fatto": "Il cervello genera abbastanza elettricità per accendere una lampadina", "categoria": "corpo"},
    {"fatto": "Gli umani sono gli unici animali che arrossiscono", "categoria": "corpo"},
    {"fatto": "Starnutiamo a circa 160 km/h", "categoria": "corpo"},

    # Tecnologia
    {"fatto": "Il primo iPhone aveva meno potenza di calcolo di una calcolatrice moderna", "categoria": "tecnologia"},
    {"fatto": "Il primo messaggio email fu inviato nel 1971", "categoria": "tecnologia"},
    {"fatto": "Il nome Google deriva da googol, il numero 1 seguito da 100 zeri", "categoria": "tecnologia"},
    {"fatto": "Il primo tweet fu postato il 21 marzo 2006", "categoria": "tecnologia"},
]

CURIOSITA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "curiosita",
        "description": (
            "Racconta fatti curiosi e interessanti."
            "Usare quando: dimmi una curiosità, lo sapevi che, fatto interessante, "
            "curiosità, dimmi qualcosa di curioso"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "description": "Categoria: animali, scienza, storia, italia, corpo, tecnologia",
                    "enum": ["animali", "scienza", "storia", "italia", "corpo", "tecnologia", "random"]
                }
            },
            "required": [],
        },
    },
}

@register_function("curiosita", CURIOSITA_FUNCTION_DESC, ToolType.WAIT)
def curiosita(conn, categoria: str = "random"):
    logger.bind(tag=TAG).info(f"Curiosità: categoria={categoria}")

    if categoria and categoria != "random":
        pool = [c for c in CURIOSITA if c["categoria"] == categoria]
        if not pool:
            pool = CURIOSITA
    else:
        pool = CURIOSITA

    cur = random.choice(pool)

    emoji_map = {
        "animali": "🐾",
        "scienza": "🔬",
        "storia": "📜",
        "italia": "🇮🇹",
        "corpo": "🧬",
        "tecnologia": "💻"
    }

    emoji = emoji_map.get(cur["categoria"], "💡")

    result = f"{emoji} **Lo sapevi che...**\n\n{cur['fatto']}"
    spoken = f"Lo sapevi che {cur['fatto']}?"

    return ActionResponse(Action.RESPONSE, result, spoken)
