"""
Health-based auto-degrade monitoring system for Conversational Onboarding

This module provides intelligent monitoring that automatically degrades the system
when performance, cost, or error thresholds are exceeded, ensuring system stability
and cost control.
"""
import logging
import time
from typing import Dict, Any
from django.db import connection
from django.utils import timezone
from enum import Enum


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    DISABLED = "disabled"


class DegradationLevel(Enum):
    """Available degradation levels"""
    NONE = "none"
    DISABLE_CHECKER_LLM = "disable_checker_llm"
    DISABLE_KB_GROUNDING = "disable_kb_grounding"
    SYNCHRONOUS_MODE = "synchronous_mode"
    DISABLE_ONBOARDING = "disable_onboarding"


class SystemMonitor:
    """
    Intelligent system monitor with auto-degradation capabilities

    This monitor tracks various system health metrics and automatically
    applies degradation strategies when thresholds are exceeded.
    """

    def __init__(self):
        self.metrics_cache_timeout = 300  # 5 minutes
        self.degradation_state = DegradationLevel.NONE
        self.last_check_time = timezone.now()
        self.alert_cooldown = 900  # 15 minutes between alerts

        # Load thresholds from settings
        self.thresholds = getattr(settings, 'ONBOARDING_ALERT_THRESHOLDS', {})
        self.rate_limits = getattr(settings, 'ONBOARDING_RATE_LIMITS', {})

    def check_system_health(self) -> Dict[str, Any]:
        """
        Comprehensive system health check with auto-degradation

        Returns:
            Dict containing health status and any actions taken
        """
        health_report = {
            'overall_status': HealthStatus.HEALTHY,
            'component_status': {},
            'metrics': {},
            'degradations_applied': [],
            'alerts_generated': [],
            'recommendations': [],
            'checked_at': timezone.now().isoformat()
        }

        try:
            # Check each system component
            components_to_check = [
                ('llm_performance', self._check_llm_performance),
                ('cost_tracking', self._check_cost_limits),
                ('error_rates', self._check_error_rates),
                ('cache_performance', self._check_cache_performance),
                ('database_performance', self._check_database_performance),
                ('rate_limiting', self._check_rate_limiting)
            ]

            critical_issues = 0
            degraded_issues = 0

            for component_name, check_function in components_to_check:
                component_result = check_function()
                health_report['component_status'][component_name] = component_result

                if component_result['status'] == HealthStatus.CRITICAL:
                    critical_issues += 1
                elif component_result['status'] == HealthStatus.DEGRADED:
                    degraded_issues += 1

                # Apply auto-degradation if needed
                if component_result.get('auto_degrade_recommended'):
                    degradation = self._apply_auto_degradation(
                        component_name,
                        component_result['degradation_level']
                    )
                    if degradation:
                        health_report['degradations_applied'].append(degradation)

                # Generate alerts if needed
                if component_result.get('alert_required'):
                    alert = self._generate_alert(component_name, component_result)
                    if alert:
                        health_report['alerts_generated'].append(alert)

                # Add metrics
                if 'metrics' in component_result:
                    health_report['metrics'][component_name] = component_result['metrics']

                # Add recommendations
                if 'recommendations' in component_result:
                    health_report['recommendations'].extend(component_result['recommendations'])

            # Determine overall status
            if critical_issues > 0:
                health_report['overall_status'] = HealthStatus.CRITICAL
            elif degraded_issues > 0:
                health_report['overall_status'] = HealthStatus.DEGRADED
            else:
                health_report['overall_status'] = HealthStatus.HEALTHY

            # Update last check time
            self.last_check_time = timezone.now()

            # Cache health report
            cache.set('onboarding_health_report', health_report, self.metrics_cache_timeout)

            logger.info(
                f"System health check completed: {health_report['overall_status'].value} "
                f"({critical_issues} critical, {degraded_issues} degraded issues)"
            )

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Health check failed: {str(e)}")
            health_report['overall_status'] = HealthStatus.CRITICAL
            health_report['error'] = str(e)

        return health_report

    def _check_llm_performance(self) -> Dict[str, Any]:
        """Check LLM service performance and latency"""
        result = {
            'status': HealthStatus.HEALTHY,
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'auto_degrade_recommended': False,
            'alert_required': False
        }

        try:
            # Get LLM metrics from cache
            llm_metrics = cache.get('onboarding_llm_metrics', {})

            if not llm_metrics:
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append('No LLM metrics available')
                result['recommendations'].append('Check LLM service connectivity')
                return result

            # Check average latency
            avg_latency = llm_metrics.get('avg_latency_ms', 0)
            max_latency_threshold = self.thresholds.get('avg_latency_ms', 30000)

            if avg_latency > max_latency_threshold:
                result['status'] = HealthStatus.CRITICAL
                result['issues'].append(f'High LLM latency: {avg_latency}ms > {max_latency_threshold}ms')
                result['auto_degrade_recommended'] = True
                result['degradation_level'] = DegradationLevel.DISABLE_CHECKER_LLM
                result['alert_required'] = True

            elif avg_latency > max_latency_threshold * 0.7:
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append(f'Elevated LLM latency: {avg_latency}ms')
                result['recommendations'].append('Monitor LLM service performance')

            # Check error rate
            error_rate = llm_metrics.get('error_rate_percent', 0)
            max_error_rate = self.thresholds.get('error_rate_percent', 10.0)

            if error_rate > max_error_rate:
                result['status'] = HealthStatus.CRITICAL
                result['issues'].append(f'High LLM error rate: {error_rate}% > {max_error_rate}%')
                result['auto_degrade_recommended'] = True
                result['degradation_level'] = DegradationLevel.SYNCHRONOUS_MODE
                result['alert_required'] = True

            # Check token usage
            daily_tokens = llm_metrics.get('daily_tokens_used', 0)
            daily_token_limit = self.rate_limits.get('llm_calls', {}).get('tokens', {}).get('daily', 50000)

            if daily_tokens > daily_token_limit * 0.9:
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append(f'High token usage: {daily_tokens}/{daily_token_limit}')
                result['recommendations'].append('Monitor token consumption and consider rate limiting')

            result['metrics'] = {
                'avg_latency_ms': avg_latency,
                'error_rate_percent': error_rate,
                'daily_tokens_used': daily_tokens,
                'daily_token_limit': daily_token_limit
            }

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"LLM performance check failed: {str(e)}")
            result['status'] = HealthStatus.CRITICAL
            result['issues'].append(f'LLM performance check failed: {str(e)}')

        return result

    def _check_cost_limits(self) -> Dict[str, Any]:
        """Check cost consumption and limits"""
        result = {
            'status': HealthStatus.HEALTHY,
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'auto_degrade_recommended': False,
            'alert_required': False
        }

        try:
            # Get cost metrics from cache
            cost_metrics = cache.get('onboarding_cost_metrics', {})

            daily_cost = cost_metrics.get('daily_cost_cents', 0)
            daily_budget = self.thresholds.get('daily_cost_cents', 10000)  # $100

            cost_percentage = (daily_cost / daily_budget) * 100 if daily_budget > 0 else 0

            if daily_cost >= daily_budget:
                result['status'] = HealthStatus.CRITICAL
                result['issues'].append(f'Daily budget exceeded: ${daily_cost/100:.2f} >= ${daily_budget/100:.2f}')
                result['auto_degrade_recommended'] = True
                result['degradation_level'] = DegradationLevel.DISABLE_ONBOARDING
                result['alert_required'] = True

            elif cost_percentage > 80:
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append(f'High cost consumption: {cost_percentage:.1f}% of daily budget')
                result['recommendations'].append('Consider reducing LLM usage or implementing cost controls')

            elif cost_percentage > 50:
                result['recommendations'].append('Monitor cost trends - approaching 50% of daily budget')

            # Check hourly burn rate
            hourly_cost = cost_metrics.get('hourly_cost_cents', 0)
            if hourly_cost > 0:
                projected_daily = hourly_cost * 24
                if projected_daily > daily_budget:
                    result['status'] = max(result['status'], HealthStatus.DEGRADED, key=lambda x: x.value)
                    result['issues'].append(f'High burn rate: projected ${projected_daily/100:.2f}/day')
                    result['recommendations'].append('Current usage rate will exceed daily budget')

            result['metrics'] = {
                'daily_cost_cents': daily_cost,
                'daily_budget_cents': daily_budget,
                'cost_percentage': cost_percentage,
                'hourly_cost_cents': hourly_cost
            }

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Cost check failed: {str(e)}")
            result['status'] = HealthStatus.DEGRADED
            result['issues'].append(f'Cost tracking unavailable: {str(e)}')

        return result

    def _check_error_rates(self) -> Dict[str, Any]:
        """Check system error rates"""
        result = {
            'status': HealthStatus.HEALTHY,
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'auto_degrade_recommended': False,
            'alert_required': False
        }

        try:
            # Get error metrics from cache
            error_metrics = cache.get('onboarding_error_metrics', {})

            error_rate = error_metrics.get('error_rate_percent', 0)
            max_error_rate = self.thresholds.get('error_rate_percent', 10.0)

            if error_rate > max_error_rate:
                result['status'] = HealthStatus.CRITICAL
                result['issues'].append(f'High system error rate: {error_rate}% > {max_error_rate}%')
                result['auto_degrade_recommended'] = True
                result['degradation_level'] = DegradationLevel.SYNCHRONOUS_MODE
                result['alert_required'] = True

            elif error_rate > max_error_rate * 0.5:
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append(f'Elevated error rate: {error_rate}%')
                result['recommendations'].append('Monitor error logs and investigate causes')

            # Check specific error types
            critical_errors = error_metrics.get('critical_errors_per_hour', 0)
            if critical_errors > 5:
                result['status'] = HealthStatus.CRITICAL
                result['issues'].append(f'High critical error rate: {critical_errors}/hour')
                result['alert_required'] = True

            result['metrics'] = {
                'error_rate_percent': error_rate,
                'critical_errors_per_hour': critical_errors,
                'total_errors_today': error_metrics.get('total_errors_today', 0)
            }

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Error rate check failed: {str(e)}")
            result['status'] = HealthStatus.DEGRADED
            result['issues'].append(f'Error monitoring unavailable: {str(e)}')

        return result

    def _check_cache_performance(self) -> Dict[str, Any]:
        """Check cache system performance"""
        result = {
            'status': HealthStatus.HEALTHY,
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'auto_degrade_recommended': False,
            'alert_required': False
        }

        try:
            # Test cache connectivity and performance
            start_time = time.time()
            test_key = f'health_check_{int(time.time())}'

            cache.set(test_key, 'test_value', 60)
            retrieved_value = cache.get(test_key)
            cache_latency = (time.time() - start_time) * 1000  # ms
            cache.delete(test_key)

            if retrieved_value != 'test_value':
                result['status'] = HealthStatus.CRITICAL
                result['issues'].append('Cache connectivity test failed')
                result['auto_degrade_recommended'] = True
                result['degradation_level'] = DegradationLevel.SYNCHRONOUS_MODE
                result['alert_required'] = True

            elif cache_latency > 100:  # 100ms threshold
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append(f'High cache latency: {cache_latency:.1f}ms')
                result['recommendations'].append('Investigate cache performance')

            # Check cache hit rate if available
            cache_stats = cache.get('cache_performance_stats', {})
            hit_rate = cache_stats.get('hit_rate_percent', 0)

            if hit_rate < 50 and hit_rate > 0:  # Only flag if we have data and it's low
                result['status'] = max(result['status'], HealthStatus.DEGRADED, key=lambda x: x.value)
                result['issues'].append(f'Low cache hit rate: {hit_rate}%')
                result['recommendations'].append('Review caching strategy')

            result['metrics'] = {
                'cache_latency_ms': cache_latency,
                'cache_working': retrieved_value == 'test_value',
                'hit_rate_percent': hit_rate
            }

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Cache check failed: {str(e)}")
            result['status'] = HealthStatus.CRITICAL
            result['issues'].append(f'Cache system failure: {str(e)}')
            result['auto_degrade_recommended'] = True
            result['degradation_level'] = DegradationLevel.SYNCHRONOUS_MODE

        return result

    def _check_database_performance(self) -> Dict[str, Any]:
        """Check database performance"""
        result = {
            'status': HealthStatus.HEALTHY,
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'auto_degrade_recommended': False,
            'alert_required': False
        }

        try:
            # Test database connectivity and performance
            start_time = time.time()

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            db_latency = (time.time() - start_time) * 1000  # ms

            if db_latency > 1000:  # 1 second threshold
                result['status'] = HealthStatus.CRITICAL
                result['issues'].append(f'High database latency: {db_latency:.1f}ms')
                result['alert_required'] = True

            elif db_latency > 500:  # 500ms threshold
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append(f'Elevated database latency: {db_latency:.1f}ms')
                result['recommendations'].append('Monitor database performance')

            # Check database connections
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT count(*)
                    FROM pg_stat_activity
                    WHERE state = 'active'
                """)
                active_connections = cursor.fetchone()[0]

                # Rough threshold - adjust based on your connection pool
                if active_connections > 80:
                    result['status'] = max(result['status'], HealthStatus.DEGRADED, key=lambda x: x.value)
                    result['issues'].append(f'High database connection count: {active_connections}')
                    result['recommendations'].append('Monitor connection pool usage')

            result['metrics'] = {
                'db_latency_ms': db_latency,
                'active_connections': active_connections
            }

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Database check failed: {str(e)}")
            result['status'] = HealthStatus.CRITICAL
            result['issues'].append(f'Database connectivity failure: {str(e)}')
            result['alert_required'] = True

        return result

    def _check_rate_limiting(self) -> Dict[str, Any]:
        """Check rate limiting effectiveness"""
        result = {
            'status': HealthStatus.HEALTHY,
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'auto_degrade_recommended': False,
            'alert_required': False
        }

        try:
            # Get rate limiting metrics
            rate_limit_metrics = cache.get('onboarding_rate_limit_metrics', {})

            if not rate_limit_metrics:
                result['recommendations'].append('Rate limiting metrics not available')
                return result

            # Check if rate limiting is being hit frequently
            rate_limit_hits = rate_limit_metrics.get('rate_limit_hits_per_hour', 0)

            if rate_limit_hits > 100:  # High rate limiting activity
                result['status'] = HealthStatus.DEGRADED
                result['issues'].append(f'High rate limiting activity: {rate_limit_hits} hits/hour')
                result['recommendations'].append('Review rate limiting thresholds or identify abuse')

            # Check for burst patterns
            burst_events = rate_limit_metrics.get('burst_events_per_hour', 0)
            if burst_events > 10:
                result['issues'].append(f'Frequent burst events: {burst_events}/hour')
                result['recommendations'].append('Investigate traffic patterns')

            result['metrics'] = {
                'rate_limit_hits_per_hour': rate_limit_hits,
                'burst_events_per_hour': burst_events
            }

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Rate limiting check failed: {str(e)}")
            result['issues'].append(f'Rate limiting monitoring error: {str(e)}')

        return result

    def _apply_auto_degradation(self, component: str, level: DegradationLevel) -> Optional[Dict[str, Any]]:
        """Apply automatic degradation strategy"""
        if level == self.degradation_state:
            return None  # Already at this level

        degradation_info = {
            'component': component,
            'level': level.value,
            'applied_at': timezone.now().isoformat(),
            'previous_level': self.degradation_state.value
        }

        try:
            if level == DegradationLevel.DISABLE_CHECKER_LLM:
                # Disable LLM checker temporarily
                cache.set('onboarding_disable_checker', True, 3600)  # 1 hour
                degradation_info['action'] = 'Disabled LLM checker to reduce latency'

            elif level == DegradationLevel.DISABLE_KB_GROUNDING:
                # Disable knowledge base grounding
                cache.set('onboarding_disable_kb', True, 1800)  # 30 minutes
                degradation_info['action'] = 'Disabled knowledge base grounding'

            elif level == DegradationLevel.SYNCHRONOUS_MODE:
                # Switch to synchronous processing
                cache.set('onboarding_force_sync', True, 1800)  # 30 minutes
                degradation_info['action'] = 'Switched to synchronous processing mode'

            elif level == DegradationLevel.DISABLE_ONBOARDING:
                # Completely disable onboarding
                cache.set('onboarding_emergency_disable', True, 7200)  # 2 hours
                degradation_info['action'] = 'Emergency disable of conversational onboarding'

            self.degradation_state = level

            logger.warning(
                f"Auto-degradation applied: {degradation_info['action']} "
                f"due to {component} issues"
            )

            return degradation_info

        except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
            logger.error(f"Failed to apply degradation: {str(e)}")
            return None

    def _generate_alert(self, component: str, component_result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate alert if conditions are met"""
        # Check cooldown period
        last_alert_key = f'last_alert_{component}'
        last_alert_time = cache.get(last_alert_key)

        if last_alert_time:
            time_since_alert = timezone.now() - last_alert_time
            if time_since_alert.total_seconds() < self.alert_cooldown:
                return None  # Still in cooldown

        alert = {
            'component': component,
            'status': component_result['status'].value,
            'issues': component_result.get('issues', []),
            'metrics': component_result.get('metrics', {}),
            'generated_at': timezone.now().isoformat(),
            'severity': 'critical' if component_result['status'] == HealthStatus.CRITICAL else 'warning'
        }

        # Set cooldown
        cache.set(last_alert_key, timezone.now(), self.alert_cooldown)

        logger.error(f"Health alert generated for {component}: {alert}")

        return alert

    def get_current_degradations(self) -> Dict[str, Any]:
        """Get current system degradation status"""
        return {
            'current_level': self.degradation_state.value,
            'active_degradations': {
                'checker_disabled': bool(cache.get('onboarding_disable_checker')),
                'kb_disabled': bool(cache.get('onboarding_disable_kb')),
                'sync_mode': bool(cache.get('onboarding_force_sync')),
                'emergency_disabled': bool(cache.get('onboarding_emergency_disable'))
            },
            'last_check': self.last_check_time.isoformat()
        }

    def reset_degradations(self, level: Optional[str] = None) -> Dict[str, Any]:
        """Reset degradations (admin function)"""
        reset_info = {
            'reset_at': timezone.now().isoformat(),
            'previous_level': self.degradation_state.value,
            'reset_items': []
        }

        if level is None or level == 'all':
            # Reset all degradations
            cache.delete('onboarding_disable_checker')
            cache.delete('onboarding_disable_kb')
            cache.delete('onboarding_force_sync')
            cache.delete('onboarding_emergency_disable')
            reset_info['reset_items'] = ['all']
            self.degradation_state = DegradationLevel.NONE

        else:
            # Reset specific degradation
            if level == 'checker':
                cache.delete('onboarding_disable_checker')
                reset_info['reset_items'].append('checker_disabled')
            elif level == 'kb':
                cache.delete('onboarding_disable_kb')
                reset_info['reset_items'].append('kb_disabled')
            elif level == 'sync':
                cache.delete('onboarding_force_sync')
                reset_info['reset_items'].append('sync_mode')
            elif level == 'emergency':
                cache.delete('onboarding_emergency_disable')
                reset_info['reset_items'].append('emergency_disabled')

        logger.info(f"Degradation reset: {reset_info}")
        return reset_info


# Global monitor instance
system_monitor = SystemMonitor()


def get_system_health() -> Dict[str, Any]:
    """Convenience function to get current system health"""
    return system_monitor.check_system_health()


def get_degradation_status() -> Dict[str, Any]:
    """Convenience function to get current degradation status"""
    return system_monitor.get_current_degradations()


def reset_system_degradations(level: Optional[str] = None) -> Dict[str, Any]:
    """Convenience function to reset degradations"""
    return system_monitor.reset_degradations(level)


def check_degradation_flag(flag_name: str) -> bool:
    """
    Check if a specific degradation flag is active

    Args:
        flag_name: One of 'checker', 'kb', 'sync', 'emergency'

    Returns:
        True if the degradation is active
    """
    flag_map = {
        'checker': 'onboarding_disable_checker',
        'kb': 'onboarding_disable_kb',
        'sync': 'onboarding_force_sync',
        'emergency': 'onboarding_emergency_disable'
    }

    cache_key = flag_map.get(flag_name)
    if cache_key:
        return bool(cache.get(cache_key))
    return False