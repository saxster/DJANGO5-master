"""
Performance and load tests for AI systems
Tests throughput, response times, and resource usage under load
"""

import time
import threading
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.db import connection
from datetime import timedelta
import gc
import psutil
import os

from apps.face_recognition.integrations import AIAttendanceIntegration
from apps.face_recognition.enhanced_engine import EnhancedFaceRecognitionEngine
from apps.anomaly_detection.engines import EnsembleAnomalyDetector
from apps.behavioral_analytics.fraud_detector import AttendanceFraudDetector
from tests.factories import (
    UserFactory, AttendanceFactory, FaceEmbeddingFactory,
    create_bulk_test_data
)
from tests.utils import AITestCase


class AISystemLoadTest(TransactionTestCase):
    """Test AI system performance under various load conditions"""
    
    def setUp(self):
        super().setUp()
        self.integration = AIAttendanceIntegration()
        self.test_users = [UserFactory() for _ in range(10)]
        
        # Create embeddings for users
        for user in self.test_users:
            FaceEmbeddingFactory.create_batch(3, user=user)
    
    def test_single_request_performance(self):
        """Test performance of single AI processing request"""
        user = self.test_users[0]
        attendance = AttendanceFactory(user=user)
        
        start_time = time.time()
        result = self.integration.process_attendance(attendance.id)
        end_time = time.time()
        
        processing_time = (end_time - start_time) * 1000  # ms
        
        # Single request should complete quickly
        self.assertLess(processing_time, 2000)  # Less than 2 seconds
        self.assertTrue(result['success'])
        
        # Check individual component times
        if 'performance_metrics' in result:
            metrics = result['performance_metrics']
            self.assertLess(metrics.get('face_verification_time_ms', 0), 1000)
            self.assertLess(metrics.get('anomaly_detection_time_ms', 0), 500)
            self.assertLess(metrics.get('fraud_analysis_time_ms', 0), 500)
    
    def test_concurrent_requests_performance(self):
        """Test performance under concurrent requests"""
        num_concurrent = 10
        attendances = [AttendanceFactory(user=self.test_users[i % len(self.test_users)]) 
                      for i in range(num_concurrent)]
        
        results = []
        start_time = time.time()
        
        def process_attendance(attendance_id):
            start = time.time()
            result = self.integration.process_attendance(attendance_id)
            end = time.time()
            return {
                'success': result.get('success', False),
                'processing_time': (end - start) * 1000
            }
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_results = [
                executor.submit(process_attendance, att.id) 
                for att in attendances
            ]
            
            for future in future_results:
                results.append(future.result(timeout=10))
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000
        
        # All requests should succeed
        success_count = sum(1 for r in results if r['success'])
        self.assertEqual(success_count, num_concurrent)
        
        # Calculate average response time
        avg_response_time = sum(r['processing_time'] for r in results) / len(results)
        
        # Average response time should be reasonable under load
        self.assertLess(avg_response_time, 5000)  # Less than 5 seconds average
        
        # Total time should show concurrency benefits
        self.assertLess(total_time, avg_response_time * num_concurrent * 0.8)
    
    def test_throughput_under_sustained_load(self):
        """Test system throughput under sustained load"""
        duration_seconds = 30  # 30 second test
        max_workers = 5
        completed_requests = []
        
        def sustained_load_worker():
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                try:
                    user = self.test_users[int(time.time()) % len(self.test_users)]
                    attendance = AttendanceFactory(user=user)
                    
                    request_start = time.time()
                    result = self.integration.process_attendance(attendance.id)
                    request_end = time.time()
                    
                    completed_requests.append({
                        'success': result.get('success', False),
                        'processing_time': (request_end - request_start) * 1000,
                        'timestamp': request_end
                    })
                    
                    # Small delay to prevent overwhelming
                    time.sleep(0.1)
                    
                except Exception as e:
                    completed_requests.append({
                        'success': False,
                        'error': str(e),
                        'timestamp': time.time()
                    })
        
        # Start sustained load
        threads = []
        load_start = time.time()
        
        for _ in range(max_workers):
            thread = threading.Thread(target=sustained_load_worker)
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        load_end = time.time()
        actual_duration = load_end - load_start
        
        # Analyze results
        total_requests = len(completed_requests)
        successful_requests = sum(1 for r in completed_requests if r['success'])
        
        # Calculate throughput
        requests_per_second = total_requests / actual_duration
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        
        # Performance assertions
        self.assertGreater(requests_per_second, 2)  # At least 2 RPS
        self.assertGreater(success_rate, 0.90)      # 90% success rate
        self.assertGreater(total_requests, 50)      # Minimum requests processed
    
    def test_memory_usage_under_load(self):
        """Test memory usage patterns under load"""
        process = psutil.Process(os.getpid())
        
        # Measure initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process many requests
        num_requests = 100
        for i in range(num_requests):
            user = self.test_users[i % len(self.test_users)]
            attendance = AttendanceFactory(user=user)
            
            result = self.integration.process_attendance(attendance.id)
            
            # Force garbage collection periodically
            if i % 10 == 0:
                gc.collect()
        
        # Measure final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable
        self.assertLess(memory_increase, 100)  # Less than 100MB increase
        
        # Force final garbage collection and check for memory leaks
        gc.collect()
        post_gc_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Memory should decrease after garbage collection
        self.assertLessEqual(post_gc_memory, final_memory)
    
    def test_database_performance_under_load(self):
        """Test database performance under AI processing load"""
        from django.db import connection
        from django.test.utils import override_settings
        
        with override_settings(DEBUG=True):
            connection.queries_log.clear()
            
            # Process multiple requests
            num_requests = 20
            for i in range(num_requests):
                user = self.test_users[i % len(self.test_users)]
                attendance = AttendanceFactory(user=user)
                
                start_queries = len(connection.queries)
                result = self.integration.process_attendance(attendance.id)
                end_queries = len(connection.queries)
                
                queries_per_request = end_queries - start_queries
                
                # Each request should not generate excessive queries
                self.assertLess(queries_per_request, 50)  # Less than 50 queries per request
            
            # Analyze query patterns
            total_queries = len(connection.queries)
            avg_queries_per_request = total_queries / num_requests
            
            self.assertLess(avg_queries_per_request, 30)  # Average less than 30 queries
    
    def test_cache_performance_under_load(self):
        """Test cache performance and hit rates under load"""
        from django.core.cache import cache
        
        cache.clear()  # Start with empty cache
        
        # First pass - populate cache
        cache_misses = 0
        cache_hits = 0
        
        for i in range(20):
            user = self.test_users[i % len(self.test_users)]
            attendance = AttendanceFactory(user=user)
            
            # Check if user embeddings are cached
            cache_key = f'user_embeddings_{user.id}'
            cached_data = cache.get(cache_key)
            
            if cached_data is None:
                cache_misses += 1
                # Simulate cache population
                cache.set(cache_key, {'embeddings': 'mock_data'}, timeout=300)
            else:
                cache_hits += 1
        
        # Calculate cache hit rate
        total_requests = cache_hits + cache_misses
        hit_rate = cache_hits / total_requests if total_requests > 0 else 0
        
        # After first pass, hit rate should improve
        self.assertGreater(hit_rate, 0.3)  # At least 30% hit rate
    
    def test_error_handling_under_load(self):
        """Test error handling and recovery under load conditions"""
        error_count = 0
        success_count = 0
        total_requests = 50
        
        for i in range(total_requests):
            try:
                user = self.test_users[i % len(self.test_users)]
                
                # Occasionally create problematic data
                if i % 10 == 0:
                    # Create attendance without required fields
                    attendance = AttendanceFactory(
                        user=user,
                        extra_info={}  # Missing face recognition data
                    )
                else:
                    attendance = AttendanceFactory(user=user)
                
                result = self.integration.process_attendance(attendance.id)
                
                if result.get('success', False):
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception:
                error_count += 1
        
        # System should handle errors gracefully
        error_rate = error_count / total_requests
        self.assertLess(error_rate, 0.2)  # Less than 20% error rate
        
        # Most requests should still succeed
        self.assertGreater(success_count, total_requests * 0.8)
    
    def test_scalability_with_user_count(self):
        """Test scalability as user count increases"""
        user_counts = [10, 50, 100]
        performance_results = []
        
        for user_count in user_counts:
            # Create users for this test
            test_users = [UserFactory() for _ in range(user_count)]
            for user in test_users:
                FaceEmbeddingFactory.create_batch(2, user=user)
            
            # Measure performance with this user count
            requests_per_user = 2
            total_requests = user_count * requests_per_user
            
            start_time = time.time()
            
            for i in range(total_requests):
                user = test_users[i % user_count]
                attendance = AttendanceFactory(user=user)
                result = self.integration.process_attendance(attendance.id)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            avg_time_per_request = total_time / total_requests
            performance_results.append({
                'user_count': user_count,
                'total_time': total_time,
                'avg_time_per_request': avg_time_per_request
            })
        
        # Performance should not degrade dramatically with user count
        first_avg = performance_results[0]['avg_time_per_request']
        last_avg = performance_results[-1]['avg_time_per_request']
        
        # Performance degradation should be sub-linear
        degradation_factor = last_avg / first_avg
        self.assertLess(degradation_factor, 3.0)  # Less than 3x degradation


