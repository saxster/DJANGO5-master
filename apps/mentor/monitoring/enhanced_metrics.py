"""
Enhanced monitoring and metrics for the AI Mentor system.

This module provides comprehensive observability including:
- LLM usage metrics (tokens, cost, latency)
- Code quality metrics (acceptance rates, edit distances)
- System performance metrics
- User interaction analytics
"""

import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from django.core.cache import cache
from django.utils import timezone


@dataclass
class LLMUsageMetrics:
    """Metrics for LLM usage."""
    provider: str
    model: str
    total_requests: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    error_count: int = 0
    last_request_at: Optional[datetime] = None


@dataclass
class QualityMetrics:
    """Code quality and acceptance metrics."""
    total_plans_generated: int = 0
    total_patches_generated: int = 0
    patches_accepted: int = 0
    patches_rejected: int = 0
    avg_edit_distance_post_merge: float = 0.0
    defect_escape_rate: float = 0.0
    mean_time_to_plan_seconds: float = 0.0
    mean_time_to_patch_seconds: float = 0.0
    user_satisfaction_score: float = 0.0


@dataclass
class SystemMetrics:
    """System performance metrics."""
    index_health_score: float = 1.0
    index_lag_commits: int = 0
    avg_response_time_ms: float = 0.0
    cache_hit_rate: float = 0.0
    error_rate: float = 0.0
    active_sessions: int = 0
    peak_memory_mb: float = 0.0


@dataclass
class UserInteractionMetrics:
    """User interaction and workflow metrics."""
    total_sessions: int = 0
    avg_session_duration_minutes: float = 0.0
    most_used_features: Dict[str, int] = field(default_factory=dict)
    workflow_completion_rate: float = 0.0
    user_feedback_scores: List[float] = field(default_factory=list)


