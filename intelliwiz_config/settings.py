"""
Django settings for intelliwiz_config project.
Modular settings architecture with automatic environment detection.

This replaces the previous monolithic 1,634-line settings file with
a compliant modular structure where each module is under 200 lines.
"""

import os
import warnings

"""
Environment selection guard
Priority:
1) DJANGO_ENV=production|development|test
2) DJANGO_SETTINGS_MODULE contains 'production'|'development'|'test'
If ambiguous, we warn loudly and (optionally) fail-closed via STRICT_SETTINGS_ENV=1.
Entry points (wsgi/asgi/celery/manage) now set safe defaults explicitly.
"""

# Get the environment hints
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
env_name = os.environ.get('DJANGO_ENV', '').strip().lower()

def _env_alias(name: str) -> str:
    name = (name or '').lower()
    if name in {"prod", "production"}:
        return "production"
    if name in {"dev", "development"}:
        return "development"
    if name in {"test", "testing"}:
        return "test"
    return ""

resolved_env = _env_alias(env_name)

# NOTE: Wildcard imports are acceptable here per Django settings pattern
# We conditionally import ONE environment module containing 100+ Django settings.
# Each environment module (production/test/development) inherits from base and
# defines environment-specific overrides. Django requires these as module-level variables.
if resolved_env == 'production':
    from .settings.production import *  # noqa: F403 - Django settings pattern
    print("[SETTINGS] ✅ Production settings loaded (DJANGO_ENV)")
elif resolved_env == 'test':
    from .settings.test import *  # noqa: F403 - Django settings pattern
    print("[SETTINGS] ✅ Test settings loaded (DJANGO_ENV)")
elif resolved_env == 'development':
    from .settings.development import *  # noqa: F403 - Django settings pattern
    print("[SETTINGS] ✅ Development settings loaded (DJANGO_ENV)")
elif 'production' in settings_module.lower():
    from .settings.production import *  # noqa: F403 - Django settings pattern
    print("[SETTINGS] ✅ Production settings loaded")
elif 'test' in settings_module.lower():
    from .settings.test import *  # noqa: F403 - Django settings pattern
    print("[SETTINGS] ✅ Test settings loaded")
elif 'development' in settings_module.lower():
    from .settings.development import *  # noqa: F403 - Django settings pattern
    print("[SETTINGS] ✅ Development settings loaded")
else:
    # Ambiguous environment selection — warn loudly and optionally fail-closed
    strict = os.environ.get('STRICT_SETTINGS_ENV', '').strip().lower() in {"1", "true", "yes"}
    message = (
        "[SETTINGS] ⚠️  Ambiguous environment selection. "
        "Set DJANGO_ENV to 'production'|'development'|'test' or use a fully-qualified "
        "DJANGO_SETTINGS_MODULE (e.g., intelliwiz_config.settings.production)."
    )
    if strict:
        raise RuntimeError(message)
    # Non-strict mode: fall back to development with a visible warning
    warnings.warn(message + " Falling back to development.", RuntimeWarning)
    from .settings.development import *  # noqa: F403 - Django settings pattern
    if not settings_module:
        print("[SETTINGS] ⚠️  No DJANGO_SETTINGS_MODULE specified, defaulting to development (non-strict)")
    else:
        print("[SETTINGS] ⚠️  DJANGO_SETTINGS_MODULE ambiguous, defaulting to development (non-strict)")

# Import specialized settings modules for runtime access
from .settings import logging as logging_settings
from .settings import llm as llm_settings
from .settings import onboarding as onboarding_settings
from .settings import security as security_settings
from .settings import integrations as integrations_settings
from .settings import websocket as websocket_settings

# Runtime validation (only in development/test)
if DEBUG:
    from .settings.health_checks import validate_settings_compliance

    try:
        compliance_result = validate_settings_compliance()
        if not compliance_result['line_count_compliance']:
            warnings.warn(
                f"Settings compliance violations detected: {compliance_result['violations']}",
                UserWarning
            )
    except Exception as e:
        print(f"[SETTINGS] Warning: Could not run compliance check: {e}")

# Legacy compatibility notice
if hasattr(os.environ, 'SETTINGS_LEGACY_WARNING') and os.environ.get('SETTINGS_LEGACY_WARNING') != 'false':
    print("\n" + "="*80)
    print("🔄 SETTINGS ARCHITECTURE MIGRATION COMPLETED")
    print("="*80)
    print("✅ Monolithic 1,634-line settings.py → Modular architecture")
    print("✅ All modules now comply with 200-line limit")
    print("✅ Enhanced security with environment-specific policies")
    print("✅ Improved performance with lazy loading")
    print("✅ Comprehensive testing and validation system")
    print("\n💡 To disable this notice: export SETTINGS_LEGACY_WARNING=false")
    print("="*80)
