"""URL routes for Calendar View app."""

from django.urls import path

from .admin import CalendarDashboardView

app_name = "calendar_view"

urlpatterns = [
    path("", CalendarDashboardView.as_view(), name="dashboard"),
]
