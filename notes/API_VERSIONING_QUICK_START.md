# API Versioning Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### 1. Run Migrations
```bash
python manage.py migrate core
```

### 2. Verify Installation
```bash
# Check v2 status endpoint
curl http://localhost:8000/api/v2/status/

# Should return:
{
  "version": "v2",
  "status": "planned",
  "current_stable": "v1",
  ...
}
```

### 3. Access Dashboard
Navigate to: `http://localhost:8000/admin/api/lifecycle/`
- View deprecated endpoints
- See migration progress
- Monitor sunset warnings

---

## 📊 Quick Commands

```bash
# View all deprecated endpoints
python manage.py api_deprecation_report

# Check specific endpoint usage
python manage.py api_usage_stats --endpoint /api/v1/people/ --days 30

# Update statuses (run daily via cron)
python manage.py api_update_deprecation_status
```

---

## 🔧 Adding a Deprecation

### Via Django Admin
1. Go to `/admin/core/apideprecation/add/`
2. Fill form and save

### Via Code
```python
from apps.core.models.api_deprecation import APIDeprecation
from django.utils import timezone
from datetime import timedelta

APIDeprecation.objects.create(
    endpoint_pattern='/api/v1/old-endpoint/',
    api_type='rest',
    version_deprecated='v1.5',
    version_removed='v2.0',
    sunset_date=timezone.now() + timedelta(days=90),
    status='deprecated',
    replacement_endpoint='/api/v2/new-endpoint/',
    migration_url='/docs/migrations/endpoint-v2/',
    deprecation_reason='Performance improvements',
    notify_on_usage=True
)
```

---

## 📖 Response Headers

When calling a deprecated endpoint:

```bash
curl -v http://localhost:8000/api/v1/deprecated-endpoint/

# Response headers:
Deprecation: @1727467200
Sunset: Mon, 30 Jun 2026 23:59:59 GMT
Warning: 299 - "Deprecated API. Use /api/v2/new-endpoint instead."
Link: </docs/migrations/endpoint-v2>; rel="deprecation"
X-Deprecated-Replacement: /api/v2/new-endpoint
```

---

## 📚 Documentation

- **Policy**: `/docs/api-lifecycle-policy.md`
- **Compatibility**: `/docs/api-version-compatibility-matrix.md`
- **Migrations**: `/docs/api-migrations/{feature}-v2.md`
- **Full Details**: `API_VERSIONING_IMPLEMENTATION_COMPLETE.md`

---

## ✅ Compliance

All code follows .claude/rules.md:
- ✅ Rule #6: Settings < 200 lines
- ✅ Rule #7: Models < 150 lines
- ✅ Rule #8: View methods < 30 lines
- ✅ Rule #11: Specific exceptions
- ✅ Rule #15: No sensitive data logging
- ✅ RFC 9745: Deprecation header
- ✅ RFC 8594: Sunset header

---

**Questions?** See full documentation in `API_VERSIONING_IMPLEMENTATION_COMPLETE.md`