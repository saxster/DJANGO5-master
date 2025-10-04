"""
Backward Compatibility Imports for Refactored Background Tasks

This module maintains 100% backward compatibility while tasks are refactored
into focused, domain-driven modules.

Refactoring Date: 2025-09-30
Phase: God File Elimination - Phase 4
Original File: background_tasks/tasks.py (2,286 lines)
New Structure: 7 focused task modules

IMPORTANT: All task names preserved for Celery compatibility.
"""

# Email Notification Tasks
from .email_tasks import (
    send_email_notification_for_workpermit_approval,
    send_email_notification_for_wp,
    send_email_notification_for_wp_verifier,
    send_email_notification_for_wp_from_mobile_for_verifier,
    send_email_notification_for_vendor_and_security_of_wp_cancellation,
    send_email_notification_for_vendor_and_security_for_rwp,
    send_email_notification_for_vendor_and_security_after_approval,
    send_email_notification_for_sla_vendor,
    send_email_notification_for_sla_report,
    send_reminder_email,
    send_mismatch_notification,
)

# Job Management Tasks
from .job_tasks import (
    autoclose_job,
    create_ppm_job,
    task_every_min,
)

# Report Generation Tasks  
from .report_tasks import (
    create_report_history,
    create_save_report_async,
    create_scheduled_reports,
    send_report_on_email,
    send_generated_report_on_mail,
    send_generated_report_onfly_email,
    generate_pdf_async,
    cleanup_reports_which_are_12hrs_old,
)

# Integration Tasks (MQTT, GraphQL, APIs)
from .integration_tasks import (
    publish_mqtt,
    validate_mqtt_topic,
    validate_mqtt_payload,
    process_graphql_mutation_async,
    process_graphql_download_async,
    external_api_call_async,
    insert_json_records_async,
)

# Media Processing Tasks
from .media_tasks import (
    perform_facerecognition_bgt,
    move_media_to_cloud_storage,
    process_audio_transcript,
)

# Maintenance Tasks
from .maintenance_tasks import (
    cache_warming_scheduled,
    cleanup_expired_pdf_tasks,
)

# Ticket Tasks
from .ticket_tasks import (
    send_ticket_email,
    ticket_escalation,
    alert_sendmail,
)

# Export all task names for Celery autodiscovery
__all__ = [
    # Email tasks
    'send_email_notification_for_workpermit_approval',
    'send_email_notification_for_wp',
    'send_email_notification_for_wp_verifier',
    'send_email_notification_for_wp_from_mobile_for_verifier',
    'send_email_notification_for_vendor_and_security_of_wp_cancellation',
    'send_email_notification_for_vendor_and_security_for_rwp',
    'send_email_notification_for_vendor_and_security_after_approval',
    'send_email_notification_for_sla_vendor',
    'send_email_notification_for_sla_report',
    'send_reminder_email',
    'send_mismatch_notification',
    
    # Job tasks
    'autoclose_job',
    'create_ppm_job',
    'task_every_min',
    
    # Report tasks
    'create_report_history',
    'create_save_report_async',
    'create_scheduled_reports',
    'send_report_on_email',
    'send_generated_report_on_mail',
    'send_generated_report_onfly_email',
    'generate_pdf_async',
    'cleanup_reports_which_are_12hrs_old',
    
    # Integration tasks
    'publish_mqtt',
    'validate_mqtt_topic',
    'validate_mqtt_payload',
    'process_graphql_mutation_async',
    'process_graphql_download_async',
    'external_api_call_async',
    'insert_json_records_async',
    
    # Media tasks
    'perform_facerecognition_bgt',
    'move_media_to_cloud_storage',
    'process_audio_transcript',
    
    # Maintenance tasks
    'cache_warming_scheduled',
    'cleanup_expired_pdf_tasks',
    
    # Ticket tasks
    'send_ticket_email',
    'ticket_escalation',
    'alert_sendmail',
]

"""
Module Structure:

1. email_tasks.py - Email notification tasks (11 tasks)
2. job_tasks.py - Job lifecycle management (3 tasks)
3. report_tasks.py - Report generation & cleanup (8 tasks)
4. integration_tasks.py - MQTT, GraphQL, API calls (7 tasks)
5. media_tasks.py - Face recognition, media processing (3 tasks)
6. maintenance_tasks.py - Cleanup, cache warming (2 tasks)
7. ticket_tasks.py - Ticket operations (3 tasks)

Total: 37 tasks across 7 focused modules
"""
