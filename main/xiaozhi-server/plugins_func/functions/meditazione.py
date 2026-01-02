"""
Meditazione e Relax Plugin - Esercizi di respirazione e suoni rilassanti
"""

import asyncio
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType
from core.handle.sendAudioHandle import send_stt_message
from core.utils.dialogue import Message

TAG = __name__
logger = setup_logging()

# Esercizi di respirazione
BREATHING_EXERCISES = {
    "4-7-8": {
        "name": "Respirazione 4-7-8",
        "desc": "Tecnica rilassante per dormire meglio",
        "inhale": 4, "hold": 7, "exhale": 8,
        "cycles": 4
    },
    "box": {
        "name": "Respirazione a scatola",
        "desc": "Per calmare l'ansia",
        "inhale": 4, "hold": 4, "exhale": 4, "pause": 4,
        "cycles": 4
    },
    "calm": {
        "name": "Respirazione calmante",
        "desc": "Semplice e rilassante",
        "inhale": 4, "hold": 2, "exhale": 6,
        "cycles": 5
    },
}

# Testi guidati per meditazione breve
MEDITATION_SCRIPTS = {
    "mattina": [
        "Chiudi gli occhi e fai un respiro profondo.",
        "Senti il tuo corpo che si risveglia dolcemente.",
        "Pensa a qualcosa di bello che accadrà oggi.",
        "Inspira energia positiva. Espira ogni tensione.",
        "Sei pronto per affrontare questa giornata con serenità.",
    ],
    "sera": [
        "Chiudi gli occhi e lascia andare le tensioni della giornata.",
        "Ogni respiro ti porta più rilassamento.",
        "Pensa a qualcosa di positivo successo oggi.",
        "Lascia andare ogni pensiero, ogni preoccupazione.",
        "Il tuo corpo è pesante e rilassato. Buonanotte.",
    ],
    "stress": [
        "Fermati un momento. Sei al sicuro.",
        "Fai tre respiri profondi con me.",
        "Inspira lentamente... ed espira.",
        "Qualunque cosa ti preoccupi, passerà.",
        "Concentrati solo su questo momento presente.",
    ],
}

MEDITAZIONE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "meditazione",
        "description": (
            "Esercizi di meditazione, respirazione e relax."
            "Usare quando: aiutami a rilassarmi, esercizio di respirazione, sono stressato, "
            "meditazione guidata, non riesco a dormire, calmami"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Tipo: breathing (respirazione), meditation (meditazione guidata)",
                    "enum": ["breathing", "meditation", "quick"]
                },
                "exercise": {
                    "type": "string",
                    "description": "Esercizio specifico: 4-7-8, box, calm, mattina, sera, stress"
                }
            },
            "required": ["type"],
        },
    },
}


async def guided_breathing(conn, exercise: dict):
    """Esegue esercizio di respirazione guidata"""
    try:
        name = exercise["name"]
        cycles = exercise.get("cycles", 4)
        inhale = exercise.get("inhale", 4)
        hold = exercise.get("hold", 4)
        exhale = exercise.get("exhale", 4)
        pause = exercise.get("pause", 0)

        # Intro
        intro = f"Iniziamo {name}. Mettiti comodo e chiudi gli occhi."
        await send_stt_message(conn, intro)

        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )

        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail=intro,
            )
        )

        await asyncio.sleep(3)

        # Cicli di respirazione
        for cycle in range(1, cycles + 1):
            # Inspira
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=f"Inspira... {inhale} secondi",
                )
            )
            await asyncio.sleep(inhale + 1)

            # Trattieni
            if hold > 0:
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.MIDDLE,
                        content_type=ContentType.TEXT,
                        content_detail=f"Trattieni... {hold} secondi",
                    )
                )
                await asyncio.sleep(hold + 1)

            # Espira
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=f"Espira lentamente... {exhale} secondi",
                )
            )
            await asyncio.sleep(exhale + 1)

            # Pausa (per box breathing)
            if pause > 0:
                await asyncio.sleep(pause)

        # Conclusione
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.TEXT,
                content_detail="Ottimo lavoro. Apri gli occhi quando sei pronto.",
            )
        )

        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore respirazione guidata: {e}")


async def guided_meditation(conn, script_type: str):
    """Esegue meditazione guidata"""
    try:
        script = MEDITATION_SCRIPTS.get(script_type, MEDITATION_SCRIPTS["stress"])

        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.FIRST,
                    content_type=ContentType.ACTION,
                )
            )

        for line in script:
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.TEXT,
                    content_detail=line,
                )
            )
            await asyncio.sleep(5)  # Pausa tra le frasi

        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore meditazione: {e}")


@register_function("meditazione", MEDITAZIONE_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def meditazione(conn, type: str = "quick", exercise: str = None):
    logger.bind(tag=TAG).info(f"Meditazione: type={type}, exercise={exercise}")

    if type == "breathing":
        # Trova esercizio
        ex_key = exercise.lower().replace(" ", "-").replace("_", "-") if exercise else "calm"
        ex = BREATHING_EXERCISES.get(ex_key, BREATHING_EXERCISES["calm"])

        if not conn.loop.is_running():
            return ActionResponse(Action.RESPONSE, "Sistema non pronto", "Sistema non pronto")

        task = conn.loop.create_task(guided_breathing(conn, ex))
        task.add_done_callback(lambda f: logger.bind(tag=TAG).info("Respirazione completata"))

        return ActionResponse(Action.NONE, None, None)

    if type == "meditation":
        script_type = exercise if exercise in MEDITATION_SCRIPTS else "stress"

        if not conn.loop.is_running():
            return ActionResponse(Action.RESPONSE, "Sistema non pronto", "Sistema non pronto")

        task = conn.loop.create_task(guided_meditation(conn, script_type))
        task.add_done_callback(lambda f: logger.bind(tag=TAG).info("Meditazione completata"))

        return ActionResponse(Action.NONE, None, None)

    if type == "quick":
        # Risposta rapida per calmare
        return ActionResponse(Action.RESPONSE,
            "Fai 3 respiri profondi. Inspira per 4 secondi, espira per 6.",
            "Fermiamoci un momento. Fai tre respiri profondi con me. Inspira lentamente... e espira. Ti senti già meglio?")

    return ActionResponse(Action.RESPONSE,
        "Posso guidarti in esercizi di respirazione o meditazione. Cosa preferisci?",
        "Vuoi un esercizio di respirazione o una meditazione guidata?")
