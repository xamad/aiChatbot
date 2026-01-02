"""
Sommario Funzioni Plugin - Elenca tutte le funzionalità disponibili
Aiuta l'utente a scoprire cosa può fare il chatbot
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Catalogo completo delle funzionalità organizzate per categoria
FUNZIONALITA = {
    "🎵 Intrattenimento Audio": [
        {"nome": "Radio Italia", "comando": "metti radio 105", "desc": "Streaming radio italiane (105, Virgin, RTL, RAI...)"},
        {"nome": "Podcast", "comando": "metti un podcast", "desc": "Programmi RAI in streaming"},
        {"nome": "Musica", "comando": "cerca musica...", "desc": "Cerca e riproduci musica"},
    ],
    "🎮 Giochi": [
        {"nome": "Quiz Trivia", "comando": "facciamo un quiz", "desc": "Quiz cultura, Italia, sport, scienza"},
        {"nome": "Cruciverba", "comando": "giochiamo a cruciverba", "desc": "Definizioni stile Settimana Enigmistica"},
        {"nome": "Impiccato", "comando": "giochiamo all'impiccato", "desc": "Indovina la parola lettera per lettera"},
        {"nome": "Venti Domande", "comando": "giochiamo a 20 domande", "desc": "Indovina con sì/no"},
        {"nome": "Memory", "comando": "giochiamo a memory", "desc": "Allena la memoria con sequenze"},
        {"nome": "Battaglia Navale", "comando": "battaglia navale", "desc": "Gioco classico vocale"},
        {"nome": "Chi Vuol Essere", "comando": "chi vuol essere milionario", "desc": "Quiz con aiuti"},
        {"nome": "Oracolo", "comando": "oracolo, devo...?", "desc": "Risposte mistiche alle tue domande"},
        {"nome": "Dado", "comando": "lancia un dado", "desc": "Lancia dadi per giochi"},
    ],
    "📚 Cultura e Info": [
        {"nome": "Notizie", "comando": "dimmi le notizie", "desc": "Ultime notizie italiane"},
        {"nome": "Meteo", "comando": "che tempo fa a Roma?", "desc": "Previsioni meteo"},
        {"nome": "Ricette", "comando": "ricetta carbonara", "desc": "Ricette cucina italiana"},
        {"nome": "Oroscopo", "comando": "oroscopo ariete", "desc": "Oroscopo giornaliero"},
        {"nome": "Santo del Giorno", "comando": "che santo è oggi?", "desc": "Santo e onomastici"},
        {"nome": "Accadde Oggi", "comando": "cosa accadde oggi?", "desc": "Eventi storici di oggi"},
        {"nome": "Proverbi", "comando": "dimmi un proverbio", "desc": "Proverbi italiani con spiegazione"},
        {"nome": "Curiosità", "comando": "dimmi una curiosità", "desc": "Fatti interessanti"},
        {"nome": "Lotto", "comando": "estrazioni lotto", "desc": "Ultime estrazioni"},
    ],
    "🛠️ Utilità": [
        {"nome": "Timer/Sveglia", "comando": "timer 5 minuti", "desc": "Timer e sveglie"},
        {"nome": "Promemoria", "comando": "ricordami di...", "desc": "Promemoria vocali"},
        {"nome": "Calcolatrice", "comando": "quanto fa 25 per 4?", "desc": "Calcoli matematici"},
        {"nome": "Convertitore", "comando": "converti 100 euro in dollari", "desc": "Valute, unità, temperature"},
        {"nome": "Traduttore", "comando": "traduci ciao in inglese", "desc": "Traduzioni"},
        {"nome": "Lista Spesa", "comando": "aggiungi pane alla lista", "desc": "Gestione lista spesa"},
        {"nome": "Note Vocali", "comando": "salva nota...", "desc": "Appunti vocali"},
        {"nome": "Rubrica", "comando": "salva numero mamma", "desc": "Rubrica telefonica vocale"},
        {"nome": "Agenda", "comando": "aggiungi appuntamento", "desc": "Calendario eventi"},
        {"nome": "Cerca Web", "comando": "cerca su internet...", "desc": "Ricerche web"},
    ],
    "🏥 Salute e Benessere": [
        {"nome": "Farmaci", "comando": "ricordami la pastiglia alle 8", "desc": "Promemoria medicine"},
        {"nome": "Diario Umore", "comando": "oggi mi sento felice", "desc": "Traccia il tuo umore"},
        {"nome": "Conta Acqua", "comando": "ho bevuto un bicchiere", "desc": "Conta bicchieri d'acqua"},
        {"nome": "Ginnastica Dolce", "comando": "facciamo ginnastica", "desc": "Esercizi guidati"},
        {"nome": "Meditazione", "comando": "facciamo meditazione", "desc": "Respirazione e relax"},
        {"nome": "Check Benessere", "comando": "come sto?", "desc": "Controllo periodico"},
    ],
    "👶 Per Bambini e Anziani": [
        {"nome": "Storie Bambini", "comando": "raccontami una storia", "desc": "Favole classiche"},
        {"nome": "Barzellette", "comando": "raccontami una barzelletta", "desc": "Battute e barzellette"},
        {"nome": "Intrattenitore", "comando": "tienimi compagnia", "desc": "Modalità compagnia per anziani"},
        {"nome": "Complimenti", "comando": "fammi un complimento", "desc": "Frasi positive"},
        {"nome": "Routine Mattutina", "comando": "buongiorno", "desc": "Briefing giornaliero"},
    ],
    "🆘 Emergenza": [
        {"nome": "SOS", "comando": "aiuto / emergenza", "desc": "Contatta familiari"},
        {"nome": "Numeri Utili", "comando": "numeri emergenza", "desc": "118, Carabinieri, ecc."},
    ],
    "🎲 Fun": [
        {"nome": "Frase del Giorno", "comando": "frase del giorno", "desc": "Citazioni motivazionali"},
        {"nome": "Genera Rime", "comando": "trova rime per amore", "desc": "Trova rime"},
    ],
}

SOMMARIO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "sommario_funzioni",
        "description": (
            "Elenca TUTTE le funzionalità disponibili del chatbot."
            "Usare quando: cosa sai fare, quali funzioni hai, aiuto, help, cosa puoi fare, "
            "elenca funzioni, menu, comandi, cosa fai, funzionalità, capabilities, "
            "che sai fare, mostrami le funzioni"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "description": "Categoria specifica da mostrare (opzionale)"
                },
                "dettaglio": {
                    "type": "boolean",
                    "description": "Se mostrare dettagli completi"
                }
            },
            "required": [],
        },
    },
}

@register_function("sommario_funzioni", SOMMARIO_FUNCTION_DESC, ToolType.WAIT)
def sommario_funzioni(conn, categoria: str = None, dettaglio: bool = False):
    logger.bind(tag=TAG).info(f"Sommario: categoria={categoria}, dettaglio={dettaglio}")

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
            result = f"{found_cat}:\n\n"
            spoken = f"Ecco le funzioni di {found_cat.split(' ', 1)[1] if ' ' in found_cat else found_cat}: "

            for f in found_funcs:
                result += f"• **{f['nome']}**: {f['desc']}\n"
                result += f"  Esempio: \"{f['comando']}\"\n\n"
                spoken += f"{f['nome']}, "

            spoken = spoken.rstrip(", ") + ". Quale vuoi provare?"

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            categorie = [c.split(' ', 1)[1] if ' ' in c else c for c in FUNZIONALITA.keys()]
            return ActionResponse(Action.RESPONSE,
                f"Categoria non trovata. Categorie: {', '.join(categorie)}",
                f"Non ho trovato quella categoria. Ho: {', '.join(categorie)}")

    # Sommario completo
    if dettaglio:
        result = "# 🤖 TUTTE LE MIE FUNZIONALITÀ\n\n"
        spoken = "Ecco tutto quello che so fare. "

        for cat_name, funcs in FUNZIONALITA.items():
            result += f"## {cat_name}\n"
            for f in funcs:
                result += f"• {f['nome']}: {f['desc']}\n"
            result += "\n"

        spoken += f"Ho {sum(len(f) for f in FUNZIONALITA.values())} funzioni in {len(FUNZIONALITA)} categorie. "
        spoken += "Chiedimi di una categoria specifica per i dettagli!"

        return ActionResponse(Action.RESPONSE, result, spoken)

    # Sommario breve
    result = "# 🤖 COSA POSSO FARE\n\n"
    spoken = "Posso aiutarti con: "

    total_funcs = 0
    categorie_brevi = []

    for cat_name, funcs in FUNZIONALITA.items():
        num = len(funcs)
        total_funcs += num
        # Rimuovi emoji
        cat_clean = cat_name.split(' ', 1)[1] if ' ' in cat_name else cat_name
        result += f"{cat_name} ({num} funzioni)\n"
        categorie_brevi.append(cat_clean)

    result += f"\n**Totale: {total_funcs} funzioni!**\n\n"
    result += "Di' \"dettagli [categoria]\" per saperne di più, oppure prova direttamente!"

    spoken += ", ".join(categorie_brevi[:5])
    spoken += f" e altro ancora! In totale {total_funcs} funzioni. Cosa ti interessa?"

    return ActionResponse(Action.RESPONSE, result, spoken)
