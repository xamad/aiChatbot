"""
Cerca Immagini Plugin - Cerca e mostra immagini sul display ESP32
Ricerca immagini via DuckDuckGo, ridimensiona e invia via WebSocket
Supporta slideshow automatico e navigazione vocale
"""

import io
import re
import json
import base64
import asyncio
import aiohttp
import threading
import time
from urllib.parse import quote
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Dimensioni display
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 160

# Slideshow interval (secondi)
SLIDESHOW_INTERVAL = 8

# Sessioni attive per device
IMAGE_SESSIONS = {}


class ImageSession:
    """Gestisce una sessione di visualizzazione immagini"""

    def __init__(self, device_id: str, conn, images: list, query: str):
        self.device_id = device_id
        self.conn = conn
        self.images = images
        self.query = query
        self.current_index = 0
        self.slideshow_active = False
        self.slideshow_thread = None

    def start_slideshow(self, interval: int = SLIDESHOW_INTERVAL):
        """Avvia slideshow automatico"""
        self.slideshow_active = True
        self.slideshow_thread = threading.Thread(
            target=self._slideshow_loop,
            args=(interval,)
        )
        self.slideshow_thread.daemon = True
        self.slideshow_thread.start()

    def stop_slideshow(self):
        """Ferma slideshow"""
        self.slideshow_active = False
        if self.slideshow_thread:
            self.slideshow_thread.join(timeout=2)

    def _slideshow_loop(self, interval: int):
        """Loop slideshow"""
        while self.slideshow_active and self.current_index < len(self.images):
            self.show_current()
            time.sleep(interval)
            self.current_index += 1
        self.slideshow_active = False

    def show_current(self):
        """Mostra immagine corrente"""
        if self.current_index >= len(self.images):
            return False

        url = self.images[self.current_index]
        try:
            import requests
            from PIL import Image

            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            if response.status_code != 200:
                return False

            img = Image.open(io.BytesIO(response.content))

            if img.mode != 'RGB':
                img = img.convert('RGB')

            img.thumbnail((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.Resampling.LANCZOS)

            final_img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), (0, 0, 0))
            offset = ((DISPLAY_WIDTH - img.width) // 2, (DISPLAY_HEIGHT - img.height) // 2)
            final_img.paste(img, offset)

            buffer = io.BytesIO()
            final_img.save(buffer, format='JPEG', quality=85)
            jpeg_data = buffer.getvalue()

            self._send_image(jpeg_data)
            return True

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore elaborazione immagine: {e}")
            return False

    def _send_image(self, jpeg_data: bytes):
        """Invia immagine JPEG al device via WebSocket"""
        try:
            image_b64 = base64.b64encode(jpeg_data).decode('utf-8')

            message = {
                "type": "image",
                "format": "jpeg",
                "width": DISPLAY_WIDTH,
                "height": DISPLAY_HEIGHT,
                "data": image_b64,
                "index": self.current_index + 1,
                "total": len(self.images),
                "query": self.query
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
                    logger.bind(tag=TAG).debug(f"Invio immagine: {e}")

        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore invio immagine: {e}")

    def next_image(self) -> bool:
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            return self.show_current()
        return False

    def prev_image(self) -> bool:
        if self.current_index > 0:
            self.current_index -= 1
            return self.show_current()
        return False

    def get_status(self) -> str:
        return f"Immagine {self.current_index + 1} di {len(self.images)}"


async def search_images_duckduckgo(query: str, num_results: int = 10) -> list:
    """Cerca immagini su DuckDuckGo"""
    try:
        token_url = "https://duckduckgo.com/"
        params = {"q": query}

        async with aiohttp.ClientSession() as session:
            async with session.get(token_url, params=params) as resp:
                text = await resp.text()
                match = re.search(r'vqd=([^&"]+)', text)
                if not match:
                    return []
                vqd = match.group(1)

            search_url = "https://duckduckgo.com/i.js"
            params = {
                "q": query,
                "vqd": vqd,
                "l": "it-it",
                "o": "json",
                "f": ",,,,,",
                "p": "1"
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://duckduckgo.com/"
            }

            async with session.get(search_url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                results = data.get("results", [])

                images = []
                for r in results[:num_results]:
                    img_url = r.get("thumbnail") or r.get("image")
                    if img_url:
                        images.append(img_url)

                return images

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore ricerca immagini: {e}")
        return []


def get_device_id(conn) -> str:
    if hasattr(conn, 'device_id') and conn.device_id:
        return conn.device_id
    return str(id(conn))


CERCA_IMMAGINI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "cerca_immagini",
        "description": (
            "ATTIVARE SEMPRE quando l'utente vuole vedere immagini o foto sul display. "
            "TRIGGER ESATTI: 'cerca immagini', 'cerca foto', 'mostrami immagini', 'mostrami foto', "
            "'fammi vedere immagini', 'fammi vedere foto', 'immagini di', 'foto di', "
            "'slideshow di', 'cerca immagini di natura', 'cerca foto di animali'. "
            "NAVIGAZIONE: 'prossima immagine', 'immagine successiva', 'avanti', "
            "'immagine precedente', 'indietro', 'ferma slideshow', 'stop immagini'. "
            "ESEMPIO: Utente dice 'cerca immagini di gatti' → azione='cerca', query='gatti'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Il soggetto da cercare, estratto dalla richiesta. Es: se utente dice 'cerca immagini di natura' → query='natura'"
                },
                "azione": {
                    "type": "string",
                    "enum": ["cerca", "prossima", "precedente", "ferma", "stato"],
                    "description": "cerca=nuova ricerca immagini, prossima=mostra successiva, precedente=mostra precedente, ferma=stop slideshow"
                },
                "slideshow": {
                    "type": "boolean",
                    "description": "Avvia slideshow automatico (default: true)"
                },
                "intervallo": {
                    "type": "integer",
                    "description": "Secondi tra immagini nello slideshow (default: 8)"
                }
            },
            "required": ["azione"]
        }
    }
}


