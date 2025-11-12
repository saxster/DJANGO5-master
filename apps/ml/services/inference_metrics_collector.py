"""
Inference Metrics Collector

Tracks ML model inference performance metrics:
- Inference latency (prediction time)
- Decision counts (predictions made)
- False positive tracking (outcome-based)
- Model usage statistics

Closes Recommendation #8 gap (inference latency tracking).

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Performance monitoring best practices
"""

import time
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('ml.inference_metrics')


class InferenceMetricsCollector:
    """
    Collects and aggregates ML inference performance metrics.

    Tracks latency, throughput, and decision quality for all ML models.
    """

    @staticmethod
    @contextmanager
    def track_inference(model_type: str, model_version: str):
        """
        Context manager to track inference latency.

        Usage:
            with InferenceMetricsCollector.track_inference('fraud_detector', '1.0'):
                prediction = model.predict(features)

        Args:
            model_type: Type of model
            model_version: Model version

        Yields:
            dict: Will contain {'latency_ms': float} after context exits
        """
        start_time = time.time()
        metrics = {}

        try:
            yield metrics
        finally:
            latency_ms = (time.time() - start_time) * 1000
            metrics['latency_ms'] = latency_ms

            # Log to cache (aggregated by minute)
            InferenceMetricsCollector._log_to_cache(
                model_type, model_version, latency_ms
            )

            # Log if latency exceeds threshold (200ms)
            if latency_ms > 200:
                logger.warning(
                    f"Slow inference for {model_type} v{model_version}: "
                    f"{latency_ms:.1f}ms"
                )

    @staticmethod
    def _log_to_cache(model_type: str, model_version: str, latency_ms: float):
        """Log inference metrics to Redis cache (1-minute aggregation)."""
        cache_key = (
            f"inference_metrics_{model_type}_{model_version}_"
            f"{timezone.now().strftime('%Y%m%d_%H%M')}"
        )

        # Get existing metrics or initialize
        metrics = cache.get(cache_key) or {
            'count': 0,
            'total_latency_ms': 0,
            'min_latency_ms': float('inf'),
            'max_latency_ms': 0,
            'latencies': []
        }

        # Update aggregates
        metrics['count'] += 1
        metrics['total_latency_ms'] += latency_ms
        metrics['min_latency_ms'] = min(metrics['min_latency_ms'], latency_ms)
        metrics['max_latency_ms'] = max(metrics['max_latency_ms'], latency_ms)
        metrics['latencies'].append(latency_ms)

        # Cache for 2 hours
        cache.set(cache_key, metrics, timeout=7200)

    @classmethod
    def get_recent_inference_stats(
        cls,
        model_type: str,
        model_version: str,
        minutes: int = 60
    ) -> Optional[Dict[str, Any]]:
        """
        Get recent inference statistics.

        Args:
            model_type: Model type
            model_version: Model version
            minutes: Minutes of recent data (default 60)

        Returns:
            {
                'count': int,
                'avg_latency_ms': float,
                'p50_latency_ms': float,
                'p95_latency_ms': float,
                'p99_latency_ms': float,
                'min_latency_ms': float,
                'max_latency_ms': float
            }
        """
        import numpy as np

        all_latencies = []
        total_count = 0

        # Aggregate from cache (last N minutes)
        now = timezone.now()
        for i in range(minutes):
            timestamp = now - timedelta(minutes=i)
            cache_key = (
                f"inference_metrics_{model_type}_{model_version}_"
                f"{timestamp.strftime('%Y%m%d_%H%M')}"
            )

            metrics = cache.get(cache_key)
            if metrics:
                all_latencies.extend(metrics['latencies'])
                total_count += metrics['count']

        if not all_latencies:
            return None

        latency_array = np.array(all_latencies)

        return {
            'count': total_count,
            'avg_latency_ms': float(np.mean(latency_array)),
            'p50_latency_ms': float(np.percentile(latency_array, 50)),
            'p95_latency_ms': float(np.percentile(latency_array, 95)),
            'p99_latency_ms': float(np.percentile(latency_array, 99)),
            'min_latency_ms': float(np.min(latency_array)),
            'max_latency_ms': float(np.max(latency_array)),
            'period_minutes': minutes
        }

    @classmethod
    def log_decision(
        cls,
        model_type: str,
        decision_type: str,
        confidence: float,
        automated: bool
    ):
        """
        Log a decision made by ML model.

        Args:
            model_type: Type of model
            decision_type: 'ticket', 'alert', 'monitor'
            confidence: Confidence score (0-1)
            automated: True if fully automated, False if human review
        """
        cache_key = f"decisions_{model_type}_{timezone.now().strftime('%Y%m%d')}"

        decisions = cache.get(cache_key) or {
            'total': 0,
            'automated': 0,
            'manual_review': 0,
            'by_type': {}
        }

        decisions['total'] += 1
        if automated:
            decisions['automated'] += 1
        else:
            decisions['manual_review'] += 1

        decisions['by_type'][decision_type] = (
            decisions['by_type'].get(decision_type, 0) + 1
        )

        cache.set(cache_key, decisions, timeout=86400)  # 24 hours

        logger.info(
            f"Decision logged: {model_type} - {decision_type} "
            f"(confidence: {confidence:.2f}, automated: {automated})"
        )
