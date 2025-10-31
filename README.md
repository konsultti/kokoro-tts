# Kokoro TTS

A text-to-speech tool using the Kokoro ONNX model with CLI and Web UI interfaces.

**This is a fork from https://github.com/nazdridoy/kokoro-tts**

## Major Upgrades from Original

- **🚀 NEW: Background Job Queue System** - Non-blocking UI with persistent job queue
- Fixed critical memory leak
- **3-8x performance boost** with parallel chunk processing
- Added AAC M4A output with metadata support
- Updated dependencies to latest versions
- Web UI with voice preview and blending
- New CLI features: `--audiobook`, `--parallel`, chapter selection
- Improved GPU support (NVIDIA, AMD, Apple Silicon)
- Auto-skip front matter when creating audiobooks
- Comprehensive testing framework

All new features coded by Claude Code.

## Features

- 🎭 **Dual Interface**: Command-line tool + browser-based web UI
- 🚀 **Background Job Queue**: Submit audiobook jobs and close browser - processing continues in background!
- 📊 **Job Dashboard**: Monitor progress, cancel jobs, resume failed jobs with full status tracking
- 🌍 **10 Languages**: en-us, en-gb, ja, zh, ko, es, fr, hi, it, pt-br
- 🎙️ **48+ Voices**: Wide variety with blending capabilities
- 📚 **Multiple Formats**: Process EPUB books, PDF documents, and text files
- ⚡ **High Performance**: 3-8x speedup with parallel processing on multi-core systems
- 💪 **GPU Acceleration**: CUDA, TensorRT, ROCm, and CoreML support
- 🎵 **Output Formats**: WAV, MP3, and M4A with metadata
- 🔄 **Streaming**: Real-time audio playback
- 📖 **Smart Processing**: Automatic chapter detection and front matter filtering
- 💾 **Persistent Jobs**: SQLite-based job persistence with resume capability

## Quick Start

### 1. Installation

**Install from Git (Recommended):**

```bash
# CLI only
pip install git+https://github.com/konsultti/kokoro-tts

# CLI + Web UI
pip install 'git+https://github.com/konsultti/kokoro-tts[ui]'

# CLI + Web UI + GPU support
pip install 'git+https://github.com/konsultti/kokoro-tts[ui,gpu]'
```

**Or clone and install locally:**

```bash
git clone https://github.com/konsultti/kokoro-tts.git
cd kokoro-tts
pip install -e .
```

### 2. Download Model Files

Download the required model files to your working directory:

```bash
# Download voice data (26 MB)
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# Download the model (325 MB)
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
```

### 3. Run

**Web UI (Easiest):**

```bash
kokoro-tts-ui
```

Then open http://127.0.0.1:7860 in your browser.

**CLI:**

```bash
# Basic usage
kokoro-tts input.txt output.wav

# Create an audiobook (parallel processing auto-enabled)
kokoro-tts book.epub audiobook.m4a --audiobook
```

See [USAGE.md](USAGE.md) for comprehensive usage instructions.

## 🚀 Background Job Queue System (NEW!)

The Web UI now includes a powerful background job queue system that revolutionizes audiobook generation:

### Key Benefits

- ✅ **Non-Blocking UI**: Submit jobs instantly, UI never freezes
- ✅ **Close Browser Anytime**: Jobs continue processing in background
- ✅ **Real-Time Progress**: Monitor jobs with live progress updates and ETA
- ✅ **Persistent Jobs**: Survive crashes and restarts with SQLite persistence
- ✅ **Resume Failed Jobs**: Automatic recovery from errors with partial progress saved
- ✅ **Job Dashboard**: Full job management (view, cancel, resume) in dedicated tab

### How to Use

1. **Start the UI** (worker starts automatically):
   ```bash
   kokoro-tts-ui
   ```

2. **Submit a Background Job**:
   - Go to "Audiobook Creator" tab
   - Upload your EPUB/PDF file
   - Select voice and settings
   - Click **"Submit as Background Job"**
   - Close the tab if you want!

3. **Monitor Progress**:
   - Switch to "Job Status" tab
   - See all jobs with real-time progress
   - View detailed job information
   - Cancel running jobs or resume failed ones

### Architecture

```
Web UI → JobManager → SQLite Database ← Worker Process
                                         (Background)
```

Jobs are stored in `~/.kokoro-tts/jobs.db` and completed audiobooks in `~/.kokoro-tts/audiobooks/`

For technical details, see [BACKGROUND_JOB_SYSTEM.md](BACKGROUND_JOB_SYSTEM.md)

## Installation Methods

### Method 1: Install from Git (Recommended)

Install directly from this fork:

```bash
# Using pip - CLI only
pip install git+https://github.com/konsultti/kokoro-tts

# Using pip - CLI + Web UI
pip install 'git+https://github.com/konsultti/kokoro-tts[ui]'

# Using pip - CLI + GPU support
pip install 'git+https://github.com/konsultti/kokoro-tts[gpu]'

# Using pip - Everything (CLI + Web UI + GPU)
pip install 'git+https://github.com/konsultti/kokoro-tts[ui,gpu]'

# Using uv (faster alternative to pip)
uv tool install git+https://github.com/konsultti/kokoro-tts
```

