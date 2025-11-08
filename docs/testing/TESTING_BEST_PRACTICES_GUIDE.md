# Testing Best Practices Guide

**Comprehensive testing patterns from remediation work (Nov 2025)**

---

## Overview

This guide captures all testing patterns and best practices from the extensive remediation work completed in November 2025, including:
- **141 IDOR security tests** across 5 apps
- **110+ service layer tests** for 3 critical services
- **Performance testing** patterns for query optimization
- **Test organization** strategies for maintainability

---

## Table of Contents

1. [Security Testing](#security-testing)
2. [Performance Testing](#performance-testing)
3. [Service Layer Testing](#service-layer-testing)
4. [Test Organization](#test-organization)
5. [Common Antipatterns](#common-antipatterns)
6. [Testing Tools](#testing-tools)

---

## Security Testing

### IDOR (Insecure Direct Object Reference) Testing

**Purpose:** Prevent users from accessing resources by manipulating IDs

**Coverage:** 141 tests across 5 apps

#### Test Pattern

```python
class PeoplesIDORTestCase(TestCase):
    """IDOR security tests for cross-tenant and cross-user access."""
    
    def setUp(self):
        # Create two tenants
        self.client_a = Client.objects.create(name='Tenant A')
        self.client_b = Client.objects.create(name='Tenant B')
        
        # Create users in different tenants
        self.user_a = People.objects.create(
            username='user_a@tenant-a.com',
            client=self.client_a
        )
        self.user_b = People.objects.create(
            username='user_b@tenant-b.com',
            client=self.client_b
        )
    
    def test_user_cannot_access_other_tenant_profile(self):
        """Verify users cannot view profiles from other tenants."""
        # Login as user from Tenant B
        self.client.force_login(self.user_b)
        
        # Attempt to access user from Tenant A
        response = self.client.get(f'/people/profile/{self.user_a.id}/')
        
        # Should be blocked (403 or 404)
        self.assertIn(response.status_code, [403, 404])
```

#### Attack Vectors to Test

1. **Cross-Tenant Access** (40+ tests)
   - Direct object access by ID
   - List/query filtering
   - Bulk operations
   - Report generation
   - API endpoints

2. **Cross-User Privacy** (25+ tests)
   - Profile access
   - Record modification
   - Assignment manipulation
   - Comment/attachment access

3. **Permission Escalation** (15+ tests)
   - Admin function access
   - Privilege escalation
   - Approval bypassing
   - Status manipulation

4. **Input Validation** (20+ tests)
   - Sequential ID enumeration
   - Negative ID handling
   - Invalid ID formats
   - Path traversal

5. **API Security** (20+ tests)
   - Endpoint authorization
   - List filtering
   - Bulk operations
   - Query parameters

6. **Workflow Security** (21+ tests)
   - Assignment validation
   - Status transitions
   - Approval workflows
   - Notification triggers

#### Examples by App

**Peoples App (24 tests):**
```python
def test_user_cannot_access_other_tenant_user_profile(self):
    """Cross-tenant profile access prevention."""
    
def test_admin_cannot_escalate_regular_user_to_superuser(self):
    """Privilege escalation prevention."""
    
def test_sequential_id_enumeration_prevention(self):
    """ID enumeration attack prevention."""
```

**Attendance App (25 tests):**
```python
def test_gps_data_cross_tenant_blocked(self):
    """GPS location data tenant isolation."""
    
def test_biometric_data_cross_tenant_blocked(self):
    """Biometric data tenant isolation."""
    
def test_cannot_backdate_attendance_for_other_user(self):
    """Time manipulation prevention."""
```

**Activity App (29 tests):**
```python
def test_user_cannot_access_other_tenant_job(self):
    """Job tenant isolation."""
    
def test_worker_can_only_view_assigned_tasks(self):
    """Task visibility control."""
    
def test_critical_asset_access_requires_authorization(self):
    """Critical asset security."""
```

**Work Order Management (29 tests):**
```python
def test_vendor_cannot_complete_other_vendor_work_order(self):
    """Vendor isolation."""
    
def test_approval_workflow_cross_tenant_protection(self):
    """Approval workflow security."""
    
def test_work_order_cannot_link_cross_tenant_asset(self):
    """Asset association validation."""
```

**Y_Helpdesk (34 tests):**
```python
def test_user_cannot_download_attachment_from_cross_tenant_ticket(self):
    """Attachment tenant isolation."""
    
def test_internal_comments_not_visible_to_regular_users(self):
    """Internal comment security."""
    
def test_attachment_path_traversal_blocked(self):
    """Path traversal prevention."""
```

---

### Cross-Tenant Testing

**Purpose:** Verify multi-tenancy isolation

**Pattern:**
```python
def test_list_scoped_to_tenant(self):
    """Verify list views only show tenant-scoped data."""
    # Create records for both tenants
    record_a = MyModel.objects.create(name='A', client=self.client_a)
    record_b = MyModel.objects.create(name='B', client=self.client_b)
    
    # Login as user from Tenant A
    self.client.force_login(self.user_a)
    
    # Get list
    response = self.client.get('/mymodels/')
    records = response.context['object_list']
    
    # Should only see Tenant A records
    self.assertIn(record_a, records)
    self.assertNotIn(record_b, records)
    
    # Verify query includes tenant filter
    self.assertTrue(
        all(r.client == self.client_a for r in records),
        "Query should filter by client=request.user.client"
    )
```

**Key Checks:**
- ✅ User cannot access other tenant's resources
- ✅ Lists are filtered to current tenant
- ✅ Bulk operations are scoped to tenant
- ✅ Reports aggregate only tenant data
- ✅ API endpoints enforce tenant isolation

---

### Permission Boundary Testing

**Purpose:** Verify users cannot perform actions outside their permission scope

**Pattern:**
```python
def test_regular_user_cannot_access_admin_functions(self):
    """Verify admin function access control."""
    # Create regular user
    regular_user = People.objects.create(
        username='regular@test.com',
        client=self.client_a,
        is_staff=False  # Not admin
    )
    
    # Login as regular user
    self.client.force_login(regular_user)
    
    # Attempt to access admin function
    response = self.client.get('/admin/peoples/people/')
    
    # Should be blocked
    self.assertEqual(response.status_code, 302)  # Redirect to login
    
def test_worker_can_only_view_assigned_tasks(self):
    """Verify task visibility is scoped to assignments."""
    # Create tasks
    assigned_task = Task.objects.create(
        name='Assigned',
        client=self.client_a
    )
    assigned_task.assigned_people.add(self.worker)
    
    unassigned_task = Task.objects.create(
        name='Unassigned',
        client=self.client_a
    )
    
    # Login as worker
    self.client.force_login(self.worker)
    
    # Get task list
    response = self.client.get('/tasks/')
    tasks = response.context['tasks']
    
    # Should only see assigned tasks
    self.assertIn(assigned_task, tasks)
    self.assertNotIn(unassigned_task, tasks)
```

---

### Authentication Testing

**Purpose:** Verify login, session management, and device trust

**Examples:**
```python
# Device Trust Testing (35+ tests)
def test_device_trust_score_increases_with_biometric(self):
    """Verify biometric enrollment increases trust score."""
    service = DeviceTrustService()
    
    # Initial score (unknown device)
    result = service.validate_device(self.user, 'device123')
    initial_score = result['trust_score']
    
    # Enroll biometric
    DeviceInfo.objects.create(
        user=self.user,
        device_id='device123',
        has_biometric=True
    )
    
    # Check score again
    result = service.validate_device(self.user, 'device123')
    new_score = result['trust_score']
    
    # Score should increase
    self.assertGreater(new_score, initial_score)

# Login Throttling Testing (40+ tests)
def test_login_locks_after_5_failed_attempts(self):
    """Verify rate limiting activates after threshold."""
    service = LoginThrottlingService()
    ip = '192.168.1.100'
    username = 'test@example.com'
    
    # Simulate 5 failed attempts
    for i in range(5):
        service.record_failed_attempt(ip, username)
    
    # 6th attempt should be locked
    result = service.check_ip_throttle(ip)
    self.assertTrue(result['is_locked'])
    self.assertIn('retry_after', result)
```

---

### File Security Testing

**Purpose:** Prevent path traversal and unauthorized file access

**Pattern:**
```python
def test_attachment_path_traversal_blocked(self):
    """Verify path traversal attacks are blocked."""
    # Attempt path traversal
    malicious_paths = [
        '../../../etc/passwd',
        '..\\..\\..\\windows\\system32\\config\\sam',
        '/etc/passwd',
        'C:\\windows\\system32\\config\\sam'
    ]
    
    for path in malicious_paths:
        response = self.client.get(f'/download/?file={path}')
        # Should be blocked
        self.assertEqual(response.status_code, 400)

def test_secure_file_download_with_token(self):
    """Verify token-based file download with permission checks."""
    # Create attachment owned by user_a
    attachment = Attachment.objects.create(
        owner=self.user_a,
        filepath='/media/uploads/test.pdf',
        filename='test.pdf'
    )
    
    # Login as user_b
    self.client.force_login(self.user_b)
    
    # Attempt download
    response = self.client.get(f'/download/{attachment.id}/')
    
    # Should be blocked (403)
    self.assertEqual(response.status_code, 403)
```

**Security Layers:**
1. **Path validation** - Prevent traversal outside MEDIA_ROOT
2. **Ownership validation** - User must own file or have permissions
3. **Tenant isolation** - Cross-tenant access blocked
4. **Token validation** - Require valid download token
5. **Audit logging** - Log all access attempts

---

## Performance Testing

### Query Count Assertions

**Purpose:** Prevent N+1 query issues and verify optimization

**Pattern:**
```python
from django.test.utils import override_settings
from django.db import connection

@override_settings(DEBUG=True)
def test_query_count_optimized(self):
    """Verify N+1 queries are prevented with select_related."""
    # Create test data (100 users with profiles)
    for i in range(100):
        user = People.objects.create(username=f'user{i}')
        PeopleProfile.objects.create(people=user, gender='M')
    
    # Clear query log
    connection.queries_log.clear()
    
    # Perform operation with optimization
    users = People.objects.select_related('peopleprofile').all()
    
    # Access related data
    for user in users:
        _ = user.peopleprofile.gender  # Should not trigger extra queries
    
    # Check query count
    query_count = len(connection.queries)
    self.assertLessEqual(
        query_count, 
        3,  # 1 for users, 1 for profiles (joined), 1 for transaction
        f"N+1 query detected: {query_count} queries for 100 users"
    )
```

**Key Points:**
- ✅ Test with realistic data volumes (100+ records)
- ✅ Use `override_settings(DEBUG=True)` to capture queries
- ✅ Force queryset evaluation with `list()` or iteration
- ✅ Set realistic thresholds (not just 1 query)
- ✅ Verify `select_related` / `prefetch_related` usage

---

### Performance Benchmarking

**Purpose:** Establish performance baselines and detect regressions

**Pattern:**
```python
import pytest
import time

@pytest.mark.performance
def test_response_time_acceptable(self):
    """Verify response time is under 100ms."""
    times = []
    
    # Run 100 iterations
    for _ in range(100):
        start = time.perf_counter()
        response = self.client.get('/dashboard/')
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    # Calculate statistics
    mean_time = sum(times) / len(times)
    p95_time = sorted(times)[94]  # 95th percentile
    p99_time = sorted(times)[98]  # 99th percentile
    
    # Assert thresholds
    self.assertLess(mean_time, 0.100, f"Mean: {mean_time:.3f}s > 100ms")
    self.assertLess(p95_time, 0.200, f"P95: {p95_time:.3f}s > 200ms")
    self.assertLess(p99_time, 0.500, f"P99: {p99_time:.3f}s > 500ms")
```

**Best Practices:**
- ✅ Mark with `@pytest.mark.performance` to run separately
- ✅ Run multiple iterations (100+) for statistical validity
- ✅ Calculate mean, median, p95, p99
- ✅ Set realistic thresholds based on SLAs
- ✅ Profile slow tests to identify bottlenecks

---

### Load Testing

**Purpose:** Verify system handles concurrent requests

**Pattern:**
```python
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed

@pytest.mark.performance
def test_concurrent_login_requests(self):
    """Verify system handles 100 concurrent logins."""
    
    def attempt_login(username):
        response = self.client.post('/login/', {
            'username': username,
            'password': 'test123'
        })
        return response.status_code
    
    # Create 100 test users
    users = [f'user{i}@test.com' for i in range(100)]
    
    # Concurrent login attempts
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_login, u) for u in users]
        results = [f.result() for f in as_completed(futures)]
    
    # Verify all succeeded
    success_count = sum(1 for r in results if r == 200)
    self.assertEqual(success_count, 100, "Some logins failed under load")
```

---

## Service Layer Testing

### Service Test Patterns

**Purpose:** Test business logic in service classes

**Coverage:** 110+ tests for 3 critical services

#### Unit Tests with Mocking

```python
from unittest.mock import patch, MagicMock

class DeviceTrustServiceTest(TestCase):
    """Unit tests for DeviceTrustService with mocked dependencies."""
    
    @patch('apps.peoples.models.DeviceInfo.objects.get')
    def test_validate_device_known_device(self, mock_get):
        """Test device validation with mocked database."""
        # Setup mock
        mock_device = MagicMock()
        mock_device.has_biometric = True
        mock_device.last_seen = timezone.now() - timedelta(hours=1)
        mock_get.return_value = mock_device
        
        # Test
        service = DeviceTrustService()
        result = service.validate_device(self.user, 'device123')
        
        # Verify
        self.assertTrue(result['is_known'])
        self.assertGreater(result['trust_score'], 50)
        mock_get.assert_called_once_with(
            user=self.user,
            device_id='device123'
        )
```

#### Integration Tests with Real Database

```python
class DeviceTrustServiceIntegrationTest(TestCase):
    """Integration tests with real database."""
    
    def test_enrollment_flow_integration(self):
        """Test complete enrollment flow end-to-end."""
        service = DeviceTrustService()
        device_id = 'new-device-123'
        
        # Step 1: Unknown device (low trust)
        result = service.validate_device(self.user, device_id)
        self.assertFalse(result['is_known'])
        self.assertLess(result['trust_score'], 30)
        
        # Step 2: Enroll device
        device = DeviceInfo.objects.create(
            user=self.user,
            device_id=device_id,
            device_name='Test Phone',
            os_type='Android'
        )
        
        # Step 3: Known device (medium trust)
        result = service.validate_device(self.user, device_id)
        self.assertTrue(result['is_known'])
        self.assertGreater(result['trust_score'], 50)
        
        # Step 4: Add biometric (high trust)
        device.has_biometric = True
        device.save()
        
        result = service.validate_device(self.user, device_id)
        self.assertGreater(result['trust_score'], 80)
```

---

### Test Fixtures and Factories

**Pytest Fixtures:**
```python
import pytest

@pytest.fixture
def sample_client(db):
    """Create a test client (tenant)."""
    return Client.objects.create(name='Test Client')

@pytest.fixture
def sample_user(db, sample_client):
    """Create a test user."""
    return People.objects.create(
        username='test@example.com',
        client=sample_client
    )

@pytest.fixture
def device_trust_service():
    """Create DeviceTrustService instance."""
    return DeviceTrustService()

# Usage
def test_with_fixtures(sample_user, device_trust_service):
    result = device_trust_service.validate_device(sample_user, 'device123')
    assert 'trust_score' in result
```

**Django setUp:**
```python
class ServiceTestCase(TestCase):
    def setUp(self):
        """Per-test setup."""
        self.client_obj = Client.objects.create(name='Test Client')
        self.user = People.objects.create(
            username='test@example.com',
            client=self.client_obj
        )
    
    @classmethod
    def setUpTestData(cls):
        """Class-level setup (faster for read-only data)."""
        cls.readonly_client = Client.objects.create(name='Read-Only Client')
```

---

### Error Handling Tests

**Purpose:** Verify graceful degradation

**Pattern:**
```python
from unittest.mock import patch
from django.db import OperationalError

class ErrorHandlingTest(TestCase):
    @patch('apps.peoples.models.DeviceInfo.objects.get')
    def test_database_error_handling(self, mock_get):
        """Verify service handles database errors gracefully."""
        # Simulate database error
        mock_get.side_effect = OperationalError("Connection lost")
        
        service = DeviceTrustService()
        result = service.validate_device(self.user, 'device123')
        
        # Should return error response (not raise exception)
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('database', result['error'].lower())
    
    @patch('django.core.cache.cache.get')
    def test_cache_failure_resilience(self, mock_cache):
        """Verify service works when cache is unavailable."""
        # Simulate cache failure
        mock_cache.side_effect = ConnectionError("Redis unavailable")
        
        service = LoginThrottlingService()
        result = service.check_ip_throttle('192.168.1.1')
        
        # Should allow request (fail open)
        self.assertFalse(result['is_locked'])
```

---

## Test Organization

### Test Naming Conventions

**Pattern:** `test_<method>_<scenario>_<expected_result>`

**Good Examples:**
- ✅ `test_login_throttle_locks_after_5_attempts`
- ✅ `test_device_trust_score_increases_with_biometric`
- ✅ `test_api_returns_404_for_invalid_user_id`
- ✅ `test_user_cannot_access_other_tenant_profile`

**Bad Examples:**
- ❌ `test_throttle` (too generic)
- ❌ `test1` (meaningless)
- ❌ `test_api` (what about the API?)

---

### Pytest Markers

**Configure in `pytest.ini`:**
```ini
[pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    security: Security tests
    performance: Performance tests (slow)
    idor: IDOR security tests
```

**Usage:**
```python
import pytest

@pytest.mark.unit
@pytest.mark.security
def test_permission_check():
    """Unit test for permission checking logic."""
    pass

@pytest.mark.integration
@pytest.mark.performance
def test_full_workflow():
    """Integration test with performance measurement."""
    pass
```

**Run specific markers:**
```bash
# Run only unit tests
pytest -m unit

# Run security tests but not slow ones
pytest -m "security and not performance"

# Run IDOR tests
pytest -m idor -v
```

---

### Test Coverage Goals

**Targets:**
- Overall: **80%+**
- Security-critical: **90%+**
- Service layer: **70%+**

**Generate coverage report:**
```bash
pytest --cov=apps \
    --cov-report=html:coverage_reports/html \
    --cov-report=term-missing \
    -v
```

**Configure `.coveragerc`:**
```ini
[run]
omit =
    */migrations/*
    */tests/*
    */venv/*
    */vendored/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if TYPE_CHECKING:
```

---

## Common Antipatterns

### ❌ Testing Implementation Details

**Bad:**
```python
def test_internal_method(self):
    """Testing private method directly."""
    result = self.service._calculate_score()  # Private method
    self.assertEqual(result, 100)
```

**Good:**
```python
def test_device_validation_behavior(self):
    """Test observable behavior through public API."""
    result = self.service.validate_device(self.user, 'device123')
    self.assertIn('trust_score', result)
    self.assertGreaterEqual(result['trust_score'], 0)
```

---

### ❌ Brittle Tests

**Bad:**
```python
def test_error_message(self):
    """Hardcoding exact error message."""
    response = self.client.get('/invalid/')
    self.assertEqual(
        response.json()['error'],
        'Invalid request: missing required field "id"'  # Exact match
    )
```

**Good:**
```python
def test_error_response(self):
    """Test error structure, not exact wording."""
    response = self.client.get('/invalid/')
    self.assertEqual(response.status_code, 400)
    self.assertIn('error', response.json())
    self.assertIn('id', response.json()['error'].lower())
```

---

### ❌ Happy Path Only

**Bad:**
```python
def test_create_user(self):
    """Only testing successful creation."""
    user = self.service.create_user('test@example.com')
    self.assertIsNotNone(user)
```

**Good:**
```python
def test_create_user_success(self):
    """Test successful creation."""
    user = self.service.create_user('test@example.com')
    self.assertIsNotNone(user)

def test_create_user_duplicate_email(self):
    """Test duplicate email handling."""
    self.service.create_user('test@example.com')
    with self.assertRaises(ValidationError):
        self.service.create_user('test@example.com')

def test_create_user_invalid_email(self):
    """Test invalid email format."""
    with self.assertRaises(ValidationError):
        self.service.create_user('not-an-email')
```

---

### ❌ Shared Mutable State

**Bad:**
```python
class BadTestCase(TestCase):
    user = None  # Class-level mutable state
    
    def test_first(self):
        self.user = People.objects.create(username='test')
        self.user.is_active = False  # Mutates shared state
    
    def test_second(self):
        # Depends on test_first running first!
        self.assertFalse(self.user.is_active)
```

**Good:**
```python
class GoodTestCase(TestCase):
    def setUp(self):
        """Each test gets fresh user."""
        self.user = People.objects.create(username='test')
    
    def test_first(self):
        self.user.is_active = False  # Only affects this test
        self.assertFalse(self.user.is_active)
    
    def test_second(self):
        # Independent of test_first
        self.assertTrue(self.user.is_active)
```

---

## Testing Tools

### Pytest
- Fixtures for setup/teardown
- Markers for categorization
- Parametrize for data-driven tests
- Plugins (pytest-cov, pytest-django)

### Coverage.py
- Line and branch coverage
- HTML reports
- Missing line identification

### Django TestCase
- Transaction wrapping
- Test client for HTTP requests
- Fixture loading
- Database management

### unittest.mock
- Mock objects
- Patch decorator
- Call assertions
- Side effects

---

## Quick Reference

### Run All IDOR Tests
```bash
pytest apps/*/tests/test_idor_security.py -v
```

### Run Service Layer Tests
```bash
pytest tests/peoples/services/ -v
```

### Run with Coverage
```bash
pytest --cov=apps --cov-report=html -v
```

### Run Security Tests Only
```bash
pytest -m security -v
```

### Run Performance Tests (Slow)
```bash
pytest -m performance -v
```

---

## Related Documentation

- [IDOR Test Coverage Report](../../IDOR_TEST_COVERAGE_REPORT.md) - 141 tests across 5 apps
- [Service Layer Tests Summary](../../SERVICE_LAYER_TESTS_IMPLEMENTATION_SUMMARY.md) - 110+ service tests
- [Testing & Quality Guide](TESTING_AND_QUALITY_GUIDE.md) - Code quality standards
- [Ontology Testing Knowledge](../../apps/ontology/registrations/testing_knowledge_nov_2025.py) - 50+ testing concepts

---

**Created:** November 6, 2025  
**Author:** Amp AI Agent  
**Coverage:** 250+ tests documented  
**Next Step:** Apply these patterns to new feature development
