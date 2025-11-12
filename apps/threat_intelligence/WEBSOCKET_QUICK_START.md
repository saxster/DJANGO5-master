# Threat Intelligence WebSocket - Quick Start Guide

## For Backend Developers

### Send Alert via WebSocket (Automatic)

When creating alerts, WebSocket notifications are sent automatically:

```python
from apps.threat_intelligence.services.alert_distributor import AlertDistributor

# Distribute alert (includes WebSocket if enabled)
AlertDistributor.distribute_alert(alert)
```

### Send Alert Updates

```python
from apps.threat_intelligence.services.websocket_notifier import WebSocketNotifier

# Alert acknowledged
WebSocketNotifier.send_alert_acknowledged(alert, user_id=request.user.id)

# Alert responded to
WebSocketNotifier.send_alert_responded(
    alert, 
    response='ACTIONABLE', 
    notes='Emergency protocols initiated'
)

# Alert escalated
WebSocketNotifier.send_alert_escalated(
    alert,
    escalated_to=['Security Manager', 'Facilities Director']
)

# Work order created
WebSocketNotifier.send_work_order_created(alert, work_order_id=123)
```

---

## For Frontend Developers

### Connect to WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/threat-alerts/');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'threat_alert') {
        // New alert received
        displayAlert(data);
    } else if (data.type === 'threat_alert_update') {
        // Alert status updated
        updateAlert(data.alert_id, data.update_type, data.data);
    }
};
```

### Message Types

**New Alert:**
```json
{
  "type": "threat_alert",
  "alert_id": 123,
  "severity": "CRITICAL",
  "category": "WEATHER",
  "title": "Hurricane Warning",
  "distance_km": 5.2,
  "urgency_level": "IMMEDIATE",
  "event_start_time": "2025-11-11T15:00:00Z",
  "created_at": "2025-11-10T14:30:00Z"
}
```

**Alert Update:**
```json
{
  "type": "threat_alert_update",
  "alert_id": 123,
  "update_type": "acknowledged",
  "data": {
    "acknowledged_by": 456,
    "acknowledged_at": "2025-11-10T14:35:00Z"
  },
  "timestamp": "2025-11-10T14:35:00Z"
}
```

### Update Types
- `acknowledged` - Alert was acknowledged
- `responded` - Tenant responded (ACTIONABLE, FALSE_POSITIVE, etc.)
- `escalated` - Alert escalated to higher authority
- `work_order_created` - Work order auto-generated

---

## Testing

### Run Tests
```bash
python -m pytest apps/threat_intelligence/tests/test_websocket.py -v
```

### Manual Test
```bash
# Start Daphne
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application

# In browser console
const ws = new WebSocket('ws://localhost:8000/ws/threat-alerts/');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## Security Notes

- ✅ Authentication required (JWT/session)
- ✅ Tenant isolation enforced
- ✅ No cross-tenant data leaks
- ✅ Rate limiting in place
- ✅ All connections logged

---

## Integration Points

**NOC Dashboard**: Add WebSocket client to receive real-time alerts
**Mobile App**: Use WebSocket for push-like notifications
**Alert Management**: Send updates when users acknowledge/respond
**Work Orders**: Notify when auto-created from alerts

---

See [THREAT_INTELLIGENCE_WEBSOCKET_INTEGRATION.md](../../THREAT_INTELLIGENCE_WEBSOCKET_INTEGRATION.md) for complete documentation.
