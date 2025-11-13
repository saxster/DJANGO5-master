from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    name = "apps.attendance"
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """
        Import signal handlers when app is ready.

        Ensures automatic workflows are registered:
        - Post order version increments
        - Acknowledgement invalidation
        - Assignment notifications
        - Attendance record updates
        - Cache invalidation (Nov 2025)
        """
        import apps.attendance.signals  # noqa: F401
        import apps.core.services.cache_invalidation_service  # noqa: F401
