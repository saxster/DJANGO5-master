"""
Security Tests for Report File Download

Tests secure file serving with SecureFileDownloadService integration.
Validates protection against path traversal, IDOR, and other file access vulnerabilities.

Created: Nov 6, 2025
"""
import os
import tempfile
from pathlib import Path
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import Http404
from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.activity.models import Attachment

User = get_user_model()


@override_settings(MEDIA_ROOT='/tmp/test_media')
class SecureReportDownloadTests(TestCase):
    """Test suite for secure report file downloads"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        
        # Create test users
        self.staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
        
        self.regular_user = User.objects.create_user(
            username='regular_user',
            email='user@test.com',
            password='testpass123',
            is_staff=False
        )
        
        # Create test media directory
        self.media_root = Path('/tmp/test_media')
        self.reports_dir = self.media_root / 'reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test file
        self.test_file = self.reports_dir / 'test_report.pdf'
        with open(self.test_file, 'wb') as f:
            f.write(b'PDF test content')
    
    def tearDown(self):
        """Clean up test files"""
        import shutil
        if self.media_root.exists():
            shutil.rmtree(self.media_root)
    
    def test_path_traversal_prevention(self):
        """Test that path traversal attacks are blocked"""
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'reports/../../../etc/passwd',
            'reports/../../sensitive_data.txt',
        ]
        
        for malicious_path in malicious_paths:
            with self.assertRaises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=malicious_path,
                    filename='report.pdf',
                    user=self.staff_user,
                    owner_id=None
                )
    
    def test_null_byte_injection_prevention(self):
        """Test that null byte injection is blocked"""
        malicious_paths = [
            'report.pdf\x00.txt',
            'reports/file\x00../../../etc/passwd',
        ]
        
        for malicious_path in malicious_paths:
            with self.assertRaises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=malicious_path,
                    filename='report.pdf',
                    user=self.staff_user,
                    owner_id=None
                )
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot download files"""
        from django.contrib.auth.models import AnonymousUser
        
        with self.assertRaises(PermissionDenied):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='reports/test_report.pdf',
                filename='test_report.pdf',
                user=AnonymousUser(),
                owner_id=None
            )
    
    def test_non_staff_direct_access_denied(self):
        """Test that non-staff users cannot access files directly"""
        with self.assertRaises(PermissionDenied):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='reports/test_report.pdf',
                filename='test_report.pdf',
                user=self.regular_user,
                owner_id=None  # Direct access requires staff privileges
            )
    
    def test_staff_user_can_download_reports(self):
        """Test that staff users can download report files"""
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath='reports/test_report.pdf',
            filename='test_report.pdf',
            user=self.staff_user,
            owner_id=None
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('test_report.pdf', response['Content-Disposition'])
    
    def test_file_not_found_returns_404(self):
        """Test that missing files return 404"""
        with self.assertRaises(Http404):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='reports/nonexistent.pdf',
                filename='nonexistent.pdf',
                user=self.staff_user,
                owner_id=None
            )
    
    def test_directory_traversal_to_allowed_dir(self):
        """Test that files outside MEDIA_ROOT are blocked even with valid paths"""
        # Try to access /etc/passwd using absolute path
        with self.assertRaises(SuspiciousFileOperation):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='/etc/passwd',
                filename='passwd',
                user=self.staff_user,
                owner_id=None
            )
    
    def test_symlink_attack_prevention(self):
        """Test that symlinks outside MEDIA_ROOT are blocked"""
        # Create symlink to /etc/passwd
        symlink_path = self.reports_dir / 'malicious_link'
        try:
            os.symlink('/etc/passwd', symlink_path)
            
            with self.assertRaises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='reports/malicious_link',
                    filename='link',
                    user=self.staff_user,
                    owner_id=None
                )
        except OSError:
            # Skip test if symlinks not supported (Windows)
            self.skipTest("Symlinks not supported on this platform")
    
    def test_disallowed_directory_access_blocked(self):
        """Test that access to non-whitelisted directories is blocked"""
        # Create file in non-allowed directory
        blocked_dir = self.media_root / 'private'
        blocked_dir.mkdir(parents=True, exist_ok=True)
        blocked_file = blocked_dir / 'secret.pdf'
        with open(blocked_file, 'wb') as f:
            f.write(b'Secret content')
        
        with self.assertRaises(SuspiciousFileOperation):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='private/secret.pdf',
                filename='secret.pdf',
                user=self.staff_user,
                owner_id=None
            )
    
    def test_filename_sanitization(self):
        """Test that filenames with special characters are handled safely"""
        # Valid filename should work
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath='reports/test_report.pdf',
            filename='My Report (Final).pdf',
            user=self.staff_user,
            owner_id=None
        )
        
        self.assertEqual(response.status_code, 200)
        # Filename should be sanitized in Content-Disposition
        self.assertIn('attachment', response['Content-Disposition'])
    
    def test_audit_logging_on_access(self):
        """Test that file access is logged for audit trail"""
        import logging
        from unittest.mock import patch
        
        with patch('apps.core.services.secure_file_download_service.logger') as mock_logger:
            SecureFileDownloadService.validate_and_serve_file(
                filepath='reports/test_report.pdf',
                filename='test_report.pdf',
                user=self.staff_user,
                owner_id=None
            )
            
            # Verify audit logging occurred
            self.assertTrue(mock_logger.info.called)
            call_args = mock_logger.info.call_args_list
            
            # Check for key audit events
            logged_messages = [call[0][0] for call in call_args]
            self.assertIn('File download request received', logged_messages)
            self.assertIn('File download successful', logged_messages)
    
    def test_audit_logging_on_security_violation(self):
        """Test that security violations are logged"""
        import logging
        from unittest.mock import patch
        
        with patch('apps.core.services.secure_file_download_service.logger') as mock_logger:
            try:
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='../../../etc/passwd',
                    filename='passwd',
                    user=self.staff_user,
                    owner_id=None
                )
            except SuspiciousFileOperation:
                pass
            
            # Verify security event was logged
            self.assertTrue(mock_logger.error.called)
            
            # Check log message indicates security violation
            call_args = mock_logger.error.call_args_list
            logged_messages = [call[0][0] for call in call_args]
            
            security_logged = any(
                'traversal' in msg.lower() or 'attack' in msg.lower()
                for msg in logged_messages
            )
            self.assertTrue(security_logged)


