"""
Reminder Scheduler - Gestisce promemoria programmati e li invia ai dispositivi
Controlla ogni minuto se ci sono promemoria da inviare
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from config.logger import setup_logging
from core.connection_registry import get_connection_registry

TAG = __name__

# Directory per salvare i promemoria (path dentro il container Docker)
REMINDERS_DIR = Path("/opt/xiaozhi-esp32-server/data/reminders")


class ReminderScheduler:
    """Scheduler per gestire e inviare promemoria programmati"""
    _instance = None

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
        self._running = False
        self._task: Optional[asyncio.Task] = None
        REMINDERS_DIR.mkdir(parents=True, exist_ok=True)

    async def start(self):
        """Avvia lo scheduler"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        self.logger.bind(tag=TAG).info("Reminder Scheduler avviato")

    async def stop(self):
        """Ferma lo scheduler"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.bind(tag=TAG).info("Reminder Scheduler fermato")

    async def _scheduler_loop(self):
        """Loop principale che controlla i promemoria ogni minuto"""
        while self._running:
            try:
                await self._check_reminders()
                await asyncio.sleep(60)  # Controlla ogni minuto
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.bind(tag=TAG).error(f"Errore scheduler: {e}")
                await asyncio.sleep(60)

    async def _check_reminders(self):
        """Controlla e invia i promemoria scaduti"""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")

        # Controlla tutti i file di promemoria
        for reminder_file in REMINDERS_DIR.glob("*.json"):
            try:
                device_id = reminder_file.stem
                reminders = self._load_reminders(device_id)

                reminders_to_send = []
                remaining_reminders = []

                for reminder in reminders:
                    reminder_time = reminder.get("time", "")
                    reminder_date = reminder.get("date", "")
                    repeat = reminder.get("repeat", False)

                    # Verifica se è ora di inviare
                    should_send = False

                    if reminder_time == current_time:
                        if not reminder_date:  # Nessuna data specifica
                            should_send = True
                        elif reminder_date == current_date:
                            should_send = True

                    if should_send:
                        reminders_to_send.append(reminder)
                        if repeat:
                            remaining_reminders.append(reminder)  # Mantieni se ripetitivo
                    else:
                        # Mantieni promemoria futuri
                        if reminder_date:
                            if reminder_date >= current_date:
                                remaining_reminders.append(reminder)
                        else:
                            remaining_reminders.append(reminder)

                # Invia promemoria
                for reminder in reminders_to_send:
                    await self._send_reminder(device_id, reminder)

                # Salva promemoria rimanenti
                if len(remaining_reminders) != len(reminders):
                    self._save_reminders(device_id, remaining_reminders)

            except Exception as e:
                self.logger.bind(tag=TAG).error(f"Errore check promemoria {reminder_file}: {e}")

    async def _send_reminder(self, device_id: str, reminder: Dict):
        """Invia un promemoria a un dispositivo"""
        message = reminder.get("message", "Hai un promemoria!")
        tipo = reminder.get("type", "promemoria")

        # Costruisci messaggio vocale
        if tipo == "farmaco":
            testo = f"Attenzione! È ora di prendere le medicine. {message}"
        elif tipo == "appuntamento":
            testo = f"Promemoria! Hai un appuntamento. {message}"
        elif tipo == "sveglia":
            testo = f"Buongiorno! È ora di svegliarsi. {message}"
        else:
            testo = f"Promemoria! {message}"

        # Invia tramite registry
        registry = get_connection_registry()
        success = await registry.send_message_to_device(device_id, testo)

        if success:
            self.logger.bind(tag=TAG).info(f"Promemoria inviato a {device_id}: {message[:30]}...")
        else:
            self.logger.bind(tag=TAG).warning(f"Device {device_id} non connesso per promemoria")

    def _load_reminders(self, device_id: str) -> List[Dict]:
        """Carica i promemoria di un dispositivo"""
        file_path = REMINDERS_DIR / f"{device_id}.json"
        if not file_path.exists():
            return []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save_reminders(self, device_id: str, reminders: List[Dict]):
        """Salva i promemoria di un dispositivo"""
        file_path = REMINDERS_DIR / f"{device_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(reminders, f, ensure_ascii=False, indent=2)

    def add_reminder(self, device_id: str, reminder: Dict) -> bool:
        """
        Aggiunge un promemoria per un dispositivo.

        Args:
            device_id: ID del dispositivo
            reminder: Dict con campi:
                - message: testo del promemoria
                - time: orario "HH:MM"
                - date: data "YYYY-MM-DD" (opzionale)
                - type: tipo (promemoria, farmaco, appuntamento, sveglia)
                - repeat: bool - se ripetere ogni giorno
        """
        try:
            reminders = self._load_reminders(device_id)
            reminder["created"] = datetime.now().isoformat()
            reminders.append(reminder)
            self._save_reminders(device_id, reminders)
            self.logger.bind(tag=TAG).info(f"Promemoria aggiunto per {device_id}: {reminder}")
            return True
        except Exception as e:
            self.logger.bind(tag=TAG).error(f"Errore aggiunta promemoria: {e}")
            return False

    def get_reminders(self, device_id: str) -> List[Dict]:
        """Ottiene tutti i promemoria di un dispositivo"""
        return self._load_reminders(device_id)

    def remove_reminder(self, device_id: str, index: int) -> bool:
        """Rimuove un promemoria per indice"""
        try:
            reminders = self._load_reminders(device_id)
            if 0 <= index < len(reminders):
                del reminders[index]
                self._save_reminders(device_id, reminders)
                return True
            return False
        except Exception:
            return False

    def clear_reminders(self, device_id: str) -> bool:
        """Cancella tutti i promemoria di un dispositivo"""
        try:
            file_path = REMINDERS_DIR / f"{device_id}.json"
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception:
            return False


# Singleton instance
_scheduler: Optional[ReminderScheduler] = None

def get_reminder_scheduler() -> ReminderScheduler:
    """Ottiene l'istanza singleton dello scheduler"""
    global _scheduler
    if _scheduler is None:
        _scheduler = ReminderScheduler()
    return _scheduler
