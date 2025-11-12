"""Application configuration for the calendar view module."""

from django.apps import AppConfig


class CalendarViewConfig(AppConfig):
    """App config used by Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.calendar_view"
    verbose_name = "Calendar View"
