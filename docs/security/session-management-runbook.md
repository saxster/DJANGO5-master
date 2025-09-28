# Session Security Management Runbook

**Implements:** Rule #10 - Session Security Standards from `.claude/rules.md`

**Purpose:** Operational guide for session security configuration, monitoring, and incident response.

---

## 📋 Configuration Reference

### Core Session Settings (Rule #10 Compliant)

```python
# intelliwiz_config/settings/security/authentication.py
SESSION_COOKIE_AGE = 2 * 60 * 60              # 2 hours max
SESSION_SAVE_EVERY_REQUEST = True              # Security first
SESSION_EXPIRE_AT_BROWSER_CLOSE = True         # Close session with browser
SESSION_COOKIE_SECURE = True                   # HTTPS only (production)
SESSION_COOKIE_HTTPONLY = True                 # Prevent XSS access
SESSION_COOKIE_SAMESITE = "Lax"               # CSRF protection
SESSION_ENGINE = "django.contrib.sessions.backends.db"  # PostgreSQL backend
```

### Additional Security Settings

```python
# Optional but recommended
SESSION_ACTIVITY_TIMEOUT = 30 * 60            # 30 minutes inactivity timeout
MAX_CONCURRENT_SESSIONS = 3                   # Max 3 sessions per user
CONCURRENT_SESSION_ACTION = 'invalidate_oldest'  # Auto-invalidate oldest
SESSION_ENABLE_GEO_TRACKING = False           # Geographic anomaly detection
```

---

## 🔧 Session Security Features

### 1. Activity Timeout Monitoring

**Middleware:** `SessionActivityMiddleware`

**Purpose:** Tracks user activity and enforces inactivity timeout.

**How it works:**
- Tracks `_last_activity` timestamp on every authenticated request
- Compares current time vs. last activity time
- Logs out user and returns 401 if timeout exceeded
- Detects IP and User-Agent changes as potential hijacking

**Monitoring:**
```python
# Check timeout events count
from django.core.cache import cache
timeout_count = cache.get('session_activity:timeout_events', 0)
```

### 2. Session Rotation on Privilege Changes

**Components:**
- `apps/peoples/signals.py` - Detects privilege escalation
- `apps/peoples/services/authentication_service.py` - Rotates sessions
- `SessionRotationMiddleware` - Applies rotation

**Triggers:**
- User promoted to superuser (`is_superuser: False → True`)
- User promoted to staff (`is_staff: False → True`)
- User promoted to admin (`isadmin: False → True`)

**Flow:**
1. User's privileges are modified
2. `pre_save` signal detects escalation
3. `post_save` signal fires `privilege_changed` event
4. Session marked for rotation (`_requires_rotation` flag)
5. Next request triggers rotation via middleware
6. Old session key invalidated, new key generated
7. Event logged to SessionForensics

### 3. Concurrent Session Limiting

**Middleware:** `ConcurrentSessionLimitingMiddleware`

**Purpose:** Prevent session hijacking by limiting concurrent sessions.

**Strategies:**
- **invalidate_oldest** (default): Auto-invalidate oldest session when limit exceeded
- **deny_new**: Reject new session creation, force user to close existing sessions

**Monitoring:**
```python
# Get user's active sessions
from apps.core.middleware.concurrent_session_limiting import SessionManagerAPI
sessions = SessionManagerAPI.get_user_active_sessions(user_id)
```

### 4. Session Forensics and Audit Trail

**Model:** `SessionForensics`

**Purpose:** Comprehensive audit trail for security analysis and incident response.

**Events Tracked:**
- `created` - Session created
- `authenticated` - User logged in
- `rotated` - Session key rotated
- `activity_timeout` - Inactivity timeout occurred
- `privilege_change` - Privilege escalation detected
- `ip_change` - IP address changed mid-session
- `user_agent_change` - User-Agent changed mid-session
- `concurrent_limit` - Concurrent session limit hit
- `manual_logout` - User logged out manually
- `forced_logout` - Admin forced logout
- `expired` - Session expired naturally

**Usage:**
```python
from apps.core.models import SessionForensics

# Log a session event
SessionForensics.log_session_event(
    user=user,
    session_key=request.session.session_key,
    event_type='rotated',
    ip_address='192.168.1.100',
    user_agent=request.META.get('HTTP_USER_AGENT'),
    correlation_id=request.correlation_id,
    metadata={'reason': 'privilege_escalation:is_superuser'},
    severity='high'
)

# Get user's session history
history = SessionForensics.get_user_session_history(user_id, days=30)

# Get suspicious activity
suspicious = SessionForensics.get_suspicious_activity(hours=24)
```

---

## 📊 Monitoring and Dashboards

### Security Dashboard Integration

**Endpoints:**
- `/security/sessions/` - Session monitoring dashboard (staff only)
- `/api/security/sessions/metrics/` - Real-time session metrics API
- `/api/security/sessions/manage/` - User session management API

