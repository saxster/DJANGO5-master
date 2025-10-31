"""
Central registry for ontology metadata.

The OntologyRegistry maintains a thread-safe collection of all metadata
about code components in the system. It provides methods for querying,
filtering, and exporting this metadata.
"""

import json
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class OntologyRegistry:
    """
    Thread-safe singleton registry for ontology metadata.

    This class maintains a central collection of all ontology metadata
    registered through the @ontology decorator or extracted via AST analysis.
    """

    _instance = None
    _lock = threading.Lock()

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
            # Store the metadata
            instance._metadata[qualified_name] = metadata

            # Index by domain
            if metadata.get("domain"):
                instance._by_domain[metadata["domain"]].add(qualified_name)

            # Index by tags
            for tag in metadata.get("tags", []):
                instance._by_tag[tag].add(qualified_name)

            # Index by type (function, class, etc.)
            if metadata.get("type"):
                instance._by_type[metadata["type"]].add(qualified_name)

            # Index by module
            if metadata.get("module"):
                instance._by_module[metadata["module"]].add(qualified_name)

            # Track deprecated items
            if metadata.get("deprecated"):
                instance._deprecated.add(qualified_name)

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
                    cls.register(qualified_name, item)
