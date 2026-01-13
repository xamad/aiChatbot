"""
Handle Exit Intent - Ferma qualsiasi funzione attiva
Gestisce: stop radio, stop immagini, stop giochi, ecc.
NON chiude la connessione - l'assistente rimane attivo
"""

from plugins_func.register import register_function, ToolType, ActionResponse, Action
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# Import per fermare sessioni attive
try:
    from plugins_func.functions.cerca_immagini import IMAGE_SESSIONS
except ImportError:
    IMAGE_SESSIONS = {}

try:
    from plugins_func.functions.cerca_gif import GIF_SESSIONS
except ImportError:
    GIF_SESSIONS = {}


def get_device_id(conn) -> str:
    """Get device ID from connection"""
    if hasattr(conn, 'device_id') and conn.device_id:
        return conn.device_id
    return str(id(conn))


handle_exit_intent_function_desc = {
    "type": "function",
    "function": {
        "name": "handle_exit_intent",
        "description": (
            "STOP GLOBALE - Ferma qualsiasi funzione attiva (radio, immagini, giochi, ecc.). "
            "TRIGGER: 'stop', 'basta', 'ferma', 'fermati', 'smetti', 'esci', 'annulla'. "
            "NON chiude la connessione - l'assistente rimane attivo dopo lo stop."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "say_goodbye": {
                    "type": "string",
                    "description": "Messaggio opzionale di conferma stop",
                }
            },
            "required": [],
        },
    },
}


@register_function(
    "handle_exit_intent", handle_exit_intent_function_desc, ToolType.SYSTEM_CTL
)
def handle_exit_intent(conn, say_goodbye: str = None):
    """
    Ferma tutte le funzioni attive per questo device.
    NON chiude la connessione - l'assistente rimane disponibile.
    """
    try:
        device_id = get_device_id(conn)
        stopped_items = []

        # Ferma sessione immagini
        if device_id in IMAGE_SESSIONS:
            session = IMAGE_SESSIONS[device_id]
            if hasattr(session, 'stop_slideshow'):
                session.stop_slideshow()
            del IMAGE_SESSIONS[device_id]
            stopped_items.append("slideshow immagini")
            logger.bind(tag=TAG).info(f"Fermato slideshow immagini per {device_id}")

        # Ferma sessione GIF
        if device_id in GIF_SESSIONS:
            session = GIF_SESSIONS[device_id]
            if hasattr(session, 'stop_animation'):
                session.stop_animation()
            del GIF_SESSIONS[device_id]
            stopped_items.append("animazione GIF")
            logger.bind(tag=TAG).info(f"Fermata animazione GIF per {device_id}")

        # Ferma eventuale audio in riproduzione (radio, podcast, ecc.)
        # Il TTS queue viene svuotato
        if hasattr(conn, 'tts') and conn.tts:
            try:
                # Svuota la coda TTS per fermare audio in corso
                while not conn.tts.tts_text_queue.empty():
                    try:
                        conn.tts.tts_text_queue.get_nowait()
                    except:
                        break
                stopped_items.append("audio")
            except Exception as e:
                logger.bind(tag=TAG).debug(f"Errore svuotamento TTS: {e}")

        # NON impostare close_after_chat = True
        # L'assistente deve rimanere attivo!

        if stopped_items:
            items_str = ", ".join(stopped_items)
            response = f"Ho fermato: {items_str}. Sono qui se hai bisogno."
            logger.bind(tag=TAG).info(f"Stop completato: {items_str}")
        else:
            response = "OK, sono qui. Come posso aiutarti?"
            logger.bind(tag=TAG).info("Stop richiesto ma nessuna funzione attiva")

        return ActionResponse(
            action=Action.RESPONSE,
            result="Stop completato",
            response=response
        )

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore handle_exit_intent: {e}")
        return ActionResponse(
            action=Action.RESPONSE,
            result="Errore stop",
            response="OK, fermato. Sono qui se hai bisogno."
        )
