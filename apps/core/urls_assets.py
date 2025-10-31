"""
Consolidated URL configuration for Assets domain
Combines asset-related functionality from activity app

Migration to concrete implementations: 2025-10-31
"""
from django.urls import path
# Import concrete asset views from refactored package
from apps.activity.views.asset import (
    AssetView,
    AssetComparisionView,
    ParameterComparisionView,
    PeopleNearAsset,
    AssetLogView,
    AssetMaintenanceList,
)
# Backward compatibility: preserve typo for existing code that may reference it
AssetMaintainceList = AssetMaintenanceList
from apps.activity.views.location_views import LocationView
from apps.activity.views.question_views import (
    Question,
    QuestionSet,
    QsetNQsetBelonging,
    Checkpoint,
    deleteQSB,
)
from apps.activity.views.attachment_views import Attachments, PreviewImage

app_name = 'assets'

urlpatterns = [
    # ========== ASSET INVENTORY ==========
    path('', AssetView.as_view(), name='asset_list'),
    path('create/', AssetView.as_view(), name='asset_create'),
    path('<int:pk>/', AssetView.as_view(), name='asset_detail'),
    path('<int:pk>/edit/', AssetView.as_view(), name='asset_edit'),
    
    # ========== MAINTENANCE ==========
    path('maintenance/', AssetMaintainceList.as_view(), name='maintenance_list'),
    path('maintenance/create/', AssetMaintainceList.as_view(), name='maintenance_create'),
    path('maintenance/<int:pk>/', AssetMaintainceList.as_view(), name='maintenance_detail'),
    
    # ========== COMPARISON & ANALYSIS ==========
    path('compare/', AssetComparisionView.as_view(), name='compare'),
    path('compare/parameters/', ParameterComparisionView.as_view(), name='compare_parameters'),
    
    # ========== MONITORING & LOGS ==========
    path('logs/', AssetLogView.as_view(), name='logs'),
    path('logs/<int:asset_id>/', AssetLogView.as_view(), name='asset_logs'),
    path('people-nearby/', PeopleNearAsset.as_view(), name='people_nearby'),
    path('people-nearby/<int:asset_id>/', PeopleNearAsset.as_view(), name='asset_people_nearby'),
    
    # ========== LOCATIONS ==========
    path('locations/', LocationView.as_view(), name='locations_list'),
    path('locations/create/', LocationView.as_view(), name='location_create'),
    path('locations/<int:pk>/', LocationView.as_view(), name='location_detail'),
    path('locations/<int:pk>/edit/', LocationView.as_view(), name='location_edit'),
    
    # ========== CHECKPOINTS ==========
    path('checkpoints/', Checkpoint.as_view(), name='checkpoints_list'),
    path('checkpoints/create/', Checkpoint.as_view(), name='checkpoint_create'),
    path('checkpoints/<int:pk>/', Checkpoint.as_view(), name='checkpoint_detail'),
    path('checkpoints/<int:pk>/edit/', Checkpoint.as_view(), name='checkpoint_edit'),
    
    # ========== CHECKLISTS & QUESTIONS ==========
    path('checklists/', QuestionSet.as_view(), name='checklists_list'),
    path('checklists/create/', QuestionSet.as_view(), name='checklist_create'),
    path('checklists/<int:pk>/', QuestionSet.as_view(), name='checklist_detail'),
    path('checklists/<int:pk>/edit/', QuestionSet.as_view(), name='checklist_edit'),
    
    # Questions
    path('checklists/questions/', Question.as_view(), name='questions_list'),
    path('checklists/questions/create/', Question.as_view(), name='question_create'),
    path('checklists/questions/<int:pk>/', Question.as_view(), name='question_detail'),
    
    # Relationships
    path('checklists/relationships/', QsetNQsetBelonging.as_view(), name='checklist_relationships'),
    path('checklists/relationships/delete/', deleteQSB, name='delete_relationship'),
    
    # ========== ATTACHMENTS ==========
    path('attachments/', Attachments.as_view(), name='attachments'),
    path('attachments/preview/', PreviewImage.as_view(), name='attachment_preview'),
]