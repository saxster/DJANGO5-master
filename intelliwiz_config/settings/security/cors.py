"""
CORS (Cross-Origin Resource Sharing) configuration.
Cross-origin settings, allowed origins, and preflight configuration.
"""

# CORS Configuration
CORS_ALLOWED_ORIGINS = ["https://django5.youtility.in"]
CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://\w+\.youtility\.in$"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with"
]
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]
CORS_PREFLIGHT_MAX_AGE = 86400