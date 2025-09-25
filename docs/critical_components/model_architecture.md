# Custom Model Architecture

## Overview
YOUTILITY5 implements a sophisticated model architecture with automatic audit trails, multi-tenant isolation, and custom field encryption. All models inherit from BaseModel and TenantAwareModel, providing consistent tracking and security across the application.

## Core Components

### BaseModel - Foundation for All Models
**Location**: `/apps/peoples/models.py`

```python
class BaseModel(models.Model):
    cuser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="%(class)s_cusers",
    )
    muser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="%(class)s_musers",
    )
    cdtz = models.DateTimeField(_("cdtz"), default=now)
    mdtz = models.DateTimeField(_("mdtz"), default=now)
    ctzoffset = models.IntegerField(_("TimeZone"), default=-1)

    class Meta:
        abstract = True
        ordering = ["mdtz"]
```

### Field Explanations

| Field | Purpose | Type | Notes |
|-------|---------|------|-------|
| `cuser` | Created by user | ForeignKey | Tracks who created the record |
| `muser` | Modified by user | ForeignKey | Tracks who last modified |
| `cdtz` | Creation timestamp | DateTimeField | When record was created |
| `mdtz` | Modification timestamp | DateTimeField | When last modified |
| `ctzoffset` | Timezone offset | IntegerField | Client timezone offset in minutes |

## TenantAwareModel - Multi-Tenant Isolation
**Location**: `/apps/tenants/models.py`

```python
class TenantAwareModel(models.Model):
    bu = models.ForeignKey(
        'BusinessUnit',
        on_delete=models.CASCADE,
        related_name="%(class)s_bu",
        null=True,
        blank=True
    )
    client = models.ForeignKey(
        'Client',
        on_delete=models.CASCADE,
        related_name="%(class)s_client",
        null=True,
        blank=True
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Auto-populate tenant fields from request context
        if not self.bu_id and hasattr(self, '_request'):
            self.bu_id = self._request.session.get('bu_id')
        if not self.client_id and hasattr(self, '_request'):
            self.client_id = self._request.session.get('client_id')
        super().save(*args, **kwargs)
```

## Custom Field Types

### SecureString - Encrypted CharField
**Purpose**: Automatic encryption/decryption for sensitive data

```python
class SecureString(CharField):
    """Custom Encrypted Field"""

    def from_db_value(self, value, expression, connection):
        """Decrypt value when reading from database"""
        from apps.core.utils_new.string_utils import decrypt
        if value and value != "":
            try:
                return decrypt(value)
            except Exception:
                # Migration compatibility - assume plain text
                return value
        return value

    def get_prep_value(self, value):
        """Encrypt value when saving to database"""
        from apps.core.utils_new.string_utils import encrypt
        if value and value != "":
            try:
                # Check if already encrypted
                if isinstance(value, str) and len(value) > 20 and \
                   value.replace('-', '').replace('_', '').isalnum():
                    return value  # Already encrypted
                return encrypt(value).decode('utf-8')
            except Exception:
                return value
        return value
```

## Model Implementation Patterns

### 1. Standard Model Definition
```python
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel

class Job(BaseModel, TenantAwareModel):
    jobcode = models.CharField(max_length=50, unique=True)
    jobname = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='pending')
    assigned_to = models.ForeignKey(
        'peoples.People',
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_jobs'
    )

    class Meta(BaseModel.Meta):
        db_table = 'activity_job'
        verbose_name = 'Job'
        verbose_name_plural = 'Jobs'
        indexes = [
            models.Index(fields=['status', 'bu']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f"{self.jobcode} - {self.jobname}"
```

### 2. Model with JSONField Default
```python
def default_settings():
    return {
        "notifications": True,
        "email_alerts": False,
        "sms_alerts": False,
        "escalation_minutes": 30,
        "priority_levels": ["low", "medium", "high", "critical"]
    }

class TicketType(BaseModel, TenantAwareModel):
    name = models.CharField(max_length=100)
    settings = models.JSONField(default=default_settings)
    is_active = models.BooleanField(default=True)

    class Meta(BaseModel.Meta):
        db_table = 'helpdesk_tickettype'
        unique_together = [['name', 'bu']]
```

