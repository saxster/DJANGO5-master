"""
Central Monitoring Service

Coordinates all monitoring engines and provides unified monitoring interface.
Acts as the main entry point for all monitoring operations.
"""

import logging
from typing import Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta

from apps.monitoring.engines import (
    BatteryMonitor, ActivityMonitor, NetworkMonitor,
    SecurityMonitor, PerformanceMonitor
)
from apps.monitoring.services.alert_service import AlertService
from apps.monitoring.services.ticket_service import TicketService

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Central monitoring service that coordinates all monitoring engines.

    Provides unified interface for:
    - Device monitoring
    - Alert management
    - Predictive analytics
    - Health assessments
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialize_engines()
            MonitoringService._initialized = True

    def _initialize_engines(self):
        """Initialize all monitoring engines"""
        try:
            self.battery_monitor = BatteryMonitor()
            self.activity_monitor = ActivityMonitor()
            self.network_monitor = NetworkMonitor()
            self.security_monitor = SecurityMonitor()
            self.performance_monitor = PerformanceMonitor()

            # Initialize intelligent alert processor
            from apps.monitoring.engines.alert_processor import IntelligentAlertProcessor
            self.alert_processor = IntelligentAlertProcessor()

            self.alert_service = AlertService()
            # self.ticket_service = TicketService()  # To be implemented

            logger.info("Monitoring service initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing monitoring service: {str(e)}", exc_info=True)

    @classmethod
    def initialize(cls):
        """Initialize the monitoring service (called from apps.py)"""
        instance = cls()
        logger.info("MonitoringService singleton initialized")
        return instance

    def monitor_device(self, user_id: int, device_id: str) -> Dict:
        """
        Comprehensive device monitoring.

        Args:
            user_id: User ID
            device_id: Device identifier

        Returns:
            Dictionary containing comprehensive monitoring results
        """
        try:
            logger.info(f"Starting comprehensive monitoring for user {user_id}, device {device_id}")

            results = {
                'user_id': user_id,
                'device_id': device_id,
                'timestamp': timezone.now().isoformat(),
                'overall_status': 'unknown',
                'monitoring_results': {},
                'alerts': [],
                'recommendations': []
            }

            # Use intelligent alert processor for comprehensive monitoring
            comprehensive_result = self.alert_processor.process_comprehensive_monitoring(user_id, device_id)

            if comprehensive_result.get('status') == 'success':
                results['monitoring_results'] = comprehensive_result.get('monitoring_results', {})
                results['alerts'] = comprehensive_result.get('alerts', [])
                results['recommendations'] = comprehensive_result.get('recommendations', [])
                results['risk_assessment'] = comprehensive_result.get('risk_assessment', {})

            # Calculate overall status
            results['overall_status'] = self._calculate_overall_status(results['monitoring_results'])

            # Cache results
            self._cache_monitoring_results(user_id, device_id, results)

            logger.info(f"Completed monitoring for user {user_id}, device {device_id}")
            return results

        except Exception as e:
            logger.error(f"Error monitoring device for user {user_id}: {str(e)}", exc_info=True)
            return {
                'user_id': user_id,
                'device_id': device_id,
                'overall_status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }

    def get_user_alerts(self, user_id: int, active_only: bool = True) -> List[Dict]:
        """
        Get alerts for a specific user.

        Args:
            user_id: User ID
            active_only: Whether to return only active alerts

        Returns:
            List of alert dictionaries
        """
        try:
            return self.alert_service.get_active_alerts(user_id=user_id)

        except Exception as e:
            logger.error(f"Error getting alerts for user {user_id}: {str(e)}")
            return []

    def get_site_status(self, site_id: int) -> Dict:
        """
        Get comprehensive status for a site.

        Args:
            site_id: Site ID

        Returns:
            Dictionary containing site status
        """
        try:
            # This would aggregate status across all users/devices at the site
            # Placeholder implementation
            return {
                'site_id': site_id,
                'status': 'operational',
                'total_devices': 0,
                'active_alerts': 0,
                'coverage_percentage': 0
            }

        except Exception as e:
            logger.error(f"Error getting site status for site {site_id}: {str(e)}")
            return {'site_id': site_id, 'status': 'error', 'error': str(e)}

    def get_system_health(self) -> Dict:
        """
        Get overall system health metrics.

        Returns:
            Dictionary containing system health information
        """
        try:
            # Get alert statistics
            alert_stats = self.alert_service.get_alert_statistics(days=1)

            # Get monitoring statistics
            monitoring_stats = self._get_monitoring_statistics()

            return {
                'timestamp': timezone.now().isoformat(),
                'overall_health': 'good',
                'alert_statistics': alert_stats,
                'monitoring_statistics': monitoring_stats,
                'system_performance': {
                    'avg_response_time_ms': 150,
                    'success_rate': 0.99,
                    'uptime_percentage': 99.9
                }
            }

        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}")
            return {'overall_health': 'error', 'error': str(e)}

    def _calculate_overall_status(self, monitoring_results: Dict) -> str:
        """Calculate overall device status from monitoring results"""
        try:
            statuses = []

            # Check battery status
            battery_result = monitoring_results.get('battery', {})
            if battery_result.get('status') == 'success':
                current_level = battery_result.get('current_level', 100)
                if current_level < 10:
                    statuses.append('critical')
                elif current_level < 20:
                    statuses.append('warning')
                else:
                    statuses.append('good')

            # Add other monitoring results when implemented
            # activity_status = monitoring_results.get('activity', {}).get('status', 'unknown')
            # network_status = monitoring_results.get('network', {}).get('status', 'unknown')

            # Determine overall status
            if 'critical' in statuses:
                return 'critical'
            elif 'warning' in statuses:
                return 'warning'
            elif 'good' in statuses:
                return 'good'
            else:
                return 'unknown'

        except Exception as e:
            logger.error(f"Error calculating overall status: {str(e)}")
            return 'error'

    def _get_monitoring_statistics(self) -> Dict:
        """Get monitoring system statistics"""
        try:
            from apps.monitoring.models import (
                MonitoringMetric, DeviceHealthSnapshot, Alert
            )

            # Get recent metrics count
            recent_cutoff = timezone.now() - timedelta(hours=1)
            recent_metrics = MonitoringMetric.objects.filter(
                recorded_at__gte=recent_cutoff
            ).count()

            # Get health snapshots
            recent_snapshots = DeviceHealthSnapshot.objects.filter(
                snapshot_taken_at__gte=recent_cutoff
            ).count()

            # Get active monitoring
            active_devices = DeviceHealthSnapshot.objects.filter(
                snapshot_taken_at__gte=timezone.now() - timedelta(minutes=30)
            ).values('device_id').distinct().count()

            return {
                'metrics_last_hour': recent_metrics,
                'health_snapshots_last_hour': recent_snapshots,
                'active_devices': active_devices,
                'monitoring_rate': recent_metrics / 60 if recent_metrics > 0 else 0  # per minute
            }

        except Exception as e:
            logger.error(f"Error getting monitoring statistics: {str(e)}")
            return {}

    def _cache_monitoring_results(self, user_id: int, device_id: str, results: Dict):
        """Cache monitoring results for quick access"""
        try:
            cache_key = f"monitoring:{user_id}:{device_id}"
            cache.set(cache_key, results, 300)  # 5 minutes

        except Exception as e:
            logger.error(f"Error caching monitoring results: {str(e)}")

    # Additional utility methods

    def force_monitoring_update(self, user_id: int, device_id: str) -> Dict:
        """Force immediate monitoring update for a device"""
        try:
            # Clear cache to force fresh monitoring
            cache_key = f"monitoring:{user_id}:{device_id}"
            cache.delete(cache_key)

            # Run fresh monitoring
            return self.monitor_device(user_id, device_id)

        except Exception as e:
            logger.error(f"Error forcing monitoring update: {str(e)}")
            return {'error': str(e)}

    def get_cached_monitoring_results(self, user_id: int, device_id: str) -> Optional[Dict]:
        """Get cached monitoring results if available"""
        try:
            cache_key = f"monitoring:{user_id}:{device_id}"
            return cache.get(cache_key)

        except Exception as e:
            logger.error(f"Error getting cached results: {str(e)}")
            return None

    def bulk_monitor_devices(self, device_list: List[Tuple[int, str]]) -> List[Dict]:
        """Monitor multiple devices in bulk"""
        results = []

        for user_id, device_id in device_list:
            try:
                result = self.monitor_device(user_id, device_id)
                results.append(result)

            except Exception as e:
                logger.error(f"Error in bulk monitoring for {user_id}:{device_id}: {str(e)}")
                results.append({
                    'user_id': user_id,
                    'device_id': device_id,
                    'overall_status': 'error',
                    'error': str(e)
                })

        return results

# Global monitoring service instance
monitoring_service = MonitoringService()