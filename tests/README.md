# Test Suite Organization

## 📁 Directory Structure

```
tests/
├── unit/                          # Fast, isolated unit tests
│   ├── test_question_id_implementation.py
│   └── test_question_logic.py
│
├── integration/                   # Integration tests with dependencies
│   ├── mqtt/                     # MQTT messaging tests
│   │   ├── test_mqtt_decompression.py
│   │   ├── test_mqtt_large.py
│   │   ├── test_mqtt_limits.py
│   │   └── test_mqtt_simple.py
│   │
│   ├── graphql/                  # GraphQL API tests
│   │   ├── test_corrected_graphql.py
│   │   ├── test_graphql_conditional_logic.py
│   │   └── test_graphql_json_fix.py
│   │
│   └── dependencies/             # Dependency & integration tests
│       ├── test_dependency_save.py
│       ├── test_dependency_ui_fixes.py
│       ├── test_web_dependency_save.py
│       └── test_web_dependency_ui.py
│
└── functional/                    # End-to-end functional tests
    ├── ui/                       # UI interaction tests
    │   ├── test_final_ui_fixes.py
    │   ├── test_javascript_debug.py
    │   └── test_null_pointer_fix.py
    │
    ├── escalation/               # Escalation feature tests
    │   ├── test_escalation_feature.py
    │   └── test_escalation_save.py
    │
    └── test_ticket_feature.py   # Ticket system tests
```

## 🎯 Test Categories

### Unit Tests (`/unit`)
- **Purpose**: Test individual components in isolation
- **Speed**: Fast (< 1 second per test)
- **Dependencies**: Minimal, use mocks
- **Examples**: Model methods, utility functions, validators

### Integration Tests (`/integration`)
- **Purpose**: Test component interactions
- **Speed**: Medium (1-10 seconds per test)
- **Dependencies**: Database, external services (mocked when possible)
- **Examples**: API endpoints, database operations, message queues

### Functional Tests (`/functional`)
- **Purpose**: Test complete user workflows
- **Speed**: Slow (> 10 seconds per test)
- **Dependencies**: Full system setup
- **Examples**: User registration flow, form submissions, UI interactions

## 🚀 Running Tests

### Run All Tests
```bash
# From project root
pytest tests/

# With coverage
pytest tests/ --cov=apps --cov-report=html
```

### Run Specific Categories
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Functional tests only
pytest tests/functional/
```

### Run Specific Feature Tests
```bash
# MQTT tests
pytest tests/integration/mqtt/

# GraphQL tests
pytest tests/integration/graphql/

# UI tests
pytest tests/functional/ui/

# Escalation tests
pytest tests/functional/escalation/
```

### Run Single Test File
```bash
pytest tests/integration/mqtt/test_mqtt_limits.py -v
```

### Run Tests Matching Pattern
```bash
pytest tests/ -k "mqtt" -v
pytest tests/ -k "graphql and not json" -v
```

## 📝 Writing Tests

### Test File Naming
- Prefix with `test_`
- Use descriptive names: `test_<feature>_<scenario>.py`
- Group related tests in subdirectories

### Test Function Naming
```python
def test_<unit>_<scenario>_<expected_result>():
    """Test that <unit> <expected behavior> when <scenario>."""
    pass
```

### Test Structure (AAA Pattern)
```python
def test_user_authentication_success():
    # Arrange - Set up test data
    user = create_test_user()
    credentials = {"username": "test", "password": "pass123"}

    # Act - Perform the action
    result = authenticate(credentials)

    # Assert - Verify the outcome
    assert result.is_authenticated
    assert result.user.id == user.id
```

## 🔧 Test Fixtures

### Common Fixtures
Located in `tests/conftest.py`:
```python
@pytest.fixture
def db_session():
    """Provides database session for tests."""

@pytest.fixture
def authenticated_client():
    """Provides authenticated test client."""

@pytest.fixture
def sample_data():
    """Provides sample test data."""
```

### Using Fixtures
```python
def test_with_fixtures(db_session, authenticated_client):
    # Use fixtures in your test
    response = authenticated_client.get('/api/endpoint/')
    assert response.status_code == 200
```

## 🎨 Test Markers

### Available Markers
```python
@pytest.mark.slow          # Tests taking > 10 seconds
@pytest.mark.integration   # Integration tests
@pytest.mark.unit          # Unit tests
@pytest.mark.mqtt          # MQTT-specific tests
@pytest.mark.graphql       # GraphQL-specific tests
@pytest.mark.ui            # UI tests
```

### Running Tests by Marker
```bash
# Run only slow tests
pytest -m slow

# Run all except slow tests
pytest -m "not slow"

# Run mqtt and integration tests
pytest -m "mqtt and integration"
```

## 📊 Coverage Reports

### Generate Coverage Report
```bash
# HTML report
pytest --cov=apps --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov=apps --cov-report=term-missing

# XML report (for CI)
pytest --cov=apps --cov-report=xml
```

### Coverage Goals
- Unit tests: > 90% coverage
- Integration tests: > 70% coverage
- Overall: > 80% coverage

## 🐛 Debugging Tests

### Verbose Output
```bash
pytest -vv tests/
```

### Show Print Statements
```bash
pytest -s tests/
```

### Debug on Failure
```bash
pytest --pdb tests/
```

### Run Last Failed
```bash
pytest --lf
```

### Run Failed First
```bash
pytest --ff
```

## ⚡ Performance Testing

### Benchmark Tests
```python
@pytest.mark.benchmark
def test_performance(benchmark):
    result = benchmark(expensive_function, arg1, arg2)
    assert result < threshold
```

### Load Tests
Located in `tests/performance/`:
- Use `locust` for load testing
- Monitor response times
- Check resource usage

## 🔒 Security Testing

### Security Test Categories
- Input validation
- Authentication/Authorization
- SQL injection prevention
- XSS protection
- CSRF protection

### Example Security Test
```python
@pytest.mark.security
def test_sql_injection_prevention():
    malicious_input = "'; DROP TABLE users; --"
    response = client.post('/api/search/', {'query': malicious_input})
    assert response.status_code == 400
    assert User.objects.count() > 0  # Table still exists
```

## 📋 Test Checklist

Before committing:
- [ ] All tests pass: `pytest`
- [ ] Coverage meets threshold: `pytest --cov=apps`
- [ ] No flaky tests: Run 3 times consecutively
- [ ] Tests are isolated: Can run individually
- [ ] Tests are documented: Clear names and docstrings
- [ ] Fixtures are reusable: Shared in conftest.py
- [ ] Markers are applied: For test categorization

## 🚨 Common Issues

### Database Not Found
```bash
# Create test database
pytest --create-db
```

### Import Errors
- Check PYTHONPATH includes project root
- Verify `__init__.py` files exist
- Check for circular imports

### Flaky Tests
- Use proper test isolation
- Mock time-dependent operations
- Use fixtures for consistent data

### Slow Tests
- Use pytest markers to separate slow tests
- Mock external API calls
- Use database transactions for cleanup

---

*Test suite maintained for YOUTILITY5 project*
*Follow pytest best practices and Django testing guidelines*