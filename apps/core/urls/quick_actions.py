"""
Quick Actions URL Configuration

Author: Claude Code
Date: 2025-11-07
"""

from django.urls import path
from apps.core.api import quick_action_views

app_name = 'quick_actions'

urlpatterns = [
    # Execute action
    path('execute/', quick_action_views.execute_quick_action, name='execute'),
    
    # List available actions
    path('available/', quick_action_views.list_available_actions, name='available'),
    
    # Checklist management
    path(
        'checklist/<int:checklist_id>/',
        quick_action_views.get_checklist,
        name='get_checklist'
    ),
    path(
        'checklist/<int:checklist_id>/step/<int:step_index>/',
        quick_action_views.update_checklist_step,
        name='update_step'
    ),
    path(
        'checklist/<int:checklist_id>/upload-photo/',
        quick_action_views.upload_step_photo,
        name='upload_photo'
    ),
]
