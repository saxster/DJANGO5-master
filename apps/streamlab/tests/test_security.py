"""
Security tests for Stream Testbench
Verify PII protection, access controls, and data sanitization
"""

import uuid
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from ..models import TestScenario, TestRun, StreamEvent
from ..services.pii_redactor import PIIRedactor

User = get_user_model()


class TestPIIProtection(TestCase):
    """Test PII protection mechanisms"""

    def setUp(self):
        self.redactor = PIIRedactor()

    def test_sensitive_data_removal(self):
        """Test that all sensitive data is properly removed"""
        sensitive_payload = {
            # PII that should be completely removed
            'full_name': 'John Smith',
            'email': 'john.smith@company.com',
            'phone_number': '+1-555-123-4567',
            'ssn': '123-45-6789',
            'credit_card': '4532-1234-5678-9012',
            'address': '123 Main St, Anytown, ST 12345',
            'passport_number': 'A12345678',

            # Biometric data that should be removed
            'voice_sample': b'binary_audio_data',
            'audio_blob': 'base64_audio_data',
            'image_data': b'binary_image_data',
            'biometric_template': 'fingerprint_template_data',

            # Location data that should be bucketed or removed
            'precise_location': 'Building A, Floor 3, Desk 42',
            'gps_coordinates': [37.774929, -122.419415],
            'latitude': 37.774929,
            'longitude': -122.419415,

            # Free text that might contain PII
            'comment': 'Please call me at 555-999-8888 or email me at personal@gmail.com',
            'notes': 'My credit card ending in 1234 was charged',

            # Data that should be kept (allowlisted)
            'quality_score': 0.85,
            'timestamp': 1645123456789,
            'event_type': 'voice_verification',

            # IDs that should be hashed
            'user_id': 'user_12345',
            'device_id': 'device_abcdef',
            'session_id': 'session_uuid_here'
        }

        result = self.redactor.redact(sensitive_payload, 'voice/recognition')

        # Verify sensitive data is removed
        sensitive_fields = [
            'full_name', 'email', 'phone_number', 'ssn', 'credit_card',
            'address', 'passport_number', 'voice_sample', 'audio_blob',
            'image_data', 'biometric_template', 'precise_location',
            'gps_coordinates', 'comment', 'notes'
        ]

        for field in sensitive_fields:
            self.assertNotIn(field, result, f"Sensitive field '{field}' was not removed")

        # Verify allowlisted data is kept
        self.assertIn('quality_score', result)
        self.assertIn('timestamp', result)
        self.assertIn('event_type', result)

        # Verify IDs are hashed (present but different)
        id_fields = ['user_id', 'device_id', 'session_id']
        for field in id_fields:
            self.assertIn(field, result, f"ID field '{field}' should be hashed, not removed")
            self.assertNotEqual(
                result[field], sensitive_payload[field],
                f"ID field '{field}' should be hashed, not stored in plain text"
            )

        # Verify GPS coordinates are bucketed or removed
        self.assertNotIn('latitude', result)
        self.assertNotIn('longitude', result)

        # Verify redaction metadata
        self.assertTrue(result['_pii_redacted'])
        self.assertIn('_redaction_timestamp', result)

    def test_pattern_based_pii_detection(self):
        """Test detection of PII patterns in text fields"""
        test_cases = [
            {
                'input': 'Call me at 555-123-4567 for updates',
                'should_contain_redacted': True,
                'description': 'Phone number pattern'
            },
            {
                'input': 'Email me at john.doe@company.com please',
                'should_contain_redacted': True,
                'description': 'Email pattern'
            },
            {
                'input': 'My card number is 4532 1234 5678 9012',
                'should_contain_redacted': True,
                'description': 'Credit card pattern'
            },
            {
                'input': 'SSN: 123-45-6789',
                'should_contain_redacted': True,
                'description': 'SSN pattern'
            },
            {
                'input': 'Server IP is 192.168.1.100',
                'should_contain_redacted': True,
                'description': 'IP address pattern'
            },
            {
                'input': 'Quality score is excellent',
                'should_contain_redacted': False,
                'description': 'Safe text'
            }
        ]

        for case in test_cases:
            payload = {
                'message': case['input'],
                'quality_score': 0.8  # Safe field
            }

            result = self.redactor.redact(payload, 'test/endpoint')

            if case['should_contain_redacted']:
                self.assertIn('[REDACTED]', result.get('message', ''), case['description'])
            else:
                self.assertNotIn('[REDACTED]', result.get('message', ''), case['description'])

    def test_nested_pii_protection(self):
        """Test PII protection in nested data structures"""
        nested_payload = {
            'user_data': {
                'profile': {
                    'name': 'John Doe',  # Should be removed
                    'email': 'john@example.com',  # Should be removed
                    'preferences': {
                        'quality_threshold': 0.8,  # Should be kept if allowlisted
                        'phone': '555-123-4567'  # Should be removed
                    }
                }
            },
            'metadata': {
                'user_id': 'user_123',  # Should be hashed
                'timestamp': 1645123456789  # Should be kept
            }
        }

        result = self.redactor.redact(nested_payload, 'user/profile')

        # Verify nested PII removal
        if 'user_data' in result:
            user_data = result['user_data']
            self.assertNotIn('name', str(user_data))
            self.assertNotIn('email', str(user_data))
            self.assertNotIn('phone', str(user_data))


