"""
Advanced Attendance Analytics System
Real-time analytics and insights for attendance patterns using face recognition data
"""

import logging
import numpy as np
from django.utils import timezone
from apps.attendance.models import PeopleEventlog
# Removed: anomaly_detection imports - app removed
# Removed: behavioral_analytics imports - app removed

logger = logging.getLogger(__name__)


class AttendanceAnalyticsEngine:
    """Advanced analytics engine for attendance patterns and insights"""
    
    def __init__(self):
        """Initialize analytics engine"""
        self.cache_timeout = 300  # 5 minutes
        self.analysis_window_days = 30
        
    def generate_attendance_insights(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        location_filters: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive attendance insights and analytics
        
        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            user_id: Specific user ID to analyze
            location_filters: List of location codes to filter by
            
        Returns:
            Comprehensive analytics results
        """
        try:
            if not start_date:
                start_date = timezone.now() - timedelta(days=self.analysis_window_days)
            if not end_date:
                end_date = timezone.now()
                
            logger.info(f"Generating attendance insights for period {start_date} to {end_date}")
            
            insights = {
                'analysis_period': {
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration_days': (end_date - start_date).days
                },
                'overall_metrics': {},
                'face_recognition_analytics': {},
                'anomaly_insights': {},
                'behavioral_patterns': {},
                'fraud_analytics': {},
                'predictive_insights': {},
                'recommendations': []
            }
            
            # Build base queryset
            base_queryset = PeopleEventlog.objects.filter(
                punchintime__gte=start_date,
                punchintime__lte=end_date
            )
            
            if user_id:
                base_queryset = base_queryset.filter(people_id=user_id)
            
            if location_filters:
                base_queryset = base_queryset.filter(
                    geofence_id__in=location_filters
                )
            
            # 1. Overall Metrics Analysis
            insights['overall_metrics'] = self._analyze_overall_metrics(base_queryset)
            
            # 2. Face Recognition Analytics
            insights['face_recognition_analytics'] = self._analyze_face_recognition_patterns(base_queryset)
            
            # 3. Anomaly Detection Insights
            insights['anomaly_insights'] = self._analyze_anomaly_patterns(base_queryset)
            
            # 4. Behavioral Pattern Analysis
            insights['behavioral_patterns'] = self._analyze_behavioral_patterns(base_queryset)
            
            # 5. Fraud Analytics
            insights['fraud_analytics'] = self._analyze_fraud_patterns(base_queryset)
            
            # 6. Predictive Insights
            insights['predictive_insights'] = self._generate_predictive_insights(base_queryset)
            
            # 7. Generate Recommendations
            insights['recommendations'] = self._generate_analytics_recommendations(insights)
            
            # Cache results
            cache_key = f"attendance_insights_{hash(str(insights['analysis_period']))}"
            cache.set(cache_key, insights, self.cache_timeout)
            
            logger.info("Attendance insights generated successfully")
            return insights
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error generating attendance insights: {str(e)}", exc_info=True)
            return {'error': str(e)}
    
    def _analyze_overall_metrics(self, queryset) -> Dict[str, Any]:
        """Analyze overall attendance metrics"""
        try:
            total_records = queryset.count()
            
            # Basic statistics
            stats = queryset.aggregate(
                unique_users=Count('people_id', distinct=True),
                unique_locations=Count('geofence_id', distinct=True),
                avg_daily_entries=Count('id') / 30.0,  # Approximate
                face_recognition_attempts=Count(
                    Case(When(facerecognitionin=True, then=1), output_field=IntegerField())
                ),
                successful_face_recognition=Count(
                    Case(When(
                        facerecognitionin=True,
                        peventlogextras__verified_in=True,
                        then=1
                    ), output_field=IntegerField())
                )
            )
            
            # Calculate success rates
            face_success_rate = 0.0
            if stats['face_recognition_attempts'] > 0:
                face_success_rate = stats['successful_face_recognition'] / stats['face_recognition_attempts']
            
            # Time distribution analysis
            hourly_distribution = queryset.annotate(
                hour=Extract('punchintime__hour')
            ).values('hour').annotate(count=Count('id')).order_by('hour')
            
            # Daily patterns
            daily_distribution = queryset.annotate(
                weekday=Extract('punchintime__week_day')
            ).values('weekday').annotate(count=Count('id')).order_by('weekday')
            
            return {
                'total_attendance_records': total_records,
                'unique_users': stats['unique_users'],
                'unique_locations': stats['unique_locations'],
                'average_daily_entries': round(stats['avg_daily_entries'], 2),
                'face_recognition_success_rate': round(face_success_rate * 100, 2),
                'face_recognition_attempts': stats['face_recognition_attempts'],
                'successful_face_recognitions': stats['successful_face_recognition'],
                'hourly_distribution': list(hourly_distribution),
                'daily_distribution': list(daily_distribution),
                'peak_hours': self._identify_peak_hours(hourly_distribution),
                'peak_days': self._identify_peak_days(daily_distribution)
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error analyzing overall metrics: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_face_recognition_patterns(self, queryset) -> Dict[str, Any]:
        """Analyze face recognition patterns and performance"""
        try:
            # Face recognition performance by time period
            face_records = queryset.filter(facerecognitionin=True)
            
            if not face_records.exists():
                return {'no_face_recognition_data': True}
            
            # Performance trends over time
            daily_performance = face_records.annotate(
                date=TruncDate('punchintime')
            ).values('date').annotate(
                total_attempts=Count('id'),
                successful_attempts=Count(
                    Case(When(
                        peventlogextras__verified_in=True,
                        then=1
                    ), output_field=IntegerField())
                )
            ).order_by('date')
            
            # Distance analysis from face recognition extras
            distance_stats = self._analyze_face_distances(face_records)
            
            # Model performance analysis
            model_performance = self._analyze_model_performance()
            
            # Quality patterns
            quality_patterns = self._analyze_face_quality_patterns(face_records)
            
            return {
                'total_face_recognition_attempts': face_records.count(),
                'daily_performance_trends': list(daily_performance),
                'distance_statistics': distance_stats,
                'model_performance': model_performance,
                'quality_patterns': quality_patterns,
                'recognition_reliability_score': self._calculate_reliability_score(face_records)
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error analyzing face recognition patterns: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_anomaly_patterns(self, queryset) -> Dict[str, Any]:
        """Analyze anomaly detection patterns in attendance data"""
        try:
            # Get anomaly detection results for these attendance records
            attendance_ids = list(queryset.values_list('id', flat=True))
            
            anomalies = AnomalyDetectionResult.objects.filter(
                content_type__model='peopleeventlog',
                object_id__in=attendance_ids
            )
            
            if not anomalies.exists():
                return {'no_anomaly_data': True}
            
            # Anomaly distribution by type
            anomaly_types = anomalies.values('anomaly_type').annotate(
                count=Count('id'),
                avg_confidence=Avg('confidence_score')
            ).order_by('-count')
            
            # Severity distribution
            severity_distribution = anomalies.values('severity').annotate(
                count=Count('id')
            ).order_by('severity')
            
            # Temporal anomaly patterns
            temporal_patterns = anomalies.annotate(
                hour=Extract('detection_timestamp__hour'),
                weekday=Extract('detection_timestamp__week_day')
            ).values('hour', 'weekday').annotate(
                anomaly_count=Count('id')
            )
            
            # User anomaly profiles
            user_anomaly_stats = anomalies.values('object_id').annotate(
                anomaly_count=Count('id'),
                max_severity=Max('confidence_score'),
                anomaly_types=Count('anomaly_type', distinct=True)
            ).order_by('-anomaly_count')[:10]
            
            return {
                'total_anomalies_detected': anomalies.count(),
                'anomaly_rate': round(anomalies.count() / queryset.count() * 100, 2),
                'anomaly_type_distribution': list(anomaly_types),
                'severity_distribution': list(severity_distribution),
                'temporal_anomaly_patterns': list(temporal_patterns),
                'high_risk_users': list(user_anomaly_stats),
                'anomaly_trends': self._calculate_anomaly_trends(anomalies)
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error analyzing anomaly patterns: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_behavioral_patterns(self, queryset) -> Dict[str, Any]:
        """Analyze behavioral patterns and user profiles"""
        try:
            # Get unique users in the dataset
            user_ids = list(queryset.values_list('people_id', flat=True).distinct())
            
            # Get behavioral profiles for these users
            profiles = UserBehaviorProfile.objects.filter(user_id__in=user_ids)
            
            if not profiles.exists():
                return {'no_behavioral_data': True}
            
            # Behavioral metrics aggregation
            behavioral_stats = profiles.aggregate(
                avg_regularity=Avg('attendance_regularity_score'),
                avg_fraud_risk=Avg('fraud_risk_score'),
                high_risk_users=Count(
                    Case(When(fraud_risk_score__gt=0.7, then=1), output_field=IntegerField())
                ),
                low_regularity_users=Count(
                    Case(When(attendance_regularity_score__lt=0.3, then=1), output_field=IntegerField())
                )
            )
            
            # Time pattern consistency analysis
            time_consistency = self._analyze_time_pattern_consistency(queryset, profiles)
            
            # Location pattern analysis
            location_consistency = self._analyze_location_pattern_consistency(queryset, profiles)
            
            # Risk distribution
            risk_distribution = profiles.values(
                'fraud_risk_score'
            ).annotate(
                risk_range=Case(
                    When(fraud_risk_score__lt=0.3, then='Low'),
                    When(fraud_risk_score__lt=0.7, then='Medium'),
                    default='High'
                )
            ).values('risk_range').annotate(count=Count('id'))
            
            return {
                'total_behavioral_profiles': profiles.count(),
                'average_regularity_score': round(behavioral_stats['avg_regularity'] or 0, 2),
                'average_fraud_risk_score': round(behavioral_stats['avg_fraud_risk'] or 0, 2),
                'high_risk_users': behavioral_stats['high_risk_users'],
                'irregular_attendance_users': behavioral_stats['low_regularity_users'],
                'time_pattern_consistency': time_consistency,
                'location_pattern_consistency': location_consistency,
                'risk_distribution': list(risk_distribution),
                'behavioral_insights': self._generate_behavioral_insights(profiles)
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error analyzing behavioral patterns: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_fraud_patterns(self, queryset) -> Dict[str, Any]:
        """Analyze fraud patterns and detection results"""
        try:
            # Get verification logs for fraud analysis
            verification_logs = FaceVerificationLog.objects.filter(
                attendance_record__in=queryset,
                verification_timestamp__gte=timezone.now() - timedelta(days=self.analysis_window_days)
            )
            
            if not verification_logs.exists():
                return {'no_fraud_data': True}
            
            # Fraud detection statistics
            fraud_stats = verification_logs.aggregate(
                total_verifications=Count('id'),
                high_fraud_risk=Count(
                    Case(When(fraud_risk_score__gt=0.7, then=1), output_field=IntegerField())
                ),
                spoof_detected=Count(
                    Case(When(spoof_detected=True, then=1), output_field=IntegerField())
                ),
                avg_fraud_risk=Avg('fraud_risk_score'),
                max_fraud_risk=Max('fraud_risk_score')
            )
            
            # Fraud indicators analysis
            fraud_indicators = self._analyze_fraud_indicators(verification_logs)
            
            # Geographic fraud patterns
            geographic_fraud = self._analyze_geographic_fraud_patterns(queryset, verification_logs)
            
            # Temporal fraud patterns
            temporal_fraud = self._analyze_temporal_fraud_patterns(verification_logs)
            
            # User fraud profiles
            user_fraud_profiles = verification_logs.values('user_id').annotate(
                total_attempts=Count('id'),
                fraud_attempts=Count(
                    Case(When(fraud_risk_score__gt=0.5, then=1), output_field=IntegerField())
                ),
                max_fraud_score=Max('fraud_risk_score'),
                spoof_attempts=Count(
                    Case(When(spoof_detected=True, then=1), output_field=IntegerField())
                )
            ).order_by('-fraud_attempts')[:10]
            
            return {
                'total_fraud_evaluations': fraud_stats['total_verifications'],
                'high_risk_detections': fraud_stats['high_fraud_risk'],
                'spoofing_attempts': fraud_stats['spoof_detected'],
                'average_fraud_risk': round(fraud_stats['avg_fraud_risk'] or 0, 3),
                'maximum_fraud_risk': round(fraud_stats['max_fraud_risk'] or 0, 3),
                'fraud_detection_rate': round(
                    (fraud_stats['high_fraud_risk'] / fraud_stats['total_verifications']) * 100, 2
                ) if fraud_stats['total_verifications'] > 0 else 0,
                'fraud_indicators_analysis': fraud_indicators,
                'geographic_fraud_patterns': geographic_fraud,
                'temporal_fraud_patterns': temporal_fraud,
                'high_risk_user_profiles': list(user_fraud_profiles)
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error analyzing fraud patterns: {str(e)}")
            return {'error': str(e)}
    
    def _generate_predictive_insights(self, queryset) -> Dict[str, Any]:
        """Generate predictive insights and forecasts"""
        try:
            # Historical trend analysis
            historical_trends = self._analyze_historical_trends(queryset)
            
            # Peak time predictions
            peak_predictions = self._predict_peak_times(queryset)
            
            # Risk forecasting
            risk_forecast = self._forecast_risk_levels(queryset)
            
            # Capacity planning insights
            capacity_insights = self._generate_capacity_insights(queryset)
            
            return {
                'historical_trends': historical_trends,
                'peak_time_predictions': peak_predictions,
                'risk_level_forecasts': risk_forecast,
                'capacity_planning': capacity_insights,
                'prediction_confidence': self._calculate_prediction_confidence(queryset)
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error generating predictive insights: {str(e)}")
            return {'error': str(e)}
    
    def _generate_analytics_recommendations(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on analytics"""
        recommendations = []
        
        try:
            # Face recognition optimization recommendations
            face_analytics = insights.get('face_recognition_analytics', {})
            if not face_analytics.get('no_face_recognition_data', False):
                if face_analytics.get('recognition_reliability_score', 0) < 0.8:
                    recommendations.append({
                        'category': 'FACE_RECOGNITION_OPTIMIZATION',
                        'priority': 'HIGH',
                        'title': 'Improve Face Recognition Accuracy',
                        'description': 'Face recognition reliability is below optimal threshold',
                        'actions': [
                            'Re-train face recognition models with recent data',
                            'Update user face embeddings with higher quality images',
                            'Implement enhanced preprocessing algorithms'
                        ]
                    })
            
            # Fraud prevention recommendations
            fraud_analytics = insights.get('fraud_analytics', {})
            if not fraud_analytics.get('no_fraud_data', False):
                fraud_rate = fraud_analytics.get('fraud_detection_rate', 0)
                if fraud_rate > 5:  # More than 5% fraud detection rate
                    recommendations.append({
                        'category': 'FRAUD_PREVENTION',
                        'priority': 'CRITICAL',
                        'title': 'High Fraud Detection Rate Alert',
                        'description': f'Current fraud detection rate is {fraud_rate}%',
                        'actions': [
                            'Implement additional verification steps for high-risk users',
                            'Review and update fraud detection algorithms',
                            'Conduct security audit of attendance systems'
                        ]
                    })
            
            # Anomaly detection recommendations
            anomaly_insights = insights.get('anomaly_insights', {})
            if not anomaly_insights.get('no_anomaly_data', False):
                anomaly_rate = anomaly_insights.get('anomaly_rate', 0)
                if anomaly_rate > 10:  # More than 10% anomaly rate
                    recommendations.append({
                        'category': 'ANOMALY_MANAGEMENT',
                        'priority': 'HIGH',
                        'title': 'High Anomaly Detection Rate',
                        'description': f'Current anomaly detection rate is {anomaly_rate}%',
                        'actions': [
                            'Review anomaly detection thresholds',
                            'Investigate common anomaly patterns',
                            'Provide additional training to users'
                        ]
                    })
            
            # Performance optimization recommendations
            overall_metrics = insights.get('overall_metrics', {})
            if overall_metrics.get('face_recognition_success_rate', 0) < 85:
                recommendations.append({
                    'category': 'PERFORMANCE_OPTIMIZATION',
                    'priority': 'MEDIUM',
                    'title': 'Face Recognition Success Rate Below Target',
                    'description': 'Consider system optimization for better performance',
                    'actions': [
                        'Optimize face recognition model parameters',
                        'Improve image capture guidelines',
                        'Implement adaptive thresholds'
                    ]
                })
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error generating recommendations: {str(e)}")
        
        return recommendations
    
    # Helper methods for detailed analysis
    def _identify_peak_hours(self, hourly_distribution) -> List[int]:
        """Identify peak hours from hourly distribution"""
        if not hourly_distribution:
            return []
        
        sorted_hours = sorted(hourly_distribution, key=lambda x: x['count'], reverse=True)
        return [hour['hour'] for hour in sorted_hours[:3]]
    
    def _identify_peak_days(self, daily_distribution) -> List[int]:
        """Identify peak days from daily distribution"""
        if not daily_distribution:
            return []
        
        sorted_days = sorted(daily_distribution, key=lambda x: x['count'], reverse=True)
        return [day['weekday'] for day in sorted_days[:3]]
    
    def _analyze_face_distances(self, face_records) -> Dict[str, Any]:
        """Analyze face recognition distance patterns"""
        try:
            distances = []
            
            for record in face_records.iterator():
                if record.peventlogextras and 'distance_in' in record.peventlogextras:
                    distances.append(float(record.peventlogextras['distance_in']))
            
            if not distances:
                return {'no_distance_data': True}
            
            distances_array = np.array(distances)
            
            return {
                'mean_distance': float(np.mean(distances_array)),
                'median_distance': float(np.median(distances_array)),
                'std_distance': float(np.std(distances_array)),
                'min_distance': float(np.min(distances_array)),
                'max_distance': float(np.max(distances_array)),
                'distance_percentiles': {
                    '25th': float(np.percentile(distances_array, 25)),
                    '75th': float(np.percentile(distances_array, 75)),
                    '90th': float(np.percentile(distances_array, 90)),
                    '95th': float(np.percentile(distances_array, 95))
                }
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error analyzing face distances: {str(e)}")
            return {'error': str(e)}
    
    def _analyze_model_performance(self) -> Dict[str, Any]:
        """Analyze face recognition model performance"""
        try:
            # Get recent verification logs
            recent_logs = FaceVerificationLog.objects.filter(
                verification_timestamp__gte=timezone.now() - timedelta(days=7)
            )
            
            model_stats = recent_logs.values('verification_model__model_type').annotate(
                total_attempts=Count('id'),
                successful_attempts=Count(
                    Case(When(result='SUCCESS', then=1), output_field=IntegerField())
                ),
                avg_confidence=Avg('confidence_score'),
                avg_processing_time=Avg('processing_time_ms')
            )
            
            return {
                'model_statistics': list(model_stats),
                'total_evaluations': recent_logs.count()
            }
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error analyzing model performance: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_reliability_score(self, face_records) -> float:
        """Calculate overall face recognition reliability score"""
        try:
            total_attempts = face_records.count()
            if total_attempts == 0:
                return 0.0
            
            successful_attempts = face_records.filter(
                peventlogextras__verified_in=True
            ).count()
            
            return round(successful_attempts / total_attempts, 3)
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            logger.error(f"Error calculating reliability score: {str(e)}")
            return 0.0
    
    # Additional helper methods would be implemented here for:
    # - _analyze_face_quality_patterns
    # - _calculate_anomaly_trends
    # - _analyze_time_pattern_consistency
    # - _analyze_location_pattern_consistency
    # - _generate_behavioral_insights
    # - _analyze_fraud_indicators
    # - _analyze_geographic_fraud_patterns
    # - _analyze_temporal_fraud_patterns
    # - _analyze_historical_trends
    # - _predict_peak_times
    # - _forecast_risk_levels
    # - _generate_capacity_insights
    # - _calculate_prediction_confidence