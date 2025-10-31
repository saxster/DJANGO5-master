# API CONTRACT - WELLNESS & JOURNAL
## Wellbeing Tracking and Evidence-Based Interventions

**Version**: 1.0
**Last Updated**: October 30, 2025
**Base Path**: `/api/v1/wellness/`
**Domain**: Wellness & Journal
**Authentication**: Required (JWT Bearer token)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Data Models](#2-data-models)
3. [Journal Entries](#3-journal-entries)
4. [Wellness Content](#4-wellness-content)
5. [Analytics](#5-analytics)
6. [Privacy Settings](#6-privacy-settings)
7. [Media Attachments](#7-media-attachments)
8. [Complete Workflows](#8-complete-workflows)
9. [Error Scenarios](#9-error-scenarios)

---

## 1. Overview

### Purpose

The Wellness & Journal system provides:
- **Journal Entry Creation**: Mood, stress, energy tracking with reflections
- **Positive Psychology**: Gratitude, goals, affirmations, achievements
- **Evidence-Based Interventions**: Personalized wellness content based on patterns
- **Privacy Controls**: Granular privacy scopes (private → shared)
- **Real-Time Analytics**: Wellbeing trends and pattern detection

### Key Features

- **25+ Fields per Entry**: Comprehensive wellbeing data capture
- **13 Work Entry Types**: Site inspections, safety audits, training, etc.
- **11 Wellbeing Types**: Mood check-ins, gratitude, daily reflections, etc.
- **Privacy Hierarchy**: 5 levels (private, manager, team, aggregate, shared)
- **Offline Support**: Create entries offline, sync when reconnected
- **Media Attachments**: Photos, videos, audio recordings
- **Personalized Content**: AI-driven wellness recommendations

### Architecture Context

```
[Mobile App - Kotlin]
    ↓ Create journal entry offline
[SQLite - Local Cache]
    ↓ Sync when online
[Django API - /api/v1/wellness/]
    ↓ Validate, analyze patterns
[PostgreSQL - Source of Truth]
    ↓ Aggregate analytics
[Wellness Content Engine]
    ↓ Deliver personalized interventions
[Mobile App - Content Display]
```

---

## 2. Data Models

### 2.1 Journal Entry (Complete Schema)

**Model**: `JournalEntry`

**Fields**:

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `id` | UUID | Yes (server) | Primary key | Server-generated UUID |
| `user` | Integer | Yes | Foreign key | User ID (from auth) |
| `title` | String | Yes | Max 200 chars | Entry title |
| `subtitle` | String | No | Max 200 chars | Optional subtitle |
| `content` | String | No | Text field | Main content/reflection |
| `entry_type` | String | Yes | Choices (24 types) | Type of entry |
| `timestamp` | DateTime | Yes | ISO 8601 UTC | When entry occurred |
| `privacy_scope` | String | Yes | Choices (5 levels) | Privacy level |
| `consent_given` | Boolean | No | Default: false | Analytics consent |
| **Wellbeing Metrics** | | | | |
| `mood_rating` | Integer | No | 1-10 | Mood rating |
| `mood_description` | String | No | Max 100 chars | Mood description |
| `stress_level` | Integer | No | 1-5 | Stress level |
| `energy_level` | Integer | No | 1-10 | Energy level |
| `stress_triggers` | Array[String] | No | JSON | List of triggers |
| `coping_strategies` | Array[String] | No | JSON | Coping methods used |
| **Positive Psychology** | | | | |
| `gratitude_items` | Array[String] | No | JSON | Things grateful for |
| `daily_goals` | Array[String] | No | JSON | Goals for the day |
| `affirmations` | Array[String] | No | JSON | Positive affirmations |
| `achievements` | Array[String] | No | JSON | Accomplishments |
| `learnings` | Array[String] | No | JSON | Lessons learned |
| `challenges` | Array[String] | No | JSON | Challenges faced |
| **Location Context** | | | | |
| `location_site_name` | String | No | Max 200 chars | Site name |
| `location_address` | String | No | Text | Full address |
| `location_coordinates` | Object | No | {lat, lng} | GPS coordinates |
| `team_members` | Array[String] | No | JSON | Team member names |
| **Metadata** | | | | |
| `tags` | Array[String] | No | JSON | Custom tags |
| `is_bookmarked` | Boolean | No | Default: false | User bookmark |
| `is_draft` | Boolean | No | Default: false | Draft status |
| `is_deleted` | Boolean | No | Default: false | Soft delete |
| **Sync** | | | | |
| `mobile_id` | UUID | No | Unique | Client-generated ID |
| `version` | Integer | No | Default: 1 | Version for conflict resolution |
| `sync_status` | String | No | Choices | Sync status |
| `last_sync_timestamp` | DateTime | No | ISO 8601 UTC | Last sync time |
| **Audit** | | | | |
| `created_at` | DateTime | Yes | ISO 8601 UTC | Creation timestamp |
| `updated_at` | DateTime | Yes | ISO 8601 UTC | Last update timestamp |

### 2.2 Entry Type Choices

**Work-Related Types** (13):
- `site_inspection` - Site Inspection
- `equipment_maintenance` - Equipment Maintenance
- `safety_audit` - Safety Audit
- `training_completed` - Training Completed
- `project_milestone` - Project Milestone
- `team_collaboration` - Team Collaboration
- `client_interaction` - Client Interaction
- `process_improvement` - Process Improvement
- `documentation_update` - Documentation Update
- `field_observation` - Field Observation
- `quality_note` - Quality Note
- `investigation_note` - Investigation Note
- `safety_concern` - Safety Concern

**Wellbeing Types** (11):
- `mood_check_in` - Mood Check-In
- `gratitude` - Gratitude Journal
- `three_good_things` - Three Good Things
- `daily_affirmations` - Daily Affirmations
- `stress_log` - Stress Log
- `strength_spotting` - Strength Spotting
- `reframe_challenge` - Reframe Challenge
- `daily_intention` - Daily Intention
- `end_of_shift_reflection` - End of Shift Reflection
- `best_self_weekly` - Best Self Weekly
- `personal_reflection` - Personal Reflection

### 2.3 Privacy Scope Choices

| Value | Label | Description | Who Can See |
|-------|-------|-------------|-------------|
| `private` | Private | Only user | User only |
| `manager` | Manager | User + direct manager | User, manager |
| `team` | Team | User + team members | User, team |
| `aggregate` | Aggregate Only | Anonymized in analytics | No one (aggregate stats only) |
| `shared` | Shared | Public within organization | All org members |

### 2.4 Sync Status Choices

- `draft` - Draft (not submitted)
- `pending_sync` - Pending Sync (offline, waiting)
- `synced` - Synced (successfully synced)
- `sync_error` - Sync Error (failed to sync)
- `pending_delete` - Pending Delete (marked for deletion)

### 2.5 Wellness Content

**Model**: `WellnessContent`

| Field | Type | Description |
|-------|------|-------------|
| `id` | Integer | Primary key |
| `title` | String | Content title |
| `summary` | String | Brief summary (max 500 chars) |
| `content` | String | Full content (markdown) |
| `category` | String | Category (mental_health, physical_wellness, etc.) |
| `content_level` | String | Level (quick_tip, short_read, deep_dive) |
| `evidence_level` | String | Evidence level (who_cdc, peer_reviewed, expert_opinion) |
| `tags` | Array[String] | Tags |
| `workplace_specific` | Boolean | Workplace-specific content |
| `field_worker_relevant` | Boolean | Relevant to field workers |
| `action_tips` | Array[String] | Actionable tips |
| `key_takeaways` | Array[String] | Key takeaways |
| `source_name` | String | Source reference |
| `priority_score` | Integer | Priority (0-100) |
| `estimated_reading_time` | Integer | Minutes to read |
| `is_active` | Boolean | Active status |

---

## 3. Journal Entries

### 3.1 List Journal Entries

**Endpoint**: `GET /api/v1/wellness/journal/`

**Purpose**: Retrieve user's journal entries with filtering and pagination.

**Authentication**: Required

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entry_type` | String | No | Filter by entry type (e.g., `mood_check_in`) |
| `privacy_scope` | String | No | Filter by privacy scope |
| `is_draft` | Boolean | No | Filter by draft status |
| `is_bookmarked` | Boolean | No | Filter bookmarked entries |
| `start_date` | Date | No | Filter entries >= this date (YYYY-MM-DD) |
| `end_date` | Date | No | Filter entries <= this date (YYYY-MM-DD) |
| `search` | String | No | Search in title, content, tags |
| `ordering` | String | No | Sort field (e.g., `-created_at`, `mood_rating`) |
| `page` | Integer | No | Page number (default: 1) |
| `page_size` | Integer | No | Page size (default: 25, max: 100) |

**Request Example**:
```http
GET /api/v1/wellness/journal/?entry_type=mood_check_in&is_draft=false&page=1&page_size=25 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
Accept: application/json
```

**Response** (200 OK):
```json
{
  "count": 150,
  "next": "https://api.example.com/api/v1/wellness/journal/?entry_type=mood_check_in&is_draft=false&page=2&page_size=25",
  "previous": null,
  "results": [
    {
      "id": "abc-123-def-456",
      "title": "Morning reflection",
      "subtitle": "Starting the day with intention",
      "content": "Feeling energized after a good night's sleep. Ready to tackle today's inspection.",
      "entry_type": "mood_check_in",
      "timestamp": "2025-10-30T06:00:00Z",
      "privacy_scope": "private",
      "consent_given": true,
      "mood_rating": 8,
      "mood_description": "Energized and optimistic",
      "stress_level": 2,
      "energy_level": 8,
      "stress_triggers": [],
      "coping_strategies": ["morning exercise", "meditation"],
      "gratitude_items": [
        "Good health",
        "Supportive team",
        "Beautiful weather"
      ],
      "daily_goals": [
        "Complete site inspection",
        "Review safety reports",
        "Team check-in"
      ],
      "affirmations": [
        "I am capable and prepared",
        "I contribute value to my team"
      ],
      "achievements": [],
      "learnings": [],
      "challenges": [],
      "location_site_name": "Downtown Office Complex",
      "location_address": "123 Main St, City, State 12345",
      "location_coordinates": {
        "lat": 28.6139,
        "lng": 77.2090
      },
      "team_members": ["John Doe", "Jane Smith"],
      "tags": ["morning", "positive", "energy"],
      "is_bookmarked": false,
      "is_draft": false,
      "is_deleted": false,
      "mobile_id": "mobile-uuid-123",
      "version": 1,
      "sync_status": "synced",
      "last_sync_timestamp": "2025-10-30T06:01:00Z",
      "created_at": "2025-10-30T06:00:00Z",
      "updated_at": "2025-10-30T06:00:00Z"
    },
    {
      "id": "def-456-ghi-789",
      "title": "End of shift check-in",
      "subtitle": null,
      "content": "Long day but productive. Completed all inspections without issues.",
      "entry_type": "end_of_shift_reflection",
      "timestamp": "2025-10-29T18:00:00Z",
      "privacy_scope": "manager",
      "consent_given": true,
      "mood_rating": 7,
      "mood_description": "Tired but satisfied",
      "stress_level": 3,
      "energy_level": 4,
      "stress_triggers": ["tight schedule", "equipment delay"],
      "coping_strategies": ["deep breathing", "short break"],
      "gratitude_items": ["No safety incidents", "Team support"],
      "daily_goals": [],
      "affirmations": [],
      "achievements": [
        "Completed 8 inspections",
        "Identified potential safety issue",
        "Mentored new team member"
      ],
      "learnings": [
        "Early start helps avoid rush",
        "Equipment check saves time later"
      ],
      "challenges": [
        "Equipment delay at Site B",
        "Complex access requirements"
      ],
      "location_site_name": "Industrial Park Site B",
      "location_address": null,
      "location_coordinates": null,
      "team_members": ["Mike Johnson"],
      "tags": ["end-of-day", "reflection", "productive"],
      "is_bookmarked": true,
      "is_draft": false,
      "is_deleted": false,
      "mobile_id": null,
      "version": 1,
      "sync_status": "synced",
      "last_sync_timestamp": "2025-10-29T18:05:00Z",
      "created_at": "2025-10-29T18:00:00Z",
      "updated_at": "2025-10-29T18:00:00Z"
    }
  ]
}
```

**Error Responses**:

**401 Unauthorized**:
```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Token is invalid or expired",
    "details": null,
    "correlation_id": "abc-123-def-456"
  }
}
```

**400 Bad Request** (invalid filter):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query parameters",
    "details": {
      "entry_type": ["Invalid choice: 'invalid_type'"]
    },
    "correlation_id": "abc-123-def-789"
  }
}
```

---

### 3.2 Create Journal Entry

**Endpoint**: `POST /api/v1/wellness/journal/`

**Purpose**: Create a new journal entry with wellbeing metrics.

**Authentication**: Required

**Request Headers**:
```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "title": "Morning gratitude practice",
  "subtitle": "Three good things from yesterday",
  "content": "Reflecting on yesterday's positive moments before starting today.",
  "entry_type": "gratitude",
  "timestamp": "2025-10-30T07:00:00Z",
  "privacy_scope": "private",
  "consent_given": true,
  "mood_rating": 9,
  "mood_description": "Grateful and peaceful",
  "stress_level": 1,
  "energy_level": 8,
  "stress_triggers": [],
  "coping_strategies": [],
  "gratitude_items": [
    "Completed all tasks on time",
    "Received positive feedback from manager",
    "Enjoyed family dinner"
  ],
  "daily_goals": [
    "Maintain positive mindset",
    "Help colleague with new process",
    "Complete safety training"
  ],
  "affirmations": [
    "I am valued for my contributions",
    "I approach challenges with confidence"
  ],
  "achievements": [],
  "learnings": [],
  "challenges": [],
  "location_site_name": "Home",
  "location_address": null,
  "location_coordinates": null,
  "team_members": [],
  "tags": ["gratitude", "morning", "positive"],
  "is_bookmarked": false,
  "is_draft": false,
  "mobile_id": "mobile-uuid-abc-789"
}
```

**Field Requirements**:

**Required Fields**:
- `title` (1-200 chars)
- `entry_type` (valid choice from 24 types)
- `timestamp` (ISO 8601 UTC)
- `privacy_scope` (valid choice from 5 levels)

**Optional Fields** (all others)

**Validation Rules**:
- `mood_rating`: If provided, must be 1-10
- `stress_level`: If provided, must be 1-5
- `energy_level`: If provided, must be 1-10
- `timestamp`: Cannot be in the future (> now + 5 minutes grace period)
- `mobile_id`: If provided, must be unique UUID

**Request Example**:
```http
POST /api/v1/wellness/journal/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
Content-Type: application/json

{
  "title": "Morning reflection",
  "entry_type": "mood_check_in",
  "timestamp": "2025-10-30T06:00:00Z",
  "privacy_scope": "private",
  "mood_rating": 8,
  "stress_level": 2,
  "energy_level": 7,
  "gratitude_items": ["Good sleep", "Clear weather"]
}
```

**Response** (201 Created):
```json
{
  "id": "xyz-789-abc-123",
  "title": "Morning reflection",
  "subtitle": null,
  "content": null,
  "entry_type": "mood_check_in",
  "timestamp": "2025-10-30T06:00:00Z",
  "privacy_scope": "private",
  "consent_given": false,
  "mood_rating": 8,
  "mood_description": null,
  "stress_level": 2,
  "energy_level": 7,
  "stress_triggers": [],
  "coping_strategies": [],
  "gratitude_items": ["Good sleep", "Clear weather"],
  "daily_goals": [],
  "affirmations": [],
  "achievements": [],
  "learnings": [],
  "challenges": [],
  "location_site_name": null,
  "location_address": null,
  "location_coordinates": null,
  "team_members": [],
  "tags": [],
  "is_bookmarked": false,
  "is_draft": false,
  "is_deleted": false,
  "mobile_id": "mobile-uuid-abc-789",
  "version": 1,
  "sync_status": "synced",
  "last_sync_timestamp": "2025-10-30T06:00:30Z",
  "created_at": "2025-10-30T06:00:30Z",
  "updated_at": "2025-10-30T06:00:30Z"
}
```

**Error Responses**:

**400 Bad Request** (validation error):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "title": ["This field is required."],
      "mood_rating": ["Ensure this value is less than or equal to 10."],
      "timestamp": ["Timestamp cannot be in the future."]
    },
    "correlation_id": "abc-123-def-012"
  }
}
```

**409 Conflict** (duplicate mobile_id):
```json
{
  "error": {
    "code": "DUPLICATE_ENTRY",
    "message": "Entry with this mobile_id already exists",
    "details": {
      "mobile_id": "mobile-uuid-abc-789",
      "existing_entry_id": "xyz-789-abc-123"
    },
    "correlation_id": "abc-123-def-345"
  }
}
```

---

### 3.3 Get Journal Entry

**Endpoint**: `GET /api/v1/wellness/journal/{id}/`

**Purpose**: Retrieve a specific journal entry by ID.

**Authentication**: Required

**Path Parameters**:
- `id` (UUID): Entry ID

**Request Example**:
```http
GET /api/v1/wellness/journal/abc-123-def-456/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
Accept: application/json
```

**Response** (200 OK):
```json
{
  "id": "abc-123-def-456",
  "title": "Morning reflection",
  "subtitle": "Starting the day with intention",
  "content": "Feeling energized after a good night's sleep...",
  "entry_type": "mood_check_in",
  "timestamp": "2025-10-30T06:00:00Z",
  "privacy_scope": "private",
  "mood_rating": 8,
  "stress_level": 2,
  "energy_level": 8,
  "gratitude_items": ["Good health", "Supportive team", "Beautiful weather"],
  "daily_goals": ["Complete site inspection", "Review safety reports"],
  "tags": ["morning", "positive", "energy"],
  "created_at": "2025-10-30T06:00:00Z",
  "updated_at": "2025-10-30T06:00:00Z"
}
```

**Error Responses**:

**404 Not Found**:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Journal entry not found",
    "details": null,
    "correlation_id": "abc-123-def-678"
  }
}
```

**403 Forbidden** (not owner):
```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "You do not have permission to view this entry",
    "details": null,
    "correlation_id": "abc-123-def-901"
  }
}
```

---

### 3.4 Update Journal Entry

**Endpoint**: `PATCH /api/v1/wellness/journal/{id}/`

**Purpose**: Partially update a journal entry.

**Authentication**: Required

**Path Parameters**:
- `id` (UUID): Entry ID

**Request Body** (partial update):
```json
{
  "mood_rating": 9,
  "gratitude_items": ["Good health", "Team support", "Progress on goals"],
  "tags": ["morning", "positive", "energy", "growth"]
}
```

**Request Example**:
```http
PATCH /api/v1/wellness/journal/abc-123-def-456/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
Content-Type: application/json

{
  "mood_rating": 9,
  "is_bookmarked": true
}
```

**Response** (200 OK):
```json
{
  "id": "abc-123-def-456",
  "title": "Morning reflection",
  "mood_rating": 9,
  "is_bookmarked": true,
  "version": 2,
  "updated_at": "2025-10-30T06:30:00Z",
  ...
}
```

**Error Responses**:

**400 Bad Request** (validation error):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "mood_rating": ["Ensure this value is less than or equal to 10."]
    },
    "correlation_id": "abc-123-def-234"
  }
}
```

**409 Conflict** (version mismatch):
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Entry has been modified. Please refresh and try again.",
    "details": {
      "client_version": 1,
      "server_version": 3
    },
    "correlation_id": "abc-123-def-567"
  }
}
```

