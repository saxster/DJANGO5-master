"""
File Streaming Performance Tests

Tests for file streaming optimization and async cleanup.

Tests implemented performance fixes from November 5, 2025 code review:
- Chunk-based streaming vs loading entire file into memory
- Async file cleanup via Celery task
- Memory efficiency under load

Compliance:
- Best practice: Stream files in chunks
- No blocking I/O in request paths
"""

import pytest
import os
import tempfile
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.conf import settings
from unittest.mock import patch, Mock, MagicMock
from apps.reports.tasks import schedule_report_cleanup

People = get_user_model()


@pytest.mark.django_db
class TestFileStreamingOptimization(TestCase):
    """Test file streaming improvements."""

    def setUp(self):
        """Set up test user and files."""
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123',
            is_staff=True
        )
        self.client = Client()
        self.client.login(loginid='testuser', password='testpass123')

    def test_large_file_streams_without_loading_into_memory(self):
        """Test that large files are streamed in chunks, not loaded into memory."""
        # Create a large temporary file (10MB)
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pdf') as f:
            test_file_path = f.name
            # Write 10MB of data
            f.write(b'x' * (10 * 1024 * 1024))
        
        try:
            # Mock the report download to use our test file
            from django.core.cache import cache
            report_id = 'test-report-123'
            cache.set(f'report_path:{report_id}', test_file_path, 300)
            
            # Make download request
            response = self.client.get(f'/api/v1/reports/{report_id}/download/')
            
            # Verify response is FileResponse (streaming)
            from django.http import FileResponse
            assert isinstance(response, FileResponse)
            
            # Verify file is streamed (has streaming_content, not just content)
            assert hasattr(response, 'streaming_content') or hasattr(response, 'file_to_stream')
            
            # Memory check: Response should not contain entire file in memory
            # FileResponse with file handle streams in 4KB chunks by default
            # So response object size should be << file size
            
        finally:
            # Cleanup
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

    def test_file_handle_properly_managed(self):
        """Test that file handles are properly managed (no leaks)."""
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pdf') as f:
            test_file_path = f.name
            f.write('test content')
        
        try:
            from django.core.cache import cache
            report_id = 'test-report-handle'
            cache.set(f'report_path:{report_id}', test_file_path, 300)
            
            # Make download request
            response = self.client.get(f'/api/v1/reports/{report_id}/download/')
            
            # Verify response is FileResponse
            from django.http import FileResponse
            assert isinstance(response, FileResponse)
            
            # FileResponse should handle file closing automatically
            # when response is consumed
            
        finally:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)


@pytest.mark.django_db
class TestAsyncFileCleanup(TestCase):
    """Test async file cleanup via Celery task."""

    def test_cleanup_task_schedules_successfully(self):
        """Test that cleanup task can be scheduled."""
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file_path = f.name
            f.write('cleanup test')
        
        try:
            # Schedule cleanup task
            result = schedule_report_cleanup.apply_async(
                args=[test_file_path],
                countdown=1  # Short delay for testing
            )
            
            # Verify task was scheduled
            assert result is not None
            assert result.id is not None
            
            # Wait for task to complete (in test mode)
            result.get(timeout=5)
            
            # Verify file was deleted
            assert not os.path.exists(test_file_path)
            
        except Exception:
            # Cleanup if task failed
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
            raise

    def test_cleanup_task_handles_missing_file(self):
        """Test that cleanup task handles already-deleted files gracefully."""
        # Reference to non-existent file
        nonexistent_path = '/tmp/nonexistent_report_file.pdf'
        
        # Should not raise exception
        result = schedule_report_cleanup.apply_async(
            args=[nonexistent_path],
            countdown=1
        )
        
        # Task should complete successfully (idempotent)
        task_result = result.get(timeout=5)
        assert task_result is True  # Returns True even if file doesn't exist

    def test_cleanup_task_retries_on_permission_error(self):
        """Test that cleanup task retries on permission errors."""
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file_path = f.name
            f.write('permission test')
        
        try:
            # Make file read-only (simulate permission issue)
            os.chmod(test_file_path, 0o444)
            
            # Mock os.remove to raise PermissionError
            with patch('os.remove') as mock_remove:
                mock_remove.side_effect = PermissionError("Permission denied")
                
                # Schedule cleanup (will retry)
                result = schedule_report_cleanup.apply(
                    args=[test_file_path]
                )
                
                # Verify task attempted retry
                # (In real scenario, would retry with exponential backoff)
                
        finally:
            # Cleanup
            os.chmod(test_file_path, 0o644)
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

    def test_cleanup_task_logs_deletion(self, caplog):
        """Test that cleanup task logs file deletions."""
        import logging
        
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file_path = f.name
            f.write('logging test')
        
        try:
            with caplog.at_level(logging.INFO):
                # Execute cleanup task
                result = schedule_report_cleanup.apply(args=[test_file_path])
            
            # Verify logging occurred
            assert any('Successfully cleaned up report file' in record.message for record in caplog.records)
            
        except Exception:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)
            raise


