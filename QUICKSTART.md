# Quick Start Guide

Get up and running in 5 minutes!

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Basic Usage (Local Files Only)

Monitor the current directory for `.txt` files:

```bash
python update_claude_context.py --watch
```

This will:
- Scan all `.txt` files in the current directory (recursively)
- Generate `CLAUDE.md` with references and contents
- Watch for new/modified `.txt` files and auto-update

## 3. Monitor Specific Directories

```bash
python update_claude_context.py --watch --dirs ./docs ./notes ./context
```

## 4. One-Time Update (No Watching)

Just generate the context file once:

```bash
python update_claude_context.py
```

## 5. Using Configuration File

1. Copy example config:
```bash
cp config.example.json config.json
```

2. Edit `config.json`:
```json
{
  "monitored_dirs": [".", "./docs"],
  "output_file": "CLAUDE.md"
}
```

3. Run:
```bash
python update_claude_context.py --watch --config config.json
```

## 6. Google Drive Setup (Optional)

To monitor a Google Drive folder:

1. **Get Google Drive credentials**:
   - Go to https://console.cloud.google.com/
   - Create a project → Enable Google Drive API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download as `gdrive_credentials.json`

2. **Get your folder ID**:
   - Open the Google Drive folder
   - Copy the ID from URL: `https://drive.google.com/drive/folders/YOUR_FOLDER_ID`

3. **Run with Google Drive**:
```bash
python update_claude_context.py --watch --gdrive-folder-id YOUR_FOLDER_ID
```

On first run, you'll authenticate in your browser. The token is saved for future use.

## Example Workflow

```bash
# Create some test files
mkdir -p docs notes
echo "Project notes" > notes/notes1.txt
echo "API docs" > docs/api.txt

# Start watching
python update_claude_context.py --watch --dirs ./docs ./notes

# In another terminal, edit a file
echo "Updated content" >> notes/notes1.txt

# Watch the script auto-update CLAUDE.md!
```

That's it! Your `CLAUDE.md` will be automatically updated whenever `.txt` files change.

## Tips

- Use `--watch` during active development
- Press `Ctrl+C` to stop watching
- Google Drive files are cached in `.gdrive_cache/` and checked every 60 seconds
- The script debounces updates (2 seconds) to avoid excessive regenerations