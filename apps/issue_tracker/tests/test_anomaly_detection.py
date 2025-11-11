"""
Unit tests for Anomaly Detection Engine

Includes tests for:
- Anomaly detection logic
- Recurrence tracking
- Fix suggestion generation
- YAML rules caching (Nov 2025 performance optimization)
"""

import pytest
import asyncio
import time
from unittest.mock import patch, mock_open, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from ..models import AnomalySignature, AnomalyOccurrence, FixSuggestion, RecurrenceTracker
from ..services.anomaly_detector import (
    AnomalyDetector,
    reload_anomaly_rules,
    CACHE_TTL_SECONDS
)

User = get_user_model()


class TestAnomalyDetector(TransactionTestCase):
    """Test anomaly detection functionality"""

    def setUp(self):
        self.detector = AnomalyDetector()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

    def test_latency_anomaly_detection(self):
        """Test detection of latency anomalies"""
        async def run_test():
            event_data = {
                'latency_ms': 150,  # Above 100ms threshold
                'endpoint': 'ws/mobile/sync',
                'outcome': 'success',
                'correlation_id': 'test-123'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertIsNotNone(result)
            self.assertEqual(result['anomaly_type'], 'latency_spike')
            self.assertEqual(result['severity'], 'warning')

        asyncio.run(run_test())

    def test_schema_validation_error_detection(self):
        """Test detection of schema validation errors"""
        async def run_test():
            event_data = {
                'outcome': 'error',
                'error_message': 'Schema validation failed: field required',
                'endpoint': 'api/sync',
                'correlation_id': 'test-456'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertIsNotNone(result)
            self.assertEqual(result['anomaly_type'], 'schema_drift')
            self.assertEqual(result['severity'], 'error')

        asyncio.run(run_test())

    def test_connection_timeout_detection(self):
        """Test detection of connection timeouts"""
        async def run_test():
            event_data = {
                'outcome': 'timeout',
                'latency_ms': 6000,  # 6 seconds
                'error_message': 'Database connection timeout',
                'endpoint': 'api/data',
                'correlation_id': 'test-789'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertIsNotNone(result)
            self.assertEqual(result['anomaly_type'], 'connection_timeout')
            self.assertEqual(result['severity'], 'error')

        asyncio.run(run_test())

    def test_rate_limit_detection(self):
        """Test detection of rate limiting issues"""
        async def run_test():
            event_data = {
                'http_status_code': 429,
                'outcome': 'error',
                'endpoint': 'api/upload',
                'correlation_id': 'test-rate-limit'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertIsNotNone(result)
            self.assertEqual(result['anomaly_type'], 'rate_limit')
            self.assertEqual(result['severity'], 'warning')

        asyncio.run(run_test())

    def test_no_anomaly_for_normal_event(self):
        """Test that normal events don't trigger anomalies"""
        async def run_test():
            event_data = {
                'latency_ms': 25,  # Normal latency
                'outcome': 'success',
                'endpoint': 'ws/mobile/sync',
                'correlation_id': 'test-normal'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertIsNone(result)

        asyncio.run(run_test())

    def test_signature_creation_and_recurrence(self):
        """Test anomaly signature creation and recurrence tracking"""
        async def run_test():
            # First occurrence
            event_data = {
                'latency_ms': 200,
                'endpoint': 'ws/mobile/sync',
                'outcome': 'success',
                'correlation_id': 'test-recurrence-1'
            }

            result1 = await self.detector.analyze_event(event_data)
            self.assertIsNotNone(result1)
            self.assertTrue(result1['is_new_signature'])

            signature = AnomalySignature.objects.get(id=result1['signature_id'])
            self.assertEqual(signature.occurrence_count, 1)

            # Second occurrence (same pattern)
            event_data['correlation_id'] = 'test-recurrence-2'
            result2 = await self.detector.analyze_event(event_data)

            self.assertIsNotNone(result2)
            self.assertFalse(result2['is_new_signature'])
            self.assertEqual(result1['signature_id'], result2['signature_id'])

            # Verify occurrence count updated
            signature.refresh_from_db()
            self.assertEqual(signature.occurrence_count, 2)

        asyncio.run(run_test())

    def test_endpoint_normalization(self):
        """Test endpoint pattern normalization"""
        test_cases = [
            ('/api/users/123/profile', '/api/users/{id}/profile'),
            ('/ws/device/abc-def-123/', '/ws/device/{device_id}/'),
            ('/api/sessions/550e8400-e29b-41d4-a716-446655440000', '/api/sessions/{uuid}'),
            ('/static/files/abcdef123456789', '/static/files/{hash}'),
            ('/simple/path', '/simple/path')
        ]

        for endpoint, expected in test_cases:
            normalized = self.detector._normalize_endpoint(endpoint)
            self.assertEqual(normalized, expected)

    def test_rule_matching_logic(self):
        """Test rule matching conditions"""
        rule = {
            'condition': {
                'latency_ms': {'gt': 100},
                'endpoint': {'contains': 'websocket'},
                'outcome': {'eq': 'success'}
            }
        }

        # Should match
        matching_event = {
            'latency_ms': 150,
            'endpoint': 'ws/websocket/sync',
            'outcome': 'success'
        }
        self.assertTrue(self.detector._matches_rule(matching_event, rule))

        # Should not match - latency too low
        non_matching_event1 = {
            'latency_ms': 50,
            'endpoint': 'ws/websocket/sync',
            'outcome': 'success'
        }
        self.assertFalse(self.detector._matches_rule(non_matching_event1, rule))

        # Should not match - wrong endpoint
        non_matching_event2 = {
            'latency_ms': 150,
            'endpoint': 'api/rest/sync',
            'outcome': 'success'
        }
        self.assertFalse(self.detector._matches_rule(non_matching_event2, rule))

    def test_statistical_anomaly_detection(self):
        """Test statistical anomaly detection beyond rules"""
        # Test latency outlier detection
        event_data = {
            'latency_ms': 350,  # 3.5x the default 100ms threshold
            'endpoint': 'ws/test',
            'correlation_id': 'test-outlier'
        }

        anomaly = self.detector._detect_statistical_anomaly(event_data)
        self.assertIsNotNone(anomaly)
        self.assertEqual(anomaly['anomaly_type'], 'latency_outlier')

    def test_anomaly_stats_calculation(self):
        """Test anomaly statistics calculation"""
        # Create some test anomalies
        signature1 = AnomalySignature.objects.create(
            signature_hash='hash1',
            anomaly_type='latency_spike',
            severity='warning',
            pattern={'test': 'pattern'},
            endpoint_pattern='/ws/test'
        )

        signature2 = AnomalySignature.objects.create(
            signature_hash='hash2',
            anomaly_type='schema_drift',
            severity='critical',
            pattern={'test': 'pattern'},
            endpoint_pattern='/api/test'
        )

        # Create occurrences
        AnomalyOccurrence.objects.create(
            signature=signature1,
            endpoint='/ws/test',
            status='new'
        )

        AnomalyOccurrence.objects.create(
            signature=signature2,
            endpoint='/api/test',
            status='investigating'
        )

        stats = self.detector.get_anomaly_stats()

        self.assertEqual(stats['total_signatures'], 2)
        self.assertEqual(stats['active_signatures'], 2)
        self.assertEqual(stats['critical_anomalies'], 1)
        self.assertEqual(stats['unresolved_occurrences'], 2)


class TestRecurrenceTracker(TestCase):
    """Test recurrence tracking functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        self.signature = AnomalySignature.objects.create(
            signature_hash='test_hash',
            anomaly_type='test_anomaly',
            severity='warning',
            pattern={'test': 'pattern'},
            endpoint_pattern='/test/endpoint'
        )

    def test_recurrence_tracking_creation(self):
        """Test creation of recurrence tracker"""
        tracker, created = RecurrenceTracker.objects.get_or_create(
            signature=self.signature
        )

        self.assertTrue(created)
        self.assertEqual(tracker.signature, self.signature)
        self.assertEqual(tracker.recurrence_count, 0)

    def test_recurrence_update_calculation(self):
        """Test recurrence tracking update logic"""
        # Create multiple occurrences
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        times = [
            now - timedelta(hours=4),
            now - timedelta(hours=3),
            now - timedelta(hours=2),
            now - timedelta(hours=1),
            now
        ]

        for i, time in enumerate(times):
            occurrence = AnomalyOccurrence.objects.create(
                signature=self.signature,
                endpoint='/test/endpoint',
                status='new' if i < 3 else 'resolved'
            )
            # Manually set created_at to test interval calculation
            occurrence.created_at = time
            occurrence.save()

        # Create and update recurrence tracker
        tracker = RecurrenceTracker.objects.create(signature=self.signature)
        tracker.update_recurrence()

        # Verify calculations
        self.assertEqual(tracker.recurrence_count, 5)
        self.assertIsNotNone(tracker.typical_interval_hours)
        self.assertTrue(tracker.requires_attention)  # >5 occurrences


class TestAnomalyDetectionIntegration(TransactionTestCase):
    """Integration tests for anomaly detection with stream events"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

    def test_end_to_end_anomaly_flow(self):
        """Test complete anomaly detection and fix suggestion flow"""
        async def run_test():
            from apps.streamlab.models import TestScenario, TestRun
            from ..services.anomaly_detector import anomaly_detector

            # Create test scenario and run
            scenario = TestScenario.objects.create(
                name='E2E Test',
                protocol='websocket',
                endpoint='ws://test/',
                expected_p95_latency_ms=100,
                expected_error_rate=0.05,
                created_by=self.user
            )

            run = TestRun.objects.create(
                scenario=scenario,
                started_by=self.user,
                status='running'
            )

            # Simulate slow event that should trigger anomaly
            event_data = {
                'latency_ms': 250,  # Slow
                'endpoint': 'ws/mobile/sync',
                'outcome': 'success',
                'correlation_id': 'e2e-test',
                'test_run_id': str(run.id),
                'payload_sanitized': {'quality_score': 0.8}
            }

            # Analyze event
            result = await anomaly_detector.analyze_event(event_data)

            self.assertIsNotNone(result)

            # Verify signature was created
            signature = AnomalySignature.objects.get(id=result['signature_id'])
            self.assertEqual(signature.anomaly_type, 'latency_spike')

            # Verify occurrence was created
            occurrence = AnomalyOccurrence.objects.get(id=result['occurrence_id'])
            self.assertEqual(occurrence.signature, signature)
            self.assertEqual(occurrence.latency_ms, 250)

            # Verify fix suggestions were generated
            suggestions = signature.fix_suggestions.all()
            self.assertGreater(suggestions.count(), 0)

            # Verify recurrence tracker was created
            tracker = RecurrenceTracker.objects.get(signature=signature)
            self.assertEqual(tracker.recurrence_count, 1)

        asyncio.run(run_test())

    def test_multiple_anomaly_types(self):
        """Test detection of multiple different anomaly types"""
        async def run_test():
            detector = AnomalyDetector()

            test_events = [
                {
                    'latency_ms': 200,
                    'endpoint': 'ws/mobile/sync',
                    'outcome': 'success',
                    'correlation_id': 'test-latency'
                },
                {
                    'outcome': 'error',
                    'error_message': 'Schema validation failed',
                    'endpoint': 'api/sync',
                    'correlation_id': 'test-schema'
                },
                {
                    'http_status_code': 429,
                    'outcome': 'error',
                    'endpoint': 'api/upload',
                    'correlation_id': 'test-rate-limit'
                }
            ]

            results = []
            for event_data in test_events:
                result = await detector.analyze_event(event_data)
                if result:
                    results.append(result)

            # Should detect all three anomaly types
            self.assertEqual(len(results), 3)

            anomaly_types = [r['anomaly_type'] for r in results]
            self.assertIn('latency_spike', anomaly_types)
            self.assertIn('schema_drift', anomaly_types)
            self.assertIn('rate_limit', anomaly_types)

        asyncio.run(run_test())


class TestFixSuggestionEngine(TestCase):
    """Test fix suggestion generation"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        self.signature = AnomalySignature.objects.create(
            signature_hash='test_hash',
            anomaly_type='latency_spike',
            severity='warning',
            pattern={'test': 'pattern'},
            endpoint_pattern='/ws/mobile/sync'
        )

    def test_fix_suggestion_generation(self):
        """Test generation of fix suggestions"""
        async def run_test():
            from ..services.fix_suggester import fix_suggester

            rule = {
                'fixes': [
                    {
                        'type': 'index',
                        'suggestion': 'Add database index',
                        'confidence': 0.8
                    },
                    {
                        'type': 'caching',
                        'suggestion': 'Implement caching',
                        'confidence': 0.6
                    }
                ]
            }

            suggestions = await fix_suggester.generate_suggestions(self.signature, rule)

            self.assertGreater(len(suggestions), 0)

            # Verify suggestion properties
            index_suggestion = next(
                (s for s in suggestions if s.fix_type == 'index'), None
            )
            self.assertIsNotNone(index_suggestion)
            self.assertEqual(index_suggestion.confidence, 0.8)
            self.assertIn('index', index_suggestion.title.lower())

        asyncio.run(run_test())

    def test_priority_calculation(self):
        """Test fix suggestion priority calculation"""
        from ..services.fix_suggester import FixSuggestionEngine

        engine = FixSuggestionEngine()

        # Test critical severity with high confidence
        critical_signature = AnomalySignature.objects.create(
            signature_hash='critical_hash',
            anomaly_type='memory_pressure',
            severity='critical',
            pattern={'test': 'pattern'},
            endpoint_pattern='/api/critical',
            occurrence_count=8
        )

        priority = engine._calculate_priority(critical_signature, 0.9)
        self.assertGreaterEqual(priority, 8)  # Should be high priority

        # Test info severity with low confidence
        info_signature = AnomalySignature.objects.create(
            signature_hash='info_hash',
            anomaly_type='minor_delay',
            severity='info',
            pattern={'test': 'pattern'},
            endpoint_pattern='/api/info',
            occurrence_count=1
        )

        priority = engine._calculate_priority(info_signature, 0.3)
        self.assertLessEqual(priority, 3)  # Should be low priority

    def test_fix_template_generation(self):
        """Test fix template content generation"""
        suggestion = FixSuggestion.objects.create(
            signature=self.signature,
            title='Add Database Index',
            description='Add index for query optimization',
            fix_type='index',
            confidence=0.85,
            priority_score=7
        )

        # Verify template content
        self.assertIn('CREATE INDEX', suggestion.patch_template)
        self.assertGreater(len(suggestion.implementation_steps), 0)

    def test_fix_approval_workflow(self):
        """Test fix suggestion approval workflow"""
        suggestion = FixSuggestion.objects.create(
            signature=self.signature,
            title='Test Fix',
            description='Test fix description',
            fix_type='code_fix',
            confidence=0.8,
            priority_score=5
        )

        # Test approval
        suggestion.approve(self.user)

        self.assertEqual(suggestion.status, 'approved')
        self.assertEqual(suggestion.approved_by, self.user)
        self.assertIsNotNone(suggestion.approved_at)

        # Test rejection
        suggestion.reject('Not applicable')

        self.assertEqual(suggestion.status, 'rejected')
        self.assertIn('Not applicable', suggestion.description)


class TestAnomalyIntegrationWithStreamEvents(TransactionTestCase):
    """Integration tests combining stream events with anomaly detection"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

    def test_stream_event_anomaly_pipeline(self):
        """Test complete pipeline from stream event to anomaly detection"""
        async def run_test():
            from apps.streamlab.models import TestScenario, TestRun, StreamEvent
            from apps.streamlab.services.event_capture import stream_event_capture
            from ..services.anomaly_detector import anomaly_detector

            # Create test infrastructure
            scenario = TestScenario.objects.create(
                name='Pipeline Test',
                protocol='websocket',
                endpoint='ws://test/',
                expected_p95_latency_ms=100,
                expected_error_rate=0.05,
                created_by=self.user
            )

            run = TestRun.objects.create(
                scenario=scenario,
                started_by=self.user,
                status='running'
            )

            # Mock active run
            correlation_id = 'pipeline-test-123'
            stream_event_capture.active_runs[correlation_id] = run

            # Capture event that should trigger anomaly
            payload = {
                'user_id': 'user_123',
                'quality_score': 0.85,
                'voice_sample': 'should_be_redacted'  # PII
            }

            event_id = await stream_event_capture.capture_event(
                correlation_id=correlation_id,
                endpoint='ws/mobile/sync',
                payload=payload,
                latency_ms=250,  # High latency - should trigger anomaly
                outcome='success'
            )

            self.assertIsNotNone(event_id)

            # Verify stream event was created
            event = StreamEvent.objects.get(id=event_id)
            self.assertEqual(event.latency_ms, 250)
            self.assertNotIn('voice_sample', event.payload_sanitized)

            # Test anomaly detection on this event
            event_data = {
                'latency_ms': event.latency_ms,
                'endpoint': event.endpoint,
                'outcome': event.outcome,
                'correlation_id': correlation_id,
                'event_id': str(event.id),
                'payload_sanitized': event.payload_sanitized
            }

            anomaly_result = await anomaly_detector.analyze_event(event_data)

            if anomaly_result:
                # Verify anomaly was detected and stored
                self.assertIsNotNone(anomaly_result['signature_id'])
                self.assertIsNotNone(anomaly_result['occurrence_id'])

                # Verify occurrence links to event
                occurrence = AnomalyOccurrence.objects.get(
                    id=anomaly_result['occurrence_id']
                )
                self.assertEqual(str(occurrence.event_ref), str(event.id))

        asyncio.run(run_test())


@pytest.mark.asyncio
class TestAsyncAnomalyDetection:
    """Pytest-based async tests for anomaly detection"""

    @pytest.fixture
    def detector(self):
        return AnomalyDetector()

    @pytest.fixture
    def user(self, db):
        User = get_user_model()
        return User.objects.create_user(
            username='pytest_user',
            email='pytest@example.com'
        )

    async def test_concurrent_anomaly_detection(self, detector, user):
        """Test anomaly detection under concurrent load"""
        # Create multiple concurrent anomaly detection tasks
        event_data_list = [
            {
                'latency_ms': 200 + i * 10,
                'endpoint': f'ws/test/{i}',
                'outcome': 'success',
                'correlation_id': f'concurrent-{i}'
            }
            for i in range(10)
        ]

        # Run anomaly detection concurrently
        tasks = [
            detector.analyze_event(event_data)
            for event_data in event_data_list
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify no exceptions occurred
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent anomaly detection failed: {result}")

        # Count successful detections
        successful_detections = [r for r in results if r is not None]
        assert len(successful_detections) > 0


# ===== YAML Rules Caching Tests (Nov 2025 Performance Optimization) =====


class TestAnomalyDetectorCaching(TestCase):
    """
    Test YAML rules caching behavior.

    Performance optimization (Nov 2025): YAML rules are cached at module level
    with 5-minute TTL to prevent repeated disk I/O during stream processing.
    """

    def setUp(self):
        """Reset cache before each test."""
        reload_anomaly_rules()

    def test_rules_cached_across_multiple_instances(self):
        """Test YAML rules cached across multiple AnomalyDetector instances."""
        yaml_content = """
rules:
  - name: test_rule
    condition:
      latency_ms: {gt: 100}
    severity: warning
    anomaly_type: test_anomaly
"""

        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('pathlib.Path.exists', return_value=True):
                # Create first instance - should load from disk
                detector1 = AnomalyDetector()

                # Create second instance - should use cache
                detector2 = AnomalyDetector()

                # Both should have same rules
                self.assertEqual(detector1.rules, detector2.rules)
                self.assertIn('rules', detector1.rules)
                self.assertEqual(len(detector1.rules['rules']), 1)

    def test_cache_hit_logs_debug_message(self):
        """Test cache hit logs debug message with cache age."""
        yaml_content = "rules: []"

        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('pathlib.Path.exists', return_value=True):
                # First instance loads from disk
                detector1 = AnomalyDetector()

                # Second instance hits cache
                with patch('apps.issue_tracker.services.anomaly_detector.logger') as mock_logger:
                    detector2 = AnomalyDetector()

                    # Verify debug log was called for cache hit
                    debug_calls = [call for call in mock_logger.debug.call_args_list]
                    cache_hit_logged = any('cached' in str(call).lower() for call in debug_calls)
                    self.assertTrue(cache_hit_logged, "Cache hit should be logged at debug level")

    def test_cache_miss_on_first_access(self):
        """Test cache miss triggers file load on first access."""
        yaml_content = "rules: []"

        reload_anomaly_rules()  # Ensure cache is empty

        with patch('builtins.open', mock_open(read_data=yaml_content)) as mock_file:
            with patch('pathlib.Path.exists', return_value=True):
                with patch('apps.issue_tracker.services.anomaly_detector.logger') as mock_logger:
                    detector = AnomalyDetector()

                    # Verify file was opened (cache miss)
                    mock_file.assert_called_once()

                    # Verify info log about loading from disk
                    info_calls = [call for call in mock_logger.info.call_args_list]
                    load_logged = any('Loaded anomaly' in str(call) for call in info_calls)
                    self.assertTrue(load_logged, "Initial load should be logged at info level")

    def test_cache_expiration_after_ttl(self):
        """Test cache expires after CACHE_TTL_SECONDS."""
        yaml_content = "rules: []"

        reload_anomaly_rules()

        with patch('builtins.open', mock_open(read_data=yaml_content)) as mock_file:
            with patch('pathlib.Path.exists', return_value=True):
                # First access - cache miss
                with patch('time.time', return_value=1000.0):
                    detector1 = AnomalyDetector()
                    first_call_count = mock_file.call_count

                # Second access within TTL - cache hit
                with patch('time.time', return_value=1000.0 + 60):  # 1 minute later
                    detector2 = AnomalyDetector()
                    # File should NOT be opened again
                    self.assertEqual(mock_file.call_count, first_call_count)

                # Third access after TTL expires - cache miss
                with patch('time.time', return_value=1000.0 + CACHE_TTL_SECONDS + 1):
                    detector3 = AnomalyDetector()
                    # File should be opened again
                    self.assertEqual(mock_file.call_count, first_call_count + 1)

    def test_manual_reload_invalidates_cache(self):
        """Test reload_anomaly_rules() forces cache invalidation."""
        yaml_content = "rules: []"

        with patch('builtins.open', mock_open(read_data=yaml_content)) as mock_file:
            with patch('pathlib.Path.exists', return_value=True):
                # First access - loads from disk
                detector1 = AnomalyDetector()
                first_call_count = mock_file.call_count

                # Manual reload
                reload_anomaly_rules()

                # Next access should reload from disk
                detector2 = AnomalyDetector()
                self.assertEqual(mock_file.call_count, first_call_count + 1)

    def test_reload_logs_invalidation_message(self):
        """Test reload_anomaly_rules() logs cache invalidation."""
        with patch('apps.issue_tracker.services.anomaly_detector.logger') as mock_logger:
            reload_anomaly_rules()

            # Verify info log about cache invalidation
            info_calls = [call for call in mock_logger.info.call_args_list]
            invalidation_logged = any('invalidated' in str(call).lower() for call in info_calls)
            self.assertTrue(invalidation_logged, "Cache invalidation should be logged")

    def test_cache_prevents_repeated_file_io(self):
        """Test cache prevents disk I/O on repeated instantiation."""
        yaml_content = "rules: []"

        reload_anomaly_rules()

        with patch('builtins.open', mock_open(read_data=yaml_content)) as mock_file:
            with patch('pathlib.Path.exists', return_value=True):
                # Create 10 instances
                detectors = [AnomalyDetector() for _ in range(10)]

                # File should only be opened once (cached for remaining 9)
                self.assertEqual(mock_file.call_count, 1)

                # All instances should have same rules reference
                first_rules = detectors[0].rules
                for detector in detectors[1:]:
                    self.assertEqual(detector.rules, first_rules)

    def test_default_rules_used_when_file_missing(self):
        """Test default rules used when YAML file doesn't exist."""
        reload_anomaly_rules()

        with patch('pathlib.Path.exists', return_value=False):
            with patch('apps.issue_tracker.services.anomaly_detector.logger') as mock_logger:
                detector = AnomalyDetector()

                # Should have default rules
                self.assertIn('rules', detector.rules)
                self.assertGreater(len(detector.rules['rules']), 0)

                # Verify info log about using defaults
                info_calls = [call for call in mock_logger.info.call_args_list]
                default_logged = any('default' in str(call).lower() for call in info_calls)
                self.assertTrue(default_logged, "Using default rules should be logged")

    def test_default_rules_also_cached(self):
        """Test default rules (when file missing) are also cached."""
        reload_anomaly_rules()

        with patch('pathlib.Path.exists', return_value=False):
            # First instance uses defaults
            detector1 = AnomalyDetector()
            default_rules = detector1.rules

            # Second instance should use cached defaults
            detector2 = AnomalyDetector()

            # Should be same reference (cached)
            self.assertEqual(detector2.rules, default_rules)

    def test_cache_thread_safety(self):
        """Test cache behaves correctly under concurrent access."""
        import threading

        yaml_content = "rules: []"
        reload_anomaly_rules()

        results = []
        errors = []

        def create_detector():
            try:
                detector = AnomalyDetector()
                results.append(detector)
            except Exception as e:
                errors.append(e)

        with patch('builtins.open', mock_open(read_data=yaml_content)):
            with patch('pathlib.Path.exists', return_value=True):
                # Create 20 detectors concurrently
                threads = [threading.Thread(target=create_detector) for _ in range(20)]

                for thread in threads:
                    thread.start()

                for thread in threads:
                    thread.join()

        # Should have no errors
        self.assertEqual(len(errors), 0, f"Concurrent access caused errors: {errors}")

        # Should have 20 successful instances
        self.assertEqual(len(results), 20)

        # All should have rules
        for detector in results:
            self.assertIsNotNone(detector.rules)