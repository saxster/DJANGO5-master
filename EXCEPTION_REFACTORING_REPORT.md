# Exception Handling Migration Report

**Generated:** 2025-09-30 21:47:51
**Total Issues Found:** 980

## Executive Summary

| Confidence | Count | Percentage |
|------------|-------|------------|
| HIGH | 470 | 48.0% |
| MEDIUM | 140 | 14.3% |
| LOW | 370 | 37.8% |

## Breakdown by Suggested Fix

### except (ValueError, TypeError, KeyError, AttributeError) as e:
**Count:** 370 occurrences

**Files:**
- `apps/attendance/models.py:178` (startlocation_display)
- `apps/attendance/models.py:201` (endlocation_display)
- `apps/attendance/forms.py:110` (clean_geometry)
- `apps/attendance/forms.py:222` (_initialize_location_fields)
- `apps/attendance/managers_optimized.py:110` (get_people_attachment_optimized)
- `apps/attendance/managers_optimized.py:238` (get_peopleeventlog_history_optimized)
- `apps/attendance/managers_optimized.py:266` (fetch_sos_events_optimized)
- `apps/attendance/managers_optimized.py:294` (get_sos_listview_optimized)
- `apps/attendance/managers_optimized.py:313` (fetch_attachments_optimized)
- `apps/attendance/managers_optimized.py:356` (get_people_event_log_punch_ins_optimized)
- ... and 360 more

### except NETWORK_EXCEPTIONS as e:
**Count:** 280 occurrences

**Files:**
- `apps/attendance/forms.py:296` (clean)
- `apps/attendance/managers_optimized.py:157` (get_peopleevents_listview_optimized)
- `apps/journal/services/workflow_orchestrator.py:93` (create_journal_entry_with_analysis)
- `apps/journal/services/workflow_orchestrator.py:158` (update_journal_entry_with_reanalysis)
- `apps/journal/services/workflow_orchestrator.py:337` (handle_privacy_settings_change)
- `apps/journal/services/workflow_orchestrator.py:378` (schedule_periodic_wellness_check)
- `apps/helpbot/signals.py:218` (handle_request_exception)
- `apps/helpbot/views.py:71` (post)
- `apps/helpbot/views.py:110` (_start_session)
- `apps/helpbot/views.py:380` (get)
- ... and 270 more

### except DATABASE_EXCEPTIONS as e:
**Count:** 277 occurrences

**Files:**
- `apps/journal/services/workflow_orchestrator.py:283` (bulk_process_entries)
- `apps/journal/services/workflow_orchestrator.py:521` (_retroactive_crisis_check)
- `apps/helpbot/signals.py:57` (handle_session_pre_save)
- `apps/helpbot/signals.py:186` (handle_user_activity)
- `apps/helpbot/context_processors.py:55` (helpbot_context)
- `apps/helpbot/graphql_schema.py:165` (resolve_helpbot_active_session)
- `apps/helpbot/graphql_schema.py:202` (resolve_helpbot_search_knowledge)
- `apps/helpbot/graphql_schema.py:334` (mutate)
- `apps/helpbot/graphql_schema.py:378` (mutate)
- `apps/helpbot/views.py:165` (_process_message)
- ... and 267 more

### except FILE_EXCEPTIONS as e:
**Count:** 37 occurrences

**Files:**
- `apps/core/tasks/base.py:353` (cleanup_temp_files)
- `apps/core/management/commands/optimize_redis_memory.py:141` (handle)
- `apps/core/management/commands/analyze_slow_queries.py:114` (handle)
- `apps/core/management/commands/analyze_slow_queries.py:258` (_create_slow_query_alerts)
- `apps/core/management/commands/analyze_slow_queries.py:286` (_export_analysis_report)
- `apps/core/management/commands/import_spatial_data.py:144` (_handle_inspect)
- `apps/core/management/commands/import_spatial_data.py:193` (_handle_template)
- `apps/core/management/commands/import_spatial_data.py:236` (_handle_import)
- `apps/core/services/spatial_data_import_service.py:452` (_cleanup_temp_files)
- `apps/core/services/redis_backup_service.py:288` (list_backups)
- ... and 27 more

### except JSON_EXCEPTIONS as e:
**Count:** 16 occurrences

**Files:**
- `apps/attendance/forms.py:205` (_initialize_transport_modes)
- `apps/attendance/managers_optimized.py:190` (get_lastmonth_conveyance_optimized)
- `apps/attendance/managers_optimized.py:484` (fetch_sitecrisis_events_optimized)
- `apps/core/templatetags/google_maps_tags.py:51` (google_maps_config)
- `apps/core/middleware/pydantic_validation_middleware.py:185` (_validate_request_payload)
- `apps/core/models/query_execution_plans.py:184` (generate_plan_hash)
- `apps/core/monitoring/google_maps_monitor.py:318` (export_metrics)
- `apps/y_helpdesk/middleware/ticket_security_middleware.py:231` (_validate_request_security)
- `apps/_UNUSED_monitoring/consumers/monitoring_consumer.py:584`
- `apps/onboarding/admin.py:1345` (pretty_context_data)
- ... and 6 more

## How to Use This Report

### High Confidence Issues (Auto-fixable)
These issues can be safely auto-fixed with the migration script:
```bash
python scripts/migrate_exception_handling.py --fix --confidence HIGH
```

### Medium/Low Confidence Issues (Manual Review)
These require manual review to determine the correct exception types:
1. Review the suggested fix
2. Check the surrounding code context
3. Apply the fix manually or adjust the suggestion

## Next Steps

1. **Run auto-fix for HIGH confidence issues** (recommended)
2. **Review MEDIUM confidence** issues (10-30 min)
3. **Manually fix LOW confidence** issues (requires code inspection)

## Pattern Examples

For correct exception handling patterns, see:
- `apps/core/exceptions/patterns.py` - Pattern library
- `.claude/rules.md` Rule #1 - Exception handling standards

---
**Note:** This is an automated analysis. Always review suggested changes before applying.
