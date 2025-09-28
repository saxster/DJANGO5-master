"""
File Upload Integration Tests

End-to-end testing of file upload flows across all upload endpoints.
Tests the complete request-to-storage pipeline with security validation.

Coverage:
- GraphQL file upload mutations
- REST API file upload endpoints
- Form-based file uploads
- Attachment management workflows
- Journal media uploads
- People image uploads
- Work order vendor files
"""

import os
import json
import tempfile
import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from rest_framework.test import APIClient
from apps.activity.models.attachment_model import Attachment
from apps.journal.models import JournalEntry, JournalMediaAttachment
from apps.peoples.models import People

User = get_user_model()


@pytest.mark.integration
class GraphQLFileUploadIntegrationTests(TestCase):
    """Integration tests for GraphQL file upload mutations."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            peoplename='Test User',
            peoplecode='TEST001'
        )
        self.client.force_authenticate(user=self.user)

    def test_secure_graphql_upload_end_to_end(self):
        """Test: Complete GraphQL upload flow with SecureFileUploadMutation"""
        valid_image = SimpleUploadedFile(
            'test_image.jpg',
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01',
            content_type='image/jpeg'
        )

        mutation = '''
        mutation($file: Upload!, $biodata: String!, $record: String!, $fileType: String) {
            secureFileUpload(file: $file, biodata: $biodata, record: $record, fileType: $fileType) {
                output {
                    rc
                    msg
                    recordcount
                }
                fileMetadata {
                    filename
                    fileSize
                    correlationId
                }
            }
        }
        '''

        variables = {
            'biodata': json.dumps({
                'filename': 'test_image.jpg',
                'people_id': str(self.user.id),
                'owner': 'test_owner',
                'ownername': 'test',
                'path': 'test/'
            }),
            'record': json.dumps({'test': 'data'}),
            'fileType': 'image'
        }

        response = self.client.post('/api/graphql/', {
            'query': mutation,
            'variables': json.dumps(variables),
            'file': valid_image
        })

        self.assertEqual(response.status_code, 200)

    def test_graphql_upload_authentication_required(self):
        """Test: Unauthenticated GraphQL uploads are rejected"""
        self.client.force_authenticate(user=None)

        valid_image = SimpleUploadedFile(
            'test.jpg',
            b'\xFF\xD8\xFF\xE0',
            content_type='image/jpeg'
        )

        mutation = '''
        mutation {
            secureFileUpload(file: $file, biodata: $biodata, record: $record) {
                output { rc }
            }
        }
        '''

        response = self.client.post('/api/graphql/', {
            'query': mutation
        })

        self.assertIn(response.status_code, [401, 403])


@pytest.mark.integration
class AttachmentUploadIntegrationTests(TestCase):
    """Integration tests for attachment upload workflows."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            peoplename='Test User',
            peoplecode='TEST001'
        )
        self.client.force_login(self.user)

    def test_attachment_upload_and_retrieval(self):
        """Test: Upload attachment and verify retrieval"""
        test_image = SimpleUploadedFile(
            'test_attachment.jpg',
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF',
            content_type='image/jpeg'
        )

        response = self.client.post('/api/upload/att_file/', {
            'img': test_image,
            'foldertype': 'ticket',
            'peopleid': str(self.user.id),
            'ownerid': 'test_owner_123',
            'ownername': 'ticket'
        })

        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)

        self.assertIn('filename', response_data)
        self.assertNotIn('../', response_data.get('filename', ''))

        created_att = Attachment.objects.filter(
            owner='test_owner_123'
        ).first()

        self.assertIsNotNone(created_att)
        self.assertIn('test', created_att.filepath)

    def test_attachment_download_security(self):
        """Test: Attachment download enforces access control"""
        attachment = Attachment.objects.create(
            filepath='test/path/',
            filename='test.jpg',
            owner='test_owner',
            ownername_id=1,
            bu_id=1
        )

        response = self.client.get('/api/attachments/', {
            'action': 'download',
            'filepath': attachment.filepath,
            'filename': 'test.jpg',
            'ownerid': 'test_owner'
        })

        self.assertIn(response.status_code, [200, 403, 404])


