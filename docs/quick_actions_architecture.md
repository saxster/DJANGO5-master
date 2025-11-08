# Quick Actions Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUICK ACTIONS SYSTEM                     │
│                   One-Click Response to Common Situations       │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   MODELS     │────▶│   SERVICE    │────▶│  API/VIEWS   │
│              │     │              │     │              │
│ QuickAction  │     │ QuickAction  │     │ execute_     │
│ Execution    │     │ Service      │     │ quick_action │
│ Checklist    │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       │                     │                     │
       ▼                     ▼                     ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    ADMIN     │     │  TEMPLATES   │     │     URLs     │
│              │     │              │     │              │
│ QuickAction  │     │ Dialog       │     │ /api/quick-  │
│ Admin        │     │ Checklist    │     │ actions/     │
└──────────────┘     └──────────────┘     └──────────────┘
```

## Data Flow

### 1. Action Definition (Admin)

```
Admin User
    │
    ├─▶ Creates QuickAction
    │   ├─ Name: "Camera Offline Quick Fix"
    │   ├─ Automated Steps: [ping, assign, notify]
    │   └─ Manual Steps: [check power, check cable]
    │
    └─▶ Saves to Database
```

### 2. Action Execution (User Flow)

```
User sees issue
    │
    ├─▶ Clicks "⚡ Quick Action" button
    │
    ├─▶ Confirmation dialog shows:
    │   ├─ 🤖 What happens automatically
    │   └─ 👤 What you'll do
    │
    ├─▶ User clicks "Let's Do It!"
    │
    ├─▶ QuickActionService.execute_action()
    │   ├─▶ Validates permissions
    │   ├─▶ Runs automated steps
    │   │   ├─ Ping camera → Success ✓
    │   │   ├─ Assign to Tech → Success ✓
    │   │   └─ Update status → Success ✓
    │   ├─▶ Creates execution record
    │   └─▶ Creates checklist
    │
    └─▶ User completes manual steps
        ├─ ☑ Check power LED [📷 uploaded]
        ├─ ☑ Check network [📷 uploaded]
        └─ ☑ Note location [📝 "Building A, 3rd floor"]
```

### 3. Completion & Analytics

```
All steps complete
    │
    ├─▶ Execution status = "completed"
    ├─▶ Update QuickAction.times_used++
    ├─▶ Calculate success_rate
    └─▶ Show celebration: "🎉 Great job!"
```

## Component Architecture

### Models Layer

```python
QuickAction
├─ name: str
├─ description: str
├─ automated_steps: JSONField
│  └─ [{"action_label": "...", "action_type": "...", "params": {...}}]
├─ manual_steps: JSONField
│  └─ [{"instruction": "...", "needs_photo": bool, "needs_note": bool}]
├─ times_used: int
└─ success_rate: Decimal

QuickActionExecution
├─ quick_action: FK(QuickAction)
├─ content_object: GenericForeignKey  # Any model
├─ executed_by: FK(People)
├─ automated_results: JSONField
├─ status: choices[pending, in_progress, completed, failed]
└─ execution_duration: DurationField

QuickActionChecklist
├─ execution: OneToOne(Execution)
├─ steps: JSONField
│  └─ [{"instruction": "...", "completed": bool, "photo_url": str, "note": str}]
└─ completion_percentage: Decimal
```

### Service Layer

```python
QuickActionService
│
├─ execute_action(action_id, item_object, user)
│  ├─ Validate permissions
│  ├─ Create execution record
│  ├─ Execute automated steps
│  ├─ Create checklist
│  └─ Return result dict
│
├─ _execute_automated_steps(action, item, user)
│  ├─ Loop through automated_steps
│  ├─ Call _execute_step() for each
│  └─ Return results list
│
├─ _execute_step(action_type, item, user, params)
│  ├─ Dispatch to handler
│  └─ Return {success, message}
│
├─ Action Handlers:
│  ├─ _action_update_status()
│  ├─ _action_assign_to_user()
│  ├─ _action_assign_to_group()
│  ├─ _action_send_notification()
│  ├─ _action_add_comment()
│  ├─ _action_set_priority()
│  └─ _action_ping_device()
│
└─ complete_checklist_step(checklist_id, step_index, photo, note)
   ├─ Update step data
   ├─ Recalculate completion
   └─ Update execution if 100% complete
```

### API Layer

```
/api/quick-actions/
│
├─ POST /execute/
│  Body: {action_id, content_type, object_id}
│  Returns: {execution_id, checklist_id, automated_results}
│
├─ GET /available/?content_type=ticket
│  Returns: [{id, name, description, steps_count}]
│
├─ GET /checklist/{id}/
│  Returns: {steps, completion_percentage}
│
├─ PATCH /checklist/{id}/step/{index}/
│  Body: {completed, note}
│  Returns: {success, completion_percentage, all_completed}
│
└─ POST /checklist/{id}/upload-photo/
   FormData: {photo, step_index}
   Returns: {success, photo_url}
