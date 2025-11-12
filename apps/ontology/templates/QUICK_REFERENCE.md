# Ontology Decorator Quick Reference

**One-page cheat sheet** for adding @ontology decorators.

---

## Minimum Viable Decorator (5 minutes)

```python
from apps.ontology.decorators import ontology

@ontology(
    domain="[people|operations|security|reports|infrastructure]",
    concept="[High-level concept]",
    purpose="[2-3 sentences: what and why]",
    criticality="[critical|high|medium|low]",
    security_boundary=[True for auth/PII/security, False otherwise],
    inputs=[{"name": "[field]", "type": "[type]", "sensitive": [True for PII]}],
    outputs=[{"name": "[return value]", "type": "[type]"}],
    side_effects=["[DB writes]", "[API calls]", "[Cache ops]"],
    depends_on=["[dependencies]"],
    used_by=["[consumers]"],
    tags=["[tag1]", "[tag2]", "[tag3]", "[tag4]", "[tag5]"],
    security_notes="CRITICAL SECURITY BOUNDARIES:\n\n1. [Aspect]:\n   - [Detail]\n\n2. NEVER:\n   - [Anti-pattern]",
    performance_notes="[Indexes, query patterns, optimizations]",
    examples=["# [Example 1]\n[code]", "# [Example 2]\n[code]"],
)
```

---

## Field Quick Reference

| Field | Required | Type | Example |
|-------|----------|------|---------|
| `domain` | ✅ | str | `"people"`, `"security"`, `"operations"` |
| `concept` | ✅ | str | `"User Authentication"` |
| `purpose` | ✅ | str | 2-3 sentences describing what and why |
| `criticality` | ✅ | str | `"critical"`, `"high"`, `"medium"`, `"low"` |
| `security_boundary` | ✅ | bool | `True` for auth/PII/security, `False` otherwise |
| `inputs` | ✅ | list[dict] | `[{"name": "email", "type": "str", "sensitive": True}]` |
| `outputs` | ✅ | list[dict] | `[{"name": "User", "type": "Model"}]` |
| `side_effects` | ✅ | list[str] | `["Creates DB record", "Logs to audit"]` |
| `depends_on` | ✅ | list[str] | `["apps.peoples.models.People"]` |
| `used_by` | ✅ | list[str] | `["LoginView", "API endpoints"]` |
| `tags` | ✅ | list[str] | `["auth", "security", "pii", "gdpr", "critical"]` |
| `security_notes` | ✅ | str | Multi-line security documentation |
| `performance_notes` | ✅ | str | Indexes, query patterns, optimizations |
| `examples` | ✅ | list[str] | `["# Example 1\ncode...", "# Example 2\ncode..."]` |

---

## Criticality Levels

| Level | When to Use | Examples |
|-------|-------------|----------|
| **critical** | Auth, PII, security boundaries, system outage if fails | AuthenticationService, People model, encryption |
| **high** | Core business functionality, revenue-impacting | WorkOrder, JobManagement, PaymentProcessing |
| **medium** | Standard features, localized impact | ReportGeneration, NotificationService |
| **low** | UI helpers, formatting, non-essential | format_date(), generate_slug() |

---

## PII Field Marking (CRITICAL!)

**ALWAYS set `sensitive: True` for PII:**

| PII Category | Examples |
|--------------|----------|
| **Identity** | name, email, phone, SSN, passport, driver_license |
| **Demographics** | date_of_birth, gender, race, ethnicity, religion |
| **Biometrics** | photo, fingerprint, face_scan, voice_print |
| **Location** | GPS coordinates, IP address, home_address, city |
| **Employment** | salary, job_title, performance_review, termination_reason |
| **Health** | medical_record, disability_status, genetic_data |
| **Financial** | credit_card, bank_account, transaction_history |
| **Online** | user_agent, browsing_history, cookies, device_id |

```python
# ✅ CORRECT
inputs=[
    {
        "name": "email",
        "type": "EmailField",
        "sensitive": True,  # ← ALWAYS True for PII
    },
]

# ❌ WRONG
inputs=[
    {
        "name": "email",
        "type": "EmailField",
        "sensitive": False,  # ← GDPR violation!
    },
]
```

---

## Security Notes Template

```python
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"
    "1. [Security Aspect 1]:\n"
    "   - [Detail]\n"
    "   - [Detail]\n\n"
    "2. [Security Aspect 2]:\n"
    "   - [Detail]\n\n"
    "3. [Security Aspect 3]:\n"
    "   - [Detail]\n\n"
    "4. NEVER:\n"  # ← MANDATORY
    "   - [Anti-pattern 1]\n"
    "   - [Anti-pattern 2]\n"
    "   - [Anti-pattern 3]"
)
```

**Minimum:** 3 aspects + NEVER section
**For critical components:** 5-9 aspects + NEVER section

---

## Common Domains

