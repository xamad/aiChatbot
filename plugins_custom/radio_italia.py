"""
Radio Italia Plugin - Riproduce stazioni radio italiane in streaming
Cattura chunk audio e li riproduce tramite il sistema TTS
"""

import os
import subprocess
import asyncio
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.handle.sendAudioHandle import send_stt_message
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__
logger = setup_logging()

# Directory cache radio
RADIO_CACHE_DIR = "/tmp/xiaozhi_radio"
CHUNK_DURATION = 60  # Secondi per chunk

# Stazioni radio italiane con stream URL
RADIO_STATIONS = {
    "rai radio 1": {
        "name": "Rai Radio 1",
        "url": "https://icestreaming.rai.it/1.mp3",
        "desc": "Notizie e attualità"
    },
    "rai radio 2": {
        "name": "Rai Radio 2",
        "url": "https://icestreaming.rai.it/2.mp3",
        "desc": "Musica e intrattenimento"
    },
    "rai radio 3": {
        "name": "Rai Radio 3",
        "url": "https://icestreaming.rai.it/3.mp3",
        "desc": "Cultura e musica classica"
    },
    "radio deejay": {
        "name": "Radio DeeJay",
        "url": "https://radiodeejay-lh.akamaihd.net/i/RadioDeejay_Live_1@189857/master.m3u8",
        "desc": "Musica pop e dance"
    },
    "rtl 102.5": {
        "name": "RTL 102.5",
        "url": "https://dd.rtl.it/broadcast/rtl1025.mp3",
        "desc": "Very Normal People"
    },
    "radio 105": {
        "name": "Radio 105",
        "url": "https://icecast.unitedradio.it/Radio105.mp3",
        "desc": "Musica e news"
    },
    "radio italia": {
        "name": "Radio Italia",
        "url": "https://radioitaliasmi.akamaized.net/hls/live/2093120/RADIOITALIA/stream01/streamPlaylist.m3u8",
        "desc": "Solo musica italiana"
    },
    "virgin radio": {
        "name": "Virgin Radio",
        "url": "https://icecast.unitedradio.it/Virgin.mp3",
        "desc": "Rock music"
    },
    "radio kiss kiss": {
        "name": "Radio Kiss Kiss",
        "url": "https://ice07.fluidstream.net/KissKiss.mp3",
        "desc": "Hit del momento"
    },
    "m2o": {
        "name": "m2o",
        "url": "https://m2o.akamaized.net/hls/live/2093123/M2O/master.m3u8",
        "desc": "Dance e elettronica"
    },
    "radio capital": {
        "name": "Radio Capital",
        "url": "https://capital.akamaized.net/hls/live/2093122/CAPITAL/master.m3u8",
        "desc": "Classic rock"
    },
    "rds": {
        "name": "RDS 100% Grandi Successi",
        "url": "https://stream.rds.it/rds.mp3",
        "desc": "Grandi successi"
    },
    "radio 24": {
        "name": "Radio 24",
        "url": "https://shoutcast.radio24.it/radio24",
        "desc": "News e informazione"
    },
    "radio zeta": {
        "name": "Radio Zeta",
        "url": "https://radiozeta.akamaized.net/hls/live/2093124/RADIOZETA/master.m3u8",
        "desc": "Future Hits - Musica giovane"
    },
    "radio freccia": {
        "name": "Radio Freccia",
        "url": "https://radiofreccia.akamaized.net/hls/live/2093121/RADIOFRECCIA/master.m3u8",
        "desc": "Rock italiano"
    },
    "radio monte carlo": {
        "name": "Radio Monte Carlo",
        "url": "https://rmc.akamaized.net/hls/live/2093125/RMC/master.m3u8",
        "desc": "Musica raffinata"
    },
}

RADIO_ITALIA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "radio_italia",
        "description": (
            "播放意大利广播电台 / Riproduce stazioni radio italiane in streaming. "
            "当用户想听广播时使用。"
            "Use when: 'metti radio...', 'ascolta radio...', 'radio deejay', 'rai radio 1', "
            "'accendi la radio', 'fammi sentire rtl'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "station": {
                    "type": "string",
                    "description": "Nome della stazione radio (es: radio deejay, rtl 102.5, rai radio 1)",
                },
                "action": {
                    "type": "string",
                    "description": "Azione: play (avvia), stop (ferma), list (elenco stazioni)",
                    "enum": ["play", "stop", "list"]
                },
            },
            "required": ["action"],
        },
    },
}


