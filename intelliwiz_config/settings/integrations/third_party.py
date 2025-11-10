"""
Third-Party Service Integrations

Non-AWS, non-GCP external services:
- Twilio IVR
- Anthropic Claude LLM
- OpenAI LLM
- Client domain routing
- Notification providers
- MQTT broker configuration
"""

import environ

env = environ.Env()

# ============================================================================
# LLM PROVIDER CONFIGURATION (Agent Intelligence)
# ============================================================================

# Anthropic Claude - Fallback LLM provider
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")

# OpenAI - Secondary fallback
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")

# LLM Provider Configuration
LLM_PROVIDERS_ENABLED = {
    'gemini': env.bool('LLM_GEMINI_ENABLED', default=True),      # Primary
    'anthropic': env.bool('LLM_ANTHROPIC_ENABLED', default=True),   # Fallback 1
    'openai': env.bool('LLM_OPENAI_ENABLED', default=False),     # Fallback 2 (disabled by default)
}

# Fallback chain priority: Gemini → Claude → OpenAI
LLM_DEFAULT_FALLBACK_CHAIN = ['gemini', 'anthropic', 'openai']

# ============================================================================
# TWILIO IVR CONFIGURATION
# ============================================================================
# Required for Twilio webhook signature validation (Rule #3 compliance)
# Webhook signature validation prevents unauthorized webhook calls (CVSS 7.5)
# See: apps/noc/security_intelligence/ivr/decorators.py

TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", default="")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", default="")
TWILIO_FROM_NUMBER = env("TWILIO_FROM_NUMBER", default="")

# Validate Twilio configuration at startup (fail fast if configured incorrectly)
if TWILIO_ACCOUNT_SID and not TWILIO_AUTH_TOKEN:
    raise ValueError(
        "TWILIO_ACCOUNT_SID is configured but TWILIO_AUTH_TOKEN is missing. "
        "Both are required for webhook signature validation. "
        "Please set TWILIO_AUTH_TOKEN environment variable."
    )

# ============================================================================
# TRANSLATION PROVIDER CONFIGURATION
# ============================================================================

AZURE_TRANSLATOR_API_KEY = env("AZURE_TRANSLATOR_API_KEY", default="")
AZURE_TRANSLATOR_REGION = env("AZURE_TRANSLATOR_REGION", default="")
AZURE_TRANSLATOR_ENDPOINT = env(
    "AZURE_TRANSLATOR_ENDPOINT",
    default="https://api.cognitive.microsofttranslator.com"
)
TRANSLATION_TEST_MODE = env.bool('TRANSLATION_TEST_MODE', default=False)

# ============================================================================
# MQTT CONFIGURATION
# ============================================================================

MQTT_CONFIG = {
    "BROKER_ADDRESS": env("MQTT_BROKER_ADDRESS", default="localhost"),
    "broker_port": env.int("MQTT_BROKER_PORT", default=1883),
    "broker_userNAME": env("MQTT_BROKER_USERNAME", default=""),
    "broker_password": env("MQTT_BROKER_PASSWORD", default=""),
}

# ============================================================================
# CLIENT DOMAINS CONFIGURATION
# ============================================================================

import json

_DEFAULT_CLIENT_DOMAINS = {
    "R_REDMINE": "redmine.youtility.in",
    "R_TOURTRAX": "redmine.youtility.in",
    "R_SUKHI": "redmine.youtility.in",
    "R_CAPGEMINI": "redmine.youtility.in",
    "D_SUKHI": "demo.youtility.in",
    "D_CAPGEMINI": "demo.youtility.in",
    "SUKHI": "sg.youtility.in",
    "D_TOURTRAX": "demo.youtility.in",
    "WTC": "intelliwiz2.youtility.in",
    "R_YTPLD": "redmine.youtility.in",
}

CLIENT_DOMAINS = _DEFAULT_CLIENT_DOMAINS.copy()

# Load CLIENT_DOMAINS from environment
client_domains_json = env('CLIENT_DOMAINS_JSON', default='{}')
try:
    client_domains_override = json.loads(client_domains_json)
    if isinstance(client_domains_override, dict):
        CLIENT_DOMAINS.update(client_domains_override)
