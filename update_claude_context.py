#!/usr/bin/env python3
"""
Automatically updates Claude project context by monitoring .txt files.
Supports local directories and optional Google Drive folder monitoring.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Set

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
except ImportError:
    print("watchdog not installed. Install with: pip install watchdog")
    sys.exit(1)

# Optional Google Drive support
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import pickle
    import io
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False


class TextFileHandler(FileSystemEventHandler):
    """Handles file system events for .txt files"""
    
    def __init__(self, context_file: str, monitored_dirs: List[str], gdrive_service=None, gdrive_folder_id=None):
        self.context_file = context_file
        self.monitored_dirs = [Path(d) for d in monitored_dirs]
        self.gdrive_service = gdrive_service
        self.gdrive_folder_id = gdrive_folder_id
        self.debounce_seconds = 2
        self.pending_files: Set[str] = set()
        self.last_update = 0
        
    def should_process(self, path: Path) -> bool:
        """Check if file should be processed"""
        if not path.suffix.lower() == '.txt':
            return False
        # Check if file is in monitored directories
        for monitored_dir in self.monitored_dirs:
            try:
                path.resolve().relative_to(monitored_dir.resolve())
                return True
            except ValueError:
                continue
        return False
    
    def on_modified(self, event):
        """Handle file modification"""
        if not event.is_directory:
            path = Path(event.src_path)
            if self.should_process(path):
                self.schedule_update(path)
    
    def on_created(self, event):
        """Handle file creation"""
        if not event.is_directory:
            path = Path(event.src_path)
            if self.should_process(path):
                self.schedule_update(path)
    
    def schedule_update(self, path: Path):
        """Schedule an update after debounce period"""
        self.pending_files.add(str(path))
        current_time = time.time()
        if current_time - self.last_update > self.debounce_seconds:
            self.update_context()
    
    def update_context(self):
        """Update the CLAUDE.md context file"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Detected changes, updating context...")
        
        all_txt_files = self.find_all_txt_files()
        
        # Generate CLAUDE.md content
        content = self.generate_claude_md(all_txt_files)
        
        # Write to CLAUDE.md
        with open(self.context_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ Updated {self.context_file} with {len(all_txt_files)} .txt files")
        self.pending_files.clear()
        self.last_update = time.time()
    
    def find_all_txt_files(self) -> List[Path]:
        """Find all .txt files in monitored directories"""
        txt_files = []
        
        # Find local .txt files
        for monitored_dir in self.monitored_dirs:
            if monitored_dir.exists():
                txt_files.extend(monitored_dir.rglob('*.txt'))
                txt_files.extend(monitored_dir.rglob('*.TXT'))
        
        # Find Google Drive .txt files if configured
        if self.gdrive_service and self.gdrive_folder_id:
            gdrive_files = self.get_gdrive_txt_files()
            txt_files.extend(gdrive_files)
        
        # Remove duplicates and sort
        txt_files = sorted(set(txt_files), key=lambda p: str(p))
        return txt_files
    
    def get_gdrive_txt_files(self) -> List[Path]:
        """Fetch .txt files from Google Drive folder"""
        if not self.gdrive_service or not self.gdrive_folder_id:
            return []
        
        txt_files = []
        try:
            # List files in the folder
            query = f"'{self.gdrive_folder_id}' in parents and mimeType='text/plain' and trashed=false"
            results = self.gdrive_service.files().list(
                q=query,
                fields="files(id, name, modifiedTime)"
            ).execute()
            
            items = results.get('files', [])
            for item in items:
                # Download to temp location and reference it
                local_cache_dir = Path('.gdrive_cache')
                local_cache_dir.mkdir(exist_ok=True)
                cache_file = local_cache_dir / item['name']
                
                # Download if not cached or if remote is newer
                if not cache_file.exists() or self.is_gdrive_newer(item, cache_file):
                    self.download_gdrive_file(item['id'], cache_file)
                
                txt_files.append(cache_file)
                
        except Exception as e:
            print(f"⚠ Error fetching Google Drive files: {e}")
        
        return txt_files
    
    def is_gdrive_newer(self, gdrive_item: dict, local_file: Path) -> bool:
        """Check if Google Drive file is newer than local cache"""
        if not local_file.exists():
            return True
        
        try:
            gdrive_time = datetime.fromisoformat(gdrive_item['modifiedTime'].replace('Z', '+00:00'))
            local_time = datetime.fromtimestamp(local_file.stat().st_mtime)
            return gdrive_time > local_time
        except:
            return True
    
    def download_gdrive_file(self, file_id: str, dest_path: Path):
        """Download a file from Google Drive"""
        try:
            request = self.gdrive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Write to file
            with open(dest_path, 'wb') as f:
                f.write(fh.getvalue())
        except Exception as e:
            print(f"⚠ Error downloading {file_id}: {e}")
    
    def generate_claude_md(self, txt_files: List[Path]) -> str:
        """Generate CLAUDE.md content with references to all .txt files"""
        lines = [
            "# Claude Project Context",
            "",
            f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "## Context Files",
            "",
            "The following .txt files are automatically included in the project context:",
            ""
        ]
        
        # Group files by directory
        by_dir = {}
        for txt_file in txt_files:
            parent = txt_file.parent
            if parent not in by_dir:
                by_dir[parent] = []
            by_dir[parent].append(txt_file)
        
        # Add file references using @ syntax for Claude
        for parent_dir in sorted(by_dir.keys(), key=lambda p: str(p)):
            rel_dir = parent_dir.relative_to(Path.cwd()) if parent_dir.is_relative_to(Path.cwd()) else parent_dir
            lines.append(f"### {rel_dir}")
            for txt_file in sorted(by_dir[parent_dir], key=lambda p: p.name):
                rel_path = txt_file.relative_to(Path.cwd()) if txt_file.is_relative_to(Path.cwd()) else txt_file
                lines.append(f"@{rel_path}")
                lines.append("")
        
        # Add actual content sections
        lines.extend([
            "",
            "---",
            "",
            "## File Contents",
            "",
            "The following sections contain the actual content of the context files:",
            ""
        ])
        
        for txt_file in txt_files:
            rel_path = txt_file.relative_to(Path.cwd()) if txt_file.is_relative_to(Path.cwd()) else txt_file
            lines.extend([
                f"### {txt_file.name}",
                f"*Source: {rel_path}*",
                "",
                "```",
            ])
            
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines.append(content)
            except Exception as e:
                lines.append(f"[Error reading file: {e}]")
            
            lines.extend([
                "```",
                "",
                "---",
                ""
            ])
        
        return "\n".join(lines)


def setup_gdrive_service(credentials_file: str = 'gdrive_credentials.json', token_file: str = 'gdrive_token.pickle') -> Optional[object]:
    """Set up and return Google Drive service"""
    if not GDRIVE_AVAILABLE:
        print("⚠ Google Drive libraries not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return None
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = None
    
    # Load existing token
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)
    
    # If no valid credentials, get user to authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                print(f"⚠ Google Drive credentials file '{credentials_file}' not found.")
                print("  To enable Google Drive monitoring:")
                print("  1. Go to https://console.cloud.google.com/")
                print("  2. Create a project and enable Google Drive API")
                print("  3. Create OAuth 2.0 credentials")
                print("  4. Download credentials as 'gdrive_credentials.json'")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials
        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('drive', 'v3', credentials=creds)


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Automatically update Claude project context from .txt files'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Watch for file changes and auto-update (default: one-time update)'
    )
    parser.add_argument(
        '--dirs',
        nargs='+',
        default=['.'],
        help='Directories to monitor for .txt files (default: current directory)'
    )
    parser.add_argument(
        '--output',
        default='CLAUDE.md',
        help='Output context file (default: CLAUDE.md)'
    )
    parser.add_argument(
        '--gdrive-folder-id',
        help='Google Drive folder ID to monitor (requires gdrive_credentials.json)'
    )
    parser.add_argument(
        '--config',
        help='JSON configuration file path'
    )
    
    args = parser.parse_args()
    
    # Load config if provided
    config = {}
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Use config values if not provided via CLI
    monitored_dirs = args.dirs if args.dirs != ['.'] else config.get('monitored_dirs', ['.'])
    output_file = args.output if args.output != 'CLAUDE.md' else config.get('output_file', 'CLAUDE.md')
    gdrive_folder_id = args.gdrive_folder_id or config.get('gdrive_folder_id')
    
    # Set up Google Drive if requested
    gdrive_service = None
    if gdrive_folder_id:
        print("🔗 Setting up Google Drive connection...")
        gdrive_service = setup_gdrive_service(
            config.get('gdrive_credentials_file', 'gdrive_credentials.json'),
            config.get('gdrive_token_file', 'gdrive_token.pickle')
        )
        if gdrive_service:
            print("✓ Google Drive connected")
    
    # Create handler
    handler = TextFileHandler(output_file, monitored_dirs, gdrive_service, gdrive_folder_id)
    
    # Initial update
    print("🔍 Scanning for .txt files...")
    handler.update_context()
    
    if args.watch:
        print(f"\n👀 Watching directories: {', '.join(monitored_dirs)}")
        if gdrive_folder_id:
            print(f"   Google Drive folder: {gdrive_folder_id}")
        print("   Press Ctrl+C to stop\n")
        
        # Set up file watchers
        observer = Observer()
        for monitored_dir in monitored_dirs:
            dir_path = Path(monitored_dir)
            if dir_path.exists():
                observer.schedule(handler, str(dir_path), recursive=True)
                print(f"✓ Watching: {dir_path.resolve()}")
            else:
                print(f"⚠ Directory not found: {dir_path}")
        
        observer.start()
        
        # Set up periodic Google Drive check if enabled
        last_gdrive_check = 0
        gdrive_check_interval = config.get('gdrive_check_interval', 60)
        
        try:
            while True:
                time.sleep(1)
                # Periodic Google Drive check
                if gdrive_service and gdrive_folder_id:
                    current_time = time.time()
                    if current_time - last_gdrive_check >= gdrive_check_interval:
                        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking Google Drive for updates...")
                        handler.update_context()
                        last_gdrive_check = current_time
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping file watcher...")
            observer.stop()
        observer.join()
        print("✓ Stopped")
    else:
        print("\n✓ One-time update complete. Use --watch to monitor for changes continuously.")


if __name__ == '__main__':
    main()