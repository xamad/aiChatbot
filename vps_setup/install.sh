#!/bin/bash
#
# Xiaozhi ESP32 Server - Script di installazione per VPS Ubuntu
# Server: vps2.xamad.net
#

set -e

echo "=========================================="
echo "  Xiaozhi ESP32 Server - Installazione"
echo "=========================================="

# Configurazione
INSTALL_DIR="/opt/xiaozhi-server"
SERVICE_NAME="xiaozhi"
DOMAIN="chatai.xamad.net"

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# Verifica root
if [ "$EUID" -ne 0 ]; then
    print_error "Esegui come root: sudo bash install.sh"
    exit 1
fi

# 1. Aggiorna sistema
print_status "Aggiornamento sistema..."
apt update && apt upgrade -y

# 2. Installa dipendenze
print_status "Installazione dipendenze..."
apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx \
    build-essential libffi-dev libssl-dev portaudio19-dev ffmpeg

# 3. Clona repository
print_status "Download server Xiaozhi..."
if [ -d "$INSTALL_DIR" ]; then
    print_warning "Directory esistente, aggiorno..."
    cd "$INSTALL_DIR" && git pull
else
    git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git "$INSTALL_DIR"
fi

# 4. Crea virtual environment
print_status "Creazione ambiente Python..."
cd "$INSTALL_DIR/main/xiaozhi-server"
python3 -m venv venv
source venv/bin/activate

# 5. Installa dipendenze Python
print_status "Installazione dipendenze Python..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. Crea file di configurazione
print_status "Creazione configurazione..."
if [ ! -f ".env" ]; then
    cat > .env << 'ENVFILE'
# Xiaozhi Server Configuration
# Modifica questi valori!

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
WEBSOCKET_PORT=8765

# AI Model - Scegli uno:
# Per DeepSeek (consigliato, economico):
LLM_TYPE=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Per OpenAI:
#LLM_TYPE=openai
#OPENAI_API_KEY=your_openai_api_key_here

# Per modello locale (Ollama):
#LLM_TYPE=ollama
#OLLAMA_HOST=http://localhost:11434
#OLLAMA_MODEL=qwen2.5:7b

# TTS (Text-to-Speech)
TTS_TYPE=edge
TTS_VOICE=it-IT-ElsaNeural

# ASR (Speech-to-Text)
ASR_TYPE=faster-whisper
ASR_MODEL=small

# Logging
LOG_LEVEL=INFO
ENVFILE
    print_warning "Configura .env con le tue API key!"
fi

# 7. Copia plugin custom
print_status "Installazione plugin custom..."
PLUGINS_SRC="/tmp/xiaozhi-plugins"
if [ -d "$PLUGINS_SRC" ]; then
    cp "$PLUGINS_SRC"/*.py plugins_func/functions/ 2>/dev/null || true
    print_status "Plugin custom installati"
fi

# 8. Crea servizio systemd
print_status "Creazione servizio systemd..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << SERVICEFILE
[Unit]
Description=Xiaozhi ESP32 AI Chatbot Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}/main/xiaozhi-server
Environment=PATH=${INSTALL_DIR}/main/xiaozhi-server/venv/bin
ExecStart=${INSTALL_DIR}/main/xiaozhi-server/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEFILE

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}

# 9. Configura Nginx
print_status "Configurazione Nginx..."
cat > /etc/nginx/sites-available/xiaozhi << NGINXCONF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }
}
NGINXCONF

ln -sf /etc/nginx/sites-available/xiaozhi /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# 10. Configura firewall
print_status "Configurazione firewall..."
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8765/tcp
ufw --force enable

# 11. SSL con Let's Encrypt
print_status "Configurazione SSL..."
certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos --email admin@${DOMAIN} || \
    print_warning "SSL non configurato, esegui: certbot --nginx -d ${DOMAIN}"

echo ""
echo "=========================================="
echo "  Installazione completata!"
echo "=========================================="
echo ""
echo "Prossimi passi:"
echo ""
echo "1. Configura le API key:"
echo "   nano ${INSTALL_DIR}/main/xiaozhi-server/.env"
echo ""
echo "2. Ottieni API key DeepSeek (consigliato):"
echo "   https://platform.deepseek.com/"
echo ""
echo "3. Avvia il server:"
echo "   systemctl start ${SERVICE_NAME}"
echo ""
echo "4. Verifica status:"
echo "   systemctl status ${SERVICE_NAME}"
echo ""
echo "5. Vedi log:"
echo "   journalctl -u ${SERVICE_NAME} -f"
echo ""
echo "Server disponibile su:"
echo "  HTTP:      http://${DOMAIN}"
echo "  WebSocket: ws://${DOMAIN}:8765"
echo ""
print_status "Ricorda di configurare il firmware ESP32!"
echo ""
