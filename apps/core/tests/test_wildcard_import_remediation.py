"""
Test suite for wildcard import remediation.

This module ensures that:
1. All utils_new modules have __all__ defined
2. Wildcard imports are properly controlled
3. Backward compatibility is maintained
4. No namespace pollution occurs
5. Circular imports are prevented

Compliance: Rule #16 - No Uncontrolled Wildcard Imports
"""

import pytest
import importlib
import inspect
from typing import List, Set


class TestBackwardCompatibility:
    """Test backward compatibility after wildcard import remediation"""

    def test_core_utils_exports_all_expected_symbols(self):
        """Verify apps.core.utils exports all expected public symbols"""
        from apps.core import utils

        expected_symbols = {
            'display_post_data',
            'PD',
            'printsql',
            'get_select_output',
            'ok',
            'failed',
            'get_email_addresses',
            'send_email',
            'create_client_site',
            'create_user',
            'basic_user_setup',
            'get_changed_keys',
            'generate_timezone_choices',
        }

        for symbol in expected_symbols:
            assert hasattr(utils, symbol), f"Missing expected symbol: {symbol}"

    def test_core_utils_has_all_defined(self):
        """Verify apps.core.utils has __all__ defined"""
        from apps.core import utils

        assert hasattr(utils, '__all__'), "apps.core.utils must define __all__"
        assert isinstance(utils.__all__, (list, tuple)), "__all__ must be a list or tuple"
        assert len(utils.__all__) > 0, "__all__ must not be empty"

    def test_utils_new_modules_have_all_defined(self):
        """Verify all utils_new modules define __all__"""
        modules_to_check = [
            'apps.core.utils_new.business_logic',
            'apps.core.utils_new.date_utils',
            'apps.core.utils_new.db_utils',
            'apps.core.utils_new.file_utils',
            'apps.core.utils_new.http_utils',
            'apps.core.utils_new.string_utils',
            'apps.core.utils_new.validation',
            'apps.core.utils_new.form_security',
            'apps.core.utils_new.error_handling',
            'apps.core.utils_new.sentinel_resolvers',
            # 'apps.core.utils_new.query_optimization',  # REMOVED 2025-10-31: Deprecated (moved to .deprecated/)
            'apps.core.utils_new.query_optimizer',
            'apps.core.utils_new.sql_security',
            'apps.core.utils_new.datetime_utilities',
            'apps.core.utils_new.cron_utilities',
            'apps.core.utils_new.code_validators',
            'apps.core.utils_new.distributed_locks',
        ]

        for module_name in modules_to_check:
            module = importlib.import_module(module_name)
            assert hasattr(module, '__all__'), f"{module_name} must define __all__"
            assert isinstance(module.__all__, (list, tuple)), f"{module_name}.__all__ must be a list or tuple"
            assert len(module.__all__) > 0, f"{module_name}.__all__ must not be empty"

    def test_date_utils_exports_expected_functions(self):
        """Verify date_utils exports expected functions"""
        from apps.core.utils_new import date_utils

        expected = [
            'get_current_year',
            'to_utc',
            'getawaredatetime',
            'format_timedelta',
            'convert_seconds_to_human_readable',
            'get_timezone',
            'find_closest_shift',
        ]

        for func_name in expected:
            assert hasattr(date_utils, func_name), f"Missing function: {func_name}"
            assert func_name in date_utils.__all__, f"{func_name} not in __all__"

    def test_db_utils_exports_expected_functions(self):
        """Verify db_utils exports expected functions"""
        from apps.core.utils_new import db_utils

        expected_functions = [
            'save_common_stuff',
            'runrawsql',
            'get_or_create_none_people',
            'get_or_create_none_bv',
            'hostname_from_request',
            'tenant_db_from_request',
        ]

        for func_name in expected_functions:
            assert hasattr(db_utils, func_name), f"Missing function: {func_name}"
            assert func_name in db_utils.__all__, f"{func_name} not in __all__"

    def test_http_utils_exports_expected_functions(self):
        """Verify http_utils exports expected functions"""
        from apps.core.utils_new import http_utils

        expected = [
            'clean_encoded_form_data',
            'get_clean_form_data',
            'handle_DoesNotExist',
            'handle_Exception',
            'render_form',
            'paginate_results',
        ]

        for func_name in expected:
            assert hasattr(http_utils, func_name), f"Missing function: {func_name}"
            assert func_name in http_utils.__all__, f"{func_name} not in __all__"

    def test_validation_exports_expected_functions(self):
        """Verify validation exports expected functions"""
        from apps.core.utils_new import validation

        expected = [
            'clean_gpslocation',
            'isValidEMEI',
            'verify_mobno',
            'verify_emailaddr',
            'verify_loginid',
            'verify_peoplename',
            'validate_date_format',
        ]

        for func_name in expected:
            assert hasattr(validation, func_name), f"Missing function: {func_name}"
            assert func_name in validation.__all__, f"{func_name} not in __all__"


