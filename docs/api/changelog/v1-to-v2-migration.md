# API v1 to v2 Migration Guide

**Last Updated:** November 6, 2025  
**Migration Deadline:** October 2025 (v1 deprecated)  
**Status:** v2 is production-ready, v1 being phased out

---

## Executive Summary

API v2 introduces significant improvements over v1:
- **Type-safe contracts** with Pydantic validation
- **Better error handling** with standardized error responses
- **Improved performance** through query optimization
- **Enhanced security** with modern authentication
- **GraphQL removal** - Cleaned up in favor of REST
- **WebSocket support** for real-time features

**Migration Effort:** Estimated 2-4 hours per integrated client

---

## Breaking Changes

### 1. Authentication

**v1:**
```python
# Session-based authentication only
Authorization: Session <session_id>
```

**v2:**
```python
# Token-based authentication (JWT)
Authorization: Bearer <jwt_token>

# Or API Keys for server-to-server
X-API-Key: <api_key>
```

**Migration:**
- Replace session auth with JWT tokens from `/api/v2/auth/token/`
- Update client to send `Authorization: Bearer <token>` header
- Tokens expire after 24 hours, implement refresh logic

---

### 2. Response Format

**v1:**
```json
{
  "status": "ok",
  "data": {...}
}
```

**v2:**
```json
{
  "success": true,
  "data": {...},
  "meta": {
    "timestamp": "2025-11-06T10:30:00Z",
    "correlation_id": "abc-123"
  }
}
```

**Error responses in v2:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": {...},
    "correlation_id": "abc-123"
  }
}
```

---

### 3. Pagination

**v1:**
```
GET /api/v1/tickets/?page=2&page_size=20
```

**v2:**
```
GET /api/v2/tickets/?limit=20&offset=20
```

**v2 Response:**
```json
{
  "success": true,
  "data": {
    "results": [...],
    "count": 150,
    "next": "/api/v2/tickets/?limit=20&offset=40",
    "previous": "/api/v2/tickets/?limit=20&offset=0"
  }
}
```

---

### 4. Date/Time Format

**v1:** Mixed formats (ISO 8601, Unix timestamps)

**v2:** Strict ISO 8601 with timezone
```json
{
  "created_at": "2025-11-06T10:30:00+00:00",
  "updated_at": "2025-11-06T15:45:30+00:00"
}
```

---

## Deprecated Endpoints

### Removed in v2

| v1 Endpoint | Status | v2 Alternative |
|-------------|--------|----------------|
| `/api/v1/graphql/` | ❌ Removed | Use REST endpoints |
| `/api/v1/peoples/login/` | ❌ Deprecated | `/api/v2/auth/token/` |
| `/api/v1/tickets/legacy_format/` | ❌ Removed | `/api/v2/helpdesk/tickets/` |
| `/api/v1/reports/csv/` | ⚠️ Deprecated | `/api/v2/reports/export/` |

---

## New Features in v2

### 1. WebSocket Support

**Real-time alerts:**
```javascript
const ws = new WebSocket('wss://api.example.com/ws/noc/alerts/');
ws.onmessage = (event) => {
  const alert = JSON.parse(event.data);
  console.log('New alert:', alert);
};
```

### 2. Bulk Operations

**v2 adds efficient bulk endpoints:**
```
POST /api/v2/helpdesk/tickets/bulk_update/
POST /api/v2/attendance/bulk_approve/
POST /api/v2/work_orders/bulk_assign/
```

### 3. Natural Language Queries

**Search tickets using natural language:**
```
GET /api/v2/helpdesk/tickets/search/?q="urgent tickets assigned to me"
```

### 4. Field Selection

**Reduce payload size:**
```
GET /api/v2/tickets/?fields=id,title,status
```

---

## Migration by Module

### Helpdesk / Ticketing

**v1:**
```
GET /api/v1/tickets/
POST /api/v1/tickets/create/
```

**v2:**
```
GET /api/v2/helpdesk/tickets/
POST /api/v2/helpdesk/tickets/
```

**Changes:**
- Nested routes: `/api/v2/helpdesk/` prefix
- Ticket transitions: Use `/api/v2/helpdesk/tickets/{id}/transition/`
- Attachments: Upload to `/api/v2/helpdesk/tickets/{id}/attachments/`

### Attendance

**v1:**
```
POST /api/v1/attendance/checkin/
POST /api/v1/attendance/checkout/
```

**v2:**
```
POST /api/v2/attendance/entries/
PATCH /api/v2/attendance/entries/{id}/
```

**Changes:**
- Single endpoint for check-in/out (use `action` field)
- GPS validation now mandatory (add `latitude`, `longitude`)
- Photo capture required for facial recognition

### Work Orders

**v1:**
```
GET /api/v1/work_orders/
POST /api/v1/work_orders/assign/
```

**v2:**
```
GET /api/v2/work_orders/
POST /api/v2/work_orders/{id}/assign/
```

**Changes:**
- RESTful resource structure
- Assignment is a sub-resource action
- Status transitions through `/transition/` endpoint

### Reports

**v1:**
```
GET /api/v1/reports/generate/?type=attendance
```

**v2:**
```
POST /api/v2/reports/
{
  "report_type": "attendance",
  "date_range": {...},
  "format": "pdf"
}
```

**Changes:**
- POST instead of GET for report generation
- Asynchronous processing (returns job ID)
- Download from `/api/v2/reports/{id}/download/`

---

## Code Examples

### Authentication Migration

**Before (v1):**
```python
import requests

