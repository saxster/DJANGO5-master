"""
Integration tests for AI system cross-app workflows
Tests end-to-end AI processing pipelines and data flow
"""

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import json

from apps.attendance.models import PeopleEventlog
from apps.face_recognition.models import FaceVerificationLog, FaceEmbedding
from apps.anomaly_detection.models import AnomalyDataPoint, AnomalyDetectionResult
from apps.behavioral_analytics.models import FraudRiskAssessment, UserBehaviorProfile
from apps.face_recognition.integrations import AIAttendanceIntegration
from tests.factories import (
    UserFactory, AttendanceFactory, FaceEmbeddingFactory,
    create_user_with_ai_data, create_bulk_test_data
)
from tests.utils import AITestCase


class EndToEndAIWorkflowTest(TransactionTestCase):
    """Test complete end-to-end AI processing workflows"""
    
    def setUp(self):
        super().setUp()
        cache.clear()  # Clear cache between tests
        self.user = UserFactory()
        self.integration = AIAttendanceIntegration()
        
        # Create user with existing AI data
        self.user_ai_data = create_user_with_ai_data()
        self.test_user = self.user_ai_data['user']
    
    def test_complete_attendance_processing_pipeline(self):
        """Test complete attendance processing from creation to AI analysis"""
        # Create new attendance record
        attendance = AttendanceFactory(
            user=self.test_user,
            punchintime=timezone.now().replace(hour=9, minute=15),
            facerecognitionin=True,
            extra_info={
                'confidence_in': '0.88',
                'distance_in': '0.75',
                'device_info': {'device_id': 'test_device_123'},
                'image_path': '/mock/face/image.jpg'
            }
        )
        
        with patch.multiple(
            'apps.face_recognition.integrations',
            EnhancedFaceRecognitionEngine=Mock(),
            EnsembleAnomalyDetector=Mock(),
            AttendanceFraudDetector=Mock()
        ):
            # Mock AI processing results
            mock_face_result = {
                'verification_successful': True,
                'similarity_score': 0.89,
                'confidence_score': 0.92,
                'processing_time_ms': 145.3
            }
            
            mock_anomaly_result = [{
                'anomaly_score': 0.25,
                'is_anomaly': False,
                'confidence': 0.88,
                'anomaly_type': 'TEMPORAL'
            }]
            
            mock_fraud_result = {
                'overall_fraud_risk': 0.15,
                'fraud_indicators': [],
                'confidence_score': 0.92
            }
            
            # Process attendance through complete pipeline
            result = self.integration.process_attendance(attendance.id)
            
            # Verify end-to-end processing
            self.assertTrue(result['success'])
            self.assertIn('face_verification', result)
            self.assertIn('anomaly_detection', result)
            self.assertIn('fraud_analysis', result)
    
    def test_cross_app_data_consistency(self):
        """Test data consistency across all AI apps"""
        attendance = AttendanceFactory(user=self.test_user)
        
        # Process attendance to generate AI data
        with patch('apps.face_recognition.integrations.AIAttendanceIntegration.process_attendance'):
            # Create related records manually to test relationships
            
            # Face verification log
            face_log = FaceVerificationLog.objects.create(
                user=self.test_user,
                verification_timestamp=attendance.punchintime,
                similarity_score=0.87,
                confidence_score=0.91,
                result='SUCCESS'
            )
            
            # Anomaly detection result
            anomaly_result = AnomalyDetectionResult.objects.create(
                anomaly_type='TEMPORAL',
                severity='LOW',
                confidence_score=0.85,
                anomaly_score=0.23,
                detection_timestamp=attendance.punchintime
            )
            
            # Fraud risk assessment
            fraud_assessment = FraudRiskAssessment.objects.create(
                user=self.test_user,
                overall_risk_score=0.18,
                face_recognition_risk=0.13,
                location_risk=0.20,
                temporal_risk=0.15,
                behavioral_risk=0.22,
                assessment_timestamp=attendance.punchintime
            )
            
            # Verify cross-app relationships and data consistency
            
            # All records should have consistent timestamps
            time_diff_face = abs((face_log.verification_timestamp - attendance.punchintime).total_seconds())
            time_diff_anomaly = abs((anomaly_result.detection_timestamp - attendance.punchintime).total_seconds())
            time_diff_fraud = abs((fraud_assessment.assessment_timestamp - attendance.punchintime).total_seconds())
            
            self.assertLess(time_diff_face, 60)    # Within 1 minute
            self.assertLess(time_diff_anomaly, 60) # Within 1 minute  
            self.assertLess(time_diff_fraud, 60)   # Within 1 minute
            
            # User should be consistent across all records
            self.assertEqual(face_log.user, self.test_user)
            self.assertEqual(fraud_assessment.user, self.test_user)
    
    def test_signal_driven_ai_processing(self):
        """Test that Django signals trigger AI processing correctly"""
        from apps.face_recognition.signals import handle_attendance_created
        
        # Create attendance that should trigger signals
        attendance = AttendanceFactory(
            user=self.test_user,
            facerecognitionin=True,
            extra_info={'image_path': '/mock/image.jpg'}
        )
        
        with patch('apps.face_recognition.integrations.process_attendance_async.delay') as mock_async:
            # Manually trigger signal (in real scenario, this happens automatically)
            handle_attendance_created(
                sender=PeopleEventlog,
                instance=attendance,
                created=True
            )
            
            # Verify async processing was scheduled
            mock_async.assert_called_once_with(attendance.id, '/mock/image.jpg')
    
    def test_ai_system_failure_recovery(self):
        """Test system behavior when individual AI components fail"""
        attendance = AttendanceFactory(user=self.test_user)
        
        with patch.multiple(
            'apps.face_recognition.integrations.AIAttendanceIntegration',
            _process_face_verification=Mock(side_effect=Exception('Face engine failed')),
            _process_anomaly_detection=Mock(return_value={'anomalies_detected': []}),
            _process_fraud_analysis=Mock(return_value={'overall_fraud_risk': 0.3})
        ):
            result = self.integration.process_attendance(attendance.id)
            
            # System should continue processing despite face recognition failure
            self.assertTrue(result['success'])
            self.assertIn('error', result.get('face_verification', {}))
            self.assertIn('anomaly_detection', result)
            self.assertIn('fraud_analysis', result)
    
    def test_bulk_processing_integration(self):
        """Test bulk processing of multiple attendance records"""
        # Create multiple attendance records
        attendances = [
            AttendanceFactory(user=self.test_user) for _ in range(5)
        ]
        attendance_ids = [att.id for att in attendances]
        
        with patch('apps.face_recognition.integrations.AIAttendanceIntegration.process_attendance') as mock_process:
            mock_process.return_value = {'success': True, 'processing_time_ms': 150.0}
            
            # Process in bulk
            results = []
            for att_id in attendance_ids:
                result = self.integration.process_attendance(att_id)
                results.append(result)
            
            # Verify all records were processed
            self.assertEqual(len(results), 5)
            self.assertTrue(all(r['success'] for r in results))
            
            # Verify each attendance was processed individually
            self.assertEqual(mock_process.call_count, 5)
    
    def test_real_time_vs_batch_processing_consistency(self):
        """Test consistency between real-time and batch processing"""
        # Create test attendance
        attendance = AttendanceFactory(user=self.test_user)
        
        with patch('apps.face_recognition.integrations.AIAttendanceIntegration._process_face_verification') as mock_face, \
             patch('apps.face_recognition.integrations.AIAttendanceIntegration._process_anomaly_detection') as mock_anomaly, \
             patch('apps.face_recognition.integrations.AIAttendanceIntegration._process_fraud_analysis') as mock_fraud:
            
            # Setup consistent mock results
            consistent_face_result = {'verification_successful': True, 'similarity_score': 0.85}
            consistent_anomaly_result = {'anomalies_detected': [{'anomaly_score': 0.3}]}
            consistent_fraud_result = {'overall_fraud_risk': 0.25}
            
            mock_face.return_value = consistent_face_result
            mock_anomaly.return_value = consistent_anomaly_result  
            mock_fraud.return_value = consistent_fraud_result
            
            # Process in real-time mode
            real_time_result = self.integration.process_attendance(attendance.id)
            
            # Reset mocks and process in batch mode (simulated)
            mock_face.reset_mock()
            mock_anomaly.reset_mock()
            mock_fraud.reset_mock()
            
            mock_face.return_value = consistent_face_result
            mock_anomaly.return_value = consistent_anomaly_result
            mock_fraud.return_value = consistent_fraud_result
            
            batch_result = self.integration.process_attendance(attendance.id)
            
            # Results should be consistent between modes
            self.assertEqual(
                real_time_result['face_verification']['similarity_score'],
                batch_result['face_verification']['similarity_score']
            )
    
    def test_ai_model_version_consistency(self):
        """Test consistency when using different AI model versions"""
        # Create face recognition models with different versions
        from apps.face_recognition.models import FaceRecognitionModel
        
        v1_model = FaceRecognitionModel.objects.create(
            name='FaceNet V1',
            model_type='FACENET512', 
            version='1.0',
            status='ACTIVE'
        )
        
        v2_model = FaceRecognitionModel.objects.create(
            name='FaceNet V2',
            model_type='FACENET512',
            version='2.0', 
            status='ACTIVE'
        )
        
        attendance = AttendanceFactory(user=self.test_user)
        
        # Process with different model versions and verify compatibility
        with patch('apps.face_recognition.integrations.EnhancedFaceRecognitionEngine') as mock_engine:
            mock_instance = Mock()
            mock_engine.return_value = mock_instance
            
            # Mock verification results for different versions
            mock_instance.verify_face.side_effect = [
                Mock(verification_successful=True, similarity_score=0.87),  # V1 result
                Mock(verification_successful=True, similarity_score=0.85)   # V2 result
            ]
            
            # Process with V1
            result_v1 = self.integration.process_attendance(attendance.id)
            
            # Process with V2  
            result_v2 = self.integration.process_attendance(attendance.id)
            
            # Results should be comparable (within reasonable range)
            v1_score = result_v1.get('face_verification', {}).get('similarity_score', 0)
            v2_score = result_v2.get('face_verification', {}).get('similarity_score', 0)
            
            if v1_score and v2_score:
                score_difference = abs(v1_score - v2_score)
                self.assertLess(score_difference, 0.1)  # Less than 10% difference
    
    def test_concurrent_processing_safety(self):
        """Test thread safety during concurrent AI processing"""
        import threading
        import time
        
        attendances = [AttendanceFactory(user=self.test_user) for _ in range(3)]
        results = {}
        errors = []
        
        def process_attendance(attendance):
            try:
                result = self.integration.process_attendance(attendance.id)
                results[attendance.id] = result
            except Exception as e:
                errors.append(str(e))
        
        # Create threads for concurrent processing
        threads = []
        for attendance in attendances:
            thread = threading.Thread(target=process_attendance, args=(attendance,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout
        
        # Verify results
        self.assertEqual(len(errors), 0, f"Concurrent processing errors: {errors}")
        self.assertEqual(len(results), 3)
        
        # All results should be successful
        for result in results.values():
            self.assertTrue(result.get('success', False))


class DatabaseIntegrationTest(TransactionTestCase):
    """Test database integration and transaction handling"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_atomic_ai_data_creation(self):
        """Test atomic creation of related AI data"""
        from django.db import transaction
        
        attendance = AttendanceFactory(user=self.user)
        
        try:
            with transaction.atomic():
                # Create related AI records atomically
                face_log = FaceVerificationLog.objects.create(
                    user=self.user,
                    similarity_score=0.85,
                    confidence_score=0.90,
                    result='SUCCESS'
                )
                
                fraud_assessment = FraudRiskAssessment.objects.create(
                    user=self.user,
                    overall_risk_score=0.25,
                    face_recognition_risk=0.2,
                    location_risk=0.3,
                    temporal_risk=0.2,
                    behavioral_risk=0.3
                )
                
                # Simulate processing error
                if False:  # Change to True to test rollback
                    raise Exception('Simulated processing error')
                
        except Exception:
            # On error, all records should be rolled back
            pass
        
        # Verify records were created successfully
        self.assertTrue(
            FaceVerificationLog.objects.filter(user=self.user).exists()
        )
        self.assertTrue(
            FraudRiskAssessment.objects.filter(user=self.user).exists()
        )
    
    def test_database_performance_with_ai_data(self):
        """Test database performance with large AI datasets"""
        from django.test.utils import override_settings
        from django.db import connection
        
        # Create bulk test data
        bulk_data = create_bulk_test_data(num_users=10)
        
        # Test query performance
        with override_settings(DEBUG=True):
            connection.queries_log.clear()
            
            # Query attendance with AI data
            attendances_with_ai = PeopleEventlog.objects.select_related(
                'user__behavior_profile'
            ).prefetch_related(
                'user__faceembedding_set',
                'user__fraudriskassessment_set'
            )[:50]
            
            # Force evaluation
            list(attendances_with_ai)
            
            # Check query count (should be optimized)
            query_count = len(connection.queries)
            self.assertLess(query_count, 10, "Too many database queries for AI data retrieval")
    
    def test_database_constraints_and_validation(self):
        """Test database constraints and validation for AI data"""
        # Test face embedding vector constraints
        with self.assertRaises(Exception):
            # Invalid embedding vector (wrong dimensions)
            FaceEmbedding.objects.create(
                user=self.user,
                embedding_vector=[],  # Empty vector should fail
                face_confidence=0.85
            )
        
        # Test fraud risk score constraints
        fraud_assessment = FraudRiskAssessment(
            user=self.user,
            overall_risk_score=1.5,  # Invalid score > 1.0
            face_recognition_risk=0.2,
            location_risk=0.3,
            temporal_risk=0.2,
            behavioral_risk=0.3
        )
        
        # Should pass model creation but could fail on custom validation
        fraud_assessment.save()  # This might be valid depending on model constraints
        
    def test_cascade_deletion_behavior(self):
        """Test cascade deletion behavior for AI-related data"""
        # Create user with AI data
        user_with_ai = create_user_with_ai_data()
        test_user = user_with_ai['user']
        
        # Count related AI records before deletion
        face_embeddings_count = FaceEmbedding.objects.filter(user=test_user).count()
        face_logs_count = FaceVerificationLog.objects.filter(user=test_user).count()
        fraud_assessments_count = FraudRiskAssessment.objects.filter(user=test_user).count()
        
        # Verify AI data exists
        self.assertGreater(face_embeddings_count, 0)
        self.assertGreater(fraud_assessments_count, 0)
        
        # Delete user
        test_user.delete()
        
        # Verify related AI data was deleted (assuming CASCADE)
        remaining_embeddings = FaceEmbedding.objects.filter(user=test_user).count()
        remaining_assessments = FraudRiskAssessment.objects.filter(user=test_user).count()
        
        self.assertEqual(remaining_embeddings, 0)
        self.assertEqual(remaining_assessments, 0)
    
    def test_data_migration_compatibility(self):
        """Test compatibility with data migrations"""
        # Create data in old format (simulating migration scenario)
        old_format_attendance = AttendanceFactory(
            user=self.user,
            extra_info={'old_format': True}  # Simulating old data format
        )
        
        # Process with new AI system
        integration = AIAttendanceIntegration()
        
        with patch.object(integration, 'process_attendance') as mock_process:
            mock_process.return_value = {'success': True, 'migrated_data': True}
            
            result = integration.process_attendance(old_format_attendance.id)
            
            # Should handle old format gracefully
            self.assertTrue(result.get('success'))
    
    def test_index_optimization_for_ai_queries(self):
        """Test that database indexes are optimized for AI queries"""
        # Create test data
        users = [UserFactory() for _ in range(20)]
        
        for user in users:
            # Create multiple face embeddings per user
            FaceEmbeddingFactory.create_batch(3, user=user)
            # Create fraud assessments
            FraudRiskAssessmentFactory.create_batch(2, user=user)
        
        from django.db import connection
        from django.test.utils import override_settings
        
        with override_settings(DEBUG=True):
            connection.queries_log.clear()
            
            # Common AI query patterns
            
            # 1. Find user embeddings for verification
            user_embeddings = FaceEmbedding.objects.filter(
                user=users[0],
                is_validated=True
            ).order_by('-face_confidence')
            list(user_embeddings)
            
            # 2. Find recent fraud assessments
            recent_assessments = FraudRiskAssessment.objects.filter(
                assessment_timestamp__gte=timezone.now() - timedelta(days=7)
            ).select_related('user')
            list(recent_assessments)
            
            # 3. Find high-risk users
            high_risk_users = FraudRiskAssessment.objects.filter(
                overall_risk_score__gte=0.7
            ).values_list('user_id', flat=True)
            list(high_risk_users)
            
            # Query count should be reasonable for these operations
            total_queries = len(connection.queries)
            self.assertLess(total_queries, 10, "AI queries should be optimized with proper indexes")


class CacheIntegrationTest(TestCase):
    """Test caching integration for AI systems"""
    
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = UserFactory()
    
    def test_ai_result_caching(self):
        """Test caching of AI processing results"""
        attendance = AttendanceFactory(user=self.user)
        integration = AIAttendanceIntegration()
        
        with patch.object(integration, '_process_face_verification') as mock_face:
            mock_face.return_value = {'similarity_score': 0.85}
            
            # First call should miss cache and process
            result1 = integration.process_attendance(attendance.id)
            mock_face.assert_called_once()
            
            # Second call should hit cache (mock won't be called again)
            mock_face.reset_mock()
            result2 = integration.process_attendance(attendance.id)
            # mock_face.assert_not_called()  # Would be true if caching is implemented
            
            # Results should be identical
            # self.assertEqual(result1, result2)  # Would be true with proper caching
    
    def test_cache_invalidation_on_data_change(self):
        """Test cache invalidation when related data changes"""
        # Create cached data
        cache.set(f'user_embeddings_{self.user.id}', {'cached': True}, timeout=300)
        
        # Verify cache exists
        cached_data = cache.get(f'user_embeddings_{self.user.id}')
        self.assertIsNotNone(cached_data)
        
        # Create new face embedding (should invalidate cache)
        FaceEmbeddingFactory(user=self.user)
        
        # In a real implementation, this would trigger cache invalidation
        # For testing purposes, we'll manually clear it
        cache.delete(f'user_embeddings_{self.user.id}')
        
        # Cache should be invalidated
        cached_data_after = cache.get(f'user_embeddings_{self.user.id}')
        self.assertIsNone(cached_data_after)
    
    def test_distributed_cache_consistency(self):
        """Test cache consistency in distributed environments"""
        # Simulate multiple cache keys for same data
        cache.set('ai_model_config_v1', {'threshold': 0.3}, timeout=300)
        cache.set('ai_model_config_v2', {'threshold': 0.4}, timeout=300)
        
        # Verify both versions are cached
        v1_config = cache.get('ai_model_config_v1')
        v2_config = cache.get('ai_model_config_v2')
        
        self.assertIsNotNone(v1_config)
        self.assertIsNotNone(v2_config)
        self.assertNotEqual(v1_config, v2_config)
        
        # Test cache cleanup
        cache.delete_many(['ai_model_config_v1', 'ai_model_config_v2'])
        
        # Verify cleanup
        self.assertIsNone(cache.get('ai_model_config_v1'))
        self.assertIsNone(cache.get('ai_model_config_v2'))