"""
Content Security Policy (CSP) configuration.
CSP directives, monitoring, and violation reporting.
"""

# CONTENT SECURITY POLICY (CSP) CONFIGURATION

CSP_ENABLE_NONCE = True
CSP_NONCE_LENGTH = 32
CSP_REPORT_ONLY = False
CSP_REPORT_URI = "/api/csp-report/"
CSP_STORE_VIOLATIONS = True

# CSP Monitoring and Directives
CSP_MONITORING = {
    'ENABLE_ALERTING': True,
    'ALERT_THRESHOLD_PER_HOUR': 10,
    'ALERT_THRESHOLD_UNIQUE_VIOLATIONS': 5,
    'ENABLE_DAILY_REPORTS': True,
    'MAX_VIOLATION_AGE_DAYS': 30,
    'BLOCKED_USER_AGENTS': [
        'googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baiduspider',
        'yandexbot', 'facebookexternalhit', 'twitterbot'
    ]
}

CSP_DIRECTIVES = {
    "default-src": ["'self'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "script-src": [
        "'self'",
        "https://fonts.googleapis.com",
        "https://ajax.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com"
    ],
    "style-src": [
        "'self'",
        "https://fonts.googleapis.com",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com"
    ],
    "img-src": ["'self'", "data:", "https:", "blob:"],
    "font-src": [
        "'self'",
        "data:",
        "https://fonts.googleapis.com",
        "https://fonts.gstatic.com",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com"
    ],
    "connect-src": ["'self'", "https:"],
}