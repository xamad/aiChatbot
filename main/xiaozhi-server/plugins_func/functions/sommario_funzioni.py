"""
Sommario Funzioni Plugin - Elenca tutte le funzionalità disponibili
Aiuta l'utente a scoprire cosa può fare il chatbot
Ora profile-aware: mostra solo le funzioni del profilo attivo
"""

from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

# Import profilo per verificare profilo attivo
try:
    from plugins_func.functions.cambia_profilo import get_device_profile, get_session_id, get_profile_info
    PROFILE_AWARE = True
except ImportError:
    PROFILE_AWARE = False
    def get_device_profile(d): return "generale"
    def get_session_id(c): return "default"
    def get_profile_info(p): return None

TAG = __name__
logger = setup_logging()

# Catalogo completo delle funzionalità organizzate per categoria
# ESCLUSI: Easter egg (giannini, osterie goliardiche, easter_egg_folli)
FUNZIONALITA = {
    "🎵 Audio & Media": [
        {"nome": "Radio Italia", "trigger": "metti radio deejay", "attivazione": "Di': metti radio [nome] - es: metti radio zeta, metti rtl", "desc": "Streaming radio italiane"},
        {"nome": "Podcast", "trigger": "ascolta podcast", "attivazione": "Di': ascolta podcast [nome programma]", "desc": "Programmi RAI"},
        {"nome": "Karaoke", "trigger": "karaoke", "attivazione": "Di': karaoke [titolo canzone]", "desc": "Testi canzoni"},
        {"nome": "Suoni Ambiente", "trigger": "suono della pioggia", "attivazione": "Di': metti suono [tipo] - pioggia, mare, foresta, camino", "desc": "ASMR e relax"},
        {"nome": "Versi Animali", "trigger": "fai il verso del gallo", "attivazione": "Di': fai il verso del [animale]", "desc": "Imita animali"},
    ],
    "🖼️ Display & Immagini": [
        {"nome": "Cerca Immagini", "trigger": "cerca immagini di gatti", "attivazione": "Di': cerca immagini di [soggetto] - mostra slideshow sul display", "desc": "Slideshow immagini"},
        {"nome": "Cerca GIF", "trigger": "cerca gif di gatti", "attivazione": "Di': cerca gif di [soggetto] - GIF animate sul display", "desc": "GIF animate"},
    ],
    "🎮 Giochi": [
        {"nome": "Quiz Trivia", "trigger": "facciamo un quiz", "attivazione": "Di': facciamo un quiz - poi rispondi A, B, C o D", "desc": "Domande cultura generale"},
        {"nome": "Impiccato", "trigger": "giochiamo all'impiccato", "attivazione": "Di': giochiamo all'impiccato - poi dì le lettere", "desc": "Indovina la parola"},
        {"nome": "20 Domande", "trigger": "giochiamo a 20 domande", "attivazione": "Di': giochiamo a 20 domande - rispondi sì o no", "desc": "Indovina con sì/no"},
        {"nome": "Battaglia Navale", "trigger": "battaglia navale", "attivazione": "Di': battaglia navale - poi coordinate come A5, B3", "desc": "Gioco classico"},
        {"nome": "Milionario", "trigger": "chi vuol essere milionario", "attivazione": "Di': chi vuol essere milionario - usa aiuti: 50/50, telefono, pubblico", "desc": "Quiz con aiuti"},
        {"nome": "Cruciverba", "trigger": "cruciverba", "attivazione": "Di': cruciverba - indovina dalle definizioni", "desc": "Definizioni"},
        {"nome": "Dado", "trigger": "lancia un dado", "attivazione": "Di': lancia un dado oppure lancia 2 dadi", "desc": "Tira dadi"},
        {"nome": "Oracolo", "trigger": "oracolo, devo...?", "attivazione": "Di': oracolo, devo [domanda sì/no]?", "desc": "Risposte mistiche"},
    ],
    "📰 Informazioni": [
        {"nome": "Notizie", "trigger": "dimmi le notizie", "attivazione": "Di': dimmi le notizie oppure notizie di oggi", "desc": "News italiane"},
        {"nome": "Meteo", "trigger": "che tempo fa a Milano?", "attivazione": "Di': che tempo fa a [città]? oppure meteo [città]", "desc": "Previsioni"},
        {"nome": "Oroscopo", "trigger": "oroscopo leone", "attivazione": "Di': oroscopo [segno] - ariete, toro, gemelli...", "desc": "Segni zodiacali"},
        {"nome": "Santo del Giorno", "trigger": "che santo è oggi?", "attivazione": "Di': che santo è oggi? oppure santo del giorno", "desc": "Onomastici"},
        {"nome": "Accadde Oggi", "trigger": "cosa accadde oggi?", "attivazione": "Di': cosa accadde oggi? oppure accadde oggi", "desc": "Storia"},
        {"nome": "Lotto", "trigger": "estrazioni lotto", "attivazione": "Di': estrazioni lotto oppure numeri del lotto", "desc": "Numeri estratti"},
        {"nome": "Curiosità", "trigger": "dimmi qualcosa di interessante", "attivazione": "Di': dimmi una curiosità oppure lo sapevi che", "desc": "Fatti curiosi"},
        {"nome": "Proverbi", "trigger": "dimmi un proverbio", "attivazione": "Di': dimmi un proverbio oppure proverbio del giorno", "desc": "Saggezza popolare"},
    ],
    "🍳 Cucina": [
        {"nome": "Ricette", "trigger": "ricetta carbonara", "attivazione": "Di': ricetta [piatto] - es: ricetta tiramisù", "desc": "Come si prepara"},
        {"nome": "Ricette Ingredienti", "trigger": "cosa cucino con uova e pasta?", "attivazione": "Di': cosa cucino con [ingredienti]?", "desc": "Idee con ingredienti"},
        {"nome": "Cooking Companion", "trigger": "cuciniamo la carbonara", "attivazione": "Di': cuciniamo [piatto] - guida passo-passo interattiva", "desc": "Guida passo-passo"},
    ],
    "🛠️ Utilità": [
        {"nome": "Timer", "trigger": "timer 5 minuti", "attivazione": "Di': timer [durata] - es: timer 10 minuti", "desc": "Conto alla rovescia"},
        {"nome": "Sveglia", "trigger": "svegliami tra 10 minuti", "attivazione": "Di': svegliami tra [durata] oppure svegliami alle [ora]", "desc": "Avvisi"},
        {"nome": "Promemoria", "trigger": "ricordami di chiamare Marco", "attivazione": "Di': ricordami di [azione] tra [tempo]", "desc": "Azioni future"},
        {"nome": "Memoria", "trigger": "ricordami che le chiavi sono nel cassetto", "attivazione": "Di': ricordami che [informazione]", "desc": "Salva informazioni"},
        {"nome": "Dove Ho Messo", "trigger": "dove ho messo le chiavi?", "attivazione": "Di': dove ho messo [oggetto]? - cerca nella memoria", "desc": "Cerca nella memoria"},
        {"nome": "Calcolatrice", "trigger": "quanto fa 25 per 4?", "attivazione": "Di': quanto fa [operazione]? - somma, moltiplica, dividi", "desc": "Calcoli"},
        {"nome": "Convertitore", "trigger": "converti 100 euro in dollari", "attivazione": "Di': converti [valore] [unità] in [unità]", "desc": "Valute/unità"},
        {"nome": "Lista Spesa", "trigger": "aggiungi latte alla spesa", "attivazione": "Di': aggiungi [prodotto] alla spesa oppure leggi la spesa", "desc": "Lista spesa"},
        {"nome": "Note Vocali", "trigger": "prendi nota", "attivazione": "Di': prendi nota [testo] oppure leggi le note", "desc": "Appunti"},
        {"nome": "Agenda", "trigger": "cosa ho in agenda?", "attivazione": "Di': cosa ho in agenda? oppure aggiungi appuntamento", "desc": "Appuntamenti"},
        {"nome": "Rubrica", "trigger": "numero di mamma", "attivazione": "Di': numero di [contatto] oppure salva numero di [nome]", "desc": "Contatti"},
    ],
    "🌍 Traduzione & Ricerca": [
        {"nome": "Traduttore", "trigger": "traduci ciao in inglese", "attivazione": "Di': traduci [frase] in [lingua]", "desc": "Traduzioni"},
        {"nome": "Traduttore Realtime", "trigger": "modalità traduttore", "attivazione": "Di': modalità traduttore [lingua] - traduce tutto in tempo reale", "desc": "Traduzione continua"},
        {"nome": "Web Search", "trigger": "cerca su internet", "attivazione": "Di': cerca su internet [argomento]", "desc": "Ricerca web"},
        {"nome": "Risposta AI", "trigger": "spiegami la blockchain", "attivazione": "Di': spiegami [argomento] oppure cos'è [cosa]?", "desc": "Domande all'AI"},
    ],
    "🧘 Benessere": [
        {"nome": "Meditazione", "trigger": "facciamo meditazione", "attivazione": "Di': facciamo meditazione oppure respirazione guidata", "desc": "Respirazione guidata"},
        {"nome": "Supporto Emotivo", "trigger": "sono ansioso", "attivazione": "Di': sono ansioso/triste/stressato - ti aiuto", "desc": "Conforto"},
        {"nome": "Compagno", "trigger": "mi sento solo", "attivazione": "Di': mi sento solo oppure facciamo due chiacchiere", "desc": "Compagnia"},
        {"nome": "Compagno Notturno", "trigger": "non riesco a dormire", "attivazione": "Di': non riesco a dormire - ti aiuto a rilassarti", "desc": "Aiuto insonnia"},
        {"nome": "Ginnastica Dolce", "trigger": "facciamo ginnastica", "attivazione": "Di': facciamo ginnastica dolce - esercizi guidati", "desc": "Esercizi leggeri"},
    ],
    "🏠 Casa Smart": [
        {"nome": "Domotica", "trigger": "accendi luce cucina", "attivazione": "Di': accendi/spegni [dispositivo] oppure stato [dispositivo]", "desc": "Controllo luci"},
        {"nome": "Numeri Utili", "trigger": "numero carabinieri", "attivazione": "Di': numero [servizio] - carabinieri, polizia, ambulanza", "desc": "Emergenze"},
    ],
    "🗺️ Guide": [
        {"nome": "Guida Turistica", "trigger": "cosa visitare a Roma?", "attivazione": "Di': cosa visitare a [città]?", "desc": "Monumenti"},
        {"nome": "Ristoranti", "trigger": "dove mangiare a Napoli?", "attivazione": "Di': dove mangiare a [città]? oppure ristoranti a [città]", "desc": "Locali"},
    ],
    "👶 Bambini & Famiglia": [
        {"nome": "Storie", "trigger": "raccontami una storia", "attivazione": "Di': raccontami una storia oppure favola della buonanotte", "desc": "Favole"},
        {"nome": "Barzellette", "trigger": "raccontami una barzelletta", "attivazione": "Di': raccontami una barzelletta oppure fammi ridere", "desc": "Battute"},
        {"nome": "Frase del Giorno", "trigger": "frase del giorno", "attivazione": "Di': frase del giorno oppure citazione motivazionale", "desc": "Citazioni"},
    ],
    "🎭 Personalità": [
        {"nome": "Cambia Personalità", "trigger": "parla come un pirata", "attivazione": "Di': parla come [personaggio] - pirata, robot, bambino", "desc": "Voci diverse"},
        {"nome": "Torna Normale", "trigger": "torna normale", "attivazione": "Di': torna normale oppure reset personalità", "desc": "Reset voce"},
        {"nome": "Chi Sono", "trigger": "tu chi sei?", "attivazione": "Di': tu chi sei? oppure presentati", "desc": "Presentazione"},
    ],
}

