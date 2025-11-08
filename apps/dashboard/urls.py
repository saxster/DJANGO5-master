"""Dashboard URL configuration."""

from django.urls import path
from apps.dashboard import views

app_name = 'dashboard'

urlpatterns = [
    # Command Center Dashboard
    path('command-center/', views.command_center_view, name='command_center'),
    
    # API Endpoints
    path('api/command-center/', views.command_center_api, name='command_center_api'),
    path('api/invalidate-cache/', views.invalidate_cache_api, name='invalidate_cache'),
]
