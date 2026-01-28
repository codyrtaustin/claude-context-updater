#!/bin/bash
# Rebuild and install TranscriptSync.app
# Run this after making changes to TranscriptSync.py

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔨 Rebuilding TranscriptSync.app..."

# Quit the running app
pkill -x TranscriptSync 2>/dev/null || true
sleep 1

# Clean and rebuild
rm -rf build dist
python3 setup_app.py py2app || { echo "❌ Build failed"; exit 1; }

# Verify build output exists
[ -d dist/TranscriptSync.app ] || { echo "❌ Build output not found"; exit 1; }

# Install to /Applications
rm -rf /Applications/TranscriptSync.app
cp -R dist/TranscriptSync.app /Applications/

echo "✓ App installed to /Applications"

# Launch the new app
open /Applications/TranscriptSync.app

echo "✓ TranscriptSync launched"
