"""
Promemoria Farmaci Plugin - Gestisce promemoria per medicine
Con orari specifici e nomi dei farmaci
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# File persistenza
FARMACI_FILE = "/tmp/xiaozhi_farmaci.json"

# Stato attivo per sessione
FARMACI_ACTIVE = {}

def load_farmaci() -> dict:
    """Carica farmaci da file"""
    try:
        if os.path.exists(FARMACI_FILE):
            with open(FARMACI_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento farmaci: {e}")
    return {"farmaci": []}

def save_farmaci(data: dict):
    """Salva farmaci su file"""
    try:
        with open(FARMACI_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio farmaci: {e}")

FARMACI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "promemoria_farmaci",
        "description": (
            "Gestisce promemoria per farmaci e medicine."
            "Usare quando: ricordami la pastiglia, devo prendere la medicina, "
            "promemoria farmaco, quali medicine devo prendere"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: add (aggiungi), remove (rimuovi), list (elenca), check (prossimo)",
                    "enum": ["add", "remove", "list", "check"]
                },
                "nome_farmaco": {
                    "type": "string",
                    "description": "Nome del farmaco"
                },
                "orari": {
                    "type": "string",
                    "description": "Orari separati da virgola (es: '8:00, 14:00, 20:00')"
                },
                "note": {
                    "type": "string",
                    "description": "Note aggiuntive (es: 'dopo i pasti', 'a stomaco vuoto')"
                }
            },
            "required": ["action"],
        },
    },
}

def parse_orari(orari_str: str) -> list:
    """Converte stringa orari in lista"""
    if not orari_str:
        return []

    orari = []
    for orario in orari_str.replace(";", ",").split(","):
        orario = orario.strip()
        # Normalizza formato
        if ":" not in orario:
            if len(orario) <= 2:
                orario = f"{orario}:00"
        orari.append(orario)

    return orari

def get_prossimo_farmaco(farmaci: list) -> tuple:
    """Trova il prossimo farmaco da prendere"""
    now = datetime.now()
    ora_corrente = now.strftime("%H:%M")

    prossimo = None
    prossimo_orario = None
    min_diff = float('inf')

    for farmaco in farmaci:
        for orario in farmaco.get("orari", []):
            try:
                h, m = map(int, orario.split(":"))
                orario_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)

                # Se l'orario è passato, considera domani
                if orario_dt < now:
                    orario_dt += timedelta(days=1)

                diff = (orario_dt - now).total_seconds()
                if diff < min_diff:
                    min_diff = diff
                    prossimo = farmaco
                    prossimo_orario = orario
            except:
                continue

    return prossimo, prossimo_orario, min_diff

@register_function("promemoria_farmaci", FARMACI_FUNCTION_DESC, ToolType.WAIT)
def promemoria_farmaci(conn, action: str = "list", nome_farmaco: str = None,
                       orari: str = None, note: str = None):
    logger.bind(tag=TAG).info(f"Farmaci: action={action}, nome={nome_farmaco}, orari={orari}")

    data = load_farmaci()
    farmaci = data.get("farmaci", [])

    if action == "list":
        if not farmaci:
            return ActionResponse(Action.RESPONSE,
                "Nessun farmaco registrato",
                "Non hai farmaci registrati. Vuoi aggiungerne uno?")

        result = "I tuoi farmaci:\n"
        spoken = "I tuoi farmaci sono: "

        for f in farmaci:
            orari_str = ", ".join(f.get("orari", []))
            note_str = f" ({f.get('note', '')})" if f.get('note') else ""
            result += f"- {f['nome']}: {orari_str}{note_str}\n"
            spoken += f"{f['nome']} alle {orari_str}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "check":
        if not farmaci:
            return ActionResponse(Action.RESPONSE,
                "Nessun farmaco registrato",
                "Non hai farmaci registrati")

        prossimo, orario, secondi = get_prossimo_farmaco(farmaci)

        if prossimo:
            minuti = int(secondi / 60)
            ore = int(minuti / 60)
            minuti = minuti % 60

            if ore > 0:
                tempo = f"{ore} ore e {minuti} minuti"
            else:
                tempo = f"{minuti} minuti"

            note_str = f". {prossimo.get('note', '')}" if prossimo.get('note') else ""

            return ActionResponse(Action.RESPONSE,
                f"Prossimo: {prossimo['nome']} alle {orario} (tra {tempo}){note_str}",
                f"Il prossimo farmaco è {prossimo['nome']} alle {orario}, tra {tempo}{note_str}")

        return ActionResponse(Action.RESPONSE,
            "Nessun farmaco programmato",
            "Non ci sono farmaci programmati")

    if action == "add":
        if not nome_farmaco:
            return ActionResponse(Action.RESPONSE,
                "Quale farmaco devo aggiungere?",
                "Dimmi il nome del farmaco da aggiungere")

        orari_list = parse_orari(orari) if orari else ["08:00"]

        # Controlla se esiste già
        for f in farmaci:
            if f["nome"].lower() == nome_farmaco.lower():
                f["orari"] = orari_list
                if note:
                    f["note"] = note
                save_farmaci(data)

                orari_str = ", ".join(orari_list)
                return ActionResponse(Action.RESPONSE,
                    f"Aggiornato {nome_farmaco}: {orari_str}",
                    f"Ho aggiornato {nome_farmaco} con gli orari {orari_str}")

        # Aggiungi nuovo
        nuovo = {
            "nome": nome_farmaco,
            "orari": orari_list,
            "note": note or "",
            "creato": datetime.now().isoformat()
        }
        farmaci.append(nuovo)
        data["farmaci"] = farmaci
        save_farmaci(data)

        orari_str = ", ".join(orari_list)
        note_str = f" Nota: {note}." if note else ""

        return ActionResponse(Action.RESPONSE,
            f"Aggiunto {nome_farmaco} alle {orari_str}.{note_str}",
            f"Ho aggiunto {nome_farmaco} alle {orari_str}.{note_str}")

    if action == "remove":
        if not nome_farmaco:
            return ActionResponse(Action.RESPONSE,
                "Quale farmaco devo rimuovere?",
                "Dimmi quale farmaco vuoi rimuovere")

        found = False
        farmaci_new = []
        for f in farmaci:
            if nome_farmaco.lower() in f["nome"].lower():
                found = True
            else:
                farmaci_new.append(f)

        if found:
            data["farmaci"] = farmaci_new
            save_farmaci(data)
            return ActionResponse(Action.RESPONSE,
                f"Rimosso {nome_farmaco}",
                f"Ho rimosso {nome_farmaco} dalla lista")
        else:
            return ActionResponse(Action.RESPONSE,
                f"Non trovo {nome_farmaco}",
                f"Non ho trovato {nome_farmaco} nella lista")

    return ActionResponse(Action.RESPONSE,
        "Cosa vuoi fare con i farmaci?",
        "Posso aggiungere, rimuovere o elencare i tuoi farmaci")
