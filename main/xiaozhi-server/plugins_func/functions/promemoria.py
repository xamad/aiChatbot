"""
Promemoria Plugin - Gestisce promemoria e sveglie programmate
Permette all'utente di impostare promemoria che verranno annunciati automaticamente
Usa ReminderScheduler per persistenza e invio proattivo
"""

from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.reminder_scheduler import get_reminder_scheduler
from datetime import datetime, timedelta
from config.logger import setup_logging
import re

TAG = __name__
logger = setup_logging()

PROMEMORIA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "promemoria",
        "description": (
            "Gestisce promemoria e sveglie programmate. "
            "Usa quando l'utente vuole: impostare un promemoria, una sveglia, "
            "ricordare di prendere medicine, ricordare un appuntamento, "
            "vedere i promemoria attivi, cancellare promemoria."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: set (imposta), list (elenca), cancel (cancella uno), cancel_all (cancella tutti)",
                    "enum": ["set", "list", "cancel", "cancel_all"]
                },
                "text": {
                    "type": "string",
                    "description": "Testo del promemoria (es: 'chiamare il dottore', 'prendere la medicina')"
                },
                "hour": {
                    "type": "number",
                    "description": "Ora del promemoria (0-23)"
                },
                "minute": {
                    "type": "number",
                    "description": "Minuto del promemoria (0-59), default 0"
                },
                "in_minutes": {
                    "type": "number",
                    "description": "Tra quanti minuti ricordare (alternativa a ora specifica)"
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo: promemoria, farmaco, appuntamento, sveglia",
                    "enum": ["promemoria", "farmaco", "appuntamento", "sveglia"]
                },
                "repeat": {
                    "type": "boolean",
                    "description": "Se ripetere ogni giorno (default false)"
                },
                "index": {
                    "type": "integer",
                    "description": "Numero del promemoria da cancellare (per action cancel)"
                }
            },
            "required": ["action"]
        }
    }
}


def parse_time_string(orario_str: str) -> tuple:
    """
    Converte vari formati di orario in (hour, minute)
    Supporta: "8:30", "8 e 30", "le 8", "otto e mezza", "mezzogiorno", etc.
    Returns: (hour, minute) or (None, None) if parsing fails
    """
    if not orario_str:
        return None, None

    orario_str = orario_str.lower().strip()

    # Casi speciali
    if "mezzogiorno" in orario_str:
        return 12, 0
    if "mezzanotte" in orario_str:
        return 0, 0

    # Prova formato HH:MM diretto
    match = re.match(r'^(\d{1,2}):(\d{2})$', orario_str)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m

    # Prova formato "8 e 30" o "8 e mezza"
    match = re.match(r'^(\d{1,2})\s*e\s*(\d{1,2}|mezza|mezzo)$', orario_str)
    if match:
        h = int(match.group(1))
        m_str = match.group(2)
        m = 30 if m_str in ["mezza", "mezzo"] else int(m_str)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m

    return None, None


@register_function("promemoria", PROMEMORIA_FUNCTION_DESC, ToolType.WAIT)
def promemoria(conn, action: str = "list", text: str = None,
               hour: int = None, minute: int = None, in_minutes: int = None,
               tipo: str = "promemoria", repeat: bool = False, index: int = None):
    """Gestisce promemoria e sveglie programmate"""

    device_id = conn.headers.get("device-id", "unknown")
    scheduler = get_reminder_scheduler()

    logger.bind(tag=TAG).info(
        f"Promemoria: action={action}, text={text}, hour={hour}, "
        f"minute={minute}, in_minutes={in_minutes}, tipo={tipo}"
    )

    # === LISTA PROMEMORIA ===
    if action == "list":
        reminders = scheduler.get_reminders(device_id)
        if not reminders:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Non hai promemoria attivi al momento."
            )

        lista = []
        for i, r in enumerate(reminders):
            msg = r.get("message", "promemoria")
            time = r.get("time", "")
            tipo_r = r.get("type", "promemoria")
            ripete = " (ogni giorno)" if r.get("repeat") else ""
            lista.append(f"{i+1}. Alle {time}: {msg}{ripete}")

        testo = "Ecco i tuoi promemoria attivi:\n" + "\n".join(lista)
        return ActionResponse(
            action=Action.RESPONSE,
            result=testo
        )

    # === CANCELLA UN PROMEMORIA ===
    elif action == "cancel":
        if index is None:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Dimmi quale promemoria vuoi cancellare. Puoi dire 'mostra promemoria' per vedere la lista numerata."
            )

        success = scheduler.remove_reminder(device_id, index - 1)  # Indice 1-based per utente
        if success:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Ho cancellato il promemoria numero {index}."
            )
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Non ho trovato il promemoria numero {index}. Prova a dire 'mostra promemoria' per vedere la lista."
            )

    # === CANCELLA TUTTI ===
    elif action == "cancel_all":
        scheduler.clear_reminders(device_id)
        return ActionResponse(
            action=Action.RESPONSE,
            result="Ho cancellato tutti i tuoi promemoria."
        )

    # === IMPOSTA PROMEMORIA ===
    elif action == "set":
        if not text:
            if tipo == "farmaco":
                text = "prendere le medicine"
            elif tipo == "sveglia":
                text = "è ora di svegliarsi"
            elif tipo == "appuntamento":
                text = "hai un appuntamento"
            else:
                return ActionResponse(
                    action=Action.RESPONSE,
                    result="Cosa vuoi che ti ricordi?"
                )

        now = datetime.now()

        # Calcola orario promemoria
        if in_minutes and in_minutes > 0:
            # "Tra X minuti"
            reminder_time = now + timedelta(minutes=in_minutes)
            orario_parsed = reminder_time.strftime("%H:%M")
        elif hour is not None:
            # Ora specifica
            minute = minute if minute is not None else 0
            orario_parsed = f"{int(hour):02d}:{int(minute):02d}"

            # Verifica se l'ora è già passata oggi
            reminder_dt = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            if reminder_dt <= now and not repeat:
                # Se è già passata e non è ripetitiva, sarà per domani
                pass  # Lo scheduler gestirà questo caso
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result="A che ora vuoi il promemoria? Dimmelo come 'alle 8', '14 e 30', o 'tra 30 minuti'."
            )

        # Crea promemoria
        reminder = {
            "message": text,
            "time": orario_parsed,
            "type": tipo,
            "repeat": repeat
        }

        success = scheduler.add_reminder(device_id, reminder)

        if success:
            ripeti_txt = " ogni giorno" if repeat else ""
            tipo_txt = ""
            if tipo == "farmaco":
                tipo_txt = " per le medicine"
            elif tipo == "sveglia":
                tipo_txt = " come sveglia"
            elif tipo == "appuntamento":
                tipo_txt = " per l'appuntamento"

            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Perfetto! Ti ricorderò alle {orario_parsed}{tipo_txt}{ripeti_txt}: {text}"
            )
        else:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Mi dispiace, non sono riuscito a salvare il promemoria. Riprova tra poco."
            )

    else:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Non ho capito cosa vuoi fare. Puoi dire 'imposta promemoria alle 8', 'mostra promemoria', o 'cancella promemoria'."
        )
