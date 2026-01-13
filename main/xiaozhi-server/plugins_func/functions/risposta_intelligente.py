"""
Risposta Intelligente - Fallback con AI per domande generiche
Usa Gemini API gratuito o web search avanzato per dare risposte complete
"""

import os
import re
import json
import aiohttp
import asyncio
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Gemini API (gratuito con limiti generosi)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"


async def ask_gemini(question: str) -> str:
    """Chiede a Gemini API (Google AI)"""
    if not GEMINI_API_KEY:
        return None

    try:
        payload = {
            "contents": [{
                "parts": [{"text": f"Rispondi in italiano, in modo conciso e naturale (max 3 frasi): {question}"}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 200
            }
        }

        async with aiohttp.ClientSession() as session:
            url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return text.strip()
    except Exception as e:
        logger.bind(tag=TAG).warning(f"Errore Gemini API: {e}")

    return None


async def search_duckduckgo_instant(query: str) -> str:
    """Usa DuckDuckGo Instant Answer API"""
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    # Abstract (Wikipedia-style)
                    if data.get("AbstractText"):
                        return data["AbstractText"][:500]

                    # Answer (calcoli, conversioni)
                    if data.get("Answer"):
                        return data["Answer"]

                    # Definition
                    if data.get("Definition"):
                        return data["Definition"]

    except Exception as e:
        logger.bind(tag=TAG).warning(f"Errore DuckDuckGo Instant: {e}")

    return None


async def search_duckduckgo_html(query: str) -> str:
    """Cerca su DuckDuckGo HTML per risultati più completi"""
    try:
        from bs4 import BeautifulSoup
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data={"q": query}, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")

                    # Prendi i primi 3 snippet
                    snippets = []
                    for result in soup.select(".result__snippet")[:3]:
                        text = result.get_text(strip=True)
                        if text and len(text) > 20:
                            snippets.append(text)

                    if snippets:
                        return " ".join(snippets)[:600]
    except Exception as e:
        logger.bind(tag=TAG).warning(f"Errore DuckDuckGo HTML: {e}")

    return None


async def get_smart_answer(question: str) -> str:
    """Ottiene risposta intelligente da varie fonti"""

    # 1. Prova Gemini (se configurato)
    gemini_answer = await ask_gemini(question)
    if gemini_answer:
        logger.bind(tag=TAG).info(f"Risposta da Gemini")
        return gemini_answer

    # 2. Prova DuckDuckGo Instant Answer (Wikipedia, calcoli)
    ddg_answer = await search_duckduckgo_instant(question)
    if ddg_answer:
        logger.bind(tag=TAG).info(f"Risposta da DuckDuckGo Instant")
        return ddg_answer

    # 3. Prova DuckDuckGo HTML search (risultati web)
    ddg_html = await search_duckduckgo_html(question)
    if ddg_html:
        logger.bind(tag=TAG).info(f"Risposta da DuckDuckGo HTML")
        return ddg_html

    # 4. Fallback generico
    return None


RISPOSTA_INTELLIGENTE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "risposta_intelligente",
        "description": (
            "ULTIMA RISORSA - Usare SOLO per domande di cultura generale senza azione specifica. "
            "NON USARE SE: l'utente chiede immagini/foto (→cerca_immagini), gif (→cerca_gif), "
            "meteo (→meteo_italia), radio (→radio_italia), timer (→timer_sveglia), "
            "ricette (→ricette), notizie (→notizie_italia), musica (→play_music). "
            "USARE SOLO PER: 'chi era Einstein', 'cos'è la fotosintesi', 'spiegami la relatività', "
            "'qual è la capitale del Giappone', domande storiche, scientifiche, definizioni."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "domanda": {
                    "type": "string",
                    "description": "Solo domande di cultura generale senza azione richiesta"
                }
            },
            "required": ["domanda"]
        }
    }
}


@register_function('risposta_intelligente', RISPOSTA_INTELLIGENTE_FUNCTION_DESC, ToolType.WAIT)
def risposta_intelligente(conn, domanda: str):
    """Risponde a domande generiche con AI"""

    if not domanda:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Non ho capito la domanda.",
            response="Scusa, non ho capito. Puoi ripetere?"
        )

    logger.bind(tag=TAG).info(f"Risposta intelligente per: {domanda[:50]}...")

    # Esegui ricerca async
    try:
        loop = asyncio.get_event_loop()
        answer = loop.run_until_complete(get_smart_answer(domanda))
    except:
        try:
            answer = asyncio.run(get_smart_answer(domanda))
        except:
            answer = None

    if answer:
        # Pulisci risposta
        answer = re.sub(r'\s+', ' ', answer).strip()

        # Tronca se troppo lunga per il parlato
        spoken = answer
        if len(spoken) > 300:
            # Tronca alla frase più vicina
            cut_point = spoken[:300].rfind('.')
            if cut_point > 100:
                spoken = spoken[:cut_point + 1]
            else:
                spoken = spoken[:300] + "..."

        return ActionResponse(
            action=Action.RESPONSE,
            result=answer,
            response=spoken
        )
    else:
        # Nessuna risposta trovata
        return ActionResponse(
            action=Action.RESPONSE,
            result="Non ho trovato informazioni su questo argomento.",
            response="Mi dispiace, non ho trovato informazioni su questo. Prova a chiedermi in modo diverso!"
        )
