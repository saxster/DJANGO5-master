# Gold-Standard Ontology Examples
**Purpose**: Annotated examples from Phase 1 showing what makes a decorator "gold-standard"

**Last Updated**: 2025-11-01
**Target Audience**: Engineers writing new ontology decorators

---

## TABLE OF CONTENTS

1. [What Makes a Decorator "Gold-Standard"?](#what-makes-a-decorator-gold-standard)
2. [Example 1: Security Audit Models](#example-1-security-audit-models-pii-heavy)
3. [Example 2: Session Management](#example-2-session-management-complex-business-logic)
4. [Example 3: RBAC Capability Model](#example-3-rbac-capability-model)
5. [Example 4: User Profile (PII-Heavy)](#example-4-user-profile-pii-heavy)
6. [Common Patterns Across All Examples](#common-patterns-across-all-examples)
7. [Quality Checklist](#quality-checklist)

---

## WHAT MAKES A DECORATOR "GOLD-STANDARD"?

**Phase 1 Quality Metrics** (Target for All Decorators):

| Metric | Target | Phase 1 Actual | Status |
|--------|--------|----------------|--------|
| Decorator size | 200+ lines | 260 lines avg | ✅ |
| PII marking accuracy | 100% | 100% | ✅ |
| Security notes completeness | 5+ sections | 7-9 sections | ✅ |
| Example count | 3+ | 3-5 | ✅ |
| Tag count | 7-10 | 7-10 | ✅ |
| Validation pass | 0 errors | 0 errors | ✅ |

**Key Characteristics**:
1. **Comprehensive** - Every field documented, no placeholders
2. **Accurate** - PII fields correctly identified, security concerns real
3. **Helpful** - Examples show actual usage patterns, not trivial demos
4. **Specific** - Security notes address component-specific concerns, not generic advice
5. **Complete** - All dependencies, side effects, and used_by relationships documented

---

## EXAMPLE 1: Security Audit Models (PII-Heavy)

**File**: `apps/peoples/models/security_models.py`
**Components**: LoginAttemptLog, AccountLockout
**Decorator Size**: 282 lines
**Quality Score**: 10/10

### What Makes This Excellent?

#### 1. Clear, Specific Purpose Statement
```python
purpose=(
    "Security audit models for tracking authentication events, login attempts, "
    "account lockouts, and security incidents. Provides comprehensive audit trail "
    "for security analysis, incident response, and compliance reporting (SOC2, GDPR)."
)
```
✅ **Why this is good**:
- Specific components listed (not "handles authentication")
- Clear use cases: security analysis, incident response, compliance
- Mentions compliance frameworks explicitly (SOC2, GDPR)

❌ **Bad example** (avoid):
```python
purpose="Handles login stuff"  # Too vague
```

---

#### 2. Comprehensive Model Documentation
```python
models=[
    {
        "name": "LoginAttemptLog",
        "purpose": "Tracks all login attempts (success + failure) with full context for security auditing",
        "pii_fields": ["username", "ip_address", "user_agent"],
        "retention": "90 days (configurable for compliance)",
    },
    {
        "name": "AccountLockout",
        "purpose": "Active account lockouts due to failed login attempts or manual admin action",
        "pii_fields": ["username", "ip_address"],
        "business_logic": [
            "is_expired() - Check if lockout has expired",
            "unlock() - Manually unlock account"
        ],
    },
]
```
✅ **Why this is good**:
- **Every PII field listed** - username, ip_address, user_agent (100% accuracy)
- **Retention policy stated** - 90 days (shows GDPR compliance thinking)
- **Business logic documented** - is_expired(), unlock() methods explained

❌ **Bad example** (avoid):
```python
models=[
    {
        "name": "LoginAttemptLog",
        "purpose": "Login attempts",  # Too brief
        "pii_fields": [],  # WRONG! username and ip_address are PII
    }
]
```

---

#### 3. Exhaustive Input Field Documentation
```python
inputs=[
    {
        "name": "LoginAttemptLog.username",
        "type": "str",
        "description": "Username attempted (not encrypted, needed for security analysis)",
        "required": True,
        "sensitive": True,  # ✅ CRITICAL - marked as PII
        "max_length": 255,
    },
    {
        "name": "LoginAttemptLog.ip_address",
        "type": "IPv4/IPv6",
        "description": "Client IP address for geolocation and rate limiting",
        "required": True,
        "sensitive": True,  # ✅ CRITICAL - IP is PII under GDPR
    },
    # ... 15+ more fields
]
```
✅ **Why this is good**:
- **All fields listed** - Not just "important" fields, ALL fields from both models
- **sensitive: True** - EVERY PII field correctly marked (username, ip_address, user_agent, etc.)
- **Specific types** - "IPv4/IPv6" not just "string"
- **Context in descriptions** - "not encrypted, needed for security analysis" explains WHY

❌ **Bad example** (avoid):
```python
inputs=[
    {
        "name": "username",  # Missing model prefix (LoginAttemptLog.username)
        "type": "string",    # Too generic (use "str")
        "description": "The username",  # Not helpful
        "sensitive": False,  # WRONG! Username is PII
    }
]
```

---

#### 4. Detailed Security Notes (7 Sections)
```python
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"

    "1. PII Data Storage:\n"
    "   - username: Stored plaintext (required for audit queries)\n"
    "   - ip_address: Stored plaintext (required for geolocation)\n"
    "   - user_agent: Stored plaintext (required for device analysis)\n"
    "   ➡️ GDPR Article 4 (Personal Data): Lawful basis = Legitimate Interest\n\n"

    "2. Retention Policy:\n"
    "   - LoginAttemptLog: 90 days retention (configurable)\n"
    "   - AccountLockout: Deleted on unlock or expiration\n"
    "   - Cleanup job: Celery beat task runs daily\n\n"

    "3. Rate Limiting Integration:\n"
    "   - Middleware checks LoginAttemptLog for throttling\n"
    "   - 5 failed attempts → 15-min IP lockout\n"
    "   - 10 failed attempts → 1-hour username lockout\n\n"

    "4. Account Lockout Security:\n"
    "   - Manual unlock requires admin permissions\n"
    "   - Automatic unlock on expiration (is_expired() check)\n"
    "   - Lockout events logged to SecurityIncidentLog\n\n"

    "5. Access Controls:\n"
    "   - LoginAttemptLog: Read-only for admins, no user access\n"
    "   - AccountLockout: Admin read/write, users can view their own\n\n"

    "6. Correlation ID Tracking:\n"
    "   - LoginAttemptLog.correlation_id links to distributed tracing\n"
    "   - Enables cross-service security analysis\n\n"

    "7. NEVER:\n"
    "   - Store passwords (even hashed) in LoginAttemptLog\n"
    "   - Expose LoginAttemptLog data via public API\n"
    "   - Allow bulk export without audit logging\n"
    "   - Delete lockouts without security team approval"
)
```
✅ **Why this is good**:
- **7 distinct sections** - PII, retention, rate limiting, lockout logic, access, correlation, anti-patterns
- **Specific security concerns** - Not generic advice ("use HTTPS"), but component-specific issues
- **GDPR compliance** - Explicitly mentions Article 4, lawful basis
- **NEVER section** - Critical anti-patterns that would break security

❌ **Bad example** (avoid):
```python
security_notes=(
    "This is a security-critical model. Use encryption and follow best practices."
)
# ❌ Too generic! What encryption? Which best practices? No specific guidance.
```

---

#### 5. Realistic Examples (5 total)
```python
examples=[
    # Example 1: Query failed login attempts
    "# Check recent failed login attempts\n"
    "from apps.peoples.models.security_models import LoginAttemptLog\n\n"
    "recent_failures = LoginAttemptLog.objects.filter(\n"
    "    username='john.doe',\n"
    "    success=False,\n"
    "    created_at__gte=timezone.now() - timedelta(minutes=15)\n"
    ").count()\n\n"
    "if recent_failures >= 5:\n"
    "    # Trigger rate limiting\n"
    "    AccountLockout.objects.create(...)",

    # Example 2: Check if account is locked
    "# Check if username is currently locked\n"
    "from apps.peoples.models.security_models import AccountLockout\n\n"
    "lockout = AccountLockout.objects.filter(\n"
    "    username='john.doe',\n"
    "    locked_until__gte=timezone.now()\n"
    ").first()\n\n"
    "if lockout and not lockout.is_expired():\n"
    "    raise ValidationError('Account is locked until {}'.format(lockout.locked_until))",

    # ... 3 more examples
]
```
✅ **Why this is good**:
- **Realistic code** - Actual usage in middleware, not "hello world"
- **Complete imports** - Shows full import paths
- **Context** - Comments explain when/why you'd use this code
- **Multiple scenarios** - Failed logins, lockout check, manual unlock, cleanup task

❌ **Bad example** (avoid):
```python
examples=[
    "LoginAttemptLog.objects.all()"  # Trivial, unhelpful
]
```

---

#### 6. Appropriate Tags (8 tags)
```python
tags=[
    "security",               # Core security
    "authentication",         # Specific domain
    "audit-trail",            # Feature
    "compliance",             # General compliance
    "soc2",                   # Specific standard
    "gdpr",                   # Specific regulation
    "pii",                    # Data sensitivity
    "django-model"            # Technology
]
```
✅ **Why this is good**:
- **8 tags** - In the 7-10 recommended range
- **Specific + General** - Both "compliance" and "soc2" + "gdpr"
- **Searchable** - Someone searching "gdpr" will find this
- **No redundancy** - Each tag adds value

---

## EXAMPLE 2: Session Management (Complex Business Logic)

**File**: `apps/peoples/models/session_models.py`
**Components**: UserSession, SessionActivityLog
**Decorator Size**: 289 lines
**Quality Score**: 10/10

### What Makes This Excellent?

#### 1. Business Logic Documentation
```python
models=[
    {
        "name": "UserSession",
        "business_logic": [
            "is_expired() - Check if session has expired (timezone.now() > expires_at)",
            "is_active() - Check if session is active (not revoked and not expired)",
            "revoke() - Revoke session and delete Django session object",
            "generate_device_fingerprint() - SHA256 hash of user_agent + ip_address",
            "get_location_display() - Human-readable location string",
            "get_device_display() - Human-readable device string",
        ],
    },
]
```
✅ **Why this is good**:
- **All methods listed** - Not just important ones, all 6 business logic methods
- **Clear signatures** - Shows what each method does
- **Implementation hints** - "(timezone.now() > expires_at)" shows the logic

**Use this pattern for**:
- State machines (list all state transition methods)
- Complex models (list all helper methods)
- Services (list all public methods)

---

#### 2. Activity Types Enumeration
```python
models=[
    {
        "name": "SessionActivityLog",
        "activity_types": [
            "login", "logout", "api_call", "page_view", "data_access",
            "permission_escalation", "suspicious_action", "ip_change"
        ],
    }
]
```
✅ **Why this is good**:
- **Complete enumeration** - All 8 activity types listed
- **Helps LLMs** - Claude knows what valid activity types are
- **Documentation** - Engineers can reference this instead of reading code

**Use this pattern for**:
- Choice fields (list all valid choices)
- State machines (list all valid states)
- Event logs (list all event types)

---

#### 3. Performance Notes
```python
performance_notes=(
    "Database Indexes:\n"
    "- Composite index: user_id + is_revoked + expires_at (session lookup)\n"
    "- Index: device_fingerprint (duplicate device detection)\n"
    "- Index: created_at (cleanup queries)\n\n"

    "Query Patterns:\n"
    "- High read volume: session validation on every authenticated request\n"
    "- Low write volume: session creation on login, updates on activity\n"
    "- select_related('user') for session queries\n\n"

    "Performance Optimizations:\n"
    "- Redis caching for active session lookups (5-min TTL)\n"
    "- Batch delete expired sessions (Celery task, off-peak hours)\n"
    "- Prefetch user data to avoid N+1 queries\n\n"

    "Bottlenecks:\n"
    "- SessionActivityLog writes can spike during high traffic\n"
    "- Use async Celery task for activity logging (don't block requests)\n"
    "- Partition table by month if > 10M rows"
)
```
✅ **Why this is good**:
- **Specific indexes** - Not "add indexes", but exact composite indexes
- **Query volume** - "High read volume: session validation on every request"
- **Optimization strategies** - Redis caching, select_related(), batching
- **Scaling guidance** - When to partition table (>10M rows)

**Use this pattern for**:
- High-traffic models (sessions, audit logs)
- Performance-critical code (rate limiting middleware)
- Large tables (attendance, activity logs)

---

## EXAMPLE 3: RBAC Capability Model

**File**: `apps/peoples/models/capability_model.py`
**Key Pattern**: Hierarchical relationships

```python
depends_on=[
    "apps.peoples.models.people.People (ForeignKey to user)",
    "apps.peoples.models.profile_model.PeopleProfile (user profile data)",
    "apps.core.middleware.tenant_isolation (enforces cross-tenant prevention)",
    "apps.core.permissions.rbac_backend (checks capabilities for authorization)",
]

used_by=[
    "apps.core.decorators.require_capability (decorator for view authorization)",
    "apps.api.middleware.api_permission_middleware (API endpoint access control)",
    "apps.y_helpdesk.views.ticket_views (checks 'helpdesk:manage_tickets' capability)",
    "apps.work_order_management.views (checks 'workorders:create' capability)",
]
```
✅ **Why this is good**:
- **Complete dependency graph** - All FK relationships, middleware, backends
- **Specific file paths** - Not "permissions module", but exact file
- **Real usage examples** - Actual views/decorators that use this model

**Use this pattern for**:
- Core models used everywhere (People, Capability, Tenant)
- Services with many consumers (audit_service, encryption_service)

---

## EXAMPLE 4: User Profile (PII-Heavy)

**File**: `apps/peoples/models/profile_model.py`
**Key Pattern**: GDPR compliance documentation

```python
security_notes=(
    "PII DATA STORAGE (GDPR Article 4 - Personal Data):\n\n"

    "1. Direct Identifiers:\n"
    "   - email: GDPR Article 4(1) - Contact information\n"
    "   - phone: GDPR Article 4(1) - Contact information\n"
    "   - name: GDPR Article 4(1) - Personal identifier\n\n"

    "2. Demographic Data:\n"
    "   - gender: GDPR Article 9 - Special category (if used for health/wellness)\n"
    "   - date_of_birth: Derived data (age calculations)\n\n"

    "3. Lawful Basis (GDPR Article 6):\n"
    "   - Legitimate Interest: Employee management, payroll, compliance\n"
    "   - Consent: Wellness features, optional data collection\n\n"

    "4. User Rights:\n"
    "   - Right to Access (Article 15): User can view own profile\n"
    "   - Right to Erasure (Article 17): Soft delete, retain logs for 90 days\n"
    "   - Right to Portability (Article 20): Export JSON endpoint\n\n"

    "5. NEVER:\n"
    "   - Store SSN/Tax ID (use encrypted_secret model instead)\n"
    "   - Expose full profile via public API without authentication\n"
    "   - Hard delete without legal team approval (compliance requirements)"
)
```
✅ **Why this is good**:
- **GDPR Article citations** - Exact articles (4, 6, 9, 15, 17, 20)
- **Lawful basis** - Legitimate Interest vs Consent
- **User rights implementation** - How Article 15/17/20 are implemented
- **Anti-patterns** - What NOT to do (SSN storage, hard deletes)

**Use this pattern for**:
- All PII-heavy models (profile, contact info, biometric data)
- Health/wellness data (journal entries, mood tracking)
- Financial data (expense claims, payroll)

---

## COMMON PATTERNS ACROSS ALL EXAMPLES

### Pattern 1: Model Prefix in Field Names
✅ **Good**:
```python
inputs=[
    {"name": "LoginAttemptLog.username", ...},
    {"name": "AccountLockout.username", ...},
]
```
❌ **Bad**:
```python
inputs=[
    {"name": "username", ...},  # Which model?
]
```

**Why**: Multiple models in one decorator need disambiguation

---

### Pattern 2: Exhaustive PII Marking
✅ **Good**:
```python
"pii_fields": ["username", "ip_address", "user_agent", "email", "phone", "name", "address"]
```
Every PII field listed, no exceptions.

❌ **Bad**:
```python
"pii_fields": ["email"]  # Missing username, phone, etc.
```

**Rule**: If validation script warns about potential PII, mark it as sensitive!

---

### Pattern 3: Security Notes Structure
**Required sections** (minimum 5):
1. **PII Data Storage** - What PII exists, GDPR articles
2. **Retention Policy** - How long data is kept
3. **Access Controls** - Who can read/write
4. **Integration Points** - How this connects to rate limiting, audit, etc.
5. **NEVER section** - Critical anti-patterns

**Optional sections** (add if relevant):
6. Encryption details
7. Multi-tenant isolation
8. Compliance specifics (SOC2 CC6.1, etc.)
9. Incident response procedures

---

### Pattern 4: Realistic Examples
✅ **Good**:
```python
examples=[
    "# Production middleware code\n"
    "lockout = AccountLockout.objects.filter(\n"
    "    username=request.user.username,\n"
    "    locked_until__gte=timezone.now()\n"
    ").first()\n"
    "if lockout:\n"
    "    raise PermissionDenied('Account locked until {}'.format(lockout.locked_until))"
]
```
Shows actual middleware logic, not trivial demo.

❌ **Bad**:
```python
examples=[
    "AccountLockout.objects.all()"
]
```
Not helpful for understanding when/why/how to use this.

---

## QUALITY CHECKLIST

Use this checklist before submitting decorator for code review:

### Completeness (6 checks)
- [ ] All 14 required fields filled (no "TODO" or "TBD")
- [ ] All model fields documented in `inputs`
- [ ] All methods documented in `business_logic` (if applicable)
- [ ] All dependencies listed in `depends_on`
- [ ] All consumers listed in `used_by`
- [ ] All PII fields marked `sensitive: True`

### Security (5 checks)
- [ ] PII fields: 100% accuracy (validation script passes)
- [ ] Security notes: 5+ sections including NEVER
- [ ] GDPR compliance: Articles cited for PII data
- [ ] Access controls documented
- [ ] Retention policy stated

### Quality (4 checks)
- [ ] Decorator size: 200+ lines (comprehensive)
- [ ] Examples: 3+ realistic code examples
- [ ] Tags: 7-10 tags from taxonomy
- [ ] Validation script: 0 errors, warnings acceptable

### Helpfulness (3 checks)
- [ ] Purpose statement: Specific, mentions use cases
- [ ] Descriptions: Context, not just field names
- [ ] Performance notes: Indexes, bottlenecks, optimizations (if applicable)

**Target**: 18/18 checks ✅

---

## REFERENCE FILES

**Phase 1 Gold-Standard Files** (Copy for your reference):

1. **apps/peoples/models/security_models.py** (282 lines)
   - PII-heavy models (username, ip_address, user_agent)
   - 7-section security notes
   - 5 realistic examples
   - **Use as template for**: Audit logs, security models

2. **apps/peoples/models/session_models.py** (289 lines)
   - Complex business logic (6 methods)
   - Activity type enumeration
   - Performance notes (indexes, caching, partitioning)
   - **Use as template for**: Session management, multi-device tracking

3. **apps/peoples/models/capability_model.py** (245 lines)
   - Hierarchical RBAC
   - Extensive depends_on/used_by documentation
   - **Use as template for**: Core models used everywhere

4. **apps/peoples/models/profile_model.py** (267 lines)
   - Heavy GDPR compliance documentation
   - User rights implementation (Article 15/17/20)
   - **Use as template for**: PII-heavy models, demographic data

---

## TIPS FOR WRITING GOLD-STANDARD DECORATORS

### Time Management
- **30-35 min** for simple components (utilities, helpers)
- **40-50 min** for complex components (services, state machines)
- **60+ min** for critical security components (encryption, auth)

Don't rush! Quality > speed.

### Research First
1. Read the source file (5-10 min)
2. Identify all PII fields (use validation script)
3. Trace dependencies (imports)
4. Find usage (grep codebase for imports)
5. Check GDPR requirements (if PII present)

### Write Iteratively
1. Start with template (5 min)
2. Fill required fields (15 min)
3. Write security notes (10 min)
4. Add examples (5 min)
5. Run validation script, fix errors (5 min)
6. Review for quality (5 min)

### Get Feedback
- Ask security team for P1 components
- Pair program with senior engineer for first few
- Reference Phase 1 examples constantly

---

**END OF GOLD-STANDARD EXAMPLES**

**Questions?** Compare your decorator side-by-side with Phase 1 examples. If yours is shorter/less detailed, you're not done yet!
