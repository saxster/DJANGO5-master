# Settings & Configuration

> **Environment files, settings structure, and configuration management**

---

## Environment Files

### Development

```bash
.env.dev.secure            # Local development settings
```

### Production

```bash
.env.production            # Production secrets (not in repo)
```

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/1
REDIS_PASSWORD=your_secure_password  # Required in production

# Django
SECRET_KEY=your_secret_key_here
DEBUG=False  # Never True in production
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# External Services (optional)
MQTT_BROKER_URL=mqtt://broker.example.com
MQTT_USERNAME=username
MQTT_PASSWORD=password

# Frappe ERP (Oct 2025 - optional)
FRAPPE_BASE_URL=https://erp.example.com
FRAPPE_API_KEY=your_api_key
FRAPPE_API_SECRET=your_api_secret
```

---

## Settings Structure

### Centralized by Concern

```text
intelliwiz_config/settings/
├── base.py               # Core Django settings (imports only)
├── development.py        # Dev overrides
├── production.py         # Production overrides
├── redis_optimized.py    # Redis configuration
└── security/
    ├── authentication.py # API authentication controls
    ├── csp.py            # Content Security Policy
    ├── headers.py        # Security headers (HSTS, cookies)
    └── middleware.py     # Security middleware config
```

### Critical Rules

- Security modules import from `security/` package to avoid drift
- Environment overrides should only adjust exported constants

---

## Database Configuration

### Primary Database

- **Engine**: PostgreSQL 14.2+ with PostGIS extension
- **Routing**: `TenantDbRouter` for multi-tenant isolation
- **Sessions**: PostgreSQL (not Redis) - 20ms trade-off approved
- **Optimization**: Use `select_related()` and `prefetch_related()` for relationships

### Connection Pooling

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME', 'intelliwiz'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
```

### Multi-Tenant Routing

```python
DATABASE_ROUTERS = ['apps.tenants.router.TenantDbRouter']
```

---

## Logging Configuration

### Comprehensive File-Based Logging with Rotation

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/intelliwiz.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/errors.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'apps': {
            'handlers': ['file', 'error_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Security: Never Log

- ❌ Passwords or authentication tokens
- ❌ PII (Personal Identifiable Information)
- ❌ Credit card or payment data
- ❌ API keys or secrets

### Log Sanitization

```python
# apps/core/services/log_access_auditing_service.py
def sanitize_log_data(data):
    """Remove sensitive fields before logging"""
    sensitive_fields = ['password', 'token', 'api_key', 'secret']
    return {k: v for k, v in data.items() if k not in sensitive_fields}
```

---

## Redis Configuration

### Environment-Specific Optimization

```python
# intelliwiz_config/settings/redis_optimized.py
from django.core.cache import CacheHandler

OPTIMIZED_CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PASSWORD': os.getenv('REDIS_PASSWORD'),
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,  # Production
                'retry_on_timeout': True,
            },
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
    },
}
```

### Cache Verification

```bash
# Verify configuration
python scripts/verify_redis_cache_config.py

# Check specific environment
python scripts/verify_redis_cache_config.py --environment production
```

---

## Static Files Configuration

### Development

```python
# Static files served automatically by runserver
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
```

### Production

```python
# Use WhiteNoise for static file serving
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Collect static files
# python manage.py collectstatic --no-input
```

---

## Security Settings

### Content Security Policy (CSP)

```python
# intelliwiz_config/settings/security/csp.py
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "cdn.example.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "*.amazonaws.com")
CSP_REPORT_URI = "/csp-report/"
```

### Middleware Stack

Order matters! Security middleware should be early in the stack:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static files
    'apps.core.middleware.security_headers.SecurityHeadersMiddleware',
    'apps.core.middleware.sql_injection.SQLInjectionProtectionMiddleware',
    'apps.core.middleware.xss_protection.XSSProtectionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # ... rest of middleware
]
```

### Session Security

```python
# Session cookies
SESSION_COOKIE_SECURE = True  # HTTPS only
SESSION_COOKIE_HTTPONLY = True  # No JavaScript access
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400  # 24 hours

# CSRF
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
```

---

## API Settings

### REST Framework

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}
```

### CORS (if needed)

```python
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
    "https://mobile.example.com",
]
CORS_ALLOW_CREDENTIALS = True
```

---

## Celery Configuration

### Basic Settings

```python
# intelliwiz_config/celery.py
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
```

### See Also

- **Complete Celery Guide**: [Celery Configuration Guide](../workflows/CELERY_CONFIGURATION_GUIDE.md)
- **Idempotency**: [Idempotency Framework](../workflows/IDEMPOTENCY_FRAMEWORK.md)

---

## Email Configuration

### Development (Console Backend)

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### Production (SMTP)

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@example.com')
```

---

## Verification Commands

### Check Configuration

```bash
# Django checks
python manage.py check

# Legacy query layer settings validation (retired Oct 2025)
# Redis configuration
python scripts/verify_redis_cache_config.py

# Schedule validation
python manage.py validate_schedules --verbose
```

---

**Last Updated**: October 29, 2025
**Maintainer**: DevOps Team
**Related**: [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md)
