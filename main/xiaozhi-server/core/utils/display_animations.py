"""
Display Animations - Sistema centralizzato per animazioni ESP32
Invia comandi al firmware per mostrare animazioni sul display

Formato WebSocket: {"type": "special_animation", "animation": "<nome>"}

Il firmware deve implementare queste animazioni:
- Ogni animazione ha un nome univoco
- Il display mostra l'animazione appropriata al contesto
"""

import json
import asyncio
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


# ============ CATALOGO ANIMAZIONI ============
# Definisce tutte le animazioni disponibili con descrizione per il firmware

ANIMATIONS_CATALOG = {
    # === EMOZIONI ===
    "heart": {
        "description": "Cuore pulsante - amore, affetto",
        "color": "red",
        "duration_ms": 3000
    },
    "happy": {
        "description": "Faccina felice - gioia, successo",
        "color": "yellow",
        "duration_ms": 2000
    },
    "sad": {
        "description": "Faccina triste - tristezza, empatia",
        "color": "blue",
        "duration_ms": 2000
    },
    "laugh": {
        "description": "Risata - barzellette, umorismo",
        "color": "yellow",
        "duration_ms": 2500
    },
    "hug": {
        "description": "Abbraccio - conforto, supporto emotivo",
        "color": "pink",
        "duration_ms": 3000
    },

    # === MEDIA & AUDIO ===
    "music": {
        "description": "Note musicali animate - radio, musica, karaoke",
        "color": "purple",
        "duration_ms": 0  # Loop continuo
    },
    "radio": {
        "description": "Onde radio/antenna - streaming radio",
        "color": "green",
        "duration_ms": 0  # Loop continuo
    },
    "podcast": {
        "description": "Microfono con onde - podcast",
        "color": "orange",
        "duration_ms": 0
    },
    "sound_wave": {
        "description": "Onde sonore - suoni ambiente, ASMR",
        "color": "cyan",
        "duration_ms": 0
    },

    # === INFORMAZIONI ===
    "weather_sun": {
        "description": "Sole splendente - meteo sereno",
        "color": "yellow",
        "duration_ms": 2000
    },
    "weather_cloud": {
        "description": "Nuvole - meteo nuvoloso",
        "color": "gray",
        "duration_ms": 2000
    },
    "weather_rain": {
        "description": "Pioggia animata - meteo piovoso",
        "color": "blue",
        "duration_ms": 2000
    },
    "news": {
        "description": "Giornale/ticker - notizie",
        "color": "white",
        "duration_ms": 2000
    },
    "calendar": {
        "description": "Calendario - agenda, eventi",
        "color": "blue",
        "duration_ms": 2000
    },
    "clock": {
        "description": "Orologio - ora, timer, sveglia",
        "color": "white",
        "duration_ms": 2000
    },

    # === AZIONI ===
    "thinking": {
        "description": "Puntini che girano - elaborazione, ricerca AI",
        "color": "blue",
        "duration_ms": 0  # Fino a completamento
    },
    "loading": {
        "description": "Barra caricamento - download, attesa",
        "color": "cyan",
        "duration_ms": 0
    },
    "success": {
        "description": "Checkmark verde - operazione completata",
        "color": "green",
        "duration_ms": 1500
    },
    "error": {
        "description": "X rossa - errore",
        "color": "red",
        "duration_ms": 1500
    },
    "warning": {
        "description": "Triangolo giallo - attenzione",
        "color": "yellow",
        "duration_ms": 2000
    },

    # === GIOCHI ===
    "dice": {
        "description": "Dado che rotola - gioco dado",
        "color": "white",
        "duration_ms": 2000
    },
    "quiz": {
        "description": "Punto interrogativo - quiz, domande",
        "color": "purple",
        "duration_ms": 2000
    },
    "winner": {
        "description": "Trofeo/stelle - vittoria gioco",
        "color": "gold",
        "duration_ms": 3000
    },
    "cards": {
        "description": "Carte che girano - giochi carte",
        "color": "red",
        "duration_ms": 2000
    },

    # === BENESSERE ===
    "meditation": {
        "description": "Cerchio che respira - meditazione, relax",
        "color": "purple",
        "duration_ms": 0  # Loop lento
    },
    "sleep": {
        "description": "Luna e stelle - notte, sonno",
        "color": "dark_blue",
        "duration_ms": 0
    },
    "exercise": {
        "description": "Figura in movimento - ginnastica",
        "color": "green",
        "duration_ms": 2000
    },
    "water": {
        "description": "Goccia d'acqua - idratazione",
        "color": "cyan",
        "duration_ms": 1500
    },
    "pill": {
        "description": "Pillola/medicina - promemoria farmaci",
        "color": "red",
        "duration_ms": 2000
    },

    # === CUCINA ===
    "cooking": {
        "description": "Pentola fumante - ricette, cucina",
        "color": "orange",
        "duration_ms": 2000
    },
    "shopping": {
        "description": "Carrello spesa - lista spesa",
        "color": "green",
        "duration_ms": 2000
    },

    # === CASA/IOT ===
    "home": {
        "description": "Casa - domotica, smart home",
        "color": "blue",
        "duration_ms": 2000
    },
    "light_on": {
        "description": "Lampadina accesa - luce on",
        "color": "yellow",
        "duration_ms": 1500
    },
    "light_off": {
        "description": "Lampadina spenta - luce off",
        "color": "gray",
        "duration_ms": 1500
    },

    # === COMUNICAZIONE ===
    "message": {
        "description": "Busta/messaggio - mesh, note",
        "color": "blue",
        "duration_ms": 2000
    },
    "phone": {
        "description": "Telefono - rubrica, chiamate",
        "color": "green",
        "duration_ms": 2000
    },
    "translate": {
        "description": "Globo con lingue - traduttore",
        "color": "blue",
        "duration_ms": 2000
    },

    # === SPECIALI ===
    "emergency": {
        "description": "Croce rossa lampeggiante - emergenza SOS",
        "color": "red",
        "duration_ms": 0  # Lampeggia
    },
    "star": {
        "description": "Stella brillante - oroscopo, magia",
        "color": "gold",
        "duration_ms": 2000
    },
    "magic": {
        "description": "Bacchetta magica - oracolo, profezie",
        "color": "purple",
        "duration_ms": 2500
    },
    "party": {
        "description": "Coriandoli/festa - celebrazione",
        "color": "multicolor",
        "duration_ms": 3000
    },
    "animal": {
        "description": "Zampa animale - versi animali",
        "color": "brown",
        "duration_ms": 2000
    },
    "microphone": {
        "description": "Microfono - karaoke, registrazione",
        "color": "silver",
        "duration_ms": 2000
    },
    "book": {
        "description": "Libro aperto - storie, curiosità",
        "color": "brown",
        "duration_ms": 2000
    },
    "image": {
        "description": "Cornice foto - immagini, slideshow",
        "color": "white",
        "duration_ms": 2000
    },
}


