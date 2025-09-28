"""
Anomaly Detection Engine for Stream Testbench
Detects patterns in stream events and creates anomaly signatures
"""

import hashlib
import json
import logging
import yaml
from django.utils import timezone

from ..models import AnomalySignature, AnomalyOccurrence, RecurrenceTracker

logger = logging.getLogger('issue_tracker.anomaly')


class AnomalyDetector:
    """
    AI-powered anomaly detection engine with rule-based fallbacks
    """

    def __init__(self):
        self.rules = self._load_detection_rules()
        self.thresholds = self._load_thresholds()

    def _load_detection_rules(self) -> Dict[str, Any]:
        """Load anomaly detection rules from configuration"""
        try:
            rules_path = Path(__file__).parent.parent / 'rules' / 'anomalies.yaml'
            if rules_path.exists():
                with open(rules_path, 'r') as f:
                    return yaml.safe_load(f)
        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            logger.warning(f"Could not load rules file: {e}")

        # Default rules if file not found
        return {
            'rules': [
                {
                    'name': 'high_latency_websocket',
                    'condition': {
                        'latency_ms': {'gt': 100},
                        'endpoint': {'contains': 'websocket'}
                    },
                    'severity': 'warning',
                    'anomaly_type': 'latency_spike',
                    'fixes': [
                        {
                            'type': 'index',
                            'suggestion': 'Add database index on frequently queried fields',
                            'confidence': 0.75
                        }
                    ]
                },
                {
                    'name': 'schema_mismatch',
                    'condition': {
                        'outcome': {'eq': 'error'},
                        'error_message': {'contains': ['schema', 'validation', 'field']}
                    },
                    'severity': 'error',
                    'anomaly_type': 'schema_drift',
                    'fixes': [
                        {
                            'type': 'serializer',
                            'suggestion': 'Update serializer to handle schema changes',
                            'confidence': 0.90
                        }
                    ]
                },
                {
                    'name': 'connection_timeout',
                    'condition': {
                        'outcome': {'eq': 'timeout'},
                        'latency_ms': {'gt': 5000}
                    },
                    'severity': 'error',
                    'anomaly_type': 'connection_timeout',
                    'fixes': [
                        {
                            'type': 'connection_pool',
                            'suggestion': 'Increase connection pool size or timeout settings',
                            'confidence': 0.80
                        }
                    ]
                },
                {
                    'name': 'rate_limit_exceeded',
                    'condition': {
                        'http_status_code': {'eq': 429},
                        'outcome': {'eq': 'error'}
                    },
                    'severity': 'warning',
                    'anomaly_type': 'rate_limit',
                    'fixes': [
                        {
                            'type': 'rate_limit',
                            'suggestion': 'Implement exponential backoff retry strategy',
                            'confidence': 0.85
                        }
                    ]
                },
                {
                    'name': 'memory_pressure',
                    'condition': {
                        'error_message': {'contains': ['memory', 'oom', 'out of memory']},
                        'outcome': {'eq': 'error'}
                    },
                    'severity': 'critical',
                    'anomaly_type': 'resource_exhaustion',
                    'fixes': [
                        {
                            'type': 'infrastructure',
                            'suggestion': 'Scale up memory or optimize memory usage',
                            'confidence': 0.85
                        }
                    ]
                }
            ]
        }

    def _load_thresholds(self) -> Dict[str, float]:
        """Load detection thresholds from YAML configuration"""
        try:
            # First try to load from YAML rules
            if self.rules.get('thresholds'):
                yaml_thresholds = self.rules['thresholds']

                # Convert YAML structure to flat threshold dictionary
                thresholds = {}

                # Latency thresholds
                if 'latency' in yaml_thresholds:
                    latency = yaml_thresholds['latency']
                    thresholds.update({
                        'websocket_p95_threshold': latency.get('websocket_p95', 100),
                        'mqtt_p95_threshold': latency.get('mqtt_p95', 50),
                        'http_p95_threshold': latency.get('http_p95', 200),
                        'latency_p95_threshold': latency.get('websocket_p95', 100)  # Default fallback
                    })

                # Error rate thresholds
                if 'error_rate' in yaml_thresholds:
                    error_rate = yaml_thresholds['error_rate']
                    thresholds.update({
                        'error_rate_warning': error_rate.get('warning_threshold', 0.05),
                        'error_rate_critical': error_rate.get('critical_threshold', 0.15),
                        'error_rate_threshold': error_rate.get('warning_threshold', 0.05)  # Default fallback
                    })

                # Recurrence thresholds
                if 'recurrence' in yaml_thresholds:
                    recurrence = yaml_thresholds['recurrence']
                    thresholds.update({
                        'frequent_threshold': recurrence.get('frequent_threshold', 5),
                        'chronic_threshold': recurrence.get('chronic_threshold', 10),
                        'recurrence_threshold': recurrence.get('frequent_threshold', 3)  # Default fallback
                    })

                # Confidence thresholds
                if 'confidence' in yaml_thresholds:
                    confidence = yaml_thresholds['confidence']
                    thresholds.update({
                        'auto_apply_confidence': confidence.get('auto_apply', 0.95),
                        'suggest_confidence': confidence.get('suggest', 0.60),
                        'minimum_confidence': confidence.get('minimum', 0.30),
                        'anomaly_score_threshold': confidence.get('suggest', 0.7)  # Default fallback
                    })

                logger.info(f"Loaded {len(thresholds)} thresholds from YAML configuration")
                return thresholds

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError) as e:
            logger.warning(f"Failed to load thresholds from YAML: {e}")

        # Fallback to hardcoded defaults if YAML loading fails
        logger.info("Using fallback hardcoded thresholds")
        return {
            'latency_p95_threshold': 100.0,  # ms
            'error_rate_threshold': 0.05,    # 5%
            'anomaly_score_threshold': 0.7,  # 0.0-1.0
            'recurrence_threshold': 3,       # occurrences
            'websocket_p95_threshold': 100.0,
            'mqtt_p95_threshold': 50.0,
            'http_p95_threshold': 200.0,
            'error_rate_warning': 0.05,
            'error_rate_critical': 0.15,
            'frequent_threshold': 5,
            'chronic_threshold': 10,
            'auto_apply_confidence': 0.95,
            'suggest_confidence': 0.60,
            'minimum_confidence': 0.30
        }

    async def analyze_event(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze a stream event for anomalies

        Args:
            event_data: Event data including metrics, payload, etc.

        Returns:
            Anomaly analysis result if anomaly detected, None otherwise
        """
        try:
            matched_anomalies = []

            # Check against all rules and collect all matches
            for rule in self.rules.get('rules', []):
                if self._matches_rule(event_data, rule):
                    anomaly_info = await self._create_anomaly(event_data, rule)
                    if anomaly_info:
                        matched_anomalies.append({
                            'anomaly_info': anomaly_info,
                            'rule': rule
                        })

                        logger.info(
                            f"Anomaly detected: {rule['name']}",
                            extra={
                                'anomaly_type': rule['anomaly_type'],
                                'severity': rule['severity'],
                                'endpoint': event_data.get('endpoint')
                            }
                        )

            # Statistical anomaly detection (beyond rules)
            statistical_anomaly = self._detect_statistical_anomaly(event_data)
            if statistical_anomaly and not matched_anomalies:
                # Only create statistical anomaly if no rule-based anomalies found
                statistical_info = await self._create_statistical_anomaly(event_data, statistical_anomaly)
                if statistical_info:
                    matched_anomalies.append({
                        'anomaly_info': statistical_info,
                        'rule': statistical_anomaly
                    })

            # Return the most severe anomaly or aggregate information
            if matched_anomalies:
                # Sort by severity (critical > error > warning > info)
                severity_order = {'critical': 4, 'error': 3, 'warning': 2, 'info': 1}
                matched_anomalies.sort(
                    key=lambda x: severity_order.get(x['rule'].get('severity', 'info'), 0),
                    reverse=True
                )

                primary_anomaly = matched_anomalies[0]['anomaly_info']

                # Add metadata about additional anomalies if multiple were found
                if len(matched_anomalies) > 1:
                    primary_anomaly['additional_anomalies'] = [
                        {
                            'type': match['rule']['anomaly_type'],
                            'severity': match['rule'].get('severity', 'info'),
                            'occurrence_id': match['anomaly_info'].get('occurrence_id')
                        }
                        for match in matched_anomalies[1:]
                    ]
                    primary_anomaly['total_anomaly_count'] = len(matched_anomalies)

                return primary_anomaly

            return None

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TimeoutError, asyncio.CancelledError) as e:
            logger.error(f"Anomaly analysis failed: {e}", exc_info=True)
            return None

    def _matches_rule(self, event_data: Dict[str, Any], rule: Dict[str, Any]) -> bool:
        """Check if event data matches anomaly rule conditions"""
        try:
            conditions = rule.get('condition', {})

            for field, condition in conditions.items():
                event_value = event_data.get(field)

                if isinstance(condition, dict):
                    # Complex condition (gt, lt, eq, contains, etc.)
                    if 'gt' in condition and (not event_value or event_value <= condition['gt']):
                        return False
                    if 'lt' in condition and (not event_value or event_value >= condition['lt']):
                        return False
                    if 'eq' in condition and event_value != condition['eq']:
                        return False
                    if 'contains' in condition:
                        if isinstance(condition['contains'], list):
                            # Any of the values must be contained
                            if not any(term in str(event_value).lower()
                                     for term in condition['contains']):
                                return False
                        else:
                            # Single value must be contained
                            if condition['contains'].lower() not in str(event_value).lower():
                                return False
                else:
                    # Simple equality condition
                    if event_value != condition:
                        return False

            return True

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, PermissionError, TimeoutError, asyncio.CancelledError) as e:
            logger.error(f"Rule matching failed: {e}")
            return False

    async def _create_anomaly(self, event_data: Dict[str, Any],
                             rule: Dict[str, Any]) -> Dict[str, Any]:
        """Create anomaly signature and occurrence"""
        try:
            from asgiref.sync import sync_to_async

            # Generate signature hash
            signature_data = {
                'anomaly_type': rule['anomaly_type'],
                'endpoint_pattern': self._normalize_endpoint(event_data.get('endpoint', '')),
                'error_class': event_data.get('error_class', ''),
                'rule_name': rule['name']
            }
            signature_hash = self._generate_signature_hash(signature_data)

            # Get or create anomaly signature
            signature, created = await sync_to_async(
                AnomalySignature.objects.get_or_create
            )(
                signature_hash=signature_hash,
                defaults={
                    'anomaly_type': rule['anomaly_type'],
                    'severity': rule['severity'],
                    'pattern': rule.get('condition', {}),
                    'endpoint_pattern': signature_data['endpoint_pattern'],
                    'error_class': signature_data.get('error_class', ''),
                    'tags': rule.get('tags', [])
                }
            )

            if not created:
                # Update existing signature
                signature.update_occurrence()

            # Create occurrence with client version tracking
            occurrence = await sync_to_async(AnomalyOccurrence.objects.create)(
                signature=signature,
                test_run_id=event_data.get('test_run_id'),
                event_ref=event_data.get('event_id'),
                endpoint=event_data.get('endpoint', ''),
                error_message=event_data.get('error_message', ''),
                exception_class=event_data.get('exception_class', ''),
                stack_hash=event_data.get('stack_hash', ''),
                http_status_code=event_data.get('http_status_code'),
                latency_ms=event_data.get('latency_ms'),
                payload_sanitized=event_data.get('payload_sanitized'),
                correlation_id=event_data.get('correlation_id'),
                # Client version tracking for trend analysis
                client_app_version=event_data.get('client_app_version', ''),
                client_os_version=event_data.get('client_os_version', ''),
                client_device_model=event_data.get('client_device_model', '')
            )

            # Update recurrence tracking
            await self._update_recurrence_tracking(signature)

            # Generate fix suggestions if new signature
            if created:
                await self._generate_fix_suggestions(signature, rule)

            # Broadcast real-time anomaly alert
            await self._broadcast_anomaly_alert(occurrence, signature, rule, event_data)

            return {
                'signature_id': str(signature.id),
                'occurrence_id': str(occurrence.id),
                'anomaly_type': rule['anomaly_type'],
                'severity': rule['severity'],
                'is_new_signature': created
            }

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, asyncio.CancelledError) as e:
            logger.error(f"Anomaly creation failed: {e}", exc_info=True)
            return None

    def _normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint for pattern matching"""
        import re

        if not endpoint:
            return 'unknown'

        # Replace IDs with placeholders
        normalized = re.sub(r'/\d+/', '/{id}/', endpoint)
        normalized = re.sub(r'/[a-f0-9-]{36}/', '/{uuid}/', normalized)
        normalized = re.sub(r'/[a-f0-9]{8,}/', '/{hash}/', normalized)

        return normalized

    def _generate_signature_hash(self, signature_data: Dict[str, Any]) -> str:
        """Generate unique hash for anomaly signature"""
        # Sort keys for consistent hashing
        signature_json = json.dumps(signature_data, sort_keys=True)
        return hashlib.sha256(signature_json.encode()).hexdigest()

    def _detect_statistical_anomaly(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect statistical anomalies beyond rule-based detection"""
        try:
            endpoint = event_data.get('endpoint', '')
            latency = event_data.get('latency_ms', 0)

            # Protocol-specific latency thresholds
            latency_threshold = self.thresholds['latency_p95_threshold']  # Default
            if 'websocket' in endpoint.lower() or 'ws/' in endpoint.lower():
                latency_threshold = self.thresholds.get('websocket_p95_threshold', 100)
            elif 'mqtt' in endpoint.lower():
                latency_threshold = self.thresholds.get('mqtt_p95_threshold', 50)
            elif 'http' in endpoint.lower() or 'api/' in endpoint.lower():
                latency_threshold = self.thresholds.get('http_p95_threshold', 200)

            # Latency outlier detection (3x normal threshold)
            if latency > latency_threshold * 3:
                confidence = min(latency / (latency_threshold * 3), 1.0)
                severity = 'warning'
                if latency > latency_threshold * 5:  # Extreme outlier
                    severity = 'error'

                return {
                    'anomaly_type': 'latency_outlier',
                    'severity': severity,
                    'confidence': confidence,
                    'details': f'Latency {latency}ms exceeds 3x protocol threshold ({latency_threshold}ms)'
                }

            # High latency but not extreme (2x threshold)
            elif latency > latency_threshold * 2:
                return {
                    'anomaly_type': 'latency_spike',
                    'severity': 'info',
                    'confidence': 0.6,
                    'details': f'Latency {latency}ms exceeds 2x protocol threshold ({latency_threshold}ms)'
                }

            # Schema anomaly detection (simplified)
            schema_hash = event_data.get('payload_schema_hash')
            if schema_hash and self._is_schema_anomaly(schema_hash, event_data.get('endpoint')):
                return {
                    'anomaly_type': 'schema_anomaly',
                    'severity': 'info',
                    'confidence': 0.6,
                    'details': 'Unusual payload schema detected'
                }

            # Error rate anomaly (if we can determine it from context)
            outcome = event_data.get('outcome')
            if outcome in ['error', 'timeout']:
                error_threshold = self.thresholds.get('error_rate_warning', 0.05)
                return {
                    'anomaly_type': 'error_event',
                    'severity': 'warning' if outcome == 'error' else 'error',
                    'confidence': 0.8,
                    'details': f'Event resulted in {outcome} status'
                }

            return None

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            logger.error(f"Statistical anomaly detection failed: {e}")
            return None

    def _is_schema_anomaly(self, schema_hash: str, endpoint: str) -> bool:
        """Simple schema anomaly detection"""
        # This would typically involve more sophisticated analysis
        # For now, just a placeholder implementation
        return False

    async def _create_statistical_anomaly(self, event_data: Dict[str, Any],
                                        statistical_anomaly: Dict[str, Any]) -> Dict[str, Any]:
        """Create anomaly from statistical detection"""
        try:
            from asgiref.sync import sync_to_async

            # Create a rule-like structure for statistical anomaly
            synthetic_rule = {
                'name': f"statistical_{statistical_anomaly['anomaly_type']}",
                'anomaly_type': statistical_anomaly['anomaly_type'],
                'severity': statistical_anomaly['severity'],
                'condition': {
                    'statistical_detection': True,
                    'confidence': statistical_anomaly['confidence']
                },
                'tags': ['statistical', 'auto_detected']
            }

            # Use existing anomaly creation logic
            return await self._create_anomaly(event_data, synthetic_rule)

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            logger.error(f"Statistical anomaly creation failed: {e}", exc_info=True)
            return None

    async def _update_recurrence_tracking(self, signature: AnomalySignature):
        """Update recurrence tracking for signature"""
        try:
            from asgiref.sync import sync_to_async

            tracker, created = await sync_to_async(
                RecurrenceTracker.objects.get_or_create
            )(signature=signature)

            await sync_to_async(tracker.update_recurrence)()

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            logger.error(f"Recurrence tracking update failed: {e}")

    async def _generate_fix_suggestions(self, signature: AnomalySignature, rule: Dict[str, Any]):
        """Generate fix suggestions for new anomaly signature"""
        try:
            from ..services.fix_suggester import fix_suggester
            await fix_suggester.generate_suggestions(signature, rule)

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            logger.error(f"Fix suggestion generation failed: {e}")

    async def _broadcast_anomaly_alert(self, occurrence, signature: AnomalySignature,
                                      rule: Dict[str, Any], event_data: Dict[str, Any]):
        """Broadcast real-time anomaly alert to dashboards"""
        try:
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.warning("Channel layer not available for anomaly broadcasting")
                return

            # Prepare alert data
            alert_data = {
                'id': str(occurrence.id),
                'signature_id': str(signature.id),
                'type': rule['anomaly_type'],
                'severity': rule['severity'],
                'endpoint': event_data.get('endpoint', ''),
                'correlation_id': event_data.get('correlation_id'),
                'latency_ms': event_data.get('latency_ms'),
                'error_message': event_data.get('error_message', ''),
                'created_at': occurrence.created_at.isoformat(),
                'is_new_signature': signature.occurrence_count == 1,
                'recurrence_count': signature.occurrence_count,
                # Client version information for context
                'client_info': {
                    'app_version': event_data.get('client_app_version', ''),
                    'os_version': event_data.get('client_os_version', ''),
                    'device_model': event_data.get('client_device_model', '')
                }
            }

            # Determine alert type based on severity and recurrence
            alert_type = 'new_anomaly'
            if rule['severity'] == 'critical':
                alert_type = 'critical_anomaly'
            elif signature.occurrence_count > 5:  # Recurring issue
                alert_type = 'recurring_anomaly'
                alert_data['alert_reason'] = 'high_recurrence'

            # Send to anomaly alerts group
            await channel_layer.group_send(
                "streamlab_anomaly_alerts",
                {
                    "type": alert_type,
                    "data": alert_data
                }
            )

            # Also send to stream metrics group for dashboard updates
            await channel_layer.group_send(
                "streamlab_stream_metrics",
                {
                    "type": "anomaly_detected",
                    "data": alert_data
                }
            )

            # Send escalation alert for critical anomalies
            if rule['severity'] == 'critical' or signature.occurrence_count > 10:
                await self._send_escalation_alert(alert_data, rule)

            logger.info(
                f"Broadcasted anomaly alert: {alert_type}",
                extra={
                    'occurrence_id': str(occurrence.id),
                    'anomaly_type': rule['anomaly_type'],
                    'severity': rule['severity']
                }
            )

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            logger.error(f"Anomaly alert broadcasting failed: {e}", exc_info=True)

    async def _send_escalation_alert(self, alert_data: Dict[str, Any], rule: Dict[str, Any]):
        """Send escalation alert for critical anomalies"""
        try:
            # Check escalation rules from YAML
            escalation_config = self.rules.get('escalation', {})

            should_escalate = False
            escalation_reason = ""

            # Critical anomaly escalation
            if (alert_data['severity'] == 'critical' and
                escalation_config.get('critical_anomalies', {}).get('immediate_alert', False)):
                should_escalate = True
                escalation_reason = "critical_severity"

            # Recurring issue escalation
            elif (alert_data['recurrence_count'] > escalation_config.get('recurring_issues', {}).get('threshold', 10)):
                should_escalate = True
                escalation_reason = "high_recurrence"

            if should_escalate:
                escalation_data = {
                    **alert_data,
                    'escalation_reason': escalation_reason,
                    'escalated_at': timezone.now().isoformat(),
                    'requires_immediate_attention': True
                }

                # Send to escalation channels (could be integrated with Slack, email, etc.)
                channel_layer = get_channel_layer()
                await channel_layer.group_send(
                    "anomaly_escalation",
                    {
                        "type": "escalation_alert",
                        "data": escalation_data
                    }
                )

                logger.warning(
                    f"Anomaly escalated: {escalation_reason}",
                    extra={
                        'occurrence_id': alert_data['id'],
                        'severity': alert_data['severity'],
                        'recurrence_count': alert_data['recurrence_count']
                    }
                )

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            logger.error(f"Escalation alert failed: {e}", exc_info=True)

    def get_anomaly_stats(self) -> Dict[str, Any]:
        """Get anomaly detection statistics"""
        try:
            from datetime import timedelta

            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            last_7d = now - timedelta(days=7)

            stats = {
                'total_signatures': AnomalySignature.objects.count(),
                'active_signatures': AnomalySignature.objects.filter(status='active').count(),
                'critical_anomalies': AnomalySignature.objects.filter(severity='critical').count(),

                'occurrences_24h': AnomalyOccurrence.objects.filter(
                    created_at__gte=last_24h
                ).count(),
                'occurrences_7d': AnomalyOccurrence.objects.filter(
                    created_at__gte=last_7d
                ).count(),

                'unresolved_occurrences': AnomalyOccurrence.objects.filter(
                    status__in=['new', 'investigating']
                ).count(),

                'top_anomaly_types': list(
                    AnomalySignature.objects.values('anomaly_type')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:5]
                ),

                'recurring_issues': AnomalySignature.objects.filter(
                    occurrence_count__gt=3
                ).count()
            }

            return stats

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TimeoutError, TypeError, ValueError, asyncio.CancelledError, json.JSONDecodeError) as e:
            logger.error(f"Stats calculation failed: {e}")
            return {}


# Singleton instance
anomaly_detector = AnomalyDetector()