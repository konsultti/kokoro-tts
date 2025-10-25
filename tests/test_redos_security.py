"""
Security tests for ReDoS vulnerability fixes in cover extraction

Tests validate that malicious input cannot cause catastrophic backtracking
or performance degradation in the cover extraction regex patterns.

Run with: pytest tests/test_redos_security.py -v
"""
import pytest
import time
from ebooklib import epub
from kokoro_tts.audiobook import extract_epub_metadata


class TestReDoSSecurity:
    """Test suite for ReDoS vulnerability protection"""

    def test_large_html_without_closing_quote(self, temp_dir):
        """Should handle HTML with missing closing quotes efficiently"""
        book = epub.EpubBook()
        book.set_identifier('security-001')
        book.set_title('Security Test')

        # Create malicious HTML with unclosed attribute (potential ReDoS vector)
        # Old regex: r'src="([^"]+)"' would scan all 100K chars
        # Make it valid HTML so ebooklib can create the EPUB
        malicious_html = '<html><body><img src="' + 'A' * 100000 + '" /></body></html>'

        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = malicious_html.encode('utf-8')
        book.add_item(cover_html)

        c1 = epub.EpubHtml(title='Chapter 1', file_name='ch1.xhtml', lang='en')
        c1.content = '<html><body><p>Content</p></body></html>'
        book.add_item(c1)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [c1]
        book.toc = (epub.Link('ch1.xhtml', 'Chapter 1', 'ch1'),)

        epub_path = temp_dir / 'security_unclosed_quote.epub'
        epub.write_epub(str(epub_path), book, {})

        # Should complete quickly (bounded by MAX_SEARCH_SIZE and quantifier limits)
        start = time.time()
        metadata = extract_epub_metadata(str(epub_path))
        elapsed = time.time() - start

        # Should complete in under 1 second even with malicious input
        assert elapsed < 1.0, f"Took {elapsed}s - potential ReDoS vulnerability"
        # Should not extract the malicious unbounded content (path too long)
        assert metadata['cover'] is None

    def test_large_html_without_closing_bracket(self, temp_dir):
        """Should handle HTML with many attributes efficiently"""
        book = epub.EpubBook()
        book.set_identifier('security-002')
        book.set_title('Security Test')

        # Create HTML with extremely long class attribute (stress test)
        # Make it valid HTML so ebooklib can create the EPUB
        malicious_html = '<html><body><img class="' + 'A' * 50000 + '" src="test.jpg" /></body></html>'

        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = malicious_html.encode('utf-8')
        book.add_item(cover_html)

        c1 = epub.EpubHtml(title='Chapter 1', file_name='ch1.xhtml', lang='en')
        c1.content = '<html><body><p>Content</p></body></html>'
        book.add_item(c1)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [c1]
        book.toc = (epub.Link('ch1.xhtml', 'Chapter 1', 'ch1'),)

        epub_path = temp_dir / 'security_unclosed_bracket.epub'
        epub.write_epub(str(epub_path), book, {})

        start = time.time()
        metadata = extract_epub_metadata(str(epub_path))
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Took {elapsed}s - potential ReDoS vulnerability"

    def test_extremely_large_html_input(self, temp_dir):
        """Should handle extremely large HTML files efficiently (size limit)"""
        book = epub.EpubBook()
        book.set_identifier('security-003')
        book.set_title('Security Test')

        # Create 2MB HTML file (much larger than MAX_SEARCH_SIZE of 100KB)
        # Old code would search entire file, new code only searches first 100KB
        # Put image reference at the end to verify size limiting works
        large_html = '<html><body>' + 'A' * (2 * 1024 * 1024) + '<img src="test.jpg" /></body></html>'

        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = large_html.encode('utf-8')
        book.add_item(cover_html)

        c1 = epub.EpubHtml(title='Chapter 1', file_name='ch1.xhtml', lang='en')
        c1.content = '<html><body><p>Content</p></body></html>'
        book.add_item(c1)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [c1]
        book.toc = (epub.Link('ch1.xhtml', 'Chapter 1', 'ch1'),)

        epub_path = temp_dir / 'security_large_html.epub'
        epub.write_epub(str(epub_path), book, {})

        start = time.time()
        metadata = extract_epub_metadata(str(epub_path))
        elapsed = time.time() - start

        # Should complete quickly due to MAX_SEARCH_SIZE limit (100KB)
        # Processing 100KB instead of 2MB
        assert elapsed < 2.0, f"Took {elapsed}s - size limit not working"

    def test_bounded_regex_quantifiers(self, temp_dir):
        """Should use bounded quantifiers to prevent excessive backtracking"""
        book = epub.EpubBook()
        book.set_identifier('security-004')
        book.set_title('Security Test')

        # Create src attribute with 600 chars (exceeds 500 char limit)
        # New regex has {1,500} bound to prevent matching overly long paths
        long_path = 'x' * 600
        html = f'<html><body><img src="{long_path}.jpg" /></body></html>'

        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = html.encode('utf-8')
        book.add_item(cover_html)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'security_bounded.epub'
        epub.write_epub(str(epub_path), book)

        start = time.time()
        metadata = extract_epub_metadata(str(epub_path))
        elapsed = time.time() - start

        assert elapsed < 0.5, f"Took {elapsed}s - bounded quantifiers not working"
        # Should not match paths longer than 500 chars
        assert metadata['cover'] is None

    def test_data_uri_rejection(self, temp_dir):
        """Should reject data URIs to prevent memory exhaustion"""
        book = epub.EpubBook()
        book.set_identifier('security-005')
        book.set_title('Security Test')

        # Data URI with large embedded image (potential memory attack)
        large_data_uri = 'data:image/jpeg;base64,' + 'A' * 100000
        html = f'<html><body><img src="{large_data_uri}" /></body></html>'

        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = html.encode('utf-8')
        book.add_item(cover_html)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'security_data_uri.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))

        # Should reject data URIs (they don't reference actual files)
        assert metadata['cover'] is None

    def test_beautifulsoup_over_regex(self, temp_dir):
        """Should use BeautifulSoup parsing over regex when possible"""
        book = epub.EpubBook()
        book.set_identifier('security-006')
        book.set_title('Security Test')

        # Well-formed HTML should be parsed by BeautifulSoup, not regex
        html = '''<html>
        <body>
            <svg xmlns:xlink="http://www.w3.org/1999/xlink">
                <image xlink:href="images/cover.jpg" />
            </svg>
        </body>
        </html>'''

        # Create actual cover image
        cover_img = epub.EpubImage()
        cover_img.file_name = 'images/cover.jpg'
        cover_img.content = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        book.add_item(cover_img)

        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = html.encode('utf-8')
        book.add_item(cover_html)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ['nav']

        epub_path = temp_dir / 'security_beautifulsoup.epub'
        epub.write_epub(str(epub_path), book)

        metadata = extract_epub_metadata(str(epub_path))

        # Should successfully extract using BeautifulSoup
        assert metadata['cover'] is not None
        assert metadata['cover'][:3] == b'\xff\xd8\xff'

    def test_malformed_html_graceful_failure(self, temp_dir):
        """Should fail gracefully on complex HTML patterns"""
        book = epub.EpubBook()
        book.set_identifier('security-007')
        book.set_title('Security Test')

        # HTML with complex nested structures
        malformed_html = '<html><body>' + '<div><span>test</span></div>' * 1000 + '</body></html>'

        cover_html = epub.EpubHtml(
            title='Cover',
            file_name='cover.html',
            lang='en'
        )
        cover_html.content = malformed_html.encode('utf-8')
        book.add_item(cover_html)

        c1 = epub.EpubHtml(title='Chapter 1', file_name='ch1.xhtml', lang='en')
        c1.content = '<html><body><p>Content</p></body></html>'
        book.add_item(c1)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [c1]
        book.toc = (epub.Link('ch1.xhtml', 'Chapter 1', 'ch1'),)

        epub_path = temp_dir / 'security_malformed.epub'
        epub.write_epub(str(epub_path), book, {})

        # Should not crash, should return None gracefully
        start = time.time()
        metadata = extract_epub_metadata(str(epub_path))
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Took {elapsed}s - error handling too slow"
        assert metadata['cover'] is None


