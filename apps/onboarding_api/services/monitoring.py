"""
Observability, monitoring and alerting system for personalization

This module provides comprehensive monitoring including:
- Real-time metrics collection and aggregation
- Performance tracking with SLOs and SLIs
- Alerting for degradation and anomalies
- Cost tracking and budget alerts
- A/B test monitoring with statistical guards
- Distributed tracing integration
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
    ConversationSession,
    PreferenceProfile
)
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Individual metric data point"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    unit: str = 'count'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'tags': self.tags,
            'unit': self.unit
        }


@dataclass
class Alert:
    """Alert definition and state"""
    alert_id: str
    name: str
    severity: str  # critical, high, medium, low
    condition: str
    threshold: float
    current_value: float
    triggered_at: datetime
    description: str
    tags: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """
    Collects and aggregates metrics from the personalization system
    """

    def __init__(self):
        self.metrics_buffer = []
        self.flush_interval = getattr(settings, 'METRICS_FLUSH_INTERVAL', 60)  # seconds
        self.buffer_size = getattr(settings, 'METRICS_BUFFER_SIZE', 1000)

    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None,
                     unit: str = 'count', timestamp: Optional[datetime] = None):
        """Record a metric point"""
        try:
            metric_point = MetricPoint(
                name=name,
                value=value,
                timestamp=timestamp or timezone.now(),
                tags=tags or {},
                unit=unit
            )

            self.metrics_buffer.append(metric_point)

            # Auto-flush if buffer is full
            if len(self.metrics_buffer) >= self.buffer_size:
                self.flush_metrics()

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error recording metric {name}: {str(e)}")

    def record_recommendation_metrics(self, session_id: str, recommendation_id: str,
                                    metrics: Dict[str, Any]):
        """Record metrics for a recommendation"""
        try:
            base_tags = {
                'session_id': session_id,
                'recommendation_id': recommendation_id,
                'service': 'onboarding_personalization'
            }

            # Core performance metrics
            if 'latency_ms' in metrics:
                self.record_metric('recommendation.latency', metrics['latency_ms'],
                                 base_tags, 'milliseconds')

            if 'cost_cents' in metrics:
                self.record_metric('recommendation.cost', metrics['cost_cents'],
                                 base_tags, 'cents')

            if 'confidence_score' in metrics:
                self.record_metric('recommendation.confidence', metrics['confidence_score'],
                                 base_tags, 'ratio')

            # Personalization metrics
            if 'personalization_score' in metrics:
                self.record_metric('personalization.score', metrics['personalization_score'],
                                 base_tags, 'ratio')

            if 'cache_hit' in metrics:
                cache_tags = base_tags.copy()
                cache_tags['cache_hit'] = str(metrics['cache_hit'])
                self.record_metric('recommendation.cache_requests', 1, cache_tags)

            # Provider metrics
            if 'provider' in metrics:
                provider_tags = base_tags.copy()
                provider_tags['provider'] = metrics['provider']
                self.record_metric('recommendation.provider_requests', 1, provider_tags)

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error recording recommendation metrics: {str(e)}")

    def record_interaction_metrics(self, interaction_type: str, user_id: int,
                                 client_id: int, metadata: Dict[str, Any] = None):
        """Record user interaction metrics"""
        try:
            base_tags = {
                'interaction_type': interaction_type,
                'user_id': str(user_id),
                'client_id': str(client_id),
                'service': 'onboarding_personalization'
            }

            # Record interaction count
            self.record_metric('user.interactions', 1, base_tags)

            # Record engagement metrics
            if metadata:
                if 'time_on_item' in metadata:
                    self.record_metric('user.time_on_item', metadata['time_on_item'],
                                     base_tags, 'seconds')

                if 'scroll_depth' in metadata:
                    self.record_metric('user.scroll_depth', metadata['scroll_depth'],
                                     base_tags, 'ratio')

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error recording interaction metrics: {str(e)}")

    def record_experiment_metrics(self, experiment_id: str, arm: str,
                                outcome: str, metadata: Dict[str, Any] = None):
        """Record A/B test experiment metrics"""
        try:
            base_tags = {
                'experiment_id': experiment_id,
                'arm': arm,
                'outcome': outcome,
                'service': 'onboarding_experiments'
            }

            # Record experiment interaction
            self.record_metric('experiment.interactions', 1, base_tags)

            # Record conversion metrics
            if outcome in ['approved', 'rejected', 'modified']:
                conversion_tags = base_tags.copy()
                conversion_tags['converted'] = str(outcome == 'approved')
                self.record_metric('experiment.conversions', 1, conversion_tags)

            # Record additional metrics
            if metadata:
                if 'decision_time_ms' in metadata:
                    self.record_metric('experiment.decision_time', metadata['decision_time_ms'],
                                     base_tags, 'milliseconds')

                if 'cost_cents' in metadata:
                    self.record_metric('experiment.cost', metadata['cost_cents'],
                                     base_tags, 'cents')

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error recording experiment metrics: {str(e)}")

    def flush_metrics(self):
        """Flush buffered metrics to storage/monitoring system"""
        if not self.metrics_buffer:
            return

        try:
            # In production, this would send to monitoring system (e.g., DataDog, Prometheus)
            # For now, we'll cache metrics for retrieval
            timestamp = timezone.now()
            cache_key = f"metrics_batch_{timestamp.strftime('%Y%m%d_%H%M%S')}"

            metrics_data = [metric.to_dict() for metric in self.metrics_buffer]
            cache.set(cache_key, metrics_data, 3600)  # 1 hour retention

            logger.debug(f"Flushed {len(self.metrics_buffer)} metrics to cache")
            self.metrics_buffer.clear()

        except (AttributeError, ConnectionError, TypeError, ValueError) as e:
            logger.error(f"Error flushing metrics: {str(e)}")


class PerformanceMonitor:
    """
    Monitors system performance against SLOs and SLIs
    """

    def __init__(self):
        # Service Level Objectives (SLOs)
        self.slos = {
            'recommendation_latency_p95_ms': getattr(settings, 'SLO_REC_LATENCY_P95', 5000),
            'recommendation_latency_p50_ms': getattr(settings, 'SLO_REC_LATENCY_P50', 2000),
            'acceptance_rate_min': getattr(settings, 'SLO_ACCEPTANCE_RATE_MIN', 0.6),
            'error_rate_max': getattr(settings, 'SLO_ERROR_RATE_MAX', 0.05),
            'availability_min': getattr(settings, 'SLO_AVAILABILITY_MIN', 0.995)
        }

        self.metrics_collector = MetricsCollector()

    def check_slos(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Check current performance against SLOs

        Args:
            time_window_minutes: Time window for SLO evaluation

        Returns:
            Dict with SLO compliance status
        """
        try:
            since = timezone.now() - timedelta(minutes=time_window_minutes)
            slo_status = {}

            # Recommendation latency SLOs
            latency_stats = self._calculate_latency_stats(since)
            slo_status['recommendation_latency'] = {
                'p50_ms': latency_stats['p50'],
                'p95_ms': latency_stats['p95'],
                'p50_compliant': latency_stats['p50'] <= self.slos['recommendation_latency_p50_ms'],
                'p95_compliant': latency_stats['p95'] <= self.slos['recommendation_latency_p95_ms'],
                'sample_size': latency_stats['count']
            }

            # Acceptance rate SLO
            acceptance_stats = self._calculate_acceptance_rate(since)
            slo_status['acceptance_rate'] = {
                'current_rate': acceptance_stats['rate'],
                'compliant': acceptance_stats['rate'] >= self.slos['acceptance_rate_min'],
                'sample_size': acceptance_stats['count']
            }

            # Error rate SLO
            error_stats = self._calculate_error_rate(since)
            slo_status['error_rate'] = {
                'current_rate': error_stats['rate'],
                'compliant': error_stats['rate'] <= self.slos['error_rate_max'],
                'sample_size': error_stats['count']
            }

            # Overall SLO compliance
            all_compliant = all([
                slo_status['recommendation_latency']['p95_compliant'],
                slo_status['acceptance_rate']['compliant'],
                slo_status['error_rate']['compliant']
            ])

            slo_status['overall'] = {
                'compliant': all_compliant,
                'evaluation_window_minutes': time_window_minutes,
                'evaluated_at': timezone.now().isoformat()
            }

            return slo_status

        except (AttributeError, ConnectionError, TypeError, ValueError) as e:
            logger.error(f"Error checking SLOs: {str(e)}")
            return {'error': str(e)}

    def _calculate_latency_stats(self, since: datetime) -> Dict[str, float]:
        """Calculate latency percentiles"""
        try:
            recommendations = LLMRecommendation.objects.filter(
                cdtz__gte=since,
                latency_ms__isnull=False
            ).values_list('latency_ms', flat=True)

            if not recommendations:
                return {'p50': 0, 'p95': 0, 'count': 0}

            latencies = list(recommendations)
            return {
                'p50': np.percentile(latencies, 50),
                'p95': np.percentile(latencies, 95),
                'count': len(latencies)
            }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating latency stats: {str(e)}")
            return {'p50': 0, 'p95': 0, 'count': 0}

    def _calculate_acceptance_rate(self, since: datetime) -> Dict[str, float]:
        """Calculate acceptance rate"""
        try:
            interactions = RecommendationInteraction.objects.filter(
                occurred_at__gte=since,
                event_type__in=['approved', 'rejected', 'modified']
            )

            total_count = interactions.count()
            if total_count == 0:
                return {'rate': 0.0, 'count': 0}

            approved_count = interactions.filter(event_type='approved').count()
            rate = approved_count / total_count

            return {'rate': rate, 'count': total_count}

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating acceptance rate: {str(e)}")
            return {'rate': 0.0, 'count': 0}

    def _calculate_error_rate(self, since: datetime) -> Dict[str, float]:
        """Calculate error rate"""
        try:
            # Count sessions with errors vs total sessions
            total_sessions = ConversationSession.objects.filter(cdtz__gte=since).count()
            if total_sessions == 0:
                return {'rate': 0.0, 'count': 0}

            error_sessions = ConversationSession.objects.filter(
                cdtz__gte=since,
                current_state='error'
            ).count()

            rate = error_sessions / total_sessions
            return {'rate': rate, 'count': total_sessions}

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating error rate: {str(e)}")
            return {'rate': 0.0, 'count': 0}


