# Android Calendar Integration Handoff

_Last updated: November 9, 2025_

## Endpoint Summary

- **URL**: `/api/v2/calendar/events/`
- **Method**: `GET`
- **Auth**: Bearer token (existing v2 JWT)
- **Scope**: Multi-tenant, RBAC aligned with backend filters

### Supported Filters

| Param | Type | Notes |
|-------|------|-------|
| `start` / `end` | ISO8601 datetime (UTC) | Required; max window 31 days |
| `event_types` | list of strings | `ATTENDANCE`, `TASK`, `TOUR`, `INSPECTION`, `INCIDENT`, `MAINTENANCE`, `TICKET`, `JOURNAL` |
| `statuses` | list of strings | `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `OVERDUE`, `CANCELLED`, `FAILED` |
| `context_type` | string | `USER`, `SITE`, `ASSET`, `TEAM`, `CLIENT`, `SHIFT`; optional |
| `context_id` | integer | Required when `context_type` (except default `USER`) |
| `search` | string | Optional free-text search |
| `page` / `page_size` | integer | Defaults 1 / 25, max size 100 |

### Response Structure

```
{
  "success": true,
  "data": {
    "count": 42,
    "next": "...",
    "previous": null,
    "page_size": 25,
    "total_pages": 2,
    "current_page": 1,
    "results": [
      {
        "id": "jobneed:98123",
        "event_type": "TASK",
        "status": "IN_PROGRESS",
        "title": "Perimeter Patrol",
        "subtitle": "Gate 3",
        "start": "2025-11-09T09:00:00Z",
        "end": "2025-11-09T09:30:00Z",
        "related_entity_type": "JOBNEED",
        "related_entity_id": 98123,
        "location": "Harbor Tower",
        "assigned_user_id": 445,
        "metadata": {
          "priority": "HIGH",
          "ticket_id": 882,
          "identifier": "INTERNALTOUR"
        }
      }
    ],
    "summary": {
      "by_type": {"TASK": 12, "ATTENDANCE": 6},
      "by_status": {"COMPLETED": 14, "IN_PROGRESS": 4}
    }
  },
  "meta": {
    "correlation_id": "c2e4d3d9-..."
  }
}
```

`event_type` drives iconography; `status` maps to color coding. `related_entity_type` + `related_entity_id` enable deep links to module screens.

## Implementation Steps for Android Team

1. **Networking**
   - Add Retrofit entry `GET /api/v2/calendar/events/` with query DTO.
   - Reuse shared interceptors + auth stack.

2. **Data Layer**
   - DTO → domain mapper producing `CalendarEvent` sealed hierarchy if needed.
   - Room cache table keyed by `(context_type, context_id, date_bucket)` for offline agenda.
   - Repository exposing `Flow<PagingData<CalendarEvent>>` with summary side channel.

3. **View Models**
   - `CalendarTimelineViewModel` that:
     - Tracks filters (type + status) and context selection.
     - Exposes chips populated via `summary.by_type` / `summary.by_status`.
     - Handles background refresh (pull-to-refresh + periodic sync).

4. **UI**
   - Day/agenda hybrid layout (virtualized list + sticky day headers).
   - Quick filters: type (Task, Tour, Ticket...) and status (Scheduled, In Progress...).
   - Event cards per `event_type` with CTA buttons:
     - Task/Tour → open jobneed detail.
     - Attendance → show shift timeline.
     - Ticket → open helpdesk thread.
     - Journal → open wellbeing entry.

5. **State Handling**
   - Cache last 7 days +/- 3 days in memory.
   - Use `page_size=50` for infinite scroll.
   - Deduplicate events by `id` when merging cached + fresh pages.

6. **Error & Offline UX**
   - On 401/403: force re-auth.
   - On 429 / 5xx: show retry snackbar and exponential backoff.
   - Display cached data when offline; badge events that failed to refresh.

7. **QA Checklist**
   - My Calendar vs Site vs Asset context switching.
   - Mixed event feed (attendance + tasks + tickets) on same day.
   - Search filtering (title/location/metadata matches).
   - Pagination + pull-to-refresh interplay.
   - Accessibility: content descriptions for icons, talkback order inside cards.

8. **Telemetry**
   - Emit analytics events: `calendar_view_loaded`, `calendar_filter_applied`, `calendar_event_clicked` with payload `{event_type, status, context_type}`.

## Reference

- Backend source: `apps/calendar_view` + `apps/api/v2/views/calendar_views.py`
- Contact: Backend Platform (calendar-view@intelliwiz.internal)
