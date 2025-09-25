#!/bin/bash

# API Test Suite Runner
# Comprehensive test execution for API modernization features

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COVERAGE_THRESHOLD=85
PARALLEL_WORKERS=auto
TEST_DB_NAME="test_youtility_api"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}\n"
}

# Check dependencies
check_dependencies() {
    print_header "Checking Dependencies"
    
    # Check if pytest is installed
    if ! command -v pytest &> /dev/null; then
        print_error "pytest is not installed. Please run: pip install -r test-requirements.txt"
        exit 1
    fi
    
    # Check if Redis is running (for cache tests)
    if ! redis-cli ping &> /dev/null; then
        print_warning "Redis is not running. Cache-related tests may fail."
        print_status "Starting Redis if possible..."
        if command -v redis-server &> /dev/null; then
            redis-server --daemonize yes &> /dev/null || true
        fi
    fi
    
    # Check if test database can be created
    print_status "Checking database permissions..."
    python manage.py check --database default
    
    print_success "Dependencies check completed"
}

# Setup test environment
setup_test_env() {
    print_header "Setting Up Test Environment"
    
    # Set test settings
    export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings
    export TESTING=true
    
    # Create test database if needed
    print_status "Preparing test database..."
    python manage.py migrate --run-syncdb --verbosity=0
    
    # Clear cache
    print_status "Clearing cache..."
    python -c "from django.core.cache import cache; cache.clear()" 2>/dev/null || true
    
    # Create test data fixtures
    print_status "Loading test fixtures..."
    python manage.py loaddata tests/fixtures/test_data.json 2>/dev/null || true
    
    print_success "Test environment setup completed"
}

# Run unit tests
run_unit_tests() {
    print_header "Running Unit Tests"
    
    print_status "Running serializer tests..."
    pytest tests/api/unit/test_serializers.py -v --tb=short || return 1
    
    print_status "Running ViewSet tests..."
    pytest tests/api/unit/test_viewsets.py -v --tb=short || return 1
    
    print_status "Running authentication tests..."
    pytest tests/api/unit/test_authentication.py -v --tb=short || return 1
    
    print_status "Running middleware tests..."
    pytest tests/api/unit/test_middleware.py -v --tb=short || return 1
    
    print_success "Unit tests completed"
}

# Run integration tests
run_integration_tests() {
    print_header "Running Integration Tests"
    
    print_status "Running REST API endpoint tests..."
    pytest tests/api/integration/test_rest_endpoints.py -v --tb=short || return 1
    
    print_status "Running GraphQL tests..."
    pytest tests/api/integration/test_graphql.py -v --tb=short || return 1
    
    print_status "Running mobile API tests..."
    pytest tests/api/integration/test_mobile_api.py -v --tb=short || return 1
    
    print_success "Integration tests completed"
}

# Run performance tests
run_performance_tests() {
    print_header "Running Performance Tests"
    
    print_status "Running load tests (this may take a while)..."
    pytest tests/api/performance/test_load_testing.py -v -m "not slow" --tb=short || return 1
    
    print_status "Running benchmark tests..."
    pytest tests/api/performance/test_load_testing.py -v -m benchmark --tb=short || return 1
    
    print_success "Performance tests completed"
}

# Run security tests
run_security_tests() {
    print_header "Running Security Tests"
    
    print_status "Running security tests..."
    pytest tests/api/security/test_security.py -v --tb=short || return 1
    
    print_status "Running security scan with bandit..."
    if command -v bandit &> /dev/null; then
        bandit -r apps/api/ -f json -o security_report.json || print_warning "Bandit scan found issues"
        print_success "Security scan completed - check security_report.json"
    else
        print_warning "Bandit not installed - skipping security scan"
    fi
    
    print_success "Security tests completed"
}

# Run end-to-end tests
run_e2e_tests() {
    print_header "Running End-to-End Tests"
    
    print_status "Running monitoring tests..."
    pytest tests/api/e2e/test_monitoring.py -v --tb=short || return 1
    
    print_success "End-to-end tests completed"
}

# Generate coverage report
generate_coverage() {
    print_header "Generating Coverage Report"
    
    print_status "Running all tests with coverage..."
    pytest tests/api/ \
        --cov=apps.api \
        --cov-report=html:htmlcov/api_coverage \
        --cov-report=xml:coverage.xml \
        --cov-report=term-missing \
        --cov-fail-under=$COVERAGE_THRESHOLD \
        -v || return 1
    
    print_success "Coverage report generated in htmlcov/api_coverage/"
    
    # Display coverage summary
    coverage report --include="apps/api/*"
}

