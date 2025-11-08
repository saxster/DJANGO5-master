# API Contract: Helpdesk Domain

> **Domain:** Helpdesk & Ticketing (Tickets, SLA, Escalations, Search)
> **Version:** 1.0.0
> **Last Updated:** November 7, 2025
> **Base URL:** `/api/v2/helpdesk/`

---

## 📋 Table of Contents

- [Overview](#overview)
- [Ticket Management](#ticket-management)
- [SLA Tracking](#sla-tracking)
- [Escalations](#escalations)
- [Search & Filters](#search--filters)
- [Complete Workflows](#complete-workflows)
- [Data Model Summary](#data-model-summary)

---

## Overview

The Helpdesk domain handles support ticketing, SLA tracking, and automated escalations.

### Key Features

- **Ticket Lifecycle**: Create → Assign → Work → Resolve → Close
- **SLA Management**: Automated SLA tracking with breach alerts
- **Smart Escalation**: Auto-escalate based on priority + time
- **Rich Attachments**: Photos, documents, audio notes
- **Natural Language**: Semantic search powered by embeddings
- **Offline Support**: Create tickets offline, sync when connected

### Django Implementation

- **Models:** `apps/y_helpdesk/models/`
- **Viewsets:** `apps/y_helpdesk/api/viewsets.py`
- **Services:** `apps/y_helpdesk/services/`
- **Permissions:** `apps/y_helpdesk/permissions.py`

---

## Ticket Management

### Ticket State Machine

```
new → open → in_progress → resolved → closed
                ↓
            on_hold (temporary pause)
                ↓
            in_progress (resume)
```

**State Transitions:**
- `new` → `open`: Agent acknowledges ticket
- `open` → `in_progress`: Agent starts work
- `in_progress` → `on_hold`: Waiting for customer/info
- `on_hold` → `in_progress`: Resume work
- `in_progress` → `resolved`: Solution implemented
- `resolved` → `closed`: Customer confirms (or auto-close after 48h)

---

### 1. Create Ticket

**Endpoint:** `POST /api/v2/helpdesk/tickets/`

**Django Implementation:**
- **Viewset:** `apps/y_helpdesk/api/viewsets.py:TicketViewSet.create()`
- **Service:** `apps/y_helpdesk/services/ticket_service.py:TicketService.create_ticket()`
- **Permissions:** `IsAuthenticated`

**Purpose:** Create support ticket with attachments

**Request:**
```json
{
  "subject": "Unable to check in - GPS error",
  "description": "I'm at the site but the app says I'm outside the geofence. My GPS shows accurate location.",
  "category": "technical_issue",
  "priority": "medium",
  "severity": "impacts_work",
  "affected_feature": "attendance_checkin",
  "related_entity": {
    "entity_type": "attendance",
    "entity_id": 7001
  },
  "attachments": [
    {
      "filename": "screenshot_error.jpg",
      "file_data": "data:image/jpeg;base64,/9j/4AAQ...",
      "file_type": "image/jpeg",
      "description": "Error message screenshot"
    }
  ],
  "device_info": {
    "device_model": "Samsung Galaxy S23",
    "os_version": "Android 14",
    "app_version": "2.1.0",
    "gps_enabled": true,
    "gps_accuracy_meters": 12.5
  },
  "tags": ["gps", "checkin", "geofence"]
}
```

**Field Validation:**
- `subject`: Required, 5-200 characters
- `description`: Required, 10-5000 characters
- `category`: Required, enum: `technical_issue|feature_request|bug_report|account_issue|other`
- `priority`: Optional, enum: `low|medium|high|urgent` (auto-set based on severity)
- `severity`: Required, enum: `minor_inconvenience|impacts_work|critical|security_issue`

**Response (201 Created):**
```json
{
  "id": 9001,
  "ticket_number": "TKT-2025-11-9001",
  "subject": "Unable to check in - GPS error",
  "description": "I'm at the site but the app says I'm outside the geofence...",
  "category": "technical_issue",
  "priority": "medium",
  "severity": "impacts_work",
  "status": "new",
  "requester": {
    "id": 123,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+65 9123 4567"
  },
  "assigned_to": null,
  "assigned_team": {
    "id": 5,
    "name": "Mobile Support Team"
  },
  "sla": {
    "response_due": "2025-11-15T12:05:00Z",
    "resolution_due": "2025-11-16T08:05:00Z",
    "time_to_response_minutes": 240,
    "time_to_resolution_minutes": 1440,
    "breach_risk": "low",
    "minutes_until_breach": 235
  },
  "attachments": [
    {
      "id": 10001,
      "filename": "screenshot_error.jpg",
      "file_url": "https://storage/tickets/9001/screenshot_error.jpg",
      "file_type": "image/jpeg",
      "file_size": 345678,
      "thumbnail_url": "https://storage/tickets/9001/thumb_screenshot_error.jpg",
      "uploaded_at": "2025-11-15T08:05:00Z"
    }
  ],
  "tags": ["gps", "checkin", "geofence"],
  "auto_tagged": ["attendance_module", "location_services"],
  "sentiment": "frustrated",
  "urgency_score": 0.65,
  "created_at": "2025-11-15T08:05:00Z",
  "updated_at": "2025-11-15T08:05:00Z",
  "correlation_id": "req-ticket-abc123"
}
```

**Auto-Assignment Logic:**
- Category `technical_issue` + tag `attendance` → Mobile Support Team
- Priority `urgent` or severity `critical` → On-call agent notified immediately
- AI sentiment analysis: "frustrated" tone → auto-escalate priority

---

### 2. List My Tickets

**Endpoint:** `GET /api/v2/helpdesk/tickets/my-tickets/`

**Django Implementation:**
- **Viewset:** `apps/y_helpdesk/api/viewsets.py:TicketViewSet.my_tickets()`
- **Permissions:** `IsAuthenticated`

**Purpose:** Get current user's tickets

**Query Parameters:**
- `status`: Filter: `new,open,in_progress,on_hold,resolved,closed`
- `priority`: Filter: `low,medium,high,urgent`
- `created_after`: ISO 8601 date
- `page`: Page number
- `page_size`: Items per page (max 100)
- `ordering`: Sort: `-created_at,priority,-sla_time_remaining`

**Request:**
```
GET /api/v2/helpdesk/tickets/my-tickets/?status=new,open,in_progress&ordering=-priority,-created_at
```

**Response (200 OK):**
```json
{
  "count": 12,
  "results": [
    {
      "id": 9001,
      "ticket_number": "TKT-2025-11-9001",
      "subject": "Unable to check in - GPS error",
      "category": "technical_issue",
      "priority": "medium",
      "status": "open",
      "requester": {
        "id": 123,
        "name": "John Doe"
      },
      "assigned_to": {
        "id": 789,
        "name": "Support Agent",
        "avatar_url": "https://storage/avatars/789.jpg"
      },
      "sla": {
        "response_due": "2025-11-15T12:05:00Z",
        "resolution_due": "2025-11-16T08:05:00Z",
        "breach_risk": "medium",
        "minutes_until_breach": 145,
        "is_breached": false
      },
      "unread_messages": 2,
      "last_activity": "2025-11-15T09:30:00Z",
      "created_at": "2025-11-15T08:05:00Z"
    }
  ]
}
```

---

### 3. Get Ticket Details

**Endpoint:** `GET /api/v2/helpdesk/tickets/{id}/`

**Django Implementation:**
- **Viewset:** `apps/y_helpdesk/api/viewsets.py:TicketViewSet.retrieve()`
- **Serializer:** `apps/y_helpdesk/serializers.py:TicketDetailSerializer`
- **Permissions:** `IsAuthenticated`, `CanViewTicket`

**Purpose:** Get complete ticket with messages and history

**Response (200 OK):**
```json
{
  "id": 9001,
  "ticket_number": "TKT-2025-11-9001",
  "subject": "Unable to check in - GPS error",
  "description": "I'm at the site but the app says I'm outside the geofence...",
  "category": "technical_issue",
  "priority": "medium",
  "severity": "impacts_work",
  "status": "in_progress",
  "requester": {
    "id": 123,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+65 9123 4567",
    "avatar_url": "https://storage/avatars/123.jpg"
  },
  "assigned_to": {
    "id": 789,
    "name": "Support Agent",
    "email": "support@example.com",
    "avatar_url": "https://storage/avatars/789.jpg"
  },
  "assigned_team": {
    "id": 5,
    "name": "Mobile Support Team"
  },
  "sla": {
    "response_time_minutes": 240,
    "resolution_time_minutes": 1440,
    "response_due": "2025-11-15T12:05:00Z",
    "resolution_due": "2025-11-16T08:05:00Z",
    "first_response_at": "2025-11-15T09:00:00Z",
    "resolved_at": null,
    "response_time_actual_minutes": 55,
    "resolution_time_actual_minutes": null,
    "response_sla_met": true,
    "resolution_sla_met": null,
    "breach_risk": "medium",
    "minutes_until_breach": 145,
    "is_breached": false
  },
  "messages": [
    {
      "id": 5001,
      "message_type": "note",
      "content": "I'm at the site but the app says I'm outside the geofence. My GPS shows accurate location.",
      "author": {
        "id": 123,
        "name": "John Doe",
        "user_type": "requester"
      },
      "created_at": "2025-11-15T08:05:00Z",
      "is_internal": false,
      "attachments": [
        {
          "id": 10001,
          "filename": "screenshot_error.jpg",
          "file_url": "https://storage/tickets/9001/screenshot_error.jpg",
          "thumbnail_url": "https://storage/tickets/9001/thumb_screenshot_error.jpg"
        }
      ]
    },
    {
      "id": 5002,
      "message_type": "reply",
      "content": "Thanks for reporting. I can see your GPS accuracy is good. Let me check the geofence configuration for your site.",
      "author": {
        "id": 789,
        "name": "Support Agent",
        "user_type": "agent"
      },
      "created_at": "2025-11-15T09:00:00Z",
      "is_internal": false,
      "attachments": []
    },
    {
      "id": 5003,
      "message_type": "internal_note",
      "content": "Site 789 geofence radius is 50m but should be 100m for this location.",
      "author": {
        "id": 789,
        "name": "Support Agent",
        "user_type": "agent"
      },
      "created_at": "2025-11-15T09:15:00Z",
      "is_internal": true,
      "attachments": []
    }
  ],
  "history": [
    {
      "timestamp": "2025-11-15T08:05:00Z",
      "action": "created",
      "user": {"id": 123, "name": "John Doe"},
      "changes": {"status": {"old": null, "new": "new"}}
    },
    {
      "timestamp": "2025-11-15T09:00:00Z",
      "action": "status_changed",
      "user": {"id": 789, "name": "Support Agent"},
      "changes": {"status": {"old": "new", "new": "in_progress"}}
    }
  ],
  "attachments": [
    {
      "id": 10001,
      "filename": "screenshot_error.jpg",
      "file_url": "https://storage/tickets/9001/screenshot_error.jpg",
      "file_type": "image/jpeg",
      "file_size": 345678,
      "uploaded_by": {"id": 123, "name": "John Doe"},
      "uploaded_at": "2025-11-15T08:05:00Z"
    }
  ],
  "tags": ["gps", "checkin", "geofence", "attendance_module", "location_services"],
  "related_tickets": [
    {
      "id": 9000,
      "ticket_number": "TKT-2025-11-9000",
      "subject": "GPS accuracy issues",
      "similarity_score": 0.87,
      "status": "resolved"
    }
  ],
  "sentiment_analysis": {
    "sentiment": "frustrated",
    "confidence": 0.82,
    "urgency_score": 0.65,
    "keywords": ["unable", "error", "not working"]
  },
  "created_at": "2025-11-15T08:05:00Z",
  "updated_at": "2025-11-15T09:15:00Z",
  "correlation_id": "req-ticket-details-999"
}
```

---

### 4. Update Ticket

**Endpoint:** `PATCH /api/v2/helpdesk/tickets/{id}/`

**Django Implementation:**
- **Viewset:** `apps/y_helpdesk/api/viewsets.py:TicketViewSet.partial_update()`
- **Permissions:** `IsAuthenticated`, `CanUpdateTicket`

**Purpose:** Update ticket fields (limited to requester)

**Request:**
```json
{
  "priority": "high",
  "description": "Updated description with more details..."
}
```

**Allowed Updates (Requester):**
- `description` - Add more details
- `priority` - Increase urgency
- Tags - Add relevant tags

**Not Allowed (Agent Only):**
- `status` - Use state transition endpoints
- `assigned_to` - Agent assignment
- `sla` - System controlled

**Response (200 OK):**
```json
{
  "id": 9001,
  "priority": "high",
  "description": "Updated description...",
  "updated_at": "2025-11-15T09:30:00Z",
  "sla": {
    "response_due": "2025-11-15T10:05:00Z",
    "resolution_due": "2025-11-15T20:05:00Z",
    "breach_risk": "high",
    "minutes_until_breach": 35
  },
  "correlation_id": "req-update-789"
}
```

---

### 5. Add Message to Ticket

**Endpoint:** `POST /api/v2/helpdesk/tickets/{id}/messages/`

**Django Implementation:**
- **Viewset:** `apps/y_helpdesk/api/viewsets.py:TicketViewSet.add_message()`
- **Permissions:** `IsAuthenticated`, `CanViewTicket`

**Purpose:** Add reply/note to ticket conversation

**Request:**
```json
{
  "content": "I tried rebooting the app but the issue persists. Still showing same error.",
  "attachments": [
    {
      "filename": "second_screenshot.jpg",
      "file_data": "data:image/jpeg;base64,/9j/4AAQ...",
      "file_type": "image/jpeg"
    }
  ]
}
```

**Response (201 Created):**
```json
{
  "id": 5004,
  "ticket_id": 9001,
  "message_type": "reply",
  "content": "I tried rebooting the app but the issue persists...",
  "author": {
    "id": 123,
    "name": "John Doe",
    "user_type": "requester"
  },
  "attachments": [
    {
      "id": 10002,
      "filename": "second_screenshot.jpg",
      "file_url": "https://storage/tickets/9001/second_screenshot.jpg",
      "thumbnail_url": "https://storage/tickets/9001/thumb_second_screenshot.jpg"
    }
  ],
  "is_internal": false,
  "created_at": "2025-11-15T09:45:00Z",
  "correlation_id": "req-message-123"
}
```

**Auto-Actions:**
- If ticket was `resolved`, auto-reopen to `in_progress`
- SLA clock restarts
- Agent notified via WebSocket

---

### 6. Close Ticket

**Endpoint:** `POST /api/v2/helpdesk/tickets/{id}/close/`

**Purpose:** Customer confirms resolution (requester only)

**Request:**
```json
{
  "resolution_feedback": "satisfied",
  "rating": 5,
  "comments": "Issue resolved quickly, great support!"
}
```

**Response (200 OK):**
```json
{
  "id": 9001,
  "status": "closed",
  "resolution_feedback": "satisfied",
  "rating": 5,
  "closed_at": "2025-11-15T15:00:00Z",
  "total_resolution_time_minutes": 415,
  "sla_met": true,
  "correlation_id": "req-close-456"
}
```

---

## SLA Tracking

### 7. Get SLA Status

**Endpoint:** `GET /api/v2/helpdesk/tickets/{id}/sla/`

**Purpose:** Get real-time SLA countdown (for showing urgency in UI)

**Response (200 OK):**
```json
{
  "ticket_id": 9001,
  "sla_policy": {
    "policy_name": "Standard Support",
    "response_time_minutes": 240,
    "resolution_time_minutes": 1440
  },
  "response": {
    "due_at": "2025-11-15T12:05:00Z",
    "first_response_at": "2025-11-15T09:00:00Z",
    "actual_time_minutes": 55,
    "target_time_minutes": 240,
    "sla_met": true,
    "breach_risk": null
  },
  "resolution": {
    "due_at": "2025-11-16T08:05:00Z",
    "resolved_at": null,
    "elapsed_time_minutes": 95,
    "remaining_time_minutes": 1345,
    "target_time_minutes": 1440,
    "sla_met": null,
    "breach_risk": "low",
    "breach_probability": 0.15
  },
  "escalation": {
    "escalated": false,
    "escalation_level": 0,
    "next_escalation_at": "2025-11-15T20:05:00Z",
    "escalation_reason": null
  },
  "correlation_id": "req-sla-789"
}
```

**UI Usage:**
```kotlin
// Show countdown timer
val minutesRemaining = sla.resolution.remainingTimeMinutes
when {
    minutesRemaining < 60 -> showRedUrgent() // Less than 1 hour
    minutesRemaining < 240 -> showOrangeWarning() // Less than 4 hours
    else -> showGreenNormal()
}

// Show breach risk indicator
if (sla.resolution.breachRisk == "high") {
    showBreachWarning()
}
```

---

## Escalations

### 8. Request Manual Escalation

**Endpoint:** `POST /api/v2/helpdesk/tickets/{id}/escalate/`

**Purpose:** Customer manually escalates unresolved ticket

**Request:**
```json
{
  "escalation_reason": "no_response_48_hours",
  "details": "Agent has not responded for 2 days, issue is blocking my work"
}
```

**Response (200 OK):**
```json
{
  "id": 9001,
  "status": "in_progress",
  "escalation": {
    "escalated": true,
    "escalation_level": 1,
    "escalated_to": {
      "id": 999,
      "name": "Support Manager",
      "email": "support.manager@example.com"
    },
    "escalation_reason": "no_response_48_hours",
    "escalated_at": "2025-11-17T10:00:00Z",
    "escalated_by": {
      "id": 123,
      "name": "John Doe"
    }
  },
  "sla": {
    "resolution_due": "2025-11-17T18:00:00Z",
    "escalated_sla": true
  },
  "correlation_id": "req-escalate-123"
}
```

---

## Search & Filters

### 9. Search Tickets

**Endpoint:** `GET /api/v2/helpdesk/tickets/search/`

**Purpose:** Natural language search with semantic matching

**Query Parameters:**
- `q`: Search query (natural language)
- `semantic`: Use AI search (default: true)
- `category`: Filter by category
- `status`: Filter by status
- `min_similarity`: Minimum similarity score (0.0-1.0, default: 0.5)

**Request:**
```
GET /api/v2/helpdesk/tickets/search/?q=GPS problems with check in&semantic=true&min_similarity=0.7
```

**Response (200 OK):**
```json
{
  "query": "GPS problems with check in",
  "search_type": "semantic",
  "results": [
    {
      "id": 9001,
      "ticket_number": "TKT-2025-11-9001",
      "subject": "Unable to check in - GPS error",
      "similarity_score": 0.94,
      "match_reason": "semantic_similarity",
      "highlighted_excerpt": "...GPS says I'm <mark>outside the geofence</mark>...",
      "status": "in_progress",
      "created_at": "2025-11-15T08:05:00Z"
    },
    {
      "id": 9000,
      "ticket_number": "TKT-2025-11-9000",
      "subject": "Check-in failing - location accuracy",
      "similarity_score": 0.87,
      "match_reason": "semantic_similarity",
      "highlighted_excerpt": "...GPS accuracy is <mark>poor</mark>, check-in <mark>fails</mark>...",
      "status": "resolved",
      "created_at": "2025-11-14T10:00:00Z",
      "resolution": {
        "summary": "Improved GPS accuracy by changing device settings",
        "resolved_at": "2025-11-14T14:30:00Z"
      }
    }
  ],
  "total_results": 2,
  "correlation_id": "req-search-555"
}
```

---

## Complete Workflows

### Workflow 1: Create → Track → Resolve Ticket

```
1. User encounters issue
   → Opens "Help & Support" screen
   → Taps "Report Issue"

2. Create ticket
   POST /api/v2/helpdesk/tickets/
   → Upload screenshot
   → Auto-categorized: "technical_issue"
   → Auto-assigned: Mobile Support Team
   → SLA: Response in 4 hours

3. Monitor ticket
   GET /api/v2/helpdesk/tickets/my-tickets/
   → Shows "Assigned to Support Agent"
   → Unread messages: 1
   → SLA countdown: 3h 25m remaining

4. Read agent response
   GET /api/v2/helpdesk/tickets/9001/
   → Agent: "Fixed geofence configuration"
   → Status: resolved

5. Test and confirm
   → User tries check-in again
   → Works successfully
   POST /api/v2/helpdesk/tickets/9001/close/
   → Rating: 5 stars
   → Ticket closed
```

### Workflow 2: Search Similar Tickets (Before Creating)

```
1. User about to create ticket
   → Enters subject: "GPS error"
   → App searches for similar tickets

2. Semantic search
   GET /api/v2/helpdesk/tickets/search/?q=GPS error checkin&semantic=true
   → Finds 2 similar resolved tickets
   → Shows: "Found similar issues - check these first"

3. User reads resolved ticket
   → "Fixed by enabling high-accuracy GPS mode"
   → User tries solution
   → Issue resolved without creating new ticket

4. If not resolved, create ticket
   → System links to similar tickets for agent context
```

---

## Data Model Summary

### Ticket Entity (Kotlin)

```kotlin
data class Ticket(
    val id: Long,
    val ticketNumber: String,
    val subject: String,
    val description: String,
    val category: TicketCategory,
    val priority: Priority,
    val severity: Severity,
    val status: TicketStatus,
    val requester: User,
    val assignedTo: User?,
    val assignedTeam: Team?,
    val sla: SlaStatus,
    val messages: List<TicketMessage>,
    val attachments: List<Attachment>,
    val history: List<AuditEntry>,
    val tags: List<String>,
    val relatedTickets: List<TicketSummary>,
    val sentimentAnalysis: SentimentAnalysis?,
    val createdAt: Instant,
    val updatedAt: Instant
)

enum class TicketStatus {
    NEW,
    OPEN,
    IN_PROGRESS,
    ON_HOLD,
    RESOLVED,
    CLOSED
}

enum class TicketCategory {
    TECHNICAL_ISSUE,
    FEATURE_REQUEST,
    BUG_REPORT,
    ACCOUNT_ISSUE,
    OTHER
}

enum class Severity {
    MINOR_INCONVENIENCE,
    IMPACTS_WORK,
    CRITICAL,
    SECURITY_ISSUE
}

data class SlaStatus(
    val responseDue: Instant,
    val resolutionDue: Instant,
    val firstResponseAt: Instant?,
    val resolvedAt: Instant?,
    val responseSlamet: Boolean?,
    val resolutionSlaMet: Boolean?,
    val breachRisk: BreachRisk,
    val minutesUntilBreach: Int?,
    val isBreached: Boolean
)

enum class BreachRisk {
    LOW, MEDIUM, HIGH
}
```

---

## Real-Time Updates

### WebSocket Events for Tickets

**Subscribe to ticket updates:**
```json
{
  "type": "subscribe",
  "channel": "ticket:9001"
}
```

**Server sends updates:**
```json
{
  "type": "ticket_updated",
  "ticket_id": 9001,
  "changes": {
    "status": {"old": "open", "new": "in_progress"},
    "assigned_to": {"old": null, "new": {"id": 789, "name": "Support Agent"}}
  },
  "timestamp": "2025-11-15T09:00:00Z"
}
```

**New message notification:**
```json
{
  "type": "new_message",
  "ticket_id": 9001,
  "message": {
    "id": 5002,
    "content": "Thanks for reporting. Checking geofence config...",
    "author": {"id": 789, "name": "Support Agent"},
    "created_at": "2025-11-15T09:00:00Z"
  }
}
```

---

## Error Scenarios

**Cannot update closed ticket:**
```json
{
  "error_code": "TICKET_CLOSED",
  "message": "Cannot update closed ticket",
  "current_status": "closed",
  "closed_at": "2025-11-15T15:00:00Z"
}
```

**Permission denied:**
```json
{
  "error_code": "PERMISSION_DENIED",
  "message": "You can only update your own tickets",
  "ticket_requester_id": 456,
  "your_user_id": 123
}
```

**Attachment too large:**
```json
{
  "error_code": "ATTACHMENT_TOO_LARGE",
  "max_size_bytes": 10485760,
  "uploaded_size_bytes": 15728640,
  "max_size_mb": 10
}
```

---

## Offline Support

### Create Ticket Offline

```
1. No network available
   → Store in pending queue with temp ID
   {
     "temp_id": "temp-ticket-{uuid}",
     "mobile_id": "device-android-abc123",
     "subject": "...",
     "description": "...",
     "attachments": [base64 data],
     "sync_status": "pending"
   }

2. Show in UI as "Pending Sync"

3. When online
   → Upload attachments first
   → Create ticket with attachment URLs
   → Update temp ID → real ID 9001

4. Conflict handling
   → If duplicate detected (similar subject+description)
   → Show: "Similar ticket already exists - merge or keep separate?"
```

---

## Testing Checklist

- [ ] Create ticket with attachments
- [ ] List my tickets with filters
- [ ] Get ticket details
- [ ] Update ticket priority
- [ ] Add message to ticket
- [ ] Close ticket with rating
- [ ] Search tickets (semantic)
- [ ] Subscribe to WebSocket updates
- [ ] Create ticket offline → sync
- [ ] Handle SLA countdown
- [ ] Request escalation
- [ ] View resolved similar tickets

---

**Document Version:** 1.0.0
**Last Updated:** November 7, 2025
**Next Review:** December 7, 2025
