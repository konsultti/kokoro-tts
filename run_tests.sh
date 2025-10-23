#!/bin/bash
# Test runner script for Kokoro TTS
# Usage: ./run_tests.sh [options]

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Kokoro TTS Test Suite ===${NC}"
echo ""

# Check if pytest is installed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${RED}Error: pytest not found${NC}"
    echo "Installing test dependencies..."
    pip install pytest pytest-cov pytest-mock
    echo ""
fi

# Parse arguments
COVERAGE=false
VERBOSE=false
SPECIFIC_TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --test|-t)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: ./run_tests.sh [options]"
            echo ""
            echo "Options:"
            echo "  -c, --coverage    Run with coverage report"
            echo "  -v, --verbose     Verbose output"
            echo "  -t, --test FILE   Run specific test file"
            echo "  -h, --help        Show this help"
            echo ""
            echo "Examples:"
            echo "  ./run_tests.sh                    # Run all tests"
            echo "  ./run_tests.sh --coverage         # Run with coverage"
            echo "  ./run_tests.sh -t test_cover_extraction.py"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="python3 -m pytest"

if [ "$SPECIFIC_TEST" != "" ]; then
    PYTEST_CMD="$PYTEST_CMD tests/$SPECIFIC_TEST"
else
    PYTEST_CMD="$PYTEST_CMD tests/"
fi

if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=kokoro_tts --cov-report=term-missing --cov-report=html"
fi

# Run tests
echo -e "${BLUE}Running tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo -e "${BLUE}Coverage report saved to: htmlcov/index.html${NC}"
    fi

    exit 0
else
    echo ""
    echo -e "${RED}❌ Tests failed!${NC}"
    exit 1
fi
