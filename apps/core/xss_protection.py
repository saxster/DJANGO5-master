"""
XSS Protection middleware for automatic input sanitization with rate limiting.
"""
import logging
import time
from collections import defaultdict, deque
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseBadRequest
from django.conf import settings
from apps.core.validation import XSSPrevention
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("security")


class XSSProtectionMiddleware(MiddlewareMixin):
    """
    Middleware to automatically sanitize request parameters and detect XSS attempts.
    Enhanced with rate limiting to prevent abuse.
    """

    # Rate limiting storage (in production, consider using Redis)
    _xss_attempts = defaultdict(deque)
    _rate_limit_window = 300  # 5 minutes
    _max_attempts = 5  # Max XSS attempts per IP per window

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)

        # Configure rate limiting from settings
        self._rate_limit_window = getattr(settings, 'XSS_RATE_LIMIT_WINDOW', 300)
        self._max_attempts = getattr(settings, 'XSS_MAX_ATTEMPTS', 5)

    # Paths to exclude from XSS scanning (admin, API endpoints that handle their own validation)
    EXCLUDED_PATHS = [
        "/admin/",
        "/api/",
        "/static/",
        "/media/",
        "/health/",
    ]

    # Parameters to exclude from sanitization (may contain legitimate HTML)
    EXCLUDED_PARAMS = [
        "csrfmiddlewaretoken",
        "password",
        "password1",
        "password2",
    ]

    def process_request(self, request):
        """
        Process incoming request to detect and sanitize XSS attempts.
        Enhanced with rate limiting for repeated XSS attempts.
        """
        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.EXCLUDED_PATHS):
            return None

        # Check rate limiting for this IP
        client_ip = self._get_client_ip(request)
        if self._is_rate_limited(client_ip):
            logger.warning(
                f"XSS rate limit exceeded for IP: {client_ip}",
                extra={
                    'client_ip': client_ip,
                    'path': request.path,
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100]
                }
            )
            return HttpResponseBadRequest("Too many suspicious requests. Please try again later.")

        # Check and sanitize GET parameters
        if request.GET:
            cleaned_get = self._sanitize_querydict(request.GET, request)
            if cleaned_get != request.GET:
                request.GET = cleaned_get

        # Check and sanitize POST parameters
        if request.POST:
            cleaned_post = self._sanitize_querydict(request.POST, request)
            if cleaned_post != request.POST:
                request.POST = cleaned_post

        return None

    def _sanitize_querydict(self, querydict, request):
        """
        Sanitize a QueryDict and detect XSS attempts.

        Args:
            querydict: Django QueryDict to sanitize
            request: HTTP request object

        Returns:
            Sanitized QueryDict or None if malicious content detected
        """
        suspicious_detected = False
        sanitized_data = {}

        for key, values in querydict.lists():
            # Skip excluded parameters
            if key in self.EXCLUDED_PARAMS:
                sanitized_data[key] = values
                continue

            sanitized_values = []
            for value in values:
                try:
                    # Check for obvious XSS attempts
                    if self._is_xss_attempt(value):
                        suspicious_detected = True
                        self._log_xss_attempt(request, key, value)

                        # Record XSS attempt for rate limiting
                        client_ip = self._get_client_ip(request)
                        self._record_xss_attempt(client_ip)

                        # Replace with safe placeholder
                        sanitized_values.append("[SANITIZED]")
                    else:
                        # Sanitize the value
                        sanitized_value = XSSPrevention.sanitize_html(value)
                        sanitized_values.append(sanitized_value)

                except (ConnectionError, ValueError) as e:
                    # Log sanitization error
                    ErrorHandler.handle_exception(
                        e,
                        context={
                            "middleware": "XSSProtectionMiddleware",
                            "parameter": key,
                            "value_length": len(str(value)),
                        },
                        level="warning",
                    )
                    sanitized_values.append("[ERROR_SANITIZING]")

            sanitized_data[key] = sanitized_values

        # Return original if no changes needed, otherwise create new QueryDict
        if not suspicious_detected and sanitized_data == dict(querydict.lists()):
            return querydict
        else:
            # Create new QueryDict with sanitized data
            from django.http import QueryDict

            new_querydict = QueryDict(mutable=True)
            for key, values in sanitized_data.items():
                for value in values:
                    new_querydict.appendlist(key, value)
            new_querydict._mutable = False
            return new_querydict

    def _is_xss_attempt(self, value):
        """
        Enhanced XSS detection with comprehensive pattern matching.

        Args:
            value: String value to check

        Returns:
            True if value appears to be malicious
        """
        if not isinstance(value, str):
            return False

        # Normalize value for comprehensive checking
        value_lower = value.lower()
        value_clean = self._normalize_for_detection(value)

        # 1. Script tag detection (various encodings and obfuscations)
        if self._check_script_patterns(value_lower, value_clean):
            return True

        # 2. Event handler detection
        if self._check_event_handlers(value_lower):
            return True

        # 3. JavaScript protocol detection
        if self._check_javascript_protocols(value_lower, value_clean):
            return True

        # 4. HTML injection patterns
        if self._check_html_injection(value_lower):
            return True

        # 5. CSS injection patterns (style-based XSS)
        if self._check_css_injection(value_lower):
            return True

        # 6. Encoded payload detection
        if self._check_encoded_patterns(value_lower, value):
            return True

        # 7. Advanced obfuscation techniques
        if self._check_obfuscated_patterns(value_lower, value):
            return True

        # 8. DOM manipulation patterns
        if self._check_dom_patterns(value_lower):
            return True

        return False

    def _normalize_for_detection(self, value):
        """Normalize value by removing whitespace and common obfuscation techniques."""
        import re

        # Remove all whitespace variations
        clean = re.sub(r'[\s\n\r\t\f\v]+', '', value)

        # Remove common comment patterns used for obfuscation
        clean = re.sub(r'/\*.*?\*/', '', clean, flags=re.DOTALL)
        clean = re.sub(r'//.*?[\n\r]', '', clean)

        # Decode common HTML entities
        entities = {
            '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'",
            '&amp;': '&', '&#60;': '<', '&#62;': '>', '&#34;': '"',
            '&#39;': "'", '&#38;': '&', '&#x3c;': '<', '&#x3e;': '>',
        }

        for entity, char in entities.items():
            clean = clean.replace(entity, char)
            clean = clean.replace(entity.upper(), char)

        return clean.lower()

    def _check_script_patterns(self, value_lower, value_clean):
        """Check for script tag variations and obfuscations."""
        import re

        script_patterns = [
            # Basic script tags
            r'<\s*script[^>]*>',
            r'</\s*script\s*>',

            # Obfuscated script tags
            r'<\s*sc\s*ript[^>]*>',
            r'<\s*s\s*c\s*r\s*i\s*p\s*t[^>]*>',

            # SVG script patterns
            r'<\s*svg[^>]*>.*?<\s*script[^>]*>',

            # XML/CDATA patterns
            r'<!\s*\[\s*cdata\s*\[.*?javascript',

            # Encoded variations
            r'%3c\s*script',
            r'&lt;\s*script',
            r'\x3cscript',
        ]

        for pattern in script_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE | re.DOTALL):
                return True
            if re.search(pattern, value_clean, re.IGNORECASE | re.DOTALL):
                return True

        return False

    def _check_event_handlers(self, value_lower):
        """Check for JavaScript event handlers."""
        event_handlers = [
            # Mouse events
            'onclick=', 'ondblclick=', 'onmousedown=', 'onmouseup=',
            'onmouseover=', 'onmouseout=', 'onmousemove=', 'oncontextmenu=',

            # Keyboard events
            'onkeydown=', 'onkeyup=', 'onkeypress=',

            # Form events
            'onsubmit=', 'onreset=', 'onchange=', 'onselect=', 'onfocus=',
            'onblur=', 'oninput=',

            # Window/document events
            'onload=', 'onunload=', 'onbeforeunload=', 'onresize=', 'onscroll=',
            'onerror=', 'onabort=', 'oncanplay=', 'oncanplaythrough=',

            # HTML5 events
            'ondrag=', 'ondragstart=', 'ondragend=', 'ondrop=', 'ondragover=',
            'ontouchstart=', 'ontouchend=', 'ontouchmove=',

            # Animation events
            'onanimationstart=', 'onanimationend=', 'ontransitionend=',

            # Media events
            'onplay=', 'onpause=', 'onended=', 'onvolumechange=',
        ]

        for handler in event_handlers:
            if handler in value_lower:
                return True

        return False

    def _check_javascript_protocols(self, value_lower, value_clean):
        """Check for JavaScript protocol variations."""
        js_protocols = [
            'javascript:', 'jscript:', 'vbscript:', 'livescript:',
            'j&#97;vascript:', 'j&#x61;vascript:', 'java&#115;cript:',
            'java%73cript:', 'data:text/html', 'data:text/javascript',
            'data:application/javascript', 'data:image/svg+xml',
        ]

        for protocol in js_protocols:
            if protocol in value_lower or protocol in value_clean:
                return True

        return False

    def _check_html_injection(self, value_lower):
        """Check for HTML injection patterns."""
        html_patterns = [
            '<iframe', '<object', '<embed', '<applet', '<meta',
            '<link', '<style', '<base', '<form', '<input',
            '<textarea', '<select', '<option', '<button',
            '<img', '<audio', '<video', '<source', '<track',
            '<frame', '<frameset', '<noframes', '<isindex',
        ]

        for pattern in html_patterns:
            if pattern in value_lower:
                return True

        return False

    def _check_css_injection(self, value_lower):
        """Check for CSS-based XSS patterns."""
        import re

        css_patterns = [
            # CSS expression() function
            r'expression\s*\(',

            # CSS @import with javascript
            r'@import.*?[\'"]javascript:',

            # CSS behavior property (IE)
            r'behavior\s*:\s*url\s*\(',

            # CSS -moz-binding (Firefox)
            r'-moz-binding\s*:\s*url\s*\(',

            # CSS background with javascript
            r'background.*?javascript:',
            r'background-image.*?javascript:',

            # CSS content with javascript
            r'content\s*:.*?javascript:',
        ]

        for pattern in css_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True

        return False

    def _check_encoded_patterns(self, value_lower, original_value):
        """Check for various encoding schemes used to bypass filters."""
        import re
        import urllib.parse

        # URL encoding variations
        encoded_patterns = [
            '%3cscript', '%3c%73%63%72%69%70%74', '%6a%61%76%61%73%63%72%69%70%74',
            '%253cscript', '%u003cscript', '%u003c%u0073%u0063%u0072%u0069%u0070%u0074',
        ]

        for pattern in encoded_patterns:
            if pattern in value_lower:
                return True

        # Try URL decoding to detect double-encoded attacks
        try:
            decoded = urllib.parse.unquote(original_value)
            if decoded != original_value and self._is_xss_attempt(decoded):
                return True
        except:
            pass

        # HTML entity encoding
        entity_patterns = [
            r'&#[0-9]{1,3};.*?script',
            r'&#x[0-9a-f]{1,2};.*?script',
            r'&lt;.*?script',
            r'&\w+;.*?javascript',
        ]

        for pattern in entity_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True

        return False

    def _check_obfuscated_patterns(self, value_lower, original_value):
        """Check for advanced obfuscation techniques."""
        import re

        # String concatenation patterns
        concat_patterns = [
            r'["\'][\s]*\+[\s]*["\']',  # "str" + "ing"
            r'string\.fromcharcode\s*\(',  # String.fromCharCode()
            r'eval\s*\(',  # eval() function
            r'settimeout\s*\(',  # setTimeout()
            r'setinterval\s*\(',  # setInterval()
        ]

        for pattern in concat_patterns:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True

        # Check for excessive character repetition (potential obfuscation)
        # SECURITY FIX: Increased entropy threshold from 0.3 to 0.4 for better detection
        if len(original_value) > 50:
            unique_chars = len(set(original_value.lower()))
            total_chars = len(original_value)
            if unique_chars / total_chars < 0.4:  # Stricter entropy threshold
                return True

        return False

    def _check_dom_patterns(self, value_lower):
        """Check for DOM manipulation patterns."""
        dom_patterns = [
            'document.cookie', 'document.write', 'document.writeln',
            'window.location', 'location.href', 'location.replace',
            'document.domain', 'document.body', 'document.head',
            'innerhtml', 'outerhtml', 'createelement', 'appendchild',
            'getelementsbytagname', 'getelementbyid', 'queryselector',
            'localstorage', 'sessionstorage', 'xmlhttprequest',
            'activexobject', 'window.open', 'history.back',
        ]

        for pattern in dom_patterns:
            if pattern in value_lower:
                return True

        return False

    def _log_xss_attempt(self, request, parameter, value):
        """
        Log XSS attempt with request details.

        Args:
            request: HTTP request object
            parameter: Parameter name containing XSS
            value: Malicious value
        """
        client_ip = self._get_client_ip(request)
        user = str(request.user) if request.user.is_authenticated else "Anonymous"

        logger.warning(
            f"XSS attempt detected - IP: {client_ip}, User: {user}, "
            f"Path: {request.path}, Parameter: {parameter}, "
            f"Value: {value[:100]}{'...' if len(value) > 100 else ''}"
        )

    def _is_rate_limited(self, client_ip: str) -> bool:
        """
        Check if client IP is rate limited for XSS attempts.

        Args:
            client_ip: Client IP address

        Returns:
            bool: True if rate limited
        """
        current_time = time.time()

        # Clean old attempts outside the window
        self._clean_old_attempts(client_ip, current_time)

        # Check if current attempts exceed limit
        return len(self._xss_attempts[client_ip]) >= self._max_attempts

    def _record_xss_attempt(self, client_ip: str):
        """
        Record an XSS attempt for rate limiting.

        Args:
            client_ip: Client IP address
        """
        current_time = time.time()

        # Clean old attempts first
        self._clean_old_attempts(client_ip, current_time)

        # Record new attempt
        self._xss_attempts[client_ip].append(current_time)

    def _clean_old_attempts(self, client_ip: str, current_time: float):
        """
        Clean XSS attempts outside the rate limiting window.

        Args:
            client_ip: Client IP address
            current_time: Current timestamp
        """
        attempts = self._xss_attempts[client_ip]
        cutoff_time = current_time - self._rate_limit_window

        # Remove attempts older than the window
        while attempts and attempts[0] < cutoff_time:
            attempts.popleft()

    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class CSRFHeaderMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers for XSS and CSRF protection.
    Note: CSP headers are now handled by CSPNonceMiddleware for better security.
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_response(self, request, response):
        """
        Add security headers to response.
        """
        # XSS Protection header (legacy, but still useful for older browsers)
        response["X-XSS-Protection"] = "1; mode=block"

        # Content Type Options header - Prevents MIME type sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # Referrer Policy header - Controls referrer information
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Frame Options - Prevents clickjacking
        if not response.get("X-Frame-Options"):
            response["X-Frame-Options"] = "DENY"
        
        # Permissions Policy (formerly Feature Policy) - Controls browser features
        if not response.get("Permissions-Policy"):
            response["Permissions-Policy"] = (
                "geolocation=(), "
                "camera=(), "
                "microphone=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "accelerometer=()"
            )

        # Note: CSP is now handled by CSPNonceMiddleware for nonce-based security
        # Only set a basic CSP if CSPNonceMiddleware is not enabled
        if not response.get("Content-Security-Policy") and not hasattr(request, 'csp_nonce'):
            # Fallback CSP without unsafe-inline/unsafe-eval - very restrictive
            csp = (
                "default-src 'self'; "
                "script-src 'self' https://fonts.googleapis.com https://ajax.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "style-src 'self' https://fonts.googleapis.com https://ajax.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https: blob:; "
                "font-src 'self' data: https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response["Content-Security-Policy"] = csp

        return response


def sanitize_template_context(context):
    """
    Sanitize template context to prevent XSS in templates.

    Args:
        context: Template context dictionary

    Returns:
        Sanitized context dictionary
    """
    if not isinstance(context, dict):
        return context

    sanitized = {}
    for key, value in context.items():
        if isinstance(value, str):
            # Only sanitize string values that are not marked as safe
            from django.utils.safestring import SafeData

            if not isinstance(value, SafeData):
                sanitized[key] = XSSPrevention.sanitize_html(value)
            else:
                sanitized[key] = value
        elif isinstance(value, (list, tuple)):
            sanitized[key] = [
                XSSPrevention.sanitize_html(item) if isinstance(item, str) else item
                for item in value
            ]
        elif isinstance(value, dict):
            sanitized[key] = sanitize_template_context(value)
        else:
            sanitized[key] = value

    return sanitized
