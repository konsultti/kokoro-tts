# Kokoro TTS

A text-to-speech tool using the Kokoro model, supporting multiple languages, voices (with blending), and various input formats including EPUB books and PDF documents. Available as both a **CLI** and **Web UI**.

**This is a fork from https://github.com/nazdridoy/kokoro-tts**

*Major upgrades from original:*
- Fixed critical memory leak
- Improved performance
- Added AAC M4A outout
- Updated dependencies
- Web-UI added
- New CLI features, like --audiobook
- Include metadata to audiobook file
- Improved GPU support (Nvidia, AMD)

All new features are coded by Claude Code.


## Features

- 🎭 **Dual Interface**: Command-line tool + browser-based web UI
- 🌍 **Multiple Languages**: 10 languages supported (en-us, en-gb, ja, zh, ko, es, fr, hi, it, pt-br)
- 🎙️ **48+ Voices**: Wide variety of voices with blending capabilities
- 🎨 **Voice Blending**: Mix 2+ voices with customizable weights
- 📚 **Multiple Formats**: EPUB, PDF, and TXT file support
- 🔄 **Streaming**: Real-time audio playback via CLI or web
- 📖 **Smart Processing**: Chapter-by-chapter for large books (memory efficient)
- ⚡ **Adjustable Speed**: 0.5x to 2.0x speech rate
- 🎵 **Output Formats**: WAV, MP3, and M4A
- 🚀 **GPU Acceleration**: CUDA, TensorRT, ROCm, CoreML support
- 🖥️ **Web UI**: Easy-to-use Gradio interface with voice preview and blending


## TODO

- [x] Add GPU support
- [x] Add PDF support
- [x] Add Web UI
- [] Improve Web UI (chapter selection etc)
- [] Add native GUI

## Prerequisites

- Python 3.10-3.13

## Installation

### Method 1: Install from Git (Recommended)

Install directly from this fork to get the latest features:

```bash
# Using uv (recommended)
uv tool install git+https://github.com/konsultti/kokoro-tts

# Using pip - CLI only
pip install git+https://github.com/konsultti/kokoro-tts

# Using pip - CLI + Web UI
pip install 'git+https://github.com/konsultti/kokoro-tts[ui]'

# Using pip - CLI + GPU support
pip install 'git+https://github.com/konsultti/kokoro-tts[gpu]'

# Using pip - CLI + Web UI + GPU support
pip install 'git+https://github.com/konsultti/kokoro-tts[ui,gpu]'
```

After installation, you can run:
```bash
# CLI
kokoro-tts --help

# Web UI
kokoro-tts-ui
```

### Method 2: Clone and Install Locally

1. Clone the repository:
```bash
git clone https://github.com/konsultti/kokoro-tts.git
cd kokoro-tts
```

2. Install the package:

**With `uv` (recommended):**
```bash
uv venv
uv pip install -e .
```

**With `pip`:**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

3. Run the tool:
```bash
# If using uv
uv run kokoro-tts --help

# If using pip with activated venv
kokoro-tts --help
```

### Method 3: Run Without Installation

If you prefer to run without installing:

1. Clone the repository:
```bash
git clone https://github.com/konsultti/kokoro-tts.git
cd kokoro-tts
```

2. Install dependencies only:

**With `uv`:**
```bash
uv venv
uv sync
```

**With `pip`:**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. Run directly:
```bash
# With uv
uv run -m kokoro_tts --help

# With pip (venv activated)
python -m kokoro_tts --help
```

### Download Model Files

After installation, download the required model files to your working directory:

```bash
# Download voice data (bin format is preferred)
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# Download the model
wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
```

> **Note:** The script requires `voices-v1.0.bin` and `kokoro-v1.0.onnx` to be present in the same directory where you run the `kokoro-tts` command. The models are downloaded from the upstream [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) repository.

### GPU Acceleration (Optional)

Kokoro TTS supports GPU acceleration for faster processing across different platforms.

#### Apple Silicon (M1/M2/M3/M4)

Apple Silicon Macs have built-in CoreML support with **automatic Neural Engine acceleration** - no configuration needed!

**CoreML is automatically enabled** when running on Apple Silicon. You'll see:
```
GPU acceleration: Using CoreMLExecutionProvider (auto-enabled)
```

To manually control the provider or force CPU execution:

```bash
# Force CoreML (usually not needed - it's auto-enabled)
export ONNX_PROVIDER=CoreMLExecutionProvider

# Force CPU execution (if you want to disable Neural Engine)
export ONNX_PROVIDER=CPUExecutionProvider
```

#### NVIDIA/AMD GPUs (Linux/Windows)

**Method 1: Using the `--gpu` flag (Recommended)**

1. **Install with GPU support**:

```bash
# Using pip
pip install 'kokoro-tts[gpu]'

# Using uv
uv pip install 'kokoro-tts[gpu]'

# Or install git version with GPU support
pip install 'git+https://github.com/konsultti/kokoro-tts[gpu]'
```

This installs `onnxruntime-gpu` alongside the CPU version, allowing you to choose at runtime.

