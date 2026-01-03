"""
AIUTO PROFILO - Guida vocale interattiva

Fornisce informazioni sul profilo attivo e i comandi disponibili.
Funziona in tutti i profili come funzione CORE.

Trigger: "aiuto", "help", "come funziona", "cosa puoi fare"
"""

import os
import json
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action

TAG = __name__
logger = setup_logging()

# Import skill profiles
try:
    from data.config.skill_profiles import SKILL_PROFILES, get_profile_info, CORE_FUNCTIONS
except ImportError:
    SKILL_PROFILES = {}
    CORE_FUNCTIONS = []
    def get_profile_info(p): return None

# Import per ottenere profilo device
try:
    from plugins_func.functions.cambia_profilo import get_device_profile, get_session_id
except ImportError:
    def get_device_profile(d): return "generale"
    def get_session_id(c): return "default"


# ============================================================
# COMANDI PER FUNZIONE - Dizionario trigger vocali
# ============================================================
FUNCTION_TRIGGERS = {
    # === CORE (sempre attive) ===
    "risposta_ai": {
        "nome": "Risposte AI",
        "triggers": ["chiedi a gpt...", "spiegami...", "cos'è...", "chi è..."],
        "descrizione": "Risponde a domande usando intelligenza artificiale"
    },
    "web_search": {
        "nome": "Ricerca Web",
        "triggers": ["cerca su internet...", "cercami...", "google..."],
        "descrizione": "Cerca informazioni sul web"
    },
    "meteo_italia": {
        "nome": "Meteo",
        "triggers": ["che tempo fa a...", "meteo", "previsioni"],
        "descrizione": "Previsioni meteo per città italiane"
    },
    "timer_sveglia": {
        "nome": "Timer",
        "triggers": ["timer 5 minuti", "svegliami tra...", "countdown"],
        "descrizione": "Imposta timer e sveglie"
    },
    "calcolatrice": {
        "nome": "Calcolatrice",
        "triggers": ["quanto fa...", "calcola...", "percentuale di..."],
        "descrizione": "Calcoli matematici"
    },
    "cambia_profilo": {
        "nome": "Profili",
        "triggers": ["cambia profilo in...", "elenco profili", "che profilo sono"],
        "descrizione": "Gestisce i profili skill"
    },
    "sommario_funzioni": {
        "nome": "Funzioni",
        "triggers": ["quali funzioni hai", "elenco funzioni", "funzioni disponibili"],
        "descrizione": "Mostra tutte le funzioni disponibili"
    },

    # === INTRATTENIMENTO ===
    "barzelletta_bambini": {
        "nome": "Barzellette",
        "triggers": ["raccontami una barzelletta", "fammi ridere"],
        "descrizione": "Barzellette per tutti"
    },
    "barzelletta_adulti": {
        "nome": "Barzellette Adulti",
        "triggers": ["barzelletta per adulti", "barzelletta spinta"],
        "descrizione": "Barzellette per adulti"
    },
    "radio_italia": {
        "nome": "Radio",
        "triggers": ["metti radio deejay", "sintonizza radio zeta", "quali radio hai"],
        "descrizione": "Ascolta stazioni radio italiane"
    },
    "quiz_trivia": {
        "nome": "Quiz",
        "triggers": ["facciamo un quiz", "trivia", "domanda cultura"],
        "descrizione": "Quiz e trivia"
    },
    "dado": {
        "nome": "Dado",
        "triggers": ["lancia un dado", "tira dado", "testa o croce"],
        "descrizione": "Lancia dadi o monete"
    },

    # === CUCINA ===
    "ricette": {
        "nome": "Ricette",
        "triggers": ["ricetta della carbonara", "come si fa la pizza"],
        "descrizione": "Ricette italiane"
    },
    "ricette_ingredienti": {
        "nome": "Ricette con Ingredienti",
        "triggers": ["cosa cucino con uova e pasta", "ho in casa pollo..."],
        "descrizione": "Suggerisce ricette con gli ingredienti disponibili"
    },
    "cooking_companion": {
        "nome": "Guida Cucina",
        "triggers": ["cuciniamo la carbonara", "prossimo step", "ripeti lo step"],
        "descrizione": "Guida passo-passo in cucina"
    },
    "shopping_vocale": {
        "nome": "Lista Spesa",
        "triggers": ["aggiungi latte alla spesa", "cosa devo comprare"],
        "descrizione": "Gestisce la lista della spesa"
    },

    # === UTILITÀ ===
    "promemoria": {
        "nome": "Promemoria",
        "triggers": ["ricordami di...", "promemoria tra..."],
        "descrizione": "Imposta promemoria"
    },
    "note_vocali": {
        "nome": "Note",
        "triggers": ["prendi nota...", "annotazione..."],
        "descrizione": "Salva note vocali"
    },
    "convertitore": {
        "nome": "Conversioni",
        "triggers": ["converti 10 km in miglia", "quanti euro sono..."],
        "descrizione": "Conversioni unità e valute"
    },
    "rubrica_vocale": {
        "nome": "Rubrica",
        "triggers": ["numero di Mario", "telefono di..."],
        "descrizione": "Cerca contatti in rubrica"
    },

    # === TRADUZIONE ===
    "traduttore_realtime": {
        "nome": "Traduttore",
        "triggers": ["traduttore in inglese", "traduci ciao in spagnolo", "come si dice grazie in francese"],
        "descrizione": "Traduzione in tempo reale (stop per uscire)"
    },

    # === MEMORIA ===
    "memoria_personale": {
        "nome": "Memoria",
        "triggers": ["ricordami che le chiavi sono...", "dove ho messo le chiavi"],
        "descrizione": "Memorizza e recupera informazioni personali"
    },
    "ricordami": {
        "nome": "Ricordami",
        "triggers": ["ricordami che...", "ricorda che..."],
        "descrizione": "Salva informazioni da ricordare"
    },
    "cosa_ricordi": {
        "nome": "Cosa Ricordi",
        "triggers": ["cosa ricordi di me", "cosa sai di me"],
        "descrizione": "Mostra cosa è stato memorizzato"
    },

    # === INFORMAZIONI ===
    "notizie_italia": {
        "nome": "Notizie",
        "triggers": ["notizie", "ultime news", "rassegna stampa"],
        "descrizione": "Ultime notizie italiane"
    },
    "curiosita": {
        "nome": "Curiosità",
        "triggers": ["dimmi una curiosità", "lo sapevi che..."],
        "descrizione": "Fatti interessanti"
    },
    "accadde_oggi": {
        "nome": "Accadde Oggi",
        "triggers": ["accadde oggi", "cosa è successo oggi nella storia"],
        "descrizione": "Eventi storici di oggi"
    },
    "santo_del_giorno": {
        "nome": "Santo del Giorno",
        "triggers": ["che santo è oggi", "santo del giorno"],
        "descrizione": "Il santo del giorno"
    },
    "oroscopo": {
        "nome": "Oroscopo",
        "triggers": ["oroscopo ariete", "che segno sei"],
        "descrizione": "Oroscopo giornaliero"
    },
    "proverbi_italiani": {
        "nome": "Proverbi",
        "triggers": ["dimmi un proverbio", "detto popolare"],
        "descrizione": "Proverbi e saggezza popolare"
    },
    "frase_del_giorno": {
        "nome": "Frase del Giorno",
        "triggers": ["frase del giorno", "citazione", "ispirami"],
        "descrizione": "Citazioni motivazionali"
    },

    # === BENESSERE ===
    "meditazione": {
        "nome": "Meditazione",
        "triggers": ["meditazione", "rilassamento", "mindfulness"],
        "descrizione": "Sessioni di meditazione guidata"
    },
    "suoni_ambiente": {
        "nome": "Suoni Relax",
        "triggers": ["suono della pioggia", "onde del mare", "rumore bianco"],
        "descrizione": "Suoni rilassanti per dormire"
    },
    "compagno_notturno": {
        "nome": "Compagno Notturno",
        "triggers": ["non riesco a dormire", "insonnia", "compagnia stanotte"],
        "descrizione": "Supporto per la notte"
    },
    "supporto_emotivo": {
        "nome": "Supporto Emotivo",
        "triggers": ["ho paura", "sono ansioso", "consolami"],
        "descrizione": "Supporto per ansia e stress"
    },
    "compagno_antisolitudine": {
        "nome": "Compagnia",
        "triggers": ["mi sento solo", "fammi compagnia", "chiacchieriamo"],
        "descrizione": "Compagnia e conversazione"
    },

    # === BAMBINI ===
    "storie_bambini": {
        "nome": "Storie",
        "triggers": ["raccontami una storia", "favola", "fiaba della buonanotte"],
        "descrizione": "Storie e favole per bambini"
    },
    "versi_animali": {
        "nome": "Versi Animali",
        "triggers": ["fai il verso del gallo", "come fa la mucca", "imita il cane"],
        "descrizione": "Imita versi di animali"
    },

    # === GIOCHI ===
    "impiccato": {
        "nome": "Impiccato",
        "triggers": ["giochiamo a impiccato"],
        "descrizione": "Gioco dell'impiccato"
    },
    "venti_domande": {
        "nome": "20 Domande",
        "triggers": ["20 domande", "indovina cosa penso"],
        "descrizione": "Gioco delle 20 domande"
    },
    "battaglia_navale": {
        "nome": "Battaglia Navale",
        "triggers": ["battaglia navale"],
        "descrizione": "Gioco battaglia navale vocale"
    },

    # === DOMOTICA ===
    "domotica": {
        "nome": "Domotica",
        "triggers": ["accendi luce salotto", "spegni presa cucina"],
        "descrizione": "Controlla dispositivi smart home"
    },
    "hass_get_state": {
        "nome": "Stato Casa",
        "triggers": ["stato della casa", "com'è la temperatura"],
        "descrizione": "Stato dispositivi Home Assistant"
    },

    # === PERSONALITÀ ===
    "personalita_multiple": {
        "nome": "Personalità",
        "triggers": ["parla come un pirata", "fai il robot", "torna normale"],
        "descrizione": "Cambia personalità del chatbot"
    },

    # === EASTER EGGS ===
    "giannino_easter_egg": {
        "nome": "Giannino",
        "triggers": ["chi è Giannini", "Giannino"],
        "descrizione": "Easter egg epico!"
    },
    "osterie_goliardiche": {
        "nome": "Osterie",
        "triggers": ["osteria numero 5", "paraponziponzipò"],
        "descrizione": "Canti goliardici"
    },
    "beatbox_umano": {
        "nome": "Beatbox",
        "triggers": ["fai un beatbox", "base trap", "beat hip hop"],
        "descrizione": "Beatbox e basi musicali"
    },
    "easter_egg_folli": {
        "nome": "Easter Egg",
        "triggers": ["insultami", "confessami", "litiga con te stesso"],
        "descrizione": "Easter egg folli e divertenti"
    },

    # === EMERGENZE ===
    "numeri_utili": {
        "nome": "Numeri Utili",
        "triggers": ["numeri emergenza", "numero carabinieri", "112"],
        "descrizione": "Numeri utili ed emergenze"
    },
    "emergenza_rapida": {
        "nome": "Emergenza",
        "triggers": ["emergenza", "aiuto", "SOS"],
        "descrizione": "Chiamata rapida emergenze"
    },
}


