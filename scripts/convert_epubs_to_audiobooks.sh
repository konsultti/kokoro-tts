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
OUTPUT_DIR="."
TEMP_DIR=""
VOICE="af_sarah"
KEEP_TEMP=false
SELECT_CHAPTERS="all"

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
    echo "  --voice <voice>          Voice to use (default: af_sarah)"
    echo "  --output-dir <dir>       Output directory for audiobooks (default: current directory)"
    echo "  --temp-dir <dir>         Custom temporary directory (optional)"
    echo "  --select-chapters <sel>  Chapter selection: 'all', '1,3,5', '1-5' (default: all)"
    echo "  --keep-temp              Keep temporary files after creation"
    echo "  --help                   Show this help message"
    echo ""
    echo "Example:"
    echo "  $0 /path/to/epubs --voice af_bella --output-dir ./audiobooks"
    echo "  $0 /path/to/epubs --select-chapters '1-5,10' --keep-temp"
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
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --temp-dir)
            TEMP_DIR="$2"
            shift 2
            ;;
        --select-chapters)
            SELECT_CHAPTERS="$2"
            shift 2
            ;;
        --keep-temp)
            KEEP_TEMP=true
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

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Print configuration
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}  Kokoro TTS - Batch EPUB to Audiobook Converter    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  EPUB Directory:    $EPUB_DIR"
echo "  Output Directory:  $OUTPUT_DIR"
echo "  Voice:             $VOICE"
echo "  Chapter Selection: $SELECT_CHAPTERS"
echo "  Keep Temp:         $KEEP_TEMP"
if [ -n "$TEMP_DIR" ]; then
    echo "  Temp Directory:    $TEMP_DIR"
fi
echo "  Files Found:       ${#EPUB_FILES[@]}"
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

    # Output file in the output directory
    AUDIOBOOK_OUTPUT="${OUTPUT_DIR}/${EPUB_NAME}.m4a"

    # Check if already processed
    if [ -f "$AUDIOBOOK_OUTPUT" ]; then
        echo -e "${YELLOW}⊙ Audiobook already exists: $AUDIOBOOK_OUTPUT${NC}"
        echo -e "${YELLOW}⊙ Skipping...${NC}"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Build kokoro-tts command
    KOKORO_CMD="python -m kokoro_tts \"$EPUB_FILE\" --audiobook \"$AUDIOBOOK_OUTPUT\" --voice \"$VOICE\" --select-chapters \"$SELECT_CHAPTERS\""

    # Add optional temp-dir if specified
    if [ -n "$TEMP_DIR" ]; then
        KOKORO_CMD="$KOKORO_CMD --temp-dir \"$TEMP_DIR\""
    fi

    # Add keep-temp flag if requested
    if [ "$KEEP_TEMP" = true ]; then
        KOKORO_CMD="$KOKORO_CMD --keep-temp"
    fi

    # Run kokoro-tts
    echo -e "${GREEN}► Starting conversion...${NC}"
    START_TIME=$(date +%s)

    # Temporarily disable exit-on-error for this command to allow continuing to next book
    set +e
    eval $KOKORO_CMD
    KOKORO_EXIT_CODE=$?
    set -e

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    MINUTES=$((DURATION / 60))
    SECONDS=$((DURATION % 60))

    if [ $KOKORO_EXIT_CODE -eq 0 ] && [ -f "$AUDIOBOOK_OUTPUT" ]; then
        echo -e "${GREEN}✓ Success! Duration: ${MINUTES}m ${SECONDS}s${NC}"
        echo -e "${GREEN}✓ Audiobook saved: $AUDIOBOOK_OUTPUT${NC}"

        # Calculate file size
        FILE_SIZE=$(du -h "$AUDIOBOOK_OUTPUT" | cut -f1)
        echo -e "${GREEN}✓ File size: $FILE_SIZE${NC}"

        SUCCESSFUL=$((SUCCESSFUL + 1))
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

# Exit code based on results
if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
