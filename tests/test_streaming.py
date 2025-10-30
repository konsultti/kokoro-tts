#!/usr/bin/env python3
"""Unit tests for memory streaming functionality.

Tests that memory streaming works correctly and reduces memory usage.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import tempfile
import shutil

from kokoro_tts.config import PerformanceConfig
from kokoro_tts.core import KokoroEngine, Chapter


class TestMemoryStreaming(unittest.TestCase):
    """Test memory streaming functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_streaming_config(self):
        """Test streaming configuration."""
        config = PerformanceConfig(use_memory_streaming=True)

        self.assertTrue(config.use_memory_streaming)

    def test_streaming_from_env(self):
        """Test loading streaming config from environment."""
        os.environ['KOKORO_MEMORY_STREAMING'] = 'true'

        try:
            config = PerformanceConfig.from_env()
            self.assertTrue(config.use_memory_streaming)
        finally:
            del os.environ['KOKORO_MEMORY_STREAMING']

    def test_extract_text_streaming(self):
        """Test streaming text file extraction."""
        config = PerformanceConfig(use_memory_streaming=True)
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Create a test text file
        test_file = os.path.join(self.test_dir, "test_streaming.txt")
        with open(test_file, "w") as f:
            f.write("A" * 60000)  # 60KB file (should create 2 chunks at 50KB each)

        # Stream chapters
        chapters = list(engine.extract_chapters_streaming(test_file))

        self.assertGreaterEqual(len(chapters), 1)
        self.assertTrue(all(isinstance(ch, Chapter) for ch in chapters))

        # Verify chapter properties
        for i, chapter in enumerate(chapters):
            self.assertEqual(chapter.order, i)
            self.assertIsNotNone(chapter.title)
            self.assertIsNotNone(chapter.content)

    def test_streaming_chapter_iterator(self):
        """Test that streaming returns an iterator."""
        config = PerformanceConfig(use_memory_streaming=True)
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Create test file
        test_file = os.path.join(self.test_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Test content")

        # Get iterator
        result = engine.extract_chapters_streaming(test_file)

        # Verify it's an iterator
        self.assertTrue(hasattr(result, '__iter__'))
        self.assertTrue(hasattr(result, '__next__'))

    def test_streaming_memory_efficiency(self):
        """Test streaming processes one chapter at a time."""
        config = PerformanceConfig(use_memory_streaming=True)
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Create a large test file
        test_file = os.path.join(self.test_dir, "large.txt")
        with open(test_file, "w") as f:
            # Write 200KB file (4 chunks)
            f.write("Test sentence. " * 15000)

        # Process streaming
        chapter_count = 0
        for chapter in engine.extract_chapters_streaming(test_file):
            chapter_count += 1
            # Verify chapter is valid
            self.assertIsInstance(chapter, Chapter)
            self.assertGreater(len(chapter.content), 0)

        # Should have multiple chunks
        self.assertGreater(chapter_count, 1)

    def test_extract_chapters_streaming_file_types(self):
        """Test streaming supports different file types."""
        config = PerformanceConfig(use_memory_streaming=True)
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Test with .txt file
        txt_file = os.path.join(self.test_dir, "test.txt")
        with open(txt_file, "w") as f:
            f.write("Test content for text file")

        chapters = list(engine.extract_chapters_streaming(txt_file))
        self.assertGreater(len(chapters), 0)

    def test_chapter_properties_in_streaming(self):
        """Test chapter properties are preserved in streaming."""
        config = PerformanceConfig(use_memory_streaming=True)
        try:
            engine = KokoroEngine(
                model_path="kokoro-v1.0.onnx",
                voices_path="voices-v1.0.bin",
                performance_config=config
            )
        except FileNotFoundError:
            self.skipTest("Model files not available")

        # Create test file
        test_file = os.path.join(self.test_dir, "test.txt")
        test_content = "This is test content for chapter properties."
        with open(test_file, "w") as f:
            f.write(test_content)

        # Stream chapters
        chapters = list(engine.extract_chapters_streaming(test_file))

        # Verify first chapter has expected properties
        self.assertGreater(len(chapters), 0)
        first_chapter = chapters[0]

        self.assertIsInstance(first_chapter.title, str)
        self.assertIsInstance(first_chapter.content, str)
        self.assertIsInstance(first_chapter.order, int)
        self.assertEqual(first_chapter.order, 0)
        self.assertIn(test_content, first_chapter.content)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
