# NOC Threat Intelligence Integration

## Overview

This integration adds real-time threat intelligence alerts to the NOC (Network Operations Center) dashboard, allowing security managers to monitor and respond to threats near their facilities.

## Architecture

### Components Created

1. **Widget Template** (`apps/noc/templates/noc/widgets/threat_intelligence_widget.html`)
   - Displays recent unacknowledged threat alerts
   - Color-coded severity badges (CRITICAL=red, HIGH=orange, MEDIUM=yellow, LOW=blue)
   - Action buttons for acknowledge/false positive/details
   - Empty state when no active threats
   - Critical alert banner for high-priority notifications

2. **JavaScript Client** (`apps/noc/static/noc/js/threat_intelligence.js`)
   - WebSocket connection with auto-reconnect (exponential backoff)
   - Real-time alert display with animations
   - Optimistic UI updates for acknowledgments
   - Alert sound for CRITICAL severity
   - Browser notifications (with user permission)
   - Time-ago formatting that auto-updates

3. **CSS Styling** (`apps/noc/static/noc/css/threat_intelligence.css`)
   - Responsive design (mobile-friendly)
   - Accessibility features (ARIA labels, high contrast mode)
   - Animations (fade-in, pulse for critical alerts)
   - Consistent with existing NOC design patterns

4. **WebSocket Consumer** (`apps/noc/consumers/threat_alerts_consumer.py`)
   - Real-time alert broadcasting
   - Tenant isolation (users only see their own alerts)
   - Authentication and RBAC enforcement
   - Rate limiting and error handling

5. **Updated NOC Dashboard View** (`apps/noc/views/ui_views.py`)
   - Fetches recent unacknowledged alerts (last 24 hours)
   - Counts critical threat alerts
   - Optimized with `select_related('threat_event')` to avoid N+1 queries

6. **WebSocket Broadcast Service** (`apps/threat_intelligence/services/websocket_broadcast.py`)
   - Service layer for broadcasting alerts
   - Serialization of alert data
   - Error handling with specific exceptions

7. **Test Suite** (`apps/noc/tests/test_threat_widget.py`)
   - Widget rendering tests
   - Tenant isolation validation
   - Severity ordering verification
   - Performance optimization checks

## Data Flow

```
Threat Detection
     ↓
ThreatEvent Created
     ↓
IntelligenceAlert Generated (via AlertDistributor)
     ↓
WebSocket Broadcast (ThreatAlertWebSocketBroadcaster)
     ↓
ThreatAlertsConsumer (tenant-specific channel)
     ↓
JavaScript Client (threat_intelligence.js)
     ↓
DOM Update + Notifications
```

## WebSocket Protocol

### Connection

```
ws://[host]/ws/threat-alerts/
```

**Authentication**: Required (session-based)

**Authorization**: User must have `noc:view` capability

### Message Types

#### Incoming (Server → Client)

1. **Connection Established**
```json
{
  "type": "connection_established",
  "message": "Connected to threat intelligence feed"
}
```

2. **New Threat Alert**
```json
{
  "type": "new_threat_alert",
  "alert": {
    "id": 123,
    "severity": "CRITICAL",
    "urgency_level": "IMMEDIATE",
    "distance_km": 2.5,
    "created_at": "2025-11-10T18:45:00Z",
    "threat_event": {
      "id": 456,
      "title": "Armed Robbery Nearby",
      "description": "...",
      "incident_type": "VIOLENT_CRIME",
      "location": "Shopping Center, Main St"
    }
  }
}
```

3. **Alert Acknowledged**
```json
{
  "type": "alert_acknowledged",
  "alert_id": 123,
  "acknowledged_by": "john_doe"
}
```

4. **Alert Updated**
```json
{
  "type": "alert_updated",
  "alert": { /* full alert object */ }
}
```

#### Outgoing (Client → Server)

**Ping (keepalive)**
```json
{
  "type": "ping"
}
```

Response:
```json
{
  "type": "pong"
}
```

## REST API Endpoints

### List Alerts
```
GET /api/v2/threat-intelligence/alerts/?limit=5&unacknowledged=true
```

### Get Alert Details
```
GET /api/v2/threat-intelligence/alerts/{id}/
```

