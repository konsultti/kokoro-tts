#!/bin/bash
#
# convert_epubs_to_audiobooks.sh
#
# Batch convert EPUB files to M4A audiobooks using kokoro-tts
#
# Usage: ./convert_epubs_to_audiobooks.sh <epub_directory>
# Example: ./convert_epubs_to_audiobooks.sh /mnt/e/LLM-stuff/sources/
#

set -euo pipefail  # Exit on error in pipeline, undefined vars

# Default parameters
CHAPTERS_DIR="./audiobook"
FORMAT="m4a"
VOICE="af_sarah"
CLEANUP=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print usage
usage() {
    echo "Usage: $0 <epub_directory> [options]"
    echo ""
    echo "Options:"
    echo "  --voice <voice>     Voice to use (default: af_sarah)"
    echo "  --format <format>   Output format (default: m4a)"
    echo "  --temp-dir <dir>    Temporary directory (default: ./audiobook)"
    echo "  --no-cleanup        Don't clean up temporary files"
    echo "  --help              Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 /path/to/epubs --voice af_bella --no-cleanup"
    exit 1
}

# Parse arguments
EPUB_DIR=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --voice)
            VOICE="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --temp-dir)
            CHAPTERS_DIR="$2"
            shift 2
            ;;
        --no-cleanup)
            CLEANUP=false
            shift
            ;;
        --help)
            usage
            ;;
        *)
            if [ -z "$EPUB_DIR" ]; then
                EPUB_DIR="$1"
            else
                echo -e "${RED}Error: Unknown argument '$1'${NC}"
                usage
            fi
            shift
            ;;
    esac
done

# Validate arguments
if [ -z "$EPUB_DIR" ]; then
    echo -e "${RED}Error: EPUB directory not specified${NC}"
    usage
fi

if [ ! -d "$EPUB_DIR" ]; then
    echo -e "${RED}Error: Directory '$EPUB_DIR' does not exist${NC}"
    exit 1
fi

# Find all EPUB files
mapfile -t EPUB_FILES < <(find "$EPUB_DIR" -maxdepth 1 -type f -name "*.epub" | sort)

if [ ${#EPUB_FILES[@]} -eq 0 ]; then
    echo -e "${YELLOW}No EPUB files found in '$EPUB_DIR'${NC}"
    exit 0
fi

# Print configuration
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  Kokoro TTS - Batch EPUB to Audiobook Converter    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  EPUB Directory: $EPUB_DIR"
echo "  Voice:          $VOICE"
echo "  Format:         $FORMAT"
echo "  Temp Directory: $CHAPTERS_DIR"
echo "  Cleanup:        $CLEANUP"
echo "  Files Found:    ${#EPUB_FILES[@]}"
echo ""

# Confirm before proceeding
read -p "Process ${#EPUB_FILES[@]} EPUB file(s)? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Cancelled by user${NC}"
    exit 0
fi

# Process each EPUB file
SUCCESSFUL=0
FAILED=0
SKIPPED=0

for i in "${!EPUB_FILES[@]}"; do
    EPUB_FILE="${EPUB_FILES[$i]}"
    EPUB_BASENAME=$(basename "$EPUB_FILE")
    EPUB_NAME="${EPUB_BASENAME%.epub}"

    # Current progress
    CURRENT=$((i + 1))
    TOTAL=${#EPUB_FILES[@]}

    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Processing [$CURRENT/$TOTAL]: ${GREEN}$EPUB_BASENAME${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

    # Expected output file
    EXPECTED_OUTPUT="${CHAPTERS_DIR}/${EPUB_NAME}_Complete.${FORMAT}"
    FINAL_OUTPUT="${EPUB_DIR}/${EPUB_NAME}.${FORMAT}"

    # Check if already processed
    if [ -f "$FINAL_OUTPUT" ]; then
        echo -e "${YELLOW}⊙ Audiobook already exists: $FINAL_OUTPUT${NC}"
        echo -e "${YELLOW}⊙ Skipping...${NC}"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Create temporary directory
    mkdir -p "$CHAPTERS_DIR"

    # Run kokoro-tts
    echo -e "${GREEN}► Starting conversion...${NC}"
    START_TIME=$(date +%s)

    # Temporarily disable exit-on-error for this command to allow continuing to next book
    set +e
    python -m kokoro_tts "$EPUB_FILE" --chapters "$CHAPTERS_DIR" --format "$FORMAT" --voice "$VOICE"
    KOKORO_EXIT_CODE=$?
    set -e

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))

    if [ $KOKORO_EXIT_CODE -eq 0 ]; then
        # Move the complete audiobook to source directory
        if [ -f "$EXPECTED_OUTPUT" ]; then
            mv "$EXPECTED_OUTPUT" "$FINAL_OUTPUT"
            echo -e "${GREEN}✓ Success! Duration: ${MINUTES}m ${SECONDS}s${NC}"
            echo -e "${GREEN}✓ Audiobook saved: $FINAL_OUTPUT${NC}"

            # Calculate file size
            FILE_SIZE=$(du -h "$FINAL_OUTPUT" | cut -f1)
            echo -e "${GREEN}✓ File size: $FILE_SIZE${NC}"

            # Cleanup chapter files if requested
            if [ "$CLEANUP" = true ]; then
                echo -e "${BLUE}► Cleaning up chapter files...${NC}"
                rm -rf "${CHAPTERS_DIR}/Chapter_"*.${FORMAT}
                echo -e "${GREEN}✓ Cleanup complete${NC}"
            fi

            SUCCESSFUL=$((SUCCESSFUL + 1))
        else
            echo -e "${RED}✗ Error: Expected output file not found: $EXPECTED_OUTPUT${NC}"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "${RED}✗ Failed after ${MINUTES}m ${SECONDS}s (exit code: $KOKORO_EXIT_CODE)${NC}"
        FAILED=$((FAILED + 1))
    fi
done

# Final summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                    Final Summary                      ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Total Files:   ${TOTAL}"
echo -e "  ${GREEN}✓ Successful:  ${SUCCESSFUL}${NC}"
if [ $SKIPPED -gt 0 ]; then
    echo -e "  ${YELLOW}⊙ Skipped:     ${SKIPPED}${NC}"
fi
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}✗ Failed:      ${FAILED}${NC}"
fi
echo ""

# Cleanup temp directory if empty and cleanup enabled
if [ "$CLEANUP" = true ] && [ -d "$CHAPTERS_DIR" ]; then
    if [ -z "$(ls -A "$CHAPTERS_DIR")" ]; then
        rmdir "$CHAPTERS_DIR"
        echo -e "${GREEN}✓ Removed empty temp directory${NC}"
    else
        echo -e "${YELLOW}⊙ Temp directory not empty, keeping: $CHAPTERS_DIR${NC}"
    fi
fi

# Exit code based on results
if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