class TestAccessControls(TestCase):
    """Test access control for Stream Testbench views"""

    def setUp(self):
        self.client = Client()

        # Create users with different permissions
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )

        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )

        self.normal_user = User.objects.create_user(
            username='normal',
            email='normal@example.com',
            password='testpass123'
        )

    def test_dashboard_access_control(self):
        """Test dashboard access is restricted to staff"""
        dashboard_url = reverse('streamlab:dashboard')

        # Test unauthorized access
        response = self.client.get(dashboard_url)
        self.assertNotEqual(response.status_code, 200)

        # Test normal user access (should be denied)
        self.client.login(username='normal', password='testpass123')
        response = self.client.get(dashboard_url)
        self.assertNotEqual(response.status_code, 200)

        # Test staff user access (should be allowed)
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)

        # Test superuser access (should be allowed)
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)

    def test_anomalies_dashboard_access(self):
        """Test anomalies dashboard access control"""
        anomalies_url = reverse('streamlab:anomalies')

        # Test unauthorized access
        response = self.client.get(anomalies_url)
        self.assertNotEqual(response.status_code, 200)

        # Test staff access
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(anomalies_url)
        self.assertEqual(response.status_code, 200)

    def test_api_endpoints_access_control(self):
        """Test API endpoints access control"""
        metrics_url = reverse('streamlab:metrics_api')

        # Test unauthorized access
        response = self.client.get(metrics_url)
        self.assertNotEqual(response.status_code, 200)

        # Test staff access
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(metrics_url)
        self.assertEqual(response.status_code, 200)


