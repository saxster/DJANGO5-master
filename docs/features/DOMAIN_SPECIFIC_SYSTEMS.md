# Domain-Specific Systems

> **Specialized features and sub-systems for facility management operations**

---

## Security & Facility AI Mentor (Oct 2025)

### Overview

Intelligent monitoring of **7 operational non-negotiables** with daily scorecards and auto-alerts.

### The 7 Pillars

1. **Right Guard at Right Post** - Schedule coverage & attendance
2. **Supervise Relentlessly** - Tour completion & checkpoints
3. **24/7 Control Desk** - Alert acknowledgment SLAs
4. **Legal & Professional** - PF/ESIC/payroll compliance
5. **Support the Field** - Uniform/equipment tickets
6. **Record Everything** - Report delivery (daily/weekly/monthly)
7. **Respond to Emergencies** - Crisis escalation <2min

### Quick Access

#### Web UI

```bash
http://localhost:8000/helpbot/security_scorecard/
```

#### API

```bash
curl http://localhost:8000/helpbot/api/v1/scorecard/ \
  -H "Authorization: Token <token>"
```

#### Programmatic

```python
from apps.noc.security_intelligence.services import NonNegotiablesService

service = NonNegotiablesService()
scorecard = service.generate_scorecard(tenant, client)
```

#### Manual Evaluation

Runs automatically daily at 6 AM, but can be triggered manually:

```python
from background_tasks.non_negotiables_tasks import evaluate_non_negotiables
evaluate_non_negotiables.delay()
```

### Scoring Logic

- **GREEN**: All pillars ≥90% OR only AMBER pillars
- **AMBER**: Any pillar 70-89% OR minor violations
- **RED**: Any pillar <70% OR CRITICAL violations

### Infrastructure (95% Reuse)

Leverages existing components:

- `ScheduleCoordinator` - Schedule health scoring
- `TaskComplianceMonitor` - Tour compliance tracking
- `NOCAlertEvent` - Alert SLA monitoring
- `AlertCorrelationService` - Auto-alert creation
- `EscalationService` - On-call routing
- `Ticket` model - Field support and crisis tracking

### Reference

- **Implementation**: `SECURITY_FACILITY_MENTOR_PHASE2_COMPLETE.md`
- **Operator Guide**: `NON_NEGOTIABLES_OPERATOR_GUIDE.md`
- **Model**: `apps/noc/security_intelligence/models/non_negotiables_scorecard.py`
- **Service**: `apps/noc/security_intelligence/services/non_negotiables_service.py` (775 lines)

---

## Secure File Download Service (Oct 2025)

### Overview

Enterprise-grade file download service with **multi-layer permission validation** preventing IDOR vulnerabilities and cross-tenant data breaches.

**CVSS Score Mitigated:** 7.5-8.5 (High) - Broken Access Control / IDOR

### Security Layers

1. **Tenant Isolation** - Enforces cross-tenant boundaries (CRITICAL for multi-tenant SaaS)
2. **Ownership Validation** - Verifies user created/owns the file
3. **Path Traversal Prevention** - MEDIA_ROOT boundary enforcement with symlink protection
4. **Role-Based Permissions** - Django permission system integration (`activity.view_attachment`)
5. **Business Unit Access Control** - Same BU membership required
6. **Audit Logging** - All access attempts logged with correlation IDs
7. **Default Deny** - Explicit permission required; no silent failures

### Quick Access

#### Validate Attachment Access

```python
from apps.core.services.secure_file_download_service import SecureFileDownloadService
from django.core.exceptions import PermissionDenied

try:
    # Multi-layer permission validation
    attachment = SecureFileDownloadService.validate_attachment_access(
        attachment_id=request.GET['id'],
        user=request.user
    )
    # Returns attachment only if user has permission

except PermissionDenied as e:
    return JsonResponse({'error': str(e)}, status=403)
```

#### Secure File Download

```python
from apps.core.services.secure_file_download_service import SecureFileDownloadService

# Path validation + permission check + secure serving
response = SecureFileDownloadService.validate_and_serve_file(
    filepath='uploads',
    filename='document.pdf',
    user=request.user,
    owner_id='attachment-uuid'  # For permission validation
)
return response  # FileResponse with security headers
```

### Permission Validation Flow

