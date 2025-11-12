# Threat Intelligence V2 API Endpoints

## Base URL

All V2 API endpoints are prefixed with:
```
/api/v2/threat-intelligence/
```

## Authentication

All endpoints require JWT authentication. Include token in request header:
```
Authorization: Bearer <your-jwt-token>
```

## Endpoints

### 1. List Intelligence Alerts

**GET** `/api/v2/threat-intelligence/alerts/`

Retrieve paginated list of threat alerts for authenticated tenant.

**Query Parameters:**
- `severity` (optional): Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
- `category` (optional): Filter by threat category (WEATHER, POLITICAL, TERRORISM, etc.)
- `urgency_level` (optional): Filter by urgency (IMMEDIATE, RAPID, STANDARD, ROUTINE)
- `delivery_status` (optional): Filter by delivery status (PENDING, SENT, FAILED)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (default: 20, max: 100)

**Response:**
```json
{
  "count": 42,
  "next": "http://api.example.com/api/v2/threat-intelligence/alerts/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "threat_event": {
        "id": 456,
        "title": "Severe Weather Warning",
        "category": "WEATHER",
        "severity": "HIGH",
        "description": "Heavy rainfall expected in region",
        "location": {
          "type": "Point",
          "coordinates": [77.5946, 12.9716]
        },
        "location_name": "Bangalore CBD",
        "event_start_time": "2025-11-10T14:00:00Z",
        "confidence_score": 0.92
      },
      "severity": "HIGH",
      "urgency_level": "RAPID",
      "distance_km": 5.2,
      "delivery_status": "SENT",
      "delivery_channels": ["websocket", "email"],
      "work_order_created": true,
      "created_at": "2025-11-10T12:30:00Z",
      "delivered_at": "2025-11-10T12:30:15Z"
    }
  ]
}
```

**Example cURL:**
```bash
curl -X GET \
  'https://api.example.com/api/v2/threat-intelligence/alerts/?severity=HIGH&page=1' \
  -H 'Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...'
```

### 2. Get Alert Detail

**GET** `/api/v2/threat-intelligence/alerts/{alert_id}/`

Retrieve detailed information for a specific alert.

**Path Parameters:**
- `alert_id`: Integer ID of the alert

**Response:**
```json
{
  "id": 123,
  "threat_event": {
    "id": 456,
    "title": "Severe Weather Warning",
    "category": "WEATHER",
    "severity": "HIGH",
    "description": "Heavy rainfall and strong winds expected...",
    "location": {
      "type": "Point",
      "coordinates": [77.5946, 12.9716]
    },
    "location_name": "Bangalore CBD",
    "impact_radius_km": 15.0,
    "event_start_time": "2025-11-10T14:00:00Z",
    "event_end_time": "2025-11-10T20:00:00Z",
    "confidence_score": 0.92,
    "source_name": "National Weather Service",
    "entities": ["Bangalore", "Karnataka", "India"],
    "keywords": ["rainfall", "flood", "weather", "alert"]
  },
  "intelligence_profile": {
    "id": 789,
    "minimum_severity": "MEDIUM",
    "buffer_radius_km": 20.0
  },
  "severity": "HIGH",
  "urgency_level": "RAPID",
  "distance_km": 5.2,
  "delivery_status": "SENT",
  "delivery_channels": ["websocket", "email", "sms"],
  "delivery_error": null,
  "work_order_created": true,
  "work_order": {
    "id": 999,
    "description": "Weather Emergency Response: Severe Weather Warning",
    "priority": "HIGH",
    "workstatus": "ASSIGNED"
  },
  "acknowledged": false,
  "acknowledged_at": null,
  "acknowledged_by": null,
  "created_at": "2025-11-10T12:30:00Z",
  "delivered_at": "2025-11-10T12:30:15Z"
}
```

**Example cURL:**
```bash
curl -X GET \
  'https://api.example.com/api/v2/threat-intelligence/alerts/123/' \
  -H 'Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...'
```

### 3. Acknowledge Alert

**POST** `/api/v2/threat-intelligence/alerts/{alert_id}/acknowledge/`

Mark an alert as acknowledged by the current user.

**Path Parameters:**
- `alert_id`: Integer ID of the alert

**Response:**
```json
{
  "id": 123,
  "acknowledged": true,
  "acknowledged_at": "2025-11-10T13:00:00Z",
  "acknowledged_by": {
    "id": 42,
    "name": "John Doe",
    "email": "john.doe@example.com"
  }
}
```

