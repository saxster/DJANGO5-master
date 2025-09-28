"""
Tests for the mentor_index management command.
"""

from io import StringIO

from django.core.management import call_command

from apps.mentor.tests.base import IndexingTestCase, MockGitTestCase, SAMPLE_PYTHON_FILES
from apps.mentor.models import IndexedFile, CodeSymbol, IndexMetadata


class MentorIndexCommandTest(IndexingTestCase, MockGitTestCase):
    """Test the mentor_index management command."""

    def test_full_index_command(self):
        """Test full indexing command."""
        # Create test files
        self.create_python_file('apps/test_app/models.py', SAMPLE_PYTHON_FILES['django_model.py'])
        self.create_python_file('apps/test_app/views.py', SAMPLE_PYTHON_FILES['django_views.py'])

        # Mock git commit
        commit_sha = self.mock_git_commit('abc123')

        with self.mock_project_root():
            # Run full index
            out = StringIO()
            call_command('mentor_index', '--full', stdout=out)

        # Check output
        output = out.getvalue()
        self.assertIn('Full indexing:', output)
        self.assertIn('Indexing completed', output)

        # Verify files were indexed
        self.assert_file_indexed('apps/test_app/models.py')
        self.assert_file_indexed('apps/test_app/views.py')

        # Verify symbols were extracted
        self.assert_symbol_exists('apps/test_app/models.py', 'User', 'class')
        self.assert_symbol_exists('apps/test_app/models.py', '__str__', 'method')
        self.assert_symbol_exists('apps/test_app/views.py', 'user_list', 'function')

        # Verify metadata was updated
        self.assertEqual(IndexMetadata.get_indexed_commit(), commit_sha)

    def test_incremental_index_command(self):
        """Test incremental indexing based on git changes."""
        # Set up initial index
        IndexMetadata.set_indexed_commit('old_commit')

        # Create test files
        self.create_python_file('apps/test_app/models.py', SAMPLE_PYTHON_FILES['django_model.py'])
        self.create_python_file('apps/test_app/views.py', SAMPLE_PYTHON_FILES['django_views.py'])
        self.create_python_file('apps/test_app/utils.py', SAMPLE_PYTHON_FILES['simple_function.py'])

        # Mock git to return only changed files
        self.mock_git_diff(['apps/test_app/models.py', 'apps/test_app/views.py'])
        self.mock_git_commit('new_commit')

        with self.mock_project_root():
            # Run incremental index
            out = StringIO()
            call_command('mentor_index', '--since', 'old_commit', stdout=out)

        # Check output
        output = out.getvalue()
        self.assertIn('Incremental indexing since old_commit:', output)

        # Verify only changed files were indexed
        self.assert_file_indexed('apps/test_app/models.py')
        self.assert_file_indexed('apps/test_app/views.py')

        # Verify unchanged file was not indexed
        self.assertEqual(IndexedFile.objects.filter(path='apps/test_app/utils.py').count(), 0)

    def test_dry_run_mode(self):
        """Test dry run mode doesn't make changes."""
        # Create test file
        self.create_python_file('apps/test_app/models.py', SAMPLE_PYTHON_FILES['django_model.py'])

        self.mock_git_commit('test_commit')

        with self.mock_project_root():
            # Run in dry run mode
            out = StringIO()
            call_command('mentor_index', '--full', '--dry-run', stdout=out)

        # Check output indicates dry run
        output = out.getvalue()
        self.assertIn('DRY RUN MODE', output)

        # Verify no files were actually indexed
        self.assertEqual(IndexedFile.objects.count(), 0)

        # Verify no metadata was updated
        self.assertIsNone(IndexMetadata.get_indexed_commit())

    def test_skip_unchanged_files(self):
        """Test that unchanged files are skipped."""
        content = SAMPLE_PYTHON_FILES['simple_function.py']

        # Create and index file initially
        file_path = self.create_python_file('apps/test_app/utils.py', content)
        self.mock_git_commit('commit1')

        with self.mock_project_root():
            call_command('mentor_index', '--full', verbosity=0)

        initial_count = CodeSymbol.objects.count()
        self.assertGreater(initial_count, 0)

        # Run index again without changing the file
        self.mock_git_commit('commit2')

        with self.mock_project_root():
            out = StringIO()
            call_command('mentor_index', '--full', stdout=out)

        # Should skip the unchanged file
        output = out.getvalue()
        self.assertIn('Files skipped: 1', output)

        # Symbol count should remain the same
        self.assertEqual(CodeSymbol.objects.count(), initial_count)

    def test_apps_filter(self):
        """Test filtering by specific apps."""
        # Create files in different apps
        self.create_python_file('apps/app1/models.py', SAMPLE_PYTHON_FILES['django_model.py'])
        self.create_python_file('apps/app2/views.py', SAMPLE_PYTHON_FILES['django_views.py'])

        self.mock_git_commit('test_commit')

        with self.mock_project_root():
            # Index only app1
            call_command('mentor_index', '--full', '--apps', 'app1', verbosity=0)

        # Verify only app1 files were indexed
        self.assert_file_indexed('apps/app1/models.py')
        self.assertEqual(IndexedFile.objects.filter(path='apps/app2/views.py').count(), 0)

    def test_syntax_error_handling(self):
        """Test handling of files with syntax errors."""
        # Create file with syntax error
        invalid_python = '''
def broken_function(
    # Missing closing parenthesis and body
'''
        self.create_python_file('apps/test_app/broken.py', invalid_python)

        self.mock_git_commit('test_commit')

        with self.mock_project_root():
            out = StringIO()
            err = StringIO()
            call_command('mentor_index', '--full', stdout=out, stderr=err)

        # Should handle the error gracefully
        error_output = err.getvalue()
        self.assertIn('Syntax error', error_output)

        # File should still be indexed (without symbols)
        file_obj = self.assert_file_indexed('apps/test_app/broken.py')
        self.assertEqual(file_obj.symbols.count(), 0)

    def test_quiet_mode(self):
        """Test quiet mode produces minimal output."""
        self.create_python_file('apps/test_app/models.py', SAMPLE_PYTHON_FILES['django_model.py'])

        self.mock_git_commit('test_commit')

        with self.mock_project_root():
            out = StringIO()
            call_command('mentor_index', '--full', '--quiet', stdout=out)

        # Should have minimal output
        output = out.getvalue()
        self.assertNotIn('Processing', output)
        # But should still show completion
        self.assertIn('Indexing completed', output)

    def test_unicode_handling(self):
        """Test handling of files with unicode content."""
        unicode_content = '''
def unicode_function():
    """Function with unicode: 🚀 rocket and café."""
    greeting = "Hello 世界"
    return greeting
'''
        self.create_python_file('apps/test_app/unicode.py', unicode_content)

        self.mock_git_commit('test_commit')

        with self.mock_project_root():
            call_command('mentor_index', '--full', verbosity=0)

        # Verify unicode file was indexed correctly
        file_obj = self.assert_file_indexed('apps/test_app/unicode.py')
        symbol = self.assert_symbol_exists('apps/test_app/unicode.py', 'unicode_function')

        self.assertIn('🚀', symbol.docstring)
        self.assertIn('café', symbol.docstring)

    @patch('apps.mentor.management.commands.mentor_index.subprocess.run')
    def test_git_command_failure(self, mock_run):
        """Test handling of git command failures."""
        # Mock git command failure
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "fatal: not a git repository"

        self.create_python_file('apps/test_app/models.py', SAMPLE_PYTHON_FILES['django_model.py'])

        with self.mock_project_root():
            out = StringIO()
            err = StringIO()
            try:
                call_command('mentor_index', '--since', 'some_commit', stdout=out, stderr=err)
            except SystemExit:
                pass  # Command may exit on git errors

        # Should handle git errors gracefully
        error_output = err.getvalue()
        self.assertIn('Git diff failed', error_output)

    def test_performance_with_large_file(self):
        """Test performance with larger files."""
        # Generate a larger Python file
        large_content = '''
from django.db import models

'''
        for i in range(100):
            large_content += f'''
class Model{i}(models.Model):
    """Model number {i}."""
    field{i} = models.CharField(max_length=100)

    def method{i}(self):
        """Method number {i}."""
        return self.field{i}

'''

        self.create_python_file('apps/test_app/large.py', large_content)
        self.mock_git_commit('test_commit')

        with self.mock_project_root():
            # Should complete within reasonable time
            self.assert_performance_within(
                lambda: call_command('mentor_index', '--full', verbosity=0),
                5.0  # 5 seconds max
            )

        # Verify all symbols were extracted
        file_obj = self.assert_file_indexed('apps/test_app/large.py')
        self.assertGreater(file_obj.symbols.count(), 200)  # 100 classes + 100 methods