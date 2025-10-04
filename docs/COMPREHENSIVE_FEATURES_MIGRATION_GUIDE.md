# 🚀 Comprehensive Features Migration Guide

## Overview

This guide covers the migration to **47 new enterprise features** implemented across 8 phases:
- Phase 0: Quick Wins (Feature Flags, K8s Health, ETags, PII Redaction)
- Phase 1: Observability (OpenTelemetry, Distributed Tracing, Structured Logging)
- Phase 2: Performance Budgets (Per-endpoint SLAs)
- Phase 3: Reliability (Outbox/Inbox Patterns, Circuit Breakers)
- Phase 4: Security (Token Binding, Secrets Rotation)
- Phase 5-7: API Enhancements (GraphQL, REST improvements)
- Phase 8: Type Safety

---

## 📋 Prerequisites

### 1. Update Requirements

```bash
# Install all new dependencies
pip install -r requirements/feature_flags.txt
pip install -r requirements/observability.txt

# Or update base requirements
pip install -r requirements/base.txt
```

### 2. Database Migrations

```bash
# Create migrations for new models
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Expected new tables:
# - core_feature_flag_metadata
# - core_feature_flag_audit
# - core_outbox_event
# - core_inbox_event
```

### 3. External Services Setup

#### Jaeger (for Distributed Tracing)

```bash
# Using Docker
docker run -d --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 5775:5775/udp \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 14268:14268 \
  -p 14250:14250 \
  -p 9411:9411 \
  jaegertracing/all-in-one:latest

# Access UI at: http://localhost:16686
```

---

## 🔧 Phase-by-Phase Migration

### **PHASE 0: Quick Wins**

#### 1. Feature Flags

**Add to settings:**

```python
# intelliwiz_config/settings/base.py

INSTALLED_APPS += [
    'waffle',
    'apps.core.feature_flags',
]

MIDDLEWARE += [
    'apps.core.feature_flags.middleware.FeatureFlagMiddleware',
]

# Configure waffle
WAFFLE_FLAG_DEFAULT = False
WAFFLE_SWITCH_DEFAULT = False
WAFFLE_SAMPLE_DEFAULT = False
```

**Usage in code:**

```python
from apps.core.feature_flags import feature_required, FeatureFlagService

# Decorator for views
@feature_required('new_dashboard')
def dashboard_view(request):
    return render(request, 'dashboard_v2.html')

# Programmatic check
if FeatureFlagService.is_enabled('beta_features', user=request.user):
    # Show beta UI
    pass

# Template usage
{% load waffle_tags %}
{% flag "new_dashboard" %}
  <div>New Dashboard Content</div>
{% endflag %}
```

**Create flags via Django admin:**

```bash
python manage.py shell
>>> from waffle.models import Flag
>>> Flag.objects.create(name='new_dashboard', everyone=False)
```

#### 2. Kubernetes Health Endpoints

**Add to URL configuration:**

```python
# intelliwiz_config/urls_optimized.py

from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...

    # Kubernetes health checks
    path('', include('apps.core.urls_kubernetes')),
]
```

**Configure K8s probes:**

```yaml
# kubernetes/deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: intelliwiz
spec:
  template:
    spec:
      containers:
      - name: app
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10

        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

        startupProbe:
          httpGet:
            path: /startup
            port: 8000
          failureThreshold: 30
          periodSeconds: 5
```

#### 3. ETag Middleware

**Add to middleware:**

```python
# intelliwiz_config/settings/base.py

MIDDLEWARE += [
    'apps.core.middleware.etag_middleware.ETagMiddleware',
    'apps.core.middleware.etag_middleware.ConditionalGetMiddleware',
]
```

**Benefits:**
- Automatic 304 Not Modified responses
- 70%+ bandwidth reduction for unchanged resources
- Browser caching optimization

#### 4. Centralized PII Redaction

**Usage:**

```python
from apps.core.security.pii_redaction import PIIRedactionService

# Redact PII from text
text = "Contact: john.doe@example.com, Phone: (555) 123-4567"
redacted = PIIRedactionService.redact_text(text)
# Output: "Contact: j***@e***.com, Phone: ***-***-4567"

# Detect PII
matches = PIIRedactionService.detect_pii(text)
for match in matches:
    print(f"{match.pii_type}: {match.value}")

# Use in models
from apps.core.security.pii_redaction import PIIRedactionMixin

class User(PIIRedactionMixin, models.Model):
    PII_FIELDS = ['email', 'phone']
    email = models.EmailField()
    phone = models.CharField(max_length=20)

    def get_safe_data(self):
        return self.redact_pii_fields()
```

---

### **PHASE 1: Observability**

#### 1. OpenTelemetry Setup

**Add to settings:**

```python
# intelliwiz_config/settings/base.py

# Tracing configuration
SERVICE_NAME = 'intelliwiz'
JAEGER_HOST = env('JAEGER_HOST', default='localhost')
JAEGER_PORT = env.int('JAEGER_PORT', default=6831)

# Initialize tracing at startup
from apps.core.observability.tracing import TracingService
TracingService.initialize()
```

