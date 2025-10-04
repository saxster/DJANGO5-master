"""
Network Connectivity Monitoring Engine

Monitors network connectivity, signal strength, and communication reliability.
Provides alerts for network issues that could impact operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from django.utils import timezone

from apps.activity.models import DeviceEventlog
from apps.monitoring.services.alert_service import AlertService

logger = logging.getLogger(__name__)


class NetworkMonitor:
    """
    Network connectivity and signal strength monitoring.

    Features:
    - Signal strength tracking and trends
    - Network disconnection detection
    - Data usage anomaly detection
    - Coverage gap identification
    - Network provider analysis
    """

    def __init__(self):
        self.alert_service = AlertService()

        # Signal strength thresholds (in dBm or bars)
        self.CRITICAL_SIGNAL_THRESHOLD = -110  # Very poor signal
        self.POOR_SIGNAL_THRESHOLD = -100     # Poor signal
        self.GOOD_SIGNAL_THRESHOLD = -80      # Good signal

        # Network monitoring thresholds
        self.DISCONNECTION_MINUTES = 10      # Alert if offline for 10+ minutes
        self.DATA_USAGE_ANOMALY_FACTOR = 3   # Alert if 3x normal usage

    def monitor_network_status(self, user_id: int, device_id: str) -> Dict:
        """Monitor network connectivity and signal strength"""
        try:
            # Get current network data
            current_data = self._get_current_network_data(device_id)
            if not current_data:
                return {'status': 'no_data', 'alerts': []}

            # Get historical network data
            historical_data = self._get_historical_network_data(device_id, hours=4)

            # Calculate network metrics
            metrics = self._calculate_network_metrics(current_data, historical_data)

            # Analyze connectivity patterns
            connectivity_analysis = self._analyze_connectivity_patterns(historical_data)

            # Evaluate network alerts
            alerts = self._evaluate_network_alerts(
                user_id, device_id, current_data, metrics, connectivity_analysis
            )

            return {
                'status': 'success',
                'current_network': current_data,
                'metrics': metrics,
                'connectivity_analysis': connectivity_analysis,
                'alerts': alerts,
                'recommendations': self._generate_network_recommendations(metrics, connectivity_analysis)
            }

        except Exception as e:
            logger.error(f"Error monitoring network for user {user_id}: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e), 'alerts': []}

    def _get_current_network_data(self, device_id: str) -> Optional[Dict]:
        """Get current network status"""
        try:
            latest_entry = DeviceEventlog.objects.filter(
                deviceid=device_id
            ).order_by('-receivedon').first()

            if not latest_entry:
                return None

            return {
                'signal_strength': latest_entry.signalstrength,
                'network_provider': latest_entry.networkprovidername,
                'signal_bandwidth': latest_entry.signalbandwidth,
                'timestamp': latest_entry.receivedon,
                'has_connectivity': latest_entry.signalstrength not in ['NA', '', None]
            }

        except Exception as e:
            logger.error(f"Error getting current network data: {str(e)}")
            return None

    def _get_historical_network_data(self, device_id: str, hours: int = 4) -> List[Dict]:
        """Get historical network data for analysis"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)

            entries = DeviceEventlog.objects.filter(
                deviceid=device_id,
                receivedon__gte=cutoff_time
            ).exclude(
                signalstrength__in=['NA', '', None]
            ).order_by('receivedon')

            return [{
                'timestamp': entry.receivedon,
                'signal_strength': entry.signalstrength,
                'network_provider': entry.networkprovidername,
                'signal_bandwidth': entry.signalbandwidth,
                'location': {
                    'lat': entry.gpslocation.y if entry.gpslocation else None,
                    'lon': entry.gpslocation.x if entry.gpslocation else None
                }
            } for entry in entries]

        except Exception as e:
            logger.error(f"Error getting historical network data: {str(e)}")
            return []

    def _calculate_network_metrics(self, current_data: Dict, historical_data: List[Dict]) -> Dict:
        """Calculate network performance metrics"""
        metrics = {
            'current_signal_strength': current_data.get('signal_strength', 'Unknown'),
            'signal_quality': 'unknown',
            'network_stability': 0,
            'disconnection_periods': 0,
            'avg_signal_strength': 0,
            'signal_strength_trend': 'stable',
            'provider_consistency': 100,
            'coverage_score': 0
        }

        try:
            # Analyze signal quality
            signal_str = current_data.get('signal_strength', '')
            if signal_str and signal_str not in ['NA', '']:
                signal_numeric = self._parse_signal_strength(signal_str)
                if signal_numeric:
                    if signal_numeric >= self.GOOD_SIGNAL_THRESHOLD:
                        metrics['signal_quality'] = 'excellent'
                    elif signal_numeric >= self.POOR_SIGNAL_THRESHOLD:
                        metrics['signal_quality'] = 'good'
                    elif signal_numeric >= self.CRITICAL_SIGNAL_THRESHOLD:
                        metrics['signal_quality'] = 'poor'
                    else:
                        metrics['signal_quality'] = 'critical'

            # Analyze historical patterns
            if historical_data:
                signal_values = []
                providers = []

                for data in historical_data:
                    signal_val = self._parse_signal_strength(data.get('signal_strength', ''))
                    if signal_val:
                        signal_values.append(signal_val)

                    provider = data.get('network_provider', '')
                    if provider and provider != 'none':
                        providers.append(provider)

                # Calculate average signal strength
                if signal_values:
                    metrics['avg_signal_strength'] = np.mean(signal_values)

                    # Calculate signal stability (lower std dev = more stable)
                    signal_std = np.std(signal_values)
                    metrics['network_stability'] = max(0, min(100, 100 - signal_std))

                    # Determine trend
                    if len(signal_values) >= 5:
                        trend_slope = np.polyfit(range(len(signal_values)), signal_values, 1)[0]
                        if trend_slope > 2:
                            metrics['signal_strength_trend'] = 'improving'
                        elif trend_slope < -2:
                            metrics['signal_strength_trend'] = 'degrading'
                        else:
                            metrics['signal_strength_trend'] = 'stable'

                # Calculate provider consistency
                if providers:
                    unique_providers = len(set(providers))
                    if unique_providers == 1:
                        metrics['provider_consistency'] = 100
                    else:
                        metrics['provider_consistency'] = max(0, 100 - (unique_providers - 1) * 20)

                # Count disconnection periods
                metrics['disconnection_periods'] = self._count_disconnections(historical_data)

                # Calculate coverage score
                metrics['coverage_score'] = self._calculate_coverage_score(historical_data)

        except Exception as e:
            logger.error(f"Error calculating network metrics: {str(e)}")

        return metrics

    def _analyze_connectivity_patterns(self, historical_data: List[Dict]) -> Dict:
        """Analyze connectivity patterns and issues"""
        analysis = {
            'connectivity_status': 'unknown',
            'dead_zones': [],
            'peak_hours': [],
            'provider_performance': {},
            'location_quality_map': []
        }

        try:
            if not historical_data:
                return analysis

            # Identify dead zones (locations with poor signal)
            dead_zones = self._identify_dead_zones(historical_data)
            analysis['dead_zones'] = dead_zones

            # Analyze provider performance
            provider_performance = self._analyze_provider_performance(historical_data)
            analysis['provider_performance'] = provider_performance

            # Overall connectivity status
            total_connected = sum(1 for d in historical_data if d.get('signal_strength') not in ['NA', '', None])
            connectivity_rate = total_connected / len(historical_data) if historical_data else 0

            if connectivity_rate >= 0.95:
                analysis['connectivity_status'] = 'excellent'
            elif connectivity_rate >= 0.85:
                analysis['connectivity_status'] = 'good'
            elif connectivity_rate >= 0.7:
                analysis['connectivity_status'] = 'poor'
            else:
                analysis['connectivity_status'] = 'critical'

        except Exception as e:
            logger.error(f"Error analyzing connectivity patterns: {str(e)}")

        return analysis

    def _evaluate_network_alerts(self, user_id: int, device_id: str, current_data: Dict,
                                metrics: Dict, connectivity_analysis: Dict) -> List[Dict]:
        """Evaluate network conditions and create alerts"""
        alerts = []

        try:
            # Poor signal strength alert
            signal_quality = metrics.get('signal_quality', 'unknown')
            if signal_quality in ['poor', 'critical']:
                alert = self._create_network_alert(
                    user_id, device_id, 'SIGNAL_POOR',
                    f"Poor signal strength: {current_data.get('signal_strength', 'Unknown')}",
                    'HIGH' if signal_quality == 'critical' else 'WARNING',
                    current_data, metrics
                )
                alerts.append(alert)

            # Network disconnection alert
            if not current_data.get('has_connectivity', False):
                alert = self._create_network_alert(
                    user_id, device_id, 'NETWORK_DOWN',
                    "Network connection lost - device offline",
                    'CRITICAL', current_data, metrics
                )
                alerts.append(alert)

            # Network instability alert
            stability = metrics.get('network_stability', 100)
            if stability < 50:
                alert = self._create_network_alert(
                    user_id, device_id, 'NETWORK_UNSTABLE',
                    f"Network connection unstable (stability: {stability:.0f}%)",
                    'WARNING', current_data, metrics
                )
                alerts.append(alert)

            # Coverage issues
            coverage_score = metrics.get('coverage_score', 100)
            if coverage_score < 70:
                alert = self._create_network_alert(
                    user_id, device_id, 'POOR_COVERAGE',
                    f"Poor network coverage in current area (score: {coverage_score:.0f}%)",
                    'WARNING', current_data, metrics
                )
                alerts.append(alert)

        except Exception as e:
            logger.error(f"Error evaluating network alerts: {str(e)}")

        return [alert for alert in alerts if alert is not None]

    def _create_network_alert(self, user_id: int, device_id: str, alert_type: str,
                             description: str, severity: str, current_data: Dict, metrics: Dict) -> Optional[Dict]:
        """Create a network-related alert"""
        try:
            alert_data = {
                'user_id': user_id,
                'device_id': device_id,
                'alert_type': alert_type,
                'severity': severity,
                'title': f"Network Alert: {alert_type.replace('_', ' ').title()}",
                'description': description,
                'alert_data': {
                    'current_signal_strength': current_data.get('signal_strength', 'Unknown'),
                    'network_provider': current_data.get('network_provider', 'Unknown'),
                    'signal_quality': metrics.get('signal_quality', 'unknown'),
                    'network_stability': metrics.get('network_stability', 0),
                    'timestamp': timezone.now().isoformat()
                },
                'context_data': {
                    'network_metrics': metrics,
                    'has_connectivity': current_data.get('has_connectivity', False)
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
            logger.error(f"Error creating network alert: {str(e)}")

        return None

    # Helper methods

    def _parse_signal_strength(self, signal_str: str) -> Optional[float]:
        """Parse signal strength string to numeric value"""
        try:
            if not signal_str or signal_str in ['NA', '', 'Unknown']:
                return None

            # Handle different signal strength formats
            if 'dBm' in signal_str.lower():
                return float(signal_str.lower().replace('dbm', '').strip())
            elif 'bars' in signal_str.lower():
                bars = float(signal_str.lower().replace('bars', '').strip())
                return -120 + (bars * 20)  # Convert bars to approximate dBm
            else:
                # Try direct numeric conversion
                return float(signal_str)

        except (ValueError, TypeError):
            return None

    def _count_disconnections(self, historical_data: List[Dict]) -> int:
        """Count network disconnection periods"""
        try:
            disconnections = 0
            was_connected = True

            for data in historical_data:
                is_connected = data.get('signal_strength') not in ['NA', '', None]

                if was_connected and not is_connected:
                    disconnections += 1

                was_connected = is_connected

            return disconnections

        except Exception as e:
            logger.error(f"Error counting disconnections: {str(e)}")
            return 0

    def _calculate_coverage_score(self, historical_data: List[Dict]) -> int:
        """Calculate network coverage score based on signal quality"""
        try:
            if not historical_data:
                return 0

            quality_scores = []
            for data in historical_data:
                signal_val = self._parse_signal_strength(data.get('signal_strength', ''))
                if signal_val:
                    if signal_val >= self.GOOD_SIGNAL_THRESHOLD:
                        quality_scores.append(100)
                    elif signal_val >= self.POOR_SIGNAL_THRESHOLD:
                        quality_scores.append(70)
                    elif signal_val >= self.CRITICAL_SIGNAL_THRESHOLD:
                        quality_scores.append(40)
                    else:
                        quality_scores.append(0)

            return int(np.mean(quality_scores)) if quality_scores else 0

        except Exception as e:
            logger.error(f"Error calculating coverage score: {str(e)}")
            return 0

    def _identify_dead_zones(self, historical_data: List[Dict]) -> List[Dict]:
        """Identify locations with poor network coverage"""
        dead_zones = []

        try:
            # Group data by location and analyze signal quality
            location_signals = {}

            for data in historical_data:
                location = data.get('location')
                signal_val = self._parse_signal_strength(data.get('signal_strength', ''))

                if location and signal_val is not None:
                    lat_lon = (round(location['lat'], 4), round(location['lon'], 4))  # Round for grouping

                    if lat_lon not in location_signals:
                        location_signals[lat_lon] = []
                    location_signals[lat_lon].append(signal_val)

            # Identify locations with consistently poor signal
            for location, signals in location_signals.items():
                avg_signal = np.mean(signals)
                if avg_signal < self.POOR_SIGNAL_THRESHOLD and len(signals) >= 3:
                    dead_zones.append({
                        'location': {'lat': location[0], 'lon': location[1]},
                        'avg_signal_strength': avg_signal,
                        'sample_count': len(signals)
                    })

        except Exception as e:
            logger.error(f"Error identifying dead zones: {str(e)}")

        return dead_zones

    def _analyze_provider_performance(self, historical_data: List[Dict]) -> Dict:
        """Analyze performance by network provider"""
        performance = {}

        try:
            provider_data = {}

            for data in historical_data:
                provider = data.get('network_provider', 'unknown')
                signal_val = self._parse_signal_strength(data.get('signal_strength', ''))

                if provider != 'none' and signal_val is not None:
                    if provider not in provider_data:
                        provider_data[provider] = []
                    provider_data[provider].append(signal_val)

            # Calculate performance metrics for each provider
            for provider, signals in provider_data.items():
                if signals:
                    performance[provider] = {
                        'avg_signal_strength': float(np.mean(signals)),
                        'signal_consistency': float(100 - np.std(signals)),
                        'sample_count': len(signals),
                        'quality_rating': self._rate_signal_quality(np.mean(signals))
                    }

        except Exception as e:
            logger.error(f"Error analyzing provider performance: {str(e)}")

        return performance

    def _rate_signal_quality(self, avg_signal: float) -> str:
        """Rate signal quality based on average signal strength"""
        if avg_signal >= self.GOOD_SIGNAL_THRESHOLD:
            return 'excellent'
        elif avg_signal >= self.POOR_SIGNAL_THRESHOLD:
            return 'good'
        elif avg_signal >= self.CRITICAL_SIGNAL_THRESHOLD:
            return 'poor'
        else:
            return 'critical'

    def _generate_network_recommendations(self, metrics: Dict, connectivity_analysis: Dict) -> List[str]:
        """Generate network-related recommendations"""
        recommendations = []

        try:
            signal_quality = metrics.get('signal_quality', 'unknown')

            if signal_quality in ['poor', 'critical']:
                recommendations.append("Move to an area with better signal reception")
                recommendations.append("Consider using WiFi if available")

            stability = metrics.get('network_stability', 100)
            if stability < 60:
                recommendations.append("Network connection is unstable - sync data when signal improves")

            if connectivity_analysis.get('dead_zones'):
                recommendations.append("Avoid identified dead zones for critical communications")

            coverage_score = metrics.get('coverage_score', 100)
            if coverage_score < 70:
                recommendations.append("Report poor coverage area to IT team for infrastructure review")

        except Exception as e:
            logger.error(f"Error generating network recommendations: {str(e)}")

        return recommendations