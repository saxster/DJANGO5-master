# Error Response Sanitization Standards

**Purpose:** Standards for secure error response handling across all endpoints
**Addresses:** Issue #19 - Inconsistent Error Message Sanitization
**Compliance:** .claude/rules.md Rule #5 (No Debug Information in Production)

---

## 🎯 Core Principles

1. **Never expose internal details** - regardless of DEBUG setting
2. **Always include correlation IDs** - for debugging and tracking
3. **Use generic user-facing messages** - no stack traces or file paths
4. **Log full details server-side** - for debugging purposes
5. **Standardize error formats** - consistent structure across API/web

---

## 🔒 Security Requirements

### ❌ FORBIDDEN - Information Disclosure

**Never expose these in error responses:**

```python
{
    "error": {
        "stack_trace": "File '/app/views.py', line 123...",
        "exception_type": "DatabaseError",
        "database_host": "prod-db-001.internal",
        "sql_query": "SELECT * FROM users WHERE...",
        "file_path": "/Users/admin/project/app.py",
        "exception_details": "Connection refused at 10.0.0.1:5432"
    }
}
```

**Why this is dangerous:**
- Exposes internal architecture
- Reveals database structure
- Leaks server paths and IPs
- Aids attackers in reconnaissance

---

### ✅ REQUIRED - Secure Error Format

**API Error Response (JSON):**

```python
from apps.core.services.error_response_factory import ErrorResponseFactory

response = ErrorResponseFactory.create_api_error_response(
    error_code='VALIDATION_ERROR',
    message='Invalid input data provided',
    status_code=400,
    correlation_id=request.correlation_id,
    field_errors={
        'email': ['Invalid email format'],
        'phone': ['Phone number required']
    }
)

{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input data provided",
        "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "timestamp": "2025-09-27T10:30:00Z",
        "field_errors": {
            "email": ["Invalid email format"],
            "phone": ["Phone number required"]
        }
    }
}
```

**Web Error Response (HTML):**

```python
response = ErrorResponseFactory.create_web_error_response(
    request=request,
    error_code='PERMISSION_DENIED',
    message='You do not have permission to access this resource',
    status_code=403,
    correlation_id=request.correlation_id,
)

<div class="error-page">
    <h1>Access Denied</h1>
    <p>You do not have permission to access this resource</p>
    <p>Reference ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890</p>
    <p>Contact support@youtility.com for assistance</p>
</div>
```

---

## 📐 Standard Error Codes

### Client Errors (4xx)

| Code | HTTP Status | User Message | Use Case |
|------|-------------|--------------|----------|
| `VALIDATION_ERROR` | 400 | Invalid input data provided | Form/data validation |
| `AUTHENTICATION_REQUIRED` | 401 | Authentication required | Unauthenticated access |
| `PERMISSION_DENIED` | 403 | Access denied | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | 404 | Resource not found | Non-existent entity |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests | Rate limiting |

### Server Errors (5xx)

| Code | HTTP Status | User Message | Use Case |
|------|-------------|--------------|----------|
| `DATABASE_ERROR` | 500 | Unable to process request | Database failures |
| `INTERNAL_ERROR` | 500 | An unexpected error occurred | Unclassified errors |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable | Dependency failures |

---

## 🛠️ Implementation Patterns

### Pattern 1: View Error Handling

```python
from apps.core.services.error_response_factory import ErrorResponseFactory
from django.core.exceptions import ValidationError

class TicketCreateView(View):
    def post(self, request):
        try:
            ticket = self._create_ticket(request.POST)
            return JsonResponse({'success': True, 'ticket_id': ticket.id})

        except ValidationError as e:
            return ErrorResponseFactory.create_validation_error_response(
                field_errors={'form': [str(e)]},
                correlation_id=request.correlation_id,
                request_type='api',
            )

        except DatabaseError as e:
            logger.error(
                f"Ticket creation failed: {type(e).__name__}",
                extra={
                    'correlation_id': request.correlation_id,
                    'user_id': request.user.id,
                }
            )

            return ErrorResponseFactory.create_api_error_response(
                error_code='DATABASE_ERROR',
                status_code=500,
                correlation_id=request.correlation_id,
            )
```

### Pattern 2: Exception-Based Response

```python
def post(self, request):
    try:
        return self._process_request(request)

    except Exception as exception:
        logger.error(
            f"Request processing failed: {type(exception).__name__}",
            extra={
                'correlation_id': request.correlation_id,
                'exception_message': str(exception),
            },
            exc_info=True
        )

        return ErrorResponseFactory.from_exception(
            exception=exception,
            request_type='api',
            correlation_id=request.correlation_id,
        )
```

### Pattern 3: Web Form Error Handling

