# ADR 004: Test Coverage Requirements

**Status:** Accepted

**Date:** 2025-11-04

**Deciders:** Development Team, QA Team, Architecture Review Board

**Related:**
- `.claude/rules.md` - Code Quality Rules
- `pytest.ini` - Test configuration
- CI/CD Pipeline - Coverage enforcement

---

## Context

The codebase had inconsistent test coverage, with some apps at 90%+ coverage and others below 40%. This led to:

1. **Production Bugs:**
   - Untested code paths causing runtime errors
   - Regression bugs in refactored code
   - Security vulnerabilities in untested logic

2. **Confidence Issues:**
   - Fear of refactoring due to lack of tests
   - Slow development (manual testing required)
   - Difficult to verify fixes

3. **Maintenance Burden:**
   - Bug fixes without regression tests
   - Changes breaking unrelated features
   - No clear contracts between components

### Coverage Analysis (Pre-ADR)

| App | Coverage | Issues |
|-----|----------|--------|
| `core` | 92% | ✅ Well tested |
| `peoples` | 85% | ✅ Good coverage |
| `attendance` | 78% | ⚠️ Needs improvement |
| `activity` | 65% | ❌ Insufficient |
| `noc` | 45% | ❌ Critical gaps |
| `y_helpdesk` | 38% | ❌ Urgent |

---

## Decision

**We enforce minimum test coverage requirements based on app criticality.**

### Coverage Targets

| App Type | Minimum Coverage | Rationale |
|----------|-----------------|-----------|
| **Security-Critical** | 90% | Authentication, encryption, permissions |
| **Business-Critical** | 85% | Core operations, data integrity |
| **User-Facing** | 80% | Views, APIs, forms |
| **Supporting** | 75% | Utilities, helpers |
| **Experimental** | 70% | Prototypes, POCs |

### App Classifications

**Security-Critical (90%):**
- `apps.core` (security, encryption, authentication)
- `apps.peoples` (user management, permissions)
- `apps.tenants` (multi-tenancy isolation)

**Business-Critical (85%):**
- `apps.attendance` (time tracking)
- `apps.activity` (work orders)
- `apps.scheduler` (scheduling)
- `apps.y_helpdesk` (ticketing)

**User-Facing (80%):**
- `apps.reports` (analytics)
- `apps.inventory` (asset management)
- `apps.noc` (monitoring dashboards)

**Supporting (75%):**
- `apps.ai_testing` (test automation)
- `apps.ml_training` (ML dataset management)
- `apps.wellness` (content delivery)

**Experimental (70%):**
- `apps.journal` (mobile app backend)
- New features in development

### Enforcement

```ini
# pytest.ini
[pytest]
addopts =
    --cov=apps
    --cov-report=html:coverage_reports/html
    --cov-report=term-missing
    --cov-fail-under=80  # Default global minimum
```

```yaml
# .github/workflows/ci.yml
- name: Run Tests with Coverage
  run: |
    pytest --cov=apps --cov-fail-under=80
    # Per-app coverage checked separately
```

---

## Consequences

### Positive

1. **Quality Assurance:**
   - ✅ Catch bugs before production
   - ✅ Confidence in refactoring
   - ✅ Regression prevention
   - ✅ Clear contracts between components

2. **Development Speed:**
   - ✅ Faster debugging (tests pinpoint issues)
   - ✅ Safe to refactor
   - ✅ Onboarding easier (tests as documentation)

3. **Security:**
   - ✅ Test all code paths in security modules
   - ✅ Verify authentication/authorization
   - ✅ Validate input sanitization

4. **Maintainability:**
   - ✅ Living documentation of behavior
   - ✅ Safe to upgrade dependencies
   - ✅ Verify bug fixes don't regress

### Negative

1. **Time Investment:**
   - ❌ Writing tests takes time
   - ❌ Initial backfill for existing code
   - ❌ Maintenance overhead

2. **False Confidence:**
   - ❌ High coverage doesn't guarantee quality
   - ❌ Can encourage shallow tests
   - ❌ May miss edge cases