After installation:
```bash
# Test CLI
kokoro-tts --help

# Launch Web UI (if installed with [ui])
kokoro-tts-ui
```

### Method 2: Clone and Install Locally

For development or customization:

```bash
# 1. Clone the repository
git clone https://github.com/konsultti/kokoro-tts.git
cd kokoro-tts

# 2. Install with pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .

# Or install with uv (recommended)
uv venv
uv pip install -e .
```

### Method 3: Run Without Installation

For testing or one-time use:

```bash
# 1. Clone the repository
git clone https://github.com/konsultti/kokoro-tts.git
cd kokoro-tts

# 2. Install dependencies only
uv venv && uv sync

# 3. Run directly as a module
uv run -m kokoro_tts --help
```

## GPU Acceleration (Optional)

### Apple Silicon (M1/M2/M3/M4)

CoreML is **automatically enabled** on Apple Silicon - no setup needed! You'll see:
```
GPU acceleration: Using CoreMLExecutionProvider (auto-enabled)
```

To manually control:
```bash
# Force CPU execution (disable Neural Engine)
export ONNX_PROVIDER=CPUExecutionProvider
```

### NVIDIA/AMD GPUs

**Method 1: Using `--gpu` flag (Recommended)**

1. Install with GPU support:
```bash
pip install 'git+https://github.com/konsultti/kokoro-tts[gpu]'
```

2. Use the flag:
```bash
kokoro-tts input.txt output.wav --gpu
kokoro-tts-ui --gpu
```

**Method 2: Environment Variable**

```bash
# NVIDIA CUDA
export ONNX_PROVIDER=CUDAExecutionProvider

# NVIDIA TensorRT (if available)
export ONNX_PROVIDER=TensorrtExecutionProvider

# AMD ROCm
export ONNX_PROVIDER=ROCMExecutionProvider

# Then run normally
kokoro-tts input.txt output.wav
```

**Performance:**
- CPU: ~4.5s for short text
- GPU (CUDA): ~3.6s (20% faster)
- CoreML (Apple): ~3.2s (30% faster)

## Performance Optimization

Kokoro TTS includes parallel chunk processing for **3-8x speedup** on multi-core systems.

### Enable Parallel Processing

**Environment Variables (for Web UI):**
```bash
export KOKORO_USE_PARALLEL=true
export KOKORO_MAX_WORKERS=4
kokoro-tts-ui
```

**CLI Flags:**
```bash
kokoro-tts book.epub audiobook.m4a --parallel --max-workers 4
```

**Programmatic API:**
```python
from kokoro_tts.core import KokoroEngine
from kokoro_tts.config import PerformanceConfig

config = PerformanceConfig(use_parallel=True, max_workers=4)
engine = KokoroEngine(performance_config=config)
```

### When to Use

**Best for:**
- Large EPUB books (10+ chapters)
- Long PDF documents
- Batch processing
- Multi-core systems (4+ cores)

**Not needed for:**
- Short texts (< 5000 characters)
- Single-core systems
- Real-time streaming

See [PERFORMANCE.md](docs/PERFORMANCE.md) for detailed optimization guide.

## Supported Voices

48+ voices across multiple languages and dialects:

| **Language** | **Voices** |
|--------------|------------|
| 🇺🇸 English (US) - Female | af_alloy, af_aoede, af_bella, af_heart, af_jessica, af_kore, af_nicole, af_nova, af_river, af_sarah, af_sky |
| 🇺🇸 English (US) - Male | am_adam, am_echo, am_eric, am_fenrir, am_liam, am_michael, am_onyx, am_puck |
| 🇬🇧 English (GB) | bf_alice, bf_emma, bf_isabella, bf_lily, bm_daniel, bm_fable, bm_george, bm_lewis |
| 🇫🇷 French | ff_siwis |
| 🇮🇹 Italian | if_sara, im_nicola |
| 🇯🇵 Japanese | jf_alpha, jf_gongitsune, jf_nezumi, jf_tebukuro, jm_kumo |
| 🇨🇳 Chinese | zf_xiaobei, zf_xiaoni, zf_xiaoxiao, zf_xiaoyi, zm_yunjian, zm_yunxi, zm_yunxia, zm_yunyang |

View all voices: `kokoro-tts --help-voices`

## Documentation

- [USAGE.md](USAGE.md) - Comprehensive usage guide with examples
- [PERFORMANCE.md](docs/PERFORMANCE.md) - Performance optimization guide
- [CLAUDE.md](CLAUDE.md) - Developer guide for Claude Code
- [tests/TESTING.md](tests/TESTING.md) - Testing documentation

## Requirements

- Python 3.10-3.13
- Model files: `kokoro-v1.0.onnx` and `voices-v1.0.bin`
- (Optional) GPU drivers for CUDA/ROCm acceleration

## Contributing

This is a personal project, but Pull Requests are welcome!

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Kokoro-ONNX](https://github.com/thewh1teagle/kokoro-onnx) - Original ONNX model
- [nazdridoy/kokoro-tts](https://github.com/nazdridoy/kokoro-tts) - Original Python implementation
