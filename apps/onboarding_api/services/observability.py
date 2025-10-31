"""
Cost tracking and observability services for Conversational Onboarding (Phase 2)
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from django.db.models import Sum, Count, Avg
from apps.onboarding.models import (
    LLMRecommendation, ConversationSession,
    AuthoritativeKnowledge, AuthoritativeKnowledgeChunk
    # KnowledgeIngestionJob  # TBD - Model not yet implemented
)
from apps.core.exceptions import LLMServiceException, IntegrationException

# Temporary stub for KnowledgeIngestionJob (until model is implemented)
class KnowledgeIngestionJob:
    """Stub for KnowledgeIngestionJob model (TBD)"""
    objects = None
    class StatusChoices:
        QUEUED = 'queued'
        READY = 'ready'
        FAILED = 'failed'

logger = logging.getLogger(__name__)
metrics_logger = logging.getLogger("metrics")


class CostTracker:
    """
    Service for tracking LLM provider costs and usage
    """

    def __init__(self):
        self.cost_models = self._load_cost_models()
        self.cache = cache

    def calculate_llm_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        operation_type: str = 'generation'
    ) -> Dict[str, Any]:
        """
        Calculate cost for LLM operation

        Args:
            provider: LLM provider (openai, anthropic, etc.)
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            operation_type: Type of operation (generation, validation, etc.)

        Returns:
            Cost calculation details
        """
        try:
            cost_model = self.cost_models.get(provider, {}).get(model)

            if not cost_model:
                logger.warning(f"No cost model found for {provider}/{model}")
                return {
                    'provider': provider,
                    'model': model,
                    'total_cost_cents': 0,
                    'input_cost_cents': 0,
                    'output_cost_cents': 0,
                    'estimated': True
                }

            # Calculate costs in cents
            input_cost = (input_tokens / 1000) * cost_model['input_cost_per_1k']
            output_cost = (output_tokens / 1000) * cost_model['output_cost_per_1k']
            total_cost = input_cost + output_cost

            return {
                'provider': provider,
                'model': model,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'input_cost_cents': int(input_cost * 100),
                'output_cost_cents': int(output_cost * 100),
                'total_cost_cents': int(total_cost * 100),
                'operation_type': operation_type,
                'calculated_at': datetime.now().isoformat(),
                'estimated': False
            }

        except (ConnectionError, LLMServiceException, TimeoutError) as e:
            logger.error(f"Error calculating LLM cost: {str(e)}")
            return {
                'provider': provider,
                'model': model,
                'total_cost_cents': 0,
                'error': str(e),
                'estimated': True
            }

    def track_recommendation_cost(self, recommendation_id: str, cost_data: Dict[str, Any]):
        """
        Track cost for a specific recommendation
        """
        try:
            recommendation = LLMRecommendation.objects.get(recommendation_id=recommendation_id)
            recommendation.provider_cost_cents = cost_data.get('total_cost_cents', 0)
            recommendation.save()

            # Also track in cache for quick aggregation
            self._cache_daily_cost(
                recommendation.session.client_id,
                cost_data.get('total_cost_cents', 0)
            )

            metrics_logger.info(
                f"Cost tracked for recommendation {recommendation_id}: {cost_data.get('total_cost_cents', 0)} cents"
            )

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error tracking recommendation cost: {str(e)}")

    def get_daily_cost_summary(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get daily cost summary for tenant or system-wide
        """
        try:
            today = datetime.now().date()

            # Query recommendations for today
            recommendations_query = LLMRecommendation.objects.filter(
                cdtz__date=today
            )

            if tenant_id:
                recommendations_query = recommendations_query.filter(
                    session__client_id=tenant_id
                )

            # Aggregate costs
            cost_stats = recommendations_query.aggregate(
                total_cost=Sum('provider_cost_cents'),
                total_recommendations=Count('recommendation_id'),
                avg_cost=Avg('provider_cost_cents')
            )

            return {
                'date': today.isoformat(),
                'tenant_id': tenant_id,
                'total_cost_cents': cost_stats['total_cost'] or 0,
                'total_recommendations': cost_stats['total_recommendations'] or 0,
                'average_cost_cents': int(cost_stats['avg_cost'] or 0),
                'generated_at': datetime.now().isoformat()
            }

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error getting daily cost summary: {str(e)}")
            return {
                'date': today.isoformat(),
                'total_cost_cents': 0,
                'error': str(e)
            }

    def get_cost_breakdown(
        self,
        start_date: datetime,
        end_date: datetime,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed cost breakdown for date range
        """
        try:
            recommendations_query = LLMRecommendation.objects.filter(
                cdtz__gte=start_date,
                cdtz__lte=end_date
            )

            if tenant_id:
                recommendations_query = recommendations_query.filter(
                    session__client_id=tenant_id
                )

            # Group by various dimensions
            breakdown = {
                'total_cost_cents': 0,
                'by_day': {},
                'by_session_type': {},
                'by_status': {},
                'total_recommendations': 0
            }

            for rec in recommendations_query:
                cost = rec.provider_cost_cents or 0
                day_key = rec.cdtz.date().isoformat()
                session_type = rec.session.conversation_type
                status = rec.status

                breakdown['total_cost_cents'] += cost
                breakdown['total_recommendations'] += 1

                # By day
                if day_key not in breakdown['by_day']:
                    breakdown['by_day'][day_key] = {'cost': 0, 'count': 0}
                breakdown['by_day'][day_key]['cost'] += cost
                breakdown['by_day'][day_key]['count'] += 1

                # By session type
                if session_type not in breakdown['by_session_type']:
                    breakdown['by_session_type'][session_type] = {'cost': 0, 'count': 0}
                breakdown['by_session_type'][session_type]['cost'] += cost
                breakdown['by_session_type'][session_type]['count'] += 1

                # By status
                if status not in breakdown['by_status']:
                    breakdown['by_status'][status] = {'cost': 0, 'count': 0}
                breakdown['by_status'][status]['cost'] += cost
                breakdown['by_status'][status]['count'] += 1

            return breakdown

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError) as e:
            logger.error(f"Error getting cost breakdown: {str(e)}")
            return {'error': str(e)}

    def _load_cost_models(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Load LLM provider cost models"""
        # Default cost models (in USD per 1K tokens)
        default_models = {
            'openai': {
                'gpt-4': {
                    'input_cost_per_1k': 0.03,
                    'output_cost_per_1k': 0.06
                },
                'gpt-3.5-turbo': {
                    'input_cost_per_1k': 0.0015,
                    'output_cost_per_1k': 0.002
                }
            },
            'anthropic': {
                'claude-3-opus': {
                    'input_cost_per_1k': 0.015,
                    'output_cost_per_1k': 0.075
                },
                'claude-3-sonnet': {
                    'input_cost_per_1k': 0.003,
                    'output_cost_per_1k': 0.015
                }
            },
            'dummy': {
                'dummy-model': {
                    'input_cost_per_1k': 0.0,
                    'output_cost_per_1k': 0.0
                }
            }
        }

        # Load custom cost models from settings
        custom_models = getattr(settings, 'LLM_COST_MODELS', {})

        # Merge custom models with defaults
        for provider, models in custom_models.items():
            if provider in default_models:
                default_models[provider].update(models)
            else:
                default_models[provider] = models

        return default_models

    def _cache_daily_cost(self, tenant_id: str, cost_cents: int):
        """Cache daily cost for quick aggregation"""
        try:
            cache_key = f"daily_cost:{tenant_id}:{datetime.now().strftime('%Y-%m-%d')}"
            current_cost = self.cache.get(cache_key, 0)
            self.cache.set(cache_key, current_cost + cost_cents, 86400)  # 24 hours
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.warning(f"Error caching daily cost: {str(e)}")


class MetricsCollector:
    """
    Service for collecting and aggregating metrics
    """

    def __init__(self):
        self.cache = cache

    def record_conversation_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Record a conversation-related metric

        Args:
            metric_name: Name of the metric
            value: Metric value
            tags: Optional tags for filtering/grouping
            timestamp: Optional timestamp (defaults to now)
        """
        try:
            metric_data = {
                'name': metric_name,
                'value': value,
                'tags': tags or {},
                'timestamp': (timestamp or datetime.now()).isoformat()
            }

            # Log structured metric
            metrics_logger.info(
                f"METRIC {metric_name}={value}",
                extra={
                    'metric_name': metric_name,
                    'metric_value': value,
                    'metric_tags': tags or {},
                    'metric_timestamp': metric_data['timestamp']
                }
            )

            # Store in cache for aggregation
            self._cache_metric_for_aggregation(metric_name, value, tags)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error recording metric {metric_name}: {str(e)}")

    def record_latency_metric(
        self,
        operation: str,
        latency_ms: int,
        success: bool = True,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record latency metric for an operation"""
        metric_tags = (tags or {}).copy()
        metric_tags.update({
            'operation': operation,
            'success': str(success).lower()
        })

        self.record_conversation_metric(
            'onboarding_operation_latency_ms',
            latency_ms,
            metric_tags
        )

    def record_recommendation_metric(self, recommendation: LLMRecommendation):
        """Record metrics for a completed recommendation"""
        try:
            tags = {
                'conversation_type': recommendation.session.conversation_type,
                'status': recommendation.status,
                'user_decision': recommendation.user_decision,
                'language': recommendation.session.language
            }

            # Record completion metric
            self.record_conversation_metric('onboarding_recommendation_completed', 1, tags)

            # Record confidence score
            if recommendation.confidence_score is not None:
                self.record_conversation_metric(
                    'onboarding_confidence_score',
                    recommendation.confidence_score,
                    tags
                )

            # Record latency if available
            if recommendation.latency_ms is not None:
                self.record_latency_metric(
                    'full_recommendation',
                    recommendation.latency_ms,
                    True,
                    tags
                )

            # Record cost if available
            if recommendation.provider_cost_cents is not None:
                self.record_conversation_metric(
                    'onboarding_cost_cents',
                    recommendation.provider_cost_cents,
                    tags
                )

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error recording recommendation metrics: {str(e)}")

    def get_metrics_summary(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get aggregated metrics summary"""
        try:
            cutoff = datetime.now() - timedelta(hours=hours_back)

            # Query recent recommendations
            recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

            summary = {
                'time_window': f"{hours_back} hours",
                'total_recommendations': recent_recs.count(),
                'by_status': {},
                'by_conversation_type': {},
                'average_confidence': 0,
                'average_latency_ms': 0,
                'total_cost_cents': 0,
                'generated_at': datetime.now().isoformat()
            }

            if recent_recs.exists():
                # Group by status
                for rec in recent_recs:
                    status = rec.status
                    conv_type = rec.session.conversation_type

                    summary['by_status'][status] = summary['by_status'].get(status, 0) + 1
                    summary['by_conversation_type'][conv_type] = summary['by_conversation_type'].get(conv_type, 0) + 1

                # Calculate averages
                stats = recent_recs.aggregate(
                    avg_confidence=Avg('confidence_score'),
                    avg_latency=Avg('latency_ms'),
                    total_cost=Sum('provider_cost_cents')
                )

                summary['average_confidence'] = round(stats['avg_confidence'] or 0, 3)
                summary['average_latency_ms'] = int(stats['avg_latency'] or 0)
                summary['total_cost_cents'] = stats['total_cost'] or 0

            return summary

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error getting metrics summary: {str(e)}")
            return {'error': str(e)}

    def _cache_metric_for_aggregation(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Cache metric data for quick aggregation"""
        try:
            # Create cache keys for different time windows
            now = datetime.now()
            hour_key = f"metrics:{metric_name}:hour:{now.strftime('%Y-%m-%d-%H')}"
            day_key = f"metrics:{metric_name}:day:{now.strftime('%Y-%m-%d')}"

            # Increment counters and track values
            for cache_key, timeout in [(hour_key, 3600), (day_key, 86400)]:
                current_data = self.cache.get(cache_key, {'count': 0, 'sum': 0, 'values': []})

                current_data['count'] += 1
                current_data['sum'] += value
                current_data['values'].append(value)

                # Keep only recent values to prevent memory bloat
                if len(current_data['values']) > 1000:
                    current_data['values'] = current_data['values'][-1000:]

                self.cache.set(cache_key, current_data, timeout)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.warning(f"Error caching metric for aggregation: {str(e)}")


class AlertManager:
    """
    Service for monitoring and alerting on metrics
    """

    def __init__(self):
        self.cache = cache
        self.alert_thresholds = self._load_alert_thresholds()

    def check_alerts(self) -> List[Dict[str, Any]]:
        """
        Check all configured alerts and return any triggered alerts
        """
        triggered_alerts = []

        try:
            # Check cost alerts
            cost_alerts = self._check_cost_alerts()
            triggered_alerts.extend(cost_alerts)

            # Check latency alerts
            latency_alerts = self._check_latency_alerts()
            triggered_alerts.extend(latency_alerts)

            # Check error rate alerts
            error_alerts = self._check_error_rate_alerts()
            triggered_alerts.extend(error_alerts)

            # Log alerts
            for alert in triggered_alerts:
                logger.warning(f"ALERT TRIGGERED: {alert}")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error checking alerts: {str(e)}")

        return triggered_alerts

    def _check_cost_alerts(self) -> List[Dict[str, Any]]:
        """Check for cost-related alerts"""
        alerts = []

        try:
            cost_tracker = CostTracker()
            daily_summary = cost_tracker.get_daily_cost_summary()

            daily_cost = daily_summary.get('total_cost_cents', 0)
            threshold = self.alert_thresholds.get('daily_cost_cents', 10000)  # $100 default

            if daily_cost > threshold:
                alerts.append({
                    'type': 'cost_alert',
                    'severity': 'warning',
                    'message': f'Daily cost exceeded threshold: ${daily_cost/100:.2f} > ${threshold/100:.2f}',
                    'current_value': daily_cost,
                    'threshold': threshold,
                    'timestamp': datetime.now().isoformat()
                })

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error checking cost alerts: {str(e)}")

        return alerts

    def _check_latency_alerts(self) -> List[Dict[str, Any]]:
        """Check for latency-related alerts"""
        alerts = []

        try:
            cutoff = datetime.now() - timedelta(hours=1)
            recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

            if recent_recs.exists():
                avg_latency = recent_recs.aggregate(Avg('latency_ms'))['latency_ms__avg']
                threshold = self.alert_thresholds.get('avg_latency_ms', 30000)  # 30 seconds

                if avg_latency and avg_latency > threshold:
                    alerts.append({
                        'type': 'latency_alert',
                        'severity': 'warning',
                        'message': f'Average latency exceeded threshold: {avg_latency:.0f}ms > {threshold}ms',
                        'current_value': avg_latency,
                        'threshold': threshold,
                        'timestamp': datetime.now().isoformat()
                    })

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error checking latency alerts: {str(e)}")

        return alerts

    def _check_error_rate_alerts(self) -> List[Dict[str, Any]]:
        """Check for error rate alerts"""
        alerts = []

        try:
            cutoff = datetime.now() - timedelta(hours=1)
            recent_recs = LLMRecommendation.objects.filter(cdtz__gte=cutoff)

            if recent_recs.exists():
                total_count = recent_recs.count()
                error_count = recent_recs.filter(status=LLMRecommendation.StatusChoices.FAILED).count()
                error_rate = (error_count / total_count) * 100

                threshold = self.alert_thresholds.get('error_rate_percent', 10.0)

                if error_rate > threshold:
                    alerts.append({
                        'type': 'error_rate_alert',
                        'severity': 'warning',
                        'message': f'Error rate exceeded threshold: {error_rate:.1f}% > {threshold}%',
                        'current_value': error_rate,
                        'threshold': threshold,
                        'error_count': error_count,
                        'total_count': total_count,
                        'timestamp': datetime.now().isoformat()
                    })

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error checking error rate alerts: {str(e)}")

        return alerts

    def _load_alert_thresholds(self) -> Dict[str, float]:
        """Load alert thresholds from settings"""
        default_thresholds = {
            'daily_cost_cents': 10000,  # $100
            'avg_latency_ms': 30000,    # 30 seconds
            'error_rate_percent': 10.0,  # 10%
        }

        custom_thresholds = getattr(settings, 'ONBOARDING_ALERT_THRESHOLDS', {})
        default_thresholds.update(custom_thresholds)

        return default_thresholds


class KnowledgeBaseMetrics:
    """
    Production-grade metrics collection for knowledge base operations
    Implements Prometheus-compatible metrics as specified in the plan
    """

    def __init__(self):
        self.cache = cache
        self.metrics_logger = logging.getLogger("metrics.knowledge_base")

    def record_ingestion_duration(self, job_id: str, duration_seconds: float, success: bool = True):
        """
        Record kb_ingest_duration_seconds metric
        """
        try:
            tags = {
                'job_id': job_id,
                'success': str(success).lower()
            }

            # Log structured metric for Prometheus scraping
            self.metrics_logger.info(
                f"kb_ingest_duration_seconds {duration_seconds}",
                extra={
                    'metric_name': 'kb_ingest_duration_seconds',
                    'metric_value': duration_seconds,
                    'metric_type': 'histogram',
                    'labels': tags,
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Cache for aggregation
            self._cache_duration_metric('ingestion', duration_seconds, success)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error recording ingestion duration: {str(e)}")

    def record_chunks_total(self, document_id: str, chunk_count: int):
        """
        Record kb_chunks_total metric
        """
        try:
            tags = {
                'document_id': document_id
            }

            self.metrics_logger.info(
                f"kb_chunks_total {chunk_count}",
                extra={
                    'metric_name': 'kb_chunks_total',
                    'metric_value': chunk_count,
                    'metric_type': 'counter',
                    'labels': tags,
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Update total chunks counter
            self._increment_counter_metric('chunks_total', chunk_count)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, ValueError) as e:
            logger.error(f"Error recording chunks total: {str(e)}")

    def record_embeddings_total(self, document_id: str, embedding_count: int, backend_type: str = 'postgres_array'):
        """
        Record kb_embeddings_total metric
        """
        try:
            tags = {
                'document_id': document_id,
                'backend_type': backend_type
            }

            self.metrics_logger.info(
                f"kb_embeddings_total {embedding_count}",
                extra={
                    'metric_name': 'kb_embeddings_total',
                    'metric_value': embedding_count,
                    'metric_type': 'counter',
                    'labels': tags,
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Update embeddings counter by backend
            self._increment_counter_metric(f'embeddings_total_{backend_type}', embedding_count)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error recording embeddings total: {str(e)}")

    def record_stale_docs_count(self):
        """
        Record kb_stale_docs metric (gauge showing current count)
        """
        try:
            # Calculate stale documents
            stale_threshold = datetime.now() - timedelta(days=90)
            stale_count = AuthoritativeKnowledge.objects.filter(
                last_verified__lt=stale_threshold,
                is_current=True
            ).count()

            self.metrics_logger.info(
                f"kb_stale_docs {stale_count}",
                extra={
                    'metric_name': 'kb_stale_docs',
                    'metric_value': stale_count,
                    'metric_type': 'gauge',
                    'labels': {'threshold_days': '90'},
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Cache current stale count
            self.cache.set('kb_stale_docs_current', stale_count, 3600)  # 1 hour

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error recording stale docs count: {str(e)}")

    def record_search_latency(self, query: str, latency_seconds: float, result_count: int, backend_type: str = 'postgres_array'):
        """
        Record kb_search_latency_seconds and kb_search_results_total metrics
        """
        try:
            search_tags = {
                'backend_type': backend_type,
                'result_count_bucket': self._get_result_count_bucket(result_count)
            }

            # Record search latency
            self.metrics_logger.info(
                f"kb_search_latency_seconds {latency_seconds}",
                extra={
                    'metric_name': 'kb_search_latency_seconds',
                    'metric_value': latency_seconds,
                    'metric_type': 'histogram',
                    'labels': search_tags,
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Record search results count
            self.metrics_logger.info(
                f"kb_search_results_total {result_count}",
                extra={
                    'metric_name': 'kb_search_results_total',
                    'metric_value': result_count,
                    'metric_type': 'histogram',
                    'labels': search_tags,
                    'timestamp': datetime.now().isoformat()
                }
            )

            # Cache search metrics for aggregation
            self._cache_search_metrics(latency_seconds, result_count, backend_type)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error recording search metrics: {str(e)}")

    def get_knowledge_base_health(self) -> Dict[str, Any]:
        """
        Get comprehensive knowledge base health metrics
        """
        try:
            # Current counts
            total_docs = AuthoritativeKnowledge.objects.filter(is_current=True).count()
            total_chunks = AuthoritativeKnowledgeChunk.objects.filter(is_current=True).count()
            docs_with_vectors = AuthoritativeKnowledge.objects.filter(
                content_vector__isnull=False,
                is_current=True
            ).count()
            chunks_with_vectors = AuthoritativeKnowledgeChunk.objects.filter(
                content_vector__isnull=False,
                is_current=True
            ).count()

            # Stale documents
            stale_threshold = datetime.now() - timedelta(days=90)
            stale_docs = AuthoritativeKnowledge.objects.filter(
                last_verified__lt=stale_threshold,
                is_current=True
            ).count()

            # Recent ingestion activity
            recent_jobs = KnowledgeIngestionJob.objects.filter(
                cdtz__gte=datetime.now() - timedelta(days=7)
            )
            successful_jobs = recent_jobs.filter(status=KnowledgeIngestionJob.StatusChoices.READY).count()
            failed_jobs = recent_jobs.filter(status=KnowledgeIngestionJob.StatusChoices.FAILED).count()

            # Authority level breakdown
            authority_breakdown = {}
            for level in ['low', 'medium', 'high', 'official']:
                count = AuthoritativeKnowledge.objects.filter(
                    authority_level=level,
                    is_current=True
                ).count()
                authority_breakdown[level] = count

            health_metrics = {
                'kb_documents_total': total_docs,
                'kb_chunks_total': total_chunks,
                'kb_embeddings_total': docs_with_vectors + chunks_with_vectors,
                'kb_stale_docs': stale_docs,
                'kb_vector_coverage_percent': (chunks_with_vectors / total_chunks * 100) if total_chunks > 0 else 0,
                'authority_level_breakdown': authority_breakdown,
                'recent_activity': {
                    'jobs_last_7_days': recent_jobs.count(),
                    'successful_jobs': successful_jobs,
                    'failed_jobs': failed_jobs,
                    'success_rate_percent': (successful_jobs / recent_jobs.count() * 100) if recent_jobs.count() > 0 else 0
                },
                'health_score': self._calculate_health_score(total_docs, stale_docs, chunks_with_vectors, total_chunks),
                'generated_at': datetime.now().isoformat()
            }

            # Log health metrics
            for metric_name, value in health_metrics.items():
                if isinstance(value, (int, float)):
                    self.metrics_logger.info(
                        f"{metric_name} {value}",
                        extra={
                            'metric_name': metric_name,
                            'metric_value': value,
                            'metric_type': 'gauge'
                        }
                    )

            return health_metrics

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error getting knowledge base health: {str(e)}")
            return {'error': str(e)}

    def get_ingestion_performance_metrics(self, days_back: int = 7) -> Dict[str, Any]:
        """
        Get detailed ingestion performance metrics
        """
        try:
            cutoff = datetime.now() - timedelta(days=days_back)
            jobs = KnowledgeIngestionJob.objects.filter(cdtz__gte=cutoff)

            # Calculate performance statistics
            completed_jobs = jobs.filter(status=KnowledgeIngestionJob.StatusChoices.READY)

            performance_metrics = {
                'total_jobs': jobs.count(),
                'completed_jobs': completed_jobs.count(),
                'failed_jobs': jobs.filter(status=KnowledgeIngestionJob.StatusChoices.FAILED).count(),
                'average_processing_time_ms': 0,
                'average_chunks_per_document': 0,
                'average_embeddings_per_document': 0,
                'processing_stage_breakdown': self._get_stage_breakdown(completed_jobs),
                'time_period_days': days_back,
                'generated_at': datetime.now().isoformat()
            }

            if completed_jobs.exists():
                # Calculate averages
                stats = completed_jobs.aggregate(
                    avg_duration=Avg('processing_duration_ms'),
                    avg_chunks=Avg('chunks_created'),
                    avg_embeddings=Avg('embeddings_generated')
                )

                performance_metrics.update({
                    'average_processing_time_ms': int(stats['avg_duration'] or 0),
                    'average_chunks_per_document': round(stats['avg_chunks'] or 0, 1),
                    'average_embeddings_per_document': round(stats['avg_embeddings'] or 0, 1)
                })

            return performance_metrics

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error getting ingestion performance metrics: {str(e)}")
            return {'error': str(e)}

    def record_budget_usage(self, tenant_id: str, resource_type: str, amount: int, unit: str = 'tokens'):
        """
        Record budget usage and check limits
        """
        try:
            # Get current usage
            cache_key = f"budget:{tenant_id}:{resource_type}:{unit}:{datetime.now().strftime('%Y-%m-%d')}"
            current_usage = self.cache.get(cache_key, 0)
            new_usage = current_usage + amount

            # Get budget limit
            budget_limits = getattr(settings, 'KB_DAILY_BUDGET_LIMITS', {})
            daily_limit = budget_limits.get(f'{resource_type}_{unit}', 100000)  # Default 100k tokens

            # Update cache
            self.cache.set(cache_key, new_usage, 86400)  # 24 hours

            # Log budget metric
            self.metrics_logger.info(
                f"kb_budget_usage_{unit} {new_usage}",
                extra={
                    'metric_name': f'kb_budget_usage_{unit}',
                    'metric_value': new_usage,
                    'metric_type': 'gauge',
                    'labels': {
                        'tenant_id': tenant_id,
                        'resource_type': resource_type,
                        'limit': daily_limit
                    }
                }
            )

            # Check for budget overflow
            if new_usage > daily_limit:
                self._trigger_budget_alert(tenant_id, resource_type, new_usage, daily_limit, unit)

            return {
                'current_usage': new_usage,
                'daily_limit': daily_limit,
                'usage_percent': (new_usage / daily_limit * 100) if daily_limit > 0 else 0,
                'remaining': max(0, daily_limit - new_usage),
                'overflow': new_usage > daily_limit
            }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error recording budget usage: {str(e)}")
            return {'error': str(e)}

    def _get_result_count_bucket(self, count: int) -> str:
        """Get result count bucket for metrics grouping"""
        if count == 0:
            return 'zero'
        elif count <= 5:
            return 'low'
        elif count <= 20:
            return 'medium'
        else:
            return 'high'

    def _cache_duration_metric(self, operation: str, duration: float, success: bool):
        """Cache duration metric for aggregation"""
        try:
            cache_key = f"duration_metrics:{operation}:{datetime.now().strftime('%Y-%m-%d-%H')}"
            current_data = self.cache.get(cache_key, {'total': 0, 'count': 0, 'successes': 0})

            current_data['total'] += duration
            current_data['count'] += 1
            if success:
                current_data['successes'] += 1

            self.cache.set(cache_key, current_data, 3600)  # 1 hour

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Error caching duration metric: {str(e)}")

    def _cache_search_metrics(self, latency: float, result_count: int, backend_type: str):
        """Cache search-specific metrics"""
        try:
            hour_key = f"search_metrics:{datetime.now().strftime('%Y-%m-%d-%H')}"
            current_data = self.cache.get(hour_key, {
                'search_count': 0,
                'total_latency': 0,
                'total_results': 0,
                'by_backend': {}
            })

            current_data['search_count'] += 1
            current_data['total_latency'] += latency
            current_data['total_results'] += result_count

            # Track by backend
            if backend_type not in current_data['by_backend']:
                current_data['by_backend'][backend_type] = {'count': 0, 'latency': 0, 'results': 0}

            current_data['by_backend'][backend_type]['count'] += 1
            current_data['by_backend'][backend_type]['latency'] += latency
            current_data['by_backend'][backend_type]['results'] += result_count

            self.cache.set(hour_key, current_data, 3600)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Error caching search metrics: {str(e)}")

    def _increment_counter_metric(self, metric_name: str, amount: int = 1):
        """Increment a counter metric"""
        try:
            cache_key = f"counter:{metric_name}:{datetime.now().strftime('%Y-%m-%d')}"
            current_value = self.cache.get(cache_key, 0)
            self.cache.set(cache_key, current_value + amount, 86400)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Error incrementing counter metric: {str(e)}")

    def _calculate_health_score(self, total_docs: int, stale_docs: int, vectors: int, total_chunks: int) -> float:
        """Calculate overall knowledge base health score (0-1)"""
        if total_docs == 0:
            return 0.0

        # Factors for health score
        stale_penalty = (stale_docs / total_docs) * 0.3 if total_docs > 0 else 0
        vector_coverage = (vectors / total_chunks) if total_chunks > 0 else 0
        size_factor = min(1.0, total_docs / 100) * 0.2  # Reward having sufficient content

        health_score = (1.0 - stale_penalty) * 0.5 + vector_coverage * 0.3 + size_factor

        return max(0.0, min(1.0, health_score))

    def _get_stage_breakdown(self, jobs) -> Dict[str, Any]:
        """Get breakdown of processing time by stage"""
        stage_breakdown = {
            'fetch_avg_ms': 0,
            'parse_avg_ms': 0,
            'chunk_avg_ms': 0,
            'embed_avg_ms': 0
        }

        try:
            total_jobs = 0
            stage_totals = {'fetch': 0, 'parse': 0, 'chunk': 0, 'embed': 0}

            for job in jobs:
                if job.timings:
                    total_jobs += 1
                    for stage in ['fetch_ms', 'parse_ms', 'chunk_ms', 'embed_ms']:
                        if stage in job.timings:
                            stage_key = stage.replace('_ms', '')
                            stage_totals[stage_key] += job.timings[stage]

            # Calculate averages
            if total_jobs > 0:
                for stage, total_time in stage_totals.items():
                    stage_breakdown[f'{stage}_avg_ms'] = int(total_time / total_jobs)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.warning(f"Error calculating stage breakdown: {str(e)}")

        return stage_breakdown

    def _trigger_budget_alert(self, tenant_id: str, resource_type: str, current_usage: int, limit: int, unit: str):
        """Trigger budget overflow alert"""
        try:
            alert_data = {
                'alert_type': 'budget_overflow',
                'tenant_id': tenant_id,
                'resource_type': resource_type,
                'current_usage': current_usage,
                'daily_limit': limit,
                'unit': unit,
                'overflow_amount': current_usage - limit,
                'overflow_percent': ((current_usage - limit) / limit * 100) if limit > 0 else 0,
                'triggered_at': datetime.now().isoformat()
            }

            # Log alert
            logger.warning(f"BUDGET OVERFLOW: {tenant_id} exceeded {resource_type} limit", extra=alert_data)

            # Store alert for admin dashboard
            alert_cache_key = f"budget_alert:{tenant_id}:{resource_type}:{datetime.now().strftime('%Y-%m-%d-%H')}"
            self.cache.set(alert_cache_key, alert_data, 3600)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error triggering budget alert: {str(e)}")

    def export_metrics_for_prometheus(self) -> str:
        """
        Export metrics in Prometheus format for scraping
        """
        try:
            metrics_lines = []

            # Get current knowledge base health
            health = self.get_knowledge_base_health()

            # Export each metric in Prometheus format
            metrics_map = [
                ('kb_documents_total', health.get('kb_documents_total', 0), 'gauge'),
                ('kb_chunks_total', health.get('kb_chunks_total', 0), 'gauge'),
                ('kb_embeddings_total', health.get('kb_embeddings_total', 0), 'gauge'),
                ('kb_stale_docs', health.get('kb_stale_docs', 0), 'gauge'),
                ('kb_health_score', health.get('health_score', 0), 'gauge'),
                ('kb_vector_coverage_percent', health.get('kb_vector_coverage_percent', 0), 'gauge')
            ]

            for metric_name, value, metric_type in metrics_map:
                metrics_lines.append(f'# HELP {metric_name} Knowledge base {metric_name.replace("kb_", "")}')
                metrics_lines.append(f'# TYPE {metric_name} {metric_type}')
                metrics_lines.append(f'{metric_name} {value}')

            # Add search performance metrics from cache
            search_data = self.cache.get(f"search_metrics:{datetime.now().strftime('%Y-%m-%d-%H')}", {})
            if search_data.get('search_count', 0) > 0:
                avg_latency = search_data['total_latency'] / search_data['search_count']
                avg_results = search_data['total_results'] / search_data['search_count']

                metrics_lines.extend([
                    '# HELP kb_search_latency_seconds_avg Average search latency',
                    '# TYPE kb_search_latency_seconds_avg gauge',
                    f'kb_search_latency_seconds_avg {avg_latency:.3f}',
                    '# HELP kb_search_results_avg Average search results returned',
                    '# TYPE kb_search_results_avg gauge',
                    f'kb_search_results_avg {avg_results:.1f}'
                ])

            return '\n'.join(metrics_lines) + '\n'

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error exporting Prometheus metrics: {str(e)}")
            return f'# Error exporting metrics: {str(e)}\n'


class StructuredLogger:
    """
    Structured logging service for knowledge base operations
    """

    def __init__(self):
        self.kb_logger = logging.getLogger("knowledge_base")

    def log_ingestion_event(
        self,
        event_type: str,
        ingestion_job_id: str,
        document_id: str = None,
        trace_id: str = None,
        **kwargs
    ):
        """
        Log structured ingestion events

        Args:
            event_type: Type of event (started, completed, failed, etc.)
            ingestion_job_id: Job ID for correlation
            document_id: Optional document ID
            trace_id: Optional trace ID for distributed tracing
            **kwargs: Additional event data
        """
        try:
            log_data = {
                'event_type': event_type,
                'ingestion_job_id': ingestion_job_id,
                'timestamp': datetime.now().isoformat()
            }

            if document_id:
                log_data['document_id'] = document_id
            if trace_id:
                log_data['trace_id'] = trace_id

            # Add additional event data
            log_data.update(kwargs)

            # Log with structured format
            self.kb_logger.info(
                f"INGESTION {event_type.upper()}: {ingestion_job_id}",
                extra=log_data
            )

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error logging ingestion event: {str(e)}")

    def log_search_event(
        self,
        query: str,
        result_count: int,
        latency_ms: int,
        user_id: str = None,
        backend_type: str = 'postgres_array',
        **kwargs
    ):
        """Log structured search events"""
        try:
            log_data = {
                'event_type': 'search',
                'query_hash': hashlib.md5(query.encode()).hexdigest()[:8],  # Don't log actual query
                'result_count': result_count,
                'latency_ms': latency_ms,
                'backend_type': backend_type,
                'timestamp': datetime.now().isoformat()
            }

            if user_id:
                log_data['user_id'] = user_id

            log_data.update(kwargs)

            self.kb_logger.info(
                f"SEARCH COMPLETED: {result_count} results in {latency_ms}ms",
                extra=log_data
            )

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error logging search event: {str(e)}")

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        user_id: str = None,
        resource_id: str = None,
        **kwargs
    ):
        """Log security-related events"""
        try:
            log_data = {
                'event_type': 'security',
                'security_event_type': event_type,
                'severity': severity,
                'description': description,
                'timestamp': datetime.now().isoformat()
            }

            if user_id:
                log_data['user_id'] = user_id
            if resource_id:
                log_data['resource_id'] = resource_id

            log_data.update(kwargs)

            # Use appropriate log level based on severity
            if severity == 'high':
                self.kb_logger.error(f"SECURITY {event_type.upper()}: {description}", extra=log_data)
            elif severity == 'medium':
                self.kb_logger.warning(f"SECURITY {event_type.upper()}: {description}", extra=log_data)
            else:
                self.kb_logger.info(f"SECURITY {event_type.upper()}: {description}", extra=log_data)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error logging security event: {str(e)}")


# =============================================================================
# SERVICE FACTORY
# =============================================================================


def get_cost_tracker() -> CostTracker:
    """Factory function to get cost tracker"""
    return CostTracker()


def get_metrics_collector() -> MetricsCollector:
    """Factory function to get metrics collector"""
    return MetricsCollector()


def get_alert_manager() -> AlertManager:
    """Factory function to get alert manager"""
    return AlertManager()


def get_knowledge_base_metrics() -> KnowledgeBaseMetrics:
    """Factory function to get knowledge base metrics collector"""
    return KnowledgeBaseMetrics()


def get_structured_logger() -> StructuredLogger:
    """Factory function to get structured logger"""
    return StructuredLogger()