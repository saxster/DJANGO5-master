"""
Real-time SQL Injection Attempt Monitoring Service

This module provides real-time monitoring and alerting for SQL injection attempts,
with automatic threat detection, IP blocking, and incident response capabilities.
"""

import logging
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import hashlib

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail

logger = logging.getLogger('security.sql_monitor')


@dataclass
class ThreatIndicator:
    """Represents a threat indicator for SQL injection attempts."""
    indicator_id: str
    threat_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    pattern: str
    description: str
    first_seen: datetime
    last_seen: datetime
    frequency: int
    source_ips: Set[str]
    affected_tables: Set[str]
    user_agents: Set[str]


@dataclass
class SecurityIncident:
    """Represents a security incident."""
    incident_id: str
    incident_type: str
    severity: str
    timestamp: datetime
    source_ip: str
    user_id: Optional[int]
    attack_vector: str
    payload: str
    blocked: bool
    response_actions: List[str]
    threat_indicators: List[str]


@dataclass
class MonitoringRule:
    """Represents a monitoring rule for threat detection."""
    rule_id: str
    name: str
    description: str
    pattern: str
    severity: str
    action: str  # LOG, BLOCK, ALERT
    threshold: int
    time_window_minutes: int
    enabled: bool


class SQLInjectionMonitor:
    """Real-time SQL injection attempt monitoring and response system."""

    def __init__(self):
        self.threat_indicators: Dict[str, ThreatIndicator] = {}
        self.active_incidents: Dict[str, SecurityIncident] = {}
        self.monitoring_rules = self._load_monitoring_rules()
        self.blocked_ips: Set[str] = set()
        self.rate_limiters: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread = None

        # Load configuration
        self.config = {
            'max_incidents_per_ip_per_hour': 10,
            'auto_block_threshold': 5,
            'block_duration_minutes': 60,
            'alert_email': getattr(settings, 'SECURITY_ALERT_EMAIL', None),
            'monitoring_interval_seconds': 30,
        }

    def _load_monitoring_rules(self) -> List[MonitoringRule]:
        """Load monitoring rules for threat detection."""
        return [
            MonitoringRule(
                rule_id='sqli_001',
                name='Classic SQL Injection',
                description='Detects classic SQL injection patterns',
                pattern=r"'\s*(or|and)\s+'.*?'",
                severity='HIGH',
                action='BLOCK',
                threshold=1,
                time_window_minutes=5,
                enabled=True
            ),
            MonitoringRule(
                rule_id='sqli_002',
                name='Union-based Injection',
                description='Detects UNION-based SQL injection attempts',
                pattern=r'union\s+(all\s+)?select',
                severity='HIGH',
                action='BLOCK',
                threshold=1,
                time_window_minutes=5,
                enabled=True
            ),
            MonitoringRule(
                rule_id='sqli_003',
                name='Comment-based Injection',
                description='Detects comment-based SQL injection attempts',
                pattern=r'--\s*|/\*.*?\*/',
                severity='MEDIUM',
                action='ALERT',
                threshold=3,
                time_window_minutes=10,
                enabled=True
            ),
            MonitoringRule(
                rule_id='sqli_004',
                name='Stacked Queries',
                description='Detects stacked query injection attempts',
                pattern=r';\s*(drop|delete|insert|update|create|alter)\s+',
                severity='CRITICAL',
                action='BLOCK',
                threshold=1,
                time_window_minutes=1,
                enabled=True
            ),
            MonitoringRule(
                rule_id='sqli_005',
                name='Time-based Blind Injection',
                description='Detects time-based blind SQL injection',
                pattern=r'(waitfor\s+delay|benchmark\s*\(|sleep\s*\()',
                severity='HIGH',
                action='BLOCK',
                threshold=2,
                time_window_minutes=5,
                enabled=True
            ),
            MonitoringRule(
                rule_id='sqli_006',
                name='Error-based Injection',
                description='Detects error-based SQL injection attempts',
                pattern=r'(extractvalue|updatexml|floor\(rand)',
                severity='HIGH',
                action='ALERT',
                threshold=2,
                time_window_minutes=10,
                enabled=True
            ),
        ]

    def start_monitoring(self):
        """Start the real-time monitoring service."""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("SQL injection monitoring service started")

    def stop_monitoring(self):
        """Stop the monitoring service."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("SQL injection monitoring service stopped")

    def process_query_event(
        self,
        query: str,
        params: Optional[List[Any]],
        ip_address: str,
        user_id: Optional[int] = None,
        user_agent: str = '',
        request_path: str = ''
    ) -> Dict[str, Any]:
        """
        Process a database query event for threat detection.

        Args:
            query: SQL query string
            params: Query parameters
            ip_address: Source IP address
            user_id: User ID if authenticated
            user_agent: User agent string
            request_path: Request path

        Returns:
            Dict containing threat assessment and actions taken
        """
        assessment = {
            'threat_detected': False,
            'severity': 'LOW',
            'blocked': False,
            'actions_taken': [],
            'threat_indicators': []
        }

        # Check if IP is already blocked
        if self.is_ip_blocked(ip_address):
            assessment['blocked'] = True
            assessment['actions_taken'].append('IP_BLOCKED')
            logger.warning(f"Blocked query from banned IP: {ip_address}")
            return assessment

        # Apply monitoring rules
        triggered_rules = []
        for rule in self.monitoring_rules:
            if not rule.enabled:
                continue

            if self._rule_matches(rule, query, ip_address):
                triggered_rules.append(rule)

        if not triggered_rules:
            return assessment

        # Process triggered rules
        assessment['threat_detected'] = True
        max_severity = self._determine_max_severity(triggered_rules)
        assessment['severity'] = max_severity

        # Create or update threat indicators
        for rule in triggered_rules:
            indicator = self._create_or_update_threat_indicator(
                rule, query, ip_address, user_agent, request_path
            )
            assessment['threat_indicators'].append(indicator.indicator_id)

        # Determine actions
        actions = self._determine_actions(triggered_rules, ip_address, user_id)
        assessment['actions_taken'] = actions

        # Check if query should be blocked
        if 'BLOCK' in [rule.action for rule in triggered_rules]:
            assessment['blocked'] = True
            self._handle_blocking_action(ip_address, user_id, query, triggered_rules)

        # Create security incident
        if assessment['threat_detected']:
            incident = self._create_security_incident(
                ip_address, user_id, query, triggered_rules, assessment['blocked']
            )
            assessment['incident_id'] = incident.incident_id

        return assessment

    def _rule_matches(self, rule: MonitoringRule, query: str, ip_address: str) -> bool:
        """Check if a monitoring rule matches the query."""
        import re

        # Check pattern match
        if not re.search(rule.pattern, query, re.IGNORECASE):
            return False

        # Check frequency threshold
        rule_key = f"rule_trigger:{rule.rule_id}:{ip_address}"
        current_time = datetime.now()

        # Get recent triggers for this rule and IP
        triggers = cache.get(rule_key, [])

        # Filter triggers within time window
        cutoff_time = current_time - timedelta(minutes=rule.time_window_minutes)
        recent_triggers = [t for t in triggers if datetime.fromisoformat(t) > cutoff_time]

        # Add current trigger
        recent_triggers.append(current_time.isoformat())

        # Update cache
        cache.set(rule_key, recent_triggers, rule.time_window_minutes * 60)

        # Check if threshold is exceeded
        return len(recent_triggers) >= rule.threshold

    def _determine_max_severity(self, rules: List[MonitoringRule]) -> str:
        """Determine the maximum severity from triggered rules."""
        severities = [rule.severity for rule in rules]

        if 'CRITICAL' in severities:
            return 'CRITICAL'
        elif 'HIGH' in severities:
            return 'HIGH'
        elif 'MEDIUM' in severities:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _create_or_update_threat_indicator(
        self,
        rule: MonitoringRule,
        query: str,
        ip_address: str,
        user_agent: str,
        request_path: str
    ) -> ThreatIndicator:
        """Create or update a threat indicator."""
        indicator_id = hashlib.sha256(f"{rule.rule_id}:{rule.pattern}".encode()).hexdigest()[:16]

        with self._lock:
            if indicator_id in self.threat_indicators:
                indicator = self.threat_indicators[indicator_id]
                indicator.last_seen = datetime.now()
                indicator.frequency += 1
                indicator.source_ips.add(ip_address)
                if user_agent:
                    indicator.user_agents.add(user_agent)
            else:
                indicator = ThreatIndicator(
                    indicator_id=indicator_id,
                    threat_type='SQL_INJECTION',
                    severity=rule.severity,
                    pattern=rule.pattern,
                    description=rule.description,
                    first_seen=datetime.now(),
                    last_seen=datetime.now(),
                    frequency=1,
                    source_ips={ip_address},
                    affected_tables=set(),
                    user_agents={user_agent} if user_agent else set()
                )
                self.threat_indicators[indicator_id] = indicator

        # Cache the indicator
        cache_key = f"threat_indicator:{indicator_id}"
        cache.set(cache_key, asdict(indicator), 86400)  # 24 hours

        return indicator

    def _determine_actions(
        self,
        triggered_rules: List[MonitoringRule],
        ip_address: str,
        user_id: Optional[int]
    ) -> List[str]:
        """Determine what actions to take based on triggered rules."""
        actions = []

        # Check rule actions
        rule_actions = [rule.action for rule in triggered_rules]

        if 'BLOCK' in rule_actions:
            actions.append('BLOCK_REQUEST')

            # Check if IP should be auto-blocked
            if self._should_auto_block_ip(ip_address):
                self.block_ip(ip_address, duration_minutes=self.config['block_duration_minutes'])
                actions.append('BLOCK_IP')

        if 'ALERT' in rule_actions:
            actions.append('SEND_ALERT')
            self._send_security_alert(triggered_rules, ip_address, user_id)

        return actions

    def _should_auto_block_ip(self, ip_address: str) -> bool:
        """Determine if an IP should be automatically blocked."""
        # Check incident count for this IP in the last hour
        hour_key = f"ip_incidents:{ip_address}:{datetime.now().strftime('%Y%m%d%H')}"
        incident_count = cache.get(hour_key, 0)

        return incident_count >= self.config['auto_block_threshold']

    def _handle_blocking_action(
        self,
        ip_address: str,
        user_id: Optional[int],
        query: str,
        triggered_rules: List[MonitoringRule]
    ):
        """Handle blocking actions."""
        # Log the blocking action
        logger.warning(
            f"BLOCKED SQL injection attempt from {ip_address} "
            f"(user: {user_id}): {query[:100]}..."
        )

        # Increment incident count for IP
        hour_key = f"ip_incidents:{ip_address}:{datetime.now().strftime('%Y%m%d%H')}"
        current_count = cache.get(hour_key, 0)
        cache.set(hour_key, current_count + 1, 3600)  # 1 hour expiry

        # Update rate limiter
        with self._lock:
            self.rate_limiters[ip_address].append(datetime.now())

            # Keep only recent entries
            cutoff = datetime.now() - timedelta(minutes=60)
            while (self.rate_limiters[ip_address] and
                   self.rate_limiters[ip_address][0] < cutoff):
                self.rate_limiters[ip_address].popleft()

    def _create_security_incident(
        self,
        ip_address: str,
        user_id: Optional[int],
        query: str,
        triggered_rules: List[MonitoringRule],
        blocked: bool
    ) -> SecurityIncident:
        """Create a security incident record."""
        incident_id = f"INC_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.sha256(query.encode()).hexdigest()[:8]}"

        attack_vector = ', '.join([rule.name for rule in triggered_rules])
        response_actions = ['LOGGED']

        if blocked:
            response_actions.append('BLOCKED')

        threat_indicators = [
            self.threat_indicators.get(
                hashlib.sha256(f"{rule.rule_id}:{rule.pattern}".encode()).hexdigest()[:16],
                ThreatIndicator('', '', '', '', '', datetime.now(), datetime.now(), 0, set(), set(), set())
            ).indicator_id
            for rule in triggered_rules
        ]

        incident = SecurityIncident(
            incident_id=incident_id,
            incident_type='SQL_INJECTION_ATTEMPT',
            severity=self._determine_max_severity(triggered_rules),
            timestamp=datetime.now(),
            source_ip=ip_address,
            user_id=user_id,
            attack_vector=attack_vector,
            payload=query[:500],  # Truncate long queries
            blocked=blocked,
            response_actions=response_actions,
            threat_indicators=threat_indicators
        )

        # Store incident
        with self._lock:
            self.active_incidents[incident_id] = incident

        # Cache incident
        cache_key = f"security_incident:{incident_id}"
        cache.set(cache_key, asdict(incident), 86400 * 7)  # Keep for 7 days

        logger.error(f"Security incident created: {incident_id}")

        return incident

    def _send_security_alert(
        self,
        triggered_rules: List[MonitoringRule],
        ip_address: str,
        user_id: Optional[int]
    ):
        """Send security alert notifications."""
        if not self.config['alert_email']:
            return

        rule_names = [rule.name for rule in triggered_rules]
        severity = self._determine_max_severity(triggered_rules)

        subject = f"[SECURITY ALERT] SQL Injection Attempt Detected - {severity}"
        message = f"""
