"""
Notizie Italia Plugin - RSS feed dai principali giornali italiani
"""

import requests
import xml.etree.ElementTree as ET
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

NOTIZIE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "notizie_italia",
        "description": (
            "获取意大利新闻 / Ottieni le ultime notizie dall'Italia. "
            "当用户询问新闻、头条、意大利发生了什么时使用。"
            "Use when user asks: 'notizie', 'news', 'cosa è successo', 'ultime notizie', "
            "'headlines', 'giornale', 'ansa', 'repubblica'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "description": "Categoria: cronaca, politica, economia, sport, tecnologia, cultura. Default: cronaca",
                },
                "fonte": {
                    "type": "string",
                    "description": "Fonte: ansa, repubblica, corriere. Default: ansa",
                },
                "num_notizie": {
                    "type": "integer",
                    "description": "Numero di notizie (1-5). Default: 3",
                },
            },
            "required": [],
        },
    },
}

# RSS feeds dei giornali italiani
RSS_FEEDS = {
    "ansa": {
        "cronaca": "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
        "politica": "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
        "economia": "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
        "sport": "https://www.ansa.it/sito/notizie/sport/sport_rss.xml",
        "tecnologia": "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
        "cultura": "https://www.ansa.it/sito/notizie/cultura/cultura_rss.xml",
    },
    "repubblica": {
        "cronaca": "https://www.repubblica.it/rss/cronaca/rss2.0.xml",
        "politica": "https://www.repubblica.it/rss/politica/rss2.0.xml",
        "economia": "https://www.repubblica.it/rss/economia/rss2.0.xml",
        "sport": "https://www.repubblica.it/rss/sport/rss2.0.xml",
        "tecnologia": "https://www.repubblica.it/rss/tecnologia/rss2.0.xml",
        "cultura": "https://www.repubblica.it/rss/cultura/rss2.0.xml",
    },
    "corriere": {
        "cronaca": "https://xml2.corriereobjects.it/rss/cronache.xml",
        "politica": "https://xml2.corriereobjects.it/rss/politica.xml",
        "economia": "https://xml2.corriereobjects.it/rss/economia.xml",
        "sport": "https://xml2.corriereobjects.it/rss/sport.xml",
        "tecnologia": "https://xml2.corriereobjects.it/rss/tecnologia.xml",
        "cultura": "https://xml2.corriereobjects.it/rss/cultura.xml",
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def fetch_rss_news(url: str, num_items: int = 3) -> list:
    """Fetch news from RSS feed"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        items = []

        # Standard RSS format
        for item in root.findall(".//item")[:num_items]:
            title = item.find("title")
            description = item.find("description")

            if title is not None:
                news_item = {
                    "title": title.text.strip() if title.text else "",
                    "description": ""
                }
                if description is not None and description.text:
                    # Clean HTML tags from description
                    desc = description.text.strip()
                    import re
                    desc = re.sub(r'<[^>]+>', '', desc)
                    news_item["description"] = desc[:150] + "..." if len(desc) > 150 else desc

                items.append(news_item)

        return items
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore fetch RSS: {e}")
        return []


@register_function("notizie_italia", NOTIZIE_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def notizie_italia(conn, categoria: str = "cronaca", fonte: str = "ansa", num_notizie: int = 3):
    """Ottieni le ultime notizie dall'Italia"""

    # Normalizza input
    categoria = categoria.lower() if categoria else "cronaca"
    fonte = fonte.lower() if fonte else "ansa"
    num_notizie = min(max(1, num_notizie if num_notizie else 3), 5)

    # Valida fonte e categoria
    if fonte not in RSS_FEEDS:
        fonte = "ansa"
    if categoria not in RSS_FEEDS[fonte]:
        categoria = "cronaca"

    url = RSS_FEEDS[fonte][categoria]
    logger.bind(tag=TAG).info(f"Fetching news: {fonte}/{categoria}")

    news = fetch_rss_news(url, num_notizie)

    if not news:
        return ActionResponse(
            Action.REQLLM,
            f"Non sono riuscito a recuperare le notizie da {fonte}. Riprova più tardi.",
            None
        )

    fonte_nome = {"ansa": "ANSA", "repubblica": "Repubblica", "corriere": "Corriere della Sera"}
    result = f"📰 **Ultime notizie {categoria.upper()}** da {fonte_nome.get(fonte, fonte)}:\n\n"

    for i, item in enumerate(news, 1):
        result += f"{i}. **{item['title']}**\n"
        if item['description']:
            result += f"   {item['description']}\n"
        result += "\n"

    return ActionResponse(Action.REQLLM, result, None)
