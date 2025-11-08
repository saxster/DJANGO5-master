"""
Query API for Claude Code and other AI assistants.

Provides natural language and structured queries for ontology metadata.
"""

import logging
from typing import Any, Dict, List, Optional

from apps.ontology.registry import OntologyRegistry

logger = logging.getLogger(__name__)


class OntologyQueryAPI:
    """
    High-level query API for ontology metadata.

    Designed specifically for LLM consumption with natural language
    query support and context-optimized responses.
    """

    @staticmethod
    def find_by_purpose(query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Find components by purpose or functionality.

        Args:
            query: Natural language query (e.g., "authentication")
            limit: Maximum number of results

        Returns:
            List of relevant component metadata

        Example:
            >>> results = OntologyQueryAPI.find_by_purpose("user login")
            >>> for item in results:
            ...     logger.info(f"{item['name']}: {item['purpose']}")
        """
        results = OntologyRegistry.search(query, fields=["purpose", "docstring", "name"])
        return results[:limit]

    @staticmethod
    def find_by_domain(domain: str) -> List[Dict[str, Any]]:
        """
        Get all components in a specific domain.

        Args:
            domain: Domain name (e.g., "authentication", "api")

        Returns:
            List of component metadata in the domain

        Example:
            >>> auth_components = OntologyQueryAPI.find_by_domain("authentication")
        """
        return OntologyRegistry.get_by_domain(domain)

    @staticmethod
    def find_related(qualified_name: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find components related to a specific component.

        Args:
            qualified_name: Fully qualified name (e.g., "apps.core.utils.format_date")

        Returns:
            Dictionary with 'dependencies' and 'dependents'

        Example:
            >>> related = OntologyQueryAPI.find_related("apps.peoples.models.People")
            >>> logger.info(f"Used by: {related['dependents']}")
        """
        component = OntologyRegistry.get(qualified_name)

        if not component:
            return {"dependencies": [], "dependents": []}

        # Find dependencies
        depends_on = component.get("depends_on", [])
        dependencies = [
            OntologyRegistry.get(dep) for dep in depends_on if OntologyRegistry.get(dep)
        ]

        # Find dependents (components that use this one)
        used_by = component.get("used_by", [])
        dependents = [
            OntologyRegistry.get(dep) for dep in used_by if OntologyRegistry.get(dep)
        ]

        return {"dependencies": dependencies, "dependents": dependents}

    @staticmethod
    def get_component_details(qualified_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete details about a specific component.

        Args:
            qualified_name: Fully qualified name

        Returns:
            Component metadata or None if not found

        Example:
            >>> details = OntologyQueryAPI.get_component_details("apps.core.utils.format_date")
            >>> logger.info(details['purpose'])
        """
        return OntologyRegistry.get(qualified_name)

    @staticmethod
    def find_security_sensitive() -> List[Dict[str, Any]]:
        """
        Find all security-sensitive components.

        Returns:
            List of components with security implications

        Example:
            >>> sensitive = OntologyQueryAPI.find_security_sensitive()
            >>> for item in sensitive:
            ...     logger.info(f"{item['name']}: {item.get('security_notes')}")
        """
        return OntologyRegistry.get_by_tag("security")

    @staticmethod
    def find_deprecated() -> List[Dict[str, Any]]:
        """
        Find all deprecated components.

        Returns:
            List of deprecated components with replacement info

        Example:
            >>> deprecated = OntologyQueryAPI.find_deprecated()
            >>> for item in deprecated:
            ...     logger.info(f"{item['name']} -> use {item.get('replacement')}")
        """
        return OntologyRegistry.get_deprecated()

    @staticmethod
    def get_api_endpoints() -> List[Dict[str, Any]]:
        """
        Get all REST API endpoints.

        Returns:
            List of API endpoint metadata

        Example:
            >>> endpoints = OntologyQueryAPI.get_api_endpoints()
            >>> for ep in endpoints:
            ...     logger.info(f"{ep['name']}: {ep.get('http_methods')}")
        """
        viewsets = OntologyRegistry.get_by_type("viewset")
        apiviews = OntologyRegistry.get_by_type("apiview")
        return viewsets + apiviews

    @staticmethod
    def get_models() -> List[Dict[str, Any]]:
        """
        Get all Django models.

        Returns:
            List of model metadata

        Example:
            >>> models = OntologyQueryAPI.get_models()
            >>> for model in models:
            ...     logger.info(f"{model['name']}: {len(model.get('fields', []))} fields")
        """
        return OntologyRegistry.get_by_type("model")

    @staticmethod
    def get_background_tasks() -> List[Dict[str, Any]]:
        """
        Get all Celery tasks.

        Returns:
            List of Celery task metadata

        Example:
            >>> tasks = OntologyQueryAPI.get_background_tasks()
            >>> for task in tasks:
            ...     logger.info(f"{task['name']}: {task.get('task_queue')}")
        """
        return OntologyRegistry.get_by_type("celery_task")

    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        """
        Get comprehensive statistics about the ontology.

        Returns:
            Dictionary with various statistics

        Example:
            >>> stats = OntologyQueryAPI.get_statistics()
            >>> logger.info(f"Total: {stats['total_components']}")
            >>> logger.info(f"Domains: {', '.join(stats['domains'])}")
        """
        return OntologyRegistry.get_statistics()

    @staticmethod
    def suggest_for_task(task_description: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Suggest components relevant to a task.

        Uses semantic search to find components that might be useful
        for a given development task.

        Args:
            task_description: Natural language task description
            limit: Maximum number of suggestions

        Returns:
            List of suggested components with relevance scores

        Example:
            >>> suggestions = OntologyQueryAPI.suggest_for_task(
            ...     "implement user password reset"
            ... )
            >>> for item in suggestions:
            ...     logger.info(f"{item['name']}: {item['purpose']}")
        """
        # Simple keyword-based matching (can be enhanced with embeddings)
        keywords = task_description.lower().split()

        results = []
        for keyword in keywords:
            matches = OntologyRegistry.search(keyword)
            results.extend(matches)

        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for item in results:
            qname = item.get("qualified_name")
            if qname and qname not in seen:
                seen.add(qname)
                unique_results.append(item)

        return unique_results[:limit]

    @staticmethod
    def get_domain_summary(domain: str) -> Dict[str, Any]:
        """
        Get a summary of a specific domain.

        Args:
            domain: Domain name

        Returns:
            Dictionary with domain statistics and key components

        Example:
            >>> summary = OntologyQueryAPI.get_domain_summary("authentication")
            >>> logger.info(f"Components: {summary['count']}")
            >>> logger.info(f"Key components: {summary['key_components']}")
        """
        components = OntologyRegistry.get_by_domain(domain)

        # Group by type
        by_type = {}
        for comp in components:
            comp_type = comp.get("type", "unknown")
            if comp_type not in by_type:
                by_type[comp_type] = []
            by_type[comp_type].append(comp)

        # Identify key components (those with many dependents)
        key_components = [
            {
                "name": comp["name"],
                "qualified_name": comp["qualified_name"],
                "purpose": comp.get("purpose", "")[:100],
            }
            for comp in components[:5]  # Top 5 for now
        ]

        return {
            "domain": domain,
            "count": len(components),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "key_components": key_components,
        }

    @staticmethod
    def format_for_llm_context(qualified_name: str, include_related: bool = True) -> str:
        """
        Format component metadata for LLM context.

        Creates a compact, human-readable representation optimized
        for LLM consumption.

        Args:
            qualified_name: Component to format
            include_related: Whether to include related components

        Returns:
            Formatted string suitable for LLM context

        Example:
            >>> context = OntologyQueryAPI.format_for_llm_context(
            ...     "apps.peoples.models.People",
            ...     include_related=True
            ... )
            >>> logger.info(context)
        """
        component = OntologyRegistry.get(qualified_name)

        if not component:
            return f"Component not found: {qualified_name}"

        lines = [
            f"# {component.get('name')} ({component.get('type')})",
            f"**Location**: `{component.get('qualified_name')}`",
            f"**File**: {component.get('source_file')}:{component.get('source_line')}",
            "",
        ]

        if component.get("purpose"):
            lines.append(f"**Purpose**: {component['purpose']}")
            lines.append("")

        if component.get("domain"):
            lines.append(f"**Domain**: {component['domain']}")

        if component.get("tags"):
            lines.append(f"**Tags**: {', '.join(component['tags'])}")

        lines.append("")

        if component.get("inputs"):
            lines.append("**Inputs**:")
            for inp in component["inputs"]:
                if isinstance(inp, dict):
                    lines.append(f"  - `{inp.get('name')}` ({inp.get('type')}): {inp.get('description', '')}")

        if component.get("outputs"):
            lines.append("**Outputs**:")
            for out in component["outputs"]:
                if isinstance(out, dict):
                    lines.append(f"  - {out.get('description', '')}")

        if component.get("side_effects"):
            lines.append(f"**Side Effects**: {', '.join(component['side_effects'])}")

        if component.get("deprecated"):
            lines.append("")
            lines.append(f"**⚠️ DEPRECATED**: Use `{component.get('replacement')}` instead")

        if component.get("security_notes"):
            lines.append("")
            lines.append(f"**🔒 Security**: {component['security_notes']}")

        if include_related:
            related = OntologyQueryAPI.find_related(qualified_name)

            if related["dependencies"]:
                lines.append("")
                lines.append("**Dependencies**:")
                for dep in related["dependencies"][:5]:
                    lines.append(f"  - {dep['qualified_name']}")

            if related["dependents"]:
                lines.append("")
                lines.append("**Used By**:")
                for dep in related["dependents"][:5]:
                    lines.append(f"  - {dep['qualified_name']}")

        return "\n".join(lines)
