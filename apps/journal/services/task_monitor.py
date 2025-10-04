"""
Journal Task Monitoring Service

Provides monitoring, health checks, and management for journal-related background tasks.
Includes task status tracking, performance metrics, and failure analysis.
"""

from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Avg
from datetime import timedelta
import json
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)


class JournalTaskMonitor:
    """
    Monitor and manage journal-related background tasks

    Provides comprehensive monitoring of task execution, performance metrics,
    and health status for the journal system's background processing.
    """

    def __init__(self):
        self.cache_prefix = 'journal_task_monitor'
        self.health_check_interval = 300  # 5 minutes

    def record_task_start(self, task_name, task_id, user_id=None, metadata=None):
        """
        Record task start for monitoring

        Args:
            task_name: Name of the task
            task_id: Unique task identifier
            user_id: User ID if task is user-specific
            metadata: Additional task metadata
        """
        task_data = {
            'task_name': task_name,
            'task_id': task_id,
            'user_id': user_id,
            'start_time': timezone.now().isoformat(),
            'status': 'running',
            'metadata': metadata or {}
        }

        cache_key = f"{self.cache_prefix}:task:{task_id}"
        cache.set(cache_key, task_data, timeout=3600)  # 1 hour

        # Update task statistics
        self._update_task_stats(task_name, 'started')

        logger.debug(f"Task monitoring started: {task_name} ({task_id})")

    def record_task_completion(self, task_id, result=None, error=None):
        """
        Record task completion

        Args:
            task_id: Unique task identifier
            result: Task result data
            error: Error information if task failed
        """
        cache_key = f"{self.cache_prefix}:task:{task_id}"
        task_data = cache.get(cache_key)

        if not task_data:
            logger.warning(f"Task data not found for completion: {task_id}")
            return

        # Calculate execution time
        start_time = timezone.fromisoformat(task_data['start_time'])
        end_time = timezone.now()
        execution_time = (end_time - start_time).total_seconds()

        # Update task data
        task_data.update({
            'end_time': end_time.isoformat(),
            'execution_time_seconds': execution_time,
            'status': 'failed' if error else 'completed',
            'result': result,
            'error': error
        })

        cache.set(cache_key, task_data, timeout=3600)

        # Update statistics
        status = 'failed' if error else 'completed'
        self._update_task_stats(task_data['task_name'], status, execution_time)

        # Log performance
        if execution_time > 60:  # Log slow tasks
            logger.warning(
                f"Slow task execution: {task_data['task_name']} "
                f"took {execution_time:.2f} seconds"
            )

        if error:
            logger.error(f"Task failed: {task_data['task_name']} ({task_id}): {error}")
        else:
            logger.debug(f"Task completed: {task_data['task_name']} ({task_id})")

    def get_task_status(self, task_id):
        """
        Get current status of a task

        Args:
            task_id: Unique task identifier

        Returns:
            dict: Task status information
        """
        cache_key = f"{self.cache_prefix}:task:{task_id}"
        task_data = cache.get(cache_key)

        if not task_data:
            return {
                'found': False,
                'message': 'Task not found or expired'
            }

        # Calculate current runtime if still running
        if task_data['status'] == 'running':
            start_time = timezone.fromisoformat(task_data['start_time'])
            current_runtime = (timezone.now() - start_time).total_seconds()
            task_data['current_runtime_seconds'] = current_runtime

        return {
            'found': True,
            'task_data': task_data
        }

    def get_system_health(self):
        """
        Get overall health status of journal task system

        Returns:
            dict: System health information
        """
        health_data = {
            'timestamp': timezone.now().isoformat(),
            'overall_status': 'healthy',
            'task_statistics': self._get_task_statistics(),
            'performance_metrics': self._get_performance_metrics(),
            'active_tasks': self._get_active_tasks(),
            'failed_tasks': self._get_recent_failed_tasks(),
            'warnings': []
        }

        # Analyze health indicators
        warnings = []

        # Check failure rates
        stats = health_data['task_statistics']
        for task_name, task_stats in stats.items():
            total_tasks = task_stats.get('completed', 0) + task_stats.get('failed', 0)
            if total_tasks > 0:
                failure_rate = task_stats.get('failed', 0) / total_tasks
                if failure_rate > 0.1:  # More than 10% failure rate
                    warnings.append(f"High failure rate for {task_name}: {failure_rate:.1%}")

        # Check performance
        performance = health_data['performance_metrics']
        for task_name, metrics in performance.items():
            avg_time = metrics.get('avg_execution_time', 0)
            if avg_time > 120:  # Tasks taking longer than 2 minutes
                warnings.append(f"Slow execution for {task_name}: {avg_time:.1f}s average")

        # Check for stuck tasks
        active_tasks = health_data['active_tasks']
        for task in active_tasks:
            if task.get('current_runtime_seconds', 0) > 1800:  # Running for more than 30 minutes
                warnings.append(f"Long-running task detected: {task['task_name']} ({task['task_id']})")

        health_data['warnings'] = warnings

        # Determine overall status
        if len(warnings) > 5:
            health_data['overall_status'] = 'unhealthy'
        elif len(warnings) > 2:
            health_data['overall_status'] = 'degraded'

        return health_data

    def get_user_task_history(self, user_id, days=7):
        """
        Get task execution history for a specific user

        Args:
            user_id: User identifier
            days: Number of days to look back

        Returns:
            dict: User task history
        """
        # This would typically query a database table with task history
        # For now, we'll check recent cache entries
        user_tasks = []

        # Scan recent task cache entries (simplified implementation)
        # In production, this would use a proper database table
        cache_pattern = f"{self.cache_prefix}:task:*"

        # Since Django cache doesn't support pattern scanning directly,
        # we'll implement a simple tracking mechanism
        user_task_keys = cache.get(f"{self.cache_prefix}:user_tasks:{user_id}", [])

        for task_key in user_task_keys[-50:]:  # Last 50 tasks
            task_data = cache.get(task_key)
            if task_data and task_data.get('user_id') == user_id:
                # Filter by date range
                task_time = timezone.fromisoformat(task_data['start_time'])
                if task_time >= timezone.now() - timedelta(days=days):
                    user_tasks.append(task_data)

        # Sort by start time
        user_tasks.sort(key=lambda x: x['start_time'], reverse=True)

        return {
            'user_id': user_id,
            'task_count': len(user_tasks),
            'date_range_days': days,
            'tasks': user_tasks,
            'summary': self._summarize_user_tasks(user_tasks)
        }

    def cleanup_expired_task_data(self):
        """
        Clean up expired task monitoring data

        Returns:
            dict: Cleanup results
        """
        # Clean up task statistics older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)

        # Clean cache entries (simplified - in production would use database)
        cleaned_count = 0

        # Reset statistics older than cutoff
        stats_key = f"{self.cache_prefix}:stats"
        current_stats = cache.get(stats_key, {})

        for task_name in list(current_stats.keys()):
            task_stats = current_stats[task_name]
            if 'last_updated' in task_stats:
                last_updated = timezone.fromisoformat(task_stats['last_updated'])
                if last_updated < cutoff_date:
                    del current_stats[task_name]
                    cleaned_count += 1

        cache.set(stats_key, current_stats, timeout=None)

        logger.info(f"Cleaned up {cleaned_count} expired task monitoring entries")

        return {
            'cleaned_entries': cleaned_count,
            'cleanup_date': timezone.now().isoformat()
        }

    def alert_on_task_failure(self, task_name, task_id, error_details):
        """
        Generate alerts for task failures

        Args:
            task_name: Name of the failed task
            task_id: Task identifier
            error_details: Error information
        """
        # Check if this is a recurring failure
        failure_count = self._get_recent_failure_count(task_name)

        alert_level = 'info'
        if failure_count >= 5:
            alert_level = 'critical'
        elif failure_count >= 3:
            alert_level = 'warning'

        alert_data = {
            'alert_level': alert_level,
            'task_name': task_name,
            'task_id': task_id,
            'error_details': error_details,
            'failure_count': failure_count,
            'timestamp': timezone.now().isoformat()
        }

        # Store alert
        alert_key = f"{self.cache_prefix}:alerts:{task_name}:{timezone.now().strftime('%Y%m%d%H')}"
        cache.set(alert_key, alert_data, timeout=86400)  # 24 hours

        # Log alert
        if alert_level == 'critical':
            logger.critical(f"Critical task failure alert: {task_name} - {error_details}")
        elif alert_level == 'warning':
            logger.warning(f"Task failure warning: {task_name} - {error_details}")
        else:
            logger.info(f"Task failure: {task_name} - {error_details}")

    # Private helper methods

    def _update_task_stats(self, task_name, status, execution_time=None):
        """Update task statistics"""
        stats_key = f"{self.cache_prefix}:stats"
        current_stats = cache.get(stats_key, {})

        if task_name not in current_stats:
            current_stats[task_name] = {
                'started': 0,
                'completed': 0,
                'failed': 0,
                'total_execution_time': 0,
                'execution_count': 0,
                'last_updated': timezone.now().isoformat()
            }

        task_stats = current_stats[task_name]
        task_stats[status] += 1
        task_stats['last_updated'] = timezone.now().isoformat()

        if execution_time and status in ['completed', 'failed']:
            task_stats['total_execution_time'] += execution_time
            task_stats['execution_count'] += 1

        current_stats[task_name] = task_stats
        cache.set(stats_key, current_stats, timeout=None)

    def _get_task_statistics(self):
        """Get task execution statistics"""
        stats_key = f"{self.cache_prefix}:stats"
        return cache.get(stats_key, {})

    def _get_performance_metrics(self):
        """Calculate performance metrics"""
        stats = self._get_task_statistics()
        performance = {}

        for task_name, task_stats in stats.items():
            if task_stats.get('execution_count', 0) > 0:
                avg_time = task_stats.get('total_execution_time', 0) / task_stats['execution_count']
                performance[task_name] = {
                    'avg_execution_time': round(avg_time, 2),
                    'total_executions': task_stats['execution_count']
                }

        return performance

    def _get_active_tasks(self):
        """Get list of currently active tasks"""
        active_tasks = []

        # Scan for running tasks in cache
        # This is a simplified implementation
        # In production, would use a proper database query

        return active_tasks

    def _get_recent_failed_tasks(self, hours=24):
        """Get recent failed tasks"""
        failed_tasks = []

        # Implementation would scan recent cache entries or database
        # for failed tasks within the time window

        return failed_tasks

    def _summarize_user_tasks(self, user_tasks):
        """Summarize user task history"""
        if not user_tasks:
            return {
                'total_tasks': 0,
                'success_rate': 0.0,
                'avg_execution_time': 0.0
            }

        total_tasks = len(user_tasks)
        successful_tasks = len([t for t in user_tasks if t.get('status') == 'completed'])
        success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0

        # Calculate average execution time for completed tasks
        completed_tasks = [t for t in user_tasks if t.get('execution_time_seconds')]
        avg_execution_time = 0.0
        if completed_tasks:
            total_time = sum(t['execution_time_seconds'] for t in completed_tasks)
            avg_execution_time = total_time / len(completed_tasks)

        return {
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'failed_tasks': total_tasks - successful_tasks,
            'success_rate': round(success_rate, 3),
            'avg_execution_time': round(avg_execution_time, 2)
        }

    def _get_recent_failure_count(self, task_name, hours=24):
        """Get count of recent failures for a task"""
        # Implementation would count failures within time window
        # For now, return a placeholder
        return 1

    def track_user_task(self, user_id, task_id):
        """Track task for a specific user"""
        user_task_key = f"{self.cache_prefix}:user_tasks:{user_id}"
        user_tasks = cache.get(user_task_key, [])

        task_cache_key = f"{self.cache_prefix}:task:{task_id}"
        user_tasks.append(task_cache_key)

        # Keep only last 100 tasks per user
        if len(user_tasks) > 100:
            user_tasks = user_tasks[-100:]

        cache.set(user_task_key, user_tasks, timeout=604800)  # 1 week


# Global instance for easy access
task_monitor = JournalTaskMonitor()