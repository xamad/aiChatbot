"""
Venti Domande Plugin - Gioco di indovinare con sì/no
L'IA pensa a qualcosa e l'utente deve indovinare
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Stato gioco per sessione
VENTI_STATE = {}

# Oggetti da indovinare con proprietà
OGGETTI = [
    {"nome": "gatto", "animale": True, "vivo": True, "domestico": True, "grande": False, "zampe": 4, "vola": False, "nuota": False},
    {"nome": "elefante", "animale": True, "vivo": True, "domestico": False, "grande": True, "zampe": 4, "vola": False, "nuota": False},
    {"nome": "aquila", "animale": True, "vivo": True, "domestico": False, "grande": False, "zampe": 2, "vola": True, "nuota": False},
    {"nome": "delfino", "animale": True, "vivo": True, "domestico": False, "grande": True, "zampe": 0, "vola": False, "nuota": True},
    {"nome": "pizza", "animale": False, "cibo": True, "dolce": False, "italiano": True, "rotondo": True, "caldo": True},
    {"nome": "gelato", "animale": False, "cibo": True, "dolce": True, "italiano": True, "rotondo": False, "caldo": False},
    {"nome": "televisione", "animale": False, "cibo": False, "elettronico": True, "portatile": False, "schermo": True, "suona": True},
    {"nome": "telefono", "animale": False, "cibo": False, "elettronico": True, "portatile": True, "schermo": True, "suona": True},
    {"nome": "libro", "animale": False, "cibo": False, "elettronico": False, "portatile": True, "schermo": False, "carta": True},
    {"nome": "sole", "animale": False, "cibo": False, "naturale": True, "grande": True, "caldo": True, "cielo": True, "rotondo": True},
    {"nome": "luna", "animale": False, "cibo": False, "naturale": True, "grande": True, "caldo": False, "cielo": True, "rotondo": True},
    {"nome": "automobile", "animale": False, "cibo": False, "veicolo": True, "ruote": True, "motore": True, "grande": True},
    {"nome": "bicicletta", "animale": False, "cibo": False, "veicolo": True, "ruote": True, "motore": False, "grande": False},
    {"nome": "pianoforte", "animale": False, "cibo": False, "musicale": True, "grande": True, "tasti": True, "portatile": False},
    {"nome": "chitarra", "animale": False, "cibo": False, "musicale": True, "grande": False, "corde": True, "portatile": True},
]

MAX_DOMANDE = 20

VENTI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "venti_domande",
        "description": (
            "Gioco delle 20 domande - indovina cosa penso."
            "Usare quando: giochiamo a 20 domande, indovina cosa penso, gioco sì no, "
            "venti domande, 20 domande"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start (nuova partita), ask (fai domanda), guess (prova a indovinare)",
                    "enum": ["start", "ask", "guess"]
                },
                "domanda": {
                    "type": "string",
                    "description": "Domanda sì/no dell'utente"
                },
                "risposta": {
                    "type": "string",
                    "description": "Tentativo di indovinare l'oggetto"
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

def rispondi_domanda(oggetto: dict, domanda: str) -> tuple:
    """Analizza la domanda e risponde in base alle proprietà dell'oggetto"""
    domanda = domanda.lower()

    # Mappatura domande -> proprietà
    mapping = {
        ("animale", "essere vivente", "vivo"): "animale",
        ("cibo", "mangiare", "commestibile"): "cibo",
        ("elettronico", "elettrico", "tecnologia", "tecnologico"): "elettronico",
        ("grande", "grosso", "enorme"): "grande",
        ("piccolo", "piccolino"): lambda o: not o.get("grande", True),
        ("vola", "volare", "ali"): "vola",
        ("nuota", "nuotare", "acqua", "mare"): "nuota",
        ("domestico", "casa", "animale domestico"): "domestico",
        ("dolce", "zucchero"): "dolce",
        ("caldo", "bollente", "fuoco"): "caldo",
        ("freddo", "ghiaccio", "fresco"): lambda o: not o.get("caldo", True),
        ("rotondo", "tondo", "circolare"): "rotondo",
        ("italiano", "italia"): "italiano",
        ("ruote", "ruota"): "ruote",
        ("motore",): "motore",
        ("musicale", "musica", "suona", "strumento"): "musicale",
        ("portatile", "portare", "tasca"): "portatile",
        ("cielo", "spazio"): "cielo",
        ("naturale", "natura"): "naturale",
        ("zampe", "gambe"): lambda o: o.get("zampe", 0) > 0,
    }

    for keywords, prop in mapping.items():
        for keyword in keywords:
            if keyword in domanda:
                if callable(prop):
                    result = prop(oggetto)
                else:
                    result = oggetto.get(prop, False)

                if result:
                    return True, "Sì!"
                else:
                    return False, "No."

    # Risposta incerta
    return None, "Non saprei rispondere a questa domanda. Prova a riformularla."

