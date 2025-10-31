"""
Signal handlers for automatic monitoring integration.
"""

import time
import logging
from django.core.signals import request_started, request_finished
from django.db.backends.signals import connection_created
from django.dispatch import receiver, Signal
from django.conf import settings

# Note: django.core.cache.signals doesn't exist in Django
# Creating custom signal for cache monitoring
cache_touched = Signal()

from .django_monitoring import metrics_collector

logger = logging.getLogger('monitoring')


@receiver(connection_created)
def log_db_connection(sender, connection, **kwargs):
    """Monitor database connection creation"""
    metrics_collector.record_metric('db_connection', 1, {
        'alias': connection.alias
    })
    logger.debug(f"Database connection created: {connection.alias}")


# Custom cache signal handler (if using custom cache backend)
def monitor_cache_operation(operation, key, **kwargs):
    """Monitor cache operations"""
    start_time = time.time()
    
    # Record operation
    metrics_collector.record_metric(f'cache_{operation}', time.time() - start_time, {
        'key_prefix': key.split(':')[0] if ':' in key else 'unknown'
    })


# Query logging for development
if hasattr(settings, 'DEBUG') and settings.DEBUG:
    from django.db import connection
    from django.db.backends import utils
    
    class QueryLogger:
        """Log slow queries in development"""

        def __init__(self, cursor_self, execute, sql, params):
            self.cursor_self = cursor_self
            self.execute = execute
            self.sql = sql
            self.params = params

        def __call__(self):
            start_time = time.time()
            # Call original execute with correct signature: execute(self, sql, params=None)
            result = self.execute(self.cursor_self, self.sql, self.params)
            duration = time.time() - start_time

            if duration > 0.01:  # Log queries over 10ms
                logger.debug(f"Slow query ({duration:.3f}s): {self.sql[:100]}")

            return result

    # Monkey patch execute wrapper
    original_execute = utils.CursorWrapper.execute

    def patched_execute(self, sql, params=None):
        return QueryLogger(self, original_execute, sql, params)()

    utils.CursorWrapper.execute = patched_execute