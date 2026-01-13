"""
Cerca Musica Web Plugin - Cerca e riproduci MP3/musica dal web
Usa DuckDuckGo per trovare file audio e li riproduce sull'ESP32
"""

import re
import json
import asyncio
import aiohttp
import threading
import time
from urllib.parse import quote, urlparse, parse_qs
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Sessioni musicali attive
MUSIC_SESSIONS = {}

# Siti con audio gratuito/libero
MUSIC_SOURCES = [
    # Archivi audio liberi
    "archive.org",
    "freemusicarchive.org",
    "jamendo.com",
    "soundcloud.com",
    # Classica/Royalty free
    "incompetech.com",
    "bensound.com",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


class MusicSession:
    """Gestisce una sessione di riproduzione musicale"""

    def __init__(self, device_id: str, conn, tracks: list, query: str):
        self.device_id = device_id
        self.conn = conn
        self.tracks = tracks  # Lista di dict con url, title
        self.query = query
        self.current_index = 0
        self.playing = False
        self.playlist_mode = False

    def play_current(self) -> bool:
        """Riproduci traccia corrente"""
        if self.current_index >= len(self.tracks):
            return False

        track = self.tracks[self.current_index]
        self.playing = True

        # Invia comando play al device
        self._send_play_command(track)
        return True

    def _send_play_command(self, track: dict):
        """Invia comando di riproduzione al device"""
        try:
            message = {
                "type": "audio_play",
                "action": "play",
                "url": track.get("url", ""),
                "title": track.get("title", "Traccia sconosciuta"),
                "artist": track.get("artist", ""),
                "index": self.current_index + 1,
                "total": len(self.tracks),
                "format": track.get("format", "mp3")
            }

            if hasattr(self.conn, 'websocket') and self.conn.websocket:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self.conn.websocket.send(json.dumps(message)),
                            loop
                        )
                except Exception as e:
                    logger.bind(tag=TAG).debug(f"Invio comando audio: {e}")

            logger.bind(tag=TAG).info(f"Play: {track.get('title')} - {track.get('url')[:50]}")

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore invio comando play: {e}")

    def stop(self):
        """Ferma riproduzione"""
        self.playing = False
        self._send_stop_command()

    def _send_stop_command(self):
        """Invia comando stop"""
        try:
            message = {
                "type": "audio_play",
                "action": "stop"
            }
            if hasattr(self.conn, 'websocket') and self.conn.websocket:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self.conn.websocket.send(json.dumps(message)),
                            loop
                        )
                except:
                    pass
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore stop: {e}")

    def next_track(self) -> bool:
        """Prossima traccia"""
        if self.current_index < len(self.tracks) - 1:
            self.current_index += 1
            return self.play_current()
        return False

    def prev_track(self) -> bool:
        """Traccia precedente"""
        if self.current_index > 0:
            self.current_index -= 1
            return self.play_current()
        return False

    def get_status(self) -> str:
        if self.current_index < len(self.tracks):
            track = self.tracks[self.current_index]
            return f"{track.get('title', 'Traccia')} ({self.current_index + 1}/{len(self.tracks)})"
        return "Nessuna traccia"


async def search_music_duckduckgo(query: str, num_results: int = 10) -> list:
    """Cerca file audio/MP3 su DuckDuckGo"""
    try:
        # Aggiungi keywords per trovare MP3
        search_query = f"{query} mp3 download free"

        # Prima ottieni token
        token_url = "https://duckduckgo.com/"
        params = {"q": search_query}

        async with aiohttp.ClientSession() as session:
            async with session.get(token_url, params=params, headers=HEADERS) as resp:
                text = await resp.text()
                match = re.search(r'vqd=([^&"]+)', text)
                if not match:
                    return []
                vqd = match.group(1)

            # Cerca
            search_url = "https://duckduckgo.com/html/"
            data = {"q": search_query, "vqd": vqd}

            async with session.post(search_url, data=data, headers=HEADERS) as resp:
                if resp.status != 200:
                    return []

                html = await resp.text()

                # Estrai risultati
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')

                tracks = []
                for result in soup.select('.result')[:num_results * 2]:
                    title_elem = result.select_one('.result__title')
                    snippet_elem = result.select_one('.result__snippet')
                    link_elem = result.select_one('.result__a')

                    if not link_elem:
                        continue

                    href = link_elem.get('href', '')
                    # Estrai URL reale
                    if 'uddg=' in href:
                        from urllib.parse import parse_qs, urlparse
                        parsed = parse_qs(urlparse(href).query)
                        url = parsed.get('uddg', [''])[0]
                    else:
                        url = href

                    title = title_elem.get_text(strip=True) if title_elem else "Traccia"

                    # Verifica se è un link audio diretto o una pagina con audio
                    if any(ext in url.lower() for ext in ['.mp3', '.m4a', '.ogg', '.wav', '.flac']):
                        tracks.append({
                            "url": url,
                            "title": title,
                            "format": "mp3",
                            "direct": True
                        })
                    elif any(site in url.lower() for site in MUSIC_SOURCES):
                        tracks.append({
                            "url": url,
                            "title": title,
                            "format": "page",
                            "direct": False
                        })

                    if len(tracks) >= num_results:
                        break

                return tracks

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore ricerca musica: {e}")
        return []


