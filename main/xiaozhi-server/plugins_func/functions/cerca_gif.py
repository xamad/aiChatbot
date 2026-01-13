"""
Cerca GIF Plugin - Cerca e mostra GIF animate da Giphy sul display ESP32
Invia i frame come sequenza JPEG per compatibilità massima
"""

import io
import json
import base64
import asyncio
import aiohttp
import threading
import time
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Giphy API (chiave pubblica beta)
GIPHY_API_KEY = "dc6zaTOxFJmzC"
GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"
GIPHY_TRENDING_URL = "https://api.giphy.com/v1/gifs/trending"

DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 160
GIF_DISPLAY_TIME = 10

GIF_SESSIONS = {}


class GifSession:
    """Gestisce una sessione di visualizzazione GIF"""

    def __init__(self, device_id: str, conn, gifs: list, query: str):
        self.device_id = device_id
        self.conn = conn
        self.gifs = gifs
        self.query = query
        self.current_index = 0
        self.slideshow_active = False
        self.slideshow_thread = None

    def start_slideshow(self, interval: int = GIF_DISPLAY_TIME):
        self.slideshow_active = True
        self.slideshow_thread = threading.Thread(
            target=self._slideshow_loop, args=(interval,)
        )
        self.slideshow_thread.daemon = True
        self.slideshow_thread.start()

    def stop_slideshow(self):
        self.slideshow_active = False
        if self.slideshow_thread:
            self.slideshow_thread.join(timeout=2)

    def _slideshow_loop(self, interval: int):
        while self.slideshow_active and self.current_index < len(self.gifs):
            self.show_current()
            time.sleep(interval)
            self.current_index += 1
        self.slideshow_active = False

    def show_current(self):
        if self.current_index >= len(self.gifs):
            return False

        gif_info = self.gifs[self.current_index]
        try:
            import requests
            from PIL import Image, ImageSequence

            url = gif_info.get('small_url') or gif_info.get('url')
            response = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0'
            })

            if response.status_code != 200:
                return False

            gif = Image.open(io.BytesIO(response.content))

            frames = []
            durations = []

            try:
                for frame in ImageSequence.Iterator(gif):
                    frame_rgb = frame.convert('RGB')
                    frame_rgb.thumbnail((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.Resampling.LANCZOS)

                    final_frame = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
                    offset = ((DISPLAY_WIDTH - frame_rgb.width) // 2,
                              (DISPLAY_HEIGHT - frame_rgb.height) // 2)
                    final_frame.paste(frame_rgb, offset)

                    buffer = io.BytesIO()
                    final_frame.save(buffer, format='JPEG', quality=80)
                    frames.append(buffer.getvalue())
                    durations.append(gif.info.get('duration', 100))

            except Exception as e:
                # Fallback singolo frame
                frame_rgb = gif.convert('RGB')
                frame_rgb.thumbnail((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.Resampling.LANCZOS)
                final_frame = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
                offset = ((DISPLAY_WIDTH - frame_rgb.width) // 2,
                          (DISPLAY_HEIGHT - frame_rgb.height) // 2)
                final_frame.paste(frame_rgb, offset)
                buffer = io.BytesIO()
                final_frame.save(buffer, format='JPEG', quality=80)
                frames.append(buffer.getvalue())
                durations.append(100)

            self._send_gif(frames, durations, gif_info.get('title', ''))
            return True

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore GIF: {e}")
            return False

    def _send_gif(self, frames: list, durations: list, title: str):
        try:
            frames_b64 = [base64.b64encode(f).decode('utf-8') for f in frames]

            message = {
                "type": "gif",
                "format": "jpeg_frames",
                "width": DISPLAY_WIDTH,
                "height": DISPLAY_HEIGHT,
                "frames": frames_b64,
                "durations": durations,
                "frame_count": len(frames),
                "title": title,
                "index": self.current_index + 1,
                "total": len(self.gifs)
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
            logger.bind(tag=TAG).error(f"Errore invio GIF: {e}")

    def next_gif(self) -> bool:
        if self.current_index < len(self.gifs) - 1:
            self.current_index += 1
            return self.show_current()
        return False

    def prev_gif(self) -> bool:
        if self.current_index > 0:
            self.current_index -= 1
            return self.show_current()
        return False

    def get_status(self) -> str:
        return f"GIF {self.current_index + 1} di {len(self.gifs)}"


async def search_giphy(query: str, num_results: int = 10) -> list:
    try:
        params = {
            "api_key": GIPHY_API_KEY,
            "q": query,
            "limit": num_results,
            "rating": "g",
            "lang": "it"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(GIPHY_SEARCH_URL, params=params) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                results = []

                for gif in data.get("data", []):
                    images = gif.get("images", {})
                    small = images.get("fixed_width_small", {})
                    original = images.get("original", {})

                    results.append({
                        "url": original.get("url", ""),
                        "small_url": small.get("url", ""),
                        "title": gif.get("title", "")
                    })

                return results

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore Giphy: {e}")
        return []


async def get_trending_giphy(num_results: int = 10) -> list:
    try:
        params = {
            "api_key": GIPHY_API_KEY,
            "limit": num_results,
            "rating": "g"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(GIPHY_TRENDING_URL, params=params) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                results = []

                for gif in data.get("data", []):
                    images = gif.get("images", {})
                    small = images.get("fixed_width_small", {})
                    original = images.get("original", {})

                    results.append({
                        "url": original.get("url", ""),
                        "small_url": small.get("url", ""),
                        "title": gif.get("title", "")
                    })

                return results

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore trending: {e}")
        return []


def get_device_id(conn) -> str:
    if hasattr(conn, 'device_id') and conn.device_id:
        return conn.device_id
    return str(id(conn))


CERCA_GIF_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "cerca_gif",
        "description": (
            "ATTIVARE SEMPRE quando l'utente vuole vedere GIF animate sul display. "
            "TRIGGER ESATTI: 'cerca gif', 'mostrami gif', 'gif di', 'animazione di', "
            "'gif divertenti', 'gif animate', 'gif gatti', 'cerca una gif', "
            "'gif trending', 'gif popolari', 'mostra gif'. "
            "NAVIGAZIONE: 'prossima gif', 'gif successiva', 'gif precedente', "
            "'ferma gif', 'stop gif'. "
            "ESEMPIO: Utente dice 'cerca gif di gatti' → azione='cerca', query='gatti'. "
            "Per GIF popolari: 'mostra gif popolari' → azione='trending'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Il soggetto da cercare. Es: 'cerca gif di cani' → query='cani'"
                },
                "azione": {
                    "type": "string",
                    "enum": ["cerca", "trending", "prossima", "precedente", "ferma"],
                    "description": "cerca=nuova ricerca, trending=gif popolari del momento, prossima/precedente=naviga, ferma=stop"
                },
                "slideshow": {
                    "type": "boolean",
                    "description": "Avvia slideshow automatico (default: true)"
                }
            },
            "required": ["azione"]
        }
    }
}


@register_function("cerca_gif", CERCA_GIF_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def cerca_gif(conn, query: str = None, azione: str = "cerca", slideshow: bool = True):
    """Cerca e mostra GIF animate"""

    device_id = get_device_id(conn)

    if azione == "prossima":
        if device_id not in GIF_SESSIONS:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna GIF attiva",
                response="Non c'è nessuna ricerca GIF attiva."
            )

        session = GIF_SESSIONS[device_id]
        session.stop_slideshow()

        if session.next_gif():
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🎬 {session.get_status()}",
                response=f"Ecco la prossima. {session.get_status()}"
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Ultima GIF",
            response="Questa è l'ultima GIF."
        )

    if azione == "precedente":
        if device_id not in GIF_SESSIONS:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna GIF attiva",
                response="Non c'è nessuna ricerca GIF attiva."
            )

        session = GIF_SESSIONS[device_id]
        session.stop_slideshow()

        if session.prev_gif():
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🎬 {session.get_status()}",
                response=f"Ecco la precedente. {session.get_status()}"
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Prima GIF",
            response="Questa è la prima GIF."
        )

    if azione == "ferma":
        if device_id in GIF_SESSIONS:
            GIF_SESSIONS[device_id].stop_slideshow()
            return ActionResponse(
                action=Action.RESPONSE,
                result="GIF fermate",
                response="Ho fermato le GIF."
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Nessuna GIF attiva",
            response="Non ci sono GIF in riproduzione."
        )

    if azione == "trending":
        if device_id in GIF_SESSIONS:
            GIF_SESSIONS[device_id].stop_slideshow()

        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_trending_giphy(10))
                gifs = future.result(timeout=15)
        except:
            gifs = []

        if not gifs:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Errore trending",
                response="Non riesco a caricare le GIF del momento."
            )

        session = GifSession(device_id, conn, gifs, "trending")
        GIF_SESSIONS[device_id] = session
        session.show_current()

        if slideshow:
            session.start_slideshow()

        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🎬 GIF Trending - {len(gifs)} GIF",
            response=f"Ecco le GIF più popolari! Ne ho trovate {len(gifs)}."
        )

    if azione == "cerca":
        if not query:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Cosa cercare?",
                response="Che GIF vuoi vedere? Dimmi: cerca gif di gatti."
            )

        if device_id in GIF_SESSIONS:
            GIF_SESSIONS[device_id].stop_slideshow()

        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, search_giphy(query, 10))
                gifs = future.result(timeout=15)
        except:
            gifs = []

        if not gifs:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Nessuna GIF per: {query}",
                response=f"Non ho trovato GIF per {query}."
            )

        session = GifSession(device_id, conn, gifs, query)
        GIF_SESSIONS[device_id] = session
        session.show_current()

        if slideshow:
            session.start_slideshow()

        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🎬 Trovate {len(gifs)} GIF di {query}",
            response=f"Ho trovato {len(gifs)} GIF di {query}!"
        )

    return ActionResponse(
        action=Action.RESPONSE,
        result="Azione non riconosciuta",
        response="Dimmi: cerca gif di gatti, oppure gif trending."
    )
