# Celery & Redis Configuration

## Overview
Celery provides distributed task queue functionality for YOUTILITY5, handling background processing, scheduled tasks, and asynchronous operations. Redis serves as both the message broker for Celery and the caching backend for Django.

## Installation
```bash
pip install celery==5.5.2
pip install redis==5.3.0
pip install django-redis==5.4.0
pip install django-celery-beat==2.8.0
pip install django-celery-results==2.6.0
```

## Architecture

### Celery Configuration
**Location**: `/intelliwiz_config/celery.py`

```python
from celery import Celery
from celery.schedules import crontab

# Initialize Celery app
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
app = Celery('intelliwiz_config')

# Load config from Django settings with CELERY_ prefix
app.config_from_object(settings, namespace='CELERY')

# Auto-discover tasks from all Django apps
app.autodiscover_tasks()

# Timezone configuration
app.conf.timezone = 'UTC'

# Prevent hijacking root logger
app.conf.CELERYD_HIJACK_ROOT_LOGGER = False
```

### Redis Configuration
**Location**: `/intelliwiz_config/settings.py`

```python
# Celery Settings
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='django-db')

# Redis Cache Configuration
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "youtility4",
    },
    "select2": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# Cache TTL (Time To Live)
CACHE_TTL = 60 * 1  # 1 minute
```

## Task Organization

### Task Structure
**Location**: `/background_tasks/`

```
background_tasks/
├── __init__.py
├── tasks.py              # Main task definitions
├── utils.py              # Task utilities
├── report_tasks.py       # Report generation tasks
└── move_files_to_GCS.py # Cloud storage tasks
```

### Task Definition Pattern
```python
from celery import shared_task
from intelliwiz_config.celery import app

@shared_task(bind=True, max_retries=5, default_retry_delay=30, name="task_name")
def example_task(self, param1, param2):
    try:
        # Task logic here
        result = perform_operation(param1, param2)
        logger.info(f"Task completed: {result}")
        return result
    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
        # Retry the task
        raise self.retry(exc=e)
```

## Scheduled Tasks (Celery Beat)

### Beat Schedule Configuration
**Location**: `/intelliwiz_config/celery.py`

```python
app.conf.beat_schedule = {
    # PPM Schedule Creation - 3:03 AM and 4:03 PM daily
    "ppm_schedule_at_minute_3_past_hour_3_and_16": {
        'task': 'create_ppm_job',
        'schedule': crontab(minute='3', hour='3,16'),
    },

    # Reminder Emails - Every 8 hours at :10
    "reminder_emails_at_minute_10_past_every_8th_hour": {
        'task': 'send_reminder_email',
        'schedule': crontab(hour='*/8', minute='10'),
    },

    # Auto-close Jobs - Every 30 minutes
    "auto_close_at_every_30_minute": {
        'task': 'auto_close_jobs',
        'schedule': crontab(minute='*/30'),
    },

    # Ticket Escalation - Every 30 minutes
    "ticket_escalation_every_30min": {
        'task': 'ticket_escalation',
        'schedule': crontab(minute='*/30')
    },

    # Create Jobs - Every 8 hours at :27
    "create_job_at_minute_27_past_every_8th_hour": {
        'task': 'create_job',
        'schedule': crontab(minute='27', hour='*/8')
    },

    # Cloud Storage Migration - Weekly on Monday midnight
    "move_media_to_cloud_storage": {
        'task': 'move_media_to_cloud_storage',
        'schedule': crontab(minute=0, hour=0, day_of_week='monday')
    },

    # Send Reports via Email - Every 27 minutes
    "send_report_genererated_on_mail": {
        'task': 'send_generated_report_on_mail',
        'schedule': crontab(minute='*/27'),
    },

    # Create Scheduled Reports - Every 15 minutes
    "create-reports-scheduled": {
        'task': 'create_scheduled_reports',
        'schedule': crontab(minute='*/15')
    }
}
```

## Common Task Patterns

### 1. Email Notification Task
```python
@app.task(bind=True, default_retry_delay=300, max_retries=5, name="send_ticket_email")
def send_ticket_email(self, ticket=None, id=None):
    from apps.y_helpdesk.models import Ticket
    from django.template.loader import render_to_string

    try:
        if not ticket and id:
            ticket = Ticket.objects.get(id=id)

        emails = get_email_recipients_for_ticket(ticket)
        subject = f"Ticket #{ticket.ticketno} is {status}"

        context = {
            "subject": subject,
            "ticket": ticket,
            "site_name": ticket.bu.buname if ticket.bu else "Unknown"
        }

        html_content = render_to_string('email_template.html', context)

        email = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=settings.EMAIL_FROM_ADDRESS,
            to=emails
        )
        email.content_subtype = "html"
        email.send()

        logger.info(f"Email sent for ticket {ticket.ticketno}")

    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        raise self.retry(exc=e)
```