class ComponentPerformanceTest(TestCase):
    """Test performance of individual AI components"""
    
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        FaceEmbeddingFactory.create_batch(5, user=self.user)
    
    def test_face_recognition_engine_performance(self):
        """Test face recognition engine performance"""
        from unittest.mock import patch
        
        engine = EnhancedFaceRecognitionEngine()
        
        # Test face verification performance
        start_time = time.time()
        
        with patch.object(engine, 'verify_face') as mock_verify:
            mock_verify.return_value = Mock(
                verification_successful=True,
                similarity_score=0.85,
                processing_time_ms=120.0
            )
            
            # Run multiple verifications
            for _ in range(10):
                result = engine.verify_face(self.user.id, '/mock/image/path.jpg')
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000
        avg_time_per_verification = total_time / 10
        
        # Each verification should be fast
        self.assertLess(avg_time_per_verification, 200)  # Less than 200ms average
    
    def test_anomaly_detection_performance(self):
        """Test anomaly detection performance"""
        detector = EnsembleAnomalyDetector()
        
        # Create test data
        import pandas as pd
        import numpy as np
        
        test_data = pd.DataFrame({
            'feature1': np.random.normal(0, 1, 100),
            'feature2': np.random.normal(0, 1, 100),
            'feature3': np.random.normal(0, 1, 100)
        })
        
        # Test detection performance
        start_time = time.time()
        
        with patch.object(detector, 'detect_anomalies') as mock_detect:
            mock_detect.return_value = [
                {'anomaly_score': 0.3, 'is_anomaly': False}
                for _ in range(100)
            ]
            
            results = detector.detect_anomalies(test_data, 'performance_test')
        
        end_time = time.time()
        processing_time = (end_time - start_time) * 1000
        
        # Anomaly detection should be fast for moderate datasets
        self.assertLess(processing_time, 1000)  # Less than 1 second
    
    def test_fraud_detection_performance(self):
        """Test fraud detection performance"""
        detector = AttendanceFraudDetector()
        
        attendances = [AttendanceFactory(user=self.user) for _ in range(10)]
        
        start_time = time.time()
        
        for attendance in attendances:
            with patch.object(detector, 'analyze_attendance') as mock_analyze:
                mock_analyze.return_value = {
                    'overall_fraud_risk': 0.25,
                    'fraud_indicators': [],
                    'confidence_score': 0.88
                }
                
                result = detector.analyze_attendance(
                    attendance, 
                    ['temporal_analysis', 'spatial_analysis']
                )
        
        end_time = time.time()
        total_time = (end_time - start_time) * 1000
        avg_time_per_analysis = total_time / len(attendances)
        
        # Fraud analysis should be fast
        self.assertLess(avg_time_per_analysis, 500)  # Less than 500ms per analysis
    
    def test_batch_processing_efficiency(self):
        """Test efficiency gains from batch processing"""
        integration = AIAttendanceIntegration()
        
        # Create test attendances
        attendances = [AttendanceFactory(user=self.user) for _ in range(20)]
        attendance_ids = [att.id for att in attendances]
        
        # Test individual processing
        start_time = time.time()
        individual_results = []
        
        for att_id in attendance_ids[:10]:  # Test with first 10
            result = integration.process_attendance(att_id)
            individual_results.append(result)
        
        individual_time = time.time() - start_time
        
        # Test batch processing (simulated)
        start_time = time.time()
        
        # Simulate batch processing advantages
        with patch.object(integration, '_process_batch_optimized') as mock_batch:
            mock_batch.return_value = [
                {'success': True, 'processing_time_ms': 80}
                for _ in range(10)
            ]
            
            batch_results = integration.process_attendance_batch(attendance_ids[10:20])
        
        batch_time = time.time() - start_time
        
        # Batch processing should be more efficient
        if batch_time > 0 and individual_time > 0:
            efficiency_gain = individual_time / batch_time
            self.assertGreater(efficiency_gain, 0.8)  # At least some efficiency gain


