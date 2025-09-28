"""
Adaptive Threshold Updater Service
Automatically updates performance thresholds based on user behavior and historical data
"""

import logging
import numpy as np
from collections import defaultdict


from apps.streamlab.models import StreamEvent, TestRun
from apps.ai_testing.models import AdaptiveThreshold
from apps.issue_tracker.models import AnomalyOccurrence

logger = logging.getLogger(__name__)


class AdaptiveThresholdUpdater:
    """
    Updates performance thresholds dynamically based on user behavior patterns and ML analysis
    """

    def __init__(self):
        self.confidence_level = 0.95
        self.min_sample_size = 50
        self.seasonal_lookback_days = 90

    def update_all_thresholds(self) -> Dict[str, Any]:
        """
        Update all thresholds that are due for recalculation

        Returns:
            Dict containing update results
        """
        logger.info("Starting adaptive threshold update process")

        try:
            # Get thresholds that need updating
            due_thresholds = AdaptiveThreshold.get_thresholds_for_update()

            results = {
                'thresholds_processed': 0,
                'thresholds_updated': 0,
                'thresholds_failed': 0,
                'updates': [],
                'errors': []
            }

            for threshold in due_thresholds:
                try:
                    update_result = self.update_threshold(threshold)
                    results['thresholds_processed'] += 1

                    if update_result['updated']:
                        results['thresholds_updated'] += 1
                        results['updates'].append({
                            'threshold_id': str(threshold.id),
                            'metric': threshold.metric_name,
                            'old_value': update_result['old_value'],
                            'new_value': update_result['new_value'],
                            'confidence': update_result['confidence']
                        })
                    else:
                        results['thresholds_failed'] += 1
                        if update_result.get('error'):
                            results['errors'].append({
                                'threshold_id': str(threshold.id),
                                'error': update_result['error']
                            })

                except (ValueError, TypeError) as e:
                    logger.error(f"Error updating threshold {threshold.id}: {str(e)}")
                    results['thresholds_failed'] += 1
                    results['errors'].append({
                        'threshold_id': str(threshold.id),
                        'error': str(e)
                    })

            logger.info(f"Threshold update completed: {results['thresholds_updated']}/{results['thresholds_processed']} updated")
            return results

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error in threshold update process: {str(e)}")
            return {'error': str(e)}

    def update_threshold(self, threshold: AdaptiveThreshold) -> Dict[str, Any]:
        """
        Update a specific adaptive threshold

        Args:
            threshold: AdaptiveThreshold instance to update

        Returns:
            Dict containing update result
        """
        logger.debug(f"Updating threshold: {threshold.metric_name} for {threshold.user_segment}")

        try:
            # Get performance data for analysis
            performance_data = self._get_performance_data(threshold)

            if len(performance_data) < self.min_sample_size:
                return {
                    'updated': False,
                    'error': f'Insufficient data: {len(performance_data)} samples (min: {self.min_sample_size})'
                }

            # Calculate new threshold based on method
            new_value, confidence_interval, metadata = self._calculate_adaptive_threshold(
                threshold, performance_data
            )

            if new_value is None:
                return {
                    'updated': False,
                    'error': 'Failed to calculate new threshold value'
                }

            # Store old value for comparison
            old_value = threshold.adaptive_value

            # Update threshold
            threshold.update_threshold(
                new_value=new_value,
                confidence_interval=confidence_interval,
                sample_size=len(performance_data),
                method_metadata=metadata
            )

            # Calculate improvement score
            improvement_score = self._calculate_improvement_score(
                threshold, performance_data, old_value, new_value
            )

            # Validate threshold if enough data
            if len(performance_data) > 100:
                validation_data = {'improvement_score': improvement_score}
                threshold.validate_threshold(validation_data)

            return {
                'updated': True,
                'old_value': old_value,
                'new_value': new_value,
                'confidence': confidence_interval,
                'improvement_score': improvement_score,
                'sample_size': len(performance_data)
            }

        except (AttributeError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error updating threshold {threshold.id}: {str(e)}")
            return {'updated': False, 'error': str(e)}

    def _get_performance_data(self, threshold: AdaptiveThreshold) -> List[float]:
        """Get performance data for threshold calculation"""
        # Calculate lookback period
        lookback_days = min(threshold.update_frequency_hours * 24, self.seasonal_lookback_days)
        since_date = timezone.now() - timedelta(days=lookback_days)

        # Base query for stream events
        events_query = StreamEvent.objects.filter(
            timestamp__gte=since_date,
            outcome='success'
        )

        # Filter by platform if specified
        if threshold.platform != 'all':
            events_query = events_query.filter(
                client_os_version__icontains=threshold.platform.title()
            )

        # Filter by app version if specified
        if threshold.app_version:
            events_query = events_query.filter(
                client_app_version=threshold.app_version
            )

        # Apply user segment filtering
        events_query = self._apply_user_segment_filter(events_query, threshold.user_segment)

        # Extract metric values based on metric type
        metric_values = self._extract_metric_values(events_query, threshold.metric_name)

        # Remove outliers
        return self._remove_outliers(metric_values)

    def _apply_user_segment_filter(self, events_query, user_segment: str):
        """Apply user segment filtering to events query"""
        if user_segment == 'all_users':
            return events_query

        # This would integrate with user behavior analysis
        # For now, apply basic filtering based on device characteristics
        if user_segment == 'power_user':
            # Power users might have longer sessions, more interactions
            return events_query.filter(
                device_context__session_duration__gte=300  # 5+ minute sessions
            )
        elif user_segment == 'casual_user':
            # Casual users have shorter sessions
            return events_query.filter(
                device_context__session_duration__lt=300
            )
        elif user_segment == 'enterprise_user':
            # Enterprise users might use specific device models or during business hours
            return events_query.filter(
                timestamp__hour__gte=8,
                timestamp__hour__lt=18
            )

        return events_query

    def _extract_metric_values(self, events_query, metric_name: str) -> List[float]:
        """Extract metric values from stream events"""
        values = []

        if metric_name == 'latency_p95':
            # Calculate P95 latency for each test run
            runs = TestRun.objects.filter(
                events__in=events_query
            ).distinct()

            for run in runs:
                latencies = list(run.events.filter(
                    id__in=events_query
                ).values_list('latency_ms', flat=True))

                if latencies:
                    p95 = np.percentile(latencies, 95)
                    values.append(p95)

        elif metric_name == 'latency_p99':
            runs = TestRun.objects.filter(
                events__in=events_query
            ).distinct()

            for run in runs:
                latencies = list(run.events.filter(
                    id__in=events_query
                ).values_list('latency_ms', flat=True))

                if latencies:
                    p99 = np.percentile(latencies, 99)
                    values.append(p99)

        elif metric_name == 'error_rate':
            # Calculate error rates for time windows
            for event in events_query.iterator():
                # Get events in same time window
                window_start = event.timestamp - timedelta(minutes=5)
                window_end = event.timestamp + timedelta(minutes=5)

                window_events = StreamEvent.objects.filter(
                    timestamp__range=(window_start, window_end)
                )

                total_events = window_events.count()
                error_events = window_events.filter(outcome='error').count()

                if total_events > 0:
                    error_rate = error_events / total_events
                    values.append(error_rate)

        elif metric_name == 'jank_score':
            values = list(events_query.filter(
                jank_score__isnull=False
            ).values_list('jank_score', flat=True))

        elif metric_name == 'composition_time':
            values = list(events_query.filter(
                composition_time_ms__isnull=False
            ).values_list('composition_time_ms', flat=True))

        elif metric_name in ['memory_usage', 'battery_drain', 'frame_drop_rate']:
            # Extract from device context JSON
            for event in events_query.filter(device_context__isnull=False).iterator():
                if event.device_context and metric_name in event.device_context:
                    values.append(float(event.device_context[metric_name]))

        elif metric_name == 'startup_time':
            # Extract startup times from performance metrics
            for event in events_query.filter(
                performance_metrics__isnull=False
            ).iterator():
                if (event.performance_metrics and
                    'startup_time_ms' in event.performance_metrics):
                    values.append(float(event.performance_metrics['startup_time_ms']))

        return [v for v in values if v is not None and not np.isnan(v)]

    def _remove_outliers(self, values: List[float]) -> List[float]:
        """Remove statistical outliers using IQR method"""
        if len(values) < 4:
            return values

        values_array = np.array(values)
        Q1 = np.percentile(values_array, 25)
        Q3 = np.percentile(values_array, 75)
        IQR = Q3 - Q1

        # Define outlier bounds
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        # Filter outliers
        filtered_values = [v for v in values if lower_bound <= v <= upper_bound]

        logger.debug(f"Filtered {len(values) - len(filtered_values)} outliers from {len(values)} values")
        return filtered_values

    def _calculate_adaptive_threshold(self, threshold: AdaptiveThreshold,
                                    performance_data: List[float]) -> Tuple[float, Tuple[float, float], Dict]:
        """Calculate new adaptive threshold value"""
        try:
            data_array = np.array(performance_data)

            if threshold.adaptation_method == 'percentile_based':
                return self._calculate_percentile_threshold(data_array, threshold)

            elif threshold.adaptation_method == 'time_series':
                return self._calculate_time_series_threshold(data_array, threshold)

            elif threshold.adaptation_method == 'ml_regression':
                return self._calculate_ml_regression_threshold(data_array, threshold)

            elif threshold.adaptation_method == 'seasonal_aware':
                return self._calculate_seasonal_threshold(data_array, threshold)

            elif threshold.adaptation_method == 'user_behavior':
                return self._calculate_user_behavior_threshold(data_array, threshold)

            else:
                # Default to percentile-based
                return self._calculate_percentile_threshold(data_array, threshold)

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error calculating adaptive threshold: {str(e)}")
            return None, (0, 0), {}

    def _calculate_percentile_threshold(self, data: np.ndarray, threshold: AdaptiveThreshold
                                      ) -> Tuple[float, Tuple[float, float], Dict]:
        """Calculate threshold based on percentiles"""
        # Use 95th percentile as threshold for most metrics
        percentile = 95 if 'latency' in threshold.metric_name or 'time' in threshold.metric_name else 90

        new_value = np.percentile(data, percentile)

        # Calculate confidence interval using bootstrap
        bootstrap_samples = []
        n_bootstrap = 1000
        n_sample = len(data)

        for _ in range(n_bootstrap):
            bootstrap_sample = np.random.choice(data, size=n_sample, replace=True)
            bootstrap_samples.append(np.percentile(bootstrap_sample, percentile))

        lower_bound = np.percentile(bootstrap_samples, (1 - threshold.confidence_level) / 2 * 100)
        upper_bound = np.percentile(bootstrap_samples, (1 + threshold.confidence_level) / 2 * 100)

        metadata = {
            'method': 'percentile_based',
            'percentile': percentile,
            'data_mean': float(np.mean(data)),
            'data_std': float(np.std(data)),
            'sample_size': len(data)
        }

        return float(new_value), (float(lower_bound), float(upper_bound)), metadata

    def _calculate_time_series_threshold(self, data: np.ndarray, threshold: AdaptiveThreshold
                                       ) -> Tuple[float, Tuple[float, float], Dict]:
        """Calculate threshold using time series analysis"""
        # Implement exponentially weighted moving average with trend detection
        alpha = 0.3  # Smoothing factor

        if len(data) < 10:
            return self._calculate_percentile_threshold(data, threshold)

        # Calculate EWMA
        ewma = [data[0]]
        for i in range(1, len(data)):
            ewma.append(alpha * data[i] + (1 - alpha) * ewma[-1])

        # Detect trend
        recent_ewma = ewma[-min(10, len(ewma)):]
        trend_slope, _, _, _, _ = stats.linregress(range(len(recent_ewma)), recent_ewma)

        # Adjust threshold based on trend
        base_threshold = ewma[-1]
        if trend_slope > 0:
            # Increasing trend - be more permissive
            new_value = base_threshold + (2 * np.std(data))
        else:
            # Stable or decreasing trend - be stricter
            new_value = base_threshold + (1.5 * np.std(data))

        # Calculate confidence interval
        std_error = np.std(data) / np.sqrt(len(data))
        z_score = stats.norm.ppf((1 + threshold.confidence_level) / 2)

        lower_bound = new_value - z_score * std_error
        upper_bound = new_value + z_score * std_error

        metadata = {
            'method': 'time_series',
            'trend_slope': float(trend_slope),
            'ewma_final': float(ewma[-1]),
            'adjustment_factor': 2.0 if trend_slope > 0 else 1.5
        }

        return float(new_value), (float(lower_bound), float(upper_bound)), metadata

    def _calculate_ml_regression_threshold(self, data: np.ndarray, threshold: AdaptiveThreshold
                                         ) -> Tuple[float, Tuple[float, float], Dict]:
        """Calculate threshold using ML regression analysis"""
        # For now, implement a sophisticated statistical approach
        # In production, this would use trained ML models

        if len(data) < 20:
            return self._calculate_percentile_threshold(data, threshold)

        # Use rolling statistics to predict next threshold
        window_size = min(10, len(data) // 2)
        rolling_means = []
        rolling_stds = []

        for i in range(window_size, len(data)):
            window = data[i-window_size:i]
            rolling_means.append(np.mean(window))
            rolling_stds.append(np.std(window))

        # Predict next values
        predicted_mean = np.mean(rolling_means[-5:])  # Average of last 5 windows
        predicted_std = np.mean(rolling_stds[-5:])

        # Set threshold as mean + 2.5 * std
        new_value = predicted_mean + 2.5 * predicted_std

        # Confidence interval based on prediction uncertainty
        prediction_std = np.std(rolling_means[-5:])
        z_score = stats.norm.ppf((1 + threshold.confidence_level) / 2)

        lower_bound = new_value - z_score * prediction_std
        upper_bound = new_value + z_score * prediction_std

        metadata = {
            'method': 'ml_regression',
            'predicted_mean': float(predicted_mean),
            'predicted_std': float(predicted_std),
            'prediction_uncertainty': float(prediction_std)
        }

        return float(new_value), (float(lower_bound), float(upper_bound)), metadata

    def _calculate_seasonal_threshold(self, data: np.ndarray, threshold: AdaptiveThreshold
                                    ) -> Tuple[float, Tuple[float, float], Dict]:
        """Calculate threshold with seasonal awareness"""
        # Get current time context
        current_time = timezone.now()
        hour = current_time.hour
        weekday = current_time.weekday()

        # Apply seasonal adjustment if patterns exist
        adjustment_factor = threshold.get_seasonal_adjustment(current_time)

        # Calculate base threshold
        base_value, (base_lower, base_upper), base_metadata = self._calculate_percentile_threshold(
            data, threshold
        )

        # Apply seasonal adjustment
        new_value = base_value * adjustment_factor
        lower_bound = base_lower * adjustment_factor
        upper_bound = base_upper * adjustment_factor

        # Detect and update seasonal patterns
        seasonal_patterns = self._detect_seasonal_patterns(data, threshold)

        metadata = {
            **base_metadata,
            'method': 'seasonal_aware',
            'seasonal_adjustment': adjustment_factor,
            'current_hour': hour,
            'current_weekday': weekday,
            'detected_patterns': seasonal_patterns
        }

        return float(new_value), (float(lower_bound), float(upper_bound)), metadata

    def _calculate_user_behavior_threshold(self, data: np.ndarray, threshold: AdaptiveThreshold
                                         ) -> Tuple[float, Tuple[float, float], Dict]:
        """Calculate threshold based on user behavior patterns"""
        # Segment users and calculate thresholds per segment
        if threshold.user_segment == 'all_users':
            # Use clustering to identify user segments
            user_segments = self._identify_user_segments(data)
        else:
            user_segments = {threshold.user_segment: data}

        # Calculate threshold for the specific segment
        segment_data = user_segments.get(threshold.user_segment, data)

        # Use different percentiles for different user segments
        percentile_map = {
            'power_user': 98,    # More tolerant for power users
            'casual_user': 90,   # Stricter for casual users
            'enterprise_user': 95,
            'developer': 99,     # Most tolerant for developers
            'all_users': 95
        }

        percentile = percentile_map.get(threshold.user_segment, 95)
        new_value = np.percentile(segment_data, percentile)

        # Calculate confidence interval
        std_error = np.std(segment_data) / np.sqrt(len(segment_data))
        z_score = stats.norm.ppf((1 + threshold.confidence_level) / 2)

        lower_bound = new_value - z_score * std_error
        upper_bound = new_value + z_score * std_error

        metadata = {
            'method': 'user_behavior',
            'user_segment': threshold.user_segment,
            'percentile_used': percentile,
            'segment_size': len(segment_data),
            'total_users': len(data)
        }

        return float(new_value), (float(lower_bound), float(upper_bound)), metadata

    def _identify_user_segments(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """Identify user segments using clustering"""
        if len(data) < 10:
            return {'all_users': data}

        try:
            # Simple k-means clustering to identify segments
            data_reshaped = data.reshape(-1, 1)
            scaler = StandardScaler()
            data_scaled = scaler.fit_transform(data_reshaped)

            # Use 3 clusters for power/casual/enterprise users
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(data_scaled)

            # Map clusters to user segments
            cluster_centers = scaler.inverse_transform(kmeans.cluster_centers_)
            sorted_centers = sorted(enumerate(cluster_centers.flatten()), key=lambda x: x[1])

            segment_mapping = {
                sorted_centers[0][0]: 'casual_user',    # Lowest values
                sorted_centers[1][0]: 'enterprise_user', # Medium values
                sorted_centers[2][0]: 'power_user'      # Highest values
            }

            segments = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                segment_name = segment_mapping[label]
                segments[segment_name].append(data[i])

            return {k: np.array(v) for k, v in segments.items()}

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error identifying user segments: {str(e)}")
            return {'all_users': data}

    def _detect_seasonal_patterns(self, data: np.ndarray, threshold: AdaptiveThreshold) -> Dict:
        """Detect seasonal patterns in performance data"""
        # This would implement more sophisticated pattern detection
        # For now, return basic pattern structure
        return {
            'hourly': {},
            'weekday': {},
            'detected': False
        }

    def _calculate_improvement_score(self, threshold: AdaptiveThreshold, performance_data: List[float],
                                   old_value: float, new_value: float) -> float:
        """Calculate improvement score for the threshold update"""
        try:
            # Calculate how many data points would be flagged as anomalies
            data_array = np.array(performance_data)

            old_violations = np.sum(data_array > old_value)
            new_violations = np.sum(data_array > new_value)

            # Calculate false positive rate (assuming most data points are normal)
            old_fp_rate = old_violations / len(data_array)
            new_fp_rate = new_violations / len(data_array)

            # Target false positive rate is around 5%
            target_fp_rate = 0.05

            # Calculate improvement (closer to target = better)
            old_distance = abs(old_fp_rate - target_fp_rate)
            new_distance = abs(new_fp_rate - target_fp_rate)

            if old_distance == 0:
                return 1.0  # Perfect score if old threshold was already optimal

            improvement = max(0.0, (old_distance - new_distance) / old_distance)

            return improvement

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error calculating improvement score: {str(e)}")
            return 0.5  # Neutral score on error

    def create_adaptive_threshold(self, metric_name: str, user_segment: str = 'all_users',
                                 platform: str = 'all', app_version: str = None) -> AdaptiveThreshold:
        """Create a new adaptive threshold"""
        try:
            # Get initial baseline from recent data
            temp_threshold = AdaptiveThreshold(
                metric_name=metric_name,
                user_segment=user_segment,
                platform=platform,
                app_version=app_version or '',
                static_baseline=0,
                adaptive_value=0,
                confidence_lower=0,
                confidence_upper=0,
                adaptation_method='percentile_based'
            )

            performance_data = self._get_performance_data(temp_threshold)

            if len(performance_data) < self.min_sample_size:
                logger.warning(f"Insufficient data for creating threshold: {metric_name}")
                # Use default values
                static_baseline = self._get_default_threshold(metric_name)
            else:
                static_baseline = np.percentile(performance_data, 95)

            # Create and save threshold
            threshold = AdaptiveThreshold.objects.create(
                metric_name=metric_name,
                user_segment=user_segment,
                platform=platform,
                app_version=app_version or '',
                static_baseline=static_baseline,
                adaptive_value=static_baseline,
                confidence_lower=static_baseline * 0.9,
                confidence_upper=static_baseline * 1.1,
                adaptation_method='percentile_based'
            )

            # Immediately update with current data if available
            if len(performance_data) >= self.min_sample_size:
                self.update_threshold(threshold)

            return threshold

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error creating adaptive threshold: {str(e)}")
            raise

    def _get_default_threshold(self, metric_name: str) -> float:
        """Get default threshold values for metrics"""
        defaults = {
            'latency_p95': 1000.0,      # 1 second
            'latency_p99': 2000.0,      # 2 seconds
            'error_rate': 0.01,         # 1%
            'jank_score': 10.0,         # Arbitrary jank units
            'composition_time': 16.0,   # 16ms for 60fps
            'memory_usage': 512.0,      # 512MB
            'battery_drain': 10.0,      # 10% per hour
            'frame_drop_rate': 0.05,    # 5%
            'startup_time': 3000.0      # 3 seconds
        }
        return defaults.get(metric_name, 100.0)

    def analyze_threshold_effectiveness(self, threshold_id: str,
                                      days: int = 30) -> Dict[str, Any]:
        """Analyze how effective a threshold has been"""
        try:
            threshold = AdaptiveThreshold.objects.get(id=threshold_id)

            # Get performance data for analysis period
            since_date = timezone.now() - timedelta(days=days)
            performance_data = self._get_performance_data(threshold)

            if not performance_data:
                return {'error': 'No performance data available'}

            # Calculate metrics
            data_array = np.array(performance_data)
            violations = np.sum(data_array > threshold.adaptive_value)
            violation_rate = violations / len(data_array)

            # Get anomalies in the same period
            related_anomalies = AnomalyOccurrence.objects.filter(
                created_at__gte=since_date,
                signature__anomaly_type__icontains=threshold.metric_name.split('_')[0]
            )

            # Calculate detection accuracy
            true_anomalies = related_anomalies.count()
            detected_violations = violations

            precision = 0.5  # Placeholder - would calculate based on validated anomalies
            recall = min(1.0, detected_violations / max(true_anomalies, 1))

            return {
                'threshold_id': threshold_id,
                'analysis_period_days': days,
                'performance_data_points': len(performance_data),
                'current_threshold': threshold.adaptive_value,
                'violations_detected': int(violations),
                'violation_rate': round(violation_rate, 4),
                'related_anomalies': true_anomalies,
                'precision_estimate': round(precision, 3),
                'recall_estimate': round(recall, 3),
                'effectiveness_score': threshold.adaptation_effectiveness,
                'recommendations': self._generate_threshold_recommendations(
                    threshold, violation_rate, precision, recall
                )
            }

        except AdaptiveThreshold.DoesNotExist:
            return {'error': 'Threshold not found'}
        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error analyzing threshold effectiveness: {str(e)}")
            return {'error': str(e)}

    def _generate_threshold_recommendations(self, threshold: AdaptiveThreshold,
                                          violation_rate: float, precision: float,
                                          recall: float) -> List[str]:
        """Generate recommendations for threshold improvement"""
        recommendations = []

        if violation_rate > 0.1:  # >10% violation rate
            recommendations.append("Consider increasing threshold - high false positive rate")

        if violation_rate < 0.01:  # <1% violation rate
            recommendations.append("Consider decreasing threshold - may miss real issues")

        if precision < 0.5:
            recommendations.append("Improve threshold precision by analyzing false positives")

        if recall < 0.7:
            recommendations.append("Increase threshold sensitivity to catch more anomalies")

        if threshold.sample_size < 100:
            recommendations.append("Collect more performance data for better threshold accuracy")

        if not threshold.is_seasonal_aware and threshold.metric_name in ['latency_p95', 'error_rate']:
            recommendations.append("Consider enabling seasonal awareness for this metric")

        return recommendations