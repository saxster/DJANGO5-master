"""
GraphQL Security Monitoring and Alerting System

Comprehensive monitoring system for GraphQL security events that provides:
- Real-time security event detection
- Automated threat analysis
- Security metrics collection
- Alert generation and escalation
- Compliance reporting
- Incident response automation
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone
from apps.core.error_handling import CorrelationIDMiddleware


security_monitor_logger = logging.getLogger('graphql_security_monitor')
alert_logger = logging.getLogger('security_alerts')


@dataclass
class SecurityEvent:
    """Represents a GraphQL security event."""
    event_id: str
    event_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    timestamp: datetime
    correlation_id: str
    user_id: Optional[str]
    client_ip: str
    user_agent: str
    origin: str
    query_fingerprint: str
    event_details: Dict[str, Any]
    threat_indicators: List[str]
    response_actions: List[str]


@dataclass
class SecurityMetrics:
    """Security metrics for monitoring dashboard."""
    total_requests: int
    blocked_requests: int
    csrf_violations: int
    rate_limit_violations: int
    origin_violations: int
    query_analysis_failures: int
    threat_score: float
    last_updated: datetime


@dataclass
class ThreatPattern:
    """Represents a detected threat pattern."""
    pattern_id: str
    pattern_name: str
    detection_count: int
    first_detected: datetime
    last_detected: datetime
    threat_level: str
    affected_users: List[str]
    affected_ips: List[str]
    mitigation_actions: List[str]


class GraphQLSecurityMonitor:
    """
    Central security monitoring system for GraphQL endpoints.

    Collects, analyzes, and responds to security events in real-time.
    """

    def __init__(self):
        self.config = self._load_monitoring_config()
        self.alert_handlers = self._setup_alert_handlers()
        self.threat_detectors = self._setup_threat_detectors()
        self.metrics_cache_ttl = 300  # 5 minutes
        self.event_retention_days = 30

    def record_security_event(self, event_type: str, severity: str, correlation_id: str,
                            request_context: Dict[str, Any], event_details: Dict[str, Any]) -> SecurityEvent:
        """
        Record a security event for monitoring and analysis.

        Args:
            event_type: Type of security event
            severity: Event severity level
            correlation_id: Request correlation ID
            request_context: Request context information
            event_details: Specific event details

        Returns:
            SecurityEvent object
        """
        try:
            # Create security event
            event = SecurityEvent(
                event_id=self._generate_event_id(),
                event_type=event_type,
                severity=severity,
                timestamp=timezone.now(),
                correlation_id=correlation_id,
                user_id=request_context.get('user_id'),
                client_ip=request_context.get('client_ip', 'unknown'),
                user_agent=request_context.get('user_agent', 'unknown'),
                origin=request_context.get('origin', ''),
                query_fingerprint=request_context.get('query_fingerprint', ''),
                event_details=event_details,
                threat_indicators=[],
                response_actions=[]
            )

            # Analyze threat indicators
            self._analyze_threat_indicators(event)

            # Determine response actions
            self._determine_response_actions(event)

            # Store event
            self._store_security_event(event)

            # Update metrics
            self._update_security_metrics(event)

            # Check for threat patterns
            self._check_threat_patterns(event)

            # Trigger alerts if necessary
            self._trigger_alerts(event)

            # Log event
            self._log_security_event(event)

            return event

        except (ValueError, TypeError) as e:
            security_monitor_logger.error(
                f"Failed to record security event: {str(e)}, Correlation ID: {correlation_id}",
                exc_info=True
            )
            # Return minimal event to prevent cascade failures
            return SecurityEvent(
                event_id='error',
                event_type=event_type,
                severity=severity,
                timestamp=timezone.now(),
                correlation_id=correlation_id,
                user_id=None,
                client_ip='unknown',
                user_agent='unknown',
                origin='',
                query_fingerprint='',
                event_details={},
                threat_indicators=['monitoring_error'],
                response_actions=[]
            )

    def get_security_metrics(self, time_window_minutes: int = 60) -> SecurityMetrics:
        """
        Get security metrics for the specified time window.

        Args:
            time_window_minutes: Time window for metrics calculation

        Returns:
            SecurityMetrics object
        """
        cache_key = f"graphql_security_metrics:{time_window_minutes}"
        cached_metrics = cache.get(cache_key)

        if cached_metrics:
            return SecurityMetrics(**cached_metrics)

        try:
            # Calculate metrics from stored events
            metrics = self._calculate_security_metrics(time_window_minutes)

            # Cache metrics
            cache.set(cache_key, asdict(metrics), self.metrics_cache_ttl)

            return metrics

        except (ConnectionError, ValueError) as e:
            security_monitor_logger.error(f"Failed to calculate security metrics: {str(e)}", exc_info=True)

            # Return default metrics
            return SecurityMetrics(
                total_requests=0,
                blocked_requests=0,
                csrf_violations=0,
                rate_limit_violations=0,
                origin_violations=0,
                query_analysis_failures=0,
                threat_score=0.0,
                last_updated=timezone.now()
            )

    def get_threat_patterns(self, time_window_hours: int = 24) -> List[ThreatPattern]:
        """
        Get detected threat patterns for the specified time window.

        Args:
            time_window_hours: Time window for pattern detection

        Returns:
            List of ThreatPattern objects
        """
        try:
            return self._detect_threat_patterns(time_window_hours)
        except (ConnectionError, ValueError) as e:
            security_monitor_logger.error(f"Failed to detect threat patterns: {str(e)}", exc_info=True)
            return []

    def generate_security_report(self, report_type: str = 'daily') -> Dict[str, Any]:
        """
        Generate comprehensive security report.

        Args:
            report_type: Type of report ('hourly', 'daily', 'weekly')

        Returns:
            Security report dictionary
        """
        try:
            time_windows = {
                'hourly': 60,
                'daily': 24 * 60,
                'weekly': 7 * 24 * 60
            }

            window_minutes = time_windows.get(report_type, 24 * 60)
            metrics = self.get_security_metrics(window_minutes)
            threat_patterns = self.get_threat_patterns(window_minutes // 60)

            report = {
                'report_type': report_type,
                'time_window_minutes': window_minutes,
                'generated_at': timezone.now().isoformat(),
                'metrics': asdict(metrics),
                'threat_patterns': [asdict(pattern) for pattern in threat_patterns],
                'recommendations': self._generate_security_recommendations(metrics, threat_patterns),
                'summary': self._generate_report_summary(metrics, threat_patterns)
            }

            return report

        except (ConnectionError, ValueError) as e:
            security_monitor_logger.error(f"Failed to generate security report: {str(e)}", exc_info=True)
            return {
                'report_type': report_type,
                'error': 'Failed to generate report',
                'generated_at': timezone.now().isoformat()
            }

    def _load_monitoring_config(self) -> Dict[str, Any]:
        """Load monitoring configuration from settings."""
        return getattr(settings, 'GRAPHQL_SECURITY_MONITORING', {
            'enable_real_time_monitoring': True,
            'enable_threat_detection': True,
            'enable_automated_response': True,
            'enable_email_alerts': True,
            'enable_webhook_alerts': False,
            'alert_thresholds': {
                'critical_events_per_minute': 5,
                'high_events_per_hour': 50,
                'blocked_requests_per_hour': 100,
                'threat_score_threshold': 0.8
            },
            'email_alert_recipients': [],
            'webhook_alert_url': '',
            'automated_response_actions': {
                'rate_limit_violations': ['increase_rate_limit_strictness'],
                'csrf_violations': ['temporary_ip_block'],
                'origin_violations': ['origin_blacklist_update'],
                'critical_threats': ['emergency_lockdown']
            },
            'metrics_retention_days': 30,
            'threat_pattern_detection': {
                'min_events_for_pattern': 5,
                'pattern_detection_window_hours': 24,
                'correlation_threshold': 0.7
            }
        })

    def _setup_alert_handlers(self) -> Dict[str, Callable]:
        """Setup alert handlers for different alert types."""
        return {
            'email': self._send_email_alert,
            'webhook': self._send_webhook_alert,
            'log': self._log_alert,
            'cache': self._cache_alert
        }

    def _setup_threat_detectors(self) -> Dict[str, Callable]:
        """Setup threat detection functions."""
        return {
            'brute_force': self._detect_brute_force,
            'credential_stuffing': self._detect_credential_stuffing,
            'enumeration': self._detect_enumeration,
            'dos_attack': self._detect_dos_attack,
            'data_exfiltration': self._detect_data_exfiltration
        }

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid
        return str(uuid.uuid4())

    def _analyze_threat_indicators(self, event: SecurityEvent):
        """Analyze event for threat indicators."""
        threat_indicators = []

        # Check for repeated violations
        if self._is_repeated_violation(event):
            threat_indicators.append('repeated_violation')

        # Check for suspicious user agent
        if self._is_suspicious_user_agent(event.user_agent):
            threat_indicators.append('suspicious_user_agent')

        # Check for known malicious IPs
        if self._is_known_malicious_ip(event.client_ip):
            threat_indicators.append('known_malicious_ip')

        # Check for anomalous behavior
        if self._is_anomalous_behavior(event):
            threat_indicators.append('anomalous_behavior')

        event.threat_indicators = threat_indicators

    def _determine_response_actions(self, event: SecurityEvent):
        """Determine appropriate response actions for the event."""
        response_actions = []

        # Automatic response based on event type and severity
        if event.severity == 'critical':
            response_actions.append('immediate_alert')

        if event.event_type in self.config['automated_response_actions']:
            actions = self.config['automated_response_actions'][event.event_type]
            response_actions.extend(actions)

        # Response based on threat indicators
        if 'repeated_violation' in event.threat_indicators:
            response_actions.append('temporary_rate_limit')

        if 'known_malicious_ip' in event.threat_indicators:
            response_actions.append('ip_block')

        event.response_actions = response_actions

    def _store_security_event(self, event: SecurityEvent):
        """Store security event for analysis and reporting."""
        # Store in cache for immediate access
        cache_key = f"security_event:{event.event_id}"
        cache.set(cache_key, asdict(event), 3600)  # 1 hour

        # Store in time-series cache for metrics
        timestamp_key = int(event.timestamp.timestamp())
        metrics_key = f"security_events_by_minute:{timestamp_key // 60}"
        events_list = cache.get(metrics_key, [])
        events_list.append(event.event_id)
        cache.set(metrics_key, events_list, 86400)  # 24 hours

        # TODO: Store in persistent database for long-term analysis

    def _update_security_metrics(self, event: SecurityEvent):
        """Update real-time security metrics."""
        metrics_key = "graphql_security_metrics_realtime"
        current_metrics = cache.get(metrics_key, {
            'total_requests': 0,
            'blocked_requests': 0,
            'csrf_violations': 0,
            'rate_limit_violations': 0,
            'origin_violations': 0,
            'query_analysis_failures': 0
        })

        # Update counters based on event type
        current_metrics['total_requests'] += 1

        if event.severity in ['high', 'critical']:
            current_metrics['blocked_requests'] += 1

        if 'csrf' in event.event_type.lower():
            current_metrics['csrf_violations'] += 1
        elif 'rate_limit' in event.event_type.lower():
            current_metrics['rate_limit_violations'] += 1
        elif 'origin' in event.event_type.lower():
            current_metrics['origin_violations'] += 1
        elif 'query_analysis' in event.event_type.lower():
            current_metrics['query_analysis_failures'] += 1

        cache.set(metrics_key, current_metrics, 3600)

    def _check_threat_patterns(self, event: SecurityEvent):
        """Check for emerging threat patterns."""
        if not self.config['enable_threat_detection']:
            return

        for detector_name, detector_func in self.threat_detectors.items():
            try:
                pattern = detector_func(event)
                if pattern:
                    self._handle_threat_pattern(pattern)
            except (ConnectionError, ValueError) as e:
                security_monitor_logger.error(
                    f"Threat detector {detector_name} failed: {str(e)}"
                )

    def _trigger_alerts(self, event: SecurityEvent):
        """Trigger appropriate alerts based on event severity and configuration."""
        if not self._should_trigger_alert(event):
            return

        # Determine alert channels
        alert_channels = []

        if event.severity == 'critical':
            alert_channels.extend(['email', 'webhook', 'log'])
        elif event.severity == 'high':
            alert_channels.extend(['email', 'log'])
        else:
            alert_channels.append('log')

        # Send alerts
        for channel in alert_channels:
            handler = self.alert_handlers.get(channel)
            if handler:
                try:
                    handler(event)
                except (ValueError, TypeError) as e:
                    alert_logger.error(f"Alert handler {channel} failed: {str(e)}")

    def _should_trigger_alert(self, event: SecurityEvent) -> bool:
        """Determine if an alert should be triggered for the event."""
        # Check rate limiting for alerts
        alert_rate_key = f"alert_rate_limit:{event.event_type}:{event.client_ip}"
        recent_alerts = cache.get(alert_rate_key, 0)

        if recent_alerts >= 5:  # Max 5 alerts per 5 minutes per IP/event type
            return False

        cache.set(alert_rate_key, recent_alerts + 1, 300)

        # Always alert on critical events
        if event.severity == 'critical':
            return True

        # Alert on high severity with threat indicators
        if event.severity == 'high' and event.threat_indicators:
            return True

        return False

    def _send_email_alert(self, event: SecurityEvent):
        """Send email alert for security event."""
        if not self.config['enable_email_alerts']:
            return

        recipients = self.config['email_alert_recipients']
        if not recipients:
            return

        subject = f"GraphQL Security Alert: {event.event_type} ({event.severity.upper()})"
        message = self._format_alert_message(event)

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False
            )
            alert_logger.info(f"Email alert sent for event {event.event_id}")
        except (ConnectionError, ValueError) as e:
            alert_logger.error(f"Failed to send email alert: {str(e)}")

    def _send_webhook_alert(self, event: SecurityEvent):
        """Send webhook alert for security event."""
        if not self.config['enable_webhook_alerts']:
            return

        webhook_url = self.config['webhook_alert_url']
        if not webhook_url:
            return

        # TODO: Implement webhook alert sending
        alert_logger.info(f"Webhook alert triggered for event {event.event_id}")

    def _log_alert(self, event: SecurityEvent):
        """Log security alert."""
        alert_logger.warning(
            f"GraphQL Security Alert: {event.event_type}",
            extra={
                'event_id': event.event_id,
                'severity': event.severity,
                'correlation_id': event.correlation_id,
                'client_ip': event.client_ip,
                'user_id': event.user_id,
                'threat_indicators': event.threat_indicators,
                'event_details': event.event_details
            }
        )

    def _cache_alert(self, event: SecurityEvent):
        """Cache alert for dashboard display."""
        alerts_key = "graphql_security_alerts"
        alerts = cache.get(alerts_key, [])

        alert_data = {
            'event_id': event.event_id,
            'event_type': event.event_type,
            'severity': event.severity,
            'timestamp': event.timestamp.isoformat(),
            'message': self._format_alert_message(event, brief=True)
        }

        alerts.insert(0, alert_data)  # Add to beginning
        alerts = alerts[:100]  # Keep only last 100 alerts

        cache.set(alerts_key, alerts, 3600)

    def _format_alert_message(self, event: SecurityEvent, brief: bool = False) -> str:
        """Format alert message for notifications."""
        if brief:
            return f"{event.event_type} from {event.client_ip} - {event.severity} severity"

        message = f"""
