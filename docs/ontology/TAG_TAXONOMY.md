# Ontology Tag Taxonomy
**Purpose**: Standardize tag names across all ontology decorators to ensure consistency and searchability

**Last Updated**: 2025-11-01
**Maintainer**: Ontology Expansion Team

---

## HOW TO USE THIS DOCUMENT

**When writing ontology decorators**:
1. Choose 7-10 tags from the lists below
2. Prefer existing tags over creating new ones
3. Use exact spelling (case-sensitive)
4. If you need a new tag, add it to this document and notify the team

**Tag Selection Strategy**:
- **Minimum 7 tags**: 2 security + 2 domain + 1 technology + 1 architecture + 1 compliance
- **Recommended 10 tags**: Full coverage across categories
- **Maximum 15 tags**: Avoid over-tagging (reduces searchability)

---

## SECURITY TAGS

### Core Security
- `security` - General security-related code (use for all security components)
- `authentication` - Login flows, session management, OAuth, JWT
- `authorization` - Permissions, RBAC, access control
- `encryption` - Data encryption, key management, HSM integration
- `pii` - Contains or processes personally identifiable information
- `audit-trail` - Audit logging, event tracking, tamper-proofing
- `compliance` - General compliance (GDPR, SOC2, HIPAA, etc.)

### Attack Prevention
- `csrf-protection` - Cross-Site Request Forgery defense
- `xss-prevention` - Cross-Site Scripting sanitization
- `sql-injection-prevention` - SQL injection defense
- `path-traversal-prevention` - File path security
- `dos-protection` - Denial of Service mitigation
- `rate-limiting` - Request throttling, abuse prevention
- `input-validation` - User input sanitization

### Data Protection
- `data-encryption` - Encryption at rest
- `transport-security` - TLS, HTTPS, encryption in transit
- `key-management` - Encryption key rotation, storage
- `secret-management` - API keys, tokens, credentials storage
- `password-security` - Password hashing, strength validation

### Security Monitoring
- `intrusion-detection` - Suspicious activity detection
- `security-logging` - Security event logging
- `threat-detection` - Anomaly detection, threat intelligence
- `vulnerability-scanning` - Automated security scanning

---

## DOMAIN TAGS (Business Areas)

### People & HR
- `people` - User management, profiles, authentication
- `employees` - Employee-specific functionality
- `contractors` - Contractor management
- `attendance` - Check-in/out, time tracking
- `expenses` - Expense claims, reimbursements
- `capabilities` - Skills, certifications, RBAC roles

### Operations & Facilities
- `operations` - General facility operations
- `tasks` - Task management, job cards
- `work-orders` - Work order workflows
- `preventive-maintenance` - PPM schedules
- `corrective-maintenance` - Reactive maintenance
- `tours` - Security patrols, inspection tours
- `shifts` - Shift scheduling, rosters

### Assets & Inventory
- `assets` - Asset tracking, lifecycle management
- `inventory` - Stock management, warehouses
- `equipment` - Equipment maintenance, calibration
- `monitoring` - Asset monitoring, IoT sensors

### Client Services
- `help-desk` - Ticketing, support requests
- `escalations` - Issue escalation workflows
- `sla-management` - Service Level Agreements
- `client-portal` - Client-facing features

### Reporting & Analytics
- `reports` - Report generation, scheduling
- `analytics` - Data analysis, dashboards
- `compliance-reporting` - GDPR, SOC2, audit reports
- `business-intelligence` - BI, data visualization

### Configuration
- `onboarding` - Client onboarding, setup
- `business-units` - Business unit management
- `contracts` - Contract management
- `geofencing` - GPS boundaries, location validation
- `sites` - Site configuration, multi-site

---

## TECHNOLOGY TAGS (Framework/Stack)

### Django Core
- `django-model` - Django ORM models
- `django-view` - Django views (class-based or function-based)
- `django-middleware` - Request/response middleware
- `django-signal` - Django signals (pre_save, post_save, etc.)
- `django-admin` - Django admin customization
- `django-management-command` - Custom management commands

### Django REST Framework
- `drf-viewset` - DRF ViewSets
- `drf-apiview` - DRF APIView classes
- `drf-serializer` - DRF Serializers
- `drf-permission` - DRF Permission classes
- `drf-authentication` - DRF Authentication backends

### Asynchronous & Real-time
- `celery-task` - Background tasks, async workers
- `celery-beat` - Scheduled periodic tasks
- `websocket` - Real-time WebSocket features
- `channels` - Django Channels integration
- `async-await` - Python async/await patterns

### Database
- `postgresql` - PostgreSQL-specific features
- `postgis` - PostGIS geospatial queries
- `orm-query` - Complex ORM queries
- `raw-sql` - Raw SQL queries
- `database-migration` - Schema migrations

