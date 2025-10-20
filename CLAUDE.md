# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kokoro TTS is a CLI text-to-speech tool using the Kokoro ONNX model. It supports multiple languages and voices with blending capabilities, and can process various input formats including text files, EPUB books, and PDF documents.

**Key characteristics:**
- Single-file architecture: All core functionality is in `kokoro_tts/__init__.py` (~1400 lines)
- Python 3.10-3.13 support
- Published to PyPI as `kokoro-tts`
- Uses `uv` as the preferred package manager
- Depends on external model files (`kokoro-v1.0.onnx` and `voices-v1.0.bin`)
- Uses kokoro-onnx 0.4.9 with hardcoded language support

## Development Commands

### Environment Setup

```bash
# Using uv (preferred)
uv venv
uv sync

# Using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application

```bash
# When installed locally with -e flag
uv run kokoro-tts --help

# Running as a module (without install)
uv run -m kokoro_tts --help

# With activated venv
python -m kokoro_tts --help
```

### Testing

There are no automated tests. Manual testing is required:

```bash
# Test basic text-to-speech
uv run kokoro-tts input.txt output.wav --speed 1.2 --lang en-us --voice af_sarah

# Test EPUB processing
uv run kokoro-tts input.epub --split-output ./chunks/ --format mp3

# Test PDF processing
uv run kokoro-tts input.pdf --split-output ./chunks/ --format mp3

# Test voice blending
uv run kokoro-tts input.txt --stream --voice "af_sarah:60,am_adam:40"

# Test stdin
echo "Hello World" | uv run kokoro-tts - --stream
```

### Building and Publishing

```bash
# Build package
python -m build

# Publish to PyPI (handled by GitHub Actions on release)
# See .github/workflows/python-publish.yml
```

## Architecture

### Core Components

**Main Module (`kokoro_tts/__init__.py`):**
All functionality is implemented in a single file with these key components:

1. **Input Processing**
   - `extract_text_from_epub()`: Basic EPUB text extraction
   - `extract_chapters_from_epub()`: Advanced EPUB chapter extraction with TOC parsing (lines 271-473)
   - `PdfParser` class: PDF processing with TOC and markdown-based extraction (lines 475-703)
   - Handles stdin cross-platform (Linux/macOS: `/dev/stdin`, `-`; Windows: `CONIN$`)

2. **Text Chunking**
   - `chunk_text()`: Splits text at sentence boundaries with dynamic sizing (lines 86-134)
   - Default chunk size: 1000 characters
   - Handles automatic subdivision for phoneme length errors

3. **Audio Generation**
   - `process_chunk_sequential()`: Processes text chunks with automatic retry and subdivision (lines 705-808)
   - Recursive subdivision when hitting phoneme length limits (index 510 error)
   - Voice blending support: Accepts single voice or "voice1:weight,voice2:weight" format
   - `stream_audio()`: Async audio streaming (lines 1064-1097)

4. **Output Handling**
   - Supports WAV and MP3 formats
   - Single file output: Concatenates all chapters
   - Split output: Saves chunks to `chapter_XXX/chunk_XXX.{format}` directories
   - Resume capability: Skips already-processed chunks
   - `merge_chunks_to_chapters()`: Merges chunks into complete chapter files (lines 1109-1226)

5. **CLI Handling**
   - `main()`: Entry point with argument parsing (lines 1249-1392)
   - Validates options with typo suggestions using `difflib`
   - Interactive voice selection when not specified via CLI

### Data Flow

```
Input File (txt/epub/pdf) → Chapter Extraction → Text Chunking →
Audio Generation (with retry/subdivision) → Output (stream/file/split)
```

### Important Implementation Details

**Phoneme Length Handling:**
The model has a phoneme length limit that can cause "index 510 is out of bounds" errors. The code handles this by:
- Catching the error in `process_chunk_sequential()`
- Reducing chunk size by 40% (multiplying by 0.6)
- Recursively processing subdivided pieces
- Concatenating results back together

**Voice Blending:**
Voices can be blended by:
- Parsing "voice1:weight,voice2:weight" format
- Normalizing weights to sum to 100
- Using numpy to blend voice style vectors: `np.add(style1 * (w1/100), style2 * (w2/100))`
- Equal blend if no weights specified: "voice1,voice2" defaults to 50-50

**EPUB Processing:**
- First attempts TOC-based extraction via `ebooklib`
- Falls back to document-by-document processing if TOC fails
- Skips front matter (copyright, title page, cover)
- Extracts content between fragment IDs for precise chapter boundaries

**PDF Processing:**
- Two-stage approach: TOC extraction → markdown conversion fallback
- Uses `fitz` (PyMuPDF) for TOC-based extraction
- Uses `pymupdf4llm` for markdown conversion when TOC unavailable
- Filters duplicate entries and empty chapters

## Project Configuration

**Dependencies** (pyproject.toml):
- `beautifulsoup4`: HTML parsing for EPUB
- `ebooklib`: EPUB file handling
- `kokoro-onnx==0.4.9`: Core TTS model (pinned version)
- `pymupdf` + `pymupdf4llm`: PDF processing
- `sounddevice` + `soundfile`: Audio I/O
- Development: `build`, `twine` for PyPI publishing

**Important Notes:**
- Language support is hardcoded in `SUPPORTED_LANGUAGES` constant (lines 29-41)
- kokoro-onnx 0.4.9 no longer exposes `get_languages()` API
- Supported languages: en-us, en-gb, ja, zh, ko, es, fr, hi, it, pt-br

**Entry Point:**
- Script name: `kokoro-tts`
- Points to: `kokoro_tts:main`

**Model Files:**
Required files (not in repo, downloaded separately):
- `kokoro-v1.0.onnx` (325MB)
- `voices-v1.0.bin` (26MB)
- Download URLs in README.md

## Code Style

Follow PEP 8 with these conventions observed in the codebase:
- 4-space indentation
- Import grouping: stdlib → third-party → local
- Docstrings for functions and classes
- Global state for spinner/audio control (`stop_spinner`, `stop_audio`)
- Cross-platform path handling (see stdin indicators)

## Common Workflows

### Adding a New Input Format

1. Add file extension check in `main()` after line 887
2. Create extraction function (follow `extract_chapters_from_epub` pattern)
3. Return list of dicts with `{'title': str, 'content': str, 'order': int}`
4. Update usage docs in `print_usage()` and README.md

### Adding a New CLI Option

1. Add to `get_valid_options()` (line 1228)
2. Add parsing logic in `main()` starting line 1334
3. Thread through to `convert_text_to_audio()` (line 810)
4. Update `print_usage()` (line 148) and README.md

### Modifying Audio Processing

- Core logic is in `process_chunk_sequential()` (line 705)
- Be careful with recursive subdivision logic
- Test with long texts to trigger phoneme errors
- Ensure sample rate consistency across chunks

## Release Process

1. Update version in `pyproject.toml`
2. Update README.md if needed
3. Commit with message following COMMIT_GUIDELINES.md
4. Create GitHub release
5. GitHub Actions automatically builds and publishes to PyPI

## Known Constraints

- Python 3.9 not supported (requires 3.10+)
- Model has phoneme length limit (~510 tokens)
- Model files must be in working directory or specified via `--model` and `--voices`
- No automated test suite (manual testing only)
- Single-threaded audio generation (no parallel chunk processing)
- Language list is hardcoded and not dynamically retrieved from kokoro-onnx
