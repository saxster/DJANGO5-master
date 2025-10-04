"""
Standardized Idempotency Key Generation Patterns

Provides consistent key generation functions for all background tasks.
Each function creates a unique key that prevents duplicate execution
while allowing intentional re-execution when parameters change.

Key Design Principles:
- Include all parameters that make execution unique
- Use date/time boundaries for periodic tasks
- Include user/tenant context for scoped operations
- Hash complex objects for deterministic keys

Usage:
    from background_tasks.task_keys import autoclose_key, report_generation_key

    # Generate key for autoclose task
    key = autoclose_key(job_id=123, execution_date=date.today())

    # Use with idempotency service
    if not check_duplicate(key):
        execute_autoclose(job_id)
"""

import hashlib
import json
from datetime import date, datetime
from typing import Dict, Any, Optional


def autoclose_key(job_id: int, execution_date: date) -> str:
    """
    Unique key for job autoclose operations.

    Ensures: One autoclose per job per day

    Args:
        job_id: Job identifier
        execution_date: Date of execution (not time, to allow retries same day)

    Returns:
        Idempotency key

    Example:
        key = autoclose_key(123, date(2025, 10, 1))
        # Returns: 'autoclose:123:2025-10-01'
    """
    return f"autoclose:{job_id}:{execution_date.isoformat()}"


def checkpoint_autoclose_key(checkpoint_ids: list, execution_date: date) -> str:
    """
    Unique key for batch checkpoint autoclose.

    Ensures: One batch autoclose per checkpoint set per day

    Args:
        checkpoint_ids: List of checkpoint IDs
        execution_date: Date of execution

    Returns:
        Idempotency key
    """
    checkpoint_hash = hashlib.sha256(
        json.dumps(sorted(checkpoint_ids)).encode()
    ).hexdigest()[:16]

    return f"checkpoint_autoclose:{checkpoint_hash}:{execution_date.isoformat()}"


def ticket_escalation_key(ticket_id: int, escalation_level: int, execution_date: date) -> str:
    """
    Unique key for ticket escalation operations.

    Ensures: One escalation per ticket per level per day

    Args:
        ticket_id: Ticket identifier
        escalation_level: Current escalation level
        execution_date: Date of execution

    Returns:
        Idempotency key

    Example:
        key = ticket_escalation_key(456, 2, date.today())
        # Returns: 'escalation:456:L2:2025-10-01'
    """
    return f"escalation:{ticket_id}:L{escalation_level}:{execution_date.isoformat()}"


def report_generation_key(
    report_name: str,
    params: Dict[str, Any],
    user_id: int,
    format: str = 'pdf'
) -> str:
    """
    Unique key for report generation.

    Ensures: One report per params per user per format

    Args:
        report_name: Report template name
        params: Report parameters (date range, filters, etc.)
        user_id: User requesting report
        format: Output format (pdf, excel, csv)

    Returns:
        Idempotency key

    Example:
        key = report_generation_key(
            'attendance_summary',
            {'start_date': '2025-10-01', 'end_date': '2025-10-31'},
            user_id=789,
            format='pdf'
        )
    """
    # Hash parameters for deterministic key
    params_str = json.dumps(params, sort_keys=True, default=str)
    params_hash = hashlib.sha256(params_str.encode()).hexdigest()[:16]

    return f"report:{report_name}:{params_hash}:U{user_id}:{format}"


def graphql_mutation_key(
    mutation_name: str,
    variables: Dict[str, Any],
    user_id: int,
    timestamp_window: Optional[datetime] = None
) -> str:
    """
    Unique key for GraphQL mutation operations.

    Ensures: One mutation per variables per user per time window

    Args:
        mutation_name: GraphQL mutation name
        variables: Mutation variables
        user_id: User executing mutation
        timestamp_window: Optional timestamp rounded to minute (for deduplication window)

    Returns:
        Idempotency key

    Example:
        key = graphql_mutation_key(
            'createJob',
            {'jobName': 'Test Job', 'siteId': 5},
            user_id=789
        )
    """
    # Hash variables for deterministic key
    variables_str = json.dumps(variables, sort_keys=True, default=str)
    variables_hash = hashlib.sha256(variables_str.encode()).hexdigest()[:16]

    # Optional time window for short-term deduplication
    time_part = ''
    if timestamp_window:
        # Round to nearest minute for 1-minute deduplication window
        time_part = f":{timestamp_window.strftime('%Y%m%d%H%M')}"

    return f"mutation:{mutation_name}:{variables_hash}:U{user_id}{time_part}"


def bulk_insert_key(
    table_name: str,
    record_uuids: list,
    operation_type: str = 'upsert'
) -> str:
    """
    Unique key for bulk database insert/update operations.

    Ensures: One bulk operation per record set

    Args:
        table_name: Target table/model name
        record_uuids: List of record UUIDs being processed
        operation_type: Operation type (insert, update, upsert, delete)

    Returns:
        Idempotency key

    Example:
        key = bulk_insert_key(
            'Job',
            ['uuid1', 'uuid2', 'uuid3'],
            operation_type='upsert'
        )
    """
    # Hash UUIDs for deterministic key
    uuid_str = json.dumps(sorted(record_uuids), default=str)
    uuid_hash = hashlib.sha256(uuid_str.encode()).hexdigest()[:16]

    return f"bulk_{operation_type}:{table_name}:{uuid_hash}"