**Dashboard Metrics:**
- Active sessions count
- Timeout events (last 24h)
- Suspicious activity count and details
- Recent session rotations
- Privilege escalation events
- Session configuration compliance

**Access:**
```bash
# View session monitoring dashboard
https://your-domain.com/security/sessions/

# Get real-time metrics (JSON)
curl -H "Authorization: Bearer $TOKEN" \
     https://your-domain.com/api/security/sessions/metrics/?hours=1
```

---

## 🚨 Incident Response

### Scenario 1: Suspected Session Hijacking

**Indicators:**
- IP address change during active session
- User-Agent change during active session
- Multiple concurrent sessions from different locations
- SessionForensics records flagged as suspicious

**Response Steps:**
1. **Identify affected user:**
   ```python
   suspicious = SessionForensics.objects.filter(
       is_suspicious=True,
       event_type__in=['ip_change', 'user_agent_change']
   ).select_related('user')
   ```

2. **Invalidate all user sessions:**
   ```python
   from apps.core.middleware.concurrent_session_limiting import SessionManagerAPI
   count = SessionManagerAPI.invalidate_all_other_sessions(
       user_id=affected_user.id,
       current_session_key='admin_session'
   )
   ```

3. **Force password reset:**
   ```python
   affected_user.set_unusable_password()
   affected_user.save()
   # Send password reset email
   ```

4. **Create security incident record:**
   ```python
   from apps.core.services.security_monitoring_service import SecurityMonitoringService
   service = SecurityMonitoringService()
   service.create_security_incident({
       'type': 'session_hijacking',
       'user_id': affected_user.id,
       'severity': 'critical',
       'details': 'IP and User-Agent changed mid-session'
   })
   ```

### Scenario 2: Activity Timeout Not Working

**Symptoms:**
- Sessions remain active beyond configured timeout
- Users not logged out after inactivity

**Diagnosis:**
1. **Verify middleware is enabled:**
   ```python
   from django.conf import settings
   'apps.core.middleware.session_activity.SessionActivityMiddleware' in settings.MIDDLEWARE
   ```

2. **Check activity timeout setting:**
   ```python
   from django.conf import settings
   timeout = getattr(settings, 'SESSION_ACTIVITY_TIMEOUT', None)
   print(f"Activity timeout: {timeout} seconds")
   ```

3. **Verify session updates:**
   ```python
   # Check if SESSION_SAVE_EVERY_REQUEST is True
   print(f"Save every request: {settings.SESSION_SAVE_EVERY_REQUEST}")
   ```

**Resolution:**
- Ensure `SESSION_SAVE_EVERY_REQUEST = True`
- Restart application servers to reload middleware
- Clear cache if activity timestamps are cached

### Scenario 3: Privilege Escalation Without Session Rotation

**Symptoms:**
- User privileges elevated but session not rotated
- Old session key still valid after privilege change

**Diagnosis:**
1. **Check signal registration:**
   ```python
   from django.db.models.signals import pre_save, post_save
   from apps.peoples.models import People

   pre_save_receivers = pre_save.receivers_for(People)
   post_save_receivers = post_save.receivers_for(People)

   print(f"Pre-save receivers: {len(pre_save_receivers)}")
   print(f"Post-save receivers: {len(post_save_receivers)}")
   ```

2. **Verify signal handler execution:**
   ```python
   # Check logs for privilege escalation detection
   grep "Privilege escalation detected" /var/log/intelliwiz/app.log
   ```

3. **Test rotation manually:**
   ```python
   from apps.peoples.services.authentication_service import AuthenticationService
   service = AuthenticationService()

   # Simulate privilege change
   result = service.rotate_session_on_privilege_change(
       request, user,
       {'is_superuser': False},
       {'is_superuser': True}
   )
   ```

**Resolution:**
- Verify signals are imported in `apps/peoples/apps.py`
- Check for signal handler exceptions in logs
- Ensure `SessionRotationMiddleware` is in middleware chain

---

## 🧪 Testing Session Security

### Run Security Test Suite

```bash
# All session security tests
python -m pytest apps/core/tests/test_session_security.py -v

# Activity monitoring tests
python -m pytest apps/core/tests/test_session_activity_monitoring.py -v

# Session rotation tests
python -m pytest apps/core/tests/test_session_rotation.py -v

# Complete security suite (includes session tests)
python -m pytest -m security --tb=short -v
```

### Manual Testing Procedures

**Test Activity Timeout:**
1. Login to application
2. Note session key and timestamp
3. Wait for activity timeout period (default 30 min)
4. Try to access protected resource
5. Verify 401 response with "Session expired due to inactivity" message