### Submit Feedback
```
POST /api/v2/threat-intelligence/alerts/{id}/feedback/
Content-Type: application/json

{
  "tenant_response": "NOTED",  // or "FALSE_POSITIVE"
  "response_notes": ""
}
```

## Installation

### 1. Add Widget to NOC Dashboard Template

Edit `apps/noc/templates/noc/overview.html`:

```django
{% extends "noc/base.html" %}
{% load static %}

{% block content %}
<div class="noc-dashboard">
    <!-- Existing dashboard content -->
    
    <!-- Add threat intelligence widget -->
    {% include 'noc/widgets/threat_intelligence_widget.html' %}
    
    <!-- Other widgets -->
</div>
{% endblock %}
```

**Recommended placement**: Top of dashboard or full-width banner area for high visibility.

### 2. Verify WebSocket Routing

Check `intelliwiz_config/routing.py` includes NOC WebSocket routes:

```python
from apps.noc.routing import websocket_urlpatterns as noc_ws_urls

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(noc_ws_urls + [...])
    ),
})
```

### 3. Static Files

Ensure static files are collected:

```bash
python manage.py collectstatic --noinput
```

### 4. Optional: Add Alert Sound

Place `critical_alert.mp3` (or `.ogg`) in `apps/noc/static/noc/sounds/`.

