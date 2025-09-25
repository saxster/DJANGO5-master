"""
Error recovery tests for AI systems
Tests graceful degradation, rollback mechanisms, and service recovery
"""

import time
import json
from unittest.mock import patch, Mock, MagicMock, PropertyMock
from django.test import TestCase, TransactionTestCase
from django.db import transaction, DatabaseError, IntegrityError
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
import numpy as np

from apps.face_recognition.models import FaceEmbedding, FaceVerificationLog
from apps.face_recognition.integrations import AIAttendanceIntegration
from apps.behavioral_analytics.models import UserBehaviorProfile, FraudRiskAssessment
from apps.anomaly_detection.models import AnomalyDetectionResult
from apps.attendance.models import PeopleEventlog
from tests.factories import UserFactory, AttendanceFactory, FaceEmbeddingFactory
from tests.utils import AITestCase

User = get_user_model()


class DatabaseTransactionRollbackTest(TransactionTestCase):
    """Test database transaction rollback scenarios"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_partial_processing_rollback(self):
        """Test rollback of partial AI processing"""
        attendance = AttendanceFactory(user=self.user)
        
        def process_attendance_with_failure(attendance_id):
            """Process attendance with simulated failure"""
            try:
                with transaction.atomic():
                    # Start processing
                    attendance = PeopleEventlog.objects.get(id=attendance_id)
                    
                    # Create face verification log
                    face_log = FaceVerificationLog.objects.create(
                        user=attendance.user,
                        similarity_score=0.85,
                        confidence_score=0.90,
                        result='SUCCESS'
                    )
                    
                    # Create anomaly detection result
                    anomaly_result = AnomalyDetectionResult.objects.create(
                        anomaly_type='TEMPORAL',
                        severity='LOW',
                        confidence_score=0.75,
                        anomaly_score=0.3
                    )
                    
                    # Simulate failure before fraud assessment
                    raise DatabaseError("Simulated database error")
                    
                    # This should not be created due to rollback
                    fraud_assessment = FraudRiskAssessment.objects.create(
                        user=attendance.user,
                        overall_risk_score=0.25
                    )
                    
                    return {'success': True}
                    
            except DatabaseError:
                # Transaction should rollback
                return {'success': False, 'rolled_back': True}
        
        # Process with failure
        result = process_attendance_with_failure(attendance.id)
        
        # Verify rollback
        self.assertFalse(result['success'])
        self.assertTrue(result['rolled_back'])
        
        # No partial data should exist
        self.assertEqual(
            FaceVerificationLog.objects.filter(user=self.user).count(),
            0
        )
        self.assertEqual(
            AnomalyDetectionResult.objects.filter(
                detection_timestamp__gte=timezone.now() - timedelta(minutes=1)
            ).count(),
            0
        )
    
    def test_nested_transaction_rollback(self):
        """Test nested transaction rollback behavior"""
        def outer_transaction(user):
            """Outer transaction"""
            try:
                with transaction.atomic():
                    # Create profile
                    profile = UserBehaviorProfile.objects.create(
                        user=user,
                        attendance_regularity_score=0.8
                    )
                    
                    # Call inner transaction
                    inner_result = inner_transaction(user)
                    
                    if not inner_result['success']:
                        raise Exception("Inner transaction failed")
                    
                    return {'success': True, 'profile_id': profile.id}
                    
            except Exception:
                return {'success': False}
        
        def inner_transaction(user):
            """Inner transaction with failure"""
            try:
                with transaction.atomic():
                    # Create embedding
                    embedding = FaceEmbeddingFactory(user=user)
                    
                    # Simulate failure
                    raise IntegrityError("Constraint violation")
                    
            except IntegrityError:
                return {'success': False}
        
        # Execute nested transactions
        result = outer_transaction(self.user)
        
        # Both should rollback
        self.assertFalse(result['success'])
        self.assertEqual(
            UserBehaviorProfile.objects.filter(user=self.user).count(),
            0
        )
    
    def test_savepoint_rollback(self):
        """Test savepoint-based partial rollback"""
        def process_with_savepoints(user):
            """Process with savepoint management"""
            results = {
                'embeddings_created': 0,
                'assessments_created': 0,
                'failed_operations': []
            }
            
            with transaction.atomic():
                # Create savepoint before embeddings
                sid1 = transaction.savepoint()
                
                try:
                    # Create embeddings
                    for i in range(3):
                        FaceEmbeddingFactory(user=user)
                        results['embeddings_created'] += 1
                    
                    # Commit savepoint
                    transaction.savepoint_commit(sid1)
                    
                except Exception as e:
                    # Rollback to savepoint
                    transaction.savepoint_rollback(sid1)
                    results['failed_operations'].append('embeddings')
                
                # Create savepoint before assessments
                sid2 = transaction.savepoint()
                
                try:
                    # Create assessments (will fail)
                    for i in range(2):
                        if i == 1:
                            raise ValueError("Simulated error")
                        
                        FraudRiskAssessment.objects.create(
                            user=user,
                            overall_risk_score=0.5
                        )
                        results['assessments_created'] += 1
                    
                    transaction.savepoint_commit(sid2)
                    
                except Exception:
                    # Rollback only assessments
                    transaction.savepoint_rollback(sid2)
                    results['failed_operations'].append('assessments')
            
            return results
        
        result = process_with_savepoints(self.user)
        
        # Embeddings should be created
        self.assertEqual(result['embeddings_created'], 3)
        self.assertEqual(
            FaceEmbedding.objects.filter(user=self.user).count(),
            3
        )
        
        # Assessments should be rolled back
        self.assertIn('assessments', result['failed_operations'])
        self.assertEqual(
            FraudRiskAssessment.objects.filter(user=self.user).count(),
            0
        )


class ServiceUnavailabilityTest(TestCase):
    """Test handling of service unavailability"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.integration = AIAttendanceIntegration()
    
    def test_redis_unavailable(self):
        """Test system behavior when Redis is unavailable"""
        def process_without_redis(data):
            """Process data when Redis cache is unavailable"""
            fallback_cache = {}  # In-memory fallback
            
            def cache_get(key):
                try:
                    return cache.get(key)
                except Exception:
                    # Redis unavailable, use fallback
                    return fallback_cache.get(key)
            
            def cache_set(key, value, timeout=None):
                try:
                    cache.set(key, value, timeout)
                except Exception:
                    # Redis unavailable, use fallback
                    fallback_cache[key] = value
            
            # Process with fallback cache
            cache_key = f'processing_{data["id"]}'
            
            # Try to get from cache
            cached_result = cache_get(cache_key)
            if cached_result:
                return cached_result
            
            # Process data
            result = {
                'processed': True,
                'cache_available': False,
                'using_fallback': True,
                'data': data
            }
            
            # Store in fallback cache
            cache_set(cache_key, result)
            
            return result
        
        # Test with simulated Redis failure
        with patch('django.core.cache.cache.get', side_effect=Exception("Redis connection failed")):
            result = process_without_redis({'id': 123, 'value': 'test'})
            
            self.assertTrue(result['processed'])
            self.assertTrue(result['using_fallback'])
    
    def test_celery_task_failure(self):
        """Test handling of Celery task failures"""
        def process_with_celery_fallback(task_data):
            """Process with Celery or fallback to synchronous"""
            try:
                # Try to queue task
                from celery import current_app
                
                # Simulate Celery task
                with patch.object(current_app, 'send_task', side_effect=Exception("Broker connection failed")):
                    raise Exception("Celery unavailable")
                    
            except Exception:
                # Fallback to synchronous processing
                return process_synchronously(task_data)
        
        def process_synchronously(task_data):
            """Synchronous processing fallback"""
            # Process immediately instead of queueing
            return {
                'processed': True,
                'mode': 'synchronous',
                'task_data': task_data,
                'warning': 'Processed synchronously due to queue unavailability'
            }
        
        result = process_with_celery_fallback({'task': 'face_verification', 'user_id': self.user.id})
        
        self.assertTrue(result['processed'])
        self.assertEqual(result['mode'], 'synchronous')
    
    def test_external_api_timeout(self):
        """Test handling of external API timeouts"""
        def call_external_api_with_retry(endpoint, max_retries=3, timeout=5):
            """Call external API with retry logic"""
            import requests
            from requests.exceptions import Timeout, RequestException
            
            retries = 0
            last_error = None
            
            while retries < max_retries:
                try:
                    # Simulate API call
                    with patch('requests.get', side_effect=Timeout("Connection timeout")):
                        response = requests.get(endpoint, timeout=timeout)
                        
                    return {
                        'success': True,
                        'data': response.json(),
                        'retries': retries
                    }
                    
                except Timeout as e:
                    retries += 1
                    last_error = str(e)
                    
                    # Exponential backoff
                    if retries < max_retries:
                        time.sleep(2 ** retries)
                        
                except RequestException as e:
                    # Non-retryable error
                    return {
                        'success': False,
                        'error': str(e),
                        'retries': retries
                    }
            
            # Max retries exceeded
            return {
                'success': False,
                'error': last_error,
                'retries': retries,
                'fallback': 'use_cached_data'
            }
        
        result = call_external_api_with_retry('https://api.example.com/verify', max_retries=3)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['retries'], 3)
        self.assertEqual(result['fallback'], 'use_cached_data')
    
    def test_database_connection_failure(self):
        """Test handling of database connection failures"""
        def process_with_db_retry(operation):
            """Process with database retry logic"""
            from django.db import connection, OperationalError
            
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Simulate database operation
                    with patch.object(connection, 'ensure_connection', side_effect=OperationalError("Connection failed")):
                        # This would fail
                        result = operation()
                        
                    return {
                        'success': True,
                        'result': result,
                        'retries': retry_count
                    }
                    
                except OperationalError as e:
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        # Wait before retry
                        time.sleep(1)
                        
                        # Try to reconnect
                        try:
                            connection.close()
                            connection.connect()
                        except:
                            pass
                    else:
                        # Use read replica or cache
                        return {
                            'success': False,
                            'error': str(e),
                            'fallback': 'read_replica',
                            'retries': retry_count
                        }
            
            return {'success': False, 'error': 'max_retries_exceeded'}
        
        def mock_operation():
            return "database_result"
        
        result = process_with_db_retry(mock_operation)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['fallback'], 'read_replica')