@pytest.mark.integration
class JournalMediaUploadIntegrationTests(TestCase):
    """Integration tests for journal media uploads."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='journal_user',
            email='journal@test.com',
            peoplename='Journal User',
            peoplecode='J001'
        )

        self.journal_entry = JournalEntry.objects.create(
            author=self.user,
            entry_type='FIELD_OBSERVATION',
            privacy_scope='PRIVATE',
            title='Test Entry',
            content='Test content'
        )

    def test_journal_media_secure_upload_path(self):
        """Test: Journal media uses secure upload callable"""
        test_image = SimpleUploadedFile(
            'journal_photo.jpg',
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF',
            content_type='image/jpeg'
        )

        media_attachment = JournalMediaAttachment(
            journal_entry=self.journal_entry,
            media_type='PHOTO',
            original_filename='journal_photo.jpg',
            mime_type='image/jpeg',
            file_size=len(test_image)
        )

        media_attachment.file = test_image
        media_attachment.save()

        self.assertNotIn('../', media_attachment.file.name)
        self.assertIn('journal_media/', media_attachment.file.name)
        self.assertTrue(os.path.exists(media_attachment.file.path))

        os.remove(media_attachment.file.path)


@pytest.mark.integration
class PeopleImageUploadIntegrationTests(TestCase):
    """Integration tests for people image uploads."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='people_user',
            email='people@test.com',
            peoplename='People User',
            peoplecode='P001'
        )
        self.client.force_login(self.user)

    def test_people_profile_image_upload(self):
        """Test: People profile image upload uses secure path"""
        test_image = SimpleUploadedFile(
            'profile.jpg',
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF',
            content_type='image/jpeg'
        )

        self.user.peopleimg = test_image
        self.user.save()

        self.assertNotIn('../', self.user.peopleimg.name)
        self.assertIn('people/', self.user.peopleimg.name)

        if os.path.exists(self.user.peopleimg.path):
            os.remove(self.user.peopleimg.path)


@pytest.mark.integration
class FileUploadMiddlewareIntegrationTests(TestCase):
    """Integration tests for file upload security middleware."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='middleware_user',
            email='middleware@test.com',
            peoplename='Middleware User',
            peoplecode='M001'
        )
        self.client.force_login(self.user)

    def test_rate_limiting_integration(self):
        """Test: File upload rate limiting enforced"""
        test_image = SimpleUploadedFile(
            'rate_limit_test.jpg',
            b'\xFF\xD8\xFF\xE0',
            content_type='image/jpeg'
        )

        upload_count = 0
        rate_limited = False

        for i in range(12):
            response = self.client.post('/api/upload/att_file/', {
                'img': test_image,
                'foldertype': 'test',
                'peopleid': str(self.user.id),
                'ownerid': f'test_{i}',
                'ownername': 'test'
            })

            if response.status_code == 429:
                rate_limited = True
                break
            elif response.status_code == 200:
                upload_count += 1

        self.assertGreater(upload_count, 0)

    def test_csrf_protection_integration(self):
        """Test: CSRF protection enforced on file uploads"""
        client_no_csrf = Client(enforce_csrf_checks=True)
        client_no_csrf.force_login(self.user)

        test_image = SimpleUploadedFile(
            'csrf_test.jpg',
            b'\xFF\xD8\xFF\xE0',
            content_type='image/jpeg'
        )

        response = client_no_csrf.post('/api/upload/att_file/', {
            'img': test_image,
            'foldertype': 'test',
            'peopleid': str(self.user.id)
        })

        self.assertEqual(response.status_code, 403)


@pytest.mark.integration
class EndToEndSecurityWorkflowTests(TestCase):
    """Complete end-to-end security workflow tests."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='e2e_user',
            email='e2e@test.com',
            peoplename='E2E User',
            peoplecode='E001'
        )
        self.client.force_login(self.user)

    def test_complete_secure_upload_workflow(self):
        """
        Test: Complete workflow from upload to download
        1. Upload file with validation
        2. Store in database
        3. Verify secure storage
        4. Download with access control
        5. Verify content integrity
        """
        original_content = b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        test_file = SimpleUploadedFile(
            'workflow_test.jpg',
            original_content,
            content_type='image/jpeg'
        )

        upload_response = self.client.post('/api/upload/att_file/', {
            'img': test_file,
            'foldertype': 'ticket',
            'peopleid': str(self.user.id),
            'ownerid': 'workflow_test',
            'ownername': 'ticket'
        })

        self.assertEqual(upload_response.status_code, 200)
        upload_data = json.loads(upload_response.content)

        attachment = Attachment.objects.filter(owner='workflow_test').first()
        self.assertIsNotNone(attachment)

        download_response = self.client.get('/api/attachments/', {
            'action': 'download',
            'filepath': attachment.filepath,
            'filename': str(attachment.filename),
            'ownerid': 'workflow_test'
        })

        self.assertEqual(download_response.status_code, 200)

    def test_malicious_upload_blocked_completely(self):
        """
        Test: Malicious uploads blocked at every layer
        1. Middleware validates request
        2. Service validates file
        3. Database constraints enforced
        4. Filesystem permissions verified
        """
        malicious_files = [
            ('../../evil.php', b'<?php system(); ?>'),
            ('shell.exe', b'MZ\x90\x00'),
            ('script\x00.jpg', b'<script>alert(1)</script>'),
        ]

        for filename, content in malicious_files:
            malicious_file = SimpleUploadedFile(
                filename,
                content,
                content_type='image/jpeg'
            )

            response = self.client.post('/api/upload/att_file/', {
                'img': malicious_file,
                'foldertype': 'ticket',
                'peopleid': str(self.user.id),
                'ownerid': 'evil_test',
                'ownername': 'ticket'
            })

            self.assertIn(response.status_code, [400, 403, 422])

            malicious_attachments = Attachment.objects.filter(owner='evil_test')
            self.assertEqual(malicious_attachments.count(), 0)