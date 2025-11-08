# Testing Knowledge Ontology - Quick Start Guide

**Fast access to testing patterns and best practices**

---

## Load Testing Knowledge

```python
# Load all 50+ testing concepts into ontology registry
from apps.ontology.registrations.testing_knowledge_nov_2025 import register_testing_knowledge

count = register_testing_knowledge()
print(f"✅ Registered {count} testing knowledge concepts")
```

---

## Query Testing Patterns

### Get IDOR Testing Guidance

```python
from apps.ontology.registry import OntologyRegistry

# Get IDOR testing concept
idor = OntologyRegistry.get("testing.security.idor_testing")

print(f"Purpose: {idor['purpose']}")
print(f"\nExamples:")
for example in idor['examples']:
    print(f"  - {example}")

print(f"\nTest Files:")
for file in idor['file_references']:
    print(f"  - {file}")

# Output:
# Purpose: Insecure Direct Object Reference vulnerability testing - verifies users cannot access resources by ID manipulation
# 
# Examples:
#   - test_user_cannot_access_other_tenant_user_profile
#   - test_user_cannot_edit_other_tenant_attendance
#   - test_sequential_id_enumeration_prevention
# 
# Test Files:
#   - apps/peoples/tests/test_idor_security.py
#   - apps/attendance/tests/test_idor_security.py
#   - apps/activity/tests/test_idor_security.py
#   - apps/work_order_management/tests/test_idor_security.py
#   - apps/y_helpdesk/tests/test_idor_security.py
#   - IDOR_TEST_COVERAGE_REPORT.md
```

---

### Find All Security Testing Patterns

```python
from apps.ontology.registry import OntologyRegistry

# Get all security testing concepts
security_tests = OntologyRegistry.get_by_domain("testing.security")

print(f"Found {len(security_tests)} security testing patterns:")
for test in security_tests:
    print(f"  - {test['qualified_name']}")
    print(f"    {test['purpose']}")

# Output:
# Found 15 security testing patterns:
#   - testing.security.idor_testing
#     Insecure Direct Object Reference vulnerability testing...
#   - testing.security.cross_tenant_testing
#     Multi-tenancy isolation testing...
#   - testing.security.permission_boundary_testing
#     Access control testing...
#   ... (and 12 more)
```

---

### Get Service Testing Patterns

```python
from apps.ontology.registry import OntologyRegistry

# Get service layer testing patterns
service_tests = OntologyRegistry.get_by_domain("testing.service")

for test in service_tests:
    print(f"\n{test['qualified_name']}")
    print(f"  Purpose: {test['purpose']}")
    if 'patterns' in test:
        print(f"  Patterns:")
        for pattern in test['patterns']:
            print(f"    - {pattern}")
```

---

### Find Antipatterns

```python
from apps.ontology.registry import OntologyRegistry

# Get all antipatterns
antipatterns = OntologyRegistry.get_by_type("antipattern")

print(f"Found {len(antipatterns)} testing antipatterns:")
for ap in antipatterns:
    print(f"\n❌ {ap['qualified_name']}")
    print(f"   Why bad: {ap['why_bad']}")
    print(f"   Fix: {ap['fix']}")

# Output:
# Found 10 testing antipatterns:
# 
# ❌ testing.antipatterns.testing_implementation_details
#    Why bad: Tests break when implementation changes, even if behavior is unchanged
#    Fix: Test behavior through public interfaces, not implementation details
# 
# ❌ testing.antipatterns.brittle_tests
#    Why bad: Tests become maintenance burden and lose developer trust
#    Fix: Use flexible assertions, test isolation, and avoid hard-coded values
# 
# ... (and 8 more)
```

---

### Search for Specific Pattern

```python
from apps.ontology.registry import OntologyRegistry

# Search for query count testing
results = OntologyRegistry.search("query count assertions")

if results:
    concept = results[0]
    print(f"Found: {concept['qualified_name']}")
    print(f"\nPurpose: {concept['purpose']}")
    print(f"\nPatterns:")
    for pattern in concept['patterns']:
        print(f"  - {pattern}")
```

---

## Test Examples Reference

### IDOR Security Tests (141 Total)

| App | File | Tests | Focus |
|-----|------|-------|-------|
| Peoples | `apps/peoples/tests/test_idor_security.py` | 24 | Cross-tenant profiles, admin escalation |
| Attendance | `apps/attendance/tests/test_idor_security.py` | 25 | GPS data, biometric security |
| Activity | `apps/activity/tests/test_idor_security.py` | 29 | Jobs, tasks, assets isolation |
| Work Orders | `apps/work_order_management/tests/test_idor_security.py` | 29 | Vendor isolation, approvals |
| Helpdesk | `apps/y_helpdesk/tests/test_idor_security.py` | 34 | Attachments, comments, escalation |

**Run all IDOR tests:**
```bash
pytest apps/*/tests/test_idor_security.py -v
```

---

### Service Layer Tests (110+ Total)

| Service | File | Tests | Focus |
|---------|------|-------|-------|
| DeviceTrustService | `tests/peoples/services/test_device_trust_service.py` | 35+ | Trust scoring, biometric validation |
| LoginThrottlingService | `tests/peoples/services/test_login_throttling_service.py` | 40+ | Rate limiting, brute force prevention |
| UserCapabilityService | `tests/peoples/services/test_user_capability_service.py` | 35+ | Permission management, AI flags |

**Run all service tests:**
```bash
pytest tests/peoples/services/ -v
```

---

## Common Testing Patterns

### IDOR Test Pattern

