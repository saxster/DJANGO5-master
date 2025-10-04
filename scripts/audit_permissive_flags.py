#!/usr/bin/env python
"""
Audit script to detect permissive security flags.
Run before production deployment to ensure all security settings are production-ready.

Usage:
    python scripts/audit_permissive_flags.py

Exit codes:
    0 = All security flags properly configured
    1 = Issues found (deployment should be blocked)

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #4: Secure secret management validation
"""

import os
import sys
import django
from typing import List, Tuple

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.production')
django.setup()

from django.conf import settings


def audit_security_flags() -> Tuple[bool, List[str]]:
    """
    Check all permissive flags are overridden in production.

    Returns:
        Tuple of (all_passed: bool, issues: List[str])
    """
    issues = []

    # Check 1: Language cookie security
    if not getattr(settings, 'LANGUAGE_COOKIE_SECURE', False):
        issues.append("LANGUAGE_COOKIE_SECURE is False (cookies can be intercepted over HTTP)")

    # Check 2: JWT expiration verification
    jwt_config = getattr(settings, 'GRAPHQL_JWT', {})
    if not jwt_config.get('JWT_VERIFY_EXPIRATION', False):
        issues.append("JWT_VERIFY_EXPIRATION is disabled (tokens never expire)")

    # Check 3: JWT expiration time (should be <= 4 hours for production)
    jwt_expiry_hours = jwt_config.get('JWT_EXPIRATION_DELTA', None)
    if jwt_expiry_hours:
        hours = jwt_expiry_hours.total_seconds() / 3600
        if hours > 4:
            issues.append(f"JWT tokens expire after {hours} hours (too long for production, should be <= 2 hours)")
    else:
        issues.append("JWT_EXPIRATION_DELTA is not set")

    # Check 4: GraphQL origin validation
    if not getattr(settings, 'GRAPHQL_STRICT_ORIGIN_VALIDATION', False):
        issues.append("GRAPHQL_STRICT_ORIGIN_VALIDATION is disabled (any origin can query API)")

    # Check 5: Jinja2 auto-reload (performance impact)
    templates = getattr(settings, 'TEMPLATES', [])
    for template in templates:
        if 'jinja2' in template.get('BACKEND', '').lower():
            if template.get('OPTIONS', {}).get('auto_reload', False):
                issues.append("Jinja2 auto_reload is enabled (performance impact in production)")

    # Check 6: DEBUG setting (critical)
    if getattr(settings, 'DEBUG', False):
        issues.append("DEBUG is True (CRITICAL: exposes stack traces and internal details)")

    # Check 7: SECRET_KEY strength
    secret_key = getattr(settings, 'SECRET_KEY', '')
    if len(secret_key) < 50:
        issues.append(f"SECRET_KEY is too short ({len(secret_key)} characters, minimum 50)")

    # Check 8: ALLOWED_HOSTS configuration
    allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
    if not allowed_hosts or '*' in allowed_hosts:
        issues.append("ALLOWED_HOSTS not properly configured (contains wildcard or is empty)")

    # Check 9: CSRF cookie security
    if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
        issues.append("CSRF_COOKIE_SECURE is False (CSRF tokens can be intercepted)")

    # Check 10: Session cookie security
    if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
        issues.append("SESSION_COOKIE_SECURE is False (session IDs can be intercepted)")

    # Check 11: SSL redirect
    if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
        issues.append("SECURE_SSL_REDIRECT is False (HTTP traffic not redirected to HTTPS)")

    all_passed = len(issues) == 0
    return all_passed, issues


def print_results(all_passed: bool, issues: List[str]):
    """Print audit results in a formatted way"""
    print("\n" + "="*80)
    print("🔒 PRODUCTION SECURITY AUDIT - Permissive Flags Check")
    print("="*80 + "\n")

    if all_passed:
        print("✅ ALL SECURITY FLAGS PROPERLY CONFIGURED FOR PRODUCTION")
        print("\nNo issues found. Deployment can proceed.\n")
    else:
        print("🚨 PERMISSIVE SECURITY FLAGS DETECTED:")
        print("\nThe following issues must be fixed before production deployment:\n")

        for i, issue in enumerate(issues, 1):
            print(f"  {i}. ❌ {issue}")

        print("\n" + "="*80)
        print(f"Total issues found: {len(issues)}")
        print("="*80)
        print("\n⚠️  DEPLOYMENT BLOCKED - Fix the above issues and re-run this audit.\n")
        print("📚 See documentation:")
        print("   - PERMISSIVE_SECURITY_FLAGS_DOCUMENTATION.md")
        print("   - SECURITY_SETTINGS_CHECKLIST.md")
        print("   - SECURITY_FIXES_CRITICAL.md\n")

    print("="*80 + "\n")


def main():
    """Main entry point"""
    try:
        all_passed, issues = audit_security_flags()
        print_results(all_passed, issues)

        # Exit with appropriate code
        sys.exit(0 if all_passed else 1)

    except Exception as e:
        print(f"\n🚨 ERROR during security audit: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()