class GracefulDegradationTest(TestCase):
    """Test graceful degradation of AI features"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_fallback_to_basic_verification(self):
        """Test fallback to basic verification when AI fails"""
        def verify_attendance_with_fallback(user, image_path):
            """Verify attendance with fallback options"""
            verification_methods = [
                ('ai_face_recognition', ai_face_verification),
                ('basic_face_match', basic_face_match),
                ('pin_verification', pin_verification),
                ('manual_override', manual_verification)
            ]
            
            for method_name, method_func in verification_methods:
                try:
                    result = method_func(user, image_path)
                    
                    if result['success']:
                        return {
                            'verified': True,
                            'method_used': method_name,
                            'confidence': result.get('confidence', 0.5),
                            'fallback_level': verification_methods.index((method_name, method_func))
                        }
                        
                except Exception as e:
                    continue  # Try next method
            
            return {
                'verified': False,
                'method_used': 'none',
                'error': 'all_methods_failed'
            }
        
        def ai_face_verification(user, image_path):
            """AI-based face verification (fails)"""
            raise Exception("AI model unavailable")
        
        def basic_face_match(user, image_path):
            """Basic face matching (succeeds)"""
            return {'success': True, 'confidence': 0.7}
        
        def pin_verification(user, image_path):
            """PIN-based verification"""
            return {'success': False}
        
        def manual_verification(user, image_path):
            """Manual override"""
            return {'success': True, 'confidence': 0.5}
        
        result = verify_attendance_with_fallback(self.user, '/mock/image.jpg')
        
        self.assertTrue(result['verified'])
        self.assertEqual(result['method_used'], 'basic_face_match')
        self.assertEqual(result['fallback_level'], 1)
    
    def test_reduced_feature_set(self):
        """Test operation with reduced AI features"""
        def get_available_features():
            """Check which AI features are available"""
            features = {
                'face_recognition': check_face_recognition(),
                'anomaly_detection': check_anomaly_detection(),
                'fraud_detection': check_fraud_detection(),
                'behavioral_analysis': check_behavioral_analysis()
            }
            
            available = [k for k, v in features.items() if v]
            
            return {
                'all_features': list(features.keys()),
                'available_features': available,
                'degraded_mode': len(available) < len(features),
                'critical_features_available': 'face_recognition' in available
            }
        
        def check_face_recognition():
            try:
                # Check if face recognition is available
                from apps.face_recognition.models import FaceRecognitionModel
                return FaceRecognitionModel.objects.filter(status='ACTIVE').exists()
            except:
                return False
        
        def check_anomaly_detection():
            try:
                # Check if anomaly detection is available
                with patch('apps.anomaly_detection.engines.EnsembleAnomalyDetector', side_effect=ImportError):
                    raise ImportError("Module not available")
            except ImportError:
                return False
        
        def check_fraud_detection():
            return True  # Available
        
        def check_behavioral_analysis():
            return True  # Available
        
        features = get_available_features()
        
        self.assertTrue(features['degraded_mode'])
        self.assertIn('fraud_detection', features['available_features'])
        self.assertNotIn('anomaly_detection', features['available_features'])
    
    def test_performance_degradation_handling(self):
        """Test handling of performance degradation"""
        def monitor_and_adapt_performance():
            """Monitor performance and adapt processing"""
            performance_metrics = {
                'response_times': [],
                'cpu_usage': [],
                'memory_usage': []
            }
            
            # Simulate performance monitoring
            for i in range(10):
                # Simulate increasing load
                response_time = 100 + (i * 50)  # Increasing response time
                cpu_usage = 50 + (i * 5)  # Increasing CPU
                memory_usage = 60 + (i * 3)  # Increasing memory
                
                performance_metrics['response_times'].append(response_time)
                performance_metrics['cpu_usage'].append(cpu_usage)
                performance_metrics['memory_usage'].append(memory_usage)
                
                # Check if adaptation needed
                if response_time > 300 or cpu_usage > 80 or memory_usage > 85:
                    return adapt_to_high_load()
            
            return {'adapted': False, 'mode': 'normal'}
        
        def adapt_to_high_load():
            """Adapt system to high load"""
            adaptations = {
                'reduced_accuracy': True,  # Use faster, less accurate models
                'increased_caching': True,  # Cache more aggressively
                'batch_processing': True,  # Batch requests
                'feature_reduction': True,  # Disable non-critical features
                'rate_limiting': True  # Implement rate limiting
            }
            
            return {
                'adapted': True,
                'mode': 'high_load',
                'adaptations': adaptations
            }
        
        result = monitor_and_adapt_performance()
        
        self.assertTrue(result['adapted'])
        self.assertEqual(result['mode'], 'high_load')
        self.assertTrue(result['adaptations']['reduced_accuracy'])


class NetworkPartitionRecoveryTest(TestCase):
    """Test recovery from network partitions"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_split_brain_resolution(self):
        """Test resolution of split-brain scenarios"""
        def detect_and_resolve_split_brain():
            """Detect and resolve split-brain in distributed system"""
            # Simulate two partitions with different data
            partition_a = {
                'node_id': 'node_a',
                'last_update': timezone.now() - timedelta(minutes=5),
                'user_count': 100,
                'latest_attendance_id': 1000
            }
            
            partition_b = {
                'node_id': 'node_b',
                'last_update': timezone.now() - timedelta(minutes=3),
                'user_count': 102,
                'latest_attendance_id': 1005
            }
            
            # Detect split brain
            if partition_a['latest_attendance_id'] != partition_b['latest_attendance_id']:
                # Split brain detected
                resolution = resolve_conflict(partition_a, partition_b)
                
                return {
                    'split_brain_detected': True,
                    'resolution': resolution,
                    'master_partition': resolution['master'],
                    'data_loss': resolution.get('data_loss', False)
                }
            
            return {'split_brain_detected': False}
        
        def resolve_conflict(partition_a, partition_b):
            """Resolve conflict between partitions"""
            # Use latest update as tiebreaker
            if partition_b['last_update'] > partition_a['last_update']:
                master = 'partition_b'
                slave = 'partition_a'
            else:
                master = 'partition_a'
                slave = 'partition_b'
            
            # Calculate potential data loss
            data_diff = abs(
                partition_a['latest_attendance_id'] - 
                partition_b['latest_attendance_id']
            )
            
            return {
                'master': master,
                'slave': slave,
                'action': 'sync_from_master',
                'potential_conflicts': data_diff,
                'data_loss': data_diff > 0
            }
        
        result = detect_and_resolve_split_brain()
        
        self.assertTrue(result['split_brain_detected'])
        self.assertIn(result['master_partition'], ['partition_a', 'partition_b'])
        self.assertTrue(result['data_loss'])
    
    def test_eventual_consistency_recovery(self):
        """Test recovery to eventual consistency"""
        def achieve_eventual_consistency(nodes):
            """Achieve eventual consistency across nodes"""
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                # Check consistency
                all_consistent = check_consistency(nodes)
                
                if all_consistent:
                    return {
                        'consistent': True,
                        'iterations': iteration,
                        'final_state': get_consensus_state(nodes)
                    }
                
                # Sync nodes
                sync_nodes(nodes)
                iteration += 1
            
            return {
                'consistent': False,
                'iterations': iteration,
                'error': 'max_iterations_exceeded'
            }
        
        def check_consistency(nodes):
            """Check if all nodes have consistent data"""
            if not nodes:
                return True
            
            first_state = nodes[0]['state']
            return all(node['state'] == first_state for node in nodes)
        
        def sync_nodes(nodes):
            """Synchronize nodes"""
            # Find node with latest data
            latest_node = max(nodes, key=lambda n: n['version'])
            
            # Update all nodes to latest state
            for node in nodes:
                if node['version'] < latest_node['version']:
                    node['state'] = latest_node['state']
                    node['version'] = latest_node['version']
        
        def get_consensus_state(nodes):
            """Get consensus state from nodes"""
            return nodes[0]['state'] if nodes else None
        
        # Create nodes with inconsistent state
        nodes = [
            {'id': 1, 'state': 'A', 'version': 1},
            {'id': 2, 'state': 'B', 'version': 2},
            {'id': 3, 'state': 'A', 'version': 1}
        ]
        
        result = achieve_eventual_consistency(nodes)
        
        self.assertTrue(result['consistent'])
        self.assertLess(result['iterations'], 10)
        self.assertEqual(result['final_state'], 'B')  # Latest version


