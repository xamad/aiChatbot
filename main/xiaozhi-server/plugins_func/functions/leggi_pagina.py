"""
Leggi Pagina Plugin - Legge e riassume il contenuto di una pagina web
"""

import requests
import re
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

LEGGI_PAGINA_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "leggi_pagina",
        "description": (
            "读取网页内容 / Legge il contenuto di una pagina web e lo riassume. "
            "当用户想要了解更多关于搜索结果的信息时使用。"
            "Use when user asks: 'leggi il primo link', 'approfondisci', 'apri quel sito', "
            "'dimmi di più sul primo risultato', 'leggi la pagina', 'cosa dice quel sito'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL della pagina da leggere",
                },
                "numero_risultato": {
                    "type": "integer",
                    "description": "Numero del risultato dalla ricerca precedente (1, 2, 3...)",
                },
            },
            "required": [],
        },
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Cache per salvare gli ultimi risultati di ricerca
last_search_results = {}


def clean_html(html: str) -> str:
    """Rimuove tag HTML e pulisce il testo"""
    # Rimuovi script e style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)

    # Rimuovi tutti i tag HTML
    text = re.sub(r'<[^>]+>', ' ', html)

    # Pulisci spazi multipli
    text = re.sub(r'\s+', ' ', text)

    # Rimuovi caratteri speciali HTML
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')

    return text.strip()


def fetch_page_content(url: str, max_chars: int = 4000) -> str:
    """Scarica e pulisce il contenuto di una pagina web"""
    try:
        # Aggiungi https se mancante
        if not url.startswith('http'):
            url = 'https://' + url

        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()

        # Prova a usare BeautifulSoup se disponibile
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Rimuovi elementi non utili
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
                tag.decompose()

            # Cerca il contenuto principale
            main_content = soup.find('main') or soup.find('article') or soup.find('div', {'class': re.compile(r'content|article|post|entry')})

            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)

        except ImportError:
            text = clean_html(response.text)

        # Limita lunghezza
        if len(text) > max_chars:
            text = text[:max_chars] + "... [contenuto troncato]"

        return text

    except requests.exceptions.Timeout:
        return "Errore: timeout nella connessione al sito"
    except requests.exceptions.RequestException as e:
        logger.bind(tag=TAG).error(f"Errore fetch pagina: {e}")
        return f"Errore nel recuperare la pagina: {str(e)[:100]}"


def save_search_results(conn_id: str, results: list):
    """Salva i risultati di ricerca per uso futuro"""
    last_search_results[conn_id] = results


def get_saved_result(numero: int) -> str:
    """Recupera un URL dai risultati salvati di web_search"""
    try:
        from plugins_func.functions.web_search import last_search_results
        if 0 < numero <= len(last_search_results):
            return last_search_results[numero - 1].get('url', '')
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore recupero risultato: {e}")
    return ''


@register_function("leggi_pagina", LEGGI_PAGINA_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def leggi_pagina(conn, url: str = None, numero_risultato: int = None):
    """Legge e riassume il contenuto di una pagina web"""

    # Se è specificato un numero, recupera l'URL dai risultati precedenti
    if numero_risultato and not url:
        url = get_saved_result(numero_risultato)
        if not url:
            return ActionResponse(
                Action.REQLLM,
                f"Non ho trovato il risultato numero {numero_risultato}. Fai prima una ricerca con 'cerca su internet...'",
                None
            )

    if not url:
        return ActionResponse(
            Action.REQLLM,
            "Dimmi quale pagina vuoi che legga. Puoi darmi un URL o dire 'leggi il primo risultato' dopo una ricerca.",
            None
        )

    logger.bind(tag=TAG).info(f"Lettura pagina: {url}")

    content = fetch_page_content(url)

    if content.startswith("Errore"):
        return ActionResponse(Action.REQLLM, content, None)

    result = f"📄 **Contenuto da {url[:50]}...**\n\n{content}\n\n---\nRiassumi o rispondi alle domande dell'utente basandoti su questo contenuto."

    return ActionResponse(Action.REQLLM, result, None)


# Patch web_search per salvare i risultati
def patch_web_search():
    """Modifica web_search per salvare i risultati"""
    try:
        from plugins_func.functions import web_search as ws_module
        original_search = ws_module.search_duckduckgo

        def patched_search(query, num_results=5, lang="it"):
            results = original_search(query, num_results, lang)
            # Salva i risultati globalmente
            last_search_results['last'] = results
            return results

        ws_module.search_duckduckgo = patched_search
        logger.bind(tag=TAG).info("web_search patched per salvare risultati")
    except Exception as e:
        logger.bind(tag=TAG).warning(f"Impossibile patchare web_search: {e}")

# Applica patch all'import
patch_web_search()
