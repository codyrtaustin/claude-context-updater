# Claude Context Auto-Updater

Automatically updates your Claude project context by monitoring `.txt` files locally and optionally from Google Drive. The script watches for new or changed `.txt` files and regenerates a `CLAUDE.md` file that Claude can use as context.

## Features

- ✅ **Automatic file monitoring** - Watches directories for `.txt` file changes in real-time
- ✅ **Local directory scanning** - Monitors multiple directories recursively
- ✅ **Google Drive integration** - Optional support for monitoring a Google Drive folder
- ✅ **Auto-updates** - Automatically regenerates `CLAUDE.md` when files change
- ✅ **Debounced updates** - Prevents excessive updates when multiple files change

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) For Google Drive support, also install:
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

3. Make the script executable:
```bash
chmod +x update_claude_context.py
```

## Usage

### Basic Usage (One-time update)

Generate `CLAUDE.md` once from all `.txt` files in the current directory:

```bash
python update_claude_context.py
```

### Watch Mode (Auto-update)

Monitor directories continuously and auto-update when `.txt` files change:

```bash
python update_claude_context.py --watch
```

### Custom Directories

Monitor specific directories:

```bash
python update_claude_context.py --watch --dirs ./docs ./notes ./context
```

### Using Configuration File

1. Copy the example config:
```bash
cp config.example.json config.json
```

2. Edit `config.json` with your settings:
```json
{
  "monitored_dirs": [".", "./docs", "./notes"],
  "output_file": "CLAUDE.md",
  "gdrive_folder_id": "your-folder-id-here"
}
```

3. Run with config:
```bash
python update_claude_context.py --watch --config config.json
```

## Google Drive Setup

To monitor a Google Drive folder:

1. **Create Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"

3. **Create OAuth 2.0 Credentials**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as the application type
   - Download the credentials JSON file

4. **Save Credentials**:
   - Save the downloaded file as `gdrive_credentials.json` in your project directory

5. **Get Folder ID**:
   - Open the Google Drive folder you want to monitor
   - The folder ID is in the URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`
   - Copy the `FOLDER_ID_HERE` part

6. **Run with Google Drive**:
   ```bash
   python update_claude_context.py --watch --gdrive-folder-id FOLDER_ID_HERE
   ```

On first run, you'll be prompted to authenticate via your browser. The authentication token will be saved for future use.

## How It Works

1. **File Detection**: The script scans specified directories for `.txt` files (both `.txt` and `.TXT` extensions)

2. **Context Generation**: Creates a `CLAUDE.md` file with:
   - File references using `@filename.txt` syntax (for Claude's file reference feature)
   - Actual file contents embedded in the document

3. **Watch Mode**: When `--watch` is enabled:
   - Monitors file system events for new/modified `.txt` files
   - Automatically triggers context regeneration on changes
   - Checks Google Drive folder periodically (every 60 seconds) if configured

4. **Google Drive Integration**:
   - Downloads `.txt` files from the specified Google Drive folder
   - Caches files locally in `.gdrive_cache/` directory
   - Only downloads when files are new or modified on Drive
   - Includes downloaded files in the generated context

## Example Output

The generated `CLAUDE.md` will look like:

```markdown
# Claude Project Context

*Auto-generated on 2025-01-09 17:45:00*

## Context Files

The following .txt files are automatically included in the project context:

### ./docs
@./docs/project-overview.txt
@./docs/api-spec.txt

### ./notes
@./notes/meeting-notes.txt

---

## File Contents

The following sections contain the actual content of the context files:

### project-overview.txt
*Source: ./docs/project-overview.txt*

```
[File contents here...]
```
```

## Command Line Options

- `--watch` - Enable watch mode for continuous monitoring
- `--dirs DIR1 DIR2 ...` - Directories to monitor (default: current directory)
- `--output FILE` - Output file name (default: `CLAUDE.md`)
- `--gdrive-folder-id ID` - Google Drive folder ID to monitor
- `--config FILE` - JSON configuration file path

## Tips

- Run in **watch mode** during active development to keep context up-to-date
- Use a **configuration file** for consistent settings across team members
- **Organize `.txt` files** in subdirectories for better structure
- **Google Drive sync** is useful for shared context files across team members
- The script uses **debouncing** (2 seconds) to avoid excessive updates when multiple files change quickly

## Troubleshooting

**Issue**: `watchdog not installed`
- Solution: `pip install watchdog`

**Issue**: Google Drive authentication fails
- Solution: Make sure `gdrive_credentials.json` is in the current directory and is valid

**Issue**: Permission denied errors
- Solution: Check that you have read permissions for monitored directories and write permissions for the output file

**Issue**: Google Drive files not updating
- Solution: Check folder ID is correct and you have access to the folder. The script checks Drive every 60 seconds.

## License

MIT License - Feel free to use and modify as needed.