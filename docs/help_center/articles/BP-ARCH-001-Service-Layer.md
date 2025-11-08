# Best Practices: Service Layer Pattern

**ID:** BP-ARCH-001  
**Category:** Architecture Best Practices  
**Difficulty:** Advanced  
**Last Updated:** November 6, 2025

---

## Overview

The service layer encapsulates business logic, keeping it separate from views, models, and forms. This creates testable, reusable, maintainable code.

**Key Principle:** Views route requests, Services implement business logic, Models represent data.

---

## Why Service Layer?

### ❌ Without Service Layer (God Views)

```python
# ❌ BAD: Business logic scattered in views

def create_work_order(request):
    """175-line view method (violates 30-line limit)."""
    
    if request.method == 'POST':
        # Validation logic
        title = request.POST.get('title')
        if not title or len(title) < 5:
            messages.error(request, "Title too short")
            return redirect('work_orders')
        
        # Business logic
        work_order = WorkOrder.objects.create(
            title=title,
            site_id=request.POST['site_id'],
            created_by=request.user,
            tenant=request.user.tenant
        )
        
        # Notification logic
        managers = People.objects.filter(
            role='MANAGER',
            site=work_order.site
        )
        for manager in managers:
            send_email(
                to=manager.email,
                subject=f"New work order: {work_order.title}",
                body=f"Created by {request.user.username}"
            )
        
        # Audit logging
        AuditLog.objects.create(
            action='CREATE_WORK_ORDER',
            user=request.user,
            details={'work_order_id': work_order.id}
        )
        
        # Webhook notifications
        if work_order.site.webhook_url:
            try:
                requests.post(
                    work_order.site.webhook_url,
                    json={'event': 'work_order_created', 'id': work_order.id}
                )
            except Exception:
                pass
        
        # ... 100+ more lines ...
        
        messages.success(request, "Work order created")
        return redirect('work_order_detail', work_order.id)
```

**Problems:**
- ✅ 175 lines (violates 30-line limit)
- ✅ Cannot test business logic without HTTP request
- ✅ Cannot reuse logic from API, Celery tasks, management commands
- ✅ Hard to maintain and debug

---

## ✅ With Service Layer (Clean Separation)

### Step 1: Extract Service

```python
# apps/work_order_management/services/work_order_service.py

import logging
from django.db import transaction
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS
from apps.work_order_management.models import WorkOrder
from apps.notifications.services import NotificationService
from apps.core.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class WorkOrderService:
    """
    Business logic for work order operations.
    
    Single Responsibility: Work order lifecycle management
    """
    
    @staticmethod
    @transaction.atomic
    def create_work_order(
        title: str,
        site_id: int,
        created_by,
        tenant,
        description: str = "",
        priority: str = "MEDIUM"
    ) -> WorkOrder:
        """
        Create work order with validation, notifications, and audit trail.
        
        Args:
            title: Work order title (min 5 chars)
            site_id: Site where work will be performed
            created_by: User creating work order
            tenant: Tenant for multi-tenant isolation
            description: Optional detailed description
            priority: Priority level (LOW, MEDIUM, HIGH, URGENT)
        
        Returns:
            Created WorkOrder instance
        
        Raises:
            ValidationError: If validation fails
            DatabaseError: If save fails
        """
        # Validation
        if not title or len(title) < 5:
            raise ValidationError("Title must be at least 5 characters")
        
        # Create work order
        try:
            work_order = WorkOrder.objects.create(
                title=title,
                site_id=site_id,
                created_by=created_by,
                tenant=tenant,
                description=description,
                priority=priority,
                status='PENDING'
            )
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to create work order: {e}", exc_info=True)
            raise
        
        # Delegate to other services
        WorkOrderService._send_notifications(work_order)
        WorkOrderService._send_webhooks(work_order)
        AuditService.log_action(
            action='CREATE_WORK_ORDER',
            user=created_by,
            resource=work_order
        )
        
        logger.info(f"Work order created: {work_order.id} by {created_by.username}")
        return work_order
    
    @staticmethod
    def _send_notifications(work_order):
        """Send notifications to relevant users."""
        from apps.peoples.models import People
        
        managers = People.objects.filter(
            role='MANAGER',
            site=work_order.site,
            tenant=work_order.tenant
        ).select_related('profile')
        
        for manager in managers:
            NotificationService.send_email(
                to=manager.email,
                template='work_order_created',
                context={
                    'work_order': work_order,
                    'manager': manager
                }
            )
    
    @staticmethod
    def _send_webhooks(work_order):
        """Send webhook notifications if configured."""
        if not work_order.site.webhook_url:
            return
        
        try:
            import requests
            from apps.core.constants.timeout_constants import API_TIMEOUT
            
            requests.post(
                work_order.site.webhook_url,
                json={
                    'event': 'work_order_created',
                    'id': work_order.id,
                    'title': work_order.title,
                    'priority': work_order.priority
                },
                timeout=API_TIMEOUT
            )
        except Exception as e:
            logger.warning(f"Webhook failed for work order {work_order.id}: {e}")
            # Don't fail work order creation if webhook fails
```

