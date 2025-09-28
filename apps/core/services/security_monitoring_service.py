"""
Security Monitoring and Alerting Service.

This service provides comprehensive security monitoring, threat detection,
and alerting capabilities for the YOUTILITY3 platform.

Features:
1. Real-time security event monitoring
2. Threat pattern detection and analysis
3. Automated incident response
4. Security metrics and reporting
5. Integration with existing middleware and services
"""
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.core.mail import send_mail
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, IntegrityError
from smtplib import SMTPException
from apps.core.error_handling import ErrorHandler
from apps.core.middleware.logging_sanitization import sanitized_warning, sanitized_error
from apps.core.exceptions import (
    SecurityException,
    EmailServiceException,
    CacheException,
    SystemException,
    DatabaseException
)

logger = logging.getLogger("security_monitoring")


class SecurityEvent:
    """Represents a security event for monitoring and analysis."""

    def __init__(self, event_type: str, severity: str, details: Dict[str, Any],
                 correlation_id: Optional[str] = None, client_ip: Optional[str] = None):
        self.event_type = event_type
        self.severity = severity  # 'low', 'medium', 'high', 'critical'
        self.details = details
        self.correlation_id = correlation_id
        self.client_ip = client_ip
        self.timestamp = datetime.now()
        self.event_id = f"{event_type}_{int(time.time())}_{id(self)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'severity': self.severity,
            'details': self.details,
            'correlation_id': self.correlation_id,
            'client_ip': self.client_ip,
            'timestamp': self.timestamp.isoformat(),
        }


