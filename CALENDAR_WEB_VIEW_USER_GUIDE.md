# Calendar Web View - User Guide

**Feature**: Visual Timeline with Photo Integration
**Version**: 1.0
**Last Updated**: November 10, 2025
**Status**: Production-Ready

---

## 📋 Table of Contents

- [Overview](#overview)
- [Accessing the Calendar](#accessing-the-calendar)
- [Calendar Views](#calendar-views)
- [Context Modes](#context-modes)
- [Event Type Filters](#event-type-filters)
- [Viewing Photos & Videos](#viewing-photos--videos)
- [Search & Filtering](#search--filtering)
- [Photo Metadata](#photo-metadata)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Calendar Web View provides a **unified visual timeline** of all time-based events across IntelliWiz, with integrated photo and video viewing capabilities.

### Key Features

✅ **Multi-Domain Event Aggregation**
- Attendance (check-in/check-out with photos)
- Tasks and Tours (with completion photos)
- Equipment Inspections (with evidence photos)
- Help Desk Tickets (with incident photos)
- Journal Entries (with wellness photos - privacy-aware)
- Maintenance Records (with before/after photos)

✅ **Photo Integration**
- View all photos/videos from calendar events
- Photo metadata display (GPS, timestamp, device, blockchain hash)
- Quality indicators (face detection, blur detection, quality scores)
- Download and share capabilities

✅ **Multiple Perspectives**
- **My Calendar**: Your personal timeline
- **Site Calendar**: All activity at a specific location
- **Asset Calendar**: Equipment service history
- **Team Calendar**: Your supervised team's events
- **Client Calendar**: All sites for a specific client
- **Shift Roster**: Schedule vs actual attendance

✅ **Advanced Features**
- Event type filtering (toggle attendance, tasks, journal, etc.)
- Free-text search across all events
- Month/Week/Day/List views
- Real-time "Today" indicator
- Responsive design (works on desktop, tablet, mobile)

---

## Accessing the Calendar

### Option 1: Via Django Admin

1. Log into Django Admin: `https://your-domain.com/admin/`
2. Navigate to **Calendar View** in the sidebar
3. Or directly visit: `https://your-domain.com/admin/calendar/`

### Option 2: Direct URL

Visit: `https://your-domain.com/admin/calendar/`

**Requirements**:
- Must be logged in as staff user
- JWT authentication (session-based for web)
- Tenant isolation enforced automatically

---

## Calendar Views

The calendar supports **4 display modes** (click toolbar buttons to switch):

### 1. Month View (Default)
- Overview of entire month
- Events color-coded by type
- Dots indicate multiple events on same day
- Click any day to see events for that day

**Best For**: High-level planning, identifying busy periods

### 2. Week View
- 7-day detailed schedule
- Hourly timeline (6 AM - 11 PM)
- Events displayed with duration bars
- Multi-day events span across columns

**Best For**: Weekly planning, shift coordination

### 3. Day View
- Single-day hourly timeline
- All events for selected day
- Precise start/end times visible
- Easy to spot schedule conflicts

**Best For**: Daily operations, detailed scheduling

### 4. List View
- Scrollable list of upcoming events
- Grouped by date
- Shows full event details (title, location, status)
- Efficient for scanning many events

**Best For**: Quick scanning, finding specific events

---

## Context Modes

**Context switcher** (top-left dropdown) changes what events are displayed:

### My Calendar (Default)
**Shows**: All YOUR events across all domains
- Your shifts
- Tasks assigned to you
- Your journal entries
- Tickets assigned to you

**Use Case**: "What's my schedule today?"

### Site Calendar
**Shows**: All activity at a specific site
**Requires**: Site ID (enter in "Context ID" field)

**Example**: Site ID = 42 → Shows all workers, tasks, incidents at Site #42

**Use Case**: "What's happening at Harbor Tower this week?"

### Asset Calendar
**Shows**: Service history for specific equipment
**Requires**: Asset ID (enter in "Context ID" field)

**Example**: Asset ID = 12 → Shows all inspections, repairs, meter readings for Generator #12

**Use Case**: "When was this generator last serviced?"

### Team Calendar
**Shows**: All events for your supervised team members
**Requires**: Team ID (enter in "Context ID" field)

**Use Case**: "What are my team members working on?"

### Client Calendar
**Shows**: All events across all sites for a client
**Requires**: Client ID (enter in "Context ID" field)

**Use Case**: "Executive dashboard for all client sites"

### Shift Roster
**Shows**: Schedule vs actual attendance for shifts
**Requires**: Shift ID (enter in "Context ID" field)

**Use Case**: "Who showed up for morning shift?"

---

## Event Type Filters

**Filter chips** (below calendar header) control which event types are visible.

### Available Event Types

| Icon | Type | Color | Description |
|------|------|-------|-------------|
| ✅ | **Attendance** | Green | Check-in/check-out events |
| 📋 | **Tasks** | Blue | General tasks and assignments |
| 🚶 | **Tours** | Purple | Patrol tours with checkpoints |
| 🔧 | **Inspections** | Orange | Equipment/PPM inspections |
| 📝 | **Journal** | Pink | Wellness journal entries |
| 🎫 | **Tickets** | Red | Help desk tickets |
| 🚨 | **Incidents** | Deep Red | Incident reports |
| ⚙️ | **Maintenance** | Gray | Asset maintenance |

### How to Use

**Toggle Individual Types**:
- Click any filter chip to show/hide that event type
- Active chips have colored background
- Inactive chips have white background with colored border

**Toggle All Types**:
- Click "Toggle All" button (dashed border)
- Turns all types on/off at once
- Useful for quick reset

**Example Workflows**:
- **View only attendance**: Disable all except ✅ Attendance
- **Hide journal entries**: Click 📝 Journal to deactivate
- **Tasks and tours only**: Disable all, then enable 📋 Tasks and 🚶 Tours

---

## Viewing Photos & Videos

### Photo Indicators

Events with photos/videos show visual indicators:

- **📷** prefix = Event has photos
- **🎥** suffix = Event has videos
- Hover over event to see attachment count in tooltip

### Opening Media Viewer

1. **Click any event on the calendar**
2. If event has photos/videos, lightbox opens automatically
3. If event has no media, alert shows "No photos or videos available"

### Lightbox Controls

**Navigation**:
- **← Left Arrow** or click **‹** button: Previous photo
- **→ Right Arrow** or click **›** button: Next photo
- **ESC key** or click **✕ Close**: Exit lightbox

**Photo Actions** (top-left buttons):
- **📥 Download**: Save photo to your computer
- **🔗 Share**: Copy photo URL to clipboard
- **🔐 Hash**: Copy blockchain hash to clipboard

### Video Playback

- Videos play automatically in lightbox
- Standard HTML5 video controls (play/pause/seek/volume)
- Click outside video to close lightbox

---

## Search & Filtering

### Free-Text Search

**Search box** (top controls) searches across:
- Event titles
- Event subtitles
- Location names
- Metadata fields

**How to Use**:
1. Type search term in "Search Events" box
2. Search executes automatically after 500ms (debounced)
3. Calendar updates to show only matching events

**Examples**:
- `"patrol"` → Shows all patrol tours
- `"generator"` → Shows all generator-related events
- `"high"` → Shows high-priority tasks
- `"harbor tower"` → Shows events at Harbor Tower site

### Advanced Filtering (API)

Via API, you can filter by:
- **`has_attachments=true`**: Only events with photos/videos
- **`min_attachment_count=3`**: Events with 3+ attachments
- **`statuses=COMPLETED`**: Only completed events
- **`event_types=TASK,TOUR`**: Specific event types

*Note*: Web UI doesn't expose all filters yet - use API directly for advanced queries.

---

## Photo Metadata

### Metadata Panel (Bottom-Left in Lightbox)

When viewing a photo, the metadata panel shows:

**Always Displayed**:
- **Filename**: Original file name
- **Captured**: Date and time photo was taken
- **Size**: File size in MB

**If Available**:
- **GPS Coordinates**: Latitude/Longitude with "View Map" link
- **Device**: Camera device or uploader name
- **Blockchain Hash**: Cryptographic proof of authenticity (first 24 chars)
- **Quality Score**: AI-assessed photo quality percentage
- **Quality Rating**: EXCELLENT, GOOD, FAIR, POOR
- **Faces Detected**: Number of faces found by AI
- **Resolution**: Image dimensions (width × height pixels)
- **Photo Type**: Check-in, Check-out, Verification, etc.
- **Caption**: User-provided description (journal photos)

### GPS Map Link

1. GPS coordinates (if available) show as `lat, lon` with **📍 View Map** link
2. Click link to open Google Maps in new tab
3. Shows exact location where photo was captured

**Use Cases**:
- Verify worker was at correct site
- Investigate incident locations
- Audit geofence compliance

### Blockchain Hash

**Purpose**: Tamper-proof verification

1. Hash shown as truncated code (first 24 characters + `...`)
2. Hover to see full hash in tooltip
3. Click **🔐 Hash** button to copy full hash
4. Compare hash against blockchain ledger for authenticity verification

**Use Cases**:
- Legal evidence (prove photo wasn't altered)
- Compliance audits (cryptographic proof)
- Dispute resolution (timestamped, location-verified, immutable)

---

## Keyboard Shortcuts

### Calendar Navigation
- **Today** button: Jump to current date
- **Prev/Next** buttons: Navigate by view mode (month/week/day)

### Lightbox Shortcuts
- **ESC**: Close lightbox
- **←** (Left Arrow): Previous photo
- **→** (Right Arrow): Next photo

---

## API Reference

### Calendar Events Endpoint

**URL**: `GET /api/v2/calendar/events/`

**Required Parameters**:
- `start`: ISO8601 datetime (UTC) - Start of time range
- `end`: ISO8601 datetime (UTC) - End of time range (max 31 days)

**Optional Parameters**:
- `event_types`: List of event types (ATTENDANCE, TASK, TOUR, etc.)
- `statuses`: List of statuses (SCHEDULED, IN_PROGRESS, COMPLETED, etc.)
- `context_type`: USER, SITE, ASSET, TEAM, CLIENT, SHIFT
- `context_id`: Context entity ID (required for non-USER contexts)
- `search`: Free-text search query
- `has_attachments`: Boolean - filter to events with/without media
- `min_attachment_count`: Integer - minimum number of attachments
- `page`: Page number for pagination (default: 1)
- `page_size`: Events per page (default: 25, max: 100)

**Example Request**:
```http
GET /api/v2/calendar/events/?start=2025-11-10T00:00:00Z&end=2025-11-17T00:00:00Z&event_types=TASK&event_types=ATTENDANCE&context_type=SITE&context_id=42&has_attachments=true
```

**Response Format**:
```json
{
  "success": true,
  "data": {
    "count": 42,
    "results": [
      {
        "id": "jobneed:123",
        "event_type": "TASK",
        "status": "IN_PROGRESS",
        "title": "Security Patrol",
        "subtitle": "Building A",
        "start": "2025-11-10T09:00:00Z",
        "end": "2025-11-10T11:00:00Z",
        "location": "Harbor Tower",
        "metadata": {
          "attachment_count": 5,
          "photo_count": 4,
          "video_count": 1,
          "has_attachments": true
        }
      }
    ],
    "summary": {
      "by_type": {"TASK": 20, "ATTENDANCE": 15},
      "by_status": {"COMPLETED": 25, "IN_PROGRESS": 10}
    }
  }
}
```

### Event Attachments Endpoint

**URL**: `GET /api/v2/calendar/events/{event_id}/attachments/`

**Path Parameter**:
- `event_id`: Composite event ID (e.g., `jobneed:123`, `attendance:456`)

**Example Request**:
```http
GET /api/v2/calendar/events/jobneed:123/attachments/
```

**Response Format**:
```json
{
  "success": true,
  "data": {
    "event_id": "jobneed:123",
    "count": 3,
    "attachments": [
      {
        "id": 1,
        "uuid": "a1b2c3d4-...",
        "filename": "inspection_001.jpg",
        "url": "/media/attachments/inspection_001.jpg",
        "thumbnail_url": "/media/thumbnails/inspection_001_thumb.jpg",
        "file_type": "photo",
        "file_size": 1024000,
        "created_at": "2025-11-10T09:15:23Z",
        "uploaded_by": "John Smith",
        "metadata": {
          "gps_lat": 40.7128,
          "gps_lon": -74.0060,
          "blockchain_hash": "a1b2c3d4e5f6...",
          "quality_score": 0.92,
          "face_detected": true
        }
      }
    ]
  }
}
```

---

## Troubleshooting

### Calendar Doesn't Load

**Symptoms**: Blank calendar or "Failed to load calendar" error

**Solutions**:
1. **Check authentication**: Ensure you're logged in as staff user
2. **Check date range**: Don't exceed 31-day window
3. **Check context ID**: If using Site/Asset calendar, verify ID is valid
4. **Check browser console**: Look for JavaScript errors (F12 → Console tab)
5. **Try different view**: Switch from Month to Week view

**Common Causes**:
- Invalid context ID (site/asset doesn't exist)
- No events in selected date range
- API endpoint not accessible (check permissions)

### Photos Don't Load

**Symptoms**: Clicking event shows "No media found" or empty lightbox

**Solutions**:
1. **Verify attachments exist**: Check event metadata for `photo_count > 0`
2. **Check file paths**: Ensure media files are accessible
3. **Check permissions**: Private journal photos only visible to owner
4. **Verify network**: Check browser Network tab (F12) for 403/404 errors

**Common Causes**:
- Event has no uploaded photos (metadata shows 0 count)
- Private journal entry accessed by non-owner (403 Forbidden)
- Media files deleted or moved
- Cross-tenant access blocked (security feature)

### Search Not Working

**Symptoms**: Typing in search box doesn't filter events

**Solutions**:
1. **Wait 500ms**: Search is debounced (delayed execution)
2. **Check spelling**: Search is case-insensitive but must match text
3. **Try broader terms**: Search looks in title, subtitle, location, metadata
4. **Clear filters**: Disable event type filters that might exclude results

### Performance Issues

**Symptoms**: Calendar loads slowly or browser freezes

**Solutions**:
1. **Reduce date range**: Try 7 days instead of 31 days
2. **Disable event types**: Filter to specific types only
3. **Clear browser cache**: Ctrl+Shift+Del → Clear cached images
4. **Close other tabs**: Free up browser memory
5. **Use List view**: More efficient than Month view for many events

**Thresholds**:
- <200 events: Fast
- 200-500 events: Normal
- 500-1000 events: Slower (consider filtering)
- >1000 events: Use narrower date range or filters

---

## Privacy & Security

### Journal Entry Privacy

**Privacy Scopes**:
- **PRIVATE**: Only owner sees events and photos (others see title only)
- **SHARED**: Specified users can see events and photos
- **MANAGER**: Manager can see events and photos
- **TEAM**: Team members can see events and photos
- **AGGREGATE_ONLY**: No individual data shown (analytics only)

**Photo Access Rules**:
- Private journal photos: `photo_count = 0` for non-owners
- Private journal event still appears in calendar (title visible)
- Clicking event shows "Permission denied" message
- Protects wellness data while showing work patterns

### Multi-Tenant Isolation

- **Automatic**: You only see events from your tenant
- **No configuration**: Enforced by backend automatically
- **Cross-tenant access**: Blocked (403 Forbidden)

### Attachment Permissions

- Attendance photos: Visible to site managers and workers
- Task photos: Visible to assigned users and managers
- Ticket photos: Visible based on ticket permissions
- Journal photos: Respect privacy scope (most restrictive)

---

## Best Practices

### For Site Managers

1. **Use Site Calendar** to monitor overall activity
2. **Filter to Attendance + Tasks** for operational overview
3. **Search for specific assets** to check maintenance history
4. **Export date ranges** for client reporting (via API)

### For Field Workers

1. **Use My Calendar** to see your daily schedule
2. **Check event photos** before starting tasks (reference images)
3. **Verify check-in photos** show correct location
4. **Review journal entries** at end of day

### For Compliance Officers

1. **Use filters** to find events with photos (proof of work)
2. **Download photos** for audit trails
3. **Verify blockchain hashes** for legal evidence
4. **Check GPS coordinates** for geofence compliance

---

## Performance Tips

### Optimize Loading Speed

1. **Narrow date ranges**: 7-day window loads 5x faster than 31 days
2. **Filter event types**: Viewing 2 types loads faster than all 8 types
3. **Use context filters**: Site calendar faster than "All sites"
4. **Enable browser caching**: API responses cached for 60 seconds

### Photo Loading Strategy

1. **Thumbnails first**: Lightbox loads thumbnails initially (fast)
2. **Full photos on demand**: Click to view full resolution
3. **Sequential loading**: Photos load one at a time (no parallel downloads)
4. **Caching**: Viewed photos cached in browser

---

## Integration with Other Modules

### From Attendance Module
- View shift calendars with check-in/out photos
- Verify attendance patterns over time
- Identify coverage gaps visually

### From Operations Module
- See task schedules on calendar grid
- View completion photos in lightbox
- Track inspection compliance

### From Journal Module
- Personal wellness timeline (privacy-protected)
- Mood/stress patterns over time
- Private photo journal integration

### From HelpDesk Module
- Incident timeline visualization
- Ticket photos in context
- Response time analysis

---

## Future Enhancements (Roadmap)

### Planned for Next Release

- 📧 **Email Notifications**: "Shift starts in 30 minutes"
- 📤 **iCal Export**: Sync with Google Calendar/Outlook
- 📊 **Analytics Dashboard**: Event density heatmaps
- 🔄 **Real-Time Updates**: WebSocket push notifications
- 📱 **Mobile PWA**: Progressive web app for offline access
- 🔗 **Calendar Sharing**: Share calendars with team members
- 🤖 **AI Suggestions**: Optimal scheduling recommendations

---

## Support & Feedback

### Getting Help

1. **Check this guide first**: Most questions answered here
2. **Check API documentation**: `/api/schema/` for detailed API specs
3. **Contact support**: For bugs or feature requests

### Known Limitations

- **Max date range**: 31 days (prevents performance issues)
- **No calendar editing**: Read-only view (edit via source modules)
- **No recurring event templates**: Use scheduler module for recurring tasks
- **Limited export**: Use API for bulk data export (PDF/iCal coming soon)

---

## Technical Details

### Browser Compatibility

**Supported Browsers**:
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+

**Required Features**:
- JavaScript enabled
- Cookies enabled (authentication)
- localStorage (preferences storage)

### Performance Characteristics

**Expected Load Times** (typical):
- Calendar page load: <2 seconds
- Event fetch (7 days): <500ms
- Attachment fetch: <1 second
- Photo lightbox open: <300ms

**API Rate Limits**:
- Calendar events: No limit (cached for 60s)
- Attachments: 100 requests/hour per user

---

## Changelog

### Version 1.0 (November 10, 2025)

**Initial Release**:
- ✅ Calendar event aggregation across 8 event types
- ✅ Photo/video lightbox with metadata
- ✅ Context switching (My/Site/Asset/Team/Client/Shift)
- ✅ Event type filtering
- ✅ Free-text search
- ✅ Multi-view support (Month/Week/Day/List)
- ✅ Download and share photo features
- ✅ Blockchain hash verification
- ✅ GPS map integration
- ✅ Privacy-aware journal photos
- ✅ Responsive design
- ✅ Keyboard navigation

---

**Document maintained by**: Development Team
**Review cycle**: After each feature release
**Last reviewed**: November 10, 2025
