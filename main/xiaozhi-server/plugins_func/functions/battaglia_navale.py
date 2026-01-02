"""
Battaglia Navale Plugin - Gioco classico in versione vocale
Griglia 5x5 semplificata per uso vocale
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

BATTAGLIA_STATE = {}

# Griglia 5x5 (A-E, 1-5)
LETTERE = ["A", "B", "C", "D", "E"]
NUMERI = ["1", "2", "3", "4", "5"]

# Navi: nome, dimensione
NAVI = [
    ("Portaerei", 3),
    ("Incrociatore", 2),
    ("Sottomarino", 2),
]

BATTAGLIA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "battaglia_navale",
        "description": (
            "Gioco battaglia navale vocale (affonda la flotta)."
            "Usare quando: battaglia navale, giochiamo a battaglia navale, affonda le navi, "
            "affonda la flotta, gioco navi, spara A3 B2"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start (nuova partita), fire (spara), status (situazione)",
                    "enum": ["start", "fire", "status"]
                },
                "coordinata": {
                    "type": "string",
                    "description": "Coordinata di tiro (es: A3, B2, C5)"
                }
            },
            "required": ["action"],
        },
    },
}

def get_session_id(conn) -> str:
    try:
        return conn.session_id if hasattr(conn, 'session_id') else str(id(conn))
    except:
        return str(id(conn))

def crea_griglia() -> dict:
    """Crea griglia vuota"""
    griglia = {}
    for l in LETTERE:
        for n in NUMERI:
            griglia[f"{l}{n}"] = {"stato": "acqua", "nave": None}
    return griglia

def piazza_navi(griglia: dict) -> list:
    """Piazza le navi casualmente"""
    navi_piazzate = []

    for nome, dimensione in NAVI:
        piazzata = False
        tentativi = 0

        while not piazzata and tentativi < 50:
            tentativi += 1

            # Direzione casuale
            orizzontale = random.choice([True, False])

            if orizzontale:
                l_idx = random.randint(0, len(LETTERE) - 1)
                n_idx = random.randint(0, len(NUMERI) - dimensione)
                celle = [f"{LETTERE[l_idx]}{NUMERI[n_idx + i]}" for i in range(dimensione)]
            else:
                l_idx = random.randint(0, len(LETTERE) - dimensione)
                n_idx = random.randint(0, len(NUMERI) - 1)
                celle = [f"{LETTERE[l_idx + i]}{NUMERI[n_idx]}" for i in range(dimensione)]

            # Controlla se celle libere
            if all(griglia[c]["stato"] == "acqua" for c in celle):
                for c in celle:
                    griglia[c]["stato"] = "nave"
                    griglia[c]["nave"] = nome
                navi_piazzate.append({"nome": nome, "celle": celle, "colpite": 0})
                piazzata = True

    return navi_piazzate

def parse_coordinata(coord: str) -> str:
    """Normalizza coordinata"""
    coord = coord.upper().strip().replace(" ", "")

    # Cerca pattern lettera-numero
    lettera = None
    numero = None

    for c in coord:
        if c in LETTERE:
            lettera = c
        elif c in NUMERI:
            numero = c

    if lettera and numero:
        return f"{lettera}{numero}"
    return None

def mostra_griglia(griglia: dict, mostra_navi: bool = False) -> str:
    """Mostra griglia testuale"""
    result = "   1  2  3  4  5\n"

    for l in LETTERE:
        result += f"{l} "
        for n in NUMERI:
            cella = griglia[f"{l}{n}"]
            stato = cella["stato"]

            if stato == "colpito":
                result += " X "
            elif stato == "mancato":
                result += " O "
            elif stato == "nave" and mostra_navi:
                result += " # "
            else:
                result += " ~ "
        result += "\n"

    return result

@register_function("battaglia_navale", BATTAGLIA_FUNCTION_DESC, ToolType.WAIT)
def battaglia_navale(conn, action: str = "start", coordinata: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Battaglia: action={action}, coord={coordinata}")

    if action == "start":
        griglia = crea_griglia()
        navi = piazza_navi(griglia)

        BATTAGLIA_STATE[session_id] = {
            "griglia": griglia,
            "navi": navi,
            "tiri": 0,
            "colpi": 0,
            "affondate": 0,
            "in_corso": True
        }

        return ActionResponse(Action.RESPONSE,
            f"⚓ BATTAGLIA NAVALE\n\n{mostra_griglia(griglia)}\n\nHo piazzato {len(navi)} navi. Spara! (es: A3, B2)",
            f"Battaglia navale! Ho piazzato {len(navi)} navi nella griglia 5 per 5. Le coordinate sono da A a E e da 1 a 5. Dove spari?")

    if session_id not in BATTAGLIA_STATE or not BATTAGLIA_STATE[session_id].get("in_corso"):
        return ActionResponse(Action.RESPONSE,
            "Nessuna partita. Di' 'battaglia navale' per iniziare!",
            "Non c'è una partita. Vuoi iniziare?")

    state = BATTAGLIA_STATE[session_id]
    griglia = state["griglia"]
    navi = state["navi"]

    if action == "status":
        navi_rimaste = len(navi) - state["affondate"]
        result = f"⚓ Situazione\n\n{mostra_griglia(griglia)}\n\n"
        result += f"Tiri: {state['tiri']} | Colpi: {state['colpi']} | Navi rimaste: {navi_rimaste}"

        spoken = f"Hai fatto {state['tiri']} tiri, {state['colpi']} colpi a segno. "
        spoken += f"Restano {navi_rimaste} navi da affondare."

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "fire":
        if not coordinata:
            return ActionResponse(Action.RESPONSE,
                "Dove spari? (es: A3, B2, C5)",
                "Dimmi le coordinate! Per esempio A3 o B2.")

        coord = parse_coordinata(coordinata)

        if not coord or coord not in griglia:
            return ActionResponse(Action.RESPONSE,
                f"Coordinata non valida: {coordinata}. Usa formato A1-E5.",
                f"Non ho capito {coordinata}. Di' una lettera da A a E e un numero da 1 a 5.")

        cella = griglia[coord]
        state["tiri"] += 1

        if cella["stato"] in ["colpito", "mancato"]:
            return ActionResponse(Action.RESPONSE,
                f"Hai già sparato in {coord}! Prova un'altra casella.",
                f"Hai già colpito {coord}. Prova un'altra coordinata.")

        if cella["stato"] == "nave":
            cella["stato"] = "colpito"
            state["colpi"] += 1
            nome_nave = cella["nave"]

            # Controlla se affondata
            for nave in navi:
                if nave["nome"] == nome_nave:
                    nave["colpite"] += 1
                    if nave["colpite"] >= len(nave["celle"]):
                        state["affondate"] += 1

                        # Controlla vittoria
                        if state["affondate"] >= len(navi):
                            state["in_corso"] = False
                            result = f"💥 COLPITO E AFFONDATO: {nome_nave}!\n\n"
                            result += f"🎉 HAI VINTO!\n\nTiri: {state['tiri']} | Precisione: {int(state['colpi']/state['tiri']*100)}%"
                            return ActionResponse(Action.RESPONSE, result,
                                f"Colpito e affondato {nome_nave}! Hai vinto in {state['tiri']} tiri! Complimenti!")

                        result = f"💥 COLPITO E AFFONDATO: {nome_nave}!\n\n{mostra_griglia(griglia)}\n\nNavi rimaste: {len(navi) - state['affondate']}"
                        return ActionResponse(Action.RESPONSE, result,
                            f"Colpito e affondato {nome_nave}! Restano {len(navi) - state['affondate']} navi.")
                    break

            result = f"💥 COLPITO in {coord}!\n\n{mostra_griglia(griglia)}"
            return ActionResponse(Action.RESPONSE, result, f"Colpito in {coord}! Continua!")

        else:
            cella["stato"] = "mancato"
            result = f"💦 Acqua in {coord}.\n\n{mostra_griglia(griglia)}"
            return ActionResponse(Action.RESPONSE, result, f"Acqua in {coord}. Riprova!")

    return ActionResponse(Action.RESPONSE,
        "Vuoi giocare a battaglia navale?",
        "Vuoi giocare a battaglia navale?")
