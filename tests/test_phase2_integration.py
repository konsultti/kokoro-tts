#!/usr/bin/env python3
"""Integration tests for Phase 2 performance optimizations.

Tests that async I/O and memory streaming work together correctly
and integrate with Phase 1 parallel processing.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import asyncio
import tempfile
import shutil

from kokoro_tts.config import PerformanceConfig
from kokoro_tts.core import KokoroEngine, ProcessingOptions, AudioFormat


class TestPhase2Integration(unittest.TestCase):
    """Test Phase 2 integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_async_io_with_parallel(self):
        """Test async I/O works with parallel processing."""
        config = PerformanceConfig(
            use_parallel=True,
            max_workers=4,
            use_async_io=True
        )

        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Verify configuration
        self.assertTrue(config.use_parallel)
        self.assertTrue(config.use_async_io)
        self.assertEqual(engine.performance_config.use_parallel, True)
        self.assertEqual(engine.performance_config.use_async_io, True)

    def test_streaming_with_async_io(self):
        """Test streaming works with async I/O."""
        config = PerformanceConfig(
            use_memory_streaming=True,
            use_async_io=True,
            io_queue_size=5
        )

        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Verify configuration
        self.assertTrue(config.use_memory_streaming)
        self.assertTrue(config.use_async_io)
        self.assertEqual(engine.performance_config.use_memory_streaming, True)
        self.assertEqual(engine.performance_config.use_async_io, True)

    def test_all_features_enabled(self):
        """Test all features work together."""
        config = PerformanceConfig(
            use_parallel=True,
            max_workers=4,
            use_async_io=True,
            io_queue_size=10,
            use_memory_streaming=True
        )

        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Verify all settings
        self.assertTrue(engine.performance_config.use_parallel)
        self.assertTrue(engine.performance_config.use_async_io)
        self.assertTrue(engine.performance_config.use_memory_streaming)
        self.assertEqual(engine.performance_config.max_workers, 4)
        self.assertEqual(engine.performance_config.io_queue_size, 10)

    def test_feature_combinations(self):
        """Test all valid feature combinations."""
        test_configs = [
            {},  # Baseline
            {'use_parallel': True},  # Phase 1
            {'use_parallel': True, 'use_async_io': True},  # Phase 1 + async
            {'use_parallel': True, 'use_memory_streaming': True},  # Phase 1 + streaming
            {'use_async_io': True, 'use_memory_streaming': True},  # Phase 2 only
            {'use_parallel': True, 'use_async_io': True, 'use_memory_streaming': True},  # Full
        ]

        for config_dict in test_configs:
            with self.subTest(config=config_dict):
                config = PerformanceConfig(**config_dict)

                try:
                    engine = KokoroEngine(
                        model_path="kokoro-v1.0.onnx",
                        voices_path="voices-v1.0.bin",
                        performance_config=config
                    )
                except FileNotFoundError:
                    self.skipTest("Model files not available")

                # Engine should initialize without errors
                self.assertIsNotNone(engine)
                self.assertEqual(engine.performance_config.use_parallel,
                               config_dict.get('use_parallel', False))
                self.assertEqual(engine.performance_config.use_async_io,
                               config_dict.get('use_async_io', False))
                self.assertEqual(engine.performance_config.use_memory_streaming,
                               config_dict.get('use_memory_streaming', False))

    def test_backward_compatibility(self):
        """Test backward compatibility with Phase 1."""
        # Phase 1 config should still work
        config = PerformanceConfig(use_parallel=True, max_workers=2)

        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Phase 2 features should be disabled by default
        self.assertTrue(engine.performance_config.use_parallel)
        self.assertFalse(engine.performance_config.use_async_io)
        self.assertFalse(engine.performance_config.use_memory_streaming)

    def test_default_config_unchanged(self):
        """Test default configuration hasn't changed."""
        config = PerformanceConfig()

        # All features should be disabled by default
        self.assertFalse(config.use_parallel)
        self.assertFalse(config.use_async_io)
        self.assertFalse(config.use_memory_streaming)
        self.assertFalse(config.use_gpu_batching)

    def test_environment_variable_loading(self):
        """Test loading all features from environment."""
        os.environ['KOKORO_USE_PARALLEL'] = 'true'
        os.environ['KOKORO_MAX_WORKERS'] = '8'
        os.environ['KOKORO_ASYNC_IO'] = 'true'
        os.environ['KOKORO_IO_QUEUE_SIZE'] = '12'
        os.environ['KOKORO_MEMORY_STREAMING'] = 'true'

        try:
            config = PerformanceConfig.from_env()

            self.assertTrue(config.use_parallel)
            self.assertEqual(config.max_workers, 8)
            self.assertTrue(config.use_async_io)
            self.assertEqual(config.io_queue_size, 12)
            self.assertTrue(config.use_memory_streaming)
        finally:
            # Cleanup
            for key in ['KOKORO_USE_PARALLEL', 'KOKORO_MAX_WORKERS',
                       'KOKORO_ASYNC_IO', 'KOKORO_IO_QUEUE_SIZE',
                       'KOKORO_MEMORY_STREAMING']:
                if key in os.environ:
                    del os.environ[key]

    def test_process_file_streaming_async_structure(self):
        """Test process_file_streaming_async method exists and has correct structure."""
        config = PerformanceConfig(use_memory_streaming=True, use_async_io=True)

        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Verify method exists
        self.assertTrue(hasattr(engine, 'process_file_streaming_async'))
        self.assertTrue(callable(getattr(engine, 'process_file_streaming_async')))

    def test_io_executor_cleanup(self):
        """Test I/O executor is properly cleaned up."""
        config = PerformanceConfig(use_async_io=True)

        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Create executor
        executor = engine._get_io_executor()
        self.assertIsNotNone(executor)

        # Cleanup
        engine._cleanup_io_executor()
        self.assertIsNone(engine._io_executor)

        # Verify tasks list is also cleared
        self.assertEqual(len(engine._io_tasks), 0)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