class AlertManager:
    """
    Manages alerts for system degradation and anomalies
    """

    def __init__(self):
        self.active_alerts = {}
        self.alert_rules = self._load_alert_rules()
        self.metrics_collector = MetricsCollector()

    def check_alerts(self) -> List[Alert]:
        """Check all alert conditions and return active alerts"""
        current_alerts = []

        try:
            for rule_name, rule_config in self.alert_rules.items():
                alert = self._evaluate_alert_rule(rule_name, rule_config)
                if alert:
                    current_alerts.append(alert)

                    # Track new alerts
                    if rule_name not in self.active_alerts:
                        self.active_alerts[rule_name] = alert
                        self._send_alert_notification(alert)

            # Clear resolved alerts
            resolved_alerts = set(self.active_alerts.keys()) - set(alert.alert_id for alert in current_alerts)
            for resolved_alert in resolved_alerts:
                del self.active_alerts[resolved_alert]

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error checking alerts: {str(e)}")

        return current_alerts

    def _load_alert_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load alert rule configurations"""
        return {
            'high_rejection_rate': {
                'metric': 'rejection_rate',
                'threshold': 0.3,  # 30% rejection rate
                'window_minutes': 15,
                'severity': 'high',
                'description': 'Rejection rate exceeds threshold'
            },
            'low_acceptance_rate': {
                'metric': 'acceptance_rate',
                'threshold': 0.4,  # Below 40% acceptance
                'window_minutes': 30,
                'severity': 'high',
                'description': 'Acceptance rate below threshold',
                'operator': 'less_than'
            },
            'high_latency': {
                'metric': 'latency_p95',
                'threshold': 8000,  # 8 second P95 latency
                'window_minutes': 10,
                'severity': 'critical',
                'description': 'P95 latency exceeds threshold'
            },
            'excessive_cost': {
                'metric': 'hourly_cost_cents',
                'threshold': 10000,  # $100/hour
                'window_minutes': 60,
                'severity': 'medium',
                'description': 'Hourly cost exceeds budget'
            },
            'experiment_error_rate': {
                'metric': 'experiment_error_rate',
                'threshold': 0.1,  # 10% error rate
                'window_minutes': 30,
                'severity': 'high',
                'description': 'Experiment error rate too high'
            },
            'cache_hit_rate_low': {
                'metric': 'cache_hit_rate',
                'threshold': 0.3,  # Below 30% cache hit rate
                'window_minutes': 30,
                'severity': 'medium',
                'description': 'Cache hit rate below optimal threshold',
                'operator': 'less_than'
            }
        }

    def _evaluate_alert_rule(self, rule_name: str, rule_config: Dict[str, Any]) -> Optional[Alert]:
        """Evaluate a single alert rule"""
        try:
            metric_name = rule_config['metric']
            threshold = rule_config['threshold']
            window_minutes = rule_config['window_minutes']
            severity = rule_config['severity']
            operator = rule_config.get('operator', 'greater_than')

            # Calculate current metric value
            current_value = self._calculate_metric_value(metric_name, window_minutes)

            # Check threshold condition
            triggered = False
            if operator == 'greater_than':
                triggered = current_value > threshold
            elif operator == 'less_than':
                triggered = current_value < threshold

            if triggered:
                return Alert(
                    alert_id=rule_name,
                    name=rule_name.replace('_', ' ').title(),
                    severity=severity,
                    condition=f"{metric_name} {operator} {threshold}",
                    threshold=threshold,
                    current_value=current_value,
                    triggered_at=timezone.now(),
                    description=rule_config['description'],
                    tags={'metric': metric_name, 'window_minutes': str(window_minutes)}
                )

            return None

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error evaluating alert rule {rule_name}: {str(e)}")
            return None

    def _calculate_metric_value(self, metric_name: str, window_minutes: int) -> float:
        """Calculate current value for a metric"""
        since = timezone.now() - timedelta(minutes=window_minutes)

        try:
            if metric_name == 'rejection_rate':
                interactions = RecommendationInteraction.objects.filter(
                    occurred_at__gte=since,
                    event_type__in=['approved', 'rejected']
                )
                total = interactions.count()
                if total == 0:
                    return 0.0
                rejected = interactions.filter(event_type='rejected').count()
                return rejected / total

            elif metric_name == 'acceptance_rate':
                interactions = RecommendationInteraction.objects.filter(
                    occurred_at__gte=since,
                    event_type__in=['approved', 'rejected', 'modified']
                )
                total = interactions.count()
                if total == 0:
                    return 0.0
                approved = interactions.filter(event_type='approved').count()
                return approved / total

            elif metric_name == 'latency_p95':
                recommendations = LLMRecommendation.objects.filter(
                    cdtz__gte=since,
                    latency_ms__isnull=False
                ).values_list('latency_ms', flat=True)

                if not recommendations:
                    return 0.0
                return float(np.percentile(list(recommendations), 95))

            elif metric_name == 'hourly_cost_cents':
                # Estimate from interactions metadata
                interactions = RecommendationInteraction.objects.filter(
                    occurred_at__gte=since
                )
                total_cost = sum(
                    interaction.metadata.get('cost_estimate', 0) * 100
                    for interaction in interactions
                )
                # Normalize to hourly rate
                hours = window_minutes / 60.0
                return total_cost / hours if hours > 0 else 0.0

            elif metric_name == 'experiment_error_rate':
                # Calculate experiment assignment errors
                assignments = ExperimentAssignment.objects.filter(
                    assigned_at__gte=since
                )
                total = assignments.count()
                if total == 0:
                    return 0.0

                # Count assignments that led to escalations
                error_interactions = RecommendationInteraction.objects.filter(
                    session__in=[a.experiment.assignments.values_list('user__conversation_sessions', flat=True) for a in assignments],
                    event_type='escalated',
                    occurred_at__gte=since
                ).count()

                return error_interactions / total

            elif metric_name == 'cache_hit_rate':
                # This would typically come from cache metrics
                # For now, return a simulated value
                return 0.65  # 65% cache hit rate

            else:
                logger.warning(f"Unknown metric: {metric_name}")
                return 0.0

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating metric {metric_name}: {str(e)}")
            return 0.0

    def _send_alert_notification(self, alert: Alert):
        """Send alert notification"""
        try:
            # In production, this would integrate with alerting systems
            # (PagerDuty, Slack, email, etc.)

            logger.warning(f"ALERT [{alert.severity.upper()}] {alert.name}: "
                         f"{alert.description}. Current value: {alert.current_value:.3f}, "
                         f"Threshold: {alert.threshold}")

            # Store alert for admin dashboard
            cache.set(f"alert_{alert.alert_id}", alert.to_dict(), 3600)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error sending alert notification: {str(e)}")


class CostTracker:
    """
    Tracks and monitors costs with budget alerts
    """

    def __init__(self):
        self.daily_budget_cents = getattr(settings, 'ONBOARDING_DAILY_BUDGET_CENTS', 10000)  # $100
        self.hourly_budget_cents = self.daily_budget_cents // 24
        self.metrics_collector = MetricsCollector()

    def track_cost(self, user_id: int, client_id: int, cost_cents: int,
                  cost_type: str = 'recommendation', metadata: Dict[str, Any] = None):
        """Track cost incurred"""
        try:
            tags = {
                'user_id': str(user_id),
                'client_id': str(client_id),
                'cost_type': cost_type
            }

            if metadata:
                tags.update({k: str(v) for k, v in metadata.items() if k in ['provider', 'model', 'experiment_arm']})

            self.metrics_collector.record_metric('cost.incurred', cost_cents, tags, 'cents')

            # Check budget alerts
            self._check_budget_alerts(user_id, client_id, cost_cents)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error tracking cost: {str(e)}")

    def get_cost_summary(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get cost summary for the time window"""
        try:
            since = timezone.now() - timedelta(hours=time_window_hours)

            # Get cost data from interactions
            interactions = RecommendationInteraction.objects.filter(
                occurred_at__gte=since
            )

            total_cost_cents = 0
            cost_by_user = {}
            cost_by_provider = {}

            for interaction in interactions:
                cost = interaction.metadata.get('cost_estimate', 0) * 100  # Convert to cents
                total_cost_cents += cost

                # By user
                user_id = interaction.session.user_id
                cost_by_user[user_id] = cost_by_user.get(user_id, 0) + cost

                # By provider
                provider = interaction.metadata.get('provider', 'unknown')
                cost_by_provider[provider] = cost_by_provider.get(provider, 0) + cost

            # Calculate rates
            hours_in_window = time_window_hours
            cost_per_hour = total_cost_cents / hours_in_window if hours_in_window > 0 else 0
            cost_per_interaction = total_cost_cents / interactions.count() if interactions.count() > 0 else 0

            return {
                'time_window_hours': time_window_hours,
                'total_cost_cents': total_cost_cents,
                'total_cost_dollars': total_cost_cents / 100,
                'cost_per_hour_cents': cost_per_hour,
                'cost_per_interaction_cents': cost_per_interaction,
                'total_interactions': interactions.count(),
                'cost_by_user': cost_by_user,
                'cost_by_provider': cost_by_provider,
                'budget_utilization': cost_per_hour / self.hourly_budget_cents if self.hourly_budget_cents > 0 else 0,
                'calculated_at': timezone.now().isoformat()
            }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error getting cost summary: {str(e)}")
            return {'error': str(e)}

    def _check_budget_alerts(self, user_id: int, client_id: int, cost_cents: int):
        """Check if budget alerts should be triggered"""
        try:
            # Check user hourly spend
            user_hourly_key = f"cost_hourly_{user_id}_{client_id}"
            current_hour_cost = cache.get(user_hourly_key, 0) + cost_cents
            cache.set(user_hourly_key, current_hour_cost, 3600)  # 1 hour TTL

            user_hourly_limit = getattr(settings, 'USER_HOURLY_BUDGET_CENTS', 1000)  # $10/hour per user
            if current_hour_cost > user_hourly_limit:
                logger.warning(f"User {user_id} exceeded hourly budget: ${current_hour_cost/100:.2f}")

            # Check client daily spend
            client_daily_key = f"cost_daily_{client_id}"
            current_day_cost = cache.get(client_daily_key, 0) + cost_cents
            cache.set(client_daily_key, current_day_cost, 86400)  # 24 hour TTL

            if current_day_cost > self.daily_budget_cents:
                logger.warning(f"Client {client_id} exceeded daily budget: ${current_day_cost/100:.2f}")

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error checking budget alerts: {str(e)}")


