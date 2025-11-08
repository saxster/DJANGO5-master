# API Contract: Operations Domain

> **Domain:** Operations Management (Jobs, Tours, Tasks, PPM, Questions)
> **Version:** 1.0.0
> **Last Updated:** November 7, 2025
> **Base URL:** `/api/v2/operations/`

---

## 📋 Table of Contents

- [Overview](#overview)
- [Jobs Management](#jobs-management)
- [Tours Management](#tours-management)
- [Tasks & PPM](#tasks--ppm)
- [Questions & Forms](#questions--forms)
- [Asset Management](#asset-management)
- [Common Patterns](#common-patterns)
- [Complete Workflows](#complete-workflows)
- [Error Scenarios](#error-scenarios)

---

## Overview

The Operations domain handles field work management including:
- **Jobs**: Work orders with assets, locations, questions, and approvals
- **Tours**: Route-based inspections with optimized scheduling
- **Tasks**: Individual work items with dependencies
- **PPM**: Preventive/Predictive Maintenance schedules
- **Questions**: Dynamic forms with conditional logic

### Domain Principles

1. **State Machines**: Jobs/tasks follow strict state transitions
2. **Optimistic Locking**: Version field prevents concurrent update conflicts
3. **Offline First**: All operations support offline queue
4. **Asset Linking**: Jobs reference equipment, locations, meters
5. **Approval Workflows**: Multi-level approvals with audit trail

### Django Implementation

- **Models:** `apps/activity/models/job/job.py`
- **Viewsets:** `apps/activity/api/viewsets/`
- **Serializers:** `apps/activity/serializers.py`
- **Permissions:** `apps/activity/permissions.py`

---

## Jobs Management

### Job State Machine

```
draft → scheduled → in_progress → pending_approval → approved → completed
                  ↓
               cancelled (from any state)
```

**State Transitions:**
- `draft` → `scheduled`: Assign resources and time
- `scheduled` → `in_progress`: Worker starts job
- `in_progress` → `pending_approval`: Worker submits
- `pending_approval` → `approved`: Supervisor approves
- `approved` → `completed`: System marks complete
- `any` → `cancelled`: Cancel with reason

---

### 1. Create Job

**Endpoint:** `POST /api/v2/operations/jobs/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.create()`
- **Serializer:** `apps/activity/serializers.py:JobCreateSerializer`
- **Model:** `apps/activity/models/job/job.py:Job`
- **Permissions:** `IsAuthenticated`, `CanCreateJob`

**Purpose:** Create a new job with location, assets, and questions

**Request:**
```json
{
  "title": "Monthly HVAC Inspection",
  "description": "Regular maintenance check for cooling system",
  "job_type": "preventive_maintenance",
  "priority": "medium",
  "scheduled_start": "2025-11-15T09:00:00Z",
  "scheduled_end": "2025-11-15T11:00:00Z",
  "assigned_to": [123, 456],
  "location": {
    "site_id": 789,
    "latitude": 1.290270,
    "longitude": 103.851959,
    "address": "123 Main St, Singapore"
  },
  "assets": [
    {
      "asset_id": 101,
      "asset_type": "hvac_unit",
      "asset_name": "HVAC-01-Floor2"
    }
  ],
  "questions": [12, 15, 18],
  "attachments": [
    {
      "filename": "inspection_checklist.pdf",
      "file_url": "https://storage/files/abc123.pdf",
      "file_type": "application/pdf"
    }
  ],
  "tags": ["hvac", "maintenance", "monthly"],
  "custom_fields": {
    "building": "Tower A",
    "floor": 2,
    "equipment_serial": "HVAC-2024-001"
  }
}
```

**Field Validation:**
- `title`: Required, 3-200 characters
- `job_type`: Required, enum: `corrective|preventive_maintenance|inspection|installation|emergency`
- `priority`: Required, enum: `low|medium|high|urgent`
- `scheduled_start`: Required, ISO 8601 UTC, must be future
- `scheduled_end`: Optional, must be after scheduled_start
- `assigned_to`: Required, array of People IDs (must exist and be active)
- `location.site_id`: Required, BusinessUnit ID (must exist)
- `location.latitude/longitude`: Optional, decimal degrees (-90 to 90, -180 to 180)
- `assets`: Optional array, each asset_id must exist
- `questions`: Optional array of Question IDs (must exist and be active)

**Response (201 Created):**
```json
{
  "id": 5001,
  "job_number": "JOB-2025-11-5001",
  "title": "Monthly HVAC Inspection",
  "description": "Regular maintenance check for cooling system",
  "job_type": "preventive_maintenance",
  "priority": "medium",
  "status": "draft",
  "scheduled_start": "2025-11-15T09:00:00Z",
  "scheduled_end": "2025-11-15T11:00:00Z",
  "actual_start": null,
  "actual_end": null,
  "assigned_to": [
    {
      "id": 123,
      "name": "John Doe",
      "avatar_url": "https://storage/avatars/123.jpg"
    },
    {
      "id": 456,
      "name": "Jane Smith",
      "avatar_url": "https://storage/avatars/456.jpg"
    }
  ],
  "location": {
    "site_id": 789,
    "site_name": "Downtown Office",
    "latitude": 1.290270,
    "longitude": 103.851959,
    "address": "123 Main St, Singapore"
  },
  "assets": [
    {
      "id": 101,
      "asset_number": "ASSET-101",
      "asset_type": "hvac_unit",
      "asset_name": "HVAC-01-Floor2",
      "status": "operational"
    }
  ],
  "questions": [
    {
      "id": 12,
      "question_text": "Is the air filter clean?",
      "question_type": "yes_no",
      "required": true,
      "order": 1
    },
    {
      "id": 15,
      "question_text": "Temperature reading (°C)",
      "question_type": "number",
      "required": true,
      "order": 2,
      "validation": {
        "min": 15,
        "max": 30
      }
    }
  ],
  "attachments": [
    {
      "id": 9001,
      "filename": "inspection_checklist.pdf",
      "file_url": "https://storage/files/abc123.pdf",
      "file_type": "application/pdf",
      "file_size": 245678,
      "uploaded_at": "2025-11-07T10:00:00Z"
    }
  ],
  "tags": ["hvac", "maintenance", "monthly"],
  "custom_fields": {
    "building": "Tower A",
    "floor": 2,
    "equipment_serial": "HVAC-2024-001"
  },
  "version": 1,
  "created_at": "2025-11-07T10:00:00Z",
  "created_by": {
    "id": 999,
    "name": "Admin User"
  },
  "updated_at": "2025-11-07T10:00:00Z",
  "correlation_id": "req-abc123-def456"
}
```

**Error Responses:**

**400 Bad Request** - Validation error:
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "field_errors": [
    {
      "field": "scheduled_start",
      "error": "must_be_future_date",
      "message": "Scheduled start must be in the future"
    },
    {
      "field": "assigned_to[0]",
      "error": "user_not_found",
      "message": "User ID 123 does not exist"
    }
  ],
  "correlation_id": "req-abc123-def456"
}
```

**403 Forbidden** - Permission denied:
```json
{
  "error_code": "PERMISSION_DENIED",
  "message": "You do not have permission to create jobs",
  "required_permission": "activity.add_job",
  "correlation_id": "req-abc123-def456"
}
```

---

### 2. List Jobs

**Endpoint:** `GET /api/v2/operations/jobs/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.list()`
- **Serializer:** `apps/activity/serializers.py:JobListSerializer`
- **Permissions:** `IsAuthenticated`, `CanViewJob`

**Purpose:** Get paginated list of jobs with filters and search

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)
- `status`: Filter by status (comma-separated): `draft,scheduled,in_progress`
- `priority`: Filter by priority: `low,medium,high,urgent`
- `job_type`: Filter by type: `corrective,preventive_maintenance,inspection`
- `assigned_to`: Filter by assignee ID (comma-separated): `123,456`
- `site_id`: Filter by site/location
- `scheduled_after`: Filter jobs scheduled after date: `2025-11-01T00:00:00Z`
- `scheduled_before`: Filter jobs scheduled before date: `2025-11-30T23:59:59Z`
- `search`: Full-text search in title, description, job_number
- `tags`: Filter by tags (comma-separated): `hvac,maintenance`
- `ordering`: Sort field: `scheduled_start,-priority,created_at` (prefix `-` for descending)

**Request:**
```
GET /api/v2/operations/jobs/?status=scheduled,in_progress&priority=high,urgent&page=1&page_size=20&ordering=-priority,scheduled_start
```

**Response (200 OK):**
```json
{
  "count": 47,
  "next": "https://api.example.com/api/v2/operations/jobs/?page=2&status=scheduled,in_progress",
  "previous": null,
  "page_size": 20,
  "current_page": 1,
  "total_pages": 3,
  "results": [
    {
      "id": 5001,
      "job_number": "JOB-2025-11-5001",
      "title": "Emergency Repair - Water Leak",
      "description": "Urgent water pipe repair on Floor 5",
      "job_type": "corrective",
      "priority": "urgent",
      "status": "in_progress",
      "scheduled_start": "2025-11-15T09:00:00Z",
      "scheduled_end": "2025-11-15T11:00:00Z",
      "actual_start": "2025-11-15T09:05:00Z",
      "actual_end": null,
      "assigned_to": [
        {
          "id": 123,
          "name": "John Doe",
          "avatar_url": "https://storage/avatars/123.jpg"
        }
      ],
      "location": {
        "site_id": 789,
        "site_name": "Downtown Office",
        "latitude": 1.290270,
        "longitude": 103.851959
      },
      "asset_count": 1,
      "question_count": 5,
      "completion_percentage": 60,
      "tags": ["plumbing", "emergency", "water"],
      "version": 3,
      "created_at": "2025-11-15T08:00:00Z",
      "updated_at": "2025-11-15T09:05:00Z"
    },
    {
      "id": 5002,
      "job_number": "JOB-2025-11-5002",
      "title": "Fire Alarm System Test",
      "description": "Quarterly fire safety check",
      "job_type": "inspection",
      "priority": "high",
      "status": "scheduled",
      "scheduled_start": "2025-11-16T10:00:00Z",
      "scheduled_end": "2025-11-16T12:00:00Z",
      "actual_start": null,
      "actual_end": null,
      "assigned_to": [
        {
          "id": 456,
          "name": "Jane Smith",
          "avatar_url": "https://storage/avatars/456.jpg"
        }
      ],
      "location": {
        "site_id": 790,
        "site_name": "North Campus",
        "latitude": 1.350000,
        "longitude": 103.900000
      },
      "asset_count": 3,
      "question_count": 8,
      "completion_percentage": 0,
      "tags": ["fire_safety", "inspection", "quarterly"],
      "version": 1,
      "created_at": "2025-11-10T14:00:00Z",
      "updated_at": "2025-11-10T14:00:00Z"
    }
  ]
}
```

---

### 3. Get Job Details

**Endpoint:** `GET /api/v2/operations/jobs/{id}/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.retrieve()`
- **Serializer:** `apps/activity/serializers.py:JobDetailSerializer`
- **Permissions:** `IsAuthenticated`, `CanViewJob`

**Purpose:** Get complete job details with nested data (assets, questions, answers, attachments)

**Request:**
```
GET /api/v2/operations/jobs/5001/
```

**Response (200 OK):**
```json
{
  "id": 5001,
  "job_number": "JOB-2025-11-5001",
  "title": "Monthly HVAC Inspection",
  "description": "Regular maintenance check for cooling system",
  "job_type": "preventive_maintenance",
  "priority": "medium",
  "status": "in_progress",
  "scheduled_start": "2025-11-15T09:00:00Z",
  "scheduled_end": "2025-11-15T11:00:00Z",
  "actual_start": "2025-11-15T09:10:00Z",
  "actual_end": null,
  "assigned_to": [
    {
      "id": 123,
      "name": "John Doe",
      "email": "john.doe@example.com",
      "phone": "+65 9123 4567",
      "avatar_url": "https://storage/avatars/123.jpg",
      "role": "technician"
    },
    {
      "id": 456,
      "name": "Jane Smith",
      "email": "jane.smith@example.com",
      "phone": "+65 9234 5678",
      "avatar_url": "https://storage/avatars/456.jpg",
      "role": "supervisor"
    }
  ],
  "location": {
    "site_id": 789,
    "site_name": "Downtown Office",
    "latitude": 1.290270,
    "longitude": 103.851959,
    "address": "123 Main St, #05-01, Singapore 123456",
    "postal_code": "123456",
    "site_type": "commercial_building"
  },
  "assets": [
    {
      "id": 101,
      "asset_number": "ASSET-101",
      "asset_type": "hvac_unit",
      "asset_name": "HVAC-01-Floor2",
      "status": "operational",
      "manufacturer": "Daikin",
      "model": "VRV-IV",
      "serial_number": "HVAC-2024-001",
      "installation_date": "2024-01-15",
      "last_maintenance": "2025-10-15T10:00:00Z",
      "qr_code": "ASSET-101-QR",
      "location_details": {
        "building": "Tower A",
        "floor": 2,
        "room": "Server Room"
      }
    }
  ],
  "questions": [
    {
      "id": 12,
      "question_text": "Is the air filter clean?",
      "question_type": "yes_no",
      "required": true,
      "order": 1,
      "options": null,
      "validation": null,
      "answer": {
        "answer_id": 9001,
        "value": "yes",
        "answered_at": "2025-11-15T09:30:00Z",
        "answered_by": {
          "id": 123,
          "name": "John Doe"
        },
        "photo_url": "https://storage/photos/filter-check-9001.jpg"
      }
    },
    {
      "id": 15,
      "question_text": "Temperature reading (°C)",
      "question_type": "number",
      "required": true,
      "order": 2,
      "options": null,
      "validation": {
        "min": 15,
        "max": 30,
        "decimal_places": 1
      },
      "answer": {
        "answer_id": 9002,
        "value": "22.5",
        "answered_at": "2025-11-15T09:35:00Z",
        "answered_by": {
          "id": 123,
          "name": "John Doe"
        },
        "photo_url": null
      }
    },
    {
      "id": 18,
      "question_text": "Any abnormal noises detected?",
      "question_type": "multiple_choice",
      "required": false,
      "order": 3,
      "options": [
        {"id": 1, "text": "None"},
        {"id": 2, "text": "Rattling"},
        {"id": 3, "text": "Buzzing"},
        {"id": 4, "text": "Grinding"},
        {"id": 5, "text": "Other"}
      ],
      "validation": null,
      "answer": null
    }
  ],
  "attachments": [
    {
      "id": 9001,
      "filename": "inspection_checklist.pdf",
      "file_url": "https://storage/files/abc123.pdf",
      "file_type": "application/pdf",
      "file_size": 245678,
      "uploaded_at": "2025-11-07T10:00:00Z",
      "uploaded_by": {
        "id": 999,
        "name": "Admin User"
      }
    },
    {
      "id": 9002,
      "filename": "before_photo.jpg",
      "file_url": "https://storage/photos/job-5001-before.jpg",
      "file_type": "image/jpeg",
      "file_size": 1234567,
      "uploaded_at": "2025-11-15T09:15:00Z",
      "uploaded_by": {
        "id": 123,
        "name": "John Doe"
      }
    }
  ],
  "tags": ["hvac", "maintenance", "monthly"],
  "custom_fields": {
    "building": "Tower A",
    "floor": 2,
    "equipment_serial": "HVAC-2024-001",
    "maintenance_contract": "MC-2025-001"
  },
  "completion_percentage": 66,
  "estimated_duration_minutes": 120,
  "actual_duration_minutes": null,
  "approval_workflow": {
    "required": true,
    "approver": {
      "id": 789,
      "name": "Supervisor Smith",
      "role": "supervisor"
    },
    "status": "pending",
    "submitted_at": null,
    "approved_at": null
  },
  "version": 5,
  "created_at": "2025-11-07T10:00:00Z",
  "created_by": {
    "id": 999,
    "name": "Admin User"
  },
  "updated_at": "2025-11-15T09:35:00Z",
  "updated_by": {
    "id": 123,
    "name": "John Doe"
  },
  "correlation_id": "req-xyz789-abc123"
}
```

**Error Responses:**

**404 Not Found** - Job doesn't exist:
```json
{
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Job with ID 5001 not found",
  "resource_type": "job",
  "resource_id": "5001",
  "correlation_id": "req-xyz789-abc123"
}
```

---

### 4. Update Job

**Endpoint:** `PATCH /api/v2/operations/jobs/{id}/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.partial_update()`
- **Serializer:** `apps/activity/serializers.py:JobUpdateSerializer`
- **Permissions:** `IsAuthenticated`, `CanUpdateJob`

**Purpose:** Update job fields (partial update supported)

**Request:**
```json
{
  "title": "Monthly HVAC Inspection - Updated",
  "priority": "high",
  "scheduled_start": "2025-11-15T08:00:00Z",
  "assigned_to": [123, 456, 789],
  "version": 5
}
```

**Field Notes:**
- `version`: Required for optimistic locking (must match current version)
- Only changed fields need to be included (partial update)
- Status cannot be changed via PATCH (use state transition endpoints)

**Response (200 OK):**
```json
{
  "id": 5001,
  "title": "Monthly HVAC Inspection - Updated",
  "priority": "high",
  "scheduled_start": "2025-11-15T08:00:00Z",
  "assigned_to": [
    {"id": 123, "name": "John Doe"},
    {"id": 456, "name": "Jane Smith"},
    {"id": 789, "name": "Mike Johnson"}
  ],
  "version": 6,
  "updated_at": "2025-11-15T10:00:00Z",
  "updated_by": {
    "id": 123,
    "name": "John Doe"
  },
  "correlation_id": "req-update-123"
}
```

**Error Responses:**

**409 Conflict** - Version mismatch:
```json
{
  "error_code": "VERSION_CONFLICT",
  "message": "Job has been updated by another user",
  "current_version": 6,
  "requested_version": 5,
  "updated_by": {
    "id": 456,
    "name": "Jane Smith"
  },
  "updated_at": "2025-11-15T09:55:00Z",
  "correlation_id": "req-update-123"
}
```

---

### 5. Start Job

**Endpoint:** `POST /api/v2/operations/jobs/{id}/start/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.start()`
- **Permissions:** `IsAuthenticated`, `CanStartJob`

**Purpose:** Transition job from `scheduled` to `in_progress`

**Request:**
```json
{
  "actual_start": "2025-11-15T09:10:00Z",
  "gps_location": {
    "latitude": 1.290270,
    "longitude": 103.851959,
    "accuracy_meters": 10
  },
  "device_info": {
    "device_id": "device-abc123",
    "app_version": "2.1.0",
    "os": "Android 14"
  },
  "version": 5
}
```

**Response (200 OK):**
```json
{
  "id": 5001,
  "status": "in_progress",
  "actual_start": "2025-11-15T09:10:00Z",
  "gps_verified": true,
  "distance_from_site_meters": 8.5,
  "version": 6,
  "updated_at": "2025-11-15T09:10:00Z",
  "correlation_id": "req-start-789"
}
```

**Error Responses:**

**400 Bad Request** - Invalid state transition:
```json
{
  "error_code": "INVALID_STATE_TRANSITION",
  "message": "Cannot start job in current state",
  "current_status": "in_progress",
  "requested_status": "in_progress",
  "allowed_transitions": ["pending_approval", "cancelled"],
  "correlation_id": "req-start-789"
}
```

**400 Bad Request** - GPS validation failed:
```json
{
  "error_code": "GPS_VALIDATION_FAILED",
  "message": "Location is too far from job site",
  "distance_meters": 152.3,
  "max_allowed_meters": 100,
  "gps_accuracy_meters": 10,
  "correlation_id": "req-start-789"
}
```

---

### 6. Complete Job

**Endpoint:** `POST /api/v2/operations/jobs/{id}/complete/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.complete()`
- **Permissions:** `IsAuthenticated`, `CanCompleteJob`

**Purpose:** Mark job complete (transitions to `pending_approval` if approval required, else `completed`)

**Request:**
```json
{
  "actual_end": "2025-11-15T11:05:00Z",
  "completion_notes": "All tasks completed successfully. Filter replaced, temperature normal.",
  "photos": [
    {
      "photo_url": "https://storage/photos/job-5001-after.jpg",
      "caption": "After maintenance - clean filter"
    }
  ],
  "signature": {
    "technician_signature": "data:image/png;base64,iVBORw0KG...",
    "signed_at": "2025-11-15T11:05:00Z"
  },
  "version": 6
}
```

**Response (200 OK):**
```json
{
  "id": 5001,
  "status": "pending_approval",
  "actual_end": "2025-11-15T11:05:00Z",
  "completion_percentage": 100,
  "actual_duration_minutes": 115,
  "requires_approval": true,
  "approver": {
    "id": 789,
    "name": "Supervisor Smith"
  },
  "version": 7,
  "updated_at": "2025-11-15T11:05:00Z",
  "correlation_id": "req-complete-456"
}
```

---

### 7. Submit for Approval

**Endpoint:** `POST /api/v2/operations/jobs/{id}/submit/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.submit()`
- **Permissions:** `IsAuthenticated`, `CanSubmitJob`

**Purpose:** Submit completed job for supervisor approval

**Request:**
```json
{
  "approver_id": 789,
  "submission_notes": "All checklist items completed, ready for review",
  "version": 7
}
```

**Response (200 OK):**
```json
{
  "id": 5001,
  "status": "pending_approval",
  "submitted_at": "2025-11-15T11:10:00Z",
  "submitted_by": {
    "id": 123,
    "name": "John Doe"
  },
  "approver": {
    "id": 789,
    "name": "Supervisor Smith",
    "email": "supervisor@example.com"
  },
  "version": 8,
  "correlation_id": "req-submit-111"
}
```

---

### 8. Get Job History

**Endpoint:** `GET /api/v2/operations/jobs/{id}/history/`

**Django Implementation:**
- **Viewset:** `apps/activity/api/viewsets/job_viewset.py:JobViewSet.history()`
- **Permissions:** `IsAuthenticated`, `CanViewJob`

**Purpose:** Get complete audit trail of job changes

**Response (200 OK):**
```json
{
  "job_id": 5001,
  "job_number": "JOB-2025-11-5001",
  "history": [
    {
      "timestamp": "2025-11-07T10:00:00Z",
      "action": "created",
      "user": {
        "id": 999,
        "name": "Admin User"
      },
      "changes": {
        "status": {"old": null, "new": "draft"}
      },
      "version": 1
    },
    {
      "timestamp": "2025-11-15T09:10:00Z",
      "action": "started",
      "user": {
        "id": 123,
        "name": "John Doe"
      },
      "changes": {
        "status": {"old": "scheduled", "new": "in_progress"},
        "actual_start": {"old": null, "new": "2025-11-15T09:10:00Z"}
      },
      "gps_location": {
        "latitude": 1.290270,
        "longitude": 103.851959,
        "accuracy_meters": 10
      },
      "version": 6
    },
    {
      "timestamp": "2025-11-15T11:05:00Z",
      "action": "completed",
      "user": {
        "id": 123,
        "name": "John Doe"
      },
      "changes": {
        "status": {"old": "in_progress", "new": "pending_approval"},
        "actual_end": {"old": null, "new": "2025-11-15T11:05:00Z"},
        "completion_percentage": {"old": 66, "new": 100}
      },
      "version": 7
    }
  ],
  "correlation_id": "req-history-999"
}
```

---

## Tours Management

### Tour Endpoints

1. **`GET /api/v2/operations/tours/`** - List tours with route optimization
2. **`POST /api/v2/operations/tours/`** - Create tour with stops
3. **`GET /api/v2/operations/tours/{id}/`** - Get tour details
4. **`PATCH /api/v2/operations/tours/{id}/`** - Update tour
5. **`POST /api/v2/operations/tours/{id}/optimize-route/`** - Optimize stop sequence
6. **`GET /api/v2/operations/tours/{id}/progress/`** - Real-time tour progress

*(Full tour documentation similar to jobs - omitted for brevity)*

---

## Tasks & PPM

### Task Endpoints

1. **`GET /api/v2/operations/tasks/`** - List tasks
2. **`POST /api/v2/operations/tasks/`** - Create task
3. **`GET /api/v2/operations/tasks/{id}/`** - Get task details
4. **`POST /api/v2/operations/ppm/schedules/`** - Create PPM schedule
5. **`GET /api/v2/operations/ppm/upcoming/`** - Get upcoming maintenance

*(Full task/PPM documentation - omitted for brevity)*

---

## Questions & Forms

### Question Endpoints

1. **`GET /api/v2/operations/questions/`** - List questions
2. **`GET /api/v2/operations/questions/{id}/`** - Get question details with conditional logic
3. **`POST /api/v2/operations/answers/`** - Submit answer
4. **`GET /api/v2/operations/forms/`** - Get complete forms/checklists

*(Full questions documentation - omitted for brevity)*

---

## Complete Workflows

### Workflow 1: Create → Execute → Complete Job

```
1. Create Job
   POST /api/v2/operations/jobs/
   → Status: draft
   → Job ID: 5001

2. Schedule Job (update)
   PATCH /api/v2/operations/jobs/5001/
   → Status: scheduled
   → Assigned workers notified

3. Worker arrives at site, starts job
   POST /api/v2/operations/jobs/5001/start/
   → GPS validated
   → Status: in_progress
   → Clock started

4. Worker answers questions
   POST /api/v2/operations/answers/ (for each question)
   → Completion % increases

5. Worker completes job
   POST /api/v2/operations/jobs/5001/complete/
   → Status: pending_approval
   → Supervisor notified

6. Supervisor approves
   POST /api/v2/operations/jobs/5001/approve/
   → Status: approved → completed
   → Job archived
```

---

## Error Scenarios

### Common Errors

**Validation Errors:**
- Missing required fields
- Invalid enum values
- Date/time validation failures
- Asset/user not found

**State Transition Errors:**
- Invalid status change
- Missing prerequisites (e.g., can't complete without answers)

**Concurrency Errors:**
- Version conflict (optimistic locking)
- Job already started by another user

**Permission Errors:**
- User lacks required capability
- Cross-tenant access attempt

---

## Offline Support

### Offline Queue Pattern

1. **Create job offline:**
   - Generate temp ID: `temp-job-{uuid}`
   - Store in pending queue with `mobile_id`
   - Show as "Pending Sync" in UI

2. **Sync when online:**
   - WebSocket sends `SyncDataMessage`
   - Server creates job, returns real ID
   - Mobile updates temp ID → real ID
   - Update all references

3. **Conflict resolution:**
   - If server has newer version, prompt user
   - Show diff between local and server
   - User chooses: keep local, accept server, or merge

---

## Data Model Summary

```typescript
interface Job {
  id: number
  job_number: string
  title: string
  description: string
  job_type: JobType
  priority: Priority
  status: JobStatus
  scheduled_start: string // ISO 8601
  scheduled_end: string | null
  actual_start: string | null
  actual_end: string | null
  assigned_to: User[]
  location: Location
  assets: Asset[]
  questions: Question[]
  attachments: Attachment[]
  tags: string[]
  custom_fields: Record<string, any>
  completion_percentage: number
  approval_workflow: ApprovalWorkflow | null
  version: number
  created_at: string
  created_by: User
  updated_at: string
  updated_by: User
}

enum JobType {
  CORRECTIVE = "corrective"
  PREVENTIVE_MAINTENANCE = "preventive_maintenance"
  INSPECTION = "inspection"
  INSTALLATION = "installation"
  EMERGENCY = "emergency"
}

enum JobStatus {
  DRAFT = "draft"
  SCHEDULED = "scheduled"
  IN_PROGRESS = "in_progress"
  PENDING_APPROVAL = "pending_approval"
  APPROVED = "approved"
  COMPLETED = "completed"
  CANCELLED = "cancelled"
}

enum Priority {
  LOW = "low"
  MEDIUM = "medium"
  HIGH = "high"
  URGENT = "urgent"
}
```

---

## Testing Checklist

- [ ] Create job with all fields
- [ ] Create job with minimal fields
- [ ] List jobs with various filters
- [ ] Update job with version check
- [ ] Start job with GPS validation
- [ ] Complete job with questions
- [ ] Submit for approval
- [ ] Handle version conflicts
- [ ] Offline job creation
- [ ] Sync offline → online
- [ ] State transition validations
- [ ] Permission checks
- [ ] Cross-tenant isolation

---

**Document Version:** 1.0.0
**Last Updated:** November 7, 2025
**Next Review:** December 7, 2025