# Run load tests with Locust
run_load_tests() {
    print_header "Running Load Tests with Locust"
    
    if ! command -v locust &> /dev/null; then
        print_warning "Locust not installed - skipping load tests"
        return 0
    fi
    
    print_status "Starting Locust load test..."
    
    # Run Locust headless for 1 minute with 50 users
    locust -f tests/api/performance/test_load_testing.py \
        --headless \
        --users 50 \
        --spawn-rate 5 \
        --run-time 60s \
        --host http://localhost:8000 \
        --html load_test_report.html \
        || print_warning "Load test completed with some issues"
    
    print_success "Load test report generated: load_test_report.html"
}

# Validate API documentation
validate_api_docs() {
    print_header "Validating API Documentation"
    
    print_status "Validating OpenAPI schema..."
    python manage.py spectacular --validate || return 1
    
    print_status "Generating OpenAPI schema..."
    python manage.py spectacular --file api_schema.yaml
    
    print_success "API documentation validated and schema generated"
}

# Run specific test categories
run_quick_tests() {
    print_header "Running Quick Test Suite"
    
    pytest tests/api/ \
        -m "not slow and not load" \
        --maxfail=5 \
        --tb=short \
        -v
}

run_full_tests() {
    print_header "Running Full Test Suite"
    
    check_dependencies
    setup_test_env
    run_unit_tests
    run_integration_tests
    run_security_tests
    run_e2e_tests
    validate_api_docs
    generate_coverage
}

# Main execution logic
main() {
    local test_type=${1:-"full"}
    local start_time=$(date +%s)
    
    echo -e "${BLUE}🚀 API Test Suite Runner${NC}"
    echo -e "${BLUE}========================${NC}\n"
    
    case $test_type in
        "quick"|"fast")
            run_quick_tests
            ;;
        "unit")
            check_dependencies
            setup_test_env
            run_unit_tests
            ;;
        "integration")
            check_dependencies
            setup_test_env
            run_integration_tests
            ;;
        "performance")
            check_dependencies
            setup_test_env
            run_performance_tests
            ;;
        "load")
            check_dependencies
            setup_test_env
            run_load_tests
            ;;
        "security")
            check_dependencies
            setup_test_env
            run_security_tests
            ;;
        "e2e")
            check_dependencies
            setup_test_env
            run_e2e_tests
            ;;
        "coverage")
            check_dependencies
            setup_test_env
            generate_coverage
            ;;
        "docs")
            validate_api_docs
            ;;
        "full"|"all")
            run_full_tests
            run_performance_tests
            run_load_tests
            ;;
        *)
            echo "Usage: $0 [quick|unit|integration|performance|load|security|e2e|coverage|docs|full]"
            echo ""
            echo "Test types:"
            echo "  quick       - Run fast tests only (excludes slow tests)"
            echo "  unit        - Run unit tests only"
            echo "  integration - Run integration tests only"
            echo "  performance - Run performance benchmarks"
            echo "  load        - Run load tests with Locust"
            echo "  security    - Run security tests"
            echo "  e2e         - Run end-to-end tests"
            echo "  coverage    - Generate coverage report"
            echo "  docs        - Validate API documentation"
            echo "  full        - Run all tests including load tests (default)"
            echo ""
            echo "Examples:"
            echo "  $0 quick          # Fast tests for development"
            echo "  $0 unit           # Unit tests only"
            echo "  $0 full           # Complete test suite"
            exit 1
            ;;
    esac
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $? -eq 0 ]; then
        print_success "All tests completed successfully in ${duration}s! ✨"
        echo ""
        echo -e "${GREEN}🎉 API Test Suite Results:${NC}"
        echo -e "   • Test Type: $test_type"
        echo -e "   • Duration: ${duration}s"
        echo -e "   • Status: PASSED"
        echo ""
        
        if [ -f "htmlcov/api_coverage/index.html" ]; then
            echo -e "${BLUE}📊 Coverage Report:${NC} htmlcov/api_coverage/index.html"
        fi
        
        if [ -f "load_test_report.html" ]; then
            echo -e "${BLUE}⚡ Load Test Report:${NC} load_test_report.html"
        fi
        
        if [ -f "security_report.json" ]; then
            echo -e "${BLUE}🔒 Security Report:${NC} security_report.json"
        fi
        
        exit 0
    else
        print_error "Some tests failed! ❌"
        echo ""
        echo -e "${RED}💥 Test Suite Failed:${NC}"
        echo -e "   • Test Type: $test_type"
        echo -e "   • Duration: ${duration}s"
        echo -e "   • Status: FAILED"
        echo ""
        echo -e "${YELLOW}💡 Tips:${NC}"
        echo -e "   • Run with -v for verbose output"
        echo -e "   • Check logs for specific error details"
        echo -e "   • Try running individual test categories first"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"