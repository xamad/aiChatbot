"""
Versi Animali da Cortile - Imitazioni goliardiche di animali
Funzione divertente per imitare versi di animali da fattoria
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Animali da cortile con i loro versi (scritti foneticamente per TTS)
ANIMALI_CORTILE = {
    "gallo": {
        "nome": "gallo",
        "verso": "Chicchirichìììììì! Chicchirichìììììì!",
        "intro": "Ecco il gallo che canta all'alba!",
        "extra": "Sveglia tutti! È ora di alzarsi!"
    },
    "gallina": {
        "nome": "gallina",
        "verso": "Coccodè coccodè coccodèèèèè! Coccodè!",
        "intro": "La gallina ha fatto l'uovo!",
        "extra": "Coccodè coccodè, un bell'uovo per te!"
    },
    "mucca": {
        "nome": "mucca",
        "verso": "Muuuuuuuu! Muuuuuuuuuuu! Muuuuu!",
        "intro": "La mucca nel prato!",
        "extra": "Vuole essere munta, muuuuu!"
    },
    "maiale": {
        "nome": "maiale",
        "verso": "Oink oink oink! Grugnf grugnf! Oink oink!",
        "intro": "Il maiale nella porcilaia!",
        "extra": "Rotola nel fango, oink oink!"
    },
    "asino": {
        "nome": "asino",
        "verso": "Iiiiaaaa! Iiiiaaaa! Iiiiiaaaaaaaa!",
        "intro": "L'asino ragliante!",
        "extra": "Il ciuchino fa la serenata!"
    },
    "pecora": {
        "nome": "pecora",
        "verso": "Beeeeee! Beeeeee! Beeeeeeeee!",
        "intro": "La pecorella nel gregge!",
        "extra": "Bee bee, voglio l'erbetta!"
    },
    "capra": {
        "nome": "capra",
        "verso": "Meeeeee! Meeeeee! Meeeeehhh!",
        "intro": "La capra sulla montagna!",
        "extra": "Meh meh, salto di roccia in roccia!"
    },
    "anatra": {
        "nome": "anatra",
        "verso": "Qua qua qua! Qua qua qua qua qua!",
        "intro": "L'anatra nello stagno!",
        "extra": "Qua qua, nuoto tutto il giorno!"
    },
    "oca": {
        "nome": "oca",
        "verso": "Ah ah ah! Ga ga ga! Ah ah ah!",
        "intro": "L'oca guardiana!",
        "extra": "Attenta a chi entra nel cortile!"
    },
    "tacchino": {
        "nome": "tacchino",
        "verso": "Glu glu glu! Glu glu glu glu!",
        "intro": "Il tacchino pomposo!",
        "extra": "Glu glu, guarda che belle piume!"
    },
    "cavallo": {
        "nome": "cavallo",
        "verso": "Hiiiiiiii! Nitrisce! Hiiiiiiii!",
        "intro": "Il cavallo nella stalla!",
        "extra": "Hiii hiii, voglio galoppare!"
    },
    "cane": {
        "nome": "cane da fattoria",
        "verso": "Bau bau bau! Woof woof! Bau bau bau!",
        "intro": "Il cane da guardia!",
        "extra": "Bau bau, proteggo la fattoria!"
    },
    "gatto": {
        "nome": "gatto",
        "verso": "Miao miao miaooo! Miao! Prrrrrr!",
        "intro": "Il gatto nel fienile!",
        "extra": "Miao, vado a caccia di topi!"
    },
    "coniglio": {
        "nome": "coniglio",
        "verso": "Frrr frrr frrr! Sniff sniff sniff!",
        "intro": "Il coniglietto!",
        "extra": "Munch munch, mangio la carota!"
    },
    "colombo": {
        "nome": "colombo",
        "verso": "Tru tru tru! Cru cru cru! Tru tru!",
        "intro": "Il piccione sul tetto!",
        "extra": "Tru tru, volo sulla colombaia!"
    },
}

# Combinazioni speciali per coro di animali
CORO_FATTORIA = [
    ("gallo", "mucca", "maiale"),
    ("gallina", "pecora", "asino"),
    ("anatra", "oca", "tacchino"),
    ("cane", "gatto", "cavallo"),
]


VERSI_ANIMALI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "versi_animali",
        "description": (
            "模仿动物叫声 / Imita i versi degli animali da cortile. "
            "Funzione goliardica per fare i versi degli animali della fattoria. "
            "Use when: 'fai il verso', 'imita animale', 'come fa il gallo', "
            "'fammi sentire la mucca', 'verso del maiale', 'animali da cortile', "
            "'fai l'animale', 'fai coccodè', 'fai muuu', 'fai bau', "
            "'imita un animale', 'fai il gallo', 'canta come un gallo'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "animale": {
                    "type": "string",
                    "description": "Animale specifico (gallo, mucca, maiale, ecc.) o 'random' per casuale"
                }
            },
            "required": []
        }
    }
}


@register_function('versi_animali', VERSI_ANIMALI_FUNCTION_DESC, ToolType.WAIT)
def versi_animali(conn, animale: str = None):
    """Imita i versi degli animali da cortile"""

    animali_keys = list(ANIMALI_CORTILE.keys())

    # Determina quale animale imitare
    if animale:
        animale_lower = animale.lower().strip()
        # Cerca match
        selected = None
        for key in animali_keys:
            if key in animale_lower or animale_lower in key:
                selected = key
                break

        # Se chiede "coro" o "tutti"
        if animale_lower in ['coro', 'tutti', 'fattoria', 'orchestra']:
            return _coro_fattoria()

        if not selected:
            # Animale non trovato, fai random
            selected = random.choice(animali_keys)
    else:
        # Random
        selected = random.choice(animali_keys)

    animale_info = ANIMALI_CORTILE[selected]

    logger.bind(tag=TAG).info(f"Verso animale: {selected}")

    # Costruisce risposta
    result_text = f"🐓 {animale_info['intro']}\n\n"
    result_text += f"🎵 {animale_info['verso']} 🎵\n\n"
    result_text += f"{animale_info['extra']}"

    # Versione parlata con enfasi
    spoken = f"{animale_info['intro']} ... {animale_info['verso']} ... {animale_info['extra']}"

    return ActionResponse(
        action=Action.RESPONSE,
        result=result_text,
        response=spoken
    )


def _coro_fattoria():
    """Coro di più animali insieme"""

    # Scegli una combinazione random
    combo = random.choice(CORO_FATTORIA)

    result_text = "🎭 IL GRANDE CORO DELLA FATTORIA! 🎭\n\n"
    spoken = "Ecco il grande coro della fattoria! "

    for animale_key in combo:
        animale = ANIMALI_CORTILE[animale_key]
        result_text += f"🐾 {animale['nome'].upper()}: {animale['verso']}\n"
        spoken += f"Il {animale['nome']}! {animale['verso']} "

    result_text += "\n🎵 Che orchestra! 🎵"
    spoken += "Che concerto meraviglioso!"

    logger.bind(tag=TAG).info(f"Coro fattoria: {combo}")

    return ActionResponse(
        action=Action.RESPONSE,
        result=result_text,
        response=spoken
    )
