"""
Sistema di Profili Skill per Xiaozhi Chatbot

Permette di caricare solo le funzioni rilevanti per il tipo di utilizzo,
riducendo conflitti di intent e migliorando le performance.

Ogni profilo definisce ~10-15 funzioni core + le funzioni base sempre attive.
"""

# ============================================================
# FUNZIONI SEMPRE ATTIVE (Core System)
# Queste sono SEMPRE disponibili in ogni profilo
# ============================================================
CORE_FUNCTIONS = [
    # Sistema e gestione
    "risposta_ai",          # Fallback AI per domande generiche
    "handle_exit_intent",   # Gestione uscita
    "change_role",          # Cambio personalità base
    "personalita_multiple", # Personalità divertenti (pirata, ubriaco, robot...)
    "sommario_funzioni",    # Elenco funzioni disponibili
    "cambia_profilo",       # Gestione profili skill
    "aiuto_profilo",        # Aiuto vocale interattivo

    # Easter egg e divertimento
    "easter_egg_folli",     # Litigio, insulti amichevoli, profezie
    "giannino_easter_egg",  # Easter egg Giannino

    # Utilità base essenziali
    "web_search",           # Ricerca web
    "meteo_italia",         # Meteo
    "timer_sveglia",        # Timer e sveglie
    "calcolatrice",         # Calcoli base
]

# ============================================================
# PROFILI SKILL
# ============================================================

SKILL_PROFILES = {

    # ----------------------------------------------------------
    # ASSISTENTE GENERALE (Default) - ~20 funzioni
    # ----------------------------------------------------------
    "generale": {
        "nome": "Assistente Generale",
        "descrizione": "Profilo bilanciato per uso quotidiano",
        "icona": "🏠",
        "functions": [
            # Informazioni
            "notizie_italia",
            "curiosita",
            "accadde_oggi",

            # Utilità
            "convertitore",
            "promemoria",
            "note_vocali",
            "lista_spesa",

            # Intrattenimento leggero
            "barzelletta_bambini",
            "radio_italia",
            "frase_del_giorno",

            # Cultura
            "ricette",
            "proverbi_italiani",
        ],
    },

    # ----------------------------------------------------------
    # ASSISTENTE ANZIANI - Semplificato e rassicurante
    # ----------------------------------------------------------
    "anziani": {
        "nome": "Compagno Anziani",
        "descrizione": "Interfaccia semplice, funzioni di supporto e compagnia",
        "icona": "👴",
        "functions": [
            # Compagnia e supporto
            "intrattenitore_anziani",
            "compagno_notturno",
            "supporto_emotivo",
            "chiacchierata",

            # Salute
            "promemoria_farmaci",
            "check_benessere",
            "ginnastica_dolce",

            # Emergenza
            "emergenza_rapida",
            "numeri_utili",
            "sos_emergenza",

            # Memoria
            "ricordami",
            "cosa_ricordi",

            # Intrattenimento semplice
            "radio_italia",
            "santo_del_giorno",
            "proverbi_italiani",
        ],
    },

    # ----------------------------------------------------------
    # BAMBINI - Contenuti sicuri e educativi
    # ----------------------------------------------------------
    "bambini": {
        "nome": "Amico Bambini",
        "descrizione": "Contenuti adatti ai bambini, educativi e divertenti",
        "icona": "🧒",
        "functions": [
            # Storie e creatività
            "storie_bambini",
            "genera_rime",

            # Giochi educativi
            "venti_domande",
            "quiz_trivia",
            "memory_vocale",
            "impiccato",

            # Divertimento
            "barzelletta_bambini",
            "versi_animali",
            "curiosita",
            "dado",

            # Apprendimento
            "convertitore",
            "traduttore_realtime",
        ],
    },

    # ----------------------------------------------------------
    # INTRATTENIMENTO - Giochi e divertimento
    # ----------------------------------------------------------
    "intrattenimento": {
        "nome": "Centro Giochi",
        "descrizione": "Giochi, quiz, barzellette e divertimento",
        "icona": "🎮",
        "functions": [
            # Giochi complessi
            "battaglia_navale",
            "chi_vuol_essere",
            "cruciverba_vocale",
            "venti_domande",
            "impiccato",
            "memory_vocale",

            # Quiz e trivia
            "quiz_trivia",
            "allenamento_mentale",

            # Umorismo
            "barzelletta_adulti",
            "barzelletta_bambini",
            "osterie_goliardiche",

            # Casualità
            "dado",
            "oracolo",

            # Musica
            "karaoke",
            "radio_italia",
        ],
    },

    # ----------------------------------------------------------
    # PRODUTTIVITÀ - Organizzazione e lavoro
    # ----------------------------------------------------------
    "produttivita": {
        "nome": "Assistente Produttivo",
        "descrizione": "Organizzazione, promemoria, note e gestione tempo",
        "icona": "📋",
        "functions": [
            # Tempo
            "timer_sveglia",
            "promemoria",
            "agenda_eventi",
            "briefing_mattutino",
            "routine_mattutina",

            # Note e memoria
            "note_vocali",
            "diario_vocale",
            "ricordami",
            "cosa_ricordi",

            # Liste
            "lista_spesa",
            "shopping_vocale",

            # Contatti
            "rubrica_vocale",

            # Ricerca
            "leggi_pagina",
        ],
    },

    # ----------------------------------------------------------
    # CULTURA ITALIANA - Focus Italia
    # ----------------------------------------------------------
    "cultura_italiana": {
        "nome": "Italia 360°",
        "descrizione": "Notizie, cultura, cucina e tradizioni italiane",
        "icona": "🇮🇹",
        "functions": [
            # Media
            "radio_italia",
            "notizie_italia",
            "podcast_italia",

            # Cucina
            "ricette",
            "ricette_ingredienti",
            "guida_ristoranti",

            # Cultura
            "proverbi_italiani",
            "santo_del_giorno",
            "accadde_oggi",
            "osterie_goliardiche",

            # Turismo
            "guida_turistica",

            # Curiosità
            "oroscopo",
            "lotto_estrazioni",
            "frase_del_giorno",
        ],
    },

    # ----------------------------------------------------------
    # BENESSERE - Salute mentale e fisica
    # ----------------------------------------------------------
    "benessere": {
        "nome": "Coach Benessere",
        "descrizione": "Meditazione, supporto emotivo, salute",
        "icona": "🧘",
        "functions": [
            # Meditazione e relax
            "meditazione",
            "suoni_ambiente",
            "compagno_notturno",

            # Supporto emotivo
            "supporto_emotivo",
            "chiacchierata",
            "complimenti",

            # Tracking
            "diario_umore",
            "check_benessere",
            "conta_acqua",

            # Fitness
            "ginnastica_dolce",

            # Farmaci
            "promemoria_farmaci",

            # Motivazione
            "frase_del_giorno",
            "allenamento_mentale",
        ],
    },

    # ----------------------------------------------------------
    # SMART HOME - Domotica e IoT
    # ----------------------------------------------------------
    "smart_home": {
        "nome": "Casa Intelligente",
        "descrizione": "Controllo domotica, sensori, automazioni",
        "icona": "🏡",
        "functions": [
            # Domotica base
            "domotica",
            "stato_casa",

            # Home Assistant
            "hass_get_state",
            "hass_set_state",

            # Sensori (quando mesh attivo)
            "leggi_sensore",
            "storico_sensore",
            "imposta_allarme_sensore",

            # Mesh network
            "panoramica_casa_mesh",
            "stato_rete_mesh",
            "leggi_sensore_mesh",
            "comando_attuatore_mesh",

            # Utility
            "briefing_mattutino",
            "routine_mattutina",
        ],
    },

    # ----------------------------------------------------------
    # INTERPRETE - Focus traduzione
    # ----------------------------------------------------------
    "interprete": {
        "nome": "Interprete Multilingue",
        "descrizione": "Modalità traduzione real-time, minime distrazioni",
        "icona": "🌍",
        "functions": [
            # Traduzione
            "traduttore_realtime",

            # Solo funzioni essenziali
            "convertitore",  # Per valute
            "numeri_utili",  # Emergenze

            # Info viaggio
            "guida_turistica",
            "guida_ristoranti",
        ],
    },

    # ----------------------------------------------------------
    # CUCINA - Chef virtuale
    # ----------------------------------------------------------
    "cucina": {
        "nome": "Chef Virtuale",
        "descrizione": "Ricette, timer cottura, lista spesa",
        "icona": "👨‍🍳",
        "functions": [
            # Ricette
            "ricette",
            "ricette_ingredienti",
            "cooking_companion",

            # Spesa
            "lista_spesa",
            "shopping_vocale",

            # Timer
            "timer_sveglia",

            # Conversioni
            "convertitore",
            "calcolatrice",

            # Ristoranti
            "guida_ristoranti",

            # Info
            "curiosita",
        ],
    },

    # ----------------------------------------------------------
    # NOTTE - Modalità notturna
    # ----------------------------------------------------------
    "notte": {
        "nome": "Compagno Notturno",
        "descrizione": "Funzioni rilassanti per la notte, voce soft",
        "icona": "🌙",
        "functions": [
            # Relax
            "compagno_notturno",
            "meditazione",
            "suoni_ambiente",

            # Storie
            "storie_bambini",

            # Supporto
            "supporto_emotivo",
            "chiacchierata",

            # Timer
            "timer_sveglia",  # Sveglia

            # Minimo essenziale
            "emergenza_rapida",
        ],
    },
}


