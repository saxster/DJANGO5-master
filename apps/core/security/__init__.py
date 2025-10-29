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
from .policy_registry import SecurityPolicyRegistry, register_policy, get_policy
from .secrets_rotation import rotate_secret, SecretRotationSchedule
from .token_binding import TokenBindingService, verify_token_binding
from .websocket_token_binding import WebsocketTokenBindingService

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
    "rotate_secret",
    "SecretRotationSchedule",
    "TokenBindingService",
    "verify_token_binding",
    "WebsocketTokenBindingService",
]
