# Background Processing Architecture

> **Enterprise-grade Celery configuration with specialized queues and monitoring**

---

## Queue Architecture

### Specialized Queues

| Queue | Priority | SLA | Use Cases |
|-------|----------|-----|-----------|
| `critical` | 10 | <2s | Crisis intervention, security alerts |
| `high_priority` | 8 | <3s | User-facing ops, biometrics |
| `email` | 7 | <5s | Email processing |
| `reports` | 6 | <60s | Analytics, ML processing |
| `external_api` | 5 | <10s | MQTT, third-party integrations |
| `maintenance` | 3 | <300s | Cleanup, cache warming |

---

## Worker Configuration

### Settings

- **Worker concurrency**: 8 workers
- **Prefetch multiplier**: 4x
- **Retry policy**: Exponential backoff with jitter (3 max)
- **Monitoring**: `TaskMetrics` with real-time tracking
- **Circuit breakers**: Automatic failure protection

### Starting Workers

```bash
# Start all optimized workers
./scripts/celery_workers.sh start

# Real-time monitoring dashboard
./scripts/celery_workers.sh monitor
```

---

## Retry Policy

### Default Configuration

```python
{
    'max_retries': 3,
    'interval_start': 0,
    'interval_step': 2,
    'interval_max': 10,
    'jitter': True  # Prevents thundering herd
}
```

### Per-Task Override

```python
from celery import shared_task

@shared_task(
    max_retries=5,
    default_retry_delay=60,  # 60 seconds
    retry_backoff=True,
    retry_jitter=True
)
def critical_api_call():
    pass
```

---

## Task Routing

### Automatic Routing

Tasks are automatically routed to appropriate queues based on configuration in `apps/core/tasks/celery_settings.py`:

```python
CELERY_TASK_ROUTES = {
    'send_reminder_email': {'queue': 'email'},
    'create_scheduled_reports': {'queue': 'reports'},
    'auto_close_jobs': {'queue': 'critical'},
    'process_mqtt_message': {'queue': 'external_api'},
}
```

### Manual Routing

```python
# Send to specific queue
task.apply_async(queue='critical')

# Override routing
task.apply_async(queue='high_priority', priority=10)
```

---

## Monitoring

### TaskMetrics Model

Real-time tracking of:
- Task execution count
- Success/failure rates
- Average execution time
- Queue depth
- Worker utilization

### Dashboards

```bash
# Celery worker dashboard
./scripts/celery_workers.sh monitor

# Task monitoring dashboard
open http://localhost:8000/admin/tasks/dashboard/

# Celery Flower (if installed)
celery -A intelliwiz_config flower
```

---

## Circuit Breakers

### Automatic Protection

The framework includes circuit breakers that:
1. Detect repeated failures
2. Stop sending tasks to failing workers
3. Automatically retry after cooldown period
4. Alert administrators of sustained issues

### Configuration

```python
# In apps/core/tasks/celery_settings.py
CIRCUIT_BREAKER = {
    'failure_threshold': 5,      # Failures before opening
    'recovery_timeout': 60,      # Seconds before retry
    'expected_exception': Exception,
}
```

---

## Race Condition Testing

### Critical for Data Integrity

```bash
# Run all race condition tests
python -m pytest -k "race" -v

# Specific test suites
python -m pytest apps/core/tests/test_background_task_race_conditions.py -v
python -m pytest apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py -v
python -m pytest apps/core/tests/test_atomic_json_field_updates.py -v

# Penetration testing
python comprehensive_race_condition_penetration_test.py --scenario all
```

---

## Best Practices

### ✅ DO

- Use appropriate queue for task priority
- Set realistic SLA targets
- Monitor task metrics regularly
- Test race conditions thoroughly
- Use idempotency framework
- Configure retries with jitter

### ❌ DON'T

- Put all tasks in default queue
- Ignore circuit breaker alerts
- Use blocking I/O in tasks
- Forget timeout parameters
- Skip race condition tests
- Use synchronous operations in async tasks

---

## Common Patterns

### Long-Running Tasks

```python
from celery import shared_task
from apps.core.tasks.base import ReportTask

@shared_task(base=ReportTask, bind=True, time_limit=600)
def generate_annual_report(self, year):
    # Long operation with progress tracking
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
    # ... processing ...
    return {'status': 'complete'}
```

### External API Calls

```python
from celery import shared_task
from apps.core.tasks.base import ExternalAPITask
import requests

@shared_task(base=ExternalAPITask, bind=True)
def fetch_weather_data(self, location):
    # Automatic retries with backoff
    response = requests.get(f'https://api.weather.com/{location}', timeout=(5, 15))
    return response.json()
```

### Chaining Tasks

```python
from celery import chain

# Execute tasks in sequence
result = chain(
    fetch_data.s(),
    process_data.s(),
    save_results.s()
).apply_async()
```

### Parallel Execution

```python
from celery import group

# Execute tasks in parallel
job = group(
    process_item.s(item) for item in items
)
results = job.apply_async()
```

---

## Troubleshooting

### Workers not processing tasks

```bash
# Check worker status
./scripts/celery_workers.sh status

# Restart workers
./scripts/celery_workers.sh restart

# Check queue depth
celery -A intelliwiz_config inspect active
```

### Tasks hanging

1. Check for missing timeout parameters
2. Verify network connectivity for external calls
3. Review circuit breaker status
4. Check worker logs: `logs/celery_*.log`

### High failure rates

1. Review TaskMetrics dashboard
2. Check circuit breaker alerts
3. Verify external service availability
4. Increase retry attempts if appropriate

---

**Last Updated**: October 29, 2025
**Maintainer**: Backend Team
**Related**: [Celery Configuration](CELERY_CONFIGURATION_GUIDE.md), [Idempotency Framework](IDEMPOTENCY_FRAMEWORK.md)
