#!/bin/bash

# Final Aggressive Cleanup Script
# Removes remaining completion reports and moves reference docs

echo "Starting final aggressive cleanup..."
echo "============================================"

# Phase 1: Delete agent/batch completion reports
echo "Phase 1: Removing agent/batch reports..."
rm -f AGENT_*.md
rm -f AGENT*.md
rm -f BATCH_*.md
rm -f BATCH*.md
echo "  ✓ Removed agent/batch reports"

# Phase 2: Delete activity-specific completion reports
echo "Phase 2: Removing activity completion reports..."
rm -f ACTIVITY_APP_TESTING_PHASE5_COMPLETE.md
rm -f ACTIVITY_MODELS_JOB_REFACTORING_COMPLETE.md
rm -f ACTIVITY_FINAL_COMPLETION.md
rm -f ACTIVITY_JOB_MODELS_REFACTORING_COMPLETE.md
echo "  ✓ Removed activity completion reports"

# Phase 3: Move activity references to docs
echo "Phase 3: Moving activity references..."
mkdir -p docs/features/activity
[ -f "ACTIVITY_JOB_MODELS_QUICK_REFERENCE.md" ] && mv ACTIVITY_JOB_MODELS_QUICK_REFERENCE.md docs/features/activity/
[ -f "ACTIVITY_MODELS_QUICK_REFERENCE.md" ] && mv ACTIVITY_MODELS_QUICK_REFERENCE.md docs/features/activity/
echo "  ✓ Moved activity references"

# Phase 4: Move attendance references to docs
echo "Phase 4: Moving attendance references..."
mkdir -p docs/features/attendance
[ -f "ATTENDANCE_MODELS_QUICK_REFERENCE.md" ] && mv ATTENDANCE_MODELS_QUICK_REFERENCE.md docs/features/attendance/
[ -f "ATTENDANCE_INTEGRATION_GUIDE.md" ] && mv ATTENDANCE_INTEGRATION_GUIDE.md docs/features/attendance/
[ -f "ATTENDANCE_FINAL_CORRECTED_SUMMARY.md" ] && mv ATTENDANCE_FINAL_CORRECTED_SUMMARY.md docs/features/attendance/
echo "  ✓ Moved attendance references"

# Phase 5: Delete AI/ML completion reports
echo "Phase 5: Removing AI/ML completion reports..."
rm -f AI_FIRST_OPERATIONS_COMPLETE_SUMMARY.md
rm -f AI_ML_MODELS_REFACTORING_COMPLETE.md
rm -f COMPLETE_AI_FIRST_OPERATIONS_FINAL.md
echo "  ✓ Removed AI/ML completion reports"

# Phase 6: Move AI/ML references to docs
echo "Phase 6: Moving AI/ML references..."
mkdir -p docs/features/ml
[ -f "AI_ML_MODELS_STRUCTURE.md" ] && mv AI_ML_MODELS_STRUCTURE.md docs/features/ml/
echo "  ✓ Moved AI/ML references"

# Phase 7: Move alert/NOC references
echo "Phase 7: Moving alert/NOC references..."
mkdir -p docs/features/noc
[ -f "ALERT_CLUSTERING_IMPLEMENTATION_REPORT.md" ] && mv ALERT_CLUSTERING_IMPLEMENTATION_REPORT.md docs/features/noc/
[ -f "ALERT_CLUSTERING_QUICK_START.md" ] && mv ALERT_CLUSTERING_QUICK_START.md docs/features/noc/
echo "  ✓ Moved alert/NOC references"

# Phase 8: Delete complete/final summaries
echo "Phase 8: Removing generic completion summaries..."
rm -f COMPLETE_IMPLEMENTATION_DELIVERABLES_FINAL.md
rm -f COMPLETE_SESSION_MASTER_INDEX.md
rm -f CONFIGURATION_CLEANUP_VERIFICATION.md
echo "  ✓ Removed generic completion summaries"

# Phase 9: Move constants/datetime references
echo "Phase 9: Moving constants references..."
mkdir -p docs/reference/architecture
[ -f "CONSTANTS_QUICK_REFERENCE.md" ] && mv CONSTANTS_QUICK_REFERENCE.md docs/reference/architecture/
[ -f "DATETIME_CONSTANTS_FILES_MODIFIED.md" ] && mv DATETIME_CONSTANTS_FILES_MODIFIED.md docs/reference/architecture/
[ -f "DATETIME_TRANSITION_REPORT.md" ] && mv DATETIME_TRANSITION_REPORT.md docs/reference/architecture/
echo "  ✓ Moved constants references"

