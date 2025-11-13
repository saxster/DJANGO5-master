# Peoples App

## Purpose

Custom user authentication and profile management system for enterprise facility management platform.

## Key Features

- **Custom User Model** - Django-compatible `People` model replacing default User
- **Multi-Model Architecture** - Separate models for profiles, organizational data, and capabilities
- **Tenant-Aware Authentication** - Multi-tenant isolation for user data
- **Device Registry** - Mobile device tracking and security risk monitoring
- **Permission Groups** - Role-based access control with flexible capability system
- **Secure File Upload** - Validated profile image uploads with path traversal protection
- **Session Activity Logging** - Comprehensive audit trail for user sessions

---

## Architecture

### Models Overview

The peoples app uses a multi-model architecture for separation of concerns:

**Core User Model:**
- `People` - Custom user model (AUTH_USER_MODEL)
  - Authentication credentials (email, loginid, password)
  - Basic user info (peoplename, mobno)
  - Tenant association and status flags
  - Capabilities JSON for permission management

**Related Models:**
- `PeopleProfile` - Demographic and employment data
  - Gender, date of birth, date of join
  - Profile image with secure upload
  - Background check status
- `PeopleOrganizational` - Organizational hierarchy
  - Location, department, designation
  - Report-to relationships
  - Work type and people type
- `Pgroup` - Permission groups for RBAC
- `Pgbelonging` - Group membership tracking
- `Capability` - Feature capability definitions
- `DeviceRegistration` - Mobile device tracking
- `DeviceRiskEvent` - Security risk monitoring
- `SessionActivityLog` - User session audit trail

**See:** `/Users/amar/Desktop/MyCode/DJANGO5-master/apps/peoples/models/` for complete model definitions

### Database Schema

```
People (Custom User Model)
  ├─ PeopleProfile (1:1)
  ├─ PeopleOrganizational (1:1)
  ├─ Pgbelonging (M2M via junction)
  │   └─ Pgroup
  ├─ DeviceRegistration (1:M)
  │   └─ DeviceRiskEvent (1:M)
  └─ SessionActivityLog (1:M)
```

### Key Relationships

```python
# One-to-One relationships
profile = models.OneToOneField(PeopleProfile, related_name='people')
organizational = models.OneToOneField(PeopleOrganizational, related_name='people')

# Many-to-Many through Pgbelonging
groups = Pgroup.objects.filter(pgbelonging__peopleid=user)

# One-to-Many
devices = DeviceRegistration.objects.filter(user=user)
sessions = SessionActivityLog.objects.filter(user=user)
```

---

## API Endpoints

### Authentication

```
POST   /api/v2/auth/login/                    # User login
POST   /api/v2/auth/logout/                   # User logout
POST   /api/v2/auth/refresh/                  # Refresh token
POST   /api/v2/auth/change-password/          # Password change
```

### User Management

```
GET    /api/v2/peoples/                       # List users
POST   /api/v2/peoples/                       # Create user
GET    /api/v2/peoples/{id}/                  # User details
PATCH  /api/v2/peoples/{id}/                  # Update user
DELETE /api/v2/peoples/{id}/                  # Deactivate user
GET    /api/v2/peoples/{id}/profile/          # Get profile
PATCH  /api/v2/peoples/{id}/profile/          # Update profile
```

### Group Management

```
GET    /api/v2/groups/                        # List groups
POST   /api/v2/groups/                        # Create group
GET    /api/v2/groups/{id}/                   # Group details
POST   /api/v2/groups/{id}/members/           # Add member
DELETE /api/v2/groups/{id}/members/{user_id}/ # Remove member
```

### Device Management

```
GET    /api/v2/peoples/{id}/devices/          # List user devices
POST   /api/v2/peoples/{id}/devices/          # Register device
DELETE /api/v2/peoples/{id}/devices/{device_id}/ # Revoke device
```

---

## Usage Examples

### Creating a User

```python
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational

# Create base user
user = People.objects.create_user(
    loginid='john_smith',
    email='john.smith@example.com',
    peoplename='John Smith',
    mobno='1234567890',
    password='SecurePass123!',
    client=tenant,
    enable=True
)

# Create profile
profile = PeopleProfile.objects.create(
    people=user,
    gender='Male',
    dateofbirth=date(1990, 1, 15),
    dateofjoin=date(2023, 6, 1)
)

# Create organizational data
org = PeopleOrganizational.objects.create(
    people=user,
    location=location,
    department=department,
    designation=designation,
    peopletype=employee_type,
    worktype=full_time_type
)
```

### Authentication

```python
from django.contrib.auth import authenticate

# Authenticate user
user = authenticate(request, loginid='john_smith', password='SecurePass123!')

if user is not None:
    # Login successful
    login(request, user)
else:
    # Login failed
    return JsonResponse({'error': 'Invalid credentials'}, status=401)
```

### Permission Checking

```python
# Check user capabilities
if 'task_management' in user.capabilities.get('webcapability', []):
    # User has task management capability
    pass

# Check group membership
if user.belongs_to_group('managers'):
    # User is in managers group
    pass

# Check if user is staff/superuser
if user.is_staff:
    # User has admin access
    pass
```

### Device Registration