class SecurityMonitoringService:
    """
    Centralized security monitoring and alerting service.

    This service aggregates security events from various components and
    provides threat detection, alerting, and incident response capabilities.
    """

    # Event storage (in production, use persistent storage like Redis/DB)
    _security_events = deque(maxlen=10000)  # Keep last 10k events
    _event_counters = defaultdict(int)
    _alert_thresholds = {
        'xss_attempts': {'count': 10, 'window': 300},  # 10 attempts in 5 minutes
        'encryption_failures': {'count': 5, 'window': 60},  # 5 failures in 1 minute
        'query_performance': {'count': 20, 'window': 300},  # 20 slow queries in 5 minutes
        'authentication_failures': {'count': 15, 'window': 300},  # 15 failures in 5 minutes
    }

    @classmethod
    def record_security_event(cls, event: SecurityEvent) -> None:
        """
        Record a security event for monitoring and analysis.

        Args:
            event: SecurityEvent instance to record
        """
        try:
            # Store event
            cls._security_events.append(event)

            # Update counters
            cls._event_counters[event.event_type] += 1

            # Log event
            sanitized_warning(
                logger,
                f"Security event recorded: {event.event_type}",
                extra=event.to_dict()
            )

            # Check for alert conditions
            cls._check_alert_conditions(event)

            # Store in cache for recent events API
            cls._cache_recent_event(event)

        except CacheException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'record_security_event_cache', 'event_type': event.event_type},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Cache operation failed during security event recording (ID: {correlation_id})"
            )
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'record_security_event_data', 'event_type': event.event_type},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data processing error during security event recording (ID: {correlation_id})"
            )
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'record_security_event_system', 'event_type': event.event_type},
                level='critical'
            )
            sanitized_error(
                logger,
                f"System error during security event recording (ID: {correlation_id})"
            )

    @classmethod
    def _check_alert_conditions(cls, event: SecurityEvent) -> None:
        """
        Check if event triggers any alert conditions.

        Args:
            event: SecurityEvent to check
        """
        event_type = event.event_type
        if event_type not in cls._alert_thresholds:
            return

        threshold_config = cls._alert_thresholds[event_type]
        window_seconds = threshold_config['window']
        max_count = threshold_config['count']

        # Count recent events of this type
        cutoff_time = datetime.now() - timedelta(seconds=window_seconds)
        recent_events = [
            e for e in cls._security_events
            if e.event_type == event_type and e.timestamp > cutoff_time
        ]

        if len(recent_events) >= max_count:
            cls._trigger_security_alert(event_type, recent_events, threshold_config)

    @classmethod
    def _trigger_security_alert(cls, event_type: str, events: List[SecurityEvent],
                               threshold_config: Dict[str, Any]) -> None:
        """
        Trigger a security alert for detected threat pattern.

        Args:
            event_type: Type of events triggering alert
            events: List of events in the pattern
            threshold_config: Threshold configuration
        """
        try:
            alert_data = {
                'alert_type': f'{event_type}_threshold_exceeded',
                'event_type': event_type,
                'event_count': len(events),
                'time_window': threshold_config['window'],
                'threshold': threshold_config['count'],
                'first_event_time': events[0].timestamp.isoformat(),
                'last_event_time': events[-1].timestamp.isoformat(),
                'affected_ips': list(set(e.client_ip for e in events if e.client_ip)),
                'correlation_ids': list(set(e.correlation_id for e in events if e.correlation_id)),
            }

            # Log critical alert
            sanitized_error(
                logger,
                f"SECURITY ALERT: {event_type} threshold exceeded",
                extra=alert_data
            )

            # Send email alert if configured
            cls._send_email_alert(alert_data)

            # Cache alert for dashboard
            cls._cache_security_alert(alert_data)

            # Trigger automated response if configured
            cls._trigger_automated_response(event_type, alert_data)

        except EmailServiceException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'trigger_security_alert_email', 'event_type': event_type},
                level='error'
            )
            sanitized_error(
                logger,
                f"Email service failed during security alert (ID: {correlation_id})"
            )
        except CacheException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'trigger_security_alert_cache', 'event_type': event_type},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Cache operation failed during security alert (ID: {correlation_id})"
            )
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'trigger_security_alert_data', 'event_type': event_type},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data processing error during security alert (ID: {correlation_id})"
            )
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'trigger_security_alert_system', 'event_type': event_type},
                level='critical'
            )
            sanitized_error(
                logger,
                f"System error during security alert (ID: {correlation_id})"
            )

    @classmethod
    def _send_email_alert(cls, alert_data: Dict[str, Any]) -> None:
        """
        Send email alert to security team.

        Args:
            alert_data: Alert information
        """
        try:
            recipients = getattr(settings, 'SECURITY_ALERT_RECIPIENTS', [])
            if not recipients:
                return

            subject = f"SECURITY ALERT: {alert_data['alert_type']}"
            message = cls._format_alert_email(alert_data)

            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'security@youtility.com'),
                recipient_list=recipients,
                fail_silently=False
            )

            sanitized_warning(
                logger,
                f"Security alert email sent to {len(recipients)} recipients"
            )

        except SMTPException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'send_email_alert_smtp'},
                level='error'
            )
            sanitized_error(
                logger,
                f"SMTP error sending security alert email (ID: {correlation_id})"
            )
        except (ConnectionError, OSError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'send_email_alert_connection'},
                level='error'
            )
            sanitized_error(
                logger,
                f"Network error sending security alert email (ID: {correlation_id})"
            )
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'send_email_alert_data'},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data error in security alert email (ID: {correlation_id})"
            )

    @classmethod
    def _format_alert_email(cls, alert_data: Dict[str, Any]) -> str:
        """Format security alert email message."""
        return f"""
SECURITY ALERT NOTIFICATION

Alert Type: {alert_data['alert_type']}
Event Type: {alert_data['event_type']}
Event Count: {alert_data['event_count']} events
Time Window: {alert_data['time_window']} seconds
Threshold: {alert_data['threshold']} events

Time Range:
  First Event: {alert_data['first_event_time']}
  Last Event: {alert_data['last_event_time']}

Affected IPs: {', '.join(alert_data['affected_ips'])}

Please investigate this security incident immediately.

Correlation IDs for investigation:
{chr(10).join(alert_data['correlation_ids'])}

YOUTILITY3 Security Monitoring System
        """.strip()

    @classmethod
    def _cache_recent_event(cls, event: SecurityEvent) -> None:
        """Cache recent events for API access."""
        try:
            cache_key = 'security_recent_events'
            recent_events = cache.get(cache_key, [])

            # Add new event and keep only last 100
            recent_events.append(event.to_dict())
            recent_events = recent_events[-100:]

            cache.set(cache_key, recent_events, timeout=3600)  # 1 hour

        except CacheException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'cache_recent_event'},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Failed to cache recent security event (ID: {correlation_id})"
            )
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'cache_recent_event_data'},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data error caching recent security event (ID: {correlation_id})"
            )

    @classmethod
    def _cache_security_alert(cls, alert_data: Dict[str, Any]) -> None:
        """Cache security alerts for dashboard display."""
        try:
            cache_key = 'security_alerts'
            alerts = cache.get(cache_key, [])

            # Add new alert and keep only last 50
            alert_data['alert_time'] = datetime.now().isoformat()
            alerts.append(alert_data)
            alerts = alerts[-50:]

            cache.set(cache_key, alerts, timeout=86400)  # 24 hours

        except CacheException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'cache_security_alert'},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Failed to cache security alert (ID: {correlation_id})"
            )
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'cache_security_alert_data'},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data error caching security alert (ID: {correlation_id})"
            )

    @classmethod
    def _trigger_automated_response(cls, event_type: str, alert_data: Dict[str, Any]) -> None:
        """
        Trigger automated incident response if configured.

        Args:
            event_type: Type of security event
            alert_data: Alert information
        """
        try:
            automated_responses = getattr(settings, 'SECURITY_AUTOMATED_RESPONSES', {})

            if event_type in automated_responses:
                response_config = automated_responses[event_type]

                if response_config.get('block_ips'):
                    cls._block_suspicious_ips(alert_data['affected_ips'])

                if response_config.get('increase_logging'):
                    cls._increase_security_logging()

                if response_config.get('notify_admins'):
                    cls._notify_administrators(alert_data)

        except (ConnectionError, OSError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'automated_response_network', 'event_type': event_type},
                level='error'
            )
            sanitized_error(
                logger,
                f"Network error in automated response for {event_type} (ID: {correlation_id})"
            )
        except PermissionDenied as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'automated_response_permission', 'event_type': event_type},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Permission denied in automated response for {event_type} (ID: {correlation_id})"
            )
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'automated_response_data', 'event_type': event_type},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data error in automated response for {event_type} (ID: {correlation_id})"
            )

    @classmethod
    def _block_suspicious_ips(cls, ip_addresses: List[str]) -> None:
        """
        Block suspicious IP addresses (placeholder for actual implementation).

        Args:
            ip_addresses: List of IP addresses to block
        """
        # In production, this would integrate with firewall/load balancer
        sanitized_warning(
            logger,
            f"IP blocking triggered for {len(ip_addresses)} addresses",
            extra={'blocked_ips': ip_addresses}
        )

    @classmethod
    def _increase_security_logging(cls) -> None:
        """Increase security logging level temporarily."""
        # Set higher logging level for security components
        security_logger = logging.getLogger("security")
        security_logger.setLevel(logging.DEBUG)

        sanitized_warning(
            logger,
            "Security logging level increased to DEBUG due to threat detection"
        )

    @classmethod
    def _notify_administrators(cls, alert_data: Dict[str, Any]) -> None:
        """Notify system administrators of security incident."""
        # This could integrate with Slack, PagerDuty, etc.
        sanitized_warning(
            logger,
            f"Administrator notification triggered for {alert_data['alert_type']}"
        )

    @classmethod
    def get_security_metrics(cls, time_window: int = 3600) -> Dict[str, Any]:
        """
        Get security metrics for the specified time window.

        Args:
            time_window: Time window in seconds (default: 1 hour)

        Returns:
            dict: Security metrics summary
        """
        try:
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            recent_events = [
                e for e in cls._security_events
                if e.timestamp > cutoff_time
            ]

            # Aggregate metrics
            metrics = {
                'time_window': time_window,
                'total_events': len(recent_events),
                'events_by_type': defaultdict(int),
                'events_by_severity': defaultdict(int),
                'unique_ips': set(),
                'event_timeline': [],
            }

            for event in recent_events:
                metrics['events_by_type'][event.event_type] += 1
                metrics['events_by_severity'][event.severity] += 1
                if event.client_ip:
                    metrics['unique_ips'].add(event.client_ip)

            # Convert sets to counts
            metrics['unique_ips'] = len(metrics['unique_ips'])

            # Create timeline (events per 5-minute buckets)
            timeline_buckets = defaultdict(int)
            bucket_size = 300  # 5 minutes

            for event in recent_events:
                bucket = int(event.timestamp.timestamp() // bucket_size) * bucket_size
                timeline_buckets[bucket] += 1

            metrics['event_timeline'] = [
                {'timestamp': bucket, 'count': count}
                for bucket, count in sorted(timeline_buckets.items())
            ]

            return dict(metrics)

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'get_security_metrics_data', 'time_window': time_window},
                level='warning'
            )
            return {'error': f'Data processing error generating metrics (ID: {correlation_id})'}
        except (MemoryError, OverflowError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'get_security_metrics_memory', 'time_window': time_window},
                level='error'
            )
            return {'error': f'Memory error generating metrics (ID: {correlation_id})'}
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'get_security_metrics_system', 'time_window': time_window},
                level='critical'
            )
            return {'error': f'System error generating metrics (ID: {correlation_id})'}

    @classmethod
    def get_recent_alerts(cls, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent security alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            list: Recent security alerts
        """
        try:
            alerts = cache.get('security_alerts', [])
            return alerts[-limit:]

        except CacheException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'get_recent_alerts_cache', 'limit': limit},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Cache error getting recent alerts (ID: {correlation_id})"
            )
            return []
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'get_recent_alerts_data', 'limit': limit},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data error getting recent alerts (ID: {correlation_id})"
            )
            return []

    @classmethod
    def clear_old_events(cls, retention_hours: int = 24) -> int:
        """
        Clear old security events to manage memory usage.

        Args:
            retention_hours: Hours to retain events

        Returns:
            int: Number of events cleared
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=retention_hours)

            original_count = len(cls._security_events)

            # Filter out old events
            cls._security_events = deque(
                (e for e in cls._security_events if e.timestamp > cutoff_time),
                maxlen=cls._security_events.maxlen
            )

            cleared_count = original_count - len(cls._security_events)

            if cleared_count > 0:
                sanitized_warning(
                    logger,
                    f"Cleared {cleared_count} old security events"
                )

            return cleared_count

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'clear_old_events_data', 'retention_hours': retention_hours},
                level='warning'
            )
            sanitized_warning(
                logger,
                f"Data error clearing old events (ID: {correlation_id})"
            )
            return 0
        except (MemoryError, OverflowError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'clear_old_events_memory', 'retention_hours': retention_hours},
                level='error'
            )
            sanitized_error(
                logger,
                f"Memory error clearing old events (ID: {correlation_id})"
            )
            return 0
        except SystemException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'clear_old_events_system', 'retention_hours': retention_hours},
                level='critical'
            )
            sanitized_error(
                logger,
                f"System error clearing old events (ID: {correlation_id})"
            )
            return 0


