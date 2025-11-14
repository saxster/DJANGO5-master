import hashlib
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.core.cache_manager import TreeCache, CacheManager


class TreeCacheKeyGenerationTests(SimpleTestCase):
    """Tests for deterministic cache key generation in TreeCache."""

    def _create_dummy_model(self):
        return SimpleNamespace(_meta=SimpleNamespace(label_lower='dummy.model'))

    def test_identical_filters_generate_same_cache_key(self):
        tree_cache_one = TreeCache(self._create_dummy_model())
        tree_cache_two = TreeCache(self._create_dummy_model())

        filters_first = {'tenant': 5, 'status': 'active'}
        filters_second = {'status': 'active', 'tenant': 5}

        with mock.patch('apps.core.cache_manager.cache.get', side_effect=[None, None]), \
                mock.patch('apps.core.cache_manager.cache.set') as mock_set, \
                mock.patch.object(TreeCache, '_build_tree', return_value=[]):
            tree_cache_one.get_or_build_tree(root_id=1, filter_kwargs=filters_first)
            tree_cache_two.get_or_build_tree(root_id=1, filter_kwargs=filters_second)

        self.assertEqual(mock_set.call_count, 2)
        first_key = mock_set.call_args_list[0][0][0]
        second_key = mock_set.call_args_list[1][0][0]

        expected_digest = hashlib.sha256(
            json.dumps(filters_first, sort_keys=True, default=str).encode('utf-8')
        ).hexdigest()
        expected_key = f"tree:dummy.model:1:{expected_digest}"

        self.assertEqual(first_key, second_key)
        self.assertEqual(first_key, expected_key)

    def test_empty_filters_use_nofilter_token(self):
        tree_cache = TreeCache(self._create_dummy_model())

        with mock.patch('apps.core.cache_manager.cache.get', side_effect=[None, None]), \
                mock.patch('apps.core.cache_manager.cache.set') as mock_set, \
                mock.patch.object(TreeCache, '_build_tree', return_value=[]):
            tree_cache.get_or_build_tree(root_id=None, filter_kwargs=None)
            tree_cache.get_or_build_tree(root_id=None, filter_kwargs={})

        first_key = mock_set.call_args_list[0][0][0]
        second_key = mock_set.call_args_list[1][0][0]

        self.assertTrue(first_key.endswith(':nofilter'))
        self.assertEqual(first_key, second_key)

    def test_invalidation_uses_cache_prefix(self):
        tree_cache = TreeCache(self._create_dummy_model())

        with mock.patch.object(CacheManager, 'invalidate_pattern') as mock_invalidate:
            tree_cache.invalidate()

        mock_invalidate.assert_called_once_with('tree:dummy.model')
