#!/bin/bash
# Wrapper script that runs the context updater and schedules the next wake time
# Run times: 8 AM and 5 PM PT

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/claude-context-updater.log"

echo "========================================" >> "$LOG_FILE"
echo "$(date): Starting scheduled run" >> "$LOG_FILE"

# Run the actual conversion script and capture output
cd "$SCRIPT_DIR"
OUTPUT=$(/usr/bin/python3 "$SCRIPT_DIR/update_claude_context.py" \
    --to-gdocs 12OpOoXU5px1kNRNjxfgDZbKNGgn9U_Ut \
    --dirs /Users/codyaustin/Documents/Katib/Transcripts 2>&1)

# Log the output (contains file names)
echo "$OUTPUT" >> "$LOG_FILE"

# Extract and log summary
CONVERTED=$(echo "$OUTPUT" | grep -c "✓ Converted:")
UPDATED=$(echo "$OUTPUT" | grep -c "✓ Updated:")
SKIPPED=$(echo "$OUTPUT" | grep -c "Skipped")

echo "$(date): Conversion complete - Converted: $CONVERTED, Updated: $UPDATED, Skipped: $SKIPPED" >> "$LOG_FILE"

# Calculate next wake time (8 AM or 5 PM)
CURRENT_HOUR=$(date +%H)
CURRENT_DATE=$(date +%m/%d/%y)
TOMORROW_DATE=$(date -v+1d +%m/%d/%y)

if [ "$CURRENT_HOUR" -lt 8 ]; then
    # Before 8 AM - next run is today at 8 AM
    NEXT_WAKE_TIME="08:00:00"
    NEXT_WAKE_DATE="$CURRENT_DATE"
elif [ "$CURRENT_HOUR" -lt 17 ]; then
    # Between 8 AM and 5 PM - next run is today at 5 PM
    NEXT_WAKE_TIME="17:00:00"
    NEXT_WAKE_DATE="$CURRENT_DATE"
else
    # After 5 PM - next run is tomorrow at 8 AM
    NEXT_WAKE_TIME="08:00:00"
    NEXT_WAKE_DATE="$TOMORROW_DATE"
fi

echo "$(date): Scheduling next wake for $NEXT_WAKE_DATE $NEXT_WAKE_TIME" >> "$LOG_FILE"

# Schedule the next wake (requires sudo - will use osascript for GUI prompt if needed)
# First, try without sudo (in case it's already configured)
# Using pmset schedule wake
sudo pmset schedule wakeorpoweron "$NEXT_WAKE_DATE $NEXT_WAKE_TIME" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    echo "$(date): Note - pmset schedule requires sudo. Run manually or configure sudoers." >> "$LOG_FILE"
fi

echo "$(date): Done" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
