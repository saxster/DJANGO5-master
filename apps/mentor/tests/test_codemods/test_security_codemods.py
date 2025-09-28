"""
Tests for LibCST-based security codemods.
"""

import unittest
from pathlib import Path
import tempfile

try:
    import libcst as cst
    from apps.mentor.codemods.security_codemods import (
        SQLInjectionFixCodemod, XSSPreventionCodemod, CSRFProtectionCodemod,
        SecureRandomCodemod, HardcodedPasswordRemovalCodemod,
        get_security_codemod
    )
    from apps.mentor.codemods.codemod_engine import CodemodEngine
    LIBCST_AVAILABLE = True
except ImportError:
    LIBCST_AVAILABLE = False


@unittest.skipUnless(LIBCST_AVAILABLE, "LibCST not available")
class TestSQLInjectionFixCodemod(unittest.TestCase):
    """Test SQL injection fix codemod."""

    def setUp(self):
        self.context = cst.codemod.CodemodContext()
        self.codemod = SQLInjectionFixCodemod(self.context)

    def test_fixes_raw_query_with_percent_s(self):
        """Test fixing raw queries with %s parameters."""
        source_code = '''
def get_users(user_id):
    return User.objects.raw("SELECT * FROM users WHERE id = %s", [user_id])
'''

        expected_contains = "%(param1)s"

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertIn(expected_contains, result_code)
        self.assertNotIn("%s", result_code)

    def test_ignores_safe_raw_queries(self):
        """Test that safe raw queries are not modified."""
        source_code = '''
def get_users():
    return User.objects.raw("SELECT * FROM users WHERE active = %(active)s", {"active": True})
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertEqual(result_code, source_code)

    def test_ignores_non_raw_calls(self):
        """Test that non-raw method calls are not modified."""
        source_code = '''
def process_data():
    return "SELECT * FROM table WHERE id = %s" % value
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertEqual(result_code, source_code)


@unittest.skipUnless(LIBCST_AVAILABLE, "LibCST not available")
class TestXSSPreventionCodemod(unittest.TestCase):
    """Test XSS prevention codemod."""

    def setUp(self):
        self.context = cst.codemod.CodemodContext()
        self.codemod = XSSPreventionCodemod(self.context)

    def test_replaces_mark_safe_with_escape(self):
        """Test replacing mark_safe with escape."""
        source_code = '''
from django.utils.safestring import mark_safe

def render_content(user_input):
    return mark_safe(user_input)
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertIn("escape(user_input)", result_code)
        self.assertNotIn("mark_safe(user_input)", result_code)

    def test_ignores_non_mark_safe_calls(self):
        """Test that other function calls are not modified."""
        source_code = '''
def safe_function():
    return some_other_function(data)
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertEqual(result_code, source_code)


@unittest.skipUnless(LIBCST_AVAILABLE, "LibCST not available")
class TestCSRFProtectionCodemod(unittest.TestCase):
    """Test CSRF protection codemod."""

    def setUp(self):
        self.context = cst.codemod.CodemodContext()
        self.codemod = CSRFProtectionCodemod(self.context)

    def test_adds_csrf_protect_to_view_function(self):
        """Test adding csrf_protect decorator to view functions."""
        source_code = '''
def user_view(request):
    if request.method == "POST":
        return HttpResponse("OK")
    return render(request, "template.html")
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertIn("@csrf_protect", result_code)
        self.assertIn("from django.views.decorators import csrf_protect", result_code)

    def test_ignores_functions_with_existing_csrf_decorators(self):
        """Test that functions with CSRF decorators are not modified."""
        source_code = '''
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def api_view(request):
    return JsonResponse({"status": "ok"})
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        # Should not add csrf_protect since csrf_exempt is present
        self.assertEqual(result_code.count("@csrf"), 1)

    def test_ignores_non_view_functions(self):
        """Test that non-view functions are not modified."""
        source_code = '''
def utility_function(data):
    return process(data)
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertEqual(result_code, source_code)


@unittest.skipUnless(LIBCST_AVAILABLE, "LibCST not available")
class TestSecureRandomCodemod(unittest.TestCase):
    """Test secure random codemod."""

    def setUp(self):
        self.context = cst.codemod.CodemodContext()
        self.codemod = SecureRandomCodemod(self.context)

    def test_replaces_random_randint(self):
        """Test replacing random.randint with secrets equivalent."""
        source_code = '''
