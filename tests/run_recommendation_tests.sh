#!/bin/bash

# Comprehensive test runner for recommendation system
# This script runs all recommendation system tests with proper organization and reporting

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test directories
UNIT_TESTS_DIR="apps/core/tests/test_recommendation"
INTEGRATION_TESTS_DIR="tests/integration"
PERFORMANCE_TESTS_DIR="tests/performance"
EDGE_CASE_TESTS_DIR="tests/edge_cases"

# Report directory
REPORT_DIR="test_reports"
mkdir -p $REPORT_DIR

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check if pytest is available
check_dependencies() {
    log "Checking test dependencies..."
    
    if ! command -v pytest &> /dev/null; then
        error "pytest is not installed. Please install it with: pip install pytest"
        exit 1
    fi
    
    if ! python -c "import pytest_django" &> /dev/null; then
        error "pytest-django is not installed. Please install it with: pip install pytest-django"
        exit 1
    fi
    
    success "Dependencies check passed"
}

# Run unit tests
run_unit_tests() {
    log "Running unit tests for recommendation system..."
    
    pytest $UNIT_TESTS_DIR \
        -v \
        --tb=short \
        -m "unit or recommendation" \
        --cov=apps.core.recommendation_engine \
        --cov=apps.core.models.recommendation \
        --cov=apps.core.views.recommendation_views \
        --cov=apps.core.middleware.recommendation_middleware \
        --cov-report=html:$REPORT_DIR/unit_coverage \
        --cov-report=xml:$REPORT_DIR/unit_coverage.xml \
        --junit-xml=$REPORT_DIR/unit_tests.xml \
        --durations=10 \
        || {
            error "Unit tests failed"
            return 1
        }
    
    success "Unit tests completed"
}

# Run integration tests
run_integration_tests() {
    log "Running integration tests for recommendation system..."
    
    pytest $INTEGRATION_TESTS_DIR/test_recommendation_integration.py \
           $INTEGRATION_TESTS_DIR/test_realtime_monitoring.py \
        -v \
        --tb=short \
        -m "integration or recommendation" \
        --junit-xml=$REPORT_DIR/integration_tests.xml \
        --durations=10 \
        || {
            error "Integration tests failed"
            return 1
        }
    
    success "Integration tests completed"
}

# Run performance tests
run_performance_tests() {
    log "Running performance tests for recommendation system..."
    
    if [[ "$1" == "--skip-performance" ]]; then
        warning "Skipping performance tests as requested"
        return 0
    fi
    
    pytest $PERFORMANCE_TESTS_DIR/test_recommendation_performance.py \
        -v \
        --tb=short \
        -m "performance or recommendation" \
        --junit-xml=$REPORT_DIR/performance_tests.xml \
        --durations=10 \
        || {
            error "Performance tests failed"
            return 1
        }
    
    success "Performance tests completed"
}

# Run edge case tests
run_edge_case_tests() {
    log "Running edge case tests for recommendation system..."
    
    pytest $EDGE_CASE_TESTS_DIR/test_recommendation_edge_cases.py \
        -v \
        --tb=short \
        -m "edge_case or recommendation" \
        --junit-xml=$REPORT_DIR/edge_case_tests.xml \
        --durations=10 \
        || {
            error "Edge case tests failed"
            return 1
        }
    
    success "Edge case tests completed"
}

# Run specific test suites
run_test_suite() {
    local suite=$1
    
    case $suite in
        "models")
            log "Running model tests..."
            pytest apps/core/tests/test_recommendation/test_models.py -v -m "unit or recommendation"
            ;;
        "engine")
            log "Running engine tests..."
            pytest apps/core/tests/test_recommendation/test_engine.py -v -m "unit or recommendation"
            ;;
        "middleware")
            log "Running middleware tests..."
            pytest apps/core/tests/test_recommendation/test_middleware.py -v -m "unit or recommendation"
            ;;
        "views")
            log "Running view tests..."
            pytest apps/core/tests/test_recommendation/test_views.py -v -m "unit or recommendation"
            ;;
        "commands")
            log "Running management command tests..."
            pytest apps/core/tests/test_recommendation/test_commands.py -v -m "unit or recommendation"
            ;;
        "integration")
            log "Running integration tests..."
            run_integration_tests
            ;;
        "performance")
            log "Running performance tests..."
            run_performance_tests
            ;;
        "edge_cases")
            log "Running edge case tests..."
            run_edge_case_tests
            ;;
        *)
            error "Unknown test suite: $suite"
            echo "Available suites: models, engine, middleware, views, commands, integration, performance, edge_cases"
            exit 1
            ;;
    esac
}