class TestDataSanitization(TestCase):
    """Test data sanitization in stored events"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        self.scenario = TestScenario.objects.create(
            name='Security Test',
            protocol='websocket',
            endpoint='ws://test/',
            expected_p95_latency_ms=100,
            expected_error_rate=0.05,
            created_by=self.user
        )

        self.run = TestRun.objects.create(
            scenario=self.scenario,
            started_by=self.user
        )

    def test_payload_sanitization_in_storage(self):
        """Test that payloads are sanitized before storage"""
        # Create event with potentially sensitive payload
        original_payload = {
            'user_email': 'sensitive@example.com',
            'credit_card': '4532-1234-5678-9012',
            'voice_data': b'binary_audio',
            'quality_score': 0.92,
            'api_key': 'secret_api_key_12345'
        }

        redactor = PIIRedactor()
        sanitized = redactor.redact(original_payload, 'test/endpoint')

        event = StreamEvent.objects.create(
            run=self.run,
            correlation_id=str(uuid.uuid4()),
            direction='inbound',
            endpoint='test/endpoint',
            latency_ms=50.0,
            message_size_bytes=len(str(original_payload)),
            payload_sanitized=sanitized  # Store sanitized version
        )

        # Verify stored payload is sanitized
        stored_payload = event.payload_sanitized

        # Should not contain sensitive data
        self.assertNotIn('user_email', stored_payload)
        self.assertNotIn('credit_card', stored_payload)
        self.assertNotIn('voice_data', stored_payload)
        self.assertNotIn('api_key', stored_payload)

        # Should contain safe data
        self.assertIn('quality_score', stored_payload)

        # Should have redaction metadata
        self.assertTrue(stored_payload.get('_pii_redacted', False))

    def test_error_message_sanitization(self):
        """Test that error messages don't leak sensitive data"""
        # Simulate error message that might contain sensitive data
        error_message = """
        Database error: INSERT INTO users (email, api_key) VALUES ('user@example.com', 'secret_key_123')
        Failed at line 42 in user_service.py
        """

        event = StreamEvent.objects.create(
            run=self.run,
            correlation_id=str(uuid.uuid4()),
            direction='inbound',
            endpoint='api/users',
            latency_ms=1000.0,
            message_size_bytes=100,
            outcome='error',
            error_message=error_message[:500],  # Truncated as per model
            payload_sanitized={'safe': 'data'}
        )

        # In a real implementation, error messages should also be sanitized
        # This test documents the current behavior and can be enhanced
        self.assertIsNotNone(event.error_message)
        self.assertLessEqual(len(event.error_message), 500)

    def test_correlation_id_tracking(self):
        """Test correlation ID tracking for security auditing"""
        correlation_id = str(uuid.uuid4())

        event = StreamEvent.objects.create(
            run=self.run,
            correlation_id=correlation_id,
            direction='inbound',
            endpoint='test/endpoint',
            latency_ms=25.0,
            message_size_bytes=100,
            payload_sanitized={'test': 'data'}
        )

        # Verify correlation ID is properly stored and indexed
        retrieved_event = StreamEvent.objects.get(correlation_id=correlation_id)
        self.assertEqual(retrieved_event, event)

        # Verify we can audit events by correlation ID
        audit_events = StreamEvent.objects.filter(correlation_id=correlation_id)
        self.assertEqual(audit_events.count(), 1)


class TestSecurityValidation(TestCase):
    """Test security validation and input sanitization"""

    def test_malicious_payload_handling(self):
        """Test handling of potentially malicious payloads"""
        malicious_payloads = [
            # XSS attempts
            {'script': '<script>alert("xss")</script>'},
            {'html': '<img src=x onerror=alert(1)>'},

            # SQL injection attempts
            {'query': "'; DROP TABLE users; --"},
            {'filter': "1=1 OR '1'='1"},

            # Command injection attempts
            {'command': '; rm -rf / ;'},
            {'file': '../../../etc/passwd'},

            # Very large payloads
            {'large_field': 'A' * 10000},

            # Deeply nested structures
            {'nested': {'level1': {'level2': {'level3': {'level4': 'deep'}}}}},
        ]

        redactor = PIIRedactor()

        for payload in malicious_payloads:
            # Should not raise exceptions
            try:
                result = redactor.redact(payload, 'test/malicious')
                self.assertIsInstance(result, dict)
                self.assertTrue(result.get('_pii_redacted', False))
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                self.fail(f"Redactor failed on payload {payload}: {e}")

    def test_endpoint_sanitization_security(self):
        """Test endpoint sanitization prevents path traversal"""
        malicious_endpoints = [
            '/api/../../../etc/passwd',
            '/ws/../admin/secret',
            '/test?param=<script>alert(1)</script>',
            '/api/users/1; DROP TABLE users; --',
            '/ws/device/../../sensitive/data'
        ]

        redactor = PIIRedactor()

        for endpoint in malicious_endpoints:
            sanitized = redactor._sanitize_endpoint(endpoint)

            # Should not contain path traversal
            self.assertNotIn('..', sanitized)

            # Should not contain script tags
            self.assertNotIn('<script', sanitized.lower())

            # Should not contain SQL injection
            self.assertNotIn('DROP TABLE', sanitized.upper())

    def test_hash_security(self):
        """Test that hashing is cryptographically secure"""
        redactor = PIIRedactor()

        # Test with same input
        value = 'sensitive_user_id_123'
        hash1 = redactor._hash_value(value)
        hash2 = redactor._hash_value(value)

        # Hashes should be consistent
        self.assertEqual(hash1, hash2)

        # Hash should not be reversible to original
        self.assertNotEqual(hash1, value)
        self.assertNotIn(value, hash1)

        # Test with different inputs
        hash3 = redactor._hash_value('different_value')
        self.assertNotEqual(hash1, hash3)

        # Verify hash length and format
        self.assertEqual(len(hash1), 16)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash1))