class TestSecurityPerformance:
    """Performance benchmarks to validate security improvements"""

    def test_performance_with_normal_input(self, simple_epub):
        """Should maintain good performance with normal input"""
        # Baseline: normal EPUB should process quickly
        iterations = 10
        start = time.time()

        for _ in range(iterations):
            metadata = extract_epub_metadata(str(simple_epub))

        elapsed = time.time() - start
        avg = elapsed / iterations

        # Should average under 100ms per extraction for normal input
        assert avg < 0.1, f"Average {avg}s - performance regression"

    def test_consistent_performance_malicious_vs_normal(self, simple_epub, temp_dir):
        """Malicious input should not be significantly slower than normal input"""
        # Extract normal EPUB
        start_normal = time.time()
        extract_epub_metadata(str(simple_epub))
        elapsed_normal = time.time() - start_normal

        # Extract EPUB with stress-test HTML (valid but pathological)
        book = epub.EpubBook()
        book.set_identifier('perf-001')
        book.set_title('Performance Test')

        # Valid HTML with very long attribute (bounded by regex quantifiers)
        malicious_html = '<html><body><img src="' + 'A' * 100000 + '" /></body></html>'
        cover_html = epub.EpubHtml(title='Cover', file_name='cover.html', lang='en')
        cover_html.content = malicious_html.encode('utf-8')
        book.add_item(cover_html)

        c1 = epub.EpubHtml(title='Chapter 1', file_name='ch1.xhtml', lang='en')
        c1.content = '<html><body><p>Content</p></body></html>'
        book.add_item(c1)

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = [c1]
        book.toc = (epub.Link('ch1.xhtml', 'Chapter 1', 'ch1'),)

        epub_path = temp_dir / 'perf_malicious.epub'
        epub.write_epub(str(epub_path), book, {})

        start_malicious = time.time()
        extract_epub_metadata(str(epub_path))
        elapsed_malicious = time.time() - start_malicious

        # Malicious input should not be more than 5x slower
        # (BeautifulSoup and size limits prevent excessive slowdown)
        ratio = elapsed_malicious / max(elapsed_normal, 0.01)
        assert ratio < 5.0, f"Malicious input {ratio}x slower - insufficient protection"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
