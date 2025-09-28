"""
Security settings package.
Modular security configuration following the 200-line rule.
"""

from .headers import *
from .csp import *
from .cors import *
from .authentication import *
from .rate_limiting import *
from .graphql import *
from .file_upload import *
from .logging import *

# Export environment-specific security functions
from .authentication import (
    get_development_security_settings,
    get_production_security_settings,
    get_test_security_settings
)
from .validation import validate_security_settings

# Security middleware configuration
SECURITY_MIDDLEWARE = [
    'apps.core.error_handling.CorrelationIDMiddleware',
    'apps.core.sql_security.SQLInjectionProtectionMiddleware',
    'apps.core.middleware.file_upload_security_middleware.FileUploadSecurityMiddleware',
    'apps.core.xss_protection.XSSProtectionMiddleware',
    'apps.core.middleware.csp_nonce.CSPNonceMiddleware',
    'apps.core.xss_protection.CSRFHeaderMiddleware',
    'apps.core.error_handling.GlobalExceptionMiddleware',
]