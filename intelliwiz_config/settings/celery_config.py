"""
Celery Task Queue Configuration

Enterprise Celery setup with:
- Multi-queue architecture with priorities
- Optimized Redis backend
- Task routing by business domain
- Monitoring and reliability settings
"""

from kombu import Queue, Exchange
import environ
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

env = environ.Env()

# ============================================================================
# REDIS BROKER CONFIGURATION FOR CELERY
# ============================================================================

from .redis_optimized import get_celery_redis_config

# Get optimized Celery Redis URLs with authentication and connection pooling
_django_environment = env('DJANGO_ENVIRONMENT', default='production')
_celery_redis_config = get_celery_redis_config(_django_environment)

CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=_celery_redis_config['broker_url'])
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default=_celery_redis_config['result_backend'])

# ============================================================================
# SERIALIZATION SECURITY
# ============================================================================

# JSON serialization to prevent code injection
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True

# ============================================================================
# PERFORMANCE OPTIMIZATION
# ============================================================================

CELERY_WORKER_PREFETCH_MULTIPLIER = 4     # 4x throughput improvement
CELERY_WORKER_CONCURRENCY = 8             # Scale based on CPU cores
CELERY_TASK_ALWAYS_EAGER = False          # Ensure async execution
CELERY_TASK_EAGER_PROPAGATES = False      # Production setting
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Restart workers periodically
CELERY_TASK_SEND_SENT_EVENT = True        # Enable monitoring
CELERY_WORKER_SEND_TASK_EVENTS = True     # Enable task events

# ============================================================================
# REDIS BROKER TRANSPORT OPTIONS
# ============================================================================

CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,            # 1 hour visibility
    'fanout_prefix': True,                 # Enable fanout optimization
    'fanout_patterns': True,               # Enable pattern matching
    'priority_steps': list(range(10)),     # Enable task priorities 0-9
    'sep': ':',                            # Key separator
    'queue_order_strategy': 'priority',    # Priority-based queue ordering
}

# ============================================================================
# RESULT BACKEND OPTIMIZATION
# ============================================================================

CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'retry_policy': {
        'timeout': 5.0,
        'max_retries': 10,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.2,
    }
}

# ============================================================================
# QUEUE DEFINITIONS WITH PRIORITIES
# ============================================================================

CELERY_TASK_QUEUES = (
    # CRITICAL PRIORITY - Safety & Security (Priority 9-10)
    Queue('critical',
          Exchange('critical', type='direct'),
          routing_key='critical',
          queue_arguments={'x-max-priority': 10}),

    # HIGH PRIORITY - User-facing operations (Priority 8)
    Queue('high_priority',
          Exchange('high_priority', type='direct'),
          routing_key='high_priority',
          queue_arguments={'x-max-priority': 8}),

    # EMAIL QUEUE - Dedicated email processing (Priority 7)
    Queue('email',
          Exchange('email', type='direct'),
          routing_key='email',
          queue_arguments={'x-max-priority': 7}),

    # REPORTS QUEUE - Background analytics (Priority 6)
    Queue('reports',
          Exchange('reports', type='direct'),
          routing_key='reports',
          queue_arguments={'x-max-priority': 6}),

    # EXTERNAL API - With circuit breaker protection (Priority 5)
    Queue('external_api',
          Exchange('external_api', type='direct'),
          routing_key='external_api',
          queue_arguments={'x-max-priority': 5}),

    # MAINTENANCE - Lowest priority cleanup (Priority 3)
    Queue('maintenance',
          Exchange('maintenance', type='direct'),
          routing_key='maintenance',
          queue_arguments={'x-max-priority': 3}),

    # DEFAULT - General tasks (Priority 5)
    Queue('default',
          Exchange('default', type='direct'),
          routing_key='default',
          queue_arguments={'x-max-priority': 5}),
)

# ============================================================================
# TASK ROUTING (Business Domain Separation)
# ============================================================================
# Import from single source of truth to prevent configuration drift

from apps.core.tasks.celery_settings import CELERY_TASK_ROUTES  # noqa: F401

# ============================================================================
# RETRY CONFIGURATION
# ============================================================================

CELERY_TASK_DEFAULT_RETRY_DELAY = 60        # 1 minute default
CELERY_TASK_MAX_RETRIES = 3                 # Maximum retry attempts
CELERY_TASK_RETRY_BACKOFF = True            # Exponential backoff
CELERY_TASK_RETRY_BACKOFF_MAX = 600         # 10 minutes max delay
CELERY_TASK_RETRY_JITTER = True             # Add randomness to prevent thundering herd

# ============================================================================
# MONITORING AND RELIABILITY
# ============================================================================

CELERY_TASK_TRACK_STARTED = True            # Track task start events
CELERY_TASK_TIME_LIMIT = SECONDS_IN_HOUR    # 1 hour hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 1800          # 30 minutes soft limit
CELERY_RESULT_EXPIRES = SECONDS_IN_HOUR     # Results expire after 1 hour

__all__ = [
    'CELERY_BROKER_URL',
    'CELERY_RESULT_BACKEND',
    'CELERY_TASK_SERIALIZER',
    'CELERY_RESULT_SERIALIZER',
    'CELERY_ACCEPT_CONTENT',
    'CELERY_TASK_REJECT_ON_WORKER_LOST',
    'CELERY_TASK_ACKS_LATE',
    'CELERY_WORKER_PREFETCH_MULTIPLIER',
    'CELERY_WORKER_CONCURRENCY',
    'CELERY_TASK_ALWAYS_EAGER',
    'CELERY_TASK_EAGER_PROPAGATES',
    'CELERY_WORKER_MAX_TASKS_PER_CHILD',
    'CELERY_TASK_SEND_SENT_EVENT',
    'CELERY_WORKER_SEND_TASK_EVENTS',
    'CELERY_BROKER_TRANSPORT_OPTIONS',
    'CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS',
    'CELERY_TASK_QUEUES',
    'CELERY_TASK_ROUTES',
    'CELERY_TASK_DEFAULT_RETRY_DELAY',
    'CELERY_TASK_MAX_RETRIES',
    'CELERY_TASK_RETRY_BACKOFF',
    'CELERY_TASK_RETRY_BACKOFF_MAX',
    'CELERY_TASK_RETRY_JITTER',
    'CELERY_TASK_TRACK_STARTED',
    'CELERY_TASK_TIME_LIMIT',
    'CELERY_TASK_SOFT_TIME_LIMIT',
    'CELERY_RESULT_EXPIRES',
]