# Phase 10: Move infrastructure guides
echo "Phase 10: Moving infrastructure guides..."
mkdir -p docs/deployment/infrastructure
[ -f "ALTERNATIVE_MQTT_SETUP.md" ] && mv ALTERNATIVE_MQTT_SETUP.md docs/deployment/infrastructure/
[ -f "AJAX_ENDPOINTS_MIGRATION_PLAN.md" ] && mv AJAX_ENDPOINTS_MIGRATION_PLAN.md docs/deployment/infrastructure/
echo "  ✓ Moved infrastructure guides"

# Phase 11: Delete bounded contexts pivot report (superseded)
echo "Phase 11: Removing superseded architecture reports..."
rm -f BOUNDED_CONTEXTS_PIVOT_REPORT.md
rm -f FLAKE8_ADOPTION_STRATEGY.md
rm -f FORMS_REFACTORING_IMPLEMENTATION.md
rm -f DEPENDENCY_MANAGEMENT_OPTIMIZATION.md
rm -f DJANGO_ADMIN_CUSTOMIZATION_GUIDE.md
echo "  ✓ Removed superseded architecture reports"

# Phase 12: Delete framework/library specific completions
echo "Phase 12: Removing framework completion reports..."
rm -f DOCKER_IMPLEMENTATION_COMPLETE.md
rm -f FRAPPE_INTEGRATION_IMPLEMENTATION.md
rm -f FRAPPE_INTEGRATION_VALIDATION.md
rm -f GRAPHQL_ENDPOINTS_REMOVAL_COMPLETE.md
rm -f INSTALL_BLEACH.md
echo "  ✓ Removed framework completion reports"

# Phase 13: Delete face recognition completions
echo "Phase 13: Removing face recognition completion reports..."
rm -f FACE_RECOGNITION_COMPLETE.md
rm -f FACE_RECOGNITION_FINAL_COMPREHENSIVE_REPORT.md
rm -f FACE_RECOGNITION_IMPLEMENTATION_COMPLETE.md
rm -f FACE_RECOGNITION_PHASE3_COMPLETE.md
echo "  ✓ Removed face recognition completion reports"

# Phase 14: Delete helpbot completions
echo "Phase 14: Removing helpbot completion reports..."
rm -f HELPBOT_COMPLETE_IMPLEMENTATION.md
rm -f HELPBOT_FINAL_COMPREHENSIVE_REPORT.md
rm -f HELPBOT_IMPLEMENTATION_COMPLETE.md
echo "  ✓ Removed helpbot completion reports"

# Phase 15: Delete issue tracker completions
echo "Phase 15: Removing issue tracker completion reports..."
rm -f ISSUE_TRACKER_COMPLETE.md
rm -f ISSUE_TRACKER_FINAL_COMPREHENSIVE_REPORT.md
rm -f ISSUE_TRACKER_IMPLEMENTATION_COMPLETE.md
echo "  ✓ Removed issue tracker completion reports"

# Phase 16: Delete journal/wellness completions
echo "Phase 16: Removing journal/wellness completion reports..."
rm -f JOURNAL_COMPLETE.md
rm -f JOURNAL_FINAL_COMPREHENSIVE_REPORT.md
rm -f JOURNAL_IMPLEMENTATION_COMPLETE.md
rm -f MENTAL_HEALTH_INTEGRATION_COMPLETE.md
echo "  ✓ Removed journal/wellness completion reports"

# Phase 17: Delete ML/training completions
echo "Phase 17: Removing ML training completion reports..."
rm -f ML_TRAINING_COMPLETE.md
rm -f ML_TRAINING_FINAL_COMPREHENSIVE_REPORT.md
rm -f ML_TRAINING_IMPLEMENTATION_COMPLETE.md
rm -f ML_TESTS_VALIDATION_CHECKLIST.md
echo "  ✓ Removed ML training completion reports"

# Phase 18: Delete MQTT completions
echo "Phase 18: Removing MQTT completion reports..."
rm -f MOSQUITTO_SETUP_GUIDE.md
rm -f MQTT_PIPELINE_TESTING_GUIDE.md
rm -f MQTT_IMPLEMENTATION_COMPLETE.md
echo "  ✓ Removed MQTT completion reports"

