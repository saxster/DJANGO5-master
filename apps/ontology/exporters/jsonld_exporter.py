"""
JSON-LD exporter for ontology metadata.

Exports ontology data in JSON-LD format for semantic web integration
and enhanced LLM understanding.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from django.utils import timezone
from apps.ontology.registry import OntologyRegistry


class JSONLDExporter:
    """
    Export ontology metadata as JSON-LD.

    JSON-LD (JavaScript Object Notation for Linked Data) is a method of
    encoding linked data using JSON. This format is ideal for:
    - Semantic web applications
    - LLM context enhancement
    - Knowledge graph construction
    - Cross-system integration
    """

    CONTEXT = {
        "@vocab": "http://schema.org/",
        "ontology": "http://intelliwiz.example.com/ontology#",
        "code": "http://intelliwiz.example.com/code#",
        "domain": "ontology:domain",
        "purpose": "ontology:purpose",
        "qualified_name": "code:qualifiedName",
        "source_file": "code:sourceFile",
        "source_line": "code:sourceLine",
        "inputs": "ontology:inputs",
        "outputs": "ontology:outputs",
        "side_effects": "ontology:sideEffects",
        "depends_on": "ontology:dependsOn",
        "used_by": "ontology:usedBy",
        "tags": "keywords",
        "deprecated": "ontology:deprecated",
        "security_notes": "ontology:securityNotes",
        "performance_notes": "ontology:performanceNotes",
    }

    @classmethod
    def export(cls, output_path: Path, include_context: bool = True) -> None:
        """
        Export ontology metadata to JSON-LD format.

        Args:
            output_path: Path where JSON-LD file should be written
            include_context: Whether to include @context (default: True)
        """
        # Get all metadata from registry
        all_metadata = OntologyRegistry.get_all()
        stats = OntologyRegistry.get_statistics()

        # Build JSON-LD document
        document = {
            "@context": cls.CONTEXT if include_context else None,
            "@type": "SoftwareSourceCode",
            "name": "IntelliWiz Django Application",
            "description": "Ontology metadata for IntelliWiz facility management platform",
            "programmingLanguage": "Python",
            "runtimePlatform": "Django",
            "dateModified": timezone.now().isoformat(),
            "codeRepository": "https://github.com/yourusername/intelliwiz",
            "hasPart": cls._convert_to_jsonld(all_metadata),
            "statistics": stats,
        }

        # Remove @context if not included
        if not include_context:
            del document["@context"]

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, default=str)

    @classmethod
    def _convert_to_jsonld(cls, metadata_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert metadata to JSON-LD format.

        Args:
            metadata_list: List of metadata dictionaries

        Returns:
            List of JSON-LD compatible dictionaries
        """
        jsonld_items = []

        for item in metadata_list:
            jsonld_item = {
                "@type": cls._map_type(item.get("type")),
                "@id": f"code:{item.get('qualified_name', 'unknown')}",
                "name": item.get("name"),
                "identifier": item.get("qualified_name"),
                "description": item.get("purpose") or item.get("docstring"),
            }

            # Add optional fields
            if item.get("domain"):
                jsonld_item["domain"] = item["domain"]

            if item.get("tags"):
                jsonld_item["keywords"] = item["tags"]

            if item.get("source_file"):
                jsonld_item["codeLocation"] = {
                    "file": item["source_file"],
                    "line": item.get("source_line"),
                }

            if item.get("deprecated"):
                jsonld_item["deprecated"] = True
                if item.get("replacement"):
                    jsonld_item["replacedBy"] = item["replacement"]

            # Add custom ontology fields
            ontology_fields = {}
            for field in ["inputs", "outputs", "side_effects", "depends_on", "used_by"]:
                if item.get(field):
                    ontology_fields[field] = item[field]

            if item.get("security_notes"):
                ontology_fields["security_notes"] = item["security_notes"]

            if item.get("performance_notes"):
                ontology_fields["performance_notes"] = item["performance_notes"]

            if ontology_fields:
                jsonld_item["ontologyMetadata"] = ontology_fields

            jsonld_items.append(jsonld_item)

        return jsonld_items

    @staticmethod
    def _map_type(code_type: str) -> str:
        """
        Map internal types to schema.org types.

        Args:
            code_type: Internal type string

        Returns:
            Schema.org type string
        """
        type_mapping = {
            "function": "SoftwareSourceCode",
            "class": "SoftwareSourceCode",
            "model": "Class",
            "viewset": "WebAPI",
            "apiview": "WebAPI",
            "serializer": "DataFeed",
            "celery_task": "Action",
            "security_pattern": "SecurityAction",
        }

        return type_mapping.get(code_type, "SoftwareSourceCode")

    @classmethod
    def export_for_llm(cls, output_path: Path) -> None:
        """
        Export ontology in LLM-optimized format.

        This creates a simplified, hierarchical format optimized for
        LLM context windows.

        Args:
            output_path: Path where LLM-optimized JSON should be written
        """
        all_metadata = OntologyRegistry.get_all()
        stats = OntologyRegistry.get_statistics()

        # Group by domain
        by_domain = {}
        for item in all_metadata:
            domain = item.get("domain", "general")
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(cls._simplify_for_llm(item))

        # Build LLM-optimized document
        document = {
            "summary": {
                "total_components": stats["total_components"],
                "by_type": stats["by_type"],
                "domains": list(stats["domains"]),
                "deprecated_count": stats["deprecated_count"],
            },
            "domains": by_domain,
            "index": {
                item["qualified_name"]: {
                    "domain": item.get("domain"),
                    "type": item.get("type"),
                    "purpose": item.get("purpose", "")[:100],  # Truncate for index
                }
                for item in all_metadata
            },
        }

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, default=str)

    @staticmethod
    def _simplify_for_llm(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simplify metadata for LLM consumption.

        Args:
            item: Full metadata dictionary

        Returns:
            Simplified dictionary with essential fields
        """
        simplified = {
            "name": item.get("name"),
            "qualified_name": item.get("qualified_name"),
            "type": item.get("type"),
            "purpose": item.get("purpose") or item.get("docstring", "")[:200],
        }

        # Add important optional fields
        if item.get("inputs"):
            simplified["inputs"] = [inp.get("name") for inp in item["inputs"] if isinstance(inp, dict)]

        if item.get("outputs"):
            simplified["outputs"] = item["outputs"]

        if item.get("side_effects"):
            simplified["side_effects"] = item["side_effects"]

        if item.get("tags"):
            simplified["tags"] = item["tags"]

        if item.get("deprecated"):
            simplified["deprecated"] = True
            simplified["replacement"] = item.get("replacement")

        if item.get("security_notes"):
            simplified["security"] = item["security_notes"][:100]

        return simplified