# ============ MAPPING FUNZIONI -> ANIMAZIONI ============
# Associa ogni funzione del server alla sua animazione

FUNCTION_ANIMATIONS = {
    # Emozioni & Supporto
    "giannino_easter_egg": "heart",
    "complimenti": "heart",
    "supporto_emotivo": "hug",
    "compagno_antisolitudine": "hug",
    "compagno_notturno": "sleep",
    "check_benessere": "happy",
    "diario_umore": "happy",

    # Media & Audio
    "radio_italia": "radio",
    "podcast_italia": "podcast",
    "karaoke": "microphone",
    "cerca_musica_web": "music",
    "suoni_ambiente": "sound_wave",
    "osterie_goliardiche": "music",
    "versi_animali": "animal",

    # Informazioni
    "meteo_italia": "weather_sun",  # Default, può cambiare in base al meteo
    "notizie_italia": "news",
    "get_news_from_newsnow": "news",
    "accadde_oggi": "calendar",
    "santo_del_giorno": "star",
    "agenda_eventi": "calendar",
    "briefing_mattutino": "news",

    # Tempo
    "get_time": "clock",
    "timer_sveglia": "clock",
    "promemoria": "clock",
    "promemoria_farmaci": "pill",

    # Giochi
    "quiz_trivia": "quiz",
    "dado": "dice",
    "impiccato": "quiz",
    "battaglia_navale": "cards",
    "venti_domande": "quiz",
    "chi_vuol_essere": "winner",
    "cruciverba_vocale": "quiz",
    "allenamento_mentale": "thinking",

    # Cucina
    "ricette": "cooking",
    "ricette_ingredienti": "cooking",
    "cooking_companion": "cooking",
    "smart_fridge": "shopping",
    "shopping_vocale": "shopping",
    "lista_spesa": "shopping",

    # Benessere
    "meditazione": "meditation",
    "ginnastica_dolce": "exercise",
    "conta_acqua": "water",
    "routine_mattutina": "exercise",

    # Casa/Domotica
    "domotica": "home",
    "hass_get_state": "home",
    "hass_set_state": "home",
    "hass_init": "home",

    # Comunicazione
    "meshtastic_lora": "message",
    "note_vocali": "message",
    "rubrica_vocale": "phone",
    "numeri_utili": "phone",
    "traduttore_realtime": "translate",
    "traduttore": "translate",

    # Ricerca & AI
    "web_search": "thinking",
    "risposta_ai": "thinking",
    "search_from_ragflow": "thinking",
    "leggi_pagina": "book",

    # Immagini
    "cerca_immagini": "image",
    "cerca_gif": "image",

    # Storie & Cultura
    "storie_bambini": "book",
    "barzellette": "laugh",
    "curiosita": "book",
    "proverbi_italiani": "book",
    "frase_del_giorno": "star",

    # Speciali
    "oroscopo": "star",
    "oracolo": "magic",
    "lotto_estrazioni": "star",
    "easter_egg_folli": "party",
    "personalita_multiple": "magic",
    "genera_rime": "book",

    # Emergenza
    "sos_emergenza": "emergency",
    "emergenza_rapida": "emergency",

    # Utility
    "calcolatrice": "thinking",
    "convertitore": "thinking",
    "guida_turistica": "book",
    "guida_ristoranti": "cooking",

    # Sistema
    "sommario_funzioni": "success",
    "aiuto_profilo": "success",
    "chi_sono": "happy",
    "handle_exit_intent": "success",
    "cambia_profilo": "success",
}


