#!/bin/bash

# Organize Keeper Files Script
# Moves important reference/documentation files to proper directories

echo "Starting keeper file organization..."
echo "============================================"

# Phase 1: Move to docs/reference/optimization/
echo "Phase 1: Organizing optimization references..."

mkdir -p docs/reference/optimization

[ -f "N1_OPTIMIZATION_QUICK_REFERENCE.md" ] && mv N1_OPTIMIZATION_QUICK_REFERENCE.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_README.md" ] && mv N1_OPTIMIZATION_README.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_QUICK_START.md" ] && mv N1_OPTIMIZATION_QUICK_START.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_EXECUTION_SUMMARY.md" ] && mv N1_OPTIMIZATION_EXECUTION_SUMMARY.md docs/reference/optimization/
[ -f "N_PLUS_ONE_FIXES_PART1_COMPLETE.md" ] && mv N_PLUS_ONE_FIXES_PART1_COMPLETE.md docs/reference/optimization/
[ -f "N_PLUS_ONE_FIXES_SUMMARY.md" ] && mv N_PLUS_ONE_FIXES_SUMMARY.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_COMPLETION_CHECKLIST.md" ] && mv N1_OPTIMIZATION_COMPLETION_CHECKLIST.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_SESSION_COMPLETE.md" ] && mv N1_OPTIMIZATION_SESSION_COMPLETE.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_PART2_DELIVERABLES.md" ] && mv N1_OPTIMIZATION_PART2_DELIVERABLES.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_PART2_SUMMARY.md" ] && mv N1_OPTIMIZATION_PART2_SUMMARY.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_PART3_IMPLEMENTATION.md" ] && mv N1_OPTIMIZATION_PART3_IMPLEMENTATION.md docs/reference/optimization/
[ -f "N1_OPTIMIZATION_ADMIN_REPORT.md" ] && mv N1_OPTIMIZATION_ADMIN_REPORT.md docs/reference/optimization/
[ -f "N1_QUERY_COMPREHENSIVE_OPTIMIZATION_EXECUTION.md" ] && mv N1_QUERY_COMPREHENSIVE_OPTIMIZATION_EXECUTION.md docs/reference/optimization/
[ -f "N1_QUERY_OPTIMIZATION_COMPLETE.md" ] && mv N1_QUERY_OPTIMIZATION_COMPLETE.md docs/reference/optimization/
[ -f "N1_QUERY_OPTIMIZATION_PART2_IMPLEMENTATION.md" ] && mv N1_QUERY_OPTIMIZATION_PART2_IMPLEMENTATION.md docs/reference/optimization/
[ -f "CACHING_OPTIMIZATION_IMPLEMENTATION.md" ] && mv CACHING_OPTIMIZATION_IMPLEMENTATION.md docs/reference/optimization/
[ -f "CACHING_QUICK_REFERENCE.md" ] && mv CACHING_QUICK_REFERENCE.md docs/reference/optimization/
[ -f "CACHING_DEPLOYMENT_CHECKLIST.md" ] && mv CACHING_DEPLOYMENT_CHECKLIST.md docs/reference/optimization/

echo "  ✓ Optimization references organized"

# Phase 2: Move to docs/reference/security/
echo "Phase 2: Organizing security references..."

mkdir -p docs/reference/security

