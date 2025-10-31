"""
Templates Configuration

Centralized template engine configuration.
Extracted from base.py for Rule #6 compliance.

Features:
- Django templates (default)
- Jinja2 templates (performance)
- Shared context processors
- Template debugging

Author: Claude Code
Date: 2025-10-01
"""

import os
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Template directories
JINJA_TEMPLATES = os.path.join(BASE_DIR, "frontend/templates")

# Shared context processors
CONTEXT_PROCESSORS = [
    "apps.peoples.context_processors.app_settings",
    "django.template.context_processors.debug",
    "django.template.context_processors.request",
    "django.contrib.auth.context_processors.auth",
    "django.contrib.messages.context_processors.messages",
    "django.template.context_processors.media",
    "apps.helpbot.context_processors.helpbot_context",
]

# Templates configuration
# https://docs.djangoproject.com/en/5.0/ref/templates/api/
TEMPLATES = [
    # ========================================================================
    # Django Template Engine (Default)
    # ========================================================================
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": CONTEXT_PROCESSORS,
        },
    },

    # ========================================================================
    # Jinja2 Template Engine (Performance)
    # ========================================================================
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [JINJA_TEMPLATES],
        "APP_DIRS": True,
        "OPTIONS": {
            "extensions": [
                "jinja2.ext.loopcontrols",  # {% break %} and {% continue %}
            ],
            "autoescape": True,
            "auto_reload": True,  # Set to False in production
            "undefined": "jinja2.StrictUndefined",  # Raise errors for undefined variables
            "environment": "intelliwiz_config.jinja.env.JinjaEnvironment",
            "context_processors": CONTEXT_PROCESSORS,
        },
    },
]

__all__ = [
    'TEMPLATES',
    'JINJA_TEMPLATES',
    'CONTEXT_PROCESSORS',
]
