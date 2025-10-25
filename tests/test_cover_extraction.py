"""
Unit tests for EPUB cover extraction

This test file validates the multi-strategy cover extraction logic
implemented to fix the issue where covers referenced from cover.html
were not being found.

Run with: pytest tests/test_cover_extraction.py -v
"""
import pytest
from ebooklib import epub
from kokoro_tts.audiobook import extract_epub_metadata


class TestCoverExtraction:
    """Test suite for EPUB cover extraction with multiple fallback strategies"""

    def test_direct_cover_type(self, temp_dir):
        """Strategy 1: Should extract cover when item type is ITEM_COVER"""
        book = epub.EpubBook()
        book.set_identifier('test-001')
        book.set_title('Test Book')

        # Create cover image with ITEM_COVER type
        cover = epub.EpubCover()
        cover.file_name = 'cover.jpg'
        # Minimal JPEG
        cover.content = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        book.add_item(cover)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'test_direct_cover.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))
        assert metadata['cover'] is not None
        assert len(metadata['cover']) > 0
        assert metadata['cover'][:3] == b'\xff\xd8\xff'  # JPEG magic bytes

    def test_cover_in_filename(self, temp_dir):
        """Strategy 1: Should extract cover when 'cover' is in filename"""
        book = epub.EpubBook()
        book.set_identifier('test-002')
        book.set_title('Test Book')

        # Create image with 'cover' in filename
        cover_img = epub.EpubImage()
        cover_img.file_name = 'images/cover.jpg'
        cover_img.content = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        book.add_item(cover_img)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'test_filename_cover.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))
        assert metadata['cover'] is not None
        assert metadata['cover'][:3] == b'\xff\xd8\xff'

    def test_cover_html_reference(self):
        """Strategy 2: Should extract cover referenced in cover.html (main fix)"""
        # Use the real test2.epub file if it exists, otherwise skip
        import os
        test_epub_path = './test2.epub'
        if not os.path.exists(test_epub_path):
            pytest.skip("test2.epub not found - this test validates the real-world fix")

        metadata = extract_epub_metadata(test_epub_path)

        # This is the key test - validates today's fix!
        assert metadata['cover'] is not None, "Cover should be found via cover.html reference"
        assert len(metadata['cover']) > 0
        # Should be JPEG
        assert metadata['cover'][:3] == b'\xff\xd8\xff'

    def test_png_cover(self, temp_dir):
        """Should handle PNG cover images"""
        book = epub.EpubBook()
        book.set_identifier('test-003')
        book.set_title('Test Book')

        cover_img = epub.EpubImage()
        cover_img.file_name = 'cover.png'
        # PNG magic bytes
        cover_img.content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        book.add_item(cover_img)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'test_png_cover.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))
        assert metadata['cover'] is not None
        assert metadata['cover'][:8] == b'\x89PNG\r\n\x1a\n'

    def test_webp_cover(self, temp_dir):
        """Should handle WEBP cover images"""
        book = epub.EpubBook()
        book.set_identifier('test-004')
        book.set_title('Test Book')

        cover_img = epub.EpubImage()
        cover_img.file_name = 'cover.webp'
        # WEBP magic bytes
        cover_img.content = b'RIFF\x00\x00\x00\x00WEBP'
        book.add_item(cover_img)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'test_webp_cover.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))
        assert metadata['cover'] is not None
        assert metadata['cover'][:4] == b'RIFF'
        assert metadata['cover'][8:12] == b'WEBP'

    def test_svg_cover_rejected(self, temp_dir):
        """Should reject SVG files (not real images)"""
        book = epub.EpubBook()
        book.set_identifier('test-005')
        book.set_title('Test Book')

        # Create SVG "cover"
        cover_svg = epub.EpubItem()
        cover_svg.file_name = 'cover.svg'
        cover_svg.content = b'<?xml version="1.0"?><svg>...</svg>'
        book.add_item(cover_svg)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'test_svg_cover.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))
        # SVG should be rejected, cover should be None
        assert metadata['cover'] is None

    def test_no_cover(self, simple_epub):
        """Should return None when no cover exists"""
        metadata = extract_epub_metadata(str(simple_epub))
        assert metadata['cover'] is None

    def test_cover_html_with_different_patterns(self, temp_dir):
        """Should handle various HTML image reference patterns"""
        # Test xlink:href pattern (most common)
        book = epub.EpubBook()
        book.set_identifier('test-pattern-001')
        book.set_title('Test Book')

        # Create cover image
        cover_img = epub.EpubImage()
        cover_img.file_name = 'images/book_cover.jpg'
        cover_img.content = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        book.add_item(cover_img)

        # Create cover.html with xlink:href pattern
        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.xhtml',
            lang='en'
        )
        cover_html.content = '''<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Cover</title></head>
<body><svg xmlns:xlink="http://www.w3.org/1999/xlink">
<image xlink:href="images/book_cover.jpg" /></svg></body></html>'''
        book.add_item(cover_html)

        c1 = epub.EpubHtml(title='Chapter 1', file_name='ch1.xhtml', lang='en')
        c1.content = '<html><body><p>Content</p></body></html>'
        book.add_item(c1)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [cover_html, c1]
        book.toc = (epub.Link('ch1.xhtml', 'Chapter 1', 'ch1'),)

        epub_path = temp_dir / 'test_pattern.epub'
        epub.write_epub(str(epub_path), book, {})

        metadata = extract_epub_metadata(str(epub_path))
        assert metadata['cover'] is not None, "xlink:href pattern should be recognized"

    def test_metadata_fields(self, simple_epub):
        """Should extract all metadata fields structure"""
        metadata = extract_epub_metadata(str(simple_epub))

        # Check structure
        assert 'title' in metadata
        assert 'author' in metadata
        assert 'cover' in metadata
        assert 'language' in metadata

        # Verify other fields exist (may be None)
        assert isinstance(metadata['title'], (str, type(None)))
        assert isinstance(metadata['author'], (str, type(None)))
        assert isinstance(metadata['cover'], (bytes, type(None)))

    @pytest.mark.parametrize("magic_bytes,expected_format", [
        (b'\xff\xd8\xff', 'JPEG'),
        (b'\x89PNG\r\n\x1a\n', 'PNG'),
        (b'RIFF\x00\x00\x00\x00WEBP', 'WEBP'),
    ])
    def test_image_format_detection(self, temp_dir, magic_bytes, expected_format):
        """Parametrized test for different image formats"""
        book = epub.EpubBook()
        book.set_identifier('test-format')
        book.set_title('Test Book')

        cover_img = epub.EpubImage()
        cover_img.file_name = f'cover.{expected_format.lower()}'
        cover_img.content = magic_bytes + b'\x00' * 20  # Pad with zeros
        book.add_item(cover_img)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / f'test_{expected_format}.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))
        assert metadata['cover'] is not None
        assert metadata['cover'][:len(magic_bytes)] == magic_bytes


