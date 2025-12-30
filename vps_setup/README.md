# Setup Server Xiaozhi su VPS Hetzner

Server: **chatai.xamad.net**

## 1. Configura DNS

Crea un record A nel tuo DNS:
```
chatai.xamad.net  →  [IP del VPS Hetzner]
```

## 2. Installa sul VPS

```bash
# Connettiti al VPS
ssh root@vps2.xamad.net

# Scarica e esegui lo script
curl -O https://raw.githubusercontent.com/xamad/aiChatbot/claude/setup-esp32-chatbot-hB2sc/vps_setup/install.sh
chmod +x install.sh
./install.sh
```

## 3. Configura API Key

```bash
nano /opt/xiaozhi-server/main/xiaozhi-server/.env
```

Modifica:
```env
# DeepSeek (consigliato - economico ~$0.28/1M token)
LLM_TYPE=deepseek
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# Oppure OpenAI
#LLM_TYPE=openai
#OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

Ottieni API key:
- **DeepSeek**: https://platform.deepseek.com/ (consigliato, economico)
- OpenAI: https://platform.openai.com/

## 4. Carica Plugin Custom

Dal tuo PC locale:
```bash
cd vps_setup
chmod +x upload_plugins.sh
./upload_plugins.sh
```

## 5. Avvia Server

```bash
systemctl start xiaozhi
systemctl status xiaozhi

# Log in tempo reale
journalctl -u xiaozhi -f
```

---

## 6. Configura ESP32 (SENZA ricompilare!)

### Passo 1: Flash firmware standard
Usa il firmware già scaricato (`firmware/merged-binary.bin`) - NON serve ricompilare!

### Passo 2: Entra in modalità configurazione
1. Accendi l'ESP32
2. Premi il pulsante **BOOT** per entrare in modalità config WiFi
3. Connettiti all'hotspot WiFi creato dall'ESP32 (nome tipo "Xiaozhi-XXXX")

### Passo 3: Configura server custom
1. Apri il browser e vai a `192.168.4.1`
2. Configura il tuo WiFi (SSID e password)
3. **IMPORTANTE**: Clicca su **"高级选项" (Opzioni Avanzate)** in alto
4. Nel campo **OTA URL** inserisci:
   ```
   https://chatai.xamad.net/xiaozhi/ota/
   ```
5. Clicca **Salva** e riavvia il dispositivo

### Passo 4: Verifica
Dopo il riavvio, l'ESP32 si connetterà automaticamente al tuo server `chatai.xamad.net`!

Verifica nei log del server:
```bash
journalctl -u xiaozhi -f
```

---

## Endpoint Server

| Servizio | URL |
|----------|-----|
| OTA Config | https://chatai.xamad.net/xiaozhi/ota/ |
| WebSocket | wss://chatai.xamad.net/xiaozhi/v1/ |
| HTTP API | https://chatai.xamad.net |

## Comandi Utili

```bash
# Status server
systemctl status xiaozhi

# Riavvia server
systemctl restart xiaozhi

# Log
journalctl -u xiaozhi -f

# Test OTA endpoint
curl https://chatai.xamad.net/xiaozhi/ota/
# Deve rispondere: "OTA接口运行正常，websocket集群数量：1"
```

## Troubleshooting

### Server non parte
```bash
cd /opt/xiaozhi-server/main/xiaozhi-server
source venv/bin/activate
python app.py
```

### Errore certificato SSL
```bash
certbot --nginx -d chatai.xamad.net
```

### ESP32 non si connette
1. Verifica che l'URL OTA sia esattamente: `https://chatai.xamad.net/xiaozhi/ota/`
2. Controlla i log del server: `journalctl -u xiaozhi -f`
3. Verifica firewall: `ufw allow 443/tcp && ufw allow 8765/tcp`
4. Testa l'endpoint OTA: `curl https://chatai.xamad.net/xiaozhi/ota/`

## Plugin Inclusi

| Plugin | Funzione |
|--------|----------|
| `web_search.py` | Ricerca web (DuckDuckGo) |
| `meteo_italia.py` | Meteo tutte le città italiane |
| `radio_italia.py` | 17+ stazioni radio italiane |
| `ricette.py` | Ricette di cucina |
