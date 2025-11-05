# Testing Training Guide

**Audience:** All developers writing tests

**Prerequisites:** Quality Standards Training

**Duration:** 2 hours + hands-on practice

**Last Updated:** November 5, 2025

---

## Table of Contents

1. [Testing Strategy](#testing-strategy)
2. [Writing Effective Tests](#writing-effective-tests)
3. [Testing Refactored Code](#testing-refactored-code)
4. [Common Anti-Patterns](#common-anti-patterns)
5. [Hands-On Exercises](#hands-on-exercises)

---

## Testing Strategy

### Test Pyramid

```
       ┌─────────────────┐
       │   E2E Tests     │  ← Few, slow, expensive
       │   (Selenium)    │
       └─────────────────┘
      ┌───────────────────┐
      │ Integration Tests │  ← Some, moderate speed
      │  (API, Services)  │
      └───────────────────┘
    ┌──────────────────────┐
    │    Unit Tests        │  ← Many, fast, cheap
    │  (Models, Utils)     │
    └──────────────────────┘
```

**Our Targets:**
- 80%+ code coverage
- 70% unit tests
- 25% integration tests
- 5% E2E tests

---

## Writing Effective Tests

### Unit Test Template

```python
# tests/test_models/test_your_model.py

import pytest
from apps.your_app.models import YourModel


@pytest.mark.django_db
class TestYourModel:
    """Tests for YourModel."""

    def test_create_success(self):
        """Test successful model creation."""
        # Arrange
        data = {
            'name': 'Test Name',
            'status': 'active'
        }

        # Act
        instance = YourModel.objects.create(**data)

        # Assert
        assert instance.id is not None
        assert instance.name == 'Test Name'
        assert instance.status == 'active'

    def test_validation_failure(self):
        """Test validation catches invalid data."""
        with pytest.raises(ValidationError):
            YourModel.objects.create(name='')  # Empty name

    def test_string_representation(self):
        """Test __str__ method."""
        instance = YourModel.objects.create(name='Test')
        assert str(instance) == 'Test'
```

### Service Test Template

```python
# tests/test_services/test_your_service.py

import pytest
from unittest.mock import patch, Mock
from apps.your_app.services import YourService


@pytest.mark.django_db
class TestYourService:
    """Tests for YourService business logic."""

    def test_create_something_success(self, user):
        """Test successful creation."""
        result = YourService.create_something(
            user=user,
            name="Test"
        )

        assert result.name == "Test"
        assert result.owner == user

    def test_create_something_sends_notification(self, user):
        """Test notification is sent."""
        with patch('apps.your_app.services.NotificationService') as mock:
            result = YourService.create_something(user=user, name="Test")
            mock.notify_creation.assert_called_once_with(result)

    def test_create_something_permission_denied(self, user_no_perms):
        """Test permission check."""
        with pytest.raises(PermissionDenied):
            YourService.create_something(user=user_no_perms, name="Test")
```

### Integration Test Template

```python
# tests/test_integration/test_attendance_flow.py

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestAttendanceFlow:
    """Integration tests for attendance flow."""

    def test_checkin_flow(self, user, geofence):
        """Test complete check-in flow."""
        client = APIClient()
        client.force_authenticate(user=user)

        # Check in
        response = client.post('/api/v1/attendance/checkin/', {
            'latitude': geofence.center.y,
            'longitude': geofence.center.x,
        })

        assert response.status_code == 201
        assert 'event_id' in response.json()

        # Verify event created
        from apps.attendance.models import PeopleEventlog
        event = PeopleEventlog.objects.get(id=response.json()['event_id'])
        assert event.user == user
        assert event.geofence == geofence
```

---

## Testing Refactored Code

### After Splitting Models

**Challenge:** Models moved from `models.py` → `models/` package

**Solution:** Update test imports

```python
# ❌ Before refactoring
from apps.your_app.models import YourModel

# ✅ After refactoring (still works!)
from apps.your_app.models import YourModel  # Works via __init__.py
```

**No test changes needed if `__init__.py` exports correctly!**

### Testing Backward Compatibility

```python
def test_backward_compatible_imports():
    """Verify old imports still work."""
    # Test package import
    from apps.your_app.models import YourModel
    assert YourModel is not None

    # Test wildcard import
    from apps.your_app.models import *
    assert 'YourModel' in dir()

    # Test __all__ completeness
    from apps.your_app import models
    assert 'YourModel' in models.__all__
```

### Testing After Service Extraction

**Before:** Business logic in view (hard to test)

```python
# No good way to test this without HTTP
def test_checkin_view(client, user):
    client.force_authenticate(user=user)
    response = client.post('/checkin/', {...})
    # Testing HTTP + business logic together
```

**After:** Service extracted (easy to test)

```python
# Test business logic independently
def test_checkin_service(user, coordinates):
    event = AttendanceService.process_checkin(user, coordinates)
    assert event.user == user

# Test view separately (thin HTTP layer)
def test_checkin_view_delegates_to_service(client, user, mock_service):
    with patch('apps.attendance.views.AttendanceService') as mock:
        response = client.post('/checkin/', {...})
        mock.process_checkin.assert_called_once()
```

---

## Common Anti-Patterns

### Anti-Pattern 1: Testing Implementation, Not Behavior

```python
# ❌ WRONG: Testing internal implementation
def test_uses_cache(self):
    service = YourService()
    service.get_data()
    # Check cache was called
    assert service._cache.get.called
```

```python
# ✅ CORRECT: Testing behavior
def test_returns_correct_data(self):
    result = YourService.get_data()
    assert result == expected_data
    # Don't care HOW it got the data
```

### Anti-Pattern 2: Mocking Too Much

```python
# ❌ WRONG: Mocking everything
def test_create_user(self):
    with patch('apps.users.models.User.objects.create') as mock:
        mock.return_value = Mock(id=1, name='Test')
        result = UserService.create_user(name='Test')
        # You're testing mocks, not real code!
```

```python
# ✅ CORRECT: Use real database for models
@pytest.mark.django_db
def test_create_user(self):
    result = UserService.create_user(name='Test')
    # Testing real database operations
    assert User.objects.filter(id=result.id).exists()
```

### Anti-Pattern 3: Test-Only Methods in Production

```python
# ❌ WRONG: Adding test-only methods
class YourModel(models.Model):
    def _test_set_status(self, status):  # Test-only method!
        self.status = status
```

```python
# ✅ CORRECT: Test public interface
class YourModel(models.Model):
    def set_status(self, status):  # Real method
        self.status = status

# Test calls real method
def test_set_status():
    model = YourModel()
    model.set_status('active')
    assert model.status == 'active'
```

### Anti-Pattern 4: Fragile Tests (Too Many Mocks)

```python
# ❌ FRAGILE: Breaks if implementation changes
def test_process_order(self):
    with patch('module.A') as mock_a, \
         patch('module.B') as mock_b, \
         patch('module.C') as mock_c, \
         patch('module.D') as mock_d:
        # If implementation changes, all tests break
```

```python
# ✅ ROBUST: Test behavior, not implementation
@pytest.mark.django_db
def test_process_order(self):
    order = OrderService.process_order(cart, user)
    assert order.status == 'completed'
    assert order.total == expected_total
    # Test output, not internal calls
```

---

## Hands-On Exercises

### Exercise 1: Write Unit Tests for Model

**Task:** Write tests for this model

```python
class Task(models.Model):
    title = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('complete', 'Complete'),
        ],
        default='pending'
    )

    def complete(self):
        """Mark task as complete."""
        self.status = 'complete'
        self.save()
```

**Tests to write:**
1. Test creation
2. Test default status
3. Test `complete()` method
4. Test string representation
5. Test validation (empty title)

### Exercise 2: Write Service Tests

**Task:** Write tests for this service

```python
class TaskService:
    @staticmethod
    def create_task(user, title):
        if not user.has_perm('tasks.add_task'):
            raise PermissionDenied()

        task = Task.objects.create(
            title=title,
            created_by=user
        )

        NotificationService.notify_task_created(task)
        return task
```

**Tests to write:**
1. Test successful creation
2. Test permission denied
3. Test notification sent
4. Test validation error (empty title)

### Exercise 3: Integration Test

**Task:** Write integration test for check-in API

**Endpoint:** `POST /api/v1/attendance/checkin/`

**Tests to write:**
1. Successful check-in
2. Out of geofence (400 error)
3. Duplicate check-in (400 error)
4. Unauthenticated (401 error)

---

## Test Coverage

### Running Coverage

```bash
# Run tests with coverage
python -m pytest --cov=apps --cov-report=html:coverage_reports/html

# View HTML report
open coverage_reports/html/index.html
```

### Interpreting Coverage

```
apps/your_app/models.py       95%   ✅ Good
apps/your_app/services.py     82%   ✅ Acceptable
apps/your_app/views.py        68%   ⚠️  Needs improvement
apps/your_app/utils.py        45%   ❌ Too low
```

**Targets:**
- Models: >90%
- Services: >80%
- Views: >70%
- Utils: >80%

---

## Fixtures

### Using pytest Fixtures

```python
# conftest.py

import pytest
from apps.users.models import User


@pytest.fixture
def user(db):
    """Create test user."""
    return User.objects.create(
        username='testuser',
        email='test@example.com'
    )


@pytest.fixture
def admin_user(db):
    """Create admin user."""
    user = User.objects.create(
        username='admin',
        email='admin@example.com',
        is_staff=True
    )
    return user


@pytest.fixture
def geofence(db):
    """Create test geofence."""
    from apps.attendance.models import Geofence
    from django.contrib.gis.geos import Point, Polygon

    return Geofence.objects.create(
        name='Test Site',
        polygon=Polygon(...),
        center=Point(0, 0)
    )
```

**Usage:**

```python
def test_something(user, geofence):
    # Fixtures injected automatically
    event = create_event(user=user, geofence=geofence)
    assert event.user == user
```

---

## Resources

- **[Testing & Quality Guide](../testing/TESTING_AND_QUALITY_GUIDE.md)**
- **[ADR 004: Test Coverage Requirements](../architecture/adr/004-test-coverage-requirements.md)**
- pytest documentation: https://docs.pytest.org/

---

## Assessment

**Complete these tasks:**

1. Write unit tests for a model (>90% coverage)
2. Write service tests with mocking
3. Write integration test for API endpoint
4. Achieve 80%+ coverage on a module

---

**Training Complete! 🎓**

**Last Updated:** November 5, 2025
