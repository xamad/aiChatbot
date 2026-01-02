"""
Storie per Bambini Plugin - Racconti e favole vocali
Genera storie interattive usando LLM
"""

import random
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Favole classiche brevi
CLASSIC_STORIES = {
    "cappuccetto": {
        "title": "Cappuccetto Rosso",
        "story": """C'era una volta una bambina chiamata Cappuccetto Rosso per il suo mantello rosso.
Un giorno la mamma le disse: "Porta questi dolci alla nonna che è malata, ma non fermarti nel bosco!"
Nel bosco incontrò il lupo cattivo che le chiese dove andava. "Dalla nonna!" disse lei ingenuamente.
Il lupo corse dalla nonna, la rinchiuse nell'armadio e si mise nel suo letto.
Quando arrivò Cappuccetto: "Nonna, che orecchie grandi hai!" - "Per sentirti meglio!"
"Che occhi grandi hai!" - "Per vederti meglio!"
"Che bocca grande hai!" - "Per mangiarti meglio!"
Ma un cacciatore sentì le grida, salvò la nonna e cacciò via il lupo.
E vissero tutti felici e contenti!"""
    },
    "tre_porcellini": {
        "title": "I Tre Porcellini",
        "story": """C'erano una volta tre porcellini che dovevano costruire la loro casa.
Il primo, pigro, la fece di paglia. Il secondo di legno. Il terzo, saggio, di mattoni.
Arrivò il lupo: "Porcellino, apri o soffierò!" E soffiò via la casa di paglia.
Andò alla casa di legno: "Apriii!" E soffiò via anche quella.
I tre si rifugiarono nella casa di mattoni. Il lupo soffiò e soffiò, ma la casa resistette!
Provò a entrare dal camino, ma cadde in una pentola d'acqua bollente e scappò via per sempre.
I tre porcellini vissero felici nella casa di mattoni!"""
    },
    "brutto_anatroccolo": {
        "title": "Il Brutto Anatroccolo",
        "story": """In una fattoria nacque un anatroccolo diverso dagli altri, più grande e grigio.
Tutti lo prendevano in giro: "Che brutto sei!" Triste, l'anatroccolo scappò via.
Passò l'inverno al freddo, nascosto tra i giunchi del lago.
In primavera vide dei bellissimi cigni bianchi nuotare eleganti.
Si avvicinò timido, aspettandosi di essere cacciato.
Ma guardando il suo riflesso nell'acqua... era diventato un bellissimo cigno bianco!
I cigni lo accolsero con gioia. Non era mai stato un brutto anatroccolo, ma un cigno!"""
    },
    "pinocchio": {
        "title": "Pinocchio",
        "story": """Geppetto era un falegname che scolpì un burattino di legno e lo chiamò Pinocchio.
La Fata Turchina lo fece parlare e muovere, promettendogli: "Se sarai buono, diventerai un bambino vero!"
Ma Pinocchio era birichino. Invece di andare a scuola, seguì il Gatto e la Volpe.
Ogni volta che diceva una bugia, il suo naso si allungava!
Finì nella pancia di una balena, dove trovò anche Geppetto.
Insieme scapparono. Pinocchio, pentito, promise di essere buono.
La Fata Turchina lo trasformò in un bambino vero. Geppetto pianse di gioia!"""
    },
}

# Temi per storie generate
STORY_THEMES = [
    "un drago che aveva paura del fuoco",
    "una principessa che amava le avventure",
    "un robot che voleva fare amicizia",
    "un gattino che si perse nel bosco magico",
    "un elefante che sapeva volare",
    "una stella cadente che cercava casa",
]

STORIE_BAMBINI_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "storie_bambini",
        "description": (
            "Racconta favole e storie per bambini."
            "Usare quando: raccontami una storia, favola, storia della buonanotte, "
            "Cappuccetto Rosso, racconta ai bambini"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "story_name": {
                    "type": "string",
                    "description": "Nome storia specifica: cappuccetto, tre_porcellini, brutto_anatroccolo, pinocchio"
                },
                "action": {
                    "type": "string",
                    "description": "Azione: tell (racconta), list (elenca disponibili), random (storia casuale)",
                    "enum": ["tell", "list", "random", "generate"]
                },
                "theme": {
                    "type": "string",
                    "description": "Tema per storia generata (es: 'un drago', 'una principessa')"
                }
            },
            "required": ["action"],
        },
    },
}


@register_function("storie_bambini", STORIE_BAMBINI_FUNCTION_DESC, ToolType.WAIT)
def storie_bambini(conn, action: str = "random", story_name: str = None, theme: str = None):
    logger.bind(tag=TAG).info(f"Storie: action={action}, story_name={story_name}")

    if action == "list":
        titles = [s["title"] for s in CLASSIC_STORIES.values()]
        return ActionResponse(Action.RESPONSE,
            f"Storie disponibili: {', '.join(titles)}",
            f"Posso raccontarti: {', '.join(titles)}. Quale vuoi sentire?")

    if action == "tell" or action == "random":
        # Trova storia
        if story_name:
            story_key = story_name.lower().replace(" ", "_")
            # Cerca match parziale
            for key in CLASSIC_STORIES:
                if story_key in key or key in story_key:
                    story = CLASSIC_STORIES[key]
                    break
            else:
                story = random.choice(list(CLASSIC_STORIES.values()))
        else:
            story = random.choice(list(CLASSIC_STORIES.values()))

        intro = f"Ti racconto la storia di {story['title']}. Mettiti comodo..."
        full_story = f"{intro}\n\n{story['story']}\n\nFine della storia! Ti è piaciuta?"

        return ActionResponse(Action.RESPONSE, full_story, full_story)

    if action == "generate":
        # Usa LLM per generare storia
        if theme:
            prompt = f"Racconta una breve favola per bambini (max 150 parole) su: {theme}. Inizia con 'C'era una volta' e finisci con una morale."
        else:
            random_theme = random.choice(STORY_THEMES)
            prompt = f"Racconta una breve favola per bambini (max 150 parole) su: {random_theme}. Inizia con 'C'era una volta' e finisci con una morale."

        return ActionResponse(Action.REQLLM, prompt, "Ti invento una storia...")

    return ActionResponse(Action.RESPONSE,
        "Vuoi sentire una favola?",
        "Vuoi che ti racconti una bella storia?")
