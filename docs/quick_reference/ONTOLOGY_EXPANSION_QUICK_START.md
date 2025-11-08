# ONTOLOGY EXPANSION - QUICK START GUIDE
**Get Your Team Started in 30 Minutes**

**Created**: 2025-11-01
**Target Audience**: Team leads, engineers joining the project
**Goal**: Understand the plan, setup tools, start decorating

---

## 🎯 THE MISSION

**Expand ontology coverage from 56 components (10.6%) to 520+ components (80%) in 20 weeks.**

**Why?** Enable LLM-assisted development, improve onboarding, reduce bugs, ensure compliance.

---

## 📚 DOCUMENTATION MAP

### **START HERE** (Read in this order):

1. **THIS FILE** (5 min) - Quick overview, essential links
2. **ONTOLOGY_EXPANSION_KICKOFF.md** (15 min) - Team meeting agenda, Week 1 plan
3. **docs/ontology/TAG_TAXONOMY.md** (10 min) - Standardized tags reference
4. **docs/ontology/GOLD_STANDARD_EXAMPLES.md** (20 min) - Annotated Phase 1 examples
5. **docs/ontology/PRE_COMMIT_HOOK_SETUP.md** (5 min) - Install validation hook

### **REFERENCE DOCUMENTS** (Bookmark these):

- **ONTOLOGY_EXPANSION_MASTER_PLAN.md** - Complete 20-week detailed plan
- **docs/ontology/TRACKING_DASHBOARD.md** - Weekly progress tracker
- **apps/ontology/templates/DECORATOR_TEMPLATES.md** - Templates for all component types
- **apps/ontology/templates/TEAM_IMPLEMENTATION_GUIDE.md** - Detailed workflow
- **apps/ontology/templates/QUICK_REFERENCE.md** - One-page cheat sheet

---

## ⏱️ 30-MINUTE QUICK START

### **Minute 1-5: Understand the Plan**

**Current State**:
- ✅ 56 components decorated (Phase 1: Authentication & Authorization)
- ✅ Infrastructure ready (validation script, dashboard, templates)
- ✅ Gold-standard established (260 lines avg, 100% PII accuracy)

**Target State**:
- 🎯 520+ components decorated (80% coverage)
- 🎯 20 weeks timeline (Weeks 1-3: Critical security, Weeks 4-20: Coverage)

**Your Role**:
- **Weeks 1-2**: Decorate Phase 2 (Core Security Infrastructure) - 20 components
- **Week 3**: Decorate Phase 3 (Security Middleware) - 10 components
- **Weeks 4+**: Business logic, API layer, tasks (390+ components)

---

### **Minute 6-10: Install Pre-Commit Hook**

**Why?** Automatic validation before every commit (enforces 100% quality).

```bash
cd /Users/amar/Desktop/MyCode/DJANGO5-master

# Step 1: Make hook executable
chmod +x .githooks/pre-commit-ontology-validation

# Step 2: Install hook (symlink method - automatic updates)
ln -sf ../../.githooks/pre-commit-ontology-validation .git/hooks/pre-commit

# Step 3: Verify installation
ls -la .git/hooks/pre-commit
# Should show: pre-commit -> ../../.githooks/pre-commit-ontology-validation

# Step 4: Test hook
git commit --allow-empty -m "test pre-commit hook"
# Should see validation output
```

**Done!** Every commit will now validate ontology decorators automatically.

---

### **Minute 11-20: Read Gold-Standard Example**

**Open**: `apps/peoples/models/security_models.py`

**What to notice**:
1. **Decorator size**: 282 lines (comprehensive, not skeleton)
2. **PII marking**: ALL PII fields marked `sensitive: True` (username, ip_address, user_agent)
3. **Security notes**: 7 sections (PII storage, retention, rate limiting, lockout, access, correlation, NEVER)
4. **Examples**: 5 realistic code examples (not "hello world")
5. **Tags**: 8 tags from taxonomy (security, authentication, audit-trail, compliance, soc2, gdpr, pii, django-model)

**Key Takeaway**: Your decorators should look like this (200+ lines, comprehensive).

---

### **Minute 21-25: Review Tag Taxonomy**

**Open**: `docs/ontology/TAG_TAXONOMY.md`

**Most Common Tags** (memorize these):

**Security** (use 2+):
- `security`, `authentication`, `authorization`, `encryption`, `pii`, `audit-trail`

**Domain** (use 1+):
- `people`, `operations`, `assets`, `reports`, `help-desk`, `attendance`

**Technology** (use 1):
- `django-model`, `django-middleware`, `drf-viewset`, `celery-task`, `django-service`

