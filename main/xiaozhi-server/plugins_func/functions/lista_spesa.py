"""
Lista Spesa Plugin - Gestisce lista della spesa vocale
Persistente su file JSON
"""

import json
import os
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# File per salvare la lista
LISTA_FILE = "/tmp/xiaozhi_lista_spesa.json"


def load_lista() -> dict:
    """Carica lista da file"""
    try:
        if os.path.exists(LISTA_FILE):
            with open(LISTA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento lista: {e}")
    return {"items": [], "last_updated": None}


def save_lista(lista: dict):
    """Salva lista su file"""
    try:
        lista["last_updated"] = datetime.now().isoformat()
        with open(LISTA_FILE, 'w', encoding='utf-8') as f:
            json.dump(lista, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio lista: {e}")


LISTA_SPESA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "lista_spesa",
        "description": (
            "Gestisce la lista della spesa."
            "Usare quando: aggiungi alla lista, cosa c'è nella lista, "
            "togli dalla lista, svuota lista, leggi la lista, lista spesa"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: add (aggiungi), remove (rimuovi), list (elenca), clear (svuota)",
                    "enum": ["add", "remove", "list", "clear"]
                },
                "item": {
                    "type": "string",
                    "description": "Articolo da aggiungere/rimuovere (es: 'latte', 'pane', '2 kg di mele')"
                },
                "quantity": {
                    "type": "string",
                    "description": "Quantità opzionale (es: '2', '1 kg', '500g')"
                }
            },
            "required": ["action"],
        },
    },
}


@register_function("lista_spesa", LISTA_SPESA_FUNCTION_DESC, ToolType.WAIT)
def lista_spesa(conn, action: str = "list", item: str = None, quantity: str = None):
    logger.bind(tag=TAG).info(f"Lista spesa: action={action}, item={item}, quantity={quantity}")

    lista = load_lista()

    if action == "list":
        items = lista.get("items", [])

        if not items:
            return ActionResponse(Action.RESPONSE,
                "La lista della spesa è vuota",
                "La tua lista della spesa è vuota. Vuoi aggiungere qualcosa?")

        # Formatta lista
        result = f"Lista della spesa ({len(items)} articoli):\n"
        spoken_items = []

        for i, item_data in enumerate(items, 1):
            if isinstance(item_data, dict):
                name = item_data.get("name", "")
                qty = item_data.get("quantity", "")
                display = f"{qty} {name}".strip() if qty else name
            else:
                display = str(item_data)

            result += f"{i}. {display}\n"
            spoken_items.append(display)

        spoken = "Nella lista hai: " + ", ".join(spoken_items)
        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "add":
        if not item:
            return ActionResponse(Action.RESPONSE,
                "Cosa vuoi aggiungere?",
                "Cosa devo aggiungere alla lista?")

        # Crea oggetto item
        item_data = {
            "name": item,
            "quantity": quantity or "",
            "added": datetime.now().isoformat()
        }

        # Controlla se esiste già
        existing = None
        for i, existing_item in enumerate(lista["items"]):
            existing_name = existing_item.get("name", "") if isinstance(existing_item, dict) else existing_item
            if existing_name.lower() == item.lower():
                existing = i
                break

        if existing is not None:
            # Aggiorna quantità
            if quantity:
                lista["items"][existing]["quantity"] = quantity
                save_lista(lista)
                return ActionResponse(Action.RESPONSE,
                    f"Aggiornato: {quantity} {item}",
                    f"Ho aggiornato {item} a {quantity}")
            else:
                return ActionResponse(Action.RESPONSE,
                    f"{item} è già nella lista",
                    f"{item} è già nella lista della spesa")
        else:
            lista["items"].append(item_data)
            save_lista(lista)

            display = f"{quantity} {item}".strip() if quantity else item
            return ActionResponse(Action.RESPONSE,
                f"Aggiunto: {display}",
                f"Ho aggiunto {display} alla lista. Ora hai {len(lista['items'])} articoli.")

    if action == "remove":
        if not item:
            return ActionResponse(Action.RESPONSE,
                "Cosa vuoi rimuovere?",
                "Cosa devo togliere dalla lista?")

        # Cerca item
        found_idx = None
        found_name = None

        for i, existing_item in enumerate(lista["items"]):
            existing_name = existing_item.get("name", "") if isinstance(existing_item, dict) else str(existing_item)
            if item.lower() in existing_name.lower():
                found_idx = i
                found_name = existing_name
                break

        if found_idx is not None:
            lista["items"].pop(found_idx)
            save_lista(lista)
            return ActionResponse(Action.RESPONSE,
                f"Rimosso: {found_name}",
                f"Ho tolto {found_name} dalla lista. Rimangono {len(lista['items'])} articoli.")
        else:
            return ActionResponse(Action.RESPONSE,
                f"'{item}' non trovato nella lista",
                f"Non trovo {item} nella lista della spesa")

    if action == "clear":
        count = len(lista.get("items", []))
        lista["items"] = []
        save_lista(lista)

        return ActionResponse(Action.RESPONSE,
            f"Lista svuotata ({count} articoli rimossi)",
            "Ho svuotato la lista della spesa")

    return ActionResponse(Action.RESPONSE, "Azione non riconosciuta", "Non ho capito cosa fare")
