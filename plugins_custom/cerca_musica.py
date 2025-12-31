"""
Cerca Musica Plugin - Cerca su YouTube, scarica e riproduce musica
"""

import os
import re
import hashlib
import asyncio
from pathlib import Path
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.handle.sendAudioHandle import send_stt_message
from core.utils.dialogue import Message
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

TAG = __name__
logger = setup_logging()

# Directory per cache musica (max 100MB)
MUSIC_CACHE_DIR = "/tmp/xiaozhi_music_cache"
MAX_CACHE_SIZE_MB = 100

CERCA_MUSICA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "cerca_musica",
        "description": (
            "搜索并播放YouTube音乐 / Cerca e riproduce musica da YouTube. "
            "当用户想听特定歌曲时使用。"
            "Use when: 'suona...', 'metti la canzone...', 'cerca e suona...', "
            "'voglio ascoltare...', 'play music...', 'fammi sentire...'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Nome della canzone o artista da cercare",
                },
            },
            "required": ["query"],
        },
    },
}


def get_cache_path(query: str) -> str:
    """Genera path cache basato sulla query"""
    os.makedirs(MUSIC_CACHE_DIR, exist_ok=True)
    # Hash della query per filename sicuro
    query_hash = hashlib.md5(query.lower().encode()).hexdigest()[:12]
    safe_name = re.sub(r'[^\w\s-]', '', query)[:30].strip().replace(' ', '_')
    return os.path.join(MUSIC_CACHE_DIR, f"{safe_name}_{query_hash}.mp3")


def check_cache(query: str) -> str:
    """Controlla se la canzone è in cache"""
    cache_path = get_cache_path(query)
    if os.path.exists(cache_path):
        logger.bind(tag=TAG).info(f"Cache hit: {cache_path}")
        return cache_path
    return None


def cleanup_cache():
    """Pulisce la cache se supera il limite"""
    try:
        if not os.path.exists(MUSIC_CACHE_DIR):
            return

        files = []
        total_size = 0
        for f in Path(MUSIC_CACHE_DIR).glob("*.mp3"):
            size = f.stat().st_size
            mtime = f.stat().st_mtime
            files.append((f, size, mtime))
            total_size += size

        # Se supera il limite, rimuovi i file più vecchi
        max_bytes = MAX_CACHE_SIZE_MB * 1024 * 1024
        if total_size > max_bytes:
            # Ordina per data (più vecchi prima)
            files.sort(key=lambda x: x[2])
            while total_size > max_bytes * 0.7 and files:  # Riduci al 70%
                f, size, _ = files.pop(0)
                f.unlink()
                total_size -= size
                logger.bind(tag=TAG).info(f"Cache cleanup: rimosso {f}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore cleanup cache: {e}")


def download_from_youtube(query: str, output_path: str) -> bool:
    """Scarica audio da YouTube usando yt-dlp"""
    try:
        import yt_dlp

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': output_path.replace('.mp3', '.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',  # 128kbps per file piccoli
            }],
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch1',  # Cerca e prendi il primo risultato
            'socket_timeout': 30,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Cerca e scarica
            logger.bind(tag=TAG).info(f"Cercando su YouTube: {query}")
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)

            if info and 'entries' in info and info['entries']:
                video_info = info['entries'][0]
                title = video_info.get('title', query)
                logger.bind(tag=TAG).info(f"Scaricato: {title}")
                return True, title

        return False, None

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore download YouTube: {e}")
        return False, None


@register_function("cerca_musica", CERCA_MUSICA_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def cerca_musica(conn, query: str):
    """Cerca e riproduce musica da YouTube"""

    if not query:
        return ActionResponse(Action.REQLLM, "Quale canzone vuoi ascoltare?", None)

    logger.bind(tag=TAG).info(f"Richiesta musica: {query}")

    # Controlla cache
    cached_path = check_cache(query)
    if cached_path:
        # Avvia riproduzione da cache in background
        conn.loop.create_task(play_downloaded_music(conn, cached_path, query))
        return ActionResponse(Action.NONE, "Riproduzione da cache", f"Riproduco {query}...")

    # Pulisci cache se necessario
    cleanup_cache()

    # Scarica in background e riproduci
    output_path = get_cache_path(query)
    conn.loop.create_task(download_and_play(conn, query, output_path))

    return ActionResponse(
        Action.REQLLM,
        f"Sto cercando '{query}' su YouTube... un attimo!",
        None
    )


async def download_and_play(conn, query: str, output_path: str):
    """Scarica da YouTube e riproduci (async)"""
    try:
        # Avvisa l'utente
        await send_stt_message(conn, f"Cerco {query} su YouTube...")

        # Scarica (in thread separato per non bloccare)
        loop = asyncio.get_event_loop()
        success, title = await loop.run_in_executor(
            None,
            download_from_youtube,
            query,
            output_path
        )

        if success and os.path.exists(output_path):
            await play_downloaded_music(conn, output_path, title or query)
        else:
            await send_stt_message(conn, f"Non ho trovato {query} su YouTube")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore download_and_play: {e}")
        await send_stt_message(conn, "Errore durante il download della musica")


async def play_downloaded_music(conn, music_path: str, song_name: str):
    """Riproduce il file musicale scaricato"""
    try:
        if not os.path.exists(music_path):
            logger.bind(tag=TAG).error(f"File non trovato: {music_path}")
            return

        # Annuncia la canzone
        text = f"Ecco a te: {song_name}"
        await send_stt_message(conn, text)
        conn.dialogue.put(Message(role="assistant", content=text))

        # Invia alla coda TTS per riproduzione
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
                content_file=music_path,
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

        logger.bind(tag=TAG).info(f"Riproduzione avviata: {music_path}")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore riproduzione: {e}")
