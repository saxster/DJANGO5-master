# State Machine Developer Guide

**Version:** 1.0
**Last Updated:** October 2025
**Framework:** Django 5.2.1+

## Overview

The State Machine framework provides a unified, type-safe approach to managing entity lifecycle state transitions with built-in permission enforcement, business rule validation, and audit logging.

## Table of Contents

1. [Architecture](#architecture)
2. [Quick Start](#quick-start)
3. [Creating a State Machine](#creating-a-state-machine)
4. [State Transitions](#state-transitions)
5. [Permission Enforcement](#permission-enforcement)
6. [Business Rule Validation](#business-rule-validation)
7. [Hooks and Callbacks](#hooks-and-callbacks)
8. [Testing State Machines](#testing-state-machines)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Architecture

### Core Components

```
BaseStateMachine (Abstract)
    ├── States (Enum)
    ├── VALID_TRANSITIONS (Dict)
    ├── TRANSITION_PERMISSIONS (Dict)
    ├── validate_transition()
    ├── transition()
    └── business_rules_hooks

Concrete Implementations:
    ├── WorkOrderStateMachine
    ├── TaskStateMachine
    ├── AttendanceStateMachine
    └── TicketStateMachineAdapter
```

### Design Principles

1. **Single Responsibility** - Each state machine manages one entity type
2. **Fail-Fast** - Validation happens before state changes
3. **Atomic Transitions** - All-or-nothing state changes with audit logging
4. **Explicit over Implicit** - All valid transitions must be declared
5. **Type Safety** - States are Enums, not magic strings

---

## Quick Start

### Using an Existing State Machine

```python
from apps.work_order_management.state_machines import WorkOrderStateMachine
from apps.core.state_machines.base import TransitionContext

# Get work order instance
work_order = Wom.objects.get(pk=123)

# Create state machine
sm = WorkOrderStateMachine(instance=work_order)

# Create transition context
context = TransitionContext(
    user=request.user,
    comments='Approved by management'
)

# Perform transition
try:
    result = sm.transition(
        to_state='APPROVED',
        context=context
    )

    if result.success:
        print(f"Transitioned from {result.from_state} to {result.to_state}")
        for warning in result.warnings:
            print(f"Warning: {warning}")
    else:
        print(f"Transition failed: {result.error_message}")

except InvalidTransitionError as e:
    print(f"Invalid transition: {e}")
except PermissionDeniedError as e:
    print(f"Permission denied: {e}")
```

### Checking Valid Transitions

```python
from apps.work_order_management.state_machines import WorkOrderStateMachine

# Get current state
work_order = Wom.objects.get(pk=123)
sm = WorkOrderStateMachine(instance=work_order)

current_state = sm.get_current_state()
print(f"Current state: {current_state}")

# Get valid next states
valid_states = sm.get_valid_next_states(current_state)
print(f"Can transition to: {valid_states}")

# Check specific transition
can_approve = sm.can_transition('APPROVED')
print(f"Can approve: {can_approve}")
```

---

## Creating a State Machine

### Step 1: Define States

```python
from enum import Enum
from apps.core.state_machines.base import BaseStateMachine

class MyEntityStateMachine(BaseStateMachine):
    """
    State machine for MyEntity lifecycle.

    States:
    - DRAFT: Initial state, editable
    - SUBMITTED: Awaiting approval
    - APPROVED: Approved, ready for processing
    - COMPLETED: Processing complete
    - CANCELLED: Cancelled by user
    """

    class States(Enum):
        """Valid states for MyEntity"""
        DRAFT = 'DRAFT'
        SUBMITTED = 'SUBMITTED'
        APPROVED = 'APPROVED'
        COMPLETED = 'COMPLETED'
        CANCELLED = 'CANCELLED'
```

### Step 2: Define Valid Transitions

```python
    VALID_TRANSITIONS = {
        States.DRAFT: {States.SUBMITTED, States.CANCELLED},
        States.SUBMITTED: {States.APPROVED, States.DRAFT},
        States.APPROVED: {States.COMPLETED, States.CANCELLED},
        # Terminal states have no outgoing transitions
        States.COMPLETED: set(),
        States.CANCELLED: set(),
    }
```

**Visualization:**

```
DRAFT ──submit──> SUBMITTED ──approve──> APPROVED ──complete──> COMPLETED
  │                   │                      │
  └──cancel──────────┴──────────────────────┴─> CANCELLED
```

### Step 3: Define Permissions

```python
    TRANSITION_PERMISSIONS = {
        # Transition tuple: (from_state, to_state) -> [required_permissions]
        (States.SUBMITTED, States.APPROVED): ['can_approve_myentity'],
        (States.SUBMITTED, States.DRAFT): [],  # Anyone can revert to draft
        (States.APPROVED, States.COMPLETED): ['can_complete_myentity'],
        (States.DRAFT, States.CANCELLED): [],  # Owner can always cancel
        (States.SUBMITTED, States.CANCELLED): ['can_cancel_submitted'],
        (States.APPROVED, States.CANCELLED): ['can_cancel_approved'],
    }
```

### Step 4: Implement Abstract Methods

```python
    def _get_current_state(self, instance) -> str:
        """Get current state from instance."""
        return instance.status  # Adjust field name as needed

    def _set_current_state(self, instance, new_state: str):
        """Set new state on instance."""
        instance.status = new_state

    def _get_state_field_name(self) -> str:
        """Return the field name that stores state."""
        return 'status'
```

### Step 5: Add Business Rules

```python
    def _validate_business_rules(self, from_state, to_state, context):
        """
        Validate business rules for this transition.

        Returns:
            ValidationResult with success=True/False and any errors
        """
        errors = []
        warnings = []

        # Rule 1: Cannot approve without vendor assignment
        if to_state == self.States.APPROVED:
            if not self.instance.vendor:
                errors.append("Vendor must be assigned before approval")

        # Rule 2: Cannot complete without all line items
        if to_state == self.States.COMPLETED:
            if self.instance.line_items.count() == 0:
                errors.append("At least one line item required for completion")

            # Warning for high-value completions
            if self.instance.total_amount > 10000:
                warnings.append(f"High-value completion: ${self.instance.total_amount}")

        # Rule 3: Rejection requires comments
        if to_state == self.States.DRAFT and from_state == self.States.SUBMITTED:
            if not context.comments:
                errors.append("Comments required when reverting to draft")

        return ValidationResult(
            success=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
```

### Step 6: Add Hooks (Optional)

```python
    def _pre_transition_hook(self, from_state, to_state, context):
        """Called before state change is persisted."""
        # Update timestamps
        if to_state == self.States.SUBMITTED:
            self.instance.submitted_at = timezone.now()
        elif to_state == self.States.APPROVED:
            self.instance.approved_at = timezone.now()
            self.instance.approved_by = context.user

    def _post_transition_hook(self, from_state, to_state, context):
        """Called after state change is persisted."""
        # Send notifications
        if to_state == self.States.APPROVED:
            send_approval_notification(self.instance, context.user)

        # Update related entities
        if to_state == self.States.COMPLETED:
            self.instance.related_tasks.update(status='CLOSED')

        # Trigger workflows
        if to_state == self.States.CANCELLED:
            cancel_related_workflows(self.instance)
```

---

## State Transitions

### Transition Context

```python
from apps.core.state_machines.base import TransitionContext
from datetime import datetime

context = TransitionContext(
    user=request.user,           # Required: User performing transition
    comments='Approval reason',   # Optional: Transition comments
    metadata={                    # Optional: Additional context
        'ip_address': request.META.get('REMOTE_ADDR'),
        'approval_date': datetime.now().isoformat(),
        'department': 'Engineering'
    }
)
```

### Transition Result

```python
from apps.core.state_machines.base import TransitionResult

result = sm.transition('APPROVED', context)

# Check success
if result.success:
    print(f"Transitioned from {result.from_state} to {result.to_state}")
else:
    print(f"Failed: {result.error_message}")

# Handle warnings
for warning in result.warnings:
    logger.warning(f"Transition warning: {warning}")

# Access metadata
correlation_id = result.metadata.get('audit_correlation_id')
```

### Validation Without Transition

```python
# Dry-run validation
validation = sm.validate_transition('APPROVED', context)

if validation.success:
    print("Transition would succeed")
    # Proceed with actual transition
    result = sm.transition('APPROVED', context)
else:
    print(f"Validation failed: {validation.error_message}")
    for error in validation.errors:
        print(f"  - {error}")
```

---

## Permission Enforcement

### Defining Permissions

```python
TRANSITION_PERMISSIONS = {
    # Simple permission check
    (States.DRAFT, States.SUBMITTED): ['can_submit'],

    # Multiple permissions required (AND)
    (States.SUBMITTED, States.APPROVED): [
        'can_approve_work_orders',
        'can_approve_budget'
    ],

    # No permissions required
    (States.DRAFT, States.CANCELLED): [],

    # Complex permission logic (use business rules)
    (States.APPROVED, States.COMPLETED): ['can_complete'],
}
```

### Custom Permission Logic

Override `_check_transition_permission` for complex logic:

```python
def _check_transition_permission(self, from_state, to_state, user):
    """
    Custom permission check with complex logic.
    """
    # Get standard permissions
    transition_key = (from_state, to_state)
    required_perms = self.TRANSITION_PERMISSIONS.get(transition_key, [])

    # Standard check
    has_perms = all(user.has_perm(perm) for perm in required_perms)

    # Additional logic: Owners can always cancel their own drafts
    if (from_state == self.States.DRAFT and
        to_state == self.States.CANCELLED and
        self.instance.created_by == user):
        return True

    # Additional logic: Managers can approve up to $10k
    if to_state == self.States.APPROVED:
        if user.groups.filter(name='Managers').exists():
            if self.instance.total_amount <= 10000:
                return True

    return has_perms
```

### Permission Denial Handling

```python
from apps.core.state_machines.base import PermissionDeniedError

try:
    result = sm.transition('APPROVED', context)
except PermissionDeniedError as e:
    logger.warning(
        f"Permission denied: {e}",
        extra={
            'user': context.user.id,
            'entity': sm.instance.id,
            'transition': f"{sm.get_current_state()} → APPROVED"
        }
    )

    # Audit trail is automatically created
    # Return user-friendly error
    return Response({
        'error': 'You do not have permission to approve this entity',
        'required_permissions': e.required_permissions
    }, status=403)
```

---

## Business Rule Validation

### Common Validation Patterns

#### 1. Field Presence Validation

```python
def _validate_business_rules(self, from_state, to_state, context):
    errors = []

    if to_state == self.States.SUBMITTED:
        # Required fields for submission
        if not self.instance.vendor:
            errors.append("Vendor is required")
        if not self.instance.description:
            errors.append("Description is required")
        if self.instance.line_items.count() == 0:
            errors.append("At least one line item required")

    return ValidationResult(success=len(errors) == 0, errors=errors)
```

#### 2. Date/Time Validation

```python
from django.utils import timezone

def _validate_business_rules(self, from_state, to_state, context):
    errors = []
    warnings = []

    if to_state == self.States.APPROVED:
        # Cannot approve past deadline
        if self.instance.approval_deadline < timezone.now():
            errors.append(f"Approval deadline passed: {self.instance.approval_deadline}")

        # Warn about approaching deadline
        time_until_deadline = self.instance.approval_deadline - timezone.now()
        if time_until_deadline.days < 2:
            warnings.append(f"Approval deadline in {time_until_deadline.days} days")

    return ValidationResult(
        success=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

#### 3. Related Entity Validation

```python
def _validate_business_rules(self, from_state, to_state, context):
    errors = []

    if to_state == self.States.COMPLETED:
        # All related tasks must be completed
        incomplete_tasks = self.instance.tasks.exclude(status='COMPLETED')
        if incomplete_tasks.exists():
            errors.append(
                f"{incomplete_tasks.count()} tasks still incomplete"
            )

        # All approvals must be obtained
        pending_approvals = self.instance.approvals.filter(status='PENDING')
        if pending_approvals.exists():
            errors.append(
                f"{pending_approvals.count()} approvals still pending"
            )

    return ValidationResult(success=len(errors) == 0, errors=errors)
```

#### 4. Threshold Validation

```python
def _validate_business_rules(self, from_state, to_state, context):
    errors = []
    warnings = []

    if to_state == self.States.APPROVED:
        # Check budget threshold
        if self.instance.total_amount > 100000:
            # Require executive approval
            if not context.user.groups.filter(name='Executives').exists():
                errors.append(
                    "Executive approval required for amounts > $100,000"
                )

        # Check spending limit
        user_limit = context.user.profile.approval_limit
        if self.instance.total_amount > user_limit:
            errors.append(
                f"Amount ${self.instance.total_amount} exceeds your limit ${user_limit}"
            )

        # Warning for high-risk categories
        if self.instance.category in ['CONSTRUCTION', 'CONSULTING']:
            warnings.append(f"High-risk category: {self.instance.category}")

    return ValidationResult(
        success=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
```

---

## Hooks and Callbacks

### Available Hooks

| Hook | When Called | Purpose |
|------|-------------|---------|
| `_pre_transition_hook` | Before state change | Update timestamps, prepare data |
| `_post_transition_hook` | After state change | Send notifications, trigger workflows |
| `_validate_business_rules` | During validation | Check business constraints |

### Pre-Transition Hook Example

```python
def _pre_transition_hook(self, from_state, to_state, context):
    """Update entity before state change."""

    # Update timestamps
    if to_state == self.States.SUBMITTED:
        self.instance.submitted_at = timezone.now()
        self.instance.submitted_by = context.user

    if to_state == self.States.APPROVED:
        self.instance.approved_at = timezone.now()
        self.instance.approved_by = context.user

    # Calculate values
    if to_state == self.States.COMPLETED:
        self.instance.completed_at = timezone.now()
        self.instance.actual_duration = (
            self.instance.completed_at - self.instance.started_at
        )

    # Set metadata
    if context.metadata:
        self.instance.transition_metadata = context.metadata
```

### Post-Transition Hook Example

```python
def _post_transition_hook(self, from_state, to_state, context):
    """Execute side effects after state change."""

    # Send notifications
    if to_state == self.States.APPROVED:
        send_email_notification(
            to=self.instance.created_by.email,
            subject=f"Work Order #{self.instance.id} Approved",
            template='work_order_approved.html',
            context={'work_order': self.instance}
        )

    # Update related entities
    if to_state == self.States.COMPLETED:
        # Close all related tasks
        self.instance.tasks.update(status='CLOSED')

        # Update inventory
        for line_item in self.instance.line_items.all():
            update_inventory_level(
                item=line_item.item,
                quantity=-line_item.quantity
            )

    # Trigger webhooks
    if to_state == self.States.CANCELLED:
        trigger_webhook(
            event='work_order.cancelled',
            payload={
                'work_order_id': self.instance.id,
                'cancelled_by': context.user.id,
                'reason': context.comments
            }
        )

    # Create follow-up entities
    if to_state == self.States.APPROVED:
        # Auto-create tasks from template
        create_tasks_from_template(
            work_order=self.instance,
            template=self.instance.task_template
        )
```

---

## Testing State Machines

### Unit Test Example

```python
from django.test import TestCase
from apps.work_order_management.models import Wom
from apps.work_order_management.state_machines import WorkOrderStateMachine
from apps.core.state_machines.base import TransitionContext, InvalidTransitionError

class WorkOrderStateMachineTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com'
        )
        self.work_order = Wom.objects.create(
            status='DRAFT',
            created_by=self.user
        )

    def test_valid_transition_draft_to_submitted(self):
        """Test valid state transition."""
        sm = WorkOrderStateMachine(instance=self.work_order)
        context = TransitionContext(user=self.user, comments='Ready for review')

        result = sm.transition('SUBMITTED', context)

        self.assertTrue(result.success)
        self.assertEqual(result.to_state, 'SUBMITTED')

        # Verify database updated
        self.work_order.refresh_from_db()
        self.assertEqual(self.work_order.status, 'SUBMITTED')

    def test_invalid_transition_rejected(self):
        """Test that invalid transitions are rejected."""
        self.work_order.status = 'DRAFT'
        self.work_order.save()

        sm = WorkOrderStateMachine(instance=self.work_order)
        context = TransitionContext(user=self.user)

        # Cannot jump from DRAFT to COMPLETED
        with self.assertRaises(InvalidTransitionError):
            sm.transition('COMPLETED', context)

    def test_permission_enforcement(self):
        """Test that permissions are enforced."""
        self.work_order.status = 'SUBMITTED'
        self.work_order.save()

        # User without approval permission
        user_no_perm = User.objects.create_user(
            loginid='noperm',
            email='noperm@example.com'
        )

        sm = WorkOrderStateMachine(instance=self.work_order)
        context = TransitionContext(user=user_no_perm, comments='Approved')

        # Should raise PermissionDeniedError
        with self.assertRaises(PermissionDeniedError):
            sm.transition('APPROVED', context)

    def test_business_rule_validation(self):
        """Test business rule validation."""
        self.work_order.status = 'DRAFT'
        self.work_order.vendor = None  # Missing vendor
        self.work_order.save()

        sm = WorkOrderStateMachine(instance=self.work_order)
        context = TransitionContext(user=self.user, comments='Submit')

        # Should fail validation
        validation = sm.validate_transition('APPROVED', context)

        self.assertFalse(validation.success)
        self.assertIn('Vendor', validation.error_message)
```

### Integration Test Example

```python
from django.test import TransactionTestCase

class StateMachineIntegrationTest(TransactionTestCase):
    def test_complete_workflow(self):
        """Test complete entity lifecycle."""
        user = User.objects.create_user(loginid='testuser')
        work_order = Wom.objects.create(status='DRAFT', created_by=user)

        sm = WorkOrderStateMachine(instance=work_order)

        # 1. Submit
        result = sm.transition('SUBMITTED', TransitionContext(user=user))
        self.assertTrue(result.success)

        # 2. Approve
        result = sm.transition('APPROVED', TransitionContext(user=user))
        self.assertTrue(result.success)

        # 3. Start
        result = sm.transition('IN_PROGRESS', TransitionContext(user=user))
        self.assertTrue(result.success)

        # 4. Complete
        result = sm.transition('COMPLETED', TransitionContext(user=user))
        self.assertTrue(result.success)

        # 5. Close
        result = sm.transition('CLOSED', TransitionContext(user=user))
        self.assertTrue(result.success)

        # Verify final state
        work_order.refresh_from_db()
        self.assertEqual(work_order.status, 'CLOSED')
```

---

## Best Practices

### 1. Keep State Machines Focused

✅ **Good:**
```python
class WorkOrderStateMachine(BaseStateMachine):
    """Manages work order lifecycle only."""
    pass
```

❌ **Bad:**
```python
class WorkOrderAndTaskStateMachine(BaseStateMachine):
    """Manages both work orders and tasks."""  # Too broad!
    pass
```

### 2. Use Explicit State Names

✅ **Good:**
```python
class States(Enum):
    DRAFT = 'DRAFT'
    AWAITING_APPROVAL = 'AWAITING_APPROVAL'
    APPROVED = 'APPROVED'
```

❌ **Bad:**
```python
class States(Enum):
    STATE_1 = '1'  # Not descriptive
    STATE_2 = '2'
```

### 3. Validate Early

✅ **Good:**
```python
# Validate before showing form
validation = sm.validate_transition('APPROVED', context)
if not validation.success:
    return render_error(validation.errors)
```

❌ **Bad:**
```python
# Try transition and catch exception
try:
    sm.transition('APPROVED', context)  # Might fail after partial work
except InvalidTransitionError:
    # Too late!
```

### 4. Keep Business Rules Testable

✅ **Good:**
```python
def _validate_business_rules(self, from_state, to_state, context):
    errors = []

    if to_state == self.States.APPROVED:
        if not self._has_vendor():
            errors.append("Vendor required")

    return ValidationResult(success=len(errors) == 0, errors=errors)

def _has_vendor(self):
    """Testable helper method."""
    return self.instance.vendor is not None
```

❌ **Bad:**
```python
def _validate_business_rules(self, from_state, to_state, context):
    # Complex nested logic - hard to test
    if to_state == self.States.APPROVED and not (
        self.instance.vendor and self.instance.vendor.is_active and
        self.instance.vendor.credit_status == 'GOOD' and
        self.instance.total_amount <= self.instance.vendor.credit_limit
    ):
        errors.append("Vendor validation failed")
```

### 5. Use Type Hints

✅ **Good:**
```python
def transition(
    self,
    to_state: str,
    context: TransitionContext
) -> TransitionResult:
    """Type hints improve IDE support and catch errors."""
```

---

## Troubleshooting

### Issue: "Current state is None"

**Cause:** State field not set on instance

**Solution:**
```python
# Ensure state field has default
class MyModel(models.Model):
    status = models.CharField(
        max_length=50,
        default='DRAFT',  # Add default
        choices=STATUS_CHOICES
    )
```

### Issue: "Transition not in VALID_TRANSITIONS"

**Cause:** Forgot to declare transition in VALID_TRANSITIONS

**Solution:**
```python
VALID_TRANSITIONS = {
    States.DRAFT: {States.SUBMITTED},  # Add missing transition
    States.SUBMITTED: {States.APPROVED, States.DRAFT},  # Bi-directional
}
```

### Issue: "Permission check always fails"

**Cause:** Wrong permission name or user doesn't have permission

**Solution:**
```python
# Check permission string
print(user.get_all_permissions())

# Add permission to user/group
from django.contrib.auth.models import Permission
perm = Permission.objects.get(codename='can_approve_work_orders')
user.user_permissions.add(perm)
```

### Issue: "Business rules not being enforced"

**Cause:** Forgot to implement `_validate_business_rules`

**Solution:**
```python
class MyStateMachine(BaseStateMachine):
    def _validate_business_rules(self, from_state, to_state, context):
        """Must implement this method."""
        # Your validation logic here
        return ValidationResult(success=True)
```

---

## Reference

### Complete State Machine Template

```python
from enum import Enum
from typing import Dict, Set, Tuple, List
from django.contrib.auth import get_user_model

from apps.core.state_machines.base import (
    BaseStateMachine,
    TransitionContext,
    ValidationResult,
)

User = get_user_model()


class MyEntityStateMachine(BaseStateMachine):
    """
    State machine for MyEntity lifecycle.

    States: [List states here]
    """

    class States(Enum):
        """Valid states."""
        DRAFT = 'DRAFT'
        SUBMITTED = 'SUBMITTED'
        APPROVED = 'APPROVED'
        COMPLETED = 'COMPLETED'

    VALID_TRANSITIONS: Dict[States, Set[States]] = {
        States.DRAFT: {States.SUBMITTED},
        States.SUBMITTED: {States.APPROVED, States.DRAFT},
        States.APPROVED: {States.COMPLETED},
        States.COMPLETED: set(),  # Terminal state
    }

    TRANSITION_PERMISSIONS: Dict[Tuple[States, States], List[str]] = {
        (States.SUBMITTED, States.APPROVED): ['can_approve'],
        (States.APPROVED, States.COMPLETED): ['can_complete'],
    }

    def _get_current_state(self, instance) -> str:
        return instance.status

    def _set_current_state(self, instance, new_state: str):
        instance.status = new_state

    def _get_state_field_name(self) -> str:
        return 'status'

    def _validate_business_rules(self, from_state, to_state, context):
        errors = []
        warnings = []

        # Add validation logic here

        return ValidationResult(
            success=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _pre_transition_hook(self, from_state, to_state, context):
        """Called before state change."""
        pass

    def _post_transition_hook(self, from_state, to_state, context):
        """Called after state change."""
        pass
```

---

## Further Reading

- [API Documentation](./API_BULK_OPERATIONS.md)
- [Deployment Guide](./DEPLOYMENT_GUIDE_WORKFLOW_ENHANCEMENTS.md)
- [Audit Logging Guide](./AUDIT_LOGGING_GUIDE.md)

**Last Updated:** October 2025
**Contributors:** DevOps Team, Engineering Team