Free sound effect sources:
- [Freesound.org](https://freesound.org)
- [Zapsplat](https://www.zapsplat.com)

## Testing

### Run Unit Tests

```bash
python -m pytest apps/noc/tests/test_threat_widget.py -v
```

### Manual Testing Checklist

1. **Basic Rendering**
   - [ ] Widget displays on NOC dashboard
   - [ ] Empty state shows when no alerts
   - [ ] Status indicator shows "Connected"

2. **Real-Time Updates**
   - [ ] Create test alert via Django admin
   - [ ] Alert appears in widget without page refresh
   - [ ] Critical alerts trigger banner + sound

3. **User Actions**
   - [ ] Click "Acknowledge" button
   - [ ] Alert marked as acknowledged in UI
   - [ ] Click "False Positive" button
   - [ ] Alert removed from list

4. **Tenant Isolation**
   - [ ] User A (Tenant 1) creates alert
   - [ ] User B (Tenant 2) does NOT see alert
   - [ ] User A sees only their tenant's alerts

5. **Connection Resilience**
   - [ ] Restart Daphne server
   - [ ] Widget auto-reconnects
   - [ ] Status indicator shows reconnection attempts

6. **Performance**
   - [ ] Multiple browser tabs (same user)
   - [ ] All tabs receive updates
   - [ ] No memory leaks (check DevTools)

### Create Test Alert (Django Shell)

```python
python manage.py shell

from apps.threat_intelligence.models import ThreatEvent, IntelligenceAlert, TenantIntelligenceProfile
from apps.tenants.models import Tenant
from django.utils import timezone

# Get tenant
tenant = Tenant.objects.first()

# Create threat event
event = ThreatEvent.objects.create(
    title="Test Armed Robbery",
    description="Test threat for dashboard integration",
    incident_type="VIOLENT_CRIME",
    severity="CRITICAL",
    location="Test Location",
    tenant=tenant
)

# Get or create intelligence profile
profile, _ = TenantIntelligenceProfile.objects.get_or_create(
    tenant=tenant,
    defaults={'radius_km': 10.0}
)

# Create alert
alert = IntelligenceAlert.objects.create(
    tenant=tenant,
    threat_event=event,
    intelligence_profile=profile,
    severity="CRITICAL",
    urgency_level="IMMEDIATE",
    distance_km=2.5,
    delivery_status="DELIVERED"
)

# Alert should appear on NOC dashboard in real-time
```

## Configuration

### JavaScript Settings (Optional)

Edit `threat_intelligence.js` to customize:

```javascript
class ThreatIntelligenceWidget {
    constructor(wsUrl, containerId) {
        // ...
        this.maxReconnectAttempts = 5;  // Max reconnection attempts
        this.reconnectDelay = 1000;     // Initial delay (ms)
        this.alertSound = new Audio('/static/noc/sounds/critical_alert.mp3');
    }
}
```

### CSS Customization

Edit `threat_intelligence.css` to match your brand:

```css
.threat-intelligence-widget .widget-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    /* Change gradient colors */
}

.severity-badge.severity-critical {
    background: #d32f2f;  /* Change severity colors */
}
```

## Security Considerations

✅ **Implemented Protections**

1. **Authentication**: WebSocket requires authenticated session
2. **Authorization**: RBAC check for `noc:view` capability
3. **Tenant Isolation**: Users only receive alerts for their tenant
4. **CSRF Protection**: POST requests include CSRF token
5. **Input Sanitization**: JavaScript escapes all HTML output
6. **Rate Limiting**: WebSocket consumer enforces message limits
7. **Audit Logging**: All actions logged with correlation IDs

⚠️ **Security Checklist**

- [ ] WebSocket only accessible over WSS (TLS) in production
- [ ] Content-Security-Policy allows WebSocket connections
- [ ] Alert sound volume not excessive (accessibility)
- [ ] Browser notification permission requested, not forced

## Performance Optimizations

1. **Database Queries**
   - `select_related('threat_event')` to avoid N+1 queries
   - Index on `(tenant, acknowledged_at, created_at)`
   - Limit to 5 most recent alerts

2. **WebSocket**
   - Auto-reconnect with exponential backoff
   - Connection pooling via Channels layer
   - Message batching for high-volume scenarios

3. **Frontend**
   - CSS animations use `transform` (GPU-accelerated)
   - Event delegation for dynamic buttons
   - Debounced time-ago updates (every 60s)

## Accessibility

✅ **WCAG 2.1 Compliance**

- Keyboard navigation for all buttons
- ARIA labels for severity badges
- Screen reader announcements for new alerts
- High contrast mode support
- Reduced motion preference respected

## Troubleshooting

### WebSocket Not Connecting

**Symptom**: Status shows "Connection error" or "Disconnected"

**Solutions**:
1. Check Daphne is running (not Django dev server)
   ```bash
   daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
   ```
2. Verify WebSocket route in `intelliwiz_config/routing.py`
3. Check browser console for errors
4. Ensure Redis is running (Channels layer backend)

### Alerts Not Appearing

**Symptom**: Widget shows empty state despite creating alerts

**Solutions**:
1. Check alert is for correct tenant
2. Verify alert is unacknowledged (`acknowledged_at IS NULL`)
3. Check alert created within last 24 hours
4. Inspect browser DevTools Network tab for WebSocket messages

### Static Files Not Loading

**Symptom**: Widget has no styling or JavaScript errors

**Solutions**:
```bash
python manage.py collectstatic --noinput
```

Check `STATIC_ROOT` and `STATICFILES_DIRS` settings.

### Cross-Tenant Data Leakage

**Symptom**: User sees alerts from other tenants

**Solutions**:
1. **CRITICAL SECURITY ISSUE** - Report immediately
2. Check `threat_alerts_consumer.py` tenant filtering
3. Verify `request.user.tenant` in view context
4. Review database query filters

## Future Enhancements

- [ ] Alert filtering (by severity, distance, type)
- [ ] Alert history view (acknowledged alerts)
- [ ] Geolocation map integration
- [ ] SMS/Email notification preferences
- [ ] Alert escalation rules
- [ ] Integration with work order system
- [ ] Threat analytics dashboard

## Files Modified/Created

### Created Files
- `apps/noc/templates/noc/widgets/threat_intelligence_widget.html`
- `apps/noc/static/noc/js/threat_intelligence.js`
- `apps/noc/static/noc/css/threat_intelligence.css`
- `apps/noc/consumers/threat_alerts_consumer.py`
- `apps/threat_intelligence/services/websocket_broadcast.py`
- `apps/noc/tests/test_threat_widget.py`
- `apps/noc/NOC_THREAT_INTELLIGENCE_INTEGRATION.md` (this file)

### Modified Files
- `apps/noc/views/ui_views.py` (added threat alert context)
- `apps/noc/routing.py` (added WebSocket route)
- `apps/noc/consumers/__init__.py` (exported ThreatAlertsConsumer)

## Support

For issues or questions:
1. Check this integration guide
2. Review test cases in `test_threat_widget.py`
3. Check logs: `logs/noc.threat_alerts.log`
4. Consult threat intelligence implementation guide

---

**Last Updated**: November 10, 2025  
**Version**: 1.0  
**Author**: Development Team
