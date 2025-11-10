"""URL routes for calendar aggregation endpoints."""

from django.urls import path

from .views import calendar_views

app_name = "calendar"

urlpatterns = [
    path("events/", calendar_views.CalendarEventListView.as_view(), name="events"),
    path("events/<str:event_id>/attachments/", calendar_views.CalendarEventAttachmentsView.as_view(), name="event_attachments"),
]
