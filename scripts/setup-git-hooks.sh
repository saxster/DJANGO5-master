#!/bin/bash
#
# Setup git hooks for the Django5 project
#
# This script installs pre-commit hooks that enforce code quality rules
# defined in .claude/rules.md
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GITHOOKS_DIR="$PROJECT_ROOT/.githooks"
GIT_HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔧 Setting up git hooks..."

# Check if .git directory exists
if [ ! -d "$GIT_HOOKS_DIR" ]; then
    echo -e "${YELLOW}Warning:${NC} .git/hooks directory not found. Are you in a git repository?"
    exit 1
fi

# Create .git/hooks directory if it doesn't exist
mkdir -p "$GIT_HOOKS_DIR"

# Copy hooks
echo "📋 Installing hooks..."

for hook in "$GITHOOKS_DIR"/*; do
    if [ -f "$hook" ] && [ "$(basename "$hook")" != "README.md" ]; then
        hook_name=$(basename "$hook")
        target="$GIT_HOOKS_DIR/pre-commit"
        
        echo "  • Installing $hook_name → pre-commit"
        cp "$hook" "$target"
        chmod +x "$target"
    fi
done

echo ""
echo -e "${GREEN}✅ Git hooks installed successfully!${NC}"
echo ""
echo "Installed hooks will:"
echo "  ✓ Validate model complexity (< 150 lines)"
echo "  ✓ Check utility function size (< 50 lines)"
echo "  ✓ Verify settings file limits (< 200 lines)"
echo ""
echo "To test the hook:"
echo "  .git/hooks/pre-commit"
echo ""