```
1. Authentication Check → User must be authenticated
2. Superuser Bypass → is_superuser = full access (logged)
3. Ownership Check → attachment.cuser == user
4. Tenant Isolation → attachment.tenant == user.tenant (CRITICAL)
5. Business Unit Check → user belongs to attachment's BU
6. Django Permissions → user.has_perm('activity.view_attachment')
7. Staff Access → is_staff can access within tenant
8. Default Deny → PermissionDenied if no rule matches
```

### Features

- **Path Traversal Protection:** Detects `..`, null bytes, symlinks outside MEDIA_ROOT
- **MIME Type Validation:** Proper Content-Type headers
- **Security Headers:** X-Content-Type-Options, X-Frame-Options
- **Correlation IDs:** Every request tracked for incident investigation
- **Error Distinction:** 403 Forbidden vs 404 Not Found (prevents enumeration)

### Exposed Endpoints

| Endpoint | Purpose | Method |
|----------|---------|--------|
| `/activity/attachments/` | Direct file download | `GET` with `action=download` |
| `/activity/previewImage/` | Attachment preview | `GET` with `id=<attachment_id>` |

**Both endpoints protected by `LoginRequiredMixin` + `SecureFileDownloadService` validation**

### Test Coverage

**Test File:** `apps/core/tests/test_secure_file_download_permissions.py`

**Test Scenarios (25+ tests):**
- Cross-tenant access blocking (CRITICAL)
- Ownership validation
- Superuser bypass
- Staff access within tenant
- Django permission enforcement
- Business unit isolation
- IDOR prevention
- Direct file access (staff-only)
- Edge cases (404 vs 403, invalid UUIDs)

### Security Compliance

✅ **OWASP Top 10 #1:** Broken Access Control - MITIGATED
✅ **Multi-Tenant Data Segregation:** Enforced at application layer
✅ **CVSS 9.8 (Path Traversal):** Prevented via MEDIA_ROOT boundary checks
✅ **Audit Requirements:** All access attempts logged with correlation IDs
✅ **Rule 14b Compliance:** `.claude/rules.md` - File Download and Access Control

### Code References

- **Service:** `apps/core/services/secure_file_download_service.py`
- **Views:** `apps/activity/views/attachment_views.py` (lines 84-139, 311-364)
- **Tests:** `apps/core/tests/test_secure_file_download_permissions.py`
- **Tests (Path Traversal):** `apps/core/tests/test_path_traversal_vulnerabilities.py`

### Monitoring

**Security Events Logged:**
- Cross-tenant access attempts (ERROR level)
- Permission denials (WARNING level)
- Superuser access (INFO level, audit trail)
- Path traversal attempts (ERROR level)
- File not found vs access denied (distinct handling)

**Recommended Alerts:**
- Alert on cross-tenant access attempts (potential breach)
- Monitor failed permission checks for patterns
- Track correlation IDs for incident investigation

### Migration from Legacy Patterns

**❌ FORBIDDEN (Insecure):**
```python
attachment = Attachment.objects.get(id=request.GET['id'])  # No permission check
with open(attachment.path, 'rb') as f:
    return FileResponse(f)  # IDOR vulnerability
```

**✅ REQUIRED (Secure):**
```python
attachment = SecureFileDownloadService.validate_attachment_access(
    attachment_id=request.GET['id'],
    user=request.user
)
# Permission validated before access
```

---

## Stream Testbench (Real-Time Testing)

### Overview

Enterprise stream testing platform with PII protection and AI-powered anomaly detection.

### Quick Start

```bash
# Run Stream Testbench tests
python -m pytest apps/streamlab/tests/ apps/issue_tracker/tests/ -v

# Complete suite
python run_stream_tests.py

# Performance validation
python testing/stream_load_testing/spike_test.py
```

### ASGI Server (Required for WebSockets)

