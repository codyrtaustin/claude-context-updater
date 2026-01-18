#!/bin/bash
# Installation script for TranscriptSync launchd agents
# Run this once to set up scheduled tasks

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$SCRIPT_DIR/logs"

echo "======================================"
echo "TranscriptSync LaunchAgent Installer"
echo "======================================"
echo ""

# Create logs directory
mkdir -p "$LOG_DIR"
echo "✓ Created logs directory: $LOG_DIR"

# Make scripts executable
chmod +x "$SCRIPT_DIR/transcriptsync_scheduled.sh"
echo "✓ Made transcriptsync_scheduled.sh executable"

if [ -f "$SCRIPT_DIR/transcriptsync_watchdog.sh" ]; then
    chmod +x "$SCRIPT_DIR/transcriptsync_watchdog.sh"
    echo "✓ Made transcriptsync_watchdog.sh executable"
fi

# Create venv if it doesn't exist
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m venv "$SCRIPT_DIR/venv"
    source "$SCRIPT_DIR/venv/bin/activate"
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
    deactivate
    echo "✓ Created and configured venv"
else
    echo "✓ Virtual environment already exists"
fi

# Ensure LaunchAgents directory exists
mkdir -p "$LAUNCH_AGENTS_DIR"

# Function to install a plist
install_plist() {
    local plist_name="$1"
    local source_file="$SCRIPT_DIR/$plist_name"
    local target_file="$LAUNCH_AGENTS_DIR/$plist_name"

    if [ ! -f "$source_file" ]; then
        echo "⚠ Plist not found: $source_file"
        return 1
    fi

    # Unload existing agent if loaded
    if launchctl list | grep -q "${plist_name%.plist}"; then
        echo "  Unloading existing agent..."
        launchctl unload "$target_file" 2>/dev/null || true
    fi

    # Copy plist with path substitution (in case home dir differs)
    sed "s|/Users/codyaustin|$HOME|g" "$source_file" > "$target_file"

    echo "✓ Installed $plist_name"
    return 0
}

echo ""
echo "Installing LaunchAgents..."

# Install main sync agent
install_plist "com.transcriptsync.plist"

# Install watchdog if it exists
if [ -f "$SCRIPT_DIR/com.transcriptsync.watchdog.plist" ]; then
    install_plist "com.transcriptsync.watchdog.plist"
fi

echo ""
echo "======================================"
echo "Installation Complete!"
echo "======================================"
echo ""
echo "To activate the scheduled tasks, run:"
echo ""
echo "  launchctl load ~/Library/LaunchAgents/com.transcriptsync.plist"
if [ -f "$SCRIPT_DIR/com.transcriptsync.watchdog.plist" ]; then
    echo "  launchctl load ~/Library/LaunchAgents/com.transcriptsync.watchdog.plist"
fi
echo ""
echo "To verify they're loaded:"
echo "  launchctl list | grep transcriptsync"
echo ""
echo "To test manually:"
echo "  bash $SCRIPT_DIR/transcriptsync_scheduled.sh"
echo ""
echo "Logs will be written to: $LOG_DIR"
echo ""
echo "Schedule:"
echo "  - 9:30 AM PT daily"
echo "  - 5:00 PM PT daily"
echo ""
