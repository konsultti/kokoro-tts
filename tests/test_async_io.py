#!/usr/bin/env python3
"""Unit tests for async I/O functionality.

Tests that async I/O operations work correctly and improve performance.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import asyncio
import numpy as np
import tempfile
import shutil

from kokoro_tts.config import PerformanceConfig
from kokoro_tts.core import KokoroEngine, ProcessingOptions, AudioFormat


class TestAsyncIO(unittest.TestCase):
    """Test async I/O functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_async_io_config(self):
        """Test async I/O configuration."""
        config = PerformanceConfig(use_async_io=True, io_queue_size=5)

        self.assertTrue(config.use_async_io)
        self.assertEqual(config.io_queue_size, 5)

    def test_async_io_from_env(self):
        """Test loading async I/O config from environment."""
        os.environ['KOKORO_ASYNC_IO'] = 'true'
        os.environ['KOKORO_IO_QUEUE_SIZE'] = '8'

        try:
            config = PerformanceConfig.from_env()
            self.assertTrue(config.use_async_io)
            self.assertEqual(config.io_queue_size, 8)
        finally:
            del os.environ['KOKORO_ASYNC_IO']
            del os.environ['KOKORO_IO_QUEUE_SIZE']

    def test_save_audio_async(self):
        """Test async audio saving."""
        async def run_test():
            config = PerformanceConfig(use_async_io=True)
            try:
                engine = KokoroEngine(
                    model_path="kokoro-v1.0.onnx",
                    voices_path="voices-v1.0.bin",
                    performance_config=config
                )
            except FileNotFoundError:
                self.skipTest("Model files not available")

            # Create test audio samples
            samples = np.random.rand(24000).astype(np.float32)  # 1 second

            output_path = os.path.join(self.test_dir, "test_async.wav")

            # Save asynchronously
            await engine.save_audio_async(samples, 24000, output_path, AudioFormat.WAV)

            # Verify file exists
            self.assertTrue(os.path.exists(output_path))

            # Cleanup
            engine._cleanup_io_executor()

        asyncio.run(run_test())

    def test_async_io_multiple_writes(self):
        """Test multiple async writes maintain order."""
        async def run_test():
            config = PerformanceConfig(use_async_io=True, io_queue_size=5)
            try:
                engine = KokoroEngine(
                    model_path="kokoro-v1.0.onnx",
                    voices_path="voices-v1.0.bin",
                    performance_config=config
                )
            except FileNotFoundError:
                self.skipTest("Model files not available")

            # Create multiple write tasks
            tasks = []
            for i in range(10):
                samples = np.full(1000, i, dtype=np.float32)
                output_path = os.path.join(self.test_dir, f"chunk_{i:02d}.wav")
                task = engine.save_audio_async(samples, 24000, output_path, AudioFormat.WAV)
                tasks.append(task)

            # Wait for all writes
            await asyncio.gather(*tasks)

            # Verify all files exist
            for i in range(10):
                output_path = os.path.join(self.test_dir, f"chunk_{i:02d}.wav")
                self.assertTrue(os.path.exists(output_path))

            engine._cleanup_io_executor()

        asyncio.run(run_test())

    def test_get_io_executor(self):
        """Test I/O executor creation."""
        config = PerformanceConfig(use_async_io=True, io_queue_size=3)
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Get executor
        executor = engine._get_io_executor()
        self.assertIsNotNone(executor)

        # Second call should return same executor
        executor2 = engine._get_io_executor()
        self.assertIs(executor, executor2)

        # Cleanup
        engine._cleanup_io_executor()
        self.assertIsNone(engine._io_executor)

    def test_cleanup_io_executor(self):
        """Test I/O executor cleanup."""
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


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
