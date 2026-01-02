"""
User Memory Manager - Gestione memoria persistente utente
Ricorda conversazioni, preferenze, funzioni preferite, stato emotivo
"""

import os
import json
from datetime import datetime, timedelta
from collections import Counter
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# Path per la memoria persistente (path dentro il container Docker)
MEMORY_DIR = "/opt/xiaozhi-esp32-server/data/user_memories"
os.makedirs(MEMORY_DIR, exist_ok=True)


class UserMemory:
    """Gestisce la memoria di un singolo utente"""

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.memory_file = os.path.join(MEMORY_DIR, f"{device_id}.json")
        self.data = self._load()

    def _load(self) -> dict:
        """Carica memoria da file"""
        default = {
            "device_id": self.device_id,
            "created_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "nome_utente": None,
            "interazioni_totali": 0,
            "funzioni_usate": {},  # {funzione: count}
            "argomenti_preferiti": [],  # Lista argomenti discussi
            "conversazioni_recenti": [],  # Ultime N conversazioni
            "stati_emotivi": [],  # Storico stati emotivi
            "cose_che_piacciono": [],  # Hobbies, interessi
            "cose_che_non_piacciono": [],
            "ricordi_importanti": [],  # Cose da ricordare
            "ultima_funzione_preferita": None,
            "umore_medio": "neutro"
        }

        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    default.update(saved)
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore caricamento memoria: {e}")

        return default

    def _save(self):
        """Salva memoria su file"""
        try:
            self.data["last_seen"] = datetime.now().isoformat()
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.bind(tag=TAG).error(f"Errore salvataggio memoria: {e}")

    def registra_interazione(self, testo_utente: str, funzione: str = None, risposta: str = None):
        """Registra un'interazione"""
        self.data["interazioni_totali"] += 1

        # Registra funzione usata
        if funzione:
            if funzione not in self.data["funzioni_usate"]:
                self.data["funzioni_usate"][funzione] = 0
            self.data["funzioni_usate"][funzione] += 1
            self.data["ultima_funzione_preferita"] = funzione

        # Salva conversazione recente (max 50)
        conv = {
            "timestamp": datetime.now().isoformat(),
            "utente": testo_utente[:200],  # Limita lunghezza
            "funzione": funzione,
            "risposta": risposta[:200] if risposta else None
        }
        self.data["conversazioni_recenti"].append(conv)
        self.data["conversazioni_recenti"] = self.data["conversazioni_recenti"][-50:]

        self._save()

    def registra_stato_emotivo(self, stato: str):
        """Registra stato emotivo"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "stato": stato
        }
        self.data["stati_emotivi"].append(entry)
        self.data["stati_emotivi"] = self.data["stati_emotivi"][-20:]

        # Aggiorna umore medio
        stati_recenti = [s["stato"] for s in self.data["stati_emotivi"][-5:]]
        if "triste" in stati_recenti or "giù" in stati_recenti:
            self.data["umore_medio"] = "basso"
        elif "felice" in stati_recenti or "contento" in stati_recenti:
            self.data["umore_medio"] = "alto"
        else:
            self.data["umore_medio"] = "neutro"

        self._save()

    def aggiungi_cosa_che_piace(self, cosa: str):
        """Aggiunge qualcosa che piace all'utente"""
        if cosa not in self.data["cose_che_piacciono"]:
            self.data["cose_che_piacciono"].append(cosa)
            self.data["cose_che_piacciono"] = self.data["cose_che_piacciono"][-20:]
        self._save()

    def aggiungi_ricordo(self, ricordo: str):
        """Aggiunge un ricordo importante"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "ricordo": ricordo
        }
        self.data["ricordi_importanti"].append(entry)
        self.data["ricordi_importanti"] = self.data["ricordi_importanti"][-30:]
        self._save()

    def set_nome_utente(self, nome: str):
        """Imposta nome utente"""
        self.data["nome_utente"] = nome
        self._save()

    def get_funzioni_preferite(self, top_n: int = 5) -> list:
        """Restituisce le funzioni più usate"""
        funzioni = self.data["funzioni_usate"]
        sorted_funzioni = sorted(funzioni.items(), key=lambda x: x[1], reverse=True)
        return sorted_funzioni[:top_n]

    def get_suggerimenti_distrazione(self) -> list:
        """Genera suggerimenti basati su preferenze"""
        suggerimenti = []

        # Basati su funzioni preferite
        funzioni_pref = self.get_funzioni_preferite(3)
        for func, count in funzioni_pref:
            if func == "radio_italia":
                suggerimenti.append("Che ne dici di ascoltare un po' di radio? Ti piace!")
            elif func == "barzelletta_bambini" or func == "barzelletta_adulti":
                suggerimenti.append("Ti racconto una barzelletta per tirarti su?")
            elif func == "quiz_trivia":
                suggerimenti.append("Facciamo un quiz? Ti piacciono le sfide!")
            elif func == "osterie_goliardiche":
                suggerimenti.append("Ti canto un'osteria goliardica per farti ridere?")
            elif func == "storie_bambini":
                suggerimenti.append("Vuoi che ti racconti una bella storia?")
            elif func == "oroscopo":
                suggerimenti.append("Vuoi sapere cosa dicono le stelle oggi?")
            elif func == "meditazione":
                suggerimenti.append("Facciamo un po' di meditazione insieme?")
            elif func == "podcast_italia":
                suggerimenti.append("Ascoltiamo un podcast interessante?")

        # Basati su cose che piacciono
        for cosa in self.data["cose_che_piacciono"][:3]:
            suggerimenti.append(f"So che ti piace {cosa}. Ne parliamo?")

        return suggerimenti[:5]

    def get_riassunto_utente(self) -> str:
        """Genera riassunto dell'utente"""
        nome = self.data["nome_utente"] or "amico"
        interazioni = self.data["interazioni_totali"]
        funz_pref = self.get_funzioni_preferite(3)
        umore = self.data["umore_medio"]

        riassunto = f"Conosco {nome} da {interazioni} interazioni. "
        if funz_pref:
            riassunto += f"Le sue funzioni preferite sono: {', '.join([f[0] for f in funz_pref])}. "
        riassunto += f"Umore recente: {umore}."

        return riassunto


# Cache globale delle memorie utente
_memory_cache = {}


def get_user_memory(device_id: str) -> UserMemory:
    """Ottiene o crea memoria utente"""
    if device_id not in _memory_cache:
        _memory_cache[device_id] = UserMemory(device_id)
    return _memory_cache[device_id]


def registra_uso_funzione(device_id: str, funzione: str, testo_utente: str = None):
    """Helper per registrare uso funzione"""
    try:
        mem = get_user_memory(device_id)
        mem.registra_interazione(testo_utente or "", funzione)
    except Exception as e:
        logger.bind(tag=TAG).debug(f"Errore registrazione: {e}")
