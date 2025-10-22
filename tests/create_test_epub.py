"""
Create a minimal test EPUB for manual testing
Requires: pip install ebooklib
"""
from ebooklib import epub

def create_test_epub():
    book = epub.EpubBook()

    # Metadata
    book.set_identifier('test123')
    book.set_title('Test Novel')
    book.set_language('en')
    book.add_author('Test Author')

    # Chapter 1: Copyright (should be skipped)
    c1 = epub.EpubHtml(title='Copyright',
                       file_name='copyright.xhtml',
                       lang='en')
    c1.content = '<html><body><h1>Copyright</h1><p>Copyright © 2024 Test Author. All rights reserved.</p></body></html>'

    # Chapter 2: Table of Contents (should be skipped)
    c2 = epub.EpubHtml(title='Table of Contents',
                       file_name='toc.xhtml',
                       lang='en')
    c2.content = '<html><body><h1>Contents</h1><p>Chapter 1... Page 1</p></body></html>'

    # Chapter 3: Dedication (should be skipped)
    c3 = epub.EpubHtml(title='Dedication',
                       file_name='dedication.xhtml',
                       lang='en')
    c3.content = '<html><body><h1>Dedication</h1><p>For my family.</p></body></html>'

    # Chapter 4: Foreword (should be KEPT)
    c4 = epub.EpubHtml(title='Foreword',
                       file_name='foreword.xhtml',
                       lang='en')
    c4.content = '<html><body><h1>Foreword</h1><p>This is an important foreword that sets up the story. It contains context about why this book was written and what readers should expect. This is part of the story experience and should not be skipped.</p></body></html>'

    # Chapter 5: Prologue (should be KEPT)
    c5 = epub.EpubHtml(title='Prologue',
                       file_name='prologue.xhtml',
                       lang='en')
    c5.content = '<html><body><h1>Prologue</h1><p>It was a dark and stormy night. The story begins here with important background that readers need to understand the main narrative.</p></body></html>'

    # Chapter 6: Chapter 1 (should be KEPT)
    c6 = epub.EpubHtml(title='Chapter 1: The Beginning',
                       file_name='chap_01.xhtml',
                       lang='en')
    c6.content = '<html><body><h1>Chapter 1</h1><p>The main story starts here. Our protagonist wakes up and discovers something amazing.</p></body></html>'

    # Add chapters to book
    book.add_item(c1)
    book.add_item(c2)
    book.add_item(c3)
    book.add_item(c4)
    book.add_item(c5)
    book.add_item(c6)

    # Define Table of Contents
    book.toc = (
        epub.Link('copyright.xhtml', 'Copyright', 'copyright'),
        epub.Link('toc.xhtml', 'Table of Contents', 'toc'),
        epub.Link('dedication.xhtml', 'Dedication', 'dedication'),
        epub.Link('foreword.xhtml', 'Foreword', 'foreword'),
        epub.Link('prologue.xhtml', 'Prologue', 'prologue'),
        epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01')
    )

    # Add navigation files
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define spine
    book.spine = ['nav', c1, c2, c3, c4, c5, c6]

    # Write EPUB file
    epub.write_epub('test_audiobook.epub', book)
    print("✓ Created test_audiobook.epub")
    print("\nExpected results when processing with --audiobook:")
    print("  SKIP: Copyright, Table of Contents, Dedication")
    print("  KEEP: Foreword, Prologue, Chapter 1")
    print("\nTest command:")
    print("  kokoro-tts test_audiobook.epub --audiobook test.m4a --debug")

if __name__ == "__main__":
    create_test_epub()
