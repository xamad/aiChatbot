"""
Connection Registry - Gestisce le connessioni attive per device_id
Permette di inviare messaggi proattivi ai dispositivi connessi
"""

import asyncio
from typing import Dict, Optional, Any
from config.logger import setup_logging

TAG = __name__

class ConnectionRegistry:
    """Singleton registry per tracciare connessioni attive"""
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = setup_logging()
        self._connections: Dict[str, Any] = {}  # device_id -> ConnectionHandler
        self._lock = asyncio.Lock()

    async def register(self, device_id: str, connection) -> None:
        """Registra una connessione attiva"""
        async with self._lock:
            self._connections[device_id] = connection
            self.logger.bind(tag=TAG).info(f"Connessione registrata: {device_id}")

    async def unregister(self, device_id: str) -> None:
        """Rimuove una connessione"""
        async with self._lock:
            if device_id in self._connections:
                del self._connections[device_id]
                self.logger.bind(tag=TAG).info(f"Connessione rimossa: {device_id}")

    async def get_connection(self, device_id: str) -> Optional[Any]:
        """Ottiene la connessione per un device_id"""
        async with self._lock:
            return self._connections.get(device_id)

    async def get_all_connections(self) -> Dict[str, Any]:
        """Ottiene tutte le connessioni attive"""
        async with self._lock:
            return dict(self._connections)

    async def is_connected(self, device_id: str) -> bool:
        """Verifica se un device è connesso"""
        async with self._lock:
            return device_id in self._connections

    async def send_message_to_device(self, device_id: str, message: str) -> bool:
        """
        Invia un messaggio TTS a un dispositivo specifico.
        Ritorna True se il messaggio è stato inviato, False altrimenti.
        """
        conn = await self.get_connection(device_id)
        if conn is None:
            self.logger.bind(tag=TAG).warning(f"Device {device_id} non connesso")
            return False

        try:
            # Usa il sistema TTS per inviare il messaggio
            from core.handle.sendAudioHandle import send_tts_message
            from core.providers.tts.dto.dto import ContentType

            # Invia messaggio come se fosse una risposta del chatbot
            conn.tts.tts_one_sentence(conn, ContentType.TEXT, content_detail=message)
            self.logger.bind(tag=TAG).info(f"Messaggio inviato a {device_id}: {message[:50]}...")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Errore invio messaggio a {device_id}: {e}")
            return False


# Singleton instance
_registry: Optional[ConnectionRegistry] = None

def get_connection_registry() -> ConnectionRegistry:
    """Ottiene l'istanza singleton del registry"""
    global _registry
    if _registry is None:
        _registry = ConnectionRegistry()
    return _registry
