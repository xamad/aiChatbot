#!/bin/bash
# Xiaozhi Chatbot Watchdog Script
# Monitora il container e lo riavvia se non risponde

CONTAINER_NAME="xiaozhi-esp32-server"
HEALTH_URL="http://localhost:8003/xiaozhi/ota/"
CHECK_INTERVAL=300
MAX_FAILURES=3
LOG_FILE="/var/log/xiaozhi-watchdog.log"

failure_count=0

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

check_health() {
    # Verifica che il container sia running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "WARN: Container $CONTAINER_NAME non in esecuzione"
        return 1
    fi

    # Verifica health status del container
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null)
    if [ "$health_status" = "unhealthy" ]; then
        log "WARN: Container unhealthy secondo Docker healthcheck"
        return 1
    fi

    # Verifica HTTP endpoint
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null)
    if [ "$http_code" != "200" ] && [ "$http_code" != "405" ]; then
        log "WARN: HTTP check fallito (code: $http_code)"
        return 1
    fi

    # Verifica porta WebSocket
    if ! ss -tlnp | grep -q ":8000 "; then
        log "WARN: Porta WebSocket 8000 non in ascolto"
        return 1
    fi

    return 0
}

restart_container() {
    log "ACTION: Riavvio container $CONTAINER_NAME"
    docker restart "$CONTAINER_NAME"
    sleep 30
    
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "OK: Container riavviato con successo"
        return 0
    else
        log "ERROR: Riavvio fallito, tentativo docker-compose"
        cd /opt/xiaozhi-server/main/xiaozhi-server
        docker compose up -d
        sleep 30
        return $?
    fi
}

log "=== Watchdog avviato ==="
log "Container: $CONTAINER_NAME"
log "Health URL: $HEALTH_URL"
log "Intervallo check: ${CHECK_INTERVAL}s"

while true; do
    if check_health; then
        if [ $failure_count -gt 0 ]; then
            log "OK: Servizio ripristinato"
        fi
        failure_count=0
    else
        ((failure_count++))
        log "FAIL: Conteggio fallimenti: $failure_count / $MAX_FAILURES"
        
        if [ $failure_count -ge $MAX_FAILURES ]; then
            restart_container
            failure_count=0
        fi
    fi
    
    sleep $CHECK_INTERVAL
done