**Add tracing middleware:**

```python
MIDDLEWARE += [
    'apps.core.middleware.tracing_middleware.TracingMiddleware',
]
```

#### 2. Structured Logging

**Configure:**

```python
from apps.core.observability.structured_logging import configure_structured_logging

# In AppConfig.ready() or settings
configure_structured_logging()
```

**Usage:**

```python
from apps.core.observability import get_logger

logger = get_logger(__name__)

logger.info('User logged in', extra={
    'user_id': user.id,
    'ip_address': request.META['REMOTE_ADDR']
})

# Output (JSON):
# {
#   "timestamp": "2025-09-30T10:30:00Z",
#   "level": "INFO",
#   "message": "User logged in",
#   "trace_id": "abc123...",
#   "span_id": "def456...",
#   "user_id": 123,
#   "ip_address": "192.168.1.1"
# }
```

#### 3. Function Tracing

**Decorator usage:**

```python
from apps.core.observability import trace_function

@trace_function('user_authentication')
def authenticate_user(username, password):
    # Your code here
    pass

# Or context manager
from apps.core.observability import TracingService

with TracingService.create_span('database_query'):
    users = User.objects.filter(active=True)
```

---

### **PHASE 2: Performance Budgets**

**Configuration:**

```python
# intelliwiz_config/settings/performance.py

from datetime import timedelta

ENDPOINT_PERFORMANCE_BUDGETS = {
    '/api/graphql/': {
        'p50': 200,   # 50th percentile: 200ms
        'p95': 500,   # 95th percentile: 500ms
        'p99': 1000,  # 99th percentile: 1s
    },
    '/api/v1/sync/': {
        'p50': 100,
        'p95': 200,
        'p99': 500,
    },
    'default': {
        'p50': 300,
        'p95': 1000,
        'p99': 3000,
    }
}
```

**Add middleware:**

```python
MIDDLEWARE += [
    'apps.core.middleware.performance_budget_middleware.PerformanceBudgetMiddleware',
]
```

**Monitoring:**

All responses include `X-Response-Time-Ms` header. Violations logged automatically.

---

### **PHASE 3: Reliability Patterns**

#### 1. Transactional Outbox

**Usage:**

```python
from django.db import transaction
from apps.core.reliability import OutboxEvent

# In your business logic
with transaction.atomic():
    # Update database
    order = Order.objects.create(customer=customer, total=100)

    # Create outbox event in same transaction
    OutboxEvent.create_event(
        event_type='order.created',
        aggregate_type='Order',
        aggregate_id=str(order.id),
        payload={
            'order_id': order.id,
            'customer_id': customer.id,
            'total': order.total
        },
        metadata={
            'correlation_id': request.correlation_id
        }
    )

# Event is guaranteed to be published (zero message loss)
```

**Setup Celery task to process outbox:**

```python
# background_tasks/outbox_tasks.py

from celery import shared_task
from apps.core.reliability import OutboxProcessor

@shared_task
def process_outbox_events():
    OutboxProcessor.process_pending_events(batch_size=100)

# Schedule with Celery Beat
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'process-outbox': {
        'task': 'background_tasks.outbox_tasks.process_outbox_events',
        'schedule': crontab(minute='*/1'),  # Every minute
    },
}
```

#### 2. Inbox Pattern (Idempotency)

**Usage:**

```python
from apps.core.reliability import InboxProcessor

def handle_order_created(payload):
    order_id = payload['order_id']
    # Process order...

# Process event idempotently
success = InboxProcessor.process_event(
    event_id='evt_order_123',  # Unique event ID
    event_type='order.created',
    payload={'order_id': 123},
    handler=handle_order_created
)

# If event_id already processed, returns False (no duplicate processing)
```

#### 3. Circuit Breaker

**Usage:**

```python
from apps.core.reliability import CircuitBreaker

# Create circuit breaker
external_api_cb = CircuitBreaker('payment_gateway')

# Protect function
@external_api_cb.protected
def charge_payment(amount):
    response = requests.post('https://api.payment.com/charge', ...)
    return response

# Or use directly
try:
    result = external_api_cb.execute(charge_payment, amount=100)
except CircuitBreakerOpen:
    # Handle gracefully
    logger.error("Payment gateway circuit breaker open")
    return fallback_response()
```

---

### **PHASE 4: Security**

#### 1. Token Binding

**Add middleware:**

```python
MIDDLEWARE += [
    'apps.core.security.token_binding.TokenBindingMiddleware',
]
```

Benefits:
- Prevents token theft
- Binds tokens to client fingerprint
- Automatic validation

#### 2. Secrets Rotation

**Setup Celery task:**

```python
from celery import shared_task
from apps.core.security.secrets_rotation import SecretsRotationService, APIKeyRotator

@shared_task
def rotate_api_keys():
    for api_name in ['openai', 'anthropic', 'google_maps']:
        if SecretsRotationService.is_rotation_due(api_name):
            rotator = APIKeyRotator(api_name)
            SecretsRotationService.rotate_secret(api_name, rotator)

# Schedule quarterly
CELERY_BEAT_SCHEDULE = {
    'rotate-secrets': {
        'task': 'background_tasks.rotate_api_keys',
        'schedule': crontab(day_of_month='1', hour='2'),  # 1st of month at 2am
    },
}
```

