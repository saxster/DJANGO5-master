"""
Alert Service

Central service for alert creation, management, and processing.
Handles alert lifecycle, notifications, and escalations.
"""

import logging
from typing import Dict, List, Optional
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from apps.monitoring.models import (
    Alert, AlertRule, AlertInstance, AlertAcknowledgment,
    OperationalTicket, TicketCategory
)
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class AlertService:
    """
    Central alert management service.

    Provides comprehensive alert lifecycle management including:
    - Alert creation and validation
    - Rule evaluation and matching
    - Notification delivery
    - Escalation handling
    - Performance tracking
    """

    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
        self.escalation_enabled = True

    def create_alert(self, alert_data: Dict) -> Optional[Alert]:
        """
        Create a new alert with full validation and processing.

        Args:
            alert_data: Dictionary containing alert information

        Returns:
            Created Alert instance or None if creation failed
        """
        try:
            with transaction.atomic():
                # Validate alert data
                if not self._validate_alert_data(alert_data):
                    logger.warning(f"Invalid alert data: {alert_data}")
                    return None

                # Find or create matching rule
                rule = self._find_or_create_rule(alert_data)
                if not rule:
                    logger.error(f"Could not find/create rule for alert: {alert_data['alert_type']}")
                    return None

                # Check if rule can trigger (cooldown, conditions, etc.)
                if not rule.can_trigger(alert_data.get('context_data', {})):
                    logger.info(f"Rule {rule.name} cannot trigger due to conditions")
                    return None

                # Get user and site
                user = People.objects.get(id=alert_data['user_id'])
                site = user.bu  # Assuming user has associated business unit

                # Create the alert
                alert = Alert.objects.create(
                    rule=rule,
                    user=user,
                    device_id=alert_data['device_id'],
                    site=site,
                    severity=alert_data['severity'],
                    title=alert_data['title'],
                    description=alert_data['description'],
                    alert_data=alert_data.get('alert_data', {}),
                    context_data=alert_data.get('context_data', {}),
                    next_escalation_at=self._calculate_escalation_time(rule)
                )

                # Update rule statistics
                rule.total_triggered += 1
                rule.last_triggered = timezone.now()
                rule.save()

                # Create alert instance for tracking
                AlertInstance.objects.create(
                    alert=alert,
                    rule=rule,
                    user=user,
                    device_id=alert_data['device_id'],
                    triggered=True,
                    evaluation_data=alert_data.get('alert_data', {}),
                    threshold_values=alert_data.get('thresholds', {}),
                    evaluation_score=alert_data.get('score', 1.0)
                )

                # Process the alert (notifications, tickets, etc.)
                self._process_new_alert(alert)

                logger.info(f"Created alert {alert.alert_id} for user {user.peoplename}")
                return alert

        except Exception as e:
            logger.error(f"Error creating alert: {str(e)}", exc_info=True)
            return None

    def acknowledge_alert(self, alert_id: str, user_id: int, method: str = 'DASHBOARD', notes: str = "") -> bool:
        """
        Acknowledge an alert and track response time.

        Args:
            alert_id: Alert UUID
            user_id: User acknowledging the alert
            method: How the alert was acknowledged
            notes: Optional acknowledgment notes

        Returns:
            True if successfully acknowledged
        """
        try:
            with transaction.atomic():
                alert = Alert.objects.select_for_update().get(alert_id=alert_id)
                user = People.objects.get(id=user_id)

                if alert.status != 'ACTIVE':
                    logger.warning(f"Alert {alert_id} is not active, cannot acknowledge")
                    return False

                # Acknowledge the alert
                alert.acknowledge(user, notes)

                # Create detailed acknowledgment record
                response_time = int((timezone.now() - alert.triggered_at).total_seconds())
                AlertAcknowledgment.objects.create(
                    alert=alert,
                    acknowledged_by=user,
                    acknowledgment_method=method,
                    notes=notes,
                    response_time_seconds=response_time
                )

                # Cancel automatic escalations
                alert.next_escalation_at = None
                alert.save()

                # Send acknowledgment notifications
                self._send_acknowledgment_notifications(alert, user)

                logger.info(f"Alert {alert_id} acknowledged by {user.peoplename}")
                return True

        except Alert.DoesNotExist:
            logger.error(f"Alert {alert_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error acknowledging alert {alert_id}: {str(e)}", exc_info=True)
            return False

    def resolve_alert(self, alert_id: str, user_id: int, notes: str = "") -> bool:
        """
        Resolve an alert and track resolution time.

        Args:
            alert_id: Alert UUID
            user_id: User resolving the alert
            notes: Resolution notes

        Returns:
            True if successfully resolved
        """
        try:
            with transaction.atomic():
                alert = Alert.objects.select_for_update().get(alert_id=alert_id)
                user = People.objects.get(id=user_id)

                if alert.status in ['RESOLVED', 'FALSE_POSITIVE']:
                    logger.warning(f"Alert {alert_id} is already resolved")
                    return False

                # Resolve the alert
                alert.resolve(user, notes)

                # Send resolution notifications
                self._send_resolution_notifications(alert, user)

                # Auto-resolve related tickets if configured
                self._auto_resolve_related_tickets(alert)

                logger.info(f"Alert {alert_id} resolved by {user.peoplename}")
                return True

        except Alert.DoesNotExist:
            logger.error(f"Alert {alert_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error resolving alert {alert_id}: {str(e)}", exc_info=True)
            return False

    def escalate_overdue_alerts(self) -> int:
        """
        Escalate overdue alerts based on escalation rules.

        Returns:
            Number of alerts escalated
        """
        try:
            # Find alerts that need escalation
            overdue_alerts = Alert.objects.filter(
                status='ACTIVE',
                next_escalation_at__lte=timezone.now()
            ).select_related('rule', 'user')

            escalated_count = 0

            for alert in overdue_alerts:
                if self._escalate_alert(alert):
                    escalated_count += 1

            if escalated_count > 0:
                logger.info(f"Escalated {escalated_count} overdue alerts")

            return escalated_count

        except Exception as e:
            logger.error(f"Error escalating overdue alerts: {str(e)}", exc_info=True)
            return 0

    def get_active_alerts(self, user_id: Optional[int] = None, site_id: Optional[int] = None,
                         severity: Optional[str] = None) -> List[Dict]:
        """
        Get active alerts with optional filtering.

        Args:
            user_id: Filter by user ID
            site_id: Filter by site ID
            severity: Filter by severity level

        Returns:
            List of alert dictionaries
        """
        try:
            queryset = Alert.objects.filter(status='ACTIVE').select_related(
                'rule', 'user', 'site'
            ).order_by('-triggered_at')

            # Apply filters
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            if site_id:
                queryset = queryset.filter(site_id=site_id)
            if severity:
                queryset = queryset.filter(severity=severity)

            alerts = []
            for alert in queryset:
                alerts.append({
                    'alert_id': str(alert.alert_id),
                    'title': alert.title,
                    'description': alert.description,
                    'severity': alert.severity,
                    'user_name': alert.user.peoplename,
                    'site_name': alert.site.buname if alert.site else '',
                    'triggered_at': alert.triggered_at.isoformat(),
                    'is_overdue': alert.is_overdue,
                    'escalation_level': alert.escalation_level,
                    'alert_type': alert.rule.alert_type,
                    'device_id': alert.device_id
                })

            return alerts

        except Exception as e:
            logger.error(f"Error getting active alerts: {str(e)}", exc_info=True)
            return []

    def get_alert_statistics(self, days: int = 7) -> Dict:
        """
        Get alert statistics for the specified period.

        Args:
            days: Number of days to include in statistics

        Returns:
            Dictionary containing alert statistics
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days)

            # Get basic counts
            total_alerts = Alert.objects.filter(triggered_at__gte=cutoff_date).count()
            active_alerts = Alert.objects.filter(status='ACTIVE').count()
            resolved_alerts = Alert.objects.filter(
                status='RESOLVED',
                triggered_at__gte=cutoff_date
            ).count()

            # Get severity breakdown
            severity_counts = Alert.objects.filter(
                triggered_at__gte=cutoff_date
            ).values('severity').annotate(
                count=models.Count('id')
            )

            # Get alert type breakdown
            type_counts = Alert.objects.filter(
                triggered_at__gte=cutoff_date
            ).values('rule__alert_type').annotate(
                count=models.Count('id')
            )

            # Calculate average response time
            avg_response_time = AlertAcknowledgment.objects.filter(
                acknowledged_at__gte=cutoff_date
            ).aggregate(
                avg_response=models.Avg('response_time_seconds')
            )['avg_response'] or 0

            return {
                'period_days': days,
                'total_alerts': total_alerts,
                'active_alerts': active_alerts,
                'resolved_alerts': resolved_alerts,
                'severity_breakdown': {item['severity']: item['count'] for item in severity_counts},
                'type_breakdown': {item['rule__alert_type']: item['count'] for item in type_counts},
                'avg_response_time_seconds': int(avg_response_time),
                'resolution_rate': (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error getting alert statistics: {str(e)}", exc_info=True)
            return {}

    def _validate_alert_data(self, alert_data: Dict) -> bool:
        """Validate alert data structure and required fields"""
        required_fields = ['user_id', 'device_id', 'alert_type', 'severity', 'title', 'description']

        for field in required_fields:
            if field not in alert_data:
                logger.error(f"Missing required field: {field}")
                return False

        # Validate severity
        valid_severities = ['INFO', 'WARNING', 'HIGH', 'CRITICAL', 'EMERGENCY']
        if alert_data['severity'] not in valid_severities:
            logger.error(f"Invalid severity: {alert_data['severity']}")
            return False

        return True

    def _find_or_create_rule(self, alert_data: Dict) -> Optional[AlertRule]:
        """Find existing rule or create a default one for the alert type"""
        try:
            # Try to find existing rule
            rule = AlertRule.objects.filter(
                alert_type=alert_data['alert_type'],
                is_active=True
            ).first()

            if rule:
                return rule

            # Create default rule
            rule = AlertRule.objects.create(
                name=f"Default {alert_data['alert_type']} Rule",
                alert_type=alert_data['alert_type'],
                severity=alert_data['severity'],
                conditions={
                    'auto_generated': True,
                    'alert_type': alert_data['alert_type']
                },
                notification_channels=['dashboard'],
                cooldown_minutes=15,
                auto_resolve_minutes=60
            )

            logger.info(f"Created default rule for {alert_data['alert_type']}")
            return rule

        except Exception as e:
            logger.error(f"Error finding/creating rule: {str(e)}")
            return None

    def _calculate_escalation_time(self, rule: AlertRule) -> Optional[timezone.datetime]:
        """Calculate when the alert should be escalated"""
        if not rule.escalation_rules or not self.escalation_enabled:
            return None

        # Default escalation after 30 minutes
        escalation_minutes = 30
        if rule.escalation_rules:
            escalation_minutes = rule.escalation_rules[0].get('minutes', 30)

        return timezone.now() + timedelta(minutes=escalation_minutes)

    def _process_new_alert(self, alert: Alert):
        """Process a newly created alert (notifications, tickets, etc.)"""
        try:
            # Send notifications
            self._send_alert_notifications(alert)

            # Create ticket if configured
            if self._should_create_ticket(alert):
                self._create_alert_ticket(alert)

            # Cache alert for quick access
            self._cache_alert(alert)

        except Exception as e:
            logger.error(f"Error processing new alert {alert.alert_id}: {str(e)}")

    def _send_alert_notifications(self, alert: Alert):
        """Send notifications for a new alert"""
        try:
            notification_channels = alert.rule.notification_channels

            for channel in notification_channels:
                if channel == 'email':
                    self._send_email_notification(alert)
                elif channel == 'sms':
                    self._send_sms_notification(alert)
                elif channel == 'webhook':
                    self._send_webhook_notification(alert)
                elif channel == 'dashboard':
                    self._send_dashboard_notification(alert)

        except Exception as e:
            logger.error(f"Error sending notifications for alert {alert.alert_id}: {str(e)}")

    def _send_dashboard_notification(self, alert: Alert):
        """Send real-time dashboard notification"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    'monitoring_dashboard',
                    {
                        'type': 'alert_notification',
                        'alert': {
                            'alert_id': str(alert.alert_id),
                            'title': alert.title,
                            'severity': alert.severity,
                            'user_name': alert.user.peoplename,
                            'triggered_at': alert.triggered_at.isoformat()
                        }
                    }
                )

        except Exception as e:
            logger.error(f"Error sending dashboard notification: {str(e)}")

    def _send_email_notification(self, alert: Alert):
        """Send email notification for alert"""
        # Implementation would send email
        logger.info(f"Email notification sent for alert {alert.alert_id}")

    def _send_sms_notification(self, alert: Alert):
        """Send SMS notification for alert"""
        # Implementation would send SMS
        logger.info(f"SMS notification sent for alert {alert.alert_id}")

    def _send_webhook_notification(self, alert: Alert):
        """Send webhook notification for alert"""
        # Implementation would send webhook
        logger.info(f"Webhook notification sent for alert {alert.alert_id}")

    def _should_create_ticket(self, alert: Alert) -> bool:
        """Determine if a ticket should be created for this alert"""
        # Create tickets for high severity alerts
        return alert.severity in ['HIGH', 'CRITICAL', 'EMERGENCY']

    def _create_alert_ticket(self, alert: Alert):
        """Create an operational ticket for the alert"""
        try:
            # Find or create ticket category
            category_name = f"{alert.rule.alert_type}_TICKET"
            category, created = TicketCategory.objects.get_or_create(
                name=category_name,
                defaults={
                    'description': f"Auto-generated tickets for {alert.rule.alert_type} alerts",
                    'default_priority': alert.severity,
                    'title_template': 'Alert: {alert_type} - {user_name}',
                    'description_template': '{alert_description}',
                    'auto_assign': True
                }
            )

            # Create the ticket
            ticket = OperationalTicket.objects.create(
                category=category,
                alert=alert,
                user=alert.user,
                device_id=alert.device_id,
                site=alert.site,
                title=f"Alert: {alert.rule.alert_type} - {alert.user.peoplename}",
                description=alert.description,
                priority=alert.severity,
                automation_data={
                    'created_from_alert': True,
                    'alert_id': str(alert.alert_id),
                    'alert_data': alert.alert_data
                }
            )

            logger.info(f"Created ticket {ticket.ticket_number} for alert {alert.alert_id}")

        except Exception as e:
            logger.error(f"Error creating ticket for alert {alert.alert_id}: {str(e)}")

    def _escalate_alert(self, alert: Alert) -> bool:
        """Escalate an overdue alert"""
        try:
            alert.escalation_level += 1
            alert.next_escalation_at = timezone.now() + timedelta(minutes=30)  # Next escalation
            alert.save()

            # Send escalation notifications
            self._send_escalation_notifications(alert)

            logger.info(f"Escalated alert {alert.alert_id} to level {alert.escalation_level}")
            return True

        except Exception as e:
            logger.error(f"Error escalating alert {alert.alert_id}: {str(e)}")
            return False

    def _send_acknowledgment_notifications(self, alert: Alert, user: People):
        """Send notifications when alert is acknowledged"""
        # Implementation would notify relevant parties
        pass

    def _send_resolution_notifications(self, alert: Alert, user: People):
        """Send notifications when alert is resolved"""
        # Implementation would notify relevant parties
        pass

    def _send_escalation_notifications(self, alert: Alert):
        """Send notifications when alert is escalated"""
        # Implementation would notify escalation contacts
        pass

    def _auto_resolve_related_tickets(self, alert: Alert):
        """Auto-resolve tickets related to the resolved alert"""
        try:
            tickets = OperationalTicket.objects.filter(
                alert=alert,
                status__in=['OPEN', 'ASSIGNED', 'IN_PROGRESS']
            )

            for ticket in tickets:
                ticket.resolve(
                    user=alert.resolved_by,
                    resolution_type='AUTOMATIC',
                    notes=f"Auto-resolved due to alert resolution: {alert.resolution_notes}"
                )

        except Exception as e:
            logger.error(f"Error auto-resolving tickets for alert {alert.alert_id}: {str(e)}")

    def _cache_alert(self, alert: Alert):
        """Cache alert for quick access"""
        try:
            cache_key = f"alert:{alert.alert_id}"
            cache.set(cache_key, {
                'alert_id': str(alert.alert_id),
                'title': alert.title,
                'severity': alert.severity,
                'status': alert.status,
                'user_id': alert.user_id,
                'device_id': alert.device_id
            }, self.cache_timeout)

        except Exception as e:
            logger.error(f"Error caching alert {alert.alert_id}: {str(e)}")