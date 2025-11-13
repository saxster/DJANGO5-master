"""
AWS Integration Configuration

Amazon Web Services configurations:
- SES Email Service
- S3 Bucket Storage
- Related AWS settings
"""

import os
import environ

env = environ.Env()

# ============================================================================
# EMAIL CONFIGURATION (AWS SES)
# ============================================================================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "email-smtp.us-east-1.amazonaws.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("AWS_SES_SMTP_USER", default="")
EMAIL_HOST_PASSWORD = env("AWS_SES_SMTP_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="dev@localhost")
EMAIL_FROM_ADDRESS = DEFAULT_FROM_EMAIL

# Email timeout configuration (prevents worker starvation on slow SMTP servers)
# Django's EmailMessage.send() respects this timeout setting
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=30)  # 30 seconds

# Email Verification Configuration
EMAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_TOKEN_LIFE = 60**2
EMAIL_MAIL_SUBJECT = "Confirm your email"
EMAIL_MAIL_HTML = "email.html"
EMAIL_MAIL_PLAIN = "mail_body.txt"
EMAIL_MAIL_PAGE_TEMPLATE = "email_verify.html"
EMAIL_PAGE_DOMAIN = env("EMAIL_PAGE_DOMAIN", default="localhost:8000")
EMAIL_MULTI_USER = True
CUSTOM_SALT = env("CUSTOM_SALT", default="django-email-verification-salt")

# Email verification callbacks
EMAIL_VERIFIED_CALLBACK = 'apps.peoples.utils.verified_callback'
EMAIL_MAIL_CALLBACK = 'apps.peoples.utils.verified_callback'

# ============================================================================
# S3 BUCKET CONFIGURATION
# ============================================================================

BUCKET = env("BUCKET", default="prod-attachment-sukhi-group")
TEMP_REPORTS_GENERATED = env("TEMP_REPORTS_GENERATED", default="/tmp/temp_reports")
ONDEMAND_REPORTS_GENERATED = env("ONDEMAND_REPORTS_GENERATED", default="/tmp/ondemand_reports")
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=10485760)

__all__ = [
    'EMAIL_BACKEND',
    'EMAIL_HOST',
    'EMAIL_PORT',
    'EMAIL_USE_TLS',
    'EMAIL_HOST_USER',
    'EMAIL_HOST_PASSWORD',
    'EMAIL_TIMEOUT',
    'DEFAULT_FROM_EMAIL',
    'EMAIL_FROM_ADDRESS',
    'EMAIL_TOKEN_LIFE',
    'EMAIL_MAIL_TOKEN_LIFE',
    'EMAIL_MAIL_SUBJECT',
    'EMAIL_MAIL_HTML',
    'EMAIL_MAIL_PLAIN',
    'EMAIL_MAIL_PAGE_TEMPLATE',
    'EMAIL_PAGE_DOMAIN',
    'EMAIL_MULTI_USER',
    'CUSTOM_SALT',
    'EMAIL_VERIFIED_CALLBACK',
    'EMAIL_MAIL_CALLBACK',
    'BUCKET',
    'TEMP_REPORTS_GENERATED',
    'ONDEMAND_REPORTS_GENERATED',
    'DATA_UPLOAD_MAX_MEMORY_SIZE',
]
