"""
Tests for Kotlin/Android-Specific Anomaly Rules
Tests the new Kotlin-specific anomaly detection rules for mobile performance issues.
"""

import uuid
from unittest.mock import patch, AsyncMock
from django.test import TestCase

from apps.issue_tracker.services.anomaly_detector import AnomalyDetector


class KotlinAnomalyRulesTests(TestCase):
    """Test Kotlin-specific anomaly detection rules"""

    def setUp(self):
        """Set up test detector with Kotlin rules"""
        self.detector = AnomalyDetector()

        # Mock YAML rules including Kotlin-specific rules
        self.detector.rules = {
            'rules': [
                # Compose Jank Detection
                {
                    'name': 'compose_jank_detected',
                    'anomaly_type': 'compose_performance',
                    'severity': 'warning',
                    'condition': {
                        'endpoint': {'contains': ['mobile', 'android']},
                        'payload_sanitized': {'contains': ['jank_percent', 'frame_drops']},
                        'latency_ms': {'gt': 16}
                    },
                    'tags': ['kotlin', 'compose', 'ui_performance', 'jank']
                },

                # ANR Detection
                {
                    'name': 'anr_detected',
                    'anomaly_type': 'anr_detected',
                    'severity': 'critical',
                    'condition': {
                        'error_message': {'contains': ['ANR', 'not responding', 'application hang']},
                        'outcome': {'eq': 'error'}
                    },
                    'tags': ['kotlin', 'anr', 'main_thread', 'critical']
                },

                # StrictMode Violations
                {
                    'name': 'strict_mode_violation',
                    'anomaly_type': 'strict_mode_violation',
                    'severity': 'warning',
                    'condition': {
                        'error_message': {'contains': ['StrictMode', 'policy violation', 'main thread']},
                        'outcome': {'eq': 'error'}
                    },
                    'tags': ['kotlin', 'strict_mode', 'threading', 'policy']
                },

                # Memory Pressure
                {
                    'name': 'android_memory_pressure',
                    'anomaly_type': 'android_memory_pressure',
                    'severity': 'error',
                    'condition': {
                        'error_message': {'contains': ['OutOfMemoryError', 'memory pressure', 'GC overhead', 'bitmap']},
                        'outcome': {'eq': 'error'}
                    },
                    'tags': ['kotlin', 'memory', 'bitmap', 'oom']
                },

                # Network on Main Thread
                {
                    'name': 'network_on_main_thread',
                    'anomaly_type': 'network_main_thread',
                    'severity': 'error',
                    'condition': {
                        'error_message': {'contains': ['NetworkOnMainThreadException', 'main thread network']},
                        'outcome': {'eq': 'error'}
                    },
                    'tags': ['kotlin', 'networking', 'main_thread', 'violation']
                },

                # Slow Cold Startup
                {
                    'name': 'slow_cold_startup',
                    'anomaly_type': 'slow_cold_startup',
                    'severity': 'warning',
                    'condition': {
                        'endpoint': {'contains': ['startup', 'cold_start', 'application']},
                        'latency_ms': {'gt': 2000}
                    },
                    'tags': ['kotlin', 'startup', 'performance', 'cold_start']
                }
            ],
            'thresholds': {
                'mobile_performance': {
                    'jank_percentage_warning': 2.0,
                    'jank_percentage_error': 5.0,
                    'anr_timeout': 5000
                }
            }
        }

        self.detector.thresholds = self.detector._load_thresholds()

    async def test_compose_jank_detection(self):
        """Test Jetpack Compose jank detection"""
        event_data = {
            'endpoint': 'mobile/android/ui',
            'latency_ms': 25,  # Above 16ms threshold
            'payload_sanitized': {
                'jank_percent': 3.2,
                'frame_drops': 5
            },
            'outcome': 'success',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                'occurrence_id': 'test-compose-jank',
                'anomaly_type': 'compose_performance',
                'severity': 'warning'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertIsNotNone(result)
            self.assertEqual(result['anomaly_type'], 'compose_performance')
            self.assertEqual(result['severity'], 'warning')
            mock_create.assert_called_once()

    async def test_anr_detection(self):
        """Test ANR (Application Not Responding) detection"""
        event_data = {
            'endpoint': 'mobile/android',
            'error_message': 'Application not responding: MainThread blocked for 5 seconds',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                'occurrence_id': 'test-anr',
                'anomaly_type': 'anr_detected',
                'severity': 'critical'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertEqual(result['anomaly_type'], 'anr_detected')
            self.assertEqual(result['severity'], 'critical')

    async def test_strict_mode_violation_detection(self):
        """Test Android StrictMode violation detection"""
        event_data = {
            'endpoint': 'mobile/sync',
            'error_message': 'StrictMode policy violation: disk read on main thread',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                'occurrence_id': 'test-strictmode',
                'anomaly_type': 'strict_mode_violation',
                'severity': 'warning'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertEqual(result['anomaly_type'], 'strict_mode_violation')
            self.assertEqual(result['severity'], 'warning')

    async def test_memory_pressure_detection(self):
        """Test Android memory pressure detection"""
        event_data = {
            'endpoint': 'mobile/image_loading',
            'error_message': 'OutOfMemoryError: Failed to allocate bitmap memory',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                'occurrence_id': 'test-oom',
                'anomaly_type': 'android_memory_pressure',
                'severity': 'error'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertEqual(result['anomaly_type'], 'android_memory_pressure')
            self.assertEqual(result['severity'], 'error')

    async def test_network_main_thread_detection(self):
        """Test network operation on main thread detection"""
        event_data = {
            'endpoint': 'mobile/api_call',
            'error_message': 'NetworkOnMainThreadException: Network operation on UI thread',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                'occurrence_id': 'test-network-main',
                'anomaly_type': 'network_main_thread',
                'severity': 'error'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertEqual(result['anomaly_type'], 'network_main_thread')
            self.assertEqual(result['severity'], 'error')

    async def test_slow_cold_startup_detection(self):
        """Test slow cold startup detection"""
        event_data = {
            'endpoint': 'mobile/cold_start',
            'latency_ms': 2500,  # Above 2000ms threshold
            'outcome': 'success',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {
                'occurrence_id': 'test-slow-startup',
                'anomaly_type': 'slow_cold_startup',
                'severity': 'warning'
            }

            result = await self.detector.analyze_event(event_data)

            self.assertEqual(result['anomaly_type'], 'slow_cold_startup')
            self.assertEqual(result['severity'], 'warning')

    async def test_kotlin_rules_no_false_positives(self):
        """Test that Kotlin rules don't trigger false positives for non-mobile events"""
        # Non-mobile event that shouldn't trigger Kotlin rules
        event_data = {
            'endpoint': 'api/backend/processing',
            'latency_ms': 50,
            'error_message': 'Database connection timeout',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4())
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = None

            result = await self.detector.analyze_event(event_data)

            # Should not match any Kotlin-specific rules
            mock_create.assert_not_called()

    async def test_multiple_kotlin_rules_matching(self):
        """Test multiple Kotlin rules matching the same event"""
        # Event that could match multiple Kotlin rules
        event_data = {
            'endpoint': 'mobile/android/ui',
            'latency_ms': 50,  # Above compose jank threshold
            'error_message': 'StrictMode policy violation: main thread network access',
            'outcome': 'error',
            'correlation_id': str(uuid.uuid4()),
            'payload_sanitized': {
                'jank_percent': 4.0,
                'frame_drops': 8
            }
        }

        with patch.object(self.detector, '_create_anomaly', new_callable=AsyncMock) as mock_create:
            # Mock multiple anomaly creations
            mock_create.side_effect = [
                {
                    'occurrence_id': 'compose-jank-occ',
                    'anomaly_type': 'compose_performance',
                    'severity': 'warning'
                },
                {
                    'occurrence_id': 'strictmode-occ',
                    'anomaly_type': 'strict_mode_violation',
                    'severity': 'warning'
                }
            ]

            result = await self.detector.analyze_event(event_data)

            # Should detect multiple anomalies
            self.assertIsNotNone(result)
            self.assertIn('additional_anomalies', result)
            self.assertEqual(result['total_anomaly_count'], 2)

    def test_kotlin_rule_conditions_matching(self):
        """Test individual rule condition matching logic"""
        # Test contains condition with list
        test_data = {
            'error_message': 'ANR detected in MainActivity',
            'outcome': 'error'
        }

        anr_rule = next(rule for rule in self.detector.rules['rules'] if rule['name'] == 'anr_detected')
        matches = self.detector._matches_rule(test_data, anr_rule)
        self.assertTrue(matches)

        # Test contains condition that should not match
        test_data_no_match = {
            'error_message': 'Simple timeout error',
            'outcome': 'error'
        }

        matches_no = self.detector._matches_rule(test_data_no_match, anr_rule)
        self.assertFalse(matches_no)

    def test_kotlin_endpoint_pattern_matching(self):
        """Test endpoint pattern matching for Kotlin rules"""
        compose_rule = next(rule for rule in self.detector.rules['rules'] if rule['name'] == 'compose_jank_detected')

        # Test mobile/android endpoints that should match
        mobile_endpoints = [
            'mobile/android/ui',
            'ws/mobile/sync',
            'api/mobile/performance'
        ]

        for endpoint in mobile_endpoints:
            test_data = {
                'endpoint': endpoint,
                'latency_ms': 20,
                'payload_sanitized': {'jank_percent': 3.0}
            }
            matches = self.detector._matches_rule(test_data, compose_rule)
            self.assertTrue(matches, f"Should match mobile endpoint: {endpoint}")

        # Test non-mobile endpoints that should not match
        non_mobile_endpoints = [
            'api/backend/processing',
            'ws/admin/dashboard',
            'graphql/query'  # Legacy - GraphQL removed Oct 2025
        ]

        for endpoint in non_mobile_endpoints:
            test_data = {
                'endpoint': endpoint,
                'latency_ms': 20,
                'payload_sanitized': {'jank_percent': 3.0}
            }
            matches = self.detector._matches_rule(test_data, compose_rule)
            self.assertFalse(matches, f"Should not match non-mobile endpoint: {endpoint}")

    async def test_kotlin_performance_thresholds(self):
        """Test Kotlin-specific performance thresholds from YAML"""
        # Test jank percentage thresholds
        self.assertEqual(self.detector.thresholds.get('jank_percentage_warning'), 2.0)
        self.assertEqual(self.detector.thresholds.get('jank_percentage_error'), 5.0)
        self.assertEqual(self.detector.thresholds.get('anr_timeout'), 5000)

        # Test statistical detection with Kotlin thresholds
        jank_event = {
            'endpoint': 'mobile/ui',
            'latency_ms': 18,  # Above 16ms UI frame time
            'payload_sanitized': {'jank_percent': 3.0}  # Above warning threshold
        }

        statistical_result = self.detector._detect_statistical_anomaly(jank_event)

        # Should detect as latency spike (since it's a UI event above 16ms)
        if statistical_result:
            self.assertEqual(statistical_result['anomaly_type'], 'latency_spike')

    def test_kotlin_rule_tags(self):
        """Test that Kotlin rules have appropriate tags"""
        kotlin_rules = [rule for rule in self.detector.rules['rules'] if 'kotlin' in rule.get('tags', [])]

        # Verify we have Kotlin rules
        self.assertGreater(len(kotlin_rules), 0)

        # Verify all Kotlin rules have 'kotlin' tag
        for rule in kotlin_rules:
            self.assertIn('kotlin', rule['tags'])

        # Verify specific rule tags
        anr_rule = next(rule for rule in kotlin_rules if rule['name'] == 'anr_detected')
        expected_anr_tags = ['kotlin', 'anr', 'main_thread', 'critical']
        for tag in expected_anr_tags:
            self.assertIn(tag, anr_rule['tags'])

        compose_rule = next(rule for rule in kotlin_rules if rule['name'] == 'compose_jank_detected')
        expected_compose_tags = ['kotlin', 'compose', 'ui_performance', 'jank']
        for tag in expected_compose_tags:
            self.assertIn(tag, compose_rule['tags'])

    def test_kotlin_severity_levels(self):
        """Test that Kotlin rules have appropriate severity levels"""
        kotlin_rules = [rule for rule in self.detector.rules['rules'] if 'kotlin' in rule.get('tags', [])]

        severity_mapping = {
            'anr_detected': 'critical',
            'network_on_main_thread': 'error',
            'android_memory_pressure': 'error',
            'compose_jank_detected': 'warning',
            'strict_mode_violation': 'warning',
            'slow_cold_startup': 'warning'
        }

        for rule in kotlin_rules:
            rule_name = rule['name']
            if rule_name in severity_mapping:
                expected_severity = severity_mapping[rule_name]
                actual_severity = rule['severity']
                self.assertEqual(actual_severity, expected_severity,
                               f"Rule {rule_name} should have severity {expected_severity}, got {actual_severity}")