#!/usr/bin/env python3
"""
Remove duplicate Google Docs files (those with (1), (2), etc. suffixes)
from a Google Drive folder.
"""

import os
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def setup_gdrive_service():
    """Set up and return Google Drive service"""
    # Note: Full drive scope required because duplicates like "file (1)" are created
    # by Google Drive itself, not by our app, so drive.file scope won't work
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = None

    token_file = 'gdrive_token_cleanup.json'
    credentials_file = 'gdrive_credentials.json'

    # Load existing token from JSON
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except (ValueError, KeyError) as e:
            print(f"⚠ Could not load token: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials in JSON format
        with open(token_file, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def find_folder_by_name(service, folder_name, parent_id=None):
    """Find a folder by name, optionally within a parent folder"""
    # Escape single quotes for the API query
    escaped_name = folder_name.replace("'", "\\'")
    query = f"name='{escaped_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    return files[0] if files else None


def get_all_files_in_folder(service, folder_id):
    """Get all files in a folder (handles pagination)"""
    all_files = []
    page_token = None

    while True:
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, mimeType)",
            pageSize=1000,
            pageToken=page_token
        ).execute()

        all_files.extend(results.get('files', []))
        page_token = results.get('nextPageToken')

        if not page_token:
            break

    return all_files


def cleanup_duplicates(service, folder_id, dry_run=True, debug=False):
    """Find and delete duplicate files with (1), (2), etc. suffixes"""

    # Pattern to match files with (1), (2), etc. at the end (Google Docs don't have extensions in API)
    duplicate_pattern = re.compile(r'^(.+) \((\d+)\)$')

    print(f"Scanning folder for duplicates...")
    files = get_all_files_in_folder(service, folder_id)
    print(f"Found {len(files)} total files")

    if debug:
        print("\nSample file names from API:")
        for f in files[:15]:
            print(f"  '{f['name']}'")
        print()

    # Separate originals and duplicates
    originals = {}
    duplicates = []

    for f in files:
        name = f['name']
        match = duplicate_pattern.match(name)

        if match:
            duplicates.append(f)
        else:
            # Store original by base name (without extension)
            base_name = name.replace('.gdoc', '')
            originals[base_name] = f

    print(f"Found {len(originals)} original files")
    print(f"Found {len(duplicates)} duplicate files to remove")

    if not duplicates:
        print("No duplicates found!")
        return

    # Show sample of duplicates
    print("\nSample duplicates to delete:")
    for f in duplicates[:10]:
        print(f"  - {f['name']}")
    if len(duplicates) > 10:
        print(f"  ... and {len(duplicates) - 10} more")

    if dry_run:
        print("\n[DRY RUN] Would delete the above files. Run with --delete to actually remove them.")
        return duplicates

    # Actually delete
    print(f"\nDeleting {len(duplicates)} duplicate files...")
    deleted = 0
    errors = 0

    for f in duplicates:
        try:
            service.files().delete(fileId=f['id']).execute()
            deleted += 1
            if deleted % 50 == 0:
                print(f"  Deleted {deleted}/{len(duplicates)}...")
        except Exception as e:
            print(f"  Error deleting {f['name']}: {e}")
            errors += 1

    print(f"\nDone! Deleted {deleted} files, {errors} errors")
    return duplicates


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Remove duplicate Google Docs files')
    parser.add_argument('--folder-id', help='Google Drive folder ID to clean up')
    parser.add_argument('--folder-name', help='Folder name to search for (required if --folder-id not provided)')
    parser.add_argument('--delete', action='store_true',
                        help='Actually delete files (default is dry run)')
    parser.add_argument('--debug', action='store_true',
                        help='Show debug info about file names')

    args = parser.parse_args()

    if not args.folder_id and not args.folder_name:
        parser.error("Either --folder-id or --folder-name is required")

    print("Connecting to Google Drive...")
    service = setup_gdrive_service()
    print("Connected!")

    # Find the folder
    if args.folder_id:
        folder_id = args.folder_id
    else:
        # Search for the folder by name
        print(f"Searching for folder: {args.folder_name}")
        folder = find_folder_by_name(service, args.folder_name)
        if not folder:
            print(f"Folder not found: {args.folder_name}")
            return
        folder_id = folder['id']
        print(f"Found folder: {folder['name']} (ID: {folder_id})")

    # Clean up duplicates
    cleanup_duplicates(service, folder_id, dry_run=not args.delete, debug=args.debug)


if __name__ == '__main__':
    main()
