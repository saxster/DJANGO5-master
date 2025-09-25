#!/bin/bash

# AI Features Test Execution Script
# Provides convenient commands for running different types of tests

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
AI_COMPONENT="all"
VERBOSE=false
COVERAGE=true
PARALLEL=true
WORKERS=4
OUTPUT_DIR="test_reports"
ENVIRONMENT="local"

# Function to print usage
usage() {
    echo "🧠 AI Features Test Runner"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --type TYPE           Test type: all|unit|integration|performance|security|edge_cases (default: all)"
    echo "  -c, --component COMP      AI component: all|anomaly_detection|behavioral_analytics|face_recognition (default: all)"
    echo "  -v, --verbose             Enable verbose output"
    echo "  -n, --no-coverage         Disable coverage reporting"
    echo "  -s, --sequential          Run tests sequentially (disable parallel execution)"
    echo "  -w, --workers NUM         Number of parallel workers (default: 4)"
    echo "  -o, --output DIR          Output directory for reports (default: test_reports)"
    echo "  -e, --environment ENV     Test environment: local|ci|docker (default: local)"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -t unit -c face_recognition    # Run unit tests for face recognition"
    echo "  $0 -t security --verbose          # Run security tests with verbose output"
    echo "  $0 -t performance -w 8            # Run performance tests with 8 workers"
    echo "  $0 --no-coverage -s               # Run all tests sequentially without coverage"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -c|--component)
            AI_COMPONENT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -n|--no-coverage)
            COVERAGE=false
            shift
            ;;
        -s|--sequential)
            PARALLEL=false
            shift
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

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

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [[ ! -f "manage.py" ]]; then
        print_error "manage.py not found. Please run this script from the project root directory."
        exit 1
    fi
    
    # Check if virtual environment is activated
    if [[ -z "$VIRTUAL_ENV" ]] && [[ -z "$CONDA_DEFAULT_ENV" ]]; then
        print_warning "No virtual environment detected. Please activate your virtual environment."
    fi
    
    # Check Python version
    PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$PYTHON_VERSION < 3.9" | bc -l) -eq 1 ]]; then
        print_error "Python 3.9+ is required. Current version: $PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
}

# Function to setup test environment
setup_environment() {
    print_status "Setting up test environment..."
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Set environment variables
    export TEST_ENVIRONMENT="$ENVIRONMENT"
    export DJANGO_SETTINGS_MODULE="intelliwiz_config.settings_test"
    export PYTHONPATH="${PYTHONPATH}:$(pwd)"
    
    # Mock ML models for testing
    export MOCK_ML_MODELS=true
    export USE_FIXED_RANDOM_SEED=true
    export RANDOM_SEED=42
    
    # Database configuration
    case $ENVIRONMENT in
        "local")
            export DATABASE_URL="sqlite:///test.db"
            export REDIS_URL="redis://localhost:6379/1"
            ;;
        "ci")
            export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost/test_youtility}"
            export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
            ;;
        "docker")
            export DATABASE_URL="postgresql://postgres:postgres@db:5432/test_youtility"
            export REDIS_URL="redis://redis:6379/0"
            ;;
    esac
    
    print_success "Environment configured for $ENVIRONMENT"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing test dependencies..."
    
    # Check if requirements files exist
    if [[ -f "test-requirements.txt" ]]; then
        pip install -r test-requirements.txt
    else
        print_warning "test-requirements.txt not found, installing basic test packages"
        pip install pytest pytest-django pytest-cov pytest-xdist pytest-mock
    fi
    
    # Install additional packages for different test types
    case $TEST_TYPE in
        "performance")
            pip install pytest-benchmark memory-profiler
            ;;
        "security")
            pip install bandit safety semgrep
            ;;
    esac
    
    print_success "Dependencies installed"
}

# Function to prepare test database
prepare_database() {
    print_status "Preparing test database..."
    
    # Run migrations
    python manage.py migrate --settings=intelliwiz_config.settings_test --run-syncdb
    
    # Create test data if needed
    if [[ "$TEST_TYPE" == "integration" ]] || [[ "$TEST_TYPE" == "all" ]]; then
        python manage.py shell --settings=intelliwiz_config.settings_test << 'EOF'
from tests.factories import create_bulk_test_data
print("Creating test data...")
create_bulk_test_data(num_users=20)
print("Test data created successfully")
EOF
    fi
    
    print_success "Database prepared"
}