### Caching & Performance
- `redis-cache` - Redis caching
- `cache-invalidation` - Cache invalidation strategies
- `query-optimization` - N+1 prevention, select_related
- `indexing` - Database indexes

### External Integrations
- `rest-api` - External REST API integrations
- `webhook` - Webhook handlers
- `third-party-integration` - External service integrations
- `mobile-api` - Mobile app (Kotlin/Swift) endpoints

---

## ARCHITECTURE TAGS (Patterns & Structures)

### Multi-Tenancy
- `multi-tenant` - Tenant isolation, tenant-aware models
- `tenant-routing` - Database routing by tenant
- `cross-tenant-prevention` - Cross-tenant access blocking

### State Management
- `state-machine` - Workflow state machines
- `state-transitions` - State transition validation
- `workflow` - Business workflow orchestration

### Performance & Scaling
- `performance-critical` - High-volume, low-latency code
- `high-throughput` - Bulk processing, batch operations
- `streaming` - Large file streaming, chunked responses
- `pagination` - Paginated queries, infinite scroll

### Data Patterns
- `event-sourcing` - Event log, audit trail
- `cqrs` - Command-Query Responsibility Segregation
- `repository-pattern` - Data access abstraction
- `service-layer` - Business logic in services

### Integration Patterns
- `idempotency` - Idempotent operations (duplicate prevention)
- `retry-mechanism` - Automatic retry with backoff
- `circuit-breaker` - Fault tolerance, degradation
- `saga-pattern` - Distributed transactions

### Code Quality
- `type-safety` - Pydantic models, type hints
- `error-handling` - Exception handling, error responses
- `logging` - Structured logging, observability
- `testing` - Test utilities, fixtures

---

## COMPLIANCE TAGS (Legal & Standards)

### Privacy Regulations
- `gdpr` - GDPR (EU General Data Protection Regulation)
  - Use with `gdpr-article-4` (personal data definitions)
  - Use with `gdpr-article-6` (lawful processing)
  - Use with `gdpr-article-17` (right to erasure)
  - Use with `gdpr-article-32` (security of processing)
- `ccpa` - California Consumer Privacy Act
- `privacy-by-design` - Privacy-first architecture

### Security Standards
- `soc2` - SOC2 Type II compliance
- `soc2-cc6.1` - Logical access controls
- `soc2-cc7.2` - System monitoring
- `iso27001` - ISO 27001 information security
- `owasp` - OWASP security best practices
- `owasp-a01-2021` - Broken Access Control
- `owasp-a02-2021` - Cryptographic Failures
- `owasp-a03-2021` - Injection
- `owasp-a04-2021` - Insecure Design
- `owasp-a05-2021` - Security Misconfiguration
- `owasp-a06-2021` - Vulnerable Components
- `owasp-a07-2021` - Identification/Authentication Failures
- `owasp-a08-2021` - Software/Data Integrity Failures
- `owasp-a09-2021` - Security Logging Failures
- `owasp-a10-2021` - Server-Side Request Forgery

### Industry Standards
- `pci-dss` - Payment Card Industry Data Security Standard
- `hipaa` - Health Insurance Portability and Accountability Act
- `fips-140-2` - Federal Information Processing Standards (cryptography)

### Operational Standards
- `data-retention` - Data retention policies
- `right-to-erasure` - User data deletion
- `data-portability` - Export user data
- `consent-management` - User consent tracking

---

## FEATURE TAGS (Specific Features)

### AI & Machine Learning
- `face-recognition` - Facial recognition, biometric auth
- `ai-model` - Machine learning models
- `noc-ai-mentor` - Security AI mentor (7 pillars)
- `anomaly-detection` - ML-based anomaly detection

### GPS & Location
- `gps` - GPS tracking, coordinates
- `geofencing` - Geofence validation
- `location-fraud-detection` - GPS spoofing prevention
- `geospatial` - PostGIS queries, spatial data

### Wellness
- `journal` - Wellness journal entries
- `wellness` - Evidence-based wellness interventions
- `mood-tracking` - Mood/stress/energy ratings
- `wellbeing-analytics` - Aggregate wellbeing metrics

### File Management
- `file-upload` - File upload handling
- `file-download` - Secure file downloads
- `file-validation` - File type, size, EXIF validation
- `media-storage` - Media file management

---

## USAGE EXAMPLES

### Example 1: Security Middleware (CSRF Protection)
```python
@ontology(
    tags=[
        "security",               # Core security
        "csrf-protection",        # Attack prevention
        "owasp-a01-2021",        # OWASP Top 10
        "django-middleware",      # Technology
        "authentication",         # Domain
        "compliance",             # Compliance
        "soc2",                   # Security standard
        "performance-critical"    # Architecture (runs on every request)
    ]
)
```