# Convenience functions for common security events
def record_xss_attempt(client_ip: str, payload: str, request_path: str,
                      correlation_id: Optional[str] = None) -> None:
    """Record an XSS attempt event."""
    event = SecurityEvent(
        event_type='xss_attempts',
        severity='high',
        details={
            'payload_preview': payload[:100],
            'request_path': request_path,
            'payload_length': len(payload)
        },
        correlation_id=correlation_id,
        client_ip=client_ip
    )
    SecurityMonitoringService.record_security_event(event)


def record_encryption_failure(operation: str, error_type: str,
                             correlation_id: Optional[str] = None) -> None:
    """Record an encryption failure event."""
    event = SecurityEvent(
        event_type='encryption_failures',
        severity='medium',
        details={
            'operation': operation,
            'error_type': error_type
        },
        correlation_id=correlation_id
    )
    SecurityMonitoringService.record_security_event(event)


def record_query_performance_issue(query_count: int, query_time: float, request_path: str,
                                  correlation_id: Optional[str] = None) -> None:
    """Record a query performance issue."""
    event = SecurityEvent(
        event_type='query_performance',
        severity='medium',
        details={
            'query_count': query_count,
            'query_time': query_time,
            'request_path': request_path
        },
        correlation_id=correlation_id
    )
    SecurityMonitoringService.record_security_event(event)


def record_authentication_failure(client_ip: str, username: str, failure_reason: str,
                                 correlation_id: Optional[str] = None) -> None:
    """Record an authentication failure event."""
    event = SecurityEvent(
        event_type='authentication_failures',
        severity='medium',
        details={
            'username': username,
            'failure_reason': failure_reason
        },
        correlation_id=correlation_id,
        client_ip=client_ip
    )
    SecurityMonitoringService.record_security_event(event)