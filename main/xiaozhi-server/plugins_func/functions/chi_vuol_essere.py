"""
Chi Vuol Essere Milionario Plugin - Quiz con aiuti
Domande a difficoltà crescente con 3 aiuti
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

MILIONARIO_STATE = {}

# Premi per livello
PREMI = ["100€", "200€", "300€", "500€", "1.000€", "2.000€", "4.000€", "8.000€", "16.000€", "32.000€", "64.000€", "125.000€", "250.000€", "500.000€", "1.000.000€"]
TRAGUARDI = [4, 9]  # Livelli sicuri (500€ e 32.000€)

# Domande per difficoltà
DOMANDE = {
    "facili": [
        {"domanda": "Qual è la capitale d'Italia?", "corretta": "Roma", "opzioni": ["Milano", "Roma", "Napoli", "Firenze"]},
        {"domanda": "Quante zampe ha un gatto?", "corretta": "4", "opzioni": ["2", "4", "6", "8"]},
        {"domanda": "Di che colore è il sole?", "corretta": "Giallo", "opzioni": ["Rosso", "Blu", "Giallo", "Verde"]},
        {"domanda": "Quale animale fa 'miao'?", "corretta": "Gatto", "opzioni": ["Cane", "Gatto", "Mucca", "Pecora"]},
        {"domanda": "Quanti giorni ha una settimana?", "corretta": "7", "opzioni": ["5", "6", "7", "8"]},
    ],
    "medie": [
        {"domanda": "Chi ha dipinto la Gioconda?", "corretta": "Leonardo da Vinci", "opzioni": ["Michelangelo", "Leonardo da Vinci", "Raffaello", "Botticelli"]},
        {"domanda": "In che anno l'uomo è andato sulla Luna?", "corretta": "1969", "opzioni": ["1959", "1965", "1969", "1972"]},
        {"domanda": "Qual è il fiume più lungo d'Italia?", "corretta": "Po", "opzioni": ["Tevere", "Arno", "Po", "Adige"]},
        {"domanda": "Quante regioni ha l'Italia?", "corretta": "20", "opzioni": ["15", "18", "20", "22"]},
        {"domanda": "Chi scrisse la Divina Commedia?", "corretta": "Dante Alighieri", "opzioni": ["Petrarca", "Boccaccio", "Dante Alighieri", "Manzoni"]},
    ],
    "difficili": [
        {"domanda": "In che anno fu fondata Roma?", "corretta": "753 a.C.", "opzioni": ["753 a.C.", "509 a.C.", "264 a.C.", "476 d.C."]},
        {"domanda": "Qual è l'elemento chimico con simbolo Au?", "corretta": "Oro", "opzioni": ["Argento", "Oro", "Alluminio", "Arsenico"]},
        {"domanda": "Chi inventò la radio?", "corretta": "Guglielmo Marconi", "opzioni": ["Alessandro Volta", "Guglielmo Marconi", "Antonio Meucci", "Galileo Galilei"]},
        {"domanda": "Quanti sono i pianeti del Sistema Solare?", "corretta": "8", "opzioni": ["7", "8", "9", "10"]},
        {"domanda": "In quale città si trova il Colosseo?", "corretta": "Roma", "opzioni": ["Napoli", "Roma", "Firenze", "Venezia"]},
    ],
    "esperto": [
        {"domanda": "Qual è la montagna più alta d'Europa?", "corretta": "Monte Bianco", "opzioni": ["Monte Rosa", "Monte Bianco", "Cervino", "Gran Paradiso"]},
        {"domanda": "Chi fu il primo presidente della Repubblica Italiana?", "corretta": "Enrico De Nicola", "opzioni": ["Luigi Einaudi", "Enrico De Nicola", "Giovanni Gronchi", "Antonio Segni"]},
        {"domanda": "In che anno cadde l'Impero Romano d'Occidente?", "corretta": "476 d.C.", "opzioni": ["410 d.C.", "455 d.C.", "476 d.C.", "493 d.C."]},
        {"domanda": "Qual è la formula chimica dell'acqua?", "corretta": "H2O", "opzioni": ["CO2", "H2O", "NaCl", "O2"]},
    ],
}

MILIONARIO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "chi_vuol_essere",
        "description": (
            "Quiz stile Chi Vuol Essere Milionario."
            "Usare quando: chi vuol essere milionario, quiz milionario, giochiamo al milionario, "
            "risposta A B C D, uso il 50 e 50, chiedo l'aiuto"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: start, answer, aiuto_50, aiuto_pubblico, aiuto_telefono, ritira",
                    "enum": ["start", "answer", "aiuto_50", "aiuto_pubblico", "aiuto_telefono", "ritira"]
                },
                "risposta": {
                    "type": "string",
                    "description": "Risposta: A, B, C o D"
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

def get_domanda(livello: int) -> dict:
    """Seleziona domanda in base al livello"""
    if livello < 5:
        pool = DOMANDE["facili"]
    elif livello < 10:
        pool = DOMANDE["medie"]
    elif livello < 13:
        pool = DOMANDE["difficili"]
    else:
        pool = DOMANDE["esperto"]

    domanda = random.choice(pool).copy()
    # Mescola opzioni
    random.shuffle(domanda["opzioni"])
    return domanda

def formatta_domanda(domanda: dict, livello: int, premio: str) -> tuple:
    """Formatta domanda per output"""
    lettere = ["A", "B", "C", "D"]
    opzioni_text = "\n".join([f"{lettere[i]}) {domanda['opzioni'][i]}" for i in range(4)])

    result = f"💰 Domanda {livello + 1} - Per {premio}\n\n"
    result += f"{domanda['domanda']}\n\n{opzioni_text}"

    spoken = f"Domanda numero {livello + 1}, per {premio}. {domanda['domanda']}. "
    spoken += " ".join([f"{lettere[i]}, {domanda['opzioni'][i]}." for i in range(4)])

    return result, spoken

@register_function("chi_vuol_essere", MILIONARIO_FUNCTION_DESC, ToolType.WAIT)
def chi_vuol_essere(conn, action: str = "start", risposta: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Milionario: action={action}, risposta={risposta}")

    if action == "start":
        domanda = get_domanda(0)

        MILIONARIO_STATE[session_id] = {
            "livello": 0,
            "domanda_corrente": domanda,
            "aiuti": {"50_50": True, "pubblico": True, "telefono": True},
            "opzioni_rimosse": [],
            "in_corso": True
        }

        result, spoken = formatta_domanda(domanda, 0, PREMI[0])
        result += "\n\n🎯 Aiuti: 50:50 | 👥 Pubblico | 📞 Telefono"

        return ActionResponse(Action.RESPONSE, result, spoken + " Hai tutti e 3 gli aiuti disponibili.")

    if session_id not in MILIONARIO_STATE or not MILIONARIO_STATE[session_id].get("in_corso"):
        return ActionResponse(Action.RESPONSE,
            "Nessuna partita. Di' 'chi vuol essere milionario' per iniziare!",
            "Non c'è una partita. Vuoi giocare?")

    state = MILIONARIO_STATE[session_id]
    livello = state["livello"]
    domanda = state["domanda_corrente"]

    if action == "ritira":
        state["in_corso"] = False
        if livello > 0:
            premio_vinto = PREMI[livello - 1]
            return ActionResponse(Action.RESPONSE,
                f"🎉 Ti ritiri con {premio_vinto}! La risposta era: {domanda['corretta']}",
                f"Ti ritiri! Porti a casa {premio_vinto}. La risposta era {domanda['corretta']}.")
        else:
            return ActionResponse(Action.RESPONSE,
                "Ti ritiri a mani vuote! Peccato.",
                "Ti ritiri senza aver risposto. Peccato!")

    if action == "aiuto_50":
        if not state["aiuti"]["50_50"]:
            return ActionResponse(Action.RESPONSE,
                "Hai già usato il 50 e 50!",
                "Hai già usato questo aiuto!")

        state["aiuti"]["50_50"] = False

        # Rimuovi 2 risposte sbagliate
        corretta = domanda["corretta"]
        sbagliate = [o for o in domanda["opzioni"] if o != corretta]
        da_rimuovere = random.sample(sbagliate, 2)
        state["opzioni_rimosse"] = da_rimuovere

        lettere = ["A", "B", "C", "D"]
        opzioni_rimaste = []
        for i, opt in enumerate(domanda["opzioni"]):
            if opt not in da_rimuovere:
                opzioni_rimaste.append(f"{lettere[i]}) {opt}")

        return ActionResponse(Action.RESPONSE,
            f"50:50 - Rimangono:\n\n" + "\n".join(opzioni_rimaste),
            f"Cinquanta e cinquanta! Rimangono: {' e '.join([o.split(') ')[1] for o in opzioni_rimaste])}")

    if action == "aiuto_pubblico":
        if not state["aiuti"]["pubblico"]:
            return ActionResponse(Action.RESPONSE,
                "Hai già usato l'aiuto del pubblico!",
                "Hai già usato questo aiuto!")

        state["aiuti"]["pubblico"] = False

        # Simula voti pubblico (favorisce la risposta corretta)
        corretta = domanda["corretta"]
        lettere = ["A", "B", "C", "D"]
        percentuali = {}

        voto_corretta = random.randint(45, 75)
        rimanente = 100 - voto_corretta

        for i, opt in enumerate(domanda["opzioni"]):
            if opt == corretta:
                percentuali[lettere[i]] = voto_corretta
            elif opt not in state.get("opzioni_rimosse", []):
                p = random.randint(1, max(rimanente - 1, 1)) if rimanente > 1 else max(rimanente, 0)
                percentuali[lettere[i]] = p
                rimanente = max(0, rimanente - p)
            else:
                percentuali[lettere[i]] = 0

        result = "👥 Il pubblico ha votato:\n\n"
        spoken = "Il pubblico ha votato: "
        for l in lettere:
            if percentuali.get(l, 0) > 0:
                result += f"{l}: {'█' * (percentuali[l] // 10)} {percentuali[l]}%\n"
                spoken += f"{l}, {percentuali[l]} percento. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "aiuto_telefono":
        if not state["aiuti"]["telefono"]:
            return ActionResponse(Action.RESPONSE,
                "Hai già usato la telefonata!",
                "Hai già usato questo aiuto!")

        state["aiuti"]["telefono"] = False

        corretta = domanda["corretta"]
        lettere = ["A", "B", "C", "D"]
        lettera_corretta = lettere[domanda["opzioni"].index(corretta)]

        # L'amico è sicuro all'80%
        if random.random() < 0.8:
            risposta_amico = lettera_corretta
            certezza = random.choice(["sono abbastanza sicuro", "direi proprio", "secondo me è"])
        else:
            opzioni_valide = [l for l, o in zip(lettere, domanda["opzioni"]) if o not in state.get("opzioni_rimosse", [])]
            risposta_amico = random.choice(opzioni_valide)
            certezza = random.choice(["non sono sicurissimo ma", "forse è", "proverei con"])

        return ActionResponse(Action.RESPONSE,
            f"📞 Il tuo amico dice: \"{certezza.capitalize()} la {risposta_amico}!\"",
            f"Il tuo amico al telefono dice: {certezza} la {risposta_amico}!")

    if action == "answer":
        if not risposta:
            return ActionResponse(Action.RESPONSE,
                "Qual è la tua risposta? A, B, C o D?",
                "Dimmi la tua risposta: A, B, C o D?")

        risposta = risposta.upper().strip()[0]
        if risposta not in ["A", "B", "C", "D"]:
            return ActionResponse(Action.RESPONSE,
                "Risposta non valida. Scegli A, B, C o D.",
                "Non ho capito. Di' A, B, C o D.")

        lettere = ["A", "B", "C", "D"]
        idx = lettere.index(risposta)
        risposta_data = domanda["opzioni"][idx]
        corretta = domanda["corretta"]

        if risposta_data == corretta:
            premio = PREMI[livello]

            if livello >= len(PREMI) - 1:
                # VITTORIA FINALE!
                state["in_corso"] = False
                return ActionResponse(Action.RESPONSE,
                    f"🎉🎉🎉 HAI VINTO UN MILIONE DI EURO! 🎉🎉🎉\n\nRisposta esatta: {corretta}",
                    f"Esatto! Hai vinto UN MILIONE DI EURO! Incredibile! Complimenti!")

            # Prossima domanda
            state["livello"] += 1
            nuova_domanda = get_domanda(state["livello"])
            state["domanda_corrente"] = nuova_domanda
            state["opzioni_rimosse"] = []

            result = f"✅ ESATTO! Hai vinto {premio}!\n\n"

            if livello + 1 in TRAGUARDI:
                result += f"🔒 Traguardo raggiunto! Non puoi scendere sotto {premio}.\n\n"

            next_result, next_spoken = formatta_domanda(nuova_domanda, state["livello"], PREMI[state["livello"]])
            result += next_result

            aiuti = []
            if state["aiuti"]["50_50"]: aiuti.append("50:50")
            if state["aiuti"]["pubblico"]: aiuti.append("Pubblico")
            if state["aiuti"]["telefono"]: aiuti.append("Telefono")

            if aiuti:
                result += f"\n\n🎯 Aiuti rimasti: {' | '.join(aiuti)}"

            spoken = f"Esatto! Hai vinto {premio}! " + next_spoken

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            # SBAGLIATO
            state["in_corso"] = False

            # Trova traguardo sicuro
            premio_finale = "0€"
            for t in TRAGUARDI:
                if livello > t:
                    premio_finale = PREMI[t]

            return ActionResponse(Action.RESPONSE,
                f"❌ SBAGLIATO!\n\nLa risposta corretta era: {corretta}\n\nPorti a casa: {premio_finale}",
                f"Mi dispiace, è sbagliato! La risposta era {corretta}. Porti a casa {premio_finale}.")

    return ActionResponse(Action.RESPONSE,
        "Vuoi giocare a Chi Vuol Essere Milionario?",
        "Vuoi giocare?")
