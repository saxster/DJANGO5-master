"""
IVR URL Configuration.

Webhook endpoints for IVR provider callbacks.
"""

from django.urls import path
from .views import webhook_views

urlpatterns = [
    path('callback/twilio/status/', webhook_views.twilio_status_callback, name='twilio_status_callback'),
    path('callback/twilio/gather/', webhook_views.twilio_gather_callback, name='twilio_gather_callback'),
]