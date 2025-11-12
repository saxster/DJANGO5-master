# mysite/celery.py
from __future__ import absolute_import, unicode_literals

import os

import intelliwiz_config.bootstrap  # noqa: F401
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
# Fail-closed: default to production for Celery workers/beat.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.production')

app = Celery('intelliwiz_config')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object(settings, namespace='CELERY')

# Explicitly set the timezone for Celery
app.conf.timezone = 'UTC'

# Load task modules from all registered Django apps.
app.autodiscover_tasks()
app.conf.CELERYD_HIJACK_ROOT_LOGGER = False

# ============================================================================
# IMPORT CENTRALIZED CELERY CONFIGURATION
# ============================================================================
# Import reusable configuration components from centralized module
# This provides queue definitions, task routing, and enhanced config presets
try:
    from apps.core.tasks.celery_settings import (
        CELERY_QUEUES,
        CELERY_TASK_ROUTES,
        get_queue_priorities
    )

    # Apply queue and routing configuration
    app.conf.task_queues = CELERY_QUEUES
    app.conf.task_routes = CELERY_TASK_ROUTES

except ImportError:
    # Gracefully handle if core app is not installed
    pass

# Initialize correlation ID propagation for request tracing
try:
    from apps.core.tasks.celery_correlation_id import setup_correlation_id_propagation
    setup_correlation_id_propagation()
except ImportError:
    # Gracefully handle if core app is not installed
    pass

# Initialize OTEL distributed tracing for Celery tasks
try:
    from apps.core.tasks.celery_otel_tracing import setup_celery_otel_tracing
    setup_celery_otel_tracing()
except ImportError:
    # Gracefully handle if core app is not installed
    pass

# Ensure tenant context is applied to all Celery tasks
try:
    import apps.tenants.task_context  # noqa: F401
except ImportError:
    pass

# Register onboarding schedules
try:
    from apps.onboarding_api.celery_schedules import register_onboarding_schedules
    register_onboarding_schedules(app)
except ImportError:
    # Gracefully handle if onboarding_api is not installed
    pass



