#!/bin/bash
# TranscriptSync scheduled task wrapper
# This script is called by launchd at 9:30 AM and 5:00 PM PT
# It handles environment setup, venv activation, and proper logging

set -e

# Configuration - can be overridden via environment variables
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
DATE_STAMP=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/sync_${DATE_STAMP}.log"
HEARTBEAT_FILE="$LOG_DIR/heartbeat_sync.txt"

# Python path: use env var, or detect from common locations
PYTHON_PATH="${TRANSCRIPTSYNC_PYTHON:-}"
if [ -z "$PYTHON_PATH" ]; then
    # Try common Python 3 locations
    for p in /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
             /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
             /usr/local/bin/python3 \
             /opt/homebrew/bin/python3 \
             /usr/bin/python3; do
        if [ -x "$p" ]; then
            PYTHON_PATH="$p"
            break
        fi
    done
fi

# Google Drive target folder ID - can be overridden via environment
GDRIVE_FOLDER_ID="${TRANSCRIPTSYNC_GDRIVE_FOLDER_ID:-1Xk8AqldChn0G2KBdRepzTb-1czbSGry4}"
SOURCE_DIR="${TRANSCRIPTSYNC_SOURCE_DIR:-/Users/codyaustin/Documents/Katib/podcasts}"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Notification function (macOS native)
notify() {
    local title="$1"
    local message="$2"
    osascript -e "display notification \"$message\" with title \"$title\"" 2>/dev/null || true
}

log "=========================================="
log "Starting TranscriptSync scheduled run"
log "Script directory: $SCRIPT_DIR"

# Set up PATH for launchd environment
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Library/Frameworks/Python.framework/Versions/3.11/bin:$PATH"
export HOME="/Users/codyaustin"

# Change to script directory
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists, otherwise use system Python
if [ -d "$SCRIPT_DIR/venv" ]; then
    log "Activating virtual environment"
    source "$SCRIPT_DIR/venv/bin/activate"
    PYTHON_CMD="python"
else
    log "No venv found, using system Python: $PYTHON_PATH"
    PYTHON_CMD="$PYTHON_PATH"
fi

# Verify Python and dependencies
log "Verifying Python installation..."
if ! $PYTHON_CMD --version >> "$LOG_FILE" 2>&1; then
    log "ERROR: Python not found"
    notify "TranscriptSync Error" "Python not found"
    exit 1
fi

# Verify required packages
log "Verifying dependencies..."
if ! $PYTHON_CMD -c "import watchdog; from google.oauth2.credentials import Credentials" 2>/dev/null; then
    log "WARNING: Some dependencies missing. Attempting to install..."
    $PYTHON_CMD -m pip install -r "$SCRIPT_DIR/requirements.txt" >> "$LOG_FILE" 2>&1 || {
        log "ERROR: Failed to install dependencies"
        notify "TranscriptSync Error" "Failed to install dependencies"
        exit 1
    }
fi

# Run the sync script
log "Running update_claude_context.py..."
log "Source: $SOURCE_DIR"
log "Target folder: $GDRIVE_FOLDER_ID"

OUTPUT=$($PYTHON_CMD "$SCRIPT_DIR/update_claude_context.py" \
    --to-gdocs "$GDRIVE_FOLDER_ID" \
    --dirs "$SOURCE_DIR" 2>&1) || {
    log "ERROR: Script failed"
    log "$OUTPUT"
    notify "TranscriptSync Error" "Sync script failed - check logs"
    exit 1
}

# Log the output
echo "$OUTPUT" >> "$LOG_FILE"

# Extract summary counts (grep -c returns 1 on no match, so we handle that)
CONVERTED=$(echo "$OUTPUT" | grep -c "✓ Converted:" 2>/dev/null || true)
UPDATED=$(echo "$OUTPUT" | grep -c "✓ Updated:" 2>/dev/null || true)
SKIPPED=$(echo "$OUTPUT" | grep -c "already up to date" 2>/dev/null || true)
ERRORS=$(echo "$OUTPUT" | grep -c "✗ Error" 2>/dev/null || true)
# Default to 0 if empty
CONVERTED=${CONVERTED:-0}
UPDATED=${UPDATED:-0}
SKIPPED=${SKIPPED:-0}
ERRORS=${ERRORS:-0}

log "Summary: Converted=$CONVERTED, Updated=$UPDATED, Skipped=$SKIPPED, Errors=$ERRORS"

# Write heartbeat file (proves this task ran today)
echo "$(date '+%Y-%m-%d %H:%M:%S')" > "$HEARTBEAT_FILE"
log "Heartbeat written to $HEARTBEAT_FILE"

# Send success notification
if [ "$ERRORS" -gt 0 ]; then
    notify "TranscriptSync" "Completed with $ERRORS errors. Converted: $CONVERTED, Updated: $UPDATED"
elif [ "$CONVERTED" -gt 0 ] || [ "$UPDATED" -gt 0 ]; then
    notify "TranscriptSync" "Success! Converted: $CONVERTED, Updated: $UPDATED"
else
    log "No new files to sync"
fi

log "TranscriptSync scheduled run complete"
log "=========================================="

# Deactivate venv if we activated it
if [ -d "$SCRIPT_DIR/venv" ]; then
    deactivate 2>/dev/null || true
fi

exit 0