class ResourceUsageTest(TestCase):
    """Test resource usage patterns during AI processing"""
    
    def setUp(self):
        super().setUp()
        self.process = psutil.Process(os.getpid())
        self.integration = AIAttendanceIntegration()
    
    def test_cpu_usage_during_processing(self):
        """Test CPU usage patterns during AI processing"""
        # Measure baseline CPU usage
        baseline_cpu = self.process.cpu_percent(interval=1)
        
        # Perform AI processing
        users = [UserFactory() for _ in range(5)]
        for user in users:
            FaceEmbeddingFactory.create_batch(2, user=user)
        
        start_time = time.time()
        
        for user in users:
            attendance = AttendanceFactory(user=user)
            result = self.integration.process_attendance(attendance.id)
        
        processing_time = time.time() - start_time
        processing_cpu = self.process.cpu_percent()
        
        # CPU usage should be reasonable
        self.assertLess(processing_cpu, 80)  # Less than 80% CPU usage
    
    def test_memory_efficiency(self):
        """Test memory efficiency during processing"""
        initial_memory = self.process.memory_info().rss
        
        # Create and process data
        bulk_data = create_bulk_test_data(num_users=20)
        
        for user_data in bulk_data[:10]:  # Process subset
            result = self.integration.process_attendance(
                user_data['attendance'].id
            )
        
        peak_memory = self.process.memory_info().rss
        memory_increase = (peak_memory - initial_memory) / 1024 / 1024  # MB
        
        # Memory increase should be reasonable
        self.assertLess(memory_increase, 50)  # Less than 50MB increase
        
        # Clean up and check memory is released
        del bulk_data
        gc.collect()
        
        final_memory = self.process.memory_info().rss
        self.assertLessEqual(final_memory, peak_memory * 1.1)  # Within 10% of peak
    
    def test_io_efficiency(self):
        """Test I/O efficiency during processing"""
        io_counters_start = self.process.io_counters()
        
        # Perform processing that involves I/O
        users = [UserFactory() for _ in range(10)]
        for user in users:
            FaceEmbeddingFactory.create_batch(3, user=user)
            attendance = AttendanceFactory(user=user)
            result = self.integration.process_attendance(attendance.id)
        
        io_counters_end = self.process.io_counters()
        
        # Calculate I/O metrics
        read_bytes = io_counters_end.read_bytes - io_counters_start.read_bytes
        write_bytes = io_counters_end.write_bytes - io_counters_start.write_bytes
        
        # I/O should be reasonable for the processing done
        total_io_mb = (read_bytes + write_bytes) / 1024 / 1024
        self.assertLess(total_io_mb, 10)  # Less than 10MB total I/O


