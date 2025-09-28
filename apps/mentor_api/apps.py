"""
Django app configuration for Mentor API.
"""

from django.apps import AppConfig


class MentorApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mentor_api'
    verbose_name = 'AI Mentor API'

    def ready(self):
        """Initialize the app when Django starts."""
        pass