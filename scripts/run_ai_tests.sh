#!/bin/bash

# YOUTILITY5 AI Features Testing Script
# Comprehensive test runner for all AI components

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COVERAGE_DIR="$PROJECT_ROOT/htmlcov"
TEST_RESULTS_DIR="$PROJECT_ROOT/test_results"
LOG_FILE="$TEST_RESULTS_DIR/ai_tests_$(date +%Y%m%d_%H%M%S).log"

# Create directories
mkdir -p "$TEST_RESULTS_DIR"
mkdir -p "$COVERAGE_DIR"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Function to check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check Python version
    python_version=$(python --version 2>&1 | awk '{print $2}')
    print_status "Python version: $python_version"
    
    # Check if virtual environment is activated
    if [[ -z "${VIRTUAL_ENV}" ]]; then
        print_warning "No virtual environment detected. Consider activating one."
    else
        print_status "Virtual environment: $VIRTUAL_ENV"
    fi
    
    # Check if required packages are installed
    print_status "Checking required packages..."
    required_packages=("pytest" "pytest-django" "pytest-cov" "factory-boy")
    
    for package in "${required_packages[@]}"; do
        if pip show "$package" >/dev/null 2>&1; then
            print_status "✓ $package installed"
        else
            print_error "✗ $package not installed"
            return 1
        fi
    done
    
    # Check database connection
    print_status "Checking database connection..."
    cd "$PROJECT_ROOT"
    if python manage.py check --database default >/dev/null 2>&1; then
        print_success "Database connection successful"
    else
        print_error "Database connection failed"
        return 1
    fi
    
    # Check Celery configuration
    print_status "Checking Celery configuration..."
    if python -c "from intelliwiz_config.celery import app; print('Celery configured')" >/dev/null 2>&1; then
        print_success "Celery configuration valid"
    else
        print_warning "Celery configuration issue detected"
    fi
}

# Function to install test dependencies
install_test_dependencies() {
    print_header "Installing Test Dependencies"
    
    cd "$PROJECT_ROOT"
    
    if [[ -f "test-requirements.txt" ]]; then
        print_status "Installing test requirements..."
        pip install -r test-requirements.txt
        print_success "Test dependencies installed"
    else
        print_warning "test-requirements.txt not found, installing basic test packages..."
        pip install pytest pytest-django pytest-cov pytest-mock factory-boy faker freezegun
    fi
}

# Function to run unit tests
run_unit_tests() {
    print_header "Running Unit Tests"
    
    cd "$PROJECT_ROOT"
    
    print_status "Running NLP Engine unit tests..."
    pytest apps/nlp_engine/tests/test_models/ \
           apps/nlp_engine/tests/test_engines/ \
           -v -m "unit or nlp" \
           --cov=apps.nlp_engine \
           --cov-report=html:$COVERAGE_DIR/nlp_unit \
           --junit-xml=$TEST_RESULTS_DIR/nlp_unit_results.xml \
           | tee -a "$LOG_FILE"
    
    print_status "Running Insights Engine unit tests..."
    pytest apps/insights_engine/tests/test_models/ \
           apps/insights_engine/tests/test_engines/ \
           -v -m "unit or insights" \
           --cov=apps.insights_engine \
           --cov-report=html:$COVERAGE_DIR/insights_unit \
           --junit-xml=$TEST_RESULTS_DIR/insights_unit_results.xml \
           | tee -a "$LOG_FILE"
    
    print_status "Running Quality Assurance unit tests..."
    pytest apps/quality_assurance/tests/test_models/ \
           apps/quality_assurance/tests/test_engines/ \
           -v -m "unit or quality" \
           --cov=apps.quality_assurance \
           --cov-report=html:$COVERAGE_DIR/quality_unit \
           --junit-xml=$TEST_RESULTS_DIR/quality_unit_results.xml \
           | tee -a "$LOG_FILE"
    
    print_status "Running AI Core unit tests..."
    pytest apps/ai_core/tests/test_models/ \
           apps/ai_core/tests/test_tasks/ \
           -v -m "unit or ai_core" \
           --cov=apps.ai_core \
           --cov-report=html:$COVERAGE_DIR/ai_core_unit \
           --junit-xml=$TEST_RESULTS_DIR/ai_core_unit_results.xml \
           | tee -a "$LOG_FILE"
    
    print_success "Unit tests completed"
}

# Function to run integration tests
run_integration_tests() {
    print_header "Running Integration Tests"
    
    cd "$PROJECT_ROOT"
    
    print_status "Running AI workflow integration tests..."
    pytest apps/ai_core/tests/test_integration/ \
           -v -m "integration" \
           --cov=apps.nlp_engine,apps.insights_engine,apps.quality_assurance,apps.ai_core \
           --cov-report=html:$COVERAGE_DIR/integration \
           --junit-xml=$TEST_RESULTS_DIR/integration_results.xml \
           | tee -a "$LOG_FILE"
    
    print_success "Integration tests completed"
}