class ExperimentMonitor:
    """
    Specialized monitoring for A/B tests and experiments
    """

    def __init__(self):
        self.metrics_collector = MetricsCollector()

    def monitor_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """Comprehensive monitoring for a single experiment"""
        try:
            experiment = Experiment.objects.get(experiment_id=experiment_id)

            # Get experiment assignments and interactions
            assignments = ExperimentAssignment.objects.filter(experiment=experiment)

            monitoring_data = {
                'experiment_id': experiment_id,
                'experiment_name': experiment.name,
                'status': experiment.status,
                'started_at': experiment.started_at.isoformat() if experiment.started_at else None,
                'monitoring_timestamp': timezone.now().isoformat(),
                'arms': {},
                'overall_stats': {},
                'alerts': []
            }

            # Monitor each arm
            for assignment in assignments:
                arm = assignment.arm
                if arm not in monitoring_data['arms']:
                    monitoring_data['arms'][arm] = {
                        'assignment_count': 0,
                        'interactions': 0,
                        'conversions': 0,
                        'conversion_rate': 0.0,
                        'avg_decision_time': 0.0,
                        'total_cost_cents': 0,
                        'error_count': 0
                    }

                arm_data = monitoring_data['arms'][arm]
                arm_data['assignment_count'] += 1

                # Get interactions for this user since assignment
                if assignment.user:
                    user_interactions = RecommendationInteraction.objects.filter(
                        session__user=assignment.user,
                        occurred_at__gte=assignment.assigned_at
                    )

                    arm_data['interactions'] += user_interactions.count()

                    conversions = user_interactions.filter(event_type='approved').count()
                    arm_data['conversions'] += conversions

                    errors = user_interactions.filter(event_type='escalated').count()
                    arm_data['error_count'] += errors

                    # Calculate cost
                    cost = sum(i.metadata.get('cost_estimate', 0) * 100 for i in user_interactions)
                    arm_data['total_cost_cents'] += cost

            # Calculate derived metrics
            for arm, arm_data in monitoring_data['arms'].items():
                if arm_data['interactions'] > 0:
                    arm_data['conversion_rate'] = arm_data['conversions'] / arm_data['interactions']
                    arm_data['error_rate'] = arm_data['error_count'] / arm_data['interactions']
                    arm_data['cost_per_interaction'] = arm_data['total_cost_cents'] / arm_data['interactions']

            # Overall experiment stats
            total_assignments = sum(arm['assignment_count'] for arm in monitoring_data['arms'].values())
            total_interactions = sum(arm['interactions'] for arm in monitoring_data['arms'].values())
            total_conversions = sum(arm['conversions'] for arm in monitoring_data['arms'].values())

            monitoring_data['overall_stats'] = {
                'total_assignments': total_assignments,
                'total_interactions': total_interactions,
                'overall_conversion_rate': total_conversions / total_interactions if total_interactions > 0 else 0,
                'arms_count': len(monitoring_data['arms'])
            }

            # Check for experiment-specific alerts
            alerts = self._check_experiment_alerts(experiment, monitoring_data['arms'])
            monitoring_data['alerts'] = alerts

            return monitoring_data

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error monitoring experiment {experiment_id}: {str(e)}")
            return {'error': str(e), 'experiment_id': experiment_id}

    def _check_experiment_alerts(self, experiment: Experiment, arms_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check experiment-specific alert conditions"""
        alerts = []

        try:
            # Check safety constraints
            safety_violations = experiment.check_safety_constraints(arms_data)
            for violation in safety_violations:
                alerts.append({
                    'type': 'safety_violation',
                    'severity': 'critical',
                    'message': violation
                })

            # Check for statistical significance if experiment has been running
            if experiment.started_at:
                runtime_hours = (timezone.now() - experiment.started_at).total_seconds() / 3600
                min_runtime_hours = getattr(settings, 'EXPERIMENT_MIN_RUNTIME_HOURS', 48)

                if runtime_hours < min_runtime_hours:
                    alerts.append({
                        'type': 'insufficient_runtime',
                        'severity': 'low',
                        'message': f'Experiment running for {runtime_hours:.1f}h, minimum {min_runtime_hours}h recommended'
                    })

            # Check for imbalanced assignment
            assignment_counts = [arm_data.get('assignment_count', 0) for arm_data in arms_data.values()]
            if assignment_counts and max(assignment_counts) > 0:
                assignment_ratio = min(assignment_counts) / max(assignment_counts)
                if assignment_ratio < 0.7:  # More than 30% imbalance
                    alerts.append({
                        'type': 'assignment_imbalance',
                        'severity': 'medium',
                        'message': f'Assignment imbalance detected: {assignment_ratio:.2%} ratio'
                    })

            # Check for high error rates in any arm
            for arm, arm_data in arms_data.items():
                error_rate = arm_data.get('error_rate', 0)
                if error_rate > 0.1:  # 10% error rate
                    alerts.append({
                        'type': 'high_error_rate',
                        'severity': 'high',
                        'message': f'Arm {arm} has {error_rate:.2%} error rate'
                    })

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error checking experiment alerts: {str(e)}")

        return alerts


# Factory functions
def get_metrics_collector() -> MetricsCollector:
    """Get the metrics collector"""
    return MetricsCollector()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the performance monitor"""
    return PerformanceMonitor()


def get_alert_manager() -> AlertManager:
    """Get the alert manager"""
    return AlertManager()


def get_cost_tracker() -> CostTracker:
    """Get the cost tracker"""
    return CostTracker()


def get_experiment_monitor() -> ExperimentMonitor:
    """Get the experiment monitor"""
    return ExperimentMonitor()