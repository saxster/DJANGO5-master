"""
Core Background Tasks - REFACTORED

Demonstrates standardized patterns for common background tasks using
new base classes and consistent error handling patterns.

This file shows how to refactor tasks from the monolithic tasks.py file
into smaller, focused modules with consistent patterns.

Key Improvements:
- Standardized error handling and retry logic
- Circuit breaker patterns for external services
- Comprehensive logging and monitoring
- Task context management
- Performance tracking
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from io import BytesIO

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from apps.core.tasks import (
    BaseTask,
    EmailTask,
    ExternalServiceTask,
    MaintenanceTask,
    task_retry_policy,
    log_task_context,
    validate_email_recipients
)


logger = logging.getLogger('background_tasks')


@shared_task(base=MaintenanceTask, bind=True, **task_retry_policy('maintenance'))
def cache_warming_scheduled(self):
    """
    Scheduled task for automatic cache warming.

    REFACTORED: Enhanced with proper error handling and monitoring

    Runs daily at 2 AM to warm critical caches during off-peak hours.
    """

    with self.task_context():
        log_task_context('cache_warming_scheduled')

        try:
            from apps.core.services.cache_warming_service import warm_critical_caches_task

            result = warm_critical_caches_task()

            logger.info(
                f"Scheduled cache warming completed: {result.get('total_keys_warmed', 0)} keys warmed",
                extra={'result': result}
            )

            return result

        except ImportError as exc:
            logger.error(f"Cache warming service not found: {exc}")
            return {'success': False, 'error': 'service_not_found'}

        except Exception as exc:
            logger.error(f"Cache warming task failed: {exc}")
            raise  # Let MaintenanceTask handle retry logic


@shared_task(base=ExternalServiceTask, bind=True, **task_retry_policy('external_api'))
def publish_mqtt(self, topic: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Securely publish MQTT message with comprehensive input validation.

    REFACTORED: Enhanced with circuit breaker and external service patterns

    Args:
        topic: MQTT topic to publish to
        payload: Message payload data

    Returns:
        dict: Publication results
    """

    with self.task_context(topic=topic, payload_size=len(str(payload))):
        log_task_context('publish_mqtt', topic=topic, payload_size=len(str(payload)))

        # Validate MQTT topic
        try:
            validated_topic = validate_mqtt_topic(topic)
        except Exception as exc:
            logger.error(f"MQTT topic validation failed: {exc}")
            return {'success': False, 'error': 'invalid_topic'}

        # Validate and sanitize payload
        try:
            sanitized_payload = sanitize_mqtt_payload(payload)
        except Exception as exc:
            logger.error(f"MQTT payload validation failed: {exc}")
            return {'success': False, 'error': 'invalid_payload'}

        # Publish with circuit breaker protection
        try:
            with self.external_service_call('mqtt_broker', timeout=10):
                from scripts.utilities.mqtt_utils import publish_message

                result = publish_message(validated_topic, sanitized_payload)

                logger.info(f"MQTT message published successfully to topic: {validated_topic}")
                return {
                    'success': True,
                    'topic': validated_topic,
                    'message_id': result.get('message_id'),
                    'payload_size': len(json.dumps(sanitized_payload))
                }

        except Exception as exc:
            logger.error(f"MQTT publish failed for topic {validated_topic}: {exc}")
            raise  # ExternalServiceTask will handle retry with circuit breaker


