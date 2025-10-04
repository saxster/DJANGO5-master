# Bulk Operations API Documentation

**Version:** 1.0
**Last Updated:** October 2025
**Status:** Production Ready

## Overview

The Bulk Operations API provides efficient endpoints for performing state transitions, assignments, and updates on multiple entities simultaneously. All bulk operations support:

- **Dry-run mode** - Preview changes without committing
- **Rollback on error** - Atomic transactions with automatic rollback
- **Partial success tracking** - Detailed success/failure reporting
- **Audit logging** - Comprehensive audit trail for compliance
- **Permission enforcement** - Granular permission checks per entity

## Table of Contents

1. [Common Request/Response Format](#common-requestresponse-format)
2. [Work Order Bulk Operations](#work-order-bulk-operations)
3. [Task Bulk Operations](#task-bulk-operations)
4. [Attendance Bulk Operations](#attendance-bulk-operations)
5. [Ticket Bulk Operations](#ticket-bulk-operations)
6. [Error Handling](#error-handling)
7. [Best Practices](#best-practices)
8. [Performance Considerations](#performance-considerations)

---

## Common Request/Response Format

### Request Parameters

All bulk operations accept these common parameters:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ids` | Array[String] | ✅ | List of entity IDs (max 1000) |
| `comments` | String | ⚠️ | Required for terminal states (approve, reject, close) |
| `dry_run` | Boolean | ❌ | Preview changes without saving (default: false) |
| `rollback_on_error` | Boolean | ❌ | Rollback all changes if any fail (default: true) |

### Response Format

```json
{
  "operation_type": "transition_to_APPROVED",
  "total_items": 100,
  "successful_items": 95,
  "failed_items": 5,
  "success_rate": 95.0,
  "successful_ids": ["1", "2", "3", ...],
  "failed_ids": ["98", "99"],
  "failure_details": {
    "98": "Invalid state transition: CLOSED → APPROVED",
    "99": "Permission denied: user lacks 'can_approve_work_orders'"
  },
  "warnings": [
    "Entity 42 is approaching SLA deadline"
  ],
  "was_rolled_back": false,
  "audit_correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `operation_type` | String | Type of operation performed |
| `total_items` | Integer | Total entities in request |
| `successful_items` | Integer | Successfully processed entities |
| `failed_items` | Integer | Failed entities |
| `success_rate` | Float | Percentage of successful operations (0-100) |
| `successful_ids` | Array[String] | IDs of successful entities |
| `failed_ids` | Array[String] | IDs of failed entities |
| `failure_details` | Object | Map of entity ID → error message |
| `warnings` | Array[String] | Non-fatal warnings |
| `was_rolled_back` | Boolean | Whether operation was rolled back |
| `audit_correlation_id` | UUID | Correlation ID for audit trail lookup |

---

## Work Order Bulk Operations

**Base URL:** `/api/v1/work-orders/bulk/`

### 1. Bulk State Transition

**Endpoint:** `POST /api/v1/work-orders/bulk/transition`

**Description:** Transition multiple work orders to a target state.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "target_state": "APPROVED",
  "comments": "Approved by management",
  "dry_run": false,
  "rollback_on_error": true
}
```

**Valid States:**
- `DRAFT` → `SUBMITTED`
- `SUBMITTED` → `APPROVED`, `REJECTED`
- `APPROVED` → `IN_PROGRESS`
- `IN_PROGRESS` → `COMPLETED`, `CANCELLED`
- `COMPLETED` → `CLOSED`

**Required Permissions:**
- `SUBMITTED` → `APPROVED`: `can_approve_work_orders`
- `SUBMITTED` → `REJECTED`: `can_reject_work_orders`
- `IN_PROGRESS` → `CANCELLED`: `can_cancel_work_orders`

---

### 2. Bulk Approve (Convenience)

**Endpoint:** `POST /api/v1/work-orders/bulk/approve`

**Description:** Approve multiple work orders (shortcut for transition to APPROVED).

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Approved",
  "dry_run": false
}
```

**Equivalent to:**
```json
{
  "ids": ["1", "2", "3"],
  "target_state": "APPROVED",
  "comments": "Approved"
}
```

---

### 3. Bulk Reject

**Endpoint:** `POST /api/v1/work-orders/bulk/reject`

**Description:** Reject multiple work orders.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Insufficient budget justification"  // REQUIRED
}
```

**⚠️ Note:** `comments` are mandatory for rejection.

---

### 4. Bulk Assign

**Endpoint:** `POST /api/v1/work-orders/bulk/assign`

**Description:** Assign multiple work orders to a user.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "assigned_to_user": "123",  // User ID
  "comments": "Assigned to maintenance team lead"
}
```

---

### 5. Bulk Update

**Endpoint:** `POST /api/v1/work-orders/bulk/update`

**Description:** Update common fields on multiple work orders.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "update_data": {
    "priority": "HIGH",
    "category": "EMERGENCY",
    "estimated_hours": 4
  },
  "comments": "Updated priority due to customer complaint"
}
```

**Protected Fields (Cannot Update):**
- `id`
- `created_at`
- `created_by`
- `version`

---

## Task Bulk Operations

**Base URL:** `/api/v1/tasks/bulk/`

### 1. Bulk Complete

**Endpoint:** `POST /api/v1/tasks/bulk/complete`

**Description:** Mark multiple tasks as completed.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "All inspections completed successfully",
  "dry_run": false
}
```

**Validation:**
- Task must be in `INPROGRESS` or `WORKING` state
- Required observations/meter readings must be filled

---

### 2. Bulk Start

**Endpoint:** `POST /api/v1/tasks/bulk/start`

**Description:** Start multiple tasks (transition to INPROGRESS).

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Starting morning shift tasks"
}
```

**Validation:**
- Task must be in `ASSIGNED` state
- Task must have an assignee

---

### 3. Bulk Assign

**Endpoint:** `POST /api/v1/tasks/bulk/assign`

**Description:** Assign multiple tasks to a user.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "assigned_to_user": "456",
  "comments": "Reassigned due to sick leave"
}
```

---

## Attendance Bulk Operations

**Base URL:** `/api/v1/attendance/bulk/`

### 1. Bulk Approve

**Endpoint:** `POST /api/v1/attendance/bulk/approve`

**Description:** Approve multiple attendance records.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Approved for payroll processing",
  "dry_run": false
}
```

**Validation:**
- Record must be in `PENDING` state
- Current date must be before payroll cutoff date

---

### 2. Bulk Reject

**Endpoint:** `POST /api/v1/attendance/bulk/reject`

**Description:** Reject multiple attendance records.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Geofence validation failed"  // REQUIRED
}
```

---

### 3. Bulk Lock

**Endpoint:** `POST /api/v1/attendance/bulk/lock`

**Description:** Lock attendance records for payroll (prevents further changes).

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Locked for October 2025 payroll cycle"
}
```

**⚠️ Warning:** This is irreversible. Locked records cannot be modified.

---

### 4. Bulk Update

**Endpoint:** `POST /api/v1/attendance/bulk/update`

**Description:** Update multiple attendance records.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "update_data": {
    "attendance_type": "ADJUSTED",
    "adjustment_reason": "System clock error corrected"
  },
  "comments": "Adjusted for DST transition"
}
```

---

## Ticket Bulk Operations

**Base URL:** `/api/v1/tickets/bulk/`

### 1. Bulk Resolve

**Endpoint:** `POST /api/v1/tickets/bulk/resolve`

**Description:** Resolve multiple tickets.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Fixed by software patch v2.1.0"  // REQUIRED
}
```

---

### 2. Bulk Close

**Endpoint:** `POST /api/v1/tickets/bulk/close`

**Description:** Close multiple tickets.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "comments": "Verified resolved by customer"  // REQUIRED
}
```

---

### 3. Bulk Assign

**Endpoint:** `POST /api/v1/tickets/bulk/assign`

**Description:** Assign multiple tickets to a user.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "assigned_to_user": "789",
  "comments": "Reassigned to Tier 2 support"
}
```

---

### 4. Bulk Update Priority

**Endpoint:** `POST /api/v1/tickets/bulk/update-priority`

**Description:** Update priority for multiple tickets.

**Request:**
```json
{
  "ids": ["1", "2", "3"],
  "priority": "HIGH",
  "comments": "Customer escalation - SLA risk"
}
```

**Valid Priorities:**
- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

---

## Error Handling

### HTTP Status Codes

| Status | Meaning | Response |
|--------|---------|----------|
| `200 OK` | Success | Operation results |
| `400 Bad Request` | Validation error | Error details |
| `401 Unauthorized` | Not authenticated | Login required |
| `403 Forbidden` | Permission denied | Missing permission |
| `404 Not Found` | Endpoint not found | Invalid URL |
| `409 Conflict` | Concurrency conflict | RecordModifiedError |
| `429 Too Many Requests` | Rate limit exceeded | Retry after X seconds |
| `500 Internal Server Error` | Server error | Contact support |

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "ids": "This field is required",
      "target_state": "Invalid choice: INVALID_STATE"
    }
  },
  "status": 400
}
```

### Common Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `VALIDATION_ERROR` | Invalid request data | Check required fields and formats |
| `PERMISSION_DENIED` | User lacks permission | Request permission from admin |
| `INVALID_STATE_TRANSITION` | State change not allowed | Review valid transitions |
| `TOO_MANY_IDS` | More than 1000 IDs | Split into multiple requests |
| `EMPTY_IDS` | No IDs provided | Provide at least one ID |
| `CONCURRENCY_ERROR` | Record modified by another user | Retry with latest data |
| `ENTITY_NOT_FOUND` | Entity ID not found | Verify entity exists |

---

## Best Practices

### 1. Use Dry-Run for Validation

Always test bulk operations with `dry_run: true` first:

```json
{
  "ids": ["1", "2", "3", "4", "5"],
  "target_state": "APPROVED",
  "dry_run": true  // Preview without saving
}
```

### 2. Batch Large Operations

For > 1000 items, split into multiple batches:

```python
def bulk_approve_all(ids, comments):
    batch_size = 1000
    results = []

    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        result = api.post('/api/v1/work-orders/bulk/approve', {
            'ids': batch,
            'comments': comments
        })
        results.append(result)

    return results
```

### 3. Handle Partial Failures

Check `failure_details` and retry failed items:

```python
response = api.post('/api/v1/work-orders/bulk/approve', data)

if response['failed_items'] > 0:
    for entity_id, error in response['failure_details'].items():
        logger.error(f"Failed to approve {entity_id}: {error}")
        # Retry or manual intervention
```

### 4. Use Correlation IDs for Debugging

Track bulk operations using the `audit_correlation_id`:

```python
response = api.post('/api/v1/work-orders/bulk/approve', data)
correlation_id = response['audit_correlation_id']

# Query audit logs later
audit_logs = api.get(f'/api/audit-logs/?correlation_id={correlation_id}')
```

### 5. Set Appropriate Timeouts

Bulk operations may take longer than single operations:

```python
import requests

response = requests.post(
    'https://api.example.com/api/v1/work-orders/bulk/approve',
    json=data,
    timeout=(5, 60)  # 5s connect, 60s read
)
```

---

## Performance Considerations

### Operation Limits

| Metric | Limit | Notes |
|--------|-------|-------|
| Max IDs per request | 1,000 | Hard limit enforced |
| Min IDs per request | 1 | Empty arrays rejected |
| Recommended batch size | 100-500 | Optimal for most cases |
| Timeout | 60 seconds | For 1,000 items |
| Rate limit | 10 req/min | Per user |

### Performance Tips

1. **Use smaller batches** - 100-500 items perform better than 1,000
2. **Parallelize batches** - Process multiple batches concurrently (respect rate limits)
3. **Optimize queries** - Ensure proper database indexes exist
4. **Monitor performance** - Track `execution_time_seconds` in audit logs

### Expected Performance

| Items | Avg Time | Max Time |
|-------|----------|----------|
| 10 | < 1s | 2s |
| 100 | < 5s | 10s |
| 500 | < 20s | 40s |
| 1,000 | < 40s | 60s |

---

## Example: Complete Workflow

### Scenario: Approve 250 work orders with validation

```python
import requests

BASE_URL = 'https://api.example.com'
AUTH_TOKEN = 'your-jwt-token'

headers = {
    'Authorization': f'Bearer {AUTH_TOKEN}',
    'Content-Type': 'application/json'
}

# Step 1: Dry-run to validate
dry_run_response = requests.post(
    f'{BASE_URL}/api/v1/work-orders/bulk/approve',
    json={
        'ids': work_order_ids,
        'comments': 'Q4 budget approval',
        'dry_run': True
    },
    headers=headers,
    timeout=(5, 30)
)

# Step 2: Check validation results
if dry_run_response.status_code == 200:
    data = dry_run_response.json()
    print(f"Validation passed: {data['successful_items']} items OK")

    if data['failed_items'] > 0:
        print(f"Validation failed for {data['failed_items']} items:")
        for entity_id, error in data['failure_details'].items():
            print(f"  - {entity_id}: {error}")
        # Handle validation errors
        exit(1)
else:
    print(f"Validation error: {dry_run_response.json()}")
    exit(1)

# Step 3: Execute actual bulk approval
actual_response = requests.post(
    f'{BASE_URL}/api/v1/work-orders/bulk/approve',
    json={
        'ids': work_order_ids,
        'comments': 'Q4 budget approval',
        'dry_run': False,
        'rollback_on_error': True
    },
    headers=headers,
    timeout=(5, 60)
)

# Step 4: Handle results
if actual_response.status_code == 200:
    data = actual_response.json()
    print(f"Success! Approved {data['successful_items']} work orders")
    print(f"Audit correlation ID: {data['audit_correlation_id']}")

    if data['failed_items'] > 0:
        print(f"Failed to approve {data['failed_items']} items:")
        for entity_id, error in data['failure_details'].items():
            print(f"  - {entity_id}: {error}")
else:
    print(f"Error: {actual_response.status_code}")
    print(actual_response.json())
```

---

## Support

For issues or questions about the Bulk Operations API:

1. **Documentation**: Check this guide and inline API docs
2. **Audit Logs**: Query using `correlation_id` for debugging
3. **Support Team**: Contact api-support@example.com
4. **Status Page**: https://status.example.com

**API Version:** v1
**Last Updated:** October 2025
**Changelog:** See [API_CHANGELOG.md](./API_CHANGELOG.md)