---

### 3.5 Delete Journal Entry

**Endpoint**: `DELETE /api/v1/wellness/journal/{id}/`

**Purpose**: Soft delete a journal entry (sets `is_deleted = True`).

**Authentication**: Required

**Path Parameters**:
- `id` (UUID): Entry ID

**Request Example**:
```http
DELETE /api/v1/wellness/journal/abc-123-def-456/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (204 No Content):
```
(Empty body)
```

**Error Responses**:

**404 Not Found**:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Journal entry not found",
    "details": null,
    "correlation_id": "abc-123-def-890"
  }
}
```

---

## 4. Wellness Content

### 4.1 List Wellness Content

**Endpoint**: `GET /api/v1/wellness/content/`

**Purpose**: Retrieve wellness content with filtering.

**Authentication**: Required

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | String | Filter by category |
| `content_level` | String | Filter by level (quick_tip, short_read, deep_dive) |
| `workplace_specific` | Boolean | Filter workplace-specific content |
| `field_worker_relevant` | Boolean | Filter field worker content |
| `search` | String | Search in title, summary, content |
| `page` | Integer | Page number |
| `page_size` | Integer | Page size |

**Request Example**:
```http
GET /api/v1/wellness/content/?category=mental_health&content_level=quick_tip&page=1&page_size=10 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (200 OK):
```json
{
  "count": 45,
  "next": "https://api.example.com/api/v1/wellness/content/?category=mental_health&page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "title": "5-Minute Stress Relief Technique",
      "summary": "Quick breathing exercise to reduce stress during your workday.",
      "content": "# 5-Minute Stress Relief\n\n## Overview\nThis simple technique can help you reset...",
      "category": "mental_health",
      "content_level": "quick_tip",
      "evidence_level": "peer_reviewed",
      "tags": ["stress", "breathing", "quick"],
      "workplace_specific": true,
      "field_worker_relevant": true,
      "action_tips": [
        "Find a quiet spot for 5 minutes",
        "Close your eyes and focus on breathing",
        "Inhale for 4 counts, exhale for 6 counts"
      ],
      "key_takeaways": [
        "Controlled breathing activates relaxation response",
        "Can be done anywhere, anytime",
        "Regular practice improves resilience"
      ],
      "source_name": "Journal of Occupational Health Psychology",
      "priority_score": 85,
      "estimated_reading_time": 3,
      "is_active": true
    },
    {
      "id": 124,
      "title": "Gratitude Practice for Better Sleep",
      "summary": "End your day with gratitude to improve sleep quality and next-day mood.",
      "content": "# Gratitude Practice\n\n## Why It Works\nResearch shows...",
      "category": "mental_health",
      "content_level": "short_read",
      "evidence_level": "who_cdc",
      "tags": ["gratitude", "sleep", "wellbeing"],
      "workplace_specific": false,
      "field_worker_relevant": true,
      "action_tips": [
        "Write 3 things you're grateful for before bed",
        "Be specific and detailed",
        "Reflect on why each matters to you"
      ],
      "key_takeaways": [
        "Gratitude shifts focus from problems to positives",
        "Improves sleep quality by reducing worry",
        "Consistent practice increases overall wellbeing"
      ],
      "source_name": "CDC Workplace Health Promotion",
      "priority_score": 78,
      "estimated_reading_time": 5,
      "is_active": true
    }
  ]
}
```

---

### 4.2 Get Daily Wellness Tip

**Endpoint**: `GET /api/v1/wellness/content/daily-tip/`

**Purpose**: Get a single daily wellness tip (rotates daily).

**Authentication**: Required

**Request Example**:
```http
GET /api/v1/wellness/content/daily-tip/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (200 OK):
```json
{
  "id": 125,
  "title": "Stay Hydrated for Better Focus",
  "summary": "Even mild dehydration can impair concentration. Aim for 8 glasses of water daily.",
  "content": "# Hydration and Cognitive Performance\n\n## The Science\n...",
  "category": "physical_wellness",
  "content_level": "quick_tip",
  "action_tips": [
    "Keep water bottle visible at workstation",
    "Set hourly reminders to drink",
    "Add fruit slices for flavor"
  ],
  "estimated_reading_time": 2,
  "created_date": "2025-10-30"
}
```

