"""
Pannello Configurazione Web - Configura chatbot via browser
Accessibile su http://chatai.xamad.net/config
"""

import os
import json
import yaml
from aiohttp import web
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()

CONFIG_FILE = "/opt/xiaozhi-server/main/xiaozhi-server/data/.config.yaml"
USER_PREFS_FILE = "/opt/xiaozhi-server/main/xiaozhi-server/data/user_preferences.json"

# Voci disponibili Edge TTS (italiane)
VOCI_DISPONIBILI = {
    "it-IT-ElsaNeural": {"nome": "Elsa", "genere": "femminile", "desc": "Voce femminile naturale"},
    "it-IT-IsabellaNeural": {"nome": "Isabella", "genere": "femminile", "desc": "Voce femminile giovane"},
    "it-IT-DiegoNeural": {"nome": "Diego", "genere": "maschile", "desc": "Voce maschile naturale"},
    "it-IT-GiuseppeNeural": {"nome": "Giuseppe", "genere": "maschile", "desc": "Voce maschile matura"},
    "it-IT-BenignoNeural": {"nome": "Benigno", "genere": "maschile", "desc": "Voce maschile calda"},
    "it-IT-CalimeroNeural": {"nome": "Calimero", "genere": "maschile", "desc": "Voce maschile espressiva"},
    "it-IT-CataldoNeural": {"nome": "Cataldo", "genere": "maschile", "desc": "Voce maschile professionale"},
    "it-IT-FabiolaNeural": {"nome": "Fabiola", "genere": "femminile", "desc": "Voce femminile elegante"},
    "it-IT-FiammaNeural": {"nome": "Fiamma", "genere": "femminile", "desc": "Voce femminile vivace"},
    "it-IT-GianniNeural": {"nome": "Gianni", "genere": "maschile", "desc": "Voce maschile amichevole"},
    "it-IT-ImeldaNeural": {"nome": "Imelda", "genere": "femminile", "desc": "Voce femminile matura"},
    "it-IT-IrmaNeural": {"nome": "Irma", "genere": "femminile", "desc": "Voce femminile dolce"},
    "it-IT-LisandroNeural": {"nome": "Lisandro", "genere": "maschile", "desc": "Voce maschile giovane"},
    "it-IT-PalmiraNeural": {"nome": "Palmira", "genere": "femminile", "desc": "Voce femminile calma"},
    "it-IT-PierinaNeural": {"nome": "Pierina", "genere": "femminile", "desc": "Voce femminile tradizionale"},
    "it-IT-RinaldoNeural": {"nome": "Rinaldo", "genere": "maschile", "desc": "Voce maschile robusta"},
}

# Modelli LLM disponibili
MODELLI_DISPONIBILI = {
    # Groq (velocissimi, gratis!)
    "llama-3.3-70b-versatile": {"nome": "Llama 3.3 70B", "provider": "Groq", "desc": "⚡ Velocissimo, raccomandato!", "llm_type": "GroqLLM"},
    "llama-3.1-70b-versatile": {"nome": "Llama 3.1 70B", "provider": "Groq", "desc": "⚡ Molto veloce", "llm_type": "GroqLLM"},
    "llama-3.1-8b-instant": {"nome": "Llama 3.1 8B", "provider": "Groq", "desc": "⚡ Ultra veloce, leggero", "llm_type": "GroqLLM"},
    "mixtral-8x7b-32768": {"nome": "Mixtral 8x7B", "provider": "Groq", "desc": "⚡ Buon bilanciamento", "llm_type": "GroqLLM"},
    "gemma2-9b-it": {"nome": "Gemma 2 9B", "provider": "Groq", "desc": "⚡ Google, veloce", "llm_type": "GroqLLM"},
    # ChatGLM (più lenti, server in Cina)
    "glm-4-plus": {"nome": "ChatGLM 4 Plus", "provider": "ZhipuAI", "desc": "Potente ma lento", "llm_type": "ChatGLMLLM"},
    "glm-4-flash": {"nome": "ChatGLM 4 Flash", "provider": "ZhipuAI", "desc": "Veloce (per ChatGLM)", "llm_type": "ChatGLMLLM"},
}