### 3. Model with Custom Manager
```python
class AssetManager(models.Manager):
    def get_active(self):
        return self.filter(status='active')

    def get_by_location(self, location_id):
        return self.filter(location_id=location_id)

class Asset(BaseModel, TenantAwareModel):
    assetcode = models.CharField(max_length=50, unique=True)
    assetname = models.CharField(max_length=200)
    location = models.ForeignKey('Location', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, default='active')

    objects = AssetManager()  # Custom manager

    class Meta(BaseModel.Meta):
        db_table = 'activity_asset'
```

## People Model - User Authentication
**Location**: `/apps/peoples/models.py`

```python
class People(AbstractBaseUser, PermissionsMixin, TenantAwareModel, BaseModel):
    class Gender(models.TextChoices):
        M = ("M", "Male")
        F = ("F", "Female")
        O = ("O", "Others")

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    peopleimg = models.ImageField(upload_to=upload_peopleimg)
    peoplecode = models.CharField(max_length=50, unique=True)
    peoplename = models.CharField(max_length=200)
    loginid = models.CharField(max_length=100, unique=True)
    password_hash = SecureString(max_length=255)  # Encrypted field
    email = models.EmailField()
    mobno = models.CharField(max_length=20)
    gender = models.CharField(max_length=1, choices=Gender.choices)
    dob = models.DateField(null=True, blank=True)
    peoplejson = models.JSONField(default=peoplejson)
    isactive = models.BooleanField(default=True)
    isverified = models.BooleanField(default=False)

    USERNAME_FIELD = 'loginid'
    REQUIRED_FIELDS = ['email', 'peoplename']

    objects = PeopleManager()

    class Meta(BaseModel.Meta):
        db_table = 'peoples_people'
        verbose_name = 'Person'
        verbose_name_plural = 'People'
```

## Model Signals & Auto-Population

### Auto-populate Audit Fields
```python
from django.db.models.signals import pre_save
from django.dispatch import receiver

@receiver(pre_save)
def auto_populate_audit_fields(sender, instance, **kwargs):
    # Skip if not a BaseModel subclass
    if not isinstance(instance, BaseModel):
        return

    # Get current user from thread-local storage
    from apps.core.middleware import get_current_user
    user = get_current_user()

    if not instance.pk:  # New record
        instance.cuser = user
        instance.cdtz = timezone.now()

    # Always update modification fields
    instance.muser = user
    instance.mdtz = timezone.now()
```

### Tenant Context Middleware
```python
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set tenant context from session/JWT
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.bu_id = request.session.get('bu_id')
            request.client_id = request.session.get('client_id')

        response = self.get_response(request)
        return response
```

## Database Indexes & Optimization

### Strategic Index Placement
```python
class Job(BaseModel, TenantAwareModel):
    # Fields...

    class Meta(BaseModel.Meta):
        indexes = [
            models.Index(fields=['status', 'bu']),  # Tenant + status queries
            models.Index(fields=['mdtz']),  # Recent modifications
            models.Index(fields=['assigned_to', 'status']),  # User workload
            models.Index(fields=['jobcode']),  # Lookup by code
        ]
        unique_together = [
            ['jobcode', 'bu']  # Unique per tenant
        ]
```

## Model Inheritance Hierarchy

```
models.Model (Django Base)
    ├── BaseModel (Audit fields)
    │   └── TenantAwareModel (Multi-tenant)
    │       ├── Job
    │       ├── Asset
    │       ├── Ticket
    │       └── [Other domain models]
    │
    └── AbstractBaseUser (Django Auth)
        └── People (Custom User Model)
```

## JSON Field Patterns

### Complex Default Structure
```python
def peoplejson():
    return {
        "andriodversion": "",
        "appversion": "",
        "mobilecapability": [],
        "portletcapability": [],
        "reportcapability": [],
        "webcapability": [],
        "noccapability": [],
        "loacationtracking": False,
        "capturemlog": False,
        "showalltemplates": False,
        "debug": False,
        "showtemplatebasedonfilter": False,
        "blacklist": False,
        "assignsitegroup": [],
        "tempincludes": [],
        "mlogsendsto": "",
        "user_type": "",
        "secondaryemails": [],
        "secondarymobno": [],
        "isemergencycontact": False,
        "alertmails": False,
        "currentaddress": "",
        "permanentaddress": "",
        "isworkpermit_approver": False,
        "userfor": "",
        'enable_gps': False,
        'noc_user': False
    }
```

