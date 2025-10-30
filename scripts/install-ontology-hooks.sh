#!/bin/bash
#
# Installation script for ontology enforcement and auto-extraction hooks.
#
# This script:
# 1. Copies hooks from .githooks/ to .git/hooks/
# 2. Makes them executable
# 3. Tests that hooks work correctly
# 4. Provides status messages and troubleshooting tips
#
# Usage:
#   ./scripts/install-ontology-hooks.sh
#
# Requirements:
#   - Git repository
#   - Python 3.8+ (for pre-commit hook)
#   - Django project with manage.py (for post-commit hook)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GITHOOKS_DIR="${GIT_ROOT}/.githooks"
GIT_HOOKS_DIR="${GIT_ROOT}/.git/hooks"

# Hook files
PRE_COMMIT_HOOK="pre-commit-ontology.py"
POST_COMMIT_HOOK="post-commit-extract.sh"

# Function to print colored messages
print_header() {
    echo -e "\n${BLUE}===${NC} $1 ${BLUE}===${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository"
        exit 1
    fi
    print_success "Git repository detected"

    # Check Python version
    if command -v python3 > /dev/null 2>&1; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        print_success "Python ${PYTHON_VERSION} detected"
    else
        print_error "Python 3 not found"
        exit 1
    fi

    # Check if Django project
    if [ -f "${GIT_ROOT}/manage.py" ]; then
        print_success "Django project detected"
    else
        print_warning "manage.py not found - post-commit hook may not work"
    fi

    # Check if .githooks directory exists
    if [ ! -d "${GITHOOKS_DIR}" ]; then
        print_error ".githooks directory not found at ${GITHOOKS_DIR}"
        exit 1
    fi
    print_success ".githooks directory found"
}

# Function to install hooks
install_hooks() {
    print_header "Installing Hooks"

    # Create .git/hooks directory if it doesn't exist
    mkdir -p "${GIT_HOOKS_DIR}"

    # Install pre-commit hook
    if [ -f "${GITHOOKS_DIR}/${PRE_COMMIT_HOOK}" ]; then
        # Create wrapper script that calls the Python hook
        cat > "${GIT_HOOKS_DIR}/pre-commit" << 'EOF'
#!/bin/bash
# Ontology enforcement pre-commit hook
# This wrapper calls the Python AST-based checker

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOOK_SCRIPT="${GIT_ROOT}/.githooks/pre-commit-ontology.py"

if [ -f "${HOOK_SCRIPT}" ]; then
    python3 "${HOOK_SCRIPT}"
    exit $?
else
    echo "Warning: pre-commit-ontology.py not found"
    exit 0
fi
EOF
        chmod +x "${GIT_HOOKS_DIR}/pre-commit"
        print_success "Pre-commit hook installed"
    else
        print_error "Pre-commit hook source not found: ${GITHOOKS_DIR}/${PRE_COMMIT_HOOK}"
        exit 1
    fi

    # Install post-commit hook
    if [ -f "${GITHOOKS_DIR}/${POST_COMMIT_HOOK}" ]; then
        # Create wrapper script that calls the extraction hook
        cat > "${GIT_HOOKS_DIR}/post-commit" << 'EOF'
#!/bin/bash
# Ontology auto-extraction post-commit hook
# This wrapper calls the extraction script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GIT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
HOOK_SCRIPT="${GIT_ROOT}/.githooks/post-commit-extract.sh"

if [ -f "${HOOK_SCRIPT}" ]; then
    bash "${HOOK_SCRIPT}"
    exit $?
else
    echo "Warning: post-commit-extract.sh not found"
    exit 0
fi
EOF
        chmod +x "${GIT_HOOKS_DIR}/post-commit"
        print_success "Post-commit hook installed"
    else
        print_error "Post-commit hook source not found: ${GITHOOKS_DIR}/${POST_COMMIT_HOOK}"
        exit 1
    fi

    # Make source hooks executable as well
    chmod +x "${GITHOOKS_DIR}/${PRE_COMMIT_HOOK}"
    chmod +x "${GITHOOKS_DIR}/${POST_COMMIT_HOOK}"
}

# Function to test hooks
test_hooks() {
    print_header "Testing Hooks"

    cd "${GIT_ROOT}"

    # Test pre-commit hook
    print_info "Testing pre-commit hook..."
    if "${GIT_HOOKS_DIR}/pre-commit"; then
        print_success "Pre-commit hook test passed"
    else
        # Hook may legitimately fail if there are violations
        print_warning "Pre-commit hook returned non-zero exit code (this may be expected)"
    fi

    # Test post-commit hook (just syntax check)
    print_info "Testing post-commit hook syntax..."
    if bash -n "${GIT_HOOKS_DIR}/post-commit"; then
        print_success "Post-commit hook syntax valid"
    else
        print_error "Post-commit hook has syntax errors"
        exit 1
    fi
}

# Function to print summary
print_summary() {
    print_header "Installation Complete"

    cat << EOF

${GREEN}✓${NC} Ontology hooks successfully installed!

${BLUE}Installed hooks:${NC}
  • ${GIT_HOOKS_DIR}/pre-commit
    → Enforces @ontology decorator on critical paths
    → Blocks commits missing documentation
    → Provides quick-fix templates

  • ${GIT_HOOKS_DIR}/post-commit
    → Auto-extracts ontology to JSON
    → Updates knowledge graph
    → Adds ~5-10s to commit time

${BLUE}What happens now:${NC}
  1. When you commit changes to critical paths (models/, services/, api/, middleware/),
     the pre-commit hook will verify @ontology decorator presence

  2. If decorators are missing, commit is blocked with helpful templates

  3. After successful commits, ontology is automatically extracted to:
     ${YELLOW}docs/ontology/knowledge_graph.json${NC}

${BLUE}Critical paths requiring @ontology:${NC}
  • apps/*/models/     - Data models
  • apps/*/services/   - Business logic
  • apps/*/api/        - API endpoints
  • apps/*/middleware/ - Request/response processing

${BLUE}Exempted paths:${NC}
  • tests/                  - Test files
  • migrations/             - Database migrations
  • management/commands/    - CLI commands
  • __init__.py            - Package files

${BLUE}Troubleshooting:${NC}
  • Skip hooks temporarily:    git commit --no-verify
  • Check hook status:         ls -l ${GIT_HOOKS_DIR}/
  • View hook logs:            Check git commit output
  • Uninstall:                 rm ${GIT_HOOKS_DIR}/pre-commit ${GIT_HOOKS_DIR}/post-commit

${BLUE}Documentation:${NC}
  • Ontology system:  .kiro/steering/ontology_system.md
  • Decorator usage:  Run pre-commit hook for templates

${YELLOW}Note:${NC} You can still commit with ${YELLOW}--no-verify${NC} if needed, but this is
discouraged for critical paths requiring architectural documentation.

EOF
}

# Main execution
main() {
    print_header "Ontology Hooks Installation"
    print_info "Installing enforcement and auto-extraction hooks..."

    check_prerequisites
    install_hooks
    test_hooks
    print_summary
}

# Run main function
main

exit 0
