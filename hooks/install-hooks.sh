#!/bin/bash
# Install git hooks for Kokoro TTS development
# Run this script after cloning the repository to set up pre-commit and pre-push hooks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Installing Git Hooks for Kokoro TTS${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Install pre-commit hook
if [ -f "$GIT_HOOKS_DIR/pre-commit" ] && [ ! -L "$GIT_HOOKS_DIR/pre-commit" ]; then
    echo -e "${YELLOW}⚠️  Existing pre-commit hook found. Backing up to pre-commit.backup${NC}"
    mv "$GIT_HOOKS_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit.backup"
fi

echo -e "${BLUE}Installing pre-commit hook...${NC}"
cp "$SCRIPT_DIR/pre-commit" "$GIT_HOOKS_DIR/pre-commit"
chmod +x "$GIT_HOOKS_DIR/pre-commit"
echo -e "${GREEN}✓ pre-commit hook installed${NC}"
echo ""

# Install pre-push hook
if [ -f "$GIT_HOOKS_DIR/pre-push" ] && [ ! -L "$GIT_HOOKS_DIR/pre-push" ]; then
    echo -e "${YELLOW}⚠️  Existing pre-push hook found. Backing up to pre-push.backup${NC}"
    mv "$GIT_HOOKS_DIR/pre-push" "$GIT_HOOKS_DIR/pre-push.backup"
fi

echo -e "${BLUE}Installing pre-push hook...${NC}"
cp "$SCRIPT_DIR/pre-push" "$GIT_HOOKS_DIR/pre-push"
chmod +x "$GIT_HOOKS_DIR/pre-push"
echo -e "${GREEN}✓ pre-push hook installed${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Git hooks installed successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Installed hooks:"
echo "  • pre-commit  - Quick syntax and quality checks"
echo "  • pre-push    - Run full test suite before push"
echo ""
echo "To bypass hooks in emergencies:"
echo "  git commit --no-verify"
echo "  git push --no-verify"
echo ""
