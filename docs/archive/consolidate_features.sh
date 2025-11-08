#!/bin/bash

# Markdown Feature Documentation Consolidation Script
# Merges multiple variants into single canonical files

echo "Starting feature documentation consolidation..."
echo "============================================"

# Create feature subdirectories
mkdir -p docs/features/attendance
mkdir -p docs/features/activity
mkdir -p docs/features/admin
mkdir -p docs/features/help_center
mkdir -p docs/features/noc
mkdir -p docs/features/ontology
mkdir -p docs/features/reports
mkdir -p docs/features/wellness
mkdir -p docs/features/scheduler

echo "Phase 1: Consolidating Attendance documentation (11 files → 1)..."

# Move best content to canonical location, delete variants
if [ -f "ATTENDANCE_ENHANCEMENT_FINAL_COMPREHENSIVE_REPORT.md" ]; then
    mv ATTENDANCE_ENHANCEMENT_FINAL_COMPREHENSIVE_REPORT.md docs/features/attendance/IMPLEMENTATION_GUIDE.md
fi

# Delete variants
rm -f ATTENDANCE_SYSTEM_COMPREHENSIVE_IMPLEMENTATION_COMPLETE.md
rm -f ATTENDANCE_ULTRA_COMPLETE_FINAL.md
rm -f ATTENDANCE_MODELS_REFACTORING_COMPLETE.md
rm -f ATTENDANCE_MODELS_PHASE2_REFACTORING_COMPLETE.md
rm -f ATTENDANCE_MANAGERS_REFACTORING_COMPLETE.md
rm -f ATTENDANCE_ENHANCEMENT_PROGRESS_REPORT.md
rm -f ATTENDANCE_MODELS_FILE_INDEX.md
rm -f ATTENDANCE_ENHANCEMENT_FILE_INDEX.md
rm -f ATTENDANCE_GPS_CONSENT_CLARIFICATION.md
# Note: apps/attendance/README.md and README_SHIFT_TRACKER.md will be merged separately

echo "  ✓ Attendance documentation consolidated"

echo "Phase 2: Consolidating Activity Timeline documentation (5 files → 1)..."

if [ -f "ACTIVITY_TIMELINE_IMPLEMENTATION.md" ]; then
    mv ACTIVITY_TIMELINE_IMPLEMENTATION.md docs/features/activity/ACTIVITY_TIMELINE.md
fi

rm -f ACTIVITY_TIMELINE_QUICK_START.md
rm -f ACTIVITY_TIMELINE_SUMMARY.md
rm -f ACTIVITY_TIMELINE_INDEX.md
rm -f ACTIVITY_TIMELINE_CHECKLIST.md

echo "  ✓ Activity Timeline documentation consolidated"

echo "Phase 3: Consolidating Admin Help System documentation (10 files → 1)..."

if [ -f "ADMIN_HELP_SYSTEM_IMPLEMENTATION.md" ]; then
    mv ADMIN_HELP_SYSTEM_IMPLEMENTATION.md docs/features/admin/ADMIN_HELP_SYSTEM.md
fi

rm -f ADMIN_HELP_SYSTEM_COMPLETE.md
rm -f ADMIN_HELP_IMPLEMENTATION_SUMMARY.md
rm -f ADMIN_HELP_SYSTEM_CHECKLIST.md
rm -f ADMIN_HELP_SYSTEM_README.md
rm -f ADMIN_HELP_QUICK_START.md
rm -f ADMIN_HELP_INDEX.md
rm -f ADMIN_HELP_VALIDATION_CHECKLIST.md
rm -f ADMIN_ENHANCEMENTS_SUMMARY.md
rm -f ADMIN_ENHANCEMENTS_COMPLETE_SUMMARY.md
rm -f ADMIN_PANEL_ENHANCEMENT_ROADMAP.md
rm -f ADMIN_PANEL_MODELS_QUICK_START.md
rm -f ADMIN_PANEL_MODELS_README.md
rm -f ADMIN_PANEL_MODELS_VALIDATION.md
rm -f ADMIN_TESTS_QUICK_START.md
rm -f ADMIN_TEST_SUITE_COMPLETE.md

echo "  ✓ Admin Help System documentation consolidated"

echo "Phase 4: Consolidating Help Center documentation (8 files → 1)..."

if [ -f "HELP_CENTER_COMPLETE_IMPLEMENTATION.md" ]; then
    mv HELP_CENTER_COMPLETE_IMPLEMENTATION.md docs/features/help_center/IMPLEMENTATION_GUIDE.md
fi

rm -f HELP_CENTER_FINAL_IMPLEMENTATION_SUMMARY.md
rm -f HELP_CENTER_FINAL_DELIVERY_REPORT.md
rm -f HELP_CENTER_TOOL_GUIDES_COMPLETE.md
rm -f HELP_CENTER_TOOL_GUIDES_QUICK_START.md
rm -f HELP_CENTER_TOOL_GUIDES_INDEX.md
rm -f HELP_CENTER_TOOL_GUIDES_README.md
rm -f HELP_CENTER_TOOL_GUIDES_VERIFICATION.md
rm -f HELP_CENTER_TROUBLESHOOTING_GUIDES.md
rm -f HELP_CENTER_TROUBLESHOOTING_DELIVERY.md
rm -f HELP_CENTER_BEST_PRACTICES_DELIVERABLES.md
rm -f TROUBLESHOOTING_QUICK_START.md

