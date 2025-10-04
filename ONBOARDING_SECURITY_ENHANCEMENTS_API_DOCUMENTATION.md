# Onboarding Security Enhancements - API Documentation

**Version:** 1.0
**Date:** 2025-10-01
**Base URL:** `https://your-domain.com/api/v1/onboarding`

---

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limiting](#rate-limiting)
3. [Error Handling](#error-handling)
4. [DLQ Admin API](#dlq-admin-api)
5. [Funnel Analytics API](#funnel-analytics-api)
6. [Session Recovery API](#session-recovery-api)
7. [Analytics Dashboard API](#analytics-dashboard-api)
8. [Code Examples](#code-examples)
9. [Postman Collection](#postman-collection)

---

## Authentication

All API endpoints require authentication using JWT Bearer tokens or API keys.

### JWT Authentication (Recommended)

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### API Key Authentication

```http
X-API-Key: your-api-key-here
```

### Obtaining a JWT Token

```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "your_username",
    "is_staff": true
  }
}
```

### Permission Levels

| Permission | Required For | Endpoints |
|------------|--------------|-----------|
| `IsAuthenticated` | All users | Session recovery, session replay |
| `IsAdminUser` | Staff only | DLQ admin, funnel analytics, dashboard overview |
| `IsSuperUser` | Superusers only | DLQ clear, system configuration |

---

## Rate Limiting

### Global Rate Limits

- **Standard users:** 100 requests per 5 minutes per endpoint
- **Staff users:** 500 requests per 5 minutes per endpoint
- **Critical resources (LLM, translations):** 50 requests per hour per user

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1633024800
Retry-After: 300
```

### Rate Limit Errors

**HTTP 429 - Too Many Requests:**
```json
{
  "error": "rate_limit_exceeded",
  "detail": "Rate limit exceeded for resource 'llm_calls'",
  "retry_after": 300,
  "limit_info": {
    "limit": 50,
    "remaining": 0,
    "reset_time": "2025-10-01T10:35:00Z"
  }
}
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "error": "error_code",
  "detail": "Human-readable error message",
  "field_errors": {
    "field_name": ["Error message for this field"]
  },
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Request completed successfully |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid parameters or validation errors |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource does not exist |
| 409 | Conflict | Duplicate resource or race condition |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error (check correlation_id) |
| 503 | Service Unavailable | Circuit breaker open or maintenance mode |

---

## DLQ Admin API

Manage failed background tasks in the Dead Letter Queue.

### Base Path

`/api/v1/onboarding/admin/dlq/`

**Required Permission:** `IsAdminUser`

---

### 1. List Failed Tasks

**Endpoint:** `GET /admin/dlq/tasks/`

**Description:** Retrieve paginated list of failed tasks in the DLQ.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | all | Filter by status: `pending`, `retrying`, `failed`, `abandoned` |
| `category` | string | No | all | Filter by category: `llm_api`, `network`, `database`, `validation` |
| `task_name` | string | No | - | Filter by specific task name |
| `correlation_id` | string | No | - | Search by correlation ID |
| `page` | integer | No | 1 | Page number |
| `page_size` | integer | No | 20 | Results per page |

**Example Request:**

```http
GET /api/v1/onboarding/admin/dlq/tasks/?status=pending&category=llm_api&page=1&page_size=20
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "count": 45,
  "next": "/api/v1/onboarding/admin/dlq/tasks/?page=2",
  "previous": null,
  "results": [
    {
      "task_id": "dlq_123456",
      "task_name": "process_conversation_step_v2",
      "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "pending",
      "category": "llm_api",
      "error_message": "OpenAI API rate limit exceeded",
      "retry_count": 3,
      "max_retries": 5,
      "created_at": "2025-10-01T10:30:00Z",
      "last_retry_at": "2025-10-01T10:35:00Z",
      "next_retry_at": "2025-10-01T10:45:00Z",
      "task_args": ["conv-uuid-123", "user input", {}],
      "task_kwargs": {"task_id": "correlation-id"}
    }
  ]
}
```

---

### 2. Get Task Details

**Endpoint:** `GET /admin/dlq/tasks/{task_id}/`

**Description:** Retrieve detailed information about a specific failed task.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | DLQ task identifier |

**Example Request:**

```http
GET /api/v1/onboarding/admin/dlq/tasks/dlq_123456/
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "task_id": "dlq_123456",
  "task_name": "process_conversation_step_v2",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "category": "llm_api",
  "error_message": "OpenAI API rate limit exceeded",
  "error_type": "RateLimitError",
  "traceback": "Traceback (most recent call last):\n  File ...",
  "retry_count": 3,
  "max_retries": 5,
  "created_at": "2025-10-01T10:30:00Z",
  "last_retry_at": "2025-10-01T10:35:00Z",
  "next_retry_at": "2025-10-01T10:45:00Z",
  "retry_history": [
    {
      "attempt": 1,
      "timestamp": "2025-10-01T10:30:00Z",
      "error": "Rate limit exceeded",
      "retry_after": 300
    },
    {
      "attempt": 2,
      "timestamp": "2025-10-01T10:32:30Z",
      "error": "Rate limit exceeded",
      "retry_after": 300
    }
  ],
  "task_args": ["conv-uuid-123", "user input", {}],
  "task_kwargs": {"task_id": "correlation-id"},
  "context": {
    "session_id": "conv-uuid-123",
    "user_id": 42,
    "client_id": 1
  }
}
```

---

### 3. Retry Failed Task

**Endpoint:** `POST /admin/dlq/tasks/{task_id}/retry/`

**Description:** Manually retry a failed task from the DLQ.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | DLQ task identifier |

**Request Body:**

```json
{
  "force": false,
  "override_args": null,
  "override_kwargs": null
}
```

**Body Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force` | boolean | No | false | Force retry even if max retries exceeded |
| `override_args` | array | No | null | Override task arguments (for manual fixing) |
| `override_kwargs` | object | No | null | Override task kwargs (for manual fixing) |

**Example Request:**

```http
POST /api/v1/onboarding/admin/dlq/tasks/dlq_123456/retry/
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "force": false
}
```

**Example Response:**

```json
{
  "status": "retrying",
  "message": "Task queued for retry",
  "task_id": "dlq_123456",
  "celery_task_id": "8f4e3d2c-1a9b-4c5d-8e7f-6a5b4c3d2e1f",
  "retry_count": 4,
  "max_retries": 5,
  "estimated_completion": "2025-10-01T10:50:00Z"
}
```

**Error Response (Max Retries Exceeded):**

```json
{
  "error": "max_retries_exceeded",
  "detail": "Task has exceeded maximum retry attempts (5). Use force=true to retry anyway.",
  "task_id": "dlq_123456",
  "retry_count": 5,
  "max_retries": 5
}
```

---

### 4. Delete Failed Task

**Endpoint:** `DELETE /admin/dlq/tasks/{task_id}/delete/`

**Description:** Remove a task from the DLQ permanently.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | string | Yes | DLQ task identifier |

**Example Request:**

```http
DELETE /api/v1/onboarding/admin/dlq/tasks/dlq_123456/delete/
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "status": "deleted",
  "message": "Task successfully removed from DLQ",
  "task_id": "dlq_123456",
  "deleted_at": "2025-10-01T11:00:00Z"
}
```

---

### 5. Get DLQ Statistics

**Endpoint:** `GET /admin/dlq/stats/`

**Description:** Retrieve aggregated statistics about the DLQ.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `time_range_hours` | integer | No | 24 | Time range for statistics |

**Example Request:**

```http
GET /api/v1/onboarding/admin/dlq/stats/?time_range_hours=24
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "total_failed_tasks": 45,
  "tasks_by_status": {
    "pending": 20,
    "retrying": 10,
    "failed": 15,
    "abandoned": 0
  },
  "tasks_by_category": {
    "llm_api": 25,
    "network": 10,
    "database": 5,
    "validation": 5
  },
  "tasks_by_name": {
    "process_conversation_step_v2": 30,
    "embed_knowledge_document": 10,
    "translate_conversation_step": 5
  },
  "retry_statistics": {
    "total_retries": 120,
    "successful_retries": 100,
    "failed_retries": 20,
    "success_rate": 0.833
  },
  "average_retry_count": 2.67,
  "oldest_task_age_hours": 12.5,
  "time_range": {
    "start": "2025-09-30T11:00:00Z",
    "end": "2025-10-01T11:00:00Z",
    "hours": 24
  },
  "last_updated": "2025-10-01T11:00:00Z"
}
```

---

### 6. Clear DLQ (Bulk Delete)

**Endpoint:** `DELETE /admin/dlq/clear/`

**Description:** Remove multiple tasks from the DLQ based on filters.

**⚠️ Warning:** This operation is irreversible. Use with caution.

**Request Body:**

```json
{
  "status": "abandoned",
  "category": null,
  "older_than_hours": 72,
  "confirm": true
}
```

**Body Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | null | Only clear tasks with this status |
| `category` | string | No | null | Only clear tasks in this category |
| `older_than_hours` | integer | No | null | Only clear tasks older than X hours |
| `confirm` | boolean | Yes | - | Must be `true` to proceed with deletion |

**Example Request:**

```http
DELETE /api/v1/onboarding/admin/dlq/clear/
Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "status": "abandoned",
  "older_than_hours": 168,
  "confirm": true
}
```

**Example Response:**

```json
{
  "status": "cleared",
  "message": "Successfully removed 15 tasks from DLQ",
  "deleted_count": 15,
  "filters_applied": {
    "status": "abandoned",
    "older_than_hours": 168
  },
  "cleared_at": "2025-10-01T11:00:00Z"
}
```

**Error Response (Missing Confirmation):**

```json
{
  "error": "confirmation_required",
  "detail": "Must set confirm=true to proceed with bulk deletion",
  "matching_tasks": 15
}
```

---

## Funnel Analytics API

Track and analyze conversion funnels for the onboarding flow.

### Base Path

`/api/v1/onboarding/analytics/`

**Required Permission:** `IsAdminUser`

---

### 1. Get Funnel Metrics

**Endpoint:** `GET /analytics/funnel/`

**Description:** Retrieve complete funnel metrics with conversion rates.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string (ISO 8601) | No | 30 days ago | Start of analysis period |
| `end_date` | string (ISO 8601) | No | now | End of analysis period |
| `client_id` | integer | No | null | Filter by specific client |
| `conversation_type` | string | No | null | Filter by type: `site_survey`, `business_unit_setup` |

**Example Request:**

```http
GET /api/v1/onboarding/analytics/funnel/?start_date=2025-09-01T00:00:00Z&end_date=2025-10-01T00:00:00Z&client_id=1
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "overall_conversion_rate": 0.7523,
  "total_sessions": 1250,
  "completed_sessions": 940,
  "abandoned_sessions": 310,
  "avg_completion_time_minutes": 18.5,
  "stages": [
    {
      "name": "Session Started",
      "session_states": ["STARTED", "INITIAL_PROMPT"],
      "count": 1250,
      "conversion_rate": 1.0,
      "drop_off_rate": 0.0,
      "avg_time_in_stage_minutes": 0.5
    },
    {
      "name": "Information Collection",
      "session_states": ["COLLECTING_INFO", "ASKING_QUESTIONS"],
      "count": 1100,
      "conversion_rate": 0.88,
      "drop_off_rate": 0.12,
      "avg_time_in_stage_minutes": 8.2
    },
    {
      "name": "Recommendation Review",
      "session_states": ["GENERATING_RECOMMENDATIONS", "AWAITING_APPROVAL"],
      "count": 1020,
      "conversion_rate": 0.816,
      "drop_off_rate": 0.073,
      "avg_time_in_stage_minutes": 5.3
    },
    {
      "name": "Approval Process",
      "session_states": ["PENDING_APPROVAL"],
      "count": 970,
      "conversion_rate": 0.776,
      "drop_off_rate": 0.049,
      "avg_time_in_stage_minutes": 3.0
    },
    {
      "name": "Completed",
      "session_states": ["COMPLETED"],
      "count": 940,
      "conversion_rate": 0.7523,
      "drop_off_rate": 0.031,
      "avg_time_in_stage_minutes": 1.5
    }
  ],
  "top_drop_off_points": [
    {
      "state": "COLLECTING_INFO",
      "count": 150,
      "percentage": 0.12,
      "reason": "User abandoned during question answering"
    },
    {
      "state": "GENERATING_RECOMMENDATIONS",
      "count": 80,
      "percentage": 0.064,
      "reason": "LLM processing timeout"
    },
    {
      "state": "AWAITING_APPROVAL",
      "count": 50,
      "percentage": 0.04,
      "reason": "User left before approving recommendations"
    }
  ],
  "recommendations": [
    {
      "priority": "high",
      "recommendation": "Reduce question count in COLLECTING_INFO stage to improve completion rate",
      "impact": "Could improve conversion by 5-8%",
      "confidence": 0.85
    },
    {
      "priority": "medium",
      "recommendation": "Add progress indicators to GENERATING_RECOMMENDATIONS stage",
      "impact": "Could improve conversion by 3-5%",
      "confidence": 0.72
    }
  ],
  "time_range": {
    "start": "2025-09-01T00:00:00Z",
    "end": "2025-10-01T00:00:00Z",
    "days": 30
  },
  "last_updated": "2025-10-01T11:00:00Z"
}
```

---

### 2. Get Drop-Off Heatmap

**Endpoint:** `GET /analytics/drop-off-heatmap/`

**Description:** Analyze drop-off patterns by time and stage.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string (ISO 8601) | No | 7 days ago | Start of analysis period |
| `end_date` | string (ISO 8601) | No | now | End of analysis period |
| `granularity` | string | No | hourly | Time granularity: `hourly`, `daily`, `weekly` |

**Example Request:**

```http
GET /api/v1/onboarding/analytics/drop-off-heatmap/?granularity=daily&start_date=2025-09-24
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "heatmap_data": [
    {
      "time_bucket": "2025-09-24",
      "sessions_started": 45,
      "drop_offs_by_stage": {
        "COLLECTING_INFO": 8,
        "GENERATING_RECOMMENDATIONS": 3,
        "PENDING_APPROVAL": 2
      },
      "completion_rate": 0.711
    },
    {
      "time_bucket": "2025-09-25",
      "sessions_started": 52,
      "drop_offs_by_stage": {
        "COLLECTING_INFO": 10,
        "GENERATING_RECOMMENDATIONS": 4,
        "PENDING_APPROVAL": 1
      },
      "completion_rate": 0.712
    }
  ],
  "overall_drop_off_rate": 0.253,
  "highest_drop_off_hour": "14:00-15:00",
  "lowest_drop_off_hour": "09:00-10:00",
  "time_range": {
    "start": "2025-09-24T00:00:00Z",
    "end": "2025-10-01T00:00:00Z",
    "granularity": "daily"
  }
}
```

---

### 3. Get Cohort Comparison

**Endpoint:** `GET /analytics/cohort-comparison/`

**Description:** Compare conversion rates across different cohorts.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `cohort_by` | string | No | client | Cohort grouping: `client`, `conversation_type`, `language` |
| `start_date` | string (ISO 8601) | No | 30 days ago | Start of analysis period |
| `end_date` | string (ISO 8601) | No | now | End of analysis period |

**Example Request:**

```http
GET /api/v1/onboarding/analytics/cohort-comparison/?cohort_by=conversation_type
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "cohorts": [
    {
      "cohort_id": "site_survey",
      "cohort_name": "Site Survey",
      "total_sessions": 800,
      "completed_sessions": 625,
      "conversion_rate": 0.781,
      "avg_completion_time_minutes": 15.2
    },
    {
      "cohort_id": "business_unit_setup",
      "cohort_name": "Business Unit Setup",
      "total_sessions": 450,
      "completed_sessions": 315,
      "conversion_rate": 0.7,
      "avg_completion_time_minutes": 22.8
    }
  ],
  "best_performing_cohort": {
    "cohort_id": "site_survey",
    "conversion_rate": 0.781
  },
  "worst_performing_cohort": {
    "cohort_id": "business_unit_setup",
    "conversion_rate": 0.7
  },
  "cohort_by": "conversation_type",
  "time_range": {
    "start": "2025-09-01T00:00:00Z",
    "end": "2025-10-01T00:00:00Z"
  }
}
```

---

### 4. Get Optimization Recommendations

**Endpoint:** `GET /analytics/recommendations/`

**Description:** Get AI-powered recommendations to improve conversion rates.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string (ISO 8601) | No | 30 days ago | Start of analysis period |
| `end_date` | string (ISO 8601) | No | now | End of analysis period |
| `min_confidence` | float | No | 0.7 | Minimum confidence threshold (0-1) |

**Example Request:**

```http
GET /api/v1/onboarding/analytics/recommendations/?min_confidence=0.75
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "recommendations": [
    {
      "id": "rec_001",
      "priority": "high",
      "confidence": 0.89,
      "category": "user_experience",
      "recommendation": "Add progress bar to information collection stage",
      "reasoning": "12% of users drop off during COLLECTING_INFO without knowing how many questions remain",
      "expected_impact": {
        "conversion_rate_increase": 0.05,
        "completion_time_decrease_minutes": 2.0
      },
      "implementation_effort": "low",
      "data_points": 1250
    },
    {
      "id": "rec_002",
      "priority": "high",
      "confidence": 0.85,
      "category": "performance",
      "recommendation": "Reduce LLM recommendation generation timeout from 60s to 30s with fallback",
      "reasoning": "6.4% of users drop off during GENERATING_RECOMMENDATIONS due to perceived slowness",
      "expected_impact": {
        "conversion_rate_increase": 0.04,
        "completion_time_decrease_minutes": 3.5
      },
      "implementation_effort": "medium",
      "data_points": 1100
    },
    {
      "id": "rec_003",
      "priority": "medium",
      "confidence": 0.78,
      "category": "content",
      "recommendation": "Simplify approval workflow - combine secondary approval into primary",
      "reasoning": "4% of users abandon at PENDING_APPROVAL stage waiting for secondary approval",
      "expected_impact": {
        "conversion_rate_increase": 0.03,
        "completion_time_decrease_minutes": 5.0
      },
      "implementation_effort": "high",
      "data_points": 970
    }
  ],
  "total_recommendations": 3,
  "aggregated_impact": {
    "potential_conversion_increase": 0.12,
    "potential_time_saved_minutes": 10.5
  },
  "time_range": {
    "start": "2025-09-01T00:00:00Z",
    "end": "2025-10-01T00:00:00Z"
  }
}
```

---

### 5. Get Real-Time Dashboard

**Endpoint:** `GET /analytics/realtime/`

**Description:** Real-time metrics with 5-minute cache (for live monitoring dashboards).

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `time_range_hours` | integer | No | 1 | Time range for real-time data |

**Example Request:**

```http
GET /api/v1/onboarding/analytics/realtime/?time_range_hours=1
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "active_sessions": 23,
  "sessions_started_last_hour": 15,
  "sessions_completed_last_hour": 11,
  "current_conversion_rate": 0.733,
  "avg_session_duration_minutes": 16.8,
  "sessions_by_stage": {
    "STARTED": 3,
    "COLLECTING_INFO": 8,
    "GENERATING_RECOMMENDATIONS": 5,
    "PENDING_APPROVAL": 4,
    "COMPLETED": 11
  },
  "recent_errors": [
    {
      "timestamp": "2025-10-01T10:55:00Z",
      "session_id": "session-uuid-123",
      "error_type": "LLM_TIMEOUT",
      "stage": "GENERATING_RECOMMENDATIONS"
    }
  ],
  "at_risk_sessions": [
    {
      "session_id": "session-uuid-456",
      "risk_level": "high",
      "risk_score": 75,
      "last_activity": "2025-10-01T10:45:00Z",
      "current_stage": "COLLECTING_INFO"
    }
  ],
  "cache_ttl": 300,
  "last_updated": "2025-10-01T11:00:00Z"
}
```

---

### 6. Get Period Comparison

**Endpoint:** `GET /analytics/comparison/`

**Description:** Compare metrics between two time periods.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `period1_start` | string (ISO 8601) | Yes | - | First period start |
| `period1_end` | string (ISO 8601) | Yes | - | First period end |
| `period2_start` | string (ISO 8601) | Yes | - | Second period start |
| `period2_end` | string (ISO 8601) | Yes | - | Second period end |

**Example Request:**

```http
GET /api/v1/onboarding/analytics/comparison/?period1_start=2025-09-01&period1_end=2025-09-15&period2_start=2025-09-16&period2_end=2025-10-01
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "period1": {
    "label": "Sep 1-15",
    "total_sessions": 625,
    "completed_sessions": 465,
    "conversion_rate": 0.744,
    "avg_completion_time_minutes": 19.2
  },
  "period2": {
    "label": "Sep 16-30",
    "total_sessions": 625,
    "completed_sessions": 475,
    "conversion_rate": 0.76,
    "avg_completion_time_minutes": 17.8
  },
  "comparison": {
    "conversion_rate_change": 0.016,
    "conversion_rate_change_percent": 2.15,
    "completion_time_change_minutes": -1.4,
    "sessions_change": 0,
    "sessions_change_percent": 0
  },
  "trend": "improving",
  "statistical_significance": {
    "p_value": 0.032,
    "is_significant": true,
    "confidence_level": 0.95
  }
}
```

---

## Session Recovery API

Manage session checkpoints and recovery for abandoned sessions.

### Base Path

`/api/v1/onboarding/sessions/`

**Required Permission:** `IsAuthenticated`

---

### 1. Create Checkpoint

**Endpoint:** `POST /sessions/{session_id}/checkpoint/`

**Description:** Create a checkpoint for session state preservation.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string (UUID) | Yes | Conversation session ID |

**Request Body:**

```json
{
  "checkpoint_data": {
    "version": 1,
    "state": "COLLECTING_INFO",
    "data": {
      "answers": [
        {"question": "Site name?", "answer": "Factory A"},
        {"question": "Location?", "answer": "Mumbai"}
      ],
      "progress": 0.4
    }
  },
  "force": false
}
```

**Body Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `checkpoint_data` | object | Yes | - | Complete session state to save |
| `checkpoint_data.version` | integer | Yes | - | Checkpoint version number |
| `checkpoint_data.state` | string | Yes | - | Current session state |
| `checkpoint_data.data` | object | Yes | - | Session data (answers, progress, etc.) |
| `force` | boolean | No | false | Force checkpoint creation (skip duplicate check) |

**Example Request:**

```http
POST /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/checkpoint/
Authorization: Bearer {token}
Content-Type: application/json