SOMMARIO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "sommario_funzioni",
        "description": (
            "ATTIVARE per elencare tutte le funzionalità disponibili del chatbot. "
            "TRIGGER ESATTI: 'quali funzioni hai', 'cosa sai fare', 'help', 'aiuto', "
            "'elenca funzioni', 'lista funzioni', 'mostrami le funzioni', 'cosa fai', "
            "'come ti uso', 'che cosa puoi fare', 'funzionalità', 'comandi disponibili', "
            "'come si attiva [funzione]', 'come uso [funzione]'. "
            "CATEGORIE: audio, giochi, info, cucina, utilità, traduzione, benessere, casa, guide, bambini, personalità, immagini. "
            "ESEMPIO: 'come si attiva la radio' → categoria='audio'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "categoria": {
                    "type": "string",
                    "description": "Categoria specifica o nome funzione da spiegare"
                },
                "funzione_specifica": {
                    "type": "string",
                    "description": "Nome della funzione di cui spiegare l'attivazione (es: radio, timer, meteo)"
                }
            },
            "required": [],
        },
    },
}

@register_function("sommario_funzioni", SOMMARIO_FUNCTION_DESC, ToolType.WAIT)
def sommario_funzioni(conn, categoria: str = None, funzione_specifica: str = None):
    logger.bind(tag=TAG).info(f"Sommario: categoria={categoria}, funzione={funzione_specifica}")

    # Ottieni profilo attivo
    device_id = get_session_id(conn) if PROFILE_AWARE else "default"
    current_profile = get_device_profile(device_id) if PROFILE_AWARE else "generale"
    profile_info = get_profile_info(current_profile) if PROFILE_AWARE else None

    # Header con info profilo
    profile_header = ""
    profile_spoken = ""
    if profile_info and current_profile != "generale":
        profile_header = f"📋 **Profilo attivo:** {profile_info['icona']} {profile_info['nome']}\n"
        profile_header += f"_({profile_info['total_functions']} funzioni disponibili)_\n\n"
        profile_spoken = f"Con il profilo {profile_info['nome']} attivo, "

    # Se cerca una funzione specifica (ricerca fuzzy)
    if funzione_specifica:
        func_lower = funzione_specifica.lower().strip()
        matches = []

        # Sinonimi comuni
        sinonimi = {
            'radio': ['radio', 'streaming', 'deejay', 'musica'],
            'meteo': ['meteo', 'tempo', 'previsioni', 'clima'],
            'foto': ['immagini', 'foto', 'picture', 'slideshow'],
            'gif': ['gif', 'animazioni', 'animate'],
            'timer': ['timer', 'sveglia', 'allarme', 'countdown'],
            'notizie': ['notizie', 'news', 'giornale', 'telegiornale'],
            'giochi': ['quiz', 'giochi', 'impiccato', 'battaglia'],
            'traduttore': ['traduttore', 'traduzione', 'traduci'],
        }

        # Espandi termine con sinonimi
        search_terms = [func_lower]
        for key, syns in sinonimi.items():
            if func_lower in syns or any(s in func_lower for s in syns):
                search_terms.extend(syns)

        for cat_name, funcs in FUNZIONALITA.items():
            for f in funcs:
                nome_lower = f['nome'].lower()
                trigger_lower = f.get('trigger', '').lower()
                desc_lower = f.get('desc', '').lower()
                attivazione_lower = f.get('attivazione', '').lower()

                # Cerca in tutti i campi
                for term in search_terms:
                    if (term in nome_lower or
                        term in trigger_lower or
                        term in desc_lower or
                        term in attivazione_lower or
                        nome_lower in term):
                        matches.append(f)
                        break

        if matches:
            # Se trovato uno solo, mostra dettagli
            if len(matches) == 1:
                f = matches[0]
                attivazione = f.get('attivazione', f"Di': {f['trigger']}")
                result = f"**{f['nome']}**\n\n"
                result += f"📝 {f['desc']}\n\n"
                result += f"🎤 **Come attivare:** {attivazione}\n\n"
                result += f"💡 **Esempio:** \"{f['trigger']}\""
                spoken = f"Per usare {f['nome']}: {attivazione}"
                return ActionResponse(Action.RESPONSE, result, spoken)
            else:
                # Più risultati - mostra lista
                result = f"Ho trovato {len(matches)} funzioni per '{funzione_specifica}':\n\n"
                spoken_parts = []
                for f in matches[:5]:  # Max 5
                    attivazione = f.get('attivazione', f"Di': {f['trigger']}")
                    result += f"• **{f['nome']}**: {attivazione}\n\n"
                    spoken_parts.append(f"{f['nome']}")
                spoken = f"Ho trovato: {', '.join(spoken_parts)}. Quale ti interessa?"
                return ActionResponse(Action.RESPONSE, result, spoken)

        # Non trovata - suggerisci categorie
        return ActionResponse(Action.RESPONSE,
            f"Non ho trovato '{funzione_specifica}'. Prova:\n- 'funzioni audio' per radio/podcast\n- 'funzioni giochi' per quiz/giochi\n- 'quali funzioni hai' per tutto",
            f"Non ho trovato {funzione_specifica}. Dimmi: funzioni audio, funzioni giochi, o quali funzioni hai.")

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
            result = profile_header + f"**{found_cat}**\n\n"
            spoken_parts = []

            for f in found_funcs:
                attivazione = f.get('attivazione', f"Di': {f['trigger']}")
                result += f"• **{f['nome']}**: {f['desc']}\n"
                result += f"  🎤 {attivazione}\n\n"
                spoken_parts.append(f"{f['nome']}: {attivazione}")

            spoken = profile_spoken + f"In {found_cat.split(' ', 1)[1]}: " + ". ".join(spoken_parts[:3])
            if len(spoken_parts) > 3:
                spoken += f". E altre {len(spoken_parts) - 3} funzioni."

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            categorie = [c.split(' ', 1)[1] for c in FUNZIONALITA.keys()]
            return ActionResponse(Action.RESPONSE,
                profile_header + f"Categoria non trovata. Categorie: {', '.join(categorie)}",
                profile_spoken + f"Non ho quella categoria. Prova: {', '.join(categorie[:5])}")

    # Elenco completo con trigger
    result = profile_header + "# 🤖 TUTTE LE MIE FUNZIONALITÀ\n\n"

    total_funcs = 0
    for cat_name, funcs in FUNZIONALITA.items():
        result += f"## {cat_name}\n"
        for f in funcs:
            result += f"• **{f['nome']}** → _\"{f['trigger']}\"_\n"
            total_funcs += 1
        result += "\n"

    result += f"---\n**Totale: {total_funcs} funzioni!**\n"

    # Aggiungi info su profilo
    if current_profile != "generale" and profile_info:
        result += f"\n💡 _Alcune funzioni potrebbero non essere attive con il profilo {profile_info['nome']}._\n"
        result += "_Dì 'cambia profilo in generale' per attivarle tutte._"

    result += "\nChiedi \"funzioni [categoria]\" per dettagli."

    # Versione parlata breve
    categorie = [c.split(' ', 1)[1] for c in list(FUNZIONALITA.keys())[:6]]
    spoken = profile_spoken + f"Ho {total_funcs} funzioni! Categorie: {', '.join(categorie)} e altre. "
    spoken += "Quale categoria ti interessa?"

    return ActionResponse(Action.RESPONSE, result, spoken)
