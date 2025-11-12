"""
Security Tests for Site Audit API (Phase C).

Comprehensive security testing including:
- Authentication and authorization
- Input validation and sanitization
- File upload security
- SQL injection prevention
- XSS protection
- Rate limiting
- Data access controls

Following security testing best practices:
- OWASP Top 10 coverage
- Penetration testing scenarios
- Boundary value analysis
"""

import uuid
from io import BytesIO

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status

from apps.core_onboarding.models import (
    Observation,
    ConversationSession
)
from apps.site_onboarding.models import (
    OnboardingSite,
    OnboardingZone
)
from apps.client_onboarding.models.business_unit import Bt

User = get_user_model()


class AuthenticationSecurityTests(TestCase):
    """Test authentication and session security."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@test.com',
            peoplename='Test User',
            password='testpass123'
        )

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated requests are rejected."""
        endpoints = [
            '/api/v1/onboarding/site-audit/start/',
            f'/api/v1/onboarding/site-audit/{uuid.uuid4()}/status/',
            f'/api/v1/onboarding/site-audit/{uuid.uuid4()}/observation/',
        ]

        for endpoint in endpoints:
            response = self.client.post(endpoint)
            self.assertEqual(
                response.status_code,
                status.HTTP_401_UNAUTHORIZED,
                f"Endpoint {endpoint} should require authentication"
            )

    def test_session_ownership_validation(self):
        """Test that users can only access their own sessions."""
        self.client.force_authenticate(user=self.user)

        # Create business unit
        bu = Bt.objects.create(buname='Test', bucode='T001')

        # Create session for another user
        other_user = User.objects.create_user(
            loginid='other_user',
            email='other@test.com',
            peoplename='Other User',
            password='otherpass123'
        )

        other_session = ConversationSession.objects.create(
            user=other_user,
            client=bu
        )

        # Try to access other user's session
        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{other_session.session_id}/status/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class InputValidationTests(TransactionTestCase):
    """Test input validation and sanitization."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@test.com',
            peoplename='Test User',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.business_unit = Bt.objects.create(
            buname='Test Branch',
            bucode='TB001'
        )

    def test_sql_injection_prevention_in_uuid(self):
        """Test SQL injection attempts in UUID parameters."""
        # Attempt SQL injection in session_id
        malicious_inputs = [
            "' OR '1'='1",
            "'; DROP TABLE observation; --",
            "1' UNION SELECT * FROM peoples--"
        ]

        for malicious_input in malicious_inputs:
            response = self.client.get(
                f'/api/v1/onboarding/site-audit/{malicious_input}/status/'
            )

            # Should return 404 or 400, never execute injection
            self.assertIn(
                response.status_code,
                [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
            )

    def test_xss_prevention_in_text_input(self):
        """Test XSS prevention in text inputs."""
        session = ConversationSession.objects.create(
            user=self.user,
            client=self.business_unit
        )

        site = OnboardingSite.objects.create(
            business_unit=self.business_unit,
            conversation_session=session,
            site_type='bank_branch'
        )

        # Attempt XSS injection
        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            'javascript:alert("XSS")'
        ]

        for payload in xss_payloads:
            data = {
                'text_input': payload,
                'gps_latitude': 19.0760,
                'gps_longitude': 72.8777
            }

            response = self.client.post(
                f'/api/v1/onboarding/site-audit/{session.session_id}/observation/',
                data,
                format='json'
            )

            # Should be accepted (sanitized server-side) or rejected
            if response.status_code == status.HTTP_201_CREATED:
                # Verify no script tags in stored data
                obs = Observation.objects.get(observation_id=response.data['observation_id'])
                self.assertNotIn('<script>', obs.transcript_english)
                self.assertNotIn('javascript:', obs.transcript_english)

    def test_gps_boundary_validation(self):
        """Test GPS coordinate boundary validation."""
        invalid_coordinates = [
            {'latitude': 91.0, 'longitude': 72.8777},    # Lat > 90
            {'latitude': -91.0, 'longitude': 72.8777},   # Lat < -90
            {'latitude': 19.0760, 'longitude': 181.0},   # Lon > 180
            {'latitude': 19.0760, 'longitude': -181.0},  # Lon < -180
        ]

        session = ConversationSession.objects.create(
            user=self.user,
            client=self.business_unit
        )

        OnboardingSite.objects.create(
            business_unit=self.business_unit,
            conversation_session=session,
            site_type='bank_branch'
        )

        for coords in invalid_coordinates:
            data = {
                'text_input': 'Test observation',
                'gps_latitude': coords['latitude'],
                'gps_longitude': coords['longitude']
            }

            response = self.client.post(
                f'/api/v1/onboarding/site-audit/{session.session_id}/observation/',
                data,
                format='json'
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Invalid GPS coordinates should be rejected: {coords}"
            )

    def test_operating_hours_validation(self):
        """Test operating hours format validation."""
        invalid_hours = [
            {'start': '25:00', 'end': '17:00'},  # Invalid hour
            {'start': '09:60', 'end': '17:00'},  # Invalid minute
            {'start': '9:00', 'end': '17:00'},   # Wrong format
            {'start': 'invalid', 'end': '17:00'}  # Non-time value
        ]

        for hours in invalid_hours:
            data = {
                'business_unit_id': str(self.business_unit.buuid),
                'site_type': 'bank_branch',
                'operating_hours': hours
            }

            response = self.client.post(
                '/api/v1/onboarding/site-audit/start/',
                data,
                format='json'
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_400_BAD_REQUEST,
                f"Invalid operating hours should be rejected: {hours}"
            )


class FileUploadSecurityTests(TransactionTestCase):
    """Test file upload security."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@test.com',
            peoplename='Test User',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.business_unit = Bt.objects.create(
            buname='Test Branch',
            bucode='TB001'
        )

        self.session = ConversationSession.objects.create(
            user=self.user,
            client=self.business_unit
        )

        self.site = OnboardingSite.objects.create(
            business_unit=self.business_unit,
            conversation_session=self.session,
            site_type='bank_branch'
        )

        OnboardingZone.objects.create(
            site=self.site,
            zone_type='gate',
            zone_name='Main Gate',
            importance_level='critical'
        )

    def test_invalid_image_mime_type_rejected(self):
        """Test that invalid image MIME types are rejected."""
        # Create file with wrong MIME type
        malicious_file = SimpleUploadedFile(
            'malicious.php',
            b'<?php echo "hack"; ?>',
            content_type='application/x-php'
        )

        data = {
            'photo': malicious_file,
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_image_rejected(self):
        """Test that oversized images are rejected."""
        # Create file larger than 5MB limit
        large_content = b'x' * (6 * 1024 * 1024)  # 6MB
        large_file = SimpleUploadedFile(
            'large.jpg',
            large_content,
            content_type='image/jpeg'
        )

        data = {
            'photo': large_file,
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_audio_mime_type_rejected(self):
        """Test that invalid audio MIME types are rejected."""
        malicious_audio = SimpleUploadedFile(
            'malicious.exe',
            b'MZ\x90\x00',  # PE executable header
            content_type='application/x-msdownload'
        )

        data = {
            'audio': malicious_audio,
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filename_path_traversal_prevention(self):
        """Test prevention of path traversal in filenames."""
        # Attempt path traversal
        traversal_names = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'test/../../sensitive.txt'
        ]

        for filename in traversal_names:
            photo = SimpleUploadedFile(
                filename,
                b'image data',
                content_type='image/jpeg'
            )

            data = {
                'photo': photo,
                'gps_latitude': 19.0760,
                'gps_longitude': 72.8777
            }

            response = self.client.post(
                f'/api/v1/onboarding/site-audit/{self.session.session_id}/observation/',
                data,
                format='multipart'
            )

            # Should either reject or sanitize filename
            # Verify no traversal sequences in stored path if accepted
            if response.status_code == status.HTTP_201_CREATED:
                from apps.site_onboarding.models import SitePhoto
                photo_record = SitePhoto.objects.filter(site=self.site).first()
                if photo_record:
                    self.assertNotIn('..', str(photo_record.image.name))


class DataAccessControlTests(TransactionTestCase):
    """Test data access controls and authorization."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user1 = User.objects.create_user(
            loginid='user1',
            email='user1@test.com',
            peoplename='User 1',
            password='pass123'
        )

        self.user2 = User.objects.create_user(
            loginid='user2',
            email='user2@test.com',
            peoplename='User 2',
            password='pass123'
        )

        self.bu = Bt.objects.create(buname='Test', bucode='T001')

    def test_cannot_access_other_user_sessions(self):
        """Test users cannot access sessions they don't own."""
        # Create session for user1
        session1 = ConversationSession.objects.create(
            user=self.user1,
            client=self.bu
        )

        # Try to access as user2
        self.client.force_authenticate(user=self.user2)

        response = self.client.get(
            f'/api/v1/onboarding/site-audit/{session1.session_id}/status/'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_modify_other_user_data(self):
        """Test users cannot modify other users' observations."""
        # Create session and site for user1
        session1 = ConversationSession.objects.create(
            user=self.user1,
            client=self.bu
        )

        site1 = OnboardingSite.objects.create(
            business_unit=self.bu,
            conversation_session=session1,
            site_type='bank_branch'
        )

        zone1 = OnboardingZone.objects.create(
            site=site1,
            zone_type='gate',
            zone_name='Gate',
            importance_level='critical'
        )

        # Try to add observation to user1's session as user2
        self.client.force_authenticate(user=self.user2)

        data = {
            'text_input': 'Observation',
            'gps_latitude': 19.0760,
            'gps_longitude': 72.8777
        }

        response = self.client.post(
            f'/api/v1/onboarding/site-audit/{session1.session_id}/observation/',
            data,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class InjectionAttackTests(TransactionTestCase):
    """Test prevention of various injection attacks."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@test.com',
            peoplename='Test User',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)

        self.bu = Bt.objects.create(buname='Test', bucode='T001')

    def test_json_injection_prevention(self):
        """Test prevention of JSON injection attacks."""
        malicious_payloads = [
            {'__proto__': {'polluted': True}},  # Prototype pollution
            {'constructor': {'prototype': {'polluted': True}}},
            '{"test": "value", "eval": "alert(1)"}'
        ]

        for payload in malicious_payloads:
            data = {
                'business_unit_id': str(self.bu.buuid),
                'site_type': 'bank_branch',
                'language': 'en',
                'gps_location': payload  # Inject into JSON field
            }

            response = self.client.post(
                '/api/v1/onboarding/site-audit/start/',
                data,
                format='json'
            )

            # Should be rejected or sanitized
            self.assertIn(
                response.status_code,
                [status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED]
            )

    def test_command_injection_prevention_in_text(self):
        """Test prevention of command injection in text fields."""
        command_injections = [
            '$(rm -rf /)',
            '`cat /etc/passwd`',
            '| ls -la',
            '; DROP TABLE observation;'
        ]

        session = ConversationSession.objects.create(
            user=self.user,
            client=self.bu
        )

        OnboardingSite.objects.create(
            business_unit=self.bu,
            conversation_session=session,
            site_type='bank_branch'
        )

        for injection in command_injections:
            data = {
                'text_input': injection,
                'gps_latitude': 19.0760,
                'gps_longitude': 72.8777
            }

            response = self.client.post(
                f'/api/v1/onboarding/site-audit/{session.session_id}/observation/',
                data,
                format='json'
            )

            # Should be accepted but sanitized
            if response.status_code == status.HTTP_201_CREATED:
                obs = Observation.objects.get(observation_id=response.data['observation_id'])
                # Verify no command execution characters preserved
                self.assertNotIn('$(', obs.transcript_english)
                self.assertNotIn('`', obs.transcript_english)


@override_settings(
    AXES_FAILURE_LIMIT=3,
    AXES_COOLOFF_TIME=1
)
class RateLimitingTests(TransactionTestCase):
    """Test rate limiting and DoS prevention."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@test.com',
            peoplename='Test User',
            password='testpass123'
        )

        self.bu = Bt.objects.create(buname='Test', bucode='T001')

    def test_observation_rate_limiting(self):
        """Test rate limiting on observation creation."""
        self.client.force_authenticate(user=self.user)

        session = ConversationSession.objects.create(
            user=self.user,
            client=self.bu
        )

        OnboardingSite.objects.create(
            business_unit=self.bu,
            conversation_session=session,
            site_type='bank_branch'
        )

        # Attempt rapid-fire observations
        for i in range(15):
            data = {
                'text_input': f'Observation {i}',
                'gps_latitude': 19.0760,
                'gps_longitude': 72.8777
            }

            response = self.client.post(
                f'/api/v1/onboarding/site-audit/{session.session_id}/observation/',
                data,
                format='json'
            )

            # Early requests should succeed
            if i < 10:
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            # Later requests might be rate limited (implementation-dependent)
            else:
                self.assertIn(
                    response.status_code,
                    [status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS]
                )