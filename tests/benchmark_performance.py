#!/usr/bin/env python3
"""Benchmark script to compare performance optimizations.

This script tests performance improvements from:
- Phase 1: Parallel chunk processing
- Phase 2: Async I/O and memory streaming
"""

import time
import sys
import os

# Add parent directory to path to import kokoro_tts
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kokoro_tts.core import KokoroEngine, ProcessingOptions, AudioFormat
from kokoro_tts.config import PerformanceConfig


def benchmark_sequential_vs_parallel():
    """Compare sequential vs parallel processing performance."""

    # Test text (long enough to benefit from parallelization)
    # This creates approximately 10-15 chunks for meaningful comparison
    test_text = """
    This is a comprehensive test of the Kokoro text-to-speech system's parallel processing capabilities.
    The test is designed to generate multiple chunks that can be processed simultaneously.
    By processing chunks in parallel, we can leverage multiple CPU cores to significantly reduce
    the total time required for audio generation. This is particularly beneficial for longer texts
    such as articles, stories, or entire books. The speedup achieved depends on several factors
    including the number of available CPU cores, the complexity of the text, and the overhead
    of managing parallel execution. In practice, users can expect speedups ranging from 3x to 8x
    on modern multi-core processors. This makes the parallel processing feature especially valuable
    for batch processing of large documents or when quick turnaround is essential. The implementation
    uses Python's concurrent.futures module to manage thread pools and handle parallel execution safely.
    """ * 10  # Repeat to create more chunks

    print("=" * 70)
    print("Kokoro TTS - Parallel Processing Benchmark")
    print("=" * 70)
    print(f"\nTest text length: {len(test_text)} characters")
    print(f"Expected chunks: ~{len(test_text) // 1000}")

    # Check if model files exist
    model_path = "kokoro-v1.0.onnx"
    voices_path = "voices-v1.0.bin"

    if not os.path.exists(model_path):
        print(f"\nError: Model file not found: {model_path}")
        print("Please download the model file first.")
        sys.exit(1)

    if not os.path.exists(voices_path):
        print(f"\nError: Voices file not found: {voices_path}")
        print("Please download the voices file first.")
        sys.exit(1)

    options = ProcessingOptions(
        voice="af_sarah",
        speed=1.0,
        lang="en-us",
        format=AudioFormat.WAV,
        debug=False
    )

    # Test 1: Sequential processing
    print("\n" + "-" * 70)
    print("Test 1: Sequential Processing (baseline)")
    print("-" * 70)

    config_seq = PerformanceConfig(use_parallel=False)
    engine_seq = KokoroEngine(
        model_path=model_path,
        voices_path=voices_path,
        performance_config=config_seq
    )

    try:
        print("Loading model...")
        engine_seq.load_model()
        print("Model loaded successfully")

        print("\nGenerating audio sequentially...")
        start = time.time()
        samples_seq, sr = engine_seq.generate_audio(test_text, options)
        time_seq = time.time() - start

        if samples_seq is None:
            print("Error: Sequential processing failed")
            sys.exit(1)

        print(f"Sequential processing time: {time_seq:.2f} seconds")
        print(f"Audio samples generated: {len(samples_seq):,}")
        print(f"Audio duration: {len(samples_seq) / sr:.2f} seconds")

    except Exception as e:
        print(f"Error during sequential processing: {e}")
        sys.exit(1)

    # Test 2: Parallel processing
    print("\n" + "-" * 70)
    print("Test 2: Parallel Processing")
    print("-" * 70)

    import multiprocessing
    cpu_count = multiprocessing.cpu_count()
    print(f"Available CPU cores: {cpu_count}")

    # Test with different worker counts
    worker_counts = [2, 4, cpu_count]
    if cpu_count > 4:
        worker_counts.append(cpu_count)

    results = []

    for workers in sorted(set(worker_counts)):
        if workers > cpu_count:
            continue

        print(f"\n  Testing with {workers} workers:")
        config_par = PerformanceConfig(use_parallel=True, max_workers=workers)
        engine_par = KokoroEngine(
            model_path=model_path,
            voices_path=voices_path,
            performance_config=config_par
        )

        try:
            engine_par.load_model()

            start = time.time()
            samples_par, sr_par = engine_par.generate_audio(test_text, options)
            time_par = time.time() - start

            if samples_par is None:
                print(f"    Error: Parallel processing failed with {workers} workers")
                continue

            speedup = time_seq / time_par
            print(f"    Processing time: {time_par:.2f} seconds")
            print(f"    Speedup: {speedup:.2f}x")
            print(f"    Efficiency: {(speedup / workers) * 100:.1f}%")

            results.append((workers, time_par, speedup))

            # Verify output length matches sequential
            if len(samples_par) != len(samples_seq):
                print(f"    WARNING: Output length differs from sequential!")
                print(f"    Sequential: {len(samples_seq):,} samples")
                print(f"    Parallel: {len(samples_par):,} samples")

        except Exception as e:
            print(f"    Error with {workers} workers: {e}")
            continue

    # Summary
    print("\n" + "=" * 70)
    print("Benchmark Summary")
    print("=" * 70)
    print(f"\nSequential baseline: {time_seq:.2f} seconds")

    if results:
        print("\nParallel results:")
        print(f"  {'Workers':<10} {'Time (s)':<12} {'Speedup':<12} {'Efficiency':<12}")
        print("  " + "-" * 46)

        for workers, time_par, speedup in results:
            efficiency = (speedup / workers) * 100
            print(f"  {workers:<10} {time_par:<12.2f} {speedup:<12.2f}x {efficiency:<12.1f}%")

        best_result = max(results, key=lambda x: x[2])
        print(f"\nBest configuration: {best_result[0]} workers")
        print(f"Best speedup: {best_result[2]:.2f}x ({best_result[1]:.2f} seconds)")

        print("\n" + "=" * 70)
        print("Verification: Output comparison")
        print("=" * 70)
        print(f"Sequential samples: {len(samples_seq):,}")
        print(f"Parallel samples: {len(samples_par):,}")

        if len(samples_seq) == len(samples_par):
            print("Output lengths match: PASS")
        else:
            print("Output lengths differ: FAIL")
            print(f"Difference: {abs(len(samples_seq) - len(samples_par)):,} samples")
    else:
        print("\nNo parallel results available")

    print("\n" + "=" * 70)
    print("Benchmark complete!")
    print("=" * 70)