---

### 4.3 Get Personalized Content

**Endpoint**: `GET /api/v1/wellness/content/personalized/`

**Purpose**: Get wellness content personalized based on user's recent journal patterns.

**Authentication**: Required

**Query Parameters**:
- `limit` (Integer): Max items to return (default: 5, max: 20)

**Request Example**:
```http
GET /api/v1/wellness/content/personalized/?limit=5 HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (200 OK):
```json
{
  "personalization_reason": "Based on your recent stress levels and sleep patterns",
  "recommended_content": [
    {
      "id": 126,
      "title": "Progressive Muscle Relaxation for Better Sleep",
      "summary": "Reduce physical tension before bed to improve sleep quality.",
      "match_reason": "You've reported high stress (4-5) for 3 consecutive days",
      "priority_score": 92,
      "estimated_reading_time": 7
    },
    {
      "id": 127,
      "title": "Setting Boundaries at Work",
      "summary": "Protect your energy by establishing healthy work boundaries.",
      "match_reason": "Your entries show signs of work overload",
      "priority_score": 88,
      "estimated_reading_time": 10
    }
  ]
}
```

**Personalization Logic**:
- Analyzes last 30 days of journal entries
- Identifies patterns: low mood, high stress, specific triggers
- Recommends evidence-based interventions
- Prioritizes actionable, field-worker-relevant content

---

## 5. Analytics

### 5.1 Get My Wellness Progress

**Endpoint**: `GET /api/v1/wellness/analytics/my-progress/`

**Purpose**: Get user's personal wellness metrics and trends.

**Authentication**: Required

**Query Parameters**:
- `period` (String): Time period (`week`, `month`, `quarter`, `year`) - Default: `month`
- `metrics` (String, comma-separated): Metrics to include (e.g., `mood,stress,energy`)

**Request Example**:
```http
GET /api/v1/wellness/analytics/my-progress/?period=month&metrics=mood,stress,energy HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (200 OK):
```json
{
  "period": "month",
  "start_date": "2025-10-01",
  "end_date": "2025-10-30",
  "entry_count": 28,
  "metrics": {
    "mood": {
      "average": 7.2,
      "trend": "improving",
      "data_points": [
        {"date": "2025-10-01", "value": 6},
        {"date": "2025-10-02", "value": 7},
        {"date": "2025-10-03", "value": 7},
        ...
      ],
      "insights": [
        "Mood has improved 15% compared to last month",
        "Best mood days: Tuesdays and Wednesdays",
        "Lowest mood: Monday mornings (avg 5.8)"
      ]
    },
    "stress": {
      "average": 2.8,
      "trend": "stable",
      "data_points": [
        {"date": "2025-10-01", "value": 3},
        {"date": "2025-10-02", "value": 2},
        ...
      ],
      "insights": [
        "Stress levels within healthy range (1-3)",
        "Spike on Oct 15 (equipment failure day)",
        "Effective coping: breathing exercises, short breaks"
      ]
    },
    "energy": {
      "average": 6.8,
      "trend": "improving",
      "data_points": [...],
      "insights": [
        "Morning energy consistently high (avg 8.2)",
        "End-of-day energy improved with regular breaks",
        "Correlates with good sleep (7+ hours)"
      ]
    }
  },
  "top_gratitude_themes": [
    {"theme": "team support", "count": 18},
    {"theme": "accomplishments", "count": 15},
    {"theme": "good health", "count": 12}
  ],
  "most_common_stressors": [
    {"trigger": "tight deadlines", "count": 8},
    {"trigger": "equipment issues", "count": 6},
    {"trigger": "communication gaps", "count": 4}
  ],
  "effective_coping_strategies": [
    {"strategy": "deep breathing", "count": 12},
    {"strategy": "short walk", "count": 9},
    {"strategy": "talking to colleague", "count": 7}
  ],
  "recommendations": [
    "Continue morning gratitude practice - it's working!",
    "Consider proactive communication about deadlines",
    "Schedule equipment checks earlier in the day"
  ]
}
```

