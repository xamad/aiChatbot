"""
Guida Ristoranti e Trattorie - Cerca ristoranti, trattorie, osterie
Usa ricerca web per dati aggiornati (Gambero Rosso, TripAdvisor, guide locali)
"""

import aiohttp
import asyncio
import re
import json
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Fonti affidabili per ristoranti italiani
FONTI = [
    "gamberorosso.it",
    "tripadvisor.it",
    "thefork.it",
    "dissapore.com",
    "lucianopignataro.it"
]


async def cerca_ristoranti_web(citta: str, zona: str, tipo: str, criterio: str) -> str:
    """Cerca ristoranti usando ricerca web"""

    # Costruisci query di ricerca ottimizzata
    query_parts = []

    if tipo == "gambero_rosso":
        query_parts.append(f"migliori ristoranti {citta} gambero rosso 2024 2025")
    elif tipo == "trattoria":
        query_parts.append(f"migliori trattorie tipiche {citta}")
    elif tipo == "osteria":
        query_parts.append(f"osterie tradizionali {citta}")
    else:
        query_parts.append(f"dove mangiare bene {citta}")

    if zona:
        query_parts[0] += f" {zona}"

    # Aggiungi criterio
    if criterio == "economico":
        query_parts[0] += " economico prezzo onesto low cost"
    elif criterio == "nascosto":
        query_parts[0] += " nascosto segreto poco conosciuto locals"
    elif criterio == "qualita":
        query_parts[0] += " prodotti tipici qualità eccellente"
    elif criterio == "famoso":
        query_parts[0] += " famoso rinomato premiato"

    query = query_parts[0]

    try:
        # Usa DuckDuckGo per ricerca
        encoded_query = query.replace(" ", "+")
        url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as response:
                if response.status == 200:
                    html = await response.text()

                    # Estrai risultati
                    risultati = []

                    # Pattern per estrarre snippet e titoli
                    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)

                    for i, (title, snippet) in enumerate(zip(titles[:5], snippets[:5])):
                        # Pulisci HTML
                        title_clean = re.sub(r'<[^>]+>', '', title).strip()
                        snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
                        if title_clean and snippet_clean:
                            risultati.append(f"{title_clean}: {snippet_clean}")

                    if risultati:
                        return "\n\n".join(risultati[:3])

        return None

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore ricerca web: {e}")
        return None


def genera_raccomandazione(citta: str, zona: str, tipo: str, criterio: str, web_results: str) -> tuple:
    """Genera raccomandazione basata sui risultati"""

    tipo_nome = {
        "gambero_rosso": "ristorante stellato/Gambero Rosso",
        "trattoria": "trattoria tipica",
        "osteria": "osteria tradizionale",
        "generico": "ristorante"
    }.get(tipo, "ristorante")

    criterio_desc = {
        "economico": "con ottimo rapporto qualità-prezzo",
        "nascosto": "poco conosciuto ma eccellente",
        "qualita": "con prodotti di alta qualità",
        "famoso": "rinomato e premiato"
    }.get(criterio, "")

    zona_txt = f" in zona {zona}" if zona else ""

    if web_results:
        intro = f"Ho cercato per te {tipo_nome} a {citta}{zona_txt} {criterio_desc}. "
        intro += "Ecco cosa ho trovato: "

        # Formatta risultati per output vocale
        risultato_parlato = intro + web_results[:500]  # Limita lunghezza

        # Formatta per display
        risultato_display = f"🍽️ **{tipo_nome.title()} a {citta}{zona_txt}**\n"
        risultato_display += f"📍 Criterio: {criterio_desc}\n\n"
        risultato_display += f"🔍 **Risultati dalla ricerca:**\n\n{web_results}\n\n"
        risultato_display += "💡 Consiglio: verifica orari e prenota in anticipo!"

    else:
        # Fallback senza risultati web
        risultato_parlato = f"Mi dispiace, non sono riuscito a trovare informazioni aggiornate su {tipo_nome} a {citta}. "
        risultato_parlato += "Ti consiglio di cercare su TripAdvisor o Gambero Rosso per recensioni recenti. "

        if tipo == "trattoria" and criterio == "economico":
            risultato_parlato += f"Per trattorie economiche a {citta}, cerca 'trattoria tipica {citta}' su Google Maps e filtra per prezzo."

        risultato_display = f"❌ Nessun risultato trovato per {tipo_nome} a {citta}.\n"
        risultato_display += "Suggerimento: prova TripAdvisor o TheFork."

    return risultato_display, risultato_parlato


GUIDA_RISTORANTI_DESC = {
    "type": "function",
    "function": {
        "name": "guida_ristoranti",
        "description": (
            "Cerca ristoranti, trattorie, osterie in Italia. Usa dati web aggiornati. "
            "Usare per: cercami un ristorante, trattoria tipica, osteria, dove mangiare, "
            "gambero rosso, ristorante economico, trattoria nascosta, dove si mangia bene, "
            "consigliami dove mangiare, ristorante qualità prezzo"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "citta": {
                    "type": "string",
                    "description": "Città dove cercare (es: Torino, Roma, Milano)"
                },
                "zona": {
                    "type": "string",
                    "description": "Zona specifica (es: centro, Trastevere, Brera) - opzionale"
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo di locale",
                    "enum": ["gambero_rosso", "trattoria", "osteria", "generico"]
                },
                "criterio": {
                    "type": "string",
                    "description": "Criterio di ricerca",
                    "enum": ["economico", "nascosto", "qualita", "famoso"]
                }
            },
            "required": ["citta"]
        }
    }
}


@register_function('guida_ristoranti', GUIDA_RISTORANTI_DESC, ToolType.WAIT)
def guida_ristoranti(conn, citta: str, zona: str = None, tipo: str = "generico", criterio: str = "qualita"):
    """Cerca e consiglia ristoranti/trattorie"""

    logger.bind(tag=TAG).info(f"Ricerca ristoranti: {citta}, zona={zona}, tipo={tipo}, criterio={criterio}")

    # Esegui ricerca web async
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        web_results = loop.run_until_complete(cerca_ristoranti_web(citta, zona, tipo, criterio))
        loop.close()
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore async: {e}")
        web_results = None

    # Genera raccomandazione
    display, parlato = genera_raccomandazione(citta, zona, tipo, criterio, web_results)

    return ActionResponse(
        action=Action.RESPONSE,
        result=display,
        response=parlato
    )
