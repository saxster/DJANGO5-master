from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.ontology.registry import OntologyRegistry


@override_settings(
    ONTOLOGY_REGISTRY_CACHE_ENABLED=True,
    ONTOLOGY_REGISTRY_CACHE_KEY="test.registry.snapshot",
)
class OntologyRegistryCacheTests(TestCase):
    def tearDown(self):
        OntologyRegistry.clear()
        OntologyRegistry._instance = None  # Reset singleton for other tests
        cache.delete("test.registry.snapshot")

    def test_registry_warms_from_cache_without_reloading_registrations(self):
        OntologyRegistry.clear()

        OntologyRegistry.register(
            "apps.sample.Component",
            {
                "qualified_name": "apps.sample.Component",
                "domain": "testing",
                "tags": ["unit-test"],
                "type": "function",
            },
        )

        self.assertIsNotNone(cache.get("test.registry.snapshot"))

        OntologyRegistry._instance = None

        with mock.patch(
            "apps.ontology.registry.load_all_registrations"
        ) as mock_loader:
            registry = OntologyRegistry()
            metadata = registry.get("apps.sample.Component")

        mock_loader.assert_not_called()
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["domain"], "testing")
