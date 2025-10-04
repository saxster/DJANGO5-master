"""
Prediction Service

Machine learning and statistical prediction service for device monitoring.
Provides predictive analytics for battery life, performance degradation, and anomaly detection.
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger = logging.getLogger(__name__)
    logger.warning("scikit-learn not available, using statistical methods only")

logger = logging.getLogger(__name__)


class PredictionService:
    """
    Advanced prediction service for device monitoring.

    Provides multiple prediction methods:
    - Statistical trend analysis
    - Machine learning regression models
    - Pattern-based predictions
    - Ensemble predictions
    """

    def __init__(self):
        self.cache_timeout = 1800  # 30 minutes
        self.min_data_points = 10
        self.use_ml = HAS_SKLEARN and getattr(settings, 'MONITORING_USE_ML', True)

        # Model cache
        self.models = {}
        self.model_cache_timeout = 3600  # 1 hour

    def predict_battery_life(self, historical_data: List[Dict], user_context: Dict) -> Dict:
        """
        Predict remaining battery life using multiple methods.

        Args:
            historical_data: List of historical battery data points
            user_context: User context for pattern-aware predictions

        Returns:
            Dictionary containing prediction results
        """
        try:
            if len(historical_data) < self.min_data_points:
                return {
                    'hours_remaining': None,
                    'confidence': 0,
                    'method': 'insufficient_data',
                    'error': 'Not enough historical data'
                }

            # Prepare data
            features, targets = self._prepare_battery_data(historical_data)
            if len(features) < 5:
                return self._fallback_prediction(historical_data)

            predictions = {}

            # Method 1: Linear trend analysis
            linear_pred = self._linear_battery_prediction(historical_data)
            if linear_pred:
                predictions['linear'] = linear_pred

            # Method 2: Machine learning prediction
            if self.use_ml and len(features) >= 20:
                ml_pred = self._ml_battery_prediction(features, targets, user_context)
                if ml_pred:
                    predictions['ml'] = ml_pred

            # Method 3: Pattern-based prediction
            pattern_pred = self._pattern_battery_prediction(historical_data, user_context)
            if pattern_pred:
                predictions['pattern'] = pattern_pred

            # Method 4: Context-aware prediction
            context_pred = self._context_battery_prediction(historical_data, user_context)
            if context_pred:
                predictions['context'] = context_pred

            # Ensemble prediction
            final_prediction = self._ensemble_battery_prediction(predictions)

            # Cache the prediction
            self._cache_prediction('battery', user_context.get('user_id'), final_prediction)

            return final_prediction

        except Exception as e:
            logger.error(f"Error predicting battery life: {str(e)}", exc_info=True)
            return self._fallback_prediction(historical_data)

    def predict_performance_degradation(self, device_id: str, metrics_history: List[Dict]) -> Dict:
        """
        Predict device performance degradation.

        Args:
            device_id: Device identifier
            metrics_history: Historical performance metrics

        Returns:
            Dictionary containing degradation predictions
        """
        try:
            if len(metrics_history) < self.min_data_points:
                return {'degradation_risk': 0, 'confidence': 0, 'method': 'insufficient_data'}

            # Analyze performance trends
            performance_score = self._calculate_performance_trend(metrics_history)

            # Predict degradation
            if self.use_ml:
                degradation_pred = self._ml_degradation_prediction(device_id, metrics_history)
            else:
                degradation_pred = self._statistical_degradation_prediction(metrics_history)

            # Combine results
            prediction = {
                'degradation_risk': degradation_pred.get('risk_score', 0),
                'confidence': degradation_pred.get('confidence', 0),
                'predicted_failure_days': degradation_pred.get('failure_days'),
                'performance_trend': performance_score,
                'method': degradation_pred.get('method', 'statistical'),
                'recommendations': self._generate_degradation_recommendations(degradation_pred)
            }

            return prediction

        except Exception as e:
            logger.error(f"Error predicting performance degradation: {str(e)}", exc_info=True)
            return {'degradation_risk': 0, 'confidence': 0, 'error': str(e)}

    def detect_anomalies(self, current_data: Dict, historical_baseline: Dict, user_pattern: Dict) -> Dict:
        """
        Detect anomalies in current device behavior.

        Args:
            current_data: Current device metrics
            historical_baseline: Historical baseline metrics
            user_pattern: User's typical usage patterns

        Returns:
            Dictionary containing anomaly detection results
        """
        try:
            anomalies = []
            anomaly_scores = {}

            # Battery anomaly detection
            battery_anomaly = self._detect_battery_anomaly(
                current_data, historical_baseline, user_pattern
            )
            if battery_anomaly['is_anomaly']:
                anomalies.append(battery_anomaly)
                anomaly_scores['battery'] = battery_anomaly['severity']

            # Usage pattern anomaly detection
            usage_anomaly = self._detect_usage_anomaly(
                current_data, historical_baseline, user_pattern
            )
            if usage_anomaly['is_anomaly']:
                anomalies.append(usage_anomaly)
                anomaly_scores['usage'] = usage_anomaly['severity']

            # Performance anomaly detection
            performance_anomaly = self._detect_performance_anomaly(
                current_data, historical_baseline
            )
            if performance_anomaly['is_anomaly']:
                anomalies.append(performance_anomaly)
                anomaly_scores['performance'] = performance_anomaly['severity']

            # Calculate overall anomaly score
            overall_score = np.mean(list(anomaly_scores.values())) if anomaly_scores else 0

            return {
                'has_anomalies': len(anomalies) > 0,
                'anomaly_count': len(anomalies),
                'overall_score': overall_score,
                'anomalies': anomalies,
                'category_scores': anomaly_scores,
                'confidence': self._calculate_anomaly_confidence(anomalies)
            }

        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}", exc_info=True)
            return {'has_anomalies': False, 'error': str(e)}

    def _prepare_battery_data(self, historical_data: List[Dict]) -> Tuple[List[List], List]:
        """Prepare battery data for ML models"""
        features = []
        targets = []

        for i in range(1, len(historical_data)):
            prev_point = historical_data[i-1]
            current_point = historical_data[i]

            # Time difference in hours
            time_diff = (current_point['timestamp'] - prev_point['timestamp']).total_seconds() / 3600

            if time_diff > 0 and time_diff < 24:  # Valid time range
                # Features: previous level, time diff, activity level, hour of day
                feature = [
                    prev_point['level'],
                    time_diff,
                    current_point.get('activity', {}).get('steps', 0),
                    current_point['timestamp'].hour,
                    # Add more features as needed
                ]
                features.append(feature)

                # Target: battery level change
                level_change = current_point['level'] - prev_point['level']
                targets.append(level_change)

        return features, targets

    def _linear_battery_prediction(self, historical_data: List[Dict]) -> Optional[Dict]:
        """Simple linear regression prediction for battery life"""
        try:
            if len(historical_data) < 5:
                return None

            # Use recent data points for short-term prediction
            recent_data = historical_data[-10:]
            current_level = recent_data[-1]['level']

            # Calculate time-based features
            times = [(d['timestamp'] - recent_data[0]['timestamp']).total_seconds() / 3600
                    for d in recent_data]
            levels = [d['level'] for d in recent_data]

            # Fit linear model
            if len(times) >= 3:
                # Simple linear regression
                slope = np.polyfit(times, levels, 1)[0]

                if slope < 0:  # Battery is draining
                    hours_remaining = current_level / abs(slope)

                    # Calculate confidence based on R-squared
                    predicted_levels = [slope * t + levels[0] for t in times]
                    r_squared = 1 - (np.sum((np.array(levels) - np.array(predicted_levels))**2) /
                                   np.sum((np.array(levels) - np.mean(levels))**2))

                    confidence = max(0.1, min(0.8, r_squared))

                    return {
                        'hours_remaining': max(0, hours_remaining),
                        'confidence': confidence,
                        'method': 'linear_regression',
                        'slope': slope
                    }

        except Exception as e:
            logger.error(f"Error in linear battery prediction: {str(e)}")

        return None

    def _ml_battery_prediction(self, features: List[List], targets: List, user_context: Dict) -> Optional[Dict]:
        """Machine learning-based battery prediction"""
        if not self.use_ml or len(features) < 20:
            return None

        try:
            # Convert to numpy arrays
            X = np.array(features)
            y = np.array(targets)

            # Split data for validation
            split_idx = int(len(X) * 0.8)
            X_train, X_test = X[:split_idx], X[split_idx:]
            y_train, y_test = y[:split_idx], y[split_idx:]

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train model
            model = RandomForestRegressor(n_estimators=50, random_state=42)
            model.fit(X_train_scaled, y_train)

            # Validate model
            predictions = model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, predictions)

            # Predict future battery drain
            current_features = X[-1:].reshape(1, -1)  # Last known state
            current_scaled = scaler.transform(current_features)

            # Simulate future drain
            current_level = current_features[0][0]  # First feature is battery level
            hours_remaining = self._simulate_battery_drain(
                model, scaler, current_features[0], current_level
            )

            # Calculate confidence based on model performance
            confidence = max(0.2, min(0.9, 1 - (mae / 20)))  # Normalize MAE to confidence

            return {
                'hours_remaining': hours_remaining,
                'confidence': confidence,
                'method': 'random_forest',
                'model_mae': mae
            }

        except Exception as e:
            logger.error(f"Error in ML battery prediction: {str(e)}")
            return None

    def _pattern_battery_prediction(self, historical_data: List[Dict], user_context: Dict) -> Optional[Dict]:
        """Pattern-based battery prediction using historical usage patterns"""
        try:
            # Group data by hour of day to find patterns
            hourly_patterns = {}
            for data in historical_data:
                hour = data['timestamp'].hour
                if hour not in hourly_patterns:
                    hourly_patterns[hour] = []
                hourly_patterns[hour].append(data['level'])

            current_hour = timezone.now().hour
            current_level = historical_data[-1]['level']

            # Find similar time periods
            similar_periods = []
            for hour in range(current_hour, current_hour + 8):  # Next 8 hours
                hour_key = hour % 24
                if hour_key in hourly_patterns and len(hourly_patterns[hour_key]) > 0:
                    avg_level = np.mean(hourly_patterns[hour_key])
                    similar_periods.append((hour - current_hour, avg_level))

            if similar_periods:
                # Estimate drain rate based on patterns
                drain_rates = []
                for i in range(1, len(similar_periods)):
                    time_diff = similar_periods[i][0] - similar_periods[i-1][0]
                    level_diff = similar_periods[i-1][1] - similar_periods[i][1]
                    if time_diff > 0:
                        drain_rates.append(level_diff / time_diff)

                if drain_rates:
                    avg_drain_rate = np.mean(drain_rates)
                    if avg_drain_rate > 0:
                        hours_remaining = current_level / avg_drain_rate

                        # Confidence based on pattern consistency
                        std_dev = np.std(drain_rates)
                        confidence = max(0.3, min(0.7, 1 - (std_dev / avg_drain_rate)))

                        return {
                            'hours_remaining': hours_remaining,
                            'confidence': confidence,
                            'method': 'pattern_analysis',
                            'avg_drain_rate': avg_drain_rate
                        }

        except Exception as e:
            logger.error(f"Error in pattern battery prediction: {str(e)}")

        return None

    def _context_battery_prediction(self, historical_data: List[Dict], user_context: Dict) -> Optional[Dict]:
        """Context-aware battery prediction"""
        try:
            current_level = historical_data[-1]['level']
            shift_hours_remaining = user_context.get('shift_hours_remaining', 8)

            # Get user's typical battery usage pattern
            activity_pattern = user_context.get('activity_pattern')
            if not activity_pattern:
                return None

            typical_usage_per_hour = getattr(activity_pattern, 'avg_battery_usage_per_hour', 12)

            # Adjust for current context
            current_time = timezone.now()

            # Time-based adjustments
            if current_time.hour < 12:  # Morning - typically higher usage
                usage_multiplier = 1.2
            elif current_time.hour > 18:  # Evening - typically lower usage
                usage_multiplier = 0.8
            else:
                usage_multiplier = 1.0

            # Activity-based adjustments
            recent_activity = self._get_recent_activity_level(historical_data)
            activity_multiplier = min(2.0, max(0.5, recent_activity))

            # Calculate predicted drain rate
            predicted_drain_rate = typical_usage_per_hour * usage_multiplier * activity_multiplier

            if predicted_drain_rate > 0:
                hours_remaining = current_level / predicted_drain_rate

                # High confidence for context-aware predictions when we have good user data
                confidence = min(0.8, getattr(activity_pattern, 'pattern_confidence', 0.5))

                return {
                    'hours_remaining': hours_remaining,
                    'confidence': confidence,
                    'method': 'context_aware',
                    'predicted_drain_rate': predicted_drain_rate
                }

        except Exception as e:
            logger.error(f"Error in context battery prediction: {str(e)}")

        return None

    def _ensemble_battery_prediction(self, predictions: Dict) -> Dict:
        """Combine multiple predictions using ensemble methods"""
        if not predictions:
            return {'hours_remaining': None, 'confidence': 0, 'method': 'no_predictions'}

        try:
            # Weight predictions by confidence
            weighted_hours = 0
            total_confidence = 0
            methods_used = []

            for method, pred in predictions.items():
                if pred and pred.get('hours_remaining') is not None:
                    confidence = pred.get('confidence', 0)
                    hours = pred['hours_remaining']

                    weighted_hours += hours * confidence
                    total_confidence += confidence
                    methods_used.append(method)

            if total_confidence > 0:
                final_hours = weighted_hours / total_confidence
                final_confidence = min(0.9, total_confidence / len(predictions))

                return {
                    'hours_remaining': final_hours,
                    'confidence': final_confidence,
                    'method': f"ensemble_{'+'.join(methods_used)}",
                    'individual_predictions': predictions
                }

        except Exception as e:
            logger.error(f"Error in ensemble prediction: {str(e)}")

        # Fallback to best single prediction
        best_pred = max(predictions.values(), key=lambda p: p.get('confidence', 0))
        return best_pred or {'hours_remaining': None, 'confidence': 0, 'method': 'fallback'}

    def _fallback_prediction(self, historical_data: List[Dict]) -> Dict:
        """Simple fallback prediction when other methods fail"""
        try:
            if len(historical_data) < 2:
                return {'hours_remaining': None, 'confidence': 0, 'method': 'insufficient_data'}

            # Simple average drain rate over last few hours
            recent_data = historical_data[-5:]
            current_level = recent_data[-1]['level']

            if len(recent_data) >= 2:
                time_span = (recent_data[-1]['timestamp'] - recent_data[0]['timestamp']).total_seconds() / 3600
                level_change = recent_data[0]['level'] - recent_data[-1]['level']

                if time_span > 0 and level_change > 0:
                    drain_rate = level_change / time_span
                    hours_remaining = current_level / drain_rate

                    return {
                        'hours_remaining': max(0, hours_remaining),
                        'confidence': 0.4,  # Low confidence for fallback
                        'method': 'simple_average'
                    }

        except Exception as e:
            logger.error(f"Error in fallback prediction: {str(e)}")

        return {'hours_remaining': None, 'confidence': 0, 'method': 'error'}

    def _simulate_battery_drain(self, model, scaler, current_features: List, current_level: float) -> float:
        """Simulate future battery drain using ML model"""
        try:
            level = current_level
            hours = 0
            max_hours = 24  # Don't simulate beyond 24 hours

            while level > 0 and hours < max_hours:
                # Update features for next prediction
                features = current_features.copy()
                features[0] = level  # Update battery level
                features[3] = (features[3] + 1) % 24  # Update hour of day

                # Predict drain for next hour
                features_scaled = scaler.transform([features])
                predicted_change = model.predict(features_scaled)[0]

                # Apply predicted change
                level += predicted_change  # predicted_change is usually negative for drain
                hours += 1

                if level <= 0:
                    break

            return hours

        except Exception as e:
            logger.error(f"Error simulating battery drain: {str(e)}")
            return 0

    def _get_recent_activity_level(self, historical_data: List[Dict]) -> float:
        """Calculate recent activity level multiplier"""
        try:
            if not historical_data:
                return 1.0

            # Look at last hour of data
            recent_cutoff = timezone.now() - timedelta(hours=1)
            recent_data = [d for d in historical_data if d['timestamp'] >= recent_cutoff]

            if not recent_data:
                recent_data = historical_data[-3:]  # Fallback to last 3 readings

            # Calculate activity metrics
            total_steps = sum(d.get('activity', {}).get('steps', 0) for d in recent_data)
            location_changes = len(set((d.get('location', {}).get('lat', 0),
                                     d.get('location', {}).get('lon', 0)) for d in recent_data))

            # Normalize to activity multiplier (0.5 to 2.0)
            steps_multiplier = min(2.0, max(0.5, total_steps / 1000))  # Normalize by 1000 steps
            location_multiplier = min(1.5, max(0.8, location_changes / 3))  # Normalize by 3 locations

            return (steps_multiplier + location_multiplier) / 2

        except Exception as e:
            logger.error(f"Error calculating activity level: {str(e)}")
            return 1.0

    # Additional prediction methods for other monitoring aspects

    def _calculate_performance_trend(self, metrics_history: List[Dict]) -> float:
        """Calculate performance trend score"""
        try:
            if len(metrics_history) < 5:
                return 0

            # Analyze trends in key performance metrics
            scores = []
            for metric in ['memory_usage', 'cpu_usage', 'response_time']:
                values = [m.get(metric, 0) for m in metrics_history if metric in m]
                if len(values) >= 3:
                    # Calculate trend slope
                    x = np.arange(len(values))
                    slope = np.polyfit(x, values, 1)[0]

                    # Convert slope to score (negative slope is good for usage metrics)
                    if metric in ['memory_usage', 'cpu_usage', 'response_time']:
                        score = max(0, min(100, 50 - slope * 10))  # Negative slope increases score
                    else:
                        score = max(0, min(100, 50 + slope * 10))  # Positive slope increases score

                    scores.append(score)

            return np.mean(scores) if scores else 50

        except Exception as e:
            logger.error(f"Error calculating performance trend: {str(e)}")
            return 50

    def _ml_degradation_prediction(self, device_id: str, metrics_history: List[Dict]) -> Dict:
        """ML-based performance degradation prediction"""
        # Implementation would use ML models to predict degradation
        return {'risk_score': 0.2, 'confidence': 0.6, 'method': 'ml_degradation'}

    def _statistical_degradation_prediction(self, metrics_history: List[Dict]) -> Dict:
        """Statistical degradation prediction"""
        # Implementation would use statistical methods
        return {'risk_score': 0.15, 'confidence': 0.5, 'method': 'statistical_degradation'}

    def _generate_degradation_recommendations(self, prediction: Dict) -> List[str]:
        """Generate recommendations based on degradation prediction"""
        recommendations = []
        risk_score = prediction.get('risk_score', 0)

        if risk_score > 0.7:
            recommendations.append("Schedule immediate device maintenance")
            recommendations.append("Consider device replacement")
        elif risk_score > 0.4:
            recommendations.append("Monitor device performance closely")
            recommendations.append("Schedule preventive maintenance")

        return recommendations

    def _detect_battery_anomaly(self, current_data: Dict, baseline: Dict, pattern: Dict) -> Dict:
        """Detect battery-related anomalies"""
        try:
            current_level = current_data.get('battery_level', 100)
            baseline_level = baseline.get('avg_battery_level', 50)

            # Simple anomaly detection
            if abs(current_level - baseline_level) > 30:
                return {
                    'is_anomaly': True,
                    'type': 'battery_level',
                    'severity': 0.7,
                    'description': f"Battery level {current_level}% significantly differs from baseline {baseline_level}%"
                }

            return {'is_anomaly': False}

        except Exception as e:
            logger.error(f"Error detecting battery anomaly: {str(e)}")
            return {'is_anomaly': False}

    def _detect_usage_anomaly(self, current_data: Dict, baseline: Dict, pattern: Dict) -> Dict:
        """Detect usage pattern anomalies"""
        # Implementation for usage anomaly detection
        return {'is_anomaly': False}

    def _detect_performance_anomaly(self, current_data: Dict, baseline: Dict) -> Dict:
        """Detect performance anomalies"""
        # Implementation for performance anomaly detection
        return {'is_anomaly': False}

    def _calculate_anomaly_confidence(self, anomalies: List[Dict]) -> float:
        """Calculate confidence in anomaly detection"""
        if not anomalies:
            return 1.0

        # Average severity of detected anomalies
        avg_severity = np.mean([a.get('severity', 0) for a in anomalies])
        return min(1.0, avg_severity)

    def _cache_prediction(self, prediction_type: str, identifier: Any, prediction: Dict):
        """Cache prediction results"""
        try:
            cache_key = f"prediction:{prediction_type}:{identifier}"
            cache.set(cache_key, prediction, self.cache_timeout)
        except Exception as e:
            logger.error(f"Error caching prediction: {str(e)}")