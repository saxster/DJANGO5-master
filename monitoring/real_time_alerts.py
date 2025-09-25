"""
Real-time Alert System for Performance Monitoring

This module provides:
1. WebSocket-based real-time alerts
2. Dashboard notifications
3. Slack/Teams integration
4. Alert escalation and acknowledgment
5. Alert dashboard and management

Features:
- Real-time browser notifications
- Mobile push notifications
- Integration with external systems
- Alert acknowledgment and resolution tracking
"""

import json
import logging
import asyncio
import aioredis
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.urls import reverse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import requests

logger = logging.getLogger('real_time_alerts')


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class Alert:
    """Represents a system alert"""
    id: str
    timestamp: datetime
    severity: AlertSeverity
    title: str
    message: str
    source: str
    tags: Dict[str, str]
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalation_level: int = 0
    notification_channels: List[str] = None
    
    def __post_init__(self):
        if self.notification_channels is None:
            self.notification_channels = ['websocket']
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        if self.acknowledged_at:
            data['acknowledged_at'] = self.acknowledged_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        return data


class AlertManager:
    """Manages real-time alerts and notifications"""
    
    def __init__(self):
        self.active_alerts = {}  # Dict[str, Alert]
        self.alert_history = deque(maxlen=1000)
        self.subscribers = defaultdict(list)  # Dict[str, List[Callable]]
        self.escalation_rules = {}
        self.notification_handlers = {}
        
        # Initialize notification handlers
        self._setup_notification_handlers()
        self._setup_escalation_rules()
    
    def create_alert(self, title: str, message: str, severity: AlertSeverity,
                    source: str, tags: Dict[str, str] = None,
                    notification_channels: List[str] = None) -> Alert:
        """Create a new alert"""
        alert = Alert(
            id=self._generate_alert_id(),
            timestamp=datetime.now(),
            severity=severity,
            title=title,
            message=message,
            source=source,
            tags=tags or {},
            notification_channels=notification_channels or ['websocket']
        )
        
        # Store alert
        self.active_alerts[alert.id] = alert
        self.alert_history.append(alert)
        
        # Send notifications
        self._send_notifications(alert)
        
        # Log alert
        logger.log(
            level=self._severity_to_log_level(severity),
            msg=f"Alert created: {title} - {message}",
            extra={'alert_id': alert.id, 'severity': severity.value}
        )
        
        return alert
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now()
        
        # Notify subscribers
        self._notify_subscribers('alert_acknowledged', alert)
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True
    
    def resolve_alert(self, alert_id: str, resolved_by: str = None) -> bool:
        """Resolve an alert"""
        if alert_id not in self.active_alerts:
            return False
        
        alert = self.active_alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        
        # Remove from active alerts
        del self.active_alerts[alert_id]
        
        # Notify subscribers
        self._notify_subscribers('alert_resolved', alert)
        
        logger.info(f"Alert {alert_id} resolved by {resolved_by or 'system'}")
        return True
    
    def get_active_alerts(self, severity_filter: AlertSeverity = None,
                         source_filter: str = None) -> List[Alert]:
        """Get active alerts with optional filtering"""
        alerts = list(self.active_alerts.values())
        
        if severity_filter:
            alerts = [a for a in alerts if a.severity == severity_filter]
        
        if source_filter:
            alerts = [a for a in alerts if a.source == source_filter]
        
        # Sort by timestamp (newest first)
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def get_alert_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get alert summary for the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent_alerts = [
            alert for alert in self.alert_history
            if alert.timestamp >= cutoff
        ]
        
        # Count by severity
        severity_counts = defaultdict(int)
        for alert in recent_alerts:
            severity_counts[alert.severity.value] += 1
        
        # Count by source
        source_counts = defaultdict(int)
        for alert in recent_alerts:
            source_counts[alert.source] += 1
        
        return {
            'total_alerts': len(recent_alerts),
            'active_alerts': len(self.active_alerts),
            'by_severity': dict(severity_counts),
            'by_source': dict(source_counts),
            'period_hours': hours
        }
    
    def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to alert events"""
        self.subscribers[event_type].append(callback)
    
    def _send_notifications(self, alert: Alert):
        """Send notifications through configured channels"""
        for channel in alert.notification_channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Error sending notification via {channel}: {e}")
    
    def _setup_notification_handlers(self):
        """Setup notification handlers"""
        self.notification_handlers = {
            'websocket': self._send_websocket_notification,
            'email': self._send_email_notification,
            'slack': self._send_slack_notification,
            'teams': self._send_teams_notification,
            'webhook': self._send_webhook_notification
        }
    
    def _send_websocket_notification(self, alert: Alert):
        """Send real-time notification via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "monitoring_alerts",
                    {
                        "type": "alert_notification",
                        "alert": alert.to_dict()
                    }
                )
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
    
    def _send_email_notification(self, alert: Alert):
        """Send email notification"""
        if not getattr(settings, 'ADMINS', None):
            return
        
        try:
            from django.core.mail import send_mail
            
            subject = f"[{alert.severity.value.upper()}] {alert.title}"
            message = f"""
Alert Details:
- Severity: {alert.severity.value}
- Source: {alert.source}
- Time: {alert.timestamp}
- Message: {alert.message}

Tags: {alert.tags}

Dashboard: {settings.SITE_URL}/monitoring/alerts/
"""
            
            recipients = [admin[1] for admin in settings.ADMINS]
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False
            )
            
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
    
    def _send_slack_notification(self, alert: Alert):
        """Send Slack notification"""
        webhook_url = getattr(settings, 'SLACK_WEBHOOK_URL', None)
        if not webhook_url:
            return
        
        try:
            color = self._severity_to_slack_color(alert.severity)
            
            payload = {
                "text": f"Performance Alert: {alert.title}",
                "attachments": [{
                    "color": color,
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert.severity.value.upper(),
                            "short": True
                        },
                        {
                            "title": "Source",
                            "value": alert.source,
                            "short": True
                        },
                        {
                            "title": "Message",
                            "value": alert.message,
                            "short": False
                        },
                        {
                            "title": "Time",
                            "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True
                        }
                    ]
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
    
    def _send_teams_notification(self, alert: Alert):
        """Send Microsoft Teams notification"""
        webhook_url = getattr(settings, 'TEAMS_WEBHOOK_URL', None)
        if not webhook_url:
            return
        
        try:
            color = self._severity_to_teams_color(alert.severity)
            
            payload = {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "themeColor": color,
                "summary": f"Performance Alert: {alert.title}",
                "sections": [{
                    "activityTitle": f"Performance Alert: {alert.title}",
                    "activitySubtitle": f"Severity: {alert.severity.value.upper()}",
                    "facts": [
                        {"name": "Source", "value": alert.source},
                        {"name": "Time", "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")},
                        {"name": "Message", "value": alert.message}
                    ]
                }]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Teams notification failed: {e}")
    
    def _send_webhook_notification(self, alert: Alert):
        """Send generic webhook notification"""
        webhook_url = getattr(settings, 'MONITORING_WEBHOOK_URL', None)
        if not webhook_url:
            return
        
        try:
            payload = {
                "event": "alert_created",
                "alert": alert.to_dict()
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
    
    def _setup_escalation_rules(self):
        """Setup alert escalation rules"""
        self.escalation_rules = {
            AlertSeverity.CRITICAL: {
                'escalation_time': 300,  # 5 minutes
                'escalation_channels': ['email', 'slack', 'teams']
            },
            AlertSeverity.ERROR: {
                'escalation_time': 900,  # 15 minutes
                'escalation_channels': ['email', 'slack']
            },
            AlertSeverity.WARNING: {
                'escalation_time': 1800,  # 30 minutes
                'escalation_channels': ['email']
            }
        }
    
    def _notify_subscribers(self, event_type: str, alert: Alert):
        """Notify event subscribers"""
        for callback in self.subscribers.get(event_type, []):
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID"""
        import uuid
        return f"alert_{uuid.uuid4().hex[:8]}"
    
    def _severity_to_log_level(self, severity: AlertSeverity) -> int:
        """Convert alert severity to log level"""
        mapping = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }
        return mapping.get(severity, logging.WARNING)
    
    def _severity_to_slack_color(self, severity: AlertSeverity) -> str:
        """Convert severity to Slack color"""
        mapping = {
            AlertSeverity.INFO: "#36a64f",      # green
            AlertSeverity.WARNING: "#ff9500",   # orange
            AlertSeverity.ERROR: "#ff0000",     # red
            AlertSeverity.CRITICAL: "#8B0000"   # dark red
        }
        return mapping.get(severity, "#ff9500")
    
    def _severity_to_teams_color(self, severity: AlertSeverity) -> str:
        """Convert severity to Teams color"""
        mapping = {
            AlertSeverity.INFO: "0078D4",       # blue
            AlertSeverity.WARNING: "FF8C00",    # orange
            AlertSeverity.ERROR: "FF0000",      # red
            AlertSeverity.CRITICAL: "8B0000"    # dark red
        }
        return mapping.get(severity, "FF8C00")


class PerformanceAlerts:
    """Performance-specific alert creation"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
    
    def slow_query_alert(self, sql: str, duration: float, threshold: float,
                        request_path: str = None) -> Alert:
        """Create slow query alert"""
        severity = AlertSeverity.CRITICAL if duration > threshold * 3 else AlertSeverity.WARNING
        
        return self.alert_manager.create_alert(
            title="Slow Query Detected",
            message=f"Query took {duration:.3f}s (threshold: {threshold:.1f}s)",
            severity=severity,
            source="database",
            tags={
                "query_duration": str(duration),
                "threshold": str(threshold),
                "request_path": request_path or "unknown",
                "sql_preview": sql[:100] + "..." if len(sql) > 100 else sql
            },
            notification_channels=['websocket', 'email'] if severity == AlertSeverity.CRITICAL else ['websocket']
        )
    
    def response_time_alert(self, endpoint: str, response_time: float,
                           threshold: float) -> Alert:
        """Create response time alert"""
        severity = AlertSeverity.ERROR if response_time > threshold * 2 else AlertSeverity.WARNING
        
        return self.alert_manager.create_alert(
            title="Slow Response Time",
            message=f"Endpoint {endpoint} responded in {response_time:.3f}s",
            severity=severity,
            source="application",
            tags={
                "endpoint": endpoint,
                "response_time": str(response_time),
                "threshold": str(threshold)
            }
        )
    
    def memory_usage_alert(self, memory_percent: float, threshold: float) -> Alert:
        """Create memory usage alert"""
        severity = AlertSeverity.CRITICAL if memory_percent > 90 else AlertSeverity.WARNING
        
        return self.alert_manager.create_alert(
            title="High Memory Usage",
            message=f"Memory usage at {memory_percent:.1f}% (threshold: {threshold:.1f}%)",
            severity=severity,
            source="system",
            tags={
                "memory_percent": str(memory_percent),
                "threshold": str(threshold)
            },
            notification_channels=['websocket', 'email', 'slack']
        )
    
    def regression_alert(self, endpoint: str, current_time: float,
                        baseline_time: float, regression_percent: float) -> Alert:
        """Create performance regression alert"""
        return self.alert_manager.create_alert(
            title="Performance Regression",
            message=f"Endpoint {endpoint} is {regression_percent:.1f}% slower than baseline",
            severity=AlertSeverity.WARNING,
            source="performance",
            tags={
                "endpoint": endpoint,
                "current_time": str(current_time),
                "baseline_time": str(baseline_time),
                "regression_percent": str(regression_percent)
            },
            notification_channels=['websocket', 'email']
        )


# Global alert manager and performance alerts
alert_manager = AlertManager()
performance_alerts = PerformanceAlerts(alert_manager)

# Convenience functions
def create_alert(title: str, message: str, severity: AlertSeverity, source: str,
                tags: Dict[str, str] = None) -> Alert:
    """Create a new alert"""
    return alert_manager.create_alert(title, message, severity, source, tags)

def get_active_alerts() -> List[Alert]:
    """Get all active alerts"""
    return alert_manager.get_active_alerts()

def acknowledge_alert(alert_id: str, acknowledged_by: str) -> bool:
    """Acknowledge an alert"""
    return alert_manager.acknowledge_alert(alert_id, acknowledged_by)