**Test Privilege Escalation Rotation:**
1. Login as regular user
2. Note session key
3. Have admin promote user to superuser
4. On next request, verify session key changed
5. Check logs for "Session rotated: privilege_escalation" message

**Test Concurrent Session Limiting:**
1. Login from Browser 1
2. Login from Browser 2
3. Login from Browser 3
4. Login from Browser 4 (should invalidate oldest or be denied)
5. Verify only 3 sessions active in dashboard

---

## 🔍 Forensic Analysis

### Investigate Suspicious Session Activity

```python
from apps.core.models import SessionForensics

# Get all suspicious events in last 24 hours
suspicious = SessionForensics.get_suspicious_activity(hours=24)

for event in suspicious:
    print(f"Event: {event.event_type}")
    print(f"User: {event.user.peoplecode}")
    print(f"Time: {event.timestamp}")
    print(f"IP: {event.ip_address}")
    print(f"Severity: {event.severity}")
    print(f"Metadata: {event.event_metadata}")
    print("---")
```

### Analyze User Session Patterns

```python
# Get user's session history
history = SessionForensics.get_user_session_history(user_id=123, days=30)

# Group by event type
from collections import Counter
event_counts = Counter(h.event_type for h in history)

print("User session pattern:")
for event_type, count in event_counts.most_common():
    print(f"  {event_type}: {count}")
```

### Geographic Anomaly Detection

```python
# Find sessions with impossible travel
def detect_impossible_travel(user_id, hours=24):
    from apps.core.models import SessionForensics
    import geopy.distance

    cutoff = timezone.now() - timedelta(hours=hours)
    events = SessionForensics.objects.filter(
        user_id=user_id,
        timestamp__gte=cutoff,
        geolocation__isnull=False
    ).order_by('timestamp')

    anomalies = []
    prev_event = None

    for event in events:
        if prev_event and prev_event.geolocation and event.geolocation:
            prev_coords = (prev_event.geolocation['lat'], prev_event.geolocation['lon'])
            curr_coords = (event.geolocation['lat'], event.geolocation['lon'])

            distance_km = geopy.distance.distance(prev_coords, curr_coords).km
            time_diff_hours = (event.timestamp - prev_event.timestamp).total_seconds() / 3600

            # Average jet speed is ~900 km/h
            if time_diff_hours > 0 and (distance_km / time_diff_hours) > 900:
                anomalies.append({
                    'from_location': prev_event.geolocation,
                    'to_location': event.geolocation,
                    'distance_km': distance_km,
                    'time_hours': time_diff_hours,
                    'speed_kmh': distance_km / time_diff_hours,
                    'events': [prev_event, event]
                })

        prev_event = event

    return anomalies
```

---

## 📈 Performance Impact

### Expected Performance Costs

| Feature | Average Latency | Mitigation |
|---------|----------------|------------|
| `SESSION_SAVE_EVERY_REQUEST = True` | +20ms per request | PostgreSQL optimizations, connection pooling |
| Activity timestamp update | +5ms per request | Cached metadata updates |
| IP/User-Agent tracking | +2ms per request | Minimal - simple string comparison |
| Concurrent session check | +10ms per request | Cache-based lookup, database fallback |

**Total:** ~37ms additional latency per authenticated request

**Acceptable:** Architecture notes approve 20ms trade-off for security

### Optimization Tips

1. **Database Connection Pooling:**
   ```python
   DATABASES = {
       'default': {
           'CONN_MAX_AGE': 600,  # 10 minutes
           'OPTIONS': {
               'connect_timeout': 10,
           }
       }
   }
   ```

2. **Session Table Indexing:**
   ```sql
   CREATE INDEX CONCURRENTLY idx_session_expire_date
   ON django_session (expire_date);

   CREATE INDEX CONCURRENTLY idx_session_key
   ON django_session (session_key);
   ```

3. **Cleanup Automation:**
   ```bash
   # Run cleanup daily via cron
   0 3 * * * python manage.py cleanup_sessions
   ```

---

## 🛡️ Security Best Practices

### 1. Regular Audit Reviews

**Weekly:**
- Review suspicious session activity dashboard
- Check for geographic anomalies
- Verify timeout events are reasonable

**Monthly:**
- Analyze privilege escalation patterns
- Review concurrent session violations
- Update activity timeout based on usage patterns

**Quarterly:**
- Conduct penetration testing for session security
- Review and update session security policies
- Train staff on session security procedures

### 2. Session Lifecycle Management

**User Onboarding:**
- Set appropriate `SESSION_ACTIVITY_TIMEOUT` based on user role
- Configure `MAX_CONCURRENT_SESSIONS` per user type
- Enable geo-tracking for high-privilege users

**User Offboarding:**
```python
# Invalidate all user sessions immediately
from django.contrib.sessions.models import Session

sessions = Session.objects.all()
for session in sessions:
    data = session.get_decoded()
    if data.get('_auth_user_id') == offboarded_user_id:
        session.delete()
```