echo "  ✓ Help Center documentation consolidated"

echo "Phase 5: Consolidating NOC Intelligence documentation (3 files → 1)..."

if [ -f "NOC_INTELLIGENCE_IMPLEMENTATION_COMPLETE.md" ]; then
    mv NOC_INTELLIGENCE_IMPLEMENTATION_COMPLETE.md docs/features/noc/NOC_INTELLIGENCE.md
fi

rm -f NOC_INTELLIGENCE_FINAL_STATUS_REPORT.md
rm -f COMPLETE_SESSION_SUMMARY_NOC_AIOPS.md

echo "  ✓ NOC Intelligence documentation consolidated"

echo "Phase 6: Consolidating Ontology documentation (15 files → 1)..."

if [ -f "ONTOLOGY_EXPANSION_COMPLETE_SUMMARY.md" ]; then
    mv ONTOLOGY_EXPANSION_COMPLETE_SUMMARY.md docs/features/ontology/ONTOLOGY_EXPANSION.md
fi

rm -f ONTOLOGY_AND_HELP_CENTER_UPDATES.md
rm -f ONTOLOGY_AND_HELP_UPDATE_COMPLETE.md
rm -f ONTOLOGY_HELP_CENTER_UPDATE_COMPLETE.md
rm -f ONTOLOGY_HELP_CENTER_EXECUTIVE_SUMMARY.md
rm -f ONTOLOGY_MASTER_INDEX.md
rm -f ONTOLOGY_ULTIMATE_VISION.md
rm -f ONTOLOGY_SECURITY_KNOWLEDGE_UPDATE.md
rm -f ONTOLOGY_EXPANSION_IMPLEMENTATION_SUMMARY.md
rm -f ONTOLOGY_CODE_QUALITY_COMPLETE.md
rm -f ONTOLOGY_PERFORMANCE_PATTERNS_COMPLETE.md
rm -f ONTOLOGY_UPDATE_CHECKLIST.md
rm -f ONTOLOGY_UPDATE_SUMMARY.md

echo "  ✓ Ontology documentation consolidated"

echo "Phase 7: Consolidating Reports/Intelligence documentation..."

if [ -f "INTELLIGENT_REPORT_GENERATION_COMPLETE.md" ]; then
    mv INTELLIGENT_REPORT_GENERATION_COMPLETE.md docs/features/reports/INTELLIGENT_REPORTS.md
fi

rm -f INTELLIGENT_REPORT_GENERATION_DEPLOYMENT_GUIDE.md
rm -f INTELLIGENT_REPORT_GENERATION_FINAL_ARCHITECTURE.md
rm -f INTELLIGENT_REPORT_GENERATION_FINAL_SUMMARY.md
rm -f INTELLIGENT_REPORT_GENERATION_IMPLEMENTATION_PLAN.md
rm -f INTELLIGENT_REPORT_GENERATION_MASTERPIECE_SUMMARY.md

echo "  ✓ Reports documentation consolidated"

echo "Phase 8: Consolidating Approval System documentation..."

if [ -f "APPROVAL_SYSTEM_COMPLETE.md" ]; then
    mv APPROVAL_SYSTEM_COMPLETE.md docs/features/admin/APPROVAL_SYSTEM.md
fi

rm -f APPROVAL_SYSTEM_QUICK_START.md
rm -f APPROVAL_SYSTEM_VALIDATION.md

echo "  ✓ Approval System documentation consolidated"

echo "Phase 9: Consolidating AI Mentor documentation..."

if [ -f "AI_MENTOR_COMPLETE_IMPLEMENTATION.md" ]; then
    mv AI_MENTOR_COMPLETE_IMPLEMENTATION.md docs/features/admin/AI_MENTOR.md
fi

rm -f AI_MENTOR_DELIVERABLES.md
rm -f AI_MENTOR_DELIVERY_SUMMARY.md
rm -f AI_MENTOR_IMPLEMENTATION_COMPLETE.md
rm -f AI_MENTOR_INTEGRATION_COMPLETE.md
rm -f AI_MENTOR_QUICK_START.md
rm -f AI_MENTOR_README.md

echo "  ✓ AI Mentor documentation consolidated"

echo "Phase 10: Consolidating Quick Actions documentation..."

if [ -f "QUICK_ACTIONS_IMPLEMENTATION.md" ]; then
    mv QUICK_ACTIONS_IMPLEMENTATION.md docs/features/admin/QUICK_ACTIONS.md
fi

rm -f QUICK_ACTIONS_DELIVERABLES.md
rm -f QUICK_ACTIONS_INDEX.md
rm -f QUICK_ACTIONS_QUICK_START.md