async def search_archive_org(query: str, num_results: int = 10) -> list:
    """Cerca musica su Archive.org (audio libero)"""
    try:
        url = "https://archive.org/advancedsearch.php"
        params = {
            "q": f"{query} AND mediatype:audio",
            "fl[]": ["identifier", "title", "creator"],
            "sort[]": "downloads desc",
            "rows": num_results,
            "page": 1,
            "output": "json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=HEADERS) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                tracks = []

                for doc in data.get("response", {}).get("docs", []):
                    identifier = doc.get("identifier", "")
                    title = doc.get("title", "Traccia sconosciuta")
                    artist = doc.get("creator", "")

                    if identifier:
                        # URL diretto al primo file MP3
                        mp3_url = f"https://archive.org/download/{identifier}/{identifier}.mp3"
                        tracks.append({
                            "url": mp3_url,
                            "title": title,
                            "artist": artist if isinstance(artist, str) else ", ".join(artist) if artist else "",
                            "format": "mp3",
                            "direct": True,
                            "source": "archive.org"
                        })

                return tracks

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore Archive.org: {e}")
        return []


async def search_freemusicarchive(query: str, num_results: int = 10) -> list:
    """Cerca su Free Music Archive"""
    try:
        # FMA ha un'API pubblica
        url = "https://freemusicarchive.org/api/get/tracks.json"
        params = {
            "api_key": "TESTREQUEST",  # Chiave pubblica per test
            "search": query,
            "limit": num_results
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=HEADERS, timeout=10) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                tracks = []

                for track in data.get("dataset", []):
                    if track.get("track_file"):
                        tracks.append({
                            "url": track["track_file"],
                            "title": track.get("track_title", "Traccia"),
                            "artist": track.get("artist_name", ""),
                            "format": "mp3",
                            "direct": True,
                            "source": "freemusicarchive"
                        })

                return tracks

    except Exception as e:
        logger.bind(tag=TAG).debug(f"FMA non disponibile: {e}")
        return []


def get_device_id(conn) -> str:
    if hasattr(conn, 'device_id') and conn.device_id:
        return conn.device_id
    return str(id(conn))


# ============ FUNCTION DESCRIPTION ============

CERCA_MUSICA_WEB_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "cerca_musica_web",
        "description": (
            "Cerca e riproduci musica/MP3 dal web. Cerca su archivi musicali gratuiti. "
            "Usare quando: 'cerca musica', 'trova una canzone', 'metti musica', "
            "'suona', 'play musica', 'cerca mp3', 'fammi sentire', 'riproduci', "
            "'musica di sottofondo', 'prossima canzone', 'canzone precedente', "
            "'ferma musica', 'stop musica', 'pausa'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Cosa cercare (artista, canzone, genere: jazz, rock, classica, ambient)"
                },
                "azione": {
                    "type": "string",
                    "enum": ["cerca", "play", "stop", "prossima", "precedente", "stato"],
                    "description": "cerca=ricerca, play=riproduci, stop=ferma, prossima/precedente=naviga"
                },
                "fonte": {
                    "type": "string",
                    "enum": ["auto", "archive", "web"],
                    "description": "auto=tutte le fonti, archive=Archive.org, web=ricerca web"
                }
            },
            "required": ["azione"]
        }
    }
}


