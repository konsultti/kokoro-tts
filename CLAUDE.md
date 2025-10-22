# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kokoro TTS is a text-to-speech tool using the Kokoro ONNX model. It provides both a CLI and web UI for converting text to speech. Supports multiple languages and voices with blending capabilities, and can process various input formats including text files, EPUB books, and PDF documents.

**Key characteristics:**
- **Dual interface**: CLI (`kokoro-tts`) and Web UI (`kokoro-tts-ui`)
- **Refactored architecture**: Core logic in `kokoro_tts/core.py`, CLI in `kokoro_tts/__init__.py`, UI in `kokoro_tts/ui/`
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

**CLI:**
```bash
# When installed locally with -e flag
uv run kokoro-tts --help

# Running as a module (without install)
uv run -m kokoro_tts --help

# With activated venv
python -m kokoro_tts --help
```

**Web UI:**
```bash
# Install with UI dependencies
pip install -e ".[ui]"

# Launch the web interface
uv run kokoro-tts-ui

# Or run directly
python -m kokoro_tts.ui.gradio_app
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

# Test GPU acceleration
uv run kokoro-tts input.txt output.wav --gpu --voice af_sarah

# Test Web UI with GPU
uv run kokoro-tts-ui --gpu
```

### Building and Publishing

```bash
# Build package
python -m build

# Publish to PyPI (handled by GitHub Actions on release)
# See .github/workflows/python-publish.yml
```

## Architecture

### Project Structure

```
kokoro_tts/
├── __init__.py          # Legacy CLI (backward compatible)
├── core.py              # Core TTS engine and business logic
└── ui/
    ├── __init__.py
    └── gradio_app.py    # Web UI implementation
```

### Core Components

**Core Engine (`kokoro_tts/core.py`):**
Refactored business logic providing reusable TTS functionality:

1. **KokoroEngine Class**
   - `__init__(use_gpu, provider)`: Initialize with optional GPU settings
   - `load_model()`: Initialize Kokoro ONNX model (sets GPU provider if requested)
   - `_select_gpu_provider()`: Auto-select best available GPU provider (TensorRT > CUDA > ROCm > CoreML)
   - `get_voices()`: List available voices
   - `validate_language()`, `validate_voice()`: Input validation
   - `chunk_text()`: Smart text chunking at sentence boundaries
   - `process_chunk()`: Process single chunk with auto-retry on phoneme errors
   - `generate_audio()`: Synchronous audio generation from text
   - `generate_audio_async()`: Async version for UI responsiveness
   - `process_file()`: Process entire files (txt/epub/pdf)
   - `process_file_async()`: Async file processing
   - `stream_audio_async()`: Streaming audio generation
   - `save_audio()`: Save audio to WAV/MP3/M4A
   - `extract_chapters_from_epub()`, `extract_chapters_from_pdf()`: Document parsing

2. **Data Classes**
   - `Chapter`: Represents text chapter with title, content, order
   - `ProcessingOptions`: Configuration for TTS (voice, speed, lang, format, debug)
   - `AudioFormat`: Enum for WAV/MP3/M4A

3. **Progress Callbacks**
   - Engine accepts `progress_callback(message, current, total)` for UI updates

4. **GPU Support**
   - `use_gpu` parameter: When True, automatically selects best GPU provider
   - `provider` parameter: Explicit provider name (takes precedence over use_gpu)
   - GPU providers set via `ONNX_PROVIDER` environment variable
   - Provider priority: TensorRT > CUDA > ROCm > CoreML
   - Compatible with both onnxruntime and onnxruntime-gpu packages

**CLI Module (`kokoro_tts/__init__.py`):**
Legacy CLI implementation (unchanged for backward compatibility):

1. **Input Processing**
   - `extract_text_from_epub()`: Basic EPUB text extraction
   - `extract_chapters_from_epub(skip_front_matter)`: Advanced EPUB chapter extraction with TOC parsing and optional front matter filtering
   - `is_front_matter(title, order, word_count)`: Detects front matter chapters (copyright, TOC, etc.)
   - `generate_audiobook_intro(metadata)`: Generates introduction text from book metadata
   - `PdfParser` class: PDF processing with TOC and markdown-based extraction
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
   - `--gpu` flag: Enables GPU acceleration (auto-selects best provider)
   - `check_gpu_availability(use_gpu)`: Detects and configures GPU providers
   - `print_gpu_info()`: Displays GPU status and recommendations

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
- Optional front matter filtering (enabled for audiobooks):
  - Skips: copyright, TOC, acknowledgments, dedication, "about the author"
  - Keeps: foreword, preface, introduction, prologue (considered story content)
  - Uses `is_front_matter()` function with title, order, and word count heuristics