{
  "checkpoint_data": {
    "version": 1,
    "state": "COLLECTING_INFO",
    "data": {
      "answers": [
        {"question": "Site name?", "answer": "Factory A"}
      ]
    }
  },
  "force": false
}
```

**Example Response:**

```json
{
  "status": "created",
  "checkpoint_version": 1,
  "checkpoint_hash": "a1b2c3d4e5f6",
  "created_at": "2025-10-01T11:00:00Z",
  "storage": {
    "redis": true,
    "postgresql": true
  },
  "ttl_seconds": 3600
}
```

---

### 2. Resume Session

**Endpoint:** `POST /sessions/{session_id}/resume/`

**Description:** Resume a session from the latest checkpoint.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string (UUID) | Yes | Conversation session ID |

**Request Body:**

```json
{
  "checkpoint_version": null
}
```

**Body Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `checkpoint_version` | integer | No | null | Specific checkpoint version to restore (default: latest) |

**Example Request:**

```http
POST /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/resume/
Authorization: Bearer {token}
Content-Type: application/json

{
  "checkpoint_version": null
}
```

**Example Response:**

```json
{
  "status": "resumed",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "restored_state": "COLLECTING_INFO",
  "restored_data": {
    "answers": [
      {"question": "Site name?", "answer": "Factory A"},
      {"question": "Location?", "answer": "Mumbai"}
    ],
    "progress": 0.4
  },
  "checkpoint_version": 1,
  "checkpoint_age_seconds": 1800,
  "next_action": {
    "type": "continue_questions",
    "description": "Resume answering remaining questions"
  }
}
```

**Error Response (No Checkpoints):**

```json
{
  "error": "no_checkpoints_found",
  "detail": "No checkpoints available for this session",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "suggestion": "Start a new session instead"
}
```

---

### 3. List Checkpoints

**Endpoint:** `GET /sessions/{session_id}/checkpoints/`

**Description:** Retrieve checkpoint history for a session.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string (UUID) | Yes | Conversation session ID |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 10 | Maximum checkpoints to return |

**Example Request:**

```http
GET /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/checkpoints/?limit=10
Authorization: Bearer {token}
```

**Example Response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_checkpoints": 5,
  "checkpoints": [
    {
      "version": 5,
      "state": "PENDING_APPROVAL",
      "created_at": "2025-10-01T11:10:00Z",
      "checkpoint_hash": "a1b2c3d4e5f6",
      "data_summary": {
        "answers_count": 10,
        "progress": 0.9
      }
    },
    {
      "version": 4,
      "state": "GENERATING_RECOMMENDATIONS",
      "created_at": "2025-10-01T11:08:00Z",
      "checkpoint_hash": "f6e5d4c3b2a1",
      "data_summary": {
        "answers_count": 10,
        "progress": 0.8
      }
    }
  ]
}
```

