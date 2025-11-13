# Security Tests - Quick Reference

**Location**: `apps/core/tests/`
**Created**: November 12, 2025
**Test Count**: 34 security tests across 13 test classes

---

## Quick Start

### Run All Security Tests

```bash
# Set up environment
export SECRET_KEY="test-secret-key-$(date +%s)"
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.test

# Run all security tests
python -m pytest -m security -v --tb=short
```

### Run Specific Test Suites

```bash
# Multi-tenancy isolation tests (15 tests)
python -m pytest apps/core/tests/test_multi_tenancy_security.py -v

# CSRF protection tests (19 tests)
python -m pytest apps/core/tests/test_csrf_state_changing_endpoints.py -v
```

---

## Test Files

### 1. `test_multi_tenancy_security.py` (15 tests)

**Purpose**: Validate cross-tenant access prevention (IDOR vulnerabilities)

**Test Classes**:
- `MultiTenantJournalSecurityTestCase` - Journal entry isolation
- `MultiTenantWellnessSecurityTestCase` - Wellness content isolation
- `MultiTenantAttendanceSecurityTestCase` - Attendance record isolation
- `MultiTenantTicketSecurityTestCase` - Helpdesk ticket isolation
- `AdminCrossTenantRestrictionsTestCase` - Staff user boundaries
- `TenantEnumerationPreventionTestCase` - Enumeration attack prevention

**Key Validations**:
- ✅ User from Tenant A cannot access Tenant B's data
- ✅ Returns 404 (not 403) to prevent resource enumeration
- ✅ Staff users respect tenant boundaries (unless superuser)
- ✅ Error messages don't leak tenant information

### 2. `test_csrf_state_changing_endpoints.py` (19 tests)

**Purpose**: Validate CSRF protection on all state-changing API endpoints

**Test Classes**:
- `CSRFProtectionJournalEndpointsTestCase` - Journal CRUD operations
- `CSRFProtectionTicketEndpointsTestCase` - Ticket CRUD operations
- `CSRFProtectionWellnessEndpointsTestCase` - Wellness content management
- `CSRFTokenValidationTestCase` - Token validation mechanisms
- `CSRFExemptEndpointsTestCase` - Alternative authentication validation
- `CSRFProtectionIntegrationTestCase` - Multi-endpoint integration
- `CSRFHeaderMiddlewareIntegrationTestCase` - Middleware integration

**Key Validations**:
- ✅ POST/PUT/DELETE require CSRF tokens
- ✅ Invalid/stolen tokens rejected
- ✅ CSRF-exempt endpoints have documented alternative auth
- ✅ Token rotation works correctly

---

## Test Execution Examples

### Run Single Test Class

```bash
# Multi-tenancy: Journal entries
python -m pytest apps/core/tests/test_multi_tenancy_security.py::MultiTenantJournalSecurityTestCase -v

# CSRF: Token validation
python -m pytest apps/core/tests/test_csrf_state_changing_endpoints.py::CSRFTokenValidationTestCase -v
```

### Run Single Test Case

```bash
# Test cross-tenant journal access
python -m pytest apps/core/tests/test_multi_tenancy_security.py::MultiTenantJournalSecurityTestCase::test_cannot_access_other_tenant_journal_entry_via_api -v

# Test CSRF on journal creation
python -m pytest apps/core/tests/test_csrf_state_changing_endpoints.py::CSRFProtectionJournalEndpointsTestCase::test_journal_entry_creation_requires_csrf_token -v
```

### Run with Coverage

```bash
# Generate coverage report
python -m pytest apps/core/tests/test_multi_tenancy_security.py \
  apps/core/tests/test_csrf_state_changing_endpoints.py \
  --cov=apps --cov-report=html:coverage_reports/security \
  --tb=short -v

# View coverage report
open coverage_reports/security/index.html
```

---

## Expected Test Results

### When Tests PASS (Security Working Correctly)

**Multi-Tenancy Tests**:
- ✅ Cross-tenant API requests return 404
- ✅ ORM queries filtered by tenant
- ✅ List endpoints show only own tenant's data
- ✅ Error messages don't leak tenant info

**CSRF Tests**:
- ✅ State-changing operations without token return 403
- ✅ Operations with valid token succeed (200/201)
- ✅ Invalid tokens rejected
- ✅ CSRF-exempt endpoints require alternative auth

### When Tests FAIL (Security Issues Detected)

**Multi-Tenancy Failures**:
- ❌ Cross-tenant access returns 200 (IDOR vulnerability!)
- ❌ Cross-tenant access returns 403 (enumeration vulnerability!)
- ❌ List shows other tenant's data (filter bypass!)
- ❌ Staff users can cross tenants (privilege escalation!)

**CSRF Failures**:
- ❌ State-changing operation succeeds without token (CSRF vulnerability!)
- ❌ Invalid token accepted (weak validation!)
- ❌ CSRF-exempt endpoint has no alternative auth (security gap!)

---

## Prerequisites

### Environment Variables

```bash
# Required
export SECRET_KEY="your-secret-key-here"
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.test

# Optional (for full test coverage)
export DATABASE_URL="postgresql://user:pass@localhost/test_db"
export REDIS_URL="redis://localhost:6379/1"
```

### Services

```bash
# Start Redis (required for journal rate limiting)
redis-server

# Start PostgreSQL (required for database tests)
# Ensure test database exists
```

