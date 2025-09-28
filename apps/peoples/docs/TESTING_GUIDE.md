# Peoples App Testing Guide

## Test Structure

### Service Layer Tests (apps/peoples/tests/test_services/)

```bash
python -m pytest apps/peoples/tests/test_services/ -v --cov=apps/peoples/services
```

**Test Files:**
- `test_people_management_service.py` - CRUD operations, encryption, pagination
- `test_capability_management_service.py` - Capability operations
- `test_group_management_service.py` - Group management
- `test_site_group_service.py` - Site group operations
- `test_password_service.py` - Password management
- `test_email_verification_service.py` - Email verification workflow

**Markers Used:**
- `@pytest.mark.unit` - Fast unit tests with mocking
- `@pytest.mark.integration` - Tests with real database
- `@pytest.mark.django_db` - Django database access

### View Integration Tests (apps/peoples/tests/test_views/)

```bash
python -m pytest apps/peoples/tests/test_views/test_refactored_people_views.py -v
```

**Coverage:**
- HTTP request/response handling
- Service integration validation
- Authentication/authorization enforcement
- Form validation and error handling

### Security Tests (apps/peoples/tests/test_security/)

```bash
python -m pytest apps/peoples/tests/test_security/test_view_refactoring_security.py -v -m security
```

**Test Scenarios:**
- SQL injection protection
- XSS protection
- CSRF enforcement
- Authentication requirements

## Running Tests

### Quick Test Commands

```bash
python -m pytest apps/peoples/tests/test_services/ -v

python -m pytest apps/peoples/tests/ -m unit -v

python -m pytest apps/peoples/tests/ -m integration -v

python -m pytest apps/peoples/tests/ -m security -v

python -m pytest apps/peoples/tests/ --cov=apps/peoples --cov-report=html
```

### Expected Coverage

- **Service layer:** > 85% coverage target
- **View layer:** > 75% coverage target (HTTP handling)
- **Overall:** > 80% coverage

## Test Fixtures

Located in `apps/peoples/tests/conftest.py`:
- Tenant, BU, Typeassist fixtures
- User creation helpers
- Session management helpers

## Success Criteria

✅ All tests pass
✅ Coverage > 80%
✅ No security test failures
✅ Performance tests within acceptable limits