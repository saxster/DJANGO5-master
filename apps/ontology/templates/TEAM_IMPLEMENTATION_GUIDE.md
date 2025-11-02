# Ontology Implementation Guide for Development Team

**Goal:** Expand ontology decorator coverage from 56 components to 520+ components (80% of critical codebase)

**Status:** Phase 1 (Authentication/Authorization models) COMPLETE ✅
**Next:** Phases 2-6 for team to implement

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Implementation Process](#implementation-process)
3. [Quality Standards](#quality-standards)
4. [Phase-by-Phase Breakdown](#phase-by-phase-breakdown)
5. [Common Patterns](#common-patterns)
6. [Validation & Review](#validation--review)
7. [FAQs](#faqs)

---

## Quick Start

### 1. Pick a File from Your Assigned Phase

See [Phase-by-Phase Breakdown](#phase-by-phase-breakdown) for your team's assignments.

### 2. Copy the Appropriate Template

From `apps/ontology/templates/DECORATOR_TEMPLATES.md`, copy:
- **Django Models** → Model template
- **Services** → Service class template
- **Middleware** → Middleware template
- **API Views** → ViewSet/APIView template
- **Background Tasks** → Celery task template

### 3. Fill in the Placeholders

Replace all `[PLACEHOLDERS]` with actual values:
- **[DOMAIN]** → Choose from: people, operations, security, reports, etc.
- **[CONCEPT]** → High-level concept (e.g., "User Authentication")
- **[PURPOSE]** → 2-3 sentences describing what and why
- **criticality** → critical (security/PII), high (business-critical), medium, low
- **security_boundary** → True if handles auth/PII/security

### 4. Mark All PII Fields

**CRITICAL:** Set `sensitive: True` for ALL PII fields:
- Names, emails, phone numbers
- IP addresses, user agents
- Date of birth, gender, employment dates
- Profile images (biometric data)
- Location data (GPS, addresses)

### 5. Document Security Boundaries

**Minimum 3 security aspects** in `security_notes`:
1. **Data sensitivity** (what PII is stored, GDPR compliance)
2. **Access controls** (who can access, permission requirements)
3. **NEVER section** (anti-patterns, security violations)

### 6. Add Usage Examples

**Minimum 2-3 examples** showing:
- How to use the component
- Common patterns
- Error handling (if applicable)

### 7. Validate Before Committing

```bash
# Run validation script (creates one in Step 3)
python scripts/validate_ontology_decorators.py --file path/to/your/file.py

# Expected output: "✅ All checks passed"
```

---

## Implementation Process

### Recommended Workflow

**Time estimate:** 30-45 minutes per file (comprehensive quality)

1. **Read the code** (5-10 min)
   - Understand purpose and business logic
   - Identify all inputs, outputs, side effects
   - Note security implications
   - Check dependencies (imports, ForeignKeys)

2. **Copy template** (1 min)
   - Choose correct template type
   - Paste at top of file (after imports, before class/function)

3. **Fill basic metadata** (5-10 min)
   - domain, concept, purpose
   - criticality, security_boundary
   - tags (at least 5)

4. **Document inputs/outputs** (10-15 min)
   - List all parameters/fields with types
   - Mark PII fields as `sensitive: True`
   - Document constraints and validation

5. **Document side effects** (5 min)
   - Database writes
   - Cache operations
   - API calls
   - Event triggers

6. **Fill security_notes** (10-15 min)
   - Data sensitivity
   - Access controls
   - Compliance requirements (GDPR, SOC2)
   - Anti-patterns (NEVER section)

7. **Add examples** (5-10 min)
   - At least 2-3 usage examples
   - Show common patterns
   - Include error handling

8. **Validate** (2 min)
   - Run validation script
   - Fix any errors
   - Commit!

---

## Quality Standards

### Required Fields

**Every decorator MUST have:**

✅ `domain` - From standard domain list
✅ `concept` - Clear high-level description
✅ `purpose` - 2-3 sentences (what and why)
✅ `criticality` - Appropriate level
✅ `security_boundary` - True/False
✅ `inputs` - All parameters/fields
✅ `outputs` - Return values
✅ `side_effects` - Database writes, API calls, etc.
✅ `depends_on` - All dependencies
✅ `used_by` - All consumers
✅ `tags` - At least 5 relevant tags
✅ `security_notes` - Minimum 3 aspects + NEVER section
✅ `performance_notes` - Query patterns, indexes, optimizations
✅ `examples` - Minimum 2-3 usage examples

### PII Field Marking

**CRITICAL:** ALL PII fields MUST have `sensitive: True`

**PII includes:**
- Names (first, last, full name)
- Contact info (email, phone, address)
- Identifiers (SSN, national ID, passport, driver's license)
- Demographics (date of birth, gender, race, ethnicity)
- Biometrics (photos, fingerprints, face scans)
- Location data (GPS coordinates, IP addresses)
- Employment data (salary, job title, performance reviews)
- Health data (medical records, disability status)

**Example:**
```python
inputs=[
    {
        "name": "email",
        "type": "EmailField",
        "description": "User email address",
        "required": True,
        "sensitive": True,  # ← ALWAYS True for PII
    },
]
```

### Security Notes Requirements

**Minimum 3 sections + NEVER:**

1. **Data Sensitivity**
   - What PII is stored
   - GDPR compliance (Articles 15, 16, 17)
   - Encryption requirements

2. **Access Controls**
   - Who can access (users, admins, system)
   - Permission requirements
   - Authentication requirements

3. **[Domain-Specific]**
   - Rate limiting (for auth)
   - Multi-tenant isolation (for tenant-aware models)
   - Input validation (for user input)
   - etc.

4. **NEVER Section** (MANDATORY)
   - Security anti-patterns
   - Common mistakes to avoid
   - Compliance violations

**Example:**
```python
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"
    "1. PII Data Storage:\n"
    "   - email: Personal data (GDPR Article 4)\n"
    "   - phone: Personal data (GDPR Article 4)\n\n"
    "2. Access Controls:\n"
    "   - Users can view/edit their own profile only\n"
    "   - Admins require 'view_userprofile' permission\n\n"
    "3. NEVER:\n"
    "   - Expose email in public API responses\n"
    "   - Allow unauthenticated access to profiles"
)
```

---

## Phase-by-Phase Breakdown

### Phase 1: Authentication & User Management ✅ COMPLETE

**Status:** 4/4 models decorated (security_models, session_models, capability_model, profile_model)
**Gold-standard examples** - Use these as reference!

**Remaining (for team):**
- [ ] `apps/peoples/services/password_management_service.py`
- [ ] `apps/peoples/services/login_throttling_service.py`
- [ ] `apps/peoples/services/audit_logging_service.py`

**Estimated time:** 2-3 hours total (3 files × 45 min)

---

### Phase 2: Core Security Infrastructure

**Priority:** CRITICAL (security boundaries)
**Files:** 20 components (7 high-priority listed below)
**Estimated time:** 10-15 hours

**High-Priority Files:**
- [ ] `apps/core/services/encryption_key_manager.py` (encryption key rotation)
- [ ] `apps/core/services/secure_file_upload_service.py` (file validation)
- [ ] `apps/core/services/unified_audit_service.py` (audit logging)
- [ ] `apps/core/services/secure_encryption_service.py` (encryption operations)
- [ ] `apps/core/models/encrypted_secret.py` (secrets storage)
- [ ] `apps/core/models/api_authentication.py` (API auth)
- [ ] `apps/core/models/audit.py` (audit trail)

**Criticality:** ALL files are `critical`
**Security boundary:** ALL are `True`
**PII:** Most files handle sensitive data

**Template:** Use Service Class template or Model template

---

### Phase 3: Security Middleware Stack

**Priority:** CRITICAL (OWASP compliance)
**Files:** 10 components (5 high-priority listed below)
**Estimated time:** 6-9 hours

**High-Priority Files:**
- [ ] `apps/core/middleware/rate_limiting.py` (DoS protection)
- [ ] `apps/core/middleware/csrf_rotation.py` (CSRF defense)
- [ ] `apps/core/middleware/file_upload_security_middleware.py` (file upload validation)
- [ ] `apps/core/middleware/input_sanitization_middleware.py` (XSS prevention)
- [ ] `apps/core/middleware/multi_tenant_url.py` (tenant isolation)

**Criticality:** ALL files are `critical`
**Security boundary:** ALL are `True`
**OWASP:** Document which OWASP Top 10 issues are addressed

**Template:** Use Middleware template

**Special notes:**
- **Performance:** Middleware runs on EVERY request - document performance impact
- **Bypass conditions:** Document when middleware is skipped (if applicable)

---

### Phase 4: Attendance & Geofencing

**Priority:** HIGH (PII + GPS fraud detection)
**Files:** 6-8 components
**Estimated time:** 4-6 hours

**Files:**
- [ ] `apps/attendance/models.py` (PeopleEventlog - attendance PII)
- [ ] `apps/attendance/services/geofence_validation_service.py` (GPS validation)
- [ ] `apps/attendance/services/attendance_calculation_service.py` (calculations)

**Criticality:** `critical` (contains PII)
**Security boundary:** `True`
**PII:** GPS coordinates, timestamps, user IDs

**Template:** Use Model template or Service Class template

**Special notes:**
- **GPS fraud:** Document GPS spoofing prevention
- **Geofencing:** Document accuracy thresholds, hysteresis

---

### Phase 5: Reports & Compliance

**Priority:** HIGH (regulatory compliance)
**Files:** 10-12 components
**Estimated time:** 6-8 hours

**Files:**
- [ ] `apps/reports/models.py` (ReportHistory, ScheduleReport)
- [ ] `apps/reports/services/report_generation_service.py` (PDF generation)
- [ ] `apps/reports/services/streaming_pdf_service.py` (large PDFs)
- [ ] `apps/reports/services/secure_report_upload_service.py` (report uploads)

**Criticality:** `high` (compliance reporting)
**Security boundary:** `True` (may contain PII in reports)
**Compliance:** Document SOC2, GDPR, industry-specific regulations

**Template:** Use Model template or Service Class template

**Special notes:**
- **PII in reports:** Document data minimization strategies
- **Report retention:** Document retention policies
- **Access controls:** Who can view/generate reports

---

### Phase 6: Work Orders & Jobs

**Priority:** HIGH (core business operations)
**Files:** 20-25 components
**Estimated time:** 12-15 hours

**Files:**
- [ ] `apps/work_order_management/models.py`
- [ ] `apps/work_order_management/services.py`
- [ ] `apps/work_order_management/views/work_order_views.py`
- [ ] `apps/work_order_management/state_machines/workorder_state_machine.py`
- [ ] `apps/activity/services/job_workflow_service.py`
- [ ] `apps/activity/services/task_sync_service.py`

**Criticality:** `high`
**Security boundary:** `False` (typically, unless handles PII)

**Template:** Use Model template or Service Class template

**Special notes:**
- **State machines:** Document all states and transitions
- **Workflow validation:** Document business rules and constraints
- **Performance:** Document N+1 query prevention

---

## Common Patterns

### Pattern 1: Multi-Tenant Models

**All tenant-aware models** inherit from `TenantAwareModel` and MUST document:

```python
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"
    "1. Multi-Tenant Isolation:\n"
    "   - Each record scoped to client organization (via client FK)\n"
    "   - Tenant A cannot access Tenant B's data\n"
    "   - ENFORCE: Always filter by client in queries (TenantAwareModel does this automatically)\n\n"
    # ... more notes
)
```

### Pattern 2: PII-Heavy Models

**Models with >3 PII fields:**

```python
models=[
    {
        "name": "ModelName",
        "purpose": "...",
        "pii_fields": ["field1", "field2", "field3"],  # List ALL PII
        "retention": "90 days after account deletion (GDPR Article 17)",
        "gdpr_compliance": [
            "Article 15: Right to access (user can download data)",
            "Article 16: Right to rectification (user can update fields)",
            "Article 17: Right to erasure (data deleted per retention policy)",
        ],
    },
],
```

### Pattern 3: Security Middleware

**All security middleware:**

```python
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"
    "1. [Security Feature]:\n"
    "   - [Implementation]\n\n"
    "2. OWASP Top 10 2021 Compliance:\n"
    "   - A01: Broken Access Control → [how addressed]\n"
    "   - A03: Injection → [how addressed]\n"
    "   # etc.\n\n"
    "3. Performance Impact:\n"
    "   - Executes on EVERY request\n"
    "   - [Performance characteristic]\n\n"
    "4. NEVER:\n"
    "   - Disable this middleware in production\n"
    "   - [Other anti-patterns]"
)
```

### Pattern 4: Service Classes with External APIs

**Services that call external APIs:**

```python
side_effects=[
    "Makes HTTP request to [external service]",
    "Network timeout: (5, 15) seconds (connect, read)",
    "Retry policy: [policy description]",
    "Logs API call to audit trail",
],
depends_on=[
    "External service: [service name] ([API documentation URL])",
    "requests library (with timeout enforcement)",
],
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"
    "1. Network Timeouts:\n"
    "   - ALWAYS include timeout parameter (prevent worker hangs)\n"
    "   - Connect timeout: 5 seconds\n"
    "   - Read timeout: 15 seconds\n\n"
    "2. API Key Security:\n"
    "   - API keys stored in environment variables (never hardcoded)\n"
    "   - Rotated every [frequency]\n\n"
    "3. NEVER:\n"
    "   - Make external API calls without timeouts\n"
    "   - Log API keys or secrets"
)
```

---

## Validation & Review

### Pre-Commit Validation

**Before committing**, run the validation script:

```bash
# Validate single file
python scripts/validate_ontology_decorators.py --file apps/peoples/models/your_file.py

# Validate all files in app
python scripts/validate_ontology_decorators.py --app peoples

# Validate all modified files
python scripts/validate_ontology_decorators.py --git-diff
```

**Expected checks:**
- ✅ Decorator is present
- ✅ All required fields filled in
- ✅ PII fields marked as `sensitive: True`
- ✅ security_notes has minimum 3 sections + NEVER
- ✅ At least 2 examples provided
- ✅ performance_notes present (for models/services)

### Code Review Checklist

**Reviewers should verify:**

- [ ] Decorator is comprehensive (not just skeleton)
- [ ] All PII fields are marked `sensitive: True`
- [ ] Security notes address real security concerns (not generic)
- [ ] Examples are helpful and accurate
- [ ] Dependencies and usage are documented
- [ ] Performance implications are documented (for high-traffic code)
- [ ] GDPR compliance documented (for PII-heavy models)

### Coverage Dashboard

**Track progress:**

```bash
# View coverage dashboard
python manage.py extract_ontology --output exports/ontology/current.json
# Then visit: http://localhost:8000/ontology/dashboard/
```

**Metrics tracked:**
- Total components decorated
- Coverage % by app
- Coverage % by domain
- Critical component coverage %
- Top gaps (undecorated critical components)

---

## FAQs

### Q: How do I know if a field is PII?

**A:** If the field contains data that can identify an individual (directly or indirectly), it's PII.

**PII examples:**
- ✅ Name, email, phone number
- ✅ Date of birth, gender, photo
- ✅ IP address, user agent
- ✅ GPS coordinates, address
- ✅ Employee ID, SSN, passport number

**Not PII:**
- ❌ System-generated UUIDs (if random, not sequential)
- ❌ Aggregate statistics (e.g., total count)
- ❌ Configuration flags (e.g., theme preference)

**When in doubt:** Mark as `sensitive: True` (safer to over-classify)

---

### Q: What criticality level should I use?

**A:** Use this decision tree:

**critical:**
- Handles authentication or authorization
- Stores PII or sensitive data
- Security boundary (encryption, secrets, audit logging)
- Failure causes complete system outage

**high:**
- Core business functionality
- Failure causes degraded service
- Revenue-impacting features

**medium:**
- Standard features
- Failure has localized impact

**low:**
- UI helpers, formatting utilities
- Non-essential features

---

### Q: How detailed should security_notes be?

**A:** **Comprehensive for critical components, focused for others:**

**Critical components** (auth, PII, encryption):
- 5-9 sections covering all security aspects
- Detailed GDPR compliance (Articles 15, 16, 17)
- Specific access control requirements
- Example: See `apps/peoples/models/profile_model.py`

**High components** (business logic, APIs):
- 3-5 sections covering main security aspects
- Access controls, input validation
- Example: See `apps/peoples/models/capability_model.py`

**Medium/Low components:**
- 2-3 sections covering relevant security
- Focus on most important aspects

**All components:**
- MUST have NEVER section (anti-patterns)

---

### Q: What if I don't know the performance characteristics?

**A:** **Use these guidelines:**

**Models:**
```python
performance_notes=(
    "Database Indexes:\n"
    "- [List indexes from Meta class or migrations]\n\n"
    "Query Patterns:\n"
    "- [High/Medium/Low] read volume\n"
    "- [High/Medium/Low] write volume\n\n"
    "Performance Optimizations:\n"
    "- Use select_related() for [FK field] (prevent N+1)\n"
    "- Cache [data] with [TTL] (if applicable)"
)
```

**Services:**
```python
performance_notes=(
    "Execution Characteristics:\n"
    "- Time complexity: O([notation]) or ~[duration] per call\n\n"
    "Caching Strategy:\n"
    "- [What is cached, TTL, invalidation]\n\n"
    "Scaling Considerations:\n"
    "- [How it scales with data volume]"
)
```

**If unknown:** Document "TODO: Profile performance characteristics" and ask team lead.

---

### Q: Can I use AI to help write decorators?

**A:** **Yes, with validation!**

**Recommended workflow:**
1. Ask AI (Claude, ChatGPT) to generate decorator based on code
2. **Review AI output carefully** (AI may hallucinate dependencies or security concerns)
3. Validate security_notes against actual security requirements
4. Ensure PII fields are correctly identified
5. Verify examples are accurate
6. Run validation script

**Warning:** **Never trust AI blindly for security-critical information**. Always verify:
- PII field identification
- Security boundaries
- GDPR compliance
- Access control requirements

---

### Q: What if the file is too complex to understand in 45 minutes?

**A:** **Ask for help!**

**Options:**
1. **Pair with domain expert** - Schedule 30-minute pairing session
2. **Review existing tests** - Tests often clarify usage and edge cases
3. **Check documentation** - Look for related docs in `docs/` directory
4. **Ask on team chat** - Someone may have context
5. **Start with basics** - Fill in what you know, mark TODOs for unknown parts

**It's OK to:**
- Mark sections as "TODO: Verify with domain expert"
- Ask questions in PR comments
- Request review from multiple team members

**It's NOT OK to:**
- Guess security requirements
- Guess PII field classifications
- Leave decorator incomplete

---

### Q: How do I handle legacy code that's unclear or poorly documented?

**A:** **Document what you can observe:**

```python
@ontology(
    domain="[domain]",
    purpose=(
        "[What the code appears to do based on reading it]\n"
        "NOTE: Legacy code - purpose inferred from implementation. "
        "TODO: Verify with original author or domain expert."
    ),
    # ... other fields
    security_notes=(
        "CRITICAL SECURITY BOUNDARIES:\n\n"
        "NOTE: Legacy code - security boundaries need verification.\n\n"
        "1. Observed behavior:\n"
        "   - [What you see in the code]\n\n"
        "2. TODO:\n"
        "   - Verify PII field identification\n"
        "   - Confirm access control requirements\n"
        "   - Validate GDPR compliance"
    ),
)
```

**Then:**
- Tag PR with "legacy-code-documentation"
- Request review from team lead + domain expert
- Schedule follow-up to complete TODOs

---

## Success Metrics

### Individual Contributor

**Target:** 1-2 files per day (comprehensive quality)

**Good pace:**
- Week 1: 5-10 files (learning phase)
- Week 2: 10-15 files (proficiency)
- Week 3+: 10-20 files/week (optimized workflow)

### Team (10 developers)

**Phase 1 (Auth):** ✅ COMPLETE
**Phase 2 (Core Security):** 2 weeks
**Phase 3 (Middleware):** 1 week
**Phase 4 (Attendance):** 1 week
**Phase 5 (Reports):** 1 week
**Phase 6 (Work Orders):** 2 weeks

**Total: 7-8 weeks** to 80% coverage (520+ components)

---

## Resources

**Templates:**
- `apps/ontology/templates/DECORATOR_TEMPLATES.md`

**Examples:**
- `apps/peoples/models/security_models.py`
- `apps/peoples/models/session_models.py`
- `apps/peoples/models/capability_model.py`
- `apps/peoples/models/profile_model.py`

**Validation:**
- `scripts/validate_ontology_decorators.py` (to be created)

**Documentation:**
- `apps/ontology/README.md` (system overview)
- `apps/ontology/IMPLEMENTATION_STATUS.md` (technical details)

**Dashboard:**
- http://localhost:8000/ontology/dashboard/

---

## Getting Help

**Questions?**
1. Check this guide first
2. Review the 4 example files (Phase 1)
3. Ask in team chat
4. Schedule pairing session

**Found an issue with this guide?**
- Create issue in project tracker
- Suggest improvements in PR

---

**Let's build comprehensive code documentation together! 🚀**