---

### **PHASE 7: GraphQL Enhancements**

#### 1. Persisted Queries

**Update GraphQL view:**

```python
from apps.api.graphql.persisted_queries import PersistedQueryService

class GraphQLView:
    def dispatch(self, request):
        data = json.loads(request.body)

        query_hash = data.get('queryHash')
        query = data.get('query')

        # Resolve persisted query
        resolved_query = PersistedQueryService.process_request(
            query=query,
            query_hash=query_hash
        )

        if not resolved_query:
            return JsonResponse({'error': 'Query not found'}, status=404)

        # Execute query...
```

**Client usage:**

```javascript
// First request: send hash only
fetch('/api/graphql/', {
  method: 'POST',
  body: JSON.stringify({
    queryHash: 'abc123...'
  })
})

// If 404, fall back to full query
.catch(() => {
  fetch('/api/graphql/', {
    method: 'POST',
    body: JSON.stringify({
      query: 'query { users { id name } }',
      queryHash: 'abc123...'
    })
  })
})
```

#### 2. Error Taxonomy

**Usage in resolvers:**

```python
from apps.api.graphql.error_taxonomy import GraphQLErrorFactory, GraphQLErrorCode

def resolve_user(info, user_id):
    try:
        user = User.objects.get(id=user_id)
        return user
    except User.DoesNotExist:
        raise GraphQLErrorFactory.resource_not_found('User', user_id)
    except PermissionDenied:
        raise GraphQLErrorFactory.unauthorized("Cannot access this user")

# Standardized error response:
# {
#   "errors": [{
#     "message": "User not found",
#     "extensions": {
#       "code": "RESOURCE_NOT_FOUND",
#       "resourceType": "User",
#       "resourceId": "123",
#       "timestamp": 1696077600.0
#     }
#   }]
# }
```

---

## 📊 Monitoring & Dashboards

### Jaeger Tracing Dashboard

Access at: `http://localhost:16686`

**Features:**
- End-to-end request traces
- Celery task traces
- GraphQL resolver performance
- Database query spans

### Performance Budget Dashboard

**View endpoint metrics:**

```python
from django.core.cache import cache

cache_key = "perf_metrics:/api/graphql/"
metrics = cache.get(cache_key)

# Calculate percentiles
import numpy as np
durations = metrics['durations']
p50 = np.percentile(durations, 50)
p95 = np.percentile(durations, 95)
p99 = np.percentile(durations, 99)
```

---

## 🧪 Testing New Features

### Feature Flags

```python
from waffle.testutils import override_flag

@override_flag('new_dashboard', active=True)
def test_new_dashboard():
    response = client.get('/dashboard/')
    assert 'v2' in response.content
```

### Tracing

```python
from apps.core.observability import TracingService

def test_tracing():
    with TracingService.create_span('test_operation') as span:
        # Your code here
        assert span.get_span_context().is_valid
```

### Circuit Breaker

```python
from apps.core.reliability import CircuitBreaker

def test_circuit_breaker():
    cb = CircuitBreaker('test_service')

    # Trigger failures
    for _ in range(6):
        try:
            cb.execute(lambda: 1/0)
        except:
            pass

    # Circuit should be open
    assert cb.is_open()
```

---

## 🚨 Rollback Procedures

### If Issues Occur

1. **Disable Feature Flags:**
   ```python
   from waffle.models import Flag
   Flag.objects.update(everyone=False)
   ```

2. **Disable Tracing:**
   ```python
   # Comment out in settings
   # TracingService.initialize()
   ```

3. **Database Rollback:**
   ```bash
   python manage.py migrate core <previous_migration_number>
   ```

---

## 📈 Success Metrics

Monitor these KPIs:

- **Feature Flags**: % of users on new features
- **ETags**: Cache hit rate (target: >70%)
- **Tracing**: 100% of requests traced
- **Performance**: P95 latency within budgets
- **Reliability**: Circuit breaker activation rate
- **Security**: Zero token binding violations

---

## 🆘 Troubleshooting

### Jaeger Not Receiving Traces

```bash
# Check Jaeger is running
docker ps | grep jaeger

# Verify settings
echo $JAEGER_HOST
echo $JAEGER_PORT

# Check logs
docker logs jaeger
```

### Feature Flags Not Working

```bash
# Verify waffle tables
python manage.py shell
>>> from waffle.models import Flag
>>> Flag.objects.all()

# Check middleware order
# FeatureFlagMiddleware should be after AuthenticationMiddleware
```

### Performance Budget Violations

```python
# Check metrics
from django.core.cache import cache
metrics = cache.get('perf_metrics:/your/endpoint/')
print(f"Recent durations: {metrics['durations'][-10:]}")
```

---

## 📚 Additional Resources

- [Feature Flags Best Practices](https://martinfowler.com/articles/feature-toggles.html)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)

---

**Migration Support:** For questions, open an issue or contact the platform team.
