#!/bin/bash
# Xiaozhi Server Watchdog
# Controlla se il server è attivo e funzionante, lo riavvia se necessario

CONTAINER_NAME="xiaozhi-esp32-server"
COMPOSE_DIR="/opt/xiaozhi-server/main/xiaozhi-server"
LOG_FILE="/var/log/xiaozhi-watchdog.log"
WEBSOCKET_PORT=8000
MAX_RESTART_ATTEMPTS=3
RESTART_COOLDOWN=300  # 5 minuti tra tentativi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

check_container_running() {
    docker inspect -f '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -q "true"
}

check_websocket_responding() {
    # Verifica che la porta WebSocket risponda
    timeout 5 bash -c "echo > /dev/tcp/127.0.0.1/$WEBSOCKET_PORT" 2>/dev/null
}

restart_server() {
    log "Tentativo di riavvio del server..."
    cd "$COMPOSE_DIR"
    docker compose down 2>/dev/null
    sleep 2
    docker compose up -d 2>/dev/null

    # Aspetta che il server si avvii
    sleep 10

    if check_container_running && check_websocket_responding; then
        log "✅ Server riavviato con successo!"
        return 0
    else
        log "❌ Riavvio fallito"
        return 1
    fi
}

# Controlla file di cooldown per evitare restart continui
COOLDOWN_FILE="/tmp/xiaozhi-watchdog-cooldown"
if [[ -f "$COOLDOWN_FILE" ]]; then
    LAST_RESTART=$(cat "$COOLDOWN_FILE")
    NOW=$(date +%s)
    DIFF=$((NOW - LAST_RESTART))
    if [[ $DIFF -lt $RESTART_COOLDOWN ]]; then
        log "⏳ Cooldown attivo, attendo ancora $((RESTART_COOLDOWN - DIFF)) secondi"
        exit 0
    fi
fi

# Check 1: Container in esecuzione?
if ! check_container_running; then
    log "⚠️ Container non in esecuzione!"
    restart_server
    date +%s > "$COOLDOWN_FILE"
    exit 0
fi

# Check 2: WebSocket risponde?
if ! check_websocket_responding; then
    log "⚠️ WebSocket non risponde sulla porta $WEBSOCKET_PORT!"
    restart_server
    date +%s > "$COOLDOWN_FILE"
    exit 0
fi

# Tutto OK
log "✅ Server funzionante"
