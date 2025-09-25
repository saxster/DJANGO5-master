#!/bin/bash
# Run all tests with coverage for YOUTILITY5

echo "========================================="
echo "YOUTILITY5 TEST SUITE"
echo "========================================="

# Set environment variables
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings
export PYTHONPATH=/home/redmine/DJANGO5/YOUTILITY5:$PYTHONPATH

# Python interpreter
PYTHON=/home/redmine/DJANGO5/django5-env/bin/python

echo ""
echo "Running tests with coverage..."
echo "-----------------------------------------"

# Run tests with coverage
$PYTHON -m pytest \
    --cov=apps \
    --cov-report=term-missing \
    --cov-report=html:coverage_reports/html \
    --tb=short \
    -v \
    apps/peoples/tests/test_models/test_people_model_comprehensive.py \
    apps/peoples/tests/test_views/test_authentication_comprehensive.py \
    apps/activity/tests/test_integration_workflows.py \
    2>&1 | tee test_results.log

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "✅ TESTS PASSED"
    echo "========================================="
    echo ""
    echo "Coverage report available at: coverage_reports/html/index.html"
else
    echo ""
    echo "========================================="
    echo "❌ TESTS FAILED"
    echo "========================================="
    echo ""
    echo "Check test_results.log for details"
fi

echo ""
echo "Test Summary:"
echo "--------------"
grep -E "passed|failed|error" test_results.log | tail -1

echo ""
echo "Coverage Summary:"
echo "-----------------"
grep -E "TOTAL" test_results.log | tail -1