### Example 2: PII Model (User Profile)
```python
@ontology(
    tags=[
        "people",                 # Domain
        "pii",                    # Security (contains PII)
        "gdpr",                   # Privacy regulation
        "gdpr-article-4",         # Personal data
        "gdpr-article-6",         # Lawful processing
        "django-model",           # Technology
        "multi-tenant",           # Architecture
        "data-encryption",        # Security
        "right-to-erasure",       # Compliance
        "consent-management"      # Compliance
    ]
)
```

### Example 3: Celery Task (Report Generation)
```python
@ontology(
    tags=[
        "reports",                # Domain
        "celery-task",            # Technology
        "celery-beat",            # Scheduled task
        "compliance-reporting",   # Domain
        "soc2",                   # Compliance
        "streaming",              # Architecture (large files)
        "idempotency",            # Architecture (duplicate prevention)
        "retry-mechanism",        # Architecture
        "logging"                 # Code quality
    ]
)
```

### Example 4: GPS Fraud Detection Service
```python
@ontology(
    tags=[
        "attendance",             # Domain
        "gps",                    # Feature
        "geofencing",             # Feature
        "location-fraud-detection", # Feature
        "security",               # Security
        "geospatial",             # Technology (PostGIS)
        "anomaly-detection",      # AI/ML
        "service-layer",          # Architecture
        "logging",                # Code quality
        "performance-critical"    # Architecture
    ]
)
```

---

## TAG COMBINATION GUIDELINES

### Minimum Viable Tags (7 tags):
1. **1 Domain tag** - What business area? (people, operations, assets, etc.)
2. **2 Security tags** - Security concerns? (pii, authentication, encryption, etc.)
3. **1 Technology tag** - What framework? (django-model, drf-viewset, celery-task)
4. **1 Architecture tag** - What pattern? (multi-tenant, state-machine, performance-critical)
5. **2 Compliance tags** - What regulations? (gdpr, soc2, owasp)

### Recommended Tags (10 tags):
- Add 2-3 feature-specific tags (gps, file-upload, face-recognition)
- Add code quality tags (error-handling, logging, testing)

### Anti-Patterns (AVOID):
❌ **Too few tags** (<5): Hard to find components
❌ **Too many tags** (>15): Dilutes searchability
❌ **Redundant tags**: Don't use both `security` and `csrf-protection` + `xss-prevention` + `sql-injection-prevention` (pick the most specific)
❌ **Vague tags**: Avoid `misc`, `utils`, `helpers` (be specific)
❌ **Typos**: `authetication` instead of `authentication` (breaks search)

---

## ADDING NEW TAGS

**When to add a new tag**:
- ✅ New business domain not covered above
- ✅ New compliance regulation (e.g., GDPR successor)
- ✅ New technology stack (e.g., new framework)
- ✅ New architecture pattern (e.g., event-driven)

**Process for adding new tags**:
1. Check if existing tags can be combined (avoid proliferation)
2. Add to appropriate category above
3. Add usage example
4. Notify team in Slack/Teams channel
5. Commit change to git: `docs/ontology/TAG_TAXONOMY.md`

**Example PR description**:
```
feat(ontology): Add new compliance tag `nist-800-53`

Added NIST 800-53 compliance tag for federal government security controls.

Category: Compliance Tags > Security Standards
Usage: For components implementing NIST controls (AC-2, AU-3, etc.)
```

---

## TAG SEARCH EXAMPLES

### Find all PII-related components:
```bash
python manage.py extract_ontology | jq '.[] | select(.tags | contains(["pii"]))'
```

### Find all OWASP Top 10 components:
```bash
grep -r "owasp" exports/ontology/current.json
```

### Find all Celery tasks:
```bash
python manage.py extract_ontology | jq '.[] | select(.tags | contains(["celery-task"]))'
```

### Find all multi-tenant security components:
```bash
python manage.py extract_ontology | jq '.[] | select(.tags | contains(["multi-tenant", "security"]))'
```

---

## MAINTENANCE SCHEDULE

**Monthly Review** (First Monday of month):
- Review new tags added in past month
- Consolidate duplicate/redundant tags
- Update usage examples
- Notify team of changes

**Quarterly Audit** (End of quarter):
- Analyze tag usage frequency (identify unused tags)
- Survey team for missing tags
- Major taxonomy restructuring if needed

---

**END OF TAG TAXONOMY**

**Questions?** Ask in #ontology-expansion Slack channel or raise in daily standup.
