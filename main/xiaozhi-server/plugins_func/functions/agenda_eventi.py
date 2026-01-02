"""
Agenda Eventi Plugin - Calendario vocale
Gestisce appuntamenti e eventi
"""

import json
import os
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

AGENDA_FILE = "/tmp/xiaozhi_agenda.json"

def load_agenda() -> dict:
    try:
        if os.path.exists(AGENDA_FILE):
            with open(AGENDA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"eventi": []}

def save_agenda(data: dict):
    try:
        with open(AGENDA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio agenda: {e}")

AGENDA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "agenda_eventi",
        "description": (
            "Gestisce calendario e appuntamenti. Usa quando l'utente dice: "
            "'aggiungi appuntamento', 'cosa ho domani?', 'agenda', 'calendario', "
            "'il 15 ho il dottore', 'quando ho...', 'prossimi impegni'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: add (aggiungi), today (oggi), tomorrow (domani), week (settimana), find (cerca), remove",
                    "enum": ["add", "today", "tomorrow", "week", "find", "remove"]
                },
                "titolo": {
                    "type": "string",
                    "description": "Titolo/descrizione dell'evento"
                },
                "data": {
                    "type": "string",
                    "description": "Data (es: 15 gennaio, domani, lunedì)"
                },
                "ora": {
                    "type": "string",
                    "description": "Ora dell'evento (es: 10:30, alle 3)"
                }
            },
            "required": ["action"],
        },
    },
}

GIORNI_SETTIMANA = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

def parse_data(data_str: str) -> str:
    """Converte data testuale in formato ISO"""
    if not data_str:
        return datetime.now().strftime("%Y-%m-%d")

    data_str = data_str.lower().strip()
    oggi = datetime.now()

    # Oggi/domani/dopodomani
    if "oggi" in data_str:
        return oggi.strftime("%Y-%m-%d")
    if "domani" in data_str:
        return (oggi + timedelta(days=1)).strftime("%Y-%m-%d")
    if "dopodomani" in data_str:
        return (oggi + timedelta(days=2)).strftime("%Y-%m-%d")

    # Giorno della settimana
    for i, giorno in enumerate(GIORNI_SETTIMANA):
        if giorno in data_str:
            giorni_avanti = (i - oggi.weekday()) % 7
            if giorni_avanti == 0:
                giorni_avanti = 7  # Prossima settimana
            return (oggi + timedelta(days=giorni_avanti)).strftime("%Y-%m-%d")

    # Formato "15 gennaio" o "15/1"
    for i, mese in enumerate(MESI):
        if mese in data_str:
            # Estrai numero giorno
            numeri = [int(s) for s in data_str.split() if s.isdigit()]
            if numeri:
                giorno = numeri[0]
                anno = oggi.year if (i + 1) >= oggi.month else oggi.year + 1
                try:
                    return datetime(anno, i + 1, giorno).strftime("%Y-%m-%d")
                except:
                    pass

    # Prova formato numerico
    for sep in ["/", "-", "."]:
        if sep in data_str:
            parts = data_str.split(sep)
            if len(parts) >= 2:
                try:
                    giorno = int(parts[0])
                    mese = int(parts[1])
                    anno = int(parts[2]) if len(parts) > 2 else oggi.year
                    if anno < 100:
                        anno += 2000
                    return datetime(anno, mese, giorno).strftime("%Y-%m-%d")
                except:
                    pass

    return oggi.strftime("%Y-%m-%d")

def parse_ora(ora_str: str) -> str:
    """Converte ora testuale in formato HH:MM"""
    if not ora_str:
        return "09:00"

    ora_str = ora_str.lower().strip()

    # Rimuovi parole comuni
    for word in ["alle", "ora", "le", "e"]:
        ora_str = ora_str.replace(word, " ")

    ora_str = ora_str.strip()

    # Formato HH:MM
    if ":" in ora_str:
        parts = ora_str.split(":")
        try:
            h = int(parts[0])
            m = int(parts[1])
            return f"{h:02d}:{m:02d}"
        except:
            pass

    # Solo ora
    numeri = [int(s) for s in ora_str.split() if s.isdigit()]
    if numeri:
        h = numeri[0]
        m = numeri[1] if len(numeri) > 1 else 0
        # Assumiamo mattina se < 8, pomeriggio altrimenti
        if h < 8:
            h += 12
        return f"{h:02d}:{m:02d}"

    return "09:00"

def formatta_data_italiano(data_iso: str) -> str:
    """Formatta data in italiano"""
    try:
        dt = datetime.strptime(data_iso, "%Y-%m-%d")
        giorno = GIORNI_SETTIMANA[dt.weekday()]
        return f"{giorno} {dt.day} {MESI[dt.month - 1]}"
    except:
        return data_iso

