"""
Dashboard Hub Views

Unified dashboard hub that displays all available dashboards to users
based on their permissions. Uses the central dashboard registry to
provide a single access point for all monitoring and analytics dashboards.

Features:
- Role-aware dashboard tiles
- Category-based organization
- Search functionality
- Favorites support
- Recent dashboards tracking

Architecture:
- Uses central dashboard registry (single source of truth)
- Permission-based filtering
- Responsive grid layout
- Progressive enhancement

Author: Dashboard Infrastructure Team
Date: 2025-10-04
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from apps.core.registry import dashboard_registry

logger = logging.getLogger(__name__)


class DashboardHubView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard hub view.

    Displays all dashboards accessible to the current user,
    organized by category with search and filtering capabilities.
    """
    template_name = 'core/dashboard_hub.html'

    def get_context_data(self, **kwargs):
        """Get dashboard hub context."""
        context = super().get_context_data(**kwargs)

        try:
            # Get all dashboards accessible to user
            user_dashboards = dashboard_registry.get_dashboards_for_user(self.request.user)

            # Organize dashboards by category
            dashboards_by_category = {}
            for dashboard in user_dashboards:
                if dashboard.category not in dashboards_by_category:
                    dashboards_by_category[dashboard.category] = []
                dashboards_by_category[dashboard.category].append(dashboard.to_dict())

            # Get user's recent dashboards from session
            recent_dashboard_ids = self.request.session.get('recent_dashboards', [])
            recent_dashboards = [
                dashboard.to_dict()
                for dashboard in user_dashboards
                if dashboard.id in recent_dashboard_ids
            ][:5]  # Last 5 dashboards

            # Get user's favorite dashboards (if implemented)
            # For now, just placeholder
            favorite_dashboards = []

            context.update({
                'total_dashboards': len(user_dashboards),
                'dashboards_by_category': dashboards_by_category,
                'categories': sorted(dashboards_by_category.keys()),
                'recent_dashboards': recent_dashboards,
                'favorite_dashboards': favorite_dashboards,
                'is_staff': self.request.user.is_staff,
                'is_superuser': self.request.user.is_superuser,
                'page_title': 'Dashboard Hub',
                'page_subtitle': f'Access to {len(user_dashboards)} dashboards'
            })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Error loading dashboard hub: {e}", exc_info=True)
            context.update({
                'error': 'Unable to load dashboard hub',
                'dashboards_by_category': {},
                'categories': []
            })

        return context


class DashboardSearchAPIView(LoginRequiredMixin, View):
    """
    API endpoint for dashboard search.

    Provides JSON search results for dashboard filtering and discovery.
    """

    def get(self, request, *args, **kwargs):
        """
        Search dashboards by query string.

        Query parameters:
            q: Search query
            category: Filter by category (optional)
            tag: Filter by tag (optional)

        Returns:
            JSON response with matching dashboards
        """
        try:
            query = request.GET.get('q', '').strip()
            category_filter = request.GET.get('category', '').strip()
            tag_filter = request.GET.get('tag', '').strip()

            # Start with all accessible dashboards
            dashboards = dashboard_registry.get_dashboards_for_user(request.user)

            # Apply search query if provided
            if query:
                all_dashboards = dashboard_registry.search(query)
                # Filter to only accessible dashboards
                dashboards = [
                    d for d in all_dashboards
                    if d in dashboards
                ]

            # Apply category filter if provided
            if category_filter:
                dashboards = [
                    d for d in dashboards
                    if d.category == category_filter
                ]

            # Apply tag filter if provided
            if tag_filter:
                dashboards = [
                    d for d in dashboards
                    if tag_filter in d.tags
                ]

            # Convert to dict and return
            results = [dashboard.to_dict() for dashboard in dashboards]

            return JsonResponse({
                'status': 'success',
                'query': query,
                'count': len(results),
                'results': results
            })

        except (ValueError, KeyError) as e:
            logger.error(f"Error in dashboard search: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid search parameters'
            }, status=400)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Database error in dashboard search: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Internal server error'
            }, status=500)


