"""
AI Testing Background Task Integration
Integrates AI testing tasks with the main background task system
"""

import logging
from django.utils import timezone
from datetime import timedelta

from apps.ai_testing.tasks import (
    ai_daily_pattern_analysis,
    ai_weekly_threshold_update,
    ai_weekly_insights_report,
    ai_emergency_analysis,
    ai_cleanup_old_data,
    ai_batch_test_generation,
    ai_health_check,
)


logger = logging.getLogger(__name__)


class AITestingTaskManager:
    """
    Manager class for coordinating AI testing background tasks
    """

    @staticmethod
    def schedule_daily_tasks():
        """
        Schedule all daily AI tasks
        Called by the main task scheduler
        """
        try:
            # Daily pattern analysis (6 AM)
            ai_daily_pattern_analysis.apply_async()

            # Daily health check (every 6 hours)
            ai_health_check.apply_async()

            logger.info("[AI Background] Daily tasks scheduled successfully")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"[AI Background] Failed to schedule daily tasks: {str(e)}")
            return False

    @staticmethod
    def schedule_weekly_tasks():
        """
        Schedule all weekly AI tasks
        Called on Sunday nights
        """
        try:
            # Weekly threshold updates
            ai_weekly_threshold_update.apply_async()

            # Weekly insights report
            ai_weekly_insights_report.apply_async()

            # Weekly performance optimization
            from apps.ai_testing.tasks import ai_performance_optimization
            ai_performance_optimization.apply_async()

            # Weekly data cleanup
            ai_cleanup_old_data.apply_async(args=[90])  # Keep 90 days

            logger.info("[AI Background] Weekly tasks scheduled successfully")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"[AI Background] Failed to schedule weekly tasks: {str(e)}")
            return False

    @staticmethod
    def handle_anomaly_trigger(anomaly_signature_id, severity="medium"):
        """
        Handle anomaly-triggered AI analysis
        Called when new anomalies are detected
        """
        try:
            # Trigger immediate analysis for high-severity anomalies
            if severity in ['critical', 'error']:
                ai_emergency_analysis.apply_async(args=["anomaly_detection"])
                logger.info(f"[AI Background] Emergency analysis triggered for {severity} anomaly")

            # Always trigger anomaly response analysis
            from apps.ai_testing.tasks import ai_anomaly_response
            ai_anomaly_response.apply_async(args=[anomaly_signature_id, severity])

            logger.info(f"[AI Background] Anomaly response triggered for signature {anomaly_signature_id}")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"[AI Background] Failed to handle anomaly trigger: {str(e)}")
            return False

    @staticmethod
    def check_system_health():
        """
        Check AI system health and trigger remediation if needed
        """
        try:
            from apps.ai_testing.dashboard_integration import get_ai_insights_summary

            insights = get_ai_insights_summary()
            health_score = insights['health_score']

            # Health thresholds
            if health_score < 60:
                # Critical health - trigger emergency procedures
                ai_emergency_analysis.apply_async(args=["health_critical"])

                # Generate immediate high-priority tests
                ai_batch_test_generation.apply_async(args=["critical", 15])

                logger.warning(f"[AI Background] Critical health detected: {health_score}%")

            elif health_score < 75:
                # Warning health - trigger standard analysis
                ai_daily_pattern_analysis.apply_async()

                logger.warning(f"[AI Background] Warning health detected: {health_score}%")

            return {
                'health_score': health_score,
                'action_taken': health_score < 75,
                'critical': health_score < 60
            }

        except (ValueError, TypeError) as e:
            logger.error(f"[AI Background] Health check failed: {str(e)}")
            return None

    @staticmethod
    def trigger_batch_generation(priority="high", max_count=25):
        """
        Trigger batch test generation
        Can be called manually or automatically
        """
        try:
            ai_batch_test_generation.apply_async(args=[priority, max_count])
            logger.info(f"[AI Background] Batch generation triggered for {priority} priority")
            return True

        except (ValueError, TypeError) as e:
            logger.error(f"[AI Background] Failed to trigger batch generation: {str(e)}")
            return False

    @staticmethod
    def get_task_status():
        """
        Get status of AI testing background tasks
        """
        try:
            from celery import current_app

            # Check active tasks
            active_tasks = current_app.control.inspect().active()
            ai_tasks = []

            if active_tasks:
                for worker, tasks in active_tasks.items():
                    for task in tasks:
                        if task['name'].startswith('ai_'):
                            ai_tasks.append({
                                'worker': worker,
                                'task_name': task['name'],
                                'task_id': task['id'],
                                'time_start': task['time_start']
                            })

            return {
                'active_ai_tasks': len(ai_tasks),
                'tasks': ai_tasks,
                'last_check': timezone.now()
            }

        except (DatabaseError, IntegrationException, ValueError) as e:
            logger.error(f"[AI Background] Failed to get task status: {str(e)}")
            return {'error': str(e)}


