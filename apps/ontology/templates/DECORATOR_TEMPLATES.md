# Ontology Decorator Templates

**Purpose:** Copy-paste templates for adding @ontology decorators to different component types.

**Usage:** Copy the appropriate template, fill in the `[PLACEHOLDERS]`, and add to your file.

---

## Table of Contents

1. [Django Models](#django-models)
2. [Service Classes](#service-classes)
3. [Middleware](#middleware)
4. [API Views & ViewSets](#api-views--viewsets)
5. [Celery Tasks](#celery-tasks)
6. [Utility Functions](#utility-functions)

---

## Django Models

### Template: Basic Model

```python
from apps.ontology.decorators import ontology

@ontology(
    domain="[DOMAIN]",  # e.g., "people", "operations", "security", "reports"
    concept="[CONCEPT]",  # e.g., "User Authentication", "Task Management"
    purpose=(
        "[DETAILED PURPOSE - 2-3 sentences describing what this model does and why it exists]"
    ),
    criticality="[LEVEL]",  # critical, high, medium, low
    security_boundary=[True/False],  # True if handles auth, PII, or security
    models=[
        {
            "name": "[ModelName]",
            "purpose": "[What this model represents]",
            "pii_fields": ["[field1]", "[field2]"],  # List all PII fields
            "retention": "[Data retention policy]",
        },
    ],
    inputs=[
        {
            "name": "[field_name]",
            "type": "[field_type]",  # CharField, ForeignKey, DateField, etc.
            "description": "[What this field stores]",
            "required": [True/False],
            "sensitive": [True/False],  # True for PII
            "max_length": [value],  # For CharField
        },
        # Add more fields...
    ],
    outputs=[
        {
            "name": "[Model queryset or method]",
            "type": "[QuerySet/return type]",
            "description": "[What is returned]",
        },
    ],
    side_effects=[
        "[Database writes/updates]",
        "[Signals triggered]",
        "[Cache operations]",
        # Add more...
    ],
    depends_on=[
        "[apps.module.Model (relationship type)]",
        # Add dependencies...
    ],
    used_by=[
        "[apps.module.Service (how it's used)]",
        # Add consumers...
    ],
    tags=[
        "[tag1]", "[tag2]", "[tag3]",
        # e.g., "pii", "security", "authentication", "multi-tenant"
    ],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. [Security Aspect 1]:\n"
        "   - [Detail]\n"
        "   - [Detail]\n\n"
        "2. [Security Aspect 2]:\n"
        "   - [Detail]\n\n"
        "3. NEVER:\n"
        "   - [Anti-pattern 1]\n"
        "   - [Anti-pattern 2]"
    ),
    performance_notes=(
        "Database Indexes:\n"
        "- [index description]\n\n"
        "Query Patterns:\n"
        "- [query pattern]\n\n"
        "Performance Optimizations:\n"
        "- [optimization]"
    ),
    examples=[
        "# [Example 1 title]\n"
        "[code]\n",
        "# [Example 2 title]\n"
        "[code]\n",
    ],
)
class [ModelName](models.Model):
    # Model implementation...
```

### Template: Model with PII (GDPR Compliance)

```python
@ontology(
    domain="[DOMAIN]",
    concept="[CONCEPT]",
    purpose=(
        "[PURPOSE - mention GDPR compliance if handling PII]"
    ),
    criticality="critical",  # Always critical for PII
    security_boundary=True,  # Always True for PII
    models=[
        {
            "name": "[ModelName]",
            "purpose": "[Purpose]",
            "pii_fields": ["[field1]", "[field2]", "[field3]"],
            "retention": "[Retention policy - e.g., '90 days after account deletion (GDPR Article 17)']",
            "gdpr_compliance": [
                "Article 15: Right to access ([how implemented])",
                "Article 16: Right to rectification ([how implemented])",
                "Article 17: Right to erasure ([how implemented])",
            ],
        },
    ],
    inputs=[
        {
            "name": "[pii_field_name]",
            "type": "[type]",
            "description": "[description]",
            "required": [True/False],
            "sensitive": True,  # ALWAYS True for PII
            "gdpr_category": "[Personal data (Article 4) / Sensitive personal data (Article 9)]",
        },
        # More fields...
    ],
    # ... rest of decorator
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. PII Data Storage (GDPR):\n"
        "   - [field]: [GDPR category and usage]\n"
        "   - [field]: [GDPR category and usage]\n"
        "   - ALL fields subject to GDPR rights (access, rectification, erasure)\n\n"
        "2. GDPR Compliance:\n"
        "   - Article 15: [Right to access implementation]\n"
        "   - Article 16: [Right to rectification implementation]\n"
        "   - Article 17: [Right to erasure - retention policy]\n\n"
        "3. Access Controls:\n"
        "   - [Who can access]\n"
        "   - [Permission requirements]\n\n"
        "4. NEVER:\n"
        "   - Expose PII in public API responses\n"
        "   - Retain PII beyond retention period\n"
        "   - Share PII with third parties without consent"
    ),
)
```

---

## Service Classes

### Template: Service Class

```python
from apps.ontology.decorators import ontology

@ontology(
    domain="[DOMAIN]",
    concept="[CONCEPT]",
    purpose=(
        "[What this service does - business logic, orchestration, etc.]"
    ),
    criticality="[LEVEL]",
    security_boundary=[True/False],
    inputs=[
        {
            "name": "[method_name.parameter_name]",
            "type": "[parameter_type]",
            "description": "[What this parameter is]",
            "required": [True/False],
            "sensitive": [True/False],
        },
        # Add more parameters...
    ],
    outputs=[
        {
            "name": "[method_name return value]",
            "type": "[return_type]",
            "description": "[What is returned]",
        },
    ],
    side_effects=[
        "[Database operations]",
        "[API calls]",
        "[Cache updates]",
        "[Event triggers]",
    ],
    depends_on=[
        "[apps.module.Model (relationship)]",
        "[External service name]",
    ],
    used_by=[
        "[apps.module.View (usage context)]",
    ],
    tags=["[tag1]", "[tag2]"],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. [Security Aspect]:\n"
        "   - [Detail]\n\n"
        "2. Rate Limiting:\n"
        "   - [Rate limit policy]\n\n"
        "3. Authentication:\n"
        "   - [Auth requirements]\n\n"
        "4. NEVER:\n"
        "   - [Anti-pattern]"
    ),
    performance_notes=(
        "Performance Characteristics:\n"
        "- [Characteristic]\n\n"
        "Optimizations:\n"
        "- [Optimization]"
    ),
    examples=[
        "# [Example title]\n"
        "[code]\n",
    ],
)
class [ServiceName]:
    """Service implementation"""
```

---

## Middleware

### Template: Security Middleware

```python
from apps.ontology.decorators import ontology

@ontology(
    domain="security",  # Usually "security" for middleware
    concept="[What security aspect this middleware handles]",
    purpose=(
        "[What this middleware does - e.g., CSRF protection, rate limiting, etc.]"
    ),
    criticality="critical",  # Usually critical for security middleware
    security_boundary=True,  # Always True for security middleware
    inputs=[
        {
            "name": "request",
            "type": "HttpRequest",
            "description": "Incoming HTTP request",
            "required": True,
            "sensitive": False,
        },
    ],
    outputs=[
        {
            "name": "response",
            "type": "HttpResponse",
            "description": "[What response is returned or modified]",
        },
    ],
    side_effects=[
        "[Request modification]",
        "[Response header modification]",
        "[Logging]",
        "[Blocking requests]",
    ],
    depends_on=[
        "[Dependencies]",
    ],
    used_by=[
        "All HTTP requests (via Django middleware stack)",
    ],
    tags=["middleware", "security", "[specific-security-feature]"],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. [Security Feature]:\n"
        "   - [Implementation detail]\n\n"
        "2. OWASP Top 10 Compliance:\n"
        "   - [Which OWASP issue this addresses]\n\n"
        "3. Bypass Conditions:\n"
        "   - [When middleware is skipped, if applicable]\n\n"
        "4. NEVER:\n"
        "   - [Security anti-pattern]"
    ),
    performance_notes=(
        "Performance Impact:\n"
        "- Executes on EVERY request\n"
        "- [Performance characteristic]\n\n"
        "Optimizations:\n"
        "- [Optimization strategy]"
    ),
    examples=[
        "# [Example usage]\n"
        "[code]\n",
    ],
)
class [MiddlewareName]:
    """Middleware implementation"""
```

---

## API Views & ViewSets

### Template: REST API ViewSet

```python
from apps.ontology.decorators import ontology

@ontology(
    domain="[DOMAIN]",
    concept="[API Concept]",
    purpose=(
        "[What this API endpoint provides - CRUD operations, data access, etc.]"
    ),
    criticality="[LEVEL]",
    security_boundary=[True/False],
    inputs=[
        {
            "name": "[HTTP method].[parameter_name]",
            "type": "[parameter_type]",
            "description": "[What this parameter is]",
            "required": [True/False],
            "sensitive": [True/False],
        },
    ],
    outputs=[
        {
            "name": "[HTTP method] response",
            "type": "JSON",
            "description": "[Response structure]",
            "status_codes": ["200 OK", "400 Bad Request", "401 Unauthorized", "404 Not Found"],
        },
    ],
    side_effects=[
        "[Database operations]",
        "[Cache updates]",
        "[Event triggers]",
    ],
    depends_on=[
        "[apps.module.Model (data source)]",
        "[apps.module.Serializer (serialization)]",
        "[apps.module.Service (business logic)]",
    ],
    used_by=[
        "[Frontend application]",
        "[Mobile app]",
        "[Third-party integrations]",
    ],
    tags=["api", "rest", "[resource-name]"],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. Authentication:\n"
        "   - [Authentication requirement]\n\n"
        "2. Authorization:\n"
        "   - [Permission requirements]\n\n"
        "3. Rate Limiting:\n"
        "   - [Rate limit policy]\n\n"
        "4. Input Validation:\n"
        "   - [Validation requirements]\n\n"
        "5. NEVER:\n"
        "   - Expose PII without permission checks\n"
        "   - Allow unauthenticated access to sensitive data"
    ),
    performance_notes=(
        "HTTP Methods:\n"
        "- GET: [query characteristics]\n"
        "- POST: [creation logic]\n"
        "- PUT/PATCH: [update logic]\n"
        "- DELETE: [deletion logic]\n\n"
        "Pagination:\n"
        "- [Pagination strategy]\n\n"
        "Caching:\n"
        "- [Cache strategy]"
    ),
    examples=[
        "# [Example API call]\n"
        "[code]\n",
    ],
)
class [ViewSetName](viewsets.ModelViewSet):
    """ViewSet implementation"""
```

---

## Celery Tasks

### Template: Celery Task

```python
from apps.ontology.decorators import ontology

@ontology(
    domain="[DOMAIN]",
    concept="[Background Task Concept]",
    purpose=(
        "[What this background task does and when it runs]"
    ),
    criticality="[LEVEL]",
    security_boundary=[True/False],
    inputs=[
        {
            "name": "[parameter_name]",
            "type": "[parameter_type]",
            "description": "[What this parameter is]",
            "required": [True/False],
            "sensitive": [True/False],
        },
    ],
    outputs=[
        {
            "name": "Task result",
            "type": "[result_type]",
            "description": "[What is returned]",
        },
    ],
    side_effects=[
        "[Database operations]",
        "[File operations]",
        "[External API calls]",
        "[Email sending]",
    ],
    depends_on=[
        "[Dependencies]",
    ],
    used_by=[
        "[Celery beat schedule - periodic task]",
        "[apps.module.View (triggered by user action)]",
    ],
    tags=["celery", "background-task", "[task-type]"],
    task_configuration={
        "queue": "[queue_name]",
        "rate_limit": "[rate limit]",
        "max_retries": "[number]",
        "retry_policy": "[policy]",
    },
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. [Security Aspect]:\n"
        "   - [Detail]\n\n"
        "2. Retry Behavior:\n"
        "   - [Retry strategy and limits]\n\n"
        "3. NEVER:\n"
        "   - [Anti-pattern]"
    ),
    performance_notes=(
        "Execution Characteristics:\n"
        "- Execution time: [duration]\n"
        "- Frequency: [frequency]\n\n"
        "Resource Usage:\n"
        "- Memory: [usage]\n"
        "- CPU: [usage]\n\n"
        "Scaling:\n"
        "- [Scaling strategy]"
    ),
    examples=[
        "# [Example task invocation]\n"
        "[code]\n",
    ],
)
@shared_task(bind=True, max_retries=3)
def [task_name](self, [parameters]):
    """Task implementation"""
```

---

## Utility Functions

### Template: Utility Function

```python
from apps.ontology.decorators import ontology

@ontology(
    domain="infrastructure",  # Usually "infrastructure" for utilities
    concept="[Utility Concept]",
    purpose=(
        "[What this utility function does and when to use it]"
    ),
    criticality="[LEVEL]",
    security_boundary=[True/False],
    inputs=[
        {
            "name": "[parameter_name]",
            "type": "[parameter_type]",
            "description": "[What this parameter is]",
            "required": [True/False],
            "sensitive": [True/False],
        },
    ],
    outputs=[
        {
            "name": "Return value",
            "type": "[return_type]",
            "description": "[What is returned]",
        },
    ],
    side_effects=[
        "[Side effects, if any - ideally 'None (pure function)']",
    ],
    depends_on=[
        "[Dependencies]",
    ],
    used_by=[
        "[apps.module.Component (usage context)]",
    ],
    tags=["utility", "[function-category]"],
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "1. [Security Aspect if applicable]:\n"
        "   - [Detail]\n\n"
        "2. NEVER:\n"
        "   - [Anti-pattern]"
    ),
    performance_notes=(
        "Time Complexity: [O notation]\n"
        "Space Complexity: [O notation]\n\n"
        "Performance Characteristics:\n"
        "- [Characteristic]"
    ),
    examples=[
        "# [Example usage]\n"
        "[code]\n",
    ],
)
def [function_name]([parameters]):
    """Function implementation"""
```

---

## Quick Fill Checklist

When filling in a template, ensure you have:

- [ ] **domain**: Chosen from standard domains (people, operations, security, etc.)
- [ ] **concept**: Clear high-level concept name
- [ ] **purpose**: 2-3 sentence description of what and why
- [ ] **criticality**: Appropriate level (critical, high, medium, low)
- [ ] **security_boundary**: True if handles auth, PII, or security
- [ ] **inputs**: All parameters with sensitive=True for PII
- [ ] **outputs**: Return values and types
- [ ] **side_effects**: All database writes, API calls, cache ops
- [ ] **depends_on**: All dependencies with relationship types
- [ ] **used_by**: All consumers with usage context
- [ ] **tags**: At least 3-5 relevant tags
- [ ] **security_notes**: At minimum 3 security aspects + NEVER section
- [ ] **performance_notes**: Query patterns, indexes, optimizations
- [ ] **examples**: At least 2-3 usage examples

---

## Common Domains

- `people` - User authentication, profiles, permissions
- `operations` - Tasks, work orders, job management
- `security` - Auth, encryption, audit, compliance
- `attendance` - Attendance tracking, geofencing, GPS
- `reports` - Analytics, scheduled reports, compliance
- `infrastructure` - Core utilities, middleware, base classes
- `onboarding` - Client/contract management
- `assets` - Inventory, asset tracking
- `help_desk` - Ticketing, escalations, SLAs
- `wellness` - Wellbeing, journal, health tracking

---

## Common Tags

**Security:**
- `authentication`, `authorization`, `security`, `pii`, `gdpr`, `encryption`, `audit-trail`

**Operations:**
- `background-task`, `celery`, `scheduled`, `async`, `worker`

**Data:**
- `model`, `database`, `orm`, `query-optimization`

**API:**
- `api`, `rest`, `websocket`, `mqtt`, `serializer`

**Features:**
- `geofencing`, `gps`, `payment`, `reporting`, `notification`

---

**For more examples, see:**
- `apps/peoples/models/security_models.py` (audit logging)
- `apps/peoples/models/session_models.py` (session management)
- `apps/peoples/models/capability_model.py` (permissions)
- `apps/peoples/models/profile_model.py` (PII data)
