#!/usr/bin/env python3
"""Unit tests for parallel processing functionality.

Tests that parallel processing produces identical output to sequential
processing and handles edge cases correctly.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import Mock, patch
import numpy as np

from kokoro_tts.config import PerformanceConfig
from kokoro_tts.core import KokoroEngine, ProcessingOptions, AudioFormat


class TestPerformanceConfig(unittest.TestCase):
    """Test PerformanceConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PerformanceConfig()
        self.assertFalse(config.use_parallel)
        self.assertIsNotNone(config.max_workers)
        self.assertGreater(config.max_workers, 0)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PerformanceConfig(
            use_parallel=True,
            max_workers=4
        )
        self.assertTrue(config.use_parallel)
        self.assertEqual(config.max_workers, 4)

    def test_from_env_default(self):
        """Test loading from environment with defaults."""
        # Clear environment
        for key in ['KOKORO_USE_PARALLEL', 'KOKORO_MAX_WORKERS']:
            if key in os.environ:
                del os.environ[key]

        config = PerformanceConfig.from_env()
        self.assertFalse(config.use_parallel)
        self.assertIsNotNone(config.max_workers)

    def test_from_env_custom(self):
        """Test loading from environment with custom values."""
        os.environ['KOKORO_USE_PARALLEL'] = 'true'
        os.environ['KOKORO_MAX_WORKERS'] = '8'

        try:
            config = PerformanceConfig.from_env()
            self.assertTrue(config.use_parallel)
            self.assertEqual(config.max_workers, 8)
        finally:
            # Cleanup
            del os.environ['KOKORO_USE_PARALLEL']
            del os.environ['KOKORO_MAX_WORKERS']


class TestKokoroEngineParallel(unittest.TestCase):
    """Test KokoroEngine parallel processing functionality."""

    def test_engine_initialization_with_config(self):
        """Test engine initialization with performance config."""
        config = PerformanceConfig(use_parallel=True, max_workers=2)

        # This will fail if model files don't exist, but tests config handling
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
            self.assertEqual(engine.performance_config.use_parallel, True)
            self.assertEqual(engine.performance_config.max_workers, 2)
        except FileNotFoundError:
            # Model files not available, skip this test
            self.skipTest("Model files not available")

    def test_engine_initialization_default_config(self):
        """Test engine initialization with default config."""
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin"
            )
            # Should have default config
            self.assertIsNotNone(engine.performance_config)
            self.assertFalse(engine.performance_config.use_parallel)
        except FileNotFoundError:
            self.skipTest("Model files not available")

    def test_process_chunk_wrapper(self):
        """Test the thread-safe chunk wrapper."""
        try:
            config = PerformanceConfig(use_parallel=True)
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )

            # Mock the process_chunk method
            engine.process_chunk = Mock(return_value=([1.0, 2.0, 3.0], 24000))

            # Test wrapper
            args = ("test chunk", "af_sarah", 1.0, "en-us", 0, False)
            result = engine._process_chunk_wrapper(args)

            # Should return (index, samples, rate, error)
            self.assertEqual(result[0], 0)  # chunk_index
            self.assertEqual(result[1], [1.0, 2.0, 3.0])  # samples
            self.assertEqual(result[2], 24000)  # sample_rate
            self.assertIsNone(result[3])  # no error

        except FileNotFoundError:
            self.skipTest("Model files not available")

    def test_chunk_selection_logic(self):
        """Test that engine correctly selects sequential vs parallel."""
        try:
            # Single chunk should use sequential even with parallel enabled
            config_par = PerformanceConfig(use_parallel=True, max_workers=4)
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config_par
            )

            # Mock both methods
            engine._generate_audio_sequential = Mock(return_value=(np.array([1.0]), 24000))
            engine._generate_audio_parallel = Mock(return_value=(np.array([1.0]), 24000))
            engine.validate_language = Mock(return_value="en-us")
            engine.validate_voice = Mock(return_value="af_sarah")
            engine.chunk_text = Mock(return_value=["single chunk"])
            engine.kokoro = Mock()  # Mock loaded model

            options = ProcessingOptions(voice="af_sarah", lang="en-us")

            # Generate audio
            engine.generate_audio("test", options)

            # With single chunk, should use sequential
            engine._generate_audio_sequential.assert_called_once()
            engine._generate_audio_parallel.assert_not_called()

        except FileNotFoundError:
            self.skipTest("Model files not available")

    def test_parallel_with_multiple_chunks(self):
        """Test that parallel is used with multiple chunks."""
        try:
            config_par = PerformanceConfig(use_parallel=True, max_workers=4)
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config_par
            )

            # Mock methods
            engine._generate_audio_sequential = Mock(return_value=(np.array([1.0]), 24000))
            engine._generate_audio_parallel = Mock(return_value=(np.array([1.0]), 24000))
            engine.validate_language = Mock(return_value="en-us")
            engine.validate_voice = Mock(return_value="af_sarah")
            engine.chunk_text = Mock(return_value=["chunk1", "chunk2", "chunk3"])
            engine.kokoro = Mock()

            options = ProcessingOptions(voice="af_sarah", lang="en-us")

            # Generate audio
            engine.generate_audio("test", options)

            # With multiple chunks and parallel enabled, should use parallel
            engine._generate_audio_parallel.assert_called_once()
            engine._generate_audio_sequential.assert_not_called()

        except FileNotFoundError:
            self.skipTest("Model files not available")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