### Step 2: Simplified View

```python
# apps/work_order_management/views.py

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from apps.work_order_management.services.work_order_service import WorkOrderService
from apps.core.exceptions.patterns import VALIDATION_EXCEPTIONS

@login_required
def create_work_order(request):
    """
    Route request to service layer.
    
    This view is now 25 lines (under 30-line limit).
    """
    if request.method == 'POST':
        try:
            # Delegate to service
            work_order = WorkOrderService.create_work_order(
                title=request.POST.get('title'),
                site_id=request.POST.get('site_id'),
                created_by=request.user,
                tenant=request.user.tenant,
                description=request.POST.get('description', ''),
                priority=request.POST.get('priority', 'MEDIUM')
            )
            
            messages.success(request, f"Work order #{work_order.id} created")
            return redirect('work_order_detail', work_order.id)
            
        except VALIDATION_EXCEPTIONS as e:
            messages.error(request, str(e))
            return redirect('work_orders')
    
    return render(request, 'work_order_form.html')
```

**Benefits:**
- ✅ View is 25 lines (under limit)
- ✅ Business logic reusable in API, Celery, management commands
- ✅ Testable without HTTP request
- ✅ Clear separation of concerns

---

## Service Layer Patterns

### Pattern 1: CRUD Operations

```python
class WorkOrderService:
    """CRUD + business logic."""
    
    @staticmethod
    def create_work_order(...):
        """Create with validation and side effects."""
        pass
    
    @staticmethod
    def update_work_order(work_order_id, **updates):
        """Update with change tracking."""
        pass
    
    @staticmethod
    def delete_work_order(work_order_id, deleted_by):
        """Soft delete with audit trail."""
        pass
    
    @staticmethod
    def get_work_order(work_order_id, user):
        """Get with permission check."""
        pass
```

### Pattern 2: Business Operations

```python
class WorkOrderService:
    """Business operations beyond CRUD."""
    
    @staticmethod
    def approve_work_order(work_order_id, approved_by):
        """Approve work order and trigger workflows."""
        work_order = WorkOrder.objects.get(id=work_order_id)
        
        # Business rules
        if not approved_by.has_perm('work_order.approve'):
            raise PermissionDenied("User cannot approve work orders")
        
        if work_order.status != 'PENDING':
            raise ValidationError("Only pending work orders can be approved")
        
        # State transition
        work_order.status = 'APPROVED'
        work_order.approved_by = approved_by
        work_order.approved_at = timezone.now()
        work_order.save()
        
        # Side effects
        NotificationService.notify_approval(work_order)
        WorkflowService.trigger_next_step(work_order)
        
        return work_order
```

### Pattern 3: Complex Queries

```python
class WorkOrderAnalyticsService:
    """Analytics and reporting queries."""
    
    @staticmethod
    def get_overdue_work_orders(site_id=None):
        """Get work orders past due date."""
        from django.utils import timezone
        
        qs = WorkOrder.objects.filter(
            status__in=['PENDING', 'IN_PROGRESS'],
            due_date__lt=timezone.now()
        ).select_related('site', 'assigned_to')
        
        if site_id:
            qs = qs.filter(site_id=site_id)
        
        return qs.order_by('due_date')
    
    @staticmethod
    def get_completion_metrics(start_date, end_date):
        """Calculate completion metrics for date range."""
        from django.db.models import Count, Avg, Q
        
        return WorkOrder.objects.filter(
            completed_at__range=[start_date, end_date]
        ).aggregate(
            total_completed=Count('id'),
            avg_completion_days=Avg('completion_days'),
            on_time_count=Count('id', filter=Q(completed_at__lte=F('due_date')))
        )
```