### 3. Compliance Requirements

**PCI DSS:**
- Session timeout ≤ 15 minutes for payment processing
- Force re-authentication for sensitive operations

**HIPAA:**
- Session timeout ≤ 20 minutes for PHI access
- Automatic session termination on workstation lock

**GDPR:**
- Log and audit all session activity
- Provide users ability to view/manage active sessions
- Implement "right to be forgotten" for session history

---

## 🔧 Operational Procedures

### Daily Operations

**Morning Security Check:**
```bash
# Check for overnight suspicious activity
python manage.py shell
>>> from apps.core.models import SessionForensics
>>> suspicious = SessionForensics.get_suspicious_activity(hours=24)
>>> print(f"Suspicious events: {suspicious.count()}")
>>> for event in suspicious[:10]:
...     print(f"  {event.event_type} - {event.user.peoplecode} @ {event.timestamp}")
```

**Session Cleanup:**
```bash
# Clean expired sessions
python manage.py cleanup_sessions

# Dry run to preview
python manage.py cleanup_sessions --dry-run
```

### Incident Response Workflow

**Step 1: Detection**
- Monitor SessionForensics for `is_suspicious=True` events
- Check security dashboard for anomalies
- Review application logs for session warnings

**Step 2: Investigation**
```python
# Get all events for suspicious session
from apps.core.models import SessionForensics
import hashlib

session_key_hash = hashlib.sha256(suspicious_session_key.encode()).hexdigest()[:40]

events = SessionForensics.objects.filter(
    session_key=session_key_hash
).order_by('timestamp')

for event in events:
    print(f"{event.timestamp}: {event.event_type} from {event.ip_address}")
```

**Step 3: Containment**
```python
# Invalidate compromised session
from django.contrib.sessions.models import Session
Session.objects.filter(session_key=suspicious_session_key).delete()

# Invalidate all user sessions
from apps.core.middleware.concurrent_session_limiting import SessionManagerAPI
SessionManagerAPI.invalidate_all_other_sessions(user_id, 'admin_session')
```

**Step 4: Recovery**
- Force password reset for affected user
- Review and revoke any unauthorized actions
- Update security rules if new attack vector discovered

**Step 5: Post-Incident Review**
- Document attack vector and response
- Update monitoring rules if needed
- Share learnings with security team

---

## 🔐 Hardening Recommendations

### Production Environment

```python
# Stricter timeouts for production
SESSION_COOKIE_AGE = 1 * 60 * 60              # 1 hour
SESSION_ACTIVITY_TIMEOUT = 15 * 60            # 15 minutes
MAX_CONCURRENT_SESSIONS = 2                   # Only 2 sessions
CONCURRENT_SESSION_ACTION = 'deny_new'        # Force explicit session management
SESSION_ENABLE_GEO_TRACKING = True            # Enable geographic anomaly detection
```

### High-Security Environments (PCI DSS, HIPAA)

```python
# Maximum security configuration
SESSION_COOKIE_AGE = 15 * 60                  # 15 minutes
SESSION_ACTIVITY_TIMEOUT = 10 * 60            # 10 minutes inactivity
MAX_CONCURRENT_SESSIONS = 1                   # Single session only
CONCURRENT_SESSION_ACTION = 'deny_new'
SESSION_ENABLE_GEO_TRACKING = True
SESSION_REQUIRE_IP_MATCH = True               # Block IP changes (new setting)
SESSION_REQUIRE_USER_AGENT_MATCH = True       # Block UA changes (new setting)
```

### Development Environment

```python
# Relaxed for development convenience
SESSION_COOKIE_AGE = 8 * 60 * 60              # 8 hours
SESSION_ACTIVITY_TIMEOUT = 2 * 60 * 60        # 2 hours
MAX_CONCURRENT_SESSIONS = 10                  # Multiple test sessions
SESSION_ENABLE_GEO_TRACKING = False
```

---

## 📚 Additional Resources

- **Django Session Security:** https://docs.djangoproject.com/en/5.0/topics/http/sessions/
- **OWASP Session Management:** https://owasp.org/www-community/Session_Management_Cheat_Sheet
- **CWE-384:** Session Fixation - https://cwe.mitre.org/data/definitions/384.html
- **Rule #10 Full Specification:** `.claude/rules.md` lines 249-267

---

## 📞 Support and Escalation

**Security Team Contact:** security@company.com

**Emergency Escalation:**
1. Contact security team immediately
2. Follow incident response workflow above
3. Document all actions taken
4. Schedule post-incident review

**Non-Emergency Questions:**
- Review this runbook
- Check application logs
- Consult with DevOps team
- File ticket with security team

---

**Last Updated:** 2025-09-27
**Version:** 1.0
**Compliance:** Rule #10 - Session Security Standards