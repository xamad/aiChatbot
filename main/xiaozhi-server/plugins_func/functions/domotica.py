"""
Domotica Plugin - Controllo dispositivi Tuya via Cloud API
Funziona da remoto (VPS) tramite le API cloud di Tuya

SETUP RICHIESTO:
1. Vai su https://iot.tuya.com e crea un account
2. Crea un progetto Cloud (Cloud > Development > Create)
3. Seleziona "Smart Home" e la tua regione (EU per Italia)
4. Vai su Devices > Link Tuya App Account
5. Scansiona il QR code con l'app Smart Life/Tuya
6. Copia Access ID e Access Secret nel file di configurazione
"""

import os
import json
import time
import hmac
import hashlib
import asyncio
from typing import Optional, Dict, List, Any, Tuple
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Path configurazione (dentro il container)
CONFIG_FILE = "/opt/xiaozhi-esp32-server/data/domotica_config.json"

# Cache dispositivi per ridurre chiamate API
_devices_cache: List[Dict] = []
_cache_timestamp = 0
CACHE_DURATION = 300  # 5 minuti


def load_config() -> dict:
    """Carica configurazione API Tuya"""
    default_config = {
        "tuya_cloud": {
            "access_id": "",      # Da iot.tuya.com > Cloud Project
            "access_secret": "",  # Da iot.tuya.com > Cloud Project
            "region": "eu",       # eu, us, cn, in
            "uid": ""             # User ID (opzionale, si trova automaticamente)
        },
        "device_aliases": {
            # Alias opzionali per nomi più semplici
            # "salotto": "device_id_xxx",
            # "acquario": "device_id_yyy"
        }
    }

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento config: {e}")

    # Crea file di esempio
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        logger.bind(tag=TAG).info(f"Creato file config: {CONFIG_FILE}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore creazione config: {e}")

    return default_config


def get_tuya_api_url(region: str) -> str:
    """Restituisce URL API per la regione"""
    regions = {
        "eu": "https://openapi.tuyaeu.com",
        "us": "https://openapi.tuyaus.com",
        "cn": "https://openapi.tuyacn.com",
        "in": "https://openapi.tuyain.com"
    }
    return regions.get(region, regions["eu"])


