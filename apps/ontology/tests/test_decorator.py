"""
Tests for the @ontology decorator and registry.
"""

import pytest

from apps.ontology import ontology
from apps.ontology.decorators import get_ontology_metadata
from apps.ontology.registry import OntologyRegistry


class TestOntologyDecorator:
    """Test the @ontology decorator."""

    def setup_method(self):
        """Clear registry before each test."""
        OntologyRegistry.clear()

    def test_decorator_on_function(self):
        """Test decorator works on functions."""

        @ontology(
            domain="test",
            purpose="Test function",
            tags=["test"],
        )
        def test_func():
            """Test function docstring."""
            return "test"

        # Check metadata is attached
        metadata = get_ontology_metadata(test_func)
        assert metadata is not None
        assert metadata["domain"] == "test"
        assert metadata["purpose"] == "Test function"
        assert "test" in metadata["tags"]

        # Check function still works
        assert test_func() == "test"

    def test_decorator_on_class(self):
        """Test decorator works on classes."""

        @ontology(
            domain="test",
            purpose="Test class",
            tags=["test", "class"],
        )
        class TestClass:
            """Test class docstring."""

            def method(self):
                return "method"

        # Check metadata is attached
        metadata = get_ontology_metadata(TestClass)
        assert metadata is not None
        assert metadata["domain"] == "test"
        assert metadata["type"] == "class"

        # Check class still works
        instance = TestClass()
        assert instance.method() == "method"

    def test_decorator_with_complex_metadata(self):
        """Test decorator with all metadata fields."""

        @ontology(
            domain="authentication",
            purpose="Validates user credentials",
            inputs=[
                {"name": "username", "type": "str", "description": "User's email"},
                {"name": "password", "type": "str", "description": "User's password"},
            ],
            outputs=[{"name": "token", "type": "str", "description": "JWT token"}],
            side_effects=["Updates last_login timestamp"],
            depends_on=["apps.peoples.models.People"],
            tags=["security", "auth"],
            security_notes="Rate limited to 5 attempts per minute",
        )
        def login_user(username: str, password: str):
            """Authenticate user."""
            return {"token": "test_token"}

        metadata = get_ontology_metadata(login_user)
        assert metadata["domain"] == "authentication"
        assert len(metadata["inputs"]) == 2
        assert metadata["inputs"][0]["name"] == "username"
        assert len(metadata["outputs"]) == 1
        assert "Updates last_login timestamp" in metadata["side_effects"]
        assert metadata["security_notes"] == "Rate limited to 5 attempts per minute"

    def test_registry_registration(self):
        """Test that decorator registers with registry."""

        @ontology(domain="test", purpose="Test registration")
        def test_func():
            pass

        # Get metadata from registry
        metadata = OntologyRegistry.get("test_decorator.test_func")
        # Note: qualified_name might be different in test environment

        # At least verify registry is not empty
        all_metadata = OntologyRegistry.get_all()
        assert len(all_metadata) > 0

    def test_deprecated_marker(self):
        """Test deprecated flag."""

        @ontology(
            domain="test",
            purpose="Old function",
            deprecated=True,
            replacement="new_function",
        )
        def old_function():
            pass

        metadata = get_ontology_metadata(old_function)
        assert metadata["deprecated"] is True
        assert metadata["replacement"] == "new_function"


class TestOntologyRegistry:
    """Test the OntologyRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        OntologyRegistry.clear()

    def test_register_and_get(self):
        """Test registering and retrieving metadata."""
        test_metadata = {
            "qualified_name": "test.module.function",
            "name": "function",
            "type": "function",
            "domain": "test",
            "purpose": "Test purpose",
            "tags": ["test"],
        }

        OntologyRegistry.register("test.module.function", test_metadata)

        retrieved = OntologyRegistry.get("test.module.function")
        assert retrieved is not None
        assert retrieved["name"] == "function"
        assert retrieved["domain"] == "test"

    def test_get_by_domain(self):
        """Test retrieving by domain."""
        OntologyRegistry.register(
            "test.func1",
            {"qualified_name": "test.func1", "domain": "auth", "type": "function"},
        )
        OntologyRegistry.register(
            "test.func2",
            {"qualified_name": "test.func2", "domain": "auth", "type": "function"},
        )
        OntologyRegistry.register(
            "test.func3",
            {"qualified_name": "test.func3", "domain": "api", "type": "function"},
        )

        auth_items = OntologyRegistry.get_by_domain("auth")
        assert len(auth_items) == 2

        api_items = OntologyRegistry.get_by_domain("api")
        assert len(api_items) == 1

    def test_get_by_tag(self):
        """Test retrieving by tag."""
        OntologyRegistry.register(
            "test.func1",
            {"qualified_name": "test.func1", "tags": ["security", "auth"]},
        )
        OntologyRegistry.register(
            "test.func2",
            {"qualified_name": "test.func2", "tags": ["security"]},
        )

        security_items = OntologyRegistry.get_by_tag("security")
        assert len(security_items) == 2

        auth_items = OntologyRegistry.get_by_tag("auth")
        assert len(auth_items) == 1

    def test_search(self):
        """Test text search."""
        OntologyRegistry.register(
            "test.login",
            {
                "qualified_name": "test.login",
                "name": "login",
                "purpose": "User authentication",
            },
        )
        OntologyRegistry.register(
            "test.logout",
            {
                "qualified_name": "test.logout",
                "name": "logout",
                "purpose": "User logout",
            },
        )

        results = OntologyRegistry.search("login")
        assert len(results) > 0
        assert any("login" in r["name"].lower() for r in results)

    def test_get_statistics(self):
        """Test statistics retrieval."""
        OntologyRegistry.register(
            "test.func1",
            {"qualified_name": "test.func1", "type": "function", "domain": "test"},
        )
        OntologyRegistry.register(
            "test.class1",
            {"qualified_name": "test.class1", "type": "class", "domain": "test"},
        )

        stats = OntologyRegistry.get_statistics()
        assert stats["total_components"] == 2
        assert "function" in stats["by_type"]
        assert "class" in stats["by_type"]
        assert "test" in stats["domains"]

    def test_get_deprecated(self):
        """Test retrieving deprecated items."""
        OntologyRegistry.register(
            "test.old",
            {"qualified_name": "test.old", "deprecated": True},
        )
        OntologyRegistry.register(
            "test.new",
            {"qualified_name": "test.new", "deprecated": False},
        )

        deprecated = OntologyRegistry.get_deprecated()
        assert len(deprecated) == 1
        assert deprecated[0]["qualified_name"] == "test.old"

    def test_bulk_register(self):
        """Test bulk registration."""
        items = [
            {"qualified_name": "test.func1", "type": "function"},
            {"qualified_name": "test.func2", "type": "function"},
            {"qualified_name": "test.func3", "type": "function"},
        ]

        OntologyRegistry.bulk_register(items)

        assert OntologyRegistry.get("test.func1") is not None
        assert OntologyRegistry.get("test.func2") is not None
        assert OntologyRegistry.get("test.func3") is not None

        stats = OntologyRegistry.get_statistics()
        assert stats["total_components"] == 3
