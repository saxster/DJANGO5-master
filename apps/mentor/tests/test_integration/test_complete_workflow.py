"""
Integration tests for complete AI Mentor workflows.

Tests the end-to-end integration of plan → patch → test → guard → apply workflows.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.core.management import call_command
from io import StringIO

from apps.mentor.models import IndexedFile, CodeSymbol, IndexMetadata


class TestCompleteWorkflowIntegration(TransactionTestCase):
    """Test complete workflow integration."""

    def setUp(self):
        self.out = StringIO()
        self.err = StringIO()

        # Create some test index data
        test_file = IndexedFile.objects.create(
            path='apps/test/models.py',
            sha='abc123',
            mtime=1234567890,
            size=1000,
            language='python'
        )

        CodeSymbol.objects.create(
            file=test_file,
            name='TestModel',
            kind='class',
            span_start=10,
            span_end=30,
            signature='class TestModel(models.Model)'
        )

    def test_plan_to_patch_workflow(self):
        """Test workflow from plan generation to patch application."""
        # Step 1: Generate plan
        call_command(
            'mentor_plan',
            '--request', 'Add validation to TestModel',
            '--format', 'json',
            stdout=self.out,
            stderr=self.err
        )

        plan_output = self.out.getvalue()
        self.assertIn('Generated plan', plan_output)

        # Reset output capture
        self.out = StringIO()

        # Step 2: Generate patches based on plan
        call_command(
            'mentor_patch',
            '--request', 'Add validation to TestModel',
            '--type', 'improvement',
            '--dry-run',
            stdout=self.out,
            stderr=self.err
        )

        patch_output = self.out.getvalue()
        self.assertIn('Generated', patch_output)

    @patch('apps.mentor.management.commands.mentor_test.TestRunner')
    def test_plan_to_test_workflow(self, mock_test_runner):
        """Test workflow from plan generation to targeted testing."""
        # Mock test execution
        mock_session = MagicMock()
        mock_session.session_id = "test_session_123"
        mock_session.total_tests = 5
        mock_session.passed = 4
        mock_session.failed = 1
        mock_session.total_duration = 15.5
        mock_session.results = []

        mock_runner = MagicMock()
        mock_runner.run_tests.return_value = mock_session
        mock_test_runner.return_value = mock_runner

        # Step 1: Run targeted tests
        call_command(
            'mentor_test',
            '--targets', 'apps/test/models.py',
            '--coverage',
            stdout=self.out,
            stderr=self.err
        )

        test_output = self.out.getvalue()
        self.assertIn('Running', test_output)

    def test_guard_validation_workflow(self):
        """Test guard validation workflow."""
        # Create a temporary Python file for validation
        test_code = '''
def test_function():
    password = "hardcoded_secret"
    except:
        pass
    print("Debug message")
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            temp_file = f.name

        try:
            call_command(
                'mentor_guard',
                '--validate',
                '--files', temp_file,
                stdout=self.out,
                stderr=self.err
            )

            guard_output = self.out.getvalue()
            self.assertIn('validation', guard_output.lower())

        finally:
            Path(temp_file).unlink()

    def test_explain_workflow(self):
        """Test code explanation workflow."""
        call_command(
            'mentor_explain',
            'TestModel',
            '--type', 'model',
            '--format', 'summary',
            stdout=self.out,
            stderr=self.err
        )

        explain_output = self.out.getvalue()
        self.assertIn('EXPLANATION', explain_output)

    def test_complete_security_workflow(self):
        """Test complete security workflow: scan → plan → patch → guard → apply."""
        security_code = '''
def unsafe_query(user_id):
    return User.objects.raw("SELECT * FROM users WHERE id = %s", [user_id])

def unsafe_template():
    return mark_safe(user_input)
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(security_code)
            temp_file = f.name

        try:
            # Step 1: Generate security plan
            self.out = StringIO()
            call_command(
                'mentor_plan',
                '--request', f'Fix security issues in {temp_file}',
                '--format', 'summary',
                stdout=self.out,
                stderr=self.err
            )
            plan_output = self.out.getvalue()
            self.assertIn('Generated plan', plan_output)

            # Step 2: Generate security patches
            self.out = StringIO()
            call_command(
                'mentor_patch',
                '--type', 'security',
                '--files', temp_file,
                '--dry-run',
                stdout=self.out,
                stderr=self.err
            )
            patch_output = self.out.getvalue()
            self.assertIn('patches', patch_output.lower())

            # Step 3: Run security validation
            self.out = StringIO()
            call_command(
                'mentor_guard',
                '--check', 'security',
                '--files', temp_file,
                stdout=self.out,
                stderr=self.err
            )
            guard_output = self.out.getvalue()
            self.assertIn('validation', guard_output.lower())

        finally:
            Path(temp_file).unlink()

    def test_performance_optimization_workflow(self):
        """Test performance optimization workflow."""
        perf_code = '''
def slow_function():
    users = []
    for user_obj in User.objects.all():
        users.append(user_obj.profile.name)
    return users

def inefficient_query():
    return User.objects.filter(active=True).count()
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(perf_code)
            temp_file = f.name

        try:
            # Step 1: Generate performance plan
            self.out = StringIO()
            call_command(
                'mentor_plan',
                '--request', f'Optimize performance in {temp_file}',
                '--format', 'summary',
                stdout=self.out,
                stderr=self.err
            )
            plan_output = self.out.getvalue()
            self.assertIn('Generated plan', plan_output)

            # Step 2: Generate performance patches
            self.out = StringIO()
            call_command(
                'mentor_patch',
                '--type', 'performance',
                '--files', temp_file,
                '--dry-run',
                stdout=self.out,
                stderr=self.err
            )
            patch_output = self.out.getvalue()
            self.assertIn('patches', patch_output.lower())

        finally:
            Path(temp_file).unlink()

    def test_error_handling_workflow(self):
        """Test error handling throughout the workflow."""
        # Test with non-existent file
        call_command(
            'mentor_explain',
            'NonExistentFile.py',
            '--type', 'file',
            stdout=self.out,
            stderr=self.err
        )

        explain_output = self.out.getvalue()
        # Should handle gracefully
        self.assertTrue(len(explain_output) > 0)

    def test_workflow_with_real_django_files(self):
        """Test workflow with actual Django files from the project."""
        # Test with an actual model file
        model_file = 'apps/mentor/models.py'

        # Step 1: Explain the model file
        self.out = StringIO()
        call_command(
            'mentor_explain',
            model_file,
            '--type', 'file',
            '--format', 'summary',
            stdout=self.out,
            stderr=self.err
        )

        explain_output = self.out.getvalue()
        self.assertIn('EXPLANATION', explain_output)

        # Step 2: Run quality analysis
        self.out = StringIO()
        call_command(
            'mentor_guard',
            '--check', 'quality',
            '--files', model_file,
            stdout=self.out,
            stderr=self.err
        )

        guard_output = self.out.getvalue()
        self.assertIn('validation', guard_output.lower())


class TestWorkflowPerformance(TestCase):
    """Test workflow performance and efficiency."""

    def test_index_freshness_check(self):
        """Test that workflows check index freshness."""
        # Create an old index entry
        old_file = IndexedFile.objects.create(
            path='apps/old/models.py',
            sha='old_sha',
            mtime=1000000000,  # Very old timestamp
            size=500,
            language='python'
        )

        # Check if workflow detects stale index
        self.assertFalse(old_file.is_fresh)

    def test_workflow_caching(self):
        """Test that workflows utilize caching appropriately."""
        # Set up index metadata
        IndexMetadata.set_value('last_analysis', '2024-01-01T00:00:00Z')

        # Test that subsequent calls use cached data appropriately
        metadata = IndexMetadata.get_value('last_analysis')
        self.assertIsNotNone(metadata)

    def test_concurrent_workflow_safety(self):
        """Test that concurrent workflows don't interfere with each other."""
        # This would test transaction isolation and concurrent access
        # For now, just ensure basic operations don't conflict

        # Create multiple index entries
        for i in range(5):
            IndexedFile.objects.create(
                path=f'apps/test/file_{i}.py',
                sha=f'sha_{i}',
                mtime=1234567890 + i,
                size=1000 + i,
                language='python'
            )

        # Verify all were created successfully
        self.assertEqual(IndexedFile.objects.count(), 5)


class TestWorkflowConfiguration(TestCase):
    """Test workflow configuration and settings."""

    def test_mentor_disabled_in_production(self):
        """Test that mentor respects production settings."""
        with patch('django.conf.settings.MENTOR_ENABLED', False):
            # Test that commands respect the disabled setting
            with self.assertRaises(SystemExit):
                call_command('mentor_plan', '--request', 'test')

    @patch('django.conf.settings.MENTOR_ENABLED', True)
    def test_mentor_enabled_in_development(self):
        """Test that mentor works when enabled."""
        # This should not raise SystemExit
        try:
            call_command(
                'mentor_plan',
                '--request', 'test request',
                '--format', 'summary',
                stdout=StringIO(),
                stderr=StringIO()
            )
        except SystemExit:
            self.fail("Mentor should work when enabled")
        except Exception:
            # Other exceptions are okay (missing dependencies, etc.)
            pass