session = requests.Session()
session.post('https://api.example.com/api/v1/peoples/login/', 
             json={'username': 'user', 'password': 'pass'})

response = session.get('https://api.example.com/api/v1/tickets/')
```

**After (v2):**
```python
import requests

# Get token
auth_response = requests.post(
    'https://api.example.com/api/v2/auth/token/',
    json={'username': 'user', 'password': 'pass'}
)
token = auth_response.json()['data']['access_token']

# Use token
headers = {'Authorization': f'Bearer {token}'}
response = requests.get(
    'https://api.example.com/api/v2/helpdesk/tickets/',
    headers=headers
)
```

### Ticket Creation

**Before (v1):**
```javascript
fetch('/api/v1/tickets/create/', {
  method: 'POST',
  body: JSON.stringify({
    title: 'Issue',
    description: 'Details',
    priority: 1
  })
})
```

**After (v2):**
```javascript
fetch('/api/v2/helpdesk/tickets/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    title: 'Issue',
    description: 'Details',
    priority: 'high',  // String enum instead of number
    category: 'technical'
  })
})
.then(res => res.json())
.then(data => {
  if (data.success) {
    console.log('Ticket created:', data.data.id);
  } else {
    console.error('Error:', data.error);
  }
})
```

---

## Error Handling

### v1 Errors
```json
{
  "error": "Invalid ticket ID"
}
```

### v2 Errors (Structured)
```json
{
  "success": false,
  "error": {
    "code": "TICKET_NOT_FOUND",
    "message": "Ticket with ID 123 does not exist",
    "details": {
      "ticket_id": 123,
      "searched_in": "tenant_A"
    },
    "correlation_id": "req-abc-123"
  }
}
```

**Error Codes:**
- `VALIDATION_ERROR` - Invalid input
- `AUTHENTICATION_REQUIRED` - Missing/invalid token
- `PERMISSION_DENIED` - Insufficient permissions
- `NOT_FOUND` - Resource doesn't exist
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INTERNAL_ERROR` - Server error (use correlation_id for support)

---

## Performance Improvements

### Query Optimization

v2 automatically optimizes database queries:
- N+1 query detection
- Automatic `select_related()` for foreign keys
- `prefetch_related()` for relationships

**Result:** 40-60% faster API response times

### Response Compression

v2 supports `gzip` compression:
```
Accept-Encoding: gzip
```

Reduces payload size by 70%+

---

## Migration Checklist

### Phase 1: Preparation (Week 1)
- [ ] Audit all v1 API calls in your application
- [ ] Review breaking changes list
- [ ] Set up v2 development environment
- [ ] Generate API tokens for testing

### Phase 2: Development (Week 2-3)
- [ ] Update authentication to JWT
- [ ] Migrate endpoint URLs
- [ ] Update request/response parsing
- [ ] Add error handling for new format
- [ ] Update date/time parsing
- [ ] Implement pagination changes

### Phase 3: Testing (Week 4)
- [ ] Test all migrated endpoints
- [ ] Verify error handling
- [ ] Performance testing
- [ ] Security audit
- [ ] User acceptance testing

### Phase 4: Deployment (Week 5)
- [ ] Deploy to staging
- [ ] Monitor for errors
- [ ] Gradual rollout to production
- [ ] Monitor performance metrics
- [ ] Decommission v1 clients

---

## Support & Resources

### Documentation
- [API v2 Reference](../TYPE_SAFE_CONTRACTS.md)
- [WebSocket Documentation](../../features/DOMAIN_SPECIFIC_SYSTEMS.md)
- [Authentication Guide](../../configuration/SETTINGS_AND_CONFIG.md)

### Testing
- **v2 Sandbox:** `https://sandbox.api.example.com/api/v2/`
- **API Explorer:** `https://api.example.com/api/v2/docs/`
- **Postman Collection:** Available in `/examples/api/`

### Getting Help
- **Correlation IDs:** Include in all support requests
- **Error logs:** Check `/api/v2/monitoring/errors/` (admin only)
- **Rate limits:** Contact support for increase if needed

---

## Timeline

| Date | Milestone |
|------|-----------|
| Oct 2025 | v1 deprecated, v2 production-ready |
| Nov 2025 | v1 endpoints return deprecation warnings |
| Dec 2025 | v1 API sunset (shutdown) |
| Jan 2026 | v1 fully decommissioned |

**Action Required:** Migrate by December 2025

---

## FAQs

**Q: Can I use both v1 and v2 during migration?**  
A: Yes, both are supported until December 2025.

**Q: Will my v1 API keys work with v2?**  
A: No, you need to generate new JWT tokens or API keys for v2.

**Q: What happens if I don't migrate?**  
A: v1 APIs will stop working in December 2025.

**Q: Is there a migration tool?**  
A: We provide Postman collections and code examples in multiple languages.

**Q: How do I get help with migration?**  
A: Contact support with your correlation IDs from failed requests.

---

**Last Updated:** November 6, 2025  
**Contact:** api-support@example.com