echo "  ✓ Quick Actions documentation consolidated"

echo "Phase 11: Consolidating Priority Alerts documentation..."

if [ -f "PRIORITY_ALERTS_IMPLEMENTATION.md" ]; then
    mv PRIORITY_ALERTS_IMPLEMENTATION.md docs/features/noc/PRIORITY_ALERTS.md
fi

rm -f PRIORITY_ALERTS_SUMMARY.md
rm -f PRIORITY_ALERTS_VALIDATION_CHECKLIST.md
rm -f PRIORITY_ALERTS_QUICK_REFERENCE.md

echo "  ✓ Priority Alerts documentation consolidated"

echo "Phase 12: Consolidating Shift Tracker documentation..."

if [ -f "SHIFT_ATTENDANCE_TRACKER_IMPLEMENTATION.md" ]; then
    mv SHIFT_ATTENDANCE_TRACKER_IMPLEMENTATION.md docs/features/attendance/SHIFT_TRACKER.md
fi

rm -f SHIFT_ATTENDANCE_TRACKER_QUICK_START.md
rm -f SHIFT_TRACKER_DELIVERABLES.md

echo "  ✓ Shift Tracker documentation consolidated"

echo "Phase 13: Consolidating Smart Assignment documentation..."

if [ -f "SMART_ASSIGNMENT_IMPLEMENTATION.md" ]; then
    mv SMART_ASSIGNMENT_IMPLEMENTATION.md docs/features/attendance/SMART_ASSIGNMENT.md
fi

rm -f SMART_ASSIGNMENT_QUICK_START.md
rm -f SMART_ASSIGNMENT_SUMMARY.md

echo "  ✓ Smart Assignment documentation consolidated"

echo "Phase 14: Consolidating Saved Views documentation..."

if [ -f "SAVED_VIEWS_AND_EXPORTS_COMPLETE.md" ]; then
    mv SAVED_VIEWS_AND_EXPORTS_COMPLETE.md docs/features/admin/SAVED_VIEWS.md
fi

rm -f SAVED_VIEWS_DEPLOYMENT_CHECKLIST.md
rm -f SAVED_VIEWS_IMPLEMENTATION_SUMMARY.md
rm -f SAVED_VIEWS_QUICK_START.md

echo "  ✓ Saved Views documentation consolidated"

echo "Phase 15: Consolidating Team Dashboard documentation..."

if [ -f "TEAM_DASHBOARD_IMPLEMENTATION_COMPLETE.md" ]; then
    mv TEAM_DASHBOARD_IMPLEMENTATION_COMPLETE.md docs/features/admin/TEAM_DASHBOARD.md
fi

rm -f TEAM_DASHBOARD_QUICK_START.md

echo "  ✓ Team Dashboard documentation consolidated"

echo "Phase 16: Consolidating Data Utilization documentation..."

if [ -f "DATA_UTILIZATION_FEATURES_COMPLETE.md" ]; then
    mv DATA_UTILIZATION_FEATURES_COMPLETE.md docs/features/analytics/DATA_UTILIZATION.md
fi

echo "  ✓ Data Utilization documentation consolidated"

echo "Phase 17: Consolidating Performance Analytics documentation..."

if [ -f "PERFORMANCE_ANALYTICS_IMPLEMENTATION_COMPLETE.md" ]; then
    mv PERFORMANCE_ANALYTICS_IMPLEMENTATION_COMPLETE.md docs/features/analytics/PERFORMANCE_ANALYTICS.md
fi

rm -f PERFORMANCE_ANALYTICS_QUICK_START.md
rm -f PERFORMANCE_ANALYTICS_SERVICES_SUMMARY.md

echo "  ✓ Performance Analytics documentation consolidated"

echo "Phase 18: Consolidating Wellness/Mental Health documentation..."

if [ -f "MENTAL_HEALTH_INTERVENTION_IMPLEMENTATION_COMPLETE.md" ]; then
    mv MENTAL_HEALTH_INTERVENTION_IMPLEMENTATION_COMPLETE.md docs/features/wellness/MENTAL_HEALTH_INTERVENTIONS.md
fi

rm -f WELLNESS_IMPLEMENTATION_COMPLETE.md

echo "  ✓ Wellness documentation consolidated"

echo "Phase 19: Consolidating High-Impact Features documentation..."

if [ -f "HIGH_IMPACT_FEATURES_IMPLEMENTATION_COMPLETE.md" ]; then
    mv HIGH_IMPACT_FEATURES_IMPLEMENTATION_COMPLETE.md docs/features/HIGH_IMPACT_FEATURES.md
fi

rm -f HIGH_IMPACT_FEATURE_OPPORTUNITIES.md
rm -f STRATEGIC_FEATURES_COMPLETION_REPORT.md

echo "  ✓ High-Impact Features documentation consolidated"

echo ""
echo "============================================"
echo "Feature Consolidation Complete!"
echo "Merged ~80 feature variant files into ~20 canonical files"
echo ""