```python
class MyAppIDORTestCase(TestCase):
    def setUp(self):
        # Two tenants
        self.client_a = Client.objects.create(name='Tenant A')
        self.client_b = Client.objects.create(name='Tenant B')
        
        # Users in different tenants
        self.user_a = People.objects.create(username='a@test.com', client=self.client_a)
        self.user_b = People.objects.create(username='b@test.com', client=self.client_b)
    
    def test_cross_tenant_access_blocked(self):
        """Verify users cannot access other tenant's resources."""
        # Create resource for tenant A
        resource = MyModel.objects.create(name='Resource A', client=self.client_a)
        
        # Login as user from tenant B
        self.client.force_login(self.user_b)
        
        # Attempt access
        response = self.client.get(f'/mymodel/{resource.id}/')
        
        # Should be blocked
        self.assertIn(response.status_code, [403, 404])
```

---

### Service Layer Test Pattern

```python
from unittest.mock import patch, MagicMock

class MyServiceTest(TestCase):
    # Unit test with mocking
    @patch('apps.myapp.models.MyModel.objects.get')
    def test_service_method_with_mock(self, mock_get):
        mock_get.return_value = MagicMock(value=100)
        
        service = MyService()
        result = service.process(123)
        
        self.assertEqual(result, 100)
        mock_get.assert_called_once_with(id=123)
    
    # Integration test with real DB
    def test_service_method_integration(self):
        obj = MyModel.objects.create(value=100)
        
        service = MyService()
        result = service.process(obj.id)
        
        self.assertEqual(result, 100)
```

---

### Query Count Test Pattern

```python
from django.test.utils import override_settings
from django.db import connection

@override_settings(DEBUG=True)
def test_query_count_optimized(self):
    """Verify N+1 queries are prevented."""
    # Create 100 records
    for i in range(100):
        MyModel.objects.create(name=f'Item {i}')
    
    # Clear query log
    connection.queries_log.clear()
    
    # Query with optimization
    items = MyModel.objects.select_related('related').all()
    list(items)  # Force evaluation
    
    # Verify query count
    query_count = len(connection.queries)
    self.assertLessEqual(query_count, 3, f"N+1 detected: {query_count} queries")
```

---

## Test Organization

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

**Run by marker:**
```bash
# Unit tests only
pytest -m unit -v

# Security tests (not slow)
pytest -m "security and not performance" -v

# IDOR tests
pytest -m idor -v
```

---

### Test Coverage

**Generate coverage report:**
```bash
pytest --cov=apps \
    --cov-report=html:coverage_reports/html \
    --cov-report=term-missing \
    -v
```

**Coverage goals:**
- Overall: 80%+
- Security-critical: 90%+
- Service layer: 70%+

---

## Common Antipatterns to Avoid

### ❌ Testing Implementation Details
```python
# Bad: Testing private methods
def test_internal_calculation(self):
    result = self.service._calculate()  # Private method
    self.assertEqual(result, 100)

# Good: Testing behavior through public API
def test_process_result(self):
    result = self.service.process()
    self.assertEqual(result, 100)
```

---

### ❌ Brittle Tests
```python
# Bad: Hardcoded exact messages
def test_error(self):
    response = self.client.get('/invalid/')
    self.assertEqual(response.json()['error'], 'Invalid request: missing field "id"')

# Good: Flexible assertions
def test_error(self):
    response = self.client.get('/invalid/')
    self.assertEqual(response.status_code, 400)
    self.assertIn('error', response.json())
    self.assertIn('id', response.json()['error'].lower())
```

---

### ❌ Happy Path Only
```python
# Bad: Only testing success
def test_create_user(self):
    user = self.service.create_user('test@example.com')
    self.assertIsNotNone(user)

# Good: Test success + error cases
def test_create_user_success(self):
    user = self.service.create_user('test@example.com')
    self.assertIsNotNone(user)

def test_create_user_duplicate_email(self):
    self.service.create_user('test@example.com')
    with self.assertRaises(ValidationError):
        self.service.create_user('test@example.com')

def test_create_user_invalid_email(self):
    with self.assertRaises(ValidationError):
        self.service.create_user('not-an-email')
```

---

## Quick Commands

```bash
# Run all IDOR tests
pytest apps/*/tests/test_idor_security.py -v

# Run service layer tests
pytest tests/peoples/services/ -v

# Run with coverage
pytest --cov=apps --cov-report=html -v

# Run security tests only
pytest -m security -v

# Run specific app IDOR tests
pytest apps/peoples/tests/test_idor_security.py -v

# Run specific test
pytest apps/peoples/tests/test_idor_security.py::PeoplesIDORTestCase::test_user_cannot_access_other_tenant_user_profile -v
```

---

## Documentation Links

- **[Complete Deliverables](TESTING_KNOWLEDGE_ONTOLOGY_DELIVERABLES.md)** - Full summary
- **[Best Practices Guide](docs/testing/TESTING_BEST_PRACTICES_GUIDE.md)** - Comprehensive patterns
- **[IDOR Test Coverage](IDOR_TEST_COVERAGE_REPORT.md)** - 141 tests detailed
- **[Service Layer Tests](SERVICE_LAYER_TESTS_IMPLEMENTATION_SUMMARY.md)** - 110+ tests
- **[Testing & Quality Guide](docs/testing/TESTING_AND_QUALITY_GUIDE.md)** - Standards
- **[Ontology System](apps/ontology/README.md)** - Ontology usage

---

**Created:** November 6, 2025  
**Usage:** Reference guide for testing knowledge  
**Next:** Load ontology and query for specific patterns
