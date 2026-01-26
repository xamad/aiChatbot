#!/bin/bash
# Xiaozhi Edge TTS Watchdog
# Monitors for TTS failures and restarts container if needed

CONTAINER_NAME="xiaozhi-esp32-server"
LOG_FILE="/var/log/xiaozhi-watchdog.log"
ERROR_THRESHOLD=10  # Number of TTS errors before restart
CHECK_INTERVAL=60   # Seconds between checks
COOLDOWN=300        # Seconds to wait after restart before checking again

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

restart_container() {
    log "Restarting $CONTAINER_NAME due to TTS failures..."
    docker restart "$CONTAINER_NAME"
    if [ $? -eq 0 ]; then
        log "Container restarted successfully. Waiting ${COOLDOWN}s cooldown..."
        sleep $COOLDOWN
    else
        log "ERROR: Failed to restart container!"
    fi
}

check_tts_errors() {
    # Count TTS errors in last 2 minutes of logs
    local error_count=$(docker logs "$CONTAINER_NAME" --since 2m 2>&1 | grep -c "Edge TTS请求失败")
    echo $error_count
}

check_container_health() {
    local health=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null)
    echo $health
}

log "Watchdog started for $CONTAINER_NAME"
log "Error threshold: $ERROR_THRESHOLD, Check interval: ${CHECK_INTERVAL}s"

while true; do
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log "WARNING: Container not running! Starting..."
        docker start "$CONTAINER_NAME"
        sleep 30
        continue
    fi

    # Check health status
    health=$(check_container_health)
    if [ "$health" != "healthy" ] && [ "$health" != "starting" ]; then
        log "WARNING: Container unhealthy (status: $health). Restarting..."
        restart_container
        continue
    fi

    # Check for TTS errors
    error_count=$(check_tts_errors)

    if [ "$error_count" -ge "$ERROR_THRESHOLD" ]; then
        log "ALERT: Detected $error_count TTS errors in last 2 minutes (threshold: $ERROR_THRESHOLD)"
        restart_container
    else
        # Only log periodically to avoid filling log
        if [ $((RANDOM % 10)) -eq 0 ]; then
            log "OK: Container healthy, TTS errors: $error_count"
        fi
    fi

    sleep $CHECK_INTERVAL
done