class TuyaCloudAPI:
    """Client per Tuya Cloud API"""

    def __init__(self, access_id: str, access_secret: str, region: str = "eu"):
        self.access_id = access_id
        self.access_secret = access_secret
        self.base_url = get_tuya_api_url(region)
        self.token = None
        self.token_expire = 0

    def _sign_request(self, method: str, path: str, body: str = "", token: str = "") -> dict:
        """Genera signature per la richiesta (nuovo metodo con nonce)"""
        import uuid

        t = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())  # UUID per prevenire replay attacks

        # Stringa da firmare
        content_hash = hashlib.sha256(body.encode()).hexdigest()
        string_to_sign = f"{method}\n{content_hash}\n\n{path}"

        # Nuova formula: client_id + [access_token] + t + nonce + stringToSign
        if token:
            sign_str = self.access_id + token + t + nonce + string_to_sign
        else:
            sign_str = self.access_id + t + nonce + string_to_sign

        # HMAC-SHA256
        sign = hmac.new(
            self.access_secret.encode(),
            sign_str.encode(),
            hashlib.sha256
        ).hexdigest().upper()

        headers = {
            "client_id": self.access_id,
            "sign": sign,
            "t": t,
            "nonce": nonce,
            "sign_method": "HMAC-SHA256",
            "Content-Type": "application/json"
        }

        if token:
            headers["access_token"] = token

        return headers

    async def _request(self, method: str, path: str, body: dict = None) -> dict:
        """Esegue richiesta HTTP alle API Tuya (forza IPv4)"""
        import urllib.request
        import urllib.error
        import socket

        # Forza IPv4 per Tuya (non supporta IPv6 nella whitelist)
        orig_getaddrinfo = socket.getaddrinfo
        def getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
            return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        body_str = json.dumps(body) if body else ""
        token = self.token if self.token and time.time() < self.token_expire else ""

        headers = self._sign_request(method, path, body_str, token)
        url = self.base_url + path

        try:
            socket.getaddrinfo = getaddrinfo_ipv4  # Forza IPv4

            req = urllib.request.Request(
                url,
                data=body_str.encode() if body_str else None,
                headers=headers,
                method=method
            )

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: urllib.request.urlopen(req, timeout=10)
            )

            result = json.loads(response.read().decode())
            return result

        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            logger.bind(tag=TAG).error(f"HTTP Error {e.code}: {error_body}")
            return {"success": False, "msg": f"HTTP {e.code}"}
        except Exception as e:
            logger.bind(tag=TAG).error(f"Request error: {e}")
            return {"success": False, "msg": str(e)}
        finally:
            socket.getaddrinfo = orig_getaddrinfo  # Ripristina

    async def get_token(self) -> bool:
        """Ottiene access token"""
        if self.token and time.time() < self.token_expire:
            return True

        result = await self._request("GET", "/v1.0/token?grant_type=1")

        if result.get("success"):
            data = result.get("result", {})
            self.token = data.get("access_token")
            expire_time = data.get("expire_time", 7200)
            self.token_expire = time.time() + expire_time - 60
            logger.bind(tag=TAG).info("Token Tuya ottenuto")
            return True

        logger.bind(tag=TAG).error(f"Errore token: {result.get('msg')}")
        return False

    async def get_user_devices(self, uid: str = None) -> List[Dict]:
        """Ottiene lista dispositivi dell'utente"""
        if not await self.get_token():
            return []

        # Prima ottieni l'UID se non specificato
        if not uid:
            # Cerca tra gli utenti collegati
            result = await self._request("GET", "/v1.0/users")
            if result.get("success"):
                users = result.get("result", {}).get("list", [])
                if users:
                    uid = users[0].get("uid")

        if not uid:
            # Prova a ottenere dispositivi direttamente dal progetto
            result = await self._request("GET", "/v1.0/devices")
            if result.get("success"):
                return result.get("result", {}).get("list", [])
            return []

        # Ottieni dispositivi dell'utente
        result = await self._request("GET", f"/v1.0/users/{uid}/devices")

        if result.get("success"):
            return result.get("result", [])

        return []

    async def get_device_status(self, device_id: str) -> Dict:
        """Ottiene stato del dispositivo"""
        if not await self.get_token():
            return {}

        result = await self._request("GET", f"/v1.0/devices/{device_id}/status")

        if result.get("success"):
            return result.get("result", [])

        return {}

    async def send_command(self, device_id: str, commands: List[Dict]) -> bool:
        """Invia comando al dispositivo"""
        if not await self.get_token():
            return False

        body = {"commands": commands}
        result = await self._request("POST", f"/v1.0/devices/{device_id}/commands", body)

        return result.get("success", False)

    async def turn_on(self, device_id: str) -> bool:
        """Accende dispositivo"""
        return await self.send_command(device_id, [{"code": "switch_1", "value": True}])

    async def turn_off(self, device_id: str) -> bool:
        """Spegne dispositivo"""
        return await self.send_command(device_id, [{"code": "switch_1", "value": False}])


# Istanza globale API
_tuya_api: Optional[TuyaCloudAPI] = None


def get_tuya_api(config: dict) -> Optional[TuyaCloudAPI]:
    """Ottiene istanza API Tuya"""
    global _tuya_api

    tuya_config = config.get("tuya_cloud", {})
    access_id = tuya_config.get("access_id", "")
    access_secret = tuya_config.get("access_secret", "")
    region = tuya_config.get("region", "eu")

    if not access_id or not access_secret:
        return None

    if _tuya_api is None:
        _tuya_api = TuyaCloudAPI(access_id, access_secret, region)

    return _tuya_api


async def get_devices(config: dict) -> List[Dict]:
    """Ottiene lista dispositivi (con cache)"""
    global _devices_cache, _cache_timestamp

    if _devices_cache and time.time() - _cache_timestamp < CACHE_DURATION:
        return _devices_cache

    api = get_tuya_api(config)
    if not api:
        return []

    uid = config.get("tuya_cloud", {}).get("uid", "")
    devices = await api.get_user_devices(uid)

    _devices_cache = devices
    _cache_timestamp = time.time()

    return devices


def find_device(query: str, devices: List[Dict], aliases: Dict[str, str]) -> Optional[Dict]:
    """Trova dispositivo per nome"""
    if not query:
        return None

    query = query.lower().strip()

    # Check alias
    if query in aliases:
        device_id = aliases[query]
        for dev in devices:
            if dev.get("id") == device_id:
                return dev

    # Match esatto nome
    for dev in devices:
        name = dev.get("name", "").lower()
        if query == name:
            return dev

    # Match parziale
    for dev in devices:
        name = dev.get("name", "").lower()
        if query in name or name in query:
            return dev

    # Match parole singole
    query_words = query.split()
    for dev in devices:
        name = dev.get("name", "").lower()
        for word in query_words:
            if len(word) > 2 and word in name:
                return dev

    return None