def load_preferences() -> dict:
    """Carica preferenze utente"""
    defaults = {
        "nome_chatbot": "Xiaozhi",
        "descrizione": "Assistente vocale intelligente in italiano",
        "voce": "it-IT-ElsaNeural",
        "pitch": "+0Hz",
        "rate": "+0%",
        "modello": "glm-4-flash"
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
        logger.bind(tag=TAG).info(f"Preferenze salvate: {prefs}")
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore salvataggio preferenze: {e}")

def update_config_yaml(voce: str, modello: str):
    """Aggiorna il file config.yaml con le nuove impostazioni"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # Aggiorna voce TTS
        if 'TTS' in config and 'EdgeTTS' in config['TTS']:
            config['TTS']['EdgeTTS']['voice'] = voce

        # Determina il tipo di LLM dal modello selezionato
        model_info = MODELLI_DISPONIBILI.get(modello, {})
        llm_type = model_info.get("llm_type", "GroqLLM")

        # Aggiorna modello LLM nel provider corretto
        if llm_type == "GroqLLM" and 'LLM' in config and 'GroqLLM' in config['LLM']:
            config['LLM']['GroqLLM']['model_name'] = modello
        elif llm_type == "ChatGLMLLM" and 'LLM' in config and 'ChatGLMLLM' in config['LLM']:
            config['LLM']['ChatGLMLLM']['model_name'] = modello

        # Aggiorna selected_module per usare il provider corretto
        if 'selected_module' in config:
            config['selected_module']['LLM'] = llm_type

        # Aggiorna anche intent_llm per usare lo stesso provider
        if 'Intent' in config and 'intent_llm' in config['Intent']:
            config['Intent']['intent_llm']['llm'] = llm_type

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        logger.bind(tag=TAG).info(f"Config aggiornato: voce={voce}, modello={modello}, llm_type={llm_type}")
        return True
    except Exception as e:
        logger.bind(tag=TAG).error(f"Errore aggiornamento config: {e}")
        return False

# HTML Template per il pannello
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚙️ Configurazione Chatbot</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2em;
        }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        .card h2 {
            margin-bottom: 20px;
            color: #4fc3f7;
            font-size: 1.3em;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #b0bec5;
        }
        input[type="text"], select, textarea {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 10px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #4fc3f7;
        }
        textarea {
            min-height: 100px;
            resize: vertical;
        }
        .voice-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }
        .voice-option {
            background: rgba(0,0,0,0.3);
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 10px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .voice-option:hover {
            border-color: #4fc3f7;
            transform: translateY(-2px);
        }
        .voice-option.selected {
            border-color: #4fc3f7;
            background: rgba(79, 195, 247, 0.2);
        }
        .voice-option input { display: none; }
        .voice-name {
            font-weight: bold;
            margin-bottom: 5px;
        }
        .voice-gender {
            font-size: 0.85em;
            color: #90a4ae;
        }
        .gender-male { color: #64b5f6; }
        .gender-female { color: #f48fb1; }
        .slider-container {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        input[type="range"] {
            flex: 1;
            height: 8px;
            -webkit-appearance: none;
            background: rgba(255,255,255,0.2);
            border-radius: 4px;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: #4fc3f7;
            border-radius: 50%;
            cursor: pointer;
        }
        .slider-value {
            min-width: 60px;
            text-align: center;
            font-weight: bold;
        }
        .btn {
            display: inline-block;
            padding: 15px 40px;
            background: linear-gradient(135deg, #4fc3f7 0%, #29b6f6 100%);
            color: #fff;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(79, 195, 247, 0.4);
        }
        .btn-container {
            text-align: center;
            margin-top: 30px;
        }
        .alert {
            padding: 15px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: none;
        }
        .alert-success {
            background: rgba(76, 175, 80, 0.3);
            border: 1px solid #4caf50;
        }
        .alert-error {
            background: rgba(244, 67, 54, 0.3);
            border: 1px solid #f44336;
        }
        .preview {
            background: rgba(0,0,0,0.4);
            border-radius: 10px;
            padding: 20px;
            margin-top: 15px;
        }
        .preview-label {
            font-size: 0.9em;
            color: #90a4ae;
            margin-bottom: 10px;
        }
        .preview-text {
            font-style: italic;
            color: #e0e0e0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚙️ Configurazione Chatbot</h1>

        <div id="alert" class="alert"></div>

        <form id="configForm">
            <!-- Identità -->
            <div class="card">
                <h2>🤖 Identità Chatbot</h2>
                <div class="form-group">
                    <label for="nome">Nome del Chatbot</label>
                    <input type="text" id="nome" name="nome_chatbot" value="{nome_chatbot}" placeholder="Es: Xiaozhi, Giulia, Marco...">
                </div>
                <div class="form-group">
                    <label for="descrizione">Descrizione / Personalità</label>
                    <textarea id="descrizione" name="descrizione" placeholder="Descrivi come deve comportarsi il chatbot...">{descrizione}</textarea>
                </div>
            </div>

            <!-- Voce -->
            <div class="card">
                <h2>🎤 Voce</h2>
                <div class="form-group">
                    <label>Seleziona la voce</label>
                    <div class="voice-grid">
                        {voci_html}
                    </div>
                </div>

                <div class="form-group">
                    <label>Velocità parlato</label>
                    <div class="slider-container">
                        <span>Lento</span>
                        <input type="range" id="rate" name="rate" min="-50" max="50" value="{rate_value}">
                        <span>Veloce</span>
                        <span class="slider-value" id="rateValue">{rate}</span>
                    </div>
                </div>

                <div class="form-group">
                    <label>Tono voce (Pitch)</label>
                    <div class="slider-container">
                        <span>Grave</span>
                        <input type="range" id="pitch" name="pitch" min="-50" max="50" value="{pitch_value}">
                        <span>Acuto</span>
                        <span class="slider-value" id="pitchValue">{pitch}</span>
                    </div>
                </div>
            </div>

            <!-- Modello LLM -->
            <div class="card">
                <h2>🧠 Modello Intelligenza</h2>
                <div class="form-group">
                    <label for="modello">Modello LLM</label>
                    <select id="modello" name="modello">
                        {modelli_html}
                    </select>
                </div>
                <div class="preview">
                    <div class="preview-label">ℹ️ Info modello selezionato</div>
                    <div class="preview-text" id="modelInfo">Seleziona un modello per vedere i dettagli</div>
                </div>
            </div>

            <div class="btn-container">
                <button type="submit" class="btn">💾 Salva Configurazione</button>
            </div>
        </form>
    </div>

    <script>
        // Gestione selezione voce
        document.querySelectorAll('.voice-option').forEach(opt => {
            opt.addEventListener('click', function() {
                document.querySelectorAll('.voice-option').forEach(o => o.classList.remove('selected'));
                this.classList.add('selected');
                this.querySelector('input').checked = true;
            });
        });

        // Slider values
        document.getElementById('rate').addEventListener('input', function() {
            document.getElementById('rateValue').textContent = (this.value >= 0 ? '+' : '') + this.value + '%';
        });
        document.getElementById('pitch').addEventListener('input', function() {
            document.getElementById('pitchValue').textContent = (this.value >= 0 ? '+' : '') + this.value + 'Hz';
        });

        // Model info
        const modelInfo = {model_info_json};
        document.getElementById('modello').addEventListener('change', function() {
            const info = modelInfo[this.value];
            if (info) {
                document.getElementById('modelInfo').textContent = info.nome + ' (' + info.provider + ') - ' + info.desc;
            }
        });

        // Form submit
        document.getElementById('configForm').addEventListener('submit', async function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const data = {};
            formData.forEach((value, key) => data[key] = value);

            // Aggiungi valori slider formattati
            data.rate = (document.getElementById('rate').value >= 0 ? '+' : '') + document.getElementById('rate').value + '%';
            data.pitch = (document.getElementById('pitch').value >= 0 ? '+' : '') + document.getElementById('pitch').value + 'Hz';

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
                    alert.textContent = '✅ ' + result.message;
                    alert.style.display = 'block';
                } else {
                    alert.className = 'alert alert-error';
                    alert.textContent = '❌ ' + result.message;
                    alert.style.display = 'block';
                }

                setTimeout(() => alert.style.display = 'none', 5000);
            } catch (err) {
                console.error(err);
            }
        });
    </script>
</body>
</html>
'''

async def config_panel_handler(request):
    """Handler per la pagina di configurazione"""
    prefs = load_preferences()

    # Genera HTML per le voci
    voci_html = ""
    for voice_id, info in VOCI_DISPONIBILI.items():
        selected = "selected" if voice_id == prefs.get("voce") else ""
        checked = "checked" if voice_id == prefs.get("voce") else ""
        gender_class = "gender-male" if info["genere"] == "maschile" else "gender-female"
        gender_icon = "👨" if info["genere"] == "maschile" else "👩"

        voci_html += f'''
        <label class="voice-option {selected}">
            <input type="radio" name="voce" value="{voice_id}" {checked}>
            <div class="voice-name">{gender_icon} {info["nome"]}</div>
            <div class="voice-gender {gender_class}">{info["desc"]}</div>
        </label>
        '''

    # Genera HTML per i modelli
    modelli_html = ""
    for model_id, info in MODELLI_DISPONIBILI.items():
        selected = "selected" if model_id == prefs.get("modello") else ""
        modelli_html += f'<option value="{model_id}" {selected}>{info["nome"]} - {info["desc"]}</option>'

    # Parse pitch e rate values
    pitch = prefs.get("pitch", "+0Hz")
    rate = prefs.get("rate", "+0%")
    pitch_value = int(pitch.replace("Hz", "").replace("+", ""))
    rate_value = int(rate.replace("%", "").replace("+", ""))

    # Render template usando replace invece di format (per evitare conflitti con CSS {})
    html = HTML_TEMPLATE
    html = html.replace("{nome_chatbot}", prefs.get("nome_chatbot", "Xiaozhi"))
    html = html.replace("{descrizione}", prefs.get("descrizione", ""))
    html = html.replace("{voci_html}", voci_html)
    html = html.replace("{modelli_html}", modelli_html)
    html = html.replace("{pitch}", pitch)
    html = html.replace("{rate}", rate)
    html = html.replace("{pitch_value}", str(pitch_value))
    html = html.replace("{rate_value}", str(rate_value))
    html = html.replace("{model_info_json}", json.dumps(MODELLI_DISPONIBILI))

    return web.Response(text=html, content_type='text/html')

async def config_save_handler(request):
    """Handler per salvare la configurazione"""
    try:
        data = await request.json()

        # Salva preferenze
        prefs = {
            "nome_chatbot": data.get("nome_chatbot", "Xiaozhi"),
            "descrizione": data.get("descrizione", ""),
            "voce": data.get("voce", "it-IT-ElsaNeural"),
            "pitch": data.get("pitch", "+0Hz"),
            "rate": data.get("rate", "+0%"),
            "modello": data.get("modello", "glm-4-flash")
        }

        save_preferences(prefs)

        # Aggiorna config.yaml
        update_config_yaml(prefs["voce"], prefs["modello"])

        return web.json_response({
            "success": True,
            "message": "Configurazione salvata! Riavvia il chatbot per applicare le modifiche."
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