---

### 4. Get Abandonment Risk

**Endpoint:** `GET /sessions/{session_id}/risk/`

**Description:** Get ML-based abandonment risk assessment for a session.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string (UUID) | Yes | Conversation session ID |

**Example Request:**

```http
GET /api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/risk/
Authorization: Bearer {token}
```

**Example Response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "risk_score": 65,
  "risk_level": "high",
  "risk_factors": [
    {
      "factor": "inactivity",
      "value": 25,
      "weight": 0.3,
      "contribution": 7.5,
      "description": "Session inactive for 25 minutes"
    },
    {
      "factor": "question_repetition",
      "value": 3,
      "weight": 0.25,
      "contribution": 18.75,
      "description": "User repeated 3 questions"
    },
    {
      "factor": "error_frequency",
      "value": 5,
      "weight": 0.25,
      "contribution": 31.25,
      "description": "5 errors encountered during session"
    },
    {
      "factor": "session_complexity",
      "value": 0.3,
      "weight": 0.2,
      "contribution": 7.5,
      "description": "Session is 30% more complex than average"
    }
  ],
  "intervention_recommendation": {
    "type": "send_reminder",
    "priority": "high",
    "message": "User has been inactive for 25 minutes with multiple errors. Send reminder email with resume link.",
    "actions": [
      "Send email reminder",
      "Include session resume link",
      "Offer chat support"
    ]
  },
  "predicted_abandonment_probability": 0.72,
  "last_activity": "2025-10-01T10:35:00Z",
  "session_age_minutes": 45,
  "current_stage": "COLLECTING_INFO"
}
```

---

### 5. List At-Risk Sessions (Admin)

**Endpoint:** `GET /admin/at-risk-sessions/`

**Description:** Retrieve all sessions at risk of abandonment.

**Required Permission:** `IsAdminUser`

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `risk_level` | string | No | high | Filter by risk: `critical`, `high`, `medium`, `low` |
| `limit` | integer | No | 20 | Maximum sessions to return |

**Example Request:**

```http
GET /api/v1/onboarding/admin/at-risk-sessions/?risk_level=high&limit=20
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "total_at_risk": 45,
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": 123,
      "risk_score": 75,
      "risk_level": "critical",
      "last_activity": "2025-10-01T10:30:00Z",
      "current_stage": "COLLECTING_INFO",
      "intervention_priority": "immediate",
      "recommended_action": "Manual outreach via phone"
    },
    {
      "session_id": "660f9511-f3ac-52e5-b827-557766551111",
      "user_id": 456,
      "risk_score": 65,
      "risk_level": "high",
      "last_activity": "2025-10-01T10:45:00Z",
      "current_stage": "GENERATING_RECOMMENDATIONS",
      "intervention_priority": "high",
      "recommended_action": "Send reminder email with resume link"
    }
  ]
}
```

---

## Analytics Dashboard API

Comprehensive analytics dashboards aggregating multiple data sources.

### Base Path

`/api/v1/onboarding/dashboard/`

**Required Permission:** `IsAdminUser` (except session replay for own sessions)

---

### 1. Get Dashboard Overview

**Endpoint:** `GET /dashboard/overview/`

**Description:** Comprehensive dashboard with all key metrics (cached 5 minutes).

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `client_id` | integer | No | null | Filter by client |
| `time_range_hours` | integer | No | 24 | Time range for metrics |

**Example Request:**

```http
GET /api/v1/onboarding/dashboard/overview/?time_range_hours=24
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "overview": {
    "total_sessions": 150,
    "active_sessions": 23,
    "completed_sessions": 112,
    "conversion_rate": 0.7467,
    "avg_completion_time_minutes": 18.5
  },
  "funnel": {
    "stages": [
      {
        "name": "Session Started",
        "count": 150,
        "conversion_rate": 1.0,
        "drop_off_rate": 0.0
      },
      {
        "name": "Information Collection",
        "count": 132,
        "conversion_rate": 0.88,
        "drop_off_rate": 0.12
      },
      {
        "name": "Recommendation Review",
        "count": 122,
        "conversion_rate": 0.813,
        "drop_off_rate": 0.076
      },
      {
        "name": "Approval Process",
        "count": 117,
        "conversion_rate": 0.78,
        "drop_off_rate": 0.041
      },
      {
        "name": "Completed",
        "count": 112,
        "conversion_rate": 0.7467,
        "drop_off_rate": 0.043
      }
    ],
    "top_drop_offs": [
      {
        "state": "COLLECTING_INFO",
        "count": 18,
        "percentage": 0.12
      },
      {
        "state": "GENERATING_RECOMMENDATIONS",
        "count": 10,
        "percentage": 0.067
      },
      {
        "state": "PENDING_APPROVAL",
        "count": 5,
        "percentage": 0.033
      }
    ]
  },
  "recovery": {
    "checkpoints_created": 450,
    "sessions_resumed": 28,
    "at_risk_count": 8,
    "at_risk_sessions": [
      {
        "session_id": "550e8400-e29b-41d4-a716-446655440000",
        "risk_score": 75,
        "risk_level": "critical",
        "last_activity": "2025-10-01T10:30:00Z"
      }
    ]
  },
  "recommendations": [
    {
      "priority": "high",
      "recommendation": "Add progress indicators to information collection",
      "impact": "Could improve conversion by 5-8%"
    },
    {
      "priority": "medium",
      "recommendation": "Reduce LLM timeout and add loading animations",
      "impact": "Could improve conversion by 3-5%"
    }
  ],
  "time_range": {
    "start": "2025-09-30T11:00:00Z",
    "end": "2025-10-01T11:00:00Z",
    "hours": 24
  },
  "last_updated": "2025-10-01T11:00:00Z"
}
```

---

### 2. Get Drop-Off Heatmap

**Endpoint:** `GET /dashboard/heatmap/`

**Description:** Drop-off heatmap visualization data.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string (ISO 8601) | No | 7 days ago | Start of period |
| `end_date` | string (ISO 8601) | No | now | End of period |
| `granularity` | string | No | daily | Time granularity: `hourly`, `daily`, `weekly` |

**Example Request:**

```http
GET /api/v1/onboarding/dashboard/heatmap/?granularity=daily&start_date=2025-09-24
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "heatmap_data": [
    {
      "time_period": "2025-09-24",
      "start": "2025-09-24T00:00:00Z",
      "end": "2025-09-25T00:00:00Z",
      "stage_counts": [
        {"stage": "Session Started", "count": 45},
        {"stage": "Information Collection", "count": 8},
        {"stage": "Recommendation Review", "count": 3},
        {"stage": "Approval Process", "count": 2},
        {"stage": "Completed", "count": 0}
      ],
      "total_sessions": 45
    }
  ],
  "overall_drop_offs": {
    "COLLECTING_INFO": 150,
    "GENERATING_RECOMMENDATIONS": 80,
    "PENDING_APPROVAL": 50
  },
  "error_patterns": [
    {
      "error_type": "LLM_TIMEOUT",
      "count": 25,
      "stages": ["GENERATING_RECOMMENDATIONS"]
    }
  ],
  "time_analysis": {
    "peak_drop_off_hour": "14:00-15:00",
    "lowest_drop_off_hour": "09:00-10:00"
  },
  "granularity": "daily",
  "period": {
    "start": "2025-09-24T00:00:00Z",
    "end": "2025-10-01T00:00:00Z"
  }
}
```

---

### 3. Get Session Replay

**Endpoint:** `GET /dashboard/session-replay/{session_id}/`

**Description:** Complete session timeline for analysis.

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string (UUID) | Yes | Conversation session ID |

**Example Request:**

```http
GET /api/v1/onboarding/dashboard/session-replay/550e8400-e29b-41d4-a716-446655440000/
Authorization: Bearer {token}
```

**Example Response:**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "timeline": [
    {
      "timestamp": "2025-10-01T10:00:00Z",
      "event_type": "session_start",
      "data": {
        "language": "en",
        "conversation_type": "site_survey"
      }
    },
    {
      "timestamp": "2025-10-01T10:02:30Z",
      "event_type": "question_answered",
      "data": {
        "question_index": 0,
        "question": "What is the site name?",
        "answer_length": 25
      }
    },
    {
      "timestamp": "2025-10-01T10:05:00Z",
      "event_type": "checkpoint_created",
      "data": {
        "checkpoint_version": 1,
        "state": "COLLECTING_INFO"
      }
    },
    {
      "timestamp": "2025-10-01T10:15:00Z",
      "event_type": "state_transition",
      "data": {
        "current_state": "GENERATING_RECOMMENDATIONS"
      }
    }
  ],
  "session_summary": {
    "started_at": "2025-10-01T10:00:00Z",
    "updated_at": "2025-10-01T10:18:30Z",
    "current_state": "COMPLETED",
    "total_events": 45,
    "duration_minutes": 18.5
  }
}
```