**Compliance** (use 2+ if applicable):
- `gdpr`, `soc2`, `owasp`, `owasp-a01-2021`, `fips-140-2`

**Target**: 7-10 tags per decorator (minimum 7, recommended 10).

---

### **Minute 26-30: Start Your First Decorator**

**Week 1 Assignment** (if you're Engineer 1):

**File**: `apps/core/services/encryption_key_manager.py`
**Estimated Time**: 45 minutes
**Template**: Service template from `apps/ontology/templates/DECORATOR_TEMPLATES.md`

**Quick Workflow**:
1. Read source file (5 min) - Understand what it does
2. Copy service template (2 min)
3. Fill required fields (20 min):
   - `domain`, `concept`, `purpose`
   - `inputs` (all method parameters)
   - `outputs` (return values)
   - `side_effects` (DB writes, cache updates)
   - `depends_on`, `used_by`
   - `tags` (7-10 from taxonomy)
4. Write security notes (10 min) - 5+ sections, component-specific
5. Add examples (5 min) - 3+ realistic usage examples
6. Validate (3 min):
   ```bash
   python scripts/validate_ontology_decorators.py --file apps/core/services/encryption_key_manager.py
   ```
7. Fix errors, commit (5 min)

**Done!** Your first gold-standard decorator.

---

## 🔥 WEEK 1 PRIORITIES

### **Monday (Day 1)**

**Morning**:
- 9:00 AM: Team kickoff meeting (1 hour)
- 10:00 AM: Install pre-commit hook (all engineers)
- 10:30 AM: Review gold-standard examples

**Afternoon**:
- 1:00 PM: **Engineer 1** starts `encryption_key_manager.py`
- 1:00 PM: **Engineer 2** starts `encrypted_secret.py` (model)
- 4:00 PM: Submit first PRs

**Goal**: 2 components decorated (encryption_key_manager, encrypted_secret)

---

### **Tuesday-Friday (Days 2-5)**

**Daily Workflow**:
- 9:00 AM: Standup (15 min) - Progress, blockers
- 9:15 AM-12:00 PM: Focused decorating (3-4 components/day)
- 1:00 PM-3:00 PM: Code review, validation fixes
- 3:00 PM-4:30 PM: Next component(s)

**Friday Specific**:
- 2:00 PM: **Security team review** of all 5 P1 components
- 3:00 PM: Weekly retrospective
- 4:00 PM: Celebrate Week 1 completion!

**Week 1 Goal**: 5 components (encryption_key_manager, secure_encryption_service, secrets_manager_service, pii_detection_service, encrypted_secret)

---

## 📋 ESSENTIAL COMMANDS

### **Validation**

```bash
# Validate single file
python scripts/validate_ontology_decorators.py --file apps/core/services/your_file.py

# Validate entire app
python scripts/validate_ontology_decorators.py --app core

# Validate all files (CI/CD)
python scripts/validate_ontology_decorators.py --all
```

### **Metrics**

```bash
# Extract ontology data (weekly snapshot)
python manage.py extract_ontology --output exports/ontology/week_$(date +%U).json --verbose

# View dashboard
python manage.py runserver
# Open: http://localhost:8000/ontology/dashboard/

# Quick stats
python manage.py extract_ontology --output - | jq '{total: length, by_domain: group_by(.domain) | map({domain: .[0].domain, count: length})}'
```

### **Git Workflow**

```bash
# Add decorator
git add apps/core/services/encryption_key_manager.py

# Commit (pre-commit hook runs automatically)
git commit -m "feat(ontology): Add encryption_key_manager decorator

- Comprehensive decorator (245 lines)
- HSM integration documented
- Key rotation lifecycle explained
- 8 security aspects, 4 examples
- Validation passed: 0 errors"

# Push (code review required)
git push origin feature/ontology-phase-2
```

---

## 🎯 QUALITY CHECKLIST

### **Before Committing** (Every Decorator):

- [ ] All 14 required fields filled (no "TODO" or "TBD")
- [ ] ALL PII fields marked `sensitive: True`
- [ ] 5+ security aspects (if security-related)
- [ ] 7-10 tags from taxonomy
- [ ] 3-5 realistic examples
- [ ] Dependencies documented (`depends_on`, `used_by`)
- [ ] Validation script passes: `python scripts/validate_ontology_decorators.py --file <file>`
- [ ] Decorator is 200+ lines (comprehensive)
- [ ] Pre-commit hook passes (automatic)

### **Gold-Standard Targets**:

| Metric | Target | Phase 1 Baseline |
|--------|--------|------------------|
| Decorator size | 200+ lines | 260 lines ✅ |
| PII marking accuracy | 100% | 100% ✅ |
| Security notes sections | 5+ | 7-9 ✅ |
| Example count | 3+ | 3-5 ✅ |
| Tag count | 7-10 | 7-10 ✅ |
| Validation pass | 0 errors | 0 errors ✅ |

---

## 🚨 COMMON MISTAKES (AVOID THESE)

### **Mistake 1: Skeleton Decorators**

❌ **Bad** (50 lines, minimal):
```python
@ontology(
    domain="security",
    concept="Encryption",
    purpose="Encrypts data",
    # ... only 5 fields filled
    tags=["security", "encryption"]
)
```

✅ **Good** (250 lines, comprehensive):
```python
@ontology(
    domain="security",
    concept="Encryption Key Management & HSM Integration",
    purpose=(
        "Enterprise encryption key lifecycle management with HSM integration. "
        "Handles key generation (RSA 4096, AES-256), rotation (90-day policy), "
        "key derivation (PBKDF2, 100k iterations), and secure storage. "
        "Integrates with AWS CloudHSM and Azure Key Vault for FIPS 140-2 compliance."
    ),
    # ... ALL 14 fields filled, 200+ lines total
    tags=[
        "security", "encryption", "key-management", "fips-140-2",
        "hsm-integration", "soc2", "compliance", "django-service"
    ]
)
```

---

### **Mistake 2: Missing PII Marking**

❌ **Bad** (email not marked sensitive):
```python
inputs=[
    {
        "name": "email",
        "type": "str",
        "description": "User email address",
        "sensitive": False  # WRONG! Email is PII
    }
]
```

✅ **Good** (email correctly marked):
```python
inputs=[
    {
        "name": "email",
        "type": "str",
        "description": "User email address (GDPR Article 4: Personal data)",
        "required": True,
        "sensitive": True,  # ✅ CRITICAL - Email is PII
        "max_length": 255
    }
]
```

**PII Fields** (always mark `sensitive: True`):
- email, phone, name, address, username
- ip_address, gps_coordinates, device_fingerprint
- ssn, tax_id, passport, license_number
- biometric data (fingerprint, face_id)

---

### **Mistake 3: Generic Security Notes**

❌ **Bad** (generic, not helpful):
```python
security_notes=(
    "This is a security-critical component. Use encryption and follow best practices."
)
```

✅ **Good** (specific, component-focused):
```python
security_notes=(
    "CRITICAL SECURITY BOUNDARIES:\n\n"

    "1. Key Storage:\n"
    "   - Master key stored in HSM (AWS CloudHSM)\n"
    "   - Data encryption keys stored encrypted with master key\n"
    "   - Never store plaintext keys in database or logs\n\n"

    "2. Key Rotation:\n"
    "   - Automatic rotation every 90 days (configurable)\n"
    "   - Old keys retained for 1 year (decrypt legacy data)\n"
    "   - Rotation job runs at 2 AM UTC (low traffic)\n\n"

    "3. Access Controls:\n"
    "   - Only encryption_service can call generate_key()\n"
    "   - Audit log on every key access\n"
    "   - Rate limiting: 100 key operations/min/service\n\n"

    "4. FIPS 140-2 Compliance:\n"
    "   - All algorithms FIPS-validated\n"
    "   - HSM modules are FIPS 140-2 Level 3\n"
    "   - Key derivation uses approved methods (PBKDF2)\n\n"

    "5. NEVER:\n"
    "   - Return plaintext master key from any method\n"
    "   - Log encryption keys (even hashed)\n"
    "   - Use non-FIPS algorithms\n"
    "   - Skip HSM for master key operations"
)
```

---

### **Mistake 4: Trivial Examples**

❌ **Bad** (unhelpful):
```python
examples=[
    "from apps.core.services import encryption_service\n"
    "encryption_service.encrypt('hello')"
]
```

✅ **Good** (realistic, shows actual usage):
```python
examples=[
    # Example 1: Encrypt PII field in model save
    "from apps.core.services.encryption_service import SecureEncryptionService\n\n"
    "class UserProfile(models.Model):\n"
    "    ssn_encrypted = models.BinaryField()\n\n"
    "    def save(self, *args, **kwargs):\n"
    "        if self.ssn:  # Plain SSN\n"
    "            self.ssn_encrypted = SecureEncryptionService.encrypt(\n"
    "                plaintext=self.ssn,\n"
    "                key_id='user-pii-key',\n"
    "                context={'user_id': self.user.id}  # Authenticated encryption\n"
    "            )\n"
    "            self.ssn = None  # Clear plaintext\n"
    "        super().save(*args, **kwargs)",

    # Example 2: Decrypt PII for authorized view
    "def export_user_data(request, user_id):\n"
    "    profile = UserProfile.objects.get(user_id=user_id)\n"
    "    ssn_plaintext = SecureEncryptionService.decrypt(\n"
    "        ciphertext=profile.ssn_encrypted,\n"
    "        key_id='user-pii-key',\n"
    "        context={'user_id': user_id}\n"
    "    )\n"
    "    # Log decryption for audit\n"
    "    AuditLog.log('pii_decryption', user=request.user, target_user=user_id)",

    # Example 3: Bulk encryption (avoid N+1)
    "profiles = UserProfile.objects.filter(ssn__isnull=False)\n"
    "for profile in profiles:\n"
    "    profile.ssn_encrypted = SecureEncryptionService.encrypt(\n"
    "        plaintext=profile.ssn,\n"
    "        key_id='user-pii-key'\n"
    "    )\n"
    "UserProfile.objects.bulk_update(profiles, ['ssn_encrypted'], batch_size=1000)"
]
```

---

## 🎉 MILESTONES & CELEBRATIONS

### **Week 3: First Milestone** (30 components)
- 🎉 Team lunch/dinner
- 📊 Share metrics with leadership
- 🏆 Recognition for top contributors

### **Week 9: Second Milestone** (75 components, 15% coverage)
- 🎉 Half-day team outing
- 📈 Measure actual productivity gains

### **Week 20: Final Milestone** (520+ components, 80% coverage)
- 🎉 Major celebration event
- 📚 Write case study/blog post
- 🏅 Company-wide recognition

---

## 💬 SUPPORT & COMMUNICATION

### **Daily Standup** (9:00 AM, 15 min)
- What did I decorate yesterday?
- What am I decorating today?
- Any blockers?

### **Team Channel**: `#ontology-expansion`
- Questions: "How do I classify GPS coordinates as PII?"
- Wins: "Just hit 10 components decorated! 🎉"
- Blockers: "Validation script failing, need help"

### **Weekly Demos** (Friday 3:00 PM)
- Show what we decorated this week
- Discuss interesting patterns
- Celebrate progress

### **Code Reviews**
- All decorators require 1 peer review (P1 requires security team review)
- Use PR label: `ontology`
- Review checklist in `docs/ontology/GOLD_STANDARD_EXAMPLES.md`

---

## 📖 PHASE 2 COMPONENT LIST

### **Week 1 (P1 Security Services)**

| # | Component | File | Owner | Time |
|---|-----------|------|-------|------|
| 1 | encryption_key_manager | `apps/core/services/encryption_key_manager.py` | Eng 1 | 45m |
| 2 | secure_encryption_service | `apps/core/services/secure_encryption_service.py` | Eng 1 | 40m |
| 3 | secrets_manager_service | `apps/core/services/secrets_manager_service.py` | Eng 1 | 40m |
| 4 | pii_detection_service | `apps/core/services/pii_detection_service.py` | Eng 1 | 40m |
| 5 | encrypted_secret (model) | `apps/core/models/encrypted_secret.py` | Eng 2 | 35m |

**Week 1 Goal**: 5 components, security team reviewed

---

### **Week 2 (Audit & File Services)**

| # | Component | File | Owner | Time |
|---|-----------|------|-------|------|
| 6 | unified_audit_service | `apps/core/services/unified_audit_service.py` | Eng 1 | 40m |
| 7 | secure_file_upload_service | `apps/core/services/secure_file_upload_service.py` | Eng 2 | 40m |
| 8 | file_upload_audit_service | `apps/core/services/file_upload_audit_service.py` | Eng 2 | 35m |
| 9 | api_key_validation_service | `apps/core/services/api_key_validation_service.py` | Eng 2 | 35m |
| 10-20 | Remaining core services | `apps/core/services/*.py` | Both | 5h |

**Week 2 Goal**: 20 total components (Phase 2 complete)

---

## 🚀 YOU'RE READY TO START!

**Next Actions**:
1. ✅ Install pre-commit hook (5 min)
2. ✅ Read security_models.py example (10 min)
3. ✅ Review tag taxonomy (5 min)
4. ✅ Start first decorator (45 min)

**Questions?** Ask in `#ontology-expansion` or see your tech lead.

**Good luck! Let's make this the best-documented Django project ever built.** 🎉

---

**Document Version**: 1.0
**Last Updated**: 2025-11-01
**Next Review**: After Week 1 (feedback iteration)
