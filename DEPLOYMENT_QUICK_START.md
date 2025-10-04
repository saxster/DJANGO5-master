# Multi-Tenant Security Deployment Quick Start

## 🚀 Quick Deployment (5 minutes)

### Step 1: Run Migrations

```bash
# Apply new security models
python manage.py migrate peoples

# Verify migrations
python manage.py showmigrations peoples | grep "0005_add_security_audit_models"
```

### Step 2: Restart Django

```bash
# Development
python manage.py runserver

# Production (with gunicorn)
sudo systemctl restart gunicorn
sudo systemctl restart celery-workers
```

### Step 3: Verify Tenant Routing

```bash
# Test tenant health
curl http://localhost:8000/admin/tenants/health/

# Expected: {"status": "healthy", "hostname": "...", "database": "..."}
```

### Step 4: Test Login Throttling

```bash
# Attempt login 6 times with wrong password
for i in {1..6}; do
  curl -X POST http://localhost:8000/login/ \
    -d "username=testuser&password=wrongpassword" \
    -c cookies.txt -b cookies.txt
  echo "\n--- Attempt $i ---\n"
done

# You should see throttling after 3-5 attempts
```

### Step 5: Access Admin Dashboard

```bash
# Navigate to admin panel
http://localhost:8000/admin/

# Check new security sections:
# - Login Attempt Logs
# - Account Lockouts
```

## ✅ Verification Checklist

- [ ] Migrations applied successfully
- [ ] Tenant health endpoint returns 200
- [ ] Login throttling blocks after N attempts
- [ ] Admin can view login attempt logs
- [ ] Admin can unlock accounts

## 🔧 Configuration (Optional)

### Custom Tenant Mappings

```bash
# Set environment variable
export TENANT_MAPPINGS='{
  "mysite.example.com": "mysite_db",
  "demo.example.com": "demo_db"
}'

# Restart Django to load new mappings
```

### Custom Throttle Limits

```python
# settings/security.py
from apps.peoples.services.login_throttling_service import ThrottleConfig

LOGIN_THROTTLE_IP_CONFIG = ThrottleConfig(
    max_attempts=10,
    window_seconds=600,
    lockout_duration_seconds=300
)
```

## 📊 Monitoring

### Key Metrics

```bash
# View recent login attempts
python manage.py shell
>>> from apps.peoples.models.security_models import LoginAttemptLog
>>> LoginAttemptLog.objects.filter(success=False).count()

# View active lockouts
>>> from apps.peoples.models.security_models import AccountLockout
>>> AccountLockout.objects.filter(is_active=True).count()
```

### Log Monitoring

```bash
# Watch security logs
tail -f logs/security.log | grep -E 'throttled|lockout'

# Watch authentication logs
tail -f logs/django.log | grep 'authentication'
```

## 🆘 Troubleshooting

### Tenant routing not working?

```bash
# Check middleware is installed
python manage.py shell
>>> from django.conf import settings
>>> 'apps.tenants.middlewares.TenantMiddleware' in settings.MIDDLEWARE
True
```

### Redis connection errors?

```bash
# Check Redis is running
redis-cli ping
# Expected: PONG

# Check Redis connection in Django
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')
>>> cache.get('test')
'value'
```

### Login always fails?

```bash
# Check if account is locked
python manage.py shell
>>> from apps.peoples.models.security_models import AccountLockout
>>> AccountLockout.objects.filter(username='your_username', is_active=True)

# Unlock manually if needed
>>> from apps.peoples.services.login_throttling_service import login_throttle_service
>>> login_throttle_service.record_successful_attempt('127.0.0.1', 'your_username')
```

## 🔒 Security Checklist

- [ ] All passwords use minimum 12 characters
- [ ] Redis uses authentication (requirepass)
- [ ] PostgreSQL uses SSL connections
- [ ] Django SECRET_KEY is rotated regularly
- [ ] ALLOWED_HOSTS is properly configured
- [ ] DEBUG = False in production
- [ ] Session cookies use HTTPS only
- [ ] CSRF protection enabled

## 📖 Full Documentation

See `MULTI_TENANT_AUTH_SECURITY_IMPLEMENTATION_SUMMARY.md` for complete details.