---

### 4. Get Cohort Trends

**Endpoint:** `GET /dashboard/cohort-trends/`

**Description:** Cohort trend analysis over time.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string (ISO 8601) | No | 30 days ago | Start of period |
| `end_date` | string (ISO 8601) | No | now | End of period |
| `cohort_type` | string | No | weekly | Cohort grouping: `daily`, `weekly`, `monthly` |

**Example Request:**

```http
GET /api/v1/onboarding/dashboard/cohort-trends/?cohort_type=weekly
Authorization: Bearer {admin_token}
```

**Example Response:**

```json
{
  "cohorts": [
    {
      "cohort_label": "2025-09-03",
      "start_date": "2025-09-03T00:00:00Z",
      "end_date": "2025-09-10T00:00:00Z",
      "total_sessions": 210,
      "completed_sessions": 155,
      "conversion_rate": 0.738,
      "avg_completion_time_minutes": 19.5
    },
    {
      "cohort_label": "2025-09-10",
      "start_date": "2025-09-10T00:00:00Z",
      "end_date": "2025-09-17T00:00:00Z",
      "total_sessions": 225,
      "completed_sessions": 168,
      "conversion_rate": 0.747,
      "avg_completion_time_minutes": 18.8
    },
    {
      "cohort_label": "2025-09-24",
      "start_date": "2025-09-24T00:00:00Z",
      "end_date": "2025-10-01T00:00:00Z",
      "total_sessions": 240,
      "completed_sessions": 182,
      "conversion_rate": 0.758,
      "avg_completion_time_minutes": 17.2
    }
  ],
  "trends": {
    "conversion_trend": "improving",
    "conversion_change": 0.02,
    "volume_trend": "growing",
    "volume_change_percent": 14.29
  },
  "cohort_type": "weekly",
  "period": {
    "start": "2025-09-03T00:00:00Z",
    "end": "2025-10-01T00:00:00Z"
  }
}
```

