"""
Check Benessere Plugin - Controllo periodico stato di salute
Chiede come sta l'utente e traccia le risposte
"""

import json
import os
import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

BENESSERE_FILE = "/tmp/xiaozhi_benessere.json"

def load_benessere() -> dict:
    try:
        if os.path.exists(BENESSERE_FILE):
            with open(BENESSERE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"check_history": [], "ultimo_check": None}

def save_benessere(data: dict):
    try:
        with open(BENESSERE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio benessere: {e}")

# Domande sul benessere
DOMANDE_BENESSERE = [
    "Come ti senti oggi?",
    "Hai dormito bene stanotte?",
    "Hai mangiato qualcosa di buono?",
    "Ti sei mosso un po' oggi?",
    "Come va l'umore?",
    "Hai bevuto abbastanza acqua?",
    "Hai parlato con qualcuno oggi?",
    "C'è qualcosa che ti preoccupa?",
]

# Risposte empatiche
RISPOSTE_POSITIVE = [
    "Che bello sentirti bene! Continua così!",
    "Fantastico! È una gioia sentirti stare bene.",
    "Ottimo! Sono contento che le cose vadano bene.",
    "Bene! È importante stare bene con se stessi.",
]

RISPOSTE_NEUTRE = [
    "Capisco. Ogni giorno ha i suoi momenti.",
    "Ok, l'importante è andare avanti.",
    "Va bene, un passo alla volta.",
]

RISPOSTE_NEGATIVE = [
    "Mi dispiace sentirti così. Posso fare qualcosa per aiutarti?",
    "Capisco che sia difficile. Vuoi parlarne?",
    "Sono qui con te. Non sei solo.",
    "Le giornate difficili passano. Vuoi che facciamo qualcosa insieme?",
]

CHECK_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "check_benessere",
        "description": (
            "Controlla il benessere dell'utente."
            "Usare quando: come sto, controllo benessere, check salute, "
            "mi sento, non sto bene, sto bene"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: check (controllo), report (risposta utente), history (storico)",
                    "enum": ["check", "report", "history"]
                },
                "stato": {
                    "type": "string",
                    "description": "Stato riportato: bene, così_così, male"
                },
                "dettaglio": {
                    "type": "string",
                    "description": "Dettaglio aggiuntivo"
                }
            },
            "required": ["action"],
        },
    },
}

def valuta_stato(stato: str) -> str:
    """Valuta lo stato dalle parole usate"""
    stato = stato.lower()

    positivi = ["bene", "benissimo", "ottimo", "felice", "contento", "sereno", "bene bene", "alla grande"]
    negativi = ["male", "malissimo", "triste", "abbattuto", "depresso", "stanco", "preoccupato"]

    for p in positivi:
        if p in stato:
            return "positivo"

    for n in negativi:
        if n in stato:
            return "negativo"

    return "neutro"

@register_function("check_benessere", CHECK_FUNCTION_DESC, ToolType.WAIT)
def check_benessere(conn, action: str = "check", stato: str = None, dettaglio: str = None):
    logger.bind(tag=TAG).info(f"Check benessere: action={action}, stato={stato}")

    data = load_benessere()
    history = data.get("check_history", [])

    if action == "check":
        # Fai una domanda sul benessere
        domanda = random.choice(DOMANDE_BENESSERE)

        data["ultimo_check"] = datetime.now().isoformat()
        save_benessere(data)

        return ActionResponse(Action.RESPONSE,
            f"💚 **Check Benessere**\n\n{domanda}",
            domanda)

    if action == "report":
        if not stato:
            return ActionResponse(Action.RESPONSE,
                "Come ti senti?",
                "Dimmi come ti senti oggi")

        # Valuta lo stato
        valutazione = valuta_stato(stato)

        # Registra
        history.append({
            "timestamp": datetime.now().isoformat(),
            "stato": stato,
            "valutazione": valutazione,
            "dettaglio": dettaglio or ""
        })

        # Mantieni solo ultimi 30 check
        data["check_history"] = history[-30:]
        save_benessere(data)

        # Rispondi in base alla valutazione
        if valutazione == "positivo":
            risposta = random.choice(RISPOSTE_POSITIVE)
        elif valutazione == "negativo":
            risposta = random.choice(RISPOSTE_NEGATIVE)
        else:
            risposta = random.choice(RISPOSTE_NEUTRE)

        emoji = {"positivo": "😊", "negativo": "🤗", "neutro": "🙂"}[valutazione]

        result = f"{emoji} {risposta}"

        return ActionResponse(Action.RESPONSE, result, risposta)

    if action == "history":
        if not history:
            return ActionResponse(Action.RESPONSE,
                "Non ho ancora dati sul tuo benessere",
                "Non abbiamo ancora fatto check insieme. Vuoi iniziare?")

        # Ultimi 7 check
        ultimi = history[-7:]

        # Statistiche
        positivi = sum(1 for h in ultimi if h["valutazione"] == "positivo")
        negativi = sum(1 for h in ultimi if h["valutazione"] == "negativo")
        neutri = len(ultimi) - positivi - negativi

        result = "📊 **Riepilogo Benessere**\n\n"
        result += f"Ultimi {len(ultimi)} check:\n"
        result += f"• 😊 Positivi: {positivi}\n"
        result += f"• 🙂 Neutri: {neutri}\n"
        result += f"• 😔 Negativi: {negativi}\n"

        if positivi >= len(ultimi) * 0.7:
            commento = "Stai andando alla grande! Continua così."
        elif negativi >= len(ultimi) * 0.5:
            commento = "Sembra un periodo difficile. Ricorda che sono qui per te."
        else:
            commento = "Un mix di alti e bassi, è normale. L'importante è andare avanti."

        result += f"\n_{commento}_"

        spoken = f"Negli ultimi {len(ultimi)} check, {positivi} erano positivi, {neutri} neutri e {negativi} negativi. {commento}"

        return ActionResponse(Action.RESPONSE, result, spoken)

    return ActionResponse(Action.RESPONSE,
        "Vuoi fare un check del benessere?",
        "Vuoi che ti chieda come stai?")
