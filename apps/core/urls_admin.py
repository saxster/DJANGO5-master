"""
Simplified admin URL configuration.

Historically this module exposed several placeholder views that lived under
the ``/admin/`` namespace. Those views have been removed; the admin now routes
directly to Django's ``admin.site.urls`` while keeping the legacy
``/admin/django/`` entry point for users that bookmarked it.
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path("", admin.site.urls),
    path("django/", RedirectView.as_view(pattern_name="admin:index", permanent=False)),
]
