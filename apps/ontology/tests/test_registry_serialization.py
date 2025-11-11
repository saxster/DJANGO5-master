"""
Registry Snapshot Serialization Tests

Tests fix for Ultrathink Phase 4:
- Issue #4: Ontology decorator stores unpicklable lambda in cache

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Test Django cache serialization works without lambda

Note: Django cache uses pickle for serialization. These tests validate
that our snapshot filtering fix makes server-generated registry data
compatible with Django's cache backend (not testing user input).
"""

import pytest
from unittest.mock import patch, Mock
from django.test import TestCase
from django.core.cache import cache

from apps.ontology.registry import OntologyRegistry
from apps.ontology.decorators import ontology


class TestRegistrySnapshotSerialization(TestCase):
    """Test registry snapshot can be serialized by Django cache."""

    def setUp(self):
        """Initialize test fixtures."""
        self.registry = OntologyRegistry()

    def test_registry_snapshot_django_cache_compatible(self):
        """
        Test that _build_snapshot() returns Django-cache-compatible data.

        Issue #4: Previously included _lazy_source_loader lambda in metadata,
        causing Django cache serialization to fail and preventing cache warming.

        Fix: Filters out lambda from snapshot before caching.
        """
        # Register a test function with ontology decorator
        @ontology(domain="test", concept="Test Function")
        def test_function():
            pass

        # Build snapshot
        snapshot = self.registry._build_snapshot()

        # Should be compatible with Django cache (which uses pickle internally)
        # Let exceptions propagate naturally - if caching fails, test should fail
        cache.set('test_snapshot', snapshot, 60)
        retrieved = cache.get('test_snapshot')

        assert retrieved is not None, (
            "Snapshot should be Django-cache-compatible and retrievable"
        )

        # Clean up
        cache.delete('test_snapshot')

    def test_lambda_excluded_from_snapshot(self):
        """
        Test that _lazy_source_loader lambda is NOT in the snapshot.

        Validates that the filter logic correctly removes unpicklable lambdas
        from metadata before serialization.
        """
        # Create metadata with lambda (simulating decorator behavior)
        qualified_name = "test.module.test_function"
        self.registry._metadata[qualified_name] = {
            "domain": "test",
            "concept": "Test",
            "_lazy_source_loader": lambda: {"file": "test.py", "line": 10}
        }

        # Build snapshot
        snapshot = self.registry._build_snapshot()

        # Lambda should be excluded from snapshot
        metadata_entry = snapshot['metadata'].get(qualified_name, {})
        assert '_lazy_source_loader' not in metadata_entry, (
            "_lazy_source_loader lambda should be filtered out of snapshot"
        )

        # Other metadata should be preserved
        assert metadata_entry.get('domain') == 'test'
        assert metadata_entry.get('concept') == 'Test'

    def test_lambda_still_available_in_memory(self):
        """
        Test that lambda is still available in memory (not removed from _metadata).

        Validates that filtering only affects the snapshot, not the in-memory registry.
        The lambda is still usable at runtime for lazy source loading.
        """
        # Create metadata with lambda
        qualified_name = "test.module.test_function"
        test_lambda = lambda: {"file": "test.py", "line": 10}
        self.registry._metadata[qualified_name] = {
            "domain": "test",
            "_lazy_source_loader": test_lambda
        }

        # Build snapshot (should filter lambda)
        snapshot = self.registry._build_snapshot()

        # Lambda should still be in memory
        assert '_lazy_source_loader' in self.registry._metadata[qualified_name], (
            "Lambda should still be in memory after snapshot creation"
        )

        # Lambda should be callable
        result = self.registry._metadata[qualified_name]['_lazy_source_loader']()
        assert result == {"file": "test.py", "line": 10}

    def test_snapshot_without_lambda_is_complete(self):
        """
        Test that snapshot includes all other metadata fields correctly.

        Validates that lambda filtering doesn't accidentally remove
        other important metadata.
        """
        qualified_name = "test.module.complete_function"
        self.registry._metadata[qualified_name] = {
            "domain": "integration",
            "concept": "API Integration",
            "purpose": "Connects to external API",
            "type": "function",
            "qualified_name": qualified_name,
            "module": "test.module",
            "source_file": "/path/to/test.py",
            "source_line": 42,
            "_lazy_source_loader": lambda: None,  # Should be filtered
            "tags": ["api", "integration"]
        }

        snapshot = self.registry._build_snapshot()
        metadata_entry = snapshot['metadata'][qualified_name]

        # All fields present except lambda
        assert metadata_entry['domain'] == 'integration'
        assert metadata_entry['concept'] == 'API Integration'
        assert metadata_entry['purpose'] == 'Connects to external API'
        assert metadata_entry['type'] == 'function'
        assert metadata_entry['source_file'] == '/path/to/test.py'
        assert metadata_entry['source_line'] == 42
        assert metadata_entry['tags'] == ['api', 'integration']

        # Lambda excluded
        assert '_lazy_source_loader' not in metadata_entry

    def test_registry_cache_persistence_succeeds(self):
        """
        Test that registry can persist snapshot to Django cache without errors.

        Integration test: validates the full cache persistence flow works
        after lambda filtering fix.
        """
        with patch('apps.ontology.registry.cache') as mock_cache:
            # Register a function
            @ontology(domain="test", concept="Cache Test")
            def cacheable_function():
                pass

            # Persist snapshot (should not raise serialization error)
            # Let exceptions propagate naturally - if persistence fails, test should fail
            self.registry._persist_snapshot_locked()

            # Verify cache.set was called
            assert mock_cache.set.called, "cache.set should be called"

    def test_snapshot_with_non_dict_metadata(self):
        """
        Test that snapshot handles non-dict metadata entries gracefully.

        Edge case: validates filter logic doesn't break on unexpected
        metadata structures.
        """
        # Add various metadata types
        self.registry._metadata['string_key'] = "simple string"
        self.registry._metadata['int_key'] = 42
        self.registry._metadata['dict_without_lambda'] = {"field": "value"}
        self.registry._metadata['dict_with_lambda'] = {
            "field": "value",
            "_lazy_source_loader": lambda: None
        }

        # Should build snapshot without errors
        snapshot = self.registry._build_snapshot()

        # Verify all entries handled correctly
        assert snapshot['metadata']['string_key'] == "simple string"
        assert snapshot['metadata']['int_key'] == 42
        assert snapshot['metadata']['dict_without_lambda'] == {"field": "value"}
        assert '_lazy_source_loader' not in snapshot['metadata']['dict_with_lambda']
        assert snapshot['metadata']['dict_with_lambda']['field'] == "value"

    def test_empty_registry_snapshot_cacheable(self):
        """
        Test that empty registry produces cacheable snapshot.

        Validates base case: even with no registered items, snapshot is valid.
        """
        # Clear registry
        self.registry._metadata.clear()

        snapshot = self.registry._build_snapshot()

        # Should be cacheable in Django cache
        cache.set('empty_snapshot', snapshot, 60)
        retrieved = cache.get('empty_snapshot')

        assert retrieved is not None
        assert retrieved['metadata'] == {}
        assert 'by_domain' in retrieved
        assert 'by_tag' in retrieved

        # Clean up
        cache.delete('empty_snapshot')
