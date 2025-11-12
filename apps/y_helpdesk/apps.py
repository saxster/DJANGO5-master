from django.apps import AppConfig


class YHelpdeskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.y_helpdesk"

    def ready(self) -> None:
        from . import signals

        # Import services to trigger ontology registration
        try:
            from apps.y_helpdesk.services import (  # noqa: F401
                ai_summarizer,
                kb_suggester,
                duplicate_detector,
                sla_calculator,
            )
        except (ImportError, RuntimeError):
            # Services may not be importable in all contexts
            pass