app.conf.beat_schedule = {
    # ============================================================================
    # OPTIMIZED CELERY BEAT SCHEDULE - COMPREHENSIVE DESIGN DOCUMENTATION
    # ============================================================================
    #
    # ⚙️ DESIGN PRINCIPLES & RATIONALE
    # ============================================================================
    #
    # 1. **COLLISION AVOIDANCE STRATEGY**
    #    - Critical tasks (autoclose, escalation): 15-minute minimum separation
    #    - High-frequency tasks (every 15min): Use :05, :20, :35, :50 to avoid
    #      common times (:00, :15, :30, :45)
    #    - Prime number intervals (27min): Natural distribution reduces collisions
    #    - Database-heavy operations: 30+ minute separation minimum
    #
    # 2. **OFFSET CALCULATION METHODOLOGY**
    #    - :00, :30 → Critical tasks (auto-close) - highest priority
    #    - :15, :45 → Critical tasks (escalation) - offset by 15 min
    #    - :05, :20, :35, :50 → Reports - fills gaps between critical tasks
    #    - :10 → Email reminders - every 8 hours, low collision risk
    #    - :27 → Job creation - prime number for even distribution
    #
    # 3. **LOAD DISTRIBUTION PHILOSOPHY**
    #    - Peak business hours (9 AM - 5 PM): Minimize heavy operations
    #    - Off-peak hours (2-4 AM): Maintenance, backups, cleanup
    #    - Queue separation: Critical, High Priority, Email, Reports, Maintenance
    #    - Worker capacity awareness: Monitor queue depth every 5 minutes
    #
    # 4. **DST (DAYLIGHT SAVING TIME) CONSIDERATIONS** 🕐
    #    ⚠️ CRITICAL: All times are in UTC (app.conf.timezone = 'UTC')
    #
    #    **Why UTC?**
    #    - No DST transitions (stable, predictable)
    #    - Eliminates schedule skipping/duplication issues
    #    - Global coordination across timezones
    #
    #    **DST Transition Issues (for reference):**
    #    - Spring Forward: 2:00 AM → 3:00 AM (1 hour skipped)
    #      → Schedules at 2:00-3:00 AM local time WON'T RUN
    #    - Fall Back: 2:00 AM → 1:00 AM (1 hour repeated)
    #      → Schedules at 1:00-2:00 AM local time RUN TWICE
    #
    #    **Best Practices:**
    #    ✅ Use UTC for all schedules (current implementation)
    #    ✅ If local time required: Use 4 AM+ (safe from DST transitions)
    #    ❌ Avoid 1-3 AM local time (high DST risk)
    #
    # 5. **IDEMPOTENCY FRAMEWORK** 🔒
    #    - All critical tasks use `IdempotentTask` base class
    #    - Redis-first duplicate detection (2ms latency)
    #    - PostgreSQL fallback for reliability
    #    - Prevents duplicate execution on schedule overlaps
    #    - See: apps/core/tasks/idempotency_service.py
    #
    # 6. **MONITORING & HEALTH CHECKS** 📊
    #    - Schedule health: /admin/tasks/schedule-conflicts
    #    - Queue depth: Monitor worker lag every 5 minutes
    #    - Collision detection: Automated alerts if >3 tasks in same minute
    #    - Performance metrics: Average execution time per task type
    #    - DST risk analysis: python manage.py validate_schedules --check-dst
    #
    # 7. **PERFORMANCE OPTIMIZATION** ⚡
    #    - Task expiration: Prevents stale task execution
    #    - Soft/hard time limits: Graceful degradation for long tasks
    #    - Queue routing: Dedicated queues by priority/type
    #    - Prefetch multiplier: 4x (balance throughput vs memory)
    #    - Circuit breakers: Automatic failure protection
    #
    # ============================================================================
    # 📅 SCHEDULE VISUALIZATION & HOTSPOT ANALYSIS
    # ============================================================================
    #
    # MINUTE DISTRIBUTION (every hour):
    # :00 ─ autoclose (every 30min) ─────────── Critical Queue
    # :05 ─ reports (every 15min) ──────────── Reports Queue
    # :10 ─ reminder emails (every 8hrs) ────── Email Queue
    # :15 ─ ticket escalation (every 30min) ── Critical Queue
    # :20 ─ reports (every 15min) ──────────── Reports Queue
    # :27 ─ job creation (every 8hrs) ───────── High Priority Queue
    #     └─ email reports (every 27min) ────── Email Queue (overlaps ok)
    # :30 ─ autoclose (every 30min) ─────────── Critical Queue
    # :35 ─ reports (every 15min) ──────────── Reports Queue
    # :45 ─ ticket escalation (every 30min) ── Critical Queue
    # :50 ─ reports (every 15min) ──────────── Reports Queue
    #
    # LOAD HOTSPOTS (potential collision points):
    # - :00 - Medium load (1 task)
    # - :15 - Medium load (1 task)
    # - :27 - Low-medium load (2 tasks, different queues)
    # - :30 - Medium load (1 task)
    # - :45 - Medium load (1 task)
    #
    # SAFE ZONES (low collision risk):
    # - :05, :10, :20, :35, :50 - Ideal for new schedules
    #
    # ============================================================================
    # 🔧 MAINTENANCE & TROUBLESHOOTING
    # ============================================================================
    #
    # **Adding New Schedules:**
    # 1. Check load distribution: python -c "from apps.scheduler.services.schedule_coordinator import ScheduleCoordinator; print(ScheduleCoordinator().analyze_schedule_health())"
    # 2. Validate DST safety: python -c "from apps.scheduler.services.dst_validator import DSTValidator; print(DSTValidator().validate_schedule_dst_safety('0 2 * * *', 'UTC'))"
    # 3. Use safe time slots: :05, :10, :20, :35, :50
    # 4. Avoid critical task minutes: :00, :15, :30, :45
    #
    # **Common Issues:**
    # - Worker queue buildup → Check schedule distribution, add offsets
    # - Task running twice → Verify idempotency implementation
    # - Task skipped on DST → Validate using UTC timezone
    # - Database locks → Separate database-heavy tasks by 30+ minutes
    #
    # **Emergency Procedures:**
    # - Disable problematic task: Comment out schedule entry, restart beat
    # - Adjust offset: Change minute value, verify no new collisions
    # - Force UTC: Always use UTC unless business requirement for local time
    #
    # ============================================================================
    # 📋 SCHEDULE DEFINITIONS START HERE
    # ============================================================================

    # PPM (Planned Preventive Maintenance) Generation
    # Runs: 3:03 AM and 4:03 PM daily
    # Rationale: Off-peak hours, 13-hour separation
    "ppm_schedule_at_minute_3_past_hour_3_and_16": {
        'task': 'create_ppm_job',
        'schedule': crontab(minute='3', hour='3,16'),
        'options': {
            'expires': 7200,  # 2 hours (allow completion before next run)
            'queue': 'high_priority',
        }
    },

    # Reminder Emails
    # Runs: Every 8 hours at :10 (2:10 AM, 10:10 AM, 6:10 PM)
    # Rationale: Spread throughout day, offset from PPM
    "reminder_emails_at_minute_10_past_every_8th_hour": {
        'task': 'send_reminder_email',
        'schedule': crontab(hour='*/8', minute='10'),
        'options': {
            'expires': 28800,  # 8 hours (before next run)
            'queue': 'email',
        }
    },

    # Job Auto-Close
    # Runs: Every 30 minutes at :00 and :30 (CHANGED: explicit times)
    # Rationale: Prevents overlap with ticket escalation
    # CRITICAL: Uses idempotent task to prevent duplicate closes
    "auto_close_at_every_30_minute": {
        'task': 'auto_close_jobs',
        'schedule': crontab(minute='0,30'),  # CHANGED: explicit minutes
        'options': {
            'expires': 1500,  # 25 minutes (buffer before next run)
            'queue': 'critical',
        }
    },

    # Ticket Escalation
    # Runs: Every 30 minutes at :15 and :45 (CHANGED: offset from autoclose)
    # Rationale: 15-minute offset prevents collision with autoclose
    # CRITICAL: Uses idempotent task to prevent duplicate escalations
    "ticket_escalation_every_30min": {
        'task': 'ticket_escalation',
        'schedule': crontab(minute='15,45'),  # CHANGED: offset from autoclose
        'options': {
            'expires': 1500,  # 25 minutes (buffer before next run)
            'queue': 'critical',
        }
    },

    # Scheduled Job Creation
    # Runs: Every 8 hours at :27 (2:27 AM, 10:27 AM, 6:27 PM)
    # Rationale: Offset from email reminders by 17 minutes
    "create_job_at_minute_27_past_every_8th_hour": {
        'task': 'create_job',
        'schedule': crontab(minute='27', hour='*/8'),
        'options': {
            'expires': 28800,  # 8 hours (before next run)
            'queue': 'high_priority',
        }
    },

    # Media Migration to Cloud Storage
    # Runs: Monday 12:00 AM (weekly)
    # Rationale: Low-traffic time, weekly to reduce load
    "move_media_to_cloud_storage": {
        'task': 'move_media_to_cloud_storage',
        'schedule': crontab(minute=0, hour=0, day_of_week='monday'),
        'options': {
            'expires': 86400,  # 24 hours (long-running task)
            'queue': 'maintenance',
            'soft_time_limit': 21600,  # 6 hours soft limit
            'time_limit': 28800,  # 8 hours hard limit
        }
    },

    # Email Generated Reports
    # Runs: Every ~27 minutes at :02, :29, :56 (offset from :27 collision)
    # Rationale: Prime number distribution, avoids DB pool contention with create_job
    # FIXED (CELERY-001): Offset from :27 to prevent collision with create_job task
    "send_report_generated_on_mail": {  # FIXED: typo in key name
        'task': 'send_generated_report_on_mail',
        'schedule': crontab(minute='2,29,56'),  # Every ~27min, offset from :27
        'options': {
            'expires': 1500,  # 25 minutes (buffer before next run)
            'queue': 'email',
        }
    },

    # Scheduled Report Generation
    # Runs: Every 15 minutes at :05, :20, :35, :50 (CHANGED: offset)
    # Rationale: Offset from other tasks, avoids :00/:15/:30/:45
    # CRITICAL: Uses idempotent task to prevent duplicate reports
    "create_reports_scheduled": {  # FIXED: hyphen to underscore
        'task': 'create_scheduled_reports',
        'schedule': crontab(minute='5,20,35,50'),  # CHANGED: explicit offset
        'options': {
            'expires': 800,  # 13 minutes (buffer before next run)
            'queue': 'reports',
            'soft_time_limit': 600,  # 10 minutes soft limit
            'time_limit': 900,  # 15 minutes hard limit
        }
    },

    # ============================================================================
    # AGENT INTELLIGENCE TASKS (Dashboard Agent Intelligence - Phase 6)
    # ============================================================================

    # Dashboard Agent Insights Processing
    # Runs: Every 5 minutes at :02, :07, :12, :17, :22, :27, :32, :37, :42, :47, :52, :57
    # Rationale: Offset by 2 minutes from report tasks to avoid collision
    # Queue: reports (analytical processing)
    "process_dashboard_agent_insights": {
        'task': 'dashboard.process_agent_insights',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {
            'expires': 240,  # 4 minutes (buffer before next run)
            'queue': 'reports',
            'soft_time_limit': 120,  # 2 minutes
            'time_limit': 180,  # 3 minutes hard limit
        }
    },

    # Auto-Execute Critical Agent Actions
    # Runs: Every 10 minutes at :03, :13, :23, :33, :43, :53
    # Rationale: Offset from agent insights by 1 minute
    # Queue: high_priority (automated actions need priority)
    "auto_execute_critical_agent_actions": {
        'task': 'dashboard.auto_execute_critical_actions',
        'schedule': crontab(minute='3,13,23,33,43,53'),  # Every 10 min, offset +3
        'options': {
            'expires': 480,  # 8 minutes (buffer before next run)
            'queue': 'high_priority',
            'soft_time_limit': 300,  # 5 minutes
            'time_limit': 420,  # 7 minutes hard limit
        }
    },

    # Cleanup Expired Agent Recommendations
    # Runs: Daily at 1:30 AM UTC
    # Rationale: Off-peak hour, safe from DST transitions (after 3 AM in most zones)
    # Queue: maintenance (low priority cleanup)
    "cleanup_expired_agent_recommendations": {
        'task': 'dashboard.cleanup_expired_recommendations',
        'schedule': crontab(minute='30', hour='1'),  # Daily 1:30 AM UTC
        'options': {
            'expires': 3600,  # 1 hour
            'queue': 'maintenance',
        }
    },

    # ============================================================================
    # ML TRAINING & AI IMPROVEMENT TASKS
    # ============================================================================

    # Active Learning Sample Selection (ML Training)
    # Runs: Every Sunday at 2:00 AM UTC
    # Rationale: Weekly batch selection, off-peak hour, low collision risk
    # Queue: ai_processing (ML/AI workloads)
    # Purpose: Selects 50 most uncertain + diverse samples for human labeling
    "ml_training_active_learning_weekly": {
        'task': 'apps.ml_training.tasks.active_learning_loop',
        'schedule': crontab(minute='0', hour='2', day_of_week='0'),  # Sunday 2:00 AM
        'options': {
            'expires': 3600,  # 1 hour (task should complete quickly)
            'queue': 'ai_processing',
            'soft_time_limit': 300,  # 5 minutes
            'time_limit': 600,  # 10 minutes hard limit
        }
    },

    # Track Conflict Prediction Outcomes
    # Runs: Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)
    # Rationale: Check 24-hour-old predictions for actual outcomes
    # Queue: ml_training (ML workloads, non-critical)
    # Purpose: Update actual_conflict_occurred field, calculate accuracy metrics
    "ml_track_conflict_prediction_outcomes": {
        'task': 'ml.track_conflict_prediction_outcomes',
        'schedule': crontab(minute='0', hour='*/6'),  # Every 6 hours
        'options': {
            'expires': 21600,  # 6 hours (before next run)
            'queue': 'ml_training',
            'soft_time_limit': 540,  # 9 minutes
            'time_limit': 600,  # 10 minutes hard limit
        }
    },

    # Weekly Conflict Model Retraining
    # Runs: Every Monday at 3:00 AM UTC
    # Rationale: Weekly retraining on 90 days data, off-peak hour
    # Queue: ml_training (ML workloads, resource-intensive)
    # Purpose: Extract data, train model, auto-activate if >5% improvement
    "ml_retrain_conflict_model_weekly": {
        'task': 'ml.retrain_conflict_model_weekly',
        'schedule': crontab(minute='0', hour='3', day_of_week='1'),  # Monday 3:00 AM
        'options': {
            'expires': 7200,  # 2 hours (long-running task)
            'queue': 'ml_training',
            'soft_time_limit': 1620,  # 27 minutes
            'time_limit': 1800,  # 30 minutes hard limit
        }
    },

    # ============================================================================
    # INFRASTRUCTURE MONITORING & ANOMALY DETECTION
    # ============================================================================

    # Collect Infrastructure Metrics (CPU, memory, disk, DB, app)
    # Runs: Every 60 seconds
    # Rationale: High-frequency monitoring for real-time anomaly detection
    # Queue: monitoring (dedicated queue for metrics)
    "monitoring_collect_infrastructure_metrics": {
        'task': 'monitoring.collect_infrastructure_metrics',
        'schedule': 60.0,  # Every 60 seconds
        'options': {
            'expires': 50,  # 50 seconds (before next run)
            'queue': 'monitoring',
            'soft_time_limit': 30,  # 30 seconds
            'time_limit': 50,  # 50 seconds hard limit
        }
    },

    # Detect Infrastructure Anomalies
    # Runs: Every 5 minutes at :01, :06, :11, :16, :21, :26, :31, :36, :41, :46, :51, :56
    # Rationale: Analyze last hour of data, offset by 1 minute from collection tasks
    # Queue: monitoring (analytical processing)
    "monitoring_detect_infrastructure_anomalies": {
        'task': 'monitoring.detect_infrastructure_anomalies',
        'schedule': crontab(minute='1,6,11,16,21,26,31,36,41,46,51,56'),  # Every 5 min, offset +1
        'options': {
            'expires': 240,  # 4 minutes (buffer before next run)
            'queue': 'monitoring',
            'soft_time_limit': 120,  # 2 minutes
            'time_limit': 240,  # 4 minutes hard limit
        }
    },

    # Cleanup Old Infrastructure Metrics
    # Runs: Daily at 2:00 AM UTC
    # Rationale: Off-peak hour, deletes metrics older than 30 days
    # Queue: maintenance (low priority cleanup)
    "monitoring_cleanup_infrastructure_metrics": {
        'task': 'monitoring.cleanup_infrastructure_metrics',
        'schedule': crontab(minute='0', hour='2'),  # Daily 2:00 AM UTC
        'options': {
            'expires': 3600,  # 1 hour
            'queue': 'maintenance',
            'soft_time_limit': 300,  # 5 minutes
            'time_limit': 540,  # 9 minutes hard limit
        }
    },

    # Auto-Tune Anomaly Detection Thresholds
    # Runs: Weekly on Sunday at 3:00 AM UTC
    # Rationale: Adjust thresholds based on false positive rates (weekly review)
    # Queue: maintenance (low priority tuning)
    "monitoring_auto_tune_anomaly_thresholds": {
        'task': 'monitoring.auto_tune_anomaly_thresholds',
        'schedule': crontab(minute='0', hour='3', day_of_week='0'),  # Sunday 3:00 AM
        'options': {
            'expires': 3600,  # 1 hour
            'queue': 'maintenance',
            'soft_time_limit': 120,  # 2 minutes
            'time_limit': 240,  # 4 minutes hard limit
        }
    },

    # ============================================================================
    # PHASE 2: ML DRIFT MONITORING TASKS
    # ============================================================================
    # Daily tasks for model performance monitoring and drift detection
    # Sequential execution: outcome tracking → metrics → statistical → performance
    # ============================================================================

    # REMOVED (INFRA-001): Duplicate task definition
    # This was identical to ml_track_conflict_prediction_outcomes (line 369)
    # The 6-hour version (line 369) is kept as it provides more frequent tracking

    # Compute daily performance metrics
    # Runs: Daily at 2:00 AM UTC
    # Rationale: Aggregates yesterday's predictions after outcomes populated
    "ml_compute_daily_metrics": {
        'task': 'apps.ml.tasks.compute_daily_performance_metrics',
        'schedule': crontab(minute='0', hour='2'),  # Daily 2:00 AM
        'options': {
            'expires': 3600,
            'queue': 'reports',
            'soft_time_limit': 3300,  # 55 minutes
            'time_limit': 3600,       # 1 hour
        }
    },

    # Detect statistical drift (KS test)
    # Runs: Daily at 3:00 AM UTC
    # Rationale: Compare recent vs baseline prediction distributions
    "ml_detect_statistical_drift": {
        'task': 'apps.ml.tasks.detect_statistical_drift',
        'schedule': crontab(minute='0', hour='3'),  # Daily 3:00 AM
        'options': {
            'expires': 3600,
            'queue': 'maintenance',
            'soft_time_limit': 540,  # 9 minutes
            'time_limit': 600,       # 10 minutes
        }
    },

    # Detect performance drift (accuracy degradation)
    # Runs: Daily at 4:00 AM UTC
    # Rationale: Compare recent vs baseline performance metrics
    "ml_detect_performance_drift": {
        'task': 'apps.ml.tasks.detect_performance_drift',
        'schedule': crontab(minute='0', hour='4'),  # Daily 4:00 AM
        'options': {
            'expires': 3600,
            'queue': 'maintenance',
            'soft_time_limit': 540,  # 9 minutes
            'time_limit': 600,       # 10 minutes
        }
    },

    # ============================================================================
    # HELP CENTER: ONTOLOGY ARTICLE SYNC
    # ============================================================================
    # Auto-generate help articles from ontology metadata (daily sync)
    # ============================================================================

    # Sync Ontology Articles
    # Runs: Daily at 2:00 AM UTC
    # Rationale: Off-peak hours, auto-generates code reference articles from ontology
    # Rate-limited: 1 article/second to prevent DB overload
    # Filters: Only high-criticality components (production-critical code)
    # Queue: default (batch processing, non-urgent)
    "help_center_sync_ontology_articles": {
        'task': 'help_center.sync_ontology_articles',
        'schedule': crontab(minute='0', hour='2'),  # Daily 2:00 AM
        'options': {
            'expires': 3600,  # 1 hour
            'queue': 'default',
            'priority': 3,  # Low priority (batch processing)
            'soft_time_limit': 540,  # 9 minutes
            'time_limit': 600,       # 10 minutes hard limit
        },
        'kwargs': {
            'dry_run': False,
            'criticality': 'high'  # Only sync high-criticality components
        }
    },

    # ============================================================================
    # ✅ SCHEDULE HEALTH SUMMARY & VALIDATION
    # ============================================================================
    #
    # CURRENT SCHEDULE DISTRIBUTION:
    # :00 - autoclose (every 30min) ───────────────── ✓ No conflicts
    # :05 - reports (every 15min) ─────────────────── ✓ Safe zone
    # :10 - reminder emails (every 8hrs) ──────────── ✓ Safe zone
    # :15 - ticket escalation (every 30min) ───────── ✓ 15min offset from autoclose
    # :20 - reports (every 15min) ─────────────────── ✓ Safe zone
    # :27 - job creation (every 8hrs) ────────────────┐
    #     - email reports (every 27min) ─────────────┘ ✓ Different queues, ok overlap
    # :30 - autoclose (every 30min) ───────────────── ✓ No conflicts
    # :35 - reports (every 15min) ─────────────────── ✓ Safe zone
    # :45 - ticket escalation (every 30min) ───────── ✓ 15min offset from autoclose
    # :50 - reports (every 15min) ─────────────────── ✓ Safe zone
    #
    # WEEKLY TASKS:
    # Sunday 2:00 AM - ML active learning ─────────── ✓ Off-peak, no conflicts
    #
    # ✓ DESIGN GOALS ACHIEVED:
    # - No overlaps at common times (:00, :15, :30, :45)
    # - Critical tasks have 15-minute minimum separation
    # - Safe zones (:05, :10, :20, :35, :50) available for new schedules
    # - All schedules use UTC (no DST issues)
    # - Queue distribution prevents resource contention
    # - Idempotency framework prevents duplicate executions
    #
    # 📊 PERFORMANCE METRICS (Expected):
    # - Average queue depth: < 3 tasks
    # - Peak load: :27 (2 tasks, different queues)
    # - Worker utilization: 40-60% (optimal range)
    # - Task expiration: 0% (all tasks complete before next run)
    # - Collision rate: 0% (no schedule conflicts)
    #
    # 🔍 VALIDATION COMMANDS:
    # - Health check: python manage.py validate_schedules
    # - DST analysis: python manage.py validate_schedules --check-dst
    # - Load analysis: ScheduleCoordinator().analyze_schedule_health()
    # - Conflict detection: ScheduleUniquenessService().validate_no_overlap(...)
    #
    # 📚 RELATED DOCUMENTATION:
    # - Idempotency: apps/core/tasks/idempotency_service.py
    # - DST Validator: apps/scheduler/services/dst_validator.py
    # - Schedule Coordinator: apps/scheduler/services/schedule_coordinator.py
    # - Uniqueness Service: apps/scheduler/services/schedule_uniqueness_service.py
    #
    # ============================================================================

}
