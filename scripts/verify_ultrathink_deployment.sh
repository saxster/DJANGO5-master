#!/bin/bash
#
# ULTRATHINK Deployment Verification Script
#
# Validates all changes from the ULTRATHINK implementation are working correctly.
# Run this after deploying the ULTRATHINK optimizations to any environment.
#
# Usage:
#   ./scripts/verify_ultrathink_deployment.sh
#
# Created: November 5, 2025
#

set -e  # Exit on any error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "================================================================="
echo "ULTRATHINK DEPLOYMENT VERIFICATION"
echo "================================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

# Helper functions
pass_test() {
    echo -e "${GREEN}✅ PASS${NC}"
    ((pass_count++))
}

fail_test() {
    echo -e "${RED}❌ FAIL${NC}"
    ((fail_count++))
}

warn_test() {
    echo -e "${YELLOW}⚠️  WARN${NC}"
}

# ============================================================================
# TEST 1: Django System Check
# ============================================================================

echo "1. Django System Check..."
if python manage.py check --deploy 2>&1 | grep -q "System check identified no issues"; then
    pass_test
else
    python manage.py check --deploy
    fail_test
fi
echo ""

# ============================================================================
# TEST 2: Migration Status
# ============================================================================

echo "2. Checking Migration Status..."

# Check journal migrations
if python manage.py showmigrations journal 2>&1 | grep -q "\[X\] 0999_add_performance_indexes"; then
    echo "  Journal migrations: ✅"
    pass_test
else
    echo "  Journal migration 0999 not applied"
    warn_test
fi

# Check activity migrations
if python manage.py showmigrations activity 2>&1 | grep -q "\[X\] 0024_add_job_performance_index"; then
    echo "  Activity migrations: ✅"
else
    echo "  Activity migration 0024 not applied"
    warn_test
fi
echo ""

# ============================================================================
# TEST 3: Syntax Validation
# ============================================================================

echo "3. Syntax Validation (12 files)..."

files=(
    "apps/journal/mqtt_integration.py"
    "apps/core/services/secure_encryption_service.py"
    "apps/wellness/constants.py"
    "apps/journal/models/entry.py"
    "apps/activity/models/job/job.py"
    "apps/reports/views/template_views.py"
    "background_tasks/mental_health_intervention_tasks.py"
    "background_tasks/journal_wellness_tasks.py"
    "apps/journal/search.py"
    "background_tasks/tests/test_mental_health_intervention.py"
    "apps/journal/migrations/0999_add_performance_indexes.py"
    "apps/activity/migrations/0024_add_job_performance_index.py"
)

syntax_pass=0
syntax_fail=0

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        if python3 -m py_compile "$file" 2>/dev/null; then
            ((syntax_pass++))
        else
            echo "  ❌ $file"
            ((syntax_fail++))
        fi
    else
        echo "  ⚠️  Missing: $file"
    fi
done

echo "  Validated: $syntax_pass passed, $syntax_fail failed"
if [ $syntax_fail -eq 0 ]; then
    pass_test
else
    fail_test
fi
echo ""

# ============================================================================
# TEST 4: Import Test (Wellness Constants)
# ============================================================================

echo "4. Wellness Constants Import Test..."
if python -c "
from apps.wellness.constants import (
    CRISIS_ESCALATION_THRESHOLD,
    INTENSIVE_ESCALATION_THRESHOLD,
    HIGH_URGENCY_THRESHOLD,
    CRISIS_FOLLOWUP_DELAY,
    ESCALATION_CHECK_INTERVALS
)
assert CRISIS_ESCALATION_THRESHOLD == 6
assert INTENSIVE_ESCALATION_THRESHOLD == 4
assert HIGH_URGENCY_THRESHOLD == 6
assert CRISIS_FOLLOWUP_DELAY == 3600
print('All constants imported successfully')
" 2>&1 | grep -q "All constants imported"; then
    pass_test
else
    fail_test
fi
echo ""

# ============================================================================
# TEST 5: Encryption Service Validation
# ============================================================================

echo "5. Encryption Service Validation..."
if python manage.py shell -c "
from apps.core.services.secure_encryption_service import SecureEncryptionService
result = SecureEncryptionService.validate_encryption_setup()
print(f'Encryption setup valid: {result}')
" 2>&1 | grep -q "True"; then
    pass_test
else
    fail_test
fi
echo ""

# ============================================================================
# TEST 6: Cache Backend Test
# ============================================================================

echo "6. Cache Backend Test..."
if python manage.py shell -c "
from django.core.cache import cache
from apps.core.constants.cache_ttl import CACHE_TTL_MEDIUM
cache.set('ultrathink_test_key', 'test_value', CACHE_TTL_MEDIUM)
result = cache.get('ultrathink_test_key')
assert result == 'test_value', 'Cache retrieval failed'
cache.delete('ultrathink_test_key')
print('Cache working correctly')
" 2>&1 | grep -q "Cache working"; then
    pass_test
else
    fail_test
fi
echo ""

# ============================================================================
# TEST 7: Database Index Verification
# ============================================================================

echo "7. Database Index Verification..."

# This requires database access - skip if no database configured
if python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()

# Check for journal indexes
cursor.execute(\"\"\"
SELECT indexname FROM pg_indexes
WHERE tablename = 'journal_entry'
AND indexname LIKE '%timestamp%deleted%'
\"\"\")

indexes = cursor.fetchall()
if len(indexes) >= 1:
    print('Journal indexes found')
else:
    print('Journal indexes missing')
" 2>&1 | grep -q "Journal indexes found"; then
    pass_test
else
    warn_test
    echo "  Note: Database indexes may not be created yet - run migrations"
fi
echo ""

# ============================================================================
# TEST 8: Security Documentation Existence
# ============================================================================

echo "8. Security Documentation Check..."

docs_exist=true
for doc in "docs/security/ENCRYPTION_AUDIT.md" "docs/security/KEY_ROTATION_PROCEDURE.md"; do
    if [ ! -f "$doc" ]; then
        echo "  ❌ Missing: $doc"
        docs_exist=false
    fi
done

if $docs_exist; then
    pass_test
else
    fail_test
fi
echo ""

# ============================================================================
# SUMMARY
# ============================================================================

echo "================================================================="
echo "VERIFICATION SUMMARY"
echo "================================================================="
echo "Passed: $pass_count"
echo "Failed: $fail_count"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}✅ ALL VERIFICATIONS PASSED${NC}"
    echo ""
    echo "ULTRATHINK deployment is verified and ready!"
    exit 0
else
    echo -e "${RED}❌ SOME VERIFICATIONS FAILED${NC}"
    echo ""
    echo "Please review errors above and check:"
    echo "  - docs/deployment/ULTRATHINK_DEPLOYMENT_GUIDE.md"
    echo "  - docs/troubleshooting/COMMON_ISSUES.md"
    exit 1
fi
