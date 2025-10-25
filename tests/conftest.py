"""
Shared pytest fixtures and configuration for Kokoro TTS tests
"""
import sys
import os
import tempfile
from pathlib import Path

import pytest
from ebooklib import epub

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_metadata():
    """Sample metadata dictionary for testing"""
    return {
        'title': 'Test Novel',
        'author': 'Test Author',
        'language': 'en',
        'date': '2024',
        'description': 'A test book',
        'publisher': 'Test Publisher',
        'rights': 'Copyright 2024',
        'cover': None
    }


@pytest.fixture
def sample_metadata_with_cover():
    """Sample metadata with a JPEG cover image"""
    metadata = {
        'title': 'Test Novel',
        'author': 'Test Author',
        'cover': b'\xff\xd8\xff\xe0\x00\x10JFIF'  # JPEG magic bytes
    }
    return metadata


@pytest.fixture
def temp_dir():
    """Temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def simple_epub(temp_dir):
    """Create a simple EPUB file for testing"""
    book = epub.EpubBook()

    # Metadata
    book.set_identifier('test-simple-001')
    book.set_title('Simple Test Book')
    book.set_language('en')
    book.add_author('Test Author')

    # Single chapter
    c1 = epub.EpubHtml(
        title='Chapter 1',
        file_name='chapter1.xhtml',
        lang='en'
    )
    c1.content = '<html><body><h1>Chapter 1</h1><p>Test content.</p></body></html>'

    book.add_item(c1)
    book.toc = (epub.Link('chapter1.xhtml', 'Chapter 1', 'ch1'),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', c1]

    # Write to temp directory
    epub_path = temp_dir / 'simple_test.epub'
    epub.write_epub(str(epub_path), book)

    return epub_path


@pytest.fixture
def epub_with_cover_html(temp_dir):
    """Create an EPUB with cover.html referencing an image (like test2.epub)"""
    book = epub.EpubBook()

    # Metadata
    book.set_identifier('test-cover-001')
    book.set_title('Book With Cover')
    book.set_language('en')
    book.add_author('Test Author')

    # Create a minimal JPEG image (1x1 pixel)
    jpeg_data = bytes.fromhex(
        'ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707'
        '070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c'
        '1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d'
        '0d1832211c213232323232323232323232323232323232323232323232323232323232'
        '32323232323232323232323232323232323232323232ffc00011080001000103012200'
        '021101031101ffc4001500010100000000000000000000000000000000ffc400140100'
        '00000000000000000000000000000000ffda000c03010002110311003f00bf800000'
        'ffd9'
    )

    # Add cover image
    cover_img = epub.EpubImage()
    cover_img.file_name = 'imagedata/cover.jpg'
    cover_img.content = jpeg_data
    book.add_item(cover_img)

    # Create cover.html that references the image
    cover_html = epub.EpubHtml(
        title='Cover',
        file_name='cover.xhtml',  # Changed to .xhtml
        lang='en'
    )
    cover_html.content = '''<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Cover</title></head>
  <body>
    <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
         height="100%" width="100%">
      <image xlink:href="imagedata/cover.jpg" height="100%" width="100%"/>
    </svg>
  </body>
</html>'''

    book.add_item(cover_html)

    # Add a content chapter
    c1 = epub.EpubHtml(
        title='Chapter 1',
        file_name='chapter1.xhtml',
        lang='en'
    )
    c1.content = '<html><body><h1>Chapter 1</h1><p>Content here.</p></body></html>'
    book.add_item(c1)

    book.toc = (
        epub.Link('cover.xhtml', 'Cover', 'cover'),
        epub.Link('chapter1.xhtml', 'Chapter 1', 'ch1')
    )
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [cover_html, c1]  # Remove 'nav' from spine

    # Write to temp directory
    epub_path = temp_dir / 'cover_test.epub'
    epub.write_epub(str(epub_path), book, {})

    return epub_path


@pytest.fixture
def epub_with_front_matter(temp_dir):
    """Create an EPUB with various front matter chapters"""
    book = epub.EpubBook()

    # Metadata
    book.set_identifier('test-frontmatter-001')
    book.set_title('Book With Front Matter')
    book.set_language('en')
    book.add_author('Test Author')

    chapters = []

    # Copyright (should be skipped)
    c1 = epub.EpubHtml(title='Copyright', file_name='copyright.xhtml', lang='en')
    c1.content = '<html><body><h1>Copyright</h1><p>© 2024</p></body></html>'
    chapters.append(c1)

    # TOC (should be skipped)
    c2 = epub.EpubHtml(title='Table of Contents', file_name='toc.xhtml', lang='en')
    c2.content = '<html><body><h1>Contents</h1><p>Chapter 1... 1</p></body></html>'
    chapters.append(c2)

    # Dedication (should be skipped)
    c3 = epub.EpubHtml(title='Dedication', file_name='dedication.xhtml', lang='en')
    c3.content = '<html><body><h1>Dedication</h1><p>For my family</p></body></html>'
    chapters.append(c3)

    # Foreword (should be KEPT)
    c4 = epub.EpubHtml(title='Foreword', file_name='foreword.xhtml', lang='en')
    c4.content = '<html><body><h1>Foreword</h1><p>This important foreword sets up the story. It contains context about why this book was written.</p></body></html>'
    chapters.append(c4)

    # Prologue (should be KEPT)
    c5 = epub.EpubHtml(title='Prologue', file_name='prologue.xhtml', lang='en')
    c5.content = '<html><body><h1>Prologue</h1><p>The story begins here with important background.</p></body></html>'
    chapters.append(c5)

    # Chapter 1 (should be KEPT)
    c6 = epub.EpubHtml(title='Chapter 1', file_name='chapter1.xhtml', lang='en')
    c6.content = '<html><body><h1>Chapter 1</h1><p>The main story starts here.</p></body></html>'
    chapters.append(c6)

    # Add all chapters
    for chapter in chapters:
        book.add_item(chapter)

    book.toc = tuple(
        epub.Link(c.file_name, c.title, f'ch{i}')
        for i, c in enumerate(chapters)
    )

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + chapters

    # Write to temp directory
    epub_path = temp_dir / 'frontmatter_test.epub'
    epub.write_epub(str(epub_path), book)

    return epub_path