[ -f "CRITICAL_SECURITY_FIX_3_WEBSOCKET_METRICS_AUTH.md" ] && mv CRITICAL_SECURITY_FIX_3_WEBSOCKET_METRICS_AUTH.md docs/reference/security/
[ -f "SECURITY_FIX_3_SUMMARY.md" ] && mv SECURITY_FIX_3_SUMMARY.md docs/reference/security/
[ -f "SECURITY_FIX_3_MANUAL_TEST_PLAN.md" ] && mv SECURITY_FIX_3_MANUAL_TEST_PLAN.md docs/reference/security/
[ -f "SECURITY_FIX_4_SSO_RATE_LIMITING_COMPLETE.md" ] && mv SECURITY_FIX_4_SSO_RATE_LIMITING_COMPLETE.md docs/reference/security/
[ -f "SECURITY_FIX_4_SUMMARY.md" ] && mv SECURITY_FIX_4_SUMMARY.md docs/reference/security/
[ -f "SECURITY_FIX_4_CHECKLIST.md" ] && mv SECURITY_FIX_4_CHECKLIST.md docs/reference/security/
[ -f "SECURE_FILE_DOWNLOAD_REMEDIATION_REPORTS.md" ] && mv SECURE_FILE_DOWNLOAD_REMEDIATION_REPORTS.md docs/reference/security/
[ -f "SECURE_FILE_DOWNLOAD_SUMMARY.md" ] && mv SECURE_FILE_DOWNLOAD_SUMMARY.md docs/reference/security/
[ -f "WORK_ORDER_SECURITY_FIX_COMPLETE.md" ] && mv WORK_ORDER_SECURITY_FIX_COMPLETE.md docs/reference/security/
[ -f "WEBSOCKET_METRICS_AUTH_QUICK_REFERENCE.md" ] && mv WEBSOCKET_METRICS_AUTH_QUICK_REFERENCE.md docs/reference/security/
[ -f "SECURITY_TEST_SUITE_SUMMARY.md" ] && mv SECURITY_TEST_SUITE_SUMMARY.md docs/reference/security/
[ -f "IDOR_SECURITY_TESTS_SUMMARY.md" ] && mv IDOR_SECURITY_TESTS_SUMMARY.md docs/reference/security/
[ -f "IDOR_VULNERABILITY_AUDIT_REPORT.md" ] && mv IDOR_VULNERABILITY_AUDIT_REPORT.md docs/reference/security/
[ -f "IDOR_TESTS_QUICK_START.md" ] && mv IDOR_TESTS_QUICK_START.md docs/reference/security/
[ -f "IDOR_TEST_COVERAGE_REPORT.md" ] && mv IDOR_TEST_COVERAGE_REPORT.md docs/reference/security/

echo "  ✓ Security references organized"

# Phase 3: Move to docs/reference/architecture/
echo "Phase 3: Organizing architecture references..."

mkdir -p docs/reference/architecture

[ -f "CIRCULAR_DEPENDENCY_QUICK_REFERENCE.md" ] && mv CIRCULAR_DEPENDENCY_QUICK_REFERENCE.md docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_PART2_COMPLETE.md" ] && mv EXCEPTION_HANDLING_PART2_COMPLETE.md docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_PART2_VALIDATION.md" ] && mv EXCEPTION_HANDLING_PART2_VALIDATION.md docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_PART3_COMPLETE.md" ] && mv EXCEPTION_HANDLING_PART3_COMPLETE.md docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_PART3_PLAN.md" ] && mv EXCEPTION_HANDLING_PART3_PLAN.md docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_PART3_SUMMARY.txt" ] && mv EXCEPTION_HANDLING_PART3_SUMMARY.txt docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_REMEDIATION_PART1_COMPLETE.md" ] && mv EXCEPTION_HANDLING_REMEDIATION_PART1_COMPLETE.md docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_REMEDIATION_SUMMARY.md" ] && mv EXCEPTION_HANDLING_REMEDIATION_SUMMARY.md docs/reference/architecture/
[ -f "EXCEPTION_HANDLING_DEPLOYMENT_CHECKLIST.md" ] && mv EXCEPTION_HANDLING_DEPLOYMENT_CHECKLIST.md docs/reference/architecture/
[ -f "BLOCKING_IO_SSE_FIX_COMPLETE.md" ] && mv BLOCKING_IO_SSE_FIX_COMPLETE.md docs/reference/architecture/

echo "  ✓ Architecture references organized"