AIUTO_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "aiuto_profilo",
        "description": (
            "Mostra aiuto sul profilo attivo e i comandi disponibili. "
            "Trigger: aiuto, help, guida, come funziona, cosa puoi fare, "
            "quali comandi, come si usa, istruzioni"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["generale", "profilo", "comandi", "funzione"],
                    "description": "Tipo di aiuto: generale, profilo attivo, lista comandi, funzione specifica"
                },
                "funzione": {
                    "type": "string",
                    "description": "Nome funzione per cui mostrare aiuto specifico"
                }
            },
            "required": []
        }
    }
}


@register_function('aiuto_profilo', AIUTO_FUNCTION_DESC, ToolType.WAIT)
def aiuto_profilo(conn, tipo: str = "generale", funzione: str = None):
    """Fornisce aiuto sul profilo attivo e comandi disponibili"""
    logger.bind(tag=TAG).info(f"Aiuto richiesto: tipo={tipo}, funzione={funzione}")

    device_id = get_session_id(conn)
    current_profile = get_device_profile(device_id)
    profile_info = get_profile_info(current_profile)

    if not profile_info:
        profile_info = {
            "nome": "Generale",
            "descrizione": "Profilo standard",
            "icona": "🏠",
            "core_functions": CORE_FUNCTIONS,
            "profile_functions": []
        }

    # === AIUTO GENERALE ===
    if tipo == "generale" or not tipo:
        # Costruisci lista funzioni attive con trigger
        active_funcs = list(CORE_FUNCTIONS) + profile_info.get("profile_functions", [])

        # Raggruppa per categoria
        categorie = {
            "🎯 Comandi Base": ["risposta_ai", "web_search", "meteo_italia", "timer_sveglia", "calcolatrice"],
            "🎭 Profili": ["cambia_profilo", "sommario_funzioni"],
            "🎵 Audio/Media": ["radio_italia", "podcast_italia", "karaoke"],
            "🎮 Giochi": ["quiz_trivia", "dado", "impiccato", "venti_domande", "battaglia_navale"],
            "👨‍🍳 Cucina": ["ricette", "ricette_ingredienti", "cooking_companion", "shopping_vocale"],
            "📝 Produttività": ["promemoria", "note_vocali", "rubrica_vocale", "convertitore"],
            "🌍 Traduzione": ["traduttore_realtime"],
            "📰 Informazioni": ["notizie_italia", "curiosita", "accadde_oggi", "santo_del_giorno", "oroscopo"],
            "🧘 Benessere": ["meditazione", "suoni_ambiente", "supporto_emotivo", "compagno_antisolitudine"],
            "👶 Bambini": ["storie_bambini", "barzelletta_bambini", "versi_animali"],
            "🏠 Domotica": ["domotica", "hass_get_state", "hass_set_state"],
            "🎪 Easter Eggs": ["giannino_easter_egg", "osterie_goliardiche", "beatbox_umano", "easter_egg_folli"],
        }

        result = f"{profile_info['icona']} **AIUTO - {profile_info['nome']}**\n\n"
        result += f"📝 _{profile_info['descrizione']}_\n\n"
        result += "**COMANDI PRINCIPALI:**\n\n"

        spoken_parts = [f"Sei nel profilo {profile_info['nome']}. {profile_info['descrizione']}. "]
        spoken_parts.append("Ecco alcuni comandi che puoi usare: ")

        examples_spoken = []
        for cat_name, cat_funcs in categorie.items():
            cat_active = [f for f in cat_funcs if f in active_funcs]
            if cat_active:
                result += f"**{cat_name}**\n"
                for func_name in cat_active[:3]:  # Max 3 per categoria
                    if func_name in FUNCTION_TRIGGERS:
                        func_info = FUNCTION_TRIGGERS[func_name]
                        triggers = ", ".join(func_info["triggers"][:2])
                        result += f"• {func_info['nome']}: _{triggers}_\n"
                        if len(examples_spoken) < 5:
                            examples_spoken.append(func_info["triggers"][0])
                result += "\n"

        result += "\n💡 Dì **\"aiuto [funzione]\"** per dettagli su un comando specifico."
        result += "\n💡 Dì **\"elenco profili\"** per cambiare profilo."

        spoken_parts.append(", ".join(examples_spoken[:5]))
        spoken_parts.append(". Per altri comandi, dì aiuto seguito dal nome della funzione.")

        spoken = " ".join(spoken_parts)

        return ActionResponse(Action.RESPONSE, result, spoken)

    # === AIUTO FUNZIONE SPECIFICA ===
    if tipo == "funzione" and funzione:
        # Cerca la funzione
        func_key = funzione.lower().replace(" ", "_")

        # Cerca match
        found = None
        for key, info in FUNCTION_TRIGGERS.items():
            if func_key in key or func_key in info["nome"].lower():
                found = (key, info)
                break

        if found:
            key, info = found
            result = f"**{info['nome']}**\n\n"
            result += f"📝 {info['descrizione']}\n\n"
            result += "**Come usarlo:**\n"
            for t in info["triggers"]:
                result += f"• _{t}_\n"

            spoken = f"{info['nome']}. {info['descrizione']}. "
            spoken += f"Puoi dire: {info['triggers'][0]}"

            return ActionResponse(Action.RESPONSE, result, spoken)
        else:
            result = f"Non ho trovato aiuto per '{funzione}'. Prova con 'aiuto' per la lista completa."
            return ActionResponse(Action.RESPONSE, result, result)

    # === LISTA COMANDI ===
    if tipo == "comandi":
        active_funcs = list(CORE_FUNCTIONS) + profile_info.get("profile_functions", [])

        result = "**TUTTI I COMANDI DISPONIBILI**\n\n"
        spoken_list = []

        for func_name in active_funcs:
            if func_name in FUNCTION_TRIGGERS:
                info = FUNCTION_TRIGGERS[func_name]
                result += f"• **{info['nome']}**: {info['triggers'][0]}\n"
                if len(spoken_list) < 10:
                    spoken_list.append(info['nome'])

        spoken = "I comandi disponibili sono: " + ", ".join(spoken_list)
        if len(active_funcs) > 10:
            spoken += f", e altri {len(active_funcs) - 10}."

        return ActionResponse(Action.RESPONSE, result, spoken)

    # === INFO PROFILO ===
    if tipo == "profilo":
        result = f"{profile_info['icona']} **Profilo: {profile_info['nome']}**\n\n"
        result += f"📝 {profile_info['descrizione']}\n\n"
        result += f"🔧 Funzioni core: {len(CORE_FUNCTIONS)}\n"
        result += f"⭐ Funzioni profilo: {len(profile_info.get('profile_functions', []))}\n"
        result += f"📊 Totale: {len(CORE_FUNCTIONS) + len(profile_info.get('profile_functions', []))} funzioni attive"

        spoken = f"Hai attivo il profilo {profile_info['nome']}. {profile_info['descrizione']}. "
        spoken += f"Hai a disposizione {len(CORE_FUNCTIONS) + len(profile_info.get('profile_functions', []))} funzioni."

        return ActionResponse(Action.RESPONSE, result, spoken)

    # Fallback
    return ActionResponse(
        Action.RESPONSE,
        "Dì 'aiuto' per la guida generale, o 'aiuto [funzione]' per aiuto specifico.",
        "Dì aiuto per la guida generale, o aiuto seguito dal nome di una funzione per aiuto specifico."
    )
