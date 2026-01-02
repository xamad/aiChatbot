"""
Chi Sono - Funzione di auto-presentazione del chatbot
Risponde a domande su identità, nome, funzionalità
"""

import os
import json
import glob
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

USER_PREFS_FILE = "/opt/xiaozhi-server/main/xiaozhi-server/data/user_preferences.json"
FUNCTIONS_DIR = "/opt/xiaozhi-server/main/xiaozhi-server/plugins_func/functions"

# Categorie funzioni per descrizione
CATEGORIE_FUNZIONI = {
    "media": {"nome": "Media e Audio", "funzioni": ["radio_italia", "podcast_italia", "cerca_musica", "karaoke"]},
    "info": {"nome": "Informazioni", "funzioni": ["meteo_italia", "notizie_italia", "oroscopo", "lotto_estrazioni", "accadde_oggi", "santo_del_giorno"]},
    "intrattenimento": {"nome": "Intrattenimento", "funzioni": ["barzelletta_bambini", "barzelletta_adulti", "quiz_trivia", "storie_bambini", "curiosita", "proverbi_italiani", "frase_del_giorno"]},
    "giochi": {"nome": "Giochi", "funzioni": ["impiccato", "battaglia_navale", "venti_domande", "cruciverba_vocale", "chi_vuol_essere", "dado", "memory_vocale"]},
    "utility": {"nome": "Utilità", "funzioni": ["timer_sveglia", "promemoria", "calcolatrice", "convertitore", "traduttore", "lista_spesa", "note_vocali", "rubrica_vocale", "agenda_eventi"]},
    "casa": {"nome": "Casa Smart", "funzioni": ["domotica"]},
    "benessere": {"nome": "Benessere", "funzioni": ["meditazione", "supporto_emotivo", "compagno_notturno", "check_benessere", "ginnastica_dolce", "conta_acqua"]},
    "cucina": {"nome": "Cucina", "funzioni": ["ricette", "ricette_ingredienti"]},
    "special": {"nome": "Speciali", "funzioni": ["giannino_easter_egg", "osterie_goliardiche", "sommario_funzioni", "intrattenitore_anziani", "complimenti"]},
    "guide": {"nome": "Guide", "funzioni": ["guida_turistica", "guida_ristoranti", "numeri_utili"]},
    "ricerca": {"nome": "Ricerca", "funzioni": ["web_search", "leggi_pagina"]},
}


def get_chatbot_info():
    """Ottiene informazioni sul chatbot dalle preferenze"""
    defaults = {
        "nome_chatbot": "Xiaozhi",
        "descrizione": "Sono un assistente vocale intelligente in italiano, creato per aiutarti e intrattenerti!",
        "disabled_functions": []
    }

    try:
        if os.path.exists(USER_PREFS_FILE):
            with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
                prefs = json.load(f)
                defaults.update(prefs)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore lettura preferenze: {e}")

    return defaults


def get_active_functions():
    """Ottiene lista funzioni attive"""
    prefs = get_chatbot_info()
    disabled = prefs.get("disabled_functions", [])

    available = []
    try:
        for f in glob.glob(os.path.join(FUNCTIONS_DIR, "*.py")):
            name = os.path.basename(f).replace(".py", "")
            if not name.startswith("_") and name not in ["register", "base", "chi_sono"]:
                if name not in disabled:
                    available.append(name)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore lettura funzioni: {e}")

    return available


def format_capabilities():
    """Formatta le funzionalità attive in modo leggibile"""
    active_funcs = get_active_functions()

    capabilities = []
    for cat_id, cat_info in CATEGORIE_FUNZIONI.items():
        cat_funcs = [f for f in cat_info["funzioni"] if f in active_funcs]
        if cat_funcs:
            capabilities.append(cat_info["nome"])

    return capabilities


CHI_SONO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "chi_sono",
        "description": (
            "身份介绍 / Presenta se stesso - chi è il chatbot, come si chiama, cosa sa fare. "
            "Use when: 'chi sei', 'come ti chiami', 'tu chi sei', 'presentati', "
            "'cosa sai fare', 'quali sono le tue funzioni', 'parlami di te', "
            "'chi sei tu', 'dimmi chi sei', 'che cos'è xiaozhi', 'cosa sei'"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dettagli": {
                    "type": "boolean",
                    "description": "Se includere lista dettagliata funzionalità"
                }
            },
            "required": []
        }
    }
}


@register_function('chi_sono', CHI_SONO_FUNCTION_DESC, ToolType.WAIT)
def chi_sono(conn, dettagli: bool = False):
    """Presenta il chatbot"""

    info = get_chatbot_info()
    nome = info.get("nome_chatbot", "Xiaozhi")
    descrizione = info.get("descrizione", "")

    capabilities = format_capabilities()
    active_count = len(get_active_functions())

    logger.bind(tag=TAG).info(f"Chi sono richiesto - Nome: {nome}, Funzioni attive: {active_count}")

    # Costruisce presentazione
    if descrizione:
        intro = f"Mi chiamo {nome}! {descrizione}"
    else:
        intro = f"Mi chiamo {nome}! Sono un assistente vocale intelligente in italiano."

    # Aggiungi funzionalità
    if capabilities:
        cap_text = ", ".join(capabilities[:-1])
        if len(capabilities) > 1:
            cap_text += f" e {capabilities[-1]}"
        else:
            cap_text = capabilities[0]

        func_intro = f"Posso aiutarti con {cap_text}."
    else:
        func_intro = "Posso aiutarti con tante cose!"

    # Esempi specifici basati su funzioni attive
    active_funcs = get_active_functions()
    examples = []

    if "radio_italia" in active_funcs:
        examples.append("sintonizzarti sulle radio italiane")
    if "meteo_italia" in active_funcs:
        examples.append("dirti le previsioni meteo")
    if "barzelletta_bambini" in active_funcs or "barzelletta_adulti" in active_funcs:
        examples.append("raccontarti barzellette")
    if "timer_sveglia" in active_funcs:
        examples.append("impostare timer e sveglie")
    if any(g in active_funcs for g in ["impiccato", "cruciverba_vocale", "quiz_trivia"]):
        examples.append("giocare insieme a giochi vocali")
    if "osterie_goliardiche" in active_funcs:
        examples.append("cantare canzoni goliardiche")
    if "ricette" in active_funcs or "ricette_ingredienti" in active_funcs:
        examples.append("suggerirti ricette")
    if "web_search" in active_funcs:
        examples.append("cercare informazioni sul web")

    if examples:
        example_text = "Per esempio posso " + ", ".join(examples[:4]) + "!"
    else:
        example_text = ""

    # Versione completa per display
    full_response = f"{intro}\n\n{func_intro}"
    if example_text:
        full_response += f"\n\n{example_text}"
    full_response += f"\n\n{active_count} funzionalità attive."

    # Versione parlata più naturale
    spoken = f"{intro} {func_intro}"
    if example_text:
        spoken += f" {example_text}"
    spoken += " Chiedimi quello che vuoi!"

    return ActionResponse(
        action=Action.RESPONSE,
        result=full_response,
        response=spoken
    )
