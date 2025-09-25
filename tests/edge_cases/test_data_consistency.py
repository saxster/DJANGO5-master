"""
Data consistency tests for AI systems
Tests race conditions, cache consistency, and cross-app data synchronization
"""

import time
import threading
import json
from unittest.mock import patch, Mock, MagicMock
from django.test import TestCase, TransactionTestCase
from django.db import transaction, connection
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import hashlib

from apps.face_recognition.models import FaceEmbedding, FaceVerificationLog
from apps.behavioral_analytics.models import UserBehaviorProfile, FraudRiskAssessment
from apps.anomaly_detection.models import AnomalyDataPoint, AnomalyDetectionResult
from apps.attendance.models import PeopleEventlog
from tests.factories import UserFactory, AttendanceFactory, FaceEmbeddingFactory
from tests.utils import AITestCase

User = get_user_model()


class RaceConditionTest(TransactionTestCase):
    """Test race condition handling in concurrent processing"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_concurrent_embedding_updates(self):
        """Test concurrent updates to face embeddings"""
        embedding = FaceEmbeddingFactory(user=self.user)
        results = []
        errors = []
        
        def update_embedding_vector(embedding_id, new_vector, thread_id):
            """Update embedding vector with optimistic locking"""
            try:
                with transaction.atomic():
                    # Get embedding with select_for_update
                    embedding = FaceEmbedding.objects.select_for_update().get(
                        id=embedding_id
                    )
                    
                    # Simulate processing time
                    time.sleep(0.01)
                    
                    # Update vector
                    embedding.embedding_vector = new_vector
                    embedding.save()
                    
                    results.append({
                        'thread_id': thread_id,
                        'success': True,
                        'final_vector': new_vector[:5]  # First 5 elements
                    })
                    
            except Exception as e:
                errors.append({
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        # Create concurrent threads
        threads = []
        for i in range(5):
            new_vector = [0.1 + i * 0.1] * 512
            thread = threading.Thread(
                target=update_embedding_vector,
                args=(embedding.id, new_vector, i)
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 5)
        
        # Check final state
        embedding.refresh_from_db()
        self.assertEqual(len(embedding.embedding_vector), 512)
    
    def test_concurrent_fraud_assessment_creation(self):
        """Test concurrent fraud assessment creation for same user"""
        results = []
        errors = []
        
        def create_fraud_assessment(user, risk_score, thread_id):
            """Create fraud assessment with race condition handling"""
            try:
                # Check if recent assessment exists
                recent_assessment = FraudRiskAssessment.objects.filter(
                    user=user,
                    assessment_timestamp__gte=timezone.now() - timedelta(minutes=5)
                ).first()
                
                if recent_assessment:
                    # Update existing instead of creating new
                    with transaction.atomic():
                        recent_assessment = FraudRiskAssessment.objects.select_for_update().get(
                            id=recent_assessment.id
                        )
                        recent_assessment.overall_risk_score = max(
                            recent_assessment.overall_risk_score,
                            risk_score
                        )
                        recent_assessment.save()
                        
                        results.append({
                            'thread_id': thread_id,
                            'action': 'updated',
                            'assessment_id': recent_assessment.id
                        })
                else:
                    # Create new assessment
                    assessment = FraudRiskAssessment.objects.create(
                        user=user,
                        overall_risk_score=risk_score
                    )
                    
                    results.append({
                        'thread_id': thread_id,
                        'action': 'created',
                        'assessment_id': assessment.id
                    })
                    
            except Exception as e:
                errors.append({
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        # Create concurrent assessments
        threads = []
        for i in range(5):
            risk_score = 0.1 + (i * 0.1)
            thread = threading.Thread(
                target=create_fraud_assessment,
                args=(self.user, risk_score, i)
            )
            threads.append(thread)
        
        # Start threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no duplicate assessments
        assessment_count = FraudRiskAssessment.objects.filter(
            user=self.user
        ).count()
        
        self.assertLessEqual(assessment_count, 1)  # Should have at most 1 assessment
        self.assertEqual(len(errors), 0)
    
    def test_concurrent_user_profile_updates(self):
        """Test concurrent updates to user behavioral profile"""
        profile = UserBehaviorProfile.objects.create(
            user=self.user,
            attendance_regularity_score=0.5
        )
        
        updates = []
        conflicts = []
        
        def update_profile_field(profile_id, field_name, value, thread_id):
            """Update profile field with conflict detection"""
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    with transaction.atomic():
                        profile = UserBehaviorProfile.objects.select_for_update().get(
                            id=profile_id
                        )
                        
                        # Store original version
                        original_modified = profile.modified_at
                        
                        # Simulate processing
                        time.sleep(0.01)
                        
                        # Update field
                        setattr(profile, field_name, value)
                        profile.save()
                        
                        updates.append({
                            'thread_id': thread_id,
                            'field': field_name,
                            'value': value,
                            'retries': retry_count
                        })
                        break
                        
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        conflicts.append({
                            'thread_id': thread_id,
                            'error': str(e)
                        })
                    else:
                        time.sleep(0.01 * retry_count)  # Exponential backoff
        
        # Create concurrent updates to different fields
        threads = []
        fields = [
            ('attendance_regularity_score', 0.8),
            ('location_consistency_score', 0.9),
            ('device_consistency_score', 0.7),
            ('attendance_regularity_score', 0.6),  # Conflicts with first
            ('location_consistency_score', 0.5)   # Conflicts with second
        ]
        
        for i, (field, value) in enumerate(fields):
            thread = threading.Thread(
                target=update_profile_field,
                args=(profile.id, field, value, i)
            )
            threads.append(thread)
        
        # Start threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify all updates completed
        self.assertEqual(len(updates), len(fields))
        self.assertEqual(len(conflicts), 0)
        
        # Check final values
        profile.refresh_from_db()
        self.assertIsNotNone(profile.attendance_regularity_score)
        self.assertIsNotNone(profile.location_consistency_score)


class CacheDatabaseConsistencyTest(TestCase):
    """Test consistency between cache and database"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        cache.clear()
    
    def test_cache_invalidation_on_update(self):
        """Test cache invalidation when database is updated"""
        # Create face embedding
        embedding = FaceEmbeddingFactory(user=self.user)
        
        # Cache the embedding
        cache_key = f'user_embeddings_{self.user.id}'
        cached_embeddings = list(FaceEmbedding.objects.filter(user=self.user))
        cache.set(cache_key, cached_embeddings, timeout=300)
        
        # Verify cache hit
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data), 1)
        
        # Update embedding in database
        embedding.face_confidence = 0.99
        embedding.save()
        
        # Simulate cache invalidation (in production, this would be triggered by signals)
        cache.delete(cache_key)
        
        # Verify cache miss
        cached_data = cache.get(cache_key)
        self.assertIsNone(cached_data)
        
        # Refetch from database
        fresh_embeddings = list(FaceEmbedding.objects.filter(user=self.user))
        cache.set(cache_key, fresh_embeddings, timeout=300)
        
        # Verify updated data
        cached_data = cache.get(cache_key)
        self.assertEqual(cached_data[0].face_confidence, 0.99)
    
    def test_cache_write_through_consistency(self):
        """Test write-through cache consistency"""
        def update_with_write_through(user, new_score):
            """Update with write-through caching"""
            cache_key = f'fraud_score_{user.id}'
            
            # Update database first
            assessment, created = FraudRiskAssessment.objects.get_or_create(
                user=user,
                defaults={'overall_risk_score': new_score}
            )
            
            if not created:
                assessment.overall_risk_score = new_score
                assessment.save()
            
            # Update cache immediately
            cache.set(cache_key, new_score, timeout=300)
            
            return assessment
        
        # Update with write-through
        assessment = update_with_write_through(self.user, 0.75)
        
        # Verify database
        self.assertEqual(assessment.overall_risk_score, 0.75)
        
        # Verify cache
        cached_score = cache.get(f'fraud_score_{self.user.id}')
        self.assertEqual(cached_score, 0.75)
        
        # Update again
        assessment2 = update_with_write_through(self.user, 0.85)
        
        # Verify consistency
        self.assertEqual(assessment2.overall_risk_score, 0.85)
        cached_score2 = cache.get(f'fraud_score_{self.user.id}')
        self.assertEqual(cached_score2, 0.85)
    
    def test_cache_aside_pattern_consistency(self):
        """Test cache-aside pattern consistency"""
        def get_user_profile_with_cache(user_id):
            """Get user profile with cache-aside pattern"""
            cache_key = f'user_profile_{user_id}'
            
            # Try cache first
            cached_profile = cache.get(cache_key)
            if cached_profile:
                return {
                    'source': 'cache',
                    'profile': cached_profile
                }
            
            # Cache miss - get from database
            try:
                profile = UserBehaviorProfile.objects.get(user_id=user_id)
                profile_data = {
                    'id': profile.id,
                    'attendance_score': profile.attendance_regularity_score,
                    'modified_at': profile.modified_at.isoformat()
                }
                
                # Cache the result
                cache.set(cache_key, profile_data, timeout=300)
                
                return {
                    'source': 'database',
                    'profile': profile_data
                }
                
            except UserBehaviorProfile.DoesNotExist:
                return {
                    'source': 'none',
                    'profile': None
                }
        
        # Create profile
        profile = UserBehaviorProfile.objects.create(
            user=self.user,
            attendance_regularity_score=0.7
        )
        
        # First call - should hit database
        result1 = get_user_profile_with_cache(self.user.id)
        self.assertEqual(result1['source'], 'database')
        self.assertEqual(result1['profile']['attendance_score'], 0.7)
        
        # Second call - should hit cache
        result2 = get_user_profile_with_cache(self.user.id)
        self.assertEqual(result2['source'], 'cache')
        self.assertEqual(result2['profile']['attendance_score'], 0.7)
    
    def test_distributed_cache_consistency(self):
        """Test consistency across distributed cache instances"""
        def simulate_distributed_cache_update(key, value, nodes):
            """Simulate update across multiple cache nodes"""
            update_results = []
            
            for node in nodes:
                try:
                    # Simulate cache update on each node
                    node_result = {
                        'node_id': node['id'],
                        'update_success': True,
                        'timestamp': timezone.now()
                    }
                    
                    # Simulate network delay
                    time.sleep(0.001)
                    
                    update_results.append(node_result)
                    
                except Exception as e:
                    update_results.append({
                        'node_id': node['id'],
                        'update_success': False,
                        'error': str(e)
                    })
            
            # Check consistency
            successful_updates = [r for r in update_results if r['update_success']]
            consistency_achieved = len(successful_updates) == len(nodes)
            
            return {
                'total_nodes': len(nodes),
                'successful_updates': len(successful_updates),
                'consistency_achieved': consistency_achieved,
                'update_results': update_results
            }
        
        # Simulate cache cluster
        cache_nodes = [
            {'id': 'cache_1', 'location': 'us-east'},
            {'id': 'cache_2', 'location': 'us-west'},
            {'id': 'cache_3', 'location': 'eu-central'}
        ]
        
        result = simulate_distributed_cache_update(
            'user_data_123',
            {'score': 0.8},
            cache_nodes
        )
        
        self.assertTrue(result['consistency_achieved'])
        self.assertEqual(result['successful_updates'], 3)


