# Scripts

This directory contains utility scripts for Kokoro TTS.

## Available Scripts

### convert_epubs_to_audiobooks.sh

Batch convert multiple EPUB files to audiobooks.

**Usage:**
```bash
./scripts/convert_epubs_to_audiobooks.sh /path/to/epub/folder/
```

**Options:**
- `--voice <voice>` - Voice to use (default: af_sarah)
- `--format <format>` - Output format: wav, mp3, m4a (default: m4a)
- `--temp-dir <dir>` - Temporary directory for chapter files (default: ./audiobook)
- `--no-cleanup` - Keep temporary chapter files after conversion
- `--help` - Show help message

**Example:**
```bash
# Basic conversion with default settings
./scripts/convert_epubs_to_audiobooks.sh ~/Books/

# Custom voice and format
./scripts/convert_epubs_to_audiobooks.sh ~/Books/ --voice af_bella --format mp3

# Keep chapter files for inspection
./scripts/convert_epubs_to_audiobooks.sh ~/Books/ --no-cleanup
```

**Features:**
- Batch processes all EPUB files in a directory
- Automatically skips already-converted audiobooks
- Shows progress with file count and elapsed time
- Cleans up temporary files automatically (optional)
- Provides summary report at completion
