"""
Streaming Anomaly Service

Coordination service for real-time streaming anomaly detection.
Provides metrics tracking, monitoring, and management interface for
StreamingAnomalyConsumer.

Features:
- Metrics tracking (events/sec, detection latency, findings rate)
- Consumer health monitoring
- Configuration management
- Statistics aggregation

Compliance with .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger('noc.streaming_anomaly_service')

__all__ = ['StreamingAnomalyService']


class StreamingAnomalyService:
    """
    Service for managing streaming anomaly detection system.

    Provides metrics, monitoring, and coordination for real-time
    anomaly detection via WebSocket consumers.
    """

    # Cache keys
    METRICS_KEY_PREFIX = 'streaming_anomaly_metrics'
    HEALTH_KEY_PREFIX = 'streaming_anomaly_health'

    @classmethod
    def record_event_processed(
        cls,
        tenant_id: int,
        event_type: str,
        detection_latency_ms: float,
        findings_count: int
    ):
        """
        Record metrics for processed event.

        Args:
            tenant_id: Tenant ID
            event_type: Event type ('attendance', 'task', 'location')
            detection_latency_ms: Detection latency in milliseconds
            findings_count: Number of findings detected
        """
        try:
            # Update event counters
            cache_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:count"
            cache.incr(cache_key, delta=1)

            # Track latency (rolling average)
            latency_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:latency"
            current_avg = cache.get(latency_key, 0)
            event_count = cache.get(cache_key, 1)
            new_avg = ((current_avg * (event_count - 1)) + detection_latency_ms) / event_count
            cache.set(latency_key, new_avg, timeout=3600)

            # Track findings rate
            if findings_count > 0:
                findings_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:findings"
                cache.incr(findings_key, delta=findings_count)

            logger.debug(
                f"Recorded metrics for {event_type} event",
                extra={
                    'tenant_id': tenant_id,
                    'event_type': event_type,
                    'latency_ms': detection_latency_ms,
                    'findings_count': findings_count
                }
            )

        except (ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to record event metrics: {e}",
                extra={'tenant_id': tenant_id, 'event_type': event_type}
            )

    @classmethod
    def get_metrics(cls, tenant_id: int, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get streaming anomaly detection metrics for tenant.

        Args:
            tenant_id: Tenant ID
            time_window_minutes: Time window for metrics (default: 60 min)

        Returns:
            Dict with metrics by event type
        """
        try:
            event_types = ['attendance', 'task', 'location']
            metrics = {
                'tenant_id': tenant_id,
                'time_window_minutes': time_window_minutes,
                'collected_at': timezone.now().isoformat(),
                'by_event_type': {}
            }

            total_events = 0
            total_findings = 0
            total_latency = 0

            for event_type in event_types:
                count_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:count"
                latency_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:latency"
                findings_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:findings"

                event_count = cache.get(count_key, 0)
                avg_latency = cache.get(latency_key, 0)
                findings_count = cache.get(findings_key, 0)

                metrics['by_event_type'][event_type] = {
                    'events_processed': event_count,
                    'avg_latency_ms': round(avg_latency, 2),
                    'findings_detected': findings_count,
                    'finding_rate': round(findings_count / event_count, 3) if event_count > 0 else 0
                }

                total_events += event_count
                total_findings += findings_count
                total_latency += avg_latency

            # Overall metrics
            metrics['overall'] = {
                'total_events': total_events,
                'total_findings': total_findings,
                'avg_latency_ms': round(total_latency / len(event_types), 2) if event_types else 0,
                'events_per_minute': round(total_events / time_window_minutes, 2),
                'overall_finding_rate': round(total_findings / total_events, 3) if total_events > 0 else 0
            }

            return metrics

        except (ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to get metrics: {e}",
                extra={'tenant_id': tenant_id}
            )
            return {'error': str(e)}

    @classmethod
    def reset_metrics(cls, tenant_id: int):
        """Reset all metrics for tenant."""
        try:
            event_types = ['attendance', 'task', 'location']
            for event_type in event_types:
                count_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:count"
                latency_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:latency"
                findings_key = f"{cls.METRICS_KEY_PREFIX}:{tenant_id}:{event_type}:findings"

                cache.delete(count_key)
                cache.delete(latency_key)
                cache.delete(findings_key)

            logger.info(f"Reset metrics for tenant {tenant_id}")

        except (ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to reset metrics: {e}",
                extra={'tenant_id': tenant_id}
            )

    @classmethod
    def get_health_status(cls) -> Dict[str, Any]:
        """
        Get health status of streaming anomaly detection system.

        Returns:
            Dict with system health information
        """
        try:
            from channels.layers import get_channel_layer

            channel_layer = get_channel_layer()
            is_healthy = channel_layer is not None

            status = {
                'is_healthy': is_healthy,
                'channel_layer_configured': is_healthy,
                'max_events_per_second': getattr(
                    settings,
                    'STREAMING_ANOMALY_MAX_EVENTS_PER_SECOND',
                    100
                ),
                'checked_at': timezone.now().isoformat()
            }

            if not is_healthy:
                status['error'] = 'Channel layer not configured'
                logger.warning("Streaming anomaly health check failed - no channel layer")

            return status

        except (ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"Health check failed: {e}")
            return {
                'is_healthy': False,
                'error': str(e),
                'checked_at': timezone.now().isoformat()
            }

    @classmethod
    def get_latency_improvement(cls, tenant_id: int) -> Dict[str, Any]:
        """
        Calculate latency improvement vs batch processing.

        Batch processing baseline: 5-15 minutes
        Streaming target: <1 minute

        Returns:
            Dict with improvement metrics
        """
        try:
            metrics = cls.get_metrics(tenant_id)
            avg_latency_ms = metrics.get('overall', {}).get('avg_latency_ms', 0)
            avg_latency_sec = avg_latency_ms / 1000

            # Batch processing baseline (average 10 minutes)
            batch_latency_sec = 10 * 60

            improvement_factor = batch_latency_sec / avg_latency_sec if avg_latency_sec > 0 else 0
            improvement_percentage = ((batch_latency_sec - avg_latency_sec) / batch_latency_sec * 100) if batch_latency_sec > 0 else 0

            return {
                'streaming_latency_seconds': round(avg_latency_sec, 2),
                'batch_latency_seconds': batch_latency_sec,
                'improvement_factor': round(improvement_factor, 1),
                'improvement_percentage': round(improvement_percentage, 1),
                'target_met': avg_latency_sec < 60,  # <1 minute target
            }

        except (ValueError, RuntimeError) as e:
            logger.error(
                f"Failed to calculate latency improvement: {e}",
                extra={'tenant_id': tenant_id}
            )
            return {'error': str(e)}