---

### 5.2 Get Wellbeing Analytics (Admin/Manager)

**Endpoint**: `GET /api/v1/wellness/analytics/wellbeing-analytics/`

**Purpose**: Get aggregated, anonymized wellbeing metrics for team/organization.

**Authentication**: Required (Admin or Manager role)

**Permissions**: `view_analytics` capability

**Query Parameters**:
- `period` (String): `week`, `month`, `quarter`, `year`
- `bu_id` (Integer): Business unit filter (optional)
- `site_id` (Integer): Site filter (optional)
- `aggregation` (String): `team`, `site`, `bu`, `org` - Default: current user's scope

**Request Example**:
```http
GET /api/v1/wellness/analytics/wellbeing-analytics/?period=month&aggregation=team HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (200 OK):
```json
{
  "period": "month",
  "start_date": "2025-10-01",
  "end_date": "2025-10-30",
  "aggregation": "team",
  "participant_count": 45,
  "participation_rate": 0.78,
  "privacy_note": "All data is aggregated and anonymized. Individual entries cannot be identified.",
  "aggregate_metrics": {
    "mood": {
      "average": 7.1,
      "median": 7,
      "std_dev": 1.2,
      "distribution": {
        "1-3": 5,
        "4-6": 12,
        "7-8": 18,
        "9-10": 10
      },
      "trend": "stable"
    },
    "stress": {
      "average": 2.9,
      "median": 3,
      "std_dev": 0.8,
      "high_stress_percentage": 18,
      "trend": "improving"
    },
    "energy": {
      "average": 6.9,
      "median": 7,
      "std_dev": 1.1,
      "trend": "improving"
    }
  },
  "common_themes": {
    "gratitude": [
      {"theme": "team collaboration", "frequency": 0.42},
      {"theme": "accomplishments", "frequency": 0.38},
      {"theme": "recognition", "frequency": 0.31}
    ],
    "stressors": [
      {"trigger": "workload", "frequency": 0.33},
      {"trigger": "time pressure", "frequency": 0.29},
      {"trigger": "equipment issues", "frequency": 0.22}
    ],
    "coping_strategies": [
      {"strategy": "peer support", "frequency": 0.41},
      {"strategy": "breaks", "frequency": 0.36},
      {"strategy": "physical activity", "frequency": 0.28}
    ]
  },
  "alerts": [
    {
      "type": "high_stress_cluster",
      "severity": "medium",
      "description": "18% of team reporting stress levels 4-5",
      "recommendation": "Consider workload review and stress management resources"
    }
  ],
  "recommendations": [
    "Team shows strong peer support culture - maintain this",
    "Equipment issues recurring - proactive maintenance may help",
    "Consider flexible scheduling during high-workload periods"
  ]
}
```

**Privacy Safeguards**:
- No individual entries exposed
- Minimum 5 participants for any aggregation
- No correlation to specific individuals
- Timestamps aggregated to daily/weekly
- Names/locations removed

---

## 6. Privacy Settings

### 6.1 Get Privacy Settings

**Endpoint**: `GET /api/v1/wellness/privacy/`

**Purpose**: Get user's current privacy settings.

**Authentication**: Required

**Request Example**:
```http
GET /api/v1/wellness/privacy/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (200 OK):
```json
{
  "user_id": 456,
  "analytics_consent": true,
  "pattern_analysis_consent": true,
  "crisis_intervention_enabled": true,
  "data_retention_days": 365,
  "sharing_enabled": false,
  "last_updated": "2025-10-01T10:00:00Z"
}
```