# Generate comprehensive test report
generate_report() {
    log "Generating comprehensive test report..."
    
    cat > $REPORT_DIR/test_summary.md << EOF
# Recommendation System Test Report

Generated on: $(date)

## Test Coverage Summary

### Unit Tests
- **Models**: Testing all recommendation models and their relationships
- **Engine**: Testing recommendation algorithms and business logic
- **Middleware**: Testing recommendation middleware integration
- **Views**: Testing API endpoints and user interfaces
- **Commands**: Testing management commands

### Integration Tests
- **Recommendation Workflows**: End-to-end recommendation generation and delivery
- **Real-time Monitoring**: WebSocket and real-time functionality

### Performance Tests
- **Scalability**: Testing with large datasets
- **Response Times**: API and algorithm performance
- **Memory Usage**: Resource utilization monitoring

### Edge Case Tests
- **Boundary Conditions**: Testing limits and edge scenarios
- **Error Handling**: Exception and error recovery testing
- **Data Integrity**: Validation and consistency checks

## Test Results

Check the following files for detailed results:
- Unit Tests: unit_tests.xml
- Integration Tests: integration_tests.xml
- Performance Tests: performance_tests.xml
- Edge Case Tests: edge_case_tests.xml

## Coverage Reports

- Unit Test Coverage: unit_coverage/index.html
- XML Coverage: unit_coverage.xml

## Next Steps

1. Review any failing tests in the XML reports
2. Check coverage reports for areas needing improvement
3. Run performance tests regularly to monitor degradation
4. Update edge case tests as new scenarios are discovered
EOF

    success "Test report generated at $REPORT_DIR/test_summary.md"
}

# Main execution function
main() {
    log "Starting comprehensive recommendation system test suite"
    
    # Parse command line arguments
    SKIP_PERFORMANCE=false
    TEST_SUITE=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-performance)
                SKIP_PERFORMANCE=true
                shift
                ;;
            --suite)
                TEST_SUITE="$2"
                shift 2
                ;;
            --help|-h)
                cat << EOF
Usage: $0 [OPTIONS]

Options:
    --skip-performance    Skip performance tests (they can be slow)
    --suite SUITE        Run specific test suite (models, engine, middleware, views, commands, integration, performance, edge_cases)
    --help, -h           Show this help message

Examples:
    $0                           # Run all tests
    $0 --skip-performance        # Run all tests except performance tests
    $0 --suite models            # Run only model tests
    $0 --suite integration       # Run only integration tests
EOF
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Check dependencies
    check_dependencies
    
    # If specific suite requested, run only that
    if [[ -n "$TEST_SUITE" ]]; then
        run_test_suite "$TEST_SUITE"
        exit 0
    fi
    
    # Run all test suites
    local failed_tests=()
    
    # Unit tests
    if ! run_unit_tests; then
        failed_tests+=("unit")
    fi
    
    # Integration tests
    if ! run_integration_tests; then
        failed_tests+=("integration")
    fi
    
    # Performance tests (optional)
    if [[ "$SKIP_PERFORMANCE" != true ]]; then
        if ! run_performance_tests; then
            failed_tests+=("performance")
        fi
    fi
    
    # Edge case tests
    if ! run_edge_case_tests; then
        failed_tests+=("edge_case")
    fi
    
    # Generate report
    generate_report
    
    # Summary
    if [[ ${#failed_tests[@]} -eq 0 ]]; then
        success "All recommendation system tests passed! ✅"
        log "View detailed results in $REPORT_DIR/"
        exit 0
    else
        error "The following test suites failed: ${failed_tests[*]}"
        log "Check the detailed reports in $REPORT_DIR/ for more information"
        exit 1
    fi
}

# Run main function with all arguments
main "$@"