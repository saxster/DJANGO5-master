# CRITICAL SECURITY FIX 3 - Manual Test Plan

**Purpose:** Verify WebSocket metrics authentication works correctly  
**Estimated Time:** 15-20 minutes  
**Prerequisites:** Development environment running with test data

---

## Pre-Test Setup

### 1. Create Test Users

```bash
# Start Django shell
python manage.py shell

# Create test users
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational
from apps.tenants.models import Tenant

tenant = Tenant.objects.first()

# Regular user (non-staff)
regular_user = People.objects.create_user(
    username='test_regular',
    email='regular@test.com',
    password='Test123!@#',
    tenant=tenant
)
PeopleProfile.objects.create(people=regular_user)
PeopleOrganizational.objects.create(people=regular_user)

# Staff user
staff_user = People.objects.create_user(
    username='test_staff',
    email='staff@test.com',
    password='Test123!@#',
    tenant=tenant,
    is_staff=True
)
PeopleProfile.objects.create(people=staff_user)
PeopleOrganizational.objects.create(people=staff_user)

print("✅ Test users created")
```

### 2. Start Development Server

```bash
# Option 1: HTTP only
python manage.py runserver

# Option 2: With WebSockets (recommended)
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

---

## Test Cases

### Test 1: Unauthenticated Access Blocked

**Objective:** Verify anonymous users cannot access metrics

**Steps:**
1. Open browser in incognito/private mode
2. Navigate to: `http://localhost:8000/noc/websocket/metrics/`
3. **Expected:** Redirect to login page (HTTP 302)

**cURL Test:**
```bash
curl -v http://localhost:8000/noc/websocket/metrics/
# Expected: 302 Found (redirect to login)
```

**✅ PASS Criteria:**
- [ ] Returns HTTP 302 redirect
- [ ] Redirects to login URL
- [ ] No metrics data exposed

---

### Test 2: Non-Staff User Access Denied

**Objective:** Verify regular users cannot access staff-only metrics

**Steps:**
1. Login as regular user: `test_regular` / `Test123!@#`
2. Navigate to: `http://localhost:8000/noc/websocket/metrics/`
3. **Expected:** Redirect to admin login or 403 Forbidden

**cURL Test:**
```bash
# First login to get session cookie
curl -c cookies.txt -X POST http://localhost:8000/login/ \
  -d "username=test_regular&password=Test123!@#"

# Then try to access metrics
curl -b cookies.txt http://localhost:8000/noc/websocket/metrics/
# Expected: 302 redirect to admin login
```

**✅ PASS Criteria:**
- [ ] Returns HTTP 302 or 403
- [ ] User not granted access to metrics
- [ ] Appropriate error message shown

---

### Test 3: Staff User Access Granted

**Objective:** Verify staff users can access metrics

**Steps:**
1. Login as staff user: `test_staff` / `Test123!@#`
2. Navigate to: `http://localhost:8000/noc/websocket/metrics/`
3. **Expected:** HTTP 200 with JSON metrics data

**cURL Test:**
```bash
# Login as staff
curl -c cookies.txt -X POST http://localhost:8000/login/ \
  -d "username=test_staff&password=Test123!@#"

# Access metrics
curl -b cookies.txt http://localhost:8000/noc/websocket/metrics/
# Expected: 200 OK with JSON data
```

**✅ PASS Criteria:**
- [ ] Returns HTTP 200 OK
- [ ] Returns valid JSON response
- [ ] Response contains metrics data structure:
  ```json
  {
    "success": true,
    "data": { ... },
    "timestamp": "..."
  }
  ```

---

### Test 4: WebSocket Dashboard Access

**Objective:** Verify WebSocket dashboard requires authentication

**Steps:**
1. **As anonymous user:**
   - Navigate to: `http://localhost:8000/noc/websocket/dashboard/`
   - **Expected:** Redirect to login

2. **As regular user:**
   - Login as `test_regular`
   - Navigate to dashboard
   - **Expected:** Redirect to admin login (non-staff)

3. **As staff user:**
   - Login as `test_staff`
   - Navigate to dashboard
   - **Expected:** Dashboard loads successfully

**✅ PASS Criteria:**
- [ ] Anonymous users redirected
- [ ] Non-staff users blocked
- [ ] Staff users can view dashboard

---

### Test 5: Admin Tools Authentication

**Objective:** Verify admin tools require staff authentication

**Endpoints to test:**
- `/noc/admin/connections/` - Connection Inspector
- `/noc/admin/message-replay/` - Message Replay
- `/noc/admin/live-connections/` - Live Connections API

**Test for each endpoint:**

```bash
# 1. Anonymous access
curl http://localhost:8000/noc/admin/connections/
# Expected: 302 redirect

# 2. Regular user access
curl -b cookies_regular.txt http://localhost:8000/noc/admin/connections/
# Expected: 302 redirect to admin login

# 3. Staff user access
curl -b cookies_staff.txt http://localhost:8000/noc/admin/connections/
# Expected: 200 OK
```

**✅ PASS Criteria:**
- [ ] All endpoints block anonymous users
- [ ] All endpoints block non-staff users
- [ ] All endpoints allow staff users

---

### Test 6: Kill Switch Security

**Objective:** Verify kill switch requires POST + staff auth

**Tests:**

```bash
# 1. Anonymous POST
curl -X POST http://localhost:8000/noc/admin/kill-switch/
# Expected: 302 redirect

# 2. Staff GET (wrong method)
curl -b cookies_staff.txt -X GET http://localhost:8000/noc/admin/kill-switch/
# Expected: 405 Method Not Allowed

# 3. Staff POST (correct)
curl -b cookies_staff.txt -X POST http://localhost:8000/noc/admin/kill-switch/
# Expected: 200 OK with success message
```

