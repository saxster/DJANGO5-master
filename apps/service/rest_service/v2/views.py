"""
REST API v2 Views
Placeholder views for v2 API.

Compliance with .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings


class V2StatusView(APIView):
    """
    Status endpoint for v2 API.
    Returns v2 availability and feature information.
    """

    permission_classes = []

    def get(self, request):
        """Return v2 API status."""
        return Response({
            'version': 'v2',
            'status': 'planned',
            'available_date': '2026-06-30',
            'message': 'v2 API is planned for release on 2026-06-30',
            'current_stable': 'v1',
            'features': [
                'Enhanced security',
                'Improved performance',
                'Better error messages',
                'Advanced filtering',
            ],
            'breaking_changes': [
                'Legacy file upload removed',
                'Enhanced authentication requirements',
                'Stricter input validation',
            ],
            'migration_guide': f"{request.scheme}://{request.get_host()}/docs/api-migrations/v1-to-v2/"
        })


__all__ = ['V2StatusView']