```

## Integration Points

### With Tickets

```python
class Ticket(models.Model):
    # ... existing fields ...
    
    def get_suggested_actions(self):
        """Get relevant quick actions for this ticket."""
        if self.priority == 'high':
            return QuickAction.objects.filter(
                name__icontains='high priority',
                is_active=True
            )
        elif 'camera' in self.title.lower():
            return QuickAction.objects.filter(
                name__icontains='camera',
                is_active=True
            )
        return QuickAction.objects.filter(is_active=True)[:5]
```

### With Work Orders

```python
class WorkOrder(models.Model):
    # ... existing fields ...
    
    def execute_maintenance_action(self, user):
        """Execute standard maintenance action."""
        action = QuickAction.objects.get(
            name='Equipment Maintenance Check'
        )
        return QuickActionService.execute_action(
            action_id=action.id,
            item_object=self,
            user=user
        )
```

### With Incidents

```python
class Incident(models.Model):
    # ... existing fields ...
    
    def trigger_emergency_response(self, user):
        """Trigger emergency quick action."""
        if self.incident_type == 'water_leak':
            action = QuickAction.objects.get(
                name='Water Leak Emergency'
            )
        elif self.incident_type == 'power_outage':
            action = QuickAction.objects.get(
                name='Power Outage Response'
            )
        
        return QuickActionService.execute_action(
            action_id=action.id,
            item_object=self,
            user=user
        )
```

## Security Architecture

```
Request
    │
    ├─▶ Authentication Check (IsAuthenticated)
    │   └─ Reject if not logged in
    │
    ├─▶ Permission Check (can_user_execute)
    │   ├─ Check user groups
    │   └─ Reject if not authorized
    │
    ├─▶ Ownership Check (for checklist updates)
    │   └─ User must own the execution
    │
    ├─▶ CSRF Protection
    │   └─ All POST/PATCH require token
    │
    └─▶ Tenant Isolation
        └─ TenantAwareModel filters by tenant
```

## Performance Optimization

```
Database Queries
    │
    ├─▶ Models
    │   ├─ Indexes on: is_active, times_used, status, created_at
    │   └─ select_related('quick_action', 'executed_by')
    │
    ├─▶ Admin
    │   └─ prefetch_related('user_groups')
    │
    └─▶ API
        └─ Batch updates with JSONField
```

## Extension Points

### Adding New Action Type

```python
# In quick_action_service.py

# 1. Add to handlers dict
handlers = {
    # ... existing ...
    'your_new_action': QuickActionService._action_your_new_action,
}

# 2. Implement handler
@staticmethod
def _action_your_new_action(item_object, user, params):
    """Your custom action logic."""
    # Do something
    return {'success': True, 'message': 'Done!'}

# 3. Use in action definition
automated_steps = [
    {
        'action_label': 'Do custom thing',
        'action_type': 'your_new_action',
        'params': {'key': 'value'}
    }
]
```

### Adding Conditional Steps

```python
# Future enhancement
automated_steps = [
    {
        'action_label': 'Notify manager',
        'action_type': 'send_notification',
        'condition': {
            'field': 'priority',
            'operator': 'equals',
            'value': 'high'
        }
    }
]
```

### Adding Rollback

```python
# Future enhancement
class QuickActionExecution(models.Model):
    # ... existing fields ...
    rollback_actions: JSONField = [
        # Actions to undo if needed
    ]
    
    def rollback(self):
        """Undo automated steps."""
        for action in reversed(self.rollback_actions):
            self._execute_rollback_action(action)
```

## Monitoring & Analytics

### Metrics Dashboard

```sql
-- Most used actions
SELECT name, times_used, success_rate
FROM core_quickaction
WHERE is_active = true
ORDER BY times_used DESC
LIMIT 10;

-- Average completion time
SELECT qa.name, AVG(qae.execution_duration)
FROM core_quickaction qa
JOIN core_quickactionexecution qae ON qae.quick_action_id = qa.id
WHERE qae.status = 'completed'
GROUP BY qa.id
ORDER BY AVG(qae.execution_duration) ASC;

-- Success rate by action
SELECT qa.name, 
       COUNT(*) as total,
       SUM(CASE WHEN qae.status = 'completed' THEN 1 ELSE 0 END) as completed,
       (SUM(CASE WHEN qae.status = 'completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as success_pct
FROM core_quickaction qa
JOIN core_quickactionexecution qae ON qae.quick_action_id = qa.id
GROUP BY qa.id
ORDER BY success_pct DESC;
```

---

**Architecture Pattern**: Command Pattern + Strategy Pattern  
**Design Principle**: Separation of Concerns  
**Scalability**: Horizontal (add more action types) + Vertical (performance optimized)  
**Maintainability**: Modular, extensible, well-documented
