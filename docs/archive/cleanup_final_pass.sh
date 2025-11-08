#!/bin/bash

# Final Pass - Move All Remaining Files
# Aggressive cleanup to get root down to essentials

echo "Final Pass: Moving remaining documentation..."
echo "============================================"

# Keep only these in root:
# - CLAUDE.md
# - CHANGELOG.md
# - README.md (if exists)
# - PRE_DEPLOYMENT_CHECKLIST.md
# - REMEDIATION_COMPLETE_REPORT.md
# - ONBOARDING_REMEDIATION_FINAL_SUMMARY.md

# Phase 1: Move all deployment-related files
echo "Phase 1: Moving deployment files..."
mkdir -p docs/deployment
mv DEPLOYMENT_*.md docs/deployment/ 2>/dev/null
mv HOSTINGER_DEPLOYMENT_COMPLETE.md docs/deployment/ 2>/dev/null
echo "  ✓ Moved deployment files"

# Phase 2: Move all datetime-related files
echo "Phase 2: Moving datetime files..."
mkdir -p docs/reference/architecture
mv DATETIME_*.md docs/reference/architecture/ 2>/dev/null
echo "  ✓ Moved datetime files"

# Phase 3: Move all message bus files
echo "Phase 3: Moving message bus files..."
mkdir -p docs/reference/architecture
mv MESSAGE_BUS_*.md docs/reference/architecture/ 2>/dev/null
echo "  ✓ Moved message bus files"

# Phase 4: Move all multi-tenancy files
echo "Phase 4: Moving multi-tenancy files..."
mkdir -p docs/reference/architecture
mv MULTI_TENANCY_*.md docs/reference/architecture/ 2>/dev/null
mv MULTI_ENTITY_ONBOARDING_ARCHITECTURE_RECOMMENDATION.md docs/reference/architecture/ 2>/dev/null
echo "  ✓ Moved multi-tenancy files"

# Phase 5: Move all ML stack files
echo "Phase 5: Moving ML stack files..."
mkdir -p docs/features/ml
mv ML_STACK_*.md docs/features/ml/ 2>/dev/null
mv ML_PHASE2_IMPLEMENTATION_COMPLETE.md docs/features/ml/ 2>/dev/null
echo "  ✓ Moved ML stack files"

# Phase 6: Move all MQTT files
echo "Phase 6: Moving MQTT files..."
mkdir -p docs/deployment/infrastructure
mv MQTT_*.md docs/deployment/infrastructure/ 2>/dev/null
echo "  ✓ Moved MQTT files"

# Phase 7: Move all magic numbers files
echo "Phase 7: Moving magic numbers files..."
mkdir -p docs/reference/optimization
mv MAGIC_NUMBERS_*.md docs/reference/optimization/ 2>/dev/null
echo "  ✓ Moved magic numbers files"

# Phase 8: Move all exception handling files
echo "Phase 8: Moving exception handling files..."
[ -f "EXCEPTION_HANDLING_QUICK_REFERENCE.md" ] && mv EXCEPTION_HANDLING_QUICK_REFERENCE.md docs/quick_reference/
echo "  ✓ Moved exception handling files"

# Phase 9: Move all refactoring completion reports
echo "Phase 9: Moving refactoring reports..."
mkdir -p docs/project-history
mv *_REFACTORING_COMPLETE.md docs/project-history/ 2>/dev/null
echo "  ✓ Moved refactoring reports"

# Phase 10: Move all verification/test reports
echo "Phase 10: Moving verification reports..."
mkdir -p docs/deliverables/quality
mv *_VERIFICATION_REPORT.md docs/deliverables/quality/ 2>/dev/null
mv *_TEST_*.md docs/deliverables/quality/ 2>/dev/null
mv FULL_SYSTEM_TEST_EXECUTION_PLAN.md docs/deliverables/quality/ 2>/dev/null
echo "  ✓ Moved verification reports"

# Phase 11: Move all implementation reports
echo "Phase 11: Moving implementation reports..."
mkdir -p docs/project-history
mv IMPLEMENTATION_*.md docs/project-history/ 2>/dev/null
mv FINAL_AI_FIRST_OPERATIONS_STATUS.md docs/project-history/ 2>/dev/null
mv IMPORT_MIGRATION_REPORT.md docs/project-history/ 2>/dev/null
mv LEGACY_CODE_CLEANUP_COMPLETE.md docs/project-history/ 2>/dev/null
echo "  ✓ Moved implementation reports"

# Phase 12: Move all feature deliverables
echo "Phase 12: Moving feature deliverables..."
mkdir -p docs/deliverables/features
mv FEATURE_*.md docs/deliverables/features/ 2>/dev/null
mv ENHANCEMENT_*.md docs/deliverables/features/ 2>/dev/null
mv HELPDESK_NL_QUERY_IMPLEMENTATION_COMPLETE.md docs/deliverables/features/ 2>/dev/null
mv ENHANCED_HELPDESK_CHATBOT_IMPLEMENTATION.md docs/deliverables/features/ 2>/dev/null
echo "  ✓ Moved feature deliverables"

# Phase 13: Move data utilization
echo "Phase 13: Moving data utilization..."
mkdir -p docs/features/analytics
mv DATA_UTILIZATION_FEATURES_COMPLETE.md docs/features/analytics/ 2>/dev/null
echo "  ✓ Moved data utilization"

# Phase 14: Move documentation files
echo "Phase 14: Moving documentation files..."
mkdir -p docs/project-history
mv DOCUMENTATION_*.md docs/project-history/ 2>/dev/null
echo "  ✓ Moved documentation files"

