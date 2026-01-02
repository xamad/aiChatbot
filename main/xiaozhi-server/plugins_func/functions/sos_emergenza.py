"""
SOS Emergenza Plugin - Sistema di notifica per anziani
Registra richieste di aiuto e notifica familiari (simulato)
NON effettua chiamate telefoniche reali
"""

import json
import os
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

SOS_FILE = "/tmp/xiaozhi_sos_config.json"
SOS_LOG_FILE = "/tmp/xiaozhi_sos_log.json"

def load_sos_config() -> dict:
    try:
        if os.path.exists(SOS_FILE):
            with open(SOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {"contatti_emergenza": [], "messaggio_default": "Ho bisogno di assistenza"}

def save_sos_config(data: dict):
    try:
        with open(SOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio SOS config: {e}")

def log_sos_event(evento: str):
    """Logga evento SOS"""
    try:
        log = []
        if os.path.exists(SOS_LOG_FILE):
            with open(SOS_LOG_FILE, 'r', encoding='utf-8') as f:
                log = json.load(f)

        log.append({
            "timestamp": datetime.now().isoformat(),
            "evento": evento
        })

        log = log[-100:]

        with open(SOS_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore log SOS: {e}")

SOS_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "sos_emergenza",
        "description": (
            "Sistema di notifica emergenza per anziani."
            "Usare quando: sto male, aiuto, emergenza, ho bisogno di assistenza, "
            "chiama mio figlio, avvisa la famiglia, SOS"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: alert (registra), config (configura), test (prova), status",
                    "enum": ["alert", "config", "test", "status", "add_contact", "remove_contact"]
                },
                "nome": {
                    "type": "string",
                    "description": "Nome contatto"
                },
                "numero": {
                    "type": "string",
                    "description": "Numero telefono contatto (per riferimento)"
                },
                "messaggio": {
                    "type": "string",
                    "description": "Messaggio personalizzato"
                }
            },
            "required": ["action"],
        },
    },
}

@register_function("sos_emergenza", SOS_FUNCTION_DESC, ToolType.WAIT)
def sos_emergenza(conn, action: str = "alert", nome: str = None, numero: str = None, messaggio: str = None):
    logger.bind(tag=TAG).info(f"SOS: action={action}, nome={nome}")

    config = load_sos_config()
    contatti = config.get("contatti_emergenza", [])

    if action == "alert":
        log_sos_event("RICHIESTA ASSISTENZA REGISTRATA")

        if not contatti:
            result = "📋 **RICHIESTA REGISTRATA**\n\n"
            result += "⚠️ Non hai configurato contatti di riferimento.\n\n"
            result += "Posso memorizzare i numeri dei tuoi familiari per riferimento.\n"
            result += "Di' 'aggiungi contatto' seguito dal nome."

            spoken = "Ho registrato la tua richiesta. "
            spoken += "Non hai contatti configurati. Vuoi aggiungere un familiare?"

            return ActionResponse(Action.RESPONSE, result, spoken)

        # Registra la richiesta
        msg = messaggio or config.get('messaggio_default', 'Ho bisogno di assistenza')
        log_sos_event(f"Messaggio: {msg} - Contatti: {', '.join([c['nome'] for c in contatti])}")

        result = "📋 **RICHIESTA REGISTRATA**\n\n"
        result += f"Messaggio: {msg}\n\n"
        result += "Contatti di riferimento:\n"

        for c in contatti:
            result += f"• {c['nome']}: {c['numero']}\n"

        result += f"\n⏰ {datetime.now().strftime('%H:%M:%S')}"
        result += "\n\n_Nota: questo sistema registra le richieste ma non effettua chiamate automatiche._"

        nomi = ", ".join([c["nome"] for c in contatti])
        spoken = f"Ho registrato la tua richiesta di assistenza. "
        spoken += f"I tuoi contatti di riferimento sono: {nomi}. "
        spoken += "Stai tranquillo, sono qui con te."

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "test":
        log_sos_event("TEST SISTEMA")

        if not contatti:
            return ActionResponse(Action.RESPONSE,
                "⚠️ Nessun contatto configurato per il test",
                "Non hai contatti di riferimento. Vuoi aggiungerne uno?")

        result = "✅ **TEST SISTEMA**\n\n"
        result += "Sistema funzionante!\n"
        result += f"Contatti registrati: {len(contatti)}\n\n"
        for c in contatti:
            result += f"• {c['nome']}: {c['numero']}\n"

        spoken = f"Test completato. Hai {len(contatti)} contatti registrati."

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "status":
        if not contatti:
            return ActionResponse(Action.RESPONSE,
                "⚠️ Nessun contatto configurato",
                "Non hai contatti di riferimento. Vuoi configurarli?")

        result = "📋 **Stato Sistema**\n\n"
        result += f"Contatti registrati: {len(contatti)}\n\n"

        for c in contatti:
            result += f"• {c['nome']}: {c['numero']}\n"

        spoken = f"Hai {len(contatti)} contatti: " + ", ".join([c["nome"] for c in contatti])

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "add_contact":
        if not nome:
            return ActionResponse(Action.RESPONSE,
                "Chi vuoi aggiungere come contatto?",
                "Dimmi il nome del contatto da aggiungere")

        if not numero:
            return ActionResponse(Action.RESPONSE,
                f"Qual è il numero di {nome}?",
                f"Qual è il numero di telefono di {nome}?")

        contatti = [c for c in contatti if c["nome"].lower() != nome.lower()]
        contatti.append({"nome": nome, "numero": numero})
        config["contatti_emergenza"] = contatti
        save_sos_config(config)

        log_sos_event(f"Aggiunto contatto: {nome}")

        return ActionResponse(Action.RESPONSE,
            f"✅ Aggiunto {nome} ai contatti",
            f"Ho aggiunto {nome} come contatto di riferimento.")

    if action == "remove_contact":
        if not nome:
            return ActionResponse(Action.RESPONSE,
                "Chi vuoi rimuovere?",
                "Dimmi il nome del contatto da rimuovere")

        found = False
        for c in contatti:
            if nome.lower() in c["nome"].lower():
                found = True
                contatti = [x for x in contatti if x != c]
                break

        if found:
            config["contatti_emergenza"] = contatti
            save_sos_config(config)
            log_sos_event(f"Rimosso contatto: {nome}")

            return ActionResponse(Action.RESPONSE,
                f"Rimosso {nome}",
                f"Ho rimosso {nome} dai contatti")
        else:
            return ActionResponse(Action.RESPONSE,
                f"Non trovo {nome}",
                f"Non ho trovato {nome} nei contatti")

    if action == "config":
        if messaggio:
            config["messaggio_default"] = messaggio
            save_sos_config(config)
            return ActionResponse(Action.RESPONSE,
                f"Messaggio aggiornato",
                f"Ho aggiornato il messaggio predefinito")

        return ActionResponse(Action.RESPONSE,
            "Cosa vuoi configurare?",
            "Posso aggiungere contatti o cambiare il messaggio predefinito")

    return ActionResponse(Action.RESPONSE,
        "Sistema pronto. Posso registrare richieste di assistenza.",
        "Sono qui per aiutarti. Dimmi se hai bisogno di qualcosa.")
