"""
Smart Fridge Integration - Interfaccia con il sistema Smart Fridge
Permette di controllare l'inventario del frigo, vedere scadenze e gestire la lista della spesa.

Comandi supportati:
- "cosa c'è nel frigo?" / "inventario frigo"
- "cosa scade nel frigo?" / "prodotti in scadenza"
- "lista della spesa" / "cosa devo comprare?"
- "aggiungi X alla lista della spesa"
"""

import aiohttp
import asyncio
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Configurazione API Smart Fridge
FRIDGE_API_URL = "https://frigo.xamad.net/api"
FRIDGE_TIMEOUT = 10  # secondi


async def fetch_fridge_api(endpoint: str) -> dict:
    """Chiama l'API del frigo"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{FRIDGE_API_URL}/{endpoint}",
                timeout=aiohttp.ClientTimeout(total=FRIDGE_TIMEOUT),
                ssl=True
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.bind(tag=TAG).error(f"API error: {resp.status}")
                    return None
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore connessione frigo: {e}")
        return None


async def post_fridge_api(endpoint: str, data: dict) -> dict:
    """POST all'API del frigo"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FRIDGE_API_URL}/{endpoint}",
                json=data,
                timeout=aiohttp.ClientTimeout(total=FRIDGE_TIMEOUT),
                ssl=True
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.bind(tag=TAG).error(f"API POST error: {resp.status}")
                    return None
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore POST frigo: {e}")
        return None


def sync_fetch(endpoint: str) -> dict:
    """Wrapper sincrono per fetch"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, fetch_fridge_api(endpoint))
                return future.result(timeout=FRIDGE_TIMEOUT + 5)
        else:
            return asyncio.run(fetch_fridge_api(endpoint))
    except Exception as e:
        logger.bind(tag=TAG).error(f"sync_fetch error: {e}")
        return None


def sync_post(endpoint: str, data: dict) -> dict:
    """Wrapper sincrono per POST"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, post_fridge_api(endpoint, data))
                return future.result(timeout=FRIDGE_TIMEOUT + 5)
        else:
            return asyncio.run(post_fridge_api(endpoint, data))
    except Exception as e:
        logger.bind(tag=TAG).error(f"sync_post error: {e}")
        return None


SMART_FRIDGE_DESC = {
    "type": "function",
    "function": {
        "name": "smart_fridge",
        "description": (
            "Gestione inventario frigo smart. "
            "Usa quando l'utente chiede: cosa c'è nel frigo, inventario frigo, "
            "cosa scade, prodotti in scadenza, lista della spesa, cosa devo comprare, "
            "aggiungi alla lista della spesa, compra [prodotto], "
            "rimuovi/togli/cancella dalla lista della spesa, svuota lista spesa"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "azione": {
                    "type": "string",
                    "description": "Azione: inventario, scadenze, spesa, aggiungi_spesa, rimuovi_spesa, svuota_spesa",
                    "enum": ["inventario", "scadenze", "spesa", "aggiungi_spesa", "rimuovi_spesa", "svuota_spesa", "statistiche"]
                },
                "prodotto": {
                    "type": "string",
                    "description": "Nome prodotto (per aggiungi_spesa o rimuovi_spesa)"
                },
                "quantita": {
                    "type": "integer",
                    "description": "Quantità (default 1)"
                }
            },
            "required": ["azione"]
        }
    }
}


