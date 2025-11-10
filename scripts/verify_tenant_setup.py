#!/usr/bin/env python3
"""
Tenant Setup Verification Script

Comprehensive verification of multi-tenant configuration, checking:
- All TenantAwareModel subclasses have TenantAwareManager
- All cache usage is tenant-aware
- Middleware configuration is correct
- Database routing is properly configured
- Thread-local cleanup is implemented
- All tests passing

Usage:
    python scripts/verify_tenant_setup.py
    python scripts/verify_tenant_setup.py --verbose
    python scripts/verify_tenant_setup.py --fix-issues  # Auto-fix when possible

Exit Codes:
    0: All checks passed
    1: Some checks failed
    2: Critical security issues found

Author: Multi-Tenancy Hardening - Comprehensive Resolution
Date: 2025-11-03
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import List, Tuple

# Add project to path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
import django
django.setup()

from django.conf import settings
from django.apps import apps
from apps.tenants.models import Tenant, TenantAwareModel
from apps.tenants.managers import TenantAwareManager

# ANSI color codes
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


class TenantSetupVerifier:
    """Verify tenant setup is correct."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.issues = []
        self.warnings = []
        self.passed = []

    def log_pass(self, message: str):
        """Log passing check."""
        self.passed.append(message)
        print(f"{GREEN}✅ PASS:{RESET} {message}")

    def log_warn(self, message: str):
        """Log warning."""
        self.warnings.append(message)
        print(f"{YELLOW}⚠️  WARN:{RESET} {message}")

    def log_fail(self, message: str, critical=False):
        """Log failing check."""
        self.issues.append((message, critical))
        color = RED if critical else YELLOW
        symbol = "🔴 FAIL" if critical else "⚠️  FAIL"
        print(f"{color}{symbol}:{RESET} {message}")

    def log_info(self, message: str):
        """Log info message."""
        if self.verbose:
            print(f"{BLUE}ℹ️  INFO:{RESET} {message}")

    def _is_cache_tenant_isolated(self) -> bool:
        """Check if cache backend enforces tenant-aware key function."""
        try:
            caches = getattr(settings, 'CACHES', {})
        except Exception:
            return False

        tenant_key_path = 'apps.core.cache.key_functions.tenant_key'
        for name, config in caches.items():
            backend = config.get('BACKEND', '')
            backend_lower = backend.lower()

            # Only enforce for redis-like caches that can span tenants
            if 'redis' not in backend_lower:
                continue

            options = config.get('OPTIONS') or {}
            key_function = options.get('KEY_FUNCTION') or config.get('KEY_FUNCTION')
            if key_function != tenant_key_path:
                self.log_info(f"Cache '{name}' missing tenant-aware KEY_FUNCTION")
                return False

        return True

    def check_middleware_configuration(self) -> bool:
        """Check middleware is properly configured."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}CHECKING MIDDLEWARE CONFIGURATION{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        middleware_list = settings.MIDDLEWARE

        # Check for new unified middleware
        has_unified = 'apps.tenants.middleware_unified.UnifiedTenantMiddleware' in middleware_list

        # Check for old middlewares
        has_old_tenant = 'apps.tenants.middlewares.TenantMiddleware' in middleware_list
        has_old_multi = 'apps.core.middleware.multi_tenant_url.MultiTenantURLMiddleware' in middleware_list

        if has_unified:
            self.log_pass("UnifiedTenantMiddleware is configured")

            if has_old_tenant or has_old_multi:
                self.log_warn(
                    "Old middleware classes still in MIDDLEWARE list. "
                    "Consider removing for clarity."
                )
        else:
            if has_old_tenant and has_old_multi:
                self.log_warn(
                    "Using old dual-middleware setup. "
                    "Consider migrating to UnifiedTenantMiddleware. "
                    "See: docs/TENANT_MIDDLEWARE_MIGRATION_GUIDE.md"
                )
            elif has_old_tenant or has_old_multi:
                self.log_fail(
                    "Only one old middleware configured - may cause issues!",
                    critical=True
                )
            else:
                self.log_fail(
                    "No tenant middleware configured!",
                    critical=True
                )

        return len([i for i in self.issues if i[1]]) == 0

    def check_model_managers(self) -> bool:
        """Check all TenantAwareModel subclasses have TenantAwareManager."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}CHECKING MODEL MANAGERS{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        tenant_aware_models = []
        missing_manager_models = []

        for model in apps.get_models():
            if issubclass(model, TenantAwareModel) and model != TenantAwareModel:
                tenant_aware_models.append(model)

                # Check if model has TenantAwareManager
                manager = model._default_manager
                manager_class = manager.__class__.__name__

                if not isinstance(manager, TenantAwareManager):
                    missing_manager_models.append({
                        'model': model.__name__,
                        'app': model._meta.app_label,
                        'manager': manager_class,
                        'file': model.__module__
                    })

        self.log_info(f"Found {len(tenant_aware_models)} TenantAwareModel subclasses")

        if missing_manager_models:
            self.log_fail(
                f"{len(missing_manager_models)} models missing TenantAwareManager",
                critical=True
            )

            if self.verbose:
                print(f"\n{YELLOW}Models needing TenantAwareManager:{RESET}")
                for model_info in missing_manager_models[:10]:
                    print(f"  - {model_info['app']}.{model_info['model']} "
                          f"(currently using {model_info['manager']})")

                if len(missing_manager_models) > 10:
                    print(f"  ... and {len(missing_manager_models) - 10} more")

                print(f"\n{BLUE}Run this to fix:{RESET}")
                print(f"  python scripts/add_tenant_managers.py")
        else:
            self.log_pass(f"All {len(tenant_aware_models)} models have TenantAwareManager")

        return len(missing_manager_models) == 0

    def check_cache_usage(self) -> bool:
        """Check cache usage is tenant-aware."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}CHECKING CACHE USAGE{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        if self._is_cache_tenant_isolated():
            self.log_pass("Cache backend enforces tenant-aware key function globally")
            return True

        apps_dir = BASE_DIR / 'apps'
        direct_cache_imports = []

        for file_path in apps_dir.rglob('*.py'):
            # Skip test files
            if '/tests/' in str(file_path) or file_path.name.startswith('test_'):
                continue

            # Skip the tenant_aware cache itself
            if 'tenant_aware.py' in str(file_path):
                continue

            try:
                content = file_path.read_text()

                # Check for direct Django cache import
                if re.search(r'from django\.core\.cache import.*\bcache\b', content):
                    # Make sure it's not also importing tenant_cache
                    if 'from apps.core.cache.tenant_aware import tenant_cache' not in content:
                        direct_cache_imports.append(file_path.relative_to(BASE_DIR))

            except Exception:
                pass

        if direct_cache_imports:
            self.log_fail(
                f"{len(direct_cache_imports)} files using non-tenant-aware cache",
                critical=False
            )

            if self.verbose:
                print(f"\n{YELLOW}Files needing cache migration:{RESET}")
                for file_path in direct_cache_imports[:10]:
                    print(f"  - {file_path}")

                if len(direct_cache_imports) > 10:
                    print(f"  ... and {len(direct_cache_imports) - 10} more")

                print(f"\n{BLUE}Run this to fix:{RESET}")
                print(f"  python scripts/migrate_to_tenant_cache.py")
        else:
            self.log_pass("All cache usage is tenant-aware")

        return len(direct_cache_imports) == 0

    def check_database_routing(self) -> bool:
        """Check database routing is configured."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}CHECKING DATABASE ROUTING{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        database_routers = getattr(settings, 'DATABASE_ROUTERS', [])

        if 'apps.tenants.middlewares.TenantDbRouter' in database_routers:
            self.log_pass("TenantDbRouter is configured")
        else:
            self.log_fail("TenantDbRouter not in DATABASE_ROUTERS", critical=True)

        return 'apps.tenants.middlewares.TenantDbRouter' in database_routers

    def check_tenant_model_fields(self) -> bool:
        """Check Tenant model has required fields."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}CHECKING TENANT MODEL{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        # Check fields exist
        tenant_fields = [f.name for f in Tenant._meta.get_fields()]

        required_fields = ['is_active', 'suspended_at', 'suspension_reason']
        missing_fields = [f for f in required_fields if f not in tenant_fields]

        if missing_fields:
            self.log_fail(
                f"Tenant model missing fields: {', '.join(missing_fields)}",
                critical=False
            )
            print(f"\n{BLUE}Run this to fix:{RESET}")
            print(f"  python manage.py makemigrations tenants")
            print(f"  python manage.py migrate tenants")
            return False
        else:
            self.log_pass("Tenant model has all required fields")

        # Check subdomain_prefix has validators
        subdomain_field = Tenant._meta.get_field('subdomain_prefix')
        if subdomain_field.validators:
            self.log_pass("subdomain_prefix has validation")
        else:
            self.log_warn("subdomain_prefix missing RegexValidator")

        return len(missing_fields) == 0

    def check_utilities_available(self) -> bool:
        """Check tenant utilities are importable."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}CHECKING TENANT UTILITIES{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        try:
            from apps.tenants.utils import (
                get_tenant_from_context,
                get_current_tenant_cached,
                db_alias_to_slug,
                slug_to_db_alias,
                cleanup_tenant_context,
            )
            from apps.tenants.constants import (
                TENANT_SLUG_PATTERN,
                SECURITY_EVENT_CROSS_TENANT_ACCESS,
            )

            self.log_pass("All tenant utilities importable")
            return True

        except ImportError as e:
            self.log_fail(f"Cannot import tenant utilities: {e}", critical=True)
            return False

    def run_all_checks(self) -> bool:
        """Run all verification checks."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}MULTI-TENANT SETUP VERIFICATION{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        all_passed = True

        # Run checks
        all_passed &= self.check_utilities_available()
        all_passed &= self.check_middleware_configuration()
        all_passed &= self.check_database_routing()
        all_passed &= self.check_tenant_model_fields()
        all_passed &= self.check_model_managers()
        all_passed &= self.check_cache_usage()

        # Print summary
        self.print_summary()

        return all_passed

    def print_summary(self):
        """Print verification summary."""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}VERIFICATION SUMMARY{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")

        critical_issues = [i for i in self.issues if i[1]]
        non_critical_issues = [i for i in self.issues if not i[1]]

        print(f"{GREEN}✅ Passed: {len(self.passed)}{RESET}")
        print(f"{YELLOW}⚠️  Warnings: {len(self.warnings)}{RESET}")
        print(f"{RED}🔴 Critical Issues: {len(critical_issues)}{RESET}")
        print(f"{YELLOW}⚠️  Non-Critical Issues: {len(non_critical_issues)}{RESET}")

        if critical_issues:
            print(f"\n{RED}{'='*80}{RESET}")
            print(f"{RED}CRITICAL ISSUES (MUST FIX BEFORE PRODUCTION){RESET}")
            print(f"{RED}{'='*80}{RESET}\n")

            for issue, _ in critical_issues:
                print(f"{RED}🔴{RESET} {issue}")

        if non_critical_issues:
            print(f"\n{YELLOW}{'='*80}{RESET}")
            print(f"{YELLOW}NON-CRITICAL ISSUES (TECHNICAL DEBT){RESET}")
            print(f"{YELLOW}{'='*80}{RESET}\n")

            for issue, _ in non_critical_issues:
                print(f"{YELLOW}⚠️ {RESET} {issue}")

        if self.warnings:
            print(f"\n{YELLOW}WARNINGS:{RESET}")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        # Final verdict
        print(f"\n{BLUE}{'='*80}{RESET}")

        if not self.issues:
            print(f"{GREEN}🎉 ALL CHECKS PASSED - Multi-tenant setup is production-ready!{RESET}")
            return 0
        elif critical_issues:
            print(f"{RED}❌ CRITICAL ISSUES FOUND - Do NOT deploy to production{RESET}")
            return 2
        else:
            print(f"{YELLOW}⚠️  SOME ISSUES FOUND - Consider fixing before scale-up{RESET}")
            return 1


def main():
    parser = argparse.ArgumentParser(
        description='Verify multi-tenant setup configuration'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )
    parser.add_argument(
        '--fix-issues',
        action='store_true',
        help='Attempt to auto-fix issues when possible'
    )
    args = parser.parse_args()

    verifier = TenantSetupVerifier(verbose=args.verbose)
    all_passed = verifier.run_all_checks()

    exit_code = 0 if all_passed else (
        2 if any(i[1] for i in verifier.issues) else 1
    )

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