### Python Dependencies

```bash
# Install test dependencies
pip install -r requirements/base-macos.txt  # or base-linux.txt
pip install pytest pytest-django pytest-cov
```

---

## Troubleshooting

### Import Errors

**Error**: `ImportError: cannot import name 'JournalEntry'`

**Fix**:
```bash
# Ensure Django settings module is set
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.test

# Verify all dependencies installed
pip install -r requirements/base-macos.txt
```

### Database Errors

**Error**: `django.db.utils.OperationalError: database "test_intelliwiz" does not exist`

**Fix**:
```bash
# Create test database
createdb test_intelliwiz

# Or let Django create it
python manage.py test --keepdb
```

### Redis Connection Errors

**Error**: `redis.exceptions.ConnectionError: Error connecting to Redis`

**Fix**:
```bash
# Start Redis server
redis-server

# Or skip Redis-dependent tests
pytest -m "security and not redis"
```

### CSRF Middleware Not Found

**Error**: `AttributeError: module 'apps.core.xss_protection' has no attribute 'CSRFHeaderMiddleware'`

**Fix**: This is expected if middleware was renamed/moved. Update test imports:
```python
# Check current middleware location
grep -r "CSRFHeaderMiddleware" apps/core/
```

---

## Updating Tests

### When to Add New Tests

**Multi-Tenancy Tests**:
- ✅ New TenantAwareModel added
- ✅ New API endpoint accessing tenant data
- ✅ New business domain (like journal, wellness, tickets)

**CSRF Tests**:
- ✅ New POST/PUT/DELETE endpoint added
- ✅ New @csrf_exempt decorator used
- ✅ New authentication method added

### How to Add Tests

**Example: New Tenant-Aware Model**

```python
# apps/core/tests/test_multi_tenancy_security.py

@pytest.mark.security
class MultiTenantNewFeatureSecurityTestCase(TestCase):
    """Test multi-tenant isolation for new feature"""

    def setUp(self):
        # Create two tenants
        self.tenant_a = Tenant.objects.create(...)
        self.tenant_b = Tenant.objects.create(...)

        # Create users
        self.user_a = User.objects.create_user(...)
        self.user_b = User.objects.create_user(...)

        # Create test data
        self.feature_a = NewFeature.objects.create(
            tenant=self.tenant_a,
            owner=self.user_a,
            ...
        )

    def test_cannot_access_other_tenant_feature(self):
        """User from Tenant B cannot access Tenant A's feature"""
        client = APIClient()
        client.force_authenticate(user=self.user_b)

        response = client.get(f'/api/features/{self.feature_a.id}/')

        self.assertEqual(
            response.status_code,
            404,
            "Cross-tenant feature access should return 404"
        )
```

**Example: New State-Changing Endpoint**

```python
# apps/core/tests/test_csrf_state_changing_endpoints.py

@pytest.mark.security
class CSRFProtectionNewFeatureEndpointsTestCase(TestCase):
    """Test CSRF protection for new feature endpoints"""

    def setUp(self):
        self.user = User.objects.create_user(...)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)

    def test_feature_creation_requires_csrf_token(self):
        """POST to create feature should require CSRF token"""
        response = self.client.post('/api/features/', {
            'name': 'Test Feature',
            'description': 'Test'
        })

        self.assertEqual(
            response.status_code,
            403,
            "Feature creation without CSRF token should be rejected"
        )
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/security-tests.yml
name: Security Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  security-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements/base-linux.txt
          pip install pytest pytest-django pytest-cov

      - name: Run security tests
        env:
          SECRET_KEY: ${{ secrets.TEST_SECRET_KEY }}
          DJANGO_SETTINGS_MODULE: intelliwiz_config.settings.test
          DATABASE_URL: postgresql://postgres:postgres@localhost/test_db
          REDIS_URL: redis://localhost:6379/1
        run: |
          pytest -m security --tb=short -v --cov=apps \
            --cov-report=xml --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: security
```

---

## Test Maintenance Checklist

### Monthly Review

- [ ] Verify all state-changing endpoints have CSRF tests
- [ ] Verify all tenant-aware models have isolation tests
- [ ] Check for new @csrf_exempt decorators (require documentation)
- [ ] Review test failures in CI/CD

### Quarterly Audit

- [ ] Run full security test suite
- [ ] Review coverage report (target: 90%+ for security-critical code)
- [ ] Update tests for new API endpoints
- [ ] Validate tenant enumeration prevention still works

### Pre-Release Checklist

- [ ] All security tests pass
- [ ] No new @csrf_exempt without alternative auth
- [ ] No cross-tenant access vulnerabilities
- [ ] Error messages don't leak tenant information

---

## Resources

### Documentation

- **Full Report**: `/SECURITY_TESTS_IMPLEMENTATION_REPORT.md`
- **Security Rules**: `/.claude/rules.md`
- **Multi-Tenancy Guide**: `/apps/tenants/QUICK_REFERENCE.md`

### Related Tests

- `test_csrf_protection.py` - CSRF middleware tests
- `test_secure_file_download_permissions.py` - File access security
- `test_tenant_isolation_comprehensive.py` - Tenant isolation tests

### OWASP References

- [API Security Top 10](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)
- [CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Authorization Testing](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/05-Authorization_Testing/)

---

**Last Updated**: November 12, 2025
**Maintainer**: Security Team
**Review Frequency**: Monthly
