"""
Unit tests for front matter detection
"""
import sys
sys.path.insert(0, '.')

from kokoro_tts import is_front_matter

def test_skip_copyright():
    """Should skip copyright pages"""
    assert is_front_matter("Copyright", order=1) == True
    assert is_front_matter("Copyright © 2024", order=1) == True
    assert is_front_matter("Legal Notice", order=1) == True

def test_skip_toc():
    """Should skip table of contents"""
    assert is_front_matter("Table of Contents", order=1) == True
    assert is_front_matter("Contents", order=1) == True
    assert is_front_matter("TOC", order=1) == True

def test_skip_acknowledgments():
    """Should skip acknowledgments and dedication"""
    assert is_front_matter("Acknowledgments", order=2) == True
    assert is_front_matter("Dedication", order=2) == True
    assert is_front_matter("About the Author", order=20) == True

def test_keep_story_content():
    """Should KEEP foreword, preface, introduction, prologue"""
    assert is_front_matter("Foreword", order=1) == False
    assert is_front_matter("Preface", order=2) == False
    assert is_front_matter("Introduction", order=3) == False
    assert is_front_matter("Prologue", order=4) == False

def test_short_early_chapters():
    """Should skip very short early chapters with skip-worthy content"""
    assert is_front_matter("Copy", order=1, word_count=100) == True
    assert is_front_matter("Edition Info", order=2, word_count=200) == True
    # But not if it's substantial
    assert is_front_matter("Copy", order=1, word_count=1000) == False

def test_regular_chapters():
    """Should not skip regular chapters"""
    assert is_front_matter("Chapter 1", order=5) == False
    assert is_front_matter("The Beginning", order=10) == False
    assert is_front_matter("Part One", order=1) == False

if __name__ == "__main__":
    # Run tests manually
    print("Testing front matter detection...")
    test_skip_copyright()
    print("✓ Copyright detection works")
    test_skip_toc()
    print("✓ TOC detection works")
    test_skip_acknowledgments()
    print("✓ Acknowledgments detection works")
    test_keep_story_content()
    print("✓ Story content preservation works")
    test_short_early_chapters()
    print("✓ Short chapter heuristics work")
    test_regular_chapters()
    print("✓ Regular chapters not skipped")
    print("\n✅ All front matter tests passed!")