---

## Code Examples

### Python (requests)

```python
import requests
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://your-domain.com/api/v1/onboarding"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Example 1: Get funnel metrics for last 30 days
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

response = requests.get(
    f"{BASE_URL}/analytics/funnel/",
    headers=headers,
    params={
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }
)

if response.status_code == 200:
    metrics = response.json()
    print(f"Overall conversion rate: {metrics['overall_conversion_rate']:.2%}")
    print(f"Total sessions: {metrics['total_sessions']}")

    # Print stage-by-stage conversion
    for stage in metrics['stages']:
        print(f"  {stage['name']}: {stage['conversion_rate']:.2%}")
else:
    print(f"Error: {response.status_code} - {response.text}")

# Example 2: Create session checkpoint
session_id = "550e8400-e29b-41d4-a716-446655440000"

checkpoint_data = {
    "checkpoint_data": {
        "version": 1,
        "state": "COLLECTING_INFO",
        "data": {
            "answers": [
                {"question": "Site name?", "answer": "Factory A"}
            ],
            "progress": 0.3
        }
    },
    "force": False
}

response = requests.post(
    f"{BASE_URL}/sessions/{session_id}/checkpoint/",
    headers=headers,
    json=checkpoint_data
)

if response.status_code == 200:
    result = response.json()
    print(f"Checkpoint created: version {result['checkpoint_version']}")
else:
    print(f"Error: {response.status_code} - {response.text}")

# Example 3: Check abandonment risk
response = requests.get(
    f"{BASE_URL}/sessions/{session_id}/risk/",
    headers=headers
)

if response.status_code == 200:
    risk = response.json()
    print(f"Risk level: {risk['risk_level']} (score: {risk['risk_score']})")
    print(f"Recommendation: {risk['intervention_recommendation']['type']}")
else:
    print(f"Error: {response.status_code} - {response.text}")

# Example 4: Retry failed task from DLQ
task_id = "dlq_123456"

response = requests.post(
    f"{BASE_URL}/admin/dlq/tasks/{task_id}/retry/",
    headers=headers,
    json={"force": False}
)

if response.status_code == 200:
    result = response.json()
    print(f"Task retrying: {result['status']}")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

### JavaScript (fetch)

```javascript
// Configuration
const BASE_URL = "https://your-domain.com/api/v1/onboarding";
const TOKEN = "your-jwt-token";