class TestNamespaceIsolation:
    """Test that wildcard imports don't pollute namespaces"""

    def test_private_functions_not_exported(self):
        """Verify private functions (starting with _) are not in __all__"""
        modules_to_check = [
            'apps.core.utils_new.datetime_utilities',
            'apps.core.utils_new.cron_utilities',
            'apps.core.utils_new.query_optimizer',
        ]

        for module_name in modules_to_check:
            module = importlib.import_module(module_name)
            if hasattr(module, '__all__'):
                for symbol in module.__all__:
                    assert not symbol.startswith('_'), \
                        f"{module_name}.__all__ contains private symbol: {symbol}"

    def test_wildcard_import_respects_all(self):
        """Verify wildcard import only exports symbols in __all__"""
        from apps.core.utils_new import date_utils

        namespace = {}
        exec("from apps.core.utils_new.date_utils import *", namespace)

        imported_symbols = {k for k in namespace.keys() if not k.startswith('__')}

        assert imported_symbols == set(date_utils.__all__), \
            "Wildcard import should only import symbols in __all__"

    def test_no_circular_import_in_utils_new_init(self):
        """Verify utils_new/__init__.py doesn't import from parent utils.py"""
        with open('apps/core/utils_new/__init__.py', 'r') as f:
            content = f.read()

        assert 'from ..utils import *' not in content, \
            "Circular import detected: utils_new/__init__.py imports from ..utils"
        assert 'from apps.core.utils import' not in content, \
            "Circular import detected: utils_new/__init__.py imports from apps.core.utils"

    def test_manager_optimized_files_have_all(self):
        """Verify manager optimized files define __all__"""
        from apps.activity.managers import asset_manager_orm_optimized
        from apps.activity.managers import job_manager_orm_optimized

        assert hasattr(asset_manager_orm_optimized, '__all__'), \
            "asset_manager_orm_optimized must define __all__"
        assert hasattr(job_manager_orm_optimized, '__all__'), \
            "job_manager_orm_optimized must define __all__"

        assert 'AssetManagerORMOptimized' in asset_manager_orm_optimized.__all__
        assert 'JobneedManagerORMOptimized' in job_manager_orm_optimized.__all__


class TestPublicAPIDocumentation:
    """Test that __all__ properly documents the public API"""

    def test_all_contains_only_public_symbols(self):
        """Verify __all__ only contains actually defined public symbols"""
        modules_to_check = [
            'apps.core.utils_new.date_utils',
            'apps.core.utils_new.db_utils',
            'apps.core.utils_new.http_utils',
            'apps.core.utils_new.validation',
            'apps.core.utils_new.string_utils',
        ]

        for module_name in modules_to_check:
            module = importlib.import_module(module_name)

            for symbol in module.__all__:
                assert hasattr(module, symbol), \
                    f"{module_name}.__all__ lists '{symbol}' but it's not defined in the module"

    def test_all_is_complete(self):
        """Verify __all__ includes all public functions/classes"""
        from apps.core.utils_new import validation

        public_symbols = {
            name for name, obj in inspect.getmembers(validation)
            if not name.startswith('_')
            and (inspect.isfunction(obj) or inspect.isclass(obj))
        }

        all_set = set(validation.__all__)

        missing_from_all = public_symbols - all_set

        assert len(missing_from_all) == 0, \
            f"validation module has public symbols not in __all__: {missing_from_all}"

    def test_wildcard_import_stability(self):
        """Test that wildcard imports are stable across code changes"""
        from apps.core import utils

        initial_dir = set(dir(utils))

        del utils

        from apps.core import utils as utils_reimported

        reimported_dir = set(dir(utils_reimported))

        assert initial_dir == reimported_dir, \
            "Wildcard imports should be deterministic across imports"


class TestImportPerformance:
    """Test import performance and circular dependency prevention"""

    def test_utils_import_time_reasonable(self):
        """Verify import time is reasonable (< 1 second)"""
        import time

        start = time.time()
        importlib.import_module('apps.core.utils')
        duration = time.time() - start

        assert duration < 1.0, \
            f"apps.core.utils import took {duration}s (should be < 1s)"

    def test_no_import_errors_from_wildcard_imports(self):
        """Verify all wildcard imports work without errors"""
        modules_with_wildcards = [
            'apps.core.utils',
            'apps.core.utils_new',
            'apps.client_onboarding.models',
            'apps.core_onboarding.models',
        ]

        for module_name in modules_with_wildcards:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                pytest.fail(f"Import error in {module_name}: {e}")


class TestSecurityImplications:
    """Test security-related aspects of import control"""

    def test_internal_functions_not_exposed(self):
        """Verify internal/helper functions aren't accidentally exposed"""
        from apps.core.utils_new import db_utils

        internal_patterns = ['_', 'internal_', 'helper_']

        for symbol in db_utils.__all__:
            for pattern in internal_patterns:
                if symbol.startswith(pattern) and pattern == '_':
                    pytest.fail(
                        f"db_utils.__all__ exposes private symbol: {symbol}"
                    )

    def test_sensitive_constants_not_exported(self):
        """Verify sensitive constants aren't in __all__"""
        from apps.core.utils_new import db_utils

        sensitive_patterns = ['SECRET', 'PASSWORD', 'KEY', 'TOKEN']

        for symbol in db_utils.__all__:
            for pattern in sensitive_patterns:
                if pattern in symbol.upper() and symbol not in ['THREAD_LOCAL']:
                    pytest.fail(
                        f"db_utils.__all__ might expose sensitive constant: {symbol}"
                    )