@register_function("cerca_immagini", CERCA_IMMAGINI_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def cerca_immagini(conn, query: str = None, azione: str = "cerca",
                   slideshow: bool = True, intervallo: int = SLIDESHOW_INTERVAL):
    """Cerca e mostra immagini sul display ESP32"""

    device_id = get_device_id(conn)

    # === PROSSIMA ===
    if azione == "prossima":
        if device_id not in IMAGE_SESSIONS:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna ricerca attiva",
                response="Non c'è nessuna ricerca immagini attiva."
            )

        session = IMAGE_SESSIONS[device_id]
        session.stop_slideshow()

        if session.next_image():
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🖼️ {session.get_status()}",
                response=f"Ecco la prossima. {session.get_status()}"
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Ultima immagine",
            response="Questa è l'ultima immagine."
        )

    # === PRECEDENTE ===
    if azione == "precedente":
        if device_id not in IMAGE_SESSIONS:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Nessuna ricerca attiva",
                response="Non c'è nessuna ricerca immagini attiva."
            )

        session = IMAGE_SESSIONS[device_id]
        session.stop_slideshow()

        if session.prev_image():
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🖼️ {session.get_status()}",
                response=f"Ecco la precedente. {session.get_status()}"
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Prima immagine",
            response="Questa è la prima immagine."
        )

    # === FERMA ===
    if azione == "ferma":
        if device_id in IMAGE_SESSIONS:
            IMAGE_SESSIONS[device_id].stop_slideshow()
            return ActionResponse(
                action=Action.RESPONSE,
                result="Slideshow fermato",
                response="Ho fermato lo slideshow."
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Nessuno slideshow attivo",
            response="Non c'è nessuno slideshow attivo."
        )

    # === STATO ===
    if azione == "stato":
        if device_id in IMAGE_SESSIONS:
            session = IMAGE_SESSIONS[device_id]
            stato = "in slideshow" if session.slideshow_active else "in pausa"
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🖼️ {session.get_status()} - {stato}",
                response=f"{session.get_status()}, ricerca: {session.query}"
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result="Nessuna ricerca attiva",
            response="Non c'è nessuna ricerca immagini attiva."
        )

    # === CERCA ===
    if azione == "cerca":
        if not query:
            return ActionResponse(
                action=Action.RESPONSE,
                result="Cosa vuoi cercare?",
                response="Cosa vuoi che cerchi? Dimmi: cerca immagini di gatti."
            )

        if device_id in IMAGE_SESSIONS:
            IMAGE_SESSIONS[device_id].stop_slideshow()

        # Cerca immagini
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    search_images_duckduckgo(query, 10)
                )
                images = future.result(timeout=15)
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore ricerca: {e}")
            images = []

        if not images:
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"Nessuna immagine trovata per: {query}",
                response=f"Non ho trovato immagini per {query}. Prova con un'altra ricerca."
            )

        session = ImageSession(device_id, conn, images, query)
        IMAGE_SESSIONS[device_id] = session

        session.show_current()

        if slideshow:
            session.start_slideshow(intervallo)
            return ActionResponse(
                action=Action.RESPONSE,
                result=f"🖼️ Trovate {len(images)} immagini di {query}",
                response=f"Ho trovato {len(images)} immagini di {query}. Le mostro ogni {intervallo} secondi."
            )
        return ActionResponse(
            action=Action.RESPONSE,
            result=f"🖼️ Trovate {len(images)} immagini di {query}",
            response=f"Ho trovato {len(images)} immagini di {query}. Dimmi prossima per navigare."
        )

    return ActionResponse(
        action=Action.RESPONSE,
        result="Azione non riconosciuta",
        response="Non ho capito. Dimmi: cerca immagini di gatti."
    )