```python
from apps.peoples.models import DeviceRegistration

# Register mobile device
device = DeviceRegistration.objects.create(
    user=user,
    device_id='unique-device-uuid',
    device_type='mobile',
    os_type='android',
    os_version='13',
    app_version='2.1.0',
    is_active=True
)
```

---

## Security Features

### Password Security

- **Hashing:** Django's PBKDF2 with SHA256
- **Min Length:** 8 characters (configurable)
- **Complexity:** Uppercase, lowercase, numbers, special chars
- **Validation:** Django password validators

### Multi-Tenant Isolation

```python
# All queries automatically filtered by tenant
users = People.objects.all()  # Only returns users from current tenant

# Explicit tenant filtering
users = People.objects.filter(client=tenant)
```

### Device Security

- **Device tracking:** All mobile devices registered
- **Risk monitoring:** Anomaly detection for suspicious activity
- **Revocation:** Admin can revoke device access

### Session Auditing

```python
from apps.peoples.models import SessionActivityLog

# Log session activity
SessionActivityLog.objects.create(
    user=user,
    session_key=request.session.session_key,
    ip_address=request.META.get('REMOTE_ADDR'),
    user_agent=request.META.get('HTTP_USER_AGENT'),
    action='login'
)
```

---

## Testing

### Running Tests

```bash
# All peoples tests
pytest apps/peoples/tests/ -v

# Specific test module
pytest apps/peoples/tests/test_authentication.py -v

# With coverage
pytest apps/peoples/tests/ --cov=apps/peoples --cov-report=html
```

### Test Factories

```python
from apps.peoples.tests.factories import (
    PeopleFactory,
    CompleteUserFactory,
    AdminUserFactory,
    ManagerUserFactory
)

# Create basic user
user = PeopleFactory.create()

# Create user with profile and org data
complete_user = CompleteUserFactory.create()

# Create admin user
admin = AdminUserFactory.create()
```

### Key Test Files

- `test_authentication.py` - Login, logout, password change
- `test_user_model.py` - User creation, validation
- `test_permissions.py` - Capability and group checks
- `test_device_registry.py` - Device registration and tracking
- `test_security.py` - IDOR, tenant isolation

---

## Configuration

### Settings

```python
# intelliwiz_config/settings/base.py

# Custom user model
AUTH_USER_MODEL = 'peoples.People'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    # ... additional validators
]

# Session settings
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_SAVE_EVERY_REQUEST = True
```

### Capabilities Structure

```python
# User capabilities JSON field
{
    "webcapability": ["task_management", "reporting", "user_management"],
    "mobilecapability": ["attendance", "journal", "tours"],
    "portletcapability": ["dashboard", "analytics"],
    "reportcapability": ["attendance_reports", "performance_reports"],
    "noccapability": ["camera_access", "alert_management"],
    "debug": False,
    "blacklist": False
}
```

---

## Migrations and Refactoring

### Model Split (October 2025)

The peoples app was refactored from a monolithic `models.py` (1200+ lines) to modular structure:

- `models/user_model.py` - People custom user model
- `models/profile_model.py` - PeopleProfile
- `models/organizational_model.py` - PeopleOrganizational
- `models/group_model.py` - Pgroup, PermissionGroup
- `models/membership_model.py` - Pgbelonging
- `models/capability_model.py` - Capability
- `models/device_registry.py` - Device tracking
- `models/session_activity.py` - Session logs

**Backward Compatibility:** The main `models.py` now serves as a compatibility shim. All imports continue to work:

```python
# Both work
from apps.peoples.models import People
from apps.peoples.models.user_model import People
```

**Deprecation Timeline:** Shim maintained until March 2026.

---

## Performance Optimization

### Query Optimization

```python
# N+1 prevention
users = People.objects.select_related(
    'profile',
    'organizational',
    'organizational__location',
    'organizational__department'
).prefetch_related(
    'pgbelonging_set__groupid'
)

# Custom manager methods
users = People.objects.with_full_details()  # Optimized query
```

### Indexes

```python
class Meta:
    indexes = [
        models.Index(fields=['loginid']),
        models.Index(fields=['email']),
        models.Index(fields=['tenant', 'enable']),
        models.Index(fields=['tenant', 'is_active']),
    ]
```

---

## Related Apps

- [attendance](../attendance/README.md) - User attendance tracking
- [journal](../journal/README.md) - Personal journal entries
- [activity](../activity/README.md) - Task assignments
- [y_helpdesk](../y_helpdesk/README.md) - Ticket assignments

---

## Troubleshooting

### Common Issues

**Issue:** User login fails with correct credentials
**Solution:** Check `enable=True` and `is_active=True` flags

**Issue:** Missing profile/organizational data
**Solution:** Ensure related models created after user creation

**Issue:** Permission denied errors
**Solution:** Verify user capabilities JSON and group memberships

**Issue:** Device registration fails
**Solution:** Check for duplicate device_id and ensure user is active

### Debug Logging

```python
import logging
logger = logging.getLogger('apps.peoples')
logger.setLevel(logging.DEBUG)
```

---

**Last Updated:** November 12, 2025
**Maintainers:** Development Team
**Contact:** dev-team@example.com
