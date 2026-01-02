"""
Impiccato Plugin - Gioco dell'impiccato vocale
Indovina la parola lettera per lettera
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Stato gioco per sessione
IMPICCATO_STATE = {}

# Parole per categoria
PAROLE = {
    "animali": ["gatto", "cane", "elefante", "giraffa", "tigre", "leone", "zebra", "pappagallo", "delfino", "farfalla"],
    "cibi": ["pizza", "pasta", "gelato", "tiramisù", "lasagna", "risotto", "focaccia", "bruschetta", "cannolo", "parmigiano"],
    "città": ["roma", "milano", "napoli", "firenze", "venezia", "torino", "bologna", "palermo", "genova", "verona"],
    "oggetti": ["telefono", "computer", "televisione", "automobile", "bicicletta", "orologio", "lampada", "finestra", "tavolo", "bottiglia"],
    "natura": ["montagna", "oceano", "foresta", "fiume", "deserto", "vulcano", "cascata", "prateria", "isola", "spiaggia"],
}

MAX_ERRORI = 6

IMPICCATO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "impiccato",
        "description": (
            "Gioco dell'impiccato - indovina la parola."
            "Usare quando: giochiamo all'impiccato, indovina la parola, gioco lettere, "
            "provo la lettera, impiccato"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start (nuova partita), guess (prova lettera), word (prova parola), status",
                    "enum": ["start", "guess", "word", "status"]
                },
                "categoria": {
                    "type": "string",
                    "description": "Categoria parole: animali, cibi, città, oggetti, natura"
                },
                "lettera": {
                    "type": "string",
                    "description": "Lettera da provare"
                },
                "parola": {
                    "type": "string",
                    "description": "Parola completa da indovinare"
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

def get_display_word(parola: str, lettere_trovate: set) -> str:
    """Mostra parola con lettere indovinate e trattini"""
    display = ""
    for lettera in parola:
        if lettera.lower() in lettere_trovate or lettera == " ":
            display += lettera.upper() + " "
        else:
            display += "_ "
    return display.strip()

def get_impiccato_ascii(errori: int) -> str:
    """ASCII art dell'impiccato"""
    stadi = [
        """
  +---+
  |   |
      |
      |
      |
      |
=========""",
        """
  +---+
  |   |
  O   |
      |
      |
      |
=========""",
        """
  +---+
  |   |
  O   |
  |   |
      |
      |
=========""",
        """
  +---+
  |   |
  O   |
 /|   |
      |
      |
=========""",
        """
  +---+
  |   |
  O   |
 /|\\  |
      |
      |
=========""",
        """
  +---+
  |   |
  O   |
 /|\\  |
 /    |
      |
=========""",
        """
  +---+
  |   |
  O   |
 /|\\  |
 / \\  |
      |
========="""
    ]
    return stadi[min(errori, len(stadi) - 1)]

