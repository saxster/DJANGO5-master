# Tenant Manager Inheritance Audit Report

**Date**: November 11, 2025
**Severity**: CRITICAL
**Type**: IDOR Vulnerability Assessment

---

## Executive Summary

Comprehensive audit of all 176 TenantAwareModel subclasses revealed **19 models (10.8%)** with vulnerable manager configurations that bypass automatic tenant filtering, creating potential IDOR (Insecure Direct Object Reference) vulnerabilities.

### Impact Assessment

- **Total tenant-aware models**: 176
- **Safe configurations**: 157 (89.2%)
- **Vulnerable configurations**: 19 (10.8%)
- **Risk level**: CRITICAL - Cross-tenant data access possible

---

## Audit Findings

### Safe Models (157 total)

**Default Manager Inheritance** (140 models)
- Models without explicit `objects` manager
- Automatically inherit `TenantAwareManager()` from base class
- ✅ **SAFE** - Automatic tenant filtering active

**Explicit TenantAwareManager** (16 models)
- Models with `objects = TenantAwareManager()`
- ✅ **SAFE** - Tenant filtering preserved

**Custom Managers Inheriting TenantAwareManager** (1 model)
- `noc.NOCIncident` - Uses `OptimizedIncidentManager(TenantAwareManager)`
- ✅ **SAFE** - Tenant filtering preserved with custom methods

---

## Vulnerable Models (19 total)

These models use custom managers that **DO NOT** inherit from `TenantAwareManager`, causing queries to bypass tenant filtering:

### Core People & Authentication (5 models)

1. **`peoples.People`** - `PeopleManager`
   - **Impact**: PRIMARY USER MODEL - Critical vulnerability
   - **Risk**: Cross-tenant user access, authentication bypass
   - **File**: `apps/peoples/models/user_model.py:129`

2. **`peoples.Pgroup`** - `PgroupManager`
   - **Impact**: User group management
   - **Risk**: Cross-tenant group access
   - **File**: `apps/peoples/models/group_model.py:33`

3. **`peoples.Pgbelonging`** - `PgblngManager`
   - **Impact**: Group membership
   - **Risk**: Cross-tenant membership exposure
   - **File**: `apps/peoples/models/membership_model.py:18`

4. **`peoples.Capability`** - `CapabilityManager`
   - **Impact**: Permission/capability system
   - **Risk**: Cross-tenant permission access
   - **File**: `apps/peoples/models/capability_model.py:264`

5. **`attendance.PeopleEventlog`** - `PELManager`
   - **Impact**: Attendance tracking (check-in/out)
   - **Risk**: Cross-tenant attendance data exposure
   - **File**: `apps/attendance/models/people_eventlog.py:69`

### Activity & Asset Management (5 models)

6. **`activity.Attachment`** - `AttachmentManager`
   - **Impact**: File attachments
   - **Risk**: Cross-tenant file access (DATA LEAK)
   - **File**: `apps/activity/models/attachment_model.py:11`

7. **`activity.Location`** - `LocationManager`
   - **Impact**: Location/site management
   - **Risk**: Cross-tenant location data
   - **File**: `apps/activity/models/location_model.py:16`

8. **`activity.Asset`** - `AssetManager`
   - **Impact**: Asset tracking
   - **Risk**: Cross-tenant asset visibility
   - **File**: `apps/activity/models/asset_model.py:216`

9. **`activity.AssetLog`** - `AssetLogManager`
   - **Impact**: Asset history/logs
   - **Risk**: Cross-tenant audit trail exposure
   - **File**: `apps/activity/models/asset_model.py:351`

10. **`activity.Question`** - `QuestionManager`
    - **Impact**: Dynamic forms/questions
    - **Risk**: Cross-tenant form data
    - **File**: `apps/activity/models/question_model.py:16`

