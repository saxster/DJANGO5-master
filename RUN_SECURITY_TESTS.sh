#!/bin/bash
#
# Security Test Suite Runner
# Run comprehensive tests for November 5, 2025 security improvements
#
# Usage:
#   ./RUN_SECURITY_TESTS.sh [option]
#
# Options:
#   all       - Run all security tests (default)
#   csrf      - Run only CSRF protection tests
#   files     - Run only file security tests
#   trans     - Run only transaction tests
#   rate      - Run only rate limiting tests
#   perf      - Run only performance tests
#   quick     - Run quick smoke tests
#   coverage  - Run with coverage report

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Security Test Suite - Nov 5, 2025${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Parse command line argument
TEST_SUITE=${1:-all}

case "$TEST_SUITE" in
    csrf)
        echo -e "${YELLOW}Running CSRF protection tests...${NC}"
        pytest apps/peoples/tests/test_session_api_security.py \
               apps/core/tests/test_resumable_upload_security.py \
               -v --tb=short
        ;;
    
    files)
        echo -e "${YELLOW}Running file security tests...${NC}"
        pytest tests/security/test_secure_file_download.py \
               -v --tb=short
        ;;
    
    trans)
        echo -e "${YELLOW}Running transaction atomicity tests...${NC}"
        pytest apps/peoples/tests/test_session_transaction_atomicity.py \
               -v --tb=short
        ;;
    
    rate)
        echo -e "${YELLOW}Running rate limiting tests...${NC}"
        pytest tests/security/test_rate_limiting.py \
               -v --tb=short
        ;;
    
    perf)
        echo -e "${YELLOW}Running performance tests...${NC}"
        pytest tests/performance/test_file_streaming.py \
               -v --tb=short
        ;;
    
    quick)
        echo -e "${YELLOW}Running quick smoke tests...${NC}"
        pytest apps/peoples/tests/test_session_api_security.py::TestSessionRevokeCSRFProtection::test_session_revoke_requires_csrf_token \
               tests/security/test_secure_file_download.py::TestPathTraversalPrevention::test_path_traversal_attack_blocked \
               apps/peoples/tests/test_session_transaction_atomicity.py::TestSessionRevocationAtomicity::test_session_revoke_creates_audit_log_atomically \
               -v --tb=short
        ;;
    
    coverage)
        echo -e "${YELLOW}Running all tests with coverage report...${NC}"
        pytest apps/peoples/tests/test_session_api_security.py \
               apps/core/tests/test_resumable_upload_security.py \
               tests/security/test_secure_file_download.py \
               apps/peoples/tests/test_session_transaction_atomicity.py \
               tests/security/test_rate_limiting.py \
               tests/performance/test_file_streaming.py \
               tests/integration/test_security_improvements_integration.py \
               tests/unit/test_exception_handling_specificity.py \
               --cov=apps/peoples/api/session_views \
               --cov=apps/core/views/resumable_upload_views \
               --cov=apps/core/services/secure_file_download_service \
               --cov=apps/peoples/services/session_management_service \
               --cov=apps/reports/tasks \
               --cov=monitoring/views/prometheus_exporter \
               --cov=apps/core/views/csp_report \
               --cov-report=html:coverage_reports/security_nov_5_2025 \
               --cov-report=term \
               -v
        
        echo ""
        echo -e "${GREEN}Coverage report generated: coverage_reports/security_nov_5_2025/index.html${NC}"
        ;;
    
    all|*)
        echo -e "${YELLOW}Running all security tests...${NC}"
        pytest apps/peoples/tests/test_session_api_security.py \
               apps/core/tests/test_resumable_upload_security.py \
               tests/security/test_secure_file_download.py \
               apps/peoples/tests/test_session_transaction_atomicity.py \
               tests/security/test_rate_limiting.py \
               tests/performance/test_file_streaming.py \
               tests/integration/test_security_improvements_integration.py \
               tests/unit/test_exception_handling_specificity.py \
               -v --tb=short
        ;;
esac

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Test suite completed!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "Test documentation: SECURITY_TEST_SUITE_SUMMARY.md"
echo "Implementation details: CODE_REVIEW_IMPLEMENTATION_COMPLETE.md"
echo ""