import random

def generate_token():
    return random.randint(1000, 9999)
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertIn("secrets.randbits", result_code)
        self.assertIn("import secrets", result_code)

    def test_replaces_random_choice(self):
        """Test replacing random.choice with secrets.choice."""
        source_code = '''
import random

def pick_item(items):
    return random.choice(items)
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertIn("secrets.choice", result_code)
        self.assertNotIn("random.choice", result_code)


@unittest.skipUnless(LIBCST_AVAILABLE, "LibCST not available")
class TestHardcodedPasswordRemovalCodemod(unittest.TestCase):
    """Test hardcoded password removal codemod."""

    def setUp(self):
        self.context = cst.codemod.CodemodContext()
        self.codemod = HardcodedPasswordRemovalCodemod(self.context)

    def test_replaces_hardcoded_password(self):
        """Test replacing hardcoded passwords with environment variables."""
        source_code = '''
def connect_db():
    password = "hardcoded_secret_123"
    return connect(password=password)
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertIn("os.getenv", result_code)
        self.assertIn("import os", result_code)
        self.assertNotIn("hardcoded_secret_123", result_code)

    def test_ignores_non_secret_variables(self):
        """Test that non-secret variables are not modified."""
        source_code = '''
def process_data():
    message = "Hello, world!"
    return message
'''

        tree = cst.parse_module(source_code)
        wrapper = cst.MetadataWrapper(tree)
        transformed = wrapper.visit(self.codemod)

        result_code = transformed.code
        self.assertEqual(result_code, source_code)


@unittest.skipUnless(LIBCST_AVAILABLE, "LibCST not available")
class TestCodemodEngine(unittest.TestCase):
    """Test codemod engine integration."""

    def setUp(self):
        self.engine = CodemodEngine(create_backups=False)

    def test_apply_security_codemod(self):
        """Test applying security codemod to a file."""
        source_code = '''
def unsafe_query(user_id):
    return User.objects.raw("SELECT * FROM users WHERE id = %s", [user_id])
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name

        try:
            result = self.engine.apply_codemod(
                temp_file,
                "sql_injection_fix",
                "security"
            )

            self.assertTrue(result.success)
            self.assertIsNotNone(result.transformed_code)
            self.assertNotEqual(result.original_code, result.transformed_code)

        finally:
            Path(temp_file).unlink()

    def test_preview_changes(self):
        """Test previewing codemod changes."""
        source_code = '''
import random

def generate_id():
    return random.randint(1, 1000)
'''

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(source_code)
            temp_file = f.name

        try:
            diff = self.engine.preview_changes(
                temp_file,
                "secure_random",
                "security"
            )

            self.assertIn("secrets", diff)
            self.assertIn("-", diff)  # Diff format
            self.assertIn("+", diff)

        finally:
            Path(temp_file).unlink()

    def test_get_security_codemod_function(self):
        """Test getting security codemods by name."""
        codemod_class = get_security_codemod("sql_injection_fix")
        self.assertEqual(codemod_class, SQLInjectionFixCodemod)

        codemod_class = get_security_codemod("nonexistent")
        self.assertIsNone(codemod_class)


@unittest.skipIf(LIBCST_AVAILABLE, "LibCST is available")
class TestLibCSTUnavailable(unittest.TestCase):
    """Test behavior when LibCST is not available."""

    def test_import_error_handling(self):
        """Test graceful handling when LibCST is not available."""
        with self.assertRaises(ImportError):
            from apps.mentor.codemods.codemod_engine import CodemodEngine
            CodemodEngine()

    def test_fallback_behavior(self):
        """Test that system falls back gracefully without LibCST."""
        # This would test the fallback mechanisms in patch_generator.py
        # when LibCST is not available
        pass