@register_function("agenda_eventi", AGENDA_FUNCTION_DESC, ToolType.WAIT)
def agenda_eventi(conn, action: str = "today", titolo: str = None, data: str = None, ora: str = None):
    logger.bind(tag=TAG).info(f"Agenda: action={action}, titolo={titolo}, data={data}, ora={ora}")

    agenda = load_agenda()
    eventi = agenda.get("eventi", [])
    oggi = datetime.now().strftime("%Y-%m-%d")

    if action == "add":
        if not titolo:
            return ActionResponse(Action.RESPONSE,
                "Cosa devo aggiungere all'agenda?",
                "Dimmi cosa devo segnare in agenda")

        data_parsed = parse_data(data)
        ora_parsed = parse_ora(ora)

        nuovo_evento = {
            "titolo": titolo,
            "data": data_parsed,
            "ora": ora_parsed,
            "creato": datetime.now().isoformat()
        }

        eventi.append(nuovo_evento)
        # Ordina per data e ora
        eventi.sort(key=lambda x: (x["data"], x["ora"]))
        agenda["eventi"] = eventi
        save_agenda(agenda)

        data_bella = formatta_data_italiano(data_parsed)

        return ActionResponse(Action.RESPONSE,
            f"Aggiunto: {titolo}\n{data_bella} alle {ora_parsed}",
            f"Ho segnato in agenda: {titolo}, {data_bella} alle {ora_parsed}")

    if action == "today":
        eventi_oggi = [e for e in eventi if e["data"] == oggi]

        if not eventi_oggi:
            return ActionResponse(Action.RESPONSE,
                "Nessun impegno per oggi",
                "Non hai impegni per oggi. Vuoi aggiungere qualcosa?")

        result = f"📅 Oggi, {formatta_data_italiano(oggi)}:\n\n"
        spoken = "Oggi hai: "

        for e in sorted(eventi_oggi, key=lambda x: x["ora"]):
            result += f"• {e['ora']} - {e['titolo']}\n"
            spoken += f"alle {e['ora']}, {e['titolo']}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "tomorrow":
        domani = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        eventi_domani = [e for e in eventi if e["data"] == domani]

        if not eventi_domani:
            return ActionResponse(Action.RESPONSE,
                "Nessun impegno per domani",
                "Non hai impegni per domani")

        result = f"📅 Domani, {formatta_data_italiano(domani)}:\n\n"
        spoken = "Domani hai: "

        for e in sorted(eventi_domani, key=lambda x: x["ora"]):
            result += f"• {e['ora']} - {e['titolo']}\n"
            spoken += f"alle {e['ora']}, {e['titolo']}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "week":
        fine_settimana = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        eventi_settimana = [e for e in eventi if oggi <= e["data"] <= fine_settimana]

        if not eventi_settimana:
            return ActionResponse(Action.RESPONSE,
                "Nessun impegno questa settimana",
                "Non hai impegni nei prossimi 7 giorni")

        result = "📅 Prossimi 7 giorni:\n\n"
        spoken = "Questa settimana hai: "

        for e in sorted(eventi_settimana, key=lambda x: (x["data"], x["ora"])):
            data_bella = formatta_data_italiano(e["data"])
            result += f"• {data_bella} {e['ora']} - {e['titolo']}\n"
            spoken += f"{data_bella} alle {e['ora']}, {e['titolo']}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "find":
        if not titolo:
            return ActionResponse(Action.RESPONSE,
                "Cosa stai cercando?",
                "Dimmi cosa cercare nell'agenda")

        trovati = [e for e in eventi if titolo.lower() in e["titolo"].lower()]

        if not trovati:
            return ActionResponse(Action.RESPONSE,
                f"Non trovo '{titolo}' in agenda",
                f"Non ho trovato {titolo} nell'agenda")

        result = f"Trovati {len(trovati)} eventi:\n\n"
        spoken = f"Ho trovato {len(trovati)} eventi: "

        for e in trovati:
            data_bella = formatta_data_italiano(e["data"])
            result += f"• {data_bella} {e['ora']} - {e['titolo']}\n"
            spoken += f"{data_bella}, {e['titolo']}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "remove":
        if not titolo:
            return ActionResponse(Action.RESPONSE,
                "Quale evento vuoi eliminare?",
                "Dimmi quale evento eliminare")

        trovati = [e for e in eventi if titolo.lower() in e["titolo"].lower()]

        if not trovati:
            return ActionResponse(Action.RESPONSE,
                f"Non trovo '{titolo}' in agenda",
                f"Non ho trovato {titolo} nell'agenda")

        evento_rimosso = trovati[0]
        agenda["eventi"] = [e for e in eventi if e != evento_rimosso]
        save_agenda(agenda)

        return ActionResponse(Action.RESPONSE,
            f"Eliminato: {evento_rimosso['titolo']}",
            f"Ho eliminato {evento_rimosso['titolo']} dall'agenda")

    return ActionResponse(Action.RESPONSE,
        "Cosa vuoi fare con l'agenda?",
        "Posso aggiungere eventi o dirti i tuoi impegni")
