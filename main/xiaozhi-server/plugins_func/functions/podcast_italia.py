"""
Podcast Italia Plugin - Streaming podcast italiani
Utilizza feed RSS per trovare episodi recenti
"""

import os
import subprocess
import asyncio
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType
from core.handle.sendAudioHandle import send_stt_message
from core.utils.dialogue import Message

TAG = __name__
logger = setup_logging()

PODCAST_CACHE_DIR = "/tmp/xiaozhi_podcast"
CHUNK_DURATION = 60  # 1 minuto per chunk

# Podcast italiani popolari con stream URL
PODCASTS = {
    "il_podcast_di_alessandro_barbero": {
        "name": "Alessandro Barbero - Storia",
        "desc": "Lezioni di storia",
        "category": "storia",
        # Questi sono esempi - in produzione si userebbe RSS feed
        "stream_url": None,  # Da popolare via RSS
    },
    "power_pizza": {
        "name": "Power Pizza",
        "desc": "Tecnologia e cultura pop",
        "category": "tecnologia",
        "stream_url": None,
    },
    "veleno": {
        "name": "Veleno",
        "desc": "True crime italiano",
        "category": "true_crime",
        "stream_url": None,
    },
}

# Per ora uso radio/audio di notizie come "podcast"
NEWS_AUDIO_STREAMS = {
    "rai_gr1": {
        "name": "RAI GR1 - Giornale Radio",
        "desc": "Notizie in diretta",
        "url": "https://icestreaming.rai.it/1.mp3",
        "category": "notizie"
    },
    "rai_radio3": {
        "name": "RAI Radio 3 - Cultura",
        "desc": "Programmi culturali",
        "url": "https://icestreaming.rai.it/3.mp3",
        "category": "cultura"
    },
}

PODCAST_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "podcast_italia",
        "description": (
            "Riproduce podcast e programmi audio italiani."
            "Usare quando: metti un podcast, ascolta podcast, programma radio, "
            "podcast di notizie, qualcosa da ascoltare"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Azione: play (riproduci), list (elenca), stop (ferma)",
                    "enum": ["play", "list", "stop"]
                },
                "category": {
                    "type": "string",
                    "description": "Categoria: notizie, cultura, storia, tecnologia"
                },
                "name": {
                    "type": "string",
                    "description": "Nome specifico del podcast"
                }
            },
            "required": ["action"],
        },
    },
}


def capture_audio_chunk(url: str, output_path: str, duration: int = 60) -> bool:
    """Cattura chunk audio"""
    try:
        os.makedirs(PODCAST_CACHE_DIR, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-user_agent", "Mozilla/5.0",
            "-i", url,
            "-t", str(duration),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=duration + 30)

        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return True
        return False

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore cattura: {e}")
        return False


PODCAST_STATE = {}


def get_session_id(conn):
    try:
        return conn.session_id if hasattr(conn, 'session_id') else str(id(conn))
    except:
        return str(id(conn))


async def play_podcast_stream(conn, podcast: dict):
    """Riproduce podcast/stream audio"""
    try:
        name = podcast["name"]
        url = podcast["url"]
        session_id = get_session_id(conn)

        PODCAST_STATE[session_id] = {"playing": True}

        logger.bind(tag=TAG).info(f"Avvio podcast: {name}")

        intro = f"Avvio {name}. Di' 'stop' per fermare."
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
                content_detail=f"Ecco {name}",
            )
        )

        loop = asyncio.get_event_loop()
        chunk_num = 0
        max_chunks = 30  # Max 30 minuti

        while chunk_num < max_chunks:
            if not PODCAST_STATE.get(session_id, {}).get("playing", False):
                break
            if conn.stop_event.is_set():
                break

            output_path = os.path.join(PODCAST_CACHE_DIR, f"podcast_{chunk_num % 2}.mp3")

            success = await loop.run_in_executor(
                None, capture_audio_chunk, url, output_path, CHUNK_DURATION
            )

            if success:
                conn.tts.tts_text_queue.put(
                    TTSMessageDTO(
                        sentence_id=conn.sentence_id,
                        sentence_type=SentenceType.MIDDLE,
                        content_type=ContentType.FILE,
                        content_file=output_path,
                    )
                )
                chunk_num += 1
            else:
                await asyncio.sleep(2)

            await asyncio.sleep(0.5)

        PODCAST_STATE[session_id]["playing"] = False

        if conn.intent_type == "intent_llm":
            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.LAST,
                    content_type=ContentType.ACTION,
                )
            )

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore podcast: {e}")


@register_function("podcast_italia", PODCAST_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def podcast_italia(conn, action: str = "list", category: str = None, name: str = None):
    session_id = get_session_id(conn)
    logger.bind(tag=TAG).info(f"Podcast: action={action}, category={category}, name={name}")

    if action == "list":
        result = "Programmi disponibili:\n"
        for key, p in NEWS_AUDIO_STREAMS.items():
            result += f"- {p['name']}: {p['desc']}\n"
        return ActionResponse(Action.RESPONSE, result,
            "Ho programmi di notizie e cultura dalla RAI. Quale vuoi?")

    if action == "stop":
        if session_id in PODCAST_STATE:
            PODCAST_STATE[session_id]["playing"] = False
        return ActionResponse(Action.RESPONSE, "Podcast fermato", "Ho fermato il programma")

    if action == "play":
        # Trova podcast per categoria o nome
        podcast = None

        if name:
            for key, p in NEWS_AUDIO_STREAMS.items():
                if name.lower() in p["name"].lower() or name.lower() in key:
                    podcast = p
                    break

        if not podcast and category:
            for key, p in NEWS_AUDIO_STREAMS.items():
                if p.get("category") == category.lower():
                    podcast = p
                    break

        if not podcast:
            # Default: RAI Radio 3 cultura
            podcast = NEWS_AUDIO_STREAMS["rai_radio3"]

        if not conn.loop.is_running():
            return ActionResponse(Action.RESPONSE, "Sistema non pronto", "Sistema non pronto")

        task = conn.loop.create_task(play_podcast_stream(conn, podcast))
        task.add_done_callback(lambda f: logger.bind(tag=TAG).info("Podcast completato"))

        return ActionResponse(Action.NONE, None, None)

    return ActionResponse(Action.RESPONSE, "Cosa vuoi ascoltare?", "Quale programma vuoi?")
