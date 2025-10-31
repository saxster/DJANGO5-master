"""
Background tasks for personalization system

This module provides async task processing for:
- Aggregating learning signals and updating preference profiles
- Retraining multi-armed bandit models
- Policy promotion and A/B test analysis
- Cost monitoring and budget enforcement
- Performance metric aggregation
"""

import logging
import json
from datetime import timedelta
from typing import Dict, List, Any, Optional
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError

from apps.core.constants.datetime_constants import SECONDS_IN_DAY
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Avg, Q
from django.core.cache import cache

from apps.onboarding.models import (
    PreferenceProfile,
    RecommendationInteraction,
    Experiment,
    ExperimentAssignment,
    ConversationSession
)
from apps.onboarding_api.services.learning import get_learning_service
from apps.onboarding_api.services.experiments import get_experiment_manager
from apps.onboarding_api.services.monitoring import (
    get_metrics_collector,
    get_performance_monitor,
    get_alert_manager,
    get_cost_tracker
)

logger = logging.getLogger(__name__)


def aggregate_interactions_batch():
    """
    Batch process to aggregate interaction signals and update preference profiles
    Should run hourly via scheduler
    """
    try:
        logger.info("Starting interaction aggregation batch job")

        # Get interactions from last hour that haven't been processed
        cutoff_time = timezone.now() - timedelta(hours=1)
        unprocessed_interactions = RecommendationInteraction.objects.filter(
            occurred_at__gte=cutoff_time,
            metadata__isnull=False  # Only process interactions with metadata
        ).select_related('session__user', 'session__client', 'recommendation')

        # Group by user-client pairs
        user_client_groups = {}
        for interaction in unprocessed_interactions:
            if not interaction.session.user:
                continue

            key = (interaction.session.user.id, interaction.session.client.id)
            if key not in user_client_groups:
                user_client_groups[key] = []
            user_client_groups[key].append(interaction)

        processed_count = 0
        error_count = 0

        # Process each user-client group
        for (user_id, client_id), interactions in user_client_groups.items():
            try:
                user = interactions[0].session.user
                client = interactions[0].session.client

                # Get or create preference profile
                profile, created = PreferenceProfile.objects.get_or_create(
                    user=user,
                    client=client,
                    defaults={
                        'weights': _get_default_weights(),
                        'stats': {}
                    }
                )

                # Aggregate features from interactions
                aggregated_features = _aggregate_interaction_features(interactions)

                # Update preference profile
                _update_profile_from_features(profile, aggregated_features)

                processed_count += len(interactions)

                if created:
                    logger.info(f"Created preference profile for user {user_id}, client {client_id}")

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Error processing interactions for user {user_id}, client {client_id}: {str(e)}")
                error_count += len(interactions)

        logger.info(f"Interaction aggregation completed: {processed_count} processed, {error_count} errors")

        # Record metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.record_metric('batch.interaction_aggregation.processed', processed_count)
        metrics_collector.record_metric('batch.interaction_aggregation.errors', error_count)

        return {
            'status': 'success',
            'processed': processed_count,
            'errors': error_count,
            'user_client_groups': len(user_client_groups)
        }

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Error in interaction aggregation batch: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def retrain_bandits():
    """
    Update multi-armed bandit arm posteriors and epsilon schedules
    Should run daily via scheduler
    """
    try:
        logger.info("Starting bandit retraining job")

        # Get active experiments
        active_experiments = Experiment.objects.filter(status='running')

        retrained_count = 0
        error_count = 0

        for experiment in active_experiments:
            try:
                # Get experiment manager
                experiment_manager = get_experiment_manager()

                # Analyze current performance
                analysis = experiment_manager.analyzer.analyze_experiment(experiment)

                if analysis.get('status') == 'complete':
                    # Update experiment results
                    experiment.update_results(analysis)

                    # Check safety constraints
                    violations = experiment_manager.check_safety_constraints(experiment)

                    if violations:
                        # Auto-pause if safety violations detected
                        experiment_manager.pause_experiment(
                            experiment,
                            f"Auto-paused due to safety violations: {'; '.join(violations)}"
                        )
                        logger.warning(f"Auto-paused experiment {experiment.name} due to safety violations")

                    retrained_count += 1

                else:
                    logger.debug(f"Skipping bandit retrain for experiment {experiment.name}: {analysis.get('status')}")

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Error retraining bandit for experiment {experiment.experiment_id}: {str(e)}")
                error_count += 1

        logger.info(f"Bandit retraining completed: {retrained_count} retrained, {error_count} errors")

        # Record metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.record_metric('batch.bandit_retrain.completed', retrained_count)
        metrics_collector.record_metric('batch.bandit_retrain.errors', error_count)

        return {
            'status': 'success',
            'retrained': retrained_count,
            'errors': error_count,
            'active_experiments': active_experiments.count()
        }

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Error in bandit retraining: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def policy_promotion_job():
    """
    Auto-promote successful experiment arms to new policy versions with approval workflow
    Should run daily via scheduler
    """
    try:
        logger.info("Starting policy promotion evaluation job")

        # Get completed experiments that haven't been processed for promotion
        completed_experiments = Experiment.objects.filter(
            status='completed',
            results__isnull=False
        ).exclude(
            results__promotion__isnull=False  # Already promoted
        )

        promoted_count = 0
        candidates_found = 0

        for experiment in completed_experiments:
            try:
                # Check if experiment has a clear winner
                results = experiment.results

                if not results or 'summary' not in results:
                    continue

                summary = results['summary']
                recommendation = summary.get('recommendation', '')

                # Look for promotion keywords in recommendation
                if any(keyword in recommendation.lower() for keyword in ['promote', 'winner', 'significant']):
                    candidates_found += 1

                    # Get statistical significance
                    statistical_significance = summary.get('statistical_significance', {})
                    if statistical_significance.get('any_significant', False):
                        # Promote winning arm
                        best_arm = summary.get('best_performing_arm', {})
                        arm_name = best_arm.get('name')

                        if arm_name:
                            experiment_manager = get_experiment_manager()
                            promotion_result = experiment_manager.promote_winning_arm(experiment, arm_name)

                            if promotion_result.get('status') == 'success':
                                promoted_count += 1
                                logger.info(f"Auto-promoted arm {arm_name} from experiment {experiment.name}")

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Error evaluating promotion for experiment {experiment.experiment_id}: {str(e)}")

        logger.info(f"Policy promotion completed: {promoted_count} promoted, {candidates_found} candidates found")

        # Record metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.record_metric('batch.policy_promotion.promoted', promoted_count)
        metrics_collector.record_metric('batch.policy_promotion.candidates', candidates_found)

        return {
            'status': 'success',
            'promoted': promoted_count,
            'candidates_found': candidates_found,
            'completed_experiments': completed_experiments.count()
        }

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Error in policy promotion job: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def cost_guard_job():
    """
    Monitor budgets and implement cost controls
    Should run every 15 minutes via scheduler
    """
    try:
        logger.info("Starting cost guard job")

        cost_tracker = get_cost_tracker()

        # Get cost summary for last hour
        cost_summary = cost_tracker.get_cost_summary(time_window_hours=1)

        if cost_summary.get('error'):
            logger.error(f"Error getting cost summary: {cost_summary['error']}")
            return {'status': 'error', 'message': cost_summary['error']}

        # Check budget utilization
        budget_utilization = cost_summary.get('budget_utilization', 0)

        actions_taken = []

        # Alert if budget utilization is high
        if budget_utilization > 0.8:  # 80% of hourly budget used
            logger.warning(f"High budget utilization: {budget_utilization:.2%}")
            actions_taken.append('high_budget_alert')

            # Implement cost controls if utilization is critical
            if budget_utilization > 0.95:  # 95% of budget used
                logger.critical("Critical budget utilization - implementing cost controls")

                # Switch to low-cost processing mode
                cache.set('cost_control_mode', True, 3600)  # 1 hour

                # Reduce token budgets temporarily
                cache.set('emergency_token_reduction', 0.5, 3600)  # 50% reduction for 1 hour

                actions_taken.append('emergency_cost_controls')

        # Check for cost anomalies by user
        cost_by_user = cost_summary.get('cost_by_user', {})
        user_cost_limit = getattr(settings, 'USER_HOURLY_BUDGET_CENTS', 1000)

        for user_id, cost_cents in cost_by_user.items():
            if cost_cents > user_cost_limit * 2:  # 2x normal limit
                logger.warning(f"User {user_id} exceeded cost limit: ${cost_cents/100:.2f}")

                # Temporarily reduce user's budget
                cache.set(f'user_cost_reduction_{user_id}', 0.3, 3600)  # 70% reduction
                actions_taken.append(f'user_cost_reduction_{user_id}')

        logger.info(f"Cost guard completed: {len(actions_taken)} actions taken")

        # Record metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.record_metric('batch.cost_guard.budget_utilization', budget_utilization)
        metrics_collector.record_metric('batch.cost_guard.actions_taken', len(actions_taken))

        return {
            'status': 'success',
            'budget_utilization': budget_utilization,
            'actions_taken': actions_taken,
            'total_cost_cents': cost_summary.get('total_cost_cents', 0)
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Error in cost guard job: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def performance_monitoring_job():
    """
    Monitor system performance and SLO compliance
    Should run every 5 minutes via scheduler
    """
    try:
        logger.info("Starting performance monitoring job")

        performance_monitor = get_performance_monitor()
        alert_manager = get_alert_manager()

        # Check SLO compliance
        slo_status = performance_monitor.check_slos(time_window_minutes=15)

        # Check for alerts
        alerts = alert_manager.check_alerts()

        # Record SLO metrics
        metrics_collector = get_metrics_collector()

        if 'recommendation_latency' in slo_status:
            latency_data = slo_status['recommendation_latency']
            metrics_collector.record_metric('slo.latency.p50', latency_data['p50_ms'], unit='milliseconds')
            metrics_collector.record_metric('slo.latency.p95', latency_data['p95_ms'], unit='milliseconds')
            metrics_collector.record_metric('slo.latency.compliant', 1 if latency_data['p95_compliant'] else 0)

        if 'acceptance_rate' in slo_status:
            acceptance_data = slo_status['acceptance_rate']
            metrics_collector.record_metric('slo.acceptance_rate', acceptance_data['current_rate'], unit='ratio')
            metrics_collector.record_metric('slo.acceptance_rate.compliant', 1 if acceptance_data['compliant'] else 0)

        if 'error_rate' in slo_status:
            error_data = slo_status['error_rate']
            metrics_collector.record_metric('slo.error_rate', error_data['current_rate'], unit='ratio')
            metrics_collector.record_metric('slo.error_rate.compliant', 1 if error_data['compliant'] else 0)

        # Record alert metrics
        alert_counts = {}
        for alert in alerts:
            severity = alert.severity
            alert_counts[severity] = alert_counts.get(severity, 0) + 1

        for severity, count in alert_counts.items():
            metrics_collector.record_metric(f'alerts.{severity}', count)

        logger.info(f"Performance monitoring completed: {len(alerts)} active alerts")

        return {
            'status': 'success',
            'slo_compliant': slo_status.get('overall', {}).get('compliant', False),
            'active_alerts': len(alerts),
            'critical_alerts': alert_counts.get('critical', 0)
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Error in performance monitoring job: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def cleanup_expired_data():
    """
    Clean up expired data and assignments
    Should run daily via scheduler
    """
    try:
        logger.info("Starting data cleanup job")

        now = timezone.now()
        cleanup_stats = {
            'expired_assignments': 0,
            'old_interactions': 0,
            'stale_cache_entries': 0
        }

        # Clean up expired experiment assignments
        expired_assignments = ExperimentAssignment.objects.filter(
            expires_at__lt=now,
            expires_at__isnull=False
        )
        cleanup_stats['expired_assignments'] = expired_assignments.count()
        expired_assignments.delete()

        # Clean up old interaction data (keep last 90 days)
        retention_cutoff = now - timedelta(days=90)
        old_interactions = RecommendationInteraction.objects.filter(
            occurred_at__lt=retention_cutoff
        )
        cleanup_stats['old_interactions'] = old_interactions.count()

        # Delete in batches to avoid long locks
        batch_size = 1000
        while old_interactions.exists():
            batch_ids = list(old_interactions[:batch_size].values_list('id', flat=True))
            RecommendationInteraction.objects.filter(id__in=batch_ids).delete()

        # Clean up stale cache entries
        # This would typically involve Redis SCAN operations
        # For Django cache, we'll implement a simple version tracking approach
        cache.set('last_cleanup', now.isoformat(), SECONDS_IN_DAY)
        cleanup_stats['stale_cache_entries'] = 0  # Placeholder

        logger.info(f"Data cleanup completed: {cleanup_stats}")

        # Record metrics
        metrics_collector = get_metrics_collector()
        for key, value in cleanup_stats.items():
            metrics_collector.record_metric(f'cleanup.{key}', value)

        return {
            'status': 'success',
            'cleanup_stats': cleanup_stats
        }

    except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Error in cleanup job: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def preference_vector_update_job():
    """
    Update preference vectors for all active users
    Should run daily via scheduler
    """
    try:
        logger.info("Starting preference vector update job")

        # Get profiles that need vector updates (updated in last 7 days)
        recent_cutoff = timezone.now() - timedelta(days=7)
        profiles_to_update = PreferenceProfile.objects.filter(
            last_updated__gte=recent_cutoff
        ).select_related('user', 'client')

        updated_count = 0
        error_count = 0

        learning_service = get_learning_service()

        for profile in profiles_to_update:
            try:
                if profile.user:
                    # Recalculate preference vector
                    new_vector = learning_service.feature_extractor.create_preference_vector(
                        profile.user, profile.client
                    )

                    if new_vector and len(new_vector) > 0:
                        profile.preference_vector = new_vector
                        profile.save()
                        updated_count += 1

            except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
                logger.error(f"Error updating preference vector for profile {profile.profile_id}: {str(e)}")
                error_count += 1

        logger.info(f"Preference vector update completed: {updated_count} updated, {error_count} errors")

        # Record metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.record_metric('batch.preference_vectors.updated', updated_count)
        metrics_collector.record_metric('batch.preference_vectors.errors', error_count)

        return {
            'status': 'success',
            'updated': updated_count,
            'errors': error_count,
            'total_profiles': profiles_to_update.count()
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
        logger.error(f"Error in preference vector update job: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def experiment_health_check():
    """
    Comprehensive health check for all running experiments
    Should run every 30 minutes via scheduler
    """
    try:
        logger.info("Starting experiment health check")

        running_experiments = Experiment.objects.filter(status='running')
        experiment_manager = get_experiment_manager()

        health_summary = {
            'total_experiments': running_experiments.count(),
            'healthy_experiments': 0,
            'unhealthy_experiments': 0,
            'auto_paused': 0,
            'health_issues': []
        }

        for experiment in running_experiments:
            try:
                # Check safety constraints
                violations = experiment_manager.check_safety_constraints(experiment)

                if violations:
                    health_summary['unhealthy_experiments'] += 1
                    health_summary['health_issues'].extend(violations)

                    # Check if auto-pause is needed
                    if any('critical' in v.lower() for v in violations):
                        experiment_manager.pause_experiment(
                            experiment,
                            f"Auto-paused: critical safety violations detected"
                        )
                        health_summary['auto_paused'] += 1

                else:
                    health_summary['healthy_experiments'] += 1

                # Check runtime and sample size
                if experiment.started_at:
                    runtime_hours = (timezone.now() - experiment.started_at).total_seconds() / 3600
                    min_runtime = getattr(settings, 'EXPERIMENT_MIN_RUNTIME_HOURS', 48)

                    if runtime_hours > min_runtime * 2:  # Running for 2x minimum time
                        # Check if we should complete
                        analysis = experiment_manager.analyzer.analyze_experiment(experiment)
                        if analysis.get('status') == 'complete':
                            statistical_tests = analysis.get('statistical_tests', [])
                            if any(test.get('significant', False) for test in statistical_tests):
                                logger.info(f"Experiment {experiment.name} ready for completion - significant results found")

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Error checking health for experiment {experiment.experiment_id}: {str(e)}")
                health_summary['unhealthy_experiments'] += 1

        logger.info(f"Experiment health check completed: {health_summary}")

        # Record metrics
        metrics_collector = get_metrics_collector()
        metrics_collector.record_metric('health.experiments.total', health_summary['total_experiments'])
        metrics_collector.record_metric('health.experiments.healthy', health_summary['healthy_experiments'])
        metrics_collector.record_metric('health.experiments.unhealthy', health_summary['unhealthy_experiments'])
        metrics_collector.record_metric('health.experiments.auto_paused', health_summary['auto_paused'])

        return {
            'status': 'success',
            'health_summary': health_summary
        }

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
        logger.error(f"Error in experiment health check: {str(e)}")
        return {'status': 'error', 'message': str(e)}


# Helper functions
def _get_default_weights() -> Dict[str, Any]:
    """Get default preference weights for new users"""
    return {
        'cost_sensitivity': 0.5,
        'risk_tolerance': 0.5,
        'detail_level': 0.5,
        'language_pref': 'en',
        'citation_importance': 0.5,
        'response_speed_pref': 0.5,
    }


def _aggregate_interaction_features(interactions: List[RecommendationInteraction]) -> Dict[str, Any]:
    """Aggregate features from a batch of interactions"""
    features = {
        'total_interactions': len(interactions),
        'event_type_counts': {},
        'avg_time_on_item': 0,
        'avg_scroll_depth': 0,
        'total_cost_estimate': 0,
        'avg_confidence_score': 0
    }

    # Count event types
    for interaction in interactions:
        event_type = interaction.event_type
        features['event_type_counts'][event_type] = features['event_type_counts'].get(event_type, 0) + 1

        # Aggregate metadata
        metadata = interaction.metadata or {}
        features['avg_time_on_item'] += metadata.get('time_on_item', 0)
        features['avg_scroll_depth'] += metadata.get('scroll_depth', 0)
        features['total_cost_estimate'] += metadata.get('cost_estimate', 0)

        # Aggregate recommendation features
        if interaction.recommendation.confidence_score:
            features['avg_confidence_score'] += interaction.recommendation.confidence_score

    # Calculate averages
    count = len(interactions)
    if count > 0:
        features['avg_time_on_item'] /= count
        features['avg_scroll_depth'] /= count
        features['avg_confidence_score'] /= count

    return features


def _update_profile_from_features(profile: PreferenceProfile, features: Dict[str, Any]):
    """Update preference profile from aggregated features"""
    try:
        # Update statistics
        if not profile.stats:
            profile.stats = {}

        for event_type, count in features['event_type_counts'].items():
            profile.stats[event_type] = profile.stats.get(event_type, 0) + count

        # Update derived metrics
        profile.stats['avg_time_on_item'] = features['avg_time_on_item']
        profile.stats['avg_scroll_depth'] = features['avg_scroll_depth']
        profile.stats['total_cost_estimate'] = features['total_cost_estimate']

        # Update preference weights based on patterns
        if not profile.weights:
            profile.weights = _get_default_weights()

        # Adapt cost sensitivity based on approval patterns
        approvals = features['event_type_counts'].get('approved', 0)
        rejections = features['event_type_counts'].get('rejected', 0)
        total_decisions = approvals + rejections

        if total_decisions > 0:
            approval_rate = approvals / total_decisions

            # High approval rate might indicate user is not cost-sensitive
            if approval_rate > 0.8 and features['total_cost_estimate'] > 0:
                current_cost_sensitivity = profile.weights.get('cost_sensitivity', 0.5)
                profile.weights['cost_sensitivity'] = max(0.1, current_cost_sensitivity - 0.05)

        # Adapt detail preference based on engagement
        avg_time_on_item = features['avg_time_on_item']
        if avg_time_on_item > 60:  # High engagement with details
            current_detail_level = profile.weights.get('detail_level', 0.5)
            profile.weights['detail_level'] = min(1.0, current_detail_level + 0.05)

        profile.save()

    except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
        logger.error(f"Error updating profile from features: {str(e)}")


# Task registration for scheduling system
PERSONALIZATION_TASKS = {
    'aggregate_interactions': {
        'function': aggregate_interactions_batch,
        'schedule': 'hourly',
        'queue': 'default'
    },
    'retrain_bandits': {
        'function': retrain_bandits,
        'schedule': 'daily',
        'queue': 'default'
    },
    'policy_promotion': {
        'function': policy_promotion_job,
        'schedule': 'daily',
        'queue': 'default'
    },
    'cost_guard': {
        'function': cost_guard_job,
        'schedule': 'every_15_minutes',
        'queue': 'high_priority'
    },
    'performance_monitoring': {
        'function': performance_monitoring_job,
        'schedule': 'every_5_minutes',
        'queue': 'high_priority'
    },
    'experiment_health_check': {
        'function': experiment_health_check,
        'schedule': 'every_30_minutes',
        'queue': 'default'
    },
    'preference_vector_update': {
        'function': preference_vector_update_job,
        'schedule': 'daily',
        'queue': 'default'
    },
    'cleanup_expired_data': {
        'function': cleanup_expired_data,
        'schedule': 'daily',
        'queue': 'default'
    }
}
