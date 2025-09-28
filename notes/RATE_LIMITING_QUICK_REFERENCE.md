# Rate Limiting Quick Reference

**Version:** 1.0.0
**Last Updated:** 2025-09-27

## Quick Commands

### Testing
```bash
# Run all rate limiting tests
python run_rate_limiting_tests.py

# Specific test suite
python -m pytest apps/core/tests/test_rate_limiting_comprehensive.py -v

# Penetration tests only
python -m pytest apps/core/tests/test_rate_limiting_penetration.py -v -m penetration

# Security tests
python -m pytest -m security -k rate_limit -v
```

### Monitoring
```bash
# Access dashboard (requires staff login)
http://localhost:8000/security/rate-limiting/dashboard/

# Generate security report
python manage.py rate_limit_report

# Last 24 hours JSON export
python manage.py rate_limit_report --hours=24 --export=json

# Cleanup old data
python manage.py rate_limit_cleanup --days=90
python manage.py rate_limit_cleanup --dry-run  # Preview only
```

### Database Operations
```python
# Django shell quick queries
python manage.py shell

# View recent violations
from apps.core.models.rate_limiting import RateLimitViolationLog
RateLimitViolationLog.objects.order_by('-timestamp')[:10]

# Check blocked IPs
from apps.core.models.rate_limiting import RateLimitBlockedIP
RateLimitBlockedIP.objects.filter(is_active=True)

# Unblock an IP
blocked = RateLimitBlockedIP.objects.get(ip_address='x.x.x.x')
blocked.is_active = False
blocked.save()

# Add trusted IP
from apps.core.models.rate_limiting import RateLimitTrustedIP
RateLimitTrustedIP.objects.create(
    ip_address='192.168.1.100',
    description='CI/CD Server',
    is_active=True
)

# Clear cache
from django.core.cache import cache
cache.delete('trusted_ips_set')
```

## Rate Limits Reference

| Endpoint Type | Limit | Window | Use Case |
|--------------|-------|--------|----------|
| `/login/` | 5 | 5 min | Authentication |
| `/admin/` | 10 | 15 min | Admin panel |
| `/api/` | 100 | 1 hour | REST API |
| `/graphql/` | 100 | 5 min | GraphQL queries |
| `/reset-password/` | 5 | 5 min | Password reset |

## Exponential Backoff Schedule

| Violations | Backoff | Cumulative Time |
|-----------|---------|-----------------|
| 1 | 2 min | 2 min |
| 2 | 4 min | 6 min |
| 3 | 8 min | 14 min |
| 5 | 32 min | ~1 hour |
| 10 | 24 hours | AUTO-BLOCK |

## Emergency Procedures

### Disable Rate Limiting (Emergency Only)
```python
# settings override
ENABLE_RATE_LIMITING = False
```
**Restart required**

### Unblock All IPs (Emergency Only)
```python
python manage.py shell
>>> from apps.core.models.rate_limiting import RateLimitBlockedIP
>>> RateLimitBlockedIP.objects.update(is_active=False)
>>> from django.core.cache import cache
>>> cache.clear()
```

### Check if Rate Limiting is Active
```bash
curl -I http://localhost:8000/login/
# Should see X-RateLimit-* headers after first request
```

## Common Issues

### Issue: Legitimate user blocked
**Solution:** Add to trusted IPs or unblock via dashboard

### Issue: Rate limiting not working
**Check:**
1. `ENABLE_RATE_LIMITING = True` in settings
2. Middleware registered in `MIDDLEWARE` list
3. Redis running: `redis-cli ping`
4. Check logs: `grep "rate limit" logs/security.log`

### Issue: Too many false positives
**Solutions:**
1. Increase limits for endpoint type
2. Add shared IPs to trusted list
3. Review violation patterns in dashboard

## Architecture

```
Request → CorrelationID → PathRateLimit → GraphQLRateLimit → Security → Auth → App
                             ↓                  ↓
                          Cache (Redis)      Database
                             ↓                  ↓
                       Monitoring → Dashboard
```

## Key Files

- Middleware: `apps/core/middleware/path_based_rate_limiting.py`
- Models: `apps/core/models/rate_limiting.py`
- Views: `apps/core/views/rate_limit_monitoring_views.py`
- Settings: `intelliwiz_config/settings/security/rate_limiting.py`
- Tests: `apps/core/tests/test_rate_limiting_*.py`
- Docs: `docs/security/rate-limiting-architecture.md`

## Support

**Documentation:** `docs/security/rate-limiting-architecture.md`
**Dashboard:** `/security/rate-limiting/dashboard/`
**Logs:** `logs/security.log` (search: "Rate limit")
**Test Runner:** `python run_rate_limiting_tests.py`