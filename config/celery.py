# Celery Configuration for YOUTILITY5 AI Services
import os
from celery import Celery
from django.conf import settings
from kombu import Queue

# Set the default Django settings module for the 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility5.settings.ai')

app = Celery('youtility5_ai')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Celery Configuration
app.conf.update(
    # Broker settings
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/2'),
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis:6379/3'),
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Task routing
    task_routes={
        # AI-specific tasks
        'apps.txtai_engine.tasks.*': {'queue': 'ai_search'},
        'apps.mindsdb_engine.tasks.*': {'queue': 'ai_ml'},
        'apps.ai_orchestrator.tasks.*': {'queue': 'ai_orchestration'},
        'apps.smart_dashboard.tasks.*': {'queue': 'ai_dashboard'},
        
        # Heavy computation tasks
        'apps.txtai_engine.tasks.build_index': {'queue': 'ai_heavy'},
        'apps.mindsdb_engine.tasks.train_model': {'queue': 'ai_heavy'},
        
        # Real-time tasks
        'apps.smart_dashboard.tasks.update_metrics': {'queue': 'ai_realtime'},
        'apps.ai_orchestrator.tasks.process_workflow': {'queue': 'ai_realtime'},
    },
    
    # Queue definitions
    task_default_queue='default',
    task_queues=(
        Queue('default'),
        Queue('ai_search', routing_key='ai_search'),
        Queue('ai_ml', routing_key='ai_ml'),
        Queue('ai_orchestration', routing_key='ai_orchestration'),
        Queue('ai_dashboard', routing_key='ai_dashboard'),
        Queue('ai_heavy', routing_key='ai_heavy'),
        Queue('ai_realtime', routing_key='ai_realtime'),
    ),
    
    # Task execution settings
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes
    task_max_retries=3,
    task_default_retry_delay=60,  # 1 minute
    
    # Monitoring and logging
    worker_send_task_events=True,
    task_send_sent_event=True,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_cache_max=1000,
    
    # Beat scheduler settings
    beat_schedule={
        # Regular maintenance tasks
        'cleanup-expired-sessions': {
            'task': 'apps.core.tasks.cleanup_expired_sessions',
            'schedule': 3600.0,  # Every hour
        },
        'update-dashboard-metrics': {
            'task': 'apps.smart_dashboard.tasks.update_all_dashboard_metrics',
            'schedule': 300.0,  # Every 5 minutes
        },
        'process-pending-predictions': {
            'task': 'apps.mindsdb_engine.tasks.process_pending_predictions',
            'schedule': 60.0,   # Every minute
        },
        'optimize-vector-indexes': {
            'task': 'apps.txtai_engine.tasks.optimize_indexes',
            'schedule': 86400.0,  # Daily
        },
        'cleanup-old-logs': {
            'task': 'apps.core.tasks.cleanup_old_logs',
            'schedule': 86400.0,  # Daily
        },
        'backup-ai-models': {
            'task': 'apps.core.tasks.backup_ai_models',
            'schedule': 86400.0,  # Daily
        },
        'health-check-ai-services': {
            'task': 'apps.ai_orchestrator.tasks.health_check_services',
            'schedule': 300.0,   # Every 5 minutes
        },
        'generate-ai-insights': {
            'task': 'apps.ai_orchestrator.tasks.generate_scheduled_insights',
            'schedule': 1800.0,  # Every 30 minutes
        }
    },
    beat_schedule_filename='celerybeat-schedule',
    
    # Error handling
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    
    # Security
    worker_hijack_root_logger=False,
    worker_log_color=False,
    
    # Performance optimizations
    broker_transport_options={
        'visibility_timeout': 3600,
        'fanout_prefix': True,
        'fanout_patterns': True
    },
    result_backend_transport_options={
        'master_name': 'mymaster'
    }
)


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery"""
    print(f'Request: {self.request!r}')
    return 'Debug task completed'


@app.task
def health_check():
    """Health check task"""
    return 'Celery is healthy'


# Task failure callback
@app.task(bind=True)
def task_failure_handler(self, task_id, error, traceback):
    """Handle task failures"""
    print(f'Task {task_id} failed: {error}')
    # Here you could send notifications, log to external services, etc.


# Custom task base classes
class AITaskBase(app.Task):
    """Base class for AI-related tasks"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        print(f'AI Task {task_id} failed: {exc}')
        
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        print(f'AI Task {task_id} succeeded')
        
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        print(f'AI Task {task_id} retrying: {exc}')


class MLTaskBase(app.Task):
    """Base class for machine learning tasks"""
    
    soft_time_limit = 1800  # 30 minutes
    time_limit = 3600       # 1 hour
    max_retries = 2
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle ML task failure"""
        print(f'ML Task {task_id} failed: {exc}')
        
    def on_success(self, retval, task_id, args, kwargs):
        """Handle ML task success"""
        print(f'ML Task {task_id} succeeded')


# Register custom task classes
app.Task = AITaskBase