```bash
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

### Core Apps

- **`streamlab`** - Stream testing core with PII protection
- **`issue_tracker`** - AI-powered issue knowledge base

### Features

1. **Real-time data streaming** via WebSockets
2. **PII detection and redaction** before storage
3. **AI anomaly detection** for unusual patterns
4. **Load testing** infrastructure for performance validation
5. **Issue tracking** with ML-based categorization

---

## Caching Strategy

### Redis Configuration

**Optimized for environment-specific performance**

```python
from intelliwiz_config.settings.redis_optimized import OPTIMIZED_CACHES
```

### Production Configuration

- Connection pooling: 100 connections
- JSON serializer (compliance-friendly)
- Zlib compression enabled
- Health checks every 30s
- Fail-fast password validation

### Development Configuration

- Connection pooling: 20 connections
- JSON serializer (consistent with production)
- No compression (easier debugging)
- Health checks every 60s

### Testing Configuration

- JSON serializer (Oct 2025: migrated for compliance)
- Local memory or Redis (configurable)
- Fast timeouts for test speed

### Cache Backends

| Cache Name | Backend | Database | Purpose |
|------------|---------|----------|---------|
| `default` | Redis | DB 1 | General Django caching |
| `select2` | PostgreSQL | N/A | Materialized views for dropdowns |
| `sessions` | Redis | DB 4 | User sessions (optional) |
| `celery_results` | Redis | DB 1 | Task results (shared with default) |

### Select2 Migration (Oct 2025) - ✅ COMPLETE

**Migrated from Redis to PostgreSQL materialized views**

```python
# Select2 now uses PostgreSQL-based materialized views (NOT Redis!)
CACHES['select2'] = {
    'BACKEND': 'apps.core.cache.materialized_view_select2.MaterializedViewCache',
    'LOCATION': '',  # No Redis needed
    'OPTIONS': {
        'MAX_ENTRIES': 10000,  # Production
        'CULL_FREQUENCY': 3,
    },
}

# Materialized views available:
# - mv_people_dropdown (users)
# - mv_location_dropdown (locations)
# - mv_asset_dropdown (assets)
```

### Session Optimization

- **Backend**: PostgreSQL sessions (not Redis)
- **Trade-off**: 20ms latency vs. architecture simplicity
- **Decision**: Approved for production use

### Security

- Production requires `REDIS_PASSWORD` environment variable (fail-fast)
- Development uses secure default with warning if env var missing
- No hardcoded credentials in source code
- Password validation on Django startup

### Verification

```bash
# Verify Redis cache configuration
python scripts/verify_redis_cache_config.py

# Test specific environment
python scripts/verify_redis_cache_config.py --environment production
```

#### Checks Performed

- ✓ Cache backend (Redis vs in-memory)
- ✓ Cache connectivity (read/write/delete)
- ✓ Select2 PostgreSQL migration status
- ✓ Serializer configuration (JSON recommended)
- ✓ Redis password security

---

## Face Recognition System

### Overview

AI-enhanced biometric authentication for attendance and access control.

### Features

1. **Real-time face detection** with <100ms latency
2. **Liveness detection** to prevent photo spoofing
3. **Multi-face tracking** for group scenarios
4. **Attendance integration** with automatic clock-in/out
5. **Analytics dashboard** with recognition accuracy metrics

### Configuration

```python
# apps/face_recognition/ai_enhanced_engine.py
FaceRecognitionConfig = {
    'detection_threshold': 0.95,  # 95% confidence required
    'liveness_enabled': True,
    'multi_face_tracking': True,
    'attendance_auto_clockin': True,
}
```

### Calibration

```bash
# Calibrate detection thresholds
python manage.py calibrate_thresholds

# Initialize AI systems (as of Oct 2025 handled automatically via startup checks)
# Manual bootstrap command was removed with the anomaly_detection deprecation.
```

---

## NOC (Network Operations Center)

### Overview

Real-time monitoring and alerting system for facility operations.

### Features

1. **Alert correlation** - Group related alerts
2. **Escalation workflows** - On-call rotation support
3. **Security intelligence** - Threat detection
4. **Incident management** - Track and resolve issues
5. **Metric snapshots** - Time-series performance data

### Quick Access

```bash
# NOC dashboard
open http://localhost:8000/noc/dashboard/

