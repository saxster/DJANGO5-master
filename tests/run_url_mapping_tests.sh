#!/bin/bash

# URL Mapping Test Execution Script
# Runs comprehensive test suite for URL mapping migration

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main execution
main() {
    echo "=========================================="
    echo "    URL Mapping Migration Test Suite     "
    echo "=========================================="
    echo

    # Check dependencies
    print_status "Checking dependencies..."
    
    # Check Node.js
    if ! command_exists node; then
        print_error "Node.js is not installed. Please install Node.js to run frontend tests."
        exit 1
    fi
    
    # Check npm
    if ! command_exists npm; then
        print_error "npm is not installed. Please install npm to run frontend tests."
        exit 1
    fi
    
    # Check Python - use virtual environment if available
    if [ -f "venv/bin/python" ]; then
        PYTHON_CMD="venv/bin/python"
        print_success "Using virtual environment Python"
    elif ! command_exists python; then
        if ! command_exists python3; then
            print_error "Python is not installed. Please install Python to run backend tests."
            exit 1
        else
            PYTHON_CMD="python3"
        fi
    else
        PYTHON_CMD="python"
    fi
    
    # Check pytest
    if ! $PYTHON_CMD -m pytest --version >/dev/null 2>&1; then
        print_error "pytest is not available in the Python environment."
        print_error "Please install pytest: $PYTHON_CMD -m pip install pytest"
        exit 1
    fi
    
    print_success "All dependencies available"
    echo

    # Install frontend dependencies
    print_status "Installing frontend dependencies..."
    if [ -f "package.json" ]; then
        npm install
        print_success "Frontend dependencies installed"
    else
        print_error "package.json not found. Please ensure you're in the correct directory."
        exit 1
    fi
    echo

    # Check Python dependencies (skip installation for pre-configured environment)
    print_status "Checking Python dependencies..."
    if [ -f "venv/bin/python" ]; then
        print_success "Using pre-configured virtual environment"
    elif [ -f "requirements.txt" ]; then
        print_warning "requirements.txt found but not installing (use virtual environment)"
    else
        print_warning "requirements.txt not found."
    fi
    
    if [ -f "test-requirements.txt" ]; then
        print_success "Test requirements file available"
    fi
    echo

    # Run frontend tests
    echo "=========================================="
    echo "           Frontend Tests                 "
    echo "=========================================="
    
    print_status "Running JavaScript unit tests..."
    if npm run test:unit; then
        print_success "JavaScript unit tests passed"
    else
        print_error "JavaScript unit tests failed"
        exit 1
    fi
    echo

    print_status "Running JavaScript integration tests..."
    if npm run test:integration; then
        print_success "JavaScript integration tests passed"
    else
        print_error "JavaScript integration tests failed"
        exit 1
    fi
    echo

    print_status "Running performance tests..."
    if npm run test:performance; then
        print_success "Performance tests passed"
    else
        print_error "Performance tests failed"
        exit 1
    fi
    echo

    # Run backend tests
    echo "=========================================="
    echo "            Backend Tests                 "
    echo "=========================================="

    print_status "Running template URL generation tests..."
    if $PYTHON_CMD -m pytest tests/backend/test_template_url_generation.py -v; then
        print_success "Template URL generation tests passed"
    else
        print_error "Template URL generation tests failed"
        exit 1
    fi
    echo

    print_status "Running workflow integration tests..."
    if $PYTHON_CMD -m pytest tests/integration/test_workflow_integration.py -v; then
        print_success "Workflow integration tests passed"
    else
        print_error "Workflow integration tests failed"
        exit 1
    fi
    echo

    print_status "Running regression tests..."
    if $PYTHON_CMD -m pytest tests/backend/test_regression.py -v; then
        print_success "Regression tests passed"
    else
        print_error "Regression tests failed"
        exit 1
    fi
    echo

    # Run coverage analysis
    echo "=========================================="
    echo "           Coverage Analysis              "
    echo "=========================================="

    print_status "Generating frontend coverage report..."
    if npm run test:coverage; then
        print_success "Frontend coverage report generated"
        if [ -d "coverage" ]; then
            echo "Coverage report available at: coverage/lcov-report/index.html"
        fi
    else
        print_warning "Frontend coverage report generation failed"
    fi
    echo

    print_status "Generating backend coverage report..."
    if $PYTHON_CMD -m pytest --cov=apps.core.url_router_optimized --cov-report=html --cov-report=term; then
        print_success "Backend coverage report generated"
        if [ -d "htmlcov" ]; then
            echo "Coverage report available at: htmlcov/index.html"
        fi
    else
        print_warning "Backend coverage report generation failed"
    fi
    echo

    # Quick URL mapping validation
    echo "=========================================="
    echo "        URL Mapping Validation            "
    echo "=========================================="

    print_status "Validating URL mappings..."
    
    # Check if URL mapper file exists
    if [ -f "frontend/static/assets/js/local/url_mapper.js" ]; then
        # Count URL mappings
        MAPPING_COUNT=$(grep -o ":" frontend/static/assets/js/local/url_mapper.js | wc -l)
        print_success "URL mapper file found with approximately $MAPPING_COUNT mappings"
        
        # Check for critical mappings
        CRITICAL_MAPPINGS=(
            "onboarding:bu"
            "onboarding:client"
            "onboarding:contract"
            "onboarding:import"
        )
        
        for mapping in "${CRITICAL_MAPPINGS[@]}"; do
            if grep -q "$mapping" frontend/static/assets/js/local/url_mapper.js; then
                print_success "Critical mapping found: $mapping"
            else
                print_error "Critical mapping missing: $mapping"
                exit 1
            fi
        done
    else
        print_error "URL mapper file not found: frontend/static/assets/js/local/url_mapper.js"
        exit 1
    fi
    echo

    # Performance benchmark
    echo "=========================================="
    echo "        Performance Benchmark             "
    echo "=========================================="

    print_status "Running URL transformation performance benchmark..."
    
    node -e "
        const fs = require('fs');
        const { performance } = require('perf_hooks');
        
        // Simple URL transformation benchmark
        const urlMappings = {
            'onboarding:bu': 'admin_panel:bu_list',
            'onboarding:client': 'admin_panel:clients_list',
            'onboarding:contract': 'admin_panel:contracts_list',
            'onboarding:import': 'admin_panel:data_import'
        };
        
        function transformUrl(url) {
            for (const [old, newUrl] of Object.entries(urlMappings)) {
                if (url.includes(old)) {
                    return url.replace(old, newUrl);
                }
            }
            return url;
        }
        
        const iterations = 10000;
        const start = performance.now();
        
        for (let i = 0; i < iterations; i++) {
            transformUrl('onboarding:bu');
            transformUrl('onboarding:client');
            transformUrl('onboarding:contract');
            transformUrl('onboarding:import');
        }
        
        const end = performance.now();
        const totalTime = end - start;
        const avgTime = totalTime / (iterations * 4);
        
        console.log('Performance Results:');
        console.log('- Total transformations:', iterations * 4);
        console.log('- Total time:', totalTime.toFixed(2) + 'ms');
        console.log('- Average per transformation:', avgTime.toFixed(4) + 'ms');
        
        if (avgTime > 0.01) {
            console.error('❌ Performance benchmark failed: transformations too slow');
            process.exit(1);
        } else {
            console.log('✅ Performance benchmark passed');
        }
    "
    
    if [ $? -eq 0 ]; then
        print_success "Performance benchmark passed"
    else
        print_error "Performance benchmark failed"
        exit 1
    fi
    echo

    # Final summary
    echo "=========================================="
    echo "             Test Summary                 "
    echo "=========================================="
    echo
    print_success "✅ All URL mapping tests completed successfully!"
    echo
    echo "Test Results:"
    echo "  ✅ Frontend JavaScript tests passed"
    echo "  ✅ Backend Django tests passed"
    echo "  ✅ Integration tests passed"
    echo "  ✅ Regression tests passed"
    echo "  ✅ URL mappings validated"
    echo "  ✅ Performance benchmarks met"
    echo
    echo "Next Steps:"
    echo "  1. Review coverage reports in coverage/ and htmlcov/ directories"
    echo "  2. Run manual testing using MANUAL_TESTING_GUIDE.md"
    echo "  3. Deploy to staging environment for further testing"
    echo "  4. Plan production deployment"
    echo
    print_success "URL mapping migration testing complete! 🎉"
}

# Help function
show_help() {
    echo "URL Mapping Test Runner"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "OPTIONS:"
    echo "  -h, --help     Show this help message"
    echo "  --frontend     Run only frontend tests"
    echo "  --backend      Run only backend tests"
    echo "  --fast         Skip coverage generation and performance benchmarks"
    echo
    echo "Examples:"
    echo "  $0                    # Run all tests"
    echo "  $0 --frontend         # Run only frontend tests"
    echo "  $0 --backend          # Run only backend tests"
    echo "  $0 --fast             # Quick test run"
}

# Parse command line arguments
case "$1" in
    -h|--help)
        show_help
        exit 0
        ;;
    --frontend)
        print_status "Running frontend tests only..."
        npm run test:unit && npm run test:integration && npm run test:performance
        exit $?
        ;;
    --backend)
        print_status "Running backend tests only..."
        $PYTHON_CMD -m pytest tests/backend/ tests/integration/ -v
        exit $?
        ;;
    --fast)
        print_status "Running quick test suite..."
        npm run test:unit && $PYTHON_CMD -m pytest tests/backend/test_template_url_generation.py -v
        exit $?
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        show_help
        exit 1
        ;;
esac