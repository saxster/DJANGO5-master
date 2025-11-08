# IDOR Security Tests - Quick Start Guide

**Created:** November 6, 2025  
**Total Tests:** 141  
**Apps Covered:** 5 (peoples, attendance, activity, work_order_management, y_helpdesk)

---

## 🚀 Quick Run Commands

### Run All IDOR Tests
```bash
# All apps at once
python -m pytest \
    apps/peoples/tests/test_idor_security.py \
    apps/attendance/tests/test_idor_security.py \
    apps/activity/tests/test_idor_security.py \
    apps/work_order_management/tests/test_idor_security.py \
    apps/y_helpdesk/tests/test_idor_security.py \
    -v --tb=short

# Or using pytest marker (if configured)
python -m pytest -m idor -v
```

### Run Individual Apps
```bash
# Peoples (24 tests)
python -m pytest apps/peoples/tests/test_idor_security.py -v

# Attendance (25 tests)
python -m pytest apps/attendance/tests/test_idor_security.py -v

# Activity (29 tests)
python -m pytest apps/activity/tests/test_idor_security.py -v

# Work Order Management (29 tests)
python -m pytest apps/work_order_management/tests/test_idor_security.py -v

# Y_Helpdesk (34 tests)
python -m pytest apps/y_helpdesk/tests/test_idor_security.py -v
```

### Generate Coverage Report
```bash
python -m pytest apps/*/tests/test_idor_security.py \
    --cov=apps \
    --cov-report=html:coverage_reports/idor \
    --cov-report=term-missing
```

---

## 📊 Test Counts by App

| App | Tests | File |
|-----|-------|------|
| Peoples | 24 | `apps/peoples/tests/test_idor_security.py` |
| Attendance | 25 | `apps/attendance/tests/test_idor_security.py` |
| Activity | 29 | `apps/activity/tests/test_idor_security.py` |
| Work Order Mgmt | 29 | `apps/work_order_management/tests/test_idor_security.py` |
| Y_Helpdesk | 34 | `apps/y_helpdesk/tests/test_idor_security.py` |
| **TOTAL** | **141** | |

---

## 🎯 What Do These Tests Cover?

### Cross-Tenant Isolation (40+ tests)
Ensures users from Tenant A cannot access Tenant B data:
- ✅ View/Edit/Delete operations
- ✅ List/Query filtering
- ✅ API endpoints
- ✅ Bulk operations
- ✅ Reports

### Cross-User Privacy (25+ tests)
Ensures users cannot access each other's data:
- ✅ Profile viewing
- ✅ Record modification
- ✅ Assignment manipulation
- ✅ Comments/attachments

### Permission Boundaries (15+ tests)
Ensures regular users cannot access admin functions:
- ✅ Admin-only operations
- ✅ Privilege escalation
- ✅ Approval workflows

### Input Validation (20+ tests)
Prevents ID manipulation attacks:
- ✅ Sequential enumeration
- ✅ Negative IDs
- ✅ Invalid formats
- ✅ Path traversal

### API Security (20+ tests)
Ensures REST APIs enforce authorization:
- ✅ Detail endpoints
- ✅ List endpoints
- ✅ Bulk operations

### Workflow Security (21+ tests)
Validates business process security:
- ✅ Assignment validation
- ✅ Status transitions
- ✅ Approval requirements

---

## 🔧 Common IDOR Fixes

### 1. Add Tenant Scoping to Views
```python
# ❌ VULNERABLE
def get_work_order(request, wo_id):
    wo = Wom.objects.get(id=wo_id)
    return render(request, 'wo.html', {'wo': wo})

# ✅ SECURE
def get_work_order(request, wo_id):
    wo = Wom.objects.get(id=wo_id, client=request.user.client)
    return render(request, 'wo.html', {'wo': wo})
```

### 2. Add Ownership Checks
```python
# ❌ VULNERABLE
def update_attendance(request, id):
    att = PeopleTracking.objects.get(id=id)
    att.clockouttime = request.POST['time']
    att.save()

# ✅ SECURE
def update_attendance(request, id):
    att = PeopleTracking.objects.get(
        id=id,
        people=request.user,  # Only own records
        client=request.user.client
    )
    att.clockouttime = request.POST['time']
    att.save()
```

### 3. Fix API QuerySets
```python
# ❌ VULNERABLE
class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()

# ✅ SECURE
class TicketViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return Ticket.objects.filter(
            client=self.request.user.client
        )
```

### 4. Validate Bulk Operations
```python
# ❌ VULNERABLE
def bulk_close(request):
    ids = request.POST.getlist('ids')
    Ticket.objects.filter(id__in=ids).update(status='CLOSED')

# ✅ SECURE
def bulk_close(request):
    ids = request.POST.getlist('ids')
    Ticket.objects.filter(
        id__in=ids,
        client=request.user.client  # Scoped
    ).update(status='CLOSED')
```

---

## 📝 Remediation Workflow

### Step 1: Run Tests
```bash
python -m pytest apps/peoples/tests/test_idor_security.py -v > peoples_idor_results.txt
```

