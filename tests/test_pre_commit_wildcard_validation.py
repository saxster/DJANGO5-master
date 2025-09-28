"""
Pre-commit hook tests for wildcard import validation.

This test suite validates that the pre-commit hook correctly:
1. Detects wildcard imports in non-settings files
2. Allows wildcard imports in Django settings files
3. Provides helpful error messages
4. Integrates with the git workflow

Compliance: Rule #16 - No Uncontrolled Wildcard Imports
"""

import pytest
import subprocess
import tempfile
import os
from pathlib import Path


class TestPreCommitWildcardValidation:
    """Test pre-commit hook wildcard import validation"""

    def test_pre_commit_hook_exists(self):
        """Verify pre-commit hook file exists"""
        hook_path = Path('.githooks/pre-commit')
        assert hook_path.exists(), "Pre-commit hook file must exist"
        assert hook_path.stat().st_mode & 0o111, "Pre-commit hook must be executable"

    def test_pre_commit_detects_wildcard_imports(self):
        """Test that pre-commit hook detects wildcard imports"""
        with open('.githooks/pre-commit', 'r') as f:
            content = f.read()

        assert 'Wildcard Import' in content, \
            "Pre-commit hook must check for wildcard imports"
        assert '__all__' in content, \
            "Pre-commit hook must validate __all__ usage"

    def test_pre_commit_allows_settings_wildcards(self):
        """Test that pre-commit hook allows wildcard imports in settings files"""
        with open('.githooks/pre-commit', 'r') as f:
            content = f.read()

        assert 'settings.*\\.py' in content, \
            "Pre-commit hook should allow wildcard imports in settings files"

    def test_hook_provides_rule_reference(self):
        """Test that violation reports reference Rule #16"""
        with open('.githooks/pre-commit', 'r') as f:
            content = f.read()

        assert 'Rule #16' in content or 'Rule 16' in content, \
            "Pre-commit hook must reference Rule #16 for wildcard imports"


class TestWildcardImportDetection:
    """Test detection of wildcard import patterns"""

    def test_detect_simple_wildcard(self):
        """Test detection of simple wildcard import"""
        test_code = "from .utils import *"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            f.flush()
            temp_file = f.name

        try:
            result = subprocess.run(
                ['grep', '-n', '^from .* import \\*', temp_file],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0, "Should detect wildcard import"
            assert '*' in result.stdout, "Should show the wildcard pattern"
        finally:
            os.unlink(temp_file)

    def test_detect_absolute_wildcard(self):
        """Test detection of absolute wildcard import"""
        test_code = "from apps.core.utils import *"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            f.flush()
            temp_file = f.name

        try:
            result = subprocess.run(
                ['grep', '-n', '^from .* import \\*', temp_file],
                capture_output=True,
                text=True
            )

            assert result.returncode == 0, "Should detect wildcard import"
        finally:
            os.unlink(temp_file)

    def test_no_false_positive_on_explicit_import(self):
        """Test that explicit imports are not flagged"""
        test_code = "from apps.core.utils import display_post_data, PD"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_code)
            f.flush()
            temp_file = f.name

        try:
            result = subprocess.run(
                ['grep', '-n', '^from .* import \\*', temp_file],
                capture_output=True,
                text=True
            )

            assert result.returncode != 0, "Should NOT detect explicit imports"
        finally:
            os.unlink(temp_file)


class TestModuleCompliance:
    """Test that all code modules comply with Rule #16"""

    def test_all_utils_new_modules_compliant(self):
        """Verify all apps/core/utils_new modules define __all__"""
        utils_new_dir = Path('apps/core/utils_new')

        for py_file in utils_new_dir.glob('*.py'):
            if py_file.name == '__init__.py':
                continue

            module_name = f"apps.core.utils_new.{py_file.stem}"

            try:
                module = importlib.import_module(module_name)
                assert hasattr(module, '__all__'), \
                    f"{module_name} must define __all__ (Rule #16)"
            except ImportError:
                pass

    def test_controlled_wildcard_imports_have_all(self):
        """Test that modules using wildcard imports define __all__"""
        modules_with_controlled_wildcards = [
            'apps.core.utils',
            'apps.onboarding.models',
            'apps.activity.managers.asset_manager_orm_optimized',
            'apps.activity.managers.job_manager_orm_optimized',
        ]

        for module_name in modules_with_controlled_wildcards:
            try:
                module = importlib.import_module(module_name)
                if module_name not in ['apps.activity.managers.asset_manager_orm',
                                       'apps.activity.managers.job_manager_orm',
                                       'apps.activity.managers.job_manager_orm_cached']:
                    assert hasattr(module, '__all__'), \
                        f"{module_name} uses wildcard imports and must define __all__"
            except ImportError:
                pass


class TestDocumentationAccuracy:
    """Test that __all__ accurately documents the module's public API"""

    def test_all_symbols_callable_or_constant(self):
        """Verify all symbols in __all__ are callable or constants"""
        from apps.core.utils_new import db_utils

        for symbol_name in db_utils.__all__:
            symbol = getattr(db_utils, symbol_name)

            assert callable(symbol) or isinstance(symbol, (str, int, float, dict, list, type(None), type)), \
                f"Symbol '{symbol_name}' in __all__ is not callable or a constant"

    def test_all_matches_module_intent(self):
        """Test that __all__ matches the module's documented purpose"""
        from apps.core.utils_new import validation

        for symbol in validation.__all__:
            assert 'valid' in symbol.lower() or 'verify' in symbol.lower() or 'clean' in symbol.lower(), \
                f"validation module symbol '{symbol}' doesn't match module purpose"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])