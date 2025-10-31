"""
Tests for the v1 file upload REST endpoints.

Verifies secure file handling, metadata caching, and download access control.
"""

import json
import os
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import Client, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage')
class FileUploadViewTests(TestCase):
    """Integration tests for file upload and download views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='uploadtester',
            peoplecode='UP001',
            peoplename='Upload Tester',
            email='upload@test.example',
            password='secure-pass-123'
        )
        self.client.force_login(self.user)
        self.temp_media_root = tempfile.mkdtemp(prefix='upload-tests-')
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_root)
        self.media_override.enable()
        cache.clear()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media_root, ignore_errors=True)
        cache.clear()

    @patch('apps.api.v1.file_views.AdvancedFileValidationService.validate_file', return_value={'is_valid': True})
    def test_secure_file_upload_persists_metadata(self, mock_validation):
        """Uploading a PDF stores relative metadata and returns secure response payload."""
        upload_path = reverse('api_v1:files:upload')
        metadata = json.dumps({'folder_type': 'reports'})
        file_content = b'%PDF-1.4 sample content'
        uploaded_file = SimpleUploadedFile(
            'audit-report.pdf',
            file_content,
            content_type='application/pdf'
        )

        response = self.client.post(
            upload_path,
            data={'file': uploaded_file, 'metadata': metadata}
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        file_id = payload['file_id']

        cached_metadata = cache.get(f'file_metadata:{file_id}')
        self.assertIsNotNone(cached_metadata)
        self.assertFalse(cached_metadata['path'].startswith('/'), "Stored path should be relative to MEDIA_ROOT")
        self.assertTrue(default_storage.exists(cached_metadata['path']))
        self.assertEqual(payload['checksum'], f"sha256:{cached_metadata['checksum']}")
        self.assertEqual(payload['url'], cached_metadata['url'])
        self.assertEqual(payload['mime_type'], 'application/pdf')
        self.assertEqual(payload['size'], len(file_content))
        self.assertIn('uploaded_at', payload)
        mock_validation.assert_called_once()

        # Metadata endpoint reflects cached details
        metadata_response = self.client.get(
            reverse('api_v1:files:metadata', args=[file_id])
        )
        self.assertEqual(metadata_response.status_code, 200)
        metadata_payload = metadata_response.json()
        self.assertEqual(metadata_payload['checksum'], payload['checksum'])
        self.assertEqual(metadata_payload['url'], payload['url'])
        self.assertEqual(metadata_payload['original_filename'], 'audit-report.pdf')

        # Download endpoint returns file with sanitized headers
        download_response = self.client.get(
            reverse('api_v1:files:download', args=[file_id])
        )
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(
            download_response['Content-Disposition'],
            'attachment; filename="audit-report.pdf"'
        )
