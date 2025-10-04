"""
Feature Flag Decorators

Decorators for view and function-level feature flag checks.
Follows .claude/rules.md Rule #8 (< 50 lines for utility functions).
"""

import logging
from functools import wraps
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from .service import FeatureFlagService

logger = logging.getLogger(__name__)


def feature_required(
    flag_name: str,
    redirect_url: Optional[str] = None,
    template: str = 'errors/403.html'
) -> Callable:
    """
    Decorator to require feature flag for view access.

    Args:
        flag_name: Name of the required feature flag
        redirect_url: URL to redirect if flag disabled (optional)
        template: Template to render if flag disabled

    Usage:
        @feature_required('new_dashboard')
        def new_dashboard_view(request):
            return render(request, 'dashboard_v2.html')
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            user = getattr(request, 'user', None)

            if FeatureFlagService.is_enabled(flag_name, user=user, request=request):
                return view_func(request, *args, **kwargs)

            logger.warning(
                f"Feature flag '{flag_name}' blocked access for user {user}",
                extra={
                    'flag_name': flag_name,
                    'user_id': user.id if user and hasattr(user, 'id') else None,
                    'path': request.path
                }
            )

            if redirect_url:
                from django.shortcuts import redirect
                return redirect(redirect_url)

            return render(
                request,
                template,
                {
                    'error_message': 'This feature is not available',
                    'correlation_id': getattr(request, 'correlation_id', 'N/A')
                },
                status=403
            )

        return wrapper
    return decorator


def feature_enabled_for_user(flag_name: str, user) -> bool:
    """
    Helper function to check if feature enabled for user.

    Args:
        flag_name: Name of the feature flag
        user: User instance

    Returns:
        True if feature enabled for user

    Usage:
        if feature_enabled_for_user('beta_features', request.user):
            # Show beta UI
    """
    return FeatureFlagService.is_enabled(flag_name, user=user)
