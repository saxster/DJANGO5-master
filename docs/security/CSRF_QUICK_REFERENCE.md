# CSRF Protection Quick Reference

**Rule:** .claude/rules.md Rule #3 - Mandatory CSRF Protection
**Status:** ✅ 100% Compliant

---

## 🚨 When to Use What

### For AJAX/JSON Endpoints
```python
from apps.core.decorators import csrf_protect_ajax, rate_limit

@csrf_protect_ajax
@rate_limit(max_requests=50, window_seconds=300)
def my_api_endpoint(request):
    data = json.loads(request.body)
    return JsonResponse({'success': True})
```

### For HTMX Endpoints
```python
from apps.core.decorators import csrf_protect_htmx, rate_limit

@csrf_protect_htmx
@rate_limit(max_requests=30, window_seconds=300)
def htmx_action(request):
    return HttpResponse('<div>Updated</div>')
```

### For Class-Based Views
```python
from apps.core.decorators import csrf_protect_ajax, rate_limit
from django.utils.decorators import method_decorator

@method_decorator(csrf_protect_ajax, name='post')
@method_decorator(rate_limit(max_requests=20, window_seconds=300), name='post')
class MyAPIView(LoginRequiredMixin, View):
    def post(self, request):
        return JsonResponse({'success': True})
```

### For Monitoring Endpoints (Read-Only)
```python
from apps.core.decorators import require_monitoring_api_key

@method_decorator(require_monitoring_api_key, name='dispatch')
class MetricsView(View):
    """Requires API key authentication (Rule #3 alternative)."""
    def get(self, request):
        return JsonResponse({'metrics': data})
```

---

## ✅ Allowed Exemptions

**Only these files can use @csrf_exempt:**
1. `apps/core/health_checks.py` - Read-only health checks (documented)
2. `apps/core/views/csp_report.py` - Browser-generated CSP reports

**All exemptions MUST include Rule #3 compliance documentation in file header.**

---

## 🔧 Quick Commands

### Create Monitoring API Key
```bash
python manage.py create_monitoring_key \
  --name "Prometheus" \
  --system prometheus \
  --permissions health,metrics,performance
```

### Rotate Keys
```bash
python manage.py rotate_monitoring_keys --auto
```

### List Keys
```bash
python manage.py list_monitoring_keys --needs-rotation
```

### Run Security Tests
```bash
pytest -m security apps/core/tests/test_csrf_*.py -v
```

---

## 🚫 Common Mistakes

### ❌ DON'T
```python
@csrf_exempt  # NEVER on mutation endpoints
def my_post_view(request):
    pass
```

### ✅ DO
```python
@csrf_protect_ajax
@rate_limit(max_requests=50, window_seconds=300)
def my_post_view(request):
    pass
```

---

## 📝 Frontend Integration

### AJAX (Fetch)
```javascript
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

fetch('/api/endpoint/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken
    },
    body: JSON.stringify({data: 'value'})
});
```

### HTMX (Global Config)
```javascript
document.body.addEventListener('htmx:configRequest', (e) => {
    e.detail.headers['X-CSRFToken'] =
        document.querySelector('meta[name="csrf-token"]').content;
});
```

---

## 📚 Full Documentation

- **Complete Guide:** `docs/security/csrf-protection-guide.md`
- **Monitoring Setup:** `docs/security/monitoring-api-authentication.md`
- **Implementation Report:** `docs/security/CSRF_REMEDIATION_COMPLETE_REPORT.md`
- **Rules Reference:** `.claude/rules.md` Rule #3