11. **`activity.QuestionSet`** - `QuestionSetManager`
    - **Impact**: Question sets
    - **Risk**: Cross-tenant survey data
    - **File**: `apps/activity/models/question_model.py:179`

12. **`activity.QuestionSetBelonging`** - `QsetBlngManager`
    - **Impact**: Question set associations
    - **Risk**: Cross-tenant configuration exposure
    - **File**: `apps/activity/models/question_model.py:295`

### Work Order Management (4 models)

13. **`work_order_management.Wom`** - `WorkOrderManager`
    - **Impact**: Work orders
    - **Risk**: Cross-tenant work order access
    - **File**: `apps/work_order_management/models/work_order.py:251`

14. **`work_order_management.WomDetails`** - `WOMDetailsManager`
    - **Impact**: Work order details
    - **Risk**: Cross-tenant work order data
    - **File**: `apps/work_order_management/models/wom_details.py:18`

15. **`work_order_management.Vendor`** - `VendorManager`
    - **Impact**: Vendor management
    - **Risk**: Cross-tenant vendor data
    - **File**: `apps/work_order_management/models/vendor.py:16`

16. **`work_order_management.Approver`** - `ApproverManager`
    - **Impact**: Approval workflows
    - **Risk**: Cross-tenant approver visibility
    - **File**: `apps/work_order_management/models/approver.py:17`

### Client Onboarding (2 models)

17. **`client_onboarding.Device`** - `DeviceManager`
    - **Impact**: Device registry
    - **Risk**: Cross-tenant device data
    - **File**: `apps/client_onboarding/models/device.py:19`

18. **`client_onboarding.Shift`** - `ShiftManager`
    - **Impact**: Shift scheduling
    - **Risk**: Cross-tenant schedule exposure
    - **File**: `apps/client_onboarding/models/scheduling.py:36`

### Core Onboarding (1 model)

19. **`core_onboarding.TypeAssist`** - `TypeAssistManager`
    - **Impact**: Type assistance/classification
    - **Risk**: Cross-tenant classification data
    - **File**: `apps/core_onboarding/models/classification.py:33`

---

## Defense-in-Depth Measures Implemented

### 1. Runtime Enforcement (`__init_subclass__()`)

Added to `TenantAwareModel` to validate manager inheritance at class definition time:

```python
def __init_subclass__(cls, **kwargs):
    """
    Validate manager inheritance when subclass is defined.
    Logs CRITICAL security warning if 'objects' manager doesn't
    inherit from TenantAwareManager.
    """
```

**Location**: `apps/tenants/models.py:196-256`

