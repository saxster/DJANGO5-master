"""
Search API URLs

Endpoints:
- GET /api/v1/search/unified/ - Unified semantic search (Feature #3)
- GET /api/v1/search/suggestions/ - Search suggestions
- POST /api/v1/search/analytics/click/ - Track search result clicks
- POST /api/v1/search - Global search (legacy)
- GET/POST /api/v1/search/saved - Saved searches (legacy)
"""

from django.urls import path
from apps.search import views
from apps.search.api import search_views

app_name = 'search'

urlpatterns = [
    # Unified semantic search (Feature #3 - NL/AI Platform)
    path('unified/', search_views.unified_search_view, name='unified-search'),
    path('suggestions/', search_views.search_suggestions_view, name='search-suggestions'),
    path('analytics/click/', search_views.search_analytics_click_view, name='search-analytics-click'),

    # Legacy endpoints (if they exist)
    path('', views.GlobalSearchView.as_view(), name='global-search'),
    path('saved/', views.SavedSearchListCreateView.as_view(), name='saved-search-list'),
]