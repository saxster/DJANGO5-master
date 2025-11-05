"""
URL Routing and Analytics Utilities

Legacy URL redirects and analytics tracking.
"""

import logging
import re
from typing import Dict, Optional
from django.http import HttpRequest
from django.utils import timezone

logger = logging.getLogger(__name__)


class URLAnalytics:
    """URL analytics and tracking utilities"""

    @staticmethod
    def track_page_view(request: HttpRequest, additional_data: Dict = None):
        """Track page view for analytics"""
        from .optimization import UrlOptimizer

        analytics_data = {
            'url': request.path,
            'canonical_url': UrlOptimizer.generate_canonical_url(request),
            'referrer': request.META.get('HTTP_REFERER'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'timestamp': timezone.now().isoformat(),
            'user_id': request.user.id if request.user.is_authenticated else None,
            'session_key': request.session.session_key if hasattr(request, 'session') else None,
        }

        if additional_data:
            analytics_data.update(additional_data)

        return analytics_data

    @staticmethod
    def track_url_error(request: HttpRequest, error_code: int, error_type: str = None):
        """Track URL errors for 404 analysis and dead link detection"""
        error_data = {
            'url': request.path,
            'error_code': error_code,
            'error_type': error_type,
            'referrer': request.META.get('HTTP_REFERER'),
            'timestamp': timezone.now().isoformat(),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
        }

        logger.warning(f"URL Error {error_code}: {request.path}", extra=error_data)

        return error_data


class LegacyURLRedirector:
    """Smart redirects for legacy URLs to maintain SEO and user bookmarks"""

    LEGACY_REDIRECTS = {
        r'^admin/peoples/people/$': '/people/directory/',
        r'^admin/activity/task/$': '/operations/tasks/',
        r'^admin/y_helpdesk/ticket/$': '/help-desk/tickets/',
        r'^peoples/$': '/people/directory/',
        r'^peoples/people/$': '/people/directory/',
        r'^activity/$': '/operations/tasks/',
        r'^activity/task/$': '/operations/tasks/',
        r'^scheduler/$': '/operations/tasks/',
        r'^y_helpdesk/$': '/help-desk/tickets/',
        r'^work_order_management/$': '/operations/work-orders/',
        r'^schedhule/': '/operations/tasks/',
        r'^helpdesk/': '/help-desk/',
        r'^workorder/': '/operations/work-orders/',
    }

    @classmethod
    def get_redirect_url(cls, path: str) -> Optional[str]:
        """Get redirect URL for legacy path"""
        for pattern, redirect_url in cls.LEGACY_REDIRECTS.items():
            if re.match(pattern, path):
                return redirect_url

        return None

    @classmethod
    def track_legacy_usage(cls, old_url: str, new_url: str, request: HttpRequest):
        """Track legacy URL usage for migration analysis"""
        logger.info(f"Legacy URL redirect: {old_url} -> {new_url}", extra={
            'old_url': old_url,
            'new_url': new_url,
            'referrer': request.META.get('HTTP_REFERER'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'user_id': request.user.id if request.user.is_authenticated else None,
        })




__all__ = [
    'URLAnalytics',
    'LegacyURLRedirector',
    'BreadcrumbGenerator',
    'SEOOptimizer',
    'URLValidator',
]
