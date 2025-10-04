"""
Backward Compatibility Imports - Phase 4

Refactored from: background_tasks/tasks.py
Date: 2025-09-30
"""

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

from .job_tasks import (
    autoclose_job,
    create_ppm_job,
    task_every_min,
)

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

from .integration_tasks import (
    publish_mqtt,
    validate_mqtt_topic,
    validate_mqtt_payload,
    process_graphql_mutation_async,
    process_graphql_download_async,
    external_api_call_async,
    insert_json_records_async,
)

from .media_tasks import (
    perform_facerecognition_bgt,
    move_media_to_cloud_storage,
    process_audio_transcript,
)

from .maintenance_tasks import (
    cache_warming_scheduled,
    cleanup_expired_pdf_tasks,
)

from .ticket_tasks import (
    send_ticket_email,
    ticket_escalation,
    alert_sendmail,
)

from .non_negotiables_tasks import (
    evaluate_non_negotiables,
)

from .site_audit_tasks import (
    site_heartbeat_5min,
    site_audit_15min,
    site_deep_analysis_1hour,
)