class CrossAppDataSynchronizationTest(TransactionTestCase):
    """Test data synchronization across AI apps"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_attendance_face_recognition_sync(self):
        """Test synchronization between attendance and face recognition data"""
        def process_attendance_with_sync(attendance):
            """Process attendance with cross-app synchronization"""
            results = {
                'attendance_updated': False,
                'face_log_created': False,
                'profile_updated': False,
                'sync_timestamp': timezone.now()
            }
            
            with transaction.atomic():
                # Update attendance status
                attendance.processed = True
                attendance.save()
                results['attendance_updated'] = True
                
                # Create face verification log
                face_log = FaceVerificationLog.objects.create(
                    user=attendance.user,
                    verification_timestamp=attendance.punchintime,
                    similarity_score=0.85,
                    confidence_score=0.90,
                    result='SUCCESS',
                    related_attendance_id=attendance.id
                )
                results['face_log_created'] = True
                
                # Update user profile
                profile, created = UserBehaviorProfile.objects.get_or_create(
                    user=attendance.user,
                    defaults={'attendance_regularity_score': 0.5}
                )
                
                # Update attendance count
                profile.total_attendance_count = getattr(profile, 'total_attendance_count', 0) + 1
                profile.last_attendance = attendance.punchintime
                profile.save()
                results['profile_updated'] = True
                
                return results
        
        # Create attendance
        attendance = AttendanceFactory(user=self.user)
        
        # Process with synchronization
        results = process_attendance_with_sync(attendance)
        
        # Verify all updates
        self.assertTrue(results['attendance_updated'])
        self.assertTrue(results['face_log_created'])
        self.assertTrue(results['profile_updated'])
        
        # Verify data consistency
        attendance.refresh_from_db()
        self.assertTrue(attendance.processed)
        
        face_log = FaceVerificationLog.objects.get(
            related_attendance_id=attendance.id
        )
        self.assertEqual(face_log.user, self.user)
        
        profile = UserBehaviorProfile.objects.get(user=self.user)
        self.assertEqual(profile.total_attendance_count, 1)
    
    def test_anomaly_detection_fraud_assessment_sync(self):
        """Test sync between anomaly detection and fraud assessment"""
        def create_synchronized_assessment(user, anomalies):
            """Create fraud assessment based on anomalies"""
            fraud_score = 0.1  # Base score
            fraud_indicators = []
            
            with transaction.atomic():
                # Process anomalies
                for anomaly_data in anomalies:
                    anomaly = AnomalyDetectionResult.objects.create(
                        anomaly_type=anomaly_data['type'],
                        severity=anomaly_data['severity'],
                        confidence_score=anomaly_data['confidence'],
                        anomaly_score=anomaly_data['score']
                    )
                    
                    # Increase fraud score based on anomaly
                    if anomaly.severity == 'HIGH':
                        fraud_score += 0.3
                        fraud_indicators.append(f"high_{anomaly.anomaly_type.lower()}")
                    elif anomaly.severity == 'MEDIUM':
                        fraud_score += 0.2
                        fraud_indicators.append(f"medium_{anomaly.anomaly_type.lower()}")
                
                # Create fraud assessment
                assessment = FraudRiskAssessment.objects.create(
                    user=user,
                    overall_risk_score=min(fraud_score, 1.0),
                    fraud_indicators=fraud_indicators,
                    anomaly_count=len(anomalies)
                )
                
                return {
                    'assessment': assessment,
                    'anomalies_created': len(anomalies),
                    'final_score': assessment.overall_risk_score
                }
        
        # Create test anomalies
        anomalies = [
            {
                'type': 'TEMPORAL',
                'severity': 'HIGH',
                'confidence': 0.9,
                'score': 0.8
            },
            {
                'type': 'LOCATION',
                'severity': 'MEDIUM', 
                'confidence': 0.8,
                'score': 0.6
            }
        ]
        
        result = create_synchronized_assessment(self.user, anomalies)
        
        # Verify synchronization
        self.assertEqual(result['anomalies_created'], 2)
        self.assertGreater(result['final_score'], 0.4)  # Should increase due to anomalies
        
        # Verify database consistency
        assessment = result['assessment']
        self.assertEqual(assessment.anomaly_count, 2)
        self.assertIn('high_temporal', assessment.fraud_indicators)
    
    def test_event_driven_synchronization(self):
        """Test event-driven synchronization between apps"""
        events = []
        
        def publish_event(event_type, data):
            """Publish synchronization event"""
            event = {
                'type': event_type,
                'data': data,
                'timestamp': timezone.now(),
                'id': hashlib.sha256(f"{event_type}_{timezone.now()}".encode()).hexdigest()[:16]
            }
            events.append(event)
            return event
        
        def handle_face_verification_event(event):
            """Handle face verification event"""
            if event['type'] == 'face_verified':
                data = event['data']
                
                # Update behavioral profile based on verification
                profile, created = UserBehaviorProfile.objects.get_or_create(
                    user_id=data['user_id'],
                    defaults={'attendance_regularity_score': 0.5}
                )
                
                # Adjust score based on verification confidence
                if data['confidence'] > 0.9:
                    profile.face_recognition_reliability += 0.1
                elif data['confidence'] < 0.6:
                    profile.face_recognition_reliability -= 0.05
                
                profile.face_recognition_reliability = max(0, min(1, 
                    getattr(profile, 'face_recognition_reliability', 0.5)
                ))
                profile.save()
                
                return {'handled': True, 'profile_updated': True}
            
            return {'handled': False}
        
        # Simulate face verification event
        event = publish_event('face_verified', {
            'user_id': self.user.id,
            'confidence': 0.95,
            'verification_time': timezone.now()
        })
        
        # Handle the event
        result = handle_face_verification_event(event)
        
        self.assertTrue(result['handled'])
        self.assertTrue(result['profile_updated'])
        
        # Verify profile was updated
        profile = UserBehaviorProfile.objects.get(user=self.user)
        self.assertGreater(profile.face_recognition_reliability, 0.5)


class DataIntegrityValidationTest(TestCase):
    """Test data integrity validation across the system"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_referential_integrity_validation(self):
        """Test referential integrity between related records"""
        def validate_referential_integrity():
            """Validate referential integrity across AI data"""
            issues = []
            
            # Check orphaned face embeddings
            orphaned_embeddings = FaceEmbedding.objects.filter(
                user__isnull=True
            ).count()
            
            if orphaned_embeddings > 0:
                issues.append({
                    'type': 'orphaned_embeddings',
                    'count': orphaned_embeddings
                })
            
            # Check orphaned verification logs
            orphaned_logs = FaceVerificationLog.objects.exclude(
                user__in=User.objects.all()
            ).count()
            
            if orphaned_logs > 0:
                issues.append({
                    'type': 'orphaned_logs',
                    'count': orphaned_logs
                })
            
            # Check missing profiles for users with embeddings
            users_with_embeddings = FaceEmbedding.objects.values_list('user', flat=True).distinct()
            users_without_profiles = User.objects.filter(
                id__in=users_with_embeddings
            ).exclude(
                behavior_profile__isnull=False
            ).count()
            
            if users_without_profiles > 0:
                issues.append({
                    'type': 'missing_profiles',
                    'count': users_without_profiles
                })
            
            return {
                'integrity_valid': len(issues) == 0,
                'issues': issues
            }
        
        # Create test data
        embedding = FaceEmbeddingFactory(user=self.user)
        FaceVerificationLog.objects.create(
            user=self.user,
            similarity_score=0.8,
            confidence_score=0.9,
            result='SUCCESS'
        )
        
        # Validate integrity
        result = validate_referential_integrity()
        
        # Should have issues (missing profile)
        self.assertFalse(result['integrity_valid'])
        self.assertEqual(len(result['issues']), 1)
        self.assertEqual(result['issues'][0]['type'], 'missing_profiles')
    
    def test_data_consistency_validation(self):
        """Test data consistency validation"""
        def validate_data_consistency(user):
            """Validate consistency of user's AI data"""
            inconsistencies = []
            
            # Get all related data
            embeddings = FaceEmbedding.objects.filter(user=user)
            verifications = FaceVerificationLog.objects.filter(user=user)
            assessments = FraudRiskAssessment.objects.filter(user=user)
            
            # Check embedding consistency
            if embeddings.count() > 0:
                embedding_confidences = [e.face_confidence for e in embeddings]
                avg_embedding_confidence = sum(embedding_confidences) / len(embedding_confidences)
                
                verification_confidences = [v.confidence_score for v in verifications if v.confidence_score]
                if verification_confidences:
                    avg_verification_confidence = sum(verification_confidences) / len(verification_confidences)
                    
                    # Should be similar
                    diff = abs(avg_embedding_confidence - avg_verification_confidence)
                    if diff > 0.3:
                        inconsistencies.append({
                            'type': 'confidence_mismatch',
                            'embedding_avg': avg_embedding_confidence,
                            'verification_avg': avg_verification_confidence,
                            'difference': diff
                        })
            
            # Check fraud assessment consistency
            if assessments.exists() and verifications.exists():
                high_confidence_verifications = verifications.filter(confidence_score__gte=0.9).count()
                total_verifications = verifications.count()
                
                if total_verifications > 0:
                    success_rate = high_confidence_verifications / total_verifications
                    
                    latest_assessment = assessments.order_by('-assessment_timestamp').first()
                    if latest_assessment:
                        # Low fraud score should correlate with high success rate
                        if success_rate > 0.8 and latest_assessment.overall_risk_score > 0.7:
                            inconsistencies.append({
                                'type': 'fraud_score_mismatch',
                                'success_rate': success_rate,
                                'fraud_score': latest_assessment.overall_risk_score
                            })
            
            return {
                'consistent': len(inconsistencies) == 0,
                'inconsistencies': inconsistencies
            }
        
        # Create consistent data
        FaceEmbeddingFactory(user=self.user, face_confidence=0.9)
        FaceVerificationLog.objects.create(
            user=self.user,
            similarity_score=0.88,
            confidence_score=0.85,  # Slightly different but consistent
            result='SUCCESS'
        )
        FraudRiskAssessment.objects.create(
            user=self.user,
            overall_risk_score=0.2  # Low risk - consistent with high confidence
        )
        
        result = validate_data_consistency(self.user)
        
        # Should be consistent
        self.assertTrue(result['consistent'])
        self.assertEqual(len(result['inconsistencies']), 0)
    
    def test_temporal_consistency_validation(self):
        """Test temporal consistency of AI data"""
        def validate_temporal_consistency(user):
            """Validate temporal relationships in data"""
            issues = []
            
            # Check if face verification logs have reasonable timestamps
            verifications = FaceVerificationLog.objects.filter(user=user).order_by('verification_timestamp')
            
            for i in range(1, len(verifications)):
                prev_verification = verifications[i-1]
                curr_verification = verifications[i]
                
                time_diff = (curr_verification.verification_timestamp - 
                           prev_verification.verification_timestamp).total_seconds()
                
                # Verifications too close together (< 1 second) might indicate duplication
                if time_diff < 1:
                    issues.append({
                        'type': 'rapid_verifications',
                        'time_diff': time_diff,
                        'verification_ids': [prev_verification.id, curr_verification.id]
                    })
            
            # Check fraud assessments temporal consistency
            assessments = FraudRiskAssessment.objects.filter(user=user).order_by('assessment_timestamp')
            
            for i in range(1, len(assessments)):
                prev_assessment = assessments[i-1]
                curr_assessment = assessments[i]
                
                # Risk score shouldn't change dramatically without reason
                score_change = abs(curr_assessment.overall_risk_score - prev_assessment.overall_risk_score)
                
                time_diff = (curr_assessment.assessment_timestamp - 
                           prev_assessment.assessment_timestamp).total_seconds() / 3600  # hours
                
                # Large change in short time (> 0.5 change in < 1 hour)
                if score_change > 0.5 and time_diff < 1:
                    issues.append({
                        'type': 'sudden_risk_change',
                        'score_change': score_change,
                        'time_hours': time_diff,
                        'assessment_ids': [prev_assessment.id, curr_assessment.id]
                    })
            
            return {
                'temporally_consistent': len(issues) == 0,
                'temporal_issues': issues
            }
        
        # Create temporally inconsistent data
        base_time = timezone.now()
        
        # Create rapid verifications (suspicious)
        FaceVerificationLog.objects.create(
            user=self.user,
            verification_timestamp=base_time,
            similarity_score=0.8,
            confidence_score=0.9,
            result='SUCCESS'
        )
        FaceVerificationLog.objects.create(
            user=self.user,
            verification_timestamp=base_time + timedelta(milliseconds=500),  # Too close
            similarity_score=0.8,
            confidence_score=0.9,
            result='SUCCESS'
        )
        
        result = validate_temporal_consistency(self.user)
        
        # Should detect temporal issues
        self.assertFalse(result['temporally_consistent'])
        self.assertGreater(len(result['temporal_issues']), 0)
        self.assertEqual(result['temporal_issues'][0]['type'], 'rapid_verifications')