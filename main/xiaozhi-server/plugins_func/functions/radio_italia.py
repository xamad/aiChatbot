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
CHUNK_DURATION = 10  # Secondi per chunk (partenza veloce ~10-15 sec attesa)
MAX_CONTINUOUS_CHUNKS = 60  # Max chunk per sessione (60 x 10s = 10 minuti totali)

# Stazioni radio italiane con stream URL verificati (Gennaio 2026)
# Mix di stream MP3 diretti e HLS (m3u8)
RADIO_STATIONS = {
    # === RADIO COMMERCIALI ITALIANE ===
    "radio deejay": {
        "name": "Radio DeeJay",
        "url": "https://4c4b867c89244861ac216426883d1ad0.msvdn.net/radiodeejay/radiodeejay/master_ma.m3u8",
        "referer": "https://www.deejay.it/",
        "desc": "Musica e programmi cult"
    },
    "m2o": {
        "name": "m2o",
        "url": "https://4c4b867c89244861ac216426883d1ad0.msvdn.net/radiom2o/radiom2o/master_ma.m3u8",
        "referer": "https://www.m2o.it/",
        "desc": "Dance e musica elettronica"
    },
    "radio capital": {
        "name": "Radio Capital",
        "url": "https://streamcdnf25-4c4b867c89244861ac216426883d1ad0.msvdn.net/radiocapital/radiocapital/master_ma.m3u8",
        "referer": "https://www.capital.it/",
        "desc": "Classic rock e pop"
    },
    "radio zeta": {
        "name": "Radio Zeta",
        "url": "https://streamingv2.shoutcast.com/radio-zeta",
        "referer": "https://www.radiozeta.it/",
        "desc": "Generazione futuro - Hit italiane"
    },
    "radio z": {
        "name": "Radio Zeta",
        "url": "https://streamingv2.shoutcast.com/radio-zeta",
        "referer": "https://www.radiozeta.it/",
        "desc": "Generazione futuro - Hit italiane"
    },
    "radio italia": {
        "name": "Radio Italia",
        "url": "https://radioitaliasmi.akamaized.net/hls/live/2093120/RISMI/stream01/streamPlaylist.m3u8",
        "referer": "https://www.radioitalia.it/",
        "desc": "Solo musica italiana"
    },
    "radio 105": {
        "name": "Radio 105",
        "url": "https://icecast.unitedradio.it/Radio105.mp3",
        "referer": "https://www.105.net/",
        "desc": "Musica e news"
    },
    "virgin radio": {
        "name": "Virgin Radio",
        "url": "https://icecast.unitedradio.it/Virgin.mp3",
        "referer": "https://www.virginradio.it/",
        "desc": "Rock music"
    },
    "radio kiss kiss": {
        "name": "Radio Kiss Kiss",
        "url": "https://ice07.fluidstream.net/KissKiss.mp3",
        "referer": "https://www.kisskiss.it/",
        "desc": "Hit del momento"
    },
    "rtl 102.5": {
        "name": "RTL 102.5",
        "url": "https://streamingv2.shoutcast.com/rtl-1025",
        "referer": "https://www.rtl.it/",
        "desc": "Very Normal People - Hit italiane e internazionali"
    },
    "rtl": {
        "name": "RTL 102.5",
        "url": "https://streamingv2.shoutcast.com/rtl-1025",
        "referer": "https://www.rtl.it/",
        "desc": "Very Normal People - Hit italiane e internazionali"
    },
    "rtl 102": {
        "name": "RTL 102.5",
        "url": "https://streamingv2.shoutcast.com/rtl-1025",
        "referer": "https://www.rtl.it/",
        "desc": "Very Normal People"
    },
    # === RAI RADIO ===
    "rai radio 1": {
        "name": "Rai Radio 1",
        "url": "https://icestreaming.rai.it/1.mp3",
        "referer": "https://www.raiplayradio.it/",
        "desc": "Notizie e attualità"
    },
    "rai radio 2": {
        "name": "Rai Radio 2",
        "url": "https://icestreaming.rai.it/2.mp3",
        "referer": "https://www.raiplayradio.it/",
        "desc": "Musica e intrattenimento"
    },
    "rai radio 3": {
        "name": "Rai Radio 3",
        "url": "https://icestreaming.rai.it/3.mp3",
        "referer": "https://www.raiplayradio.it/",
        "desc": "Cultura e musica classica"
    },
    "rai radio classica": {
        "name": "Rai Radio Classica",
        "url": "https://icestreaming.rai.it/5.mp3",
        "referer": "https://www.raiplayradio.it/",
        "desc": "Musica classica"
    },
    # === NEWS E TALK ===
    "radio radicale": {
        "name": "Radio Radicale",
        "url": "https://stream.radioradicale.it/live.mp3",
        "referer": "https://www.radioradicale.it/",
        "desc": "Politica e Parlamento"
    },
    "radio cusano": {
        "name": "Radio Cusano Campus",
        "url": "https://ice05.fluidstream.net/RadioCusano.mp3",
        "referer": "https://www.radiocusanocampus.it/",
        "desc": "News e attualità"
    },
    # === RADIO INTERNAZIONALI ===
    "bbc world service": {
        "name": "BBC World Service",
        "url": "https://stream.live.vc.bbcmedia.co.uk/bbc_world_service",
        "referer": "https://www.bbc.co.uk/",
        "desc": "Notizie internazionali in inglese"
    },
    "bbc radio 4": {
        "name": "BBC Radio 4",
        "url": "https://stream.live.vc.bbcmedia.co.uk/bbc_radio_fourfm",
        "referer": "https://www.bbc.co.uk/",
        "desc": "News e cultura BBC"
    },
}

