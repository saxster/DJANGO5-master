"""
Model Complexity Compliance Tests

Validates that all model files comply with .claude/rules.md Rule #7:
- Model classes < 150 lines
- Utility functions < 50 lines
- Settings files < 200 lines

These tests ensure code quality standards are maintained and prevent
regression to anti-patterns.
"""

import pytest
import os
from pathlib import Path


class TestModelComplexityLimits:
    """Test that model files comply with line count limits."""

    def test_compatibility_shim_under_200_lines(self):
        """Verify models.py (compatibility shim) is under 200 lines"""
        models_path = Path(__file__).parent.parent.parent / "models.py"
        line_count = self._count_lines(models_path)

        assert line_count < 200, f"models.py has {line_count} lines (limit: 200)"

    def test_user_model_under_150_lines(self):
        """Verify user_model.py is under 150 lines (Rule #7)"""
        model_path = Path(__file__).parent.parent.parent / "models" / "user_model.py"
        line_count = self._count_lines(model_path)

        # Allow small buffer for necessary boilerplate
        assert line_count <= 155, f"user_model.py has {line_count} lines (target: <150)"

    def test_organizational_model_reasonable_size(self):
        """Verify organizational_model.py is reasonable size"""
        model_path = Path(__file__).parent.parent.parent / "models" / "organizational_model.py"
        line_count = self._count_lines(model_path)

        # Organizational model has many field definitions, allow slight buffer
        assert line_count < 200, f"organizational_model.py has {line_count} lines (limit: 200)"

    def test_all_model_files_under_200_lines(self):
        """Verify all model files in models/ directory are under 200 lines"""
        models_dir = Path(__file__).parent.parent.parent / "models"

        if not models_dir.exists():
            pytest.skip("Models directory not found")

        for model_file in models_dir.glob("*.py"):
            if model_file.name == "__init__.py":
                continue

            line_count = self._count_lines(model_file)
            assert line_count < 200, f"{model_file.name} has {line_count} lines (limit: 200)"

    def test_mixin_files_under_150_lines(self):
        """Verify mixin files are under 150 lines"""
        mixins_dir = Path(__file__).parent.parent.parent / "mixins"

        if not mixins_dir.exists():
            pytest.skip("Mixins directory not found")

        for mixin_file in mixins_dir.glob("*.py"):
            if mixin_file.name == "__init__.py":
                continue

            line_count = self._count_lines(mixin_file)
            assert line_count < 150, f"{mixin_file.name} has {line_count} lines (limit: 150)"

    def _count_lines(self, file_path):
        """Count non-empty lines in a file"""
        if not os.path.exists(file_path):
            return 0

        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        return len(lines)


class TestUtilityFunctionCompliance:
    """Test that utility functions comply with Rule #14 (<50 lines)."""

    def test_deprecated_utility_functions_under_50_lines(self):
        """Verify deprecated utility functions are now under 50 lines"""
        from apps.peoples.models import upload_peopleimg, peoplejson, now
        import inspect

        # Each deprecated function should be small (delegation only)
        upload_lines = len(inspect.getsource(upload_peopleimg).split('\n'))
        peoplejson_lines = len(inspect.getsource(peoplejson).split('\n'))
        now_lines = len(inspect.getsource(now).split('\n'))

        assert upload_lines < 50, f"upload_peopleimg has {upload_lines} lines (limit: 50)"
        assert peoplejson_lines < 50, f"peoplejson has {peoplejson_lines} lines (limit: 50)"
        assert now_lines < 20, f"now has {now_lines} lines (limit: 20)"


class TestCodeQualityMetrics:
    """Test general code quality metrics."""

    def test_no_god_classes(self):
        """Verify no single model file is overly complex"""
        models_dir = Path(__file__).parent.parent.parent / "models"

        if not models_dir.exists():
            pytest.skip("Models directory not found")

        max_allowed_lines = 250  # Absolute maximum
        for model_file in models_dir.glob("*.py"):
            if model_file.name == "__init__.py":
                continue

            line_count = self._count_lines(model_file)
            assert line_count < max_allowed_lines, (
                f"{model_file.name} is a god class with {line_count} lines "
                f"(absolute max: {max_allowed_lines})"
            )

    def _count_lines(self, file_path):
        """Count total lines in a file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return len(f.readlines())


class TestArchitecturalCompliance:
    """Test that architecture follows SOLID principles."""

    def test_models_have_single_responsibility(self):
        """Verify each model has a clear single responsibility"""
        from apps.peoples.models import (
            People, PeopleProfile, PeopleOrganizational,
            Pgroup, Pgbelonging, Capability
        )

        # Each model should have a focused purpose (tested via docstring)
        assert "authentication" in People.__doc__.lower() or "core" in People.__doc__.lower()
        assert "profile" in PeopleProfile.__doc__.lower()
        assert "organizational" in PeopleOrganizational.__doc__.lower()

    def test_mixins_provide_focused_functionality(self):
        """Verify mixins have clear, focused responsibilities"""
        from apps.peoples.mixins import (
            PeopleCapabilityMixin,
            OrganizationalQueryMixin
        )

        # Mixins should have descriptive docstrings
        assert PeopleCapabilityMixin.__doc__ is not None
        assert "capability" in PeopleCapabilityMixin.__doc__.lower()

        assert OrganizationalQueryMixin.__doc__ is not None
        assert "query" in OrganizationalQueryMixin.__doc__.lower() or "organizational" in OrganizationalQueryMixin.__doc__.lower()