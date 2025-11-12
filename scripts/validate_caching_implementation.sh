#!/bin/bash
# Validation script for caching implementation
# Run this to verify all components are properly installed

echo "=================================================="
echo "Caching Implementation Validation"
echo "=================================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track validation status
ERRORS=0
WARNINGS=0

# Function to check file exists
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
    else
        echo -e "${RED}✗${NC} $1 (missing)"
        ((ERRORS++))
    fi
}

# Function to validate Python syntax
check_syntax() {
    if python3 -m py_compile "$1" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $1 syntax OK"
    else
        echo -e "${RED}✗${NC} $1 syntax error"
        ((ERRORS++))
    fi
}

echo "1. Checking Core Files..."
echo "----------------------------"
check_file "apps/core/utils_new/cache_utils.py"
check_file "apps/core/middleware/cache_monitoring.py"
check_file "apps/reports/services/dashboard_cache_service.py"
check_file "apps/peoples/services/permission_cache_service.py"
check_file "apps/reports/views/dashboard_cached_views.py"
check_file "scripts/optimize_count_to_exists.py"
echo ""

echo "2. Validating Python Syntax..."
echo "----------------------------"
check_syntax "apps/core/utils_new/cache_utils.py"
check_syntax "apps/core/middleware/cache_monitoring.py"
check_syntax "apps/reports/services/dashboard_cache_service.py"
check_syntax "apps/peoples/services/permission_cache_service.py"
check_syntax "apps/reports/views/dashboard_cached_views.py"
check_syntax "scripts/optimize_count_to_exists.py"
echo ""

echo "3. Checking Documentation..."
echo "----------------------------"
check_file "CACHING_OPTIMIZATION_IMPLEMENTATION.md"
check_file "CACHING_QUICK_REFERENCE.md"
check_file "TASK_2_5_2_6_COMPLETE.md"
echo ""

echo "4. Checking Redis Configuration..."
echo "----------------------------"
if grep -q "OPTIMIZED_CACHES" intelliwiz_config/settings/redis_optimized.py; then
    echo -e "${GREEN}✓${NC} Redis configuration present"
else
    echo -e "${YELLOW}⚠${NC} Redis configuration may be missing"
    ((WARNINGS++))
fi
echo ""

echo "5. Testing Cache Import..."
echo "----------------------------"
python3 -c "from apps.core.utils_new.cache_utils import cache_result, get_cache_stats; print('✓ Cache utils imports OK')" 2>/dev/null && \
    echo -e "${GREEN}✓${NC} Cache utilities importable" || \
    (echo -e "${RED}✗${NC} Cache utilities import failed" && ((ERRORS++)))
echo ""

echo "6. Checking for Inefficient Patterns..."
echo "----------------------------"
COUNT_PATTERNS=$(grep -r "\.count() >" apps/core/views apps/reports/views 2>/dev/null | grep -v "# OK" | wc -l)
if [ "$COUNT_PATTERNS" -le 2 ]; then
    echo -e "${GREEN}✓${NC} Minimal inefficient count() patterns found ($COUNT_PATTERNS)"
else
    echo -e "${YELLOW}⚠${NC} Found $COUNT_PATTERNS inefficient count() patterns"
    echo "  Run: python scripts/optimize_count_to_exists.py --dry-run"
    ((WARNINGS++))
fi
echo ""

echo "7. Checking Code Statistics..."
echo "----------------------------"
TOTAL_LINES=$(wc -l apps/core/utils_new/cache_utils.py \
    apps/core/middleware/cache_monitoring.py \
    apps/reports/services/dashboard_cache_service.py \
    apps/peoples/services/permission_cache_service.py 2>/dev/null | tail -1 | awk '{print $1}')

if [ -n "$TOTAL_LINES" ] && [ "$TOTAL_LINES" -gt 700 ]; then
    echo -e "${GREEN}✓${NC} Total implementation: $TOTAL_LINES lines"
else
    echo -e "${YELLOW}⚠${NC} Implementation may be incomplete"
    ((WARNINGS++))
fi
echo ""

echo "=================================================="
echo "Validation Summary"
echo "=================================================="
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Enable CacheMonitoringMiddleware in settings"
    echo "2. Run: python scripts/optimize_count_to_exists.py"
    echo "3. Monitor cache performance for 1 week"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Validation completed with $WARNINGS warning(s)${NC}"
    echo ""
    echo "Review warnings above and address if needed."
    exit 0
else
    echo -e "${RED}✗ Validation failed with $ERRORS error(s) and $WARNINGS warning(s)${NC}"
    echo ""
    echo "Please fix errors above before proceeding."
    exit 1
fi
