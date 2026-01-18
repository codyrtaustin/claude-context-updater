# Development Guide

## Project Overview

**Claude Context Updater** automatically converts podcast transcript `.txt` files to Google Docs, with a native macOS menu bar app to monitor sync status.

**Sister project:** [Katib](https://github.com/codyrtaustin/Katib) - adds podcasts and generates transcripts

## Components

| File | Purpose |
|------|---------|
| `update_claude_context.py` | Main conversion script - .txt to Google Docs |
| `transcriptsync_scheduled.sh` | Bash wrapper with venv, logging, notifications |
| `transcriptsync_watchdog.sh` | Health monitor - auto-recovers missed runs |
| `com.transcriptsync.plist` | LaunchAgent config for 9:30 AM and 5 PM runs |
| `com.transcriptsync.watchdog.plist` | LaunchAgent for watchdog (every 30 min) |
| `install_launchd.sh` | One-time installer for launchd setup |
| `TranscriptSync.py` | Menu bar GUI app |
| `setup_app.py` | py2app config to build .app bundle |
| `cleanup_duplicates.py` | Utility to remove duplicate Google Docs |

## How It Works

- **Scheduled runs:** 9:30 AM and 5 PM PT daily via launchd
- **Watchdog:** Runs every 30 min, auto-recovers if scheduled run missed
- **Source:** `/Users/codyaustin/Documents/Katib/podcasts/` (all subfolders)
- **Destination:** Google Drive folder ID `1Xk8AqldChn0G2KBdRepzTb-1czbSGry4`
- **New podcasts:** Auto-detected when added via Katib (recursive scan)

## Setup

### Install LaunchAgents (one-time)
```bash
bash install_launchd.sh
launchctl load ~/Library/LaunchAgents/com.transcriptsync.plist
launchctl load ~/Library/LaunchAgents/com.transcriptsync.watchdog.plist
```

## Development Commands

### Run Manual Sync
```bash
bash transcriptsync_scheduled.sh
```

### Check Logs
```bash
# Today's sync log
cat logs/sync_$(date +%Y-%m-%d).log

# Watchdog log
cat logs/watchdog_$(date +%Y-%m-%d).log

# Heartbeat (proves last successful run)
cat logs/heartbeat_sync.txt
```

### Check LaunchAgent Status
```bash
launchctl list | grep transcriptsync
```

### Reload LaunchAgents (after plist changes)
```bash
launchctl unload ~/Library/LaunchAgents/com.transcriptsync.plist
launchctl unload ~/Library/LaunchAgents/com.transcriptsync.watchdog.plist
launchctl load ~/Library/LaunchAgents/com.transcriptsync.plist
launchctl load ~/Library/LaunchAgents/com.transcriptsync.watchdog.plist
```

### Rebuild GUI App (after code changes)
```bash
pkill -f TranscriptSync
rm -rf build dist
python3 setup_app.py py2app
rm -rf /Applications/TranscriptSync.app
cp -R dist/TranscriptSync.app /Applications/
open /Applications/TranscriptSync.app
```

## Key Paths

| What | Path |
|------|------|
| Transcripts source | `/Users/codyaustin/Documents/Katib/podcasts/` |
| Log directory | `./logs/` |
| LaunchAgents | `~/Library/LaunchAgents/com.transcriptsync*.plist` |
| Installed app | `/Applications/TranscriptSync.app` |
| Google credentials | `./gdrive_credentials.json` |
| Virtual environment | `./venv/` |

## Dependencies

```bash
pip3 install watchdog google-api-python-client google-auth-httplib2 google-auth-oauthlib rumps py2app
```

Or use the venv created by the installer:
```bash
source venv/bin/activate
```

## Troubleshooting

**App not syncing?**
- Check `launchctl list | grep transcriptsync` for agent status
- Check `logs/sync_$(date +%Y-%m-%d).log` for errors
- Check `logs/heartbeat_sync.txt` for last successful run

**Need to re-authenticate Google?**
- Delete the token file and run script again

**Menu bar app not showing?**
- Run `open /Applications/TranscriptSync.app`

**Watchdog not recovering?**
- Check `logs/watchdog_$(date +%Y-%m-%d).log`
- Verify agent loaded: `launchctl list | grep watchdog`