const headers = {
  "Authorization": `Bearer ${TOKEN}`,
  "Content-Type": "application/json"
};

// Example 1: Get dashboard overview
async function getDashboardOverview() {
  try {
    const response = await fetch(
      `${BASE_URL}/dashboard/overview/?time_range_hours=24`,
      { headers }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log("Total sessions:", data.overview.total_sessions);
    console.log("Conversion rate:", data.overview.conversion_rate);
    console.log("Top drop-offs:", data.funnel.top_drop_offs);

    return data;
  } catch (error) {
    console.error("Error fetching dashboard:", error);
  }
}

// Example 2: Resume session from checkpoint
async function resumeSession(sessionId) {
  try {
    const response = await fetch(
      `${BASE_URL}/sessions/${sessionId}/resume/`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ checkpoint_version: null })
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log("Session resumed:", data.status);
    console.log("Restored state:", data.restored_state);
    console.log("Next action:", data.next_action.description);

    return data;
  } catch (error) {
    console.error("Error resuming session:", error);
  }
}

// Example 3: Get real-time analytics
async function getRealtimeAnalytics() {
  try {
    const response = await fetch(
      `${BASE_URL}/analytics/realtime/?time_range_hours=1`,
      { headers }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    console.log("Active sessions:", data.active_sessions);
    console.log("At-risk sessions:", data.at_risk_sessions.length);

    // Update dashboard
    document.getElementById("active-sessions").textContent = data.active_sessions;
    document.getElementById("conversion-rate").textContent =
      `${(data.current_conversion_rate * 100).toFixed(1)}%`;

    return data;
  } catch (error) {
    console.error("Error fetching realtime analytics:", error);
  }
}

// Poll real-time analytics every 30 seconds
setInterval(getRealtimeAnalytics, 30000);

// Usage
getDashboardOverview();
resumeSession("550e8400-e29b-41d4-a716-446655440000");
```

### cURL Examples

```bash
# Get funnel metrics
curl -X GET "https://your-domain.com/api/v1/onboarding/analytics/funnel/?start_date=2025-09-01" \
  -H "Authorization: Bearer {token}" \
  | jq '.overall_conversion_rate'

# Create checkpoint
curl -X POST "https://your-domain.com/api/v1/onboarding/sessions/550e8400-e29b-41d4-a716-446655440000/checkpoint/" \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_data": {
      "version": 1,
      "state": "COLLECTING_INFO",
      "data": {"answers": []}
    }
  }' | jq '.status'