### Step 2: Identify Failures
Review test output:
- Count failing tests
- Group by IDOR type (cross-tenant, cross-user, etc.)
- Prioritize by severity

### Step 3: Fix Code
For each failing test:
1. Locate the vulnerable view/API
2. Add tenant scoping: `client=request.user.client`
3. Add ownership checks: `people=request.user`
4. Add permission checks: `@permission_required(...)`

### Step 4: Re-run Tests
```bash
python -m pytest apps/peoples/tests/test_idor_security.py -v
```

### Step 5: Verify All Pass
```bash
python -m pytest apps/*/tests/test_idor_security.py -v --tb=short
```

---

## 🎓 Test Examples

### Example 1: Cross-Tenant Test
```python
def test_user_cannot_access_other_tenant_work_order(self):
    """User from tenant A cannot access tenant B's work order"""
    self.client.force_login(self.user_a)
    
    # Try to access tenant B work order
    response = self.client.get(f'/work-orders/{self.wo_b.id}/')
    
    # Should be forbidden
    self.assertIn(response.status_code, [403, 404])
```

### Example 2: Ownership Test
```python
def test_user_cannot_edit_other_user_attendance(self):
    """User cannot modify another user's attendance"""
    self.client.force_login(self.user_a1)
    
    # Try to update user_a2's attendance
    response = self.client.post(
        f'/attendance/{self.attendance_a2.id}/update/',
        {'clockouttime': datetime.now()}
    )
    
    # Should be forbidden
    self.assertIn(response.status_code, [403, 404])
```

### Example 3: API Test
```python
def test_api_ticket_list_filtered_by_tenant(self):
    """API list endpoints scope to tenant"""
    self.client.force_login(self.user_a)
    
    response = self.client.get('/api/v1/tickets/')
    data = response.json()
    
    ticket_ids = [item['id'] for item in data['results']]
    
    # Should include tenant A tickets
    self.assertIn(self.ticket_a.id, ticket_ids)
    
    # Should NOT include tenant B tickets
    self.assertNotIn(self.ticket_b.id, ticket_ids)
```

---

## ⚡ Priority Fix Order

### P0 - CRITICAL (Week 1)
**Cross-Tenant Isolation - 40+ tests**
- Fix all views/APIs to filter by `client=request.user.client`
- Impact: Prevents catastrophic data leakage

### P1 - HIGH (Week 1-2)
**Cross-User Privacy - 25+ tests**
- Add ownership checks (`people=request.user`)
- Impact: Protects individual user data

### P2 - MEDIUM (Week 2)
**Permission Boundaries - 15+ tests**
- Add `@permission_required` decorators
- Impact: Prevents privilege escalation

### P3 - LOW (Week 2)
**Input Validation - 20+ tests**
- Validate ID formats
- Handle edge cases
- Impact: Hardens security

---

## 📈 Success Criteria

✅ **Created:** 141 comprehensive IDOR tests  
⏳ **Baseline:** Run tests to establish current state  
⏳ **Remediation:** Fix all failing tests  
⏳ **Verification:** 100% pass rate  
⏳ **Integration:** Add to CI/CD pipeline  

---

## 🔗 Related Files

### Test Files
- `apps/peoples/tests/test_idor_security.py` - User/profile IDOR tests
- `apps/attendance/tests/test_idor_security.py` - Attendance IDOR tests
- `apps/activity/tests/test_idor_security.py` - Job/task/asset IDOR tests
- `apps/work_order_management/tests/test_idor_security.py` - Work order IDOR tests
- `apps/y_helpdesk/tests/test_idor_security.py` - Ticket IDOR tests

### Documentation
- `IDOR_SECURITY_TESTS_SUMMARY.md` - Detailed overview
- `IDOR_TEST_COVERAGE_REPORT.md` - Complete test breakdown
- `.claude/rules.md` - Security rules (check before coding)

---

## 💡 Tips

1. **Run tests incrementally** - Fix one app at a time
2. **Start with critical** - Cross-tenant isolation first
3. **Use TDD approach** - Tests FAIL first, then fix code
4. **Check existing patterns** - Look at `apps/tenants/tests/` for examples
5. **Document fixes** - Note which views were vulnerable

---

## 🆘 Troubleshooting

### Tests won't run
```bash
# Check pytest is installed
python -m pip install pytest pytest-django

# Check Django settings
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings
```

### Import errors
```bash
# Ensure apps are in INSTALLED_APPS
python manage.py check

# Check __init__.py files exist
find apps/*/tests -name "__init__.py"
```

### Fixtures failing
```bash
# Check factory_boy is installed
python -m pip install factory-boy

# Verify factories work
python manage.py shell
>>> from apps.peoples.tests.factories import PeopleFactory
>>> PeopleFactory.create()
```

---

**Next Step:** Run tests to establish baseline

```bash
python -m pytest apps/peoples/tests/test_idor_security.py -v --tb=short
```

Good luck! 🚀