# Phase 19: Delete NOC completions (keeping quick references)
echo "Phase 19: Removing NOC completion reports..."
rm -f NOC_AIOPS_ENHANCEMENTS_MASTER_PLAN.md
rm -f NOC_COMPLETE.md
rm -f NOC_FINAL_COMPREHENSIVE_REPORT.md
rm -f NOC_IMPLEMENTATION_COMPLETE.md
rm -f NOC_STREAMLAB_COMPLETE.md
echo "  ✓ Removed NOC completion reports"

# Phase 20: Delete onboarding completions
echo "Phase 20: Removing onboarding completion reports..."
rm -f ONBOARDING_COMPLETE.md
rm -f ONBOARDING_FINAL_COMPREHENSIVE_REPORT.md
rm -f ONBOARDING_IMPLEMENTATION_COMPLETE.md
rm -f ONBOARDING_API_COMPLETE.md
echo "  ✓ Removed onboarding completion reports"

# Phase 21: Delete peoples completions
echo "Phase 21: Removing peoples completion reports..."
rm -f PEOPLES_COMPLETE.md
rm -f PEOPLES_FINAL_COMPREHENSIVE_REPORT.md
rm -f PEOPLES_IMPLEMENTATION_COMPLETE.md
rm -f PEOPLES_MODELS_REFACTORING_COMPLETE.md
echo "  ✓ Removed peoples completion reports"

# Phase 22: Delete reports completions
echo "Phase 22: Removing reports completion reports..."
rm -f REPORTS_COMPLETE.md
rm -f REPORTS_FINAL_COMPREHENSIVE_REPORT.md
rm -f REPORTS_IMPLEMENTATION_COMPLETE.md
echo "  ✓ Removed reports completion reports"

# Phase 23: Delete scheduler completions
echo "Phase 23: Removing scheduler completion reports..."
rm -f SCHEDULER_COMPLETE.md
rm -f SCHEDULER_FINAL_COMPREHENSIVE_REPORT.md
rm -f SCHEDULER_IMPLEMENTATION_COMPLETE.md
rm -f SCHEDULER_MODELS_REFACTORING_COMPLETE.md
echo "  ✓ Removed scheduler completion reports"

# Phase 24: Delete search completions
echo "Phase 24: Removing search completion reports..."
rm -f SEARCH_COMPLETE.md
rm -f SEARCH_FINAL_COMPREHENSIVE_REPORT.md
rm -f SEARCH_IMPLEMENTATION_COMPLETE.md
echo "  ✓ Removed search completion reports"

# Phase 25: Delete tenants completions
echo "Phase 25: Removing tenants completion reports..."
rm -f TENANTS_COMPLETE.md
rm -f TENANTS_FINAL_COMPREHENSIVE_REPORT.md
rm -f TENANTS_IMPLEMENTATION_COMPLETE.md
echo "  ✓ Removed tenants completion reports"

# Phase 26: Delete work order completions
echo "Phase 26: Removing work order completion reports..."
rm -f WORK_ORDER_COMPLETE.md
rm -f WORK_ORDER_FINAL_COMPREHENSIVE_REPORT.md
rm -f WORK_ORDER_IMPLEMENTATION_COMPLETE.md
rm -f WORK_ORDER_MANAGEMENT_COMPLETE.md
echo "  ✓ Removed work order completion reports"

# Phase 27: Delete y_helpdesk completions
echo "Phase 27: Removing y_helpdesk completion reports..."
rm -f Y_HELPDESK_COMPLETE.md
rm -f Y_HELPDESK_FINAL_COMPREHENSIVE_REPORT.md
rm -f Y_HELPDESK_IMPLEMENTATION_COMPLETE.md
echo "  ✓ Removed y_helpdesk completion reports"

# Phase 28: Move docker guide
echo "Phase 28: Moving docker guide..."
[ -f "DOCKER_README.md" ] && mv DOCKER_README.md docs/deployment/infrastructure/
echo "  ✓ Moved docker guide"

# Phase 29: Delete ultra/final completion summaries
echo "Phase 29: Removing ultra/final summaries..."
rm -f EVERYTHING_COMPLETE_COMPREHENSIVE_FINAL.md
rm -f FINAL_COMPLETE_COMPREHENSIVE_SUMMARY.md
rm -f FINAL_STATUS_COMPREHENSIVE_REPORT.md
rm -f MASTER_COMPLETION_INDEX.md
rm -f ULTIMATE_FINAL_COMPLETE_SUMMARY.md
echo "  ✓ Removed ultra/final summaries"

echo ""
echo "============================================"
echo "Final Cleanup Complete!"
echo ""
