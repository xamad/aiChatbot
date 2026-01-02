"""
Briefing Mattutino - Riassunto personalizzato della giornata
Meteo, santo del giorno, oroscopo, promemoria, notizie
"""

import aiohttp
import asyncio
import random
from datetime import datetime
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from plugins_func.functions.user_memory import get_user_memory

TAG = __name__
logger = setup_logging()

# Saluti mattutini
SALUTI_MATTINA = [
    "Buongiorno! Ecco il tuo briefing di oggi.",
    "Ben svegliato! Vediamo cosa ci riserva questa giornata.",
    "Buongiorno! Pronto per iniziare la giornata?",
    "Buona mattina! Ecco le informazioni per oggi.",
]

# Santi del giorno (semplificato - primi mesi)
SANTI = {
    "01-01": "Maria Santissima Madre di Dio",
    "01-02": "San Basilio Magno",
    "01-06": "Epifania del Signore",
    "01-17": "Sant'Antonio Abate",
    "02-14": "San Valentino",
    "03-19": "San Giuseppe",
    "04-25": "San Marco Evangelista",
    "05-01": "San Giuseppe Lavoratore",
    "06-24": "San Giovanni Battista",
    "06-29": "Santi Pietro e Paolo",
    "08-15": "Assunzione di Maria",
    "10-04": "San Francesco d'Assisi",
    "11-01": "Tutti i Santi",
    "12-08": "Immacolata Concezione",
    "12-25": "Natale del Signore",
    "12-26": "Santo Stefano",
}


async def get_meteo_breve(citta: str = "Roma") -> str:
    """Ottiene meteo breve per il briefing"""
    try:
        url = f"https://wttr.in/{citta}?format=%c+%t&lang=it"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.text()
    except:
        pass
    return None


def get_santo_oggi() -> str:
    """Restituisce il santo del giorno"""
    oggi = datetime.now().strftime("%m-%d")
    return SANTI.get(oggi, None)


def get_frase_motivazionale() -> str:
    """Restituisce una frase motivazionale"""
    frasi = [
        "Ogni giorno è una nuova opportunità per fare qualcosa di bello.",
        "Il segreto per andare avanti è iniziare.",
        "Sii il cambiamento che vuoi vedere nel mondo.",
        "La vita è quello che succede mentre fai altri piani.",
        "Ogni mattina porta nuove speranze.",
        "Il momento migliore per piantare un albero era vent'anni fa. Il secondo momento migliore è adesso.",
        "Non contare i giorni, fai che i giorni contino.",
        "La felicità non è qualcosa di già pronto. Viene dalle tue azioni.",
    ]
    return random.choice(frasi)


def genera_briefing(conn, memoria) -> tuple:
    """Genera il briefing personalizzato"""

    nome = memoria.data.get("nome_utente") or "amico"
    oggi = datetime.now()
    giorno_settimana = ["lunedì", "martedì", "mercoledì", "giovedì",
                        "venerdì", "sabato", "domenica"][oggi.weekday()]
    data_str = oggi.strftime("%d/%m/%Y")

    # Saluto personalizzato
    saluto = random.choice(SALUTI_MATTINA)

    # Costruisci briefing
    parlato = f"{saluto} {nome}! "
    parlato += f"Oggi è {giorno_settimana} {data_str}. "

    display = f"☀️ **Buongiorno {nome}!**\n\n"
    display += f"📅 **{giorno_settimana.capitalize()} {data_str}**\n\n"

    # Santo del giorno
    santo = get_santo_oggi()
    if santo:
        parlato += f"Oggi si festeggia {santo}. "
        display += f"⛪ Santo: {santo}\n\n"

    # Meteo (sincrono per semplicità)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        meteo = loop.run_until_complete(get_meteo_breve())
        loop.close()
        if meteo:
            parlato += f"Il meteo prevede {meteo.strip()}. "
            display += f"🌤️ Meteo: {meteo.strip()}\n\n"
    except:
        pass

    # Promemoria farmaci se presenti
    farmaci = memoria.data.get("farmaci_da_prendere", [])
    if farmaci:
        farmaci_mattina = [f for f in farmaci if "mattina" in f.get("orario", "").lower()]
        if farmaci_mattina:
            nomi_farmaci = ", ".join([f["nome"] for f in farmaci_mattina])
            parlato += f"Ricorda di prendere: {nomi_farmaci}. "
            display += f"💊 Farmaci mattina: {nomi_farmaci}\n\n"

    # Funzioni preferite come suggerimento
    funz_pref = memoria.get_funzioni_preferite(2)
    if funz_pref:
        suggerimento = funz_pref[0][0].replace("_", " ")
        parlato += f"Se vuoi, possiamo fare un po' di {suggerimento}. "
        display += f"💡 Suggerimento: {suggerimento}\n\n"

    # Frase motivazionale
    frase = get_frase_motivazionale()
    parlato += frase
    display += f"✨ *{frase}*\n\n"

    display += "Buona giornata!"

    return display, parlato


BRIEFING_MATTUTINO_DESC = {
    "type": "function",
    "function": {
        "name": "briefing_mattutino",
        "description": (
            "Briefing mattutino personalizzato con data, meteo, santo, promemoria. "
            "Usare per: buongiorno, briefing, cosa c'è oggi, inizia giornata, "
            "mattina, sveglia, programma di oggi, che giorno è"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}


@register_function('briefing_mattutino', BRIEFING_MATTUTINO_DESC, ToolType.WAIT)
def briefing_mattutino(conn):
    """Fornisce briefing mattutino personalizzato"""

    device_id = getattr(conn, 'device_id', 'unknown')
    logger.bind(tag=TAG).info(f"Briefing mattutino per {device_id}")

    # Ottieni memoria utente
    memoria = get_user_memory(device_id)

    # Genera briefing
    display, parlato = genera_briefing(conn, memoria)

    # Registra interazione
    memoria.registra_interazione("briefing mattutino", "briefing_mattutino")

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )
