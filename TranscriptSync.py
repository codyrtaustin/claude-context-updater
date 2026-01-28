#!/usr/bin/env python3
"""
TranscriptSync - Menu bar app for monitoring podcast transcript conversions
Lightweight, fast, native macOS app using rumps
"""

import rumps
import subprocess
import os
import re
from datetime import datetime
from pathlib import Path
import webbrowser

# Paths - use environment variables with fallbacks for portability
# Set TRANSCRIPTSYNC_PROJECT_DIR and TRANSCRIPTSYNC_PODCASTS_DIR to override defaults
PROJECT_DIR = Path(os.environ.get("TRANSCRIPTSYNC_PROJECT_DIR", "/Users/codyaustin/claude-context-updater"))
LOG_DIR = PROJECT_DIR / "logs"
CONVERSION_SCRIPT = PROJECT_DIR / "transcriptsync_scheduled.sh"

# Base podcasts folder - transcripts live alongside MP3s
PODCASTS_BASE = os.environ.get("TRANSCRIPTSYNC_PODCASTS_DIR", "/Users/codyaustin/Documents/Katib/podcasts")


class TranscriptSyncApp(rumps.App):
    def __init__(self):
        super(TranscriptSyncApp, self).__init__(
            "TranscriptSync",
            icon=None,
            title="📝",
            quit_button=None
        )

        # Build menu
        self.menu = [
            rumps.MenuItem("View Recent Syncs", callback=self.show_log_window),
            rumps.MenuItem("Sync Now", callback=self.run_sync_now),
            None,  # Separator
            rumps.MenuItem("Episode Counts", callback=self.show_counts),
            rumps.MenuItem("Next Scheduled Run", callback=self.show_next_run),
            None,  # Separator
            rumps.MenuItem("Open Log File", callback=self.open_log_file),
            rumps.MenuItem("Open Transcripts Folder", callback=self.open_transcripts),
            None,  # Separator
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

    def show_log_window(self, _):
        """Show recent sync activity in a window"""
        recent = self.get_recent_syncs()

        if recent:
            count = len(recent)
            header = f"Last {count} sync{'s' if count > 1 else ''}:\n\n"
            message = header + "\n".join(recent)
        else:
            message = "No sync activity found yet.\n\nSyncs run automatically at 8 AM and 5 PM daily."

        # Use alert for read-only display (no text input)
        rumps.alert(
            title="Recent Transcript Syncs",
            message=message,
            ok="Close"
        )

    def run_sync_now(self, _):
        """Run conversion immediately"""
        self.title = "🔄"
        rumps.notification(
            title="TranscriptSync",
            subtitle="Starting sync...",
            message="Converting new transcripts to Google Docs"
        )

        try:
            subprocess.Popen(
                ["bash", str(CONVERSION_SCRIPT)],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            rumps.Timer(self.reset_icon, 5).start()

        except Exception as e:
            rumps.alert(title="Sync Error", message=f"Error running sync:\n\n{e}", ok="Close")
            self.title = "📝"

    def reset_icon(self, _):
        """Reset the menu bar icon"""
        self.title = "📝"
        rumps.notification(
            title="TranscriptSync",
            subtitle="Sync complete",
            message="Check 'View Recent Syncs' for details"
        )

    def show_counts(self, _):
        """Show episode counts per podcast - counts transcripts in podcast folders"""
        counts = []
        total_txt = 0
        total_mp3 = 0

        try:
            base = Path(PODCASTS_BASE)
            if not base.exists():
                rumps.alert(title="Episode Counts", message=f"Podcasts folder not found:\n{PODCASTS_BASE}", ok="Close")
                return

            # Find all podcast subfolders
            for folder in sorted(base.iterdir()):
                if not folder.is_dir() or folder.name.startswith('.'):
                    continue

                # Count .txt and .mp3 files in each podcast folder
                txt_count = len([f for f in folder.iterdir() if f.suffix.lower() == '.txt'])
                mp3_count = len([f for f in folder.iterdir() if f.suffix.lower() == '.mp3'])

                total_txt += txt_count
                total_mp3 += mp3_count

                # Shorten long names
                clean_name = folder.name
                if len(clean_name) > 30:
                    clean_name = clean_name[:27] + "..."

                counts.append(f"{clean_name}: {txt_count}/{mp3_count}")

            if counts:
                message = "Transcripts per podcast (transcribed/total):\n\n" + "\n".join(counts) + f"\n\n─────────────────\nTotal: {total_txt} transcripts / {total_mp3} episodes"
            else:
                message = "No podcasts found yet.\n\nAdd podcasts in Katib and download episodes."

        except Exception as e:
            message = f"Error reading folders: {e}"

        rumps.alert(title="Episode Counts", message=message, ok="Close")

    def show_next_run(self, _):
        """Show next scheduled wake/run time"""
        try:
            result = subprocess.run(
                ["pmset", "-g", "sched"],
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()

            if output:
                message = output
            else:
                message = "No wake schedule found.\n\nRun setup commands to enable auto-wake."

            rumps.alert(title="Wake Schedule", message=message, ok="Close")

        except Exception as e:
            rumps.alert(title="Schedule Error", message=f"Error checking schedule:\n\n{e}", ok="Close")

    def open_log_file(self, _):
        """Open log file in Console"""
        # Find most recent sync log
        if LOG_DIR.exists():
            log_files = sorted(LOG_DIR.glob("sync_*.log"), reverse=True)
            if log_files:
                subprocess.run(["open", "-a", "Console", str(log_files[0])])
                return
        rumps.notification(
            title="TranscriptSync",
            subtitle="Log not found",
            message="No sync has run yet."
        )

    def open_transcripts(self, _):
        """Open podcasts folder in Finder"""
        subprocess.run(["open", PODCASTS_BASE])

    def quit_app(self, _):
        """Quit the app"""
        rumps.quit_application()

    def get_recent_syncs(self):
        """Parse log files for recent sync activity with file names"""
        if not LOG_DIR.exists():
            return []

        entries = []  # List of (datetime, entry_string) tuples
        try:
            # Get recent log files (last 5 days)
            log_files = sorted(LOG_DIR.glob("sync_*.log"), reverse=True)[:5]

            for log_file in log_files:
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Split by run separators (42 equals signs)
                runs = content.split("=" * 42)

                for run in runs:
                    if not run.strip():
                        continue

                    lines = run.strip().split('\n')
                    dt = None
                    timestamp = None
                    files = []
                    converted = 0
                    updated = 0
                    skipped = 0

                    for line in lines:
                        line = line.strip()

                        # Get timestamp from "Starting TranscriptSync scheduled run"
                        if "Starting TranscriptSync" in line:
                            match = re.match(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]', line)
                            if match:
                                try:
                                    dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                                    timestamp = dt.strftime("%b %d, %I:%M %p")
                                except ValueError:
                                    timestamp = match.group(1)
                                    dt = datetime.min

                        # Get converted/updated files
                        elif "✓ Converted:" in line or "✓ Updated:" in line:
                            # Extract file name
                            match = re.search(r'✓ (?:Converted|Updated): (.+?)(?:\s+\(\d+/|$)', line)
                            if match:
                                files.append(match.group(1))

                        # Get summary from "Converted: X files" format
                        elif "Converted:" in line and "files" in line:
                            match = re.search(r'Converted: (\d+) files', line)
                            if match:
                                converted = int(match.group(1))
                        elif "Updated:" in line and "files" in line:
                            match = re.search(r'Updated: (\d+) files', line)
                            if match:
                                updated = int(match.group(1))
                        elif "Skipped" in line and "files" in line:
                            match = re.search(r'Skipped.*?: (\d+) files', line)
                            if match:
                                skipped = int(match.group(1))

                    if timestamp and dt:
                        summary = f"({converted} new, {updated} updated, {skipped} skipped)"
                        entry = f"\n📅 {timestamp} {summary}"
                        if files:
                            entry += "\n   " + "\n   ".join(files[:5])
                            if len(files) > 5:
                                entry += f"\n   ... and {len(files) - 5} more"
                        elif converted == 0 and updated == 0:
                            entry += "\n   (no new files)"
                        entries.append((dt, entry))

        except Exception as e:
            return [f"Error reading log: {e}"]

        # Sort by datetime descending (newest first), return just the entry strings
        entries.sort(key=lambda x: x[0], reverse=True)
        result = [entry for _, entry in entries[:10]]
        return result if result else ["No sync entries found in log."]


if __name__ == "__main__":
    TranscriptSyncApp().run()
