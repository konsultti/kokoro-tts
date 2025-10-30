# Kokoro TTS Usage Guide

This guide covers all the ways to use Kokoro TTS, from the simple web interface to advanced CLI options.

## Table of Contents

- [Web UI Usage](#web-ui-usage)
- [CLI Usage](#cli-usage)
- [CLI Commands](#cli-commands)
- [CLI Options](#cli-options)
- [Input Formats](#input-formats)
- [Usage Examples](#usage-examples)
  - [Basic Text-to-Speech](#basic-text-to-speech)
  - [Standard Input (stdin)](#standard-input-stdin)
  - [Voice Blending](#voice-blending)
  - [EPUB Book Processing](#epub-book-processing)
  - [PDF Document Processing](#pdf-document-processing)
  - [Audiobook Creation](#audiobook-creation)
  - [Parallel Processing](#parallel-processing)
  - [GPU Acceleration](#gpu-acceleration)
  - [Custom Model Paths](#custom-model-paths)
  - [Utility Commands](#utility-commands)
- [Features in Detail](#features-in-detail)
- [Tips and Best Practices](#tips-and-best-practices)

## Web UI Usage

The web interface is the easiest way to use Kokoro TTS, especially for beginners.

### Launch the Web UI

```bash
# Basic launch
kokoro-tts-ui

# Custom port
kokoro-tts-ui --server-port 8080

# Listen on all interfaces (access from other devices)
kokoro-tts-ui --server-name 0.0.0.0

# Create a public share link (for remote access)
kokoro-tts-ui --share

# With GPU acceleration
kokoro-tts-ui --gpu

# Custom model paths
kokoro-tts-ui --model /path/to/model.onnx --voices /path/to/voices.bin

# With parallel processing enabled
export KOKORO_USE_PARALLEL=true
export KOKORO_MAX_WORKERS=4
kokoro-tts-ui
```

The UI will be available at `http://127.0.0.1:7860` (or your custom port).

### Web UI Features

**📝 Quick Generate Tab:**
- Enter text directly in the browser
- Select voice from dropdown menu
- Adjust speech speed (0.5x to 2.0x)
- Choose language
- Play audio directly in browser
- Download generated audio

**📁 File Processing Tab:**
- Upload `.txt`, `.epub`, or `.pdf` files
- Select output format (WAV, MP3, M4A)
- Choose voice and adjust settings
- Process entire books to audiobooks
- Download completed files

**🎭 Voice Lab Tab:**
- **Voice Preview**: Test individual voices with sample text
- **Voice Blending**: Mix two voices with adjustable weights (sliders)
- Experiment with different voice combinations
- Hear the results immediately

### Web UI Tips

- For large files, use the File Processing tab (more efficient than Quick Generate)
- Voice Lab is great for finding your favorite voice before processing a book
- Enable parallel processing via environment variables for faster processing
- Use M4A format for audiobooks (includes metadata support)

## CLI Usage

The command-line interface provides more control and is better for automation.

### Basic Syntax

```bash
kokoro-tts <input_file> [<output_file>] [options]
```

### Installation Method Notes

The command you use depends on how you installed Kokoro TTS:

| Installation Method | Command to Use |
|---------------------|----------------|
| Method 1: `pip install git+...` | `kokoro-tts` |
| Method 2: Local install with `-e` | `kokoro-tts` or `uv run kokoro-tts` |
| Method 3: No install | `uv run -m kokoro_tts` or `python -m kokoro_tts` |

For the rest of this guide, we'll use `kokoro-tts` in examples. Substitute with your appropriate command.

## CLI Commands

### Help Commands

```bash
# Show general help
kokoro-tts --help

# List all supported languages
kokoro-tts --help-languages

# List all available voices
kokoro-tts --help-voices
```

### Utility Commands

```bash
# Merge existing chunks into chapter files
kokoro-tts --merge-chunks --split-output ./chunks/ --format wav
```

## CLI Options

### Basic Options

| Option | Description | Default |
|--------|-------------|---------|
| `--stream` | Stream audio instead of saving to file | Disabled |
| `--speed <float>` | Speech speed (0.5 to 2.0) | 1.0 |
| `--lang <code>` | Language code | en-us |
| `--voice <name>` | Voice name or blend | Interactive selection |
| `--format <fmt>` | Output format: wav, mp3, or m4a | wav |
| `--debug` | Show detailed debug information | Disabled |

### Output Options

| Option | Description |
|--------|-------------|
| `--split-output <dir>` | Save each chunk as separate file in directory |
| `--chapters <dir>` | Save one audio file per chapter (memory efficient) |

### Audiobook Options

| Option | Description | Default |
|--------|-------------|---------|
| `--audiobook <file>` | Create M4A audiobook with metadata (parallel processing auto-enabled) | - |
| `--title <text>` | Book title for metadata | From file |
| `--author <name>` | Author name for metadata | From file |
| `--narrator <name>` | Narrator name for metadata | "Kokoro TTS" |
| `--cover <image>` | Cover image path | From EPUB |
| `--select-chapters <list>` | Chapter selection (e.g., "1-5,10") | All chapters |
| `--skip-front-matter` | Skip copyright, TOC, etc. | Enabled |
| `--intro-text <text>` | Custom introduction text | Auto-generated |
| `--no-intro` | Disable introduction chapter | Disabled |

### Performance Options

| Option | Description | Default |
|--------|-------------|---------|
| `--parallel` | Enable parallel chunk processing | Disabled (auto-enabled for `--audiobook`) |
| `--max-workers <n>` | Number of worker threads | CPU count - 1 |
| `--gpu` | Enable GPU acceleration (auto-select provider) | Disabled |

### Advanced Options

| Option | Description | Default |
|--------|-------------|---------|
| `--model <path>` | Path to ONNX model file | ./kokoro-v1.0.onnx |
| `--voices <path>` | Path to voices file | ./voices-v1.0.bin |

## Input Formats

Kokoro TTS supports multiple input formats:

| Format | Extension | Notes |
|--------|-----------|-------|
| Text file | `.txt` | Plain text |
| EPUB book | `.epub` | Extracts chapters automatically |
| PDF document | `.pdf` | Extracts chapters from TOC or content |
| Standard input | `-` or `/dev/stdin` | Pipe from other programs |

## Usage Examples

### Basic Text-to-Speech

```bash
# Simple text file to audio
kokoro-tts input.txt output.wav

# With specific voice and speed
kokoro-tts input.txt output.wav --speed 1.2 --lang en-us --voice af_sarah

# Stream audio directly (no file saved)
kokoro-tts input.txt --stream --speed 0.8

# Different output formats
kokoro-tts input.txt output.mp3 --format mp3
kokoro-tts input.txt output.m4a --format m4a

# Choose voice interactively
kokoro-tts input.txt output.wav
# (will prompt for voice selection)
```

### Standard Input (stdin)

```bash
# Read from stdin and stream
echo "Hello World" | kokoro-tts - --stream

# Pipe from file
cat input.txt | kokoro-tts - output.wav

# Pipe from another command
curl https://example.com/article.txt | kokoro-tts - --stream

# Cross-platform support
# Linux/macOS: Works with /dev/stdin or -
# Windows: Works with - or CONIN$
```

### Voice Blending

Create unique voice combinations by blending multiple voices:

```bash
# Two-voice blend with specific weights (60% sarah, 40% adam)
kokoro-tts input.txt output.wav --voice "af_sarah:60,am_adam:40"

# Equal blend (50-50)
kokoro-tts input.txt --stream --voice "am_adam,af_sarah"

# Three-way blend
kokoro-tts input.txt output.wav --voice "af_sarah:50,am_adam:30,af_bella:20"

# Blend with streaming
kokoro-tts input.txt --stream --voice "af_nicole:70,af_sky:30"
```

**Note:** Weights are normalized to 100%, so "2,1" is the same as "66.67,33.33".

### EPUB Book Processing

```bash
# Process EPUB with chapters (memory efficient, recommended)
kokoro-tts book.epub --chapters ./audiobook/ --format m4a

# Process with specific voice and speed
kokoro-tts book.epub --chapters ./audiobook/ --voice af_sarah --speed 1.1 --format m4a

# Process and split into small chunks
kokoro-tts book.epub --split-output ./chunks/ --format mp3

# Process with debug output to see chapter structure
kokoro-tts book.epub --chapters ./audiobook/ --debug --format m4a

# Single file output (concatenate all chapters)
kokoro-tts book.epub audiobook.m4a --format m4a
```

### PDF Document Processing

```bash
# Process PDF with chapter detection
kokoro-tts document.pdf --chapters ./chapters/ --format m4a

# Process PDF with specific settings
kokoro-tts document.pdf output.m4a --speed 1.2 --voice af_sarah --format m4a

# Process PDF and split into chunks
kokoro-tts document.pdf --split-output ./chunks/ --format mp3

# Debug PDF chapter extraction
kokoro-tts document.pdf --chapters ./output/ --debug
```

### Audiobook Creation

Create professional M4A audiobooks with embedded metadata, cover art, and chapter markers:

```bash
# Basic audiobook (uses metadata from EPUB)
kokoro-tts book.epub --audiobook audiobook.m4a

# With custom metadata
kokoro-tts book.epub --audiobook output.m4a \
  --title "The Great Novel" \
  --author "Jane Smith" \
  --narrator "Kokoro Sarah"

# Skip front matter (copyright, TOC, etc.) - enabled by default
kokoro-tts book.epub --audiobook output.m4a --skip-front-matter

# Custom introduction text
kokoro-tts book.epub --audiobook output.m4a \
  --intro-text "Welcome to this audiobook presentation of the great novel"

# Disable auto-generated introduction
kokoro-tts book.epub --audiobook output.m4a --no-intro

# Select specific chapters
kokoro-tts book.epub --audiobook output.m4a --select-chapters "1-5,10"

# With custom cover image
kokoro-tts book.epub --audiobook output.m4a --cover cover.jpg

# Complete example with all options
kokoro-tts book.epub --audiobook output.m4a \
  --title "The Great Novel" \
  --author "Jane Smith" \
  --narrator "Kokoro Sarah" \
  --voice af_sarah \
  --speed 1.1 \
  --cover cover.jpg \
  --select-chapters "all" \
  --skip-front-matter
```

**Audiobook Features:**
- **Parallel processing auto-enabled** for 3-8x faster generation on multi-core systems
- Automatically skips front matter (copyright, TOC, acknowledgments, dedication, "about the author")
- Preserves story content (foreword, preface, introduction, prologue)
- Generates introduction: "This is [title], written by [author], narrated by Kokoro Text-to-Speech"
- Embeds chapter markers for easy navigation
- Includes metadata: title, author, narrator, cover art
- M4A format with AAC audio (widely compatible)

### Parallel Processing

Speed up processing on multi-core systems:

```bash
# Audiobook mode (parallel processing auto-enabled)
kokoro-tts book.epub --audiobook output.m4a

# Audiobook with custom worker count
kokoro-tts book.epub --audiobook output.m4a --max-workers 8

# Manual parallel processing for non-audiobook
kokoro-tts book.epub audiobook.m4a --parallel --max-workers 4

# Combine with GPU acceleration
kokoro-tts book.epub --audiobook output.m4a --gpu

# Using environment variables (for Web UI)
export KOKORO_USE_PARALLEL=true
export KOKORO_MAX_WORKERS=4
kokoro-tts book.epub audiobook.m4a
```

**Performance expectations:**
- 4 cores: 2.5-3.5x speedup
- 8 cores: 3.5-5.5x speedup
- 16+ cores: 5.0-8.0x speedup

See [PERFORMANCE.md](docs/PERFORMANCE.md) for detailed benchmarking.

### GPU Acceleration

```bash
# Enable GPU with auto-selection (recommended)
kokoro-tts input.txt output.wav --gpu --voice af_sarah

# Web UI with GPU
kokoro-tts-ui --gpu

# GPU + parallel processing (maximum speed)
kokoro-tts book.epub audiobook.m4a --gpu --parallel --max-workers 4

# Manual GPU provider selection via environment variable
export ONNX_PROVIDER=CUDAExecutionProvider
kokoro-tts input.txt output.wav

# Apple Silicon (CoreML is auto-enabled, no flag needed)
kokoro-tts input.txt output.wav  # Automatically uses Neural Engine
```

### Custom Model Paths

```bash
# Use custom model and voices files
kokoro-tts input.txt output.wav \
  --model /path/to/kokoro-v1.0.onnx \
  --voices /path/to/voices-v1.0.bin

# Use models from specific directory
kokoro-tts input.txt output.wav \
  --model ./models/kokoro-v1.0.onnx \
  --voices ./models/voices-v1.0.bin
```

### Utility Commands

```bash
# List all available voices
kokoro-tts --help-voices

# List all supported languages
kokoro-tts --help-languages

# Merge existing chunks into chapter files
kokoro-tts --merge-chunks --split-output ./chunks/ --format wav

# Check if GPU is available
kokoro-tts --help  # Shows GPU status in output
```

## Features in Detail

### EPUB Processing

When processing EPUB files, Kokoro TTS:

1. **Extracts chapters** using the book's Table of Contents (TOC)
2. **Preserves chapter titles** and structure
3. **Filters front matter** (optional, enabled by default for audiobooks)
   - Skips: copyright, TOC, acknowledgments, dedication, "about the author"
   - Keeps: foreword, preface, introduction, prologue
4. **Generates introduction** (optional, enabled for audiobooks)
5. **Creates organized output** with chapter-by-chapter files

**Front Matter Detection:**
Uses heuristics based on:
- Chapter title keywords
- Chapter position in book
- Word count (very short chapters likely to be front matter)

### PDF Processing

PDF processing uses a two-stage approach:

1. **TOC-based extraction** - Extracts chapters using PDF's Table of Contents
2. **Markdown conversion fallback** - Converts PDF to markdown if no TOC
3. **Duplicate filtering** - Removes duplicate entries
4. **Empty chapter handling** - Skips chapters with no text

### Audio Processing

**Text Chunking:**
- Smart chunking at sentence boundaries
- Default chunk size: 1000 characters
- Dynamic subdivision for phoneme length errors
- Preserves natural speech flow

**Error Handling:**
- Automatic retry on phoneme length errors
- Recursive subdivision (reduces chunk by 40%)
- Graceful handling of interruptions
- Progress indicators for long processes

**Voice Blending:**
- Parse "voice1:weight,voice2:weight" format
- Normalize weights to sum to 100%
- Blend voice style vectors using numpy
- Equal blend if no weights specified

### Output Options

**Single File Output:**
```bash
kokoro-tts book.epub audiobook.m4a
```
- Concatenates all chapters into one file
- Good for smaller books
- Uses more memory

**Chapter Output (Recommended for Books):**
```bash
kokoro-tts book.epub --chapters ./output/ --format m4a
```
- One file per chapter
- Memory efficient
- Easy to navigate
- Resume capability

**Split Output (Advanced):**
```bash
kokoro-tts book.epub --split-output ./output/ --format mp3
```
- Many small chunk files
- Organized in chapter subdirectories
- Resume capability
- Can merge later with `--merge-chunks`

### Debug Mode

Enable with `--debug` flag to see:
- File processing details
- NCX/TOC parsing details for EPUB
- Chapter metadata (title, order, word count)
- Front matter detection decisions
- Chunk processing progress
- Error details and stack traces

Useful for:
- Troubleshooting chapter extraction
- Understanding why certain chapters are skipped
- Diagnosing processing issues

## Tips and Best Practices

### General Tips

1. **Choose the right output mode:**
   - Small texts: Single file output
   - Books: `--chapters` mode (memory efficient)
   - Advanced users: `--split-output` with `--merge-chunks`

2. **Voice selection:**
   - Use Voice Lab in Web UI to preview voices
   - Try voice blending for unique combinations
   - Stick to same language as input text

3. **Speed adjustment:**
   - 1.0 = normal speed (natural)
   - 1.1-1.2 = slightly faster (common for audiobooks)
   - 0.8-0.9 = slower (good for learning)

4. **Format selection:**
   - WAV: Highest quality, largest size
   - MP3: Good quality, smaller size
   - M4A: Best for audiobooks (metadata support)

### Performance Tips

1. **Enable parallel processing for:**
   - Large books (10+ chapters)
   - Long documents
   - Multi-core systems (4+ cores)

2. **Use GPU acceleration for:**
   - Repeated processing
   - Real-time applications
   - When GPU is available (NVIDIA, AMD, Apple Silicon)

3. **Combine optimizations:**
   ```bash
   kokoro-tts book.epub audiobook.m4a --parallel --gpu --max-workers 4
   ```

4. **Monitor performance:**
   ```bash
   python tests/benchmark_performance.py
   ```

### Audiobook Creation Tips

1. **Use `--audiobook` flag** instead of manual processing (parallel processing auto-enabled)
2. **Enable `--skip-front-matter`** to skip boilerplate content (enabled by default)
3. **Add metadata** with `--title`, `--author`, `--narrator`
4. **Include cover art** with `--cover` for better organization
5. **Select chapters** strategically with `--select-chapters`
6. **Adjust workers** with `--max-workers` if needed (default uses all CPU cores)

### Troubleshooting

**No audio generated:**
- Check model files are in current directory
- Verify input file is valid
- Use `--debug` to see detailed errors

**Phoneme length errors:**
- Usually handled automatically with subdivision
- Try reducing text length manually if issues persist
- Check for unusual characters or formatting

**Poor audio quality:**
- Try different voices
- Adjust speed (too fast can sound garbled)
- Check input text formatting (remove excessive punctuation)

**Slow processing:**
- Use `--audiobook` flag (parallel processing auto-enabled)
- For non-audiobook: enable `--parallel` flag
- Enable GPU with `--gpu` flag for additional 20-30% speedup
- Increase workers with `--max-workers` (if using fewer than CPU count)
- Check system resources (CPU/memory usage)

**Chapter detection issues:**
- Use `--debug` to see detected chapters
- For PDFs, ensure TOC exists in document
- For EPUBs, check NCX/TOC structure

### Platform-Specific Notes

**Linux/macOS:**
- Use `wget` or `curl` to download models
- Stdin works with `/dev/stdin` or `-`
- GPU requires CUDA/ROCm drivers

**Windows:**
- Use browser or PowerShell to download models
- Stdin works with `-` (no need for `CONIN$`)
- GPU requires CUDA drivers
- WSL2 may show harmless device warnings

**Apple Silicon (M1/M2/M3/M4):**
- CoreML automatically enabled (Neural Engine)
- No GPU flag needed
- Excellent performance out of the box
- Best TTS performance on Mac

## Need More Help?

- Check [PERFORMANCE.md](docs/PERFORMANCE.md) for optimization guide
- See [README.md](README.md) for installation instructions
- Read [CLAUDE.md](CLAUDE.md) for developer information
- Open an issue on GitHub for bugs or feature requests
