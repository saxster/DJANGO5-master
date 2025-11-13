# Core App

## Purpose

Central infrastructure and shared utilities for the enterprise facility management platform. Provides security middleware, caching strategies, performance monitoring, state machines, and reusable services.

## Key Features

- **Security Middleware** - CSP, CORS, SQL injection protection, mass assignment protection
- **Caching Infrastructure** - Redis-backed multi-layer caching with tenant awareness
- **Performance Monitoring** - Slow query detection, performance budgets, metrics collection
- **State Machines** - Workflow state management with transition validation
- **Exception Handling** - Centralized exception patterns and sanitization
- **Feature Flags** - Dynamic feature toggles without deployments
- **File Services** - Secure file upload/download with validation
- **Health Checks** - Comprehensive system health monitoring
- **Correlation IDs** - Request tracing across distributed systems
- **Encryption** - Field-level encryption with key rotation

---

## Architecture

### Core Components

**Security Layer:**
- SQL Injection Protection Middleware
- Mass Assignment Protection
- CSV Injection Prevention
- Logging Sanitization
- Error Response Validation
- Content Security Policy (CSP) with nonce generation

**Caching Layer:**
- Tenant-aware caching
- Smart cache invalidation
- Cache security middleware
- PostgreSQL Select2 caching
- Materialized view caching

**Performance Monitoring:**
- Slow query detection
- Performance budget enforcement
- Query optimization helpers
- WebSocket throttling

**Middleware Stack:**
- Correlation ID tracking
- Session activity logging
- Concurrent session limiting
- CSP nonce injection
- Smart caching
- WebSocket origin validation

**Services:**
- Secure File Upload/Download Service
- Encryption Service
- Feature Flag Service
- Health Check Service
- Idempotency Service
- Audit Logging Service

---

## Directory Structure

```
apps/core/
├── admin/                      # Admin panel enhancements
├── api/                        # REST API utilities
├── cache/                      # Caching strategies
│   ├── tenant_aware.py
│   ├── materialized_view_select2.py
│   └── postgresql_select2.py
├── constants/                  # Shared constants
│   ├── datetime_constants.py
│   ├── sentinel_constants.py
│   └── spatial_constants.py
├── decorators/                 # Reusable decorators
├── encryption/                 # Encryption utilities
├── exceptions/                 # Custom exceptions
│   └── patterns.py
├── feature_flags/              # Feature toggle system
├── fields/                     # Custom Django fields
│   └── encrypted_fields.py
├── managers/                   # Custom model managers
├── middleware/                 # Security & performance middleware
├── mixins/                     # Reusable model/view mixins
├── security/                   # Security utilities
│   ├── secrets_rotation.py
│   ├── csv_injection_protection.py
│   └── mass_assignment_protection.py
├── services/                   # Business logic services
│   ├── secure_file_download_service.py
│   ├── file_upload_service.py
│   ├── encryption_service.py
│   └── audit_logging_service.py
├── state_machines/             # Workflow state machines
├── tasks/                      # Celery tasks
├── templatetags/               # Django template tags
├── tests/                      # Comprehensive test suite
└── utils_new/                  # Utility functions
    ├── datetime_utilities.py
    ├── error_handling.py
    └── retry_mechanism.py
```

---

## Security Features

### SQL Injection Protection

```python
# Middleware automatically sanitizes SQL queries
# intelliwiz_config/settings/base.py
MIDDLEWARE = [
    'apps.core.sql_security.SQLInjectionProtectionMiddleware',
    # ... other middleware
]

# Enforces parameterized queries
cursor.execute("SELECT * FROM users WHERE id = %s", [user_id])  # ✅ SAFE
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")     # ❌ BLOCKED
```

### Mass Assignment Protection

```python
from apps.core.security.mass_assignment_protection import safe_update_model

# Protects against mass assignment attacks
safe_fields = ['name', 'email', 'phone']
safe_update_model(
    instance=user,
    data=request.POST,
    allowed_fields=safe_fields
)

# Attempts to set is_admin=True will be blocked
```

### CSV Injection Prevention

```python
from apps.core.security.csv_injection_protection import sanitize_csv_value

# Sanitizes CSV exports to prevent formula injection
sanitized = sanitize_csv_value("=1+1")  # Returns "'=1+1" (quoted)
```

### Content Security Policy (CSP)

```python
# Automatic CSP nonce generation
# apps/core/middleware/csp_nonce.py

# In templates
{% load csp_tags %}
<script nonce="{% csp_nonce %}">
    console.log('Inline script with CSP nonce');
</script>
```

### Logging Sanitization

