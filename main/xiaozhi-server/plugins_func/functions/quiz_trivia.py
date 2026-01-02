"""
Quiz e Trivia Plugin - Giochi a quiz vocali
Domande di cultura generale, storia, geografia, scienza, sport
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Stato corrente quiz per sessione
QUIZ_STATE = {}

# Database domande per categoria
QUIZ_DATABASE = {
    "cultura_generale": [
        {"q": "Qual è la capitale della Francia?", "a": "parigi", "options": ["Parigi", "Londra", "Berlino", "Madrid"]},
        {"q": "Quanti continenti ci sono?", "a": "7", "options": ["5", "6", "7", "8"]},
        {"q": "Chi ha dipinto la Gioconda?", "a": "leonardo", "options": ["Leonardo da Vinci", "Michelangelo", "Raffaello", "Botticelli"]},
        {"q": "Qual è l'oceano più grande?", "a": "pacifico", "options": ["Atlantico", "Pacifico", "Indiano", "Artico"]},
        {"q": "In che anno l'uomo è andato sulla Luna?", "a": "1969", "options": ["1965", "1969", "1972", "1975"]},
        {"q": "Qual è il fiume più lungo del mondo?", "a": "nilo", "options": ["Rio delle Amazzoni", "Nilo", "Yangtze", "Mississippi"]},
        {"q": "Quante ossa ha il corpo umano adulto?", "a": "206", "options": ["206", "186", "226", "256"]},
        {"q": "Qual è il pianeta più grande del sistema solare?", "a": "giove", "options": ["Saturno", "Giove", "Urano", "Nettuno"]},
    ],
    "italia": [
        {"q": "Qual è la capitale d'Italia?", "a": "roma", "options": ["Roma", "Milano", "Napoli", "Firenze"]},
        {"q": "Quante regioni ha l'Italia?", "a": "20", "options": ["18", "20", "22", "25"]},
        {"q": "In che anno è stata unificata l'Italia?", "a": "1861", "options": ["1848", "1861", "1870", "1880"]},
        {"q": "Qual è il vulcano più alto d'Europa?", "a": "etna", "options": ["Vesuvio", "Etna", "Stromboli", "Vulcano"]},
        {"q": "Quale città italiana è famosa per la pizza?", "a": "napoli", "options": ["Roma", "Milano", "Napoli", "Palermo"]},
        {"q": "Chi ha scritto la Divina Commedia?", "a": "dante", "options": ["Dante", "Petrarca", "Boccaccio", "Ariosto"]},
        {"q": "Qual è il lago più grande d'Italia?", "a": "garda", "options": ["Como", "Maggiore", "Garda", "Trasimeno"]},
        {"q": "In quale regione si trova Venezia?", "a": "veneto", "options": ["Lombardia", "Veneto", "Friuli", "Emilia-Romagna"]},
    ],
    "sport": [
        {"q": "Quanti giocatori ci sono in una squadra di calcio?", "a": "11", "options": ["9", "10", "11", "12"]},
        {"q": "In che sport si usa la racchetta e il volano?", "a": "badminton", "options": ["Tennis", "Badminton", "Squash", "Ping pong"]},
        {"q": "Ogni quanti anni si tengono le Olimpiadi?", "a": "4", "options": ["2", "3", "4", "5"]},
        {"q": "In quale città si trova il Camp Nou?", "a": "barcellona", "options": ["Madrid", "Barcellona", "Milano", "Monaco"]},
        {"q": "Quanti set deve vincere un tennista per vincere a Wimbledon (uomini)?", "a": "3", "options": ["2", "3", "4", "5"]},
        {"q": "Di che colore è la maglia del leader al Tour de France?", "a": "gialla", "options": ["Rosa", "Gialla", "Verde", "Rossa"]},
    ],
    "scienza": [
        {"q": "Qual è il simbolo chimico dell'oro?", "a": "au", "options": ["Au", "Ag", "Fe", "Cu"]},
        {"q": "Quanti denti ha un adulto?", "a": "32", "options": ["28", "30", "32", "34"]},
        {"q": "Qual è l'organo più grande del corpo umano?", "a": "pelle", "options": ["Fegato", "Cervello", "Pelle", "Polmoni"]},
        {"q": "Che gas respiriamo principalmente?", "a": "azoto", "options": ["Ossigeno", "Azoto", "Carbonio", "Idrogeno"]},
        {"q": "A quanti gradi bolle l'acqua?", "a": "100", "options": ["90", "100", "110", "120"]},
        {"q": "Chi ha formulato la teoria della relatività?", "a": "einstein", "options": ["Newton", "Einstein", "Galileo", "Hawking"]},
    ],
    "musica_cinema": [
        {"q": "Chi ha composto la Nona Sinfonia?", "a": "beethoven", "options": ["Mozart", "Beethoven", "Bach", "Vivaldi"]},
        {"q": "In che anno è uscito il primo film di Star Wars?", "a": "1977", "options": ["1975", "1977", "1980", "1983"]},
        {"q": "Chi ha diretto Titanic?", "a": "cameron", "options": ["Spielberg", "Cameron", "Scorsese", "Nolan"]},
        {"q": "Quante corde ha una chitarra classica?", "a": "6", "options": ["4", "5", "6", "8"]},
        {"q": "Chi interpreta Iron Man nei film Marvel?", "a": "downey", "options": ["Chris Evans", "Robert Downey Jr", "Chris Hemsworth", "Mark Ruffalo"]},
    ],
}

QUIZ_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "quiz_trivia",
        "description": (
            "Gioco quiz a domande vocali."
            "Usare quando: facciamo un quiz, domanda di cultura generale, gioco a trivia, "
            "quiz sull'Italia, domanda di sport, la risposta è"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start (nuova domanda), answer (risposta), score (punteggio)",
                    "enum": ["start", "answer", "score", "hint"]
                },
                "category": {
                    "type": "string",
                    "description": "Categoria: cultura_generale, italia, sport, scienza, musica_cinema",
                    "enum": ["cultura_generale", "italia", "sport", "scienza", "musica_cinema", "random"]
                },
                "response": {
                    "type": "string",
                    "description": "Risposta dell'utente alla domanda"
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
    """Verifica se la risposta è corretta"""
    correct = correct.lower().strip()
    response = response.lower().strip()

    # Match esatto
    if correct == response:
        return True

    # Match parziale
    if correct in response or response in correct:
        return True

    # Numeri
    try:
        if float(correct) == float(response):
            return True
    except:
        pass

    return False


@register_function("quiz_trivia", QUIZ_FUNCTION_DESC, ToolType.WAIT)
def quiz_trivia(conn, action: str = "start", category: str = "random", response: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Quiz: action={action}, category={category}, response={response}")

    # Inizializza stato sessione
    if session_id not in QUIZ_STATE:
        QUIZ_STATE[session_id] = {
            "score": 0,
            "total": 0,
            "current_question": None,
            "current_answer": None,
        }

    state = QUIZ_STATE[session_id]

    if action == "score":
        score = state["score"]
        total = state["total"]
        if total == 0:
            return ActionResponse(Action.RESPONSE,
                "Non hai ancora risposto a nessuna domanda",
                "Non hai ancora giocato. Vuoi iniziare un quiz?")

        percentage = int((score / total) * 100)
        return ActionResponse(Action.RESPONSE,
            f"Punteggio: {score}/{total} ({percentage}%)",
            f"Hai totalizzato {score} risposte corrette su {total}. Il {percentage} percento!")

    if action == "answer":
        if not state["current_question"]:
            return ActionResponse(Action.RESPONSE,
                "Non c'è nessuna domanda attiva",
                "Non c'è una domanda in corso. Vuoi iniziare un quiz?")

        if not response:
            return ActionResponse(Action.RESPONSE,
                "Qual è la tua risposta?",
                "Dimmi la tua risposta")

        correct_answer = state["current_answer"]
        is_correct = check_answer(correct_answer, response)

        state["total"] += 1
        if is_correct:
            state["score"] += 1
            state["current_question"] = None
            state["current_answer"] = None

            messages = [
                "Corretto! Bravissimo!",
                "Esatto! Ottimo lavoro!",
                "Giusto! Sei preparato!",
                "Perfetto! Continua così!",
            ]
            return ActionResponse(Action.RESPONSE,
                f"✓ Corretto! Punteggio: {state['score']}/{state['total']}",
                random.choice(messages) + f" Punteggio: {state['score']} su {state['total']}. Vuoi un'altra domanda?")
        else:
            state["current_question"] = None
            state["current_answer"] = None

            return ActionResponse(Action.RESPONSE,
                f"✗ Sbagliato! La risposta era: {correct_answer}. Punteggio: {state['score']}/{state['total']}",
                f"Mi dispiace, la risposta corretta era {correct_answer}. Punteggio: {state['score']} su {state['total']}. Vuoi riprovare?")

    if action == "hint":
        if not state["current_answer"]:
            return ActionResponse(Action.RESPONSE,
                "Non c'è nessuna domanda attiva",
                "Non c'è una domanda in corso")

        answer = state["current_answer"]
        hint = answer[0] + "..." if len(answer) > 1 else "..."
        return ActionResponse(Action.RESPONSE,
            f"Suggerimento: inizia con '{answer[0].upper()}'",
            f"Ti do un aiutino: la risposta inizia con la lettera {answer[0].upper()}")

    if action == "start":
        # Scegli categoria
        if category == "random" or category not in QUIZ_DATABASE:
            category = random.choice(list(QUIZ_DATABASE.keys()))

        questions = QUIZ_DATABASE[category]
        question = random.choice(questions)

        state["current_question"] = question["q"]
        state["current_answer"] = question["a"]

        # Formatta opzioni se presenti
        options_text = ""
        if "options" in question:
            options_text = "\nOpzioni: " + ", ".join(question["options"])

        category_names = {
            "cultura_generale": "cultura generale",
            "italia": "Italia",
            "sport": "sport",
            "scienza": "scienza",
            "musica_cinema": "musica e cinema",
        }

        return ActionResponse(Action.RESPONSE,
            f"[{category_names.get(category, category)}] {question['q']}{options_text}",
            f"Domanda di {category_names.get(category, category)}: {question['q']}")

    return ActionResponse(Action.RESPONSE, "Azione non riconosciuta", "Non ho capito")