**✅ PASS Criteria:**
- [ ] Anonymous requests rejected
- [ ] GET requests rejected (405)
- [ ] Staff POST requests succeed

---

### Test 7: WebSocket Consumer Authentication

**Objective:** Verify WebSocket connections require authentication

**Browser Console Test:**

```javascript
// Open browser console on login page
// Try to connect without authentication
const ws = new WebSocket('ws://localhost:8000/ws/noc/dashboard/');

ws.onopen = () => console.log('❌ FAIL: Connected without auth');
ws.onerror = () => console.log('✅ PASS: Connection rejected');
ws.onclose = (e) => console.log(`Connection closed: ${e.code}`);

// Expected: Connection should be rejected
```

**Python Test:**

```python
# In Django shell or test file
import asyncio
from channels.testing import WebsocketCommunicator
from apps.noc.consumers.noc_dashboard_consumer import NOCDashboardConsumer

async def test_unauthenticated():
    communicator = WebsocketCommunicator(
        NOCDashboardConsumer.as_asgi(),
        "/ws/noc/dashboard/"
    )
    connected, subprotocol = await communicator.connect()
    print(f"Connected: {connected}")  # Should be False
    await communicator.disconnect()

asyncio.run(test_unauthenticated())
# Expected: Connected: False
```

**✅ PASS Criteria:**
- [ ] WebSocket connection rejected for anonymous users
- [ ] Close code is 403 (Forbidden)
- [ ] Connection accepted for authenticated users with capabilities

---

### Test 8: Monitoring Endpoints API Key

**Objective:** Verify monitoring endpoints require API key

**Tests:**

```bash
# 1. No API key
curl http://localhost:8000/monitoring/websocket/
# Expected: 403 Forbidden

# 2. Invalid API key
curl -H "X-Monitoring-API-Key: invalid_key" \
  http://localhost:8000/monitoring/websocket/
# Expected: 403 Forbidden

# 3. Valid API key (if you have one)
curl -H "X-Monitoring-API-Key: YOUR_VALID_KEY" \
  http://localhost:8000/monitoring/websocket/
# Expected: 200 OK with metrics
```

**✅ PASS Criteria:**
- [ ] Requests without API key rejected
- [ ] Requests with invalid key rejected
- [ ] Requests with valid key succeed

---

## Post-Test Verification

### 1. Check Authentication Logs

```python
# Django shell
from apps.noc.models import NOCEventLog
from django.utils import timezone
from datetime import timedelta

# Check for auth failures in last hour
recent_failures = NOCEventLog.objects.filter(
    event_type='websocket_auth_failure',
    created_at__gte=timezone.now() - timedelta(hours=1)
)

print(f"Auth failures: {recent_failures.count()}")
for event in recent_failures:
    print(f"  - {event.created_at}: {event.details}")
```

### 2. Verify No Security Regressions

```bash
# Run security test suite
python -m pytest apps/noc/tests/test_websocket_metrics_auth.py -v

# Run all NOC tests
python -m pytest apps/noc/tests/ -v

# Check for any new security issues
python manage.py check --deploy
```

### 3. Performance Check

```python
# Verify authentication doesn't significantly impact performance
import time
import requests

# Login first
session = requests.Session()
session.post('http://localhost:8000/login/', {
    'username': 'test_staff',
    'password': 'Test123!@#'
})

# Time 10 requests
times = []
for i in range(10):
    start = time.time()
    response = session.get('http://localhost:8000/noc/websocket/metrics/')
    times.append(time.time() - start)

avg_time = sum(times) / len(times)
print(f"Average response time: {avg_time*1000:.2f}ms")
# Should be < 100ms for metrics endpoint
```

---

## Cleanup

```python
# Delete test users (Django shell)
from apps.peoples.models import People

People.objects.filter(username__in=['test_regular', 'test_staff']).delete()
print("✅ Test users deleted")
```

---

## Test Results Template

```
CRITICAL SECURITY FIX 3 - Test Results
======================================

Date: _______________
Tester: _______________

Test 1: Unauthenticated Access Blocked     [ ] PASS [ ] FAIL
Test 2: Non-Staff User Access Denied       [ ] PASS [ ] FAIL
Test 3: Staff User Access Granted          [ ] PASS [ ] FAIL
Test 4: WebSocket Dashboard Access         [ ] PASS [ ] FAIL
Test 5: Admin Tools Authentication         [ ] PASS [ ] FAIL
Test 6: Kill Switch Security               [ ] PASS [ ] FAIL
Test 7: WebSocket Consumer Authentication  [ ] PASS [ ] FAIL
Test 8: Monitoring Endpoints API Key       [ ] PASS [ ] FAIL

Post-Test Verification:
- [ ] Authentication logs reviewed
- [ ] No security regressions found
- [ ] Performance acceptable (<100ms)
- [ ] Test users cleaned up

Overall Result: [ ] PASS [ ] FAIL

Notes:
_____________________________________________________________
_____________________________________________________________
_____________________________________________________________

Approved By: _______________  Date: _______________
```

---

## Troubleshooting

### Issue: "404 Not Found" on metrics endpoint
**Solution:** Ensure URL routes are properly configured in `apps/noc/urls.py`

### Issue: Infinite redirect loop
**Solution:** Clear browser cookies and session data, then re-login

### Issue: WebSocket connection immediately closes
**Solution:** Check browser console for error messages, verify WebSocket routing configured

### Issue: Tests fail with "No module named pytest"
**Solution:** Install test dependencies: `pip install -r requirements/base.txt`

---

**Test Duration:** ~15-20 minutes  
**Required:** Before production deployment  
**Repeatable:** Yes (automated tests preferred for regression testing)
