# Tests

This directory contains automated tests for the Kokoro TTS project using pytest.

## Test Files

### Unit Tests
- **test_front_matter.py** - Front matter detection logic (pytest format)
- **test_intro_generation.py** - Audiobook introduction generation (pytest format)
- **test_cover_extraction.py** - EPUB cover extraction with multi-strategy fallback (NEW!)

### Test Utilities
- **conftest.py** - Shared pytest fixtures and configuration
- **create_test_epub.py** - Script to create test EPUB files for manual testing
- **TESTING.md** - Comprehensive testing plan and documentation

## Quick Start

### Install Test Dependencies

```bash
# Using pip
pip install pytest pytest-cov pytest-mock

# Or add to your environment
pip install -e ".[test]"
```

### Running Tests

**Easiest way - use the test runner:**

```bash
# Run all tests
./run_tests.sh

# Run with coverage report
./run_tests.sh --coverage

# Run specific test file
./run_tests.sh --test test_cover_extraction.py

# Verbose output
./run_tests.sh --verbose
```

**Using pytest directly:**

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_cover_extraction.py -v

# Run with coverage
pytest tests/ --cov=kokoro_tts --cov-report=term-missing

# Run specific test class
pytest tests/test_cover_extraction.py::TestCoverExtraction -v

# Run specific test method
pytest tests/test_cover_extraction.py::TestCoverExtraction::test_cover_html_reference -v
```

**Backwards compatible - run tests directly:**

```bash
# Still works for backwards compatibility
python tests/test_front_matter.py
python tests/test_intro_generation.py
```

## Test Coverage

Current test coverage focuses on:

✅ **Front Matter Detection** - Identifying and filtering audiobook front matter
✅ **Intro Generation** - Creating audiobook introduction text from metadata
✅ **Cover Extraction** - Multi-strategy EPUB cover image extraction (validates recent fix)

### Coverage Report

Generate HTML coverage report:

```bash
pytest tests/ --cov=kokoro_tts --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Fixtures

Shared fixtures are defined in `conftest.py`:

- `sample_metadata` - Sample metadata dictionary
- `sample_metadata_with_cover` - Metadata with JPEG cover
- `temp_dir` - Temporary directory for test files
- `simple_epub` - Simple single-chapter EPUB
- `epub_with_cover_html` - EPUB with cover.html referencing image (tests fix)
- `epub_with_front_matter` - EPUB with various front matter chapters

## Writing New Tests

Example test structure:

```python
import pytest
from kokoro_tts.audiobook import some_function

class TestMyFeature:
    """Test suite for my feature"""

    def test_basic_case(self):
        """Should handle basic case"""
        result = some_function("input")
        assert result == "expected"

    def test_with_fixture(self, simple_epub):
        """Should work with EPUB fixture"""
        result = some_function(str(simple_epub))
        assert result is not None

    @pytest.mark.parametrize("input,expected", [
        ("a", "A"),
        ("b", "B"),
    ])
    def test_parametrized(self, input, expected):
        """Should handle multiple cases"""
        assert some_function(input) == expected
```

## Continuous Integration

Tests run automatically on GitHub Actions for:
- Python 3.10, 3.11, 3.12, 3.13
- Linux, macOS, Windows (when CI is configured)

## Test Documentation

See [TESTING.md](TESTING.md) for:
- Complete testing plan
- Manual test checklist
- Future test improvements
- Integration test plans

## Notes

- Tests must be run from the project root directory
- Fixtures in `conftest.py` are automatically available to all tests
- Use `pytest -v` for verbose output showing each test
- Use `pytest -k "keyword"` to run tests matching a keyword
- Use `pytest --lf` to run only last failed tests
- Use `pytest --tb=short` for shorter traceback output
