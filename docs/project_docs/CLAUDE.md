# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Running Tests
```bash
# Run all tests with pytest
pytest

# Run specific app tests with Django settings
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/activity/tests/

# Run specific test file
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/peoples/tests/test_views/test_authentication_comprehensive.py -v

# Run specific test class
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/peoples/tests/test_views/test_authentication_comprehensive.py::TestPasswordManagement -v

# Run specific test method
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/peoples/tests/test_views/test_authentication_comprehensive.py::TestPasswordManagement::test_change_password_weak -v

# Run tests with coverage
pytest --cov=apps --cov-report=html

# Run tests matching pattern
pytest -k "test_authentication"

# Quick test collection check
pytest --collect-only
```

### Development Server
```bash
# Start development server
python manage.py runserver

# With specific settings (production)
python manage.py runserver --settings=intelliwiz_config.settings_production
```

### Database Operations
```bash
# Apply migrations
python manage.py migrate

# Create migrations for specific app
python manage.py makemigrations [app_name]

# Show migration status
python manage.py showmigrations

# Database shell
python manage.py dbshell

# Create superuser
python manage.py createsuperuser
```

### Code Quality
```bash
# Format code with black (120 character line length)
black apps/ --line-length 120

# Lint with flake8
flake8 apps/ --max-line-length=120

# Type checking
mypy apps/ --ignore-missing-imports

# Security scan
bandit -r apps/
```

## High-Level Architecture

### Modular Application Structure
The codebase follows a strict modular pattern where each Django app is self-contained with its own subdirectories for models, views, forms, managers, services, and tests. This separation ensures maintainability and clear boundaries between components.

```
apps/[app_name]/
├── models/           # Split into separate files per model
├── views/            # Split into logical view groups
├── forms/            # Form definitions
├── managers/         # Custom model managers
│   ├── standard/     # Basic CRUD operations
│   └── optimized/    # Performance-optimized with select_related/prefetch_related
├── services/         # Business logic layer
├── tests/            # Organized by component type
│   ├── test_models/
│   ├── test_views/
│   ├── test_forms/
│   └── test_services/
└── utils.py          # App-specific utilities
```

### Multi-Tenant Architecture
All models inherit from `TenantAwareModel` or `BaseModel`, providing automatic tracking of creation/modification timestamps (`cdtz`, `mdtz`) and users (`cuser`, `muser`). This enables comprehensive audit trails and tenant isolation.

### Service Layer Pattern
Business logic is extracted into service classes, keeping views thin and testable:
- `AuthenticationService` handles login/logout/session management
- Each app has its own service layer for domain-specific operations
- Services coordinate between models, external APIs, and business rules

### Manager Strategy
Three-tier manager approach for database operations:
1. **Standard Managers**: Basic CRUD without optimization
2. **ORM-Optimized Managers**: Use `select_related()` and `prefetch_related()` for known query patterns
3. **Cached Managers**: Frequently accessed data with Redis caching

### Import/Export System
Comprehensive data import/export using `django-import-export`:
- Resource classes for each model defining import/export behavior
- Separate Update resources for handling edits vs creates
- Custom validation hooks in resource classes
- Bulk operations support with transaction management

### Security Architecture
- Custom `SecureFormMixin` for XSS protection on all forms
- Input validation in `apps/core/validation/`
- SQL injection prevention through parameterized queries
- Rate limiting on authentication endpoints
- Session management with timezone awareness

### Testing Strategy
- Tests organized by component type within each app
- `conftest.py` files provide app-specific fixtures
- `pytest.ini` configured with Django settings and test markers
- Reusable test database with `--reuse-db` flag
- Test markers for categorization: `@pytest.mark.slow`, `@pytest.mark.security`

### CRITICAL: Test Failure Resolution
**When tests fail, ALWAYS follow this order:**
1. **First** - Examine the test to understand what it expects
2. **Second** - Verify if the test expectations are correct and match requirements
3. **Third** - Fix the test if expectations are wrong
4. **Last** - Only modify implementation code if the test correctly identifies a bug

**Never assume implementation is wrong just because a test fails. Tests can have:**
- Incorrect assertions
- Wrong expected values
- Invalid test data setup
- Outdated expectations after requirements change

### CRITICAL: No Stub Code Policy
**NEVER write placeholder/stub code. ALL code must be complete and functional:**

❌ **NEVER DO THIS:**
```python
def process_data(self, data):
    # TODO: Implement this
    pass

def calculate_total(self, items):
    # Stub implementation
    return 0
```

✅ **ALWAYS DO THIS:**
```python
def process_data(self, data):
    if not data:
        return []

    processed = []
    for item in data:
        processed.append({
            'id': item.get('id'),
            'value': item.get('value', 0) * 1.1,
            'status': 'processed'
        })
    return processed

def calculate_total(self, items):
    if not items:
        return Decimal('0.00')

    total = sum(Decimal(str(item.get('price', 0))) * item.get('quantity', 0)
                for item in items)
    return total.quantize(Decimal('0.01'))
```

**Requirements:**
- Every function must have a complete implementation
- Handle edge cases (None, empty inputs, invalid data)
- Return appropriate values, never just `pass` or `return None` without logic
- If unsure about requirements, ask for clarification rather than writing stubs