@shared_task(base=EmailTask, bind=True, **task_retry_policy('email'))
def send_ticket_email(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send ticket notification email with secure error handling.

    REFACTORED: Enhanced email validation and error handling

    Args:
        ticket_data: Dictionary containing ticket information

    Returns:
        dict: Email sending results
    """

    with self.task_context(ticket_id=ticket_data.get('id')):
        log_task_context('send_ticket_email', ticket_id=ticket_data.get('id'))

        # Validate required ticket data
        required_fields = ['id', 'title', 'recipient_email', 'status']
        for field in required_fields:
            if field not in ticket_data:
                logger.error(f"Missing required field in ticket data: {field}")
                return {'success': False, 'error': f'missing_field_{field}'}

        try:
            # Validate email addresses
            recipients = validate_email_recipients([ticket_data['recipient_email']])

            # Prepare email content
            subject = f"Ticket #{ticket_data['id']}: {ticket_data['title']}"

            message = f"""
            Ticket Update Notification

            Ticket ID: {ticket_data['id']}
            Title: {ticket_data['title']}
            Status: {ticket_data['status']}
            Updated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

            {ticket_data.get('description', '')}

            Please log in to the system for more details.
            """

            # Send email with proper error handling
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients
            )

            email.send(fail_silently=False)

            logger.info(f"Ticket email sent successfully for ticket {ticket_data['id']}")
            return {
                'success': True,
                'ticket_id': ticket_data['id'],
                'recipients': recipients,
                'subject': subject
            }

        except Exception as exc:
            logger.error(f"Failed to send ticket email: {exc}")
            raise  # EmailTask will handle email-specific retry logic


@shared_task(base=MaintenanceTask, bind=True, **task_retry_policy('maintenance'))
def auto_close_jobs(self, job_criteria: Optional[Dict[str, Any]] = None):
    """
    Auto-close jobs based on criteria.

    REFACTORED: Enhanced with batch processing and better error handling

    Args:
        job_criteria: Optional criteria for job selection

    Returns:
        dict: Processing results
    """

    with self.task_context(job_criteria=job_criteria):
        log_task_context('auto_close_jobs', criteria=job_criteria)

        from apps.activity.models import Jobneed
        from django.template.loader import render_to_string

        # Default criteria for auto-closing jobs
        default_criteria = {
            'status__in': ['pending', 'in_progress'],
            'created__lte': timezone.now() - timedelta(days=30),
            'auto_close_enabled': True
        }

        criteria = job_criteria or default_criteria

        # Get jobs to auto-close
        try:
            jobs_to_close = list(Jobneed.objects.filter(**criteria))

            if not jobs_to_close:
                logger.info("No jobs found for auto-closing")
                return {
                    'success': True,
                    'jobs_processed': 0,
                    'jobs_closed': 0
                }

        except Exception as exc:
            logger.error(f"Failed to query jobs for auto-closing: {exc}")
            raise

        # Batch process job closures
        def close_job(job):
            try:
                with transaction.atomic():
                    job.status = 'auto_closed'
                    job.closed_at = timezone.now()
                    job.closure_reason = 'Automatically closed due to inactivity'
                    job.save()

                    # Send notification if required
                    if hasattr(job, 'requester') and job.requester:
                        send_job_closure_notification.delay(job.id)

                return True

            except Exception as exc:
                logger.error(f"Failed to close job {job.id}: {exc}")
                raise

        # Process jobs in batches
        results = self.batch_process(
            jobs_to_close,
            batch_size=50,
            process_func=close_job
        )

        logger.info(f"Auto-close jobs completed: {results}")
        return {
            'success': True,
            'jobs_found': len(jobs_to_close),
            **results
        }


@shared_task(base=EmailTask, bind=True, **task_retry_policy('email'))
def send_job_closure_notification(self, job_id: int):
    """
    Send notification about job auto-closure.

    REFACTORED: Separated from main auto-close logic for better error handling

    Args:
        job_id: ID of the closed job

    Returns:
        dict: Notification results
    """

    with self.task_context(job_id=job_id):
        log_task_context('send_job_closure_notification', job_id=job_id)

        from apps.activity.models import Jobneed

        try:
            job = Jobneed.objects.get(id=job_id)
            if not job.requester or not job.requester.email:
                logger.warning(f"No requester email for job {job_id}")
                return {'success': False, 'error': 'no_requester_email'}

            # Validate email
            recipients = validate_email_recipients([job.requester.email])

            # Prepare notification
            subject = f"Job #{job_id} Auto-Closed"
            message = f"""
            Dear {job.requester.get_full_name()},

            Your job request has been automatically closed due to inactivity.

            Job Details:
            - ID: #{job_id}
            - Title: {job.title}
            - Created: {job.created.strftime('%Y-%m-%d')}
            - Closed: {job.closed_at.strftime('%Y-%m-%d %H:%M')}

            If you need to reopen this job, please contact support.

            Best regards,
            System Administration
            """

            # Send notification
            email = EmailMessage(
                subject=subject,
                body=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients
            )

            email.send(fail_silently=False)

            logger.info(f"Job closure notification sent for job {job_id}")
            return {
                'success': True,
                'job_id': job_id,
                'recipient': recipients[0]
            }

        except Exception as exc:
            logger.error(f"Failed to send job closure notification: {exc}")
            raise


@shared_task(base=MaintenanceTask, bind=True, **task_retry_policy('maintenance'))
def cleanup_expired_uploads(self, days_old: int = 7):
    """
    Clean up expired file uploads.

    REFACTORED: Enhanced with batch processing and file system safety

    Args:
        days_old: Number of days after which uploads are considered expired

    Returns:
        dict: Cleanup results
    """

    with self.task_context(days_old=days_old):
        log_task_context('cleanup_expired_uploads', days_old=days_old)

        import os
        from apps.core.models.upload_session import UploadSession

        cutoff_date = timezone.now() - timedelta(days=days_old)

        # Get expired upload sessions
        try:
            expired_sessions = list(
                UploadSession.objects.filter(
                    created_at__lt=cutoff_date,
                    status__in=['completed', 'failed', 'expired']
                )
            )

            if not expired_sessions:
                logger.info("No expired upload sessions found")
                return {
                    'success': True,
                    'sessions_processed': 0,
                    'files_deleted': 0
                }

        except Exception as exc:
            logger.error(f"Failed to query expired upload sessions: {exc}")
            raise

        # Batch process cleanup
        def cleanup_session(session):
            files_deleted = 0
            try:
                # Clean up associated files
                if hasattr(session, 'file_path') and session.file_path:
                    if os.path.exists(session.file_path):
                        os.remove(session.file_path)
                        files_deleted += 1

                # Clean up temp files
                if hasattr(session, 'temp_files'):
                    for temp_file in session.temp_files or []:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                            files_deleted += 1

                # Delete session record
                session.delete()

                return files_deleted

            except Exception as exc:
                logger.error(f"Failed to cleanup session {session.id}: {exc}")
                raise

        # Process cleanup in batches
        total_files_deleted = 0
        results = {'total': len(expired_sessions), 'processed': 0, 'failed': 0}

        for session in expired_sessions:
            try:
                files_deleted = cleanup_session(session)
                total_files_deleted += files_deleted
                results['processed'] += 1
            except Exception as exc:
                logger.warning(f"Failed to cleanup session {session.id}: {exc}")
                results['failed'] += 1

        logger.info(f"Upload cleanup completed: {results}")
        return {
            'success': True,
            'files_deleted': total_files_deleted,
            **results
        }


# Utility functions for MQTT validation
def validate_mqtt_topic(topic: str) -> str:
    """
    Validate MQTT topic for security and format compliance.

    Args:
        topic: MQTT topic string

    Returns:
        Validated topic string

    Raises:
        ValueError: If topic validation fails
    """
    import re

    if not topic or not isinstance(topic, str):
        raise ValueError("Topic must be a non-empty string")

    # Basic topic validation
    if len(topic) > 65535:
        raise ValueError("Topic too long")

    # Check for prohibited characters
    prohibited_chars = ['+', '#', '\x00']
    for char in prohibited_chars:
        if char in topic:
            raise ValueError(f"Topic contains prohibited character: {char}")

    # Topic structure validation
    if not re.match(r'^[a-zA-Z0-9/_-]+$', topic):
        raise ValueError("Topic contains invalid characters")

    return topic.strip()


def sanitize_mqtt_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize MQTT payload for security.

    Args:
        payload: Payload dictionary

    Returns:
        Sanitized payload dictionary

    Raises:
        ValueError: If payload is invalid
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary")

    # Size limit check
    payload_str = json.dumps(payload)
    if len(payload_str) > 256000:  # 256KB limit
        raise ValueError("Payload too large")

    # Sanitize values
    sanitized = {}
    for key, value in payload.items():
        if isinstance(key, str) and len(key) <= 100:
            if isinstance(value, (str, int, float, bool, type(None))):
                if isinstance(value, str) and len(value) <= 10000:
                    sanitized[key] = value
                elif not isinstance(value, str):
                    sanitized[key] = value
            elif isinstance(value, (list, dict)) and len(json.dumps(value)) <= 50000:
                sanitized[key] = value

    return sanitized