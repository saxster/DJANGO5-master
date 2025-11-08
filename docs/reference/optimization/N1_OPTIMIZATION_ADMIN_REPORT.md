================================================================================
N+1 QUERY OPTIMIZATION REPORT
================================================================================

📊 Summary:
   Total Admin Classes: 72
   ✅ Already Optimized: 21
   ⚠️  Needs Optimization: 51

================================================================================
🔴 HIGH PRIORITY - Missing N+1 Optimizations
================================================================================

📁 help_center.HelpArticleAdmin
   File: apps/help_center/admin.py
   List Display Fields: title, category, status_badge, difficulty_level, view_count, helpful_ratio_display, version, published_date, is_stale_badge
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 help_center.HelpArticleInteractionAdmin
   File: apps/help_center/admin.py
   List Display Fields: user, article_link, interaction_type, time_spent_seconds, scroll_depth_percent, timestamp
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 help_center.HelpCategoryAdmin
   File: apps/help_center/admin.py
   List Display Fields: name, parent, display_order, is_active, article_count_display, tenant
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 help_center.HelpSearchHistoryAdmin
   File: apps/help_center/admin.py
   List Display Fields: query, user, results_count, clicked_article_link, click_position, timestamp
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 help_center.HelpTagAdmin
   File: apps/help_center/admin.py
   List Display Fields: name, slug, tenant
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 help_center.HelpTicketCorrelationAdmin
   File: apps/help_center/admin.py
   List Display Fields: ticket_link, help_attempted_badge, content_gap_badge, resolution_time_minutes, suggested_article_link
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 issue_tracker.AnomalyOccurrenceAdmin
   File: apps/issue_tracker/admin.py
   List Display Fields: created_at, signature, endpoint, status, resolution_time_display, assigned_to
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 issue_tracker.FixActionAdmin
   File: apps/issue_tracker/admin.py
   List Display Fields: action_type, suggestion, applied_at, applied_by, result, commit_sha_short
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 issue_tracker.FixSuggestionAdmin
   File: apps/issue_tracker/admin.py
   List Display Fields: title, fix_type, confidence, priority_score, status, auto_applicable, risk_level, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 issue_tracker.RecurrenceTrackerAdmin
   File: apps/issue_tracker/admin.py
   List Display Fields: signature, recurrence_count, last_occurrence_at, severity_trend, fix_success_rate_display, requires_attention
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 ml.ConflictPredictionModelAdmin
   File: apps/ml/admin.py
   List Display Fields: version, algorithm, accuracy_display, is_active, trained_on_samples, feature_count, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 ml.PredictionLogAdmin
   File: apps/ml/admin.py
   List Display Fields: id, model_type, model_version, entity_type, predicted_status, probability_display, outcome_status, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 ml_training.LabelingTaskAdmin
   File: apps/ml_training/admin.py
   List Display Fields: dataset_name, task_type, status_badge, assigned_to, progress_bar, priority, due_date, is_overdue
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 ml_training.MLTrainingAdminSite
   File: apps/ml_training/admin.py
   List Display Fields: 
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 ml_training.TrainingDatasetAdmin
   File: apps/ml_training/admin.py
   List Display Fields: name, dataset_type, version, status_badge, progress_bar, quality_badge, created_by, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 ml_training.TrainingExampleAdmin
   File: apps/ml_training/admin.py
   List Display Fields: dataset_name, image_thumbnail, labeling_status_badge, quality_badge, uncertainty_badge, example_type, source_system, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 mqtt.DeviceAlertAdmin
   File: apps/mqtt/admin.py
   List Display Fields: alert_type_badge, source_id, severity_badge, status_badge, message_short, acknowledged_by, timestamp
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 mqtt.DeviceTelemetryAdmin
   File: apps/mqtt/admin.py
   List Display Fields: device_id, battery_badge, signal_badge, temperature_display, connectivity_status, timestamp, received_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 mqtt.GuardLocationAdmin
   File: apps/mqtt/admin.py
   List Display Fields: guard_link, location_display, geofence_badge, accuracy, timestamp, received_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 mqtt.SensorReadingAdmin
   File: apps/mqtt/admin.py
   List Display Fields: sensor_id, sensor_type, value_display, state_badge, timestamp, received_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 noc.FraudDetectionModelAdmin
   File: apps/noc/admin.py
   List Display Fields: model_version, tenant, pr_auc_display, precision_at_80_display, train_samples, fraud_ratio_display, is_active_badge, created_at_display
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 onboarding_api.OnboardingAdminSite
   File: apps/onboarding_api/admin.py
   List Display Fields: 
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.AccessProvisioningAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: onboarding_request, access_type, status, provisioned_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.ApprovalWorkflowAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: onboarding_request, approval_level, approver, decision, sequence_number
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.BackgroundCheckAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: onboarding_request, verification_type, status, result
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.CandidateProfileAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: full_name, primary_email, primary_phone, onboarding_request
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.DocumentSubmissionAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: onboarding_request, document_type, verification_status, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.OnboardingRequestAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: request_number, person_type, current_state, start_date, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.OnboardingTaskAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: onboarding_request, title, category, status, priority, assigned_to
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 people_onboarding.TrainingAssignmentAdmin
   File: apps/people_onboarding/admin.py
   List Display Fields: onboarding_request, training_title, status, due_date
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.AchievementAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: icon, name, rarity, points, category
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.CoachingSessionAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: worker, coach, session_date, session_type, follow_up_completed
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.CohortBenchmarkAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: cohort_key, metric_name, period_start, period_end, sample_size, median
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.KudosAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: recipient, giver, kudos_type, created_at, visibility
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.PerformanceStreakAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: worker, streak_type, current_count, best_count, started_date
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.TeamDailyMetricsAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: site, date, shift_type, active_workers, team_bpi_avg, sla_hit_rate_avg
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.WorkerAchievementAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: worker, achievement, earned_date, count
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 performance_analytics.WorkerDailyMetricsAdmin
   File: apps/performance_analytics/admin.py
   List Display Fields: worker, date, balanced_performance_index, performance_band, site, shift_type
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 search.SavedSearchAdmin
   File: apps/search/admin.py
   List Display Fields: name, user, tenant, is_alert_enabled, alert_frequency
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 search.SearchAnalyticsAdmin
   File: apps/search/admin.py
   List Display Fields: query, tenant, result_count, response_time_ms, timestamp
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 search.SearchIndexAdmin
   File: apps/search/admin.py
   List Display Fields: entity_type, title, tenant, is_active, last_indexed_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 streamlab.EventRetentionAdmin
   File: apps/streamlab/admin.py
   List Display Fields: retention_type, days_to_keep, last_cleanup_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 streamlab.StreamEventAdmin
   File: apps/streamlab/admin.py
   List Display Fields: timestamp, run, endpoint, direction, latency_ms, outcome, message_size_bytes
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 streamlab.StreamEventArchiveAdmin
   File: apps/streamlab/admin.py
   List Display Fields: archive_date, event_count, compressed_size_display, expires_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 streamlab.TestRunAdmin
   File: apps/streamlab/admin.py
   List Display Fields: scenario, status, started_by, started_at, duration_display, total_events, error_rate_display, slo_status
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 streamlab.TestScenarioAdmin
   File: apps/streamlab/admin.py
   List Display Fields: name, protocol, created_by, is_active, expected_p95_latency_ms, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 tenants.TenantAdmin
   File: apps/tenants/admin.py
   List Display Fields: tenantname, subdomain_prefix, created_at
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 tenants.TenantReadOnlyAdminMixin
   File: apps/tenants/admin.py
   List Display Fields: 
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 voice_recognition.EnrollmentPolicyAdmin
   File: apps/voice_recognition/admin.py
   List Display Fields: policy_name, is_active, min_device_trust_score, location_requirement, require_supervisor_approval, min_voice_samples
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 voice_recognition.VoiceEmbeddingAdmin
   File: apps/voice_recognition/admin.py
   List Display Fields: user, is_validated, voice_confidence, extraction_timestamp, language_code
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

