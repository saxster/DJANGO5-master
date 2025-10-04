"""
Battery Monitoring Engine

Advanced battery monitoring with predictive analytics and intelligent alerting.
Provides real-time battery status tracking and failure prediction.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.db.models import Q, Avg, F
from django.core.cache import cache

from apps.activity.models import DeviceEventlog
from apps.monitoring.models import (
    Alert, AlertRule, MonitoringMetric, DeviceHealthSnapshot,
    UserActivityPattern
)
from apps.monitoring.services.alert_service import AlertService
from apps.monitoring.services.prediction_service import PredictionService

logger = logging.getLogger(__name__)


class BatteryMonitor:
    """
    Intelligent battery monitoring with predictive analytics.

    Features:
    - Real-time battery level tracking
    - Drain rate calculation and prediction
    - Context-aware alerting (shift times, workload)
    - Predictive failure detection
    - Charging pattern analysis
    """

    def __init__(self):
        self.alert_service = AlertService()
        self.prediction_service = PredictionService()

        # Battery thresholds
        self.CRITICAL_LEVEL = 10  # Battery level that requires immediate action
        self.LOW_LEVEL = 20       # Battery level that requires warning
        self.WARNING_LEVEL = 30   # Battery level for early warning

        # Drain rate thresholds (% per hour)
        self.CRITICAL_DRAIN_RATE = 40  # Extremely fast drain
        self.HIGH_DRAIN_RATE = 25      # High drain rate
        self.NORMAL_DRAIN_RATE = 12    # Normal drain rate

        # Prediction accuracy requirements
        self.MIN_PREDICTION_CONFIDENCE = 0.7
        self.MIN_DATA_POINTS = 10

    def monitor_battery_status(self, user_id: int, device_id: str) -> Dict:
        """
        Comprehensive battery monitoring for a specific user/device.

        Returns monitoring results and any triggered alerts.
        """
        try:
            logger.info(f"Monitoring battery status for user {user_id}, device {device_id}")

            # Get current battery data
            current_data = self._get_current_battery_data(device_id)
            if not current_data:
                logger.warning(f"No battery data found for device {device_id}")
                return {'status': 'no_data', 'alerts': []}

            # Get historical data for trend analysis
            historical_data = self._get_historical_battery_data(device_id, hours=24)

            # Calculate current metrics
            metrics = self._calculate_battery_metrics(current_data, historical_data)

            # Get user context for smart alerting
            user_context = self._get_user_context(user_id)

            # Predict battery life
            prediction = self._predict_battery_life(historical_data, user_context)

            # Evaluate alert conditions
            alerts = self._evaluate_battery_alerts(
                user_id, device_id, current_data, metrics, prediction, user_context
            )

            # Update monitoring metrics
            self._update_monitoring_metrics(user_id, device_id, metrics, prediction)

            # Store device health snapshot
            self._store_health_snapshot(user_id, device_id, current_data, metrics, prediction)

            return {
                'status': 'success',
                'current_level': current_data.get('batterylevel', 0),
                'metrics': metrics,
                'prediction': prediction,
                'alerts': alerts,
                'recommendations': self._generate_recommendations(metrics, prediction, user_context)
            }

        except Exception as e:
            logger.error(f"Error monitoring battery for user {user_id}: {str(e)}", exc_info=True)
            return {'status': 'error', 'error': str(e), 'alerts': []}

    def _get_current_battery_data(self, device_id: str) -> Optional[Dict]:
        """Get the most recent battery data for a device"""
        try:
            latest_entry = DeviceEventlog.objects.filter(
                deviceid=device_id
            ).exclude(
                batterylevel='NA'
            ).order_by('-receivedon').first()

            if not latest_entry:
                return None

            return {
                'batterylevel': self._safe_int(latest_entry.batterylevel),
                'timestamp': latest_entry.receivedon,
                'charging_status': self._detect_charging_status(latest_entry),
                'device_info': {
                    'platform_version': latest_entry.platformversion,
                    'app_version': latest_entry.applicationversion,
                    'model': latest_entry.modelname
                }
            }

        except Exception as e:
            logger.error(f"Error getting current battery data for device {device_id}: {str(e)}")
            return None

    def _get_historical_battery_data(self, device_id: str, hours: int = 24) -> List[Dict]:
        """Get historical battery data for trend analysis"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)

            entries = DeviceEventlog.objects.filter(
                deviceid=device_id,
                receivedon__gte=cutoff_time
            ).exclude(
                batterylevel='NA'
            ).order_by('receivedon')

            historical_data = []
            for entry in entries:
                battery_level = self._safe_int(entry.batterylevel)
                if battery_level > 0:  # Filter out invalid readings
                    historical_data.append({
                        'level': battery_level,
                        'timestamp': entry.receivedon,
                        'location': {
                            'lat': entry.gpslocation.y if entry.gpslocation else None,
                            'lon': entry.gpslocation.x if entry.gpslocation else None,
                        },
                        'activity': {
                            'steps': self._safe_int(entry.stepcount) if entry.stepcount != 'No Steps' else 0,
                            'signal_strength': entry.signalstrength,
                            'network_type': entry.networkprovidername
                        }
                    })

            return historical_data

        except Exception as e:
            logger.error(f"Error getting historical battery data for device {device_id}: {str(e)}")
            return []

    def _calculate_battery_metrics(self, current_data: Dict, historical_data: List[Dict]) -> Dict:
        """Calculate comprehensive battery metrics"""
        metrics = {
            'current_level': current_data.get('batterylevel', 0),
            'drain_rate_per_hour': 0,
            'time_since_last_charge': None,
            'average_drain_rate_24h': 0,
            'battery_health_score': 100,
            'charging_efficiency': None,
            'usage_pattern_score': 50
        }

        if len(historical_data) < 2:
            return metrics

        try:
            # Calculate current drain rate
            recent_data = historical_data[-10:]  # Last 10 readings
            if len(recent_data) >= 2:
                time_diff_hours = (recent_data[-1]['timestamp'] - recent_data[0]['timestamp']).total_seconds() / 3600
                level_diff = recent_data[0]['level'] - recent_data[-1]['level']

                if time_diff_hours > 0:
                    metrics['drain_rate_per_hour'] = max(0, level_diff / time_diff_hours)

            # Calculate 24-hour average drain rate
            if len(historical_data) >= 2:
                total_time_hours = (historical_data[-1]['timestamp'] - historical_data[0]['timestamp']).total_seconds() / 3600
                total_drain = historical_data[0]['level'] - historical_data[-1]['level']

                if total_time_hours > 0:
                    metrics['average_drain_rate_24h'] = max(0, total_drain / total_time_hours)

            # Detect charging patterns
            charging_sessions = self._detect_charging_sessions(historical_data)
            if charging_sessions:
                metrics['charging_efficiency'] = self._calculate_charging_efficiency(charging_sessions)
                metrics['time_since_last_charge'] = self._time_since_last_charge(charging_sessions)

            # Calculate battery health score based on drain patterns
            metrics['battery_health_score'] = self._calculate_battery_health_score(historical_data)

            # Calculate usage pattern score
            metrics['usage_pattern_score'] = self._calculate_usage_pattern_score(historical_data)

        except Exception as e:
            logger.error(f"Error calculating battery metrics: {str(e)}")

        return metrics

    def _predict_battery_life(self, historical_data: List[Dict], user_context: Dict) -> Dict:
        """Predict remaining battery life using ML and statistical analysis"""
        prediction = {
            'hours_remaining': None,
            'confidence': 0,
            'predicted_depletion_time': None,
            'will_last_shift': False,
            'prediction_method': 'none'
        }

        if len(historical_data) < self.MIN_DATA_POINTS:
            return prediction

        try:
            current_level = historical_data[-1]['level']
            if current_level <= 0:
                return prediction

            # Method 1: Linear trend prediction
            linear_prediction = self._linear_trend_prediction(historical_data, current_level)

            # Method 2: ML-based prediction (if enough data)
            ml_prediction = None
            if len(historical_data) >= 50:
                ml_prediction = self.prediction_service.predict_battery_life(
                    historical_data, user_context
                )

            # Method 3: Context-aware prediction
            context_prediction = self._context_aware_prediction(
                historical_data, user_context, current_level
            )

            # Choose best prediction method
            final_prediction = self._select_best_prediction(
                linear_prediction, ml_prediction, context_prediction
            )

            if final_prediction:
                prediction.update(final_prediction)

                # Check if battery will last the current shift
                shift_hours_remaining = user_context.get('shift_hours_remaining', 8)
                prediction['will_last_shift'] = (
                    prediction['hours_remaining'] and
                    prediction['hours_remaining'] >= shift_hours_remaining
                )

                # Calculate predicted depletion time
                if prediction['hours_remaining']:
                    prediction['predicted_depletion_time'] = (
                        timezone.now() + timedelta(hours=prediction['hours_remaining'])
                    )

        except Exception as e:
            logger.error(f"Error predicting battery life: {str(e)}")

        return prediction

    def _linear_trend_prediction(self, historical_data: List[Dict], current_level: int) -> Dict:
        """Simple linear trend prediction"""
        if len(historical_data) < 5:
            return None

        try:
            # Use last 2 hours of data for short-term prediction
            recent_cutoff = timezone.now() - timedelta(hours=2)
            recent_data = [d for d in historical_data if d['timestamp'] >= recent_cutoff]

            if len(recent_data) < 3:
                recent_data = historical_data[-10:]  # Fallback to last 10 readings

            # Calculate trend
            levels = [d['level'] for d in recent_data]
            timestamps = [(d['timestamp'] - recent_data[0]['timestamp']).total_seconds() / 3600
                         for d in recent_data]

            if len(levels) >= 2:
                # Linear regression
                drain_rate = np.polyfit(timestamps, levels, 1)[0]  # Slope

                if drain_rate < 0:  # Battery is draining
                    hours_remaining = current_level / abs(drain_rate)
                    return {
                        'hours_remaining': max(0, hours_remaining),
                        'confidence': 0.6,
                        'prediction_method': 'linear_trend'
                    }

        except Exception as e:
            logger.error(f"Error in linear trend prediction: {str(e)}")

        return None

    def _context_aware_prediction(self, historical_data: List[Dict], user_context: Dict, current_level: int) -> Dict:
        """Context-aware prediction based on user patterns and current activity"""
        try:
            # Get user's typical battery usage patterns
            activity_pattern = user_context.get('activity_pattern')
            if not activity_pattern:
                return None

            # Adjust prediction based on:
            # 1. Time of day
            # 2. Remaining shift time
            # 3. Typical usage patterns
            # 4. Current activity level

            current_hour = timezone.now().hour
            shift_hours_remaining = user_context.get('shift_hours_remaining', 8)

            # Get typical usage for this time period
            typical_usage = activity_pattern.avg_battery_usage_per_hour

            # Adjust for current activity level
            recent_activity = self._get_recent_activity_level(historical_data)
            activity_multiplier = self._calculate_activity_multiplier(recent_activity)

            # Predicted drain rate
            predicted_drain_rate = typical_usage * activity_multiplier

            if predicted_drain_rate > 0:
                hours_remaining = current_level / predicted_drain_rate
                confidence = min(0.8, activity_pattern.pattern_confidence)

                return {
                    'hours_remaining': hours_remaining,
                    'confidence': confidence,
                    'prediction_method': 'context_aware'
                }

        except Exception as e:
            logger.error(f"Error in context-aware prediction: {str(e)}")

        return None

    def _evaluate_battery_alerts(self, user_id: int, device_id: str, current_data: Dict,
                                metrics: Dict, prediction: Dict, user_context: Dict) -> List[Dict]:
        """Evaluate battery conditions and trigger appropriate alerts"""
        alerts = []
        current_level = current_data.get('batterylevel', 0)
        drain_rate = metrics.get('drain_rate_per_hour', 0)

        try:
            # Critical battery level
            if current_level <= self.CRITICAL_LEVEL:
                alert = self._create_battery_alert(
                    user_id, device_id, 'BATTERY_CRITICAL',
                    f"Critical battery level: {current_level}%",
                    'CRITICAL', current_data, metrics, prediction
                )
                alerts.append(alert)

            # Low battery level with shift consideration
            elif current_level <= self.LOW_LEVEL:
                hours_remaining = prediction.get('hours_remaining', 0)
                shift_hours = user_context.get('shift_hours_remaining', 0)

                if hours_remaining and hours_remaining < shift_hours:
                    alert = self._create_battery_alert(
                        user_id, device_id, 'BATTERY_LOW',
                        f"Low battery: {current_level}% - may not last shift",
                        'HIGH', current_data, metrics, prediction
                    )
                    alerts.append(alert)

            # High drain rate alert
            if drain_rate > self.CRITICAL_DRAIN_RATE:
                alert = self._create_battery_alert(
                    user_id, device_id, 'BATTERY_RAPID_DRAIN',
                    f"Rapid battery drain: {drain_rate:.1f}% per hour",
                    'HIGH', current_data, metrics, prediction
                )
                alerts.append(alert)

            # Charging anomaly detection
            charging_issues = self._detect_charging_anomalies(metrics, historical_data=None)
            for issue in charging_issues:
                alert = self._create_battery_alert(
                    user_id, device_id, 'BATTERY_CHARGING_ISSUE',
                    f"Charging issue detected: {issue}",
                    'MEDIUM', current_data, metrics, prediction
                )
                alerts.append(alert)

            # Predictive alerts
            if prediction.get('hours_remaining'):
                if (prediction['hours_remaining'] < 2 and
                    user_context.get('shift_hours_remaining', 0) > 2):
                    alert = self._create_battery_alert(
                        user_id, device_id, 'BATTERY_PREDICTION_WARNING',
                        f"Battery predicted to drain in {prediction['hours_remaining']:.1f} hours",
                        'WARNING', current_data, metrics, prediction
                    )
                    alerts.append(alert)

        except Exception as e:
            logger.error(f"Error evaluating battery alerts for user {user_id}: {str(e)}")

        return alerts

    def _create_battery_alert(self, user_id: int, device_id: str, alert_type: str,
                            description: str, severity: str, current_data: Dict,
                            metrics: Dict, prediction: Dict) -> Dict:
        """Create a battery-related alert"""
        try:
            # Check if we should create this alert (cooldown, etc.)
            if not self._should_create_alert(user_id, device_id, alert_type):
                return None

            alert_data = {
                'user_id': user_id,
                'device_id': device_id,
                'alert_type': alert_type,
                'severity': severity,
                'title': f"Battery Alert: {alert_type.replace('_', ' ').title()}",
                'description': description,
                'alert_data': {
                    'current_battery_level': current_data.get('batterylevel', 0),
                    'drain_rate_per_hour': metrics.get('drain_rate_per_hour', 0),
                    'predicted_hours_remaining': prediction.get('hours_remaining'),
                    'device_info': current_data.get('device_info', {}),
                    'timestamp': timezone.now().isoformat()
                },
                'context_data': {
                    'battery_metrics': metrics,
                    'prediction_data': prediction,
                    'device_health_score': metrics.get('battery_health_score', 100)
                }
            }

            # Create alert through alert service
            alert = self.alert_service.create_alert(alert_data)

            return {
                'alert_id': str(alert.alert_id),
                'type': alert_type,
                'severity': severity,
                'description': description,
                'created_at': alert.triggered_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Error creating battery alert: {str(e)}")
            return None

    def _should_create_alert(self, user_id: int, device_id: str, alert_type: str) -> bool:
        """Check if alert should be created based on cooldown rules"""
        try:
            # Check for recent similar alerts
            cooldown_minutes = 15  # Default cooldown
            if alert_type == 'BATTERY_CRITICAL':
                cooldown_minutes = 5  # Shorter cooldown for critical alerts

            recent_cutoff = timezone.now() - timedelta(minutes=cooldown_minutes)

            recent_alert = Alert.objects.filter(
                user_id=user_id,
                device_id=device_id,
                rule__alert_type=alert_type,
                triggered_at__gte=recent_cutoff,
                status='ACTIVE'
            ).first()

            return recent_alert is None

        except Exception as e:
            logger.error(f"Error checking alert cooldown: {str(e)}")
            return True  # Default to allowing alert

    def _get_user_context(self, user_id: int) -> Dict:
        """Get user context for intelligent alerting"""
        try:
            from apps.peoples.models import People
            user = People.objects.get(id=user_id)

            # Get activity pattern if available
            activity_pattern = getattr(user, 'activity_pattern', None)

            # Calculate remaining shift time (simplified)
            current_time = timezone.now()
            shift_end_hour = 17  # Default 5 PM end time
            if current_time.hour < shift_end_hour:
                shift_hours_remaining = shift_end_hour - current_time.hour
            else:
                shift_hours_remaining = 0

            return {
                'user_id': user_id,
                'user_name': user.peoplename,
                'activity_pattern': activity_pattern,
                'shift_hours_remaining': shift_hours_remaining,
                'current_time': current_time,
                'work_schedule': {
                    'start_hour': 9,
                    'end_hour': 17,
                    'break_hours': [12, 13]  # Lunch break
                }
            }

        except Exception as e:
            logger.error(f"Error getting user context for user {user_id}: {str(e)}")
            return {'user_id': user_id, 'shift_hours_remaining': 8}

    def _update_monitoring_metrics(self, user_id: int, device_id: str, metrics: Dict, prediction: Dict):
        """Update monitoring metrics in the database"""
        try:
            # Store key metrics
            metric_data = [
                ('BATTERY_LEVEL', metrics['current_level'], '%'),
                ('BATTERY_DRAIN_RATE', metrics['drain_rate_per_hour'], '%/hour'),
                ('BATTERY_HEALTH_SCORE', metrics['battery_health_score'], 'score'),
            ]

            if prediction.get('hours_remaining'):
                metric_data.append(('BATTERY_PREDICTED_HOURS', prediction['hours_remaining'], 'hours'))

            for metric_type, value, unit in metric_data:
                MonitoringMetric.objects.create(
                    user_id=user_id,
                    device_id=device_id,
                    metric_type=metric_type,
                    value=value,
                    unit=unit,
                    context={
                        'prediction_confidence': prediction.get('confidence', 0),
                        'prediction_method': prediction.get('prediction_method', 'none')
                    }
                )

        except Exception as e:
            logger.error(f"Error updating monitoring metrics: {str(e)}")

    def _store_health_snapshot(self, user_id: int, device_id: str, current_data: Dict, metrics: Dict, prediction: Dict):
        """Store device health snapshot"""
        try:
            DeviceHealthSnapshot.objects.create(
                user_id=user_id,
                device_id=device_id,
                overall_health=self._calculate_overall_health(metrics),
                health_score=metrics.get('battery_health_score', 100),
                battery_level=current_data.get('batterylevel', 0),
                battery_health=self._get_battery_health_category(metrics['battery_health_score']),
                is_charging=current_data.get('charging_status', False),
                predicted_battery_hours=prediction.get('hours_remaining'),
                risk_score=self._calculate_risk_score(metrics, prediction),
                anomaly_indicators=self._detect_anomalies(metrics)
            )

        except Exception as e:
            logger.error(f"Error storing health snapshot: {str(e)}")

    def _generate_recommendations(self, metrics: Dict, prediction: Dict, user_context: Dict) -> List[str]:
        """Generate actionable recommendations based on battery analysis"""
        recommendations = []

        try:
            current_level = metrics['current_level']
            drain_rate = metrics.get('drain_rate_per_hour', 0)

            # Battery level recommendations
            if current_level < 20:
                recommendations.append("Find a charging station immediately")
                recommendations.append("Reduce device usage to essential functions only")

            if drain_rate > self.HIGH_DRAIN_RATE:
                recommendations.append("Check for apps running in background")
                recommendations.append("Reduce screen brightness to conserve battery")
                recommendations.append("Consider switching to power saving mode")

            # Predictive recommendations
            if prediction.get('hours_remaining'):
                hours_remaining = prediction['hours_remaining']
                shift_hours = user_context.get('shift_hours_remaining', 0)

                if hours_remaining < shift_hours:
                    recommendations.append(f"Battery may not last full shift - plan charging break")

            # Health recommendations
            health_score = metrics.get('battery_health_score', 100)
            if health_score < 70:
                recommendations.append("Consider device replacement - battery health degraded")

        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")

        return recommendations

    # Helper methods

    def _safe_int(self, value, default=0):
        """Safely convert value to integer"""
        if value == 'NA' or value is None:
            return default
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return default

    def _detect_charging_status(self, entry):
        """Detect if device is currently charging"""
        # This would need to be enhanced based on available data
        # For now, return False as placeholder
        return False

    def _detect_charging_sessions(self, historical_data: List[Dict]) -> List[Dict]:
        """Detect charging sessions from historical data"""
        sessions = []
        # Implementation would analyze battery level increases
        # to identify charging periods
        return sessions

    def _calculate_charging_efficiency(self, charging_sessions: List[Dict]) -> float:
        """Calculate charging efficiency from charging sessions"""
        # Implementation would analyze charging speed and efficiency
        return 85.0  # Placeholder

    def _time_since_last_charge(self, charging_sessions: List[Dict]) -> Optional[float]:
        """Calculate time since last charging session"""
        # Implementation would find the most recent charging session
        return None

    def _calculate_battery_health_score(self, historical_data: List[Dict]) -> int:
        """Calculate battery health score based on usage patterns"""
        # Implementation would analyze drain patterns, charging behavior
        # and other factors to determine battery health
        return 85

    def _calculate_usage_pattern_score(self, historical_data: List[Dict]) -> int:
        """Calculate usage pattern score"""
        # Implementation would analyze if usage is normal/abnormal
        return 50

    def _select_best_prediction(self, linear, ml, context) -> Optional[Dict]:
        """Select the best prediction from available methods"""
        predictions = [p for p in [linear, ml, context] if p is not None]

        if not predictions:
            return None

        # Select prediction with highest confidence
        best = max(predictions, key=lambda p: p.get('confidence', 0))
        return best

    def _get_recent_activity_level(self, historical_data: List[Dict]) -> float:
        """Get recent activity level multiplier"""
        # Implementation would analyze recent step count, location changes, etc.
        return 1.0

    def _calculate_activity_multiplier(self, activity_level: float) -> float:
        """Calculate battery drain multiplier based on activity"""
        # High activity = higher battery drain
        return max(0.5, min(2.0, activity_level))

    def _detect_charging_anomalies(self, metrics: Dict, historical_data) -> List[str]:
        """Detect charging-related anomalies"""
        anomalies = []
        # Implementation would detect slow charging, charging failures, etc.
        return anomalies

    def _calculate_overall_health(self, metrics: Dict) -> str:
        """Calculate overall device health category"""
        health_score = metrics.get('battery_health_score', 100)
        if health_score >= 90:
            return 'EXCELLENT'
        elif health_score >= 75:
            return 'GOOD'
        elif health_score >= 50:
            return 'FAIR'
        elif health_score >= 25:
            return 'POOR'
        else:
            return 'CRITICAL'

    def _get_battery_health_category(self, health_score: int) -> str:
        """Convert health score to category"""
        return self._calculate_overall_health({'battery_health_score': health_score})

    def _calculate_risk_score(self, metrics: Dict, prediction: Dict) -> float:
        """Calculate overall risk score"""
        risk = 0.0

        # Battery level risk
        current_level = metrics['current_level']
        if current_level < 10:
            risk += 0.5
        elif current_level < 20:
            risk += 0.3

        # Drain rate risk
        drain_rate = metrics.get('drain_rate_per_hour', 0)
        if drain_rate > 30:
            risk += 0.3
        elif drain_rate > 20:
            risk += 0.2

        # Prediction risk
        if prediction.get('will_last_shift') is False:
            risk += 0.2

        return min(1.0, risk)

    def _detect_anomalies(self, metrics: Dict) -> List[str]:
        """Detect battery-related anomalies"""
        anomalies = []

        if metrics.get('drain_rate_per_hour', 0) > self.CRITICAL_DRAIN_RATE:
            anomalies.append('rapid_battery_drain')

        if metrics.get('battery_health_score', 100) < 50:
            anomalies.append('battery_degradation')

        return anomalies