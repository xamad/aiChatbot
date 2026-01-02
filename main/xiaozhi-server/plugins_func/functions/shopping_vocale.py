"""
Shopping Vocale - Lista della spesa intelligente con condivisione
Aggiungi, rimuovi, leggi la lista. Condividi via link web.
"""

import os
import json
import re
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# File per la lista della spesa
SHOPPING_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "shopping_list.json")

# Categorie automatiche per organizzare la spesa
CATEGORIE_PRODOTTI = {
    "frutta_verdura": ["mele", "banane", "arance", "limoni", "pomodori", "insalata", "zucchine",
                       "carote", "patate", "cipolle", "aglio", "peperoni", "melanzane", "frutta", "verdura"],
    "latticini": ["latte", "yogurt", "formaggio", "mozzarella", "burro", "panna", "ricotta",
                  "parmigiano", "grana", "uova"],
    "carne_pesce": ["pollo", "manzo", "maiale", "vitello", "salsicce", "prosciutto", "salame",
                    "tonno", "salmone", "pesce", "carne", "bresaola", "speck"],
    "pane_pasta": ["pane", "pasta", "riso", "farina", "grissini", "crackers", "cereali",
                   "biscotti", "fette biscottate", "pizza"],
    "bevande": ["acqua", "vino", "birra", "succo", "coca cola", "aranciata", "caffè", "tè"],
    "pulizia": ["detersivo", "sapone", "shampoo", "carta igienica", "scottex", "spugne",
                "candeggina", "ammorbidente"],
    "altro": []
}


def load_shopping_list() -> dict:
    """Carica la lista della spesa"""
    default = {"items": [], "last_updated": None, "completed": []}
    try:
        if os.path.exists(SHOPPING_FILE):
            with open(SHOPPING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento lista: {e}")
    return default


def save_shopping_list(data: dict):
    """Salva la lista della spesa"""
    try:
        os.makedirs(os.path.dirname(SHOPPING_FILE), exist_ok=True)
        data["last_updated"] = datetime.now().isoformat()
        with open(SHOPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio lista: {e}")


def get_categoria(item: str) -> str:
    """Determina la categoria di un prodotto"""
    item_lower = item.lower()
    for cat, prodotti in CATEGORIE_PRODOTTI.items():
        for prod in prodotti:
            if prod in item_lower or item_lower in prod:
                return cat
    return "altro"


def format_lista(items: list) -> str:
    """Formatta la lista per categoria"""
    if not items:
        return "La lista della spesa è vuota!"

    # Raggruppa per categoria
    by_cat = {}
    for item in items:
        cat = get_categoria(item)
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(item)

    # Nomi categorie friendly
    cat_names = {
        "frutta_verdura": "🥬 Frutta e Verdura",
        "latticini": "🥛 Latticini",
        "carne_pesce": "🥩 Carne e Pesce",
        "pane_pasta": "🍞 Pane e Pasta",
        "bevande": "🍷 Bevande",
        "pulizia": "🧹 Pulizia Casa",
        "altro": "📦 Altro"
    }

    result = "📝 LISTA DELLA SPESA\n\n"
    for cat, cat_items in by_cat.items():
        result += f"{cat_names.get(cat, cat)}:\n"
        for item in cat_items:
            result += f"  • {item}\n"
        result += "\n"

    result += f"Totale: {len(items)} prodotti"
    return result


SHOPPING_VOCALE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "shopping_vocale",
        "description": (
            "购物清单 / Lista della spesa vocale. Aggiungi, rimuovi, leggi la lista della spesa. "
            "Use when: 'aggiungi alla spesa', 'lista della spesa', 'cosa devo comprare', "
            "'metti in lista', 'togli dalla spesa', 'ho comprato', 'svuota la spesa', "
            "'leggi la spesa', 'cosa manca', 'devo comprare'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "azione": {
                    "type": "string",
                    "description": "Azione: aggiungi, rimuovi, leggi, svuota, comprato"
                },
                "prodotto": {
                    "type": "string",
                    "description": "Nome del prodotto da aggiungere/rimuovere"
                }
            },
            "required": []
        }
    }
}


