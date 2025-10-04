"""
API Version Negotiation Middleware

Routes requests to correct API version based on URL path.

Follows .claude/rules.md:
- Rule #7: Middleware methods < 50 lines
"""

import logging
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('api.versioning')


class APIVersionMiddleware(MiddlewareMixin):
    """Route requests to correct API version."""

    SUPPORTED_VERSIONS = ['v1', 'v2']

    DEPRECATION_INFO = {
        'v1': {
            'released': '2025-01-01',
            'deprecated': '2026-01-01',
            'sunset': '2026-06-01',
            'status': 'active',
        },
        'v2': {
            'released': '2025-10-01',
            'deprecated': None,
            'sunset': None,
            'status': 'current',
        }
    }

    def process_request(self, request):
        """Detect and validate API version."""
        if not request.path.startswith('/api/'):
            return None

        version = self._extract_version(request.path)

        if version and version not in self.SUPPORTED_VERSIONS:
            return JsonResponse({
                'error': 'Unsupported API version',
                'requested_version': version,
                'supported_versions': self.SUPPORTED_VERSIONS,
                'current_version': 'v2',
                'migration_guide': '/docs/api-v2-migration'
            }, status=400)

        request.api_version = version or 'v1'

        return None

    def process_response(self, request, response):
        """Add version headers to response."""
        if hasattr(request, 'api_version'):
            response['API-Version'] = request.api_version

            version_info = self.DEPRECATION_INFO.get(request.api_version, {})

            if version_info.get('deprecated'):
                response['Deprecation'] = 'true'
                response['Sunset'] = version_info['sunset']
                response['Link'] = '</docs/api-v2-migration>; rel="migration"'

            response['API-Status'] = version_info.get('status', 'unknown')

        return response

    def _extract_version(self, path: str) -> str:
        """Extract version from URL path."""
        parts = path.split('/')

        for part in parts:
            if part.startswith('v') and part[1:].isdigit():
                return part

        return ''