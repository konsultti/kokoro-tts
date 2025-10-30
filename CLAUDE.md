# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kokoro TTS is a text-to-speech tool using the Kokoro ONNX model. It provides both a CLI and web UI for converting text to speech. Supports multiple languages and voices with blending capabilities, and can process various input formats including text files, EPUB books, and PDF documents.

**Key characteristics:**
- **Dual interface**: CLI (`kokoro-tts`) and Web UI (`kokoro-tts-ui`)
- **Refactored architecture**: Core logic in `kokoro_tts/core.py`, CLI in `kokoro_tts/__init__.py`, UI in `kokoro_tts/ui/`
- Python 3.10-3.13 support
- Uses `uv` as the preferred package manager
- Depends on external model files (`kokoro-v1.0.onnx` and `voices-v1.0.bin`)
- Uses kokoro-onnx 0.4.9 with hardcoded language support
- Fork of original kokoro-tts with additional audiobook features

## Development Commands

### Environment Setup

```bash
# Using uv (preferred)
uv venv
uv sync

# Using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
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

The project has minimal automated tests for audiobook features located in the `tests/` directory.

**Run automated tests:**
```bash
# Test audiobook front matter detection
python tests/test_front_matter.py

# Test audiobook intro generation
python tests/test_intro_generation.py

# Test parallel processing (Phase 1)
python tests/test_parallel_processing.py

# Performance benchmarking
python tests/benchmark_performance.py

# Create a test EPUB file
python tests/create_test_epub.py
```

**Manual testing** is required for most features:
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

# Test parallel processing performance
export KOKORO_USE_PARALLEL=true
export KOKORO_MAX_WORKERS=4
uv run kokoro-tts input.epub output.m4a --voice af_sarah

# Test CLI with parallel flags
uv run kokoro-tts input.epub output.m4a --parallel --max-workers 4
```

See `tests/TESTING.md` for comprehensive testing documentation.
See `PERFORMANCE.md` for performance optimization guide.

### Building

```bash
# Build package (if needed for local distribution)
python -m build
```

Note: This is a fork, not published to PyPI.

## Architecture

### Project Structure

```
kokoro_tts/
├── __init__.py          # Legacy CLI (backward compatible)
├── core.py              # Core TTS engine and business logic
├── config.py            # Performance configuration system
└── ui/
    ├── __init__.py
    └── gradio_app.py    # Web UI implementation

tests/
├── README.md            # Testing documentation
├── TESTING.md           # Comprehensive testing plan
├── test_front_matter.py # Unit tests for front matter detection
├── test_intro_generation.py # Unit tests for intro generation
├── test_parallel_processing.py # Unit tests for parallel processing
├── benchmark_performance.py # Performance benchmarking suite
└── create_test_epub.py  # Test EPUB generation script

scripts/
├── README.md            # Scripts documentation
└── convert_epubs_to_audiobooks.sh # Batch EPUB conversion

PERFORMANCE.md           # Performance optimization guide
IMPLEMENTATION_SUMMARY.md # Technical implementation details
```

### Core Components

**Core Engine (`kokoro_tts/core.py`):**
Refactored business logic providing reusable TTS functionality:

1. **KokoroEngine Class**
   - `__init__(use_gpu, provider, performance_config)`: Initialize with optional GPU and performance settings
   - `load_model()`: Initialize Kokoro ONNX model (sets GPU provider if requested)
   - `_select_gpu_provider()`: Auto-select best available GPU provider (TensorRT > CUDA > ROCm > CoreML)
   - `get_voices()`: List available voices
   - `validate_language()`, `validate_voice()`: Input validation
   - `chunk_text()`: Smart text chunking at sentence boundaries
   - `process_chunk()`: Process single chunk with auto-retry on phoneme errors
   - `generate_audio()`: Synchronous audio generation from text (with automatic parallel/sequential selection)
   - `_generate_audio_sequential()`: Sequential chunk processing (original implementation)
   - `_generate_audio_parallel()`: Parallel chunk processing (new - 3-8x speedup)
   - `_process_chunk_wrapper()`: Thread-safe wrapper for parallel processing
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

3. **Performance Configuration (`kokoro_tts/config.py`)**
   - `PerformanceConfig`: Dataclass for performance settings
     - `use_parallel`: Enable/disable parallel chunk processing (default: False)
     - `max_workers`: Number of worker threads (default: CPU count - 1)
     - `use_gpu_batching`: Enable GPU batching (Phase 2 - not yet implemented)
     - `gpu_batch_size`: GPU batch size (Phase 2 - not yet implemented)
     - `use_streaming`: Enable memory streaming (Phase 2 - not yet implemented)
   - `from_env()`: Load configuration from environment variables
   - `get_max_workers()`: Get actual worker count with auto-detection

4. **Progress Callbacks**
   - Engine accepts `progress_callback(message, current, total)` for UI updates
   - Thread-safe with locking for parallel processing

5. **GPU Support**
   - `use_gpu` parameter: When True, automatically selects best GPU provider
   - `provider` parameter: Explicit provider name (takes precedence over use_gpu)
   - GPU providers set via `ONNX_PROVIDER` environment variable
   - Provider priority: TensorRT > CUDA > ROCm > CoreML
   - Compatible with both onnxruntime and onnxruntime-gpu packages

6. **Performance Optimization**
   - **Parallel Chunk Processing**: 3-8x speedup on multi-core systems
   - Thread-safe execution using `concurrent.futures.ThreadPoolExecutor`
   - Automatic mode selection based on workload size
   - Configurable via environment variables or programmatic API
   - Preserves chunk order for deterministic output

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

## Development Process

1. Make changes on feature branches
2. Test manually with relevant test cases
3. Update README.md or CLAUDE.md if needed for significant changes
4. Commit with descriptive messages
5. Merge to `development` branch for testing
6. Merge to `main` when stable

## Known Constraints

- Python 3.9 not supported (requires 3.10+)
- Model has phoneme length limit (~510 tokens)
- Model files must be in working directory or specified via `--model` and `--voices`
- Limited automated tests (only for audiobook features)
- Single-threaded audio generation (no parallel chunk processing)
- Language list is hardcoded and not dynamically retrieved from kokoro-onnx