class DashboardCategoriesAPIView(LoginRequiredMixin, View):
    """
    API endpoint for dashboard categories.

    Returns list of all categories with dashboard counts.
    """

    def get(self, request, *args, **kwargs):
        """
        Get all dashboard categories accessible to user.

        Returns:
            JSON response with categories and counts
        """
        try:
            # Get all dashboards accessible to user
            user_dashboards = dashboard_registry.get_dashboards_for_user(request.user)

            # Count dashboards per category
            category_counts = {}
            for dashboard in user_dashboards:
                if dashboard.category not in category_counts:
                    category_counts[dashboard.category] = 0
                category_counts[dashboard.category] += 1

            # Format response
            categories = [
                {
                    'name': category,
                    'count': count,
                    'display_name': category.replace('_', ' ').title()
                }
                for category, count in sorted(category_counts.items())
            ]

            return JsonResponse({
                'status': 'success',
                'total_categories': len(categories),
                'categories': categories
            })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Error getting dashboard categories: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Internal server error'
            }, status=500)


class DashboardMetricsAPIView(LoginRequiredMixin, View):
    """
    API endpoint for dashboard registry metrics.

    Provides usage analytics and statistics about dashboard access.
    """

    def get(self, request, *args, **kwargs):
        """
        Get dashboard registry metrics.

        Returns:
            JSON response with metrics
        """
        try:
            # Get user-accessible dashboards
            user_dashboards = dashboard_registry.get_dashboards_for_user(request.user)

            # Calculate metrics
            total_dashboards = dashboard_registry.get_dashboard_count()
            accessible_dashboards = len(user_dashboards)
            total_categories = dashboard_registry.get_category_count()

            # Get recent activity from session
            recent_dashboard_ids = request.session.get('recent_dashboards', [])

            # Category breakdown
            category_breakdown = {}
            for dashboard in user_dashboards:
                if dashboard.category not in category_breakdown:
                    category_breakdown[dashboard.category] = 0
                category_breakdown[dashboard.category] += 1

            # Real-time dashboards
            realtime_count = sum(1 for d in user_dashboards if d.real_time)

            return JsonResponse({
                'status': 'success',
                'metrics': {
                    'total_dashboards': total_dashboards,
                    'accessible_dashboards': accessible_dashboards,
                    'total_categories': total_categories,
                    'recent_activity_count': len(recent_dashboard_ids),
                    'realtime_dashboards': realtime_count,
                    'category_breakdown': category_breakdown
                },
                'user_context': {
                    'is_staff': request.user.is_staff,
                    'is_superuser': request.user.is_superuser,
                    'username': request.user.get_username()
                },
                'timestamp': timezone.now().isoformat()
            })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Error getting dashboard metrics: {e}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': 'Internal server error'
            }, status=500)


@login_required
def track_dashboard_access(request, dashboard_id: str):
    """
    Track dashboard access for recent dashboards feature.

    Args:
        request: HTTP request
        dashboard_id: Dashboard ID to track

    Returns:
        JSON response with success status
    """
    try:
        # Get dashboard to verify it exists and user has access
        dashboard = dashboard_registry.get(dashboard_id)

        if not dashboard:
            return JsonResponse({
                'status': 'error',
                'message': 'Dashboard not found'
            }, status=404)

        if not dashboard.has_access(request.user):
            return JsonResponse({
                'status': 'error',
                'message': 'Access denied'
            }, status=403)

        # Update recent dashboards in session
        recent_dashboards = request.session.get('recent_dashboards', [])

        # Remove if already in list
        if dashboard_id in recent_dashboards:
            recent_dashboards.remove(dashboard_id)

        # Add to front of list
        recent_dashboards.insert(0, dashboard_id)

        # Keep only last 10
        recent_dashboards = recent_dashboards[:10]

        # Save back to session
        request.session['recent_dashboards'] = recent_dashboards
        request.session.modified = True

        logger.info(f"Tracked dashboard access: {dashboard_id} by user {request.user.id}")

        return JsonResponse({
            'status': 'success',
            'dashboard_id': dashboard_id,
            'recent_count': len(recent_dashboards)
        })

    except (ValueError, KeyError) as e:
        logger.error(f"Error tracking dashboard access: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request'
        }, status=400)

    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Database error tracking dashboard access: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)


# Export views
__all__ = [
    'DashboardHubView',
    'DashboardSearchAPIView',
    'DashboardCategoriesAPIView',
    'DashboardMetricsAPIView',
    'track_dashboard_access'
]
