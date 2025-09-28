"""
Settings validation utilities.
Lightweight validation functions for runtime checks.
"""

import os
from typing import Dict, Any

def quick_health_check() -> Dict[str, Any]:
    """Quick health check for settings modules."""
    errors, warnings = [], []

    # Check critical environment variables
    critical_vars = ['SECRET_KEY', 'ENCRYPT_KEY', 'DBUSER', 'DBNAME', 'DBPASS', 'DBHOST']
    missing_critical = [var for var in critical_vars if not os.getenv(var)]
    if missing_critical:
        errors.append(f"Missing critical variables: {', '.join(missing_critical)}")

    # Check SSL in production
    django_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    if 'production' in django_module.lower():
        if not os.getenv('SECURE_SSL_REDIRECT', '').lower() == 'true':
            warnings.append("SSL redirect not enabled in production")

    return {
        'status': 'healthy' if not errors else 'unhealthy',
        'errors': errors,
        'warnings': warnings,
        'summary': f"{'✅' if not errors else '❌'} {len(errors)} errors, {len(warnings)} warnings"
    }

def validate_line_count_compliance() -> Dict[str, Any]:
    """Quick line count compliance check including security submodules."""
    violations = []
    settings_files = [
        ('base.py', 'intelliwiz_config.settings.base'),
        ('development.py', 'intelliwiz_config.settings.development'),
        ('production.py', 'intelliwiz_config.settings.production'),
        ('logging.py', 'intelliwiz_config.settings.logging'),
        ('security.py', 'intelliwiz_config.settings.security'),
        ('integrations.py', 'intelliwiz_config.settings.integrations'),
        ('llm.py', 'intelliwiz_config.settings.llm'),
        ('onboarding.py', 'intelliwiz_config.settings.onboarding')
    ]

    # Add security submodules for detailed compliance checking
    security_submodules = [
        ('security/headers.py', 'intelliwiz_config.settings.security.headers'),
        ('security/csp.py', 'intelliwiz_config.settings.security.csp'),
        ('security/cors.py', 'intelliwiz_config.settings.security.cors'),
        ('security/authentication.py', 'intelliwiz_config.settings.security.authentication'),
        ('security/rate_limiting.py', 'intelliwiz_config.settings.security.rate_limiting'),
        ('security/graphql.py', 'intelliwiz_config.settings.security.graphql'),
        ('security/file_upload.py', 'intelliwiz_config.settings.security.file_upload'),
        ('security/validation.py', 'intelliwiz_config.settings.security.validation'),
    ]

    all_files = settings_files + security_submodules

    for file_name, module_name in all_files:
        try:
            import importlib, inspect
            module = importlib.import_module(module_name)
            source_lines = len(inspect.getsourcelines(module)[0])
            if source_lines > 200:
                violations.append(f"{file_name}: {source_lines} lines (limit: 200)")
        except Exception as e:
            violations.append(f"Could not check {file_name}: {e}")

    return {
        'compliant': len(violations) == 0,
        'violations': violations,
        'summary': f"{'✅' if not violations else '❌'} {len(violations)} violations found"
    }

def validate_security_basics() -> Dict[str, Any]:
    """Basic security validation."""
    errors, warnings = [], []

    # Check secret key strength
    secret_key = os.getenv('SECRET_KEY', '')
    if len(secret_key) < 32:
        errors.append("SECRET_KEY too short (minimum 32 characters)")

    # Check debug mode in production
    django_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    if 'production' in django_module.lower():
        if os.getenv('DEBUG', '').lower() == 'true':
            errors.append("DEBUG=True in production environment")

    return {
        'secure': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'summary': f"{'✅' if not errors else '❌'} Security check: {len(errors)} errors"
    }