---

## Testing Service Layer

```python
from django.test import TestCase
from apps.work_order_management.services.work_order_service import WorkOrderService
from apps.peoples.models import People
from apps.sites.models import Site

class WorkOrderServiceTests(TestCase):
    """
    Test business logic without HTTP layer.
    
    Much simpler than view tests!
    """
    
    def setUp(self):
        self.user = People.objects.create_user(username='testuser')
        self.site = Site.objects.create(name='Test Site', tenant=self.user.tenant)
    
    def test_create_work_order_success(self):
        """Valid work order creation."""
        work_order = WorkOrderService.create_work_order(
            title='Fix broken door',
            site_id=self.site.id,
            created_by=self.user,
            tenant=self.user.tenant
        )
        
        self.assertIsNotNone(work_order.id)
        self.assertEqual(work_order.title, 'Fix broken door')
        self.assertEqual(work_order.status, 'PENDING')
    
    def test_create_work_order_title_too_short(self):
        """Validation error for short title."""
        with self.assertRaises(ValidationError) as cm:
            WorkOrderService.create_work_order(
                title='Fix',  # Too short
                site_id=self.site.id,
                created_by=self.user,
                tenant=self.user.tenant
            )
        
        self.assertIn('at least 5 characters', str(cm.exception))
    
    def test_approve_work_order(self):
        """Approval workflow."""
        work_order = WorkOrderService.create_work_order(
            title='Fix broken door',
            site_id=self.site.id,
            created_by=self.user,
            tenant=self.user.tenant
        )
        
        # Approve
        approved = WorkOrderService.approve_work_order(
            work_order_id=work_order.id,
            approved_by=self.user
        )
        
        self.assertEqual(approved.status, 'APPROVED')
        self.assertIsNotNone(approved.approved_at)
```

---

## Service Organization

```
apps/work_order_management/
├── services/
│   ├── __init__.py
│   ├── work_order_service.py      # CRUD operations
│   ├── approval_service.py        # Approval workflows
│   ├── analytics_service.py       # Reporting queries
│   └── notification_service.py    # Work order notifications
├── models/
│   └── work_order.py
├── views.py                        # Thin routing layer
└── tests/
    ├── test_work_order_service.py
    └── test_approval_service.py
```

---

## Service Layer Checklist

- [ ] **Views are < 30 lines (routing only)**
- [ ] **Business logic in service classes**
- [ ] **Services are static methods or standalone functions**
- [ ] **Services use `@transaction.atomic` for multi-step operations**
- [ ] **Services raise specific exceptions**
- [ ] **Service tests independent of HTTP layer**
- [ ] **Services reused in views, APIs, Celery tasks**
- [ ] **One service per business domain**

---

## Common Mistakes

### Mistake 1: Service Depends on Request

```python
# ❌ WRONG: Service depends on HTTP request
class WorkOrderService:
    @staticmethod
    def create(request):  # Don't pass request object!
        title = request.POST.get('title')
        user = request.user
        # ...
```

**Fix:** Pass only needed parameters.

```python
# ✅ CORRECT: Service independent of HTTP
class WorkOrderService:
    @staticmethod
    def create(title: str, created_by, tenant):
        # ...
```

### Mistake 2: Business Logic in Models

```python
# ❌ WRONG: Business logic in model
class WorkOrder(models.Model):
    def approve(self, approved_by):
        # Complex approval logic with notifications...
        pass
```

**Fix:** Move to service layer.

---

## References

- **[ADR-003: Service Layer Pattern](../../docs/architecture/adr/003-service-layer-pattern.md)** - Architecture decision
- **[Service Layer Training](../../docs/training/SERVICE_LAYER_TRAINING.md)** - Detailed guide
- **[Refactoring Playbook](../../docs/architecture/REFACTORING_PLAYBOOK.md)** - How to extract services
- **[BP-TEST-002: Service Testing](BP-TEST-002-Service-Testing.md)** - Testing strategies

---

**Questions?** Submit a Help Desk ticket with tag `best-practices-services`
