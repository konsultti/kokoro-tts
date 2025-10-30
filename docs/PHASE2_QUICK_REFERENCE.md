# Phase 2 Quick Reference

Quick reference for using Phase 2 performance optimizations in Kokoro TTS.

## TL;DR - Copy & Paste Examples

### Maximum Performance (Parallel + Async I/O)

```python
from kokoro_tts.core import KokoroEngine, ProcessingOptions
from kokoro_tts.config import PerformanceConfig
import asyncio

config = PerformanceConfig(
    use_parallel=True,
    max_workers=4,
    use_async_io=True,
    io_queue_size=10
)

engine = KokoroEngine(performance_config=config)
engine.load_model()

async def process():
    await engine.process_file_async(
        "input.epub",
        "output/",
        ProcessingOptions(voice="af_sarah")
    )

asyncio.run(process())
```

### Minimum Memory (Streaming)

```python
config = PerformanceConfig(use_memory_streaming=True)

engine = KokoroEngine(performance_config=config)
engine.load_model()

async def process():
    await engine.process_file_async(
        "large_book.epub",
        "output_dir/",
        ProcessingOptions(voice="af_sarah")
    )

asyncio.run(process())
```

### Best of Both (All Optimizations)

```python
config = PerformanceConfig(
    use_parallel=True,
    max_workers=4,
    use_async_io=True,
    io_queue_size=10,
    use_memory_streaming=True
)

engine = KokoroEngine(performance_config=config)
engine.load_model()

async def process():
    await engine.process_file_async(
        "huge_book.epub",
        "output/",
        ProcessingOptions(voice="af_sarah", speed=1.2)
    )

asyncio.run(process())
```

## Environment Variables

```bash
# Phase 1: Parallel Processing
export KOKORO_USE_PARALLEL=true
export KOKORO_MAX_WORKERS=4

# Phase 2: Async I/O
export KOKORO_ASYNC_IO=true
export KOKORO_IO_QUEUE_SIZE=10

# Phase 2: Memory Streaming
export KOKORO_MEMORY_STREAMING=true

# Run with all optimizations
python -m kokoro_tts.ui.gradio_app
```

## Quick Decision Guide

### Should I use Async I/O?

**YES if:**
- Processing multiple output files (split chapters)
- Using parallel processing
- Have slow storage (HDD, network)

**NO if:**
- Single output file
- Very short text
- Already at max CPU

### Should I use Memory Streaming?

**YES if:**
- File is large (>100MB)
- Limited RAM (<4GB available)
- Docker/cloud with memory limits
- Book has many chapters (>50)

**NO if:**
- File is small (<10MB)
- Plenty of RAM (>8GB)
- Need single output file
- Short document (<10 chapters)

### Should I use Parallel Processing?

**YES if:**
- Multi-core CPU (4+ cores)
- Text has 5+ chunks
- Long documents
- Batch processing

**NO if:**
- Single core CPU
- Very short text
- Real-time streaming
- Memory constrained

## Configuration Presets

### Preset: Fast (Multi-core systems)

```python
config = PerformanceConfig(
    use_parallel=True,
    max_workers=4
)
```

**Best for:** Fast processing on multi-core systems

### Preset: Memory Efficient (Large files)

```python
config = PerformanceConfig(
    use_memory_streaming=True
)
```

**Best for:** Large files, limited RAM

### Preset: Balanced (Recommended)

```python
config = PerformanceConfig(
    use_parallel=True,
    max_workers=4,
    use_async_io=True
)
```

**Best for:** Most use cases, good balance

### Preset: Maximum (High-end systems)

```python
config = PerformanceConfig(
    use_parallel=True,
    max_workers=8,
    use_async_io=True,
    io_queue_size=20,
    use_memory_streaming=True
)
```

**Best for:** High-end systems, large audiobooks

### Preset: Conservative (Low resources)

```python
config = PerformanceConfig(
    use_parallel=False,
    use_memory_streaming=True
)
```

**Best for:** Limited resources, old hardware

## Benchmarking

```bash
# Test Phase 1 (parallel)
python tests/benchmark_performance.py

# Test Phase 2 (async + streaming)
python tests/benchmark_performance.py --phase2

# Test everything
python tests/benchmark_performance.py --all
```

## Common Issues

### Issue: No speedup with async I/O

**Cause:** Single output file (no benefit)

**Solution:** Use split output or disable async I/O

### Issue: Out of memory

**Cause:** Too many parallel workers or no streaming

**Solution:** Enable streaming and reduce workers:
```python
config = PerformanceConfig(
    use_parallel=True,
    max_workers=2,
    use_memory_streaming=True
)
```

### Issue: Slower with streaming

**Cause:** File too small for streaming overhead

**Solution:** Disable streaming for small files:
```python
config = PerformanceConfig(
    use_parallel=True,
    use_async_io=True,
    use_memory_streaming=False  # Disable for small files
)
```

## Testing

```bash
# Install test dependencies
pip install pytest

# Run Phase 2 tests
pytest tests/test_async_io.py tests/test_streaming.py -v

# Run all tests
pytest tests/ -v
```

## Performance Expectations

| Configuration | Speedup | Memory | Notes |
|--------------|---------|--------|-------|
| Baseline | 1.0x | 100% | No optimizations |
| Parallel (4 workers) | 3-4x | 100% | Phase 1 |
| Parallel + Async I/O | 4.5-8x | 100% | Phase 2 |
| Streaming only | 1.0x | 20% | Phase 2 |
| All optimizations | 4.5-8x | 20% | Full Phase 2 |

## API Reference

### PerformanceConfig

```python
@dataclass
class PerformanceConfig:
    use_parallel: bool = False           # Enable parallel processing
    max_workers: int = None              # Worker count (None = CPU count)
    use_async_io: bool = False           # Enable async file I/O
    io_queue_size: int = 10              # Max concurrent I/O ops
    use_memory_streaming: bool = False   # Enable memory streaming
```

### KokoroEngine Methods

```python
# Sync generation
samples, sr = engine.generate_audio(text, options)

# Async generation
samples, sr = await engine.generate_audio_async(text, options)

# File processing (auto-detects streaming)
success = await engine.process_file_async(input_path, output_path, options)

# Explicit streaming
success = await engine.process_file_streaming_async(input_path, output_dir, options)

# Async file save
await engine.save_audio_async(samples, sr, output_path, format)
```

### Environment Variables

```bash
KOKORO_USE_PARALLEL=true/false          # Enable parallel
KOKORO_MAX_WORKERS=4                    # Worker count
KOKORO_ASYNC_IO=true/false              # Enable async I/O
KOKORO_IO_QUEUE_SIZE=10                 # I/O queue size
KOKORO_MEMORY_STREAMING=true/false      # Enable streaming
```

## Examples by Use Case

### Audiobook from EPUB

```python
config = PerformanceConfig(
    use_parallel=True,
    use_async_io=True,
    use_memory_streaming=True
)

async def create_audiobook():
    engine = KokoroEngine(performance_config=config)
    engine.load_model()

    await engine.process_file_async(
        "book.epub",
        "audiobook_chapters/",
        ProcessingOptions(
            voice="af_sarah",
            speed=1.1,
            format=AudioFormat.MP3
        )
    )
```

### Batch Processing

```python
config = PerformanceConfig(
    use_parallel=True,
    max_workers=4,
    use_async_io=True
)

async def batch_process(files):
    engine = KokoroEngine(performance_config=config)
    engine.load_model()

    for file in files:
        await engine.process_file_async(
            file,
            f"output/{file}.wav",
            ProcessingOptions(voice="af_sarah")
        )
```

### Large PDF

```python
config = PerformanceConfig(
    use_memory_streaming=True,
    use_parallel=True,
    max_workers=2  # Lower workers due to streaming
)

async def process_pdf():
    engine = KokoroEngine(performance_config=config)
    engine.load_model()

    await engine.process_file_async(
        "large_document.pdf",
        "chapters/",
        ProcessingOptions(voice="af_sarah")
    )
```

## Documentation Links

- Full guide: `PERFORMANCE.md`
- Implementation details: `docs/PHASE2_IMPLEMENTATION.md`
- Summary: `PHASE2_SUMMARY.md`
- Tests: `tests/test_async_io.py`, `tests/test_streaming.py`

## Version

This reference is for:
- Phase 1: Parallel processing ✅ Complete
- Phase 2: Async I/O + Memory Streaming ✅ Complete
- Phase 3: GPU batching ⏳ Future