DOMOTICA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "domotica",
        "description": (
            "控制智能家居设备 / Controlla dispositivi smart home Tuya (luci, prese, interruttori). "
            "Use when: 'accendi la luce', 'spegni la presa', 'accendi salotto', "
            "'spegni acquario', 'luce camera on', 'stato luce cucina', "
            "'quali dispositivi hai', 'elenco dispositivi', 'lista luci', "
            "'accendi tutto', 'spegni tutte le luci'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Nome del dispositivo (es: luce salotto, presa acquario, camera, tutto)",
                },
                "action": {
                    "type": "string",
                    "description": "Azione: on (accendi), off (spegni), status (stato), list (elenco)",
                    "enum": ["on", "off", "status", "list"]
                },
            },
            "required": ["action"],
        },
    },
}


@register_function("domotica", DOMOTICA_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def domotica(conn, action: str = "list", device: str = None):
    """Gestisce dispositivi smart home via Tuya Cloud"""
    logger.bind(tag=TAG).info(f"Domotica: action={action}, device={device}")

    config = load_config()

    # Verifica configurazione
    tuya_config = config.get("tuya_cloud", {})
    if not tuya_config.get("access_id") or not tuya_config.get("access_secret"):
        return ActionResponse(
            Action.REQLLM,
            "Domotica non configurata. Serve configurare le API Tuya Cloud nel file domotica_config.json. "
            "Vai su iot.tuya.com, crea un progetto e inserisci access_id e access_secret.",
            None
        )

    # Esegui in background
    conn.loop.create_task(execute_domotica_action(conn, config, action, device))

    if action == "list":
        return ActionResponse(Action.REQLLM, "Cerco i dispositivi...", None)

    if device:
        action_text = {"on": "Accendo", "off": "Spengo", "status": "Controllo"}
        return ActionResponse(Action.REQLLM, f"{action_text.get(action, 'Controllo')} {device}...", None)

    return ActionResponse(Action.REQLLM, "Eseguo...", None)


async def execute_domotica_action(conn, config: dict, action: str, device_query: str):
    """Esegue l'azione domotica"""
    from core.handle.sendAudioHandle import send_stt_message

    try:
        api = get_tuya_api(config)
        if not api:
            await send_stt_message(conn, "API Tuya non configurate correttamente")
            return

        devices = await get_devices(config)

        if not devices:
            await send_stt_message(conn, "Nessun dispositivo trovato. Verifica la configurazione Tuya.")
            return

        # Lista dispositivi
        if action == "list":
            if len(devices) == 0:
                await send_stt_message(conn, "Non ho trovato dispositivi collegati")
                return

            result = "Ho trovato questi dispositivi: "
            names = [d.get("name", "Sconosciuto") for d in devices[:10]]
            result += ", ".join(names)
            if len(devices) > 10:
                result += f", e altri {len(devices) - 10}"
            await send_stt_message(conn, result)
            return

        # Azioni che richiedono dispositivo
        if not device_query:
            await send_stt_message(conn, "Quale dispositivo vuoi controllare?")
            return

        # Trova dispositivo
        aliases = config.get("device_aliases", {})
        found = find_device(device_query, devices, aliases)

        if not found:
            names = [d.get("name", "") for d in devices[:5]]
            await send_stt_message(conn, f"Non ho trovato {device_query}. Ho: {', '.join(names)}")
            return

        device_id = found.get("id")
        device_name = found.get("name", "Dispositivo")

        # Esegui azione
        if action == "on":
            success = await api.turn_on(device_id)
            if success:
                await send_stt_message(conn, f"{device_name} acceso")
            else:
                await send_stt_message(conn, f"Non sono riuscito ad accendere {device_name}")

        elif action == "off":
            success = await api.turn_off(device_id)
            if success:
                await send_stt_message(conn, f"{device_name} spento")
            else:
                await send_stt_message(conn, f"Non sono riuscito a spegnere {device_name}")

        elif action == "status":
            status = await api.get_device_status(device_id)
            is_on = False
            for s in status:
                if s.get("code") in ["switch_1", "switch"]:
                    is_on = s.get("value", False)
                    break
            stato = "acceso" if is_on else "spento"
            await send_stt_message(conn, f"{device_name} è {stato}")

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore domotica: {e}")
        await send_stt_message(conn, "Si è verificato un errore nel controllo dei dispositivi")
