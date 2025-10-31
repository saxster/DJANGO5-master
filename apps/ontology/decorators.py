"""
Decorators for marking code with semantic ontology metadata.

The @ontology decorator allows developers to annotate functions, classes,
and methods with structured metadata that describes their purpose, domain,
and relationships within the system.
"""

import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, Union

from apps.ontology.registry import OntologyRegistry


def ontology(
    *,
    domain: Optional[str] = None,
    purpose: Optional[str] = None,
    inputs: Optional[List[Dict[str, Any]]] = None,
    outputs: Optional[List[Dict[str, Any]]] = None,
    side_effects: Optional[List[str]] = None,
    depends_on: Optional[List[str]] = None,
    used_by: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    deprecated: bool = False,
    replacement: Optional[str] = None,
    security_notes: Optional[str] = None,
    performance_notes: Optional[str] = None,
    examples: Optional[List[str]] = None,
    **extra_metadata: Any,
) -> Callable:
    """
    Decorator to mark code with semantic ontology metadata.

    This decorator allows developers to annotate code with rich metadata
    that describes its purpose, relationships, and characteristics. The
    metadata is collected into a central registry for documentation,
    analysis, and LLM querying.

    Args:
        domain: The business domain (e.g., "authentication", "reporting")
        purpose: A clear description of what this code does
        inputs: List of input parameter descriptions
        outputs: List of output/return value descriptions
        side_effects: List of side effects (DB writes, API calls, etc.)
        depends_on: List of dependencies (modules, services, etc.)
        used_by: List of components that use this code
        tags: List of tags for categorization
        deprecated: Whether this code is deprecated
        replacement: If deprecated, what to use instead
        security_notes: Security considerations and requirements
        performance_notes: Performance characteristics and considerations
        examples: List of usage examples
        **extra_metadata: Additional custom metadata fields

    Returns:
        Decorated function or class with metadata attached

    Example:
        @ontology(
            domain="authentication",
            purpose="Validates user credentials and returns JWT token",
            inputs=[{"name": "username", "type": "str", "description": "User's email"}],
            outputs=[{"name": "token", "type": "str", "description": "JWT access token"}],
            side_effects=["Updates last_login timestamp in database"],
            tags=["security", "authentication", "jwt"],
            security_notes="Rate limited to 5 attempts per minute per IP"
        )
        def login_user(username: str, password: str) -> dict:
            pass
    """

    def decorator(func_or_class: Union[Callable, type]) -> Union[Callable, type]:
        """Inner decorator that processes the function or class."""

        # Collect metadata
        metadata = {
            "domain": domain,
            "purpose": purpose,
            "inputs": inputs or [],
            "outputs": outputs or [],
            "side_effects": side_effects or [],
            "depends_on": depends_on or [],
            "used_by": used_by or [],
            "tags": tags or [],
            "deprecated": deprecated,
            "replacement": replacement,
            "security_notes": security_notes,
            "performance_notes": performance_notes,
            "examples": examples or [],
        }

        # Add any extra metadata
        metadata.update(extra_metadata)

        # Get code location information
        try:
            source_file = inspect.getfile(func_or_class)
            source_line = inspect.getsourcelines(func_or_class)[1]
        except (TypeError, OSError):
            source_file = None
            source_line = None

        # Determine if this is a class or function
        is_class = inspect.isclass(func_or_class)
        code_type = "class" if is_class else "function"

        # Get the full qualified name
        module = inspect.getmodule(func_or_class)
        if module:
            qualified_name = f"{module.__name__}.{func_or_class.__qualname__}"
        else:
            qualified_name = func_or_class.__qualname__

        # Add code location metadata
        metadata.update(
            {
                "type": code_type,
                "qualified_name": qualified_name,
                "name": func_or_class.__name__,
                "module": module.__name__ if module else None,
                "source_file": source_file,
                "source_line": source_line,
            }
        )

        # Extract docstring
        docstring = inspect.getdoc(func_or_class)
        if docstring:
            metadata["docstring"] = docstring

        # Register with the ontology registry
        OntologyRegistry.register(qualified_name, metadata)

        # Attach metadata to the function/class for runtime access
        func_or_class.__ontology_metadata__ = metadata

        # If it's a function, wrap it to preserve functionality
        if not is_class:

            @functools.wraps(func_or_class)
            def wrapper(*args, **kwargs):
                return func_or_class(*args, **kwargs)

            # Preserve the metadata on the wrapper
            wrapper.__ontology_metadata__ = metadata
            return wrapper

        # If it's a class, return it as-is with metadata attached
        return func_or_class

    return decorator


def get_ontology_metadata(func_or_class: Union[Callable, type]) -> Optional[Dict[str, Any]]:
    """
    Retrieve ontology metadata from a decorated function or class.

    Args:
        func_or_class: The decorated function or class

    Returns:
        Dictionary of metadata, or None if not decorated
    """
    return getattr(func_or_class, "__ontology_metadata__", None)
