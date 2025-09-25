"""
Comprehensive Security Headers Middleware
Consolidates all security headers in one place for better management
"""

import logging
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("security")


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add comprehensive security headers to all responses.
    
    This middleware should be placed early in the middleware stack,
    but after SecurityMiddleware to ensure headers are applied to all responses.
    """
    
    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)
        
        # Load configuration from settings
        self.enable_hsts = getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0
        self.hsts_seconds = getattr(settings, 'SECURE_HSTS_SECONDS', 31536000)
        self.hsts_include_subdomains = getattr(settings, 'SECURE_HSTS_INCLUDE_SUBDOMAINS', True)
        self.hsts_preload = getattr(settings, 'SECURE_HSTS_PRELOAD', True)
        
    def process_response(self, request, response):
        """
        Add security headers to response.
        
        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object
            
        Returns:
            Modified response with security headers
        """
        # Skip for static files to avoid overhead
        if request.path.startswith(('/static/', '/media/')):
            return response
            
        # 1. Strict-Transport-Security (HSTS)
        if self.enable_hsts and not response.get('Strict-Transport-Security'):
            hsts_header = f"max-age={self.hsts_seconds}"
            if self.hsts_include_subdomains:
                hsts_header += "; includeSubDomains"
            if self.hsts_preload:
                hsts_header += "; preload"
            response['Strict-Transport-Security'] = hsts_header
            
        # 2. X-Content-Type-Options - Prevent MIME type sniffing
        if not response.get('X-Content-Type-Options'):
            response['X-Content-Type-Options'] = 'nosniff'
            
        # 3. X-Frame-Options - Prevent clickjacking
        if not response.get('X-Frame-Options'):
            frame_options = getattr(settings, 'X_FRAME_OPTIONS', 'DENY')
            response['X-Frame-Options'] = frame_options
            
        # 4. X-XSS-Protection - Legacy XSS protection for older browsers
        if not response.get('X-XSS-Protection'):
            response['X-XSS-Protection'] = '1; mode=block'
            
        # 5. Referrer-Policy - Control referrer information
        if not response.get('Referrer-Policy'):
            referrer_policy = getattr(
                settings, 
                'REFERRER_POLICY', 
                'strict-origin-when-cross-origin'
            )
            response['Referrer-Policy'] = referrer_policy
            
        # 6. Permissions-Policy (formerly Feature-Policy)
        if not response.get('Permissions-Policy'):
            permissions_policy = self._build_permissions_policy()
            response['Permissions-Policy'] = permissions_policy
            
        # 7. Cross-Origin Headers
        if not response.get('Cross-Origin-Embedder-Policy'):
            response['Cross-Origin-Embedder-Policy'] = 'require-corp'
            
        if not response.get('Cross-Origin-Opener-Policy'):
            response['Cross-Origin-Opener-Policy'] = 'same-origin'
            
        if not response.get('Cross-Origin-Resource-Policy'):
            response['Cross-Origin-Resource-Policy'] = 'same-origin'
            
        # 8. Cache-Control for sensitive pages
        if self._is_sensitive_page(request):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
        # 9. X-Permitted-Cross-Domain-Policies for Adobe products
        if not response.get('X-Permitted-Cross-Domain-Policies'):
            response['X-Permitted-Cross-Domain-Policies'] = 'none'
            
        # 10. X-Download-Options for IE
        if not response.get('X-Download-Options'):
            response['X-Download-Options'] = 'noopen'
            
        # 11. Report-To header for error reporting
        if not response.get('Report-To'):
            report_to = self._build_report_to_header()
            if report_to:
                response['Report-To'] = report_to
                
        # 12. NEL (Network Error Logging) header
        if not response.get('NEL'):
            nel = self._build_nel_header()
            if nel:
                response['NEL'] = nel
                
        return response
        
    def _build_permissions_policy(self):
        """
        Build Permissions-Policy header value.
        
        Returns:
            str: Permissions-Policy header value
        """
        # Get custom policy from settings or use secure defaults
        permissions = getattr(settings, 'PERMISSIONS_POLICY', {})
        
        default_permissions = {
            'accelerometer': '()',
            'ambient-light-sensor': '()',
            'autoplay': '(self)',
            'battery': '()',
            'camera': '()',
            'cross-origin-isolated': '()',
            'display-capture': '()',
            'document-domain': '()',
            'encrypted-media': '(self)',
            'execution-while-not-rendered': '()',
            'execution-while-out-of-viewport': '()',
            'fullscreen': '(self)',
            'geolocation': '()',
            'gyroscope': '()',
            'keyboard-map': '()',
            'magnetometer': '()',
            'microphone': '()',
            'midi': '()',
            'navigation-override': '()',
            'payment': '()',
            'picture-in-picture': '()',
            'publickey-credentials-get': '()',
            'screen-wake-lock': '()',
            'sync-xhr': '()',
            'usb': '()',
            'web-share': '()',
            'xr-spatial-tracking': '()',
        }
        
        # Merge custom with defaults
        final_permissions = {**default_permissions, **permissions}
        
        # Build the header string
        policy_parts = []
        for feature, allowlist in final_permissions.items():
            policy_parts.append(f"{feature}={allowlist}")
            
        return ', '.join(policy_parts)
        
    def _build_report_to_header(self):
        """
        Build Report-To header for error reporting.
        
        Returns:
            str: Report-To header value or None
        """
        report_uri = getattr(settings, 'SECURITY_REPORT_URI', None)
        if not report_uri:
            return None
            
        report_to = {
            "group": "security-endpoints",
            "max_age": 10886400,  # 126 days
            "endpoints": [
                {"url": report_uri}
            ],
            "include_subdomains": True
        }
        
        import json
        return json.dumps(report_to)
        
    def _build_nel_header(self):
        """
        Build Network Error Logging header.
        
        Returns:
            str: NEL header value or None
        """
        nel_uri = getattr(settings, 'NEL_REPORT_URI', None)
        if not nel_uri:
            return None
            
        nel_config = {
            "report_to": "security-endpoints",
            "max_age": 86400,  # 1 day
            "include_subdomains": True,
            "failure_fraction": 0.01,  # Report 1% of failures
            "success_fraction": 0.001   # Report 0.1% of successes
        }
        
        import json
        return json.dumps(nel_config)
        
    def _is_sensitive_page(self, request):
        """
        Determine if the current page contains sensitive information.
        
        Args:
            request: Django HttpRequest object
            
        Returns:
            bool: True if page is sensitive
        """
        sensitive_paths = [
            '/admin/',
            '/accounts/',
            '/profile/',
            '/settings/',
            '/api/auth/',
            '/password/',
        ]
        
        for path in sensitive_paths:
            if request.path.startswith(path):
                return True
                
        # Check if user is authenticated (authenticated pages are sensitive)
        if hasattr(request, 'user') and request.user.is_authenticated:
            return True
            
        return False


class SecurityReportMiddleware(MiddlewareMixin):
    """
    Middleware to handle security violation reports.
    
    This middleware processes reports from:
    - CSP violations
    - Permissions Policy violations
    - Network errors (NEL)
    - Other security reports
    """
    
    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)
        
    def process_request(self, request):
        """
        Process security report requests.
        
        Args:
            request: Django HttpRequest object
        """
        # Check if this is a security report endpoint
        if request.path == '/api/security-report/':
            return self._handle_security_report(request)
            
        return None
        
    def _handle_security_report(self, request):
        """
        Handle incoming security reports.
        
        Args:
            request: Django HttpRequest object
            
        Returns:
            HttpResponse: Empty response
        """
        from django.http import HttpResponse
        import json
        
        if request.method != 'POST':
            return HttpResponse(status=405)  # Method Not Allowed
            
        try:
            report_data = json.loads(request.body.decode('utf-8'))
            
            # Log the security report
            report_type = report_data.get('type', 'unknown')
            
            if report_type == 'csp-violation':
                self._log_csp_violation(report_data)
            elif report_type == 'permissions-policy-violation':
                self._log_permissions_violation(report_data)
            elif report_type == 'network-error':
                self._log_network_error(report_data)
            else:
                logger.warning(f"Unknown security report type: {report_type}")
                
            return HttpResponse(status=204)  # No Content
            
        except Exception as e:
            logger.error(f"Error processing security report: {e}")
            return HttpResponse(status=400)  # Bad Request
            
    def _log_csp_violation(self, report):
        """Log CSP violation."""
        logger.warning(f"CSP Violation: {report}")
        
    def _log_permissions_violation(self, report):
        """Log Permissions Policy violation."""
        logger.warning(f"Permissions Policy Violation: {report}")
        
    def _log_network_error(self, report):
        """Log network error."""
        logger.info(f"Network Error: {report}")