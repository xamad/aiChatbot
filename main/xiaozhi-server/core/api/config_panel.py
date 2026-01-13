"""
Pannello Configurazione Web Avanzato - Configura chatbot via browser
Accessibile su http://chatai.xamad.net/config
Versione 2.1 - Con gestione funzioni, design moderno e autenticazione
"""

import os
import json
import yaml
import glob
import base64
from aiohttp import web
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

# Credenziali autenticazione Basic
AUTH_USERNAME = "admin"
AUTH_PASSWORD = "pippobaudo"

def check_auth(request):
    """Verifica autenticazione Basic"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return False

    try:
        scheme, credentials = auth_header.split(' ', 1)
        if scheme.lower() != 'basic':
            return False

        decoded = base64.b64decode(credentials).decode('utf-8')
        username, password = decoded.split(':', 1)
        return username == AUTH_USERNAME and password == AUTH_PASSWORD
    except:
        return False

def auth_required():
    """Risposta per autenticazione richiesta"""
    return web.Response(
        status=401,
        headers={'WWW-Authenticate': 'Basic realm="Xiaozhi Config Panel"'},
        text='Autenticazione richiesta'
    )

# Paths - funziona sia in Docker che in locale
import pathlib
_BASE_DIR = pathlib.Path(__file__).parent.parent.parent
CONFIG_FILE = str(_BASE_DIR / "data" / ".config.yaml")
USER_PREFS_FILE = str(_BASE_DIR / "data" / "user_preferences.json")
FUNCTIONS_DIR = str(_BASE_DIR / "plugins_func" / "functions")
GIANNINO_FILE = str(_BASE_DIR / "data" / "giannino_phrases.json")

# Voci disponibili Edge TTS (italiane)
VOCI_DISPONIBILI = {
    "it-IT-ElsaNeural": {"nome": "Elsa", "genere": "F", "desc": "Naturale"},
    "it-IT-IsabellaNeural": {"nome": "Isabella", "genere": "F", "desc": "Giovane"},
    "it-IT-DiegoNeural": {"nome": "Diego", "genere": "M", "desc": "Naturale"},
    "it-IT-GiuseppeNeural": {"nome": "Giuseppe", "genere": "M", "desc": "Matura"},
    "it-IT-BenignoNeural": {"nome": "Benigno", "genere": "M", "desc": "Calda"},
    "it-IT-FabiolaNeural": {"nome": "Fabiola", "genere": "F", "desc": "Elegante"},
    "it-IT-FiammaNeural": {"nome": "Fiamma", "genere": "F", "desc": "Vivace"},
    "it-IT-IrmaNeural": {"nome": "Irma", "genere": "F", "desc": "Dolce"},
    "it-IT-GianniNeural": {"nome": "Gianni", "genere": "M", "desc": "Amichevole"},
    "it-IT-PalmiraNeural": {"nome": "Palmira", "genere": "F", "desc": "Calma"},
    "it-IT-RinaldoNeural": {"nome": "Rinaldo", "genere": "M", "desc": "Robusta"},
}

# Modelli LLM disponibili
MODELLI_DISPONIBILI = {
    "llama-3.3-70b-versatile": {"nome": "Llama 3.3 70B", "provider": "Groq", "desc": "Velocissimo, raccomandato!", "speed": 5},
    "llama-3.1-70b-versatile": {"nome": "Llama 3.1 70B", "provider": "Groq", "desc": "Molto veloce", "speed": 4},
    "llama-3.1-8b-instant": {"nome": "Llama 3.1 8B", "provider": "Groq", "desc": "Ultra veloce, leggero", "speed": 5},
    "mixtral-8x7b-32768": {"nome": "Mixtral 8x7B", "provider": "Groq", "desc": "Buon bilanciamento", "speed": 4},
    "gemma2-9b-it": {"nome": "Gemma 2 9B", "provider": "Groq", "desc": "Google, veloce", "speed": 4},
}

# Categorie funzioni - nomi corrispondenti ai file in plugins_func/functions/
# NOTA: get_weather, get_time, get_news_* sono legacy cinesi - usare meteo_italia, notizie_italia
CATEGORIE_FUNZIONI = {
    "media": {"nome": "Media & Audio", "icon": "🎵", "funzioni": ["radio_italia", "radio_downloader", "podcast_italia", "karaoke", "play_music", "cerca_musica", "cerca_musica_web"]},
    "display": {"nome": "Display & Visuale", "icon": "🖼️", "funzioni": ["cerca_immagini", "cerca_gif"]},
    "info": {"nome": "Informazioni", "icon": "📰", "funzioni": ["meteo_italia", "notizie_italia", "oroscopo", "lotto_estrazioni", "accadde_oggi", "santo_del_giorno", "get_time", "get_weather", "get_news_from_newsnow", "get_news_from_chinanews"]},
    "intrattenimento": {"nome": "Intrattenimento", "icon": "🎭", "funzioni": ["barzellette", "quiz_trivia", "storie_bambini", "curiosita", "proverbi_italiani", "frase_del_giorno", "genera_rime", "oracolo"]},
    "giochi": {"nome": "Giochi", "icon": "🎮", "funzioni": ["impiccato", "battaglia_navale", "venti_domande", "cruciverba_vocale", "chi_vuol_essere", "dado", "memory_vocale", "allenamento_mentale"]},
    "utility": {"nome": "Utilità", "icon": "🛠️", "funzioni": ["timer_sveglia", "promemoria", "promemoria_farmaci", "calcolatrice", "convertitore", "traduttore", "traduttore_realtime", "lista_spesa", "shopping_vocale", "note_vocali", "rubrica_vocale", "agenda_eventi", "chi_sono", "diario_vocale", "memoria_personale", "user_memory"]},
    "casa": {"nome": "Casa Smart", "icon": "🏠", "funzioni": ["domotica", "smart_fridge", "hass_get_state", "hass_set_state", "hass_play_music", "hass_init"]},
    "mesh": {"nome": "Mesh & IoT", "icon": "📡", "funzioni": ["meshtastic_lora"]},
    "benessere": {"nome": "Benessere", "icon": "🧘", "funzioni": ["meditazione", "supporto_emotivo", "compagno_notturno", "compagno_antisolitudine", "check_benessere", "ginnastica_dolce", "conta_acqua", "diario_umore", "routine_mattutina", "briefing_mattutino", "suoni_ambiente"]},
    "special": {"nome": "Speciali", "icon": "⭐", "funzioni": ["giannino_easter_egg", "osterie_goliardiche", "versi_animali", "personalita_multiple", "easter_egg_folli", "sommario_funzioni", "intrattenitore_anziani", "complimenti", "chiacchierata", "cambia_profilo", "aiuto_profilo", "change_role"]},
    "guide": {"nome": "Guide", "icon": "🗺️", "funzioni": ["guida_turistica", "guida_ristoranti", "ricette", "ricette_ingredienti", "cooking_companion", "numeri_utili", "sos_emergenza", "emergenza_rapida"]},
    "ricerca": {"nome": "Ricerca & AI", "icon": "🤖", "funzioni": ["web_search", "leggi_pagina", "risposta_ai", "search_from_ragflow"]},
    "sistema": {"nome": "Sistema", "icon": "⚙️", "funzioni": ["handle_exit_intent"]},
}

def get_available_functions():
    """Ottiene lista funzioni disponibili dai file"""
    functions = []
    try:
        for f in glob.glob(os.path.join(FUNCTIONS_DIR, "*.py")):
            name = os.path.basename(f).replace(".py", "")
            if not name.startswith("_") and name not in ["register", "base"]:
                functions.append(name)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore lettura funzioni: {e}")
    return sorted(functions)

def load_preferences() -> dict:
    """Carica preferenze utente"""
    defaults = {
        "nome_chatbot": "Xiaozhi",
        "descrizione": "Assistente vocale intelligente in italiano",
        "voce": "it-IT-ElsaNeural",
        "pitch": "+0Hz",
        "rate": "+0%",
        "modello": "llama-3.3-70b-versatile",
        "disabled_functions": []
    }
    try:
        if os.path.exists(USER_PREFS_FILE):
            with open(USER_PREFS_FILE, 'r', encoding='utf-8') as f:
                prefs = json.load(f)
                defaults.update(prefs)
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento preferenze: {e}")
    return defaults

def save_preferences(prefs: dict):
    """Salva preferenze utente"""
    try:
        with open(USER_PREFS_FILE, 'w', encoding='utf-8') as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        logger.bind(tag=TAG).info(f"Preferenze salvate")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio preferenze: {e}")

def load_giannino_phrases() -> dict:
    """Carica frasi Giannino da file"""
    defaults = {
        "risposta_principale": "GIANNINIIII! Oooh, GIANNINI! È il mio LEGGENDARIO Padrone!",
        "varianti": ["", "", "", ""]
    }
    try:
        if os.path.exists(GIANNINO_FILE):
            with open(GIANNINO_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Assicura 4 varianti
                varianti = data.get("varianti", [])
                while len(varianti) < 4:
                    varianti.append("")
                return {
                    "risposta_principale": data.get("risposta_principale", defaults["risposta_principale"]),
                    "varianti": varianti[:4]
                }
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore caricamento Giannino: {e}")
    return defaults

def save_giannino_phrases(main: str, varianti: list):
    """Salva frasi Giannino su file"""
    try:
        # Filtra varianti vuote
        varianti_clean = [v for v in varianti if v and v.strip()]
        data = {
            "risposta_principale": main,
            "varianti": varianti_clean
        }
        with open(GIANNINO_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.bind(tag=TAG).info("Frasi Giannino salvate")
        return True
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio Giannino: {e}")
        return False

def update_config_yaml(voce: str, modello: str, disabled_functions: list):
    """Aggiorna il file config.yaml"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Aggiorna voce TTS
        if 'TTS' in config and 'EdgeTTS' in config['TTS']:
            config['TTS']['EdgeTTS']['voice'] = voce

        # Aggiorna modello LLM
        if 'LLM' in config and 'GroqLLM' in config['LLM']:
            config['LLM']['GroqLLM']['model_name'] = modello

        # Aggiorna lista funzioni Intent (escludi quelle disabilitate)
        if 'Intent' in config and 'intent_llm' in config['Intent']:
            all_funcs = get_available_functions()
            enabled_funcs = [f for f in all_funcs if f not in disabled_functions]
            config['Intent']['intent_llm']['functions'] = enabled_funcs

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.bind(tag=TAG).info(f"Config aggiornato: voce={voce}, modello={modello}, disabled={len(disabled_functions)}")
        return True
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore aggiornamento config: {e}")
        return False