**Example cURL:**
```bash
curl -X POST \
  'https://api.example.com/api/v2/threat-intelligence/alerts/123/acknowledge/' \
  -H 'Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...' \
  -H 'Content-Type: application/json'
```

### 4. Update Delivery Feedback

**POST** `/api/v2/threat-intelligence/alerts/{alert_id}/feedback/`

Submit feedback on alert relevance/accuracy (used for ML learning).

**Path Parameters:**
- `alert_id`: Integer ID of the alert

**Request Body:**
```json
{
  "relevant": true,
  "action_taken": "WORK_ORDER_CREATED",
  "feedback_text": "Alert was accurate and timely"
}
```

**Response:**
```json
{
  "id": 123,
  "feedback_received": true,
  "feedback_timestamp": "2025-11-10T13:05:00Z"
}
```

**Example cURL:**
```bash
curl -X POST \
  'https://api.example.com/api/v2/threat-intelligence/alerts/123/feedback/' \
  -H 'Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...' \
  -H 'Content-Type: application/json' \
  -d '{
    "relevant": true,
    "action_taken": "WORK_ORDER_CREATED",
    "feedback_text": "Alert was accurate and timely"
  }'
```

## WebSocket Connection

### Real-time Alert Stream

Connect to real-time threat alerts via WebSocket:

**URL:** `ws://api.example.com/ws/threat-alerts/`

**Authentication:** Include JWT token in connection query params:
```
ws://api.example.com/ws/threat-alerts/?token=eyJ0eXAiOiJKV1QiLCJhbGc...
```

**Message Format:**
```json
{
  "type": "threat_alert",
  "data": {
    "id": 123,
    "severity": "HIGH",
    "urgency_level": "IMMEDIATE",
    "title": "Security Alert",
    "category": "TERRORISM",
    "distance_km": 2.5,
    "event_start_time": "2025-11-10T14:00:00Z"
  }
}
```

**Example JavaScript:**
```javascript
const ws = new WebSocket(
  `ws://api.example.com/ws/threat-alerts/?token=${jwtToken}`
);

ws.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  if (alert.type === 'threat_alert') {
    console.log('New threat alert:', alert.data);
    // Display notification to user
  }
};
```

## Error Responses

All endpoints return standard error responses:

**400 Bad Request:**
```json
{
  "error": "Invalid query parameters",
  "details": {
    "severity": ["Invalid severity level"]
  }
}
```

**401 Unauthorized:**
```json
{
  "error": "Authentication credentials were not provided"
}
```

**403 Forbidden:**
```json
{
  "error": "You do not have permission to access this resource"
}
```

**404 Not Found:**
```json
{
  "error": "Alert not found"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal server error",
  "request_id": "abc-123-def"
}
```

## Rate Limiting

- **Standard endpoints:** 100 requests/minute per tenant
- **WebSocket connections:** 5 concurrent connections per user
- **Alert acknowledgment:** 60 requests/minute per user

Rate limit headers included in responses:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1636550400
```

## Pagination

List endpoints use cursor-based pagination:
- Default page size: 20
- Maximum page size: 100
- Use `next` and `previous` URLs for navigation

## Filtering & Sorting

**Alerts can be filtered by:**
- `severity`: CRITICAL, HIGH, MEDIUM, LOW, INFO
- `category`: WEATHER, POLITICAL, TERRORISM, INFRASTRUCTURE, HEALTH, CYBER, OTHER
- `urgency_level`: IMMEDIATE, RAPID, STANDARD, ROUTINE
- `delivery_status`: PENDING, SENT, FAILED
- `acknowledged`: true/false
- `work_order_created`: true/false

**Default sorting:** Most recent alerts first (`-created_at`)

## Work Order Integration

Alerts with severity CRITICAL or HIGH automatically create work orders when:
- `intelligence_profile.enable_work_order_creation = True`
- Alert passes all geospatial and confidence filters

Work order contains:
- Title: Category-specific template (e.g., "Weather Emergency Response: {title}")
- Description: Formatted threat details with distance, confidence, etc.
- Priority: HIGH or CRITICAL based on threat severity
- Status: ASSIGNED (ready for response)
- Metadata: Links to alert and threat event IDs

## Testing

**Test alert creation (admin only):**
```bash
curl -X POST \
  'https://api.example.com/api/v2/threat-intelligence/test-alert/' \
  -H 'Authorization: Bearer <admin-jwt-token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "category": "WEATHER",
    "severity": "HIGH",
    "location": [77.5946, 12.9716],
    "title": "Test Weather Alert"
  }'
```

---

**Last Updated:** November 10, 2025  
**API Version:** v2.0  
**Namespace:** `threat_intelligence_v2`
