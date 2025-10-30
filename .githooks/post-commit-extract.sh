#!/bin/bash
#
# Post-commit hook to automatically extract ontology to knowledge graph JSON.
#
# This hook runs after every successful commit and:
# 1. Executes the extract_ontology management command
# 2. Updates docs/ontology/knowledge_graph.json
# 3. Silent unless errors occur
# 4. Adds 5-10s to commit time
#
# Installation: Run scripts/install-ontology-hooks.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ONTOLOGY_OUTPUT="docs/ontology/knowledge_graph.json"
EXTRACTION_CMD="python manage.py extract_ontology --output ${ONTOLOGY_OUTPUT} --quiet"

# Function to print status messages
print_status() {
    echo -e "${GREEN}[Ontology]${NC} $1"
}

print_error() {
    echo -e "${RED}[Ontology Error]${NC} $1" >&2
}

print_warning() {
    echo -e "${YELLOW}[Ontology Warning]${NC} $1"
}

# Main execution
main() {
    # Check if in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository"
        exit 1
    fi

    # Get the root directory of the git repository
    GIT_ROOT=$(git rev-parse --show-toplevel)
    cd "${GIT_ROOT}"

    # Check if manage.py exists
    if [ ! -f "manage.py" ]; then
        print_warning "manage.py not found, skipping ontology extraction"
        exit 0
    fi

    # Create output directory if it doesn't exist
    mkdir -p "$(dirname "${ONTOLOGY_OUTPUT}")"

    # Extract ontology
    print_status "Extracting ontology to ${ONTOLOGY_OUTPUT}..."

    if ${EXTRACTION_CMD} 2>&1; then
        # Check if file was created/updated
        if [ -f "${ONTOLOGY_OUTPUT}" ]; then
            # Get file size for feedback
            FILE_SIZE=$(wc -c < "${ONTOLOGY_OUTPUT}" | tr -d ' ')

            # Count nodes and edges for summary
            if command -v jq > /dev/null 2>&1; then
                NODES=$(jq '.nodes | length' "${ONTOLOGY_OUTPUT}" 2>/dev/null || echo "?")
                EDGES=$(jq '.edges | length' "${ONTOLOGY_OUTPUT}" 2>/dev/null || echo "?")
                print_status "Knowledge graph updated: ${NODES} nodes, ${EDGES} edges (${FILE_SIZE} bytes)"
            else
                print_status "Knowledge graph updated (${FILE_SIZE} bytes)"
            fi
        else
            print_warning "Ontology extraction completed but output file not found"
        fi
    else
        print_error "Failed to extract ontology"
        print_warning "This doesn't block your commit, but knowledge graph may be outdated"
        print_warning "Run manually: ${EXTRACTION_CMD}"
        # Don't exit with error - we don't want to block the commit
        exit 0
    fi
}

# Run main function
main

exit 0
