"""
Comprehensive Tests for Bandwidth Optimization Service

Following .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
import gzip
import json
from django.test import TestCase
from django.core.exceptions import ValidationError

from apps.api.v1.services.bandwidth_optimization_service import BandwidthOptimizationService


@pytest.mark.unit
class TestBandwidthOptimization(TestCase):
    """Test bandwidth optimization features."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = BandwidthOptimizationService()

    def test_compress_large_payload(self):
        """Test compression of large payload."""
        large_data = {
            'items': [{'id': i, 'data': 'x' * 100} for i in range(50)]
        }

        result = self.service.compress_payload(large_data, compression_level='always')

        self.assertTrue(result['compressed'])
        self.assertLess(result['compressed_size'], result['original_size'])
        self.assertLess(result['compression_ratio'], 1.0)

    def test_skip_compression_for_small_payload(self):
        """Test adaptive compression skips small payloads."""
        small_data = {'id': 1, 'name': 'test'}

        result = self.service.compress_payload(small_data, compression_level='adaptive')

        self.assertFalse(result['compressed'])
        self.assertEqual(result['compression_ratio'], 1.0)

    def test_never_compress_option(self):
        """Test never compress option."""
        data = {'items': [{'id': i} for i in range(100)]}

        result = self.service.compress_payload(data, compression_level='never')

        self.assertFalse(result['compressed'])

    def test_calculate_delta_only_changed_fields(self):
        """Test delta calculation returns only changed fields."""
        server_version = {
            'mobile_id': 'uuid-123',
            'version': 3,
            'status': 'in_progress',
            'assigned_to': 'user-1',
            'priority': 'high'
        }

        client_version = {
            'mobile_id': 'uuid-123',
            'version': 4,
            'status': 'completed',
            'assigned_to': 'user-1',
            'priority': 'high'
        }

        result = self.service.calculate_delta(server_version, client_version)

        self.assertEqual(result['mobile_id'], 'uuid-123')
        self.assertEqual(result['version'], 4)
        self.assertEqual(result['fields_changed'], 1)
        self.assertIn('status', result['delta'])
        self.assertNotIn('assigned_to', result['delta'])

    def test_adaptive_batch_sizing_poor_network(self):
        """Test batch sizing for poor network quality."""
        items = [{'id': i} for i in range(100)]

        batches = self.service.adaptive_batch_sizing(items, network_quality='poor')

        self.assertEqual(len(batches), 10)
        self.assertEqual(len(batches[0]), 10)

    def test_adaptive_batch_sizing_excellent_network(self):
        """Test batch sizing for excellent network quality."""
        items = [{'id': i} for i in range(100)]

        batches = self.service.adaptive_batch_sizing(items, network_quality='excellent')

        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 100)

    def test_prioritize_items_sorting(self):
        """Test item prioritization by priority field."""
        items = [
            {'id': 1, 'priority': 'low'},
            {'id': 2, 'priority': 'high'},
            {'id': 3, 'priority': 'medium'},
            {'id': 4, 'priority': 'high'},
        ]

        prioritized = self.service.prioritize_items(items)

        self.assertEqual(prioritized[0]['priority'], 'high')
        self.assertEqual(prioritized[1]['priority'], 'high')
        self.assertEqual(prioritized[2]['priority'], 'medium')
        self.assertEqual(prioritized[3]['priority'], 'low')

    def test_compression_ratio_threshold(self):
        """Test compression is skipped if not beneficial."""
        incompressible_data = {
            'random': ''.join([chr(i % 256) for i in range(2000)])
        }

        result = self.service.compress_payload(
            incompressible_data,
            compression_level='adaptive'
        )

        self.assertTrue(result['compression_ratio'] >= self.service.MIN_COMPRESSION_RATIO or not result['compressed'])


@pytest.mark.integration
class TestBandwidthOptimizationIntegration(TestCase):
    """Integration tests for bandwidth optimization."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = BandwidthOptimizationService()

    def test_end_to_end_optimization_workflow(self):
        """Test complete optimization workflow."""
        items = [
            {'id': i, 'priority': 'high' if i < 10 else 'low', 'data': 'x' * 50}
            for i in range(50)
        ]

        prioritized = self.service.prioritize_items(items)

        batches = self.service.adaptive_batch_sizing(prioritized, network_quality='good')

        compressed_batches = []
        for batch in batches:
            result = self.service.compress_payload({'batch': batch}, compression_level='adaptive')
            compressed_batches.append(result)

        self.assertEqual(len(batches), 1)
        self.assertTrue(compressed_batches[0]['compressed'])

    def test_delta_sync_reduces_payload_size(self):
        """Test delta sync significantly reduces payload size."""
        server_version = {
            'mobile_id': 'uuid-123',
            'version': 5,
            'field1': 'value1',
            'field2': 'value2',
            'field3': 'value3',
            'field4': 'value4',
            'field5': 'value5',
        }

        client_version = {
            **server_version,
            'version': 6,
            'field1': 'new_value1',
        }

        delta = self.service.calculate_delta(server_version, client_version)

        self.assertEqual(delta['fields_changed'], 1)
        delta_size = len(json.dumps(delta))
        full_size = len(json.dumps(client_version))

        self.assertLess(delta_size, full_size)