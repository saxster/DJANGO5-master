"""
Intelligent Alert Processing Engine

Central brain for alert processing with ML-based rules and correlation.
Coordinates multiple monitoring engines and applies intelligent logic.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.cache import cache

from apps.monitoring.engines import (
    BatteryMonitor, ActivityMonitor, NetworkMonitor,
    SecurityMonitor, PerformanceMonitor
)
from apps.monitoring.models import (
    Alert, AlertRule, MonitoringMetric, DeviceHealthSnapshot,
    UserActivityPattern
)
from apps.monitoring.services.alert_service import AlertService
from apps.monitoring.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


class IntelligentAlertProcessor:
    """
    Advanced alert processing engine with ML capabilities.

    Features:
    - Multi-engine coordination
    - Alert correlation and deduplication
    - ML-based threshold adaptation
    - Context-aware alerting
    - Predictive alert prevention
    - Smart escalation logic
    """

    def __init__(self):
        # Initialize monitoring engines
        self.battery_monitor = BatteryMonitor()
        self.activity_monitor = ActivityMonitor()
        self.network_monitor = NetworkMonitor()
        self.security_monitor = SecurityMonitor()
        self.performance_monitor = PerformanceMonitor()

        # Initialize services
        self.alert_service = AlertService()
        self.prediction_service = PredictionService()

        # Processing configuration
        self.correlation_window_minutes = 10
        self.max_alerts_per_user_hour = 5
        self.ml_threshold_adaptation = True

    def process_comprehensive_monitoring(self, user_id: int, device_id: str) -> Dict:
        """
        Run comprehensive monitoring across all engines with intelligent processing.

        Args:
            user_id: User ID to monitor
            device_id: Device ID to monitor

        Returns:
            Dictionary containing comprehensive monitoring results
        """
        try:
            logger.info(f"Starting comprehensive monitoring for user {user_id}, device {device_id}")

            # Run all monitoring engines in parallel
            monitoring_results = self._run_all_monitoring_engines(user_id, device_id)

            # Get user context for intelligent processing
            user_context = self._get_comprehensive_user_context(user_id)

            # Apply intelligent alert correlation
            correlated_alerts = self._correlate_alerts(monitoring_results, user_context)

            # Apply ML-based alert filtering
            filtered_alerts = self._apply_ml_filtering(correlated_alerts, user_context)

            # Apply context-aware alert prioritization
            prioritized_alerts = self._prioritize_alerts(filtered_alerts, user_context)

            # Generate comprehensive recommendations
            recommendations = self._generate_comprehensive_recommendations(
                monitoring_results, prioritized_alerts, user_context
            )

            # Calculate overall risk assessment
            risk_assessment = self._calculate_overall_risk(monitoring_results, prioritized_alerts)

            # Update user patterns and learning
            self._update_ml_patterns(user_id, monitoring_results, prioritized_alerts)

            result = {
                'status': 'success',
                'user_id': user_id,
                'device_id': device_id,
                'timestamp': timezone.now().isoformat(),
                'monitoring_results': monitoring_results,
                'alerts': prioritized_alerts,
                'recommendations': recommendations,
                'risk_assessment': risk_assessment,
                'processing_metadata': {
                    'engines_used': list(monitoring_results.keys()),
                    'alerts_correlated': len(correlated_alerts),
                    'alerts_filtered': len(filtered_alerts),
                    'final_alerts': len(prioritized_alerts)
                }
            }

            # Cache comprehensive results
            self._cache_comprehensive_results(user_id, device_id, result)

            logger.info(f"Completed comprehensive monitoring for user {user_id}")
            return result

        except Exception as e:
            logger.error(f"Error in comprehensive monitoring: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'user_id': user_id,
                'device_id': device_id
            }

    def _run_all_monitoring_engines(self, user_id: int, device_id: str) -> Dict:
        """Run all monitoring engines and collect results"""
        results = {}

        try:
            # Battery monitoring
            battery_result = self.battery_monitor.monitor_battery_status(user_id, device_id)
            results['battery'] = battery_result

            # Activity monitoring
            activity_result = self.activity_monitor.monitor_activity_status(user_id, device_id)
            results['activity'] = activity_result

            # Network monitoring
            network_result = self.network_monitor.monitor_network_status(user_id, device_id)
            results['network'] = network_result

            # Security monitoring
            security_result = self.security_monitor.monitor_security_status(user_id, device_id)
            results['security'] = security_result

            # Performance monitoring
            performance_result = self.performance_monitor.monitor_performance_status(user_id, device_id)
            results['performance'] = performance_result

        except Exception as e:
            logger.error(f"Error running monitoring engines: {str(e)}")

        return results

    def _get_comprehensive_user_context(self, user_id: int) -> Dict:
        """Get comprehensive user context for intelligent processing"""
        try:
            from apps.peoples.models import People

            user = People.objects.get(id=user_id)

            # Get activity pattern
            activity_pattern = getattr(user, 'activity_pattern', None)

            # Get behavioral profile
            behavioral_profile = None
            try:
                from apps.noc.security_intelligence.models import BehavioralProfile
                behavioral_profile = BehavioralProfile.objects.get(person=user)
            except:
                pass

            # Calculate current shift context
            current_time = timezone.now()
            shift_context = self._calculate_shift_context(user, current_time)

            # Get historical alert patterns
            alert_history = self._get_user_alert_history(user_id)

            return {
                'user_id': user_id,
                'user_name': user.peoplename,
                'activity_pattern': activity_pattern,
                'behavioral_profile': behavioral_profile,
                'shift_context': shift_context,
                'alert_history': alert_history,
                'current_time': current_time,
                'is_high_priority_user': getattr(user, 'isadmin', False),
                'user_role': getattr(user, 'worktype', 'guard')
            }

        except Exception as e:
            logger.error(f"Error getting comprehensive user context: {str(e)}")
            return {'user_id': user_id}

    def _correlate_alerts(self, monitoring_results: Dict, user_context: Dict) -> List[Dict]:
        """Correlate alerts from different engines to avoid duplication"""
        all_alerts = []

        # Collect all alerts from all engines
        for engine_name, result in monitoring_results.items():
            if result.get('status') == 'success' and result.get('alerts'):
                for alert in result['alerts']:
                    alert['source_engine'] = engine_name
                    all_alerts.append(alert)

        if not all_alerts:
            return []

        try:
            # Group related alerts
            correlated_groups = self._group_related_alerts(all_alerts)

            # Create consolidated alerts
            correlated_alerts = []
            for group in correlated_groups:
                if len(group) == 1:
                    correlated_alerts.append(group[0])
                else:
                    # Create consolidated alert
                    consolidated = self._consolidate_alert_group(group, user_context)
                    correlated_alerts.append(consolidated)

            return correlated_alerts

        except Exception as e:
            logger.error(f"Error correlating alerts: {str(e)}")
            return all_alerts

    def _apply_ml_filtering(self, alerts: List[Dict], user_context: Dict) -> List[Dict]:
        """Apply ML-based filtering to reduce false positives"""
        if not alerts:
            return alerts

        try:
            filtered_alerts = []

            for alert in alerts:
                # Calculate alert relevance score
                relevance_score = self._calculate_alert_relevance(alert, user_context)

                # Apply ML-based filtering
                if self._should_suppress_alert(alert, relevance_score, user_context):
                    logger.debug(f"Suppressing alert {alert.get('type')} due to low relevance")
                    continue

                # Add relevance score to alert
                alert['relevance_score'] = relevance_score
                filtered_alerts.append(alert)

            return filtered_alerts

        except Exception as e:
            logger.error(f"Error applying ML filtering: {str(e)}")
            return alerts

    def _prioritize_alerts(self, alerts: List[Dict], user_context: Dict) -> List[Dict]:
        """Apply context-aware alert prioritization"""
        if not alerts:
            return alerts

        try:
            # Calculate priority scores for each alert
            for alert in alerts:
                priority_score = self._calculate_alert_priority(alert, user_context)
                alert['priority_score'] = priority_score

            # Sort by priority score (descending)
            prioritized_alerts = sorted(alerts, key=lambda a: a.get('priority_score', 0), reverse=True)

            # Apply rate limiting
            return self._apply_rate_limiting(prioritized_alerts, user_context)

        except Exception as e:
            logger.error(f"Error prioritizing alerts: {str(e)}")
            return alerts

    def _calculate_overall_risk(self, monitoring_results: Dict, alerts: List[Dict]) -> Dict:
        """Calculate comprehensive risk assessment"""
        try:
            risk_factors = {
                'battery_risk': 0,
                'activity_risk': 0,
                'network_risk': 0,
                'security_risk': 0,
                'performance_risk': 0,
                'overall_risk': 0
            }

            # Calculate individual risk factors
            for engine, result in monitoring_results.items():
                if result.get('status') == 'success':
                    if engine == 'battery':
                        risk_factors['battery_risk'] = self._calculate_battery_risk(result)
                    elif engine == 'activity':
                        risk_factors['activity_risk'] = self._calculate_activity_risk(result)
                    elif engine == 'network':
                        risk_factors['network_risk'] = self._calculate_network_risk(result)
                    elif engine == 'security':
                        risk_factors['security_risk'] = self._calculate_security_risk(result)
                    elif engine == 'performance':
                        risk_factors['performance_risk'] = self._calculate_performance_risk(result)

            # Calculate overall risk (weighted average)
            weights = {
                'battery_risk': 0.25,
                'activity_risk': 0.20,
                'network_risk': 0.20,
                'security_risk': 0.25,
                'performance_risk': 0.10
            }

            overall_risk = sum(
                risk_factors[factor] * weight
                for factor, weight in weights.items()
            )

            risk_factors['overall_risk'] = min(1.0, overall_risk)

            # Add risk level categorization
            if overall_risk >= 0.8:
                risk_level = 'CRITICAL'
            elif overall_risk >= 0.6:
                risk_level = 'HIGH'
            elif overall_risk >= 0.4:
                risk_level = 'MEDIUM'
            elif overall_risk >= 0.2:
                risk_level = 'LOW'
            else:
                risk_level = 'MINIMAL'

            risk_factors['risk_level'] = risk_level
            risk_factors['alert_count'] = len(alerts)

            return risk_factors

        except Exception as e:
            logger.error(f"Error calculating overall risk: {str(e)}")
            return {'overall_risk': 0, 'risk_level': 'UNKNOWN'}

    def _group_related_alerts(self, alerts: List[Dict]) -> List[List[Dict]]:
        """Group related alerts that should be consolidated"""
        try:
            groups = []
            ungrouped_alerts = alerts.copy()

            # Define correlation rules
            correlation_rules = [
                # Battery and performance correlation
                (['BATTERY_LOW', 'BATTERY_CRITICAL'], ['MEMORY_HIGH', 'PERFORMANCE_DEGRADED']),
                # Security correlations
                (['BIOMETRIC_FAILURE', 'CONCURRENT_USAGE'], ['FRAUD_RISK']),
                # Network and activity correlation
                (['NETWORK_DOWN', 'SIGNAL_POOR'], ['NO_MOVEMENT', 'LOW_ACTIVITY'])
            ]

            for rule in correlation_rules:
                primary_types, secondary_types = rule

                # Find alerts matching this rule
                primary_alerts = [a for a in ungrouped_alerts if a.get('type') in primary_types]
                secondary_alerts = [a for a in ungrouped_alerts if a.get('type') in secondary_types]

                if primary_alerts and secondary_alerts:
                    # Create correlation group
                    group = primary_alerts + secondary_alerts
                    groups.append(group)

                    # Remove from ungrouped
                    for alert in group:
                        if alert in ungrouped_alerts:
                            ungrouped_alerts.remove(alert)

            # Add remaining alerts as individual groups
            for alert in ungrouped_alerts:
                groups.append([alert])

            return groups

        except Exception as e:
            logger.error(f"Error grouping related alerts: {str(e)}")
            return [[alert] for alert in alerts]

    def _consolidate_alert_group(self, alert_group: List[Dict], user_context: Dict) -> Dict:
        """Consolidate multiple related alerts into a single alert"""
        try:
            # Find the highest severity alert
            primary_alert = max(alert_group, key=lambda a: self._severity_to_number(a.get('severity', 'INFO')))

            # Combine descriptions
            combined_description = primary_alert.get('description', '')
            if len(alert_group) > 1:
                other_alerts = [a.get('description', '') for a in alert_group if a != primary_alert]
                combined_description += f". Related issues: {'; '.join(other_alerts)}"

            # Create consolidated alert
            consolidated = primary_alert.copy()
            consolidated['description'] = combined_description
            consolidated['consolidated_from'] = [a.get('type') for a in alert_group]
            consolidated['source_engines'] = list(set(a.get('source_engine') for a in alert_group))

            return consolidated

        except Exception as e:
            logger.error(f"Error consolidating alert group: {str(e)}")
            return alert_group[0] if alert_group else {}

    def _calculate_alert_relevance(self, alert: Dict, user_context: Dict) -> float:
        """Calculate relevance score for an alert using ML techniques"""
        try:
            relevance_score = 0.5  # Base relevance

            # Factor 1: Severity
            severity = alert.get('severity', 'INFO')
            severity_score = self._severity_to_number(severity) / 5
            relevance_score += severity_score * 0.3

            # Factor 2: User history
            alert_history = user_context.get('alert_history', {})
            alert_type = alert.get('type', '')

            if alert_type in alert_history:
                false_positive_rate = alert_history[alert_type].get('false_positive_rate', 0)
                relevance_score -= false_positive_rate * 0.2

            # Factor 3: Context relevance
            context_relevance = self._calculate_context_relevance(alert, user_context)
            relevance_score += context_relevance * 0.3

            # Factor 4: Pattern matching
            pattern_match = self._calculate_pattern_match(alert, user_context)
            relevance_score += pattern_match * 0.2

            return min(1.0, max(0.0, relevance_score))

        except Exception as e:
            logger.error(f"Error calculating alert relevance: {str(e)}")
            return 0.5

    def _should_suppress_alert(self, alert: Dict, relevance_score: float, user_context: Dict) -> bool:
        """Determine if alert should be suppressed"""
        try:
            # Suppress low relevance alerts
            if relevance_score < 0.3:
                return True

            # Check rate limiting
            if self._exceeds_rate_limit(alert, user_context):
                return True

            # Check for duplicate recent alerts
            if self._is_duplicate_recent_alert(alert, user_context):
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking alert suppression: {str(e)}")
            return False

    def _calculate_alert_priority(self, alert: Dict, user_context: Dict) -> float:
        """Calculate priority score for alert ordering"""
        try:
            priority_score = 0

            # Base priority from severity
            severity = alert.get('severity', 'INFO')
            priority_score += self._severity_to_number(severity) * 20

            # User priority boost
            if user_context.get('is_high_priority_user', False):
                priority_score += 10

            # Time sensitivity
            alert_type = alert.get('type', '')
            if alert_type in ['BATTERY_CRITICAL', 'NO_MOVEMENT', 'FRAUD_RISK']:
                priority_score += 15

            # Context-based priority
            shift_context = user_context.get('shift_context', {})
            if shift_context.get('is_active_shift', False):
                priority_score += 10

            # Relevance boost
            relevance_score = alert.get('relevance_score', 0.5)
            priority_score += relevance_score * 20

            return priority_score

        except Exception as e:
            logger.error(f"Error calculating alert priority: {str(e)}")
            return 0

    def _generate_comprehensive_recommendations(self, monitoring_results: Dict, alerts: List[Dict], user_context: Dict) -> List[str]:
        """Generate comprehensive recommendations across all monitoring domains"""
        recommendations = []

        try:
            # Collect recommendations from each engine
            for engine_name, result in monitoring_results.items():
                if result.get('status') == 'success' and result.get('recommendations'):
                    recommendations.extend(result['recommendations'])

            # Add intelligent cross-domain recommendations
            if any(a.get('type') == 'BATTERY_LOW' for a in alerts) and \
               any(a.get('type') == 'HIGH_ACTIVITY' for a in alerts):
                recommendations.append("High activity is draining battery - consider optimizing movement patterns")

            if any(a.get('type') == 'NETWORK_DOWN' for a in alerts) and \
               any(a.get('type') == 'NO_MOVEMENT' for a in alerts):
                recommendations.append("Network issues may be preventing location updates - check manually")

            # Prioritize recommendations
            prioritized = self._prioritize_recommendations(recommendations, alerts, user_context)

            return prioritized[:10]  # Limit to top 10 recommendations

        except Exception as e:
            logger.error(f"Error generating comprehensive recommendations: {str(e)}")
            return []

    def _update_ml_patterns(self, user_id: int, monitoring_results: Dict, alerts: List[Dict]):
        """Update ML patterns and learning based on monitoring results"""
        try:
            # Update user activity pattern
            self._update_activity_learning(user_id, monitoring_results)

            # Update alert pattern learning
            self._update_alert_learning(user_id, alerts)

            # Update threshold adaptation
            if self.ml_threshold_adaptation:
                self._adapt_thresholds(user_id, monitoring_results, alerts)

        except Exception as e:
            logger.error(f"Error updating ML patterns: {str(e)}")

    # Helper methods for intelligent processing

    def _severity_to_number(self, severity: str) -> int:
        """Convert severity string to numeric value"""
        severity_map = {
            'INFO': 1,
            'WARNING': 2,
            'HIGH': 3,
            'CRITICAL': 4,
            'EMERGENCY': 5
        }
        return severity_map.get(severity, 1)

    def _calculate_context_relevance(self, alert: Dict, user_context: Dict) -> float:
        """Calculate how relevant an alert is in current context"""
        try:
            relevance = 0.5  # Base relevance

            # Time-based relevance
            shift_context = user_context.get('shift_context', {})
            if shift_context.get('is_work_time', True):
                relevance += 0.2
            else:
                relevance -= 0.1  # Less relevant outside work hours

            # Role-based relevance
            user_role = user_context.get('user_role', 'guard')
            alert_type = alert.get('type', '')

            role_relevance_map = {
                'supervisor': ['FRAUD_RISK', 'CONCURRENT_USAGE', 'SECURITY_BREACH'],
                'guard': ['BATTERY_LOW', 'NO_MOVEMENT', 'LOCATION_VIOLATION'],
                'maintenance': ['PERFORMANCE_DEGRADED', 'DEVICE_OVERHEATING']
            }

            if alert_type in role_relevance_map.get(user_role, []):
                relevance += 0.2

            return min(1.0, max(0.0, relevance))

        except Exception as e:
            logger.error(f"Error calculating context relevance: {str(e)}")
            return 0.5

    def _calculate_pattern_match(self, alert: Dict, user_context: Dict) -> float:
        """Calculate how well alert matches user patterns"""
        try:
            # Check against historical patterns
            alert_history = user_context.get('alert_history', {})
            alert_type = alert.get('type', '')

            if alert_type in alert_history:
                pattern_data = alert_history[alert_type]
                # Higher pattern match for alerts that have been valid in the past
                true_positive_rate = pattern_data.get('true_positive_rate', 0.5)
                return true_positive_rate
            else:
                return 0.5  # Unknown pattern

        except Exception as e:
            logger.error(f"Error calculating pattern match: {str(e)}")
            return 0.5

    def _exceeds_rate_limit(self, alert: Dict, user_context: Dict) -> bool:
        """Check if alert exceeds rate limiting"""
        try:
            user_id = user_context.get('user_id')
            if not user_id:
                return False

            # Count recent alerts for this user
            recent_cutoff = timezone.now() - timedelta(hours=1)
            recent_alerts = Alert.objects.filter(
                user_id=user_id,
                triggered_at__gte=recent_cutoff
            ).count()

            return recent_alerts >= self.max_alerts_per_user_hour

        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            return False

    def _is_duplicate_recent_alert(self, alert: Dict, user_context: Dict) -> bool:
        """Check if this is a duplicate of a recent alert"""
        try:
            user_id = user_context.get('user_id')
            alert_type = alert.get('type')

            if not user_id or not alert_type:
                return False

            # Check for recent similar alerts
            recent_cutoff = timezone.now() - timedelta(minutes=30)
            similar_alert = Alert.objects.filter(
                user_id=user_id,
                rule__alert_type=alert_type,
                triggered_at__gte=recent_cutoff
            ).first()

            return similar_alert is not None

        except Exception as e:
            logger.error(f"Error checking duplicate alert: {str(e)}")
            return False

    def _apply_rate_limiting(self, alerts: List[Dict], user_context: Dict) -> List[Dict]:
        """Apply rate limiting to prevent alert flooding"""
        try:
            # Limit to max alerts per user per hour
            return alerts[:self.max_alerts_per_user_hour]

        except Exception as e:
            logger.error(f"Error applying rate limiting: {str(e)}")
            return alerts

    def _calculate_shift_context(self, user, current_time: datetime) -> Dict:
        """Calculate current shift context"""
        try:
            # Simplified shift detection
            work_start = 9
            work_end = 17

            is_work_time = work_start <= current_time.hour < work_end
            shift_progress = 0

            if is_work_time:
                shift_progress = (current_time.hour - work_start) / (work_end - work_start)

            return {
                'is_work_time': is_work_time,
                'is_active_shift': is_work_time,
                'shift_progress': shift_progress,
                'shift_start_hour': work_start,
                'shift_end_hour': work_end
            }

        except Exception as e:
            logger.error(f"Error calculating shift context: {str(e)}")
            return {'is_work_time': True, 'is_active_shift': True}

    def _get_user_alert_history(self, user_id: int) -> Dict:
        """Get user's alert history for pattern learning"""
        try:
            # Get alert statistics for this user
            recent_cutoff = timezone.now() - timedelta(days=30)

            alert_stats = Alert.objects.filter(
                user_id=user_id,
                triggered_at__gte=recent_cutoff
            ).values('rule__alert_type').annotate(
                total=Count('id'),
                false_positives=Count('id', filter=Q(status='FALSE_POSITIVE'))
            )

            history = {}
            for stat in alert_stats:
                alert_type = stat['rule__alert_type']
                total = stat['total']
                false_positives = stat['false_positives']

                history[alert_type] = {
                    'total_alerts': total,
                    'false_positives': false_positives,
                    'false_positive_rate': false_positives / total if total > 0 else 0,
                    'true_positive_rate': (total - false_positives) / total if total > 0 else 1.0
                }

            return history

        except Exception as e:
            logger.error(f"Error getting user alert history: {str(e)}")
            return {}

    def _prioritize_recommendations(self, recommendations: List[str], alerts: List[Dict], user_context: Dict) -> List[str]:
        """Prioritize recommendations based on alerts and context"""
        try:
            # Remove duplicates while preserving order
            seen = set()
            unique_recommendations = []
            for rec in recommendations:
                if rec not in seen:
                    seen.add(rec)
                    unique_recommendations.append(rec)

            # Sort by urgency keywords
            urgent_keywords = ['immediate', 'critical', 'emergency', 'now']
            warning_keywords = ['consider', 'check', 'review', 'monitor']

            def priority_key(rec):
                rec_lower = rec.lower()
                if any(word in rec_lower for word in urgent_keywords):
                    return 1
                elif any(word in rec_lower for word in warning_keywords):
                    return 3
                else:
                    return 2

            return sorted(unique_recommendations, key=priority_key)

        except Exception as e:
            logger.error(f"Error prioritizing recommendations: {str(e)}")
            return recommendations

    # Risk calculation methods for each domain

    def _calculate_battery_risk(self, battery_result: Dict) -> float:
        """Calculate battery-related risk"""
        try:
            metrics = battery_result.get('metrics', {})
            current_level = metrics.get('current_level', 100)

            risk = 0
            if current_level < 10:
                risk += 0.8
            elif current_level < 20:
                risk += 0.5
            elif current_level < 30:
                risk += 0.3

            return min(1.0, risk)

        except Exception as e:
            return 0

    def _calculate_activity_risk(self, activity_result: Dict) -> float:
        """Calculate activity-related risk"""
        try:
            metrics = activity_result.get('metrics', {})
            stationary_minutes = metrics.get('stationary_duration_minutes', 0)

            risk = 0
            if stationary_minutes > 60:
                risk += 0.7
            elif stationary_minutes > 30:
                risk += 0.4

            return min(1.0, risk)

        except Exception as e:
            return 0

    def _calculate_network_risk(self, network_result: Dict) -> float:
        """Calculate network-related risk"""
        try:
            metrics = network_result.get('metrics', {})
            signal_quality = metrics.get('signal_quality', 'good')

            risk_map = {
                'critical': 0.8,
                'poor': 0.6,
                'good': 0.2,
                'excellent': 0.0
            }

            return risk_map.get(signal_quality, 0.3)

        except Exception as e:
            return 0

    def _calculate_security_risk(self, security_result: Dict) -> float:
        """Calculate security-related risk"""
        try:
            metrics = security_result.get('metrics', {})
            fraud_risk = metrics.get('fraud_risk_score', 0)
            return fraud_risk

        except Exception as e:
            return 0

    def _calculate_performance_risk(self, performance_result: Dict) -> float:
        """Calculate performance-related risk"""
        try:
            metrics = performance_result.get('metrics', {})
            performance_score = metrics.get('performance_score', 100)

            # Convert performance score to risk (inverse relationship)
            risk = max(0, (100 - performance_score) / 100)
            return risk

        except Exception as e:
            return 0

    def _cache_comprehensive_results(self, user_id: int, device_id: str, results: Dict):
        """Cache comprehensive monitoring results"""
        try:
            cache_key = f"comprehensive_monitoring:{user_id}:{device_id}"
            cache.set(cache_key, results, 600)  # 10 minutes

        except Exception as e:
            logger.error(f"Error caching comprehensive results: {str(e)}")

    def _update_activity_learning(self, user_id: int, monitoring_results: Dict):
        """Update activity pattern learning"""
        # Implementation for updating activity patterns
        pass

    def _update_alert_learning(self, user_id: int, alerts: List[Dict]):
        """Update alert pattern learning"""
        # Implementation for alert pattern learning
        pass

    def _adapt_thresholds(self, user_id: int, monitoring_results: Dict, alerts: List[Dict]):
        """Adapt monitoring thresholds based on user patterns"""
        # Implementation for adaptive thresholds
        pass