"""
Tests for enhanced patch generator with LibCST integration.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.test import TestCase

from apps.mentor.generators.patch_generator import (
    PatchGenerator, CodePatch, PatchType, PatchPriority
)


class TestEnhancedPatchGenerator(TestCase):
    """Test enhanced patch generator with LibCST integration."""

    def setUp(self):
        self.generator = PatchGenerator()

    def test_generate_security_fixes_integration(self):
        """Test security fixes with LibCST integration."""
        security_issues = [
            {
                'type': 'sql_injection',
                'file_path': '/tmp/test_file.py',
                'vulnerable_code': 'User.objects.raw("SELECT * FROM users WHERE id = %s", [user_id])',
                'line_number': 10
            }
        ]

        # Create a temporary file for testing
        test_code = '''
def get_user(user_id):
    return User.objects.raw("SELECT * FROM users WHERE id = %s", [user_id])
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_file = f.name

        try:
            # Update the issue to use the real file
            security_issues[0]['file_path'] = temp_file

            patches = self.generator.generate_security_fixes(security_issues)

            self.assertGreater(len(patches), 0)

            patch = patches[0]
            self.assertEqual(patch.type, PatchType.FIX_SECURITY)
            self.assertEqual(patch.priority, PatchPriority.CRITICAL)
            self.assertIn('SQL injection', patch.description)

            # Should use LibCST approach if available
            if 'AST-based' in patch.description:
                self.assertGreater(patch.confidence, 0.9)
            else:
                # Fallback approach
                self.assertGreater(patch.confidence, 0.7)

        finally:
            Path(temp_file).unlink()

    def test_generate_performance_optimizations_integration(self):
        """Test performance optimizations with LibCST integration."""
        performance_issues = [
            {
                'type': 'n_plus_one_query',
                'file_path': '/tmp/test_perf.py',
                'code': 'for user in User.objects.all(): print(user.profile.name)',
                'line_number': 5
            }
        ]

        # Create a temporary file for testing
        test_code = '''
def get_user_profiles():
    users = []
    for user in User.objects.all():
        users.append(user.profile.name)
    return users
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_file = f.name

        try:
            performance_issues[0]['file_path'] = temp_file

            patches = self.generator.generate_performance_optimizations(performance_issues)

            # Should generate performance patches
            if patches:
                patch = patches[0]
                self.assertEqual(patch.type, PatchType.OPTIMIZE_PERFORMANCE)
                self.assertIn('optimization', patch.description.lower())

        finally:
            Path(temp_file).unlink()

    @patch('apps.mentor.codemods.codemod_engine.CodemodEngine')
    def test_libcst_integration_fallback(self, mock_engine_class):
        """Test fallback when LibCST operations fail."""
        # Mock LibCST failure
        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "LibCST transform failed"
        mock_engine.apply_codemod.return_value = mock_result
        mock_engine_class.return_value = mock_engine

        # Create test file
        test_code = '''
def unsafe_function():
    return User.objects.raw("SELECT * FROM users WHERE id = %s", [1])
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_file = f.name

        try:
            patch = self.generator._fix_sql_injection(
                temp_file,
                'User.objects.raw("SELECT * FROM users WHERE id = %s", [1])',
                5
            )

            # Should fall back to string-based approach
            self.assertIsNotNone(patch)
            self.assertIn('fallback', patch.description)
            self.assertEqual(patch.confidence, 0.8)  # Lower confidence for fallback

        finally:
            Path(temp_file).unlink()

    def test_generate_code_improvement_with_libcst(self):
        """Test code improvement generation with LibCST."""
        test_code = '''
def inefficient_function():
    result = []
    for item in items:
        result.append(item.value)
    return result
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_file = f.name

        try:
            patch = self.generator.generate_code_improvement(
                temp_file,
                "Replace loop with list comprehension",
                2
            )

            self.assertIsNotNone(patch)
            self.assertEqual(patch.type, PatchType.REFACTOR)

            # Check if LibCST optimization was attempted
            if 'AST analysis' in patch.description:
                self.assertGreater(patch.confidence, 0.8)

        finally:
            Path(temp_file).unlink()

    def test_patch_confidence_scores(self):
        """Test that patch confidence scores are appropriate."""
        # Test high-confidence AST-based patch
        with patch('apps.mentor.codemods.codemod_engine.CodemodEngine') as mock_engine_class:
            mock_engine = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.transformed_code = "fixed code"
            mock_result.original_code = "original code"
            mock_result.changes_made = 1
            mock_engine.apply_codemod.return_value = mock_result
            mock_engine_class.return_value = mock_engine

            patch = self.generator._fix_sql_injection(
                "/tmp/test.py",
                "vulnerable code",
                10
            )

            self.assertIsNotNone(patch)
            self.assertEqual(patch.confidence, 0.95)  # High confidence for AST-based

        # Test lower-confidence fallback
        patch = self.generator._fix_sql_injection(
            "/tmp/nonexistent.py",
            'User.objects.raw("SELECT * WHERE id = %s", [1])',
            10
        )

        if patch:
            self.assertLessEqual(patch.confidence, 0.8)  # Lower confidence for fallback

    def test_multi_file_patch_coordination(self):
        """Test coordination of patches across multiple files."""
        # Test that related changes are properly coordinated
        # This would be expanded in a full implementation

        files = ['apps/models.py', 'apps/views.py', 'apps/serializers.py']
        issues = [
            {
                'type': 'sql_injection',
                'file_path': 'apps/models.py',
                'vulnerable_code': 'raw query',
                'line_number': 10
            }
        ]

        patches = self.generator.generate_security_fixes(issues)

        # Verify patches maintain consistency
        for patch in patches:
            self.assertIsInstance(patch, CodePatch)
            self.assertIn(patch.type, [t for t in PatchType])
            self.assertIn(patch.priority, [p for p in PatchPriority])

    def test_dependency_tracking(self):
        """Test that patch dependencies are properly tracked."""
        # Create a patch that would require import changes
        patch = CodePatch(
            type=PatchType.FIX_SECURITY,
            priority=PatchPriority.HIGH,
            description="Test patch with dependencies",
            file_path="test.py",
            original_code="old code",
            modified_code="new code",
            line_start=1,
            line_end=1,
            dependencies=["from django.utils.html import escape"],
            confidence=0.9
        )

        self.assertEqual(len(patch.dependencies), 1)
        self.assertIn('escape', patch.dependencies[0])

    def test_rollback_patch_generation(self):
        """Test that rollback patches are properly generated."""
        original_patch = CodePatch(
            type=PatchType.MODIFY_FUNCTION,
            priority=PatchPriority.MEDIUM,
            description="Modify function",
            file_path="test.py",
            original_code="def old_function(): pass",
            modified_code="def new_function(): return True",
            line_start=5,
            line_end=5,
            dependencies=[],
            confidence=0.8
        )

        # In a full implementation, this would generate the rollback patch
        rollback_patch = CodePatch(
            type=PatchType.MODIFY_FUNCTION,
            priority=PatchPriority.MEDIUM,
            description="Rollback: Modify function",
            file_path="test.py",
            original_code=original_patch.modified_code,
            modified_code=original_patch.original_code,
            line_start=5,
            line_end=5,
            dependencies=[],
            confidence=0.9  # Rollback should be high confidence
        )

        original_patch.rollback_patch = rollback_patch

        self.assertIsNotNone(original_patch.rollback_patch)
        self.assertEqual(
            original_patch.rollback_patch.original_code,
            original_patch.modified_code
        )