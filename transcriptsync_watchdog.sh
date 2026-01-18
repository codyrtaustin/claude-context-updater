#!/bin/bash
# TranscriptSync Watchdog
# Runs every 30 minutes to ensure scheduled tasks complete successfully
# Automatically triggers recovery if tasks are missed

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
DATE_STAMP=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/watchdog_${DATE_STAMP}.log"
HEARTBEAT_FILE="$LOG_DIR/heartbeat_sync.txt"

# Scheduled run times (in minutes from midnight)
# 9:30 AM = 570 minutes, 5:00 PM = 1020 minutes
MORNING_RUN=570
EVENING_RUN=1020

# Recovery window: how many minutes after scheduled time to wait before recovery
RECOVERY_WINDOW=45

mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WATCHDOG: $1" | tee -a "$LOG_FILE"
}

notify() {
    local title="$1"
    local message="$2"
    osascript -e "display notification \"$message\" with title \"$title\"" 2>/dev/null || true
}

# Get current time in minutes from midnight
get_current_minutes() {
    echo $(($(date +%H) * 60 + $(date +%M)))
}

# Check if heartbeat file exists and was updated today
check_heartbeat() {
    if [ ! -f "$HEARTBEAT_FILE" ]; then
        return 1
    fi

    local heartbeat_date=$(head -1 "$HEARTBEAT_FILE" | cut -d' ' -f1)
    local today=$(date +%Y-%m-%d)

    if [ "$heartbeat_date" = "$today" ]; then
        return 0
    fi
    return 1
}

# Check if heartbeat was updated after a specific time today
heartbeat_after_time() {
    local check_minutes=$1

    if [ ! -f "$HEARTBEAT_FILE" ]; then
        return 1
    fi

    local heartbeat_content=$(head -1 "$HEARTBEAT_FILE")
    local heartbeat_date=$(echo "$heartbeat_content" | cut -d' ' -f1)
    local today=$(date +%Y-%m-%d)

    if [ "$heartbeat_date" != "$today" ]; then
        return 1
    fi

    local heartbeat_time=$(echo "$heartbeat_content" | cut -d' ' -f2)
    local heartbeat_hour=$(echo "$heartbeat_time" | cut -d':' -f1)
    local heartbeat_min=$(echo "$heartbeat_time" | cut -d':' -f2)
    local heartbeat_minutes=$((10#$heartbeat_hour * 60 + 10#$heartbeat_min))

    if [ "$heartbeat_minutes" -ge "$check_minutes" ]; then
        return 0
    fi
    return 1
}

# Trigger recovery run
trigger_recovery() {
    local reason="$1"
    log "RECOVERY: Triggering sync due to: $reason"
    notify "TranscriptSync Watchdog" "Triggering recovery sync: $reason"

    # Run the sync script
    bash "$SCRIPT_DIR/transcriptsync_scheduled.sh" >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
        log "RECOVERY: Sync completed successfully"
    else
        log "RECOVERY: Sync failed - check logs"
        notify "TranscriptSync Watchdog" "Recovery sync failed!"
    fi
}

# Check if launchd agent is loaded
check_agent_loaded() {
    if launchctl list | grep -q "com.transcriptsync"; then
        return 0
    fi
    return 1
}

log "----------------------------------------"
log "Watchdog check started"

CURRENT_MINUTES=$(get_current_minutes)
log "Current time: $(date '+%H:%M') ($CURRENT_MINUTES minutes from midnight)"

# Check if main launchd agent is loaded
if ! check_agent_loaded; then
    log "WARNING: com.transcriptsync agent not loaded!"
    notify "TranscriptSync Watchdog" "LaunchAgent not loaded - run install_launchd.sh"
fi

# Determine which scheduled run(s) should have happened by now
NEEDS_RECOVERY=false
RECOVERY_REASON=""

# Check morning run (9:30 AM)
if [ "$CURRENT_MINUTES" -ge $((MORNING_RUN + RECOVERY_WINDOW)) ]; then
    # Morning run should have happened
    if ! heartbeat_after_time "$MORNING_RUN"; then
        # Check if we're past evening run time too
        if [ "$CURRENT_MINUTES" -ge $((EVENING_RUN + RECOVERY_WINDOW)) ]; then
            # Both runs should have happened, check for evening run
            if ! heartbeat_after_time "$EVENING_RUN"; then
                NEEDS_RECOVERY=true
                RECOVERY_REASON="No successful run today (missed both 9:30 AM and 5:00 PM)"
            fi
        elif [ "$CURRENT_MINUTES" -lt "$EVENING_RUN" ]; then
            # Between morning+recovery and evening, morning should have run
            NEEDS_RECOVERY=true
            RECOVERY_REASON="Missed 9:30 AM scheduled run"
        fi
    fi
fi

# Check evening run (5:00 PM)
if [ "$CURRENT_MINUTES" -ge $((EVENING_RUN + RECOVERY_WINDOW)) ]; then
    if ! heartbeat_after_time "$EVENING_RUN"; then
        NEEDS_RECOVERY=true
        RECOVERY_REASON="Missed 5:00 PM scheduled run"
    fi
fi

# Report status
if check_heartbeat; then
    LAST_RUN=$(head -1 "$HEARTBEAT_FILE")
    log "Last successful run: $LAST_RUN"
else
    log "No successful run recorded today"
fi

# Trigger recovery if needed
if [ "$NEEDS_RECOVERY" = true ]; then
    trigger_recovery "$RECOVERY_REASON"
else
    log "All scheduled runs are on track"
fi

log "Watchdog check complete"
log "----------------------------------------"