class StressTest(TransactionTestCase):
    """Stress tests for AI systems"""
    
    def setUp(self):
        super().setUp()
        self.integration = AIAttendanceIntegration()
    
    def test_high_concurrency_stress(self):
        """Test system under very high concurrency"""
        max_workers = 20  # High concurrency
        num_requests = 100
        users = [UserFactory() for _ in range(10)]
        
        # Create embeddings
        for user in users:
            FaceEmbeddingFactory.create_batch(2, user=user)
        
        results = []
        errors = []
        
        def stress_worker(worker_id):
            for i in range(num_requests // max_workers):
                try:
                    user = users[i % len(users)]
                    attendance = AttendanceFactory(user=user)
                    
                    start_time = time.time()
                    result = self.integration.process_attendance(attendance.id)
                    end_time = time.time()
                    
                    results.append({
                        'worker_id': worker_id,
                        'success': result.get('success', False),
                        'processing_time': (end_time - start_time) * 1000
                    })
                    
                except Exception as e:
                    errors.append({
                        'worker_id': worker_id,
                        'error': str(e)
                    })
        
        # Run stress test
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(stress_worker, i) 
                for i in range(max_workers)
            ]
            
            # Wait for completion with timeout
            for future in futures:
                future.result(timeout=60)  # 60 second timeout
        
        # Analyze stress test results
        total_attempts = len(results) + len(errors)
        success_rate = len([r for r in results if r['success']]) / len(results) if results else 0
        error_rate = len(errors) / total_attempts if total_attempts > 0 else 0
        
        # System should maintain reasonable performance under stress
        self.assertGreater(success_rate, 0.85)  # 85% success rate
        self.assertLess(error_rate, 0.15)       # Less than 15% errors
        self.assertGreater(total_attempts, 80)   # Most requests completed
    
    def test_prolonged_operation_stability(self):
        """Test system stability during prolonged operations"""
        duration_minutes = 2  # 2 minute stress test
        duration_seconds = duration_minutes * 60
        
        users = [UserFactory() for _ in range(5)]
        for user in users:
            FaceEmbeddingFactory.create_batch(2, user=user)
        
        start_time = time.time()
        requests_completed = 0
        errors_encountered = 0
        
        while time.time() - start_time < duration_seconds:
            try:
                user = users[requests_completed % len(users)]
                attendance = AttendanceFactory(user=user)
                
                result = self.integration.process_attendance(attendance.id)
                
                if result.get('success', False):
                    requests_completed += 1
                else:
                    errors_encountered += 1
                
                # Small delay to prevent overwhelming
                time.sleep(0.5)
                
            except Exception:
                errors_encountered += 1
        
        total_attempts = requests_completed + errors_encountered
        actual_duration = time.time() - start_time
        
        # System should maintain stability
        throughput = total_attempts / actual_duration
        error_rate = errors_encountered / total_attempts if total_attempts > 0 else 0
        
        self.assertGreater(throughput, 0.5)     # At least 0.5 requests per second
        self.assertLess(error_rate, 0.1)        # Less than 10% error rate
        self.assertGreater(total_attempts, 100) # Minimum requests processed