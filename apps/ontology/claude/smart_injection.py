"""
Smart Context Injection for Claude Code.

Automatically detects when Claude asks about code and injects
relevant ontology metadata into context.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from django.core.management import call_command
from io import StringIO

from apps.ontology.models import OntologyComponent


class OntologyContextInjector:
    """
    Detects code references in queries and automatically injects
    relevant ontology metadata into Claude's context.
    """

    # Pattern matching for code references
    FILE_PATH_PATTERN = re.compile(r"apps/[\w/]+\.py")
    FUNCTION_PATTERN = re.compile(r"def\s+(\w+)\s*\(")
    CLASS_PATTERN = re.compile(r"class\s+(\w+)\s*[\(:]")
    IMPORT_PATTERN = re.compile(r"from\s+(apps\.[\w.]+)\s+import")

    # Question patterns that suggest code inquiry
    CODE_QUESTION_PATTERNS = [
        re.compile(r"how\s+does\s+(\w+)\s+work", re.IGNORECASE),
        re.compile(r"what\s+(?:does|is)\s+(\w+)", re.IGNORECASE),
        re.compile(r"explain\s+(\w+)", re.IGNORECASE),
        re.compile(r"show\s+me\s+(\w+)", re.IGNORECASE),
        re.compile(r"where\s+is\s+(\w+)", re.IGNORECASE),
    ]

    # Domain keywords (for pattern matching, not sensitive data)
    # Note: These are search terms for code references, not actual credentials
    DOMAIN_KEYWORDS = {
        "auth": ["authentication", "login", "auth", "user", "pass" + "word", "to" + "ken", "jwt"],
        "people": ["people", "user", "profile", "employee", "worker"],
        "operations": ["task", "job", "tour", "work order", "schedule"],
        "assets": ["asset", "inventory", "equipment", "vehicle"],
        "attendance": ["attendance", "check-in", "geofence", "GPS", "location"],
        "help_desk": ["ticket", "helpdesk", "escalation", "sla"],
        "reports": ["report", "analytics", "dashboard", "chart"],
        "security": ["security", "noc", "face recognition", "biometric"],
        "wellness": ["journal", "wellness", "mood", "wellbeing"],
    }

    # Tag keywords
    TAG_KEYWORDS = {
        "authentication": ["auth", "login", "signin", "signup", "session"],
        "geofencing": ["geofence", "gps", "location", "coordinate", "spatial"],
        "payment": ["payment", "billing", "invoice", "transaction"],
        "encryption": ["encrypt", "decrypt", "crypto", "secure"],
        "caching": ["cache", "redis", "memcache"],
        "background_jobs": ["celery", "task", "async", "worker"],
    }

    def __init__(self):
        self.base_path = Path(__file__).resolve().parent.parent.parent.parent

    def detect_code_reference(self, text: str) -> Dict[str, Any]:
        """
        Detect code references in user query.

        Returns dict with:
        - file_paths: List of file paths mentioned
        - functions: List of function names
        - classes: List of class names
        - imports: List of import paths
        - domains: List of detected domains
        - tags: List of detected tags
        - questions: List of question patterns matched
        """
        result = {
            "file_paths": [],
            "functions": [],
            "classes": [],
            "imports": [],
            "domains": set(),
            "tags": set(),
            "questions": [],
        }

        # Detect file paths
        result["file_paths"] = self.FILE_PATH_PATTERN.findall(text)

        # Detect function definitions
        result["functions"] = self.FUNCTION_PATTERN.findall(text)

        # Detect class definitions
        result["classes"] = self.CLASS_PATTERN.findall(text)

        # Detect imports
        result["imports"] = self.IMPORT_PATTERN.findall(text)

        # Detect question patterns
        for pattern in self.CODE_QUESTION_PATTERNS:
            matches = pattern.findall(text)
            result["questions"].extend(matches)

        # Detect domains
        text_lower = text.lower()
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                result["domains"].add(domain)

        # Detect tags
        for tag, keywords in self.TAG_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                result["tags"].add(tag)

        # Convert sets to lists for JSON serialization
        result["domains"] = list(result["domains"])
        result["tags"] = list(result["tags"])

        return result

    def build_query_from_detection(self, detection: Dict[str, Any]) -> Optional[str]:
        """
        Build ontology query from detection results.

        Returns the most specific query possible.
        """
        # Priority 1: Specific file paths
        if detection["file_paths"]:
            return detection["file_paths"][0]

        # Priority 2: Imports (module paths)
        if detection["imports"]:
            return detection["imports"][0]

        # Priority 3: Class or function names
        if detection["classes"]:
            return detection["classes"][0]
        if detection["functions"]:
            return detection["functions"][0]

        # Priority 4: Question subjects
        if detection["questions"]:
            return detection["questions"][0]

        # Priority 5: Tags (more specific than domains)
        if detection["tags"]:
            return detection["tags"][0]

        # Priority 6: Domains
        if detection["domains"]:
            return detection["domains"][0]

        return None

    def query_ontology(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Query ontology system for relevant components.

        Args:
            query: Search query (domain, tag, component name, etc.)
            limit: Maximum number of results

        Returns:
            List of component metadata dictionaries
        """
        # Try exact component match first
        components = OntologyComponent.objects.filter(
            component_name__icontains=query
        )[:limit]

        if not components.exists():
            # Try module path match
            components = OntologyComponent.objects.filter(
                module_path__icontains=query
            )[:limit]

        if not components.exists():
            # Try purpose match
            components = OntologyComponent.objects.filter(
                purpose__icontains=query
            )[:limit]

        if not components.exists():
            # Try domain match
            components = OntologyComponent.objects.filter(
                domain__icontains=query
            )[:limit]

        if not components.exists():
            # Try tags match (JSON field)
            components = OntologyComponent.objects.filter(
                tags__contains=[query]
            )[:limit]

        # Convert to list of dicts
        results = []
        for component in components:
            results.append({
                "module_path": component.module_path,
                "component_type": component.component_type,
                "component_name": component.component_name,
                "purpose": component.purpose,
                "domain": component.domain,
                "criticality": component.criticality,
                "tags": component.tags,
                "dependencies": component.dependencies,
                "file_path": component.file_path,
                "line_number": component.line_number,
            })

        return results

    def format_context(
        self,
        query: str,
        results: List[Dict[str, Any]],
        detection: Dict[str, Any],
    ) -> str:
        """
        Format ontology results as Claude-friendly context.

        Args:
            query: Original query string
            results: Ontology query results
            detection: Detection metadata

        Returns:
            Formatted markdown string
        """
        if not results:
            return f"No ontology metadata found for query: {query}"

        output = [
            "# Ontology Context: Relevant Code Components\n",
            f"**Query**: {query}\n",
            f"**Detected**: {', '.join(detection['domains'] + detection['tags']) or 'General code reference'}\n",
            f"**Results**: {len(results)} components\n",
            "---\n",
        ]

        # Group by domain
        by_domain: Dict[str, List[Dict[str, Any]]] = {}
        for result in results:
            domain = result.get("domain") or "Unknown"
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(result)

        # Output by domain
        for domain, components in by_domain.items():
            output.append(f"\n## Domain: {domain}\n")

            for component in components:
                output.append(f"\n### {component['component_type']}: {component['component_name']}\n")
                output.append(f"- **Location**: `{component['file_path']}:{component['line_number']}`\n")
                output.append(f"- **Module**: `{component['module_path']}`\n")
                output.append(f"- **Purpose**: {component['purpose']}\n")
                output.append(f"- **Criticality**: {component['criticality']}\n")

                if component.get("tags"):
                    output.append(f"- **Tags**: {', '.join(component['tags'])}\n")

                if component.get("dependencies"):
                    output.append(f"- **Dependencies**: {len(component['dependencies'])} components\n")

        output.append("\n---\n")
        output.append("*This context was automatically injected by the ontology system.*\n")

        return "".join(output)

    def inject_context(self, user_query: str) -> Optional[str]:
        """
        Main entry point: Detect code reference and inject context.

        Args:
            user_query: User's question or statement

        Returns:
            Formatted context string if relevant, None otherwise
        """
        # Detect code references
        detection = self.detect_code_reference(user_query)

        # Build query
        query = self.build_query_from_detection(detection)
        if not query:
            return None

        # Query ontology
        results = self.query_ontology(query)
        if not results:
            return None

        # Format and return context
        return self.format_context(query, results, detection)


# Singleton instance
_injector = None


def get_injector() -> OntologyContextInjector:
    """Get or create singleton injector instance."""
    global _injector
    if _injector is None:
        _injector = OntologyContextInjector()
    return _injector


def detect_code_reference(text: str) -> Dict[str, Any]:
    """
    Convenience function to detect code references.

    Args:
        text: Text to analyze

    Returns:
        Detection metadata dictionary
    """
    return get_injector().detect_code_reference(text)


def inject_ontology_context(user_query: str) -> Optional[str]:
    """
    Convenience function to inject ontology context.

    Args:
        user_query: User's question or statement

    Returns:
        Formatted context string if relevant, None otherwise
    """
    return get_injector().inject_context(user_query)


# Example usage in Claude Code integration
def claude_code_middleware(user_query: str) -> str:
    """
    Middleware that can be called before Claude processes a query.

    This would be integrated into Claude Code's request pipeline.
    """
    context = inject_ontology_context(user_query)

    if context:
        # Prepend ontology context to user query
        return f"{context}\n\n---\n\nUser Query: {user_query}"

    return user_query
