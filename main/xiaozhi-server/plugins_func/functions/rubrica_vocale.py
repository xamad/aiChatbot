"""
Rubrica Vocale Plugin - Gestione contatti vocale
Salva, cerca e legge numeri di telefono
"""

import json
import os
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

RUBRICA_FILE = "/tmp/xiaozhi_rubrica.json"

def load_rubrica() -> dict:
    try:
        if os.path.exists(RUBRICA_FILE):
            with open(RUBRICA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"contatti": []}

def save_rubrica(data: dict):
    try:
        with open(RUBRICA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio rubrica: {e}")

RUBRICA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "rubrica_vocale",
        "description": (
            "Gestisce rubrica telefonica vocale. Usa quando l'utente dice: "
            "'salva numero di mamma', 'qual è il numero di...', 'aggiungi contatto', "
            "'rubrica', 'cerca numero', 'elimina contatto'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: add (aggiungi), find (cerca), list (elenca), remove (rimuovi)",
                    "enum": ["add", "find", "list", "remove"]
                },
                "nome": {
                    "type": "string",
                    "description": "Nome del contatto"
                },
                "numero": {
                    "type": "string",
                    "description": "Numero di telefono"
                }
            },
            "required": ["action"],
        },
    },
}

def normalizza_numero(numero: str) -> str:
    """Pulisce e normalizza numero telefono"""
    # Rimuovi tutto tranne numeri e +
    clean = ""
    for c in numero:
        if c.isdigit() or c == "+":
            clean += c
    return clean

def leggi_numero(numero: str) -> str:
    """Converte numero in formato leggibile"""
    # Leggi cifra per cifra con pause
    result = ""
    for c in numero:
        if c == "+":
            result += "più "
        else:
            result += c + ". "
    return result.strip()

def cerca_contatto(contatti: list, query: str) -> list:
    """Cerca contatti per nome"""
    query = query.lower().strip()
    risultati = []

    for c in contatti:
        nome = c.get("nome", "").lower()
        if query in nome or nome in query:
            risultati.append(c)

    return risultati

@register_function("rubrica_vocale", RUBRICA_FUNCTION_DESC, ToolType.WAIT)
def rubrica_vocale(conn, action: str = "list", nome: str = None, numero: str = None):
    logger.bind(tag=TAG).info(f"Rubrica: action={action}, nome={nome}, numero={numero}")

    data = load_rubrica()
    contatti = data.get("contatti", [])

    if action == "list":
        if not contatti:
            return ActionResponse(Action.RESPONSE,
                "La rubrica è vuota",
                "Non hai ancora salvato nessun contatto. Vuoi aggiungerne uno?")

        result = "📱 I tuoi contatti:\n\n"
        spoken = "I tuoi contatti sono: "

        for c in contatti:
            result += f"• {c['nome']}: {c['numero']}\n"
            spoken += f"{c['nome']}, "

        spoken = spoken.rstrip(", ") + ". Quale numero ti serve?"

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "find":
        if not nome:
            return ActionResponse(Action.RESPONSE,
                "Chi stai cercando?",
                "Dimmi il nome del contatto che cerchi")

        risultati = cerca_contatto(contatti, nome)

        if not risultati:
            return ActionResponse(Action.RESPONSE,
                f"Non trovo '{nome}' in rubrica",
                f"Non ho trovato {nome} nella rubrica. Vuoi aggiungerlo?")

        if len(risultati) == 1:
            c = risultati[0]
            num_letto = leggi_numero(c["numero"])
            return ActionResponse(Action.RESPONSE,
                f"📞 {c['nome']}: {c['numero']}",
                f"Il numero di {c['nome']} è: {num_letto}")

        result = f"Ho trovato {len(risultati)} contatti:\n\n"
        spoken = f"Ho trovato {len(risultati)} contatti: "

        for c in risultati:
            result += f"• {c['nome']}: {c['numero']}\n"
            spoken += f"{c['nome']}, {leggi_numero(c['numero'])}. "

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "add":
        if not nome:
            return ActionResponse(Action.RESPONSE,
                "Che nome vuoi salvare?",
                "Dimmi il nome del contatto da salvare")

        if not numero:
            return ActionResponse(Action.RESPONSE,
                f"Qual è il numero di {nome}?",
                f"Qual è il numero di telefono di {nome}?")

        numero = normalizza_numero(numero)

        if len(numero) < 6:
            return ActionResponse(Action.RESPONSE,
                "Numero troppo corto. Ripeti il numero.",
                "Il numero sembra troppo corto. Puoi ripeterlo?")

        # Controlla se esiste già
        for c in contatti:
            if c["nome"].lower() == nome.lower():
                c["numero"] = numero
                save_rubrica(data)
                num_letto = leggi_numero(numero)
                return ActionResponse(Action.RESPONSE,
                    f"Aggiornato {nome}: {numero}",
                    f"Ho aggiornato il numero di {nome} con {num_letto}")

        # Nuovo contatto
        contatti.append({
            "nome": nome,
            "numero": numero
        })
        data["contatti"] = contatti
        save_rubrica(data)

        num_letto = leggi_numero(numero)
        return ActionResponse(Action.RESPONSE,
            f"Salvato {nome}: {numero}",
            f"Ho salvato {nome} con il numero {num_letto}")

    if action == "remove":
        if not nome:
            return ActionResponse(Action.RESPONSE,
                "Chi vuoi eliminare?",
                "Dimmi il nome del contatto da eliminare")

        risultati = cerca_contatto(contatti, nome)

        if not risultati:
            return ActionResponse(Action.RESPONSE,
                f"Non trovo '{nome}' in rubrica",
                f"Non ho trovato {nome} nella rubrica")

        # Rimuovi il primo match
        contatto_rimosso = risultati[0]
        data["contatti"] = [c for c in contatti if c["nome"].lower() != contatto_rimosso["nome"].lower()]
        save_rubrica(data)

        return ActionResponse(Action.RESPONSE,
            f"Eliminato {contatto_rimosso['nome']}",
            f"Ho eliminato {contatto_rimosso['nome']} dalla rubrica")

    return ActionResponse(Action.RESPONSE,
        "Cosa vuoi fare con la rubrica?",
        "Posso aggiungere, cercare o elencare i tuoi contatti")