@register_function("smart_fridge", SMART_FRIDGE_DESC, ToolType.WAIT)
def smart_fridge(conn, azione: str = "statistiche", prodotto: str = None, quantita: int = 1):
    """
    Gestione Smart Fridge

    Azioni:
    - inventario: mostra cosa c'è nel frigo
    - scadenze: mostra prodotti in scadenza
    - spesa: mostra lista della spesa
    - aggiungi_spesa: aggiunge prodotto alla lista
    - statistiche: mostra riepilogo
    """
    logger.bind(tag=TAG).info(f"Smart Fridge: azione={azione}, prodotto={prodotto}")

    if azione == "statistiche":
        data = sync_fetch("stats")
        if not data:
            return ActionResponse(Action.RESPONSE, "Non riesco a connettermi al frigo smart",
                                "Mi dispiace, non riesco a connettermi al frigo. Riprova più tardi.")

        result = f"Nel frigo ci sono {data['total_products']} prodotti. "
        if data['expiring_soon'] > 0:
            result += f"Attenzione: {data['expiring_soon']} prodotti in scadenza nei prossimi 7 giorni! "
        if data['shopping_items'] > 0:
            result += f"Hai {data['shopping_items']} prodotti nella lista della spesa."
        else:
            result += "La lista della spesa è vuota."

        return ActionResponse(Action.RESPONSE, result, result)

    elif azione == "inventario":
        data = sync_fetch("inventory")
        if not data:
            return ActionResponse(Action.RESPONSE, "Errore connessione frigo",
                                "Non riesco a connettermi al frigo.")

        if not data.get('products') or data['count'] == 0:
            return ActionResponse(Action.RESPONSE, "Il frigo è vuoto!",
                                "Il frigo è vuoto! Non c'è nessun prodotto.")

        # Raggruppa per nome/barcode e mostra i principali
        products = data['products']
        if len(products) > 10:
            # Mostra solo i primi 10 e il totale
            product_list = ", ".join([
                f"{p['name'] or p['barcode']} ({p['quantity']})"
                for p in products[:10]
            ])
            result = f"Nel frigo ci sono {data['count']} prodotti. I principali: {product_list}... e altri."
        else:
            product_list = ", ".join([
                f"{p['name'] or p['barcode']} ({p['quantity']})"
                for p in products
            ])
            result = f"Nel frigo ci sono: {product_list}."

        return ActionResponse(Action.RESPONSE, result, result)

    elif azione == "scadenze":
        data = sync_fetch("expiring?days=7")
        if not data:
            return ActionResponse(Action.RESPONSE, "Errore connessione frigo",
                                "Non riesco a connettermi al frigo.")

        if not data.get('products') or data['count'] == 0:
            return ActionResponse(Action.RESPONSE, "Nessun prodotto in scadenza",
                                "Ottimo! Non ci sono prodotti in scadenza nei prossimi 7 giorni.")

        products = data['products']
        expiring_list = []
        for p in products[:5]:  # Max 5 prodotti
            name = p['name'] or p['barcode']
            expiry = p['expiry_date']
            expiring_list.append(f"{name} scade il {expiry}")

        result = f"Attenzione! {data['count']} prodotti in scadenza: " + ", ".join(expiring_list)
        if data['count'] > 5:
            result += f"... e altri {data['count'] - 5}."

        return ActionResponse(Action.RESPONSE, result, result)

    elif azione == "spesa":
        data = sync_fetch("shopping")
        if not data:
            return ActionResponse(Action.RESPONSE, "Errore connessione frigo",
                                "Non riesco a connettermi al frigo.")

        if not data.get('shopping_list') or data['total_items'] == 0:
            return ActionResponse(Action.RESPONSE, "Lista della spesa vuota",
                                "La lista della spesa è vuota. Non devi comprare niente!")

        items = data['shopping_list']
        shopping_list = ", ".join([
            f"{item['name'] or item['barcode']} ({item['quantity_needed']})"
            for item in items[:10]
        ])

        result = f"Devi comprare: {shopping_list}"
        if data['total_items'] > 10:
            result += f"... e altri {data['total_items'] - 10} prodotti."

        return ActionResponse(Action.RESPONSE, result, result)

    elif azione == "aggiungi_spesa":
        if not prodotto:
            return ActionResponse(Action.RESPONSE, "Quale prodotto?",
                                "Quale prodotto vuoi aggiungere alla lista della spesa?")

        result = sync_post("shopping", {
            "name": prodotto,
            "barcode": "",
            "quantity": quantita or 1
        })

        if result and result.get('success'):
            qty_text = f" ({quantita})" if quantita > 1 else ""
            return ActionResponse(Action.RESPONSE,
                                f"Aggiunto {prodotto}{qty_text} alla lista della spesa",
                                f"Ho aggiunto {prodotto}{qty_text} alla lista della spesa!")
        else:
            return ActionResponse(Action.RESPONSE, "Errore",
                                "Non sono riuscito ad aggiungere il prodotto alla lista.")

    elif azione == "rimuovi_spesa":
        if not prodotto:
            return ActionResponse(Action.RESPONSE, "Quale prodotto?",
                                "Quale prodotto vuoi rimuovere dalla lista della spesa?")

        result = sync_post("shopping/remove", {"name": prodotto})

        if result and result.get('success'):
            return ActionResponse(Action.RESPONSE,
                                f"Rimosso {prodotto} dalla lista della spesa",
                                f"Ho rimosso {prodotto} dalla lista della spesa!")
        elif result and result.get('not_found'):
            return ActionResponse(Action.RESPONSE,
                                f"{prodotto} non è nella lista",
                                f"{prodotto} non era nella lista della spesa.")
        else:
            return ActionResponse(Action.RESPONSE, "Errore",
                                "Non sono riuscito a rimuovere il prodotto dalla lista.")

    elif azione == "svuota_spesa":
        result = sync_post("shopping/clear", {})

        if result and result.get('success'):
            return ActionResponse(Action.RESPONSE,
                                "Lista della spesa svuotata",
                                "Ho svuotato la lista della spesa!")
        else:
            return ActionResponse(Action.RESPONSE, "Errore",
                                "Non sono riuscito a svuotare la lista della spesa.")

    else:
        return ActionResponse(Action.RESPONSE, "Azione non riconosciuta",
                            "Non ho capito cosa vuoi fare. Prova: cosa c'è nel frigo, cosa scade, lista della spesa.")
