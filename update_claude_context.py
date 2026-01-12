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
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
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


def setup_gdrive_service(credentials_file: str = 'gdrive_credentials.json', token_file: str = 'gdrive_token.pickle', write_access: bool = False) -> Optional[object]:
    """Set up and return Google Drive service"""
    if not GDRIVE_AVAILABLE:
        print("⚠ Google Drive libraries not installed. Install with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        return None

    # Use file scope for write access (allows creating/updating files)
    if write_access:
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
    else:
        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

    creds = None

    # Load existing token
    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

        # Check if we need different scopes than what's stored
        if write_access and creds and hasattr(creds, 'scopes'):
            if 'https://www.googleapis.com/auth/drive.file' not in (creds.scopes or []):
                print("⚠ Existing token doesn't have write access. Re-authenticating...")
                creds = None

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


def convert_txt_to_gdocs(gdrive_service, source_dirs: List[str], target_folder_id: str, preserve_structure: bool = True, limit: int = 0) -> dict:
    """
    Convert .txt files to Google Docs in the specified Google Drive folder.
    If preserve_structure=True, recreates the subfolder structure in Google Drive.
    If limit > 0, only convert that many files (useful for batch processing).
    Returns a dict with conversion results.
    """
    import tempfile

    if not gdrive_service:
        return {"error": "Google Drive service not available"}

    results = {"converted": [], "updated": [], "skipped": [], "errors": [], "limit_reached": False}
    converted_count = 0  # Track how many files we've actually converted/updated

    # Cache for folder IDs (folder_path -> gdrive_folder_id)
    folder_cache = {"": target_folder_id}

    def get_or_create_folder(folder_name: str, parent_id: str) -> str:
        """Get existing folder or create new one in Google Drive"""
        cache_key = f"{parent_id}/{folder_name}"
        if cache_key in folder_cache:
            return folder_cache[cache_key]

        # Search for existing folder
        try:
            query = f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            response = gdrive_service.files().list(q=query, fields="files(id, name)").execute()
            files = response.get('files', [])
            if files:
                folder_id = files[0]['id']
                folder_cache[cache_key] = folder_id
                return folder_id
        except Exception as e:
            print(f"⚠ Error searching for folder {folder_name}: {e}")

        # Create new folder
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = gdrive_service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder['id']
            folder_cache[cache_key] = folder_id
            print(f"📁 Created folder: {folder_name}")
            return folder_id
        except Exception as e:
            print(f"✗ Error creating folder {folder_name}: {e}")
            return parent_id

    def clean_folder_name(name: str) -> str:
        """Clean up folder names by removing TXT suffix and (1) etc."""
        import re
        # Remove " TXT" suffix
        name = re.sub(r'\s+TXT$', '', name)
        # Remove " (1)" or similar numbered suffixes
        name = re.sub(r'\s+\(\d+\)$', '', name)
        return name.strip()

    def get_target_folder_id(txt_file: Path, source_root: Path) -> str:
        """Determine the target folder ID based on file's relative path"""
        if not preserve_structure:
            return target_folder_id

        try:
            rel_path = txt_file.parent.relative_to(source_root)

            # If file is directly in source_root, use source_root's name as target folder
            if str(rel_path) == '.':
                source_folder_name = clean_folder_name(source_root.name)
                # Only create subfolder if source folder has a meaningful name
                if source_folder_name and source_folder_name.lower() not in ['transcripts', '.']:
                    return get_or_create_folder(source_folder_name, target_folder_id)
                return target_folder_id

            # Navigate/create folder hierarchy
            current_folder_id = target_folder_id
            for part in rel_path.parts:
                clean_name = clean_folder_name(part)
                current_folder_id = get_or_create_folder(clean_name, current_folder_id)
            return current_folder_id
        except ValueError:
            return target_folder_id

    def get_existing_docs_in_folder(folder_id: str) -> dict:
        """Get existing Google Docs in a folder"""
        existing = {}
        try:
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            response = gdrive_service.files().list(
                q=query,
                fields="files(id, name, modifiedTime)"
            ).execute()
            for doc in response.get('files', []):
                existing[doc['name']] = doc
        except Exception as e:
            print(f"⚠ Error listing docs in folder: {e}")
        return existing

    # Process each source directory
    for dir_path in source_dirs:
        source_root = Path(dir_path)
        if not source_root.exists():
            print(f"⚠ Source directory not found: {dir_path}")
            continue

        # Find all .txt files
        txt_files = list(source_root.rglob('*.txt')) + list(source_root.rglob('*.TXT'))
        print(f"📂 Found {len(txt_files)} .txt files in {dir_path}")

        # Group files by target folder for efficient batch checking
        files_by_folder = {}
        for txt_file in txt_files:
            target_id = get_target_folder_id(txt_file, source_root)
            if target_id not in files_by_folder:
                files_by_folder[target_id] = []
            files_by_folder[target_id].append(txt_file)

        # Process each folder group
        for folder_id, files in files_by_folder.items():
            if limit > 0 and converted_count >= limit:
                results["limit_reached"] = True
                break

            existing_docs = get_existing_docs_in_folder(folder_id)

            for txt_file in files:
                # Check limit before processing each file
                if limit > 0 and converted_count >= limit:
                    results["limit_reached"] = True
                    break
                try:
                    doc_name = txt_file.stem

                    # Check if doc already exists and skip if so (no update needed)
                    if doc_name in existing_docs:
                        # Check if local file is newer than Google Doc
                        existing_doc = existing_docs[doc_name]
                        try:
                            gdrive_time = datetime.fromisoformat(existing_doc['modifiedTime'].replace('Z', '+00:00'))
                            local_time = datetime.fromtimestamp(txt_file.stat().st_mtime)
                            # Make local_time timezone-aware for comparison
                            from datetime import timezone
                            local_time = local_time.replace(tzinfo=timezone.utc)
                            if local_time <= gdrive_time:
                                results["skipped"].append({"name": doc_name, "reason": "already up to date"})
                                continue
                        except Exception:
                            pass  # If we can't compare times, update anyway

                        # Delete old doc to replace with new content
                        try:
                            gdrive_service.files().delete(fileId=existing_doc['id']).execute()
                        except Exception as e:
                            print(f"⚠ Could not delete old doc {doc_name}: {e}")

                    # Read the .txt file content
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Create Google Doc with the content
                    file_metadata = {
                        'name': doc_name,
                        'mimeType': 'application/vnd.google-apps.document',
                        'parents': [folder_id]
                    }

                    # Write content to temp file for upload
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name

                    try:
                        media = MediaFileUpload(tmp_path, mimetype='text/plain', resumable=True)

                        # Retry logic for rate limiting
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                created_file = gdrive_service.files().create(
                                    body=file_metadata,
                                    media_body=media,
                                    fields='id, name, webViewLink'
                                ).execute()
                                break
                            except Exception as api_error:
                                if attempt < max_retries - 1 and ('500' in str(api_error) or '503' in str(api_error) or 'rate' in str(api_error).lower()):
                                    print(f"⏳ Rate limited, waiting 5 seconds...")
                                    time.sleep(5)
                                else:
                                    raise api_error

                        if doc_name in existing_docs:
                            results["updated"].append({
                                "name": doc_name,
                                "source": str(txt_file),
                                "link": created_file.get('webViewLink')
                            })
                            converted_count += 1
                            print(f"✓ Updated: {doc_name} ({converted_count}/{limit if limit > 0 else '∞'})")
                        else:
                            results["converted"].append({
                                "name": doc_name,
                                "source": str(txt_file),
                                "link": created_file.get('webViewLink')
                            })
                            converted_count += 1
                            print(f"✓ Converted: {doc_name} ({converted_count}/{limit if limit > 0 else '∞'})")

                        # Small delay to avoid rate limiting
                        time.sleep(0.5)
                    finally:
                        os.unlink(tmp_path)

                except Exception as e:
                    results["errors"].append({
                        "file": str(txt_file),
                        "error": str(e)
                    })
                    print(f"✗ Error converting {txt_file}: {e}")

    return results


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
        '--to-gdocs',
        metavar='FOLDER_ID',
        help='Convert .txt files to Google Docs in the specified Drive folder'
    )
    parser.add_argument(
        '--config',
        help='JSON configuration file path'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Limit number of files to convert (useful for batch processing, 0=unlimited)'
    )
    parser.add_argument(
        '--no-subfolders',
        action='store_true',
        help='Put all files directly in target folder without creating subfolders'
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
    to_gdocs_folder_id = args.to_gdocs or config.get('to_gdocs_folder_id')

    # Handle --to-gdocs mode (convert .txt files to Google Docs)
    if to_gdocs_folder_id:
        print("📝 Converting .txt files to Google Docs...")
        print(f"   Source directories: {', '.join(monitored_dirs)}")
        print(f"   Target folder ID: {to_gdocs_folder_id}")
        print("🔗 Setting up Google Drive connection (with write access)...")

        gdrive_service = setup_gdrive_service(
            config.get('gdrive_credentials_file', 'gdrive_credentials.json'),
            config.get('gdrive_token_file', 'gdrive_token.pickle'),
            write_access=True
        )

        if not gdrive_service:
            print("✗ Failed to connect to Google Drive")
            sys.exit(1)

        print("✓ Google Drive connected")
        if args.limit > 0:
            print(f"   Limit: {args.limit} files per batch")
        preserve_structure = not args.no_subfolders
        results = convert_txt_to_gdocs(gdrive_service, monitored_dirs, to_gdocs_folder_id, preserve_structure=preserve_structure, limit=args.limit)

        # Print summary
        print(f"\n📊 Conversion Summary:")
        print(f"   Converted: {len(results.get('converted', []))} files")
        print(f"   Updated: {len(results.get('updated', []))} files")
        print(f"   Skipped (already up to date): {len(results.get('skipped', []))} files")
        print(f"   Errors: {len(results.get('errors', []))} files")
        if results.get('limit_reached'):
            print(f"   ⚠️  Limit of {args.limit} reached - run again to continue")

        if results.get('converted') or results.get('updated'):
            print("\n🔗 Google Docs links:")
            for item in results.get('converted', []) + results.get('updated', []):
                print(f"   {item['name']}: {item.get('link', 'N/A')}")

        return

    # Set up Google Drive if requested (read-only mode for monitoring)
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