# Function to run task tests
run_task_tests() {
    print_header "Running Celery Task Tests"
    
    cd "$PROJECT_ROOT"
    
    print_status "Running async task tests..."
    pytest apps/nlp_engine/tests/test_tasks/ \
           apps/insights_engine/tests/test_tasks/ \
           apps/quality_assurance/tests/test_tasks/ \
           apps/ai_core/tests/test_tasks/ \
           -v -m "celery" \
           --cov=apps.nlp_engine.tasks,apps.insights_engine.tasks,apps.quality_assurance.tasks,apps.ai_core.tasks \
           --cov-report=html:$COVERAGE_DIR/tasks \
           --junit-xml=$TEST_RESULTS_DIR/task_results.xml \
           | tee -a "$LOG_FILE"
    
    print_success "Task tests completed"
}

# Function to run view tests
run_view_tests() {
    print_header "Running View Tests"
    
    cd "$PROJECT_ROOT"
    
    print_status "Running AI view tests..."
    pytest apps/nlp_engine/tests/test_views/ \
           apps/insights_engine/tests/test_views/ \
           apps/quality_assurance/tests/test_views/ \
           apps/ai_core/tests/test_views/ \
           -v \
           --cov=apps.nlp_engine.views,apps.insights_engine.views,apps.quality_assurance.views,apps.ai_core.views \
           --cov-report=html:$COVERAGE_DIR/views \
           --junit-xml=$TEST_RESULTS_DIR/view_results.xml \
           | tee -a "$LOG_FILE"
    
    print_success "View tests completed"
}

# Function to run performance tests
run_performance_tests() {
    print_header "Running Performance Tests"
    
    cd "$PROJECT_ROOT"
    
    print_status "Running AI performance benchmarks..."
    pytest apps/nlp_engine/tests/ \
           apps/insights_engine/tests/ \
           apps/quality_assurance/tests/ \
           apps/ai_core/tests/ \
           -v -m "performance" \
           --benchmark-only \
           --benchmark-json=$TEST_RESULTS_DIR/benchmark_results.json \
           | tee -a "$LOG_FILE"
    
    print_success "Performance tests completed"
}

# Function to run security tests
run_security_tests() {
    print_header "Running Security Tests"
    
    cd "$PROJECT_ROOT"
    
    print_status "Running AI security tests..."
    pytest apps/nlp_engine/tests/ \
           apps/insights_engine/tests/ \
           apps/quality_assurance/tests/ \
           apps/ai_core/tests/ \
           -v -m "security" \
           --junit-xml=$TEST_RESULTS_DIR/security_results.xml \
           | tee -a "$LOG_FILE"
    
    print_status "Running security scan with bandit..."
    bandit -r apps/nlp_engine/ apps/insights_engine/ apps/quality_assurance/ apps/ai_core/ \
           -f json -o "$TEST_RESULTS_DIR/bandit_security_report.json" || true
    
    print_status "Running dependency security scan..."
    safety check --json --output "$TEST_RESULTS_DIR/safety_report.json" || true
    
    print_success "Security tests completed"
}

# Function to generate comprehensive coverage report
generate_coverage_report() {
    print_header "Generating Coverage Report"
    
    cd "$PROJECT_ROOT"
    
    print_status "Running complete test suite with coverage..."
    pytest apps/nlp_engine/tests/ \
           apps/insights_engine/tests/ \
           apps/quality_assurance/tests/ \
           apps/ai_core/tests/ \
           --cov=apps.nlp_engine \
           --cov=apps.insights_engine \
           --cov=apps.quality_assurance \
           --cov=apps.ai_core \
           --cov-report=html:$COVERAGE_DIR/complete \
           --cov-report=xml:$TEST_RESULTS_DIR/coverage.xml \
           --cov-report=term-missing \
           --junit-xml=$TEST_RESULTS_DIR/complete_results.xml \
           | tee -a "$LOG_FILE"
    
    print_success "Coverage report generated at $COVERAGE_DIR/complete/index.html"
}

# Function to generate test summary
generate_test_summary() {
    print_header "Generating Test Summary"
    
    cd "$PROJECT_ROOT"
    
    summary_file="$TEST_RESULTS_DIR/test_summary.md"
    
    cat > "$summary_file" << EOF
# AI Features Test Summary

**Test Run Date:** $(date)
**Project:** YOUTILITY5 AI Features
**Test Environment:** $(python --version 2>&1)

## Test Results Summary

### Coverage Results
- **NLP Engine Coverage:** Available in htmlcov/nlp_unit/
- **Insights Engine Coverage:** Available in htmlcov/insights_unit/
- **Quality Assurance Coverage:** Available in htmlcov/quality_unit/
- **AI Core Coverage:** Available in htmlcov/ai_core_unit/
- **Complete Coverage:** Available in htmlcov/complete/

### Test Result Files
- **Unit Test Results:** Generated in test_results/
- **Integration Test Results:** integration_results.xml
- **Performance Benchmarks:** benchmark_results.json
- **Security Scan Results:** bandit_security_report.json, safety_report.json

### Log Files
- **Complete Test Log:** $LOG_FILE

## Test Categories Executed

1. **Unit Tests** - Individual component testing
2. **Integration Tests** - Cross-component workflow testing
3. **Task Tests** - Celery async task testing
4. **View Tests** - API and view endpoint testing
5. **Performance Tests** - Benchmark and load testing
6. **Security Tests** - Security vulnerability testing

## Next Steps

1. Review coverage reports for any gaps
2. Address any failing tests
3. Optimize performance based on benchmark results
4. Address security findings if any
5. Consider adding more edge case tests

## AI Features Tested

### NLP Engine (Feature 6)
- Sentiment analysis
- Urgency detection
- Category prediction
- Keyword extraction
- Named entity recognition
- Language detection
- Intelligent routing

### Insights Engine (Feature 8)
- Trend analysis
- Anomaly detection
- Report enhancement
- Automated insights generation
- Performance metrics analysis

### Quality Assurance Engine (Feature 10)
- Quality scoring algorithms
- Compliance rule evaluation
- Alert generation
- Quality trend analysis
- Image quality assessment

### AI Core
- Task coordination
- Model initialization
- Performance monitoring
- Error handling
- Cross-engine integration

EOF
    
    print_success "Test summary generated at $summary_file"
}

# Function to cleanup test artifacts
cleanup_test_artifacts() {
    print_status "Cleaning up temporary test files..."
    
    # Remove __pycache__ directories
    find "$PROJECT_ROOT" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Remove .pyc files
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true
    
    print_success "Test cleanup completed"
}

# Main execution function
main() {
    print_header "YOUTILITY5 AI Features Test Suite"
    print_status "Starting comprehensive AI testing process..."
    print_status "Results will be saved to: $TEST_RESULTS_DIR"
    print_status "Logs will be saved to: $LOG_FILE"
    
    # Start logging
    echo "AI Test Suite started at $(date)" > "$LOG_FILE"
    
    # Parse command line arguments
    run_all=true
    run_unit=false
    run_integration=false
    run_tasks=false
    run_views=false
    run_performance=false
    run_security=false
    install_deps=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --unit)
                run_all=false
                run_unit=true
                shift
                ;;
            --integration)
                run_all=false
                run_integration=true
                shift
                ;;
            --tasks)
                run_all=false
                run_tasks=true
                shift
                ;;
            --views)
                run_all=false
                run_views=true
                shift
                ;;
            --performance)
                run_all=false
                run_performance=true
                shift
                ;;
            --security)
                run_all=false
                run_security=true
                shift
                ;;
            --install-deps)
                install_deps=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --unit           Run only unit tests"
                echo "  --integration    Run only integration tests"
                echo "  --tasks          Run only task tests"
                echo "  --views          Run only view tests"
                echo "  --performance    Run only performance tests"
                echo "  --security       Run only security tests"
                echo "  --install-deps   Install test dependencies"
                echo "  --help           Show this help message"
                echo ""
                echo "If no specific test type is specified, all tests will be run."
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Install dependencies if requested
    if [[ "$install_deps" == true ]]; then
        install_test_dependencies
    fi
    
    # Check prerequisites
    if ! check_prerequisites; then
        print_error "Prerequisites check failed. Please fix issues and try again."
        exit 1
    fi
    
    # Run selected tests
    if [[ "$run_all" == true ]]; then
        run_unit_tests
        run_integration_tests
        run_task_tests
        run_view_tests
        run_performance_tests
        run_security_tests
        generate_coverage_report
    else
        [[ "$run_unit" == true ]] && run_unit_tests
        [[ "$run_integration" == true ]] && run_integration_tests
        [[ "$run_tasks" == true ]] && run_task_tests
        [[ "$run_views" == true ]] && run_views_tests
        [[ "$run_performance" == true ]] && run_performance_tests
        [[ "$run_security" == true ]] && run_security_tests
    fi
    
    # Generate summary and cleanup
    generate_test_summary
    cleanup_test_artifacts
    
    print_header "Test Suite Completed"
    print_success "All AI tests completed successfully!"
    print_status "Check the following locations for results:"
    print_status "  - Test Results: $TEST_RESULTS_DIR"
    print_status "  - Coverage Reports: $COVERAGE_DIR"
    print_status "  - Complete Log: $LOG_FILE"
    
    echo "Test suite completed at $(date)" >> "$LOG_FILE"
}

# Execute main function with all arguments
main "$@"