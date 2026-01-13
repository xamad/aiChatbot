"""
Ricette Italiane Plugin - Cerca ricette di cucina italiana
Usa l'API gratuita TheMealDB
"""

import requests
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

RICETTE_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "ricette",
        "description": (
            "Cerca ricette di cucina. Puoi cercare per nome piatto, ingrediente, "
            "o categoria. Esempi: 'ricetta carbonara', 'cosa posso fare con pollo', "
            "'ricette dolci', 'come si fa la pizza'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Nome del piatto o ingrediente da cercare",
                },
                "tipo": {
                    "type": "string",
                    "description": "Tipo di ricerca: piatto (nome), ingrediente, categoria",
                    "enum": ["piatto", "ingrediente", "categoria"]
                },
            },
            "required": ["query"],
        },
    },
}

# Traduzioni comuni IT -> EN per la ricerca
TRADUZIONI = {
    "pollo": "chicken", "manzo": "beef", "maiale": "pork",
    "pesce": "fish", "agnello": "lamb", "pasta": "pasta",
    "riso": "rice", "uova": "egg", "formaggio": "cheese",
    "pomodoro": "tomato", "patate": "potato", "verdure": "vegetable",
    "dolce": "dessert", "dolci": "dessert", "carne": "beef",
    "vegetariano": "vegetarian", "vegano": "vegan",
}


def translate_query(query: str) -> str:
    """Traduce termini comuni in inglese per la ricerca"""
    query_lower = query.lower()
    for it, en in TRADUZIONI.items():
        if it in query_lower:
            return en
    return query


def search_by_name(query: str) -> list:
    """Cerca ricette per nome"""
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={query}"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data.get("meals") or []
    except:
        return []


def search_by_ingredient(ingredient: str) -> list:
    """Cerca ricette per ingrediente"""
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ingredient}"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data.get("meals") or []
    except:
        return []


def get_recipe_details(meal_id: str) -> dict:
    """Ottiene i dettagli completi di una ricetta"""
    try:
        url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal_id}"
        response = requests.get(url, timeout=10)
        data = response.json()
        meals = data.get("meals")
        return meals[0] if meals else None
    except:
        return None


def format_recipe(meal: dict) -> str:
    """Formatta una ricetta per la risposta"""
    result = f"**{meal['strMeal']}**\n"
    result += f"Categoria: {meal.get('strCategory', 'N/A')}\n"
    result += f"Origine: {meal.get('strArea', 'N/A')}\n\n"

    # Ingredienti
    result += "**Ingredienti:**\n"
    for i in range(1, 21):
        ingredient = meal.get(f"strIngredient{i}")
        measure = meal.get(f"strMeasure{i}")
        if ingredient and ingredient.strip():
            result += f"- {measure} {ingredient}\n"

    # Istruzioni (abbreviate)
    instructions = meal.get("strInstructions", "")
    if instructions:
        # Prendi solo le prime 500 caratteri per non essere troppo lungo
        if len(instructions) > 500:
            instructions = instructions[:500] + "..."
        result += f"\n**Preparazione:**\n{instructions}\n"

    return result


def format_recipe_spoken(meal: dict) -> str:
    """Formatta una ricetta per la lettura vocale"""
    spoken = f"Ecco la ricetta: {meal['strMeal']}. "

    # Ingredienti principali (max 5)
    ingredients = []
    for i in range(1, 6):
        ingredient = meal.get(f"strIngredient{i}")
        if ingredient and ingredient.strip():
            ingredients.append(ingredient)

    if ingredients:
        spoken += f"Ingredienti principali: {', '.join(ingredients)}. "

    # Istruzioni brevi
    instructions = meal.get("strInstructions", "")
    if instructions:
        # Solo prima frase
        first_sentence = instructions.split('.')[0]
        spoken += f"Preparazione: {first_sentence}."

    return spoken


@register_function("ricette", RICETTE_FUNCTION_DESC, ToolType.SYSTEM_CTL)
def ricette(conn, query: str, tipo: str = "piatto"):
    if not query:
        msg = "Cosa vuoi cucinare? Dimmi il nome di un piatto!"
        return ActionResponse(Action.RESPONSE, msg, msg)

    logger.bind(tag=TAG).info(f"Ricerca ricetta: '{query}' (tipo={tipo})")

    # Traduci la query
    query_en = translate_query(query)

    meals = []

    if tipo == "ingrediente":
        meals = search_by_ingredient(query_en)
    else:
        # Prova prima con il nome originale, poi tradotto
        meals = search_by_name(query)
        if not meals and query_en != query:
            meals = search_by_name(query_en)

    if not meals:
        msg = f"Nessuna ricetta trovata per {query}. Prova con un altro termine!"
        return ActionResponse(Action.RESPONSE, msg, msg)

    # Se abbiamo solo ID, ottieni dettagli
    meal = None
    if meals and "strInstructions" not in meals[0]:
        meal = get_recipe_details(meals[0]["idMeal"])
    else:
        meal = meals[0] if meals else None

    if meal:
        result = format_recipe(meal)
        spoken = format_recipe_spoken(meal)

        # Aggiungi altre opzioni se disponibili
        if len(meals) > 1:
            result += "\n**Altre ricette simili:** "
            others = [m["strMeal"] for m in meals[1:4]]
            result += ", ".join(others)
            spoken += f" Altre opzioni: {', '.join(others)}."

        return ActionResponse(Action.RESPONSE, result, spoken)

    msg = "Errore nella ricerca ricette."
    return ActionResponse(Action.RESPONSE, msg, msg)
