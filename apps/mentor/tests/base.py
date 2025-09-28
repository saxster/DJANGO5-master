"""
Base test classes and utilities for the AI Mentor system.

Provides common functionality for testing indexing, analysis, and generation.
"""

import os
import tempfile
import shutil
from pathlib import Path

from django.conf import settings

from apps.mentor.models import (
    IndexedFile, CodeSymbol, SymbolRelation, DjangoURL,
    DjangoModel, GraphQLDefinition, TestCase as MentorTestCase,
    TestCoverage, IndexMetadata
)


class MentorTestCase(TestCase):
    """Base test case for mentor system tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure we're in test mode
        cls.original_mentor_enabled = os.environ.get('MENTOR_ENABLED')
        os.environ['MENTOR_ENABLED'] = '1'

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Restore original environment
        if cls.original_mentor_enabled is not None:
            os.environ['MENTOR_ENABLED'] = cls.original_mentor_enabled
        elif 'MENTOR_ENABLED' in os.environ:
            del os.environ['MENTOR_ENABLED']

    def setUp(self):
        super().setUp()
        # Clear all mentor data before each test
        self.clear_mentor_data()

    def clear_mentor_data(self):
        """Clear all mentor-related data."""
        models_to_clear = [
            TestCoverage, MentorTestCase, GraphQLDefinition,
            DjangoModel, DjangoURL, SymbolRelation, CodeSymbol,
            IndexedFile, IndexMetadata
        ]
        for model in models_to_clear:
            model.objects.all().delete()

    def create_test_file(self, path: str, content: str, **kwargs) -> IndexedFile:
        """Create a test file record."""
        defaults = {
            'sha': 'test_sha_' + path.replace('/', '_'),
            'mtime': 1234567890,
            'size': len(content),
            'language': 'python',
            'content_preview': content[:1000],
        }
        defaults.update(kwargs)

        return IndexedFile.objects.create(path=path, **defaults)

    def create_test_symbol(self, file_obj: IndexedFile, name: str, kind: str = 'function', **kwargs) -> CodeSymbol:
        """Create a test code symbol."""
        defaults = {
            'span_start': 1,
            'span_end': 10,
            'parents': [],
            'decorators': [],
        }
        defaults.update(kwargs)

        return CodeSymbol.objects.create(
            file=file_obj,
            name=name,
            kind=kind,
            **defaults
        )

    def create_test_relation(self, source: CodeSymbol, target: CodeSymbol, kind: str = 'call', **kwargs) -> SymbolRelation:
        """Create a test symbol relation."""
        defaults = {'line_number': 5}
        defaults.update(kwargs)

        return SymbolRelation.objects.create(
            source=source,
            target=target,
            kind=kind,
            **defaults
        )


class FileSystemTestCase(MentorTestCase):
    """Test case that provides a temporary file system for testing."""

    def setUp(self):
        super().setUp()
        # Create temporary directory
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)

    def create_python_file(self, relative_path: str, content: str) -> Path:
        """Create a Python file in the temp directory."""
        file_path = self.temp_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return file_path

    def mock_project_root(self):
        """Mock the Django project root to point to temp directory."""
        return patch.object(settings, 'BASE_DIR', self.temp_dir)


class IndexingTestCase(FileSystemTestCase):
    """Test case for indexing functionality."""

    def assert_file_indexed(self, path: str, content: str = None):
        """Assert that a file has been indexed."""
        file_obj = IndexedFile.objects.filter(path=path).first()
        self.assertIsNotNone(file_obj, f"File {path} was not indexed")

        if content is not None:
            self.assertEqual(file_obj.content_preview, content[:1000])

        return file_obj

    def assert_symbol_exists(self, file_path: str, symbol_name: str, symbol_kind: str = None):
        """Assert that a symbol exists in the index."""
        file_obj = IndexedFile.objects.get(path=file_path)
        symbol = file_obj.symbols.filter(name=symbol_name).first()
        self.assertIsNotNone(symbol, f"Symbol {symbol_name} not found in {file_path}")

        if symbol_kind:
            self.assertEqual(symbol.kind, symbol_kind)

        return symbol

    def assert_relation_exists(self, source_name: str, target_name: str, relation_kind: str):
        """Assert that a relation exists between symbols."""
        relation = SymbolRelation.objects.filter(
            source__name=source_name,
            target__name=target_name,
            kind=relation_kind
        ).first()
        self.assertIsNotNone(
            relation,
            f"Relation {source_name} --{relation_kind}--> {target_name} not found"
        )
        return relation


class GoldenFileTestCase(MentorTestCase):
    """Test case for golden file testing."""

    def setUp(self):
        super().setUp()
        self.golden_dir = Path(__file__).parent / 'golden'
        self.golden_dir.mkdir(exist_ok=True)

    def load_golden_file(self, filename: str) -> str:
        """Load content from a golden file."""
        golden_path = self.golden_dir / filename
        if not golden_path.exists():
            self.fail(f"Golden file {filename} does not exist")
        return golden_path.read_text()

    def save_golden_file(self, filename: str, content: str):
        """Save content to a golden file (for generating test data)."""
        golden_path = self.golden_dir / filename
        golden_path.write_text(content)

    def assert_matches_golden(self, actual: str, golden_filename: str, update_golden: bool = False):
        """Assert that actual content matches golden file."""
        if update_golden:
            self.save_golden_file(golden_filename, actual)
            return

        expected = self.load_golden_file(golden_filename)
        self.assertEqual(
            actual.strip(),
            expected.strip(),
            f"Content does not match golden file {golden_filename}"
        )


class MockGitTestCase(MentorTestCase):
    """Test case that provides git mocking utilities."""

    def setUp(self):
        super().setUp()
        self.git_patches = []

    def tearDown(self):
        super().tearDown()
        for patch_obj in self.git_patches:
            patch_obj.stop()

    def mock_git_commit(self, commit_sha: str = 'abc123def456'):
        """Mock git commit SHA."""
        mock_patch = patch('subprocess.run')
        mock_run = mock_patch.start()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = commit_sha
        self.git_patches.append(mock_patch)
        return commit_sha

    def mock_git_diff(self, changed_files: List[str]):
        """Mock git diff to return specific changed files."""
        mock_patch = patch('subprocess.run')
        mock_run = mock_patch.start()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '\n'.join(changed_files)
        self.git_patches.append(mock_patch)


class PerformanceTestCase(MentorTestCase):
    """Test case for performance testing."""

    def assert_performance_within(self, func, max_seconds: float, *args, **kwargs):
        """Assert that function executes within time limit."""
        import time
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start

        self.assertLess(
            elapsed,
            max_seconds,
            f"Function took {elapsed:.2f}s, expected < {max_seconds}s"
        )

        return result

    def assert_query_count_within(self, expected_count: int, tolerance: int = 0):
        """Assert that query count is within expected range."""
        from django.test.utils import override_settings
        from django.db import connection

        def decorator(func):
            def wrapper(*args, **kwargs):
                with override_settings(DEBUG=True):
                    initial_queries = len(connection.queries)
                    result = func(*args, **kwargs)
                    final_queries = len(connection.queries)

                    actual_count = final_queries - initial_queries
                    max_allowed = expected_count + tolerance

                    self.assertLessEqual(
                        actual_count,
                        max_allowed,
                        f"Query count {actual_count} exceeds expected {expected_count} ± {tolerance}"
                    )

                    return result
            return wrapper
        return decorator


# Test data fixtures
SAMPLE_PYTHON_FILES = {
    'simple_function.py': '''
def hello_world():
    """Print hello world."""
    print("Hello, world!")
    return "hello"

class SimpleClass:
    """A simple test class."""

    def __init__(self):
        self.value = 42

    def get_value(self):
        """Get the value."""
        return self.value

CONSTANT_VALUE = "test"
''',

    'django_model.py': '''
from django.db import models

class User(models.Model):
    """User model."""

    name = models.CharField(max_length=100)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.name

class Profile(models.Model):
    """User profile model."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
''',

    'django_views.py': '''
from django.shortcuts import render
from django.http import JsonResponse
from .models import User

def user_list(request):
    """List all users."""
    users = User.objects.all()
    return render(request, 'users.html', {'users': users})

def user_detail(request, user_id):
    """Get user details."""
    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({'name': user.name, 'email': user.email})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
''',

    'test_example.py': '''
import unittest
from django.test import TestCase
from .models import User

class UserModelTest(TestCase):
    """Test the User model."""

    def setUp(self):
        self.user = User.objects.create(
            name="Test User",
            email="test@example.com"
        )

    def test_user_creation(self):
        """Test that user is created correctly."""
        self.assertEqual(self.user.name, "Test User")
        self.assertEqual(self.user.email, "test@example.com")

    def test_str_representation(self):
        """Test string representation."""
        self.assertEqual(str(self.user), "Test User")
'''
}