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
        """
        import apps.attendance.signals  # noqa: F401