RADIO_ITALIA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "radio_italia",
        "description": (
            "ATTIVARE SEMPRE per ascoltare stazioni radio italiane in streaming. "
            "TRIGGER ESATTI: 'metti la radio', 'accendi radio', 'ascolta radio', "
            "'sintonizza', 'fammi sentire la radio', 'voglio ascoltare la radio', "
            "'radio deejay', 'radio zeta', 'radio 105', 'virgin radio', 'rtl', 'm2o', "
            "'rai radio', 'radio capital', 'kiss kiss', 'radio italia'. "
            "ELENCO: 'quali radio hai', 'elenco radio', 'che radio ci sono'. "
            "STOP: 'ferma la radio', 'stop radio', 'spegni radio'. "
            "ESEMPIO: 'metti radio deejay' → action='play', station='radio deejay'. "
            "Per chiedere: 'Metti [nome radio]' oppure 'Ascolta [nome radio]'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "station": {
                    "type": "string",
                    "description": "Nome stazione. Es: 'metti radio zeta' → station='radio zeta'",
                },
                "action": {
                    "type": "string",
                    "description": "play=avvia streaming, stop=ferma, list=mostra elenco stazioni",
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


def capture_radio_chunk(url: str, output_path: str, duration: int = 30, referer: str = None) -> bool:
    """
    Cattura un chunk di radio usando Python urllib (più affidabile per headers)
    poi converte in MP3 con ffmpeg
    """
    try:
        os.makedirs(RADIO_CACHE_DIR, exist_ok=True)
        import urllib.request

        # Headers browser completi
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
        }

        if referer:
            headers['Referer'] = referer
            headers['Origin'] = referer.rstrip('/')

        # Per stream HLS, usa ffmpeg con headers file
        if '.m3u8' in url or 'hls' in url.lower():
            return capture_hls_stream(url, output_path, duration, headers)

        # Per stream MP3 diretti, scarica con Python urllib
        req = urllib.request.Request(url, headers=headers)
        raw_file = output_path.replace('.mp3', '_raw.dat')

        try:
            # Calcola bytes da scaricare (assumo 320kbps = 40KB/s + 50% margine)
            bytes_to_download = duration * 60 * 1024  # ~480kbps per coprire tutti i bitrate

            with urllib.request.urlopen(req, timeout=duration + 30) as resp:
                if resp.status != 200:
                    logger.bind(tag=TAG).error(f"HTTP {resp.status} per {url}")
                    return False

                with open(raw_file, 'wb') as f:
                    downloaded = 0
                    while downloaded < bytes_to_download:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                logger.bind(tag=TAG).info(f"Scaricati {downloaded} bytes")

            # Converti con ffmpeg
            if os.path.exists(raw_file) and os.path.getsize(raw_file) > 1000:
                cmd = [
                    "ffmpeg", "-y", "-i", raw_file,
                    "-t", str(duration),
                    "-c:a", "libmp3lame", "-b:a", "128k",
                    output_path
                ]
                subprocess.run(cmd, capture_output=True, timeout=180)

                if os.path.exists(raw_file):
                    os.remove(raw_file)

                if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                    logger.bind(tag=TAG).info(f"Radio salvata: {output_path}")
                    return True

        except urllib.error.HTTPError as e:
            logger.bind(tag=TAG).error(f"HTTP Error {e.code}: {e.reason}")
            return False

        return False

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore cattura radio: {e}")
        return False