# Get DLQ stats
curl -X GET "https://your-domain.com/api/v1/onboarding/admin/dlq/stats/" \
  -H "Authorization: Bearer {admin_token}" \
  | jq '.total_failed_tasks'

# Get at-risk sessions
curl -X GET "https://your-domain.com/api/v1/onboarding/admin/at-risk-sessions/?risk_level=high" \
  -H "Authorization: Bearer {admin_token}" \
  | jq '.sessions | length'
```

---

## Postman Collection

Import this collection into Postman for easy API testing:

```json
{
  "info": {
    "name": "Onboarding Security Enhancements API",
    "description": "Complete API collection for DLQ, Funnel Analytics, Session Recovery, and Analytics Dashboard",
    "version": "1.0.0"
  },
  "auth": {
    "type": "bearer",
    "bearer": [
      {
        "key": "token",
        "value": "{{jwt_token}}",
        "type": "string"
      }
    ]
  },
  "variable": [
    {
      "key": "base_url",
      "value": "https://your-domain.com/api/v1/onboarding",
      "type": "string"
    },
    {
      "key": "jwt_token",
      "value": "your-jwt-token-here",
      "type": "string"
    },
    {
      "key": "session_id",
      "value": "550e8400-e29b-41d4-a716-446655440000",
      "type": "string"
    }
  ],
  "item": [
    {
      "name": "DLQ Admin",
      "item": [
        {
          "name": "List Failed Tasks",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/admin/dlq/tasks/?status=pending"
          }
        },
        {
          "name": "Get Task Details",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/admin/dlq/tasks/dlq_123456/"
          }
        },
        {
          "name": "Retry Task",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/admin/dlq/tasks/dlq_123456/retry/",
            "body": {
              "mode": "raw",
              "raw": "{\"force\": false}"
            }
          }
        },
        {
          "name": "Get DLQ Stats",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/admin/dlq/stats/"
          }
        }
      ]
    },
    {
      "name": "Funnel Analytics",
      "item": [
        {
          "name": "Get Funnel Metrics",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/analytics/funnel/?start_date=2025-09-01"
          }
        },
        {
          "name": "Get Drop-Off Heatmap",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/analytics/drop-off-heatmap/?granularity=daily"
          }
        },
        {
          "name": "Get Real-Time Analytics",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/analytics/realtime/?time_range_hours=1"
          }
        }
      ]
    },
    {
      "name": "Session Recovery",
      "item": [
        {
          "name": "Create Checkpoint",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/sessions/{{session_id}}/checkpoint/",
            "body": {
              "mode": "raw",
              "raw": "{\"checkpoint_data\": {\"version\": 1, \"state\": \"COLLECTING_INFO\", \"data\": {}}}"
            }
          }
        },
        {
          "name": "Resume Session",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/sessions/{{session_id}}/resume/",
            "body": {
              "mode": "raw",
              "raw": "{}"
            }
          }
        },
        {
          "name": "Get Abandonment Risk",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/sessions/{{session_id}}/risk/"
          }
        }
      ]
    },
    {
      "name": "Analytics Dashboard",
      "item": [
        {
          "name": "Dashboard Overview",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/dashboard/overview/?time_range_hours=24"
          }
        },
        {
          "name": "Session Replay",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/dashboard/session-replay/{{session_id}}/"
          }
        },
        {
          "name": "Cohort Trends",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/dashboard/cohort-trends/?cohort_type=weekly"
          }
        }
      ]
    }
  ]
}
```

---

## Support and Contact

**Documentation Version:** 1.0
**Last Updated:** 2025-10-01

For API support, issues, or feature requests, please contact:
- **Development Team:** dev@your-company.com
- **API Documentation:** https://your-domain.com/api/docs/

---

**End of API Documentation**
