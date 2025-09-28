"""
Tests for Enhanced Anomaly Detector
Tests YAML threshold loading, multiple rule matching, client version tracking, and real-time broadcasting.
"""

import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.issue_tracker.models import AnomalySignature, AnomalyOccurrence
from apps.streamlab.models import TestRun, TestScenario

User = get_user_model()


class EnhancedAnomalyDetectorTests(TestCase):
    """Test enhanced anomaly detector functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com'
        )

        # Create test scenario and run
        self.test_scenario = TestScenario.objects.create(
            name='Test Scenario',
            protocol='websocket',
            endpoint='ws/mobile/sync/',
            expected_p95_latency_ms=100.0,
            expected_error_rate=0.05,
            created_by=self.user
        )

        self.test_run = TestRun.objects.create(
            scenario=self.test_scenario,
            started_by=self.user,
            status='running'
        )

    def test_yaml_threshold_loading(self):
        """Test that thresholds are loaded from YAML configuration"""
        # Mock YAML rules with thresholds
        mock_rules = {
            'thresholds': {
                'latency': {
                    'websocket_p95': 150,
                    'mqtt_p95': 75,
                    'http_p95': 300
                },
                'error_rate': {
                    'warning_threshold': 0.03,
                    'critical_threshold': 0.10
                },
                'mobile_performance': {
                    'jank_percentage_warning': 3.0,
                    'anr_timeout': 6000
                },
                'confidence': {
                    'auto_apply': 0.98,
                    'suggest': 0.65
                }
            }
        }

        detector = AnomalyDetector()
        detector.rules = mock_rules

        thresholds = detector._load_thresholds()

        # Verify YAML thresholds are loaded
        self.assertEqual(thresholds['websocket_p95_threshold'], 150)
        self.assertEqual(thresholds['mqtt_p95_threshold'], 75)
        self.assertEqual(thresholds['http_p95_threshold'], 300)
        self.assertEqual(thresholds['error_rate_warning'], 0.03)
        self.assertEqual(thresholds['error_rate_critical'], 0.10)
        self.assertEqual(thresholds['auto_apply_confidence'], 0.98)
        self.assertEqual(thresholds['suggest_confidence'], 0.65)

    def test_yaml_threshold_loading_fallback(self):
        """Test fallback to hardcoded thresholds when YAML loading fails"""
        detector = AnomalyDetector()
        detector.rules = {}  # Empty rules

        thresholds = detector._load_thresholds()

        # Should fallback to hardcoded values
        self.assertEqual(thresholds['latency_p95_threshold'], 100.0)
        self.assertEqual(thresholds['error_rate_threshold'], 0.05)
        self.assertEqual(thresholds['anomaly_score_threshold'], 0.7)

    @patch('apps.issue_tracker.services.anomaly_detector.logger')
    def test_yaml_threshold_loading_error_handling(self, mock_logger):
        """Test error handling when YAML threshold loading fails"""
        detector = AnomalyDetector()
        detector.rules = {'thresholds': None}  # Invalid structure

        thresholds = detector._load_thresholds()

        # Should fallback and log warning
        mock_logger.warning.assert_called()
        self.assertEqual(thresholds['latency_p95_threshold'], 100.0)

    async def test_multiple_rule_matching(self):
        """Test that multiple matching rules are collected and prioritized"""
        detector = AnomalyDetector()

        # Mock multiple matching rules
        detector.rules = {
            'rules': [
                {
                    'name': 'rule1',
                    'anomaly_type': 'latency_spike',
                    'severity': 'warning',
                    'condition': {'latency_ms': {'gt': 50}}
                },
                {
                    'name': 'rule2',
                    'anomaly_type': 'error_pattern',
                    'severity': 'critical',
                    'condition': {'outcome': {'eq': 'error'}}
                },
                {
                    'name': 'rule3',
                    'anomaly_type': 'schema_drift',
                    'severity': 'info',
                    'condition': {'latency_ms': {'gt': 50}}
                }
            ]
        }

        detector.thresholds = {'latency_p95_threshold': 100}

        # Mock event data that matches multiple rules
        event_data = {
            'latency_ms': 100,
            'outcome': 'error',
            'endpoint': 'ws/test',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [
                {'occurrence_id': 'occ1', 'anomaly_type': 'latency_spike', 'severity': 'warning'},
                {'occurrence_id': 'occ2', 'anomaly_type': 'error_pattern', 'severity': 'critical'},
                {'occurrence_id': 'occ3', 'anomaly_type': 'schema_drift', 'severity': 'info'}
            ]

            result = await detector.analyze_event(event_data)

            # Should return the most severe (critical) anomaly first
            self.assertEqual(result['anomaly_type'], 'error_pattern')
            self.assertEqual(result['severity'], 'critical')

            # Should include info about additional anomalies
            self.assertIn('additional_anomalies', result)
            self.assertEqual(result['total_anomaly_count'], 3)
            self.assertEqual(len(result['additional_anomalies']), 2)

    async def test_statistical_anomaly_creation(self):
        """Test creation of statistical anomalies"""
        detector = AnomalyDetector()
        detector.rules = {'rules': []}
        detector.thresholds = {
            'websocket_p95_threshold': 100,
            'mqtt_p95_threshold': 50,
            'http_p95_threshold': 200
        }

        # Test WebSocket latency outlier
        event_data = {
            'latency_ms': 350,  # 3.5x threshold
            'endpoint': 'ws/mobile/sync',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(detector, '_create_statistical_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                'occurrence_id': 'stat-occ-1',
                'anomaly_type': 'latency_outlier',
                'severity': 'warning'
            }

            result = await detector.analyze_event(event_data)

            self.assertEqual(result['anomaly_type'], 'latency_outlier')
            self.assertEqual(result['severity'], 'warning')
            mock_create.assert_called_once()

    async def test_protocol_specific_thresholds(self):
        """Test protocol-specific threshold application"""
        detector = AnomalyDetector()
        detector.rules = {'rules': []}
        detector.thresholds = {
            'websocket_p95_threshold': 100,
            'mqtt_p95_threshold': 50,
            'http_p95_threshold': 200,
            'latency_p95_threshold': 100  # Default
        }

        test_cases = [
            ('ws/mobile/sync', 150, False),  # Below 3x WS threshold (300)
            ('ws/mobile/sync', 350, True),   # Above 3x WS threshold
            ('mqtt/topic', 75, False),       # Below 3x MQTT threshold (150)
            ('mqtt/topic', 180, True),       # Above 3x MQTT threshold
            ('api/rest', 300, False),        # Below 3x HTTP threshold (600)
            ('api/rest', 700, True),         # Above 3x HTTP threshold
        ]

        for endpoint, latency, should_detect in test_cases:
            event_data = {
                'endpoint': endpoint,
                'latency_ms': latency,
                'correlation_id': str(uuid.uuid4())
            }

            statistical_anomaly = detector._detect_statistical_anomaly(event_data)

            if should_detect:
                self.assertIsNotNone(statistical_anomaly, f"Should detect anomaly for {endpoint} with {latency}ms")
                self.assertEqual(statistical_anomaly['anomaly_type'], 'latency_outlier')
            else:
                # Should be None or not a latency outlier
                if statistical_anomaly:
                    self.assertNotEqual(statistical_anomaly['anomaly_type'], 'latency_outlier')

    async def test_client_version_tracking_in_anomaly_creation(self):
        """Test that client version information is stored in anomaly occurrences"""
        detector = AnomalyDetector()

        # Mock rule
        rule = {
            'name': 'test_rule',
            'anomaly_type': 'test_anomaly',
            'severity': 'warning',
            'condition': {}
        }

        # Event data with client version info
        event_data = {
            'endpoint': 'ws/mobile/sync',
            'latency_ms': 150,
            'correlation_id': str(uuid.uuid4()),
            'client_app_version': '1.2.3',
            'client_os_version': 'Android 13',
            'client_device_model': 'Pixel 7'
        }

        with patch('apps.issue_tracker.services.anomaly_detector.sync_to_async') as mock_sync_to_async:
            # Mock signature creation
            mock_signature = MagicMock()
            mock_signature.id = uuid.uuid4()
            mock_signature.occurrence_count = 1

            # Mock occurrence creation
            mock_occurrence = MagicMock()
            mock_occurrence.id = uuid.uuid4()
            mock_occurrence.created_at = timezone.now()

            # Configure sync_to_async mocks
            mock_sync_to_async.side_effect = [
                # get_or_create signature
                lambda func: lambda **kwargs: (mock_signature, True),
                # create occurrence
                lambda func: lambda **kwargs: mock_occurrence,
                # update_recurrence call
                lambda func: lambda: None
            ]

            with patch.object(detector, '_update_recurrence_tracking', new_callable=AsyncMock):
                with patch.object(detector, '_generate_fix_suggestions', new_callable=AsyncMock):
                    with patch.object(detector, '_broadcast_anomaly_alert', new_callable=AsyncMock):
                        result = await detector._create_anomaly(event_data, rule)

                        self.assertIsNotNone(result)
                        self.assertEqual(result['anomaly_type'], 'test_anomaly')

    @patch('apps.issue_tracker.services.anomaly_detector.get_channel_layer')
    async def test_real_time_anomaly_broadcasting(self, mock_get_channel_layer):
        """Test real-time anomaly broadcasting functionality"""
        mock_channel_layer = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        detector = AnomalyDetector()
        detector.rules = {'escalation': {'critical_anomalies': {'immediate_alert': True}}}

        # Mock objects
        mock_occurrence = MagicMock()
        mock_occurrence.id = uuid.uuid4()
        mock_occurrence.created_at = timezone.now()

        mock_signature = MagicMock()
        mock_signature.id = uuid.uuid4()
        mock_signature.occurrence_count = 1

        rule = {
            'anomaly_type': 'test_anomaly',
            'severity': 'critical'
        }

        event_data = {
            'endpoint': 'ws/mobile/sync',
            'correlation_id': str(uuid.uuid4()),
            'latency_ms': 200,
            'client_app_version': '1.0.0'
        }

        await detector._broadcast_anomaly_alert(mock_occurrence, mock_signature, rule, event_data)

        # Verify channel layer was called for both groups
        self.assertEqual(mock_channel_layer.group_send.call_count, 2)

        # Check anomaly alerts group call
        args, kwargs = mock_channel_layer.group_send.call_args_list[0]
        self.assertEqual(args[0], 'streamlab_anomaly_alerts')
        self.assertEqual(kwargs['type'], 'critical_anomaly')

        # Check stream metrics group call
        args, kwargs = mock_channel_layer.group_send.call_args_list[1]
        self.assertEqual(args[0], 'streamlab_stream_metrics')
        self.assertEqual(kwargs['type'], 'anomaly_detected')

    async def test_escalation_alert_for_critical_anomalies(self):
        """Test escalation alerts for critical anomalies"""
        detector = AnomalyDetector()
        detector.rules = {
            'escalation': {
                'critical_anomalies': {'immediate_alert': True},
                'recurring_issues': {'threshold': 5}
            }
        }

        alert_data = {
            'severity': 'critical',
            'recurrence_count': 1,
            'id': str(uuid.uuid4())
        }

        rule = {'severity': 'critical'}

        with patch('apps.issue_tracker.services.anomaly_detector.get_channel_layer') as mock_get_channel_layer:
            mock_channel_layer = AsyncMock()
            mock_get_channel_layer.return_value = mock_channel_layer

            await detector._send_escalation_alert(alert_data, rule)

            # Verify escalation alert was sent
            mock_channel_layer.group_send.assert_called_once()
            args, kwargs = mock_channel_layer.group_send.call_args
            self.assertEqual(args[0], 'anomaly_escalation')
            self.assertEqual(kwargs['type'], 'escalation_alert')
            self.assertEqual(kwargs['data']['escalation_reason'], 'critical_severity')

    async def test_recurring_issue_escalation(self):
        """Test escalation for recurring issues"""
        detector = AnomalyDetector()
        detector.rules = {
            'escalation': {
                'critical_anomalies': {'immediate_alert': False},
                'recurring_issues': {'threshold': 3}
            }
        }

        alert_data = {
            'severity': 'warning',
            'recurrence_count': 5,  # Above threshold
            'id': str(uuid.uuid4())
        }

        rule = {'severity': 'warning'}

        with patch('apps.issue_tracker.services.anomaly_detector.get_channel_layer') as mock_get_channel_layer:
            mock_channel_layer = AsyncMock()
            mock_get_channel_layer.return_value = mock_channel_layer

            await detector._send_escalation_alert(alert_data, rule)

            # Verify escalation alert was sent for recurring issue
            mock_channel_layer.group_send.assert_called_once()
            args, kwargs = mock_channel_layer.group_send.call_args
            self.assertEqual(kwargs['data']['escalation_reason'], 'high_recurrence')


class AnomalyOccurrenceVersionTrackingTests(TestCase):
    """Test client version tracking functionality in AnomalyOccurrence"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='versionuser',
            email='version@example.com'
        )

        self.signature = AnomalySignature.objects.create(
            signature_hash='test-hash-123',
            anomaly_type='test_anomaly',
            severity='warning',
            pattern={'test': True},
            endpoint_pattern='ws/test'
        )

    def test_client_version_info_property(self):
        """Test client_version_info property"""
        occurrence = AnomalyOccurrence.objects.create(
            signature=self.signature,
            endpoint='ws/test',
            client_app_version='1.2.3',
            client_os_version='Android 13',
            client_device_model='Pixel 7'
        )

        version_info = occurrence.client_version_info

        self.assertEqual(version_info['app_version'], '1.2.3')
        self.assertEqual(version_info['os_version'], 'Android 13')
        self.assertEqual(version_info['device_model'], 'Pixel 7')

    def test_client_version_info_with_empty_fields(self):
        """Test client_version_info with empty/unknown fields"""
        occurrence = AnomalyOccurrence.objects.create(
            signature=self.signature,
            endpoint='ws/test'
            # No version fields set
        )

        version_info = occurrence.client_version_info

        self.assertEqual(version_info['app_version'], 'unknown')
        self.assertEqual(version_info['os_version'], 'unknown')
        self.assertEqual(version_info['device_model'], 'unknown')

    def test_version_trend_analysis(self):
        """Test version trend analysis functionality"""
        # Create occurrences with different versions
        versions_data = [
            ('1.0.0', 'Android 12', 'Pixel 6'),
            ('1.0.0', 'Android 12', 'Pixel 6'),
            ('1.1.0', 'Android 13', 'Pixel 7'),
            ('1.1.0', 'Android 13', 'Pixel 7'),
            ('1.1.0', 'Android 13', 'Galaxy S23'),
            ('1.2.0', 'Android 14', 'Pixel 8'),
        ]

        for app_version, os_version, device_model in versions_data:
            AnomalyOccurrence.objects.create(
                signature=self.signature,
                endpoint='ws/test',
                client_app_version=app_version,
                client_os_version=os_version,
                client_device_model=device_model
            )

        trend_analysis = AnomalyOccurrence.version_trend_analysis(
            signature_id=self.signature.id,
            days=30
        )

        # Verify trend analysis structure
        self.assertIn('app_version_trends', trend_analysis)
        self.assertIn('os_version_trends', trend_analysis)
        self.assertIn('device_trends', trend_analysis)
        self.assertIn('version_regression_analysis', trend_analysis)

        # Verify app version trends
        app_trends = trend_analysis['app_version_trends']
        self.assertEqual(app_trends['1.1.0'], 3)  # Most occurrences
        self.assertEqual(app_trends['1.0.0'], 2)
        self.assertEqual(app_trends['1.2.0'], 1)

        # Verify OS version trends
        os_trends = trend_analysis['os_version_trends']
        self.assertEqual(os_trends['Android 13'], 3)
        self.assertEqual(os_trends['Android 12'], 2)
        self.assertEqual(os_trends['Android 14'], 1)

    def test_version_trend_analysis_no_data(self):
        """Test version trend analysis with no data"""
        trend_analysis = AnomalyOccurrence.version_trend_analysis(days=30)

        self.assertEqual(trend_analysis['app_version_trends'], {})
        self.assertEqual(trend_analysis['os_version_trends'], {})
        self.assertEqual(trend_analysis['device_trends'], {})
        self.assertEqual(trend_analysis['version_regression_analysis'], [])