def send_animation(conn, animation_name: str):
    """
    Invia animazione al display ESP32

    Args:
        conn: Connessione WebSocket
        animation_name: Nome animazione dal catalogo
    """
    try:
        if animation_name not in ANIMATIONS_CATALOG:
            logger.bind(tag=TAG).warning(f"Animazione sconosciuta: {animation_name}")
            return False

        if not hasattr(conn, 'websocket') or conn.websocket is None:
            logger.bind(tag=TAG).debug("WebSocket non disponibile per animazione")
            return False

        message = {
            "type": "special_animation",
            "animation": animation_name
        }

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                conn.websocket.send(json.dumps(message)),
                loop
            )
        else:
            asyncio.run(conn.websocket.send(json.dumps(message)))

        logger.bind(tag=TAG).debug(f"Animazione '{animation_name}' inviata")
        return True

    except Exception as e:
        logger.bind(tag=TAG).debug(f"Errore invio animazione: {e}")
        return False


def send_animation_for_function(conn, function_name: str):
    """
    Invia l'animazione appropriata per una funzione

    Args:
        conn: Connessione WebSocket
        function_name: Nome della funzione chiamata
    """
    animation = FUNCTION_ANIMATIONS.get(function_name)
    if animation:
        return send_animation(conn, animation)
    return False


def stop_animation(conn):
    """Ferma l'animazione corrente (per animazioni in loop)"""
    try:
        if hasattr(conn, 'websocket') and conn.websocket:
            message = {
                "type": "special_animation",
                "animation": "stop"
            }
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    conn.websocket.send(json.dumps(message)),
                    loop
                )
            return True
    except Exception:
        pass
    return False


def get_weather_animation(weather_condition: str) -> str:
    """Ritorna l'animazione appropriata per la condizione meteo"""
    condition_lower = weather_condition.lower()

    if any(w in condition_lower for w in ['sole', 'sereno', 'soleggiato', 'sunny', 'clear']):
        return "weather_sun"
    elif any(w in condition_lower for w in ['pioggia', 'piovoso', 'rain', 'shower']):
        return "weather_rain"
    elif any(w in condition_lower for w in ['neve', 'snow']):
        return "weather_rain"  # Usa pioggia come fallback
    elif any(w in condition_lower for w in ['nuvol', 'cloud', 'coperto']):
        return "weather_cloud"
    else:
        return "weather_sun"  # Default


# ============ ESPORTA CATALOGO PER FIRMWARE ============
def export_animations_for_firmware():
    """
    Esporta il catalogo animazioni in formato JSON per il firmware
    """
    export = {
        "version": "1.0",
        "animations": ANIMATIONS_CATALOG,
        "function_mapping": FUNCTION_ANIMATIONS
    }
    return json.dumps(export, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Stampa catalogo per sviluppo firmware
    print(export_animations_for_firmware())
