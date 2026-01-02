"""
Cruciverba Vocale Plugin - Definizioni stile Settimana Enigmistica
Quiz di parole con definizioni criptiche e normali
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Stato gioco per sessione
CRUCIVERBA_STATE = {}

# Database definizioni stile Settimana Enigmistica
DEFINIZIONI = {
    "facili": [
        {"definizione": "Il re degli animali", "risposta": "leone", "lettere": 5},
        {"definizione": "Capitale d'Italia", "risposta": "roma", "lettere": 4},
        {"definizione": "Il colore del cielo", "risposta": "blu", "lettere": 3},
        {"definizione": "Il contrario di giorno", "risposta": "notte", "lettere": 5},
        {"definizione": "L'animale che fa miao", "risposta": "gatto", "lettere": 5},
        {"definizione": "L'animale che fa bau", "risposta": "cane", "lettere": 4},
        {"definizione": "Il satellite della Terra", "risposta": "luna", "lettere": 4},
        {"definizione": "Lo beviamo ogni mattina, è nero", "risposta": "caffe", "lettere": 5},
        {"definizione": "Il frutto giallo delle scimmie", "risposta": "banana", "lettere": 6},
        {"definizione": "Dove nuotano i pesci", "risposta": "mare", "lettere": 4},
    ],
    "medie": [
        {"definizione": "Il fiume che passa per Roma", "risposta": "tevere", "lettere": 6},
        {"definizione": "La torre pendente si trova a...", "risposta": "pisa", "lettere": 4},
        {"definizione": "L'inventore della lampadina", "risposta": "edison", "lettere": 6},
        {"definizione": "Il pianeta rosso", "risposta": "marte", "lettere": 5},
        {"definizione": "L'autore della Divina Commedia", "risposta": "dante", "lettere": 5},
        {"definizione": "Pittore della Gioconda", "risposta": "leonardo", "lettere": 8},
        {"definizione": "La moneta europea", "risposta": "euro", "lettere": 4},
        {"definizione": "Lo sport con la racchetta e la pallina gialla", "risposta": "tennis", "lettere": 6},
        {"definizione": "Il vulcano siciliano", "risposta": "etna", "lettere": 4},
        {"definizione": "La città dei canali", "risposta": "venezia", "lettere": 7},
    ],
    "difficili": [
        {"definizione": "Può precedere sia mosca che cadere", "risposta": "carta", "lettere": 5},  # carta mosca, carta che cade
        {"definizione": "È bianca ma non è neve, dolce ma non è miele", "risposta": "zucchero", "lettere": 8},
        {"definizione": "Ha le mani ma non può applaudire", "risposta": "orologio", "lettere": 8},
        {"definizione": "Più è grande meno si vede", "risposta": "buio", "lettere": 4},
        {"definizione": "Ha denti ma non morde", "risposta": "pettine", "lettere": 7},
        {"definizione": "Cade sempre ma non si fa mai male", "risposta": "pioggia", "lettere": 7},
        {"definizione": "Ha un occhio solo ma non può vedere", "risposta": "ago", "lettere": 3},
        {"definizione": "Viaggia in tutto il mondo restando in un angolo", "risposta": "francobollo", "lettere": 11},
        {"definizione": "Ha le gambe ma non cammina", "risposta": "tavolo", "lettere": 6},
        {"definizione": "Ha la testa ma non pensa", "risposta": "chiodo", "lettere": 6},
    ],
    "criptiche": [  # Stile vero Settimana Enigmistica
        {"definizione": "Diede il nome al fenomeno dell'udito", "risposta": "eco", "lettere": 3},
        {"definizione": "Finisce sempre in bellezza", "risposta": "za", "lettere": 2},  # bellez-ZA
        {"definizione": "Nell'auto sta davanti al posto", "risposta": "cruscotto", "lettere": 9},
        {"definizione": "Mette fine alla noia", "risposta": "ia", "lettere": 2},  # no-IA
        {"definizione": "Sta in mezzo al mare", "risposta": "a", "lettere": 1},  # m-A-re
        {"definizione": "È nel cuore di Roma", "risposta": "om", "lettere": 2},  # r-OM-a
    ],
}

CRUCIVERBA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "cruciverba_vocale",
        "description": (
            "Gioco cruciverba stile Settimana Enigmistica."
            "Usare quando: cruciverba, giochiamo a cruciverba, definizione, indovinello, "
            "enigmistica, gioco di parole, quiz parole"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start (nuova definizione), answer (risposta), hint (aiuto), score (punteggio)",
                    "enum": ["start", "answer", "hint", "score"]
                },
                "difficulty": {
                    "type": "string",
                    "description": "Difficoltà: facili, medie, difficili, criptiche",
                    "enum": ["facili", "medie", "difficili", "criptiche", "random"]
                },
                "response": {
                    "type": "string",
                    "description": "Risposta dell'utente"
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


def check_answer(correct: str, response: str) -> bool:
    """Verifica risposta (tollerante su accenti e maiuscole)"""
    correct = correct.lower().strip()
    response = response.lower().strip()

    # Match esatto
    if correct == response:
        return True

    # Rimuovi accenti per confronto
    import unicodedata
    def remove_accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s)
                      if unicodedata.category(c) != 'Mn')

    if remove_accents(correct) == remove_accents(response):
        return True

    return False


@register_function("cruciverba_vocale", CRUCIVERBA_FUNCTION_DESC, ToolType.WAIT)
def cruciverba_vocale(conn, action: str = "start", difficulty: str = "random", response: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Cruciverba: action={action}, difficulty={difficulty}, response={response}")

    # Inizializza stato
    if session_id not in CRUCIVERBA_STATE:
        CRUCIVERBA_STATE[session_id] = {
            "score": 0,
            "total": 0,
            "current": None,
            "hints_used": 0,
        }

    state = CRUCIVERBA_STATE[session_id]

    if action == "score":
        score = state["score"]
        total = state["total"]
        if total == 0:
            return ActionResponse(Action.RESPONSE,
                "Non hai ancora risposto a nessuna definizione",
                "Non hai ancora giocato. Vuoi iniziare?")

        percentage = int((score / total) * 100) if total > 0 else 0
        return ActionResponse(Action.RESPONSE,
            f"Punteggio: {score}/{total} ({percentage}%)",
            f"Hai indovinato {score} definizioni su {total}. Il {percentage} percento!")

    if action == "hint":
        if not state["current"]:
            return ActionResponse(Action.RESPONSE,
                "Non c'è nessuna definizione attiva",
                "Non c'è una definizione in corso. Vuoi iniziare?")

        risposta = state["current"]["risposta"]
        lettere = state["current"]["lettere"]

        # Mostra prima e ultima lettera
        if len(risposta) >= 3:
            hint = f"{risposta[0].upper()}{'_' * (len(risposta) - 2)}{risposta[-1].upper()}"
        else:
            hint = f"{risposta[0].upper()}{'_' * (len(risposta) - 1)}"

        state["hints_used"] += 1

        return ActionResponse(Action.RESPONSE,
            f"Aiuto: {hint} ({lettere} lettere)",
            f"Ti aiuto: la parola è {hint}, con {lettere} lettere")

    if action == "answer":
        if not state["current"]:
            return ActionResponse(Action.RESPONSE,
                "Non c'è nessuna definizione attiva",
                "Non c'è una definizione in corso. Vuoi iniziare?")

        if not response:
            return ActionResponse(Action.RESPONSE,
                "Qual è la tua risposta?",
                "Dimmi la tua risposta")

        risposta_corretta = state["current"]["risposta"]
        is_correct = check_answer(risposta_corretta, response)

        state["total"] += 1

        if is_correct:
            state["score"] += 1
            state["current"] = None
            state["hints_used"] = 0

            risposte_positive = [
                "Esatto! Complimenti!",
                "Corretto! Sei bravissimo!",
                "Giusto! Continua così!",
                "Perfetto! Grande intuizione!",
            ]
            return ActionResponse(Action.RESPONSE,
                f"✓ Corretto! Era proprio '{risposta_corretta}'. Punteggio: {state['score']}/{state['total']}",
                f"{random.choice(risposte_positive)} Punteggio: {state['score']} su {state['total']}. Altra definizione?")
        else:
            state["current"] = None
            state["hints_used"] = 0

            return ActionResponse(Action.RESPONSE,
                f"✗ Sbagliato! La risposta era: {risposta_corretta}. Punteggio: {state['score']}/{state['total']}",
                f"Mi dispiace, la risposta corretta era {risposta_corretta}. Punteggio {state['score']} su {state['total']}. Vuoi riprovare?")

    if action == "start":
        # Scegli difficoltà
        if difficulty == "random":
            difficulty = random.choice(list(DEFINIZIONI.keys()))

        if difficulty not in DEFINIZIONI:
            difficulty = "facili"

        # Scegli definizione casuale
        definizione = random.choice(DEFINIZIONI[difficulty])
        state["current"] = definizione
        state["hints_used"] = 0

        diff_names = {
            "facili": "facile",
            "medie": "media",
            "difficili": "difficile",
            "criptiche": "criptica"
        }

        return ActionResponse(Action.RESPONSE,
            f"[{diff_names.get(difficulty, difficulty)}] {definizione['definizione']} ({definizione['lettere']} lettere)",
            f"Definizione {diff_names.get(difficulty, 'di livello')} {difficulty}: {definizione['definizione']}. La parola ha {definizione['lettere']} lettere. Qual è la risposta?")

    return ActionResponse(Action.RESPONSE,
        "Vuoi giocare al cruciverba?",
        "Vuoi che ti dia una definizione stile Settimana Enigmistica?")