# Function to build test command
build_test_command() {
    local cmd="python -m pytest"
    local test_path=""
    local markers=""
    
    # Determine test path based on type and component
    case $TEST_TYPE in
        "unit")
            if [[ "$AI_COMPONENT" == "all" ]]; then
                test_path="apps/anomaly_detection/tests apps/behavioral_analytics/tests apps/face_recognition/tests"
                markers="-m 'not integration and not performance and not security'"
            else
                test_path="apps/$AI_COMPONENT/tests"
                markers="-m 'not integration and not performance and not security'"
            fi
            ;;
        "integration")
            test_path="tests/integration"
            markers="-m integration"
            ;;
        "performance")
            test_path="tests/performance"
            markers="-m performance"
            ;;
        "security")
            test_path="tests/security"
            markers="-m security"
            ;;
        "edge_cases")
            test_path="tests/edge_cases"
            ;;
        "all")
            if [[ "$AI_COMPONENT" == "all" ]]; then
                test_path="apps/anomaly_detection/tests apps/behavioral_analytics/tests apps/face_recognition/tests tests/"
            else
                test_path="apps/$AI_COMPONENT/tests tests/"
            fi
            ;;
    esac
    
    # Add test path
    cmd="$cmd $test_path"
    
    # Add markers
    if [[ -n "$markers" ]]; then
        cmd="$cmd $markers"
    fi
    
    # Add coverage options
    if [[ "$COVERAGE" == true ]]; then
        cmd="$cmd --cov=apps.anomaly_detection,apps.behavioral_analytics,apps.face_recognition"
        cmd="$cmd --cov-report=html:$OUTPUT_DIR/htmlcov"
        cmd="$cmd --cov-report=xml:$OUTPUT_DIR/coverage.xml"
        cmd="$cmd --cov-report=term-missing"
    fi
    
    # Add parallel execution
    if [[ "$PARALLEL" == true ]] && [[ "$TEST_TYPE" != "performance" ]]; then
        cmd="$cmd -n $WORKERS"
    fi
    
    # Add output options
    cmd="$cmd --junit-xml=$OUTPUT_DIR/test-results.xml"
    cmd="$cmd --tb=short"
    
    # Add verbose flag
    if [[ "$VERBOSE" == true ]]; then
        cmd="$cmd -v"
    else
        cmd="$cmd -q"
    fi
    
    # Add additional options for specific test types
    case $TEST_TYPE in
        "performance")
            cmd="$cmd --benchmark-only --benchmark-json=$OUTPUT_DIR/benchmark-results.json"
            ;;
        "security")
            cmd="$cmd --disable-warnings"
            ;;
    esac
    
    echo "$cmd"
}

# Function to run additional security scans
run_security_scans() {
    if [[ "$TEST_TYPE" == "security" ]] || [[ "$TEST_TYPE" == "all" ]]; then
        print_status "Running additional security scans..."
        
        # Bandit scan
        print_status "Running Bandit security scan..."
        bandit -r apps/anomaly_detection/ apps/behavioral_analytics/ apps/face_recognition/ \
               -f json -o "$OUTPUT_DIR/bandit-report.json" || true
        
        # Safety scan
        print_status "Running Safety dependency scan..."
        safety check --json --output "$OUTPUT_DIR/safety-report.json" || true
        
        # Generate security summary
        python -c "
import json
import os

reports_dir = '$OUTPUT_DIR'
summary = {'total_issues': 0, 'high_severity': 0, 'tools_run': []}

# Process Bandit results
bandit_file = os.path.join(reports_dir, 'bandit-report.json')
if os.path.exists(bandit_file):
    with open(bandit_file, 'r') as f:
        bandit_data = json.load(f)
        bandit_issues = len(bandit_data.get('results', []))
        high_issues = len([r for r in bandit_data.get('results', []) if r.get('issue_severity') == 'HIGH'])
        summary['total_issues'] += bandit_issues
        summary['high_severity'] += high_issues
        summary['tools_run'].append(f'Bandit: {bandit_issues} issues ({high_issues} high)')

# Process Safety results  
safety_file = os.path.join(reports_dir, 'safety-report.json')
if os.path.exists(safety_file):
    with open(safety_file, 'r') as f:
        safety_data = json.load(f)
        safety_issues = len(safety_data.get('vulnerabilities', []))
        summary['total_issues'] += safety_issues
        summary['tools_run'].append(f'Safety: {safety_issues} vulnerabilities')

# Save summary
with open(os.path.join(reports_dir, 'security-summary.json'), 'w') as f:
    json.dump(summary, f, indent=2)

print(f'Security scan complete: {summary[\"total_issues\"]} total issues found')
"
        
        print_success "Security scans completed"
    fi
}

