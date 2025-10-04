"""
Performance Monitoring Engine

Monitors device performance including memory, thermal, storage, and app performance.
Provides predictive maintenance alerts and optimization recommendations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.utils import timezone

from apps.activity.models import DeviceEventlog
from apps.monitoring.services.alert_service import AlertService

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Device performance monitoring with predictive maintenance.

    Features:
    - Memory usage tracking
    - Storage capacity monitoring
    - Thermal state monitoring
    - App performance tracking
    - Performance degradation prediction
    """

    def __init__(self):
        self.alert_service = AlertService()

        # Performance thresholds
        self.CRITICAL_MEMORY_THRESHOLD = 90    # % memory usage
        self.WARNING_MEMORY_THRESHOLD = 80     # % memory usage
        self.CRITICAL_STORAGE_THRESHOLD = 95   # % storage usage
        self.WARNING_STORAGE_THRESHOLD = 85    # % storage usage

        # Thermal thresholds
        self.THERMAL_WARNING_STATES = ['serious', 'critical']
        self.THERMAL_CRITICAL_STATES = ['critical']

    def monitor_performance_status(self, user_id: int, device_id: str) -> Dict:
        """Monitor device performance status"""
        try:
            # Get current performance data
            current_data = self._get_current_performance_data(device_id)
            if not current_data:
                return {'status': 'no_data', 'alerts': []}

            # Get historical performance data
            historical_data = self._get_historical_performance_data(device_id, hours=6)

            # Calculate performance metrics
            metrics = self._calculate_performance_metrics(current_data, historical_data)

            # Analyze performance trends
            trends = self._analyze_performance_trends(historical_data)

            # Evaluate performance alerts
            alerts = self._evaluate_performance_alerts(
                user_id, device_id, current_data, metrics, trends
            )

            return {
                'status': 'success',
                'current_performance': current_data,
                'metrics': metrics,
                'trends': trends,
                'alerts': alerts,
                'recommendations': self._generate_performance_recommendations(metrics, trends)
            }

        except Exception as e:
            logger.error(f"Error monitoring performance for user {user_id}: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e), 'alerts': []}

    def _get_current_performance_data(self, device_id: str) -> Optional[Dict]:
        """Get current device performance data"""
        try:
            latest_entry = DeviceEventlog.objects.filter(
                deviceid=device_id
            ).order_by('-receivedon').first()

            if not latest_entry:
                return None

            return {
                'memory_internal': self._parse_memory(latest_entry.availintmemory),
                'memory_external': self._parse_memory(latest_entry.availextmemory),
                'platform_version': latest_entry.platformversion,
                'app_version': latest_entry.applicationversion,
                'model_name': latest_entry.modelname,
                'installed_apps': latest_entry.installedapps,
                'timestamp': latest_entry.receivedon,
                'battery_level': self._safe_int(latest_entry.batterylevel),
                'signal_bandwidth': latest_entry.signalbandwidth
            }

        except Exception as e:
            logger.error(f"Error getting current performance data: {str(e)}")
            return None

    def _get_historical_performance_data(self, device_id: str, hours: int = 6) -> List[Dict]:
        """Get historical performance data"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)

            entries = DeviceEventlog.objects.filter(
                deviceid=device_id,
                receivedon__gte=cutoff_time
            ).order_by('receivedon')

            return [{
                'timestamp': entry.receivedon,
                'memory_internal': self._parse_memory(entry.availintmemory),
                'memory_external': self._parse_memory(entry.availextmemory),
                'battery_level': self._safe_int(entry.batterylevel),
                'app_version': entry.applicationversion,
                'platform_version': entry.platformversion
            } for entry in entries]

        except Exception as e:
            logger.error(f"Error getting historical performance data: {str(e)}")
            return []

    def _calculate_performance_metrics(self, current_data: Dict, historical_data: List[Dict]) -> Dict:
        """Calculate comprehensive performance metrics"""
        metrics = {
            'memory_usage_percentage': 0,
            'storage_usage_percentage': 0,
            'performance_score': 100,
            'memory_trend': 'stable',
            'storage_trend': 'stable',
            'app_stability_score': 100,
            'system_health_score': 100
        }

        try:
            # Calculate current memory usage
            internal_mem = current_data.get('memory_internal', 0)
            if internal_mem > 0:
                # Assuming total memory can be estimated or configured
                total_memory = 4000  # 4GB default
                used_memory = total_memory - internal_mem
                metrics['memory_usage_percentage'] = (used_memory / total_memory) * 100

            # Calculate storage usage (simplified)
            external_mem = current_data.get('memory_external', 0)
            if external_mem > 0:
                total_storage = 32000  # 32GB default
                used_storage = total_storage - external_mem
                metrics['storage_usage_percentage'] = (used_storage / total_storage) * 100

            # Analyze historical trends
            if len(historical_data) >= 5:
                metrics.update(self._calculate_performance_trends(historical_data))

            # Calculate overall performance score
            metrics['performance_score'] = self._calculate_overall_performance_score(metrics)

        except Exception as e:
            logger.error(f"Error calculating performance metrics: {str(e)}")

        return metrics

    def _calculate_performance_trends(self, historical_data: List[Dict]) -> Dict:
        """Calculate performance trends from historical data"""
        trends = {
            'memory_trend': 'stable',
            'storage_trend': 'stable',
            'performance_degradation': False
        }

        try:
            # Analyze memory trend
            memory_values = [self._parse_memory(d.get('memory_internal', 0)) for d in historical_data]
            memory_values = [v for v in memory_values if v > 0]

            if len(memory_values) >= 3:
                x = np.arange(len(memory_values))
                slope = np.polyfit(x, memory_values, 1)[0]

                if slope < -50:  # Decreasing available memory
                    trends['memory_trend'] = 'degrading'
                elif slope > 50:  # Increasing available memory
                    trends['memory_trend'] = 'improving'

            # Detect performance degradation patterns
            if trends['memory_trend'] == 'degrading':
                trends['performance_degradation'] = True

        except Exception as e:
            logger.error(f"Error calculating performance trends: {str(e)}")

        return trends

    def _analyze_performance_trends(self, historical_data: List[Dict]) -> Dict:
        """Analyze comprehensive performance trends"""
        return self._calculate_performance_trends(historical_data)

    def _evaluate_performance_alerts(self, user_id: int, device_id: str, current_data: Dict,
                                   metrics: Dict, trends: Dict) -> List[Dict]:
        """Evaluate performance conditions and create alerts"""
        alerts = []

        try:
            # Memory usage alerts
            memory_usage = metrics.get('memory_usage_percentage', 0)
            if memory_usage >= self.CRITICAL_MEMORY_THRESHOLD:
                alert = self._create_performance_alert(
                    user_id, device_id, 'MEMORY_CRITICAL',
                    f"Critical memory usage: {memory_usage:.1f}%",
                    'CRITICAL', current_data, metrics
                )
                alerts.append(alert)
            elif memory_usage >= self.WARNING_MEMORY_THRESHOLD:
                alert = self._create_performance_alert(
                    user_id, device_id, 'MEMORY_HIGH',
                    f"High memory usage: {memory_usage:.1f}%",
                    'WARNING', current_data, metrics
                )
                alerts.append(alert)

            # Storage usage alerts
            storage_usage = metrics.get('storage_usage_percentage', 0)
            if storage_usage >= self.CRITICAL_STORAGE_THRESHOLD:
                alert = self._create_performance_alert(
                    user_id, device_id, 'STORAGE_FULL',
                    f"Storage nearly full: {storage_usage:.1f}%",
                    'HIGH', current_data, metrics
                )
                alerts.append(alert)

            # Performance degradation alert
            if trends.get('performance_degradation', False):
                alert = self._create_performance_alert(
                    user_id, device_id, 'PERFORMANCE_DEGRADED',
                    "Performance degradation detected",
                    'WARNING', current_data, metrics
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error evaluating performance alerts: {str(e)}")

        return [alert for alert in alerts if alert is not None]

    def _create_performance_alert(self, user_id: int, device_id: str, alert_type: str,
                                 description: str, severity: str, current_data: Dict, metrics: Dict) -> Optional[Dict]:
        """Create a performance-related alert"""
        try:
            alert_data = {
                'user_id': user_id,
                'device_id': device_id,
                'alert_type': alert_type,
                'severity': severity,
                'title': f"Performance Alert: {alert_type.replace('_', ' ').title()}",
                'description': description,
                'alert_data': {
                    'memory_usage_percentage': metrics.get('memory_usage_percentage', 0),
                    'storage_usage_percentage': metrics.get('storage_usage_percentage', 0),
                    'performance_score': metrics.get('performance_score', 100),
                    'device_model': current_data.get('model_name', 'Unknown'),
                    'timestamp': timezone.now().isoformat()
                },
                'context_data': {
                    'performance_metrics': metrics,
                    'device_info': {
                        'model': current_data.get('model_name'),
                        'app_version': current_data.get('app_version'),
                        'platform_version': current_data.get('platform_version')
                    }
                }
            }

            alert = self.alert_service.create_alert(alert_data)

            if alert:
                return {
                    'alert_id': str(alert.alert_id),
                    'type': alert_type,
                    'severity': severity,
                    'description': description,
                    'created_at': alert.triggered_at.isoformat()
                }

        except Exception as e:
            logger.error(f"Error creating performance alert: {str(e)}")

        return None

    def _calculate_overall_performance_score(self, metrics: Dict) -> int:
        """Calculate overall performance score"""
        try:
            base_score = 100

            # Deduct for high memory usage
            memory_usage = metrics.get('memory_usage_percentage', 0)
            if memory_usage > 80:
                base_score -= (memory_usage - 80) * 2

            # Deduct for high storage usage
            storage_usage = metrics.get('storage_usage_percentage', 0)
            if storage_usage > 80:
                base_score -= (storage_usage - 80) * 1.5

            return max(0, int(base_score))

        except Exception as e:
            logger.error(f"Error calculating performance score: {str(e)}")
            return 50

    def _generate_performance_recommendations(self, metrics: Dict, trends: Dict) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []

        try:
            memory_usage = metrics.get('memory_usage_percentage', 0)
            if memory_usage > 80:
                recommendations.append("Close unused applications to free memory")
                recommendations.append("Restart device if memory usage remains high")

            storage_usage = metrics.get('storage_usage_percentage', 0)
            if storage_usage > 85:
                recommendations.append("Delete unnecessary files or photos")
                recommendations.append("Clear app cache to free storage space")

            if trends.get('performance_degradation', False):
                recommendations.append("Consider device optimization or maintenance")
                recommendations.append("Update apps to latest versions")

        except Exception as e:
            logger.error(f"Error generating performance recommendations: {str(e)}")

        return recommendations

    # Helper methods

    def _parse_memory(self, memory_str: str) -> float:
        """Parse memory string to MB value"""
        try:
            if not memory_str or memory_str == 'NA':
                return 0

            # Remove units and convert to float
            clean_str = memory_str.replace('MB', '').replace('GB', '').replace(',', '').strip()
            value = float(clean_str)

            # Convert GB to MB if needed
            if 'GB' in memory_str:
                value *= 1024

            return value

        except (ValueError, TypeError):
            return 0

    def _safe_int(self, value, default=0):
        """Safely convert value to integer"""
        if value == 'NA' or value is None:
            return default
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return default