# Phase 15: Move phase-specific testing files
echo "Phase 15: Moving phase testing files..."
mkdir -p docs/deliverables/quality
mv *_TESTING_PHASE5_COMPLETE.md docs/deliverables/quality/ 2>/dev/null
echo "  ✓ Moved phase testing files"

# Phase 16: Move help center files
echo "Phase 16: Moving help center files..."
mkdir -p docs/features/help_center
mv HELP_CENTER_*.md docs/features/help_center/ 2>/dev/null
echo "  ✓ Moved help center files"

# Phase 17: Move journal files
echo "Phase 17: Moving journal files..."
mkdir -p docs/features/wellness
mv JOURNAL_*.md docs/features/wellness/ 2>/dev/null
echo "  ✓ Moved journal files"

# Phase 18: Move issue tracker files
echo "Phase 18: Moving issue tracker files..."
mkdir -p docs/features/y_helpdesk
mv ISSUE_TRACKER_*.md docs/features/y_helpdesk/ 2>/dev/null
echo "  ✓ Moved issue tracker files"

# Phase 19: Move quick start/reference files
echo "Phase 19: Moving quick reference files..."
mkdir -p docs/quick_reference
mv *_QUICK_START.md docs/quick_reference/ 2>/dev/null
mv *_QUICK_REFERENCE.md docs/quick_reference/ 2>/dev/null
echo "  ✓ Moved quick reference files"

# Phase 20: Move master index files
echo "Phase 20: Moving master index files..."
mkdir -p docs/project-history
mv *_MASTER_INDEX.md docs/project-history/ 2>/dev/null
echo "  ✓ Moved master index files"

# Phase 21: Move operator guides
echo "Phase 21: Moving operator guides..."
mkdir -p docs/operations
mv *_OPERATOR_GUIDE.md docs/operations/ 2>/dev/null
echo "  ✓ Moved operator guides"

# Phase 22: Move NON_NEGOTIABLES files
echo "Phase 22: Moving NON_NEGOTIABLES files..."
mkdir -p docs/operations
mv NON_NEGOTIABLES_*.md docs/operations/ 2>/dev/null
echo "  ✓ Moved NON_NEGOTIABLES files"

# Phase 23: Move ONBOARDING files (except final summary)
echo "Phase 23: Moving onboarding files..."
mkdir -p docs/features/onboarding
mv ONBOARDING_*.md docs/features/onboarding/ 2>/dev/null
# Move back the final summary to root
[ -f "docs/features/onboarding/ONBOARDING_REMEDIATION_FINAL_SUMMARY.md" ] && mv docs/features/onboarding/ONBOARDING_REMEDIATION_FINAL_SUMMARY.md .
echo "  ✓ Moved onboarding files"

# Phase 24: Move PEOPLES files
echo "Phase 24: Moving peoples files..."
mkdir -p docs/features/peoples
mv PEOPLES_*.md docs/features/peoples/ 2>/dev/null
echo "  ✓ Moved peoples files"

# Phase 25: Move REMEDIATION files (except complete report)
echo "Phase 25: Moving remediation files..."
mkdir -p docs/project-history
mv REMEDIATION_*.md docs/project-history/ 2>/dev/null
# Move back the complete report to root
[ -f "docs/project-history/REMEDIATION_COMPLETE_REPORT.md" ] && mv docs/project-history/REMEDIATION_COMPLETE_REPORT.md .
echo "  ✓ Moved remediation files"

# Phase 26: Move REMOVED_CODE and TRANSITIONAL files
echo "Phase 26: Moving code inventory files..."
mkdir -p docs/reference/architecture
mv REMOVED_CODE_*.md docs/reference/architecture/ 2>/dev/null
mv TRANSITIONAL_*.md docs/reference/architecture/ 2>/dev/null
echo "  ✓ Moved code inventory files"

# Phase 27: Move REST_API files
echo "Phase 27: Moving REST API files..."
mkdir -p docs/api
mv REST_API_*.md docs/api/ 2>/dev/null
echo "  ✓ Moved REST API files"

# Phase 28: Move SECURITY files
echo "Phase 28: Moving security files..."
mkdir -p docs/reference/security
mv SECURITY_*.md docs/reference/security/ 2>/dev/null
mv SECURE_*.md docs/reference/security/ 2>/dev/null
echo "  ✓ Moved security files"

# Phase 29: Move remaining completion/progress files
echo "Phase 29: Moving remaining completion files..."
mkdir -p docs/project-history
mv *_COMPLETE.md docs/project-history/ 2>/dev/null
mv *_PROGRESS*.md docs/project-history/ 2>/dev/null
mv *_STATUS*.md docs/project-history/ 2>/dev/null
echo "  ✓ Moved remaining completion files"

# Phase 30: Move GOD_FILE files
echo "Phase 30: Moving god file documents..."
mkdir -p docs/reference/architecture
mv GOD_FILE_*.md docs/reference/architecture/ 2>/dev/null
echo "  ✓ Moved god file documents"

# Phase 31: Clean up cleanup scripts
echo "Phase 31: Archiving cleanup scripts..."
mkdir -p docs/archive
mv cleanup_*.sh docs/archive/ 2>/dev/null
mv consolidate_*.sh docs/archive/ 2>/dev/null
mv organize_*.sh docs/archive/ 2>/dev/null
echo "  ✓ Archived cleanup scripts"

echo ""
echo "============================================"
echo "Final Pass Complete!"
echo ""
echo "Counting remaining files in root..."
ls -1 *.md 2>/dev/null | wc -l
echo ""
echo "Files remaining in root:"
ls -1 *.md 2>/dev/null
echo ""