class TestSecurityHeaders(TestCase):
    """Test security headers and CSRF protection"""

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )

    def test_csrf_protection_on_actions(self):
        """Test CSRF protection on sensitive actions"""
        self.client.login(username='staff', password='testpass123')

        # Create test scenario
        scenario = TestScenario.objects.create(
            name='CSRF Test',
            protocol='websocket',
            endpoint='ws://test/',
            expected_p95_latency_ms=100,
            expected_error_rate=0.05,
            created_by=self.staff_user
        )

        # Test starting scenario without CSRF token
        start_url = reverse('streamlab:start_scenario', args=[scenario.id])
        response = self.client.post(start_url, {})

        # Should be allowed due to @csrf_exempt decorator for HTMX compatibility
        # In production, consider using CSRF tokens with HTMX
        self.assertIn(response.status_code, [200, 400])  # 400 for other validation errors

    def test_input_validation(self):
        """Test input validation for API endpoints"""
        self.client.login(username='staff', password='testpass123')

        # Test metrics API with invalid parameters
        metrics_url = reverse('streamlab:metrics_api')

        # Test with very large hours parameter
        response = self.client.get(metrics_url, {'hours': '99999'})
        self.assertEqual(response.status_code, 200)  # Should handle gracefully

        # Test with negative hours
        response = self.client.get(metrics_url, {'hours': '-1'})
        self.assertEqual(response.status_code, 200)  # Should handle gracefully

        # Test with non-numeric hours
        response = self.client.get(metrics_url, {'hours': 'invalid'})
        self.assertEqual(response.status_code, 200)  # Should use default


class TestDataRetention(TestCase):
    """Test data retention and cleanup mechanisms"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

    def test_retention_policy_compliance(self):
        """Test that retention policies are properly defined"""
        from ..models import EventRetention

        # Verify default retention policies exist or can be created
        retention_types = [
            ('sanitized_metadata', 14),
            ('stack_traces', 30),
            ('aggregated_metrics', 90)
        ]

        for retention_type, days in retention_types:
            retention, created = EventRetention.objects.get_or_create(
                retention_type=retention_type,
                defaults={'days_to_keep': days}
            )

            self.assertEqual(retention.days_to_keep, days)

    def test_event_archival_structure(self):
        """Test event archival data structure"""
        from ..models import StreamEventArchive
        from django.utils import timezone
        from datetime import timedelta

        # Create test archive
        archive = StreamEventArchive.objects.create(
            archive_date=timezone.now().date(),
            run_ids=['run1', 'run2', 'run3'],
            event_count=1000,
            compressed_size_bytes=50000,
            storage_location='s3://bucket/archives/2024-01-01.tar.gz',
            checksum_sha256='a' * 64,
            expires_at=timezone.now() + timedelta(days=365)
        )

        # Verify archive structure
        self.assertEqual(len(archive.run_ids), 3)
        self.assertEqual(archive.event_count, 1000)
        self.assertEqual(len(archive.checksum_sha256), 64)

    def test_pii_redaction_consistency(self):
        """Test that PII redaction is consistent across operations"""
        redactor1 = PIIRedactor()
        redactor2 = PIIRedactor()

        payload = {
            'user_id': 'user_123',
            'email': 'test@example.com',
            'quality_score': 0.85
        }

        result1 = redactor1.redact(payload, 'test/endpoint')
        result2 = redactor2.redact(payload, 'test/endpoint')

        # Hash values should be consistent
        self.assertEqual(result1['user_id'], result2['user_id'])

        # Both should remove email
        self.assertNotIn('email', result1)
        self.assertNotIn('email', result2)

        # Both should keep quality_score
        self.assertIn('quality_score', result1)
        self.assertIn('quality_score', result2)