| Domain | Use For |
|--------|---------|
| `people` | User auth, profiles, permissions, sessions |
| `operations` | Tasks, work orders, job management, scheduling |
| `security` | Auth, encryption, audit logging, compliance |
| `attendance` | Attendance tracking, geofencing, GPS |
| `reports` | Analytics, scheduled reports, compliance reports |
| `infrastructure` | Core utilities, middleware, base classes |
| `onboarding` | Client/contract management, site configuration |
| `assets` | Inventory, asset tracking, maintenance |
| `help_desk` | Ticketing, escalations, SLAs |
| `wellness` | Wellbeing, journal entries, health tracking |

---

## Common Tags

**Security:**
```python
tags=["authentication", "authorization", "security", "pii", "gdpr", "encryption", "audit-trail"]
```

**Operations:**
```python
tags=["background-task", "celery", "scheduled", "async", "worker", "retry-logic"]
```

**Data:**
```python
tags=["model", "database", "orm", "query-optimization", "caching"]
```

**API:**
```python
tags=["api", "rest", "websocket", "serializer", "viewset"]
```

**Features:**
```python
tags=["geofencing", "gps", "payment", "reporting", "notification", "email"]
```

---

## Validation Checklist

Before committing, verify:

- [ ] All required fields filled in (not `[PLACEHOLDER]`)
- [ ] PII fields marked `sensitive: True`
- [ ] Criticality level appropriate
- [ ] security_notes has 3+ sections + NEVER
- [ ] At least 5 tags
- [ ] At least 2 examples
- [ ] Validation script passes: `python scripts/validate_ontology_decorators.py --file path/to/file.py`

---

## Examples Location

**Gold-standard examples:**
- `apps/peoples/models/security_models.py` (2 models, audit logging)
- `apps/peoples/models/session_models.py` (2 models, device tracking)
- `apps/peoples/models/capability_model.py` (1 model, permissions)
- `apps/peoples/models/profile_model.py` (1 model, PII-heavy)

---

## Command Reference

```bash
# Validate single file
python scripts/validate_ontology_decorators.py --file apps/peoples/models/your_file.py

# Validate entire app
python scripts/validate_ontology_decorators.py --app peoples

# Validate modified files (git diff)
python scripts/validate_ontology_decorators.py --git-diff

# Validate all files
python scripts/validate_ontology_decorators.py --all

# Extract ontology metadata
python manage.py extract_ontology --output exports/ontology/current.json

# View coverage dashboard
# http://localhost:8000/ontology/dashboard/
```

---

## Time Estimates

| Task | Time |
|------|------|
| Read code & understand | 5-10 min |
| Copy template & fill basics | 5-10 min |
| Document inputs/outputs/side effects | 10-15 min |
| Write security_notes | 10-15 min |
| Add examples | 5-10 min |
| Validate & commit | 2-5 min |
| **TOTAL** | **30-45 min/file** |

---

## Common Mistakes

❌ **Forgetting `sensitive: True` for PII**
```python
# WRONG
{"name": "email", "type": "str", "sensitive": False}  # GDPR violation!

# CORRECT
{"name": "email", "type": "str", "sensitive": True}
```

❌ **Generic security_notes**
```python
# WRONG
security_notes="This is secure."  # Too vague!

# CORRECT
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"
    "1. PII Data:\n"
    "   - email: GDPR Article 4 personal data\n"
    "   - Encrypted at rest via Fernet\n\n"
    "2. Access Controls:\n"
    "   - Users can only view own profile\n\n"
    "3. NEVER:\n"
    "   - Expose email in public API"
)
```

❌ **Wrong criticality level**
```python
# WRONG
criticality="low"  # For a model storing user passwords!

# CORRECT
criticality="critical"  # Authentication is always critical
```

❌ **Missing examples**
```python
# WRONG
examples=[]  # No examples provided

# CORRECT
examples=[
    "# Get user by email\n"
    "user = People.objects.get(email='user@example.com')\n",
    "# Create new user\n"
    "user = People.objects.create(email='...', password='...')\n",
]
```

---

## Getting Help

1. **Check templates:** `apps/ontology/templates/DECORATOR_TEMPLATES.md`
2. **Review examples:** See 4 completed files in `apps/peoples/models/`
3. **Read guide:** `apps/ontology/templates/TEAM_IMPLEMENTATION_GUIDE.md`
4. **Ask team:** Post in team chat or schedule pairing session
5. **Validate:** Run validation script before asking for help

---

## Resources

| Resource | Location |
|----------|----------|
| **Templates** | `apps/ontology/templates/DECORATOR_TEMPLATES.md` |
| **Guide** | `apps/ontology/templates/TEAM_IMPLEMENTATION_GUIDE.md` |
| **Validation Script** | `scripts/validate_ontology_decorators.py` |
| **Examples** | `apps/peoples/models/*.py` (4 files) |
| **Dashboard** | http://localhost:8000/ontology/dashboard/ |
| **System README** | `apps/ontology/README.md` |

---

**Print this page and keep it next to your keyboard! 📋**