📁 voice_recognition.VoiceVerificationLogAdmin
   File: apps/voice_recognition/admin.py
   List Display Fields: user, result, confidence_score, verification_timestamp, spoof_detected
   💡 Recommendation: Add list_select_related for foreign key relations in list_display

   Suggested Fix:
   ```python
   # Add to your ModelAdmin class:
   list_select_related = ['user', 'created_by', 'site', 'client']  # FK fields
   list_prefetch_related = ['tags', 'attachments']  # M2M fields
   ```

================================================================================
✅ WELL OPTIMIZED - Good Examples
================================================================================

📁 attendance.GeofenceAdmin
   File: apps/attendance/admin.py
   Optimizations: get_queryset override

📁 attendance.PeopleEventlogAdmin
   File: apps/attendance/admin.py
   Optimizations: get_queryset override

📁 attendance.PostAdmin
   File: apps/attendance/admin.py
   Optimizations: list_select_related, list_prefetch_related, get_queryset override

📁 attendance.PostAssignmentAdmin
   File: apps/attendance/admin.py
   Optimizations: get_queryset override

📁 attendance.PostOrderAcknowledgementAdmin
   File: apps/attendance/admin.py
   Optimizations: get_queryset override

📁 core.TaskFailureRecordAdmin
   File: apps/core/admin.py
   Optimizations: get_queryset override

📁 journal.JournalEntryAdmin
   File: apps/journal/admin.py
   Optimizations: get_queryset override

📁 journal.JournalMediaAttachmentAdmin
   File: apps/journal/admin.py
   Optimizations: get_queryset override

📁 journal.JournalPrivacySettingsAdmin
   File: apps/journal/admin.py
   Optimizations: get_queryset override

📁 y_helpdesk.TicketAdmin
   File: apps/y_helpdesk/admin.py
   Optimizations: list_select_related, list_prefetch_related, get_queryset override
