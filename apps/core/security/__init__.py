"""
Core security utilities.

This package exposes defensive helpers used throughout the REST API stack,
including CSRF protections, secrets rotation, token binding, and PII controls.
"""

from .csv_injection_protection import (
    CSVInjectionProtector as CsvInjectionProtector,
    sanitize_csv_value,
    sanitize_csv_data
)
# Alias for backward compatibility
sanitize_csv_fields = sanitize_csv_data
from .mass_assignment_protection import MassAssignmentProtector
# protect_model_fields doesn't exist - only class available
from .pii_redaction import PIIRedactionService, redact_pii
from .policy_registry import SecurityPolicyRegistry, policy_registry as _policy_registry, security_policy_status
try:
    from .secrets_rotation import SecretsRotationService
except (ImportError, AttributeError):
    SecretsRotationService = None
try:
    from .token_binding import TokenBindingService, verify_token_binding
except (ImportError, AttributeError):
    TokenBindingService = None
    verify_token_binding = None
try:
    from .websocket_token_binding import WebsocketTokenBindingService
except (ImportError, AttributeError):
    WebsocketTokenBindingService = None


# Convenience functions for policy registry
def register_policy(policy):
    """Register a new security policy."""
    return _policy_registry.register(policy)


def get_policy(policy_name: str):
    """Get a registered security policy by name."""
    return _policy_registry.policies.get(policy_name)

__all__ = [
    "CsvInjectionProtector",
    "sanitize_csv_fields",
    "sanitize_csv_value",
    "sanitize_csv_data",
    "MassAssignmentProtector",
    # "protect_model_fields",  # Doesn't exist
    "PIIRedactionService",
    "redact_pii",
    "SecurityPolicyRegistry",
    "register_policy",
    "get_policy",
    "security_policy_status",
    "SecretsRotationService",
    "TokenBindingService",
    "verify_token_binding",
    "WebsocketTokenBindingService",
]