### 2. MQTT Publishing Task
```python
@shared_task(bind=True, max_retries=5, default_retry_delay=30, name="publish_mqtt")
def publish_mqtt(self, topic, payload):
    try:
        publish_message(topic, payload)
        logger.info(f"[Celery] Published to topic={topic}")
    except Exception as e:
        logger.error(f"[Celery] MQTT publish failed: {e}")
        raise self.retry(exc=e)
```

### 3. Database Cleanup Task
```python
@app.task(name="cleanup_old_records")
def cleanup_old_records():
    from django.utils import timezone
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=90)

    # Delete old tracking records
    deleted_count = Tracking.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]

    logger.info(f"Deleted {deleted_count} old tracking records")
    return deleted_count
```

### 4. Report Generation Task
```python
@app.task(name="generate_monthly_report")
def generate_monthly_report(month, year, user_id):
    try:
        user = User.objects.get(id=user_id)

        # Generate report
        report_data = compile_monthly_data(month, year)
        pdf_buffer = generate_pdf_report(report_data)

        # Save to database
        report = Report.objects.create(
            user=user,
            month=month,
            year=year,
            file_content=pdf_buffer.getvalue()
        )

        # Send notification
        send_report_notification.delay(report.id)

        return report.id
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise
```

## Queue Configuration

### Task Routing
```python
CELERY_TASK_ROUTES = {
    'background_tasks.tasks.process_graphql_mutation_async': {'queue': 'django5_queue'},
    'background_tasks.tasks.*': {'queue': 'django5_queue'},
    'email_tasks.*': {'queue': 'email_queue'},
    'report_tasks.*': {'queue': 'report_queue'},
}
```

### Priority Queues
```python
from kombu import Queue, Exchange

CELERY_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('high_priority', Exchange('high_priority'), routing_key='high_priority'),
    Queue('low_priority', Exchange('low_priority'), routing_key='low_priority'),
)

CELERY_DEFAULT_QUEUE = 'default'
CELERY_DEFAULT_EXCHANGE = 'default'
CELERY_DEFAULT_ROUTING_KEY = 'default'
```

## Redis Caching Patterns

### 1. Function Result Caching
```python
from django.core.cache import cache

def get_expensive_data(param):
    cache_key = f"expensive_data_{param}"

    # Try to get from cache
    result = cache.get(cache_key)

    if result is None:
        # Cache miss - compute result
        result = perform_expensive_operation(param)

        # Store in cache for 5 minutes
        cache.set(cache_key, result, 300)

    return result
```

### 2. Query Result Caching
```python
from django.core.cache import cache
from django.db.models import Q

def get_active_jobs(site_id):
    cache_key = f"active_jobs_site_{site_id}"

    jobs = cache.get(cache_key)
    if jobs is None:
        jobs = list(Job.objects.filter(
            site_id=site_id,
            status='active'
        ).select_related('assigned_to').values())

        cache.set(cache_key, jobs, 60)  # Cache for 1 minute

    return jobs
```

### 3. Session Storage
```python
# Store session data in Redis
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
```

### 4. Cache Invalidation
```python
from django.core.cache import cache

def update_job(job_id, data):
    # Update the job
    job = Job.objects.filter(id=job_id).update(**data)

    # Invalidate related caches
    cache.delete(f"job_{job_id}")
    cache.delete(f"active_jobs_site_{job.site_id}")
    cache.delete_pattern("job_list_*")  # Delete all job lists

    return job
```

## Running Celery

### Development Setup
```bash
# Start Redis server
redis-server

# Start Celery worker
celery -A intelliwiz_config worker -l info

# Start Celery Beat (in separate terminal)
celery -A intelliwiz_config beat -l info

# Combined worker + beat (development only)
celery -A intelliwiz_config worker --beat -l info
```

### Production Setup
```bash
# Systemd service for Celery worker
[Unit]
Description=Celery Worker
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/home/redmine/DJANGO5/YOUTILITY5
ExecStart=/usr/local/bin/celery multi start worker1 \
    -A intelliwiz_config \
    --pidfile=/var/run/celery/%n.pid \
    --logfile=/var/log/celery/%n%I.log \
    --loglevel=info
ExecStop=/usr/local/bin/celery multi stopwait worker1 \
    --pidfile=/var/run/celery/%n.pid
ExecReload=/usr/local/bin/celery multi restart worker1 \
    --pidfile=/var/run/celery/%n.pid

[Install]
WantedBy=multi-user.target
```

