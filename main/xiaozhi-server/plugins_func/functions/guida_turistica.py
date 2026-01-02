"""
Guida Turistica - Audioguida per città d'arte, musei e monumenti
Usa ricerca web in realtime per informazioni aggiornate
"""

import aiohttp
import asyncio
import re
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()


async def cerca_info_luogo(luogo: str, dettaglio: str = "generale") -> str:
    """Cerca informazioni sul luogo usando ricerca web"""

    # Costruisci query ottimizzata per il tipo di dettaglio
    if dettaglio == "storia":
        query = f"{luogo} storia origini costruzione wikipedia"
    elif dettaglio == "arte":
        query = f"{luogo} opere arte capolavori collezioni"
    elif dettaglio == "architettura":
        query = f"{luogo} architettura stile costruzione"
    elif dettaglio == "curiosita":
        query = f"{luogo} curiosità aneddoti segreti"
    else:
        query = f"{luogo} guida turistica cosa vedere informazioni"

    try:
        encoded_query = query.replace(" ", "+")
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as response:
                if response.status == 200:
                    html = await response.text()

                    # Estrai snippet dai risultati
                    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

                    risultati = []
                    for snippet in snippets[:4]:
                        # Pulisci HTML
                        clean = re.sub(r'<[^>]+>', '', snippet).strip()
                        if clean and len(clean) > 50:
                            risultati.append(clean)

                    if risultati:
                        return " ".join(risultati[:2])

        return None

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore ricerca web: {e}")
        return None


def genera_guida(luogo: str, dettaglio: str, web_info: str) -> tuple:
    """Genera la guida basata sui risultati web"""

    dettaglio_intro = {
        "storia": "la storia di",
        "arte": "le opere d'arte di",
        "architettura": "l'architettura di",
        "curiosita": "le curiosità su",
        "generale": ""
    }.get(dettaglio, "")

    if web_info:
        # Costruisci guida dai risultati web
        intro = f"Benvenuto! Ti parlo {dettaglio_intro} {luogo}. "

        # Limita lunghezza per output vocale
        info_breve = web_info[:600] if len(web_info) > 600 else web_info

        parlato = intro + info_breve

        display = f"🏛️ **{luogo}**\n\n"
        if dettaglio != "generale":
            display += f"📍 Focus: {dettaglio}\n\n"
        display += f"📖 {web_info}\n\n"
        display += "💡 Vuoi sapere altro?"

    else:
        # Nessun risultato trovato
        parlato = f"Mi dispiace, non ho trovato informazioni aggiornate su {luogo}. "
        parlato += "Prova a specificare meglio il nome del luogo o monumento."

        display = f"❌ Nessuna informazione trovata su {luogo}.\n"
        display += "Prova con nomi più specifici come 'Colosseo Roma' o 'Galleria Uffizi Firenze'."

    return display, parlato


GUIDA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "guida_turistica",
        "description": (
            "Audioguida turistica per città d'arte, musei e monumenti. Cerca info dal web. "
            "Usare per: guida turistica, visita museo, informazioni monumento, "
            "racconta storia di, parlami del Colosseo, guida Uffizi, visita Pompei, "
            "cosa vedere a, storia del Duomo, arte rinascimentale"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "luogo": {
                    "type": "string",
                    "description": "Nome del luogo, museo, monumento o città d'arte (es: Colosseo, Uffizi, Pompei)"
                },
                "dettaglio": {
                    "type": "string",
                    "description": "Aspetto specifico da approfondire",
                    "enum": ["generale", "storia", "arte", "architettura", "curiosita"]
                }
            },
            "required": ["luogo"]
        }
    }
}


@register_function('guida_turistica', GUIDA_FUNCTION_DESC, ToolType.WAIT)
def guida_turistica(conn, luogo: str, dettaglio: str = "generale"):
    """Fornisce informazioni turistiche cercando sul web in realtime"""

    logger.bind(tag=TAG).info(f"Guida turistica: {luogo}, dettaglio: {dettaglio}")

    # Cerca informazioni sul web
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        web_info = loop.run_until_complete(cerca_info_luogo(luogo, dettaglio))
        loop.close()
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore async: {e}")
        web_info = None

    # Genera guida
    display, parlato = genera_guida(luogo, dettaglio, web_info)

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )
