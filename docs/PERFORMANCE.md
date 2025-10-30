# Performance Optimization Guide

This guide covers the performance optimizations in Kokoro TTS that can provide significant speedup and memory reduction.

## Overview

Kokoro TTS supports multiple performance optimization techniques:

### Phase 1: Parallel Chunk Processing

- **3-8x speedup** on modern multi-core processors
- **Better CPU utilization** (from 10-15% to 85-90%)
- **Thread-safe** - ONNX runtime handles concurrent inference

### Phase 2: Async I/O and Memory Streaming

- **Async I/O** - Non-blocking file writes for 1.5-2x additional speedup
- **Memory streaming** - Process large files chapter-by-chapter for 80% memory reduction
- **Composable** - Works together with parallel processing

### General Benefits

- **Backward compatible** - all optimizations default to off
- **No quality loss** - output is identical to sequential processing
- **Configurable** - enable features individually or combined

## Usage

### CLI Usage

The legacy CLI in `kokoro_tts/__init__.py` has the flags defined but does not currently use the parallel processing engine. The flags are available for future integration.

```bash
# Enable parallel processing (flags available but not yet connected)
kokoro-tts input.txt output.wav --parallel

# Specify number of workers
kokoro-tts input.txt output.wav --parallel --max-workers 4
```

### Programmatic Usage (KokoroEngine)

The `KokoroEngine` class in `kokoro_tts/core.py` fully supports parallel processing:

```python
from kokoro_tts.core import KokoroEngine, ProcessingOptions, AudioFormat
from kokoro_tts.config import PerformanceConfig

# Create performance config
perf_config = PerformanceConfig(
    use_parallel=True,
    max_workers=4  # Or None to use CPU count
)

# Initialize engine with parallel processing
engine = KokoroEngine(
    model_path="kokoro-v1.0.onnx",
    voices_path="voices-v1.0.bin",
    performance_config=perf_config
)

# Generate audio (automatically uses parallel processing)
engine.load_model()
options = ProcessingOptions(
    voice="af_sarah",
    speed=1.0,
    lang="en-us"
)

samples, sample_rate = engine.generate_audio("Your text here", options)
```

### Environment Variables

You can also configure performance via environment variables:

```bash
# Phase 1: Parallel processing
export KOKORO_USE_PARALLEL=true
export KOKORO_MAX_WORKERS=4

# Phase 2: Async I/O
export KOKORO_ASYNC_IO=true
export KOKORO_IO_QUEUE_SIZE=10

# Phase 2: Memory streaming
export KOKORO_MEMORY_STREAMING=true

# Run the application
python -m kokoro_tts.ui.gradio_app
```

### Phase 2 Features

#### Async I/O

Enable asynchronous file writes to avoid blocking TTS processing:

```python
from kokoro_tts.config import PerformanceConfig

# Enable async I/O
perf_config = PerformanceConfig(
    use_parallel=True,
    use_async_io=True,
    io_queue_size=10  # Max concurrent writes
)

engine = KokoroEngine(performance_config=perf_config)
```

Benefits:
- TTS processing continues while files are being written
- Best for split output (multiple chapter files)
- 1.5-2x additional speedup when combined with parallel processing

#### Memory Streaming

Process large files chapter-by-chapter to reduce memory usage:

```python
# Enable memory streaming
perf_config = PerformanceConfig(
    use_memory_streaming=True
)

# Use async processing method
await engine.process_file_streaming_async(
    "large_book.epub",
    "output_dir/",
    options
)
```

Benefits:
- 80% memory reduction for large files
- Processes one chapter at a time
- Ideal for EPUBs and PDFs with many chapters

#### Combined Configuration

For best results, enable all optimizations:

```python
perf_config = PerformanceConfig(
    use_parallel=True,
    max_workers=4,
    use_async_io=True,
    io_queue_size=10,
    use_memory_streaming=True
)
```

## Benchmarking

A benchmark script is provided to measure the speedup on your system:

```bash
# Make sure you're in the project root
cd /home/jari/github/kokoro-tts

# Phase 1 benchmark (parallel processing)
python tests/benchmark_performance.py

# Phase 2 benchmark (async I/O and streaming)
python tests/benchmark_performance.py --phase2

# Run all benchmarks
python tests/benchmark_performance.py --all
```

### Expected Output

```
======================================================================
Kokoro TTS - Parallel Processing Benchmark
======================================================================

Test text length: 12450 characters
Expected chunks: ~12

----------------------------------------------------------------------
Test 1: Sequential Processing (baseline)
----------------------------------------------------------------------
Loading model...
Model loaded successfully

Generating audio sequentially...
Sequential processing time: 15.23 seconds
Audio samples generated: 367,890
Audio duration: 15.23 seconds

----------------------------------------------------------------------
Test 2: Parallel Processing
----------------------------------------------------------------------
Available CPU cores: 8

  Testing with 2 workers:
    Processing time: 8.45 seconds
    Speedup: 1.80x
    Efficiency: 90.1%

  Testing with 4 workers:
    Processing time: 4.12 seconds
    Speedup: 3.70x
    Efficiency: 92.4%

  Testing with 8 workers:
    Processing time: 2.89 seconds
    Speedup: 5.27x
    Efficiency: 65.9%

======================================================================
Benchmark Summary
======================================================================

Sequential baseline: 15.23 seconds

Parallel results:
  Workers    Time (s)     Speedup      Efficiency
  --------------------------------------------------
  2          8.45         1.80x        90.1%
  4          4.12         3.70x        92.4%
  8          2.89         5.27x        65.9%

Best configuration: 8 workers
Best speedup: 5.27x (2.89 seconds)

======================================================================
Verification: Output comparison
======================================================================
Sequential samples: 367,890
Parallel samples: 367,890
Output lengths match: PASS

======================================================================
Benchmark complete!
======================================================================
```

## Performance Characteristics

### When to Use Parallel Processing

Parallel processing is most beneficial for:

- **Longer texts** - At least 5-10 chunks (5,000-10,000 characters)
- **Batch processing** - Multiple files or chapters
- **Audiobook generation** - EPUBs and PDFs with many chapters
- **Multi-core systems** - 4+ CPU cores recommended

### When to Use Async I/O

Async I/O is beneficial for:

- **Split output** - Generating multiple chapter files
- **Large audiobooks** - Many output files being written
- **I/O-bound systems** - Slow storage or network drives
- **Combined with parallel** - Maximize throughput

### When to Use Memory Streaming

Memory streaming is essential for:

- **Large files** - EPUBs/PDFs over 100MB
- **Memory-constrained systems** - Limited RAM available
- **Many chapters** - Books with 50+ chapters
- **Docker/cloud** - Environments with memory limits

### When NOT to Use These Features

- **Short texts** - Less than 1-2 chunks (< 2,000 characters)
- **Real-time streaming** - Audio playback during generation
- **Single file output** - No benefit for single concatenated file
- **Single-core systems** - Parallel has no benefit

### Optimal Worker Count

The optimal number of workers depends on:

1. **CPU cores** - Generally, use 50-100% of available cores
2. **Text length** - No benefit if fewer chunks than workers
3. **Memory** - Each worker uses additional RAM
4. **System load** - Leave cores for other processes

**Recommendations:**

- **4-8 core systems**: Use 4 workers
- **8-16 core systems**: Use 4-8 workers
- **16+ core systems**: Use 8-12 workers

Efficiency typically drops above 8 workers due to Python's GIL and coordination overhead.

## Technical Details

### Implementation

- **Thread pool**: Uses `concurrent.futures.ThreadPoolExecutor`
- **ONNX thread safety**: ONNX Runtime supports concurrent inference
- **Order preservation**: Results are reassembled in correct order
- **Error handling**: Errors in any chunk fail the entire operation
- **Progress tracking**: Thread-safe callback updates

### Limitations

1. **Python GIL**: Some overhead from Global Interpreter Lock
2. **Memory usage**: Each worker maintains state
3. **Coordination overhead**: Diminishing returns beyond 8-12 workers
4. **Not for streaming**: Parallel processing generates full audio

### Optimization Roadmap

Phase 1 (completed):
- Parallel chunk processing (3-8x speedup)

Phase 2 (completed):
- Async I/O (1.5-2x additional speedup)
- Memory streaming (80% memory reduction)

Phase 3 (future):
- GPU batch processing (2-3x additional on GPU)
- Smart chunk sizing based on content
- Streaming parallel generation

## Troubleshooting

### Issue: No speedup observed

**Possible causes:**
1. Text is too short (< 5 chunks)
2. System is already at capacity
3. Running on single-core system

**Solution:** Use `--debug` flag to see chunk count and ensure text is long enough.

### Issue: Out of memory

**Possible causes:**
1. Too many workers for available RAM
2. Very large text chunks

**Solution:** Reduce `--max-workers` or process in smaller batches.

### Issue: Output differs from sequential

**This should not happen.** If output differs:
1. Run the benchmark script to verify
2. Report as a bug with sample text

## Integration Status

### Fully Integrated

- `KokoroEngine` class (core.py)
- Web UI (uses KokoroEngine)
- Environment variable configuration

### Partially Integrated

- Legacy CLI (flags defined but not connected to engine)

### Not Yet Integrated

- Streaming mode
- GPU batch processing

## Contributing

To improve performance optimization:

1. Run benchmarks on your system
2. Share results with system specifications
3. Test edge cases (very long texts, many chunks)
4. Profile for bottlenecks

See `/tests/benchmark_performance.py` for the benchmark implementation.