@register_function('shopping_vocale', SHOPPING_VOCALE_FUNCTION_DESC, ToolType.WAIT)
def shopping_vocale(conn, azione: str = None, prodotto: str = None):
    """Gestisce la lista della spesa"""

    data = load_shopping_list()
    items = data.get("items", [])

    # Determina azione dal contesto
    if not azione:
        if prodotto:
            azione = "aggiungi"
        else:
            azione = "leggi"

    azione_lower = azione.lower() if azione else ""

    # === AGGIUNGI ===
    if any(x in azione_lower for x in ['aggiungi', 'metti', 'inserisci', 'add']):
        if not prodotto:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Cosa devo aggiungere alla lista?",
                response="Cosa vuoi aggiungere alla lista della spesa?"
            )

        # Pulisci prodotto
        prodotto = prodotto.strip().lower()

        # Gestisci quantità (es: "3 mele", "un litro di latte")
        # Per ora aggiungiamo così com'è

        if prodotto in items:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"'{prodotto}' è già nella lista!",
                response=f"{prodotto} è già nella lista della spesa!"
            )

        items.append(prodotto)
        data["items"] = items
        save_shopping_list(data)

        logger.bind(tag=TAG).info(f"Aggiunto alla spesa: {prodotto}")

        return ActionResponse(
            action=Action.RESPONSE,
            result=f"✅ Aggiunto: {prodotto}\n\nTotale: {len(items)} prodotti",
            response=f"Ok! Ho aggiunto {prodotto} alla lista. Ora hai {len(items)} prodotti da comprare."
        )

    # === RIMUOVI ===
    if any(x in azione_lower for x in ['rimuovi', 'togli', 'elimina', 'cancella', 'comprato', 'preso']):
        if not prodotto:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Cosa devo rimuovere dalla lista?",
                response="Cosa hai comprato o vuoi rimuovere dalla lista?"
            )

        prodotto_lower = prodotto.strip().lower()

        # Cerca match parziale
        removed = None
        for item in items:
            if prodotto_lower in item.lower() or item.lower() in prodotto_lower:
                removed = item
                items.remove(item)
                break

        if removed:
            data["items"] = items
            data.setdefault("completed", []).append({"item": removed, "date": datetime.now().isoformat()})
            save_shopping_list(data)

            return ActionResponse(
                action=Action.RESPONSE,
                result=f"✅ Rimosso: {removed}\n\nRimangono: {len(items)} prodotti",
                response=f"Perfetto! Ho tolto {removed} dalla lista. Ti rimangono {len(items)} cose da comprare."
            )
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"'{prodotto}' non trovato nella lista",
                response=f"Non ho trovato {prodotto} nella lista della spesa."
            )

    # === SVUOTA ===
    if any(x in azione_lower for x in ['svuota', 'pulisci', 'reset', 'cancella tutto']):
        old_count = len(items)
        data["items"] = []
        data["completed"] = data.get("completed", []) + [{"item": i, "date": datetime.now().isoformat()} for i in items]
        save_shopping_list(data)

        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🗑️ Lista svuotata! ({old_count} prodotti rimossi)",
            response=f"Ho svuotato la lista della spesa. Avevi {old_count} prodotti."
        )

    # === LEGGI (default) ===
    if not items:
        return ActionResponse(
            action=Action.RESPONSE,
            result="📝 La lista della spesa è vuota!",
            response="La lista della spesa è vuota! Dimmi cosa aggiungere."
        )

    formatted = format_lista(items)

    # Versione parlata più breve
    if len(items) <= 5:
        spoken = "Nella lista della spesa hai: " + ", ".join(items)
    else:
        spoken = f"Hai {len(items)} prodotti nella lista: " + ", ".join(items[:5]) + f" e altri {len(items)-5}."

    return ActionResponse(
        action=Action.RESPONSE,
        result=formatted,
        response=spoken
    )