# Integration functions for main background task system

def integrate_ai_tasks_with_scheduler():
    """
    Integration point for the main task scheduler
    Call this function from your main scheduler to include AI tasks
    """
    manager = AITestingTaskManager()

    # Schedule based on time
    current_hour = timezone.now().hour
    current_day = timezone.now().weekday()  # 0 = Monday, 6 = Sunday

    # Daily tasks (6 AM)
    if current_hour == 6:
        manager.schedule_daily_tasks()

    # Weekly tasks (Sunday 8 AM)
    if current_day == 6 and current_hour == 8:  # Sunday 8 AM
        manager.schedule_weekly_tasks()

    # Health checks (every 6 hours)
    if current_hour % 6 == 0:
        manager.check_system_health()


def trigger_ai_analysis_for_anomaly(anomaly_signature_id, severity="medium"):
    """
    Integration point for anomaly detection system
    Call this when new anomalies are detected
    """
    manager = AITestingTaskManager()
    return manager.handle_anomaly_trigger(anomaly_signature_id, severity)


def get_ai_task_monitoring():
    """
    Integration point for monitoring systems
    Returns current AI task status for health monitoring
    """
    manager = AITestingTaskManager()
    return manager.get_task_status()


# Periodic task configuration for Celery Beat
# Add this to your CELERY_BEAT_SCHEDULE in settings.py:

CELERY_BEAT_SCHEDULE_AI = {
    # Daily Pattern Analysis - 6 AM every day
    'ai-daily-pattern-analysis': {
        'task': 'ai_daily_pattern_analysis',
        'schedule': 60.0 * 60.0 * 24.0,  # 24 hours
        'args': (),
        'options': {
            'expires': 60.0 * 60.0 * 2.0,  # Expire after 2 hours if not picked up
        }
    },

    # Weekly Threshold Update - Sunday 8 PM
    'ai-weekly-threshold-update': {
        'task': 'ai_weekly_threshold_update',
        'schedule': 60.0 * 60.0 * 24.0 * 7.0,  # 7 days
        'args': (),
        'options': {
            'expires': 60.0 * 60.0 * 4.0,  # Expire after 4 hours
        }
    },

    # Weekly Insights Report - Sunday 9 PM
    'ai-weekly-insights-report': {
        'task': 'ai_weekly_insights_report',
        'schedule': 60.0 * 60.0 * 24.0 * 7.0,  # 7 days
        'args': (),
        'options': {
            'expires': 60.0 * 60.0 * 2.0,  # Expire after 2 hours
        }
    },

    # AI Health Check - Every 6 hours
    'ai-health-check': {
        'task': 'ai_health_check',
        'schedule': 60.0 * 60.0 * 6.0,  # 6 hours
        'args': (),
        'options': {
            'expires': 60.0 * 60.0 * 1.0,  # Expire after 1 hour
        }
    },

    # Data Cleanup - Weekly on Monday 2 AM
    'ai-cleanup-old-data': {
        'task': 'ai_cleanup_old_data',
        'schedule': 60.0 * 60.0 * 24.0 * 7.0,  # 7 days
        'args': (90,),  # Keep 90 days of data
        'options': {
            'expires': 60.0 * 60.0 * 3.0,  # Expire after 3 hours
        }
    },
}


# Error handling and monitoring

def monitor_ai_task_health():
    """
    Monitor AI task health and trigger alerts if needed
    """
    try:
        status = get_ai_task_monitoring()

        if 'error' in status:
            logger.error(f"[AI Background] Task monitoring error: {status['error']}")
            return False

        # Check for stuck tasks
        active_tasks = status.get('active_ai_tasks', 0)

        if active_tasks > 5:  # Too many active tasks might indicate problems
            logger.warning(f"[AI Background] High number of active AI tasks: {active_tasks}")

        return True

    except (DatabaseError, IntegrationException, ValueError) as e:
        logger.error(f"[AI Background] Task health monitoring failed: {str(e)}")
        return False


def handle_ai_task_failure(task_name, error_details):
    """
    Handle AI task failures with appropriate remediation
    """
    try:
        logger.error(f"[AI Background] Task failure: {task_name} - {error_details}")

        # Trigger emergency analysis if critical tasks fail
        if task_name in ['ai_daily_pattern_analysis', 'ai_weekly_threshold_update']:
            ai_emergency_analysis.apply_async(args=["task_failure"])

        return True

    except (DatabaseError, IntegrationException, ValueError) as e:
        logger.error(f"[AI Background] Failed to handle task failure: {str(e)}")
        return False