class MentorMetricsCollector:
    """Comprehensive metrics collector for AI Mentor system."""

    def __init__(self):
        self.cache_prefix = "mentor_metrics"
        self.metrics_retention_days = 30

    # LLM Metrics
    def record_llm_request(self, provider: str, model: str, tokens_input: int,
                          tokens_output: int, latency_ms: float, cost_usd: float = 0.0,
                          error: bool = False):
        """Record an LLM request with usage metrics."""
        metrics_key = f"{self.cache_prefix}_llm_{provider}_{model}"
        metrics = self._get_or_create_llm_metrics(metrics_key, provider, model)

        metrics.total_requests += 1
        metrics.total_tokens_input += tokens_input
        metrics.total_tokens_output += tokens_output
        metrics.total_cost_usd += cost_usd
        metrics.last_request_at = timezone.now()

        if error:
            metrics.error_count += 1
        else:
            # Update average latency (exponential moving average)
            alpha = 0.1  # Smoothing factor
            if metrics.avg_latency_ms == 0:
                metrics.avg_latency_ms = latency_ms
            else:
                metrics.avg_latency_ms = (alpha * latency_ms) + ((1 - alpha) * metrics.avg_latency_ms)

        self._save_llm_metrics(metrics_key, metrics)

    def record_maker_checker_session(self, task_type: str, iterations: int,
                                   total_tokens: int, total_time_seconds: float,
                                   validation_result: str, confidence_score: float):
        """Record a maker/checker session."""
        session_key = f"{self.cache_prefix}_maker_checker_sessions"
        sessions = cache.get(session_key, [])

        session_data = {
            'timestamp': time.time(),
            'task_type': task_type,
            'iterations': iterations,
            'total_tokens': total_tokens,
            'total_time_seconds': total_time_seconds,
            'validation_result': validation_result,
            'confidence_score': confidence_score
        }

        sessions.append(session_data)

        # Keep only recent sessions
        cutoff_time = time.time() - (self.metrics_retention_days * 24 * 3600)
        sessions = [s for s in sessions if s['timestamp'] > cutoff_time]

        cache.set(session_key, sessions, timeout=86400)

    # Quality Metrics
    def record_plan_generation(self, plan_id: str, generation_time_seconds: float,
                             user_id: Optional[int] = None):
        """Record plan generation metrics."""
        quality_key = f"{self.cache_prefix}_quality"
        metrics = self._get_or_create_quality_metrics(quality_key)

        metrics.total_plans_generated += 1

        # Update mean time to plan (exponential moving average)
        alpha = 0.1
        if metrics.mean_time_to_plan_seconds == 0:
            metrics.mean_time_to_plan_seconds = generation_time_seconds
        else:
            metrics.mean_time_to_plan_seconds = (
                alpha * generation_time_seconds +
                (1 - alpha) * metrics.mean_time_to_plan_seconds
            )

        self._save_quality_metrics(quality_key, metrics)

    def record_patch_outcome(self, patch_id: str, accepted: bool, edit_distance: float = 0.0,
                           generation_time_seconds: float = 0.0):
        """Record patch acceptance/rejection outcome."""
        quality_key = f"{self.cache_prefix}_quality"
        metrics = self._get_or_create_quality_metrics(quality_key)

        metrics.total_patches_generated += 1

        if accepted:
            metrics.patches_accepted += 1

            # Update average edit distance
            if metrics.avg_edit_distance_post_merge == 0:
                metrics.avg_edit_distance_post_merge = edit_distance
            else:
                alpha = 0.1
                metrics.avg_edit_distance_post_merge = (
                    alpha * edit_distance +
                    (1 - alpha) * metrics.avg_edit_distance_post_merge
                )
        else:
            metrics.patches_rejected += 1

        # Update mean time to patch
        if generation_time_seconds > 0:
            alpha = 0.1
            if metrics.mean_time_to_patch_seconds == 0:
                metrics.mean_time_to_patch_seconds = generation_time_seconds
            else:
                metrics.mean_time_to_patch_seconds = (
                    alpha * generation_time_seconds +
                    (1 - alpha) * metrics.mean_time_to_patch_seconds
                )

        self._save_quality_metrics(quality_key, metrics)

    def record_user_feedback(self, feature: str, rating: float, comment: str = ""):
        """Record user feedback for quality improvement."""
        feedback_key = f"{self.cache_prefix}_user_feedback"
        feedback_data = cache.get(feedback_key, [])

        feedback_entry = {
            'timestamp': time.time(),
            'feature': feature,
            'rating': rating,  # 1-5 scale
            'comment': comment
        }

        feedback_data.append(feedback_entry)

        # Keep only recent feedback
        cutoff_time = time.time() - (self.metrics_retention_days * 24 * 3600)
        feedback_data = [f for f in feedback_data if f['timestamp'] > cutoff_time]

        cache.set(feedback_key, feedback_data, timeout=86400)

    # System Metrics
    def record_system_performance(self, response_time_ms: float, memory_usage_mb: float,
                                cache_hit: bool = False, error: bool = False):
        """Record system performance metrics."""
        system_key = f"{self.cache_prefix}_system"
        metrics = self._get_or_create_system_metrics(system_key)

        # Update response time (exponential moving average)
        alpha = 0.1
        if metrics.avg_response_time_ms == 0:
            metrics.avg_response_time_ms = response_time_ms
        else:
            metrics.avg_response_time_ms = (
                alpha * response_time_ms + (1 - alpha) * metrics.avg_response_time_ms
            )

        # Update peak memory
        if memory_usage_mb > metrics.peak_memory_mb:
            metrics.peak_memory_mb = memory_usage_mb

        # Update cache hit rate
        cache_stats_key = f"{self.cache_prefix}_cache_stats"
        cache_stats = cache.get(cache_stats_key, {'hits': 0, 'total': 0})
        cache_stats['total'] += 1
        if cache_hit:
            cache_stats['hits'] += 1

        metrics.cache_hit_rate = cache_stats['hits'] / cache_stats['total'] if cache_stats['total'] > 0 else 0
        cache.set(cache_stats_key, cache_stats, timeout=86400)

        # Update error rate
        error_stats_key = f"{self.cache_prefix}_error_stats"
        error_stats = cache.get(error_stats_key, {'errors': 0, 'total': 0})
        error_stats['total'] += 1
        if error:
            error_stats['errors'] += 1

        metrics.error_rate = error_stats['errors'] / error_stats['total'] if error_stats['total'] > 0 else 0
        cache.set(error_stats_key, error_stats, timeout=86400)

        self._save_system_metrics(system_key, metrics)

    # Analytics and Reporting
    def get_comprehensive_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        return {
            'llm_usage': self.get_llm_usage_summary(),
            'quality_metrics': self.get_quality_summary(),
            'system_performance': self.get_system_performance_summary(),
            'user_interactions': self.get_user_interaction_summary(),
            'maker_checker_performance': self.get_maker_checker_summary(),
            'cost_analysis': self.get_cost_analysis(),
            'recommendations': self.generate_recommendations()
        }

    def get_llm_usage_summary(self) -> Dict[str, Any]:
        """Get LLM usage summary across all providers."""
        all_metrics = self._get_all_llm_metrics()

        if not all_metrics:
            return {'total_requests': 0, 'total_cost': 0.0}

        total_requests = sum(m.total_requests for m in all_metrics)
        total_tokens = sum(m.total_tokens_input + m.total_tokens_output for m in all_metrics)
        total_cost = sum(m.total_cost_usd for m in all_metrics)
        avg_latency = sum(m.avg_latency_ms for m in all_metrics) / len(all_metrics)

        provider_breakdown = {}
        for metrics in all_metrics:
            provider_breakdown[f"{metrics.provider}_{metrics.model}"] = {
                'requests': metrics.total_requests,
                'tokens': metrics.total_tokens_input + metrics.total_tokens_output,
                'cost': metrics.total_cost_usd,
                'avg_latency_ms': metrics.avg_latency_ms,
                'error_rate': metrics.error_count / metrics.total_requests if metrics.total_requests > 0 else 0
            }

        return {
            'total_requests': total_requests,
            'total_tokens': total_tokens,
            'total_cost_usd': round(total_cost, 4),
            'average_latency_ms': round(avg_latency, 2),
            'provider_breakdown': provider_breakdown
        }

    def get_quality_summary(self) -> Dict[str, Any]:
        """Get code quality metrics summary."""
        quality_key = f"{self.cache_prefix}_quality"
        metrics = self._get_or_create_quality_metrics(quality_key)

        acceptance_rate = 0.0
        if metrics.total_patches_generated > 0:
            acceptance_rate = metrics.patches_accepted / metrics.total_patches_generated

        return {
            'total_plans_generated': metrics.total_plans_generated,
            'total_patches_generated': metrics.total_patches_generated,
            'patch_acceptance_rate': round(acceptance_rate, 3),
            'average_edit_distance': round(metrics.avg_edit_distance_post_merge, 2),
            'defect_escape_rate': round(metrics.defect_escape_rate, 3),
            'mean_time_to_plan_seconds': round(metrics.mean_time_to_plan_seconds, 2),
            'mean_time_to_patch_seconds': round(metrics.mean_time_to_patch_seconds, 2)
        }

    def get_maker_checker_summary(self) -> Dict[str, Any]:
        """Get maker/checker performance summary."""
        session_key = f"{self.cache_prefix}_maker_checker_sessions"
        sessions = cache.get(session_key, [])

        if not sessions:
            return {'total_sessions': 0}

        total_sessions = len(sessions)
        avg_iterations = sum(s['iterations'] for s in sessions) / total_sessions
        avg_confidence = sum(s['confidence_score'] for s in sessions) / total_sessions
        approval_rate = len([s for s in sessions if s['validation_result'] == 'approved']) / total_sessions

        task_type_stats = defaultdict(list)
        for session in sessions:
            task_type_stats[session['task_type']].append(session)

        task_breakdown = {}
        for task_type, task_sessions in task_type_stats.items():
            task_breakdown[task_type] = {
                'sessions': len(task_sessions),
                'avg_iterations': sum(s['iterations'] for s in task_sessions) / len(task_sessions),
                'avg_confidence': sum(s['confidence_score'] for s in task_sessions) / len(task_sessions),
                'approval_rate': len([s for s in task_sessions if s['validation_result'] == 'approved']) / len(task_sessions)
            }

        return {
            'total_sessions': total_sessions,
            'average_iterations': round(avg_iterations, 2),
            'average_confidence': round(avg_confidence, 3),
            'approval_rate': round(approval_rate, 3),
            'task_breakdown': task_breakdown
        }

    def get_cost_analysis(self) -> Dict[str, Any]:
        """Get detailed cost analysis."""
        llm_summary = self.get_llm_usage_summary()
        quality_summary = self.get_quality_summary()

        # Calculate cost per operation
        total_cost = llm_summary.get('total_cost_usd', 0.0)
        total_plans = quality_summary.get('total_plans_generated', 0)
        total_patches = quality_summary.get('total_patches_generated', 0)
        total_operations = total_plans + total_patches

        cost_per_operation = total_cost / total_operations if total_operations > 0 else 0.0

        # Cost efficiency metrics
        acceptance_rate = quality_summary.get('patch_acceptance_rate', 0.0)
        cost_per_accepted_patch = (total_cost / quality_summary.get('patches_accepted', 1)) if quality_summary.get('patches_accepted', 0) > 0 else 0.0

        return {
            'total_cost_usd': total_cost,
            'cost_per_operation': round(cost_per_operation, 4),
            'cost_per_accepted_patch': round(cost_per_accepted_patch, 4),
            'efficiency_score': round(acceptance_rate / cost_per_operation if cost_per_operation > 0 else 0, 2),
            'monthly_cost_projection': round(total_cost * 30, 2),  # Simple projection
            'cost_breakdown_by_provider': llm_summary.get('provider_breakdown', {})
        }

    def generate_recommendations(self) -> List[Dict[str, str]]:
        """Generate actionable recommendations based on metrics."""
        recommendations = []

        # Analyze quality metrics
        quality_summary = self.get_quality_summary()
        acceptance_rate = quality_summary.get('patch_acceptance_rate', 0.0)

        if acceptance_rate < 0.7:
            recommendations.append({
                'type': 'quality',
                'priority': 'high',
                'title': 'Low Patch Acceptance Rate',
                'description': f'Current acceptance rate is {acceptance_rate:.1%}. Consider improving prompt engineering or adding more validation steps.',
                'action': 'Review and enhance maker/checker prompts'
            })

        # Analyze performance metrics
        system_summary = self.get_system_performance_summary()
        avg_response_time = system_summary.get('avg_response_time_ms', 0)

        if avg_response_time > 2000:  # 2 seconds
            recommendations.append({
                'type': 'performance',
                'priority': 'medium',
                'title': 'Slow Response Times',
                'description': f'Average response time is {avg_response_time:.0f}ms. Consider optimizing LLM calls or adding caching.',
                'action': 'Optimize LLM usage and implement result caching'
            })

        # Analyze cost metrics
        cost_analysis = self.get_cost_analysis()
        cost_per_operation = cost_analysis.get('cost_per_operation', 0.0)

        if cost_per_operation > 0.10:  # $0.10 per operation
            recommendations.append({
                'type': 'cost',
                'priority': 'medium',
                'title': 'High Cost Per Operation',
                'description': f'Cost per operation is ${cost_per_operation:.3f}. Consider using smaller models or optimizing prompts.',
                'action': 'Review LLM provider selection and prompt efficiency'
            })

        # Analyze maker/checker performance
        maker_checker_summary = self.get_maker_checker_summary()
        avg_iterations = maker_checker_summary.get('average_iterations', 0)

        if avg_iterations > 2.5:
            recommendations.append({
                'type': 'efficiency',
                'priority': 'low',
                'title': 'High Maker/Checker Iterations',
                'description': f'Average iterations is {avg_iterations:.1f}. Consider improving initial maker prompts.',
                'action': 'Enhance maker prompt templates for better first-pass quality'
            })

        return recommendations

    # Helper methods
    def _get_or_create_llm_metrics(self, key: str, provider: str, model: str) -> LLMUsageMetrics:
        """Get or create LLM metrics object."""
        metrics_data = cache.get(key)
        if metrics_data:
            return LLMUsageMetrics(**metrics_data)
        else:
            return LLMUsageMetrics(provider=provider, model=model)

    def _save_llm_metrics(self, key: str, metrics: LLMUsageMetrics):
        """Save LLM metrics to cache."""
        metrics_data = {
            'provider': metrics.provider,
            'model': metrics.model,
            'total_requests': metrics.total_requests,
            'total_tokens_input': metrics.total_tokens_input,
            'total_tokens_output': metrics.total_tokens_output,
            'total_cost_usd': metrics.total_cost_usd,
            'avg_latency_ms': metrics.avg_latency_ms,
            'error_count': metrics.error_count,
            'last_request_at': metrics.last_request_at.isoformat() if metrics.last_request_at else None
        }
        cache.set(key, metrics_data, timeout=86400)

    def _get_all_llm_metrics(self) -> List[LLMUsageMetrics]:
        """Get all LLM metrics."""
        # This is a simplified implementation
        # In production, you'd store metrics in a database
        metrics = []

        # For demo, create some sample metrics
        sample_providers = [
            ('openai', 'gpt-4'),
            ('anthropic', 'claude-3'),
            ('openai', 'gpt-3.5-turbo')
        ]

        for provider, model in sample_providers:
            key = f"{self.cache_prefix}_llm_{provider}_{model}"
            metric = self._get_or_create_llm_metrics(key, provider, model)
            if metric.total_requests > 0:
                metrics.append(metric)

        return metrics

    def _get_or_create_quality_metrics(self, key: str) -> QualityMetrics:
        """Get or create quality metrics object."""
        metrics_data = cache.get(key)
        if metrics_data:
            return QualityMetrics(**metrics_data)
        else:
            return QualityMetrics()

    def _save_quality_metrics(self, key: str, metrics: QualityMetrics):
        """Save quality metrics to cache."""
        metrics_data = {
            'total_plans_generated': metrics.total_plans_generated,
            'total_patches_generated': metrics.total_patches_generated,
            'patches_accepted': metrics.patches_accepted,
            'patches_rejected': metrics.patches_rejected,
            'avg_edit_distance_post_merge': metrics.avg_edit_distance_post_merge,
            'defect_escape_rate': metrics.defect_escape_rate,
            'mean_time_to_plan_seconds': metrics.mean_time_to_plan_seconds,
            'mean_time_to_patch_seconds': metrics.mean_time_to_patch_seconds,
            'user_satisfaction_score': metrics.user_satisfaction_score
        }
        cache.set(key, metrics_data, timeout=86400)

    def _get_or_create_system_metrics(self, key: str) -> SystemMetrics:
        """Get or create system metrics object."""
        metrics_data = cache.get(key)
        if metrics_data:
            return SystemMetrics(**metrics_data)
        else:
            return SystemMetrics()

    def _save_system_metrics(self, key: str, metrics: SystemMetrics):
        """Save system metrics to cache."""
        metrics_data = {
            'index_health_score': metrics.index_health_score,
            'index_lag_commits': metrics.index_lag_commits,
            'avg_response_time_ms': metrics.avg_response_time_ms,
            'cache_hit_rate': metrics.cache_hit_rate,
            'error_rate': metrics.error_rate,
            'active_sessions': metrics.active_sessions,
            'peak_memory_mb': metrics.peak_memory_mb
        }
        cache.set(key, metrics_data, timeout=86400)

    def get_system_performance_summary(self) -> Dict[str, Any]:
        """Get system performance summary."""
        system_key = f"{self.cache_prefix}_system"
        metrics = self._get_or_create_system_metrics(system_key)

        return {
            'index_health_score': metrics.index_health_score,
            'index_lag_commits': metrics.index_lag_commits,
            'avg_response_time_ms': round(metrics.avg_response_time_ms, 2),
            'cache_hit_rate': round(metrics.cache_hit_rate, 3),
            'error_rate': round(metrics.error_rate, 3),
            'active_sessions': metrics.active_sessions,
            'peak_memory_mb': round(metrics.peak_memory_mb, 2)
        }

    def get_user_interaction_summary(self) -> Dict[str, Any]:
        """Get user interaction summary."""
        feedback_key = f"{self.cache_prefix}_user_feedback"
        feedback_data = cache.get(feedback_key, [])

        if not feedback_data:
            return {'total_feedback': 0}

        avg_rating = sum(f['rating'] for f in feedback_data) / len(feedback_data)

        feature_ratings = defaultdict(list)
        for feedback in feedback_data:
            feature_ratings[feedback['feature']].append(feedback['rating'])

        feature_summary = {}
        for feature, ratings in feature_ratings.items():
            feature_summary[feature] = {
                'avg_rating': round(sum(ratings) / len(ratings), 2),
                'feedback_count': len(ratings)
            }

        return {
            'total_feedback': len(feedback_data),
            'average_rating': round(avg_rating, 2),
            'feature_ratings': feature_summary
        }

    def export_metrics(self, format: str = 'json') -> str:
        """Export all metrics in specified format."""
        dashboard_data = self.get_comprehensive_dashboard()

        if format == 'json':
            return json.dumps(dashboard_data, indent=2, default=str)
        elif format == 'csv':
            # Simple CSV export (could be enhanced)
            csv_lines = ['metric_type,metric_name,value']
            for category, metrics in dashboard_data.items():
                if isinstance(metrics, dict):
                    for metric_name, value in metrics.items():
                        csv_lines.append(f"{category},{metric_name},{value}")
            return '\n'.join(csv_lines)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def reset_metrics(self, confirm: bool = False):
        """Reset all metrics (use with caution)."""
        if not confirm:
            raise ValueError("Must confirm metrics reset with confirm=True")

        # Clear all metric cache keys
        cache_keys = [
            f"{self.cache_prefix}_quality",
            f"{self.cache_prefix}_system",
            f"{self.cache_prefix}_user_feedback",
            f"{self.cache_prefix}_maker_checker_sessions",
            f"{self.cache_prefix}_cache_stats",
            f"{self.cache_prefix}_error_stats"
        ]

        for key in cache_keys:
            cache.delete(key)

        # Clear LLM metrics (would need to iterate through all combinations)
        # For demo, we'll just clear known ones
        known_combinations = [
            ('openai', 'gpt-4'),
            ('anthropic', 'claude-3'),
            ('openai', 'gpt-3.5-turbo')
        ]

        for provider, model in known_combinations:
            key = f"{self.cache_prefix}_llm_{provider}_{model}"
            cache.delete(key)


# Global metrics collector instance
_metrics_collector = None

def get_metrics_collector() -> MentorMetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MentorMetricsCollector()
    return _metrics_collector


# Decorator for automatic metrics collection
def track_mentor_operation(operation_type: str):
    """Decorator to automatically track mentor operations."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            metrics = get_metrics_collector()

            try:
                result = func(*args, **kwargs)

                # Record successful operation
                duration = time.time() - start_time
                metrics.record_system_performance(
                    response_time_ms=duration * 1000,
                    memory_usage_mb=0,  # Could be enhanced to track actual memory
                    error=False
                )

                # Record operation-specific metrics
                if operation_type == 'plan_generation':
                    metrics.record_plan_generation(
                        plan_id=getattr(result, 'plan_id', 'unknown'),
                        generation_time_seconds=duration
                    )

                return result

            except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
                # Record failed operation
                duration = time.time() - start_time
                metrics.record_system_performance(
                    response_time_ms=duration * 1000,
                    memory_usage_mb=0,
                    error=True
                )
                raise

        return wrapper
    return decorator