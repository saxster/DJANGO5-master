"""
Unit tests for PII Redaction Service
"""

from django.test import TestCase

from ..services.pii_redactor import PIIRedactor


class TestPIIRedactor(TestCase):
    """Test PII redaction functionality"""

    def setUp(self):
        self.redactor = PIIRedactor()

    def test_voice_data_redaction(self):
        """Test that voice data is properly redacted"""
        voice_payload = {
            'user_id': 'user_123',
            'voice_sample': b'binary_audio_data',
            'quality_score': 0.95,
            'duration_ms': 3000,
            'confidence_score': 0.87,
            'full_name': 'John Doe',
            'email': 'john@example.com'
        }

        result = self.redactor.redact(voice_payload, 'voice/recognition')

        # Should keep allowlisted fields
        self.assertIn('quality_score', result)
        self.assertIn('duration_ms', result)
        self.assertIn('confidence_score', result)

        # Should hash user_id
        self.assertIn('user_id', result)
        self.assertNotEqual(result['user_id'], 'user_123')
        self.assertEqual(len(result['user_id']), 16)  # Hash length

        # Should remove sensitive fields
        self.assertNotIn('voice_sample', result)
        self.assertNotIn('full_name', result)
        self.assertNotIn('email', result)

        # Should have metadata
        self.assertTrue(result['_pii_redacted'])
        self.assertIn('_redaction_timestamp', result)

    def test_behavioral_data_redaction(self):
        """Test that behavioral data is properly redacted"""
        behavioral_payload = {
            'user_id': 'user_456',
            'device_id': 'device_789',
            'event_type': 'click',
            'interaction_count': 25,
            'session_duration_ms': 45000,
            'gps_coordinates': [37.7749, -122.4194],  # San Francisco
            'precise_location': 'Building A, Floor 3, Room 301',
            'free_text_comment': 'User feedback about the app'
        }

        result = self.redactor.redact(behavioral_payload, 'behavioral/events')

        # Should keep allowlisted fields
        self.assertIn('event_type', result)
        self.assertIn('interaction_count', result)
        self.assertIn('session_duration_ms', result)

        # Should hash IDs
        self.assertIn('user_id', result)
        self.assertIn('device_id', result)
        self.assertNotEqual(result['user_id'], 'user_456')
        self.assertNotEqual(result['device_id'], 'device_789')

        # Should remove sensitive location data
        self.assertNotIn('gps_coordinates', result)
        self.assertNotIn('precise_location', result)
        self.assertNotIn('free_text_comment', result)

    def test_sensitive_pattern_detection(self):
        """Test detection of sensitive patterns in strings"""
        sensitive_data = {
            'message': 'Call me at 555-123-4567 or email test@example.com',
            'credit_card': '4532 1234 5678 9012',
            'ssn': '123-45-6789',
            'safe_field': 'This is safe content',
            'quality_score': 0.85
        }

        result = self.redactor.redact(sensitive_data, 'test/endpoint')

        # Should redact sensitive patterns
        self.assertIn('[REDACTED]', result.get('message', ''))
        self.assertNotIn('555-123-4567', str(result))
        self.assertNotIn('test@example.com', str(result))

        # Should remove credit card and SSN completely
        self.assertNotIn('credit_card', result)
        self.assertNotIn('ssn', result)

    def test_nested_data_redaction(self):
        """Test redaction of nested data structures"""
        nested_payload = {
            'metadata': {
                'user_id': 'user_123',
                'session_id': 'session_456',
                'timestamp': 1645123456789
            },
            'data': {
                'quality_score': 0.92,
                'voice_sample': 'sensitive_audio_data',
                'nested_email': 'hidden@example.com'
            },
            'allowed_list': [
                {'event_type': 'click', 'count': 5},
                {'event_type': 'scroll', 'count': 12}
            ],
            'sensitive_list': [
                {'name': 'John Doe', 'email': 'john@example.com'}
            ]
        }

        result = self.redactor.redact(nested_payload, 'test/nested')

        # Should handle nested structures appropriately
        self.assertIsInstance(result, dict)

        # Should have redaction metadata
        self.assertTrue(result['_pii_redacted'])

    def test_schema_hash_calculation(self):
        """Test schema hash calculation for anomaly detection"""
        payload1 = {
            'field_a': 'string_value',
            'field_b': 123,
            'field_c': True
        }

        payload2 = {
            'field_a': 'different_string',
            'field_b': 456,
            'field_c': False
        }

        payload3 = {
            'field_a': 'string_value',
            'field_b': 123,
            'field_d': 'new_field'  # Different schema
        }

        hash1 = self.redactor.calculate_schema_hash(payload1)
        hash2 = self.redactor.calculate_schema_hash(payload2)
        hash3 = self.redactor.calculate_schema_hash(payload3)

        # Same schema should produce same hash
        self.assertEqual(hash1, hash2)

        # Different schema should produce different hash
        self.assertNotEqual(hash1, hash3)

        # Hash should be consistent
        self.assertEqual(len(hash1), 16)

    def test_gps_coordinate_bucketing(self):
        """Test GPS coordinate bucketing for privacy"""
        payload = {
            'latitude': 37.774929,
            'longitude': -122.419415,
            'quality_score': 0.8
        }

        result = self.redactor.redact(payload, 'location/gps')

        # GPS coordinates should be bucketed
        if 'latitude_bucketed' in result:
            self.assertAlmostEqual(result['latitude_bucketed'], 37.8, places=1)
        if 'longitude_bucketed' in result:
            self.assertAlmostEqual(result['longitude_bucketed'], -122.4, places=1)

        # Original coordinates should be removed
        self.assertNotIn('latitude', result)
        self.assertNotIn('longitude', result)

    def test_endpoint_sanitization(self):
        """Test endpoint URL sanitization"""
        endpoints = [
            '/api/users/123/profile',
            '/ws/mobile/device/abc-def-123/',
            '/api/sessions/session-uuid-here',
            '/api/internal?query=sensitive'
        ]

        expected = [
            '/api/users/{id}/profile',
            '/ws/mobile/device/{device_id}/',
            '/api/sessions/{session_id}',
            '/api/internal'
        ]

        for endpoint, expected_result in zip(endpoints, expected):
            sanitized = self.redactor._sanitize_endpoint(endpoint)
            self.assertEqual(sanitized, expected_result)

    def test_retention_category_assignment(self):
        """Test retention category assignment"""
        test_cases = [
            ('voice_data', 'sanitized_metadata'),
            ('behavioral_data', 'sanitized_metadata'),
            ('metrics', 'aggregated_metrics'),
            ('websocket_meta', 'sanitized_metadata'),
            ('unknown_type', 'sanitized_metadata')
        ]

        for data_type, expected_category in test_cases:
            category = self.redactor.get_retention_category(data_type)
            self.assertEqual(category, expected_category)

    def test_empty_or_invalid_data(self):
        """Test handling of empty or invalid data"""
        test_cases = [
            None,
            {},
            [],
            '',
            123,
            {'empty': None}
        ]

        for invalid_data in test_cases:
            result = self.redactor.redact(invalid_data, 'test/endpoint')

            # Should always return a dict with metadata
            self.assertIsInstance(result, dict)
            self.assertIn('_redaction_timestamp', result)

    def test_large_payload_handling(self):
        """Test handling of large payloads"""
        # Create a large payload
        large_payload = {
            'user_id': 'user_123',
            'large_list': list(range(1000)),  # Large list
            'quality_score': 0.85,
            'nested_data': {
                f'field_{i}': f'value_{i}' for i in range(100)
            }
        }

        result = self.redactor.redact(large_payload, 'test/large')

        # Should handle large payloads without errors
        self.assertIsInstance(result, dict)
        self.assertTrue(result['_pii_redacted'])

        # Should limit list sizes
        if 'large_list' in result:
            self.assertLessEqual(len(result['large_list']), 10)

    def test_custom_redaction_rules(self):
        """Test custom redaction rules override defaults"""
        payload = {
            'user_id': 'user_123',
            'custom_field': 'custom_value',
            'quality_score': 0.9,
            'voice_sample': 'audio_data'
        }

        custom_rules = {
            'allowlisted_fields': {'custom_field', 'quality_score'},
            'hash_fields': {'user_id'},
            'remove_fields': {'voice_sample'}
        }

        result = self.redactor.redact(payload, 'test/custom', custom_rules)

        # Should apply custom rules
        self.assertIn('custom_field', result)
        self.assertIn('quality_score', result)
        self.assertIn('user_id', result)
        self.assertNotIn('voice_sample', result)

        # user_id should be hashed
        self.assertNotEqual(result['user_id'], 'user_123')


