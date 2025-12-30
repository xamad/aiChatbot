#!/bin/bash
#
# Carica i plugin custom sul VPS
#

VPS_HOST="chatai.xamad.net"
VPS_USER="root"
REMOTE_DIR="/opt/xiaozhi-server/main/xiaozhi-server/plugins_func/functions"

echo "Caricamento plugin su ${VPS_HOST}..."

# Carica tutti i plugin
scp ../plugins_custom/*.py ${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/

echo "Riavvio server..."
ssh ${VPS_USER}@${VPS_HOST} "systemctl restart xiaozhi"

echo "Plugin caricati e server riavviato!"