**Behavior**:
- ✅ Validates manager inheritance on model import
- ✅ Logs CRITICAL security warnings to audit log
- ✅ Non-blocking (doesn't break existing code)
- ✅ Skips abstract models and migrations

### 2. Audit Script

**Script**: `scripts/audit_tenant_aware_models.py`

**Capabilities**:
- Scans all 247 model files across codebase
- Detects TenantAwareModel subclasses using AST parsing
- Validates manager inheritance chains
- Generates detailed vulnerability reports
- Supports `--fix` flag for remediation guidance

**Usage**:
```bash
# Run audit
python scripts/audit_tenant_aware_models.py --verbose

# Generate fix suggestions
python scripts/audit_tenant_aware_models.py --fix
```

### 3. Comprehensive Test Suite

**File**: `apps/tenants/tests/test_tenant_manager_inheritance.py`

**Test Coverage**:
- Default manager inheritance validation
- Explicit TenantAwareManager declaration
- Custom manager inheritance chains
- Unsafe manager detection via `__init_subclass__()`
- Tenant isolation with custom managers
- Multi-level manager inheritance
- Cross-tenant query behavior
- Audit of critical production models
- Documentation of known vulnerabilities

**Run Tests**:
```bash
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.development \
    python -m pytest apps/tenants/tests/test_tenant_manager_inheritance.py -v
```

---

## Remediation Plan

### Phase 1: Immediate Actions (Week 1)

**Priority**: CRITICAL models (Primary user model and attachments)

1. **`peoples.People`** - Update `PeopleManager` to inherit from `TenantAwareManager`
2. **`activity.Attachment`** - Update `AttachmentManager` (file access vulnerability)
3. **`attendance.PeopleEventlog`** - Update `PELManager` (attendance tracking)

### Phase 2: High Priority (Week 2)

**Priority**: Permission and authentication systems

4. **`peoples.Pgroup`** - Update `PgroupManager`
5. **`peoples.Pgbelonging`** - Update `PgblngManager`
6. **`peoples.Capability`** - Update `CapabilityManager`

### Phase 3: Medium Priority (Weeks 3-4)

**Priority**: Business logic models

7-12. **Activity models** (Asset, Location, Question, etc.)
13-16. **Work Order Management** models
17-18. **Client Onboarding** models

### Phase 4: Final Validation (Week 5)

19. **`core_onboarding.TypeAssist`**
- Re-run audit script to verify 0 vulnerabilities
- Run full test suite
- Security penetration testing
- Update this document with completion status

---

## Migration Pattern

### Example: Fixing PeopleManager

**Before** (VULNERABLE):
```python
# apps/peoples/managers.py
class PeopleManager(models.Manager):
    def active_users(self):
        return self.filter(is_active=True)
```

**After** (SAFE):
```python
# apps/peoples/managers.py
from apps.tenants.managers import TenantAwareManager

class PeopleManager(TenantAwareManager):  # ← Inherit from TenantAwareManager
    def active_users(self):
        return self.filter(is_active=True)  # Still tenant-scoped!
```

**Benefits**:
- ✅ Preserves all custom manager methods
- ✅ Adds automatic tenant filtering
- ✅ Minimal code changes required
- ✅ Backward compatible

---

## Verification Checklist

After fixing each model:

- [ ] Manager class inherits from `TenantAwareManager`
- [ ] Run audit script - model no longer in vulnerable list
- [ ] Check logs for `__init_subclass__()` security warnings
- [ ] Run model-specific tests
- [ ] Verify tenant isolation with integration tests
- [ ] Update this document

---

## Monitoring & Detection

### Production Monitoring

**Log Query**: Search for security event `TENANT_MANAGER_INHERITANCE_VIOLATION`

```json
{
  "security_event": "TENANT_MANAGER_INHERITANCE_VIOLATION",
  "severity": "CRITICAL",
  "model": "VulnerableModel",
  "manager_class": "UnsafeManager"
}
```

### Continuous Validation

**CI/CD Integration**:
```yaml
# .github/workflows/security.yml
- name: Tenant Manager Audit
  run: |
    python scripts/audit_tenant_aware_models.py
    # Exit code 1 if vulnerabilities found
```

---

## References

- **Architecture**: `apps/tenants/models.py` - TenantAwareModel base class
- **Managers**: `apps/tenants/managers.py` - TenantAwareManager implementation
- **Tests**: `apps/tenants/tests/test_tenant_manager_inheritance.py`
- **Audit Script**: `scripts/audit_tenant_aware_models.py`
- **Documentation**: `CLAUDE.md` - Secure file access standards

---

## Success Criteria

- ✅ 19/19 vulnerable models identified
- ✅ Runtime enforcement implemented (`__init_subclass__`)
- ✅ Audit script created and tested
- ✅ Comprehensive test suite (12 test cases)
- ⏳ 0/19 models remediated (target: Q1 2026)
- ⏳ CI/CD integration pending
- ⏳ Production monitoring pending

---

**Next Steps**:
1. Review this report with security team
2. Prioritize remediation based on business impact
3. Begin Phase 1 fixes (week of Nov 11, 2025)
4. Schedule security audit post-remediation

**Audit Completed By**: Claude Code Security Audit
**Report Generated**: November 11, 2025