---

### 6.2 Update Privacy Settings

**Endpoint**: `PATCH /api/v1/wellness/privacy/`

**Purpose**: Update user's privacy settings.

**Authentication**: Required

**Request Body**:
```json
{
  "analytics_consent": false,
  "pattern_analysis_consent": false,
  "crisis_intervention_enabled": true
}
```

**Request Example**:
```http
PATCH /api/v1/wellness/privacy/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
Content-Type: application/json

{
  "analytics_consent": false
}
```

**Response** (200 OK):
```json
{
  "user_id": 456,
  "analytics_consent": false,
  "pattern_analysis_consent": true,
  "crisis_intervention_enabled": true,
  "data_retention_days": 365,
  "sharing_enabled": false,
  "last_updated": "2025-10-30T08:00:00Z"
}
```

**Effect of Settings**:
- `analytics_consent: false` → Excludes from aggregate analytics
- `pattern_analysis_consent: false` → No personalized content recommendations
- `crisis_intervention_enabled: false` → No proactive wellness alerts
- `data_retention_days: 90` → Entries older than 90 days auto-deleted

---

## 7. Media Attachments

### 7.1 Upload Media to Journal Entry

**Endpoint**: `POST /api/v1/wellness/journal/{entry_id}/media/`

**Purpose**: Upload photo, video, or audio attachment to a journal entry.