@register_function("impiccato", IMPICCATO_FUNCTION_DESC, ToolType.WAIT)
def impiccato(conn, action: str = "start", categoria: str = None, lettera: str = None, parola: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Impiccato: action={action}, lettera={lettera}")

    if action == "start":
        # Nuova partita
        if not categoria or categoria not in PAROLE:
            categoria = random.choice(list(PAROLE.keys()))

        parola_segreta = random.choice(PAROLE[categoria])

        IMPICCATO_STATE[session_id] = {
            "parola": parola_segreta,
            "categoria": categoria,
            "lettere_provate": set(),
            "lettere_trovate": set(),
            "errori": 0,
            "in_corso": True
        }

        display = get_display_word(parola_segreta, set())

        result = f"Nuova partita! Categoria: {categoria}\n\n{display}\n\nLa parola ha {len(parola_segreta)} lettere. Prova una lettera!"
        spoken = f"Iniziamo! Categoria {categoria}. La parola ha {len(parola_segreta)} lettere. Di' una lettera!"

        return ActionResponse(Action.RESPONSE, result, spoken)

    # Verifica partita in corso
    if session_id not in IMPICCATO_STATE or not IMPICCATO_STATE[session_id].get("in_corso"):
        return ActionResponse(Action.RESPONSE,
            "Nessuna partita in corso. Di' 'inizia impiccato' per giocare!",
            "Non c'è una partita in corso. Vuoi iniziare?")

    state = IMPICCATO_STATE[session_id]
    parola_segreta = state["parola"]

    if action == "status":
        display = get_display_word(parola_segreta, state["lettere_trovate"])
        provate = ", ".join(sorted(state["lettere_provate"])) or "nessuna"
        errori = state["errori"]

        result = f"{get_impiccato_ascii(errori)}\n\n{display}\n\nErrori: {errori}/{MAX_ERRORI}\nLettere provate: {provate}"
        spoken = f"La parola è {display.replace('_', 'trattino')}. Hai fatto {errori} errori su {MAX_ERRORI}. Lettere provate: {provate}"

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "word":
        # Prova parola intera
        if not parola:
            return ActionResponse(Action.RESPONSE,
                "Quale parola vuoi provare?",
                "Dimmi la parola che vuoi provare")

        if parola.lower() == parola_segreta.lower():
            state["in_corso"] = False
            state["lettere_trovate"] = set(parola_segreta.lower())

            result = f"🎉 ESATTO! La parola era: {parola_segreta.upper()}\n\nHai vinto con {state['errori']} errori!"
            spoken = f"Esatto! Hai indovinato! La parola era {parola_segreta}. Bravo!"

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            state["errori"] += 1

            if state["errori"] >= MAX_ERRORI:
                state["in_corso"] = False
                result = f"❌ Sbagliato! Hai perso!\n\nLa parola era: {parola_segreta.upper()}"
                spoken = f"Mi dispiace, la parola era {parola_segreta}. Vuoi riprovare?"
                return ActionResponse(Action.RESPONSE, result, spoken)

            display = get_display_word(parola_segreta, state["lettere_trovate"])
            result = f"❌ Non è {parola}!\n\n{get_impiccato_ascii(state['errori'])}\n\n{display}\n\nErrori: {state['errori']}/{MAX_ERRORI}"
            spoken = f"No, non è {parola}. Errori {state['errori']} su {MAX_ERRORI}. Continua!"

            return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "guess":
        if not lettera:
            return ActionResponse(Action.RESPONSE,
                "Quale lettera vuoi provare?",
                "Dimmi una lettera")

        lettera = lettera.lower()[0]  # Prima lettera

        if lettera in state["lettere_provate"]:
            return ActionResponse(Action.RESPONSE,
                f"Hai già provato la lettera {lettera.upper()}!",
                f"Hai già provato la {lettera}! Prova un'altra lettera.")

        state["lettere_provate"].add(lettera)

        if lettera in parola_segreta.lower():
            state["lettere_trovate"].add(lettera)
            display = get_display_word(parola_segreta, state["lettere_trovate"])

            # Controlla vittoria
            if "_" not in display:
                state["in_corso"] = False
                result = f"🎉 BRAVO! Hai indovinato: {parola_segreta.upper()}\n\nErrori: {state['errori']}/{MAX_ERRORI}"
                spoken = f"Fantastico! Hai indovinato! La parola era {parola_segreta}!"
                return ActionResponse(Action.RESPONSE, result, spoken)

            # Conta occorrenze
            occorrenze = parola_segreta.lower().count(lettera)

            result = f"✓ Sì! '{lettera.upper()}' è presente {occorrenze} volta/e!\n\n{display}"
            spoken = f"Sì! La lettera {lettera} c'è {occorrenze} volta. {display.replace('_', 'trattino')}"

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            state["errori"] += 1

            if state["errori"] >= MAX_ERRORI:
                state["in_corso"] = False
                result = f"❌ '{lettera.upper()}' non c'è!\n\n{get_impiccato_ascii(state['errori'])}\n\nHai perso! La parola era: {parola_segreta.upper()}"
                spoken = f"Mi dispiace, la lettera {lettera} non c'era e hai perso! La parola era {parola_segreta}."
                return ActionResponse(Action.RESPONSE, result, spoken)

            display = get_display_word(parola_segreta, state["lettere_trovate"])
            rimanenti = MAX_ERRORI - state["errori"]

            result = f"✗ '{lettera.upper()}' non c'è!\n\n{get_impiccato_ascii(state['errori'])}\n\n{display}\n\nTentativi rimasti: {rimanenti}"
            spoken = f"No, la lettera {lettera} non c'è. Ti restano {rimanenti} tentativi."

            return ActionResponse(Action.RESPONSE, result, spoken)

    return ActionResponse(Action.RESPONSE,
        "Vuoi giocare all'impiccato?",
        "Vuoi iniziare una partita?")
