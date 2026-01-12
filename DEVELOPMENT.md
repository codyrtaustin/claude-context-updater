# Development Guide

## Project Overview

**Claude Context Updater** automatically converts podcast transcript `.txt` files to Google Docs, with a native macOS menu bar app to monitor sync status.

**Sister project:** [Katib](https://github.com/codyrtaustin/Katib) - adds podcasts and generates transcripts

## Components

| File | Purpose |
|------|---------|
| `update_claude_context.py` | Main conversion script - .txt → Google Docs |
| `run_with_wake.sh` | Wrapper that runs conversion + schedules next Mac wake |
| `TranscriptSync.py` | Menu bar GUI app (📝 icon) |
| `setup_app.py` | py2app config to build .app bundle |
| `cleanup_duplicates.py` | Utility to remove duplicate Google Docs |

## How It Works

- **Scheduled runs:** 8 AM & 5 PM PT daily
- **Mac wakes from sleep** automatically via `pmset`
- **Source:** `/Users/codyaustin/Documents/Katib/Transcripts/` (all subfolders)
- **Destination:** Google Drive folder ID `12OpOoXU5px1kNRNjxfgDZbKNGgn9U_Ut`
- **New podcasts:** Auto-detected when added via Katib (recursive scan)

## Development Commands

### Navigate to Project
```bash
cd "/Users/codyaustin/Library/CloudStorage/GoogleDrive-codyrtaustin@gmail.com/My Drive/Claude Code/claude-context-updater"
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

### Run Manual Sync
```bash
bash run_with_wake.sh
```

### Check Logs
```bash
cat /tmp/claude-context-updater.log
```

### Check Wake Schedule
```bash
pmset -g sched
```

### Check Launch Agent Status
```bash
launchctl list | grep claude
```

## Key Paths

| What | Path |
|------|------|
| Transcripts source | `/Users/codyaustin/Documents/Katib/Transcripts/` |
| Log file | `/tmp/claude-context-updater.log` |
| Launch agent | `~/Library/LaunchAgents/com.claude.context-updater.plist` |
| Installed app | `/Applications/TranscriptSync.app` |
| Google credentials | `./gdrive_credentials.json` |
| Google token | `./gdrive_token.pickle` (auto-generated on first auth) |

## Dependencies

```bash
pip3 install watchdog google-api-python-client google-auth-httplib2 google-auth-oauthlib rumps py2app
```

## Troubleshooting

**App not syncing?**
- Check `pmset -g sched` for wake schedule
- Check `launchctl list | grep claude` for launch agent
- Check `/tmp/claude-context-updater.log` for errors

**Need to re-authenticate Google?**
- Delete the token file and run script again

**Menu bar app not showing?**
- Run `open /Applications/TranscriptSync.app`
