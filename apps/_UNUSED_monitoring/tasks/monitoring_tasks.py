"""
Monitoring Background Tasks

Continuous monitoring and alert processing tasks.
Handles automated monitoring, escalations, and system maintenance.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.monitoring.services.monitoring_service import monitoring_service
from apps.monitoring.models import (
    Alert, OperationalTicket, MonitoringMetric, DeviceHealthSnapshot
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def monitor_device_task(self, user_id: int, device_id: str):
    """
    Background task to monitor a specific device.

    Args:
        user_id: User ID to monitor
        device_id: Device ID to monitor
    """
    try:
        logger.info(f"Starting background monitoring for user {user_id}, device {device_id}")

        # Run comprehensive monitoring
        monitoring_result = monitoring_service.monitor_device(user_id, device_id)

        # Broadcast updates to dashboard if there are alerts
        if monitoring_result.get('alerts'):
            channel_layer = get_channel_layer()
            if channel_layer:
                for alert in monitoring_result['alerts']:
                    async_to_sync(channel_layer.group_send)(
                        'monitoring_dashboard',
                        {
                            'type': 'alert_notification',
                            'alert': alert
                        }
                    )

        # Update device status cache for quick access
        _update_device_status_cache(user_id, device_id, monitoring_result)

        logger.info(f"Completed background monitoring for user {user_id}, device {device_id}")

        return {
            'status': 'success',
            'user_id': user_id,
            'device_id': device_id,
            'alerts_triggered': len(monitoring_result.get('alerts', [])),
            'overall_status': monitoring_result.get('overall_status', 'unknown')
        }

    except Exception as e:
        logger.error(f"Error in monitor_device_task: {str(e)}", exc_info=True)

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_countdown = 2 ** self.request.retries * 60  # 1, 2, 4 minutes
            raise self.retry(countdown=retry_countdown, exc=e)

        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def process_pending_alerts_task(self):
    """
    Process pending alerts and trigger automated actions.

    Runs every 5 minutes to process new alerts and execute automated responses.
    """
    try:
        logger.info("Starting pending alerts processing")

        # Get recent unprocessed alerts
        recent_cutoff = timezone.now() - timedelta(minutes=10)
        pending_alerts = Alert.objects.filter(
            status='ACTIVE',
            triggered_at__gte=recent_cutoff
        ).select_related('user', 'rule')

        processed_count = 0
        actions_executed = 0

        for alert in pending_alerts:
            try:
                # Check if automated actions should be triggered
                actions = _get_automated_actions_for_alert(alert)

                for action in actions:
                    if _execute_automated_action(action, alert):
                        actions_executed += 1

                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing alert {alert.alert_id}: {str(e)}")

        # Broadcast system update
        _broadcast_system_update('alert_processing_complete', {
            'processed_alerts': processed_count,
            'actions_executed': actions_executed
        })

        logger.info(f"Processed {processed_count} alerts, executed {actions_executed} actions")

        return {
            'status': 'success',
            'processed_alerts': processed_count,
            'actions_executed': actions_executed
        }

    except Exception as e:
        logger.error(f"Error in process_pending_alerts_task: {str(e)}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def escalate_overdue_alerts_task(self):
    """
    Escalate overdue alerts based on escalation rules.

    Runs every 15 minutes to check for alerts that need escalation.
    """
    try:
        logger.info("Starting alert escalation processing")

        # Escalate overdue alerts
        escalated_alerts = monitoring_service.alert_service.escalate_overdue_alerts()

        # Escalate overdue tickets
        from apps.monitoring.services.ticket_service import TicketService
        ticket_service = TicketService()
        escalated_tickets = ticket_service.escalate_overdue_tickets()

        # Broadcast escalation updates
        if escalated_alerts > 0 or escalated_tickets > 0:
            _broadcast_system_update('escalations_processed', {
                'escalated_alerts': escalated_alerts,
                'escalated_tickets': escalated_tickets
            })

        logger.info(f"Escalated {escalated_alerts} alerts and {escalated_tickets} tickets")

        return {
            'status': 'success',
            'escalated_alerts': escalated_alerts,
            'escalated_tickets': escalated_tickets
        }

    except Exception as e:
        logger.error(f"Error in escalate_overdue_alerts_task: {str(e)}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def cleanup_old_metrics_task(self):
    """
    Clean up old monitoring metrics and maintain database performance.

    Runs daily to clean up old data and maintain optimal performance.
    """
    try:
        logger.info("Starting monitoring data cleanup")

        cleanup_stats = {
            'metrics_deleted': 0,
            'snapshots_deleted': 0,
            'old_alerts_archived': 0
        }

        # Clean up old metrics (keep 30 days)
        metrics_cutoff = timezone.now() - timedelta(days=30)
        deleted_metrics = MonitoringMetric.objects.filter(
            recorded_at__lt=metrics_cutoff
        ).delete()
        cleanup_stats['metrics_deleted'] = deleted_metrics[0] if deleted_metrics else 0

        # Clean up old health snapshots (keep 14 days)
        snapshots_cutoff = timezone.now() - timedelta(days=14)
        deleted_snapshots = DeviceHealthSnapshot.objects.filter(
            snapshot_taken_at__lt=snapshots_cutoff
        ).delete()
        cleanup_stats['snapshots_deleted'] = deleted_snapshots[0] if deleted_snapshots else 0

        # Archive old resolved alerts (keep 90 days)
        alerts_cutoff = timezone.now() - timedelta(days=90)
        old_alerts = Alert.objects.filter(
            status__in=['RESOLVED', 'FALSE_POSITIVE'],
            resolved_at__lt=alerts_cutoff
        )

        # Mark alerts as archived instead of deleting
        archived_count = old_alerts.update(status='ARCHIVED')
        cleanup_stats['old_alerts_archived'] = archived_count

        logger.info(f"Cleanup completed: {cleanup_stats}")

        return {
            'status': 'success',
            'cleanup_stats': cleanup_stats
        }

    except Exception as e:
        logger.error(f"Error in cleanup_old_metrics_task: {str(e)}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def update_system_health_task(self):
    """
    Update system health metrics and performance indicators.

    Runs every 5 minutes to update system-wide health metrics.
    """
    try:
        logger.info("Updating system health metrics")

        # Get system health from monitoring service
        system_health = monitoring_service.get_system_health()

        # Store system health snapshot
        from apps.monitoring.models import SystemHealthMetric

        health_metrics = [
            ('ACTIVE_DEVICES', system_health.get('monitoring_statistics', {}).get('active_devices', 0), 'count'),
            ('ACTIVE_ALERTS', system_health.get('alert_statistics', {}).get('active_alerts', 0), 'count'),
            ('AVG_RESPONSE_TIME', system_health.get('system_performance', {}).get('avg_response_time_ms', 0), 'ms'),
            ('SUCCESS_RATE', system_health.get('system_performance', {}).get('success_rate', 1.0) * 100, '%'),
        ]

        for metric_name, value, unit in health_metrics:
            SystemHealthMetric.objects.create(
                metric_name=metric_name,
                value=value,
                unit=unit
            )

        # Broadcast system health update
        _broadcast_system_update('system_health_updated', system_health)

        logger.info("System health metrics updated")

        return {
            'status': 'success',
            'metrics_updated': len(health_metrics),
            'system_health': system_health
        }

    except Exception as e:
        logger.error(f"Error in update_system_health_task: {str(e)}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def generate_monitoring_reports_task(self):
    """
    Generate daily monitoring reports and analytics.

    Runs daily to generate summary reports and performance analytics.
    """
    try:
        logger.info("Generating monitoring reports")

        # Generate daily summary
        daily_summary = _generate_daily_summary()

        # Generate alert analysis
        alert_analysis = _generate_alert_analysis()

        # Generate device performance report
        device_report = _generate_device_performance_report()

        # Store or send reports
        report_data = {
            'date': timezone.now().date().isoformat(),
            'daily_summary': daily_summary,
            'alert_analysis': alert_analysis,
            'device_report': device_report
        }

        # In production, this could email reports or store in database
        logger.info(f"Generated monitoring reports: {len(report_data)} sections")

        return {
            'status': 'success',
            'report_sections': len(report_data),
            'report_data': report_data
        }

    except Exception as e:
        logger.error(f"Error in generate_monitoring_reports_task: {str(e)}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


@shared_task(bind=True)
def bulk_device_monitoring_task(self, device_list: List[Dict]):
    """
    Monitor multiple devices in bulk for efficiency.

    Args:
        device_list: List of {'user_id': int, 'device_id': str} dictionaries
    """
    try:
        logger.info(f"Starting bulk monitoring for {len(device_list)} devices")

        results = []
        total_alerts = 0

        for device_info in device_list:
            try:
                user_id = device_info['user_id']
                device_id = device_info['device_id']

                result = monitoring_service.monitor_device(user_id, device_id)
                results.append(result)

                if result.get('alerts'):
                    total_alerts += len(result['alerts'])

            except Exception as e:
                logger.error(f"Error in bulk monitoring for device {device_info}: {str(e)}")
                results.append({'status': 'error', 'error': str(e)})

        # Broadcast bulk update
        _broadcast_system_update('bulk_monitoring_complete', {
            'devices_monitored': len(device_list),
            'total_alerts': total_alerts
        })

        logger.info(f"Bulk monitoring completed: {len(device_list)} devices, {total_alerts} alerts")

        return {
            'status': 'success',
            'devices_monitored': len(device_list),
            'total_alerts': total_alerts,
            'results': results
        }

    except Exception as e:
        logger.error(f"Error in bulk_device_monitoring_task: {str(e)}", exc_info=True)
        return {'status': 'error', 'error': str(e)}


# Helper functions

def _update_device_status_cache(user_id: int, device_id: str, monitoring_result: Dict):
    """Update device status in cache for quick dashboard access"""
    try:
        from django.core.cache import cache

        cache_key = f"device_status:{user_id}:{device_id}"
        cache_data = {
            'overall_status': monitoring_result.get('overall_status', 'unknown'),
            'alert_count': len(monitoring_result.get('alerts', [])),
            'last_updated': timezone.now().isoformat(),
            'risk_level': monitoring_result.get('risk_assessment', {}).get('risk_level', 'UNKNOWN')
        }

        cache.set(cache_key, cache_data, timeout=1800)  # 30 minutes

    except Exception as e:
        logger.error(f"Error updating device status cache: {str(e)}")


def _get_automated_actions_for_alert(alert: Alert) -> List[Dict]:
    """Get automated actions that should be triggered for an alert"""
    try:
        from apps.monitoring.models import AutomatedAction

        # Find matching automated actions
        actions = AutomatedAction.objects.filter(
            trigger_condition='ALERT_CREATED',
            is_active=True
        ).filter(
            Q(trigger_criteria__alert_types__contains=[alert.rule.alert_type]) |
            Q(trigger_criteria__severity_levels__contains=[alert.severity])
        )

        return [{
            'action_id': str(action.action_id),
            'action_type': action.action_type,
            'action_config': action.action_config,
            'action_name': action.name
        } for action in actions if action.can_execute()]

    except Exception as e:
        logger.error(f"Error getting automated actions for alert: {str(e)}")
        return []


def _execute_automated_action(action: Dict, alert: Alert) -> bool:
    """Execute an automated action"""
    try:
        action_type = action.get('action_type')
        action_config = action.get('action_config', {})

        if action_type == 'NOTIFICATION':
            return _execute_notification_action(action_config, alert)
        elif action_type == 'DEVICE_COMMAND':
            return _execute_device_command_action(action_config, alert)
        elif action_type == 'TICKET_CREATE':
            return _execute_ticket_creation_action(action_config, alert)
        elif action_type == 'ESCALATION':
            return _execute_escalation_action(action_config, alert)
        elif action_type == 'RESOURCE_ALLOCATION':
            return _execute_resource_allocation_action(action_config, alert)

        logger.warning(f"Unknown action type: {action_type}")
        return False

    except Exception as e:
        logger.error(f"Error executing automated action: {str(e)}")
        return False


def _execute_notification_action(config: Dict, alert: Alert) -> bool:
    """Execute notification action"""
    try:
        notification_type = config.get('type', 'email')
        recipients = config.get('recipients', [])

        # Send notifications (implementation would vary by type)
        logger.info(f"Sending {notification_type} notification for alert {alert.alert_id}")

        # Broadcast to dashboard
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'monitoring_dashboard',
                {
                    'type': 'notification_sent',
                    'alert_id': str(alert.alert_id),
                    'notification_type': notification_type
                }
            )

        return True

    except Exception as e:
        logger.error(f"Error executing notification action: {str(e)}")
        return False


def _execute_device_command_action(config: Dict, alert: Alert) -> bool:
    """Execute device command action"""
    try:
        command = config.get('command', 'status_check')

        # Send command to device (implementation would use mobile SDK)
        logger.info(f"Sending device command '{command}' for alert {alert.alert_id}")

        # For now, just log the action
        return True

    except Exception as e:
        logger.error(f"Error executing device command action: {str(e)}")
        return False


def _execute_ticket_creation_action(config: Dict, alert: Alert) -> bool:
    """Execute ticket creation action"""
    try:
        from apps.monitoring.services.ticket_service import TicketService

        ticket_service = TicketService()
        ticket = ticket_service.create_ticket_from_alert(alert)

        if ticket:
            logger.info(f"Created ticket {ticket.ticket_number} from alert {alert.alert_id}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error executing ticket creation action: {str(e)}")
        return False


def _execute_escalation_action(config: Dict, alert: Alert) -> bool:
    """Execute escalation action"""
    try:
        escalation_level = config.get('level', 1)
        logger.info(f"Escalating alert {alert.alert_id} to level {escalation_level}")

        # Implementation would escalate the alert
        return True

    except Exception as e:
        logger.error(f"Error executing escalation action: {str(e)}")
        return False


def _execute_resource_allocation_action(config: Dict, alert: Alert) -> bool:
    """Execute resource allocation action"""
    try:
        resource_type = config.get('resource_type', 'backup_personnel')
        logger.info(f"Allocating {resource_type} for alert {alert.alert_id}")

        # Implementation would allocate resources
        return True

    except Exception as e:
        logger.error(f"Error executing resource allocation action: {str(e)}")
        return False


def _broadcast_system_update(update_type: str, data: Dict):
    """Broadcast system update to all dashboard users"""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'monitoring_dashboard',
                {
                    'type': 'system_metric_update',
                    'update_type': update_type,
                    'data': data,
                    'timestamp': timezone.now().isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error broadcasting system update: {str(e)}")


def _generate_daily_summary() -> Dict:
    """Generate daily monitoring summary"""
    try:
        today = timezone.now().date()
        today_start = timezone.make_aware(datetime.combine(today, datetime.min.time()))

        # Alert statistics
        today_alerts = Alert.objects.filter(triggered_at__gte=today_start)
        alert_stats = {
            'total_alerts': today_alerts.count(),
            'critical_alerts': today_alerts.filter(severity='CRITICAL').count(),
            'resolved_alerts': today_alerts.filter(status='RESOLVED').count(),
            'active_alerts': today_alerts.filter(status='ACTIVE').count()
        }

        # Device statistics
        today_snapshots = DeviceHealthSnapshot.objects.filter(snapshot_taken_at__gte=today_start)
        device_stats = {
            'total_devices_monitored': today_snapshots.values('device_id').distinct().count(),
            'devices_at_risk': today_snapshots.filter(risk_score__gt=0.7).values('device_id').distinct().count(),
            'avg_battery_level': today_snapshots.aggregate(avg=models.Avg('battery_level'))['avg'] or 0
        }

        # Ticket statistics
        today_tickets = OperationalTicket.objects.filter(created_at__gte=today_start)
        ticket_stats = {
            'total_tickets': today_tickets.count(),
            'resolved_tickets': today_tickets.filter(status='RESOLVED').count(),
            'overdue_tickets': today_tickets.filter(is_overdue=True).count()
        }

        return {
            'date': today.isoformat(),
            'alert_statistics': alert_stats,
            'device_statistics': device_stats,
            'ticket_statistics': ticket_stats
        }

    except Exception as e:
        logger.error(f"Error generating daily summary: {str(e)}")
        return {}


def _generate_alert_analysis() -> Dict:
    """Generate alert pattern analysis"""
    try:
        # Analyze alert patterns from last 7 days
        week_ago = timezone.now() - timedelta(days=7)

        alerts = Alert.objects.filter(triggered_at__gte=week_ago)

        # Alert type breakdown
        type_breakdown = alerts.values('rule__alert_type').annotate(
            count=Count('id')
        ).order_by('-count')

        # Hourly pattern analysis
        hourly_pattern = {}
        for hour in range(24):
            hourly_count = alerts.filter(triggered_at__hour=hour).count()
            hourly_pattern[hour] = hourly_count

        # User pattern analysis
        user_breakdown = alerts.values('user__peoplename').annotate(
            count=Count('id')
        ).order_by('-count')[:10]  # Top 10 users

        return {
            'analysis_period_days': 7,
            'type_breakdown': {item['rule__alert_type']: item['count'] for item in type_breakdown},
            'hourly_pattern': hourly_pattern,
            'top_users': {item['user__peoplename']: item['count'] for item in user_breakdown}
        }

    except Exception as e:
        logger.error(f"Error generating alert analysis: {str(e)}")
        return {}


def _generate_device_performance_report() -> Dict:
    """Generate device performance report"""
    try:
        # Analyze device performance from last 24 hours
        yesterday = timezone.now() - timedelta(hours=24)

        snapshots = DeviceHealthSnapshot.objects.filter(snapshot_taken_at__gte=yesterday)

        # Performance statistics
        performance_stats = {
            'total_snapshots': snapshots.count(),
            'avg_health_score': snapshots.aggregate(avg=models.Avg('health_score'))['avg'] or 0,
            'devices_excellent': snapshots.filter(overall_health='EXCELLENT').values('device_id').distinct().count(),
            'devices_poor': snapshots.filter(overall_health__in=['POOR', 'CRITICAL']).values('device_id').distinct().count(),
        }

        # Battery analysis
        battery_stats = {
            'avg_battery_level': snapshots.aggregate(avg=models.Avg('battery_level'))['avg'] or 0,
            'devices_low_battery': snapshots.filter(battery_level__lt=20).values('device_id').distinct().count(),
            'devices_critical_battery': snapshots.filter(battery_level__lt=10).values('device_id').distinct().count(),
        }

        return {
            'report_period_hours': 24,
            'performance_statistics': performance_stats,
            'battery_statistics': battery_stats
        }

    except Exception as e:
        logger.error(f"Error generating device performance report: {str(e)}")
        return {}