# Security intelligence scorecard
open http://localhost:8000/noc/security_intelligence/scorecard/
```

### Alert Configuration

```python
# apps/noc/models/audit.py
AlertConfig = {
    'critical_sla': 120,  # 2 minutes
    'high_sla': 300,      # 5 minutes
    'medium_sla': 900,    # 15 minutes
    'low_sla': 3600,      # 1 hour
}
```

---

## Wellness & Journal System

### Overview

**Privacy-first wellbeing support system** that aggregates journal entries from Kotlin mobile frontends and delivers contextual, evidence-based wellness interventions to field workers.

### Architecture

**Wellness as an Aggregator:**
- Journal entries created on **Kotlin mobile clients** (Android)
- Synced to backend via REST API (`/api/journal/`)
- **Wellness module aggregates and analyzes** journal data in real-time
- Site admins view **anonymized, aggregated metrics** through Django Admin

### Data Flow

```
Kotlin Frontend → Journal Entry → Pattern Analysis → Wellness Content Delivery → Admin Aggregation
```

1. **Mobile Submission**: Field workers submit mood/stress/energy ratings via Kotlin app
2. **Real-time Analysis**: `JournalAnalyticsService` scores urgency (0-10) and detects crisis patterns
3. **Content Delivery**: Evidence-based wellness content (WHO/CDC) delivered contextually
4. **Interaction Tracking**: User engagement monitored for effectiveness metrics
5. **Admin Aggregation**: Site admins view anonymized wellbeing trends and intervention effectiveness

### Key Features

1. **Journal Entry Types**
   - Mood check-ins (1-10 scale)
   - Stress logs (1-5 scale)
   - Gratitude entries
   - Safety concerns
   - End-of-shift reflections

2. **Pattern Analysis Engine**
   - Crisis keyword detection ("overwhelmed", "hopeless")
   - Urgency scoring algorithm
   - Trend analysis (30/60/90 day patterns)
   - Intervention triggers (immediate/same_hour/same_day)

3. **Wellness Content System**
   - Evidence-based interventions (WHO/CDC compliant)
   - Contextual delivery based on mood/stress
   - Multiple categories: mental_health, stress_management, resilience, sleep_hygiene
   - User engagement tracking (views, completion, ratings)

4. **Privacy Controls**
   - Privacy scopes: `private`, `manager`, `team`, `aggregate`
   - Granular consent management
   - GDPR compliance
   - Wellbeing entries default to `private`

5. **Gamification**
   - Streak tracking (consecutive engagement days)
   - Achievement system (badges)
   - Category-specific progress scores
   - Leaderboards (optional, anonymized)

### Quick Access

#### API Endpoints

```bash
# Journal API
POST   /api/journal/entries/              # Create journal entry
POST   /api/journal/entries/bulk_create/  # Batch sync from mobile
GET    /api/journal/analytics/            # Wellbeing analytics

# Wellness API
POST   /api/wellness/contextual/          # Get contextual content
GET    /api/wellness/daily-tip/           # Daily wellness tip
GET    /api/wellness/progress/            # User progress & gamification
POST   /api/wellness/content/{id}/track_interaction/  # Track engagement
```

#### Admin Interfaces (Site Admins)

```bash
# Wellness content management
open http://localhost:8000/admin/wellness/wellnesscontent/

# Wellness interactions & effectiveness
open http://localhost:8000/admin/wellness/wellnesscontentinteraction/

# Journal entries (privacy-filtered)
open http://localhost:8000/admin/journal/journalentry/

# User progress & gamification
open http://localhost:8000/admin/wellness/wellnessuserprogress/

# Analytics dashboard
open http://localhost:8000/journal/analytics/
```

### Admin Aggregation Metrics

**What Site Admins Can See:**

1. **Wellbeing Trends** (anonymized)
   - Average mood/stress/energy across team
   - Trend direction (improving/stable/declining)
   - High-risk user count (anonymous)

2. **Intervention Effectiveness**
   - Content delivery count
   - User engagement rate
   - Completion rates
   - Average content ratings

3. **Content Performance**
   - Views per content item
   - Effectiveness score
   - Most helpful content (by category)

4. **Privacy-Respecting Analytics**
   - Only shows data where user consent given
   - Wellbeing entries always private unless explicitly shared
   - Crisis interventions require opt-in consent

### Urgency Scoring Algorithm

```python
urgency_score = 0

if stress_level >= 4:           urgency += 3
if mood_rating <= 2:            urgency += 4
if energy_level <= 3:           urgency += 1
if crisis_keywords_found:       urgency += 2
if entry_type == 'SAFETY_CONCERN': urgency += 2

# Classification:
# 7-10: CRITICAL → immediate delivery
# 5-6:  HIGH     → same hour
# 3-4:  MEDIUM   → same day
# 1-2:  LOW      → next session
```

### Programmatic Access

```python
# Generate comprehensive analytics
from apps.journal.services.analytics_service import JournalAnalyticsService