Security Alert: SQL Injection Attempt Detected

Severity: {severity}
Source IP: {ip_address}
User ID: {user_id}
Triggered Rules: {', '.join(rule_names)}
Timestamp: {datetime.now().isoformat()}

Please investigate this security incident immediately.
        """

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.config['alert_email']],
                fail_silently=False
            )
            logger.info(f"Security alert sent for IP {ip_address}")
        except (AttributeError, ConnectionError, TypeError, ValueError) as e:
            logger.error(f"Failed to send security alert: {e}")

    def block_ip(self, ip_address: str, duration_minutes: int = 60):
        """Block an IP address for a specified duration."""
        with self._lock:
            self.blocked_ips.add(ip_address)

        # Cache the block
        block_key = f"blocked_ip:{ip_address}"
        cache.set(block_key, True, duration_minutes * 60)

        logger.warning(f"IP {ip_address} blocked for {duration_minutes} minutes")

    def unblock_ip(self, ip_address: str):
        """Unblock an IP address."""
        with self._lock:
            self.blocked_ips.discard(ip_address)

        # Remove from cache
        block_key = f"blocked_ip:{ip_address}"
        cache.delete(block_key)

        logger.info(f"IP {ip_address} unblocked")

    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if an IP address is blocked."""
        # Check in-memory set
        if ip_address in self.blocked_ips:
            return True

        # Check cache
        block_key = f"blocked_ip:{ip_address}"
        return cache.get(block_key, False)

    def get_threat_dashboard_data(self) -> Dict[str, Any]:
        """Get data for the threat monitoring dashboard."""
        current_time = datetime.now()

        # Get recent incidents
        recent_incidents = []
        for incident in self.active_incidents.values():
            if (current_time - incident.timestamp).total_seconds() < 86400:  # Last 24 hours
                recent_incidents.append(asdict(incident))

        # Get threat indicators
        threat_indicators = [asdict(indicator) for indicator in self.threat_indicators.values()]

        # Get blocked IPs
        blocked_ips = list(self.blocked_ips)

        # Calculate statistics
        stats = {
            'total_incidents_24h': len(recent_incidents),
            'blocked_incidents_24h': len([i for i in recent_incidents if i['blocked']]),
            'unique_source_ips_24h': len(set([i['source_ip'] for i in recent_incidents])),
            'active_threat_indicators': len(threat_indicators),
            'blocked_ips': len(blocked_ips),
        }

        return {
            'timestamp': current_time.isoformat(),
            'statistics': stats,
            'recent_incidents': recent_incidents[-50:],  # Last 50 incidents
            'threat_indicators': threat_indicators,
            'blocked_ips': blocked_ips,
            'monitoring_rules': [asdict(rule) for rule in self.monitoring_rules]
        }

    def _monitoring_loop(self):
        """Main monitoring loop that runs in background thread."""
        while self._running:
            try:
                # Cleanup expired data
                self._cleanup_expired_data()

                # Update threat intelligence
                self._update_threat_intelligence()

                # Check for pattern escalations
                self._check_pattern_escalations()

                # SAFE: time.sleep() acceptable in background monitoring loop
                # - Runs in separate monitoring thread (not request path)
                # - Part of security monitoring infrastructure
                time.sleep(self.config['monitoring_interval_seconds'])

            except (ConnectionError, ValueError) as e:
                logger.error(f"Error in monitoring loop: {e}")
                # SAFE: time.sleep() acceptable in background monitoring loop
                time.sleep(5)  # Short delay before retrying

    def _cleanup_expired_data(self):
        """Clean up expired threat indicators and incidents."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(days=7)

        with self._lock:
            # Clean up old incidents
            expired_incidents = [
                incident_id for incident_id, incident in self.active_incidents.items()
                if incident.timestamp < cutoff_time
            ]
            for incident_id in expired_incidents:
                del self.active_incidents[incident_id]

            # Clean up old blocked IPs
            for ip in list(self.blocked_ips):
                if not self.is_ip_blocked(ip):  # Check cache
                    self.blocked_ips.discard(ip)

    def _update_threat_intelligence(self):
        """Update threat intelligence data."""
        # This could integrate with external threat intelligence feeds
        # For now, it's a placeholder for future enhancement
        pass

    def _check_pattern_escalations(self):
        """Check for patterns that indicate escalating attacks."""
        # Analyze recent incidents for patterns
        current_time = datetime.now()
        hour_ago = current_time - timedelta(hours=1)

        recent_incidents = [
            incident for incident in self.active_incidents.values()
            if incident.timestamp > hour_ago
        ]

        # Group by source IP
        incidents_by_ip = defaultdict(list)
        for incident in recent_incidents:
            incidents_by_ip[incident.source_ip].append(incident)

        # Check for escalating patterns
        for ip, incidents in incidents_by_ip.items():
            if len(incidents) > 5:  # More than 5 incidents from same IP in 1 hour
                logger.warning(f"Escalating attack pattern detected from IP {ip}: {len(incidents)} incidents")

                # Auto-block if not already blocked
                if not self.is_ip_blocked(ip):
                    self.block_ip(ip, duration_minutes=120)  # Block for 2 hours


# Global instance
sql_injection_monitor = SQLInjectionMonitor()