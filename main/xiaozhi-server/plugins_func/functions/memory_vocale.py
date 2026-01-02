"""
Memory Vocale Plugin - Gioco di memoria con sequenze
Ripeti sequenze di numeri, parole o colori
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

MEMORY_STATE = {}

# Elementi per le sequenze
NUMERI = ["uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove"]
COLORI = ["rosso", "blu", "verde", "giallo", "arancione", "viola", "bianco", "nero"]
PAROLE = ["casa", "sole", "luna", "mare", "monte", "fiore", "albero", "stella", "nuvola", "vento"]
ANIMALI = ["gatto", "cane", "uccello", "pesce", "cavallo", "leone", "tigre", "orso"]

MEMORY_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "memory_vocale",
        "description": (
            "Gioco di memoria - ripeti la sequenza."
            "Usare quando: giochiamo a memory, allena la memoria, gioco sequenze, "
            "ripeti la sequenza, memory vocale, brain training"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start (nuova partita), answer (risposta), next (prossimo livello)",
                    "enum": ["start", "answer", "next"]
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo sequenza: numeri, colori, parole, animali",
                    "enum": ["numeri", "colori", "parole", "animali"]
                },
                "risposta": {
                    "type": "string",
                    "description": "Sequenza ripetuta dall'utente"
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

def genera_sequenza(tipo: str, lunghezza: int) -> list:
    """Genera una sequenza casuale"""
    elementi = {
        "numeri": NUMERI,
        "colori": COLORI,
        "parole": PAROLE,
        "animali": ANIMALI
    }
    pool = elementi.get(tipo, NUMERI)
    return [random.choice(pool) for _ in range(lunghezza)]

def normalizza(testo: str) -> list:
    """Normalizza la risposta dell'utente"""
    testo = testo.lower().strip()
    # Rimuovi punteggiatura
    for c in ",.;:!?":
        testo = testo.replace(c, " ")
    # Dividi in parole
    parole = [p.strip() for p in testo.split() if p.strip()]
    return parole

def confronta_sequenze(corretta: list, risposta: list) -> tuple:
    """Confronta due sequenze e conta errori"""
    errori = 0
    min_len = min(len(corretta), len(risposta))

    for i in range(min_len):
        if corretta[i].lower() != risposta[i].lower():
            errori += 1

    # Aggiungi errori per lunghezza diversa
    errori += abs(len(corretta) - len(risposta))

    return errori == 0, errori

@register_function("memory_vocale", MEMORY_FUNCTION_DESC, ToolType.WAIT)
def memory_vocale(conn, action: str = "start", tipo: str = "numeri", risposta: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Memory: action={action}, tipo={tipo}")

    if action == "start":
        if tipo not in ["numeri", "colori", "parole", "animali"]:
            tipo = "numeri"

        # Inizia con sequenza di 3 elementi
        sequenza = genera_sequenza(tipo, 3)

        MEMORY_STATE[session_id] = {
            "tipo": tipo,
            "livello": 1,
            "sequenza": sequenza,
            "punteggio": 0,
            "record": 0,
            "in_corso": True
        }

        seq_text = ", ".join(sequenza)

        return ActionResponse(Action.RESPONSE,
            f"🧠 Memory - Livello 1 ({tipo})\n\nRipeti: {seq_text}",
            f"Gioco memory con {tipo}! Livello 1. Ascolta e ripeti: {seq_text}")

    if session_id not in MEMORY_STATE or not MEMORY_STATE[session_id].get("in_corso"):
        return ActionResponse(Action.RESPONSE,
            "Nessuna partita in corso. Di' 'giochiamo a memory'!",
            "Non c'è una partita. Vuoi iniziare?")

    state = MEMORY_STATE[session_id]

    if action == "answer":
        if not risposta:
            seq_text = ", ".join(state["sequenza"])
            return ActionResponse(Action.RESPONSE,
                f"Ripeti la sequenza: {seq_text}",
                f"Ripeti la sequenza: {seq_text}")

        risposta_parole = normalizza(risposta)
        corretto, errori = confronta_sequenze(state["sequenza"], risposta_parole)

        if corretto:
            state["punteggio"] += state["livello"]
            state["record"] = max(state["record"], state["livello"])

            return ActionResponse(Action.RESPONSE,
                f"✅ CORRETTO! Punteggio: {state['punteggio']}\n\nDi' 'avanti' per il prossimo livello!",
                f"Esatto! Bravissimo! Punteggio {state['punteggio']}. Di' avanti per continuare!")
        else:
            seq_corretta = ", ".join(state["sequenza"])
            risposta_text = ", ".join(risposta_parole) if risposta_parole else "vuoto"

            # Riprova stesso livello
            nuova_sequenza = genera_sequenza(state["tipo"], len(state["sequenza"]))
            state["sequenza"] = nuova_sequenza

            return ActionResponse(Action.RESPONSE,
                f"❌ Sbagliato! ({errori} errori)\n\nEra: {seq_corretta}\nHai detto: {risposta_text}\n\nNuova sequenza: {', '.join(nuova_sequenza)}",
                f"Mi dispiace, era {seq_corretta}. Riprova! Nuova sequenza: {', '.join(nuova_sequenza)}")

    if action == "next":
        state["livello"] += 1
        lunghezza = 2 + state["livello"]  # Aumenta con il livello

        sequenza = genera_sequenza(state["tipo"], lunghezza)
        state["sequenza"] = sequenza

        seq_text = ", ".join(sequenza)

        return ActionResponse(Action.RESPONSE,
            f"🧠 Livello {state['livello']} ({lunghezza} elementi)\n\nRipeti: {seq_text}",
            f"Livello {state['livello']}! {lunghezza} elementi. Ascolta: {seq_text}")

    return ActionResponse(Action.RESPONSE,
        "Vuoi giocare a memory?",
        "Vuoi allenare la memoria?")
