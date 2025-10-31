from django.conf import settings


def app_settings(request):
    return {
        "HOST": getattr(settings, 'HOST', 'http://localhost:8000'),
        "DEBUG": settings.DEBUG,
    }
