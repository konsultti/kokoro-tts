# Tests

This directory contains test files for the Kokoro TTS project.

## Test Files

- **test_front_matter.py** - Unit tests for audiobook front matter detection
- **test_intro_generation.py** - Unit tests for audiobook introduction generation
- **create_test_epub.py** - Script to create a test EPUB file for manual testing
- **TESTING.md** - Comprehensive testing plan and documentation

## Running Tests

From the project root directory:

```bash
# Run front matter detection tests
uv run python tests/test_front_matter.py

# Run intro generation tests
uv run python tests/test_intro_generation.py

# Create a test EPUB file
uv run python tests/create_test_epub.py
```

**Note:** Tests must be run from the project root directory (not from within the `tests/` directory) to ensure proper module imports.

## Test Documentation

See [TESTING.md](TESTING.md) for the complete testing plan, manual test checklist, and future improvements.