def email_notification_key(
    template_name: str,
    recipient: str,
    context_hash: str,
    date_boundary: date
) -> str:
    """
    Unique key for email notifications.

    Ensures: One email per template per recipient per context per day

    Args:
        template_name: Email template name
        recipient: Recipient email address
        context_hash: Hash of email context/data
        date_boundary: Date boundary (prevents re-sending same day)

    Returns:
        Idempotency key

    Example:
        context_data = {'job_id': 123, 'status': 'completed'}
        context_hash = hashlib.sha256(str(context_data).encode()).hexdigest()[:16]
        key = email_notification_key(
            'job_completion_notification',
            'user@example.com',
            context_hash,
            date.today()
        )
    """
    # Normalize email address
    recipient_normalized = recipient.lower().strip()

    return f"email:{template_name}:{recipient_normalized}:{context_hash}:{date_boundary.isoformat()}"


def scheduled_task_key(
    schedule_id: int,
    execution_time: datetime,
    task_type: str
) -> str:
    """
    Unique key for scheduled task execution.

    Ensures: One execution per schedule per time slot

    Args:
        schedule_id: Schedule definition ID
        execution_time: Planned execution time (rounded to minute)
        task_type: Type of scheduled task

    Returns:
        Idempotency key

    Example:
        key = scheduled_task_key(
            schedule_id=42,
            execution_time=datetime(2025, 10, 1, 14, 30),
            task_type='ppm_generation'
        )
        # Returns: 'schedule:42:ppm_generation:202510011430'
    """
    # Round to minute for deduplication
    time_slot = execution_time.strftime('%Y%m%d%H%M')

    return f"schedule:{schedule_id}:{task_type}:{time_slot}"


def ppm_generation_key(
    schedule_id: int,
    site_id: int,
    generation_date: date
) -> str:
    """
    Unique key for PPM (Planned Preventive Maintenance) generation.

    Ensures: One PPM generation per schedule per site per day

    Args:
        schedule_id: PPM schedule ID
        site_id: Site/location ID
        generation_date: Date of generation

    Returns:
        Idempotency key
    """
    return f"ppm:S{schedule_id}:site{site_id}:{generation_date.isoformat()}"


def cache_warming_key(
    cache_category: str,
    execution_datetime: datetime
) -> str:
    """
    Unique key for cache warming operations.

    Ensures: One cache warming per category per execution window

    Args:
        cache_category: Category of cache to warm (e.g., 'select2', 'reports')
        execution_datetime: Execution time (rounded to hour)

    Returns:
        Idempotency key
    """
    # Round to hour for deduplication window
    execution_hour = execution_datetime.strftime('%Y%m%d%H')

    return f"cache_warming:{cache_category}:{execution_hour}"


def media_migration_key(
    file_path: str,
    destination: str,
    migration_batch: str
) -> str:
    """
    Unique key for media file migrations (e.g., to cloud storage).

    Ensures: One migration per file per destination per batch

    Args:
        file_path: Source file path
        destination: Destination (e.g., 'gcs', 's3')
        migration_batch: Batch identifier (e.g., date of migration)

    Returns:
        Idempotency key
    """
    # Hash file path for security (don't expose paths in logs)
    path_hash = hashlib.sha256(file_path.encode()).hexdigest()[:16]

    return f"media_migration:{destination}:{path_hash}:{migration_batch}"


def cleanup_task_key(
    cleanup_type: str,
    target_path: str,
    age_threshold_hours: int,
    execution_date: date
) -> str:
    """
    Unique key for cleanup/maintenance tasks.

    Ensures: One cleanup per target per threshold per day

    Args:
        cleanup_type: Type of cleanup (e.g., 'old_files', 'expired_sessions')
        target_path: Target path or identifier
        age_threshold_hours: Age threshold in hours
        execution_date: Date of execution

    Returns:
        Idempotency key
    """
    # Hash target path to avoid exposing system paths
    target_hash = hashlib.sha256(target_path.encode()).hexdigest()[:16]

    return f"cleanup:{cleanup_type}:{target_hash}:age{age_threshold_hours}h:{execution_date.isoformat()}"


# Helper function for custom key generation
def custom_task_key(task_name: str, **kwargs) -> str:
    """
    Generate custom idempotency key for tasks not covered by standard patterns.

    Args:
        task_name: Name of the task
        **kwargs: Key-value pairs that uniquely identify this execution

    Returns:
        Idempotency key

    Example:
        key = custom_task_key(
            'sync_external_api',
            api_name='weather_service',
            sync_type='full',
            timestamp=datetime.now().date()
        )
    """
    # Sort kwargs for deterministic key
    kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
    kwargs_hash = hashlib.sha256(kwargs_str.encode()).hexdigest()[:16]

    return f"custom:{task_name}:{kwargs_hash}"
