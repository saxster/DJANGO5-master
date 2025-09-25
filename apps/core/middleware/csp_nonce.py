"""
CSP Nonce Middleware for Content Security Policy
Generates and manages nonces for inline scripts and styles to replace unsafe-inline
"""

import base64
import hashlib
import secrets
import logging
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

logger = logging.getLogger("security")


class CSPNonceMiddleware(MiddlewareMixin):
    """
    Middleware to generate and inject CSP nonces for inline scripts and styles.
    This allows removing 'unsafe-inline' from CSP while maintaining functionality.
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)
        
        # Configuration
        self.enable_nonce = getattr(settings, 'CSP_ENABLE_NONCE', True)
        self.nonce_length = getattr(settings, 'CSP_NONCE_LENGTH', 32)
        
    def process_request(self, request):
        """
        Generate CSP nonce for the request.
        
        Args:
            request: Django HttpRequest object
        """
        if not self.enable_nonce:
            return None
            
        # Generate a cryptographically secure random nonce
        nonce_bytes = secrets.token_bytes(self.nonce_length)
        nonce = base64.b64encode(nonce_bytes).decode('utf-8')
        
        # Store nonce in request for use in templates and response
        request.csp_nonce = nonce
        
        # Also generate script hashes for known inline scripts if needed
        request.csp_script_hashes = []
        request.csp_style_hashes = []
        
        return None
        
    def process_response(self, request, response):
        """
        Add CSP nonce to response headers.
        
        Args:
            request: Django HttpRequest object
            response: Django HttpResponse object
            
        Returns:
            Modified response with CSP headers
        """
        # Skip if nonce is disabled or not generated
        if not self.enable_nonce or not hasattr(request, 'csp_nonce'):
            return response
            
        # Skip for static files and media
        if request.path.startswith(('/static/', '/media/')):
            return response
            
        nonce = request.csp_nonce
        
        # Build CSP directives with nonce
        csp_directives = self._build_csp_directives(nonce, request)
        
        # Set the Content-Security-Policy header
        response['Content-Security-Policy'] = csp_directives
        
        # Also set report-only header for testing (can be removed in production)
        if getattr(settings, 'CSP_REPORT_ONLY', False):
            response['Content-Security-Policy-Report-Only'] = csp_directives
            
        return response
        
    def _build_csp_directives(self, nonce, request):
        """
        Build CSP directive string with nonce support.
        
        Args:
            nonce: Generated nonce value
            request: Django HttpRequest object
            
        Returns:
            CSP directive string
        """
        # Get base CSP configuration from settings
        csp_config = getattr(settings, 'CSP_DIRECTIVES', {})
        
        # Default secure CSP directives
        directives = {
            'default-src': ["'self'"],
            'script-src': ["'self'", f"'nonce-{nonce}'"],
            'style-src': ["'self'", f"'nonce-{nonce}'"],
            'img-src': ["'self'", "data:", "https:", "blob:"],
            'font-src': ["'self'", "data:", "https://fonts.googleapis.com", "https://fonts.gstatic.com"],
            'connect-src': ["'self'", "https:"],
            'frame-ancestors': ["'none'"],
            'base-uri': ["'self'"],
            'form-action': ["'self'"],
            'object-src': ["'none'"],
            'upgrade-insecure-requests': [],
        }
        
        # Merge with custom configuration
        for directive, sources in csp_config.items():
            if directive in directives:
                # Merge sources, avoiding duplicates
                directives[directive] = list(set(directives[directive] + sources))
            else:
                directives[directive] = sources
                
        # Add script hashes if any were collected
        if hasattr(request, 'csp_script_hashes') and request.csp_script_hashes:
            for hash_value in request.csp_script_hashes:
                directives['script-src'].append(f"'sha256-{hash_value}'")
                
        # Add style hashes if any were collected  
        if hasattr(request, 'csp_style_hashes') and request.csp_style_hashes:
            for hash_value in request.csp_style_hashes:
                directives['style-src'].append(f"'sha256-{hash_value}'")
                
        # Add report-uri if configured
        report_uri = getattr(settings, 'CSP_REPORT_URI', None)
        if report_uri:
            directives['report-uri'] = [report_uri]
            directives['report-to'] = ['csp-endpoint']
            
        # Build the directive string
        directive_strings = []
        for directive, sources in directives.items():
            if sources:
                if directive in ['upgrade-insecure-requests']:
                    # These directives don't take values
                    directive_strings.append(directive)
                else:
                    sources_str = ' '.join(sources)
                    directive_strings.append(f"{directive} {sources_str}")
            elif directive in ['upgrade-insecure-requests']:
                directive_strings.append(directive)
                
        return '; '.join(directive_strings)


def calculate_script_hash(script_content):
    """
    Calculate SHA-256 hash for inline script content.
    
    Args:
        script_content: The inline script content
        
    Returns:
        Base64-encoded SHA-256 hash
    """
    # Remove leading/trailing whitespace but preserve internal formatting
    script_content = script_content.strip()
    
    # Calculate SHA-256 hash
    hash_obj = hashlib.sha256(script_content.encode('utf-8'))
    hash_bytes = hash_obj.digest()
    
    # Base64 encode the hash
    return base64.b64encode(hash_bytes).decode('utf-8')


def calculate_style_hash(style_content):
    """
    Calculate SHA-256 hash for inline style content.
    
    Args:
        style_content: The inline style content
        
    Returns:
        Base64-encoded SHA-256 hash
    """
    # Remove leading/trailing whitespace but preserve internal formatting
    style_content = style_content.strip()
    
    # Calculate SHA-256 hash
    hash_obj = hashlib.sha256(style_content.encode('utf-8'))
    hash_bytes = hash_obj.digest()
    
    # Base64 encode the hash
    return base64.b64encode(hash_bytes).decode('utf-8')