class CircuitBreakerTest(TestCase):
    """Test circuit breaker pattern for fault tolerance"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
    
    def test_circuit_breaker_activation(self):
        """Test circuit breaker activation on failures"""
        class CircuitBreaker:
            def __init__(self, failure_threshold=5, timeout=30):
                self.failure_threshold = failure_threshold
                self.timeout = timeout
                self.failure_count = 0
                self.last_failure_time = None
                self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
            
            def call(self, func, *args, **kwargs):
                """Call function through circuit breaker"""
                # Check if circuit is open
                if self.state == 'OPEN':
                    if self._should_attempt_reset():
                        self.state = 'HALF_OPEN'
                    else:
                        return {
                            'success': False,
                            'error': 'circuit_open',
                            'retry_after': self._get_retry_time()
                        }
                
                # Try to call function
                try:
                    result = func(*args, **kwargs)
                    
                    # Reset on success
                    if self.state == 'HALF_OPEN':
                        self._reset()
                    
                    return result
                    
                except Exception as e:
                    self._record_failure()
                    
                    if self.failure_count >= self.failure_threshold:
                        self._trip()
                    
                    raise
            
            def _record_failure(self):
                """Record a failure"""
                self.failure_count += 1
                self.last_failure_time = time.time()
            
            def _trip(self):
                """Trip the circuit breaker"""
                self.state = 'OPEN'
            
            def _reset(self):
                """Reset the circuit breaker"""
                self.state = 'CLOSED'
                self.failure_count = 0
                self.last_failure_time = None
            
            def _should_attempt_reset(self):
                """Check if should attempt reset"""
                return (
                    self.last_failure_time and
                    time.time() - self.last_failure_time > self.timeout
                )
            
            def _get_retry_time(self):
                """Get time until retry"""
                if self.last_failure_time:
                    elapsed = time.time() - self.last_failure_time
                    return max(0, self.timeout - elapsed)
                return self.timeout
        
        # Create circuit breaker
        breaker = CircuitBreaker(failure_threshold=3, timeout=30)
        
        # Simulate failures
        def failing_function():
            raise Exception("Service unavailable")
        
        # Test circuit breaker activation
        for i in range(3):
            try:
                breaker.call(failing_function)
            except:
                pass
        
        # Circuit should be open now
        self.assertEqual(breaker.state, 'OPEN')
        
        # Further calls should fail immediately
        result = breaker.call(failing_function)
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'circuit_open')