def capture_hls_stream(url: str, output_path: str, duration: int, headers: dict) -> bool:
    """Cattura stream HLS (m3u8) scaricando manifest e segments con Python"""
    import urllib.request
    import re

    try:
        req = urllib.request.Request(url, headers=headers)

        # Scarica il master manifest
        with urllib.request.urlopen(req, timeout=10) as resp:
            manifest = resp.read().decode('utf-8')

        # Trova URL degli stream (prendi la prima variante)
        stream_urls = re.findall(r'https?://[^\s\n"]+\.m3u8[^\s\n"]*', manifest)
        if not stream_urls:
            # Prova a trovare URL relativo
            stream_lines = [l for l in manifest.split('\n') if l.endswith('.m3u8') and not l.startswith('#')]
            if stream_lines:
                base_url = url.rsplit('/', 1)[0]
                stream_urls = [f"{base_url}/{stream_lines[0]}"]

        if not stream_urls:
            logger.bind(tag=TAG).error("Nessuno stream trovato nel manifest HLS")
            return False

        # Scarica il playlist dello stream
        stream_url = stream_urls[0]
        req = urllib.request.Request(stream_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            playlist = resp.read().decode('utf-8')

        # Trova i segment (.ts o .aac)
        segments = re.findall(r'(https?://[^\s\n"]+\.(ts|aac|mp4)[^\s\n"]*)', playlist)
        if not segments:
            # URL relativi
            segment_lines = [l.strip() for l in playlist.split('\n')
                           if not l.startswith('#') and l.strip() and
                           (l.endswith('.ts') or l.endswith('.aac') or '.ts?' in l)]
            if segment_lines:
                base_url = stream_url.rsplit('/', 1)[0]
                segments = [(f"{base_url}/{s}", 'ts') for s in segment_lines[:10]]

        if not segments:
            logger.bind(tag=TAG).error("Nessun segment trovato nel playlist HLS")
            return False

        # Scarica i primi N segments (circa duration secondi, ~3s per segment)
        num_segments = min(len(segments), duration // 3 + 1)
        raw_file = output_path.replace('.mp3', '_raw.ts')

        with open(raw_file, 'wb') as f:
            for seg_url, _ in segments[:num_segments]:
                try:
                    req = urllib.request.Request(seg_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        f.write(resp.read())
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"Segment skip: {e}")
                    continue

        if os.path.exists(raw_file) and os.path.getsize(raw_file) > 1000:
            # Converti in MP3
            cmd = [
                "ffmpeg", "-y", "-i", raw_file,
                "-t", str(duration),
                "-c:a", "libmp3lame", "-b:a", "128k",
                output_path
            ]
            subprocess.run(cmd, capture_output=True, timeout=180)
            os.remove(raw_file)

            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                logger.bind(tag=TAG).info(f"HLS salvato: {output_path}")
                return True

        return False

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore HLS: {e}")
        return False


@register_function("radio_italia", RADIO_ITALIA_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def radio_italia(conn, action: str = "list", station: str = None):
    logger.bind(tag=TAG).info(f"Radio Italia: action={action}, station={station}")

    if action == "list":
        result = "Ecco le radio disponibili: "
        result += "Radio DeeJay, m2o, Radio Capital, Radio Zeta, Radio Italia, "
        result += "Radio 105, Virgin Radio, RTL 102.5, Radio Kiss Kiss, "
        result += "Rai Radio 1, 2, 3, Radio Radicale, BBC World Service. "
        result += "Dimmi quale vuoi ascoltare!"
        return ActionResponse(Action.RESPONSE, result, None)

    if action == "stop":
        return ActionResponse(Action.RESPONSE, "Radio fermata!", None)

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

        # IMPORTANTE: Action.RESPONSE per evitare che l'LLM aggiunga domande
        # Il terzo parametro è il testo PARLATO - deve essere uguale al testo mostrato
        return ActionResponse(
            Action.RESPONSE,
            f"Sintonizzazione su {found['name']}... un momento!",
            f"Sintonizzazione su {found['name']}... un momento!"
        )

    return ActionResponse(Action.REQLLM, "Azione non riconosciuta", None)


async def capture_and_play_radio(conn, station: dict):
    """Cattura e riproduce chunk radio in streaming progressivo"""
    try:
        station_name = station["name"]
        url = station["url"]
        referer = station.get("referer")

        await send_stt_message(conn, f"Sintonizzazione su {station_name}...")

        safe_name = station_name.lower().replace(" ", "_").replace(".", "")
        loop = asyncio.get_event_loop()

        # Streaming progressivo: scarica e riproduci chunk uno alla volta
        for chunk_num in range(MAX_CONTINUOUS_CHUNKS):
            # Verifica se la connessione è ancora attiva
            if not hasattr(conn, 'websocket') or conn.websocket is None:
                logger.bind(tag=TAG).warning("Connessione chiusa, fermo radio")
                break

            try:
                # Controlla stato websocket
                if hasattr(conn.websocket, 'closed') and conn.websocket.closed:
                    logger.bind(tag=TAG).warning("WebSocket chiuso, fermo radio")
                    break
            except Exception:
                pass

            output_path = os.path.join(RADIO_CACHE_DIR, f"{safe_name}_{chunk_num}.mp3")

            # Scarica chunk
            success = await loop.run_in_executor(
                None,
                lambda p=output_path: capture_radio_chunk(url, p, CHUNK_DURATION, referer)
            )

            if success and os.path.exists(output_path):
                # Riproduci chunk
                await play_radio_chunk(conn, output_path, station_name, is_first=(chunk_num == 0))
                logger.bind(tag=TAG).info(f"Radio chunk {chunk_num + 1}/{MAX_CONTINUOUS_CHUNKS} riprodotto")

                # Breve pausa tra chunk per permettere riproduzione
                await asyncio.sleep(1)
            else:
                logger.bind(tag=TAG).error(f"Chunk {chunk_num} fallito")
                if chunk_num == 0:
                    await send_stt_message(conn, f"Non riesco a sintonizzare {station_name}")
                break

        logger.bind(tag=TAG).info(f"Streaming {station_name} completato")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore capture_and_play_radio: {e}")


async def play_radio_chunk(conn, audio_path: str, station_name: str, is_first: bool = True):
    """Riproduce il chunk audio della radio"""
    try:
        # Solo il primo chunk ha l'annuncio
        if is_first:
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

        # Invia file audio
        conn.tts.tts_text_queue.put(
            TTSMessageDTO(
                sentence_id=conn.sentence_id,
                sentence_type=SentenceType.MIDDLE,
                content_type=ContentType.FILE,
                content_file=audio_path,
            )
        )

        logger.bind(tag=TAG).info(f"Radio chunk in coda: {station_name}")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore riproduzione radio: {e}")