GraphQL Security Alert

Event Type: {event.event_type}
Severity: {event.severity.upper()}
Timestamp: {event.timestamp}
Correlation ID: {event.correlation_id}

Client Information:
- IP Address: {event.client_ip}
- User ID: {event.user_id or 'Anonymous'}
- User Agent: {event.user_agent}
- Origin: {event.origin or 'Not specified'}

Threat Indicators: {', '.join(event.threat_indicators) or 'None'}
Response Actions: {', '.join(event.response_actions) or 'None'}

Event Details:
{json.dumps(event.event_details, indent=2)}
        """.strip()

        return message

    def _calculate_security_metrics(self, time_window_minutes: int) -> SecurityMetrics:
        """Calculate security metrics for the specified time window."""
        # TODO: Implement proper metrics calculation from stored events
        # For now, return cached real-time metrics
        metrics_key = "graphql_security_metrics_realtime"
        current_metrics = cache.get(metrics_key, {
            'total_requests': 0,
            'blocked_requests': 0,
            'csrf_violations': 0,
            'rate_limit_violations': 0,
            'origin_violations': 0,
            'query_analysis_failures': 0
        })

        # Calculate threat score
        total = current_metrics['total_requests']
        blocked = current_metrics['blocked_requests']
        threat_score = (blocked / total) if total > 0 else 0.0

        return SecurityMetrics(
            total_requests=current_metrics['total_requests'],
            blocked_requests=current_metrics['blocked_requests'],
            csrf_violations=current_metrics['csrf_violations'],
            rate_limit_violations=current_metrics['rate_limit_violations'],
            origin_violations=current_metrics['origin_violations'],
            query_analysis_failures=current_metrics['query_analysis_failures'],
            threat_score=threat_score,
            last_updated=timezone.now()
        )

    def _detect_threat_patterns(self, time_window_hours: int) -> List[ThreatPattern]:
        """Detect threat patterns in the specified time window."""
        # TODO: Implement proper threat pattern detection
        return []

    def _generate_security_recommendations(self, metrics: SecurityMetrics,
                                         threat_patterns: List[ThreatPattern]) -> List[str]:
        """Generate security recommendations based on metrics and patterns."""
        recommendations = []

        if metrics.threat_score > 0.5:
            recommendations.append("High threat activity detected - consider increasing security measures")

        if metrics.csrf_violations > 10:
            recommendations.append("Multiple CSRF violations - review client applications for proper token handling")

        if metrics.rate_limit_violations > 50:
            recommendations.append("High rate limit violations - consider adjusting rate limits or investigating abuse")

        if len(threat_patterns) > 0:
            recommendations.append(f"Detected {len(threat_patterns)} threat patterns - review and implement mitigations")

        return recommendations

    def _generate_report_summary(self, metrics: SecurityMetrics,
                                threat_patterns: List[ThreatPattern]) -> str:
        """Generate executive summary for security report."""
        total_requests = metrics.total_requests
        blocked_requests = metrics.blocked_requests
        block_rate = (blocked_requests / total_requests * 100) if total_requests > 0 else 0

        summary = f"""
