"""
Memoria Personale - Ricordami che... / Dove ho messo...
Sistema di memoria persistente per informazioni personali
"""

import os
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# File memoria
MEMORIA_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "memoria_personale.json")


def load_memoria() -> dict:
    """Carica la memoria"""
    default = {
        "ricordi": [],           # Lista di {categoria, chiave, valore, data, contesto}
        "persone": {},           # Info su persone {nome: {info1: val, info2: val}}
        "luoghi": {},            # Dove sono le cose {cosa: dove}
        "date_importanti": {},   # Date da ricordare
        "preferenze": {},        # Preferenze utente
        "stats": {"ricordi_totali": 0, "ricerche": 0}
    }
    try:
        if os.path.exists(MEMORIA_FILE):
            with open(MEMORIA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Merge con default per campi mancanti
                for key in default:
                    if key not in data:
                        data[key] = default[key]
                return data
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento memoria: {e}")
    return default


def save_memoria(data: dict):
    """Salva la memoria"""
    try:
        os.makedirs(os.path.dirname(MEMORIA_FILE), exist_ok=True)
        with open(MEMORIA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio memoria: {e}")


def similarity(a: str, b: str) -> float:
    """Calcola similarità tra due stringhe"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def cerca_in_memoria(query: str, memoria: dict) -> list:
    """Cerca informazioni rilevanti nella memoria"""
    risultati = []
    query_lower = query.lower()

    # Cerca nei ricordi generici
    for ricordo in memoria.get("ricordi", []):
        chiave = ricordo.get("chiave", "").lower()
        valore = ricordo.get("valore", "").lower()

        # Match esatto o parziale
        if query_lower in chiave or query_lower in valore:
            risultati.append({
                "tipo": "ricordo",
                "match": ricordo["chiave"],
                "valore": ricordo["valore"],
                "data": ricordo.get("data"),
                "score": 1.0 if query_lower in chiave else 0.8
            })
        elif similarity(query_lower, chiave) > 0.6:
            risultati.append({
                "tipo": "ricordo",
                "match": ricordo["chiave"],
                "valore": ricordo["valore"],
                "data": ricordo.get("data"),
                "score": similarity(query_lower, chiave)
            })

    # Cerca nei luoghi (dove ho messo...)
    for cosa, dove in memoria.get("luoghi", {}).items():
        if query_lower in cosa.lower() or similarity(query_lower, cosa.lower()) > 0.6:
            risultati.append({
                "tipo": "luogo",
                "match": cosa,
                "valore": dove,
                "score": 1.0 if query_lower in cosa.lower() else similarity(query_lower, cosa.lower())
            })

    # Cerca nelle persone
    for nome, info in memoria.get("persone", {}).items():
        if query_lower in nome.lower():
            risultati.append({
                "tipo": "persona",
                "match": nome,
                "valore": info,
                "score": 1.0
            })
        # Cerca anche nelle info della persona
        for chiave, valore in info.items():
            if query_lower in chiave.lower() or query_lower in str(valore).lower():
                risultati.append({
                    "tipo": "persona_info",
                    "match": f"{nome} - {chiave}",
                    "valore": valore,
                    "score": 0.9
                })

    # Cerca nelle date
    for evento, data in memoria.get("date_importanti", {}).items():
        if query_lower in evento.lower():
            risultati.append({
                "tipo": "data",
                "match": evento,
                "valore": data,
                "score": 1.0
            })

    # Ordina per score
    risultati.sort(key=lambda x: x["score"], reverse=True)

    return risultati[:5]  # Top 5 risultati


def parse_ricordami(testo: str) -> tuple:
    """Estrae cosa ricordare dal testo"""
    testo_lower = testo.lower()

    # Pattern: "ricordami che [info]"
    match = re.search(r"ricordami\s+che\s+(.+)", testo_lower)
    if match:
        return "ricordo", match.group(1).strip(), None

    # Pattern: "ricorda che [info]"
    match = re.search(r"ricorda\s+che\s+(.+)", testo_lower)
    if match:
        return "ricordo", match.group(1).strip(), None

    # Pattern: "[cosa] è/sta/sono in/nel/nella [dove]"
    match = re.search(r"(.+?)\s+(?:è|sta|sono|stanno)\s+(?:in|nel|nella|nello|nell'|sul|sulla|dentro|sopra|sotto)\s+(.+)", testo_lower)
    if match:
        return "luogo", match.group(1).strip(), match.group(2).strip()

    # Pattern: "ho messo [cosa] in/nel [dove]"
    match = re.search(r"ho\s+messo\s+(.+?)\s+(?:in|nel|nella|nello|nell'|sul|sulla|dentro|sopra|sotto)\s+(.+)", testo_lower)
    if match:
        return "luogo", match.group(1).strip(), match.group(2).strip()

    # Pattern: "[persona] è allergico/allergica a [cosa]"
    match = re.search(r"(\w+)\s+è\s+allergic[oa]\s+(?:a|al|alla|alle|agli)\s+(.+)", testo_lower)
    if match:
        return "persona_info", match.group(1).strip(), f"allergico a {match.group(2).strip()}"

    # Pattern: "il compleanno di [persona] è il [data]"
    match = re.search(r"il\s+compleanno\s+di\s+(\w+)\s+è\s+(?:il\s+)?(.+)", testo_lower)
    if match:
        return "data", f"compleanno di {match.group(1).strip()}", match.group(2).strip()

    # Pattern: "[persona] + info generica
    match = re.search(r"(\w+)\s+(.+)", testo_lower)
    if match and len(match.group(1)) > 2:
        # Potrebbe essere una persona
        return "ricordo", testo, None

    return "ricordo", testo, None


def parse_domanda(testo: str) -> str:
    """Estrae cosa cercare dalla domanda"""
    testo_lower = testo.lower()

    # "dove ho messo [cosa]"
    match = re.search(r"dove\s+(?:ho\s+messo|sono|è|stanno)\s+(?:le\s+|il\s+|la\s+|i\s+|gli\s+|lo\s+)?(.+?)(?:\?|$)", testo_lower)
    if match:
        return match.group(1).strip()

    # "cosa mi hai detto di/su [argomento]"
    match = re.search(r"cosa\s+(?:mi\s+)?(?:hai\s+detto|sai)\s+(?:di|su|riguardo)\s+(.+?)(?:\?|$)", testo_lower)
    if match:
        return match.group(1).strip()

    # "chi è [nome]"
    match = re.search(r"chi\s+è\s+(.+?)(?:\?|$)", testo_lower)
    if match:
        return match.group(1).strip()

    # "[persona] è allergico a cosa"
    match = re.search(r"(\w+)\s+(?:è\s+)?allergic[oa]\s+a\s+cosa", testo_lower)
    if match:
        return match.group(1).strip()

    # Rimuovi parole comuni e restituisci
    for prefix in ["dimmi", "sai", "ricordi", "ti ricordi"]:
        if testo_lower.startswith(prefix):
            return testo_lower[len(prefix):].strip()

    return testo


MEMORIA_PERSONALE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "memoria_personale",
        "description": (
            "个人记忆 / Memoria personale persistente. Ricorda informazioni, oggetti, persone, date. "
            "Use when: 'ricordami che', 'ricorda che', 'dove ho messo', 'dove sono le chiavi', "
            "'cosa mi hai detto', 'ti avevo detto che', 'ho messo X in Y', "
            "'il compleanno di', 'X è allergico a', 'ricordi che', 'dimmi cosa sai di'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "azione": {
                    "type": "string",
                    "description": "Azione: ricorda, cerca, lista, dimentica"
                },
                "contenuto": {
                    "type": "string",
                    "description": "Cosa ricordare o cercare"
                }
            },
            "required": []
        }
    }
}


@register_function('memoria_personale', MEMORIA_PERSONALE_FUNCTION_DESC, ToolType.WAIT)
def memoria_personale(conn, azione: str = None, contenuto: str = None):
    """Gestisce la memoria personale"""

    memoria = load_memoria()
    azione_lower = (azione or "").lower()
    contenuto = contenuto or ""

    logger.bind(tag=TAG).info(f"Memoria: azione={azione}, contenuto={contenuto}")

    # === DIMENTICA ===
    if any(x in azione_lower for x in ["dimentica", "cancella", "elimina", "togli"]):
        if not contenuto:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Cosa devo dimenticare?",
                response="Cosa vuoi che dimentichi?"
            )

        # Cerca e rimuovi
        query = parse_domanda(contenuto)
        rimosso = False

        # Rimuovi da luoghi
        for cosa in list(memoria.get("luoghi", {}).keys()):
            if query.lower() in cosa.lower():
                del memoria["luoghi"][cosa]
                rimosso = True
                break

        # Rimuovi da ricordi
        for i, ricordo in enumerate(memoria.get("ricordi", [])):
            if query.lower() in ricordo.get("chiave", "").lower():
                memoria["ricordi"].pop(i)
                rimosso = True
                break

        if rimosso:
            save_memoria(memoria)
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🗑️ Dimenticato: {query}",
                response=f"Ok, ho dimenticato le informazioni su {query}."
            )
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Non ho trovato '{query}' nella memoria",
                response=f"Non avevo nulla su {query} nella mia memoria."
            )

    # === LISTA ===
    if any(x in azione_lower for x in ["lista", "tutto", "mostra", "elenca"]):
        result = "🧠 **LA MIA MEMORIA:**\n\n"

        if memoria.get("luoghi"):
            result += "📍 **Dove sono le cose:**\n"
            for cosa, dove in list(memoria["luoghi"].items())[:10]:
                result += f"• {cosa} → {dove}\n"
            result += "\n"

        if memoria.get("ricordi"):
            result += "💭 **Ricordi:**\n"
            for r in memoria["ricordi"][-10:]:
                result += f"• {r['chiave']}: {r['valore']}\n"
            result += "\n"

        if memoria.get("persone"):
            result += "👥 **Persone:**\n"
            for nome, info in list(memoria["persone"].items())[:5]:
                result += f"• {nome}: {info}\n"
            result += "\n"

        if memoria.get("date_importanti"):
            result += "📅 **Date importanti:**\n"
            for evento, data in memoria["date_importanti"].items():
                result += f"• {evento}: {data}\n"

        tot = len(memoria.get("ricordi", [])) + len(memoria.get("luoghi", {}))
        result += f"\n_Totale: {tot} informazioni memorizzate_"

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=f"Ho {tot} cose in memoria. Vuoi i dettagli?"
        )

    # === RICORDA (salva nuovo ricordo) ===
    if any(x in azione_lower for x in ["ricorda", "memorizza", "salva", "segna"]) or "ricordami" in contenuto.lower():
        if not contenuto:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Cosa devo ricordare?",
                response="Cosa vuoi che ricordi?"
            )

        tipo, chiave, valore = parse_ricordami(contenuto)

        if tipo == "luogo" and valore:
            memoria.setdefault("luoghi", {})[chiave] = valore
            save_memoria(memoria)

            return ActionResponse(
                action=Action.RESPONSE,
                result=f"📍 Memorizzato: {chiave} → {valore}",
                response=f"Ok! Mi ricorderò che {chiave} sta in {valore}."
            )

        elif tipo == "persona_info" and valore:
            # Estrai nome persona dalla chiave
            nome = chiave.split()[0] if chiave else "Qualcuno"
            memoria.setdefault("persone", {}).setdefault(nome, {})
            memoria["persone"][nome]["info"] = valore
            save_memoria(memoria)

            return ActionResponse(
                action=Action.RESPONSE,
                result=f"👤 Memorizzato su {nome}: {valore}",
                response=f"Ok! Mi ricorderò che {nome} {valore}."
            )

        elif tipo == "data" and valore:
            memoria.setdefault("date_importanti", {})[chiave] = valore
            save_memoria(memoria)

            return ActionResponse(
                action=Action.RESPONSE,
                result=f"📅 Memorizzato: {chiave} - {valore}",
                response=f"Ok! Mi ricorderò che {chiave} è il {valore}."
            )

        else:
            # Ricordo generico
            nuovo_ricordo = {
                "chiave": chiave,
                "valore": contenuto,
                "data": datetime.now().isoformat(),
                "categoria": "generale"
            }
            memoria.setdefault("ricordi", []).append(nuovo_ricordo)
            memoria["stats"]["ricordi_totali"] = memoria["stats"].get("ricordi_totali", 0) + 1
            save_memoria(memoria)

            return ActionResponse(
                action=Action.RESPONSE,
                result=f"💭 Memorizzato: {chiave}",
                response=f"Ok! Mi ricorderò che {chiave}."
            )

    # === CERCA (default) ===
    if not contenuto:
        tot = len(memoria.get("ricordi", [])) + len(memoria.get("luoghi", {}))
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🧠 Ho {tot} informazioni in memoria. Cosa vuoi sapere?",
            response=f"Ho {tot} cose in memoria. Dimmi cosa cerchi, oppure dimmi 'ricordami che' per aggiungere qualcosa."
        )

    # Cerca nella memoria
    query = parse_domanda(contenuto)
    risultati = cerca_in_memoria(query, memoria)

    memoria["stats"]["ricerche"] = memoria["stats"].get("ricerche", 0) + 1
    save_memoria(memoria)

    if risultati:
        # Miglior risultato
        best = risultati[0]

        if best["tipo"] == "luogo":
            result = f"📍 {best['match']} → **{best['valore']}**"
            spoken = f"{best['match']} si trova in {best['valore']}!"

        elif best["tipo"] == "persona":
            result = f"👤 **{best['match']}**:\n"
            if isinstance(best['valore'], dict):
                for k, v in best['valore'].items():
                    result += f"• {k}: {v}\n"
                spoken = f"Di {best['match']} so che: " + ", ".join([f"{k} è {v}" for k, v in best['valore'].items()])
            else:
                result += str(best['valore'])
                spoken = f"{best['match']}: {best['valore']}"

        elif best["tipo"] == "data":
            result = f"📅 {best['match']}: **{best['valore']}**"
            spoken = f"{best['match']} è il {best['valore']}!"

        else:
            result = f"💭 {best['match']}: **{best['valore']}**"
            spoken = f"Mi avevi detto che {best['valore']}."

        # Se ci sono altri risultati
        if len(risultati) > 1:
            result += "\n\n_Altre corrispondenze:_\n"
            for r in risultati[1:3]:
                result += f"• {r['match']}\n"

        return ActionResponse(
            action=Action.RESPONSE,
            result=result,
            response=spoken
        )
    else:
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"❓ Non ho informazioni su '{query}'",
            response=f"Non ho nulla in memoria su {query}. Vuoi che me lo ricordi?"
        )