### CRITICAL: Test-After-Feature Policy
**ALWAYS write tests immediately after implementing any new feature or fixing a bug:**

**Development Flow:**
1. **Implement the feature** - Complete, functional code
2. **Write comprehensive tests** - Cover all code paths
3. **Run the tests** - Ensure they pass
4. **Verify edge cases** - Add tests for boundary conditions

**Example Workflow:**
```python
# Step 1: Implement feature in apps/activity/services/asset_service.py
class AssetService:
    def calculate_depreciation(self, asset, years):
        if not asset or years <= 0:
            return Decimal('0.00')

        initial_value = Decimal(str(asset.purchase_price))
        salvage_value = Decimal(str(asset.salvage_value or 0))
        depreciation = (initial_value - salvage_value) / Decimal(str(years))
        return depreciation.quantize(Decimal('0.01'))

# Step 2: Immediately write test in apps/activity/tests/test_services/test_asset_service.py
import pytest
from decimal import Decimal
from apps.activity.services.asset_service import AssetService

class TestAssetService:
    def test_calculate_depreciation_valid(self):
        service = AssetService()
        asset = Mock(purchase_price=10000, salvage_value=1000)

        result = service.calculate_depreciation(asset, 5)

        assert result == Decimal('1800.00')

    def test_calculate_depreciation_no_salvage(self):
        service = AssetService()
        asset = Mock(purchase_price=5000, salvage_value=None)

        result = service.calculate_depreciation(asset, 10)

        assert result == Decimal('500.00')

    def test_calculate_depreciation_invalid_years(self):
        service = AssetService()
        asset = Mock(purchase_price=10000, salvage_value=1000)

        result = service.calculate_depreciation(asset, 0)

        assert result == Decimal('0.00')

    def test_calculate_depreciation_no_asset(self):
        service = AssetService()

        result = service.calculate_depreciation(None, 5)

        assert result == Decimal('0.00')
```

**Test Coverage Requirements:**
- **Happy path** - Normal, expected usage
- **Edge cases** - Boundary values, None, empty inputs
- **Error cases** - Invalid inputs, exceptions
- **Integration** - If the feature interacts with other components

**Where to Place Tests:**
- Service methods → `apps/[app_name]/tests/test_services/`
- Model methods → `apps/[app_name]/tests/test_models/`
- View functions → `apps/[app_name]/tests/test_views/`
- Forms → `apps/[app_name]/tests/test_forms/`
- API endpoints → `apps/[app_name]/tests/test_api/`

**Running Tests After Writing:**
```bash
# Run the new test immediately
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/activity/tests/test_services/test_asset_service.py -v

# Run all tests for the app to ensure nothing broke
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings pytest apps/activity/tests/ -v
```

### Response Handling Pattern
Consistent use of `django.http.response as rp` shorthand across views:
```python
import django.http.response as rp

def view_function(request):
    return rp.JsonResponse({'status': 'success'})
```

### Logging Strategy
Multiple specialized loggers for different concerns:
```python
import logging
logger = logging.getLogger('general')
error_logger = logging.getLogger('errors')
debug_logger = logging.getLogger('debug')
```

### Database Performance
- PostgreSQL with PostGIS for geospatial data
- Strategic indexing defined in model Meta classes
- Query optimization through custom managers
- Iterator pattern for large datasets: `Model.objects.all().iterator()`
- Connection pooling configured in settings

### Cross-App Communication
Apps communicate through well-defined interfaces:
- Scheduler app imports Job models from Activity app
- Reports app aggregates data from multiple apps
- Avoid circular dependencies by using string references in ForeignKeys

### Configuration Management
- Base settings in `intelliwiz_config/settings.py`
- Production overrides in `intelliwiz_config/settings_production.py`
- Environment-specific configs in `intelliwiz_config/envs/`
- `DJANGO_SETTINGS_MODULE` defaults to `intelliwiz_config.settings`

### Frontend Integration
- Bootstrap 5 for UI components
- jQuery for DOM manipulation
- Select2 for enhanced dropdowns
- WebSocket support for real-time updates
- Static files served from `frontend/static/`
- Templates in `frontend/templates/` and app-specific `templates/`

### Background Processing
- Celery for async tasks
- Task definitions in `background_tasks/`
- Redis as message broker
- Scheduled tasks via Celery Beat

### API Architecture
- REST API endpoints in `apps/api/`
- GraphQL support via Graphene
- API documentation at `/api/docs/`
- Version-prefixed URLs: `/api/v1/`

### Utility Organization
Two-tier utility structure in core app:
- `apps/core/utils.py` - Legacy utilities (avoid modifying)
- `apps/core/utils_new/` - New modular utilities:
  - `validators.py` - Input validation functions
  - `helpers.py` - General helper functions
  - `decorators.py` - Custom decorators

### Real-time Features
- MQTT client for IoT communication
- WebSocket support for live updates
- Real-time monitoring and alerts
- Event-driven architecture for notifications

### AI Integration
Dedicated AI apps with specialized purposes:
- `ai_core/` - Central AI orchestration
- `face_recognition/` - Biometric authentication
- `nlp_engine/` - Natural language processing
- `insights_engine/` - Data analysis and insights
- `anomaly_detection/` - Real-time anomaly detection
- `behavioral_analytics/` - User behavior analysis