## Migration Strategies

### Adding BaseModel to Existing Model
```python
# Step 1: Add fields with null=True
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='existingmodel',
            name='cuser',
            field=models.ForeignKey(null=True, blank=True, ...),
        ),
        migrations.AddField(
            model_name='existingmodel',
            name='cdtz',
            field=models.DateTimeField(null=True),
        ),
        # Add other fields...
    ]

# Step 2: Data migration to populate fields
def populate_audit_fields(apps, schema_editor):
    Model = apps.get_model('app', 'ExistingModel')
    for obj in Model.objects.all():
        if not obj.cdtz:
            obj.cdtz = obj.created_at or timezone.now()
        if not obj.mdtz:
            obj.mdtz = obj.updated_at or timezone.now()
        obj.save()

# Step 3: Make fields non-nullable
```

## Testing Model Architecture

### Test Audit Fields
```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.activity.models import Job

class TestBaseModel(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            loginid='testuser',
            email='test@test.com',
            password='testpass'
        )

    def test_audit_fields_populated(self):
        job = Job.objects.create(
            jobcode='TEST001',
            jobname='Test Job',
            _request=self.client.request
        )

        self.assertIsNotNone(job.cdtz)
        self.assertIsNotNone(job.mdtz)
        self.assertEqual(job.cdtz, job.mdtz)  # Same on creation

    def test_modification_updates_mdtz(self):
        job = Job.objects.create(jobcode='TEST002', jobname='Test')
        original_mdtz = job.mdtz

        # Simulate time passing
        import time
        time.sleep(1)

        job.jobname = 'Updated'
        job.save()

        self.assertNotEqual(job.mdtz, original_mdtz)
        self.assertEqual(job.cdtz, job.cdtz)  # Creation time unchanged
```

### Test Tenant Isolation
```python
def test_tenant_isolation(self):
    bu1 = BusinessUnit.objects.create(buname='Unit1')
    bu2 = BusinessUnit.objects.create(buname='Unit2')

    job1 = Job.objects.create(jobcode='J1', bu=bu1)
    job2 = Job.objects.create(jobcode='J2', bu=bu2)

    # Filter by tenant
    bu1_jobs = Job.objects.filter(bu=bu1)
    self.assertEqual(bu1_jobs.count(), 1)
    self.assertEqual(bu1_jobs.first(), job1)
```

## Best Practices

1. **Always inherit from BaseModel** for domain models
2. **Add TenantAwareModel** for multi-tenant data
3. **Use SecureString** for sensitive data fields
4. **Define appropriate indexes** based on query patterns
5. **Set unique_together** for tenant-scoped uniqueness
6. **Use JSONField defaults** as functions, not mutable objects
7. **Override save()** for complex business logic
8. **Add custom managers** for common query patterns
9. **Document field purposes** in help_text
10. **Test audit trail** functionality

## Performance Considerations

### Query Optimization
```python
# Bad - N+1 queries
jobs = Job.objects.all()
for job in jobs:
    print(job.assigned_to.peoplename)  # Extra query per job

# Good - Single query with join
jobs = Job.objects.select_related('assigned_to').all()
for job in jobs:
    print(job.assigned_to.peoplename)  # No extra queries
```

### Index Usage
```python
# Queries that benefit from indexes
Job.objects.filter(status='active', bu_id=1)  # Uses composite index
Job.objects.filter(mdtz__gte=yesterday)  # Uses mdtz index
Job.objects.filter(assigned_to_id=user_id, status='pending')  # Uses composite
```

## Related Documentation
- [Manager Pattern](./manager_pattern.md) - Query optimization strategies
- [Multi-Tenancy](./multi_tenancy.md) - Tenant isolation details
- [Security Middleware](./security_middleware.md) - Request context handling