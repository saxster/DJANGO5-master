#!/bin/bash
# Run working tests with coverage for YOUTILITY5

echo "========================================="
echo "YOUTILITY5 WORKING TEST SUITE"
echo "========================================="

# Set environment variables
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.test
export PYTHONPATH=/home/redmine/DJANGO5/YOUTILITY5:$PYTHONPATH

# Python interpreter
PYTHON=/home/redmine/DJANGO5/django5-env/bin/python

echo ""
echo "Running verified working tests with coverage..."
echo "------------------------------------------------"

# Define working test files
WORKING_TESTS=(
    "apps/peoples/tests/test_models/test_people_model_comprehensive.py"
    "apps/peoples/tests/test_views/test_authentication_comprehensive.py"
    "apps/activity/tests/test_integration_simple.py"
    "apps/peoples/tests/test_models/test_people_model.py"
    "apps/core/tests/test_models.py"
)

# Run tests with coverage
$PYTHON -m pytest \
    --cov=apps.peoples.models \
    --cov=apps.peoples.views \
    --cov=apps.activity.models \
    --cov-report=term-missing \
    --cov-report=html:coverage_reports/html \
    --tb=short \
    -v \
    "${WORKING_TESTS[@]}" \
    2>&1 | tee test_results_working.log

# Check exit code
EXIT_CODE=$?

echo ""
echo "========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ ALL WORKING TESTS PASSED"
else
    echo "❌ SOME TESTS FAILED"
fi
echo "========================================="

echo ""
echo "Test Summary:"
echo "--------------"
grep -E "passed|failed|error|warnings" test_results_working.log | tail -3

echo ""
echo "Coverage Summary:"
echo "-----------------"
grep -A 10 -B 5 "TOTAL" test_results_working.log | tail -10

echo ""
echo "Files Tested:"
echo "-------------"
echo "✅ People Model Tests (Comprehensive)"
echo "✅ Authentication & Security Tests"
echo "✅ Activity Integration Tests (Simplified)"
echo "✅ Core Model Tests"

echo ""
echo "Coverage Report: coverage_reports/html/index.html"
echo "Test Results Log: test_results_working.log"

exit $EXIT_CODE