**Authentication**: Required

**Content-Type**: `multipart/form-data`

**Path Parameters**:
- `entry_id` (UUID): Journal entry ID

**Form Data**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Media file |
| `media_type` | String | Yes | `PHOTO`, `VIDEO`, `AUDIO`, `DOCUMENT` |
| `caption` | String | No | Caption (max 500 chars) |
| `display_order` | Integer | No | Display order (default: 0) |
| `is_hero_image` | Boolean | No | Hero image flag (default: false) |

**Validation**:
- **Photos**: .jpg, .jpeg, .png, .gif, .webp (max 10 MB)
- **Videos**: .mp4, .mov, .avi, .webm (max 100 MB)
- **Audio**: .mp3, .wav, .m4a, .aac, .ogg (max 50 MB)
- **Documents**: .pdf (max 25 MB)

**Request Example**:
```http
POST /api/v1/wellness/journal/abc-123-def-456/media/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="inspection_photo.jpg"
Content-Type: image/jpeg

[binary data]
------WebKitFormBoundary
Content-Disposition: form-data; name="media_type"

PHOTO
------WebKitFormBoundary
Content-Disposition: form-data; name="caption"

Equipment condition - all systems operational
------WebKitFormBoundary--
```

**Response** (201 Created):
```json
{
  "id": "media-uuid-123",
  "journal_entry": "abc-123-def-456",
  "file": "https://cdn.example.com/media/journal/2025/10/30/inspection_photo.jpg",
  "original_filename": "inspection_photo.jpg",
  "mime_type": "image/jpeg",
  "file_size": 245678,
  "media_type": "PHOTO",
  "caption": "Equipment condition - all systems operational",
  "display_order": 0,
  "is_hero_image": false,
  "created_at": "2025-10-30T09:00:00Z"
}
```

**Error Responses**:

