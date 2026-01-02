"""
Conta Acqua Plugin - Traccia i bicchieri d'acqua bevuti
Obiettivo giornaliero 8 bicchieri
"""

import json
import os
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

ACQUA_FILE = "/tmp/xiaozhi_acqua.json"
OBIETTIVO_DEFAULT = 8  # bicchieri al giorno

def load_acqua() -> dict:
    try:
        if os.path.exists(ACQUA_FILE):
            with open(ACQUA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"giorni": {}, "obiettivo": OBIETTIVO_DEFAULT}

def save_acqua(data: dict):
    try:
        with open(ACQUA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio acqua: {e}")

ACQUA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "conta_acqua",
        "description": (
            "Traccia i bicchieri d'acqua bevuti."
            "Usare quando: ho bevuto un bicchiere, acqua, quanta acqua ho bevuto, "
            "conta acqua, bicchiere d'acqua, idratazione"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: add (aggiungi), status (stato), reset (azzera), obiettivo (imposta)",
                    "enum": ["add", "status", "reset", "obiettivo", "history"]
                },
                "quantita": {
                    "type": "integer",
                    "description": "Numero di bicchieri (default 1)"
                },
                "nuovo_obiettivo": {
                    "type": "integer",
                    "description": "Nuovo obiettivo giornaliero"
                }
            },
            "required": ["action"],
        },
    },
}

def get_incoraggiamento(bevuti: int, obiettivo: int) -> str:
    """Genera messaggio di incoraggiamento"""
    percentuale = (bevuti / obiettivo) * 100 if obiettivo > 0 else 0

    if percentuale >= 100:
        messaggi = [
            "Fantastico! Hai raggiunto l'obiettivo!",
            "Bravissimo! Obiettivo completato!",
            "Ottimo lavoro! Hai bevuto abbastanza oggi!",
        ]
    elif percentuale >= 75:
        messaggi = [
            "Quasi al traguardo! Ancora un po'!",
            "Ci sei quasi! Continua così!",
            "Ottimo, manca poco all'obiettivo!",
        ]
    elif percentuale >= 50:
        messaggi = [
            "A metà strada! Continua!",
            "Buon progresso! Vai avanti!",
            "Sei sulla buona strada!",
        ]
    elif percentuale >= 25:
        messaggi = [
            "Buon inizio! Ricorda di bere ancora.",
            "Continua a idratarti!",
            "Stai andando bene!",
        ]
    else:
        messaggi = [
            "Ricorda di bere! L'acqua è importante.",
            "Non dimenticare di idratarti oggi!",
            "Un bicchiere d'acqua fa sempre bene!",
        ]

    import random
    return random.choice(messaggi)

@register_function("conta_acqua", ACQUA_FUNCTION_DESC, ToolType.WAIT)
def conta_acqua(conn, action: str = "status", quantita: int = 1, nuovo_obiettivo: int = None):
    logger.bind(tag=TAG).info(f"Acqua: action={action}, quantita={quantita}")

    data = load_acqua()
    oggi = datetime.now().strftime("%Y-%m-%d")
    obiettivo = data.get("obiettivo", OBIETTIVO_DEFAULT)

    # Inizializza oggi se non esiste
    if oggi not in data.get("giorni", {}):
        if "giorni" not in data:
            data["giorni"] = {}
        data["giorni"][oggi] = {"bicchieri": 0, "orari": []}

    oggi_data = data["giorni"][oggi]

    if action == "add":
        oggi_data["bicchieri"] += quantita
        oggi_data["orari"].append(datetime.now().strftime("%H:%M"))
        save_acqua(data)

        bevuti = oggi_data["bicchieri"]
        mancanti = max(0, obiettivo - bevuti)

        incoraggiamento = get_incoraggiamento(bevuti, obiettivo)

        if quantita == 1:
            msg = f"Registrato 1 bicchiere! Totale oggi: {bevuti}/{obiettivo}. "
        else:
            msg = f"Registrati {quantita} bicchieri! Totale oggi: {bevuti}/{obiettivo}. "

        msg += incoraggiamento

        if mancanti > 0 and bevuti < obiettivo:
            msg += f" Te ne mancano ancora {mancanti}."

        return ActionResponse(Action.RESPONSE, msg, msg)

    if action == "status":
        bevuti = oggi_data["bicchieri"]
        mancanti = max(0, obiettivo - bevuti)
        percentuale = int((bevuti / obiettivo) * 100) if obiettivo > 0 else 0

        # Barra progresso visiva
        barra_piena = "💧" * min(bevuti, obiettivo)
        barra_vuota = "○" * max(0, obiettivo - bevuti)
        barra = barra_piena + barra_vuota

        result = f"Acqua oggi: {bevuti}/{obiettivo} bicchieri ({percentuale}%)\n{barra}"

        if bevuti >= obiettivo:
            spoken = f"Oggi hai bevuto {bevuti} bicchieri, hai raggiunto l'obiettivo di {obiettivo}! Bravo!"
        else:
            spoken = f"Oggi hai bevuto {bevuti} bicchieri su {obiettivo}. Te ne mancano {mancanti}."

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "reset":
        oggi_data["bicchieri"] = 0
        oggi_data["orari"] = []
        save_acqua(data)

        return ActionResponse(Action.RESPONSE,
            "Contatore azzerato",
            "Ho azzerato il contatore dell'acqua per oggi")

    if action == "obiettivo":
        if nuovo_obiettivo and nuovo_obiettivo > 0:
            data["obiettivo"] = nuovo_obiettivo
            save_acqua(data)
            return ActionResponse(Action.RESPONSE,
                f"Obiettivo impostato a {nuovo_obiettivo} bicchieri",
                f"Ho impostato il tuo obiettivo giornaliero a {nuovo_obiettivo} bicchieri")
        else:
            return ActionResponse(Action.RESPONSE,
                f"Obiettivo attuale: {obiettivo} bicchieri",
                f"Il tuo obiettivo attuale è {obiettivo} bicchieri al giorno. Vuoi cambiarlo?")

    if action == "history":
        giorni = data.get("giorni", {})
        if not giorni:
            return ActionResponse(Action.RESPONSE,
                "Nessuno storico",
                "Non ho ancora dati sull'acqua")

        # Ultimi 7 giorni
        result = "Storico acqua:\n"
        spoken = "Negli ultimi giorni: "

        giorni_ordinati = sorted(giorni.items(), reverse=True)[:7]
        totale = 0

        for data_g, info in giorni_ordinati:
            b = info.get("bicchieri", 0)
            totale += b
            emoji = "✓" if b >= obiettivo else ""
            result += f"- {data_g}: {b} bicchieri {emoji}\n"
            spoken += f"{data_g}, {b} bicchieri. "

        media = totale / len(giorni_ordinati) if giorni_ordinati else 0
        result += f"\nMedia: {media:.1f} bicchieri/giorno"
        spoken += f"Media: {media:.1f} bicchieri al giorno."

        return ActionResponse(Action.RESPONSE, result, spoken)

    return ActionResponse(Action.RESPONSE,
        "Vuoi registrare un bicchiere d'acqua?",
        "Dimmi quando bevi e terrò il conto per te!")
