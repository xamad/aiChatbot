"""
Beatbox Umano - Basi vocali stile rapper/trapper
Simula beatbox con pattern fonetici per TTS
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Pattern beatbox fonetici - ottimizzati per TTS italiano
BASI_BEATBOX = {
    "hip_hop_classico": {
        "nome": "Hip Hop Classico",
        "emoji": "🎤",
        "descrizione": "Il classico boom bap old school",
        "pattern": (
            "Boom... tss... Boom boom... tss... "
            "Boom... tss... Boom boom... tss... "
            "Pah! Boom taka taka... tss... "
            "Boom... pah! Taka tss tss... "
            "Boots and cats and boots and cats... "
            "Boom... tss... pah! Taka taka boom!"
        ),
        "loop": (
            "Boom tss boom boom tss... "
            "Boom tss boom boom tss... "
            "Boom tss pah! Taka boom!"
        )
    },

    "trap_basso": {
        "nome": "Trap Bass",
        "emoji": "🔊",
        "descrizione": "Bassi profondi stile trap",
        "pattern": (
            "Brrrrap! Boom boom... skrrt skrrt... "
            "Boom... boom boom... brrap! "
            "Pew pew pew... boom... tss tss... "
            "Skibidi bap bap... boom... "
            "Brrap brrap! Skrrt! Boom boom boom... "
            "Tss tss... brrrrap! Pew!"
        ),
        "loop": (
            "Boom boom skrrt... brrap! "
            "Boom boom pew pew... skrrt! "
            "Brrrrap boom boom!"
        )
    },

    "dubstep_drop": {
        "nome": "Dubstep Drop",
        "emoji": "💥",
        "descrizione": "Wub wub wub... DROP!",
        "pattern": (
            "Wub wub wub wub... "
            "Tss tss tss... "
            "Wub wub wub wub... "
            "BWAAAAAH! "
            "Wicky wicky wub wub... "
            "Dzz dzz dzz... BWAH! "
            "Wub wub... DROOOP! "
            "Bzzz bzzz wub wub wub!"
        ),
        "loop": (
            "Wub wub wub... BWAH! "
            "Wicky wub wub... dzz! "
            "Wub wub DROOOP!"
        )
    },

    "drum_n_bass": {
        "nome": "Drum and Bass",
        "emoji": "🥁",
        "descrizione": "Ritmo veloce e incalzante",
        "pattern": (
            "Taka taka boom... tss taka taka boom... "
            "Taka taka taka taka boom boom... "
            "Prrr taka boom... tss tss... "
            "Taka boom taka boom taka taka boom! "
            "Dugu dugu dugu... boom tss! "
            "Taka taka prrr boom boom!"
        ),
        "loop": (
            "Taka taka boom tss... "
            "Taka taka boom tss... "
            "Dugu dugu boom boom!"
        )
    },

    "reggaeton": {
        "nome": "Reggaeton",
        "emoji": "🌴",
        "descrizione": "Dembow latino",
        "pattern": (
            "Boom... taka tss... boom taka... "
            "Boom... taka tss... boom taka... "
            "Dum dum... pa! Dum dum... pa! "
            "Boom chika boom chika boom chika boom! "
            "Tss boom... taka taka... boom tss... "
            "Chika boom! Chika chika boom!"
        ),
        "loop": (
            "Boom taka tss boom taka... "
            "Dum dum pa! Dum dum pa! "
            "Chika boom chika boom!"
        )
    },

    "freestyle_battle": {
        "nome": "Freestyle Battle",
        "emoji": "🔥",
        "descrizione": "Base per freestyle rap",
        "pattern": (
            "Yo yo yo... check it! "
            "Boom... tss... boom boom... tss... "
            "Uh! Yeah! Boom taka... "
            "Tss tss... boom... uh! "
            "Pah pah! Taka boom... "
            "Check check... boom tss boom! "
            "Yo! Taka taka... boom boom... tss!"
        ),
        "loop": (
            "Boom tss boom boom tss... uh! "
            "Yeah! Boom tss boom boom tss... "
            "Yo! Check it! Boom!"
        )
    },

    "techno_minimal": {
        "nome": "Techno Minimal",
        "emoji": "🎛️",
        "descrizione": "Beat elettronico minimale",
        "pattern": (
            "Unz unz unz unz... "
            "Tss tss tss tss... "
            "Unz unz unz unz... "
            "Boom! Unz unz... "
            "Tss tss unz unz tss tss unz unz... "
            "Doof doof doof doof... "
            "Unz tss unz tss unz tss boom!"
        ),
        "loop": (
            "Unz unz unz unz... "
            "Tss tss tss tss... "
            "Doof doof boom!"
        )
    },

    "jazz_scat": {
        "nome": "Jazz Scat",
        "emoji": "🎷",
        "descrizione": "Scat jazz improvvisato",
        "pattern": (
            "Ski-bi dibby dib yo da dub dub... "
            "Bop bop... shoo bee doo bee... "
            "Ska badabadoo... bee bop! "
            "Doo wop... sha la la... "
            "Ski-bi boom boom... shoo wop! "
            "Ba da ba da... bee bop a loo bop!"
        ),
        "loop": (
            "Ski-bi dibby dib... "
            "Bop bop shoo bee... "
            "Ba da ba boom!"
        )
    },

    "italia_rap": {
        "nome": "Italia Underground",
        "emoji": "🇮🇹",
        "descrizione": "Stile rap italiano",
        "pattern": (
            "Ehi ehi! Boom... tss... "
            "Alza le mani! Boom boom... tss... "
            "Zio! Boom taka... boom taka... "
            "Fra! Tss tss... boom boom... "
            "Bro! Pah! Taka taka boom... "
            "Yeah yeah! Boom tss boom tss boom!"
        ),
        "loop": (
            "Ehi! Boom tss boom boom tss... "
            "Fra! Boom tss boom boom tss... "
            "Zio! Boom boom boom!"
        )
    },

    "robot_glitch": {
        "nome": "Robot Glitch",
        "emoji": "🤖",
        "descrizione": "Suoni robotici glitchati",
        "pattern": (
            "Bip bip boop... bzzzt! "
            "Click clack... bip boop... "
            "Errore! Bzzz bzzz... bip! "
            "Wrrr wrrr... click! Boop! "
            "Sistema... bip... attivo... bzzzt! "
            "Boop boop bip bip... BZZZT!"
        ),
        "loop": (
            "Bip boop bzzzt... "
            "Click clack bip... "
            "Boop boop BZZZT!"
        )
    }
}

# Risposte per introdurre il beatbox
INTRO_FRASI = [
    "Okay, prepara le orecchie! Tre, due, uno...",
    "Check, check! Microfono acceso! Ecco la base!",
    "Yo! Senti questa bomba!",
    "Attenzione che parte il beat!",
    "Pronto? Ecco il mio beatbox!",
]


def get_lista_basi() -> str:
    """Restituisce lista delle basi disponibili"""
    result = "🎤 BASI BEATBOX DISPONIBILI:\n\n"
    for key, base in BASI_BEATBOX.items():
        result += f"{base['emoji']} **{base['nome']}**\n"
        result += f"   _{base['descrizione']}_\n\n"
    result += "Dimmi quale vuoi sentire!"
    return result


def trova_base(richiesta: str) -> tuple:
    """Trova la base richiesta"""
    if not richiesta:
        return None, None

    richiesta_lower = richiesta.lower()

    # Mapping parole chiave -> base
    keywords = {
        "hip hop": "hip_hop_classico",
        "hiphop": "hip_hop_classico",
        "classico": "hip_hop_classico",
        "old school": "hip_hop_classico",
        "boom bap": "hip_hop_classico",

        "trap": "trap_basso",
        "basso": "trap_basso",
        "bass": "trap_basso",
        "skrrt": "trap_basso",

        "dubstep": "dubstep_drop",
        "drop": "dubstep_drop",
        "wub": "dubstep_drop",

        "drum": "drum_n_bass",
        "bass veloce": "drum_n_bass",
        "dnb": "drum_n_bass",
        "veloce": "drum_n_bass",

        "reggaeton": "reggaeton",
        "dembow": "reggaeton",
        "latino": "reggaeton",
        "latina": "reggaeton",

        "freestyle": "freestyle_battle",
        "battle": "freestyle_battle",
        "rap": "freestyle_battle",
        "rapper": "freestyle_battle",

        "techno": "techno_minimal",
        "minimal": "techno_minimal",
        "elettronica": "techno_minimal",
        "discoteca": "techno_minimal",
        "unz": "techno_minimal",

        "jazz": "jazz_scat",
        "scat": "jazz_scat",

        "italia": "italia_rap",
        "italiano": "italia_rap",
        "underground": "italia_rap",
        "zio": "italia_rap",

        "robot": "robot_glitch",
        "glitch": "robot_glitch",
        "robotico": "robot_glitch",
    }

    for keyword, base_key in keywords.items():
        if keyword in richiesta_lower:
            return base_key, BASI_BEATBOX[base_key]

    # Cerca match diretto nel nome
    for key, base in BASI_BEATBOX.items():
        if key.replace("_", " ") in richiesta_lower:
            return key, base
        if base["nome"].lower() in richiesta_lower:
            return key, base

    return None, None


BEATBOX_UMANO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "beatbox_umano",
        "description": (
            "人声打击乐 / Beatbox umano vocale stile rapper e trapper. "
            "Produce beat vocali, basi hip-hop, trap, dubstep, drum and bass. "
            "Use when: 'fammi un beat', 'beatbox', 'fai il beatbox', 'base rap', "
            "'fammi una base', 'beat trap', 'beat hip hop', 'freestyle', "
            "'boom tss', 'fai il rapper', 'beatboxing'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stile": {
                    "type": "string",
                    "description": "Stile beatbox: hip hop, trap, dubstep, drum and bass, reggaeton, freestyle, techno, jazz, italiano, robot"
                },
                "durata": {
                    "type": "string",
                    "description": "Durata: corto, normale, lungo"
                }
            },
            "required": []
        }
    }
}


@register_function('beatbox_umano', BEATBOX_UMANO_FUNCTION_DESC, ToolType.WAIT)
def beatbox_umano(conn, stile: str = None, durata: str = "normale"):
    """Produce beatbox vocale"""

    logger.bind(tag=TAG).info(f"Beatbox richiesto - stile: {stile}, durata: {durata}")

    # Se non specificato stile, mostra lista
    if not stile:
        lista = get_lista_basi()
        return ActionResponse(
            action=Action.RESPONSE,
            result=lista,
            response="Sono un beatboxer! Ho tante basi: hip hop, trap, dubstep, reggaeton, freestyle, techno, jazz e altre! Quale vuoi sentire?"
        )

    # Cerca la base richiesta
    base_key, base = trova_base(stile)

    # Se non trovata, scegli random
    if not base:
        base_key = random.choice(list(BASI_BEATBOX.keys()))
        base = BASI_BEATBOX[base_key]
        intro = f"Non conosco '{stile}', ma ti faccio sentire {base['nome']}! "
    else:
        intro = random.choice(INTRO_FRASI) + " "

    # Costruisci il beat in base alla durata
    if durata and "corto" in durata.lower():
        beat = base["loop"]
    elif durata and "lungo" in durata.lower():
        beat = base["pattern"] + " " + base["loop"] + " " + base["pattern"]
    else:
        beat = base["pattern"]

    # Risultato display
    result = f"{base['emoji']} **{base['nome']}**\n\n"
    result += f"_{base['descrizione']}_\n\n"
    result += f"🎵 {beat}"

    # Versione parlata con intro
    spoken = intro + beat

    return ActionResponse(
        action=Action.RESPONSE,
        result=result,
        response=spoken
    )