def find_station(query: str) -> dict:
    """Trova la stazione radio più simile alla query"""
    if not query:
        return None

    query = query.lower().strip()

    # Match esatto
    if query in RADIO_STATIONS:
        return RADIO_STATIONS[query]

    # Match parziale
    for key, station in RADIO_STATIONS.items():
        if query in key or key in query:
            return station
        if query in station["name"].lower():
            return station

    # Match parole singole
    query_words = query.split()
    for key, station in RADIO_STATIONS.items():
        for word in query_words:
            if len(word) > 2 and (word in key or word in station["name"].lower()):
                return station

    return None


def capture_radio_chunk(url: str, output_path: str, duration: int = 60) -> bool:
    """Cattura un chunk di radio usando ffmpeg"""
    try:
        os.makedirs(RADIO_CACHE_DIR, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "-i", url,
            "-t", str(duration),
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            "-y",
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=duration + 30
        )

        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.bind(tag=TAG).info(f"Radio catturata: {output_path}")
            return True

        return False

    except subprocess.TimeoutExpired:
        logger.bind(tag=TAG).error("Timeout cattura radio")
        return False
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore cattura radio: {e}")
        return False


@register_function("radio_italia", RADIO_ITALIA_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def radio_italia(conn, action: str = "list", station: str = None):
    logger.bind(tag=TAG).info(f"Radio Italia: action={action}, station={station}")

    if action == "list":
        result = "📻 **Stazioni radio disponibili:**\n\n"
        for key, s in RADIO_STATIONS.items():
            result += f"• **{s['name']}** - {s['desc']}\n"
        result += "\nDi' 'metti [nome radio]' per ascoltare!"
        return ActionResponse(Action.REQLLM, result, None)

    if action == "stop":
        return ActionResponse(Action.REQLLM, "Radio fermata", None)

    if action == "play":
        if not station:
            return ActionResponse(Action.REQLLM,
                "Quale radio vuoi ascoltare? Di' 'metti radio deejay' o 'elenco radio'", None)

        found = find_station(station)
        if not found:
            stations_list = ", ".join([s["name"] for s in list(RADIO_STATIONS.values())[:5]])
            return ActionResponse(Action.REQLLM,
                f"Radio '{station}' non trovata. Prova: {stations_list}...", None)

        # Avvia cattura e riproduzione in background
        conn.loop.create_task(capture_and_play_radio(conn, found))

        return ActionResponse(
            Action.REQLLM,
            f"Sintonizzazione su **{found['name']}**... un momento!",
            None
        )

    return ActionResponse(Action.REQLLM, "Azione non riconosciuta", None)


async def capture_and_play_radio(conn, station: dict):
    """Cattura chunk radio e riproducilo"""
    try:
        station_name = station["name"]
        url = station["url"]

        await send_stt_message(conn, f"Sintonizzazione su {station_name}...")

        # Nome file cache
        safe_name = station_name.lower().replace(" ", "_").replace(".", "")
        output_path = os.path.join(RADIO_CACHE_DIR, f"{safe_name}.mp3")

        # Cattura in thread separato
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            capture_radio_chunk,
            url,
            output_path,
            CHUNK_DURATION
        )

        if success and os.path.exists(output_path):
            await play_radio_chunk(conn, output_path, station_name)
        else:
            await send_stt_message(conn, f"Non riesco a sintonizzare {station_name}")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore capture_and_play_radio: {e}")


async def play_radio_chunk(conn, audio_path: str, station_name: str):
    """Riproduce il chunk audio della radio"""
    try:
        text = f"Ecco {station_name}!"
        await send_stt_message(conn, text)
        conn.dialogue.put(Message(role="assistant", content=text))

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
                content_detail=text,
            )
        )

        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.FILE,
                content_file=audio_path,
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

        logger.bind(tag=TAG).info(f"Radio in riproduzione: {station_name}")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore riproduzione radio: {e}")