def benchmark_phase2_features():
    """Benchmark Phase 2 async I/O and memory streaming features."""
    import asyncio
    import tempfile
    import shutil

    print("\n" + "=" * 70)
    print("Phase 2: Async I/O and Memory Streaming Benchmark")
    print("=" * 70)

    # Create test text file
    test_dir = tempfile.mkdtemp()
    test_file = os.path.join(test_dir, "test_input.txt")

    # Generate test content (multiple chapters worth)
    test_content = "This is a test sentence for benchmarking. " * 500  # ~20KB
    with open(test_file, 'w') as f:
        f.write(test_content)

    print(f"\nTest file size: {len(test_content)} characters")

    model_path = "kokoro-v1.0.onnx"
    voices_path = "voices-v1.0.bin"

    if not os.path.exists(model_path) or not os.path.exists(voices_path):
        print("Model files not found. Skipping Phase 2 benchmark.")
        shutil.rmtree(test_dir)
        return

    options = ProcessingOptions(
        voice="af_sarah",
        speed=1.0,
        lang="en-us",
        format=AudioFormat.WAV,
        debug=False
    )

    results = {}

    # Test 1: Baseline (no optimizations)
    print("\n" + "-" * 70)
    print("Test 1: Baseline (Phase 1 disabled, no async I/O)")
    print("-" * 70)

    config_baseline = PerformanceConfig(
        use_parallel=False,
        use_async_io=False,
        use_memory_streaming=False
    )

    try:
        engine = KokoroEngine(
            model_path=model_path,
            voices_path=voices_path,
            performance_config=config_baseline
        )
        engine.load_model()

        async def run_baseline():
            output_dir = os.path.join(test_dir, "baseline")
            os.makedirs(output_dir, exist_ok=True)
            start = time.time()
            await engine.process_file_streaming_async(test_file, output_dir, options)
            return time.time() - start

        time_baseline = asyncio.run(run_baseline())
        results['baseline'] = time_baseline
        print(f"Baseline time: {time_baseline:.2f} seconds")

    except Exception as e:
        print(f"Error in baseline test: {e}")
        shutil.rmtree(test_dir)
        return

    # Test 2: Parallel only (Phase 1)
    print("\n" + "-" * 70)
    print("Test 2: Parallel Processing (Phase 1)")
    print("-" * 70)

    config_phase1 = PerformanceConfig(
        use_parallel=True,
        max_workers=4,
        use_async_io=False,
        use_memory_streaming=False
    )

    try:
        engine = KokoroEngine(
            model_path=model_path,
            voices_path=voices_path,
            performance_config=config_phase1
        )
        engine.load_model()

        async def run_phase1():
            output_dir = os.path.join(test_dir, "phase1")
            os.makedirs(output_dir, exist_ok=True)
            start = time.time()
            await engine.process_file_streaming_async(test_file, output_dir, options)
            return time.time() - start

        time_phase1 = asyncio.run(run_phase1())
        results['phase1'] = time_phase1
        speedup = results['baseline'] / time_phase1
        print(f"Phase 1 time: {time_phase1:.2f} seconds")
        print(f"Speedup vs baseline: {speedup:.2f}x")

    except Exception as e:
        print(f"Error in Phase 1 test: {e}")

    # Test 3: Parallel + Async I/O
    print("\n" + "-" * 70)
    print("Test 3: Parallel + Async I/O")
    print("-" * 70)

    config_async = PerformanceConfig(
        use_parallel=True,
        max_workers=4,
        use_async_io=True,
        io_queue_size=10,
        use_memory_streaming=False
    )

    try:
        engine = KokoroEngine(
            model_path=model_path,
            voices_path=voices_path,
            performance_config=config_async
        )
        engine.load_model()

        async def run_async():
            output_dir = os.path.join(test_dir, "async_io")
            os.makedirs(output_dir, exist_ok=True)
            start = time.time()
            await engine.process_file_streaming_async(test_file, output_dir, options)
            return time.time() - start

        time_async = asyncio.run(run_async())
        results['async_io'] = time_async
        speedup = results['baseline'] / time_async
        print(f"Async I/O time: {time_async:.2f} seconds")
        print(f"Speedup vs baseline: {speedup:.2f}x")

    except Exception as e:
        print(f"Error in async I/O test: {e}")

    # Test 4: Parallel + Memory Streaming
    print("\n" + "-" * 70)
    print("Test 4: Parallel + Memory Streaming")
    print("-" * 70)

    config_streaming = PerformanceConfig(
        use_parallel=True,
        max_workers=4,
        use_async_io=False,
        use_memory_streaming=True
    )

    try:
        engine = KokoroEngine(
            model_path=model_path,
            voices_path=voices_path,
            performance_config=config_streaming
        )
        engine.load_model()

        async def run_streaming():
            output_dir = os.path.join(test_dir, "streaming")
            os.makedirs(output_dir, exist_ok=True)
            start = time.time()
            await engine.process_file_streaming_async(test_file, output_dir, options)
            return time.time() - start

        time_streaming = asyncio.run(run_streaming())
        results['streaming'] = time_streaming
        speedup = results['baseline'] / time_streaming
        print(f"Streaming time: {time_streaming:.2f} seconds")
        print(f"Speedup vs baseline: {speedup:.2f}x")

    except Exception as e:
        print(f"Error in streaming test: {e}")

    # Test 5: Full Phase 2 (Parallel + Async I/O + Streaming)
    print("\n" + "-" * 70)
    print("Test 5: Full Phase 2 (All Optimizations)")
    print("-" * 70)

    config_full = PerformanceConfig(
        use_parallel=True,
        max_workers=4,
        use_async_io=True,
        io_queue_size=10,
        use_memory_streaming=True
    )

    try:
        engine = KokoroEngine(
            model_path=model_path,
            voices_path=voices_path,
            performance_config=config_full
        )
        engine.load_model()

        async def run_full():
            output_dir = os.path.join(test_dir, "full_phase2")
            os.makedirs(output_dir, exist_ok=True)
            start = time.time()
            await engine.process_file_streaming_async(test_file, output_dir, options)
            return time.time() - start

        time_full = asyncio.run(run_full())
        results['full_phase2'] = time_full
        speedup = results['baseline'] / time_full
        print(f"Full Phase 2 time: {time_full:.2f} seconds")
        print(f"Speedup vs baseline: {speedup:.2f}x")

    except Exception as e:
        print(f"Error in full Phase 2 test: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("Phase 2 Benchmark Summary")
    print("=" * 70)

    if results:
        print(f"\n{'Configuration':<25} {'Time (s)':<12} {'Speedup':<12}")
        print("-" * 49)

        for config_name, config_time in results.items():
            speedup = results['baseline'] / config_time if config_name != 'baseline' else 1.0
            print(f"{config_name:<25} {config_time:<12.2f} {speedup:<12.2f}x")

        best_config = min((k, v) for k, v in results.items() if k != 'baseline')
        best_speedup = results['baseline'] / best_config[1]
        print(f"\nBest configuration: {best_config[0]}")
        print(f"Best speedup: {best_speedup:.2f}x")

    # Cleanup
    shutil.rmtree(test_dir)

    print("\n" + "=" * 70)
    print("Phase 2 Benchmark Complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        # Allow user to choose which benchmark to run
        if len(sys.argv) > 1 and sys.argv[1] == "--phase2":
            benchmark_phase2_features()
        elif len(sys.argv) > 1 and sys.argv[1] == "--all":
            benchmark_sequential_vs_parallel()
            print("\n")
            benchmark_phase2_features()
        else:
            # Default: Phase 1 benchmark
            print("Run with --phase2 for Phase 2 benchmark, --all for both")
            print("Running Phase 1 benchmark...\n")
            benchmark_sequential_vs_parallel()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