```python
# Automatically sanitizes PII from logs
# apps/core/middleware/logging_sanitization.py

logger.info(f"User login: {email}")  # Email redacted in logs
# Output: "User login: [REDACTED-EMAIL]"
```

---

## Caching Infrastructure

### Tenant-Aware Caching

```python
from apps.core.cache.tenant_aware import TenantAwareCache

# Cache automatically scoped to tenant
cache = TenantAwareCache()
cache.set('user_count', 150, timeout=3600)  # Key: "tenant_123:user_count"
value = cache.get('user_count')
```

### Smart Cache Invalidation

```python
from apps.core.cache_manager import CacheManager

# Invalidate related caches
CacheManager.invalidate_pattern('user_*')  # Invalidates all user_* keys
CacheManager.invalidate_tenant_cache(tenant_id)  # Clear all tenant caches
```

### PostgreSQL Select2 Caching

```python
# Materialized view for large Select2 dropdowns
from apps.core.cache.materialized_view_select2 import MaterializedViewSelect2Mixin

class UserAutocomplete(MaterializedViewSelect2Mixin, autocomplete.Select2QuerySetView):
    """Fast autocomplete with materialized view caching"""
    model = People
    search_fields = ['peoplename', 'email']
```

---

## Performance Monitoring

### Slow Query Detection

```python
# Middleware logs queries exceeding threshold
# intelliwiz_config/settings/base.py
SLOW_QUERY_THRESHOLD_MS = 100  # Log queries > 100ms

# Logged automatically
# WARNING: Slow query detected: SELECT * FROM users (Duration: 250ms)
```

### Performance Budget Enforcement

```python
# Middleware enforces response time budgets
# apps/core/middleware/performance_budget_middleware.py

PERFORMANCE_BUDGETS = {
    '/api/': 200,        # 200ms max for API
    '/dashboard/': 500,  # 500ms max for dashboard
}
```

### Query Optimization

```python
from apps.core.managers.optimized_managers import OptimizedManager

# Automatically optimizes queries
users = People.objects.with_full_details()  # select_related + prefetch_related
```

---

## State Machines

### Workflow State Management

```python
from apps.core.state_machines.base import BaseStateMachine

class TicketStateMachine(BaseStateMachine):
    """State machine for ticket workflow"""

    states = ['NEW', 'OPEN', 'RESOLVED', 'CLOSED']
    transitions = {
        'NEW': ['OPEN', 'CLOSED'],
        'OPEN': ['RESOLVED', 'CLOSED'],
        'RESOLVED': ['OPEN', 'CLOSED'],
    }

    def can_transition(self, from_state, to_state):
        """Validate if transition is allowed"""
        return to_state in self.transitions.get(from_state, [])

    def transition(self, obj, new_state, user):
        """Execute state transition with validation"""
        if not self.can_transition(obj.status, new_state):
            raise ValidationError(f"Cannot transition from {obj.status} to {new_state}")

        obj.status = new_state
        obj.save()
```

---

## Exception Handling

### Centralized Exception Patterns

```python
from apps.core.exceptions.patterns import (
    DATABASE_EXCEPTIONS,
    NETWORK_EXCEPTIONS,
    PARSING_EXCEPTIONS
)

# Use specific exception groups
try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise

try:
    response = requests.get(url, timeout=(5, 15))
except NETWORK_EXCEPTIONS as e:
    logger.warning(f"Network error: {e}")
    # Handle network failures
```

### Error Response Sanitization

```python
# Middleware sanitizes error responses
# apps/core/middleware/error_response_validation.py

# Development: Full stack traces
# Production: Sanitized error messages only
```

---

## Feature Flags

### Dynamic Feature Toggles

```python
from apps.core.feature_flags.service import FeatureFlagService

# Check if feature enabled
if FeatureFlagService.is_enabled('new_dashboard', user=request.user):
    # Show new dashboard
    return render(request, 'dashboard_v2.html')
else:
    # Show old dashboard
    return render(request, 'dashboard.html')

# Feature flag decorator
from apps.core.feature_flags.decorators import require_feature_flag

@require_feature_flag('api_v2')
def new_api_endpoint(request):
    return JsonResponse({'version': 'v2'})
```

---

## File Services

### Secure File Upload

```python
from apps.core.services.file_upload_service import SecureFileUploadService

# Validate and upload file
uploaded_file = SecureFileUploadService.validate_and_upload(
    file=request.FILES['document'],
    user=request.user,
    allowed_extensions=['.pdf', '.docx', '.xlsx'],
    max_size_mb=10
)
```

### Secure File Download

```python
from apps.core.services.secure_file_download_service import SecureFileDownloadService

# Validate access and serve file
response = SecureFileDownloadService.validate_and_serve_file(
    filepath='/media/documents/report.pdf',
    filename='report.pdf',
    user=request.user,
    owner_id=document_owner_id
)
```