Security Summary:
- Total GraphQL requests: {total_requests:,}
- Blocked requests: {blocked_requests:,} ({block_rate:.2f}%)
- Threat score: {metrics.threat_score:.2f}/1.0
- Active threat patterns: {len(threat_patterns)}

Key security events:
- CSRF violations: {metrics.csrf_violations}
- Rate limit violations: {metrics.rate_limit_violations}
- Origin violations: {metrics.origin_violations}
- Query analysis failures: {metrics.query_analysis_failures}
        """.strip()

        return summary

    def _log_security_event(self, event: SecurityEvent):
        """Log security event for audit trail."""
        security_monitor_logger.info(
            f"Security event recorded: {event.event_type}",
            extra={
                'event_id': event.event_id,
                'event_type': event.event_type,
                'severity': event.severity,
                'correlation_id': event.correlation_id,
                'user_id': event.user_id,
                'client_ip': event.client_ip,
                'threat_indicators': event.threat_indicators,
                'response_actions': event.response_actions
            }
        )

    # Placeholder threat detection methods
    def _is_repeated_violation(self, event: SecurityEvent) -> bool:
        """Check if this is a repeated violation from the same source."""
        # TODO: Implement repeated violation detection
        return False

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is suspicious."""
        suspicious_patterns = ['bot', 'crawler', 'scanner', 'curl', 'wget']
        return any(pattern in user_agent.lower() for pattern in suspicious_patterns)

    def _is_known_malicious_ip(self, ip: str) -> bool:
        """Check if IP is in known malicious IP list."""
        # TODO: Implement malicious IP checking
        return False

    def _is_anomalous_behavior(self, event: SecurityEvent) -> bool:
        """Check for anomalous behavior patterns."""
        # TODO: Implement anomaly detection
        return False

    def _detect_brute_force(self, event: SecurityEvent) -> Optional[ThreatPattern]:
        """Detect brute force attack patterns."""
        # TODO: Implement brute force detection
        return None

    def _detect_credential_stuffing(self, event: SecurityEvent) -> Optional[ThreatPattern]:
        """Detect credential stuffing attack patterns."""
        # TODO: Implement credential stuffing detection
        return None

    def _detect_enumeration(self, event: SecurityEvent) -> Optional[ThreatPattern]:
        """Detect enumeration attack patterns."""
        # TODO: Implement enumeration detection
        return None

    def _detect_dos_attack(self, event: SecurityEvent) -> Optional[ThreatPattern]:
        """Detect DoS attack patterns."""
        # TODO: Implement DoS detection
        return None

    def _detect_data_exfiltration(self, event: SecurityEvent) -> Optional[ThreatPattern]:
        """Detect data exfiltration patterns."""
        # TODO: Implement data exfiltration detection
        return None

    def _handle_threat_pattern(self, pattern: ThreatPattern):
        """Handle detected threat pattern."""
        security_monitor_logger.warning(
            f"Threat pattern detected: {pattern.pattern_name}",
            extra=asdict(pattern)
        )


# Global instance for use throughout the application
security_monitor = GraphQLSecurityMonitor()