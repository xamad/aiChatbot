"""
Ricette per Ingredienti - Cerca ricette in base agli ingredienti disponibili
Usa web search per trovare piatti con gli ingredienti specificati
"""

import re
import aiohttp
import asyncio
from urllib.parse import quote
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Ricette base comuni per ingredienti tipici (fallback se web search fallisce)
RICETTE_COMUNI = {
    "pasta": ["Pasta al pomodoro", "Pasta aglio olio e peperoncino", "Carbonara", "Amatriciana", "Cacio e pepe"],
    "riso": ["Risotto alla milanese", "Riso in bianco", "Risotto ai funghi", "Arancini", "Insalata di riso"],
    "pollo": ["Pollo arrosto", "Petto di pollo alla piastra", "Pollo al limone", "Spezzatino di pollo", "Cotoletta di pollo"],
    "uova": ["Frittata", "Uova strapazzate", "Uova al tegamino", "Carbonara", "Omelette"],
    "patate": ["Patate arrosto", "Purè di patate", "Patate al forno", "Gnocchi", "Insalata di patate"],
    "pomodoro": ["Pasta al pomodoro", "Bruschetta", "Pappa al pomodoro", "Sugo di pomodoro", "Caprese"],
    "formaggio": ["Pizza margherita", "Pasta ai 4 formaggi", "Fonduta", "Parmigiana", "Crostini al formaggio"],
    "tonno": ["Insalata di tonno", "Pasta al tonno", "Tonno sott'olio con insalata", "Tramezzini al tonno"],
    "carne": ["Polpette", "Ragù", "Hamburger", "Spezzatino", "Bistecca alla fiorentina"],
    "verdure": ["Minestrone", "Verdure grigliate", "Frittata di verdure", "Pasta primavera", "Insalatona"],
    "pesce": ["Pesce al forno", "Pesce alla griglia", "Frittura di pesce", "Zuppa di pesce", "Carpaccio di pesce"],
    "zucchine": ["Zucchine trifolate", "Pasta con le zucchine", "Zucchine ripiene", "Frittata di zucchine"],
    "melanzane": ["Parmigiana di melanzane", "Melanzane alla griglia", "Pasta alla norma", "Caponata"],
    "funghi": ["Risotto ai funghi", "Funghi trifolati", "Pasta ai funghi", "Bruschetta ai funghi"],
}

# Suggerimenti combinazioni
COMBINAZIONI = {
    ("pasta", "uova", "pancetta"): "Carbonara",
    ("pasta", "pomodoro", "basilico"): "Pasta al pomodoro fresco",
    ("riso", "zafferano"): "Risotto alla milanese",
    ("pollo", "limone"): "Pollo al limone",
    ("patate", "uova"): "Frittata di patate",
    ("tonno", "pasta"): "Pasta al tonno",
    ("melanzane", "pomodoro", "mozzarella"): "Parmigiana di melanzane",
}


async def search_recipes_web(ingredienti: list) -> list:
    """Cerca ricette sul web con gli ingredienti specificati"""
    query = "ricette con " + " ".join(ingredienti) + " facili"
    search_url = f"https://www.google.com/search?q={quote(query)}"

    recipes = []

    try:
        # Usa DuckDuckGo HTML per evitare blocchi
        ddg_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"

        async with aiohttp.ClientSession() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            async with session.get(ddg_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # Estrai titoli dai risultati
                    titles = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
                    for title in titles[:5]:
                        clean_title = re.sub(r'\s+', ' ', title).strip()
                        if len(clean_title) > 10:
                            recipes.append(clean_title)

    except Exception as e:
        logger.bind(tag=TAG).warning(f"Errore ricerca web ricette: {e}")

    return recipes


def get_local_recipes(ingredienti: list) -> list:
    """Ottiene ricette dal database locale"""
    recipes = set()

    # Cerca per singoli ingredienti
    for ing in ingredienti:
        ing_lower = ing.lower().strip()
        for key, recs in RICETTE_COMUNI.items():
            if key in ing_lower or ing_lower in key:
                recipes.update(recs[:3])

    # Cerca combinazioni
    ing_set = set(i.lower().strip() for i in ingredienti)
    for combo, recipe in COMBINAZIONI.items():
        if set(combo).issubset(ing_set) or len(set(combo) & ing_set) >= 2:
            recipes.add(recipe)

    return list(recipes)


RICETTE_INGREDIENTI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "ricette_ingredienti",
        "description": (
            "Cerca ricette in base agli ingredienti disponibili. "
            "Usare quando: 'cosa posso cucinare con', 'ricette con', 'ho in casa', "
            "'cosa preparo con', 'ricetta con quello che ho', 'che piatto faccio con'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ingredienti": {
                    "type": "string",
                    "description": "Lista ingredienti separati da virgola (es: pasta, uova, pancetta)"
                }
            },
            "required": ["ingredienti"]
        }
    }
}


@register_function('ricette_ingredienti', RICETTE_INGREDIENTI_FUNCTION_DESC, ToolType.WAIT)
def ricette_ingredienti(conn, ingredienti: str):
    """Cerca ricette in base agli ingredienti"""

    if not ingredienti:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Dimmi quali ingredienti hai a disposizione!",
            response="Dimmi quali ingredienti hai a disposizione e ti suggerisco delle ricette!"
        )

    # Parsa ingredienti
    ing_list = [i.strip() for i in ingredienti.replace(" e ", ",").split(",") if i.strip()]

    if not ing_list:
        return ActionResponse(
            action=Action.RESPONSE,
            result="Non ho capito gli ingredienti. Prova a dirmeli separati da virgola.",
            response="Non ho capito gli ingredienti. Prova a dirmeli separati da virgola, per esempio: pasta, uova, pancetta."
        )

    logger.bind(tag=TAG).info(f"Ricerca ricette per ingredienti: {ing_list}")

    # Cerca ricette locali (sempre disponibili)
    local_recipes = get_local_recipes(ing_list)

    # Cerca ricette web (async)
    try:
        loop = asyncio.get_event_loop()
        web_recipes = loop.run_until_complete(search_recipes_web(ing_list))
    except:
        try:
            web_recipes = asyncio.run(search_recipes_web(ing_list))
        except:
            web_recipes = []

    # Combina risultati
    all_recipes = list(dict.fromkeys(local_recipes + web_recipes))  # Rimuove duplicati mantenendo ordine

    if not all_recipes:
        # Fallback generico
        all_recipes = [
            f"Frittata con {ing_list[0]}" if ing_list else "Frittata",
            "Pasta in bianco",
            "Riso in bianco con verdure"
        ]

    ing_text = ", ".join(ing_list)

    # Formatta risposta
    recipe_list = "\n".join([f"• {r}" for r in all_recipes[:6]])

    result_text = f"Con {ing_text} puoi preparare:\n\n{recipe_list}"

    # Versione parlata
    spoken_recipes = ", ".join(all_recipes[:4])
    spoken = f"Con {ing_text} puoi preparare: {spoken_recipes}. Vuoi che ti dica la ricetta di qualcuno di questi piatti?"

    return ActionResponse(
        action=Action.RESPONSE,
        result=result_text,
        response=spoken
    )