---

## Health Checks

### System Health Monitoring

```python
# Endpoint: /health/
# Checks:
# - Database connectivity
# - Redis connectivity
# - Celery workers
# - Disk space
# - Memory usage

# Example response
{
    "status": "healthy",
    "checks": {
        "database": "OK",
        "redis": "OK",
        "celery": "OK",
        "disk_space": "OK (45% used)",
        "memory": "OK (2.1GB / 8GB)"
    },
    "timestamp": "2025-11-12T04:30:00Z"
}
```

---

## Correlation IDs

### Request Tracing

```python
# Middleware adds correlation IDs to all requests
# apps/core/middleware/correlation_id_middleware.py

# Headers
X-Correlation-ID: 550e8400-e29b-41d4-a716-446655440000

# Logging
logger.info("Processing request", extra={
    'correlation_id': request.correlation_id
})

# Celery tasks inherit correlation IDs
from apps.core.tasks.celery_correlation_id import inherit_correlation_id

@shared_task
@inherit_correlation_id
def process_report(data):
    logger.info("Processing report")  # correlation_id automatically included
```

---

## Encryption

### Field-Level Encryption

```python
from apps.core.fields import EncryptedTextField, EncryptedJSONField

class SensitiveData(models.Model):
    ssn = EncryptedTextField()  # Encrypted at rest
    medical_history = EncryptedJSONField()  # Encrypted JSON

# Transparent encryption/decryption
data = SensitiveData.objects.create(
    ssn='123-45-6789',
    medical_history={'conditions': ['diabetes']}
)

# Automatically encrypted in database
# Automatically decrypted on retrieval
print(data.ssn)  # '123-45-6789'
```

### Key Rotation

```python
from apps.core.security.secrets_rotation import rotate_encryption_keys

# Rotate encryption keys
rotate_encryption_keys(
    old_key=settings.OLD_ENCRYPTION_KEY,
    new_key=settings.NEW_ENCRYPTION_KEY
)
```

---

## Utilities

### DateTime Utilities

```python
from apps.core.utils_new.datetime_utilities import (
    get_current_utc,
    convert_to_utc,
    get_date_range
)
from apps.core.constants.datetime_constants import SECONDS_IN_DAY, SECONDS_IN_HOUR

# Python 3.12+ compatible
now = get_current_utc()
utc_time = convert_to_utc(local_time, 'Asia/Singapore')

# Use constants instead of magic numbers
cache_timeout = 2 * SECONDS_IN_HOUR  # 2 hours
```

### Retry Mechanism

```python
from apps.core.utils_new.retry_mechanism import with_retry

@with_retry(
    exceptions=(IntegrityError, OperationalError),
    max_retries=3,
    retry_policy='DATABASE_OPERATION'
)
def save_user(user):
    user.save()
```

### Error Handling

```python
from apps.core.utils_new.error_handling import safe_property

class MyModel(models.Model):
    @property
    @safe_property(fallback_value="")
    def computed_value(self):
        """Property with automatic error handling"""
        return self.complex_computation()
```

---

## Testing

### Running Tests

```bash
# All core tests
pytest apps/core/tests/ -v

# Specific test module
pytest apps/core/tests/test_cache_security_comprehensive.py -v

# Security tests
pytest apps/core/tests/test_comprehensive_security_fixes.py -v

# With coverage
pytest apps/core/tests/ --cov=apps/core --cov-report=html
```

---

## Configuration

### Settings

```python
# intelliwiz_config/settings/base.py

# Security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

# Performance
SLOW_QUERY_THRESHOLD_MS = 100
PERFORMANCE_BUDGETS = {'/api/': 200}

# Feature flags
FEATURE_FLAGS = {
    'new_dashboard': True,
    'api_v2': True,
}
```

---

## Related Apps

- [peoples](../peoples/README.md) - User authentication
- [tenants](../tenants/README.md) - Multi-tenancy
- All apps depend on core infrastructure

---

## Troubleshooting

### Common Issues

**Issue:** SQL injection protection blocking valid queries
**Solution:** Use parameterized queries with %s placeholders

**Issue:** Cache not invalidating
**Solution:** Check tenant scoping and invalidation patterns

**Issue:** Feature flag not working
**Solution:** Verify flag enabled in settings and cleared cache

**Issue:** Slow query logs flooding
**Solution:** Adjust SLOW_QUERY_THRESHOLD_MS or optimize queries

---

**Last Updated:** November 12, 2025
**Maintainers:** Infrastructure Team
**Contact:** infrastructure-team@example.com
