"""
Unit tests for front matter detection

Run with: pytest tests/test_front_matter.py -v
"""
import pytest
from kokoro_tts import is_front_matter


class TestFrontMatterDetection:
    """Test suite for front matter detection logic"""

    def test_skip_copyright(self):
        """Should skip copyright pages"""
        assert is_front_matter("Copyright", order=1) is True
        assert is_front_matter("Copyright © 2024", order=1) is True
        assert is_front_matter("Legal Notice", order=1) is True

    def test_skip_toc(self):
        """Should skip table of contents"""
        assert is_front_matter("Table of Contents", order=1) is True
        assert is_front_matter("Contents", order=1) is True
        assert is_front_matter("TOC", order=1) is True

    def test_skip_acknowledgments(self):
        """Should skip acknowledgments and dedication"""
        assert is_front_matter("Acknowledgments", order=2) is True
        assert is_front_matter("Dedication", order=2) is True
        assert is_front_matter("About the Author", order=20) is True

    def test_keep_story_content(self):
        """Should KEEP foreword, preface, introduction, prologue"""
        assert is_front_matter("Foreword", order=1) is False
        assert is_front_matter("Preface", order=2) is False
        assert is_front_matter("Introduction", order=3) is False
        assert is_front_matter("Prologue", order=4) is False

    def test_short_early_chapters(self):
        """Should skip very short early chapters with skip-worthy content"""
        assert is_front_matter("Copy", order=1, word_count=100) is True
        assert is_front_matter("Edition Info", order=2, word_count=200) is True
        # But not if it's substantial
        assert is_front_matter("Copy", order=1, word_count=1000) is False

    def test_regular_chapters(self):
        """Should not skip regular chapters"""
        assert is_front_matter("Chapter 1", order=5) is False
        assert is_front_matter("The Beginning", order=10) is False
        assert is_front_matter("Part One", order=1) is False

    @pytest.mark.parametrize("title,expected", [
        ("Copyright", True),
        ("Table of Contents", True),
        ("Dedication", True),
        ("Acknowledgments", True),
        ("Foreword", False),
        ("Prologue", False),
        ("Chapter 1", False),
    ])
    def test_parametrized_titles(self, title, expected):
        """Parametrized test for various chapter titles"""
        assert is_front_matter(title, order=1) is expected


if __name__ == "__main__":
    # Allow running directly for backwards compatibility
    pytest.main([__file__, "-v"])
