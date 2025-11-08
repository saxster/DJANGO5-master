# Testing Quick Start Guide

**For Developers**: How to run and write tests for the IntelliWiz platform

---

## Table of Contents
1. [Running Tests](#running-tests)
2. [Test Structure](#test-structure)
3. [Writing New Tests](#writing-new-tests)
4. [Coverage Reports](#coverage-reports)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

---

## Running Tests

### Prerequisites

```bash
# Ensure correct Python version
python --version  # Should be 3.11.9

# Install test dependencies (if not already installed)
pip install pytest pytest-cov pytest-django
```

### Quick Commands

```bash
# Run all tests
python -m pytest

# Run specific module
python -m pytest tests/mqtt/

# Run specific test file
python -m pytest tests/mqtt/test_alert_notification_service.py

# Run specific test class
python -m pytest tests/mqtt/test_alert_notification_service.py::TestSMSNotifications

# Run specific test
python -m pytest tests/mqtt/test_alert_notification_service.py::TestSMSNotifications::test_send_sms_success

# Run with verbose output
python -m pytest -v

# Run with coverage
python -m pytest --cov=apps --cov-report=term-missing

# Run only fast tests (skip slow ones)
python -m pytest -m "not slow"
```

### Test Categories

```bash
# MQTT Services Tests
python -m pytest tests/mqtt/ -v

# ML Training Services Tests
python -m pytest tests/ml_training/ -v

# Monitoring Services Tests
python -m pytest tests/monitoring/ -v

# Integration Tests
python -m pytest tests/integration/ -v

# Performance Tests
python -m pytest tests/performance/ -v
```

---

## Test Structure

### Directory Layout

```
tests/
├── mqtt/                           # MQTT service tests
│   └── test_alert_notification_service.py
├── ml_training/                    # ML training tests
│   └── test_active_learning_service.py
├── monitoring/                     # Monitoring tests
│   └── test_device_health_service.py
├── integration/                    # Integration tests
│   └── test_critical_workflows.py
└── performance/                    # Performance tests
    └── test_performance_benchmarks.py
```

### Test File Naming

- **File**: `test_<module_name>.py`
- **Class**: `Test<FeatureName>`
- **Method**: `test_<what_it_tests>`

Example:
```python
# File: tests/mqtt/test_alert_notification_service.py

class TestAlertNotificationService:
    def test_notify_critical_alert_all_channels(self, sample_alert, recipients):
        """Test that critical alerts trigger all notification channels."""
        pass
```

---

## Writing New Tests

### Basic Test Template

```python
"""
Brief description of what this test module covers.
"""

import pytest
from unittest.mock import Mock, patch

from apps.your_app.services import YourService


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    return {"key": "value"}


class TestYourService:
    """Test YourService functionality."""
    
    def test_happy_path(self, sample_data):
        """Test successful execution."""
        result = YourService.do_something(sample_data)
        
        assert result is not None
        assert result['success'] is True
    
    def test_error_handling(self):
        """Test error scenarios."""
        with pytest.raises(ValueError):
            YourService.do_something(None)
    
    def test_validation(self):
        """Test input validation."""
        invalid_data = {"invalid": "data"}
        result = YourService.do_something(invalid_data)
        
        assert result['success'] is False
        assert 'error' in result
```

### Using Fixtures

```python
@pytest.fixture
def authenticated_user(db):
    """Create authenticated test user."""
    from apps.peoples.models import People
    
    user = People.objects.create(
        peoplename="testuser",
        peopleemail="test@example.com",
        peoplecontactno="+919876543210",
        is_active=True
    )
    return user


def test_something_with_user(authenticated_user):
    """Test using authenticated user."""
    assert authenticated_user.is_active is True
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, patch

@patch('apps.mqtt.services.alert_notification_service.Client')
def test_send_sms_with_mock(mock_twilio_client):
    """Test SMS sending with mocked Twilio."""
    # Setup mock
    mock_message = Mock()
    mock_message.sid = 'SM123456'
    mock_twilio_client.return_value.messages.create.return_value = mock_message
    
    # Call service
    result = AlertNotificationService._send_sms_notifications(alert, phones)
    
    # Verify
    assert result[0].success is True
    assert result[0].external_id == 'SM123456'
```

### Performance Testing

```python
import time

def test_api_response_time(client, authenticated_user):
    """Test API responds in < 100ms."""
    start_time = time.time()
    response = client.get('/api/v1/users/')
    elapsed_time = time.time() - start_time
    
    assert elapsed_time < 0.1
    assert response.status_code == 200
```

### Database Query Optimization

```python
def test_no_n_plus_one_queries(django_assert_num_queries):
    """Test query count is optimized."""
    with django_assert_num_queries(5):
        users = People.objects.select_related('peopleprofile').all()[:10]
        list(users)
```

---

## Coverage Reports

### Generate Coverage Report

```bash
# Run tests with coverage
python -m pytest --cov=apps --cov-report=html:coverage_reports/html

# Open HTML report
open coverage_reports/html/index.html
```

### Coverage Thresholds

```bash
# Fail if coverage below 80%
python -m pytest --cov=apps --cov-fail-under=80

# Coverage for specific app
python -m pytest --cov=apps/mqtt --cov-report=term
```

### View Coverage in Terminal

```bash
# Show missing lines
python -m pytest --cov=apps --cov-report=term-missing

# Show only summary
python -m pytest --cov=apps --cov-report=term
```

---

## Common Patterns

### Pattern 1: Testing Service Methods

```python
class TestYourService:
    """Test service layer methods."""
    
    def test_create_resource(self, db):
        """Test resource creation."""
        result = YourService.create_resource(
            name="Test Resource",
            description="Test"
        )
        
        assert result['success'] is True
        assert result['resource'] is not None
    
    def test_update_resource(self, db):
        """Test resource update."""
        resource = YourService.create_resource(name="Test")
        
        result = YourService.update_resource(
            resource['resource'].id,
            name="Updated"
        )
        
        assert result['success'] is True
        assert result['resource'].name == "Updated"
```

### Pattern 2: Integration Testing

```python
def test_end_to_end_workflow(client, authenticated_user, db):
    """Test complete workflow from start to finish."""
    # Step 1: Create resource
    resource = create_resource(...)
    assert resource.status == 'PENDING'
    
    # Step 2: Process resource
    process_resource(resource)
    resource.refresh_from_db()
    assert resource.status == 'PROCESSING'
    
    # Step 3: Complete resource
    complete_resource(resource)
    resource.refresh_from_db()
    assert resource.status == 'COMPLETED'
```

### Pattern 3: Multi-Tenant Testing

```python
def test_tenant_isolation(db):
    """Test data isolation between tenants."""
    tenant1 = Tenant.objects.create(name="Tenant 1", subdomain="t1")
    tenant2 = Tenant.objects.create(name="Tenant 2", subdomain="t2")
    
    # Create resource in tenant1
    resource1 = Resource.objects.create(name="R1", tenant=tenant1)
    
    # Verify tenant2 can't see it
    tenant2_resources = Resource.objects.filter(tenant=tenant2)
    assert resource1 not in tenant2_resources
```

### Pattern 4: Error Handling Testing

```python
def test_handles_database_error(db):
    """Test graceful handling of database errors."""
    from django.db import DatabaseError
    
    with patch.object(Model.objects, 'create', side_effect=DatabaseError("Connection lost")):
        result = YourService.create_resource(...)
        
        assert result['success'] is False
        assert 'error' in result
```

---

## Troubleshooting

### Common Issues

#### Issue: "No module named pytest"
**Solution**:
```bash
pip install pytest pytest-cov pytest-django
```

#### Issue: Database errors during tests
**Solution**:
```bash
# Reset test database
python manage.py flush --no-input --database=default

# Migrate test database
python manage.py migrate --run-syncdb
```

#### Issue: Tests hang or timeout
**Solution**:
```bash
# Run with timeout
python -m pytest --timeout=60

# Check for blocking I/O or missing mocks
```

#### Issue: ImportError for apps
**Solution**:
```bash
# Ensure Django settings are configured
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.development

# Or use pytest-django
pytest --ds=intelliwiz_config.settings.development
```

#### Issue: Cache-related test failures
**Solution**:
```python
# Clear cache before each test
@pytest.fixture(autouse=True)
def clear_cache():
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
```

### Debug Tips

```bash
# Run tests with print statements visible
python -m pytest -s

# Drop into debugger on failure
python -m pytest --pdb

# Show full traceback
python -m pytest --tb=long

# Run only failed tests
python -m pytest --lf

# Run tests matching pattern
python -m pytest -k "test_sms"
```

---

## Best Practices

### 1. Keep Tests Fast
- Mock external services (Twilio, email, FCM)
- Use in-memory databases where possible
- Mark slow tests with `@pytest.mark.slow`

### 2. Test One Thing
```python
# Good: Tests one specific behavior
def test_create_user_with_valid_data(self):
    user = create_user(email="test@example.com")
    assert user.email == "test@example.com"

# Bad: Tests multiple things
def test_user_operations(self):
    user = create_user(...)
    update_user(...)
    delete_user(...)
    # Too much in one test
```

### 3. Use Descriptive Names
```python
# Good: Clear what's being tested
def test_user_cannot_access_other_tenant_data(self):
    pass

# Bad: Unclear purpose
def test_user_access(self):
    pass
```

### 4. Arrange-Act-Assert Pattern
```python
def test_create_work_order(self):
    # Arrange: Set up test data
    user = create_user()
    tenant = create_tenant()
    
    # Act: Perform the action
    work_order = WorkOrder.objects.create(
        title="Test",
        tenant=tenant,
        created_by=user
    )
    
    # Assert: Verify results
    assert work_order.title == "Test"
    assert work_order.tenant == tenant
```

### 5. Clean Up After Tests
```python
@pytest.fixture
def temp_file():
    """Create temporary file for testing."""
    file_path = "/tmp/test_file.txt"
    with open(file_path, 'w') as f:
        f.write("test")
    
    yield file_path
    
    # Cleanup
    if os.path.exists(file_path):
        os.remove(file_path)
```

---

## Reference

### Pytest Markers

```python
@pytest.mark.slow          # Mark as slow test
@pytest.mark.django_db     # Requires database access
@pytest.mark.skip          # Skip this test
@pytest.mark.skipif(...)   # Conditional skip
@pytest.mark.parametrize   # Run test with multiple inputs
```

### Assertions

```python
assert value == expected
assert value is True
assert value is not None
assert len(list) == 5
assert 'key' in dict
assert value > 10
with pytest.raises(ValueError):
    do_something()
```

### Django Test Client

```python
from django.test import Client

client = Client()

# GET request
response = client.get('/api/users/')
assert response.status_code == 200

# POST request
response = client.post('/api/users/', {'name': 'Test'})
assert response.status_code == 201

# With authentication
client.force_login(user)
response = client.get('/dashboard/')
```

---

## Additional Resources

- **Django Testing**: https://docs.djangoproject.com/en/5.2/topics/testing/
- **Pytest**: https://docs.pytest.org/
- **pytest-django**: https://pytest-django.readthedocs.io/
- **Coverage.py**: https://coverage.readthedocs.io/

---

**Last Updated**: November 7, 2025  
**Maintainer**: Development Team
