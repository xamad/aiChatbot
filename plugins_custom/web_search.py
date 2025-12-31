"""
Web Search Plugin for Xiaozhi ESP32 Server
Permette al chatbot di cercare informazioni sul web in tempo reale.
Usa DuckDuckGo (gratuito, senza API key)
"""

import requests
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

WEB_SEARCH_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索网络信息 / Cerca informazioni sul web in tempo reale. "
            "当用户询问最新信息、新闻、价格、当前事件时使用此功能。"
            "Use when user asks: 'cerca su google', 'cerca su internet', 'cerca online', "
            "'google...', 'search...', 'cerca...', 'qual è il prezzo di...', 'cosa è successo...'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "La query di ricerca da cercare sul web",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Numero di risultati da restituire (default: 5, max: 10)",
                },
                "lang": {
                    "type": "string",
                    "description": "Lingua dei risultati: it (italiano), en (inglese), etc. Default: it",
                },
            },
            "required": ["query"],
        },
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def search_duckduckgo(query: str, num_results: int = 5, lang: str = "it") -> list:
    """
    Cerca su DuckDuckGo usando l'API HTML (gratuita)
    """
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {
            "q": query,
            "kl": f"{lang}-{lang}",
        }

        response = requests.post(url, data=params, headers=HEADERS, timeout=10)
        response.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        results = []
        for result in soup.select(".result")[:num_results]:
            title_elem = result.select_one(".result__title")
            snippet_elem = result.select_one(".result__snippet")
            link_elem = result.select_one(".result__url")

            if title_elem and snippet_elem:
                title = title_elem.get_text(strip=True)
                snippet = snippet_elem.get_text(strip=True)
                link = link_elem.get_text(strip=True) if link_elem else ""

                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": link
                })

        return results

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore ricerca DuckDuckGo: {e}")
        return []


@register_function("web_search", WEB_SEARCH_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def web_search(conn, query: str, num_results: int = 5, lang: str = "it"):
    from core.utils.cache.manager import cache_manager, CacheType

    if not query:
        return ActionResponse(Action.REQLLM, "Nessuna query di ricerca fornita", None)

    num_results = min(max(1, num_results), 10)
    cache_key = f"web_search_{query}_{lang}_{num_results}"
    cached_result = cache_manager.get(CacheType.WEATHER, cache_key)
    if cached_result:
        return ActionResponse(Action.REQLLM, cached_result, None)

    logger.bind(tag=TAG).info(f"Ricerca web: '{query}'")

    results = search_duckduckgo(query, num_results, lang)

    if not results:
        return ActionResponse(
            Action.REQLLM,
            f"Nessun risultato trovato per: {query}",
            None
        )

    result_text = f"**Risultati per: {query}**\n\n"
    for i, r in enumerate(results, 1):
        result_text += f"{i}. **{r['title']}**\n   {r['snippet']}\n\n"

    cache_manager.set(CacheType.WEATHER, cache_key, result_text)
    return ActionResponse(Action.REQLLM, result_text, None)