```python
def post(self, request):
    form = TicketForm(request.POST)

    if not form.is_valid():
        if request.META.get('HTTP_ACCEPT', '').startswith('application/json'):
            return ErrorResponseFactory.create_validation_error_response(
                field_errors=form.errors,
                correlation_id=request.correlation_id,
                request_type='api',
            )
        else:
            return render(request, 'ticket_form.html', {
                'form': form,
                'correlation_id': request.correlation_id,
            })
```

---

## 🔍 Correlation ID Workflow

### 1. Correlation ID Assignment

```python
class CorrelationIDMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.correlation_id = str(uuid.uuid4())
        return None

    def process_response(self, request, response):
        if hasattr(request, 'correlation_id'):
            response['X-Correlation-ID'] = request.correlation_id
        return response
```

### 2. Error Logging with Correlation ID

```python
logger.error(
    "Operation failed",
    extra={
        'correlation_id': request.correlation_id,
        'user_id': request.user.id,
        'operation': 'create_ticket',
    },
    exc_info=True
)
```

### 3. User Support Workflow

1. User reports error with correlation ID
2. Support looks up correlation ID in logs
3. Full error details available server-side
4. No sensitive data exposed to user

---

## 🧪 Testing Requirements

### Test: No Information Disclosure

```python
@pytest.mark.security
@override_settings(DEBUG=True)
def test_no_debug_info_even_when_debug_true(self):
    """CRITICAL: Verify no debug info exposed with DEBUG=True."""
    exception = DatabaseError("Connection to 'prod_db' failed")

    response = ErrorResponseFactory.from_exception(
        exception=exception,
        request_type='api',
    )

    content = json.loads(response.content)

    self.assertNotIn('prod_db', str(content))
    self.assertNotIn('traceback', str(content))
    self.assertNotIn('exception_type', str(content))
```

### Test: Correlation ID Presence

```python
def test_all_errors_include_correlation_id(self):
    """Verify all error responses include correlation ID."""
    response = ErrorResponseFactory.create_api_error_response(
        error_code='VALIDATION_ERROR',
    )

    content = json.loads(response.content)
    self.assertIn('correlation_id', content['error'])
    self.assertEqual(len(content['error']['correlation_id']), 36)
```

---

## 🔧 Monitoring and Compliance

### Audit Error Sanitization

```bash
python manage.py audit_error_sanitization
python manage.py audit_error_sanitization --app peoples
python manage.py audit_error_sanitization --critical-only
python manage.py audit_error_sanitization --export report.json
```

### Monitor Compliance

```bash
python manage.py audit_error_sanitization --check-compliance
```

**Compliance Targets:**
- 100% of errors include correlation IDs
- 0 information disclosure violations
- 100% use of ErrorResponseFactory for new code

---

## 📋 Developer Checklist

Before merging any error handling code:

- [ ] All error responses use `ErrorResponseFactory`
- [ ] Correlation IDs included in all error responses
- [ ] No DEBUG-dependent information exposure
- [ ] Generic messages for users, detailed logs for debugging
- [ ] Field-specific validation errors when applicable
- [ ] Proper exception logging with `exc_info=True`
- [ ] Tests verify no information disclosure
- [ ] Error responses follow standard format

---

## 🚨 Common Violations and Fixes

### Violation 1: DEBUG-Dependent Exposure

❌ **BAD:**
```python
if settings.DEBUG:
    response['debug'] = {
        'exception_type': type(e).__name__,
        'stack_trace': traceback.format_exc(),
    }
```

✅ **GOOD:**
```python
logger.error(
    f"Error occurred: {type(e).__name__}",
    extra={'correlation_id': correlation_id},
    exc_info=True
)
```

### Violation 2: Missing Correlation ID

❌ **BAD:**
```python
return JsonResponse({
    'error': 'Something went wrong'
}, status=500)
```

✅ **GOOD:**
```python
return ErrorResponseFactory.create_api_error_response(
    error_code='INTERNAL_ERROR',
    correlation_id=request.correlation_id,
)
```

### Violation 3: Raw Exception in Response

❌ **BAD:**
```python
except Exception as e:
    return JsonResponse({
        'error': str(e)
    }, status=500)
```

✅ **GOOD:**
```python
except ValidationError as e:
    logger.warning(
        f"Validation failed: {type(e).__name__}",
        extra={'correlation_id': request.correlation_id}
    )

    return ErrorResponseFactory.create_api_error_response(
        error_code='VALIDATION_ERROR',
        correlation_id=request.correlation_id,
    )
```

---

## 📚 Additional Resources

- `.claude/rules.md` Rule #5: No Debug Information in Production
- `.claude/rules.md` Rule #11: Exception Handling Specificity
- `docs/EXCEPTION_HANDLING_PATTERNS.md`: Exception handling guide
- `apps/core/services/error_response_factory.py`: Implementation reference
- `apps/core/middleware/error_response_validation.py`: Validation middleware