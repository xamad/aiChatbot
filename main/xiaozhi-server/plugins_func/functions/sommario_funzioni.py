"""
Sommario Funzioni Plugin - Elenca tutte le funzionalità disponibili
Aiuta l'utente a scoprire cosa può fare il chatbot
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Catalogo completo delle funzionalità organizzate per categoria
# ESCLUSI: Easter egg (giannini, osterie goliardiche, easter_egg_folli)
FUNZIONALITA = {
    "🎵 Audio & Media": [
        {"nome": "Radio Italia", "trigger": "metti radio deejay", "desc": "Streaming radio italiane"},
        {"nome": "Podcast", "trigger": "ascolta podcast", "desc": "Programmi RAI"},
        {"nome": "Beatbox", "trigger": "fai un beatbox", "desc": "Beat vocali stile rapper"},
        {"nome": "Karaoke", "trigger": "karaoke", "desc": "Testi canzoni"},
        {"nome": "Suoni Ambiente", "trigger": "suono della pioggia", "desc": "ASMR e relax"},
        {"nome": "Versi Animali", "trigger": "fai il verso del gallo", "desc": "Imita animali"},
    ],
    "🎮 Giochi": [
        {"nome": "Quiz Trivia", "trigger": "facciamo un quiz", "desc": "Domande cultura generale"},
        {"nome": "Impiccato", "trigger": "giochiamo all'impiccato", "desc": "Indovina la parola"},
        {"nome": "20 Domande", "trigger": "giochiamo a 20 domande", "desc": "Indovina con sì/no"},
        {"nome": "Battaglia Navale", "trigger": "battaglia navale", "desc": "Gioco classico"},
        {"nome": "Milionario", "trigger": "chi vuol essere milionario", "desc": "Quiz con aiuti"},
        {"nome": "Cruciverba", "trigger": "cruciverba", "desc": "Definizioni"},
        {"nome": "Dado", "trigger": "lancia un dado", "desc": "Tira dadi"},
        {"nome": "Oracolo", "trigger": "oracolo, devo...?", "desc": "Risposte mistiche"},
    ],
    "📰 Informazioni": [
        {"nome": "Notizie", "trigger": "dimmi le notizie", "desc": "News italiane"},
        {"nome": "Meteo", "trigger": "che tempo fa a Milano?", "desc": "Previsioni"},
        {"nome": "Oroscopo", "trigger": "oroscopo leone", "desc": "Segni zodiacali"},
        {"nome": "Santo del Giorno", "trigger": "che santo è oggi?", "desc": "Onomastici"},
        {"nome": "Accadde Oggi", "trigger": "cosa accadde oggi?", "desc": "Storia"},
        {"nome": "Lotto", "trigger": "estrazioni lotto", "desc": "Numeri estratti"},
        {"nome": "Curiosità", "trigger": "dimmi qualcosa di interessante", "desc": "Fatti curiosi"},
        {"nome": "Proverbi", "trigger": "dimmi un proverbio", "desc": "Saggezza popolare"},
    ],
    "🍳 Cucina": [
        {"nome": "Ricette", "trigger": "ricetta carbonara", "desc": "Come si prepara"},
        {"nome": "Ricette Ingredienti", "trigger": "cosa cucino con uova e pasta?", "desc": "Idee con ingredienti"},
        {"nome": "Cooking Companion", "trigger": "cuciniamo la carbonara", "desc": "Guida passo-passo"},
    ],
    "🛠️ Utilità": [
        {"nome": "Timer", "trigger": "timer 5 minuti", "desc": "Conto alla rovescia"},
        {"nome": "Sveglia", "trigger": "svegliami tra 10 minuti", "desc": "Avvisi"},
        {"nome": "Promemoria", "trigger": "ricordami di chiamare Marco", "desc": "Azioni future"},
        {"nome": "Memoria", "trigger": "ricordami che le chiavi sono nel cassetto", "desc": "Salva informazioni"},
        {"nome": "Dove Ho Messo", "trigger": "dove ho messo le chiavi?", "desc": "Cerca nella memoria"},
        {"nome": "Calcolatrice", "trigger": "quanto fa 25 per 4?", "desc": "Calcoli"},
        {"nome": "Convertitore", "trigger": "converti 100 euro in dollari", "desc": "Valute/unità"},
        {"nome": "Shopping Vocale", "trigger": "aggiungi latte alla spesa", "desc": "Lista spesa"},
        {"nome": "Note Vocali", "trigger": "prendi nota", "desc": "Appunti"},
        {"nome": "Agenda", "trigger": "cosa ho in agenda?", "desc": "Appuntamenti"},
        {"nome": "Rubrica", "trigger": "numero di mamma", "desc": "Contatti"},
    ],
    "🌍 Traduzione & Ricerca": [
        {"nome": "Traduttore", "trigger": "traduci ciao in inglese", "desc": "Traduzioni"},
        {"nome": "Web Search", "trigger": "cerca su google intelligenza artificiale", "desc": "Ricerca web"},
        {"nome": "Risposta AI", "trigger": "chiedi a gpt cos'è la blockchain", "desc": "Domande all'AI"},
        {"nome": "Spiegazioni", "trigger": "cos'è il machine learning?", "desc": "Definizioni AI"},
    ],
    "🧘 Benessere": [
        {"nome": "Meditazione", "trigger": "facciamo meditazione", "desc": "Respirazione guidata"},
        {"nome": "Supporto Emotivo", "trigger": "sono ansioso", "desc": "Conforto"},
        {"nome": "Compagno", "trigger": "mi sento solo", "desc": "Compagnia"},
        {"nome": "Compagno Notturno", "trigger": "non riesco a dormire", "desc": "Aiuto insonnia"},
    ],
    "🏠 Casa Smart": [
        {"nome": "Domotica", "trigger": "accendi luce cucina", "desc": "Controllo luci"},
        {"nome": "Numeri Utili", "trigger": "numero carabinieri", "desc": "Emergenze"},
    ],
    "🗺️ Guide": [
        {"nome": "Guida Turistica", "trigger": "cosa visitare a Roma?", "desc": "Monumenti"},
        {"nome": "Ristoranti", "trigger": "dove mangiare a Napoli?", "desc": "Locali"},
    ],
    "👶 Bambini & Famiglia": [
        {"nome": "Storie", "trigger": "raccontami una storia", "desc": "Favole"},
        {"nome": "Barzellette", "trigger": "raccontami una barzelletta", "desc": "Battute"},
        {"nome": "Frase del Giorno", "trigger": "frase del giorno", "desc": "Citazioni"},
    ],
    "🎭 Personalità": [
        {"nome": "Cambia Personalità", "trigger": "parla come un pirata", "desc": "Voci diverse"},
        {"nome": "Torna Normale", "trigger": "torna normale", "desc": "Reset voce"},
        {"nome": "Chi Sono", "trigger": "tu chi sei?", "desc": "Presentazione"},
    ],
}

SOMMARIO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "sommario_funzioni",
        "description": (
            "Elenca TUTTE le funzionalità disponibili del chatbot con esempi."
            "Usare quando: quali funzioni hai, help, elenca funzioni, lista funzioni, "
            "mostrami le funzioni, cosa fai"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "description": "Categoria specifica (audio, giochi, info, cucina, utilità, traduzione, benessere, casa, guide, bambini, personalità)"
                }
            },
            "required": [],
        },
    },
}

@register_function("sommario_funzioni", SOMMARIO_FUNCTION_DESC, ToolType.WAIT)
def sommario_funzioni(conn, categoria: str = None):
    logger.bind(tag=TAG).info(f"Sommario: categoria={categoria}")

    if categoria:
        # Cerca categoria
        cat_lower = categoria.lower()
        found_cat = None
        found_funcs = None

        for cat_name, funcs in FUNZIONALITA.items():
            if cat_lower in cat_name.lower():
                found_cat = cat_name
                found_funcs = funcs
                break

        if found_funcs:
            result = f"**{found_cat}**\n\n"
            spoken_parts = []

            for f in found_funcs:
                result += f"• **{f['nome']}**: {f['desc']}\n"
                result += f"  → _\"{f['trigger']}\"_\n\n"
                spoken_parts.append(f"{f['nome']}, dì: {f['trigger']}")

            spoken = f"In {found_cat.split(' ', 1)[1]}: " + ". ".join(spoken_parts[:4])
            if len(spoken_parts) > 4:
                spoken += f". E altre {len(spoken_parts) - 4} funzioni."

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            categorie = [c.split(' ', 1)[1] for c in FUNZIONALITA.keys()]
            return ActionResponse(Action.RESPONSE,
                f"Categoria non trovata. Categorie: {', '.join(categorie)}",
                f"Non ho quella categoria. Prova: {', '.join(categorie[:5])}")

    # Elenco completo con trigger
    result = "# 🤖 TUTTE LE MIE FUNZIONALITÀ\n\n"

    total_funcs = 0
    for cat_name, funcs in FUNZIONALITA.items():
        result += f"## {cat_name}\n"
        for f in funcs:
            result += f"• **{f['nome']}** → _\"{f['trigger']}\"_\n"
            total_funcs += 1
        result += "\n"

    result += f"---\n**Totale: {total_funcs} funzioni!**\n"
    result += "Chiedi \"funzioni [categoria]\" per dettagli."

    # Versione parlata breve
    categorie = [c.split(' ', 1)[1] for c in list(FUNZIONALITA.keys())[:6]]
    spoken = f"Ho {total_funcs} funzioni! Categorie: {', '.join(categorie)} e altre. "
    spoken += "Quale categoria ti interessa?"

    return ActionResponse(Action.RESPONSE, result, spoken)