class ReportViewSecurityTests(TestCase):
    """Integration tests for report view security"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='test123',
            is_staff=True
        )
        
        # Create temp directory for reports
        self.temp_dir = tempfile.mkdtemp()
        self.test_report = os.path.join(self.temp_dir, 'test_report.pdf')
        with open(self.test_report, 'wb') as f:
            f.write(b'Test report content')
    
    def tearDown(self):
        """Clean up"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_return_status_of_report_uses_secure_service(self):
        """Test that return_status_of_report uses SecureFileDownloadService"""
        from apps.reports.views.export_views import return_status_of_report
        from unittest.mock import patch, MagicMock
        from celery.result import AsyncResult
        
        request = self.factory.get('/reports/status/', {'task_id': 'test-task-123'})
        request.user = self.staff_user
        
        # Mock AsyncResult
        with patch('apps.reports.views.export_views.AsyncResult') as mock_result:
            mock_task = MagicMock()
            mock_task.status = 'SUCCESS'
            mock_task.get.return_value = {
                'status': 200,
                'filepath': 'reports/test.pdf',
                'filename': 'test.pdf'
            }
            mock_result.return_value = mock_task
            
            # Mock SecureFileDownloadService
            with patch('apps.reports.views.export_views.SecureFileDownloadService') as mock_service:
                from django.http import FileResponse
                mock_response = FileResponse(open(self.test_report, 'rb'))
                mock_service.validate_and_serve_file.return_value = mock_response
                
                # Call the view
                response = return_status_of_report(request)
                
                # Verify SecureFileDownloadService was called
                mock_service.validate_and_serve_file.assert_called_once()
                call_kwargs = mock_service.validate_and_serve_file.call_args[1]
                
                self.assertEqual(call_kwargs['filepath'], 'reports/test.pdf')
                self.assertEqual(call_kwargs['filename'], 'test.pdf')
                self.assertEqual(call_kwargs['user'], self.staff_user)
                self.assertIsNone(call_kwargs['owner_id'])