3. **CI/CD Slowdown:**
   - ❌ More tests = longer CI runs
   - ❌ Flaky tests block deployments

### Mitigation Strategies

1. **For Time Investment:**
   - Test new code as it's written (TDD)
   - Incremental backfill (don't stop development)
   - Focus on critical paths first

2. **For False Confidence:**
   - Code review validates test quality
   - Require edge case tests
   - Mutation testing to verify test effectiveness

3. **For CI/CD Slowdown:**
   - Parallel test execution
   - Smart test selection (only affected tests)
   - Fast unit tests, slower integration tests

---

## Test Strategy

### Test Pyramid

```
         ┌────────────────┐
         │   E2E Tests    │ 5% - Full user flows
         │   (Selenium)   │
         ├────────────────┤
         │ Integration    │ 25% - Multiple components
         │   Tests        │
         ├────────────────┤
         │  Unit Tests    │ 70% - Individual functions
         │  (Fast!)       │
         └────────────────┘
```

### Coverage Requirements by Test Type

| Test Type | Target | Focus |
|-----------|--------|-------|
| Unit Tests | 70% of lines | Business logic, utilities |
| Integration Tests | 20% of lines | Component interactions |
| E2E Tests | 5% of lines | Critical user workflows |
| Edge Cases | 5% of lines | Error handling, boundaries |

### What to Test

**Must Test (Required for Coverage):**
- ✅ Business logic in services
- ✅ Model validation and constraints
- ✅ Form validation
- ✅ API endpoints (inputs, outputs, errors)
- ✅ Utility functions
- ✅ Security checks (permissions, authentication)
- ✅ Database queries (correctness, performance)

**Should Test (Best Practice):**
- ✅ View logic (if not trivial)
- ✅ Signal handlers
- ✅ Custom middleware
- ✅ Management commands
- ✅ Celery tasks

**Can Skip (Low Value):**
- ⚠️ Django framework code (already tested)
- ⚠️ Simple property getters/setters
- ⚠️ Trivial constructors
- ⚠️ Auto-generated migrations

---

## Implementation Patterns

### Pattern 1: Unit Test (Fast)

```python
# apps/attendance/tests/test_services.py
import pytest
from apps.attendance.services.geofence_service import GeofenceService

class TestGeofenceService:
    """Unit tests for geofence validation"""

    def test_is_within_geofence_when_inside(self):
        service = GeofenceService()
        is_within, distance = service.is_within_geofence(
            latitude=40.7128,
            longitude=-74.0060,
            post_id=1
        )
        assert is_within is True
        assert distance < 100  # meters

    def test_is_within_geofence_when_outside(self):
        service = GeofenceService()
        is_within, distance = service.is_within_geofence(
            latitude=0,
            longitude=0,
            post_id=1
        )
        assert is_within is False
        assert distance > 1000

    def test_invalid_coordinates_raises_validation_error(self):
        service = GeofenceService()
        with pytest.raises(ValidationError):
            service.is_within_geofence(latitude=200, longitude=0, post_id=1)
```

### Pattern 2: Integration Test

```python
# apps/attendance/tests/test_integration.py
import pytest
from django.test import TestCase
from apps.attendance.models import PeopleEventlog, Post
from apps.attendance.services.attendance_service import AttendanceService

@pytest.mark.django_db
class TestAttendanceIntegration(TestCase):
    """Integration tests for attendance workflows"""

    def setUp(self):
        self.user = People.objects.create(username='test')
        self.post = Post.objects.create(name='Test Post')

    def test_check_in_creates_event_and_updates_post(self):
        service = AttendanceService()
        event = service.check_in(
            user_id=self.user.id,
            post_id=self.post.id,
            geolocation={'lat': 0, 'lng': 0}
        )

        # Verify event created
        assert PeopleEventlog.objects.filter(id=event.id).exists()

        # Verify post updated
        self.post.refresh_from_db()
        assert self.post.last_check_in_time is not None
```

### Pattern 3: API Test

```python
# apps/api/v2/tests/test_attendance_api.py
from rest_framework.test import APITestCase
from rest_framework import status

class TestAttendanceAPI(APITestCase):
    """Test REST API endpoints"""

    def test_check_in_endpoint_success(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v2/attendance/check-in/', {
            'post_id': self.post.id,
            'latitude': 40.7128,
            'longitude': -74.0060,
        })
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True

    def test_check_in_endpoint_unauthorized(self):
        response = self.client.post('/api/v2/attendance/check-in/', {})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_check_in_endpoint_invalid_geofence(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/v2/attendance/check-in/', {
            'post_id': self.post.id,
            'latitude': 0,  # Outside geofence
            'longitude': 0,
        })
        assert response.status_code == status.HTTP_400_BAD_REQUEST
```

### Pattern 4: Edge Case Tests

```python
# apps/attendance/tests/test_edge_cases.py
import pytest

class TestAttendanceEdgeCases:
    """Test boundary conditions and error handling"""

    def test_concurrent_check_ins_same_user(self):
        """Verify race condition handling"""
        # Test concurrent check-ins don't create duplicates
        pass

    def test_check_in_at_exactly_midnight(self):
        """Verify date boundary handling"""
        pass

    def test_check_in_with_gps_precision_edge(self):
        """Verify geofence boundary (exactly on border)"""
        pass

    def test_check_in_after_post_deleted(self):
        """Verify foreign key constraint handling"""
        pass
```

---

## Coverage Measurement

### Running Coverage Reports

```bash
# Full coverage report
pytest --cov=apps --cov-report=html:coverage_reports/html

# Per-app coverage
pytest apps/attendance/tests/ --cov=apps.attendance --cov-report=term-missing

# Show uncovered lines
pytest --cov=apps --cov-report=term-missing

# Coverage badge (for README)
pytest --cov=apps --cov-report=json
coverage-badge -o coverage.svg -f
```

### Interpreting Coverage Reports

```
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
apps/attendance/services.py          100     10    90%   45-48, 92-95
apps/attendance/models.py            150      5    97%   120-124
apps/attendance/views.py              75     20    73%   25-30, 45-55
---------------------------------------------------------------
TOTAL                                325     35    89%
```

**Focus on:**
- **Missing lines** - What's not tested?
- **Low coverage files** - Which files need attention?
- **Critical paths** - Are security/business-critical paths covered?

---

## Coverage Enforcement

### Pre-Commit Hook

```bash
# .githooks/check-coverage.sh
#!/bin/bash
echo "Running tests with coverage check..."

pytest --cov=apps --cov-fail-under=80 --tb=short

if [ $? -ne 0 ]; then
    echo "❌ Test coverage below 80%"
    echo "Run: pytest --cov=apps --cov-report=term-missing"
    exit 1
fi

echo "✅ Coverage requirements met"
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci.yml
- name: Run Tests and Check Coverage
  run: |
    pytest --cov=apps --cov-fail-under=80 --cov-report=xml

- name: Upload Coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
    flags: unittests
    fail_ci_if_error: true
```

### Per-App Enforcement

```bash
# scripts/check_app_coverage.sh
#!/bin/bash

# Security-critical apps (90%)
pytest apps/core/tests/ --cov=apps.core --cov-fail-under=90
pytest apps/peoples/tests/ --cov=apps.peoples --cov-fail-under=90

# Business-critical apps (85%)
pytest apps/attendance/tests/ --cov=apps.attendance --cov-fail-under=85
pytest apps/activity/tests/ --cov=apps.activity --cov-fail-under=85

# User-facing apps (80%)
pytest apps/reports/tests/ --cov=apps.reports --cov-fail-under=80
```

---

## Backfill Strategy

### Prioritization

1. **Phase 1: Security-Critical (Immediate)**
   - `apps.core` → 90%
   - `apps.peoples` → 90%
   - Timeline: 2 weeks

2. **Phase 2: Business-Critical (High Priority)**
   - `apps.attendance` → 85%
   - `apps.activity` → 85%
   - Timeline: 4 weeks

3. **Phase 3: User-Facing (Medium Priority)**
   - `apps.reports` → 80%
   - `apps.noc` → 80%
   - Timeline: 6 weeks

4. **Phase 4: Supporting (Lower Priority)**
   - Remaining apps → 75%
   - Timeline: Ongoing

### Process

**For each app:**

1. **Baseline:** Run coverage report
2. **Identify:** Find critical untested paths
3. **Test:** Write tests for critical paths first
4. **Measure:** Re-run coverage, track progress
5. **Repeat:** Until target coverage met

**Do NOT:**
- ❌ Stop feature development for testing
- ❌ Write shallow tests just for coverage
- ❌ Test everything at once

**DO:**
- ✅ Test new code as written (TDD)
- ✅ Add tests when fixing bugs
- ✅ Incrementally improve coverage

---

## Quality Guidelines

### Good Tests

✅ **Test behavior, not implementation:**
```python
# ✅ GOOD: Test behavior
def test_user_can_check_in_at_assigned_post():
    assert service.check_in(user_id, post_id) is not None

# ❌ BAD: Test implementation
def test_check_in_calls_create_method():
    assert mock_model.create.called
```

✅ **Test one thing per test:**
```python
# ✅ GOOD: Focused test
def test_check_in_creates_event():
    event = service.check_in(user_id, post_id, geolocation)
    assert event.event_type == 'check_in'

def test_check_in_validates_geofence():
    with pytest.raises(ValidationError):
        service.check_in(user_id, post_id, invalid_location)

# ❌ BAD: Tests multiple things
def test_check_in():
    event = service.check_in(user_id, post_id, geolocation)
    assert event.event_type == 'check_in'
    assert event.geolocation_validated is True
    assert event.notification_sent is True
    # Too much in one test!
```

✅ **Clear test names:**
```python
# ✅ GOOD: Descriptive name
def test_check_in_fails_when_user_not_assigned_to_post():
    pass

# ❌ BAD: Vague name
def test_check_in_error():
    pass
```

### Bad Tests

❌ **Brittle tests:**
```python
# ❌ BAD: Depends on database state
def test_get_users():
    users = User.objects.all()
    assert len(users) == 5  # Fails if data changes!

# ✅ GOOD: Create test data
def test_get_users():
    User.objects.create(username='test1')
    User.objects.create(username='test2')
    users = User.objects.all()
    assert len(users) == 2
```

❌ **Slow tests:**
```python
# ❌ BAD: Unnecessary delays
def test_async_operation():
    service.start_operation()
    time.sleep(5)  # Don't do this!
    assert service.is_complete()

# ✅ GOOD: Mock or use test utilities
def test_async_operation(mocker):
    mocker.patch('service.delay', return_value=immediate_result)
    assert service.start_operation() is True
```

---

## Metrics and Monitoring

### Coverage Dashboard

Track over time:
- Overall coverage percentage
- Per-app coverage
- Coverage trends (improving/declining)
- Uncovered critical paths

### Quality Metrics

Monitor:
- Test execution time (should stay fast)
- Flaky test rate (< 1%)
- Coverage delta per PR (should not decrease)
- Test-to-code ratio (1:1 to 1:2)

---

## References

- [Testing Best Practices - Django](https://docs.djangoproject.com/en/5.0/topics/testing/overview/)
- [pytest Documentation](https://docs.pytest.org/)
- [Test Pyramid - Martin Fowler](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Coverage.py](https://coverage.readthedocs.io/)

---

**Last Updated:** 2025-11-04

**Next Review:** 2026-02-04 (3 months) - Review coverage targets and backfill progress
---

## Implementation Status

**Status:** ✅ **Implemented and Validated** (Phase 1-6)

**Phase 1-6 Results:**
- Applied across 16 refactored apps
- 100% compliance in all new code
- 0 production incidents related to this ADR

**See:** [PROJECT_RETROSPECTIVE.md](../../PROJECT_RETROSPECTIVE.md) for complete implementation details

**Last Updated:** 2025-11-05