class TestCoverExtractionRegression:
    """Regression tests to ensure cover extraction doesn't break existing functionality"""

    def test_backwards_compatibility_simple(self, simple_epub):
        """Should not break on simple EPUBs without covers"""
        metadata = extract_epub_metadata(str(simple_epub))
        assert isinstance(metadata, dict)
        assert 'cover' in metadata

    def test_backwards_compatibility_with_front_matter(self, epub_with_front_matter):
        """Should not interfere with front matter processing"""
        metadata = extract_epub_metadata(str(epub_with_front_matter))
        assert isinstance(metadata, dict)
        # Front matter EPUB doesn't have cover
        assert metadata['cover'] is None

    def test_empty_cover_file(self, temp_dir):
        """Should handle empty cover files gracefully"""
        book = epub.EpubBook()
        book.set_identifier('test-empty')
        book.set_title('Test Book')

        cover_img = epub.EpubImage()
        cover_img.file_name = 'cover.jpg'
        cover_img.content = b''  # Empty file
        book.add_item(cover_img)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'test_empty_cover.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))
        # Empty file should be rejected
        assert metadata['cover'] is None

    def test_malformed_cover_html(self, temp_dir):
        """Should handle malformed cover.html gracefully"""
        book = epub.EpubBook()
        book.set_identifier('test-malformed')
        book.set_title('Test Book')

        # Malformed HTML
        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = b'<html><invalid>Not proper HTML without images'
        book.add_item(cover_html)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'test_malformed.epub'
        epub.write_epub(str(epub_path), book)

        # Should not crash, should return None
        metadata = extract_epub_metadata(str(epub_path))
        assert metadata['cover'] is None


if __name__ == "__main__":
    # Allow running directly
    pytest.main([__file__, "-v"])