@register_function("cerca_musica_web", CERCA_MUSICA_WEB_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def cerca_musica_web(conn, query: str = None, azione: str = "cerca", fonte: str = "auto"):
    """Cerca e riproduci musica dal web"""

    device_id = get_device_id(conn)

    # === STOP ===
    if azione == "stop":
        if device_id in MUSIC_SESSIONS:
            MUSIC_SESSIONS[device_id].stop()
            del MUSIC_SESSIONS[device_id]
            return ActionResponse(
                action=Action.RESPONSE,
                result="🎵 Musica fermata",
                response="Ho fermato la musica."
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Nessuna musica in riproduzione",
            response="Non c'è musica in riproduzione."
        )

    # === PROSSIMA ===
    if azione == "prossima":
        if device_id not in MUSIC_SESSIONS:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna playlist attiva",
                response="Non c'è nessuna musica. Dimmi cosa cercare."
            )

        session = MUSIC_SESSIONS[device_id]
        if session.next_track():
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🎵 {session.get_status()}",
                response=f"Prossima traccia: {session.tracks[session.current_index].get('title', 'Traccia')}"
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Fine playlist",
            response="Questa era l'ultima traccia. Vuoi cercare altra musica?"
        )

    # === PRECEDENTE ===
    if azione == "precedente":
        if device_id not in MUSIC_SESSIONS:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna playlist attiva",
                response="Non c'è nessuna musica."
            )

        session = MUSIC_SESSIONS[device_id]
        if session.prev_track():
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🎵 {session.get_status()}",
                response=f"Traccia precedente: {session.tracks[session.current_index].get('title', 'Traccia')}"
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Prima traccia",
            response="Questa è la prima traccia."
        )

    # === STATO ===
    if azione == "stato":
        if device_id in MUSIC_SESSIONS:
            session = MUSIC_SESSIONS[device_id]
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🎵 {session.get_status()}",
                response=session.get_status()
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Nessuna musica",
            response="Non c'è musica in riproduzione."
        )

    # === CERCA / PLAY ===
    if azione in ["cerca", "play"]:
        if not query:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Cosa vuoi ascoltare?",
                response="Che musica vuoi ascoltare? Dimmi un genere o un artista."
            )

        # Ferma sessione precedente
        if device_id in MUSIC_SESSIONS:
            MUSIC_SESSIONS[device_id].stop()

        # Cerca musica
        tracks = []

        import asyncio
        try:
            loop = asyncio.get_event_loop()
            run_async = lambda coro: (
                asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=15)
                if loop.is_running()
                else asyncio.run(coro)
            )
        except:
            run_async = lambda coro: asyncio.run(coro)

        # Cerca su fonti diverse
        if fonte in ["auto", "archive"]:
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, search_archive_org(query, 5))
                    archive_tracks = future.result(timeout=10)
                    tracks.extend(archive_tracks)
            except Exception as e:
                logger.bind(tag=TAG).debug(f"Archive.org: {e}")

        if fonte in ["auto", "web"] and len(tracks) < 5:
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, search_music_duckduckgo(query, 5))
                    web_tracks = future.result(timeout=10)
                    tracks.extend(web_tracks)
            except Exception as e:
                logger.bind(tag=TAG).debug(f"Web search: {e}")

        # Filtra solo tracce dirette
        direct_tracks = [t for t in tracks if t.get("direct", False)]

        if not direct_tracks:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Nessuna musica trovata per: {query}",
                response=f"Non ho trovato musica per {query}. Prova con jazz, classica, rock, o un altro genere."
            )

        # Crea sessione
        session = MusicSession(device_id, conn, direct_tracks, query)
        MUSIC_SESSIONS[device_id] = session

        # Avvia riproduzione
        session.play_current()

        first_track = direct_tracks[0]
        artist = first_track.get('artist', '')
        artist_text = f" di {artist}" if artist else ""

        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🎵 Trovate {len(direct_tracks)} tracce - Play: {first_track.get('title', 'Traccia')}",
            response=f"Ho trovato {len(direct_tracks)} tracce per {query}. Ora suona: {first_track.get('title', 'Traccia')}{artist_text}. Dimmi prossima per cambiare."
        )

    return ActionResponse(
        action=Action.RESPONSE,
        result="Azione non riconosciuta",
        response="Non ho capito. Dimmi: cerca musica jazz, oppure prossima canzone, o ferma musica."
    )
