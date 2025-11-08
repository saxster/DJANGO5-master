"""
API Deprecation Middleware

Adds deprecation headers to v1 API endpoints to inform clients
of the migration path to v2.

Ontology: middleware=True, api_versioning=True
Category: middleware, api, deprecation
Domain: api_versioning
Responsibility: Add deprecation headers to v1 responses
Dependencies: django
"""

from datetime import datetime, timedelta


class APIDeprecationMiddleware:
    """
    Middleware to add deprecation headers to v1 API responses.
    
    Headers added:
    - Deprecation: true
    - Sunset: Date when v1 will be EOL
    - Link: URL to migration documentation
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # v1 sunset date: 90 days from now (Jan 31, 2026)
        self.sunset_date = datetime(2026, 1, 31)
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Check if this is a v1 API endpoint
        if self.is_v1_endpoint(request.path):
            self.add_deprecation_headers(response)
        
        return response
    
    def is_v1_endpoint(self, path: str) -> bool:
        """Check if the path is a v1 API endpoint."""
        v1_patterns = [
            '/api/v1/',
            '/api/operations/',  # Legacy operations
            '/api/attendance/',  # Legacy attendance
        ]
        return any(pattern in path for pattern in v1_patterns)
    
    def add_deprecation_headers(self, response):
        """Add deprecation headers to the response."""
        response['Deprecation'] = 'true'
        response['Sunset'] = self.sunset_date.strftime('%a, %d %b %Y %H:%M:%S GMT')
        response['Link'] = '</docs/kotlin-frontend/API_VERSION_RESOLUTION_STRATEGY.md>; rel="deprecation"'
        response['X-API-Version'] = 'v1'
        response['X-Upgrade-Available'] = 'v2'
        
        return response
