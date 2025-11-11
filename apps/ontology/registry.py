"""
Central registry for ontology metadata.

The OntologyRegistry maintains a thread-safe collection of all metadata
about code components in the system. It provides methods for querying,
filtering, and exporting this metadata.
"""

import json
import logging
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OntologyRegistry:
    """
    Thread-safe singleton registry for ontology metadata.

    This class maintains a central collection of all ontology metadata
    registered through the @ontology decorator or extracted via AST analysis.
    """

    _instance = None
    _lock = threading.Lock()
    _CACHE_DEFAULT_KEY = "apps.ontology.registry.snapshot"

    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the registry data structures."""
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._by_domain: Dict[str, Set[str]] = defaultdict(set)
        self._by_tag: Dict[str, Set[str]] = defaultdict(set)
        self._by_type: Dict[str, Set[str]] = defaultdict(set)
        self._by_module: Dict[str, Set[str]] = defaultdict(set)
        self._deprecated: Set[str] = set()
        self._lock = threading.RLock()
        self._auto_warm_attempted = False
        self._warm_from_cache_or_source()

    @classmethod
    def register(cls, qualified_name: str, metadata: Dict[str, Any]) -> None:
        """
        Register a code component with its metadata.

        Args:
            qualified_name: Fully qualified name (e.g., "apps.core.utils.format_date")
            metadata: Dictionary of metadata about the component
        """
        instance = cls()
        with instance._lock:
            instance._register_unlocked(qualified_name, metadata)
            instance._persist_snapshot_locked()

    def _register_unlocked(self, qualified_name: str, metadata: Dict[str, Any]) -> None:
        """Internal helper that assumes the caller already holds ``self._lock``."""
        # Store the metadata
        self._metadata[qualified_name] = metadata

        # Index by domain
        if metadata.get("domain"):
            self._by_domain[metadata["domain"]].add(qualified_name)

        # Index by tags
        for tag in metadata.get("tags", []):
            self._by_tag[tag].add(qualified_name)

        # Index by type (function, class, etc.)
        if metadata.get("type"):
            self._by_type[metadata["type"]].add(qualified_name)

        # Index by module
        if metadata.get("module"):
            self._by_module[metadata["module"]].add(qualified_name)

        # Track deprecated items
        if metadata.get("deprecated"):
            self._deprecated.add(qualified_name)

    @classmethod
    def get(cls, qualified_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata for a specific component.

        Args:
            qualified_name: Fully qualified name of the component

        Returns:
            Metadata dictionary or None if not found
        """
        instance = cls()
        with instance._lock:
            return instance._metadata.get(qualified_name)

    @classmethod
    def get_by_domain(cls, domain: str) -> List[Dict[str, Any]]:
        """
        Get all components in a specific domain.

        Args:
            domain: Domain name (e.g., "authentication")

        Returns:
            List of metadata dictionaries
        """
        instance = cls()
        with instance._lock:
            qualified_names = instance._by_domain.get(domain, set())
            return [instance._metadata[name] for name in qualified_names if name in instance._metadata]

    @classmethod
    def get_by_tag(cls, tag: str) -> List[Dict[str, Any]]:
        """
        Get all components with a specific tag.

        Args:
            tag: Tag name (e.g., "security")

        Returns:
            List of metadata dictionaries
        """
        instance = cls()
        with instance._lock:
            qualified_names = instance._by_tag.get(tag, set())
            return [instance._metadata[name] for name in qualified_names if name in instance._metadata]

    @classmethod
    def get_by_type(cls, code_type: str) -> List[Dict[str, Any]]:
        """
        Get all components of a specific type.

        Args:
            code_type: Type name (e.g., "function", "class")

        Returns:
            List of metadata dictionaries
        """
        instance = cls()
        with instance._lock:
            qualified_names = instance._by_type.get(code_type, set())
            return [instance._metadata[name] for name in qualified_names if name in instance._metadata]

    @classmethod
    def get_by_module(cls, module: str) -> List[Dict[str, Any]]:
        """
        Get all components in a specific module.

        Args:
            module: Module name (e.g., "apps.core.utils")

        Returns:
            List of metadata dictionaries
        """
        instance = cls()
        with instance._lock:
            qualified_names = instance._by_module.get(module, set())
            return [instance._metadata[name] for name in qualified_names if name in instance._metadata]

    @classmethod
    def get_deprecated(cls) -> List[Dict[str, Any]]:
        """
        Get all deprecated components.

        Returns:
            List of metadata dictionaries for deprecated components
        """
        instance = cls()
        with instance._lock:
            return [instance._metadata[name] for name in instance._deprecated if name in instance._metadata]

    @classmethod
    def search(cls, query: str, fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for components matching a text query.

        Args:
            query: Search query string
            fields: Optional list of fields to search in (default: all text fields)

        Returns:
            List of matching metadata dictionaries
        """
        instance = cls()
        if fields is None:
            fields = ["name", "qualified_name", "purpose", "docstring", "domain"]

        query_lower = query.lower()
        results = []

        with instance._lock:
            for metadata in instance._metadata.values():
                for field in fields:
                    value = metadata.get(field)
                    if value and isinstance(value, str) and query_lower in value.lower():
                        results.append(metadata)
                        break

        return results

    @classmethod
    def get_all(cls) -> List[Dict[str, Any]]:
        """
        Get all registered metadata.

        Returns:
            List of all metadata dictionaries
        """
        instance = cls()
        with instance._lock:
            return list(instance._metadata.values())

    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """
        Get statistics about the registered ontology.

        Returns:
            Dictionary with various statistics
        """
        instance = cls()
        with instance._lock:
            return {
                "total_components": len(instance._metadata),
                "by_type": {
                    code_type: len(names) for code_type, names in instance._by_type.items()
                },
                "by_domain": {domain: len(names) for domain, names in instance._by_domain.items()},
                "domains": list(instance._by_domain.keys()),
                "tags": list(instance._by_tag.keys()),
                "modules": list(instance._by_module.keys()),
                "deprecated_count": len(instance._deprecated),
            }

    @classmethod
    def export_json(cls, output_path: Path) -> None:
        """
        Export all metadata to a JSON file.

        Args:
            output_path: Path where JSON file should be written
        """
        instance = cls()
        with instance._lock:
            data = {
                "metadata": instance._metadata,
                "statistics": instance.get_statistics(),
            }

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered metadata.

        Warning: This is primarily for testing. Use with caution.
        """
        instance = cls()
        with instance._lock:
            instance._metadata.clear()
            instance._by_domain.clear()
            instance._by_tag.clear()
            instance._by_type.clear()
            instance._by_module.clear()
            instance._deprecated.clear()
            instance._persist_snapshot_locked()

    @classmethod
    def bulk_register(cls, items: List[Dict[str, Any]]) -> None:
        """
        Register multiple components at once.

        Args:
            items: List of dictionaries, each containing 'qualified_name' and metadata
        """
        instance = cls()
        with instance._lock:
            for item in items:
                qualified_name = item.get("qualified_name")
                if qualified_name:
                    instance._register_unlocked(qualified_name, item)
            instance._persist_snapshot_locked()

    # -- Internal helpers -------------------------------------------------

    def _warm_from_cache_or_source(self) -> None:
        """Ensure the registry has data either from cache or by reloading registrations."""
        if self._load_snapshot_from_cache():
            return
        self._warm_from_registrations()

    def _load_snapshot_from_cache(self) -> bool:
        """Attempt to hydrate the registry from the shared cache snapshot."""
        if not self._cache_available():
            return False

        cache_key = self._get_setting('ONTOLOGY_REGISTRY_CACHE_KEY', self._CACHE_DEFAULT_KEY)
        try:
            snapshot = cache.get(cache_key)
        except Exception as exc:  # pragma: no cover - defensive logging for cache errors
            logger.debug("Unable to read ontology registry cache snapshot: %s", exc)
            return False

        if not snapshot:
            return False

        with self._lock:
            self._apply_snapshot(snapshot)
        return True

    def _warm_from_registrations(self) -> None:
        """Load data by executing the registration modules when cache is empty."""
        if self._auto_warm_attempted:
            return
        self._auto_warm_attempted = True

        if not self._get_setting('ONTOLOGY_REGISTRY_AUTO_WARM', True):
            return

        try:
            from apps.ontology.registrations import load_all_registrations
        except ImportError as exc:
            logger.warning("Unable to auto-load ontology registrations: %s", exc)
            return

        load_all_registrations()

    def _persist_snapshot_locked(self) -> None:
        """Persist the in-memory snapshot so other processes can reuse it."""
        if not self._cache_available():
            return

        timeout = self._get_setting('ONTOLOGY_REGISTRY_CACHE_TIMEOUT', 3600)
        cache_key = self._get_setting('ONTOLOGY_REGISTRY_CACHE_KEY', self._CACHE_DEFAULT_KEY)
        snapshot = self._build_snapshot()

        try:
            cache.set(cache_key, snapshot, timeout)
        except Exception as exc:  # pragma: no cover - defensive logging for cache errors
            logger.warning("Failed to persist ontology registry snapshot: %s", exc)

    def _build_snapshot(self) -> Dict[str, Any]:
        """
        Create a serializable representation of the registry state.

        Note: Filters out unpicklable lambda functions from metadata before caching.
        The _lazy_source_loader lambda (added in decorators.py for lazy source loading)
        cannot be pickled by Django cache, so we exclude it from the snapshot.

        The lambda is kept in memory for runtime use but excluded from persistence.
        This allows the registry to warm from cache on worker startup.
        """
        # Filter out unpicklable lambdas from metadata
        serializable_metadata = {}
        for key, value in self._metadata.items():
            # Create a copy of the metadata dict without the lambda
            if isinstance(value, dict) and '_lazy_source_loader' in value:
                # Clone metadata entry without the lambda
                filtered_entry = {k: v for k, v in value.items() if k != '_lazy_source_loader'}
                serializable_metadata[key] = filtered_entry
            else:
                serializable_metadata[key] = value

        return {
            "metadata": serializable_metadata,
            "by_domain": {key: set(values) for key, values in self._by_domain.items()},
            "by_tag": {key: set(values) for key, values in self._by_tag.items()},
            "by_type": {key: set(values) for key, values in self._by_type.items()},
            "by_module": {key: set(values) for key, values in self._by_module.items()},
            "deprecated": set(self._deprecated),
        }

    def _apply_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Replace the current state with the provided snapshot."""
        def _coerce(mapping: Optional[Dict[str, Set[str]]]) -> defaultdict:
            target = defaultdict(set)
            if mapping:
                for key, values in mapping.items():
                    target[key] = set(values)
            return target

        self._metadata = dict(snapshot.get("metadata", {}))
        self._by_domain = _coerce(snapshot.get("by_domain"))
        self._by_tag = _coerce(snapshot.get("by_tag"))
        self._by_type = _coerce(snapshot.get("by_type"))
        self._by_module = _coerce(snapshot.get("by_module"))
        self._deprecated = set(snapshot.get("deprecated", set()))

    def _cache_available(self) -> bool:
        """Return True when the cache backend can be used for sharing snapshots."""
        if not getattr(settings, "configured", False):
            return False
        return self._get_setting('ONTOLOGY_REGISTRY_CACHE_ENABLED', True)

    @staticmethod
    def _get_setting(name: str, default: Any) -> Any:
        """Safely read Django settings with a default when the project isn't configured yet."""
        if not getattr(settings, "configured", False):
            return default
        return getattr(settings, name, default)
