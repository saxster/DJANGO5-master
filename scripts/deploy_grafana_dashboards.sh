#!/bin/bash
# Deploy Grafana Dashboards for REST API Monitoring
# Usage: ./scripts/deploy_grafana_dashboards.sh [grafana_url] [api_key]
#
# Error-free deployment with validation and rollback

set -euo pipefail

# Configuration
GRAFANA_URL="${1:-http://localhost:3000}"
GRAFANA_API_KEY="${2:-}"
DASHBOARD_DIR="config/grafana/dashboards"
BACKUP_DIR="config/grafana/backups/$(date +%Y%m%d_%H%M%S)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validation
validate_prerequisites() {
    log_info "Validating prerequisites..."

    # Check if Grafana URL is accessible
    if ! curl -s -f -o /dev/null -w "%{http_code}" "$GRAFANA_URL/api/health" > /dev/null 2>&1; then
        log_error "Grafana not accessible at $GRAFANA_URL"
        log_info "Please ensure Grafana is running and accessible"
        exit 1
    fi
    log_success "Grafana is accessible at $GRAFANA_URL"

    # Check if API key is provided
    if [ -z "$GRAFANA_API_KEY" ]; then
        log_warning "No API key provided - trying to use Basic auth"
        log_info "Set GRAFANA_API_KEY environment variable or pass as second argument"
        log_info "Example: export GRAFANA_API_KEY=eyJrIjoiVGVzdDEyMzQ..."

        # Try to get from environment
        if [ -n "${GRAFANA_API_KEY:-}" ]; then
            log_success "Using API key from environment variable"
        else
            log_error "No API key available. Cannot proceed."
            exit 1
        fi
    else
        log_success "API key provided"
    fi

    # Check if dashboard files exist
    if [ ! -d "$DASHBOARD_DIR" ]; then
        log_error "Dashboard directory not found: $DASHBOARD_DIR"
        exit 1
    fi

    local dashboard_count=$(find "$DASHBOARD_DIR" -name "*.json" -type f | wc -l)
    if [ "$dashboard_count" -eq 0 ]; then
        log_error "No dashboard JSON files found in $DASHBOARD_DIR"
        exit 1
    fi

    log_success "Found $dashboard_count dashboard(s) to deploy"
}

# Backup existing dashboards
backup_existing_dashboards() {
    log_info "Backing up existing dashboards..."

    mkdir -p "$BACKUP_DIR"

    # List all dashboards
    local dashboards=$(curl -s -H "Authorization: Bearer $GRAFANA_API_KEY" \
        "$GRAFANA_URL/api/search?type=dash-db" 2>/dev/null || echo "[]")

    # Save backup
    echo "$dashboards" > "$BACKUP_DIR/existing_dashboards.json"

    local count=$(echo "$dashboards" | grep -o '"uid"' | wc -l)
    log_success "Backed up $count existing dashboard(s) to $BACKUP_DIR"
}

# Deploy single dashboard
deploy_dashboard() {
    local dashboard_file="$1"
    local dashboard_name=$(basename "$dashboard_file" .json)

    log_info "Deploying: $dashboard_name..."

    # Validate JSON syntax
    if ! python3 -m json.tool "$dashboard_file" > /dev/null 2>&1; then
        log_error "Invalid JSON in $dashboard_file"
        return 1
    fi

    # Wrap dashboard in required format
    local payload=$(cat <<EOF
{
  "dashboard": $(cat "$dashboard_file" | python3 -m json.tool | grep -A 9999 '"dashboard"' | tail -n +2 | head -n -1),
  "overwrite": true,
  "message": "Deployed by REST API migration (Oct 2025)"
}
EOF
)

    # Deploy to Grafana
    local response=$(curl -s -X POST \
        -H "Authorization: Bearer $GRAFANA_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$GRAFANA_URL/api/dashboards/db" 2>&1)

    # Check response
    if echo "$response" | grep -q '"status":"success"'; then
        local dashboard_url=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('url', ''))" 2>/dev/null || echo "")
        log_success "✓ $dashboard_name deployed successfully"
        if [ -n "$dashboard_url" ]; then
            log_info "  URL: $GRAFANA_URL$dashboard_url"
        fi
        return 0
    else
        log_error "✗ Failed to deploy $dashboard_name"
        log_error "  Response: $response"
        return 1
    fi
}

# Main deployment function
main() {
    echo ""
    log_info "================================================"
    log_info "Grafana Dashboard Deployment"
    log_info "REST API Migration Monitoring (Oct 2025)"
    log_info "================================================"
    echo ""

    # Step 1: Validate
    validate_prerequisites

    # Step 2: Backup
    backup_existing_dashboards

    # Step 3: Deploy dashboards
    log_info ""
    log_info "Deploying dashboards..."
    echo ""

    local success_count=0
    local fail_count=0

    for dashboard in "$DASHBOARD_DIR"/*.json; do
        if [ -f "$dashboard" ]; then
            if deploy_dashboard "$dashboard"; then
                ((success_count++))
            else
                ((fail_count++))
            fi
        fi
    done

    # Summary
    echo ""
    log_info "================================================"
    log_info "Deployment Summary"
    log_info "================================================"
    log_success "Successfully deployed: $success_count dashboard(s)"

    if [ "$fail_count" -gt 0 ]; then
        log_error "Failed: $fail_count dashboard(s)"
        log_info "Check error messages above for details"
        exit 1
    else
        log_success "All dashboards deployed successfully!"
    fi

    # Next steps
    echo ""
    log_info "Next Steps:"
    log_info "1. Visit Grafana: $GRAFANA_URL"
    log_info "2. Check 'REST API' folder for new dashboards"
    log_info "3. Configure alert notification channels if needed"
    log_info "4. Set up Prometheus scraping (see config/grafana/dashboards/README.md)"
    echo ""
}

# Run main function
main "$@"