- Extracts content between fragment IDs for precise chapter boundaries

**PDF Processing:**
- Two-stage approach: TOC extraction → markdown conversion fallback
- Uses `fitz` (PyMuPDF) for TOC-based extraction
- Uses `pymupdf4llm` for markdown conversion when TOC unavailable
- Filters duplicate entries and empty chapters

**GPU Acceleration:**
- Two methods: `--gpu` CLI flag (recommended) or `ONNX_PROVIDER` env variable
- `--gpu` flag automatically selects best provider using priority: TensorRT > CUDA > ROCm > CoreML
- Environment variable takes precedence over `--gpu` flag
- Apple Silicon (CoreML) is auto-enabled by default on macOS
- GPU provider is set via `ONNX_PROVIDER` environment variable before loading model
- `kokoro-onnx` library respects the environment variable for provider selection
- Compatible with both `onnxruntime` (CPU + CoreML) and `onnxruntime-gpu` (CUDA/TensorRT/ROCm)
- Both packages can coexist; runtime selection based on `ONNX_PROVIDER`

**Audiobook Processing:**
- Automatic front matter detection and skipping (enabled by default with `--audiobook`)
- Front matter keywords defined in `FRONT_MATTER_SKIP_KEYWORDS` constant
- `is_front_matter()` uses title matching, position, and word count heuristics
- Generated introduction chapter added automatically:
  - Format: "This is [title], written by [author], narrated by Kokoro Text-to-Speech"
  - Uses metadata from EPUB/PDF if available
  - Can be customized with `--intro-text` or disabled with `--no-intro`
- Introduction inserted as Chapter 0 before selected chapters
- AudiobookOptions includes: `skip_front_matter`, `intro_text`, `no_intro`

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

**Entry Points:**
- CLI: `kokoro-tts` → `kokoro_tts:main`
- Web UI: `kokoro-tts-ui` → `kokoro_tts.ui.gradio_app:launch_ui`

**Optional Dependencies:**
- `ui`: Gradio web interface (`pip install 'kokoro-tts[ui]'`)
  - `gradio>=4.0.0`: Web UI framework
- `gpu`: GPU acceleration support (`pip install 'kokoro-tts[gpu]'`)
  - `onnxruntime-gpu>=1.20.0`: ONNX runtime with CUDA/ROCm/TensorRT support

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

### Using the Web UI

The Gradio web UI provides three main interfaces:

1. **Quick Generate Tab**
   - Simple text-to-speech conversion
   - Select voice, adjust speed, choose language
   - Generates audio directly in browser for playback

2. **File Processing Tab**
   - Upload .txt, .epub, or .pdf files
   - Converts entire documents to audiobooks
   - Downloads generated audio in WAV/MP3/M4A format

3. **Voice Lab Tab**
   - **Voice Preview**: Test individual voices with sample text
   - **Voice Blending**: Mix two voices with adjustable weights
   - Experiment with different voice combinations

### Using the Core Engine Programmatically

```python
from kokoro_tts.core import KokoroEngine, ProcessingOptions, AudioFormat

# Initialize engine
engine = KokoroEngine(
    model_path="kokoro-v1.0.onnx",
    voices_path="voices-v1.0.bin"
)
engine.load_model()

# Generate audio
options = ProcessingOptions(
    voice="af_sarah",
    speed=1.2,
    lang="en-us",
    format=AudioFormat.WAV
)

samples, sample_rate = engine.generate_audio("Hello world!", options)
engine.save_audio(samples, sample_rate, "output.wav", AudioFormat.WAV)

# Or process a file
engine.process_file("input.epub", "output.mp3", options)
```

### Adding a New Input Format

1. Add extraction method to `KokoroEngine` class in `core.py`
2. Follow pattern of `extract_chapters_from_epub()` or `extract_chapters_from_pdf()`
3. Return list of `Chapter` objects
4. Update `process_file()` method to handle new extension
5. Update CLI `main()` if needed for backward compatibility
6. Update README.md with examples

### Modifying Audio Processing

- Core logic is in `KokoroEngine.process_chunk()` in `core.py`
- Be careful with recursive subdivision logic (phoneme limit handling)
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
