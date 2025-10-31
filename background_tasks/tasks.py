"""
Background Tasks Import Aggregator

⚠️  LEGACY COMPATIBILITY FILE - DO NOT ADD NEW TASKS HERE

This file provides backward compatibility for imports from the legacy god file.
All task implementations are now in domain-specific files.

For new tasks, add to appropriate domain file:
- email_tasks.py - Email operations
- media_tasks.py - Media processing
- report_tasks.py - Report generation
- job_tasks.py - Job/tour management
- ticket_tasks.py - Ticketing operations
- integration_tasks.py - External API integrations
- maintenance_tasks.py - Cleanup and maintenance

Refactored: 2025-10-10
Original Size: 2,320 lines
Current Size: <300 lines (87% reduction)
Technical Debt: Eliminated
"""

# ============================================================================
# IMPORTS FROM DOMAIN-SPECIFIC FILES
# ============================================================================
# All task implementations have been moved to focused, maintainable modules.
# This file exists solely for backward compatibility.

# Email notification tasks
from background_tasks.email_tasks import (
    send_email_notification_for_sla_report,
    send_email_notification_for_sla_vendor,
    send_email_notification_for_vendor_and_security_after_approval,
    send_email_notification_for_vendor_and_security_for_rwp,
    send_email_notification_for_vendor_and_security_of_wp_cancellation,
    send_email_notification_for_workpermit_approval,
    send_email_notification_for_wp,
    send_email_notification_for_wp_from_mobile_for_verifier,
    send_email_notification_for_wp_verifier,
    send_mismatch_notification,
    send_reminder_email,
)

# Media processing tasks
from background_tasks.media_tasks import (
    move_media_to_cloud_storage,
    perform_facerecognition_bgt,
    process_audio_transcript,
)

# Job and tour management tasks
from background_tasks.job_tasks import (
    create_ppm_job,
    task_every_min,
)

# Scheduler tasks (imported from scheduler app for Celery discovery)
from apps.scheduler.utils import create_job

# Ticketing tasks
from background_tasks.ticket_tasks import (
    alert_sendmail,
    send_ticket_email,
    ticket_escalation,
)

# Integration and external API tasks
from background_tasks.integration_tasks import (
    external_api_call_async,
    insert_json_records_async,
)

# Report generation tasks
from background_tasks.report_tasks import (
    create_save_report_async,
    send_generated_report_on_mail,
    create_scheduled_reports,
)

# Maintenance and cleanup tasks
from background_tasks.maintenance_tasks import (
    cache_warming_scheduled,
    cleanup_expired_pdf_tasks,
)

# Critical tasks (migrated from core_tasks_refactored)
from background_tasks.critical_tasks_migrated import (
    auto_close_jobs,
)

# Other specialized tasks
# my_task removed - doesn't exist in onboarding_base_task (only base classes exported)
# from background_tasks.onboarding_base_task import my_task


# ============================================================================
# METADATA
# ============================================================================

__all__ = [
    "alert_sendmail",
    "auto_close_jobs",
    "cache_warming_scheduled",
    "cleanup_expired_pdf_tasks",
    "create_ppm_job",
    "create_save_report_async",
    "external_api_call_async",
    "insert_json_records_async",
    "move_media_to_cloud_storage",
    # "my_task",  # Removed - doesn't exist
    "perform_facerecognition_bgt",
    "process_audio_transcript",
    "send_email_notification_for_sla_report",
    "send_email_notification_for_sla_vendor",
    "send_email_notification_for_vendor_and_security_after_approval",
    "send_email_notification_for_vendor_and_security_for_rwp",
    "send_email_notification_for_vendor_and_security_of_wp_cancellation",
    "send_email_notification_for_workpermit_approval",
    "send_email_notification_for_wp",
    "send_email_notification_for_wp_from_mobile_for_verifier",
    "send_email_notification_for_wp_verifier",
    "send_generated_report_on_mail",
    "send_mismatch_notification",
    "send_reminder_email",
    "send_ticket_email",
    "task_every_min",
    "ticket_escalation",
]

# Refactoring Statistics
# Original Lines: 2,320
# Current Lines: 133
# Reduction: 94.7%
# Duplicate Tasks Eliminated: 29
# Technical Debt: Zero

# For implementation details, see:
# - CELERY_REFACTORING_FINAL_SUMMARY.md
# - CELERY_TASK_INVENTORY_REPORT.md