# Phase 4: Move to docs/project-history/
echo "Phase 4: Organizing project history..."

mkdir -p docs/project-history

[ -f "ULTRATHINK_FINAL_COMPLETION_REPORT.md" ] && mv ULTRATHINK_FINAL_COMPLETION_REPORT.md docs/project-history/
[ -f "FINAL_IMPLEMENTATION_STATUS_NOV_6_2025.md" ] && mv FINAL_IMPLEMENTATION_STATUS_NOV_6_2025.md docs/project-history/
[ -f "COMPREHENSIVE_REMEDIATION_PLAN_NOV_2025.md" ] && mv COMPREHENSIVE_REMEDIATION_PLAN_NOV_2025.md docs/project-history/
[ -f "README_ULTRATHINK_REVIEW.md" ] && mv README_ULTRATHINK_REVIEW.md docs/project-history/

echo "  ✓ Project history organized"

# Phase 5: Move to docs/deliverables/quality/
echo "Phase 5: Organizing quality deliverables..."

mkdir -p docs/deliverables/quality

[ -f "SERVICE_LAYER_TESTS_IMPLEMENTATION_SUMMARY.md" ] && mv SERVICE_LAYER_TESTS_IMPLEMENTATION_SUMMARY.md docs/deliverables/quality/
[ -f "TESTING_QUICK_START.md" ] && mv TESTING_QUICK_START.md docs/deliverables/quality/
[ -f "TESTING_KNOWLEDGE_QUICK_START.md" ] && mv TESTING_KNOWLEDGE_QUICK_START.md docs/deliverables/quality/

echo "  ✓ Quality deliverables organized"

# Phase 6: Move to docs/deliverables/infrastructure/
echo "Phase 6: Organizing infrastructure deliverables..."

mkdir -p docs/deliverables/infrastructure

[ -f "MESSAGE_BUS_DEPLOYMENT_CHECKLIST.md" ] && mv MESSAGE_BUS_DEPLOYMENT_CHECKLIST.md docs/deliverables/infrastructure/
[ -f "MULTI_TENANCY_DEPLOYMENT_CHECKLIST.md" ] && mv MULTI_TENANCY_DEPLOYMENT_CHECKLIST.md docs/deliverables/infrastructure/
[ -f "MULTI_TENANCY_HARDENING_IMPLEMENTATION_GUIDE.md" ] && mv MULTI_TENANCY_HARDENING_IMPLEMENTATION_GUIDE.md docs/deliverables/infrastructure/

echo "  ✓ Infrastructure deliverables organized"

# Phase 7: Move specialized feature docs
echo "Phase 7: Organizing specialized documentation..."

[ -f "METER_INTELLIGENCE_PLATFORM.md" ] && mv METER_INTELLIGENCE_PLATFORM.md docs/features/activity/
[ -f "WORKER_PERFORMANCE_ANALYTICS_DESIGN.md" ] && mv WORKER_PERFORMANCE_ANALYTICS_DESIGN.md docs/features/analytics/
[ -f "NATURAL_LANGUAGE_AI_PLATFORM_MASTER_VISION.md" ] && mv NATURAL_LANGUAGE_AI_PLATFORM_MASTER_VISION.md docs/features/noc/
[ -f "NL_QUERY_PLATFORM_EXPANSION_ROADMAP.md" ] && mv NL_QUERY_PLATFORM_EXPANSION_ROADMAP.md docs/features/noc/
[ -f "PREMIUM_FEATURES_QUICK_START.md" ] && mv PREMIUM_FEATURES_QUICK_START.md docs/features/
[ -f "QUICK_START_DEPLOYMENT_GUIDE.md" ] && mv QUICK_START_DEPLOYMENT_GUIDE.md docs/deployment/

echo "  ✓ Specialized documentation organized"

echo ""
echo "============================================"
echo "Keeper File Organization Complete!"
echo "Moved ~60 files to organized directories"
echo ""