except (json.JSONDecodeError, TypeError):
    pass

# Individual domain overrides
for client_key in list(_DEFAULT_CLIENT_DOMAINS.keys()):
    env_key = f'CLIENT_DOMAIN_{client_key}'
    domain_override = env(env_key, default=None)
    if domain_override:
        CLIENT_DOMAINS[client_key] = domain_override

# ============================================================================
# NOTIFICATION SERVICE CONFIGURATION
# ============================================================================

ENABLE_WEBHOOK_NOTIFICATIONS = env.bool('ENABLE_WEBHOOK_NOTIFICATIONS', default=False)

NOTIFICATION_PROVIDERS = {
    'slack': {
        'type': 'slack',
        'webhook_url': env('SLACK_WEBHOOK_URL', default=''),
        'channel': env('SLACK_CHANNEL', default='#onboarding-alerts'),
        'username': env('SLACK_USERNAME', default='IntelliWiz AI'),
        'timeout_seconds': env.int('SLACK_TIMEOUT', default=10)
    },
    'discord': {
        'type': 'discord',
        'webhook_url': env('DISCORD_WEBHOOK_URL', default=''),
        'username': env('DISCORD_USERNAME', default='IntelliWiz AI'),
        'timeout_seconds': env.int('DISCORD_TIMEOUT', default=10)
    },
    'email': {
        'type': 'email',
        'recipients': env.list('NOTIFICATION_EMAIL_RECIPIENTS', default=[]),
        'from_email': env('NOTIFICATION_FROM_EMAIL', default=''),
        'template_dir': 'onboarding/notifications/'
    },
    'webhook_alerts': {
        'type': 'webhook',
        'webhook_url': env('CUSTOM_WEBHOOK_URL', default=''),
        'secret': env('CUSTOM_WEBHOOK_SECRET', default=''),
        'auth_header': env('CUSTOM_WEBHOOK_AUTH', default=''),
        'timeout_seconds': env.int('CUSTOM_WEBHOOK_TIMEOUT', default=10),
        'headers': {'User-Agent': 'IntelliWiz-Notifications/1.0'}
    }
}

NOTIFICATION_ROUTING = {
    'approval_pending': env.list('NOTIFICATION_APPROVAL_PENDING_PROVIDERS', default=['slack', 'email']),
    'approval_granted': env.list('NOTIFICATION_APPROVAL_GRANTED_PROVIDERS', default=['slack']),
    'approval_rejected': env.list('NOTIFICATION_APPROVAL_REJECTED_PROVIDERS', default=['slack', 'email']),
    'escalation_created': env.list('NOTIFICATION_ESCALATION_PROVIDERS', default=['slack', 'discord', 'email']),
    'changeset_applied': env.list('NOTIFICATION_CHANGESET_APPLIED_PROVIDERS', default=['slack']),
    'changeset_rollback': env.list('NOTIFICATION_CHANGESET_ROLLBACK_PROVIDERS', default=['slack', 'email']),
    'system_error': env.list('NOTIFICATION_SYSTEM_ERROR_PROVIDERS', default=['email', 'webhook_alerts'])
}

__all__ = [
    'ANTHROPIC_API_KEY',
    'OPENAI_API_KEY',
    'LLM_PROVIDERS_ENABLED',
    'LLM_DEFAULT_FALLBACK_CHAIN',
    'TWILIO_ACCOUNT_SID',
    'TWILIO_AUTH_TOKEN',
    'TWILIO_FROM_NUMBER',
    'AZURE_TRANSLATOR_API_KEY',
    'AZURE_TRANSLATOR_REGION',
    'AZURE_TRANSLATOR_ENDPOINT',
    'TRANSLATION_TEST_MODE',
    'MQTT_CONFIG',
    'CLIENT_DOMAINS',
    'ENABLE_WEBHOOK_NOTIFICATIONS',
    'NOTIFICATION_PROVIDERS',
    'NOTIFICATION_ROUTING',
]
