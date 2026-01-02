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

CONFIG_FILE = "/opt/xiaozhi-server/main/xiaozhi-server/data/.config.yaml"
USER_PREFS_FILE = "/opt/xiaozhi-server/main/xiaozhi-server/data/user_preferences.json"
FUNCTIONS_DIR = "/opt/xiaozhi-server/main/xiaozhi-server/plugins_func/functions"

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

# Categorie funzioni
CATEGORIE_FUNZIONI = {
    "media": {"nome": "Media & Audio", "icon": "🎵", "funzioni": ["radio_italia", "podcast_italia", "cerca_musica", "karaoke"]},
    "info": {"nome": "Informazioni", "icon": "📰", "funzioni": ["meteo_italia", "notizie_italia", "oroscopo", "lotto_estrazioni", "accadde_oggi", "santo_del_giorno"]},
    "intrattenimento": {"nome": "Intrattenimento", "icon": "🎭", "funzioni": ["barzelletta_bambini", "barzelletta_adulti", "quiz_trivia", "storie_bambini", "curiosita", "proverbi_italiani", "frase_del_giorno"]},
    "giochi": {"nome": "Giochi", "icon": "🎮", "funzioni": ["impiccato", "battaglia_navale", "venti_domande", "cruciverba_vocale", "chi_vuol_essere", "dado", "memory_vocale"]},
    "utility": {"nome": "Utilità", "icon": "🛠️", "funzioni": ["timer_sveglia", "promemoria", "calcolatrice", "convertitore", "traduttore", "lista_spesa", "note_vocali", "rubrica_vocale", "agenda_eventi", "chi_sono"]},
    "casa": {"nome": "Casa Smart", "icon": "🏠", "funzioni": ["domotica"]},
    "benessere": {"nome": "Benessere", "icon": "🧘", "funzioni": ["meditazione", "supporto_emotivo", "compagno_notturno", "check_benessere", "ginnastica_dolce", "conta_acqua"]},
    "special": {"nome": "Speciali", "icon": "⭐", "funzioni": ["giannino_easter_egg", "osterie_goliardiche", "sommario_funzioni", "intrattenitore_anziani", "complimenti"]},
    "guide": {"nome": "Guide", "icon": "🗺️", "funzioni": ["guida_turistica", "guida_ristoranti", "ricette", "ricette_ingredienti", "numeri_utili"]},
    "ricerca": {"nome": "Ricerca", "icon": "🔍", "funzioni": ["web_search", "leggi_pagina"]},
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
                disabled_functions: disabledFunctions
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

def setup_config_routes(app):
    """Configura le route per il pannello"""
    app.router.add_get('/config', config_panel_handler)
    app.router.add_post('/config/save', config_save_handler)
    logger.bind(tag=TAG).info("Pannello configurazione attivo su /config")
