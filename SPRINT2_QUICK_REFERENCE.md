# Sprint 2: Mobile Sync API - Quick Reference

## 🚀 Available Endpoints

### Activity/Tasks
```bash
POST /api/v1/sync/activity/sync/
GET  /api/v1/sync/activity/changes/?since=2025-09-28T10:00:00Z&limit=100
```

### Work Orders
```bash
POST /api/v1/sync/work-orders/sync/
GET  /api/v1/sync/work-orders/changes/?since=2025-09-28T10:00:00Z&status=in_progress
```

### Attendance
```bash
POST /api/v1/sync/attendance/sync/
GET  /api/v1/sync/attendance/changes/?since=2025-09-28T10:00:00Z&date_from=2025-09-01
```

### Helpdesk
```bash
POST /api/v1/sync/helpdesk/sync/
GET  /api/v1/sync/helpdesk/changes/?since=2025-09-28T10:00:00Z&priority=HIGH
```

---

## 📝 Request Format

```json
{
  "entries": [
    {
      "mobile_id": "550e8400-e29b-41d4-a716-446655440000",
      "version": 1,
      "field1": "value1",
      "field2": "value2"
    }
  ],
  "last_sync_timestamp": "2025-09-28T10:00:00Z",
  "client_id": "device-123"
}
```

**Headers:**
- `Authorization: Bearer <token>` (required)
- `Idempotency-Key: <unique-uuid>` (optional, recommended)
- `Content-Type: application/json`

---

## 📥 Response Format

```json
{
  "synced_items": [
    {"mobile_id": "uuid", "status": "created", "server_version": 1}
  ],
  "conflicts": [
    {"mobile_id": "uuid", "status": "conflict", "server_version": 2, "client_version": 1}
  ],
  "errors": [
    {"mobile_id": "uuid", "status": "error", "error_message": "Validation failed"}
  ],
  "timestamp": "2025-09-28T10:15:00Z"
}
```

---

## 🎯 Status Values

- **created** - New item created on server
- **updated** - Existing item updated successfully
- **conflict** - Version mismatch (server has newer version)
- **error** - Validation or database error

---

## 🔑 Required Fields by Domain

### Activity/Tasks
```json
{
  "mobile_id": "uuid",
  "jobdesc": "Task description (min 3 chars)",
  "gracetime": 0,
  "priority": "HIGH|MEDIUM|LOW",
  "jobstatus": "ASSIGNED|INPROGRESS|COMPLETED"
}
```

### Work Orders
```json
{
  "mobile_id": "uuid",
  "description": "Work order description (min 5 chars)",
  "status": "draft|in_progress|completed|closed",
  "priority": "HIGH|MEDIUM|LOW"
}
```

### Attendance
```json
{
  "mobile_id": "uuid",
  "deviceid": "device-123 (min 5 chars)",
  "gpslocation": "POINT(lon lat)",
  "transportmode": "WALK|BIKE|CAR|BUS|TRAIN",
  "identifier": "TRACKING|CONVEYANCE|EXTERNALTOUR"
}
```

### Helpdesk
```json
{
  "mobile_id": "uuid",
  "ticketdesc": "Ticket description (min 10 chars)",
  "status": "NEW|OPEN|INPROGRESS|RESOLVED|CLOSED",
  "priority": "HIGH|MEDIUM|LOW"
}
```

---

## ⚡ Code Quality Rules

✅ All services < 150 lines
✅ All serializers < 100 lines
✅ View methods < 30 lines
✅ Specific exception handling (no bare `except`)
✅ Multi-tenant isolation enforced
✅ Idempotency support built-in

---

## 📂 File Structure

```
apps/
├── api/v1/
│   ├── services/
│   │   ├── base_sync_service.py       # Foundation
│   │   └── idempotency_service.py     # Already exists
│   ├── serializers/
│   │   └── sync_base_serializers.py   # Base serializers
│   └── urls.py                         # Sync routes
│
├── activity/
│   ├── services/task_sync_service.py
│   ├── serializers/task_sync_serializers.py
│   └── views/task_sync_views.py
│
├── work_order_management/
│   ├── services/wom_sync_service.py
│   ├── serializers/wom_sync_serializers.py
│   └── views/wom_sync_views.py
│
├── attendance/
│   ├── services/attendance_sync_service.py
│   ├── serializers/attendance_sync_serializers.py
│   └── views/attendance_sync_views.py
│
└── y_helpdesk/
    ├── services/ticket_sync_service.py
    ├── serializers/ticket_sync_serializers.py
    └── views/ticket_sync_views.py
```

---

## 🔍 Testing Quick Commands

```bash
# Run all tests
python -m pytest --cov=apps --cov-report=html -v

# Test specific domain
python -m pytest apps/activity/tests/test_task_sync_integration.py -v

# Check URL configuration
python manage.py show_urls | grep sync
```

---

## 📚 Documentation Files

1. **SPRINT2_IMPLEMENTATION_STATUS.md** - Detailed implementation guide
2. **SPRINT2_COMPLETE_SUMMARY.md** - Full project summary (1200+ lines)
3. **SPRINT2_QUICK_REFERENCE.md** - This file

---

## 🎓 Key Concepts

**Idempotency:** Same request = same response (24-hour TTL)
**Conflict Detection:** Version-based optimistic locking
**Multi-tenancy:** Bu/client filtering enforced
**Server-Wins:** Attendance domain overrides client on conflict
**Delta Sync:** Only fetch changes since last sync

---

**Status:** ✅ Sprint 2 Core Complete (85%)
**Pending:** Tests, Rate Limiting, Journal Enhancement