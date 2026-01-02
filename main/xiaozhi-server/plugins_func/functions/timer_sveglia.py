"""
Timer e Sveglia Plugin - Gestisce timer e sveglie vocali
Utile per cucina, promemoria brevi, ecc.
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType
from core.handle.sendAudioHandle import send_stt_message
from core.utils.dialogue import Message

TAG = __name__
logger = setup_logging()

# Timer attivi per sessione {session_id: [{"name": str, "end_time": datetime, "task": asyncio.Task}]}
ACTIVE_TIMERS = {}

TIMER_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "timer_sveglia",
        "description": (
            "Gestisce timer e sveglie."
            "Usare quando: timer 5 minuti, svegliami tra, metti un timer, "
            "quanto manca al timer, cancella timer, ferma sveglia"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: set (imposta), cancel (cancella), list (elenca), stop (ferma suono)",
                    "enum": ["set", "cancel", "list", "stop"]
                },
                "minutes": {
                    "type": "number",
                    "description": "Minuti per il timer (es: 5, 10, 30)"
                },
                "seconds": {
                    "type": "number",
                    "description": "Secondi aggiuntivi (es: 30 per 5 minuti e 30 secondi)"
                },
                "name": {
                    "type": "string",
                    "description": "Nome/etichetta del timer (es: 'pasta', 'uova', 'pausa')"
                }
            },
            "required": ["action"],
        },
    },
}


def get_session_id(conn) -> str:
    """Ottieni ID sessione dalla connessione"""
    try:
        return conn.session_id if hasattr(conn, 'session_id') else str(id(conn))
    except:
        return str(id(conn))


def format_duration(seconds: int) -> str:
    """Formatta durata in modo leggibile"""
    if seconds < 60:
        return f"{seconds} secondi"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        if secs > 0:
            return f"{mins} minuti e {secs} secondi"
        return f"{mins} minuti"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        if mins > 0:
            return f"{hours} ore e {mins} minuti"
        return f"{hours} ore"


async def timer_countdown(conn, timer_name: str, duration_seconds: int, session_id: str):
    """Esegue il countdown e notifica quando scade"""
    try:
        logger.bind(tag=TAG).info(f"Timer '{timer_name}' avviato: {duration_seconds}s")

        # Attendi la durata
        await asyncio.sleep(duration_seconds)

        # Verifica se il timer è ancora attivo (non cancellato)
        if session_id in ACTIVE_TIMERS:
            timers = ACTIVE_TIMERS[session_id]
            timer_exists = any(t["name"] == timer_name for t in timers)

            if timer_exists:
                # Timer scaduto - notifica
                logger.bind(tag=TAG).info(f"Timer '{timer_name}' scaduto!")

                # Rimuovi dalla lista
                ACTIVE_TIMERS[session_id] = [t for t in timers if t["name"] != timer_name]

                # Invia notifica vocale
                alert_text = f"Tempo scaduto! Il timer {timer_name} è terminato!"

                # Prova a inviare notifica
                try:
                    if conn.intent_type == "intent_llm":
                        conn.tts.tts_text_queue.put(
                            TTSMessageDTO(
                                sentence_id=conn.sentence_id,
                                sentence_type=SentenceType.FIRST,
                                content_type=ContentType.ACTION,
                            )
                        )

                    # Ripeti l'avviso 3 volte
                    for i in range(3):
                        conn.tts.tts_text_queue.put(
                            TTSMessageDTO(
                                sentence_id=conn.sentence_id,
                                sentence_type=SentenceType.MIDDLE,
                                content_type=ContentType.TEXT,
                                content_detail=alert_text if i == 0 else f"Timer {timer_name} scaduto!",
                            )
                        )
                        await asyncio.sleep(2)

                    if conn.intent_type == "intent_llm":
                        conn.tts.tts_text_queue.put(
                            TTSMessageDTO(
                                sentence_id=conn.sentence_id,
                                sentence_type=SentenceType.LAST,
                                content_type=ContentType.ACTION,
                            )
                        )
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Errore notifica timer: {e}")

    except asyncio.CancelledError:
        logger.bind(tag=TAG).info(f"Timer '{timer_name}' cancellato")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore timer: {e}")


@register_function("timer_sveglia", TIMER_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def timer_sveglia(conn, action: str = "list", minutes: float = None, seconds: float = None, name: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Timer: action={action}, minutes={minutes}, seconds={seconds}, name={name}")

    # Inizializza lista timer per sessione
    if session_id not in ACTIVE_TIMERS:
        ACTIVE_TIMERS[session_id] = []

    if action == "list":
        timers = ACTIVE_TIMERS.get(session_id, [])
        if not timers:
            return ActionResponse(Action.RESPONSE, "Nessun timer attivo", "Non hai timer attivi")

        result = "Timer attivi:\n"
        spoken_parts = []
        now = datetime.now()

        for t in timers:
            remaining = (t["end_time"] - now).total_seconds()
            if remaining > 0:
                result += f"- {t['name']}: {format_duration(int(remaining))} rimanenti\n"
                spoken_parts.append(f"{t['name']}, {format_duration(int(remaining))}")

        if spoken_parts:
            spoken = "Timer attivi: " + ", ".join(spoken_parts)
        else:
            spoken = "Non hai timer attivi"

        return ActionResponse(Action.RESPONSE, result, spoken)

    if action == "cancel" or action == "stop":
        timers = ACTIVE_TIMERS.get(session_id, [])

        if not timers:
            return ActionResponse(Action.RESPONSE, "Nessun timer da cancellare", "Non hai timer attivi")

        if name:
            # Cancella timer specifico
            found = None
            for t in timers:
                if name.lower() in t["name"].lower():
                    found = t
                    break

            if found:
                found["task"].cancel()
                ACTIVE_TIMERS[session_id] = [t for t in timers if t != found]
                return ActionResponse(Action.RESPONSE,
                    f"Timer '{found['name']}' cancellato",
                    f"Ho cancellato il timer {found['name']}")
            else:
                return ActionResponse(Action.RESPONSE,
                    f"Timer '{name}' non trovato",
                    f"Non trovo un timer chiamato {name}")
        else:
            # Cancella tutti
            for t in timers:
                t["task"].cancel()
            ACTIVE_TIMERS[session_id] = []
            return ActionResponse(Action.RESPONSE,
                "Tutti i timer cancellati",
                "Ho cancellato tutti i timer")

    if action == "set":
        # Calcola durata totale in secondi
        total_seconds = 0
        if minutes:
            total_seconds += int(minutes * 60)
        if seconds:
            total_seconds += int(seconds)

        if total_seconds <= 0:
            return ActionResponse(Action.RESPONSE,
                "Specifica la durata del timer",
                "Per quanto tempo vuoi il timer? Dimmi i minuti.")

        # Nome del timer
        timer_name = name if name else f"timer_{len(ACTIVE_TIMERS[session_id]) + 1}"

        # Verifica event loop
        if not conn.loop.is_running():
            return ActionResponse(Action.RESPONSE, "Errore sistema", "Sistema non pronto")

        # Crea task timer
        end_time = datetime.now() + timedelta(seconds=total_seconds)
        task = conn.loop.create_task(
            timer_countdown(conn, timer_name, total_seconds, session_id)
        )

        # Salva timer
        ACTIVE_TIMERS[session_id].append({
            "name": timer_name,
            "end_time": end_time,
            "task": task
        })

        duration_str = format_duration(total_seconds)
        return ActionResponse(Action.RESPONSE,
            f"Timer '{timer_name}' impostato per {duration_str}",
            f"Ok! Timer {timer_name} impostato per {duration_str}. Ti avviserò quando scade.")

    return ActionResponse(Action.RESPONSE, "Azione non riconosciuta", "Non ho capito cosa fare con il timer")