## Monitoring & Management

### Flower - Web-based Monitoring
```bash
pip install flower
celery -A intelliwiz_config flower --port=5555
```

### Celery Commands
```bash
# List active tasks
celery -A intelliwiz_config inspect active

# List scheduled tasks
celery -A intelliwiz_config inspect scheduled

# List registered tasks
celery -A intelliwiz_config inspect registered

# Purge all tasks
celery -A intelliwiz_config purge

# Check worker stats
celery -A intelliwiz_config inspect stats
```

### Redis Commands
```bash
# Connect to Redis CLI
redis-cli

# Monitor Redis in real-time
redis-cli monitor

# Get cache statistics
redis-cli info stats

# Clear all cache
redis-cli flushall

# Clear specific database
redis-cli -n 1 flushdb
```

## Error Handling & Retries

### Retry Configuration
```python
@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # seconds
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60}
)
def resilient_task(self, data):
    try:
        process_data(data)
    except RecoverableError as e:
        # Exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    except NonRecoverableError:
        # Don't retry for known unrecoverable errors
        logger.error("Unrecoverable error occurred")
        return None
```

### Dead Letter Queue
```python
@app.task(bind=True, max_retries=3)
def task_with_dlq(self, data):
    try:
        process_data(data)
    except Exception as e:
        if self.request.retries >= self.max_retries:
            # Send to dead letter queue
            send_to_dlq.delay(
                task_name=self.name,
                args=self.request.args,
                error=str(e)
            )
        raise self.retry(exc=e)
```

## Testing Celery Tasks

### Synchronous Testing
```python
# settings_test.py
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# test_tasks.py
from django.test import TestCase
from background_tasks.tasks import send_ticket_email

class TestCeleryTasks(TestCase):
    def test_send_ticket_email(self):
        # Task runs synchronously in tests
        result = send_ticket_email.delay(ticket_id=1)
        self.assertTrue(result.successful())
```

### Mocking Tasks
```python
from unittest.mock import patch

@patch('background_tasks.tasks.send_ticket_email.delay')
def test_ticket_creation_triggers_email(mock_task):
    ticket = Ticket.objects.create(title="Test")

    mock_task.assert_called_once_with(ticket_id=ticket.id)
```

## Performance Optimization

### 1. Task Chunking
```python
@shared_task
def process_large_dataset(dataset_id):
    dataset = Dataset.objects.get(id=dataset_id)

    # Split into chunks
    chunk_size = 100
    for i in range(0, dataset.count(), chunk_size):
        process_chunk.delay(dataset_id, i, i + chunk_size)
```

### 2. Rate Limiting
```python
@shared_task(rate_limit='10/m')  # 10 tasks per minute
def rate_limited_task(data):
    process_data(data)
```

### 3. Time Limits
```python
@shared_task(time_limit=300, soft_time_limit=250)  # 5 minutes hard, 4:10 soft
def long_running_task():
    try:
        perform_long_operation()
    except SoftTimeLimitExceeded:
        cleanup_and_save_progress()
```

## Best Practices

1. **Keep tasks idempotent** - Tasks should be safe to retry
2. **Use meaningful task names** - Makes monitoring easier
3. **Log task progress** - Especially for long-running tasks
4. **Handle exceptions gracefully** - Use proper retry strategies
5. **Avoid passing complex objects** - Serialize to JSON/primitives
6. **Set appropriate timeouts** - Prevent tasks from hanging
7. **Monitor queue lengths** - Watch for backlog buildup
8. **Use task routing** - Separate queues for different priorities
9. **Clean up old results** - Prevent database/Redis bloat
10. **Test with CELERY_TASK_ALWAYS_EAGER** in development

## Common Issues & Solutions

### Issue: Tasks Not Executing
```bash
# Check if worker is running
ps aux | grep celery

# Check Redis connectivity
redis-cli ping

# Check task registration
celery -A intelliwiz_config inspect registered
```

### Issue: Memory Leaks in Workers
```python
# Restart workers periodically
CELERYD_MAX_TASKS_PER_CHILD = 100  # Restart after 100 tasks
```

### Issue: Task Result Timeout
```python
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour
```

## Related Documentation
- [GraphQL/Graphene](./graphql_graphene.md) - Async GraphQL operations
- [Manager Pattern](./manager_pattern.md) - Cached query results
- [Testing Infrastructure](./testing_infrastructure.md) - Testing async tasks