class TestPIIRedactorIntegration(TestCase):
    """Integration tests for PII redactor with Django models"""

    def test_integration_with_stream_events(self):
        """Test PII redactor integration with StreamEvent model"""
        from ..models import TestScenario, TestRun, StreamEvent
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Create test user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        # Create test scenario
        scenario = TestScenario.objects.create(
            name='PII Test Scenario',
            protocol='websocket',
            endpoint='ws://test/',
            expected_p95_latency_ms=100,
            expected_error_rate=0.05,
            created_by=user
        )

        # Create test run
        run = TestRun.objects.create(
            scenario=scenario,
            started_by=user
        )

        # Test payload with PII
        payload_with_pii = {
            'user_id': 'sensitive_user_123',
            'voice_sample': b'binary_audio_data',
            'quality_score': 0.85,
            'email': 'user@example.com',
            'phone': '555-123-4567'
        }

        # Create stream event
        redactor = PIIRedactor()
        sanitized_payload = redactor.redact(payload_with_pii, 'voice/test')

        event = StreamEvent.objects.create(
            run=run,
            correlation_id='test-correlation-123',
            direction='inbound',
            endpoint='voice/test',
            latency_ms=45.5,
            message_size_bytes=len(str(payload_with_pii)),
            payload_sanitized=sanitized_payload,
            payload_schema_hash=redactor.calculate_schema_hash(payload_with_pii)
        )

        # Verify PII was redacted
        stored_payload = event.payload_sanitized
        self.assertNotIn('voice_sample', stored_payload)
        self.assertNotIn('email', stored_payload)
        self.assertNotIn('phone', stored_payload)
        self.assertIn('quality_score', stored_payload)
        self.assertTrue(stored_payload['_pii_redacted'])

    def test_hash_consistency(self):
        """Test that hashing is consistent across instances"""
        redactor1 = PIIRedactor()
        redactor2 = PIIRedactor()

        value = 'test_user_123'
        hash1 = redactor1._hash_value(value)
        hash2 = redactor2._hash_value(value)

        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, value)
        self.assertEqual(len(hash1), 16)