@register_function("venti_domande", VENTI_FUNCTION_DESC, ToolType.WAIT)
def venti_domande(conn, action: str = "start", domanda: str = None, risposta: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"20 Domande: action={action}, domanda={domanda}")

    if action == "start":
        oggetto = random.choice(OGGETTI)

        VENTI_STATE[session_id] = {
            "oggetto": oggetto,
            "domande": 0,
            "in_corso": True,
            "storico": []
        }

        return ActionResponse(Action.RESPONSE,
            f"Ho pensato a qualcosa! Hai {MAX_DOMANDE} domande sì/no per indovinare. Inizia!",
            f"Ok, ho pensato a qualcosa. Hai {MAX_DOMANDE} domande. Fammi una domanda con risposta sì o no!")

    if session_id not in VENTI_STATE or not VENTI_STATE[session_id].get("in_corso"):
        return ActionResponse(Action.RESPONSE,
            "Nessuna partita in corso. Di' 'giochiamo a 20 domande'!",
            "Non c'è una partita in corso. Vuoi iniziare?")

    state = VENTI_STATE[session_id]
    oggetto = state["oggetto"]

    if action == "guess":
        if not risposta:
            return ActionResponse(Action.RESPONSE,
                "Cosa pensi che sia?",
                "Cosa pensi che io stia pensando?")

        state["domande"] += 1

        if risposta.lower() == oggetto["nome"].lower():
            state["in_corso"] = False
            return ActionResponse(Action.RESPONSE,
                f"🎉 ESATTO! Era proprio {oggetto['nome'].upper()}! Indovinato in {state['domande']} domande!",
                f"Bravissimo! Era proprio {oggetto['nome']}! Hai indovinato in {state['domande']} domande!")
        else:
            rimanenti = MAX_DOMANDE - state["domande"]

            if rimanenti <= 0:
                state["in_corso"] = False
                return ActionResponse(Action.RESPONSE,
                    f"❌ No! Hai esaurito le domande. Era: {oggetto['nome'].upper()}",
                    f"Mi dispiace, non era {risposta}. La risposta era {oggetto['nome']}. Vuoi rigiocare?")

            return ActionResponse(Action.RESPONSE,
                f"❌ No, non è {risposta}. Ti restano {rimanenti} domande.",
                f"No, non è {risposta}. Hai ancora {rimanenti} domande. Continua!")

    if action == "ask":
        if not domanda:
            return ActionResponse(Action.RESPONSE,
                "Fammi una domanda!",
                "Fammi una domanda con risposta sì o no")

        state["domande"] += 1
        rimanenti = MAX_DOMANDE - state["domande"]

        _, risposta_text = rispondi_domanda(oggetto, domanda)
        state["storico"].append({"domanda": domanda, "risposta": risposta_text})

        if rimanenti <= 0:
            state["in_corso"] = False
            return ActionResponse(Action.RESPONSE,
                f"{risposta_text}\n\nHai esaurito le domande! Era: {oggetto['nome'].upper()}",
                f"{risposta_text} Hai finito le domande. Era {oggetto['nome']}!")

        if rimanenti <= 5:
            extra = f" Attenzione, solo {rimanenti} domande rimaste!"
        else:
            extra = f" Domande rimaste: {rimanenti}."

        return ActionResponse(Action.RESPONSE,
            f"{risposta_text}{extra}",
            f"{risposta_text}{extra}")

    return ActionResponse(Action.RESPONSE,
        "Vuoi giocare a 20 domande?",
        "Vuoi che pensi a qualcosa e tu indovini?")