def get_profile_functions(profile_name: str) -> list:
    """
    Ritorna la lista completa di funzioni per un profilo.
    Include sempre CORE_FUNCTIONS + funzioni specifiche del profilo.
    """
    if profile_name not in SKILL_PROFILES:
        profile_name = "generale"

    profile = SKILL_PROFILES[profile_name]
    functions = list(CORE_FUNCTIONS)  # Copia core

    # Aggiungi funzioni profilo (evita duplicati)
    for func in profile["functions"]:
        if func not in functions:
            functions.append(func)

    return functions


def get_all_profiles() -> dict:
    """Ritorna tutti i profili disponibili"""
    return {
        name: {
            "nome": p["nome"],
            "descrizione": p["descrizione"],
            "icona": p["icona"],
            "num_functions": len(CORE_FUNCTIONS) + len(p["functions"])
        }
        for name, p in SKILL_PROFILES.items()
    }


def get_profile_info(profile_name: str) -> dict:
    """Ritorna info dettagliate su un profilo"""
    if profile_name not in SKILL_PROFILES:
        return None

    profile = SKILL_PROFILES[profile_name]
    return {
        "nome": profile["nome"],
        "descrizione": profile["descrizione"],
        "icona": profile["icona"],
        "core_functions": CORE_FUNCTIONS,
        "profile_functions": profile["functions"],
        "total_functions": len(get_profile_functions(profile_name))
    }
