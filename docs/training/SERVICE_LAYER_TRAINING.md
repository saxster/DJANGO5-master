# Service Layer Training Guide

**Audience:** Developers implementing business logic

**Prerequisites:** Quality Standards Training

**Duration:** 2 hours

**Last Updated:** November 5, 2025

---

## What is the Service Layer Pattern?

**ADR 003 Decision:** Views handle HTTP, Services handle business logic

### The Problem

```python
# ❌ FAT VIEW: 200+ lines of business logic
class AttendanceView(View):
    def post(self, request):
        # Validate form (30 lines)
        # Check geofence (40 lines)
        # Verify biometrics (50 lines)
        # Save to database (30 lines)
        # Send notifications (25 lines)
        # Log audit trail (25 lines)
        # All mixed together!
```

### The Solution

```python
# ✅ THIN VIEW: 15 lines of HTTP handling
class AttendanceView(View):
    def post(self, request):
        """Handle attendance check-in request."""
        # Validate HTTP request
        form = AttendanceForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'errors': form.errors}, status=400)

        # Delegate to service
        try:
            event = AttendanceService.process_checkin(
                user=request.user,
                **form.cleaned_data
            )
            return JsonResponse({'event_id': event.id}, status=201)
        except AttendanceError as e:
            return JsonResponse({'error': str(e)}, status=400)
```

```python
# ✅ SERVICE LAYER: Reusable business logic
class AttendanceService:
    """Service for attendance operations."""

    @staticmethod
    def process_checkin(user, coordinates, timestamp):
        """Process attendance check-in with all business rules."""
        # Validate geofence
        location = GeofenceService.validate_location(coordinates)

        # Verify biometrics (if required)
        if location.requires_biometrics:
            BiometricService.verify_face(user, ...)

        # Create event
        event = PeopleEventlog.objects.create(
            user=user,
            location=location,
            timestamp=timestamp
        )

        # Send notifications
        NotificationService.send_checkin_confirmation(user, event)

        # Audit trail
        AuditService.log_checkin(user, event)

        return event
```

---

## Benefits

✅ **Reusability** - Call from views, Celery tasks, management commands
✅ **Testability** - Test business logic without HTTP layer
✅ **Maintainability** - Business logic in one place
✅ **Clarity** - Clear separation of concerns

---

## Service Layer Architecture

```
┌─────────────────────────────────────────┐
│         HTTP/API/CLI Layer              │
│  (Views, API ViewSets, Commands)        │
│  • Request validation                   │
│  • Response formatting                  │
│  • < 30 lines per method                │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│           Service Layer                 │
│  (Business Logic)                       │
│  • Domain rules                         │
│  • Orchestration                        │
│  • Transaction management               │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│        Data Layer                       │
│  (Models, QuerySets)                    │
│  • Database operations                  │
│  • Data validation                      │
└─────────────────────────────────────────┘
```

---

## Creating a Service Class

### File Organization

```
apps/your_app/
├── services/
│   ├── __init__.py
│   ├── your_service.py      # Main service
│   ├── notification_service.py
│   └── validation_service.py
```

### Basic Service Template

```python
# services/your_service.py
"""
YourService: Business logic for [domain]

Responsibilities:
- [Responsibility 1]
- [Responsibility 2]

Usage:
    result = YourService.do_something(user, data)
"""

from django.db import transaction
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


class YourService:
    """Service for [domain] operations."""

    @staticmethod
    @transaction.atomic
    def create_something(user, name, **kwargs):
        """
        Create something with business rules.

        Args:
            user: User creating the entity
            name: Name of the entity
            **kwargs: Additional fields

        Returns:
            Created instance

        Raises:
            ValidationError: If data invalid
            PermissionDenied: If user lacks permission
        """
        # 1. Validate permissions
        if not user.has_perm('your_app.add_something'):
            raise PermissionDenied("User cannot create something")

        # 2. Apply business rules
        if len(name) < 3:
            raise ValidationError("Name too short")

        # 3. Create entity
        try:
            instance = YourModel.objects.create(
                owner=user,
                name=name,
                **kwargs
            )
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to create: {e}", exc_info=True)
            raise

        # 4. Side effects
        NotificationService.notify_creation(instance)
        AuditService.log_creation(user, instance)

        return instance

    @staticmethod
    def update_something(instance, **kwargs):
        """Update something with validation."""
        # Implementation...
        pass

    @staticmethod
    def delete_something(instance, user):
        """Delete with business rules."""
        # Implementation...
        pass
```

---

## Common Patterns

### Pattern 1: Orchestration

**Use when:** Coordinating multiple operations

```python
class OrderService:
    @staticmethod
    @transaction.atomic
    def process_order(cart, user):
        """Process order with multiple steps."""
        # Validate inventory
        inventory_ok = InventoryService.check_availability(cart)
        if not inventory_ok:
            raise OutOfStockError()

        # Process payment
        payment = PaymentService.charge_card(cart.total, user)

        # Create order
        order = Order.objects.create(user=user, total=cart.total)

        # Reserve inventory
        InventoryService.reserve_items(cart, order)

        # Send confirmations
        EmailService.send_order_confirmation(order)

        return order
```

### Pattern 2: Complex Validation

```python
class AttendanceService:
    @staticmethod
    def validate_checkin(user, coordinates, timestamp):
        """Multi-step validation."""
        # Geographic validation
        if not GeofenceService.is_within_boundary(coordinates):
            raise OutOfBoundsError()

        # Time validation
        if timestamp > timezone.now():
            raise FutureTimestampError()

        # Duplicate check
        if AttendanceService.has_recent_checkin(user):
            raise DuplicateCheckinError()

        return True
```