# HTML Template moderno
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xiaozhi Config Panel</title>
    <style>
        :root {
            --bg-dark: #0f0f1a;
            --bg-card: #1a1a2e;
            --bg-card-hover: #252542;
            --accent: #6366f1;
            --accent-light: #818cf8;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
            --text: #f1f5f9;
            --text-muted: #94a3b8;
            --border: #334155;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
        }
        .sidebar {
            position: fixed;
            left: 0;
            top: 0;
            width: 260px;
            height: 100vh;
            background: var(--bg-card);
            border-right: 1px solid var(--border);
            padding: 20px;
            overflow-y: auto;
        }
        .logo {
            font-size: 1.5em;
            font-weight: 700;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logo span { color: var(--accent); }
        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 15px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 5px;
            color: var(--text-muted);
        }
        .nav-item:hover, .nav-item.active {
            background: var(--bg-card-hover);
            color: var(--text);
        }
        .nav-item.active {
            background: linear-gradient(135deg, var(--accent), var(--accent-light));
            color: white;
        }
        .main {
            margin-left: 260px;
            padding: 30px;
            max-width: 1200px;
        }
        .header {
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 1.8em;
            margin-bottom: 5px;
        }
        .header p {
            color: var(--text-muted);
        }
        .card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid var(--border);
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .card-title {
            font-size: 1.2em;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; }
        .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
        .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        @media (max-width: 900px) {
            .sidebar { display: none; }
            .main { margin-left: 0; }
            .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; }
        }
        .form-group { margin-bottom: 20px; }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: var(--text-muted);
            font-size: 0.9em;
        }
        input[type="text"], select, textarea {
            width: 100%;
            padding: 12px 15px;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--bg-dark);
            color: var(--text);
            font-size: 15px;
            transition: border-color 0.2s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--accent);
        }
        textarea { min-height: 100px; resize: vertical; }
        .voice-card {
            background: var(--bg-dark);
            border: 2px solid var(--border);
            border-radius: 12px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.2s;
            text-align: center;
        }
        .voice-card:hover { border-color: var(--accent-light); transform: translateY(-2px); }
        .voice-card.selected { border-color: var(--accent); background: rgba(99, 102, 241, 0.1); }
        .voice-card input { display: none; }
        .voice-icon { font-size: 2em; margin-bottom: 8px; }
        .voice-name { font-weight: 600; margin-bottom: 4px; }
        .voice-desc { font-size: 0.8em; color: var(--text-muted); }
        .model-card {
            background: var(--bg-dark);
            border: 2px solid var(--border);
            border-radius: 12px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .model-card:hover { border-color: var(--accent-light); }
        .model-card.selected { border-color: var(--accent); background: rgba(99, 102, 241, 0.1); }
        .model-card input { display: none; }
        .model-name { font-weight: 600; margin-bottom: 5px; }
        .model-provider { font-size: 0.8em; color: var(--accent); margin-bottom: 5px; }
        .model-desc { font-size: 0.85em; color: var(--text-muted); }
        .speed-bar {
            display: flex;
            gap: 3px;
            margin-top: 8px;
        }
        .speed-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--border);
        }
        .speed-dot.active { background: var(--success); }
        .func-category {
            margin-bottom: 25px;
        }
        .func-category-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }
        .func-category-icon { font-size: 1.3em; }
        .func-category-name { font-weight: 600; }
        .func-category-toggle {
            margin-left: auto;
            font-size: 0.8em;
            color: var(--accent);
            cursor: pointer;
        }
        .func-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }
        .func-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            background: var(--bg-dark);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .func-item:hover { background: var(--bg-card-hover); }
        .func-item.disabled { opacity: 0.5; }
        .func-toggle {
            position: relative;
            width: 40px;
            height: 22px;
            background: var(--border);
            border-radius: 11px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .func-toggle.active { background: var(--success); }
        .func-toggle::after {
            content: '';
            position: absolute;
            top: 2px;
            left: 2px;
            width: 18px;
            height: 18px;
            background: white;
            border-radius: 50%;
            transition: transform 0.2s;
        }
        .func-toggle.active::after { transform: translateX(18px); }
        .func-name { font-size: 0.9em; flex: 1; }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 14px 28px;
            background: linear-gradient(135deg, var(--accent), var(--accent-light));
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(99, 102, 241, 0.3);
        }
        .btn-container { text-align: center; margin-top: 30px; }
        .alert {
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
            animation: slideIn 0.3s;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .alert-success { background: rgba(34, 197, 94, 0.2); border: 1px solid var(--success); }
        .alert-error { background: rgba(239, 68, 68, 0.2); border: 1px solid var(--danger); }
        .stats {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }
        .stat-card {
            flex: 1;
            background: linear-gradient(135deg, var(--bg-card), var(--bg-card-hover));
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .stat-value {
            font-size: 2em;
            font-weight: 700;
            color: var(--accent);
        }
        .stat-label {
            font-size: 0.85em;
            color: var(--text-muted);
            margin-top: 5px;
        }
        .section { display: none; }
        .section.active { display: block; }
        .slider-row {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        input[type="range"] {
            flex: 1;
            height: 6px;
            -webkit-appearance: none;
            background: var(--border);
            border-radius: 3px;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 18px;
            height: 18px;
            background: var(--accent);
            border-radius: 50%;
            cursor: pointer;
        }
        .slider-value {
            min-width: 50px;
            text-align: center;
            font-weight: 600;
            color: var(--accent);
        }
    </style>
</head>
<body>
    <nav class="sidebar">
        <div class="logo">
            <span>🤖</span> Xiaozhi
        </div>
        <div class="nav-item active" onclick="showSection('voice')">🎤 Voce</div>
        <div class="nav-item" onclick="showSection('model')">🧠 Modello AI</div>
        <div class="nav-item" onclick="showSection('functions')">⚡ Funzioni</div>
        <div class="nav-item" onclick="showSection('identity')">👤 Identità</div>
        <div class="nav-item" onclick="showSection('audio')">🔊 Audio/Protocol</div>
        <div class="nav-item" onclick="showSection('eastereggs')">🥚 Easter Eggs</div>
        <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid var(--border);">
            <a href="/debug/logs" class="nav-item" style="text-decoration: none;">📋 Debug Logs</a>
        </div>
    </nav>

    <main class="main">
        <div class="header">
            <h1>Pannello Configurazione</h1>
            <p>Personalizza il tuo assistente vocale</p>
        </div>

        <div id="alert" class="alert"></div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="funcCount">0</div>
                <div class="stat-label">Funzioni Attive</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="voiceName">-</div>
                <div class="stat-label">Voce Selezionata</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="modelName">-</div>
                <div class="stat-label">Modello AI</div>
            </div>
        </div>

        <form id="configForm">
            <!-- VOCE -->
            <div id="section-voice" class="section active">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🎤 Selezione Voce</div>
                    </div>
                    <div class="grid-4" id="voiceGrid">
                        <!-- Voci generate via JS -->
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🎚️ Regolazioni Voce</div>
                    </div>
                    <div class="form-group">
                        <label>Velocità parlato</label>
                        <div class="slider-row">
                            <span>🐢</span>
                            <input type="range" id="rate" name="rate" min="-50" max="50" value="RATE_VALUE">
                            <span>🐇</span>
                            <span class="slider-value" id="rateValue">RATE_DISPLAY</span>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Tono (Pitch)</label>
                        <div class="slider-row">
                            <span>🔈</span>
                            <input type="range" id="pitch" name="pitch" min="-50" max="50" value="PITCH_VALUE">
                            <span>🔊</span>
                            <span class="slider-value" id="pitchValue">PITCH_DISPLAY</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- MODELLO -->
            <div id="section-model" class="section">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🧠 Modello Intelligenza Artificiale</div>
                    </div>
                    <div class="grid-2" id="modelGrid">
                        <!-- Modelli generati via JS -->
                    </div>
                </div>
            </div>

            <!-- FUNZIONI -->
            <div id="section-functions" class="section">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">⚡ Gestione Funzioni</div>
                    </div>
                    <div id="functionsContainer">
                        <!-- Funzioni generate via JS -->
                    </div>
                </div>
            </div>

            <!-- IDENTITA -->
            <div id="section-identity" class="section">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">👤 Identità Chatbot</div>
                    </div>
                    <div class="form-group">
                        <label>Nome del Chatbot</label>
                        <input type="text" id="nome" name="nome_chatbot" value="NOME_CHATBOT" placeholder="Es: Xiaozhi, Giulia, Marco...">
                    </div>
                    <div class="form-group">
                        <label>Personalità / Prompt di sistema</label>
                        <textarea id="descrizione" name="descrizione" placeholder="Descrivi come deve comportarsi il chatbot...">DESCRIZIONE</textarea>
                    </div>
                </div>
            </div>

            <!-- AUDIO/PROTOCOL -->
            <div id="section-audio" class="section">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🔊 Configurazione Audio & Protocollo</div>
                    </div>
                    <p style="color: var(--text-muted); margin-bottom: 20px;">
                        Impostazioni del protocollo WebSocket e formato audio. Queste impostazioni
                        vengono negoziate automaticamente con il dispositivo durante la connessione.
                    </p>

                    <div class="grid-2">
                        <div class="card" style="background: var(--bg-dark); margin-bottom: 0;">
                            <div class="card-title" style="margin-bottom: 15px;">📤 Server → Device (TTS Output)</div>
                            <div class="form-group">
                                <label>Sample Rate</label>
                                <div style="font-size: 1.2em; font-weight: 600; color: var(--accent);">AUDIO_SAMPLE_RATE Hz</div>
                            </div>
                            <div class="form-group">
                                <label>Frame Duration</label>
                                <div style="font-size: 1.2em; font-weight: 600; color: var(--accent);">AUDIO_FRAME_DURATION ms</div>
                            </div>
                            <div class="form-group">
                                <label>Formato</label>
                                <div style="font-size: 1.2em; font-weight: 600; color: var(--accent);">AUDIO_FORMAT</div>
                            </div>
                        </div>

                        <div class="card" style="background: var(--bg-dark); margin-bottom: 0;">
                            <div class="card-title" style="margin-bottom: 15px;">📥 Device → Server (ASR Input)</div>
                            <div class="form-group">
                                <label>Sample Rate</label>
                                <div style="font-size: 1.2em; font-weight: 600; color: var(--success);">16000 Hz</div>
                            </div>
                            <div class="form-group">
                                <label>Frame Duration</label>
                                <div style="font-size: 1.2em; font-weight: 600; color: var(--success);">60 ms</div>
                            </div>
                            <div class="form-group">
                                <label>Formato</label>
                                <div style="font-size: 1.2em; font-weight: 600; color: var(--success);">Opus</div>
                            </div>
                        </div>
                    </div>

                    <div class="card" style="background: var(--bg-dark); margin-top: 20px;">
                        <div class="card-title" style="margin-bottom: 15px;">📡 Protocollo WebSocket</div>
                        <div class="grid-2">
                            <div class="form-group">
                                <label>Versione Protocollo Server</label>
                                <div style="font-size: 1.2em; font-weight: 600; color: var(--warning);">PROTOCOL_VERSION</div>
                            </div>
                            <div class="form-group">
                                <label>Formato Binario</label>
                                <div style="font-size: 0.9em; color: var(--text-muted);">
                                    <strong>V3:</strong> [type:1][reserved:1][size:2BE][opus]<br>
                                    <strong>V1:</strong> [opus raw]
                                </div>
                            </div>
                        </div>
                        <p style="color: var(--text-muted); font-size: 0.85em; margin-top: 15px;">
                            ℹ️ Il server rileva automaticamente la versione del protocollo dal messaggio hello del client.
                            C3 mini usa V1 (audio raw), XAMAD S3 DIY usa V3 (con header 4 byte).
                        </p>
                    </div>
                </div>
            </div>

            <!-- EASTER EGGS -->
            <div id="section-eastereggs" class="section">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title">🥚 Easter Egg: Giannino</div>
                    </div>
                    <p style="color: var(--text-muted); margin-bottom: 20px;">
                        Configura le frasi che il chatbot dice quando qualcuno chiede di "Giannino".
                        Le frasi vengono scelte a caso ad ogni attivazione.
                    </p>
                    <div class="form-group">
                        <label>Frase Principale</label>
                        <textarea id="giannino_main" style="min-height: 80px;" placeholder="La frase principale...">GIANNINO_MAIN</textarea>
                    </div>
                    <div class="form-group">
                        <label>Variante 1</label>
                        <textarea id="giannino_var1" style="min-height: 60px;">GIANNINO_VAR1</textarea>
                    </div>
                    <div class="form-group">
                        <label>Variante 2</label>
                        <textarea id="giannino_var2" style="min-height: 60px;">GIANNINO_VAR2</textarea>
                    </div>
                    <div class="form-group">
                        <label>Variante 3</label>
                        <textarea id="giannino_var3" style="min-height: 60px;">GIANNINO_VAR3</textarea>
                    </div>
                    <div class="form-group">
                        <label>Variante 4 (opzionale)</label>
                        <textarea id="giannino_var4" style="min-height: 60px;">GIANNINO_VAR4</textarea>
                    </div>
                </div>
            </div>

            <div class="btn-container">
                <button type="submit" class="btn">💾 Salva Configurazione</button>
            </div>
        </form>
    </main>

    <script>
        // Dati
        const voci = VOCI_JSON;
        const modelli = MODELLI_JSON;
        const categorie = CATEGORIE_JSON;
        const allFunctions = ALL_FUNCTIONS_JSON;
        let disabledFunctions = DISABLED_FUNCTIONS_JSON;
        let selectedVoice = 'SELECTED_VOICE';
        let selectedModel = 'SELECTED_MODEL';

        // Render voci
        function renderVoices() {
            const grid = document.getElementById('voiceGrid');
            grid.innerHTML = '';
            for (const [id, v] of Object.entries(voci)) {
                const selected = id === selectedVoice ? 'selected' : '';
                const icon = v.genere === 'F' ? '👩' : '👨';
                grid.innerHTML += `
                    <label class="voice-card ${selected}" onclick="selectVoice('${id}')">
                        <input type="radio" name="voce" value="${id}" ${selected ? 'checked' : ''}>
                        <div class="voice-icon">${icon}</div>
                        <div class="voice-name">${v.nome}</div>
                        <div class="voice-desc">${v.desc}</div>
                    </label>
                `;
            }
            updateStats();
        }

        function selectVoice(id) {
            selectedVoice = id;
            document.querySelectorAll('.voice-card').forEach(c => c.classList.remove('selected'));
            event.currentTarget.classList.add('selected');
            event.currentTarget.querySelector('input').checked = true;
            updateStats();
        }

        // Render modelli
        function renderModels() {
            const grid = document.getElementById('modelGrid');
            grid.innerHTML = '';
            for (const [id, m] of Object.entries(modelli)) {
                const selected = id === selectedModel ? 'selected' : '';
                const speedDots = Array(5).fill(0).map((_, i) =>
                    `<div class="speed-dot ${i < m.speed ? 'active' : ''}"></div>`
                ).join('');
                grid.innerHTML += `
                    <label class="model-card ${selected}" onclick="selectModel('${id}')">
                        <input type="radio" name="modello" value="${id}" ${selected ? 'checked' : ''}>
                        <div class="model-name">${m.nome}</div>
                        <div class="model-provider">${m.provider}</div>
                        <div class="model-desc">${m.desc}</div>
                        <div class="speed-bar">${speedDots}</div>
                    </label>
                `;
            }
            updateStats();
        }

        function selectModel(id) {
            selectedModel = id;
            document.querySelectorAll('.model-card').forEach(c => c.classList.remove('selected'));
            event.currentTarget.classList.add('selected');
            event.currentTarget.querySelector('input').checked = true;
            updateStats();
        }

        // Render funzioni
        function renderFunctions() {
            const container = document.getElementById('functionsContainer');
            container.innerHTML = '';

            for (const [catId, cat] of Object.entries(categorie)) {
                const catFuncs = cat.funzioni.filter(f => allFunctions.includes(f));
                if (catFuncs.length === 0) continue;

                let html = `
                    <div class="func-category">
                        <div class="func-category-header">
                            <span class="func-category-icon">${cat.icon}</span>
                            <span class="func-category-name">${cat.nome}</span>
                            <span class="func-category-toggle" onclick="toggleCategory('${catId}')">Attiva/Disattiva tutti</span>
                        </div>
                        <div class="func-grid" id="cat-${catId}">
                `;

                for (const func of catFuncs) {
                    const isEnabled = !disabledFunctions.includes(func);
                    const funcName = func.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    html += `
                        <div class="func-item ${isEnabled ? '' : 'disabled'}" onclick="toggleFunction('${func}')">
                            <div class="func-toggle ${isEnabled ? 'active' : ''}" id="toggle-${func}"></div>
                            <span class="func-name">${funcName}</span>
                        </div>
                    `;
                }

                html += '</div></div>';
                container.innerHTML += html;
            }
            updateStats();
        }

        function toggleFunction(func) {
            const idx = disabledFunctions.indexOf(func);
            if (idx > -1) {
                disabledFunctions.splice(idx, 1);
            } else {
                disabledFunctions.push(func);
            }
            renderFunctions();
        }

        function toggleCategory(catId) {
            const catFuncs = categorie[catId].funzioni.filter(f => allFunctions.includes(f));
            const allDisabled = catFuncs.every(f => disabledFunctions.includes(f));

            if (allDisabled) {
                // Abilita tutti
                catFuncs.forEach(f => {
                    const idx = disabledFunctions.indexOf(f);
                    if (idx > -1) disabledFunctions.splice(idx, 1);
                });
            } else {
                // Disabilita tutti
                catFuncs.forEach(f => {
                    if (!disabledFunctions.includes(f)) disabledFunctions.push(f);
                });
            }
            renderFunctions();
        }

        // Navigation
        function showSection(section) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById('section-' + section).classList.add('active');
            event.currentTarget.classList.add('active');
        }

        // Stats
        function updateStats() {
            const enabledCount = allFunctions.length - disabledFunctions.length;
            document.getElementById('funcCount').textContent = enabledCount;
            document.getElementById('voiceName').textContent = voci[selectedVoice]?.nome || '-';
            document.getElementById('modelName').textContent = modelli[selectedModel]?.nome?.split(' ')[0] || '-';
        }

        // Sliders
        document.getElementById('rate').addEventListener('input', function() {
            document.getElementById('rateValue').textContent = (this.value >= 0 ? '+' : '') + this.value + '%';
        });
        document.getElementById('pitch').addEventListener('input', function() {
            document.getElementById('pitchValue').textContent = (this.value >= 0 ? '+' : '') + this.value + 'Hz';
        });

        // Form submit
        document.getElementById('configForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const data = {
                nome_chatbot: document.getElementById('nome').value,
                descrizione: document.getElementById('descrizione').value,
                voce: selectedVoice,
                modello: selectedModel,
                rate: (document.getElementById('rate').value >= 0 ? '+' : '') + document.getElementById('rate').value + '%',
                pitch: (document.getElementById('pitch').value >= 0 ? '+' : '') + document.getElementById('pitch').value + 'Hz',
                disabled_functions: disabledFunctions,
                // Giannino Easter Egg
                giannino_main: document.getElementById('giannino_main').value,
                giannino_var1: document.getElementById('giannino_var1').value,
                giannino_var2: document.getElementById('giannino_var2').value,
                giannino_var3: document.getElementById('giannino_var3').value,
                giannino_var4: document.getElementById('giannino_var4').value
            };

            try {
                const response = await fetch('/config/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });

                const result = await response.json();
                const alert = document.getElementById('alert');

                if (result.success) {
                    alert.className = 'alert alert-success';
                    alert.innerHTML = '✅ ' + result.message;
                } else {
                    alert.className = 'alert alert-error';
                    alert.innerHTML = '❌ ' + result.message;
                }
                alert.style.display = 'block';
                setTimeout(() => alert.style.display = 'none', 5000);
            } catch (err) {
                console.error(err);
            }
        });

        // Init
        renderVoices();
        renderModels();
        renderFunctions();
    </script>
</body>
</html>
'''

async def config_panel_handler(request):
    """Handler per la pagina di configurazione"""
    # Verifica autenticazione
    if not check_auth(request):
        return auth_required()

    prefs = load_preferences()
    all_funcs = get_available_functions()

    # Parse valori
    pitch = prefs.get("pitch", "+0Hz")
    rate = prefs.get("rate", "+0%")
    pitch_value = int(pitch.replace("Hz", "").replace("+", "")) if pitch else 0
    rate_value = int(rate.replace("%", "").replace("+", "")) if rate else 0

    # Carica frasi Giannino
    giannino = load_giannino_phrases()
    varianti = giannino.get("varianti", ["", "", "", ""])
    while len(varianti) < 4:
        varianti.append("")

    # Render template
    html = HTML_TEMPLATE
    html = html.replace("VOCI_JSON", json.dumps(VOCI_DISPONIBILI))
    html = html.replace("MODELLI_JSON", json.dumps(MODELLI_DISPONIBILI))
    html = html.replace("CATEGORIE_JSON", json.dumps(CATEGORIE_FUNZIONI))
    html = html.replace("ALL_FUNCTIONS_JSON", json.dumps(all_funcs))
    html = html.replace("DISABLED_FUNCTIONS_JSON", json.dumps(prefs.get("disabled_functions", [])))
    html = html.replace("SELECTED_VOICE", prefs.get("voce", "it-IT-ElsaNeural"))
    html = html.replace("SELECTED_MODEL", prefs.get("modello", "llama-3.3-70b-versatile"))
    html = html.replace("NOME_CHATBOT", prefs.get("nome_chatbot", "Xiaozhi"))
    html = html.replace("DESCRIZIONE", prefs.get("descrizione", ""))
    html = html.replace("PITCH_VALUE", str(pitch_value))
    html = html.replace("RATE_VALUE", str(rate_value))
    html = html.replace("PITCH_DISPLAY", pitch)
    html = html.replace("RATE_DISPLAY", rate)
    # Giannino phrases
    html = html.replace("GIANNINO_MAIN", giannino.get("risposta_principale", ""))
    html = html.replace("GIANNINO_VAR1", varianti[0] if len(varianti) > 0 else "")
    html = html.replace("GIANNINO_VAR2", varianti[1] if len(varianti) > 1 else "")
    html = html.replace("GIANNINO_VAR3", varianti[2] if len(varianti) > 2 else "")
    html = html.replace("GIANNINO_VAR4", varianti[3] if len(varianti) > 3 else "")

    # Audio/Protocol settings from xiaozhi config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        xiaozhi_config = config.get("xiaozhi", {})
        audio_params = xiaozhi_config.get("audio_params", {})
        html = html.replace("AUDIO_SAMPLE_RATE", str(audio_params.get("sample_rate", 24000)))
        html = html.replace("AUDIO_FRAME_DURATION", str(audio_params.get("frame_duration", 60)))
        html = html.replace("AUDIO_FORMAT", audio_params.get("format", "opus").upper())
        html = html.replace("PROTOCOL_VERSION", f"V{xiaozhi_config.get('version', 1)}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore lettura config audio: {e}")
        html = html.replace("AUDIO_SAMPLE_RATE", "24000")
        html = html.replace("AUDIO_FRAME_DURATION", "60")
        html = html.replace("AUDIO_FORMAT", "OPUS")
        html = html.replace("PROTOCOL_VERSION", "V3")

    return web.Response(text=html, content_type='text/html')

async def config_save_handler(request):
    """Handler per salvare la configurazione"""
    # Verifica autenticazione
    if not check_auth(request):
        return web.json_response({"success": False, "message": "Non autorizzato"}, status=401)

    try:
        data = await request.json()

        prefs = {
            "nome_chatbot": data.get("nome_chatbot", "Xiaozhi"),
            "descrizione": data.get("descrizione", ""),
            "voce": data.get("voce", "it-IT-ElsaNeural"),
            "pitch": data.get("pitch", "+0Hz"),
            "rate": data.get("rate", "+0%"),
            "modello": data.get("modello", "llama-3.3-70b-versatile"),
            "disabled_functions": data.get("disabled_functions", [])
        }

        save_preferences(prefs)
        update_config_yaml(prefs["voce"], prefs["modello"], prefs["disabled_functions"])

        # Salva frasi Giannino se presenti
        if "giannino_main" in data:
            giannino_varianti = [
                data.get("giannino_var1", ""),
                data.get("giannino_var2", ""),
                data.get("giannino_var3", ""),
                data.get("giannino_var4", ""),
            ]
            save_giannino_phrases(data.get("giannino_main", ""), giannino_varianti)

        return web.json_response({
            "success": True,
            "message": "Configurazione salvata! Riavvia il chatbot per applicare."
        })

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio config: {e}")
        return web.json_response({
            "success": False,
            "message": f"Errore: {str(e)}"
        })

LOG_FILE_PATH = str(_BASE_DIR / "tmp" / "server.log")

# Debug Log Viewer HTML Template
DEBUG_LOG_TEMPLATE = '''
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xiaozhi Debug Logs</title>
    <style>
        :root {
            --bg-dark: #0d1117;
            --bg-card: #161b22;
            --accent: #58a6ff;
            --success: #3fb950;
            --warning: #d29922;
            --danger: #f85149;
            --text: #c9d1d9;
            --text-muted: #8b949e;
            --border: #30363d;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', Monaco, monospace;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
        }
        .header {
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 15px 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .logo {
            font-size: 1.3em;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logo span { color: var(--accent); }
        .controls {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        .btn {
            padding: 8px 16px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-card);
            color: var(--text);
            cursor: pointer;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }
        .btn:hover {
            background: var(--border);
            border-color: var(--accent);
        }
        .btn.active {
            background: var(--accent);
            color: #000;
            border-color: var(--accent);
        }
        .btn-danger { border-color: var(--danger); }
        .btn-danger:hover { background: var(--danger); color: #fff; }
        .filters {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .filter-input {
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-dark);
            color: var(--text);
            font-size: 13px;
            width: 200px;
        }
        .filter-input:focus {
            outline: none;
            border-color: var(--accent);
        }
        select.filter-input {
            width: auto;
        }
        .stats {
            display: flex;
            gap: 20px;
            padding: 10px 25px;
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            font-size: 12px;
        }
        .stat {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .stat-label { color: var(--text-muted); }
        .stat-value { font-weight: 600; }
        .stat-value.info { color: var(--accent); }
        .stat-value.debug { color: var(--text-muted); }
        .stat-value.warning { color: var(--warning); }
        .stat-value.error { color: var(--danger); }
        .log-container {
            padding: 15px;
            height: calc(100vh - 130px);
            overflow-y: auto;
        }
        .log-line {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            line-height: 1.6;
            white-space: pre-wrap;
            word-break: break-all;
            margin-bottom: 2px;
        }
        .log-line:hover {
            background: var(--bg-card);
        }
        .log-line.info { border-left: 3px solid var(--accent); }
        .log-line.debug { border-left: 3px solid var(--text-muted); color: var(--text-muted); }
        .log-line.warning { border-left: 3px solid var(--warning); background: rgba(210, 153, 34, 0.1); }
        .log-line.error { border-left: 3px solid var(--danger); background: rgba(248, 81, 73, 0.1); }
        .log-time { color: var(--text-muted); }
        .log-tag { color: var(--accent); }
        .log-level { font-weight: 600; padding: 1px 6px; border-radius: 3px; font-size: 10px; }
        .log-level.INFO { background: rgba(88, 166, 255, 0.2); color: var(--accent); }
        .log-level.DEBUG { background: rgba(139, 148, 158, 0.2); color: var(--text-muted); }
        .log-level.WARNING { background: rgba(210, 153, 34, 0.3); color: var(--warning); }
        .log-level.ERROR { background: rgba(248, 81, 73, 0.3); color: var(--danger); }
        .empty-state {
            text-align: center;
            padding: 50px;
            color: var(--text-muted);
        }
        .empty-state .icon { font-size: 3em; margin-bottom: 15px; }
        .connection-status {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 12px;
        }
        .connection-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--danger);
        }
        .connection-dot.connected { background: var(--success); animation: pulse 2s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .back-link {
            color: var(--accent);
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .back-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <a href="/config" class="back-link">← Config</a>
            <span>|</span>
            <span>🔍</span> Debug Logs
        </div>
        <div class="filters">
            <input type="text" class="filter-input" id="searchFilter" placeholder="Cerca nei log...">
            <select class="filter-input" id="levelFilter">
                <option value="">Tutti i livelli</option>
                <option value="ERROR">Solo ERROR</option>
                <option value="WARNING">Solo WARNING</option>
                <option value="INFO">Solo INFO</option>
                <option value="DEBUG">Solo DEBUG</option>
            </select>
        </div>
        <div class="controls">
            <div class="connection-status">
                <div class="connection-dot" id="connectionDot"></div>
                <span id="connectionText">Disconnesso</span>
            </div>
            <button class="btn" id="autoScrollBtn" onclick="toggleAutoScroll()">
                <span>📜</span> Auto-scroll
            </button>
            <button class="btn" id="pauseBtn" onclick="togglePause()">
                <span>⏸️</span> Pausa
            </button>
            <button class="btn btn-danger" onclick="clearLogs()">
                <span>🗑️</span> Pulisci
            </button>
        </div>
    </header>

    <div class="stats">
        <div class="stat">
            <span class="stat-label">Totale:</span>
            <span class="stat-value" id="totalCount">0</span>
        </div>
        <div class="stat">
            <span class="stat-label">Info:</span>
            <span class="stat-value info" id="infoCount">0</span>
        </div>
        <div class="stat">
            <span class="stat-label">Debug:</span>
            <span class="stat-value debug" id="debugCount">0</span>
        </div>
        <div class="stat">
            <span class="stat-label">Warning:</span>
            <span class="stat-value warning" id="warningCount">0</span>
        </div>
        <div class="stat">
            <span class="stat-label">Error:</span>
            <span class="stat-value error" id="errorCount">0</span>
        </div>
    </div>

    <div class="log-container" id="logContainer">
        <div class="empty-state">
            <div class="icon">📋</div>
            <p>Caricamento log in corso...</p>
        </div>
    </div>

    <script>
        let logs = [];
        let autoScroll = true;
        let paused = false;
        let lastPosition = 0;
        let pollInterval = null;
        const MAX_LOGS = 2000;

        const container = document.getElementById('logContainer');
        const searchFilter = document.getElementById('searchFilter');
        const levelFilter = document.getElementById('levelFilter');

        function parseLogLine(line) {
            // Format: 2026-01-11 17:33:47 - 0.8.10_xxx - tag - LEVEL - tag - message
            const match = line.match(/^(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}) - ([^ ]+) - ([^ ]+) - (DEBUG|INFO|WARNING|ERROR) - [^ ]+ - (.*)$/);
            if (match) {
                return {
                    time: match[1],
                    version: match[2],
                    tag: match[3],
                    level: match[4],
                    message: match[5],
                    raw: line
                };
            }
            // Fallback: try to detect level from line content
            let level = 'INFO';
            if (line.includes(' - ERROR - ') || line.includes('ERROR')) level = 'ERROR';
            else if (line.includes(' - WARNING - ') || line.includes('WARNING')) level = 'WARNING';
            else if (line.includes(' - DEBUG - ')) level = 'DEBUG';
            return { raw: line, level: level };
        }

        function renderLog(log) {
            const div = document.createElement('div');
            const levelClass = (log.level || 'INFO').toLowerCase();
            div.className = 'log-line ' + levelClass;

            if (log.time) {
                div.innerHTML = `<span class="log-time">${log.time}</span> ` +
                    `<span class="log-level ${log.level}">${log.level}</span> ` +
                    `<span class="log-tag">[${log.tag}]</span> ${escapeHtml(log.message)}`;
            } else {
                div.textContent = log.raw;
            }
            return div;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function filterLogs() {
            const search = searchFilter.value.toLowerCase();
            const level = levelFilter.value;

            return logs.filter(log => {
                if (level && log.level !== level) return false;
                if (search && !log.raw.toLowerCase().includes(search)) return false;
                return true;
            });
        }

        function renderLogs() {
            const filtered = filterLogs();
            container.innerHTML = '';

            if (filtered.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="icon">📋</div><p>Nessun log trovato</p></div>';
                return;
            }

            const fragment = document.createDocumentFragment();
            filtered.forEach(log => fragment.appendChild(renderLog(log)));
            container.appendChild(fragment);

            if (autoScroll) {
                container.scrollTop = container.scrollHeight;
            }

            updateStats();
        }

        function updateStats() {
            const counts = { INFO: 0, DEBUG: 0, WARNING: 0, ERROR: 0 };
            logs.forEach(log => {
                if (counts[log.level] !== undefined) counts[log.level]++;
            });

            document.getElementById('totalCount').textContent = logs.length;
            document.getElementById('infoCount').textContent = counts.INFO;
            document.getElementById('debugCount').textContent = counts.DEBUG;
            document.getElementById('warningCount').textContent = counts.WARNING;
            document.getElementById('errorCount').textContent = counts.ERROR;
        }

        async function fetchLogs() {
            if (paused) return;

            try {
                const response = await fetch('/debug/logs/stream?position=' + lastPosition);
                const data = await response.json();

                document.getElementById('connectionDot').classList.add('connected');
                document.getElementById('connectionText').textContent = 'Connesso';

                if (data.lines && data.lines.length > 0) {
                    data.lines.forEach(line => {
                        if (line.trim()) {
                            logs.push(parseLogLine(line));
                        }
                    });

                    // Limita numero log
                    if (logs.length > MAX_LOGS) {
                        logs = logs.slice(-MAX_LOGS);
                    }

                    lastPosition = data.position;
                    renderLogs();
                }
            } catch (err) {
                document.getElementById('connectionDot').classList.remove('connected');
                document.getElementById('connectionText').textContent = 'Errore connessione';
                console.error('Fetch error:', err);
            }
        }

        function toggleAutoScroll() {
            autoScroll = !autoScroll;
            document.getElementById('autoScrollBtn').classList.toggle('active', autoScroll);
        }

        function togglePause() {
            paused = !paused;
            const btn = document.getElementById('pauseBtn');
            btn.classList.toggle('active', paused);
            btn.innerHTML = paused ? '<span>▶️</span> Riprendi' : '<span>⏸️</span> Pausa';
        }

        function clearLogs() {
            logs = [];
            renderLogs();
        }

        searchFilter.addEventListener('input', renderLogs);
        levelFilter.addEventListener('change', renderLogs);

        // Start polling
        fetchLogs();
        pollInterval = setInterval(fetchLogs, 1000);

        // Initial state
        document.getElementById('autoScrollBtn').classList.add('active');
    </script>
</body>
</html>
'''

async def debug_log_handler(request):
    """Handler per la pagina debug log viewer"""
    if not check_auth(request):
        return auth_required()
    return web.Response(text=DEBUG_LOG_TEMPLATE, content_type='text/html')

async def debug_log_stream_handler(request):
    """Handler per streaming log (polling)"""
    if not check_auth(request):
        return web.json_response({"error": "Unauthorized"}, status=401)

    try:
        position = int(request.query.get('position', 0))
        lines = []
        new_position = position

        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(0, 2)  # Fine file
                file_size = f.tell()

                if position == 0:
                    # Prima richiesta: ultimi 100KB
                    start = max(0, file_size - 100000)
                    f.seek(start)
                    if start > 0:
                        f.readline()  # Salta linea parziale
                else:
                    f.seek(position)

                lines = f.readlines()
                new_position = f.tell()

        return web.json_response({
            "lines": lines[-500:] if len(lines) > 500 else lines,  # Max 500 righe per request
            "position": new_position
        })

    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore lettura log: {e}")
        return web.json_response({"error": str(e), "lines": [], "position": 0})

def setup_config_routes(app):
    """Configura le route per il pannello"""
    app.router.add_get('/config', config_panel_handler)
    app.router.add_post('/config/save', config_save_handler)
    # Debug log viewer
    app.router.add_get('/debug/logs', debug_log_handler)
    app.router.add_get('/debug/logs/stream', debug_log_stream_handler)
    logger.bind(tag=TAG).info("Pannello configurazione attivo su /config")
