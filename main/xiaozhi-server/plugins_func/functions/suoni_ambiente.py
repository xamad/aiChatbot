"""
Suoni Ambiente / ASMR - Suoni rilassanti per dormire o concentrarsi
Pioggia, temporale, onde, foresta, camino, rumore bianco, ecc.
Genera suoni con onomatopee TTS creative
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Suoni ambiente con rappresentazioni fonetiche per TTS
SUONI_AMBIENTE = {
    "pioggia": {
        "nome": "Pioggia Leggera",
        "icon": "🌧️",
        "desc": "Gocce di pioggia che cadono dolcemente",
        "suono": "Plic ploc plic ploc... shhhhh... plic plic ploc... shhhhhh... "
                 "gocce che cadono... plic ploc plic... shhhhhh... "
                 "la pioggia cade dolcemente... plic ploc ploc plic...",
        "loop": "plic ploc shhh plic ploc shhh",
    },
    "temporale": {
        "nome": "Temporale",
        "icon": "⛈️",
        "desc": "Pioggia forte con tuoni in lontananza",
        "suono": "SHHHHHHHH... la pioggia cade forte... BRUMMMM... "
                 "un tuono in lontananza... SHHHHHH... "
                 "CRACK! Un lampo! BRUMMMMMM... "
                 "la pioggia continua... shhhhhh...",
        "loop": "shhhhh brummm shhhhh crack brummmm",
    },
    "onde": {
        "nome": "Onde del Mare",
        "icon": "🌊",
        "desc": "Onde che si infrangono sulla spiaggia",
        "suono": "Shhhwoooosh... l'onda arriva... shhhhhh... "
                 "e si ritira... woooosh... shhhhhh... "
                 "un'altra onda... shhhwoooosh... "
                 "il mare respira... woooosh shhhh...",
        "loop": "shhhwoooosh woooosh shhhhh",
    },
    "foresta": {
        "nome": "Foresta",
        "icon": "🌲",
        "desc": "Uccellini, vento tra le foglie, natura",
        "suono": "Cip cip cip... gli uccellini cantano... "
                 "fruscio di foglie... shhhh... "
                 "tweet tweet... il vento soffia leggero... "
                 "cip cip... pace nella foresta... shhhh...",
        "loop": "cip cip shhh tweet cip shhh",
    },
    "camino": {
        "nome": "Fuoco nel Camino",
        "icon": "🔥",
        "desc": "Scoppiettio del fuoco caldo",
        "suono": "Crepita crepita... il fuoco arde... "
                 "crac... un ciocco si spezza... "
                 "crepita crepita... caldo e accogliente... "
                 "shhh... le fiamme danzano... crepita...",
        "loop": "crepita crac crepita shhh crepita",
    },
    "ruscello": {
        "nome": "Ruscello",
        "icon": "💧",
        "desc": "Acqua che scorre tra le rocce",
        "suono": "Gluglu gluglu... l'acqua scorre... "
                 "sciabordio tra le rocce... splish splash... "
                 "gluglu gluglu... fresco e cristallino... "
                 "l'acqua canta... splish gluglu...",
        "loop": "gluglu splish splash gluglu",
    },
    "vento": {
        "nome": "Vento",
        "icon": "💨",
        "desc": "Vento che soffia dolcemente",
        "suono": "Woooosh... il vento soffia... shhhhhh... "
                 "huuuu... tra gli alberi... woooosh... "
                 "un soffio leggero... shhhh... huuuu... "
                 "pace nel vento... woooosh...",
        "loop": "woooosh shhhhh huuuu woooosh",
    },
    "notte": {
        "nome": "Notte d'Estate",
        "icon": "🌙",
        "desc": "Grilli, civetta, suoni notturni",
        "suono": "Cri cri cri... i grilli cantano... "
                 "uh-uh... una civetta in lontananza... "
                 "cri cri cri... la notte è serena... "
                 "silenzio... uh-uh... cri cri...",
        "loop": "cri cri cri uh-uh cri cri",
    },
    "rumore_bianco": {
        "nome": "Rumore Bianco",
        "icon": "📺",
        "desc": "Rumore statico rilassante",
        "suono": "Shhhhhhhhhhhh... rumore uniforme... "
                 "shhhhhhhhhhhh... niente pensieri... "
                 "shhhhhhhhhhhh... solo calma... "
                 "shhhhhhhhhhhh... rilassati... shhhhhh...",
        "loop": "shhhhhhhhhhhhhhhhhhhhhhh",
    },
    "battito": {
        "nome": "Battito del Cuore",
        "icon": "❤️",
        "desc": "Battito cardiaco lento e rassicurante",
        "suono": "Tum tum... tum tum... il cuore batte... "
                 "tum tum... ritmo lento... tum tum... "
                 "rassicurante... tum tum... calmo... "
                 "tum tum... respira... tum tum...",
        "loop": "tum tum tum tum",
    },
    "caffetteria": {
        "nome": "Caffetteria",
        "icon": "☕",
        "desc": "Chiacchiericcio, tazze, macchina del caffè",
        "suono": "Brusio di voci... chiacchiere in sottofondo... "
                 "tlin! Una tazzina... shhh la macchina del caffè... "
                 "risate in lontananza... brusio... tlin tlin... "
                 "l'atmosfera accogliente del bar...",
        "loop": "brusio chiacchiere tlin shhh brusio",
    },
    "treno": {
        "nome": "Treno in Viaggio",
        "icon": "🚂",
        "desc": "Ritmo delle rotaie, viaggio rilassante",
        "suono": "Ciuf ciuf ciuf ciuf... il treno corre... "
                 "tac-tac tac-tac... le rotaie cantano... "
                 "ciuf ciuf... paesaggi che scorrono... "
                 "tac-tac tac-tac... viaggio sereno...",
        "loop": "ciuf ciuf tac-tac ciuf ciuf tac-tac",
    },
}

# Combinazioni speciali
COMBINAZIONI = {
    "spa": ["ruscello", "vento"],
    "campagna": ["foresta", "ruscello"],
    "notte_pioggia": ["pioggia", "notte"],
    "casa_accogliente": ["pioggia", "camino"],
    "spiaggia": ["onde", "vento"],
}


SUONI_AMBIENTE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "suoni_ambiente",
        "description": (
            "环境音/ASMR / Suoni ambiente rilassanti e ASMR per dormire o rilassarsi. "
            "Disponibili: pioggia, temporale, onde, foresta, camino, ruscello, vento, notte, rumore bianco, battito cuore, caffetteria, treno. "
            "Use when: 'suoni rilassanti', 'rumore bianco', 'suono della pioggia', 'onde del mare', "
            "'aiutami a dormire', 'ASMR', 'suoni natura', 'temporale', 'fuoco camino', "
            "'suoni per concentrarsi', 'ambiente rilassante'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "suono": {
                    "type": "string",
                    "description": "Tipo: pioggia, temporale, onde, foresta, camino, ruscello, vento, notte, rumore_bianco, battito, caffetteria, treno"
                },
                "durata": {
                    "type": "string",
                    "description": "Durata: breve (default), lungo"
                }
            },
            "required": []
        }
    }
}


@register_function('suoni_ambiente', SUONI_AMBIENTE_FUNCTION_DESC, ToolType.WAIT)
def suoni_ambiente(conn, suono: str = None, durata: str = "breve"):
    """Riproduce suoni ambiente rilassanti"""

    # Determina quale suono
    if suono:
        suono_lower = suono.lower().strip()
        selected = None

        # Match diretto
        for key in SUONI_AMBIENTE:
            if key in suono_lower or suono_lower in key:
                selected = key
                break

        # Alias
        aliases = {
            "mare": "onde", "oceano": "onde", "spiaggia": "onde",
            "bosco": "foresta", "uccelli": "foresta", "uccellini": "foresta",
            "fuoco": "camino", "fiamme": "camino",
            "acqua": "ruscello", "fiume": "ruscello", "torrente": "ruscello",
            "grilli": "notte", "estate": "notte", "sera": "notte",
            "bianco": "rumore_bianco", "statico": "rumore_bianco", "white": "rumore_bianco",
            "cuore": "battito", "heartbeat": "battito",
            "bar": "caffetteria", "caffe": "caffetteria", "coffee": "caffetteria",
            "ferrovia": "treno", "binari": "treno",
            "tuoni": "temporale", "lampi": "temporale", "storm": "temporale",
        }

        if not selected:
            for alias, target in aliases.items():
                if alias in suono_lower:
                    selected = target
                    break

        # Combinazioni
        for combo_name, combo_sounds in COMBINAZIONI.items():
            if combo_name in suono_lower:
                # Unisci più suoni
                combined = " ... ".join([SUONI_AMBIENTE[s]["suono"] for s in combo_sounds])
                icons = "".join([SUONI_AMBIENTE[s]["icon"] for s in combo_sounds])
                return ActionResponse(
                    action=Action.RESPONSE,
                    result=f"{icons} Mix: {combo_name}\n\n{combined}",
                    response=combined
                )

        if not selected:
            selected = random.choice(list(SUONI_AMBIENTE.keys()))
    else:
        selected = random.choice(list(SUONI_AMBIENTE.keys()))

    ambiente = SUONI_AMBIENTE[selected]

    logger.bind(tag=TAG).info(f"Suono ambiente: {selected}")

    # Determina lunghezza
    if durata and ('lung' in durata.lower() or 'long' in durata.lower()):
        # Versione lunga: ripeti il suono
        testo = ambiente["suono"] + " ... " + ambiente["suono"] + " ... " + ambiente["loop"] + " ... " + ambiente["loop"]
    else:
        testo = ambiente["suono"]

    result = f"{ambiente['icon']} {ambiente['nome']}\n\n{ambiente['desc']}\n\n{testo}"

    # Intro rilassante
    intro = "Chiudi gli occhi e rilassati... "
    spoken = intro + testo

    return ActionResponse(
        action=Action.RESPONSE,
        result=result,
        response=spoken
    )
