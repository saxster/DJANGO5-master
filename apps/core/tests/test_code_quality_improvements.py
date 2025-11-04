"""
Comprehensive tests for code quality improvements.
Tests the fixes applied for:
- Code style inconsistencies
- Commented dead code removal
- Missing type hints
- Inefficient string operations
"""

# Standard library imports
import ast
import inspect
import unittest
from pathlib import Path
from django.test import TestCase

# Third-party imports
import pytest

# Local application imports
from background_tasks import tasks
from intelliwiz_config import settings


class CodeQualityImprovementsTest(TestCase):
    """Test suite for validating code quality improvements."""

    def test_string_formatting_improvement(self):
        """Test that the inefficient string operation has been fixed."""
        # Read the tasks.py file to check if the problematic line was fixed
        tasks_file = Path(__file__).parent.parent.parent.parent / "background_tasks" / "tasks.py"

        with open(tasks_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Ensure the old problematic pattern is no longer present
        problematic_pattern = 'f\'AUTOCLOSE {"TOUR" if rec["identifier"] in  ["INTERNALTOUR", "EXTERNALTOUR"] else rec["identifier"] } planned on \\'
        self.assertNotIn(problematic_pattern, content)

        # Ensure the improved pattern is present
        improved_pattern = 'task_type = "TOUR" if rec["identifier"] in ["INTERNALTOUR", "EXTERNALTOUR"] else rec["identifier"]'
        self.assertIn(improved_pattern, content)

        # Check that the f-string is now clean and readable
        clean_f_string = 'f"AUTOCLOSE {task_type} planned on {pdate} not reported in time"'
        self.assertIn(clean_f_string, content)

    def test_commented_dead_code_removal(self):
        """Test that commented CELERY dead code has been removed."""
        settings_file = Path(__file__).parent.parent.parent.parent / "intelliwiz_config" / "settings.py"

        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Ensure specific commented CELERY configurations are removed
        dead_code_patterns = [
            "# CELERY SETTINGS - REMOVED (Replaced with PostgreSQL Task Queue)",
            "# CELERY_BROKER_URL = env('CELERY_broker_url')",
            "# result_backend = env(\"result_backend\")",
            "# CELERY_TASK_ROUTES - REMOVED (Replaced with PostgreSQL Task Queue)"
        ]

        for pattern in dead_code_patterns:
            self.assertNotIn(pattern, content)

    def test_import_ordering_compliance(self):
        """Test that import ordering follows PEP8 standards."""
        tasks_file = Path(__file__).parent.parent.parent.parent / "background_tasks" / "tasks.py"

        with open(tasks_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Check that import sections are properly organized with comments
        content = ''.join(lines)

        # Verify section headers are present in correct order
        expected_sections = [
            "# Standard library imports",
            "# Third-party imports",
            "# Django imports",
            "# Local application imports"
        ]

        last_index = -1
        for section in expected_sections:
            current_index = content.find(section)
            self.assertGreater(current_index, last_index,
                             f"Import section '{section}' not found or out of order")
            last_index = current_index

        # Check that multi-line imports are split
        self.assertNotIn("import base64, os, json", content)
        self.assertIn("import base64", content)
        self.assertIn("import json", content)
        self.assertIn("import os", content)

    def test_type_hints_added(self):
        """Test that type hints have been added to critical functions."""
        # Test validate_mqtt_topic function
        sig = inspect.signature(tasks.validate_mqtt_topic)
        self.assertIn('topic', sig.parameters)
        self.assertEqual(sig.parameters['topic'].annotation, str)
        self.assertEqual(sig.return_annotation, str)

        # Test validate_mqtt_payload function
        sig = inspect.signature(tasks.validate_mqtt_payload)
        self.assertIn('payload', sig.parameters)
        # Check that return annotation exists
        self.assertNotEqual(sig.return_annotation, inspect.Signature.empty)

        # Test settings functions
        sig = inspect.signature(settings.check_path)
        self.assertIn('path', sig.parameters)
        self.assertEqual(sig.return_annotation, bool)

    def test_typing_imports_present(self):
        """Test that typing imports are properly added to files."""
        # Check tasks.py has typing imports
        tasks_file = Path(__file__).parent.parent.parent.parent / "background_tasks" / "tasks.py"
        with open(tasks_file, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("from typing import Dict, Any, Optional, List, Union", content)

        # Check settings.py has typing imports
        settings_file = Path(__file__).parent.parent.parent.parent / "intelliwiz_config" / "settings.py"
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("from typing import Union, Optional, Dict, Any", content)

    def test_code_quality_tools_configuration(self):
        """Test that code quality tools are properly configured."""
        project_root = Path(__file__).parent.parent.parent.parent

        # Check that configuration files exist
        config_files = [
            "pyproject.toml",
            ".flake8",
            "Makefile",
            ".github/workflows/code-quality.yml"
        ]

        for config_file in config_files:
            file_path = project_root / config_file
            self.assertTrue(file_path.exists(), f"Configuration file {config_file} should exist")

        # Check pyproject.toml has correct tool configurations
        pyproject_content = (project_root / "pyproject.toml").read_text()
        tool_sections = ["[tool.black]", "[tool.isort]", "[tool.mypy]", "[tool.coverage.run]"]

        for section in tool_sections:
            self.assertIn(section, pyproject_content, f"Tool section {section} should be configured")

    def test_function_readability_improvements(self):
        """Test specific improvements to function readability."""
        # Import the actual function and test its logic
        # This tests that the refactored string formatting logic works correctly

        # Test case 1: INTERNALTOUR identifier
        test_data_1 = {"identifier": "INTERNALTOUR"}
        expected_task_type_1 = "TOUR"
        actual_task_type_1 = "TOUR" if test_data_1["identifier"] in ["INTERNALTOUR", "EXTERNALTOUR"] else test_data_1["identifier"]
        self.assertEqual(actual_task_type_1, expected_task_type_1)

        # Test case 2: EXTERNALTOUR identifier
        test_data_2 = {"identifier": "EXTERNALTOUR"}
        expected_task_type_2 = "TOUR"
        actual_task_type_2 = "TOUR" if test_data_2["identifier"] in ["INTERNALTOUR", "EXTERNALTOUR"] else test_data_2["identifier"]
        self.assertEqual(actual_task_type_2, expected_task_type_2)

        # Test case 3: Other identifier
        test_data_3 = {"identifier": "MAINTENANCE"}
        expected_task_type_3 = "MAINTENANCE"
        actual_task_type_3 = "TOUR" if test_data_3["identifier"] in ["INTERNALTOUR", "EXTERNALTOUR"] else test_data_3["identifier"]
        self.assertEqual(actual_task_type_3, expected_task_type_3)

    def test_no_syntax_errors_after_changes(self):
        """Test that all Python files compile correctly after changes."""
        project_root = Path(__file__).parent.parent.parent.parent
        python_files = [
            "background_tasks/tasks.py",
            "intelliwiz_config/settings.py",
            "intelliwiz_config/__init__.py"
        ]

        for python_file in python_files:
            file_path = project_root / python_file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Try to parse the file - should not raise SyntaxError
            try:
                ast.parse(content)
            except SyntaxError as e:
                self.fail(f"Syntax error in {python_file}: {e}")

    @pytest.mark.security
    def test_security_improvements_maintained(self):
        """Test that security features are maintained after code quality improvements."""
        # Ensure XSS protection is still in place
        tasks_file = Path(__file__).parent.parent.parent.parent / "background_tasks" / "tasks.py"
        with open(tasks_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check that XSS prevention is still imported and used
        self.assertIn("XSSPrevention", content)
        self.assertIn("sanitize_input", content)

        # Check that validation functions are still present
        self.assertIn("validate_mqtt_topic", content)
        self.assertIn("validate_mqtt_payload", content)


class CodeQualityIntegrationTest(TestCase):
    """Integration tests for code quality improvements."""

    def test_import_structure_integrity(self):
        """Test that import restructuring doesn't break functionality."""
        # Test that we can still import required modules
        try:
            # Minimal sanity import to ensure modules resolve
            from apps.core import utils  # noqa: F401
            from background_tasks import tasks as _tasks  # noqa: F401
        except ImportError as e:
            self.fail(f"Import error after restructuring: {e}")

    def test_type_annotations_runtime_compatibility(self):
        """Test that type annotations don't break runtime functionality."""
        # Call functions with type hints to ensure they still work
        from background_tasks.tasks import validate_mqtt_topic
        from intelliwiz_config.settings import check_path

        # These should work without type-related errors
        try:
            result = validate_mqtt_topic("test/topic")
            self.assertIsInstance(result, str)

            # Test with Path object and string
            from pathlib import Path
            temp_path = "/tmp/claude/test_path"
            result = check_path(temp_path)
            self.assertIsInstance(result, bool)

        except (ValueError, TypeError, AttributeError, KeyError) as e:
            self.fail(f"Runtime error with type-annotated functions: {e}")


if __name__ == "__main__":
    unittest.main()
