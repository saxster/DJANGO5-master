# Project Structure & Organization

## Directory Layout

```
YOUTILITY5/
├── apps/                           # Django applications (business logic)
├── intelliwiz_config/              # Django project configuration
├── frontend/                       # Frontend assets and templates
├── background_tasks/               # Celery task definitions
├── monitoring/                     # System monitoring and metrics
├── tests/                          # Test suite and fixtures
├── scripts/                        # Utility and deployment scripts
├── docs/                          # Project documentation
├── config/                        # External service configurations
├── deploy/                        # Deployment files and Docker configs
├── requirements/                   # Python dependencies
└── logs/                          # Application logs
```

## Core Applications Structure

### Business Domain Apps

#### `apps/peoples/` - User Management & Authentication
- **Purpose**: User profiles, authentication, groups, and capabilities
- **Key Models**: People (custom user), Pgroup, Pgbelonging, Capability
- **Naming**: Custom user model extends AbstractBaseUser with tenant isolation

#### `apps/onboarding/` - Client & Site Management
- **Purpose**: Multi-tenant client setup, business units, type configuration
- **Key Models**: Bt (business units), TypeAssist (configuration types)
- **Naming**: "Bt" represents business units/clients, "TypeAssist" for categorization

#### `apps/activity/` - Assets & Operations
- **Purpose**: Asset lifecycle, locations, jobs, questions, device events
- **Key Models**: Asset, Location, Job, Question, DeviceEvent
- **Naming**: Central hub for all operational activities and asset management

#### `apps/attendance/` - People Tracking
- **Purpose**: Attendance tracking, geofencing, SOS functionality
- **Key Models**: Attendance, Geofence, SosAlert
- **Features**: Real-time location tracking, AI-enhanced fraud detection

#### `apps/scheduler/` - Task Scheduling
- **Purpose**: Tour scheduling, PPM (Preventive Maintenance), task automation
- **Key Models**: Schedule, Tour, Task, JobNeed
- **Note**: Intentional spelling "scheduler" (legacy naming convention)

#### `apps/reports/` - Document Generation
- **Purpose**: PDF generation, scheduled reporting, custom templates
- **Structure**: `report_designs/` contains PDF templates
- **Features**: WeasyPrint integration, automated report delivery

### Technical Apps

#### `apps/service/` - API Layer
- **Purpose**: GraphQL API for mobile applications
- **Structure**:
  - `queries/` - GraphQL query resolvers
  - `mutations.py` - GraphQL mutations
  - `types.py` - GraphQL type definitions
  - `pydantic_schemas/` - Data validation schemas
- **Endpoints**: `/graphql/` main API, `/api/` REST endpoints

#### `apps/core/` - Shared Utilities
- **Purpose**: Cross-cutting concerns, middleware, utilities
- **Key Components**:
  - `middleware/` - Custom middleware (rate limiting, security)
  - `cache/` - Caching strategies and implementations
  - `utils.py` - Shared utility functions
  - `models.py` - Base models and security models

#### `apps/face_recognition/` - AI Services
- **Purpose**: Biometric authentication and AI processing
- **Features**: Face recognition, enhanced security, analytics integration

## Configuration Structure

### Settings Organization
```
intelliwiz_config/
├── settings.py              # Main settings file
├── settings_ia.py          # Information architecture settings
├── settings_local.py       # Local development overrides
├── settings_test.py        # Test-specific settings
├── envs/                   # Environment-specific configurations
│   ├── .env.dev           # Development environment
│   ├── .env.dev.secure    # Secure development
│   ├── .env.prod          # Production environment
│   └── .env.prod.secure   # Secure production
├── urls.py                # Main URL configuration
├── urls_clean.py          # Clean URL patterns
├── urls_optimized.py      # Optimized URL routing
└── jinja/                 # Jinja2 template configuration
```

### Frontend Organization
```
frontend/
├── static/
│   └── assets/
│       ├── css/           # Stylesheets
│       ├── js/            # JavaScript files
│       ├── images/        # Static images
│       └── plugins/       # Third-party plugins
└── templates/
    ├── globals/           # Global templates
    ├── base/              # Base templates
    └── [app_name]/        # App-specific templates
```

## Naming Conventions

### Python Code
- **Classes**: PascalCase (`AssetManager`, `PeopleModel`)
- **Functions/Methods**: snake_case (`get_asset_by_code`, `create_user`)
- **Variables**: snake_case (`user_profile`, `asset_list`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRY_ATTEMPTS`, `DEFAULT_TIMEOUT`)

### Database Tables
- **Models**: Use `db_table` to specify explicit table names
- **Convention**: Lowercase with underscores (`people`, `asset_maintenance`)
- **Constraints**: Descriptive names (`people_loginid_bu_uk`)

### File Organization
- **Models**: Split large models into `models/` directory with `__init__.py`
- **Views**: Use `views/` directory for complex apps
- **Forms**: Separate forms by functionality (`forms/user_forms.py`)
- **Tests**: Mirror app structure in `tests/` directory

### URL Patterns
- **Modern URLs**: Use path() with descriptive names
- **Naming**: `app_name:view_name` pattern (`people:user_list`)
- **Parameters**: Use typed parameters (`<int:user_id>`, `<str:asset_code>`)

## Multi-Tenant Architecture

### Tenant Isolation
- **Base Model**: All models inherit from `TenantAwareModel`
- **Filtering**: Automatic tenant filtering in managers
- **Middleware**: `TenantMiddleware` handles tenant context

### Database Design
- **Client Field**: Every model has `client` foreign key to `Bt` model
- **Constraints**: Unique constraints include client for proper isolation
- **Queries**: All queries automatically filtered by tenant

## Security Patterns

### Authentication & Authorization
- **Custom User Model**: `People` model with enhanced security
- **Rate Limiting**: PostgreSQL-based rate limiting in `apps/core/models.py`
- **Capabilities**: Role-based access control via `Capability` model

### Data Protection
- **Encrypted Fields**: Use `SecureString` for sensitive data
- **Audit Logging**: Track user actions and data changes
- **Session Security**: Secure session configuration with Redis backend

## Testing Structure

### Test Organization
```
tests/
├── conftest.py            # Pytest fixtures and configuration
├── factories/             # Factory classes for test data
├── integration/           # Integration tests
├── performance/           # Performance and load tests
├── security/              # Security-specific tests
├── api/                   # API endpoint tests
└── [app_name]/           # App-specific test modules
```

### Test Patterns
- **Fixtures**: Comprehensive fixtures in `conftest.py`
- **Factories**: Use factory classes for consistent test data
- **Markers**: Use pytest markers for test categorization
- **Coverage**: Maintain high test coverage for critical paths

## Documentation Standards

### Code Documentation
- **Docstrings**: Use Google-style docstrings for functions and classes
- **Comments**: Explain business logic and complex algorithms
- **Type Hints**: Use type hints for better code clarity

### API Documentation
- **GraphQL**: Self-documenting via GraphQL introspection
- **REST**: Use DRF's built-in documentation features
- **Examples**: Provide usage examples in docstrings

## Development Workflow

### Branch Strategy
- **Feature Branches**: `feature/description`
- **Bug Fixes**: `bugfix/description`
- **Security**: `security/description`

### Code Quality
- **Linting**: Follow PEP 8 standards
- **Testing**: All new code requires tests
- **Security**: Security review for sensitive changes
- **Performance**: Consider performance impact of changes