"""
Note Vocali Plugin - Salva e recupera note/appunti vocali
"""

import json
import os
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# File per salvare le note
NOTE_FILE = "/tmp/xiaozhi_note.json"


def load_notes() -> dict:
    """Carica note da file"""
    try:
        if os.path.exists(NOTE_FILE):
            with open(NOTE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento note: {e}")
    return {"notes": []}


def save_notes(notes: dict):
    """Salva note su file"""
    try:
        with open(NOTE_FILE, 'w', encoding='utf-8') as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio note: {e}")


NOTE_VOCALI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "note_vocali",
        "description": (
            "appunti vocali."
            "Usare quando: salva nota, appunto, ricorda che, "
            "quali note ho, leggi le mie note, cancella nota"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: save (salva), list (elenca), search (cerca), delete (cancella)",
                    "enum": ["save", "list", "search", "delete", "clear"]
                },
                "content": {
                    "type": "string",
                    "description": "Contenuto della nota o termine di ricerca"
                },
                "title": {
                    "type": "string",
                    "description": "Titolo/etichetta opzionale per la nota"
                }
            },
            "required": ["action"],
        },
    },
}


@register_function("note_vocali", NOTE_VOCALI_FUNCTION_DESC, ToolType.WAIT)
def note_vocali(conn, action: str = "list", content: str = None, title: str = None):
    logger.bind(tag=TAG).info(f"Note vocali: action={action}, content={content[:50] if content else None}...")

    data = load_notes()
    notes = data.get("notes", [])

    if action == "save":
        if not content:
            return ActionResponse(Action.RESPONSE,
                "Cosa vuoi annotare?",
                "Dimmi cosa vuoi salvare come nota")

        note = {
            "id": len(notes) + 1,
            "content": content,
            "title": title or f"Nota {len(notes) + 1}",
            "created": datetime.now().isoformat(),
            "date_display": datetime.now().strftime("%d/%m/%Y %H:%M")
        }

        notes.append(note)
        data["notes"] = notes
        save_notes(data)

        return ActionResponse(Action.RESPONSE,
            f"Nota salvata: {content[:50]}...",
            f"Ho salvato la nota. Ora hai {len(notes)} note.")

    if action == "list":
        if not notes:
            return ActionResponse(Action.RESPONSE,
                "Non hai note salvate",
                "Non hai ancora salvato nessuna nota")

        # Mostra ultime 5 note
        recent = notes[-5:]
        result = f"Le tue note ({len(notes)} totali):\n"
        spoken_parts = []

        for note in reversed(recent):
            title = note.get("title", "Nota")
            preview = note.get("content", "")[:40]
            date = note.get("date_display", "")
            result += f"- {title}: {preview}... ({date})\n"
            spoken_parts.append(f"{title}: {preview}")

        spoken = "Le tue ultime note: " + ". ".join(spoken_parts)
        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "search":
        if not content:
            return ActionResponse(Action.RESPONSE,
                "Cosa cerchi nelle note?",
                "Dimmi cosa cercare")

        # Cerca nelle note
        found = []
        search_term = content.lower()

        for note in notes:
            note_content = note.get("content", "").lower()
            note_title = note.get("title", "").lower()

            if search_term in note_content or search_term in note_title:
                found.append(note)

        if not found:
            return ActionResponse(Action.RESPONSE,
                f"Nessuna nota trovata per '{content}'",
                f"Non ho trovato note su {content}")

        result = f"Trovate {len(found)} note:\n"
        spoken_parts = []

        for note in found[:3]:
            title = note.get("title", "Nota")
            note_content = note.get("content", "")
            result += f"- {title}: {note_content}\n"
            spoken_parts.append(note_content)

        spoken = "Ho trovato: " + ". ".join(spoken_parts)
        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "delete":
        if not notes:
            return ActionResponse(Action.RESPONSE,
                "Non hai note da cancellare",
                "Non ci sono note da eliminare")

        if content:
            # Cerca nota specifica
            found_idx = None
            for i, note in enumerate(notes):
                if content.lower() in note.get("content", "").lower() or \
                   content.lower() in note.get("title", "").lower():
                    found_idx = i
                    break

            if found_idx is not None:
                deleted = notes.pop(found_idx)
                data["notes"] = notes
                save_notes(data)
                return ActionResponse(Action.RESPONSE,
                    f"Nota cancellata: {deleted.get('title', 'Nota')}",
                    f"Ho cancellato la nota")
            else:
                return ActionResponse(Action.RESPONSE,
                    f"Nota '{content}' non trovata",
                    f"Non trovo una nota su {content}")
        else:
            # Cancella ultima nota
            deleted = notes.pop()
            data["notes"] = notes
            save_notes(data)
            return ActionResponse(Action.RESPONSE,
                f"Ultima nota cancellata",
                "Ho cancellato l'ultima nota")

    if action == "clear":
        count = len(notes)
        data["notes"] = []
        save_notes(data)
        return ActionResponse(Action.RESPONSE,
            f"Tutte le note cancellate ({count})",
            f"Ho cancellato tutte le {count} note")

    return ActionResponse(Action.RESPONSE, "Azione non riconosciuta", "Non ho capito")
