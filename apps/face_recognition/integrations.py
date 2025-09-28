"""
Integration layer for AI-enhanced attendance system
Connects anomaly detection, behavioral analytics, and face recognition
"""

import logging
from django.utils import timezone
from django.core.signals import Signal
from django.dispatch import receiver
from celery import shared_task

from apps.attendance.models import PeopleEventlog
from .enhanced_engine import EnhancedFaceRecognitionEngine
from .analytics import AttendanceAnalyticsEngine
# Removed: anomaly_detection imports - app removed
# Removed: behavioral_analytics imports - app removed

logger = logging.getLogger(__name__)

# Custom signals for AI system integration
attendance_verified = Signal()
fraud_detected = Signal()
anomaly_detected = Signal()
behavioral_pattern_updated = Signal()


class AIAttendanceIntegration:
    """Main integration class for AI-enhanced attendance system"""
    
    def __init__(self):
        """Initialize AI integration components"""
        self.face_engine = EnhancedFaceRecognitionEngine()
        self.analytics_engine = AttendanceAnalyticsEngine()
        self.anomaly_collector = AnomalyDataCollector()
        self.anomaly_detector = EnsembleAnomalyDetector()
        self.fraud_detector = AttendanceFraudDetector()
        
    def process_attendance_with_ai(
        self, 
        attendance: PeopleEventlog,
        image_path: Optional[str] = None,
        enable_all_checks: bool = True
    ) -> Dict[str, Any]:
        """
        Process attendance record with full AI analysis pipeline
        
        Args:
            attendance: Attendance record to process
            image_path: Path to face image for verification
            enable_all_checks: Enable all AI checks (face, fraud, anomaly)
            
        Returns:
            Comprehensive processing results
        """
        try:
            logger.info(f"Processing attendance {attendance.id} with AI pipeline")
            
            results = {
                'attendance_id': attendance.id,
                'processing_timestamp': timezone.now(),
                'face_verification': {},
                'anomaly_detection': {},
                'fraud_analysis': {},
                'behavioral_update': {},
                'overall_risk_score': 0.0,
                'recommendations': [],
                'alerts': []
            }
            
            # 1. Face Recognition Processing
            if enable_all_checks and image_path and attendance.facerecognitionin:
                face_results = self.face_engine.verify_face(
                    user_id=attendance.people_id,
                    image_path=image_path,
                    attendance_record_id=attendance.id
                )
                results['face_verification'] = face_results
                
                # Emit signal for face verification completion
                attendance_verified.send(
                    sender=self.__class__,
                    attendance=attendance,
                    verification_result=face_results
                )
            
            # 2. Anomaly Detection Processing
            if enable_all_checks:
                # Collect data for anomaly detection
                features = self.anomaly_collector.collect_attendance_features(attendance)
                if features:
                    # Run anomaly detection
                    anomaly_results = self.anomaly_detector.detect_anomalies_single(
                        features, 'ATTENDANCE'
                    )
                    results['anomaly_detection'] = anomaly_results
                    
                    # Check for high-severity anomalies
                    if anomaly_results.get('is_anomaly', False) and anomaly_results.get('confidence_score', 0) > 0.8:
                        results['alerts'].append({
                            'type': 'ANOMALY_DETECTED',
                            'severity': 'HIGH',
                            'message': f"High-confidence anomaly detected in attendance pattern",
                            'confidence': anomaly_results.get('confidence_score', 0)
                        })
                        
                        # Emit anomaly detection signal
                        anomaly_detected.send(
                            sender=self.__class__,
                            attendance=attendance,
                            anomaly_result=anomaly_results
                        )
            
            # 3. Fraud Detection Processing
            if enable_all_checks:
                # Collect initial fraud indicators
                fraud_indicators = []
                if results.get('face_verification', {}).get('fraud_indicators'):
                    fraud_indicators.extend(results['face_verification']['fraud_indicators'])
                if results.get('anomaly_detection', {}).get('is_anomaly', False):
                    fraud_indicators.append('ANOMALY_DETECTED')
                
                # Run comprehensive fraud analysis
                fraud_results = self.fraud_detector.analyze_attendance(attendance, fraud_indicators)
                results['fraud_analysis'] = fraud_results
                
                # Check for high fraud probability
                fraud_probability = fraud_results.get('fraud_probability', 0)
                if fraud_probability > 0.7:
                    results['alerts'].append({
                        'type': 'FRAUD_DETECTED',
                        'severity': 'CRITICAL',
                        'message': f"High fraud probability detected: {fraud_probability:.2%}",
                        'probability': fraud_probability
                    })
                    
                    # Emit fraud detection signal
                    fraud_detected.send(
                        sender=self.__class__,
                        attendance=attendance,
                        fraud_result=fraud_results
                    )
            
            # 4. Behavioral Profile Update
            if enable_all_checks:
                behavioral_update = self._update_behavioral_profile(attendance, results)
                results['behavioral_update'] = behavioral_update
            
            # 5. Calculate Overall Risk Score
            results['overall_risk_score'] = self._calculate_overall_risk_score(results)
            
            # 6. Generate Recommendations
            results['recommendations'] = self._generate_integration_recommendations(results)
            
            # 7. Store Processing Results
            self._store_processing_results(attendance, results)
            
            logger.info(f"AI processing completed for attendance {attendance.id}")
            return results
            
        except (DatabaseError, IntegrationException, ValueError) as e:
            logger.error(f"Error in AI attendance processing: {str(e)}", exc_info=True)
            return {
                'attendance_id': attendance.id,
                'error': str(e),
                'processing_timestamp': timezone.now()
            }
    
    def _update_behavioral_profile(
        self,
        attendance: PeopleEventlog,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update user behavioral profile with race condition protection"""
        from django.db import transaction
        from apps.core.utils_new.distributed_locks import distributed_lock

        try:
            if not attendance.people_id:
                return {'error': 'No user ID available'}

            # Use distributed lock to prevent concurrent profile updates
            with distributed_lock(f"behavioral_profile:{attendance.people_id}", timeout=20):
                with transaction.atomic():
                    # Get or create with locking
                    profile, created = UserBehaviorProfile.objects.select_for_update().get_or_create(
                        user_id=attendance.people_id,
                        defaults={
                            'attendance_regularity_score': 0.5,
                            'fraud_risk_score': 0.0,
                            'anomaly_history': [],
                            'last_analysis_date': timezone.now()
                        }
                    )

                    # Update profile based on current analysis
                    updates = {}

                    # Update fraud risk score
                    fraud_probability = results.get('fraud_analysis', {}).get('fraud_probability', 0)
                    if fraud_probability > 0:
                        # Weighted average with historical fraud risk
                        current_weight = 0.3
                        historical_weight = 0.7

                        new_fraud_score = (
                            current_weight * fraud_probability +
                            historical_weight * profile.fraud_risk_score
                        )
                        updates['fraud_risk_score'] = min(1.0, new_fraud_score)

                    # Update anomaly history
                    if results.get('anomaly_detection', {}).get('is_anomaly', False):
                        anomaly_history = profile.anomaly_history or []
                        anomaly_record = {
                            'timestamp': timezone.now().isoformat(),
                            'anomaly_type': results['anomaly_detection'].get('anomaly_type', 'UNKNOWN'),
                            'confidence_score': results['anomaly_detection'].get('confidence_score', 0),
                            'attendance_id': attendance.id
                        }

                        anomaly_history.append(anomaly_record)
                        if len(anomaly_history) > 50:
                            anomaly_history = anomaly_history[-50:]

                        updates['anomaly_history'] = anomaly_history

                    # Calculate attendance regularity
                    regularity_score = self._calculate_attendance_regularity(attendance.people_id)
                    if regularity_score is not None:
                        updates['attendance_regularity_score'] = regularity_score

                    # Update timing patterns
                    if attendance.punchintime:
                        updates['last_attendance_time'] = attendance.punchintime

                        if profile.avg_arrival_time:
                            current_minutes = attendance.punchintime.hour * 60 + attendance.punchintime.minute
                            avg_minutes = profile.avg_arrival_time.hour * 60 + profile.avg_arrival_time.minute

                            new_avg_minutes = int(0.9 * avg_minutes + 0.1 * current_minutes)
                            new_avg_time = datetime.time(
                                hour=new_avg_minutes // 60,
                                minute=new_avg_minutes % 60
                            )
                            updates['avg_arrival_time'] = new_avg_time
                        else:
                            updates['avg_arrival_time'] = attendance.punchintime.time()

                    # Update location patterns
                    if attendance.startlocation:
                        location_history = profile.frequent_locations or []
                        location_key = f"{attendance.startlocation.y:.6f},{attendance.startlocation.x:.6f}"

                        found = False
                        for loc in location_history:
                            if loc.get('location') == location_key:
                                loc['count'] = loc.get('count', 0) + 1
                                loc['last_used'] = timezone.now().isoformat()
                                found = True
                                break

                        if not found:
                            location_history.append({
                                'location': location_key,
                                'count': 1,
                                'first_used': timezone.now().isoformat(),
                                'last_used': timezone.now().isoformat()
                            })

                        location_history.sort(key=lambda x: x['count'], reverse=True)
                        updates['frequent_locations'] = location_history[:10]

                    # Apply updates
                    updates['last_analysis_date'] = timezone.now()
                    for field, value in updates.items():
                        setattr(profile, field, value)

                    profile.save()

                    # Create behavioral event record
                    BehavioralEvent.objects.create(
                        user_id=attendance.people_id,
                        event_type='ATTENDANCE_PROCESSED',
                        event_data={
                            'attendance_id': attendance.id,
                            'processing_results': {
                                'fraud_probability': fraud_probability,
                                'anomaly_detected': results.get('anomaly_detection', {}).get('is_anomaly', False),
                                'face_verified': results.get('face_verification', {}).get('verified', False)
                            }
                        },
                        risk_impact=fraud_probability,
                        confidence_score=results.get('face_verification', {}).get('confidence', 0.5)
                    )

                # Emit behavioral pattern update signal (outside transaction)
                behavioral_pattern_updated.send(
                    sender=self.__class__,
                    user_id=attendance.people_id,
                    profile=profile,
                    updates=updates
                )

                return {
                    'profile_updated': True,
                    'profile_created': created,
                    'updates_applied': list(updates.keys()),
                    'new_fraud_risk_score': updates.get('fraud_risk_score', profile.fraud_risk_score),
                    'new_regularity_score': updates.get('attendance_regularity_score', profile.attendance_regularity_score)
                }

        except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
            logger.error(f"Error updating behavioral profile: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_attendance_regularity(self, user_id: int) -> Optional[float]:
        """Calculate attendance regularity score for a user"""
        try:
            # Get last 30 days of attendance
            recent_attendance = PeopleEventlog.objects.filter(
                people_id=user_id,
                punchintime__gte=timezone.now() - timedelta(days=30)
            ).order_by('punchintime')
            
            if recent_attendance.count() < 3:
                return None  # Not enough data
            
            # Calculate time consistency
            arrival_times = [
                att.punchintime.hour * 60 + att.punchintime.minute
                for att in recent_attendance
                if att.punchintime
            ]
            
            if not arrival_times:
                return None
            
            # Standard deviation of arrival times (lower = more regular)
            import numpy as np
            std_dev = np.std(arrival_times)
            
            # Convert to regularity score (0-1, higher is more regular)
            # Assuming 60 minutes std dev = 0.5 regularity, 30 minutes = 0.75, etc.
            regularity_score = max(0.0, min(1.0, 1.0 - (std_dev / 120.0)))
            
            return regularity_score
            
        except (AttributeError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error calculating attendance regularity: {str(e)}")
            return None
    
    def _calculate_overall_risk_score(self, results: Dict[str, Any]) -> float:
        """Calculate overall risk score from all AI components"""
        try:
            risk_components = {
                'fraud_risk': results.get('fraud_analysis', {}).get('fraud_probability', 0) * 0.4,
                'anomaly_risk': 0.3 if results.get('anomaly_detection', {}).get('is_anomaly', False) else 0,
                'face_recognition_risk': (1 - results.get('face_verification', {}).get('confidence', 1)) * 0.2,
                'behavioral_risk': 0.1 if results.get('behavioral_update', {}).get('new_fraud_risk_score', 0) > 0.5 else 0
            }
            
            total_risk = sum(risk_components.values())
            return min(1.0, total_risk)
            
        except (AttributeError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error calculating overall risk score: {str(e)}")
            return 0.0
    
    def _generate_integration_recommendations(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on integrated analysis"""
        recommendations = []
        
        try:
            overall_risk = results.get('overall_risk_score', 0)
            
            # High-risk recommendations
            if overall_risk > 0.7:
                recommendations.append({
                    'type': 'IMMEDIATE_ACTION',
                    'priority': 'CRITICAL',
                    'title': 'High-Risk Attendance Detected',
                    'description': f'Overall risk score: {overall_risk:.2%}',
                    'actions': [
                        'Require manual verification for this attendance',
                        'Initiate security review process',
                        'Monitor user activity closely'
                    ]
                })
            
            # Face recognition specific recommendations
            face_results = results.get('face_verification', {})
            if not face_results.get('verified', False) and face_results.get('confidence', 0) < 0.5:
                recommendations.append({
                    'type': 'FACE_RECOGNITION_IMPROVEMENT',
                    'priority': 'HIGH',
                    'title': 'Face Recognition Failed',
                    'description': 'Consider updating face enrollment data',
                    'actions': [
                        'Re-enroll user with better quality images',
                        'Check image capture environment',
                        'Verify user identity manually'
                    ]
                })
            
            # Fraud-specific recommendations
            fraud_results = results.get('fraud_analysis', {})
            fraud_probability = fraud_results.get('fraud_probability', 0)
            if fraud_probability > 0.5:
                recommendations.append({
                    'type': 'FRAUD_PREVENTION',
                    'priority': 'HIGH',
                    'title': 'Potential Fraud Detected',
                    'description': f'Fraud probability: {fraud_probability:.2%}',
                    'actions': [
                        'Investigate attendance patterns',
                        'Review recent user behavior',
                        'Consider additional verification steps'
                    ]
                })
            
            # Anomaly-specific recommendations
            if results.get('anomaly_detection', {}).get('is_anomaly', False):
                recommendations.append({
                    'type': 'ANOMALY_INVESTIGATION',
                    'priority': 'MEDIUM',
                    'title': 'Unusual Pattern Detected',
                    'description': 'Attendance pattern deviates from normal behavior',
                    'actions': [
                        'Review attendance history',
                        'Check for system issues',
                        'Validate user permissions'
                    ]
                })
            
        except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error generating recommendations: {str(e)}")
        
        return recommendations
    
    def _store_processing_results(self, attendance: PeopleEventlog, results: Dict[str, Any]):
        """Store AI processing results with race condition protection"""
        from django.db import transaction
        from apps.core.utils_new.distributed_locks import distributed_lock

        try:
            # Use same lock as main update to prevent conflicts
            with distributed_lock(f"attendance_update:{attendance.uuid}", timeout=5):
                with transaction.atomic():
                    # Refresh from database to get latest state
                    attendance = PeopleEventlog.objects.select_for_update().get(pk=attendance.pk)

                    # Update with AI results
                    extras = dict(attendance.peventlogextras or {})
                    extras['ai_processing_results'] = results

                    attendance.peventlogextras = extras
                    attendance.save(update_fields=['peventlogextras'])

            logger.info(f"AI processing results stored for attendance {attendance.id}")

        except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error storing processing results: {str(e)}", exc_info=True)


# Celery task for asynchronous AI processing
@shared_task(bind=True, max_retries=3)
def process_attendance_async(self, attendance_id: int, image_path: Optional[str] = None):
    """Asynchronously process attendance with AI pipeline"""
    try:
        attendance = PeopleEventlog.objects.get(id=attendance_id)
        integration = AIAttendanceIntegration()
        
        results = integration.process_attendance_with_ai(
            attendance=attendance,
            image_path=image_path,
            enable_all_checks=True
        )
        
        logger.info(f"Async AI processing completed for attendance {attendance_id}")
        return results
        
    except PeopleEventlog.DoesNotExist:
        logger.error(f"Attendance record {attendance_id} not found")
        return {'error': 'Attendance record not found'}
    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error in async AI processing: {str(e)}")
        # Retry the task
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


# Signal handlers for real-time integration
@receiver(attendance_verified)
def handle_attendance_verification(sender, attendance, verification_result, **kwargs):
    """Handle attendance verification completion"""
    try:
        logger.info(f"Attendance verification completed for {attendance.id}")
        
        # Trigger additional processing if verification failed
        if not verification_result.get('verified', False):
            # Schedule enhanced monitoring for this user
            pass
            
    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error handling attendance verification: {str(e)}")


@receiver(fraud_detected)
def handle_fraud_detection(sender, attendance, fraud_result, **kwargs):
    """Handle fraud detection alert"""
    try:
        logger.warning(f"Fraud detected for attendance {attendance.id}")
        
        # Implement immediate response actions
        fraud_probability = fraud_result.get('fraud_probability', 0)
        
        if fraud_probability > 0.8:
            # Critical fraud - immediate action required
            logger.critical(f"Critical fraud detected: {fraud_probability:.2%}")
            # Send alert to security team
            # Temporarily suspend user access
            # Log security incident
            
    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error handling fraud detection: {str(e)}")


@receiver(anomaly_detected)
def handle_anomaly_detection(sender, attendance, anomaly_result, **kwargs):
    """Handle anomaly detection alert"""
    try:
        logger.info(f"Anomaly detected for attendance {attendance.id}")
        
        # Log anomaly for pattern analysis
        confidence = anomaly_result.get('confidence_score', 0)
        
        if confidence > 0.9:
            # High-confidence anomaly - investigate further
            logger.warning(f"High-confidence anomaly: {confidence:.2%}")
            
    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error handling anomaly detection: {str(e)}")


@receiver(behavioral_pattern_updated)
def handle_behavioral_update(sender, user_id, profile, updates, **kwargs):
    """Handle behavioral profile updates"""
    try:
        logger.info(f"Behavioral profile updated for user {user_id}")
        
        # Check if user has become high-risk
        if profile.fraud_risk_score > 0.7:
            logger.warning(f"User {user_id} now has high fraud risk: {profile.fraud_risk_score:.2%}")
            # Implement enhanced monitoring
            
    except (AttributeError, ConnectionError, DatabaseError, IntegrationException, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
        logger.error(f"Error handling behavioral update: {str(e)}")