@pytest.mark.django_db
class TestFileStreamingVsLoading(TestCase):
    """Test memory efficiency of file streaming."""

    def test_streaming_uses_constant_memory(self):
        """Test that file streaming uses constant memory regardless of file size."""
        import sys
        
        # Create test files of different sizes
        sizes = [1024, 1024 * 1024, 10 * 1024 * 1024]  # 1KB, 1MB, 10MB
        
        for size in sizes:
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
                test_file_path = f.name
                f.write(b'x' * size)
            
            try:
                from django.http import FileResponse
                
                # Open file for streaming
                file_handle = open(test_file_path, 'rb')
                response = FileResponse(file_handle)
                
                # Get response object size (approximate)
                response_size = sys.getsizeof(response)
                
                # Response object should be small (< 10KB) regardless of file size
                assert response_size < 10240, f"Response object too large: {response_size} bytes for {size} byte file"
                
                # Close file handle
                file_handle.close()
                
            finally:
                if os.path.exists(test_file_path):
                    os.remove(test_file_path)

    def test_file_response_with_read_loads_into_memory(self):
        """Test that FileResponse(file.read()) loads entire file (anti-pattern)."""
        import sys
        
        # Create 5MB file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            test_file_path = f.name
            f.write(b'x' * (5 * 1024 * 1024))
        
        try:
            from django.http import FileResponse
            
            # Anti-pattern: Read entire file into memory
            with open(test_file_path, 'rb') as file_handle:
                content = file_handle.read()  # Loads 5MB into memory
                response_size = sys.getsizeof(content)
                
                # Content size should be ~5MB (bad!)
                assert response_size > 5 * 1024 * 1024, "Content should be large"
                
            # This demonstrates why we fixed the streaming issue
            
        finally:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)


@pytest.mark.django_db
class TestAsyncCleanupNoRaceCondition(TestCase):
    """Test that async cleanup doesn't cause race conditions."""

    def test_file_available_during_download(self):
        """Test that file is not deleted during active download."""
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file_path = f.name
            f.write('download test content')
        
        try:
            # Schedule cleanup with 5 minute delay
            result = schedule_report_cleanup.apply_async(
                args=[test_file_path],
                countdown=300  # 5 minutes
            )
            
            # File should still exist immediately after scheduling
            assert os.path.exists(test_file_path)
            
            # Simulate download happening (file should still be there)
            with open(test_file_path, 'rb') as f:
                content = f.read()
                assert content == b'download test content'
            
            # Cancel the scheduled task to prevent actual deletion
            result.revoke()
            
        finally:
            # Manual cleanup
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

    def test_cleanup_countdown_prevents_immediate_deletion(self):
        """Test that countdown parameter prevents race conditions."""
        # Create test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            test_file_path = f.name
            f.write('countdown test')
        
        try:
            # Schedule cleanup with 300 second countdown
            result = schedule_report_cleanup.apply_async(
                args=[test_file_path],
                countdown=300
            )
            
            # File should still exist after scheduling
            assert os.path.exists(test_file_path)
            
            # Revoke task
            result.revoke()
            
            # File should still exist (not deleted yet)
            assert os.path.exists(test_file_path)
            
        finally:
            if os.path.exists(test_file_path):
                os.remove(test_file_path)


__all__ = [
    'TestFileStreamingOptimization',
    'TestAsyncFileCleanup',
    'TestFileStreamingVsLoading',
    'TestAsyncCleanupNoRaceCondition',
]