### Pattern 3: Data Aggregation

```python
class ReportService:
    @staticmethod
    def generate_summary(site_id, start_date, end_date):
        """Aggregate data from multiple sources."""
        attendance = AttendanceService.get_stats(site_id, start_date, end_date)
        incidents = IncidentService.get_stats(site_id, start_date, end_date)
        tasks = TaskService.get_stats(site_id, start_date, end_date)

        return {
            'attendance': attendance,
            'incidents': incidents,
            'tasks': tasks,
            'generated_at': timezone.now()
        }
```

---

## Testing Services

### Unit Testing (Fast)

```python
# tests/test_services/test_your_service.py

import pytest
from apps.your_app.services import YourService


@pytest.mark.django_db
class TestYourService:
    def test_create_something_success(self, user):
        """Test successful creation."""
        result = YourService.create_something(
            user=user,
            name="Test Name"
        )

        assert result.name == "Test Name"
        assert result.owner == user

    def test_create_something_validation_error(self, user):
        """Test validation failure."""
        with pytest.raises(ValidationError):
            YourService.create_something(
                user=user,
                name="ab"  # Too short
            )

    def test_create_something_permission_denied(self, user_without_perm):
        """Test permission check."""
        with pytest.raises(PermissionDenied):
            YourService.create_something(
                user=user_without_perm,
                name="Test"
            )
```

### Integration Testing

```python
@pytest.mark.django_db
class TestOrderServiceIntegration:
    def test_process_order_flow(self, cart, user):
        """Test complete order flow."""
        # Process order
        order = OrderService.process_order(cart, user)

        # Verify order created
        assert Order.objects.filter(id=order.id).exists()

        # Verify inventory reserved
        assert InventoryService.is_reserved(cart.items)

        # Verify payment processed
        assert PaymentService.has_charge(order)

        # Verify email sent
        assert len(mail.outbox) == 1
```

---

## Common Mistakes

### Mistake 1: Business Logic in Views

```python
# ❌ WRONG
class UserRegistrationView(View):
    def post(self, request):
        # 150 lines of business logic
        # Validation, creation, emails, etc.
        pass
```

```python
# ✅ CORRECT
class UserRegistrationView(View):
    def post(self, request):
        form = RegistrationForm(request.POST)
        if not form.is_valid():
            return JsonResponse({'errors': form.errors}, status=400)

        user = UserService.register_user(**form.cleaned_data)
        return JsonResponse({'user_id': user.id}, status=201)
```

### Mistake 2: Services in Models

```python
# ❌ WRONG: Service logic in model
class Order(models.Model):
    def process_payment_and_fulfill(self):
        # Charge card
        # Send emails
        # Update inventory
        pass
```

```python
# ✅ CORRECT: Models for data, services for logic
class Order(models.Model):
    # Just data and simple methods
    def total_amount(self):
        return sum(item.price for item in self.items.all())

class OrderService:
    @staticmethod
    def process_and_fulfill(order):
        # Business logic here
        pass
```

### Mistake 3: Tight Coupling

```python
# ❌ WRONG: Service depends on request object
class YourService:
    def do_something(self, request):
        user = request.user  # Tight coupling to HTTP!
        # Now can't call from Celery task
```

```python
# ✅ CORRECT: Service accepts explicit parameters
class YourService:
    def do_something(self, user, data):
        # Can call from anywhere
        pass
```

---

## Hands-On Exercise

**Task:** Extract business logic from a fat view into a service

**Starting Code:**

```python
# views.py (80 lines)
class CheckInView(View):
    def post(self, request):
        # Parse data
        latitude = float(request.POST.get('latitude'))
        longitude = float(request.POST.get('longitude'))

        # Check geofence
        geofence = Geofence.objects.filter(
            location__contains=Point(longitude, latitude)
        ).first()
        if not geofence:
            return JsonResponse({'error': 'Out of bounds'}, status=400)

        # Check duplicate
        recent = PeopleEventlog.objects.filter(
            user=request.user,
            timestamp__gte=timezone.now() - timedelta(minutes=5)
        ).exists()
        if recent:
            return JsonResponse({'error': 'Duplicate'}, status=400)

        # Create event
        event = PeopleEventlog.objects.create(
            user=request.user,
            geofence=geofence,
            latitude=latitude,
            longitude=longitude
        )

        # Send notification
        send_mail(
            subject='Check-in Confirmed',
            message=f'You checked in at {geofence.name}',
            from_email='noreply@example.com',
            recipient_list=[request.user.email]
        )

        return JsonResponse({'event_id': event.id}, status=201)
```

**Your Task:** Refactor into:
1. Thin view (< 30 lines)
2. Service class with business logic
3. Tests for service

**Solution:** See `docs/architecture/adr/003-service-layer-pattern.md` for complete example

---

## Resources

- **[ADR 003: Service Layer Pattern](../architecture/adr/003-service-layer-pattern.md)**
- **[REFACTORING_PLAYBOOK.md](../architecture/REFACTORING_PLAYBOOK.md)**
- Clean Architecture by Robert C. Martin

---

## Next Steps

1. Complete [Testing Training](TESTING_TRAINING.md)
2. Refactor one fat view in your codebase
3. Write tests for your service
4. Get code review feedback

---

**Training Complete! 🎓**

**Last Updated:** November 5, 2025
