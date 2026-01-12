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

# Paths
SCRIPT_DIR = Path(__file__).parent
LOG_FILE = Path("/tmp/claude-context-updater.log")
CONVERSION_SCRIPT = SCRIPT_DIR / "run_with_wake.sh"

# Google Drive folders to monitor
GDOCS_FOLDERS = {
    "Lenny's Podcast": "/Users/codyaustin/Documents/Katib/Transcripts/Lenny's Podcast Product  Career  Growth (2)",
    "10x Recruiting": "/Users/codyaustin/Documents/Katib/Transcripts/10x Recruiting (1)",
    "Offer Accepted": "/Users/codyaustin/Documents/Katib/Transcripts/Offer Accepted (1)",
    "Pragmatic Engineer": "/Users/codyaustin/Documents/Katib/Transcripts/The Pragmatic Engineer (1)",
}


class TranscriptSyncApp(rumps.App):
    def __init__(self):
        super(TranscriptSyncApp, self).__init__(
            "TranscriptSync",
            icon=None,  # Will use text instead
            title="📝",
            quit_button=None  # Custom quit button
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

    @rumps.clicked("View Recent Syncs")
    def show_log_window(self, _):
        """Show recent sync activity in a window"""
        recent = self.get_recent_syncs()
        if recent:
            message = "\n".join(recent[-15:])  # Last 15 entries
        else:
            message = "No sync activity found yet.\n\nSyncs run at 8 AM and 5 PM daily."

        rumps.alert(
            title="Recent Transcript Syncs",
            message=message,
            ok="Close"
        )

    @rumps.clicked("Sync Now")
    def run_sync_now(self, _):
        """Run conversion immediately"""
        self.title = "🔄"  # Show syncing indicator
        rumps.notification(
            title="TranscriptSync",
            subtitle="Starting sync...",
            message="Converting new transcripts to Google Docs"
        )

        try:
            # Run in background
            subprocess.Popen(
                ["bash", str(CONVERSION_SCRIPT)],
                cwd=str(SCRIPT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Reset icon after a delay (handled by timer)
            rumps.Timer(self.reset_icon, 5).start()

        except Exception as e:
            rumps.alert(f"Error running sync: {e}")
            self.title = "📝"

    def reset_icon(self, _):
        """Reset the menu bar icon"""
        self.title = "📝"
        rumps.notification(
            title="TranscriptSync",
            subtitle="Sync complete",
            message="Check 'View Recent Syncs' for details"
        )

    @rumps.clicked("Episode Counts")
    def show_counts(self, _):
        """Show episode counts per podcast"""
        counts = []
        total = 0

        for name, path in GDOCS_FOLDERS.items():
            try:
                if os.path.exists(path):
                    # Count .gdoc files (excluding duplicates)
                    files = [f for f in os.listdir(path)
                             if f.endswith('.gdoc') and not re.search(r' \(\d+\)\.gdoc$', f)]
                    count = len(files)
                    total += count
                    counts.append(f"  {name}: {count}")
                else:
                    counts.append(f"  {name}: (folder not synced)")
            except Exception as e:
                counts.append(f"  {name}: (error)")

        message = "Episodes converted to Google Docs:\n\n" + "\n".join(counts) + f"\n\nTotal: {total}"
        rumps.alert(title="Episode Counts", message=message, ok="Close")

    @rumps.clicked("Next Scheduled Run")
    def show_next_run(self, _):
        """Show next scheduled wake/run time"""
        try:
            result = subprocess.run(
                ["pmset", "-g", "sched"],
                capture_output=True,
                text=True
            )
            output = result.stdout

            # Parse the schedule
            lines = []
            if "wakepoweron" in output.lower() or "wakeorpoweron" in output.lower():
                for line in output.split('\n'):
                    if 'wake' in line.lower() or 'poweron' in line.lower():
                        lines.append(line.strip())

            if lines:
                message = "Scheduled wake times:\n\n" + "\n".join(lines)
            else:
                message = "No wake schedule found.\n\nRun setup commands to enable auto-wake."

            rumps.alert(title="Schedule", message=message, ok="Close")

        except Exception as e:
            rumps.alert(f"Error checking schedule: {e}")

    @rumps.clicked("Open Log File")
    def open_log_file(self, _):
        """Open log file in Console"""
        if LOG_FILE.exists():
            subprocess.run(["open", "-a", "Console", str(LOG_FILE)])
        else:
            rumps.alert("Log file not found", "No sync has run yet.")

    @rumps.clicked("Open Transcripts Folder")
    def open_transcripts(self, _):
        """Open transcripts folder in Finder"""
        subprocess.run(["open", "/Users/codyaustin/Documents/Katib/Transcripts"])

    @rumps.clicked("Quit")
    def quit_app(self, _):
        """Quit the app"""
        rumps.quit_application()

    def get_recent_syncs(self):
        """Parse log file for recent sync activity"""
        if not LOG_FILE.exists():
            return []

        entries = []
        try:
            with open(LOG_FILE, 'r') as f:
                content = f.read()

            # Find conversion entries
            for match in re.finditer(
                r'(\w+ \w+ \d+ [\d:]+)[^\n]*Starting scheduled run.*?'
                r'(?:Converted: (\d+)|Updated: (\d+)|Skipped.*?: (\d+))?.*?'
                r'Conversion complete',
                content, re.DOTALL
            ):
                timestamp = match.group(1)
                converted = match.group(2) or "0"
                updated = match.group(3) or "0"
                skipped = match.group(4) or "0"

                # Format nicely
                try:
                    dt = datetime.strptime(timestamp, "%a %b %d %H:%M:%S")
                    dt = dt.replace(year=datetime.now().year)
                    formatted = dt.strftime("%b %d, %I:%M %p")
                except:
                    formatted = timestamp

                entries.append(f"✓ {formatted}")

            # If no detailed entries, just show timestamps
            if not entries:
                for match in re.finditer(r'(\w+ \w+ \d+ [\d:]+)[^\n]*Starting scheduled run', content):
                    timestamp = match.group(1)
                    try:
                        dt = datetime.strptime(timestamp, "%a %b %d %H:%M:%S")
                        dt = dt.replace(year=datetime.now().year)
                        formatted = dt.strftime("%b %d, %I:%M %p")
                    except:
                        formatted = timestamp
                    entries.append(f"✓ {formatted}")

        except Exception as e:
            entries.append(f"Error reading log: {e}")

        return entries


if __name__ == "__main__":
    TranscriptSyncApp().run()
