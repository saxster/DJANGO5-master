"""
File Upload Performance Tests

Validates that security validations don't create unacceptable performance overhead.
Tests concurrent uploads, large files, and system resource usage.

Performance Targets:
- Small files (<1MB): < 100ms validation
- Medium files (1-5MB): < 500ms validation
- Large files (5-10MB): < 2000ms validation
- Concurrent uploads: Support 10+ simultaneous uploads
- Memory usage: < 50MB per upload
"""

import os
import time
import io
import pytest
import threading
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from apps.core.services.secure_file_upload_service import SecureFileUploadService
from apps.core.services.advanced_file_validation_service import AdvancedFileValidationService

User = get_user_model()


@pytest.mark.performance
class FileValidationPerformanceTests(TestCase):
    """Performance tests for file validation operations."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='perf_user',
            email='perf@test.com',
            peoplename='Performance User',
            peoplecode='PERF001'
        )

    def create_test_file(self, size_bytes, filename='test.jpg'):
        """Create test file of specified size."""
        content = b'\xFF\xD8\xFF\xE0' + b'X' * (size_bytes - 4)
        return SimpleUploadedFile(filename, content, content_type='image/jpeg')

    def test_small_file_validation_performance(self):
        """Test: Validation of small files (<1MB) completes quickly"""
        small_file = self.create_test_file(500 * 1024)

        start_time = time.time()
        result = SecureFileUploadService.validate_and_process_upload(
            small_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )
        elapsed_ms = (time.time() - start_time) * 1000

        self.assertLess(elapsed_ms, 100, f"Small file validation took {elapsed_ms:.2f}ms (target: <100ms)")
        self.assertIn('correlation_id', result)

    def test_medium_file_validation_performance(self):
        """Test: Validation of medium files (1-5MB) completes in reasonable time"""
        medium_file = self.create_test_file(3 * 1024 * 1024)

        start_time = time.time()
        result = SecureFileUploadService.validate_and_process_upload(
            medium_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )
        elapsed_ms = (time.time() - start_time) * 1000

        self.assertLess(elapsed_ms, 500, f"Medium file validation took {elapsed_ms:.2f}ms (target: <500ms)")

    def test_large_file_validation_performance(self):
        """Test: Validation of large files (5-10MB) completes within limits"""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            tmp_file.write(b'\xFF\xD8\xFF\xE0')
            tmp_file.write(b'X' * (5 * 1024 * 1024))
            tmp_path = tmp_file.name

        with open(tmp_path, 'rb') as f:
            large_file = InMemoryUploadedFile(
                f, None, 'large.jpg', 'image/jpeg', os.path.getsize(tmp_path), None
            )

            start_time = time.time()
            try:
                result = SecureFileUploadService.validate_and_process_upload(
                    large_file,
                    'image',
                    {'people_id': self.user.id, 'folder_type': 'test'}
                )
                elapsed_ms = (time.time() - start_time) * 1000

                self.assertLess(elapsed_ms, 2000, f"Large file validation took {elapsed_ms:.2f}ms (target: <2000ms)")

            finally:
                os.unlink(tmp_path)


@pytest.mark.performance
class ConcurrentUploadTests(TestCase):
    """Performance tests for concurrent file uploads."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='concurrent_user',
            email='concurrent@test.com',
            peoplename='Concurrent User',
            peoplecode='C001'
        )
        self.results = []
        self.lock = threading.Lock()

    def upload_file_thread(self, file_index):
        """Upload file in separate thread."""
        try:
            test_file = SimpleUploadedFile(
                f'concurrent_{file_index}.jpg',
                b'\xFF\xD8\xFF\xE0' + b'X' * (100 * 1024),
                content_type='image/jpeg'
            )

            start_time = time.time()
            result = SecureFileUploadService.validate_and_process_upload(
                test_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )
            elapsed = time.time() - start_time

            with self.lock:
                self.results.append({
                    'index': file_index,
                    'success': True,
                    'elapsed': elapsed,
                    'correlation_id': result['correlation_id']
                })

        except Exception as e:
            with self.lock:
                self.results.append({
                    'index': file_index,
                    'success': False,
                    'error': str(e)
                })

    def test_concurrent_uploads_performance(self):
        """Test: System handles 10 concurrent uploads efficiently"""
        threads = []
        num_concurrent = 10

        start_time = time.time()

        for i in range(num_concurrent):
            thread = threading.Thread(target=self.upload_file_thread, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=10)

        total_elapsed = time.time() - start_time

        successful = sum(1 for r in self.results if r.get('success'))
        avg_time = sum(r.get('elapsed', 0) for r in self.results) / len(self.results) if self.results else 0

        self.assertGreaterEqual(successful, 8, f"Only {successful}/{num_concurrent} uploads succeeded")
        self.assertLess(total_elapsed, 5, f"Concurrent uploads took {total_elapsed:.2f}s (target: <5s)")
        self.assertLess(avg_time, 1, f"Average validation time {avg_time:.2f}s (target: <1s)")


@pytest.mark.performance
class MemoryUsageTests(TestCase):
    """Test memory usage during file uploads."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='memory_user',
            email='memory@test.com',
            peoplename='Memory User',
            peoplecode='MEM001'
        )

    def test_memory_efficient_large_file_processing(self):
        """Test: Large files processed without excessive memory usage"""
        import psutil
        import gc

        gc.collect()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024

        large_file = SimpleUploadedFile(
            'memory_test.jpg',
            b'\xFF\xD8\xFF\xE0' + b'X' * (5 * 1024 * 1024),
            content_type='image/jpeg'
        )

        try:
            result = SecureFileUploadService.validate_and_process_upload(
                large_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

            gc.collect()
            peak_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = peak_memory - initial_memory

            self.assertLess(memory_increase, 50, f"Memory usage increased by {memory_increase:.2f}MB (target: <50MB)")

        finally:
            gc.collect()


@pytest.mark.performance
class CachingPerformanceTests(TestCase):
    """Test performance of caching mechanisms in file upload."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='cache_user',
            email='cache@test.com',
            peoplename='Cache User',
            peoplecode='CACHE001'
        )

    def test_repeated_validation_performance(self):
        """Test: Repeated validation of same file type is optimized"""
        test_file = SimpleUploadedFile(
            'cache_test.jpg',
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF',
            content_type='image/jpeg'
        )

        first_run_time = self._measure_validation_time(test_file)

        second_run_time = self._measure_validation_time(test_file)

        self.assertLess(second_run_time, first_run_time * 1.2,
                       "Second validation should be similar or faster")

    def _measure_validation_time(self, test_file):
        """Measure validation time for a file."""
        start = time.time()
        SecureFileUploadService.validate_and_process_upload(
            test_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )
        return (time.time() - start) * 1000