service = JournalAnalyticsService()
analytics = service.generate_comprehensive_analytics(user, days=30)
# Returns: mood_trends, stress_patterns, behavioral_insights

# Analyze entry for immediate action
urgency = service.analyze_entry_for_immediate_action(journal_entry)
# Returns: urgency_score, urgency_level, intervention_categories

# Get contextual wellness content
from apps.wellness.views import ContextualWellnessContentView

content = view.get_contextual_content(user, urgency_analysis)
# Returns: immediate_content, follow_up_content
```

### Database Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `JournalEntry` | User journal entries from mobile | `mood_rating`, `stress_level`, `energy_level`, `privacy_scope` |
| `JournalPrivacySettings` | User consent management | `wellbeing_sharing_consent`, `analytics_consent`, `crisis_intervention_consent` |
| `WellnessContent` | Evidence-based content library | `category`, `delivery_context`, `evidence_level`, `priority_score` |
| `WellnessContentInteraction` | Engagement tracking | `interaction_type`, `time_spent_seconds`, `user_rating` |
| `WellnessUserProgress` | Gamification data | `current_streak`, `total_score`, `achievements_earned` |

### Code References

| Component | File | Lines |
|-----------|------|-------|
| Journal models | `apps/journal/models.py` | 700 |
| Wellness models | `apps/wellness/models.py` | 700 |
| Pattern analysis | `apps/journal/services/analytics_service.py` | 957 |
| Wellness API | `apps/wellness/views.py` | 900 |
| Journal API | `apps/journal/views.py` | 775 |
| Wellness admin | `apps/wellness/admin/content_admin.py` | 233 |

### Security & Compliance

- **PII Protection**: Journal content never logged or exposed in error messages
- **Encryption**: Sensitive fields encrypted at rest
- **GDPR Compliance**: Right to access, deletion, data portability
- **Consent Required**: Crisis intervention requires explicit opt-in
- **Privacy by Default**: Wellbeing entries always private unless user changes scope

### Mobile Integration (Kotlin Frontend)

**Expected Data Contract:**

```kotlin
// Journal entry from Kotlin client
data class JournalEntryCreate(
    val title: String,
    val entry_type: String,  // "MOOD_CHECK_IN", "STRESS_LOG", etc.
    val mood_rating: Int?,    // 1-10
    val stress_level: Int?,   // 1-5
    val energy_level: Int?,   // 1-10
    val content: String,
    val stress_triggers: List<String>,
    val timestamp: String     // ISO 8601 format
)

// Backend responds with urgency analysis + wellness content
data class WellnessResponse(
    val immediate_content: List<WellnessContentItem>,
    val urgency_analysis: UrgencyAnalysis,
    val user_progress: UserProgress
)
```

### Reference Documents

- **Analytics Service**: `apps/journal/services/analytics_service.py`
- **Wellness Content Delivery**: `apps/wellness/views.py`
- **Privacy Implementation**: `apps/journal/middleware/pii_redaction_middleware.py`
- **Admin Interfaces**: `apps/wellness/admin/` directory

---

## Reports System

### Overview

Comprehensive reporting system with scheduled generation and multiple export formats.

### Features

1. **Template management** - Reusable report templates
2. **Scheduled generation** - Automatic daily/weekly/monthly reports
3. **Multiple formats** - PDF, Excel, CSV, JSON
4. **ERP integration** - Frappe/ERPNext support (Oct 2025)
5. **Analytics** - Built-in data visualization

### Quick Start

```bash
# Generate report
python manage.py generate_report --template daily_summary

# Schedule report
python manage.py schedule_report --template weekly_analysis --day monday
```

### Frappe ERP Integration (Oct 2025)

```python
from apps.reports.services import get_frappe_service, FrappeCompany

service = get_frappe_service()
customers = service.get_customers(FrappeCompany.SPS)
payroll = service.get_payroll_data(
    company=FrappeCompany.SPS,
    from_date='2025-01-01',
    to_date='2025-01-31'
)
```

---

**Last Updated**: October 29, 2025
**Maintainer**: Feature Teams
**Related**: [System Architecture](../architecture/SYSTEM_ARCHITECTURE.md)