**400 Bad Request** (invalid file type):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid file type",
    "details": {
      "file": ["File extension '.exe' not allowed. Allowed: .jpg, .jpeg, .png, .gif, .webp"]
    },
    "correlation_id": "abc-123-def-111"
  }
}
```

**413 Payload Too Large**:
```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File exceeds maximum size",
    "details": {
      "file_size": 12000000,
      "max_size": 10000000,
      "media_type": "PHOTO"
    },
    "correlation_id": "abc-123-def-222"
  }
}
```

---

### 7.2 List Entry Media

**Endpoint**: `GET /api/v1/wellness/journal/{entry_id}/media/`

**Purpose**: List all media attachments for a journal entry.

**Authentication**: Required

**Request Example**:
```http
GET /api/v1/wellness/journal/abc-123-def-456/media/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (200 OK):
```json
[
  {
    "id": "media-uuid-123",
    "file": "https://cdn.example.com/media/journal/2025/10/30/inspection_photo.jpg",
    "media_type": "PHOTO",
    "caption": "Equipment condition - all systems operational",
    "display_order": 0,
    "is_hero_image": true,
    "created_at": "2025-10-30T09:00:00Z"
  },
  {
    "id": "media-uuid-456",
    "file": "https://cdn.example.com/media/journal/2025/10/30/safety_notes.pdf",
    "media_type": "DOCUMENT",
    "caption": "Safety checklist completed",
    "display_order": 1,
    "is_hero_image": false,
    "created_at": "2025-10-30T09:05:00Z"
  }
]
```

---

### 7.3 Delete Media

**Endpoint**: `DELETE /api/v1/wellness/journal/{entry_id}/media/{media_id}/`

**Purpose**: Delete a media attachment.

**Authentication**: Required

**Request Example**:
```http
DELETE /api/v1/wellness/journal/abc-123-def-456/media/media-uuid-123/ HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJ0eXAiOiJKV1Qi...
```

**Response** (204 No Content):
```
(Empty body)
```

---

## 8. Complete Workflows

### 8.1 Morning Mood Check-In Workflow

**Use Case**: User starts their day with a mood check-in on mobile app.

**Steps**:

**1. User Opens App (Offline)**

**2. Create Entry (Local Cache)**
```json
POST /api/v1/wellness/journal/ (queued offline)
{
  "title": "Morning check-in",
  "entry_type": "mood_check_in",
  "timestamp": "2025-10-30T06:00:00Z",
  "privacy_scope": "private",
  "mood_rating": 8,
  "stress_level": 2,
  "energy_level": 7,
  "gratitude_items": ["Good sleep", "Clear day ahead"],
  "mobile_id": "mobile-uuid-morning-123"
}
```

**3. App Saves to SQLite**
```sql
INSERT INTO journal_entry_local (
  id, mobile_id, title, entry_type, mood_rating, stress_level, energy_level,
  gratitude_items_json, sync_status, created_at
) VALUES (
  'temp-local-id', 'mobile-uuid-morning-123', 'Morning check-in', 'mood_check_in',
  8, 2, 7, '["Good sleep", "Clear day ahead"]', 'pending_sync', 1730268000000
);
```

**4. UI Shows Entry Immediately** (with "syncing" indicator)

**5. Background Sync (When Online)**
```http
POST /api/v1/wellness/journal/ HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Morning check-in",
  "entry_type": "mood_check_in",
  "timestamp": "2025-10-30T06:00:00Z",
  "privacy_scope": "private",
  "mood_rating": 8,
  "stress_level": 2,
  "energy_level": 7,
  "gratitude_items": ["Good sleep", "Clear day ahead"],
  "mobile_id": "mobile-uuid-morning-123"
}
```

**6. Server Response** (201 Created)
```json
{
  "id": "server-uuid-abc-123",
  "title": "Morning check-in",
  "mobile_id": "mobile-uuid-morning-123",
  "version": 1,
  "sync_status": "synced",
  "created_at": "2025-10-30T06:00:30Z",
  ...
}
```

**7. Update Local Cache**
```sql
UPDATE journal_entry_local
SET id = 'server-uuid-abc-123', sync_status = 'synced', last_sync_timestamp = 1730268030000
WHERE mobile_id = 'mobile-uuid-morning-123';
```

**8. UI Updates** (remove "syncing" indicator)

---

### 8.2 End-of-Day Reflection with Photo

**Use Case**: User completes shift, adds reflection with inspection photo.

**Steps**:

**1. Create Entry**
```http
POST /api/v1/wellness/journal/ HTTP/1.1
Authorization: Bearer <token>

{
  "title": "End of shift - Site B",
  "entry_type": "end_of_shift_reflection",
  "timestamp": "2025-10-30T18:00:00Z",
  "privacy_scope": "manager",
  "mood_rating": 7,
  "stress_level": 3,
  "energy_level": 4,
  "achievements": ["Completed 8 inspections", "Identified safety issue"],
  "challenges": ["Equipment delay at Site B"],
  "location_site_name": "Industrial Park Site B"
}
```

**2. Response** (201 Created)
```json
{
  "id": "entry-uuid-evening-456",
  ...
}
```

**3. Upload Photo**
```http
POST /api/v1/wellness/journal/entry-uuid-evening-456/media/ HTTP/1.1
Authorization: Bearer <token>
Content-Type: multipart/form-data

[file: inspection_complete.jpg]
[media_type: PHOTO]
[caption: Final inspection - all clear]
```

**4. Response** (201 Created)
```json
{
  "id": "media-uuid-photo-789",
  "file": "https://cdn.example.com/media/journal/2025/10/30/inspection_complete.jpg",
  "media_type": "PHOTO",
  "caption": "Final inspection - all clear",
  ...
}
```

**5. Manager Reviews** (privacy_scope: manager)
```http
GET /api/v1/wellness/journal/entry-uuid-evening-456/ HTTP/1.1
Authorization: Bearer <manager_token>
```

