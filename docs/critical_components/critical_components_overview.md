# Critical Components Overview - YOUTILITY5

Based on analysis of the codebase, here are the critical components that form the backbone of the YOUTILITY5 application:

## 1. API Layer Components

### GraphQL (Graphene-Django) ⭐⭐⭐⭐⭐
- **Location**: `/apps/service/schema.py`, `/apps/api/graphql/`
- **Purpose**: Primary API interface for mobile and web clients
- **Critical Features**:
  - JWT authentication via `graphql-jwt`
  - Pydantic validation for inputs
  - Custom queries and mutations
  - DataLoaders for N+1 query optimization

### Django REST Framework ⭐⭐⭐⭐
- **Location**: `/apps/api/`
- **Purpose**: REST API endpoints for legacy integrations
- **Critical Features**:
  - Token authentication
  - API documentation via drf-spectacular
  - API key authentication

## 2. Database & ORM

### PostgreSQL with PostGIS ⭐⭐⭐⭐⭐
- **Engine**: `django.contrib.gis.db.backends.postgis`
- **Purpose**: Primary database with geospatial capabilities
- **Critical Features**:
  - Spatial queries for location-based features
  - Multi-tenant data isolation
  - Connection pooling

### Custom Model Architecture ⭐⭐⭐⭐⭐
- **BaseModel & TenantAwareModel**
  - Location: `/apps/peoples/models.py`
  - Automatic tracking: `cdtz`, `mdtz`, `cuser`, `muser`
  - Tenant isolation per business unit

### Manager Pattern ⭐⭐⭐⭐⭐
- **Three-tier approach**:
  1. Standard managers (basic CRUD)
  2. ORM-optimized managers (select_related/prefetch_related)
  3. Cached managers (Redis integration)
- **Examples**:
  - `/apps/activity/managers/job_manager.py`
  - `/apps/activity/managers/job_manager_orm_optimized.py`

## 3. Background Processing

### Celery ⭐⭐⭐⭐⭐
- **Configuration**: `/intelliwiz_config/celery.py`
- **Broker**: Redis (`redis://127.0.0.1:6379/`)
- **Result Backend**: `django-db`
- **Scheduled Tasks**:
  - PPM schedule creation
  - Reminder emails
  - Auto-close jobs
  - Ticket escalation
  - Report generation

### Celery Beat ⭐⭐⭐⭐
- **Purpose**: Periodic task scheduling
- **Key schedules**:
  - Every 30 min: Auto-close jobs, ticket escalation
  - Every 8 hours: Reminders, job creation
  - Weekly: Media cloud storage migration

## 4. Caching

### Redis ⭐⭐⭐⭐⭐
- **Location**: `redis://127.0.0.1:6379/1`
- **Cache Backend**: `django_redis.cache.RedisCache`
- **Key Prefix**: `youtility4`
- **TTL**: 60 seconds (configurable)
- **Usage**: Session storage, query caching, Celery broker

## 5. Authentication & Security

### Custom User Model ⭐⭐⭐⭐⭐
- **Model**: `peoples.People`
- **Features**:
  - Email verification
  - Multi-user same email support
  - Role-based permissions

### JWT Authentication ⭐⭐⭐⭐⭐
- **Library**: `graphql-jwt`
- **Token Expiry**: 5 minutes
- **Refresh Token**: 7 days
- **Used in**: GraphQL API

### Security Middleware ⭐⭐⭐⭐⭐
- **Custom Middleware**:
  - `SQLInjectionProtectionMiddleware`
  - `XSSProtectionMiddleware`
  - `CorrelationIDMiddleware`
- **Location**: `/apps/core/`

## 6. Data Import/Export

### django-import-export ⭐⭐⭐⭐
- **Purpose**: Bulk data operations
- **Features**:
  - CSV/Excel import/export
  - Custom resource classes
  - Validation hooks
  - Transaction management

## 7. File & Media Handling

### WeasyPrint ⭐⭐⭐
- **Purpose**: PDF generation from HTML
- **Usage**: Reports, invoices, documents

### WhiteNoise ⭐⭐⭐
- **Purpose**: Static file serving
- **Middleware**: `whitenoise.middleware.WhiteNoiseMiddleware`

## 8. Multi-Tenancy

### Tenant System ⭐⭐⭐⭐⭐
- **Middleware**: `TenantMiddleware` (currently disabled)
- **Router**: `TenantDbRouter`
- **Model**: All models inherit tenant awareness
- **Isolation**: Business unit (buid) based

## 9. Real-time Features

### MQTT Integration ⭐⭐⭐
- **Purpose**: IoT device communication
- **Library**: `paho-mqtt`
- **Usage**: Real-time sensor data, alerts

### WebSockets ⭐⭐⭐
- **Purpose**: Real-time updates
- **Usage**: Live notifications, status updates

## 10. Frontend Integration

### Django Templates ⭐⭐⭐⭐
- **Location**: `/frontend/templates/`
- **Engine**: Django template system with Bootstrap 5

### Select2 ⭐⭐⭐
- **Purpose**: Enhanced dropdowns
- **Cache**: Dedicated Redis cache

## 11. Email System

### Django Email Verification ⭐⭐⭐⭐
- **Library**: `django-email-verification`
- **Features**:
  - Token-based verification
  - Multi-user same email support
  - Custom callbacks

### AWS SES ⭐⭐⭐
- **Library**: `django-ses`
- **Purpose**: Production email sending

## 12. Monitoring & Logging

### Python Logging ⭐⭐⭐⭐⭐
- **Loggers**:
  - `general`: General application logs
  - `errors`: Error tracking
  - `debug`: Debug information
  - `mobile_service_log`: Mobile API logs

## 13. Testing Infrastructure

### Pytest ⭐⭐⭐⭐⭐
- **Configuration**: `pytest.ini`
- **Coverage**: `pytest-cov`
- **Django Integration**: `pytest-django`
- **Fixtures**: App-specific `conftest.py`

## 14. AI/ML Components

### Transformers & Torch ⭐⭐⭐
- **Libraries**: `transformers==4.44.0`, `torch==2.4.0`
- **Purpose**: NLP and deep learning features

### spaCy ⭐⭐⭐
- **Version**: `3.7.6`
- **Purpose**: Natural language processing

### DeepFace ⭐⭐⭐
- **Version**: `0.0.93`
- **Purpose**: Face recognition, biometric authentication

## 15. Service Layer

### Service Classes ⭐⭐⭐⭐
- **Pattern**: Business logic abstraction
- **Example**: `/apps/core/services/geofence_service.py`
- **Purpose**: Keep views thin, testable business logic

## 16. Forms & Validation

### SecureFormMixin ⭐⭐⭐⭐
- **Purpose**: XSS protection on all forms
- **Location**: Forms throughout apps

## Priority Ranking

⭐⭐⭐⭐⭐ **Critical** - Core functionality depends on it
⭐⭐⭐⭐ **Important** - Major features require it
⭐⭐⭐ **Moderate** - Enhances functionality but not essential

## Documentation Priority

1. **GraphQL/Graphene** - Primary API
2. **Celery & Redis** - Background processing & caching
3. **Custom Model Architecture** - Foundation of data layer
4. **Manager Pattern** - Query optimization
5. **Security Middleware** - Critical for protection
6. **Multi-tenancy** - Business isolation
7. **Service Layer** - Business logic patterns
8. **Import/Export** - Data management
9. **Testing Infrastructure** - Quality assurance
10. **AI/ML Components** - Advanced features