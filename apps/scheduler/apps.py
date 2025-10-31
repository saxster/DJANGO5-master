from django.apps import AppConfig


class SchedulerConfig(AppConfig):
    name = "apps.scheduler"

    def ready(self):
        pass
