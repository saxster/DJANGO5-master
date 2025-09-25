# Critical Components Documentation

This directory contains detailed documentation for critical components and libraries used in the YOUTILITY5 project. Each document provides comprehensive information about how the component is integrated, configured, and used throughout the codebase.

## Core Components

### Data Validation & Serialization
- [**Pydantic Usage**](./pydantic_usage.md) - Type validation for GraphQL APIs, schema definitions, and error handling

### To Be Documented

#### API Layer
- [ ] **GraphQL (Graphene-Django)** - GraphQL API implementation, schema design, resolvers
- [ ] **Django REST Framework** - REST API endpoints, serializers, viewsets
- [ ] **django-graphql-jwt** - JWT authentication for GraphQL

#### Database & ORM
- [ ] **PostgreSQL with PostGIS** - Spatial database features, performance optimization
- [ ] **Django ORM Patterns** - Custom managers, query optimization, migrations
- [ ] **Redis Caching** - Cache strategies, session storage, Celery broker

#### Background Processing
- [ ] **Celery** - Async task processing, scheduling, monitoring
- [ ] **Celery Beat** - Periodic tasks, cron jobs
- [ ] **Django Celery Results** - Task result backend

#### Authentication & Security
- [ ] **Django Authentication** - Custom user model, permissions, groups
- [ ] **JWT Tokens** - Token generation, validation, refresh
- [ ] **Security Middleware** - XSS protection, CSRF, rate limiting

#### Frontend Integration
- [ ] **Bootstrap 5** - UI components, responsive design
- [ ] **jQuery** - DOM manipulation, AJAX
- [ ] **Select2** - Enhanced dropdowns, search functionality
- [ ] **WebSockets** - Real-time updates, notifications

#### File Handling
- [ ] **WeasyPrint** - PDF generation from HTML
- [ ] **django-import-export** - Data import/export, CSV/Excel handling
- [ ] **Pillow** - Image processing, thumbnails

#### AI/ML Components
- [ ] **Transformers** - NLP models, text analysis
- [ ] **Torch** - Deep learning framework
- [ ] **spaCy** - Natural language processing
- [ ] **DeepFace** - Face recognition, biometric authentication

#### Monitoring & Logging
- [ ] **Python Logging** - Log configuration, handlers, formatters
- [ ] **Django Debug Toolbar** - Development debugging
- [ ] **Error Tracking** - Exception handling, error reporting

#### Testing
- [ ] **Pytest** - Test framework, fixtures, markers
- [ ] **Coverage.py** - Code coverage reporting
- [ ] **Factory Boy** - Test data generation

## Documentation Standards

Each component documentation should include:

1. **Overview** - What the component does and why it's used
2. **Installation** - Package versions and dependencies
3. **Configuration** - Settings and environment variables
4. **Architecture** - How it fits into the system
5. **Usage Patterns** - Common implementation patterns
6. **Code Examples** - Real examples from the codebase
7. **Best Practices** - Do's and don'ts
8. **Testing** - How to test the component
9. **Troubleshooting** - Common issues and solutions
10. **Related Documentation** - Links to other relevant docs

## Contributing

When documenting a new component:

1. Create a new markdown file: `component_name.md`
2. Follow the documentation standards above
3. Include real code examples from the project
4. Add the component to this README index
5. Cross-reference with related components

## Quick Reference

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| Pydantic | API input validation | `/apps/service/pydantic_schemas/` |
| Celery | Background tasks | `/background_tasks/`, `celery.py` |
| GraphQL | API layer | `/apps/service/queries/`, `schema.py` |
| Redis | Caching & queues | `settings.py`, cache backends |
| PostgreSQL | Primary database | Models in `/apps/*/models/` |

## Project Structure Reference

```
YOUTILITY5/
├── apps/                    # Django applications
│   ├── service/            # API service layer
│   │   ├── pydantic_schemas/  # Pydantic validation
│   │   ├── queries/           # GraphQL queries
│   │   └── mutations/         # GraphQL mutations
│   ├── core/               # Core utilities
│   └── [other apps]/       # Domain-specific apps
├── background_tasks/       # Celery tasks
├── intelliwiz_config/      # Django settings
├── frontend/              # Static files & templates
└── docs/                  # Documentation
    └── critical_components/  # This directory
```

## Useful Commands

```bash
# Check installed versions
pip list | grep -E "pydantic|celery|graphene|redis"

# Run tests for a component
pytest apps/service/tests/ -v

# Check component configuration
python manage.py shell
>>> from django.conf import settings
>>> settings.INSTALLED_APPS  # Check installed apps
```