2. **Use the `--gpu` flag**:

```bash
# Enable GPU acceleration automatically
kokoro-tts input.txt output.wav --voice af_sarah --gpu

# Web UI with GPU
kokoro-tts-ui --gpu
```

The `--gpu` flag automatically selects the best available GPU provider (TensorRT > CUDA > ROCm).

**Method 2: Environment Variable (Advanced)**

If you prefer manual control or need to specify a particular provider:

```bash
# For CUDA/NVIDIA GPUs
export ONNX_PROVIDER=CUDAExecutionProvider

# For TensorRT (if available)
export ONNX_PROVIDER=TensorrtExecutionProvider

# For ROCm/AMD GPUs
export ONNX_PROVIDER=ROCMExecutionProvider

# Then run normally (no --gpu flag needed)
kokoro-tts input.txt output.wav --voice af_sarah
```

#### Notes

- GPU acceleration provides **~20-40% speed improvement** over CPU
- **Apple Silicon (M1/M2/M3/M4)**: CoreML Neural Engine acceleration is **automatically enabled** - no setup required!
- **NVIDIA/AMD GPUs**: Use `--gpu` flag (recommended) or set `ONNX_PROVIDER` environment variable
- The tool will automatically detect available GPU providers and show their status
- Installation with `[gpu]` extra allows runtime selection between CPU and GPU (no need to uninstall anything)
- You need appropriate GPU drivers installed (CUDA for NVIDIA, ROCm for AMD)
- In WSL2, you may see a harmless warning about device discovery - this doesn't prevent GPU usage

#### Performance Comparison

- **CPU only**: ~4.5 seconds for a short text
- **GPU (CUDA)**: ~3.6 seconds for the same text (20% faster)
- **CoreML (Apple Silicon)**: ~3.2 seconds for the same text (30% faster)

## Supported voices:

| **Category** | **Voices** | **Language Code** |
| --- | --- | --- |
| 🇺🇸 👩 | af\_alloy, af\_aoede, af\_bella, af\_heart, af\_jessica, af\_kore, af\_nicole, af\_nova, af\_river, af\_sarah, af\_sky | **en-us** |
| 🇺🇸 👨 | am\_adam, am\_echo, am\_eric, am\_fenrir, am\_liam, am\_michael, am\_onyx, am\_puck | **en-us** |
| 🇬🇧 | bf\_alice, bf\_emma, bf\_isabella, bf\_lily, bm\_daniel, bm\_fable, bm\_george, bm\_lewis | **en-gb** |
| 🇫🇷 | ff\_siwis | **fr-fr** |
| 🇮🇹 | if\_sara, im\_nicola | **it** |
| 🇯🇵 | jf\_alpha, jf\_gongitsune, jf\_nezumi, jf\_tebukuro, jm\_kumo | **ja** |
| 🇨🇳 | zf\_xiaobei, zf\_xiaoni, zf\_xiaoxiao, zf\_xiaoyi, zm\_yunjian, zm\_yunxi, zm\_yunxia, zm\_yunyang | **cmn** |

## Usage

### Web UI (Recommended for Beginners)

The easiest way to use Kokoro TTS is through the web interface:

```bash
# Launch the web UI (requires gradio)
kokoro-tts-ui
```

This will start a local web server at `http://127.0.0.1:7860` with an easy-to-use interface featuring:

**📝 Quick Generate Tab:**
- Enter text directly in the browser
- Select voice, adjust speed, choose language
- Play audio directly or download

**📁 File Processing Tab:**
- Upload `.txt`, `.epub`, or `.pdf` files
- Convert entire books to audiobooks
- Download in WAV, MP3, or M4A format

**🎭 Voice Lab Tab:**
- Preview different voices with sample text
- Blend two voices with adjustable weights
- Experiment with voice combinations

**Command Line Options for Web UI:**
```bash
# Custom port
kokoro-tts-ui --server-port 8080

# Listen on all interfaces
kokoro-tts-ui --server-name 0.0.0.0

# Create a public share link
kokoro-tts-ui --share

# Custom model paths
kokoro-tts-ui --model /path/to/model.onnx --voices /path/to/voices.bin
```

---

### CLI Usage (For Advanced Users)

```bash
kokoro-tts <input_text_file> [<output_audio_file>] [options]
```

> [!NOTE]
> - If you installed via Method 1 (PyPI) or Method 2 (git install), use `kokoro-tts` directly
> - If you installed via Method 3 (local install), use `uv run kokoro-tts` or activate your virtual environment first
> - If you're using Method 4 (no install), use `uv run -m kokoro_tts` or `python -m kokoro_tts` with activated venv

### Commands

- `-h, --help`: Show help message
- `--help-languages`: List supported languages
- `--help-voices`: List available voices
- `--merge-chunks`: Merge existing chunks into chapter files

### Options

- `--stream`: Stream audio instead of saving to file
- `--speed <float>`: Set speech speed (default: 1.0, range: 0.5-2.0)
- `--lang <str>`: Set language (default: en-us)
- `--voice <str>`: Set voice or blend voices (default: interactive selection)
  - Single voice: Use voice name (e.g., "af_sarah")
  - Blended voices: Use "voice1:weight,voice2:weight" format
- `--split-output <dir>`: Save each chunk as separate file in directory
- `--chapters <dir>`: Save one audio file per chapter in directory (memory efficient for books)
- `--format <str>`: Audio format: wav, mp3, or m4a (default: wav)
- `--debug`: Show detailed debug information during processing
- `--model <path>`: Path to kokoro-v1.0.onnx model file (default: ./kokoro-v1.0.onnx)
- `--voices <path>`: Path to voices-v1.0.bin file (default: ./voices-v1.0.bin)

### Input Formats

- `.txt`: Text file input
- `.epub`: EPUB book input (will process chapters)
- `.pdf`: PDF document input (extracts chapters from TOC or content)
- `-` or `/dev/stdin` (Linux/macOS) or `CONIN$` (Windows): Standard input (stdin)

### Examples

#### Basic Text-to-Speech

```bash
# Simple text file to audio
kokoro-tts input.txt output.wav

# With specific voice and speed
kokoro-tts input.txt output.wav --speed 1.2 --lang en-us --voice af_sarah

# Stream audio directly (no file saved)
kokoro-tts input.txt --stream --speed 0.8

# Using different output formats
kokoro-tts input.txt output.mp3 --format mp3
kokoro-tts input.txt output.m4a --format m4a
```

#### Standard Input (stdin)

```bash
# Read from stdin and stream
echo "Hello World" | kokoro-tts - --stream

# Pipe from file
cat input.txt | kokoro-tts - output.wav

# Cross-platform stdin support:
# Linux/macOS: echo "text" | kokoro-tts - --stream
# Windows: echo "text" | kokoro-tts - --stream
```

#### Voice Blending

```bash
# Use voice blending with specific weights (60-40 mix)
kokoro-tts input.txt output.wav --voice "af_sarah:60,am_adam:40"

# Use equal voice blend (50-50)
kokoro-tts input.txt --stream --voice "am_adam,af_sarah"

# Three-way blend is also supported
kokoro-tts input.txt output.wav --voice "af_sarah:50,am_adam:30,af_bella:20"
```

#### EPUB Book Processing

```bash
# Process EPUB book with chapters (memory efficient, recommended)
kokoro-tts input.epub --chapters ./audiobook/ --format m4a

# Process EPUB and split into small chunks
kokoro-tts input.epub --split-output ./chunks/ --format mp3

# Process EPUB with detailed debug output
kokoro-tts input.epub --chapters ./audiobook/ --debug --format m4a
```

#### PDF Document Processing

```bash
# Process PDF with chapter detection
kokoro-tts input.pdf --chapters ./chapters/ --format m4a

# Process PDF with specific voice and speed
kokoro-tts input.pdf output.m4a --speed 1.2 --lang en-us --voice af_sarah --format m4a

# Process PDF and split into chunks
kokoro-tts input.pdf --split-output ./chunks/ --format mp3
```

#### Custom Model Paths

```bash
# Use custom model and voices files
kokoro-tts input.txt output.wav --model /path/to/model.onnx --voices /path/to/voices.bin

# Use models from a specific directory
kokoro-tts input.txt output.wav --model ./models/kokoro-v1.0.onnx --voices ./models/voices-v1.0.bin
```

#### Utility Commands

```bash
# List all available voices
kokoro-tts --help-voices

# List all supported languages
kokoro-tts --help-languages

# Merge existing chunks into chapter files
kokoro-tts --merge-chunks --split-output ./chunks/ --format wav
```

> [!TIP]
> If you're using Method 3, replace `kokoro-tts` with `uv run kokoro-tts` in the examples above.
> If you're using Method 4, replace `kokoro-tts` with `uv run -m kokoro_tts` or `python -m kokoro_tts` in the examples above.

## Features in Detail

### EPUB Processing
- Automatically extracts chapters from EPUB files
- Preserves chapter titles and structure
- Creates organized output for each chapter
- Detailed debug output available for troubleshooting

### Audio Processing
- Chunks long text into manageable segments
- Supports streaming for immediate playback
- Voice blending with customizable mix ratios
- Progress indicators for long processes
- Handles interruptions gracefully

### Output Options
- Single file output (entire book/document in one file)
- `--chapters` mode: One file per chapter (memory efficient, recommended for books)
- `--split-output` mode: Many small chunk files with chapter organization
- Chunk merging capability with `--merge-chunks`
- Multiple audio format support: WAV, MP3, M4A

### Debug Mode
- Shows detailed information about file processing
- Displays NCX parsing details for EPUB files
- Lists all found chapters and their metadata
- Helps troubleshoot processing issues

### Input Options
- Text file input (.txt)
- EPUB book input (.epub)
- Standard input (stdin)
- Supports piping from other programs

## Contributing

This is a personal project. But if you want to contribute, please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Kokoro-ONNX](https://github.com/thewh1teagle/kokoro-onnx)