# Function to generate test report
generate_report() {
    print_status "Generating test report..."
    
    # Create comprehensive report
    cat > "$OUTPUT_DIR/test-summary.txt" << EOF
🧠 AI Features Test Execution Summary
=====================================

Configuration:
- Test Type: $TEST_TYPE
- AI Component: $AI_COMPONENT  
- Environment: $ENVIRONMENT
- Parallel Execution: $PARALLEL
- Workers: $WORKERS
- Coverage Enabled: $COVERAGE
- Timestamp: $(date)

Reports Generated:
- Test Results: $OUTPUT_DIR/test-results.xml
EOF

    if [[ "$COVERAGE" == true ]]; then
        echo "- Coverage Report: $OUTPUT_DIR/htmlcov/index.html" >> "$OUTPUT_DIR/test-summary.txt"
        echo "- Coverage XML: $OUTPUT_DIR/coverage.xml" >> "$OUTPUT_DIR/test-summary.txt"
    fi
    
    if [[ "$TEST_TYPE" == "performance" ]] || [[ "$TEST_TYPE" == "all" ]]; then
        echo "- Performance Benchmarks: $OUTPUT_DIR/benchmark-results.json" >> "$OUTPUT_DIR/test-summary.txt"
    fi
    
    if [[ "$TEST_TYPE" == "security" ]] || [[ "$TEST_TYPE" == "all" ]]; then
        echo "- Security Scans: $OUTPUT_DIR/bandit-report.json, $OUTPUT_DIR/safety-report.json" >> "$OUTPUT_DIR/test-summary.txt"
    fi
    
    print_success "Test report generated: $OUTPUT_DIR/test-summary.txt"
}

# Function to cleanup
cleanup() {
    print_status "Cleaning up..."
    
    # Remove test database if SQLite
    if [[ "$ENVIRONMENT" == "local" ]] && [[ -f "test.db" ]]; then
        rm -f test.db
    fi
    
    # Clean up temporary files
    find /tmp -name "pytest_report_*" -type f -delete 2>/dev/null || true
    find /tmp -name "test_*" -type d -empty -delete 2>/dev/null || true
    
    print_success "Cleanup completed"
}

# Main execution function
main() {
    local start_time=$(date +%s)
    
    echo "🧠 AI Features Test Runner"
    echo "=========================="
    echo ""
    echo "Configuration:"
    echo "- Test Type: $TEST_TYPE"
    echo "- AI Component: $AI_COMPONENT"
    echo "- Environment: $ENVIRONMENT"
    echo "- Parallel: $PARALLEL ($WORKERS workers)"
    echo "- Coverage: $COVERAGE"
    echo "- Output Directory: $OUTPUT_DIR"
    echo ""
    
    # Execute setup steps
    check_prerequisites
    setup_environment
    install_dependencies
    prepare_database
    
    # Build and execute test command
    local test_cmd=$(build_test_command)
    print_status "Executing tests..."
    print_status "Command: $test_cmd"
    echo ""
    
    # Run tests
    if eval "$test_cmd"; then
        print_success "Tests completed successfully"
        local exit_code=0
    else
        print_error "Some tests failed"
        local exit_code=1
    fi
    
    # Run additional scans
    run_security_scans
    
    # Generate reports
    generate_report
    
    # Show execution time
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo "📊 Execution Summary"
    echo "==================="
    echo "Duration: ${duration} seconds"
    echo "Reports available in: $OUTPUT_DIR"
    
    if [[ "$COVERAGE" == true ]]; then
        echo "Coverage report: $OUTPUT_DIR/htmlcov/index.html"
    fi
    
    # Cleanup
    cleanup
    
    exit $exit_code
}

# Trap cleanup on script exit
trap cleanup EXIT

# Run main function
main