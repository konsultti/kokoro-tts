# Batch EPUB to Audiobook Conversion

This guide explains how to use the `convert_epubs_to_audiobooks.sh` script to batch convert multiple EPUB files into audiobooks.

## Quick Start

```bash
# Basic usage - process all EPUBs in a directory
./convert_epubs_to_audiobooks.sh /path/to/epub/folder/

# With custom voice
./convert_epubs_to_audiobooks.sh /path/to/epub/folder/ --voice af_bella

# Keep temporary chapter files for inspection
./convert_epubs_to_audiobooks.sh /path/to/epub/folder/ --no-cleanup
```

## Features

✅ **Batch Processing** - Converts all EPUB files in a directory
✅ **Progress Tracking** - Shows current file (N/Total) and time elapsed
✅ **Smart Skip** - Automatically skips already-converted audiobooks
✅ **Automatic Cleanup** - Removes temporary chapter files after merging
✅ **File Organization** - Moves completed audiobooks back to source folder
✅ **Error Handling** - Continues processing even if one file fails
✅ **Summary Report** - Shows success/failure/skip counts at the end

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `<epub_directory>` | Path to folder containing EPUB files | **Required** |
| `--voice <voice>` | Voice to use for TTS | `af_sarah` |
| `--format <format>` | Output audio format (wav, mp3, m4a) | `m4a` |
| `--temp-dir <dir>` | Directory for temporary chapter files | `./audiobook` |
| `--no-cleanup` | Keep temporary chapter files | Cleanup enabled |
| `--help` | Show help message | - |

## Usage Examples

### Example 1: Basic Conversion
Convert all EPUBs in a folder with default settings:
```bash
./convert_epubs_to_audiobooks.sh /mnt/e/Books/
```

**Output:**
- `/mnt/e/Books/Book1.m4a` (complete audiobook)
- `/mnt/e/Books/Book2.m4a` (complete audiobook)
- Temporary files automatically cleaned up

### Example 2: Custom Voice
Use a different voice (e.g., af_bella):
```bash
./convert_epubs_to_audiobooks.sh /mnt/e/Books/ --voice af_bella
```

### Example 3: Keep Chapter Files
Preserve individual chapter files for inspection:
```bash
./convert_epubs_to_audiobooks.sh /mnt/e/Books/ --no-cleanup
```

**Output:**
- `/mnt/e/Books/Book1.m4a` (complete audiobook)
- `./audiobook/Chapter_001_Prologue.m4a`
- `./audiobook/Chapter_002_Chapter_One.m4a`
- ... (all individual chapters preserved)

### Example 4: Custom Temporary Directory
Use a different temp directory:
```bash
./convert_epubs_to_audiobooks.sh /mnt/e/Books/ --temp-dir /tmp/audiobook_processing
```

## How It Works

1. **Scans** the specified directory for `.epub` files
2. **Checks** if audiobook already exists (skips if found)
3. **Converts** EPUB to audiobook using `--chapters` mode:
   - Creates individual chapter files
   - Combines all chapters into single M4A
4. **Moves** the complete audiobook to the source directory
5. **Cleans** temporary chapter files (unless `--no-cleanup`)
6. **Repeats** for all EPUBs in the directory

## File Naming

**Input:**
`/mnt/e/Books/Leviathan Wakes.epub`

**Temporary Files:**
`./audiobook/Chapter_001_Prologue.m4a`
`./audiobook/Chapter_002_The_Canterbury_Tale.m4a`
`./audiobook/Leviathan_Wakes_Complete.m4a`

**Final Output:**
`/mnt/e/Books/Leviathan Wakes.m4a`

## Progress Display

```
╔════════════════════════════════════════════════════════╗
║  Kokoro TTS - Batch EPUB to Audiobook Converter       ║
╚════════════════════════════════════════════════════════╝

Configuration:
  EPUB Directory: /mnt/e/Books
  Voice:          af_sarah
  Format:         m4a
  Temp Directory: ./audiobook
  Cleanup:        true
  Files Found:    3

Process 3 EPUB file(s)? (y/N) y

═══════════════════════════════════════════════════════
Processing [1/3]: Book1.epub
═══════════════════════════════════════════════════════
► Starting conversion...
✓ Success! Duration: 45m 23s
✓ Audiobook saved: /mnt/e/Books/Book1.m4a
✓ File size: 487M
► Cleaning up chapter files...
✓ Cleanup complete

═══════════════════════════════════════════════════════
Processing [2/3]: Book2.epub
═══════════════════════════════════════════════════════
⊙ Audiobook already exists: /mnt/e/Books/Book2.m4a
⊙ Skipping...

╔════════════════════════════════════════════════════════╗
║                    Final Summary                       ║
╚════════════════════════════════════════════════════════╝

  Total Files:   3
  ✓ Successful:  2
  ⊙ Skipped:     1
  ✗ Failed:      0
```

## Error Handling

The script will:
- ✅ Continue processing if one file fails
- ✅ Show detailed error messages
- ✅ Report failures in final summary
- ✅ Return exit code 1 if any failures occurred

## Tips

1. **Resume Processing:** If interrupted, just re-run the script - it will skip already-completed audiobooks
2. **Disk Space:** Ensure you have enough space (typically 2-3x the EPUB size for temp files)
3. **GPU Acceleration:** Set `export ONNX_PROVIDER=CUDAExecutionProvider` before running for faster processing
4. **Testing:** Use `--no-cleanup` first to inspect chapter files, then clean manually

## Troubleshooting

**Problem:** "No EPUB files found"
**Solution:** Check the directory path and ensure it contains `.epub` files

**Problem:** "Expected output file not found"
**Solution:** Check disk space and ensure kokoro-tts completed successfully

**Problem:** Processing very slow
**Solution:** Enable GPU acceleration or reduce voice quality settings

## Integration with Automation

You can integrate this script into automation workflows:

```bash
# Cron job: Process new EPUBs nightly
0 2 * * * /path/to/convert_epubs_to_audiobooks.sh /mnt/e/NewBooks/ --voice af_sarah

# Watch directory for new EPUBs
inotifywait -m /mnt/e/NewBooks/ -e create -e moved_to |
    while read path action file; do
        if [[ "$file" =~ \.epub$ ]]; then
            ./convert_epubs_to_audiobooks.sh "$path"
        fi
    done
```

## See Also

- [Main README](README.md) - General kokoro-tts documentation
- [Voice Samples](samples/) - Preview different voice options
- [Project Documentation](CLAUDE.md) - Developer documentation