Manager sees entry (because privacy_scope = "manager")

---

### 8.3 Personalized Content Recommendation

**Use Case**: System detects high stress pattern, recommends content.

**Trigger**: User logs 3+ consecutive days with stress_level >= 4

**1. User Opens App**

**2. Fetch Personalized Content**
```http
GET /api/v1/wellness/content/personalized/?limit=3 HTTP/1.1
Authorization: Bearer <token>
```

**3. Response** (200 OK)
```json
{
  "personalization_reason": "Based on your recent stress levels",
  "recommended_content": [
    {
      "id": 126,
      "title": "Quick Stress Relief Techniques",
      "summary": "5-minute exercises to reduce stress during your shift",
      "match_reason": "You've reported high stress for 3 days",
      "priority_score": 92,
      "estimated_reading_time": 5
    },
    {
      "id": 127,
      "title": "Managing Workload Pressure",
      "summary": "Strategies for handling tight deadlines",
      "match_reason": "Your entries mention 'tight schedule'",
      "priority_score": 88,
      "estimated_reading_time": 8
    }
  ]
}
```

**4. User Reads Content**
```http
GET /api/v1/wellness/content/126/ HTTP/1.1
Authorization: Bearer <token>
```

**5. User Applies Technique**

**6. Next Day - Lower Stress**
```json
POST /api/v1/wellness/journal/
{
  "title": "Feeling better today",
  "entry_type": "mood_check_in",
  "stress_level": 2,
  "coping_strategies": ["breathing exercise from wellness app"]
}
```

---

## 9. Error Scenarios

### 9.1 Field-Level Validation Errors

**Request** (multiple validation errors):
```json
POST /api/v1/wellness/journal/
{
  "title": "",
  "entry_type": "invalid_type",
  "timestamp": "2025-11-30T10:00:00Z",
  "privacy_scope": "private",
  "mood_rating": 15,
  "stress_level": 10
}
```

**Response** (400 Bad Request):
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "title": ["This field may not be blank."],
      "entry_type": ["Invalid choice: 'invalid_type'. Choose from: mood_check_in, gratitude, ..."],
      "timestamp": ["Timestamp cannot be in the future."],
      "mood_rating": ["Ensure this value is less than or equal to 10."],
      "stress_level": ["Ensure this value is less than or equal to 5."]
    },
    "correlation_id": "abc-123-validation-001"
  }
}
```

---

### 9.2 Conflict Resolution (Concurrent Edits)

**Scenario**: User edits entry offline while server version also changes.

**Client State** (version 2):
```json
{
  "id": "entry-uuid-123",
  "title": "Updated title (client)",
  "mood_rating": 9,
  "version": 2,
  "updated_at": "2025-10-30T10:05:00Z"
}
```

**Server State** (version 2):
```json
{
  "id": "entry-uuid-123",
  "title": "Updated title (server)",
  "mood_rating": 7,
  "version": 2,
  "updated_at": "2025-10-30T10:03:00Z"
}
```

**Client Attempts Update**:
```http
PATCH /api/v1/wellness/journal/entry-uuid-123/ HTTP/1.1
{
  "title": "Updated title (client)",
  "mood_rating": 9,
  "version": 2
}
```

**Response** (409 Conflict):
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Entry has been modified. Please refresh and try again.",
    "details": {
      "client_version": 2,
      "server_version": 2,
      "server_updated_at": "2025-10-30T10:03:00Z",
      "client_updated_at": "2025-10-30T10:05:00Z",
      "conflict_resolution": "last_write_wins",
      "winner": "client"
    },
    "correlation_id": "abc-123-conflict-001"
  }
}
```

**Resolution**: Last-write-wins → Client wins (later timestamp)

**Server Accepts**:
```json
{
  "id": "entry-uuid-123",
  "title": "Updated title (client)",
  "mood_rating": 9,
  "version": 3,
  "updated_at": "2025-10-30T10:06:00Z"
}
```

---

### 9.3 Rate Limiting

**Scenario**: User creates 100+ entries in 1 minute (automated script?)

**Response** (429 Too Many Requests):
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Request was throttled. Expected available in 3540 seconds.",
    "details": {
      "retry_after": 3540,
      "rate_limit": "600 requests per hour",
      "current_usage": 600,
      "window_reset": "2025-10-30T11:00:00Z"
    },
    "correlation_id": "abc-123-rate-limit-001"
  }
}
```

**Headers**:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 3540
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1730282400
```

---

## Summary

This contract defines the complete WELLNESS & JOURNAL API:

✅ **25+ Fields**: Comprehensive wellbeing data capture
✅ **24 Entry Types**: Work + wellbeing entries
✅ **5 Privacy Levels**: Private → shared
✅ **CRUD Operations**: Create, read, update, delete
✅ **Media Attachments**: Photos, videos, audio, documents
✅ **Personalized Content**: AI-driven recommendations
✅ **Analytics**: Personal progress + aggregated team insights
✅ **Privacy Controls**: Granular consent management
✅ **Offline Support**: mobile_id, version tracking, conflict resolution
✅ **Complete Workflows**: 3 end-to-end scenarios
✅ **Error Scenarios**: Validation, conflicts, rate limiting

**Reference Documents**:
- [API_CONTRACT_FOUNDATION.md](./API_CONTRACT_FOUNDATION.md) - Auth, errors, pagination
- [MAPPING_GUIDE.md](./MAPPING_GUIDE.md) - Data transformations
- [KOTLIN_PRD_SUMMARY.md](./KOTLIN_PRD_SUMMARY.md) - Implementation architecture

---

**Document Version**: 1.0
**Last Reviewed**: October 30, 2025
**Maintainer**: Backend & Mobile Teams
**Next Review**: Quarterly or on API changes
