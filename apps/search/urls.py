"""
Search API URLs

Endpoints:
- POST /api/v1/search - Global search
- GET/POST /api/v1/search/saved - Saved searches
"""

from django.urls import path
from apps.search import views

app_name = 'search'

urlpatterns = [
    path('', views.GlobalSearchView.as_view(), name='global-search'),
    path('saved/', views.SavedSearchListCreateView.as_view(), name='saved-search-list'),
]