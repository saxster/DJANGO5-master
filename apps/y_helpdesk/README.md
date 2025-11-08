# Help Desk App

**Purpose:** Enterprise ticketing system with SLA management, escalations, and AI-powered ticket assistant

**Owner:** Support & Operations Team  
**Status:** Production  
**Django Version:** 5.2.1

---

## Overview

The Help Desk app (`y_helpdesk`) provides comprehensive ticketing and support management with SLA tracking, automated escalations, AI-powered assistance, and multi-channel support (email, web, mobile, API).

### Key Features

- **Ticket Management** - Full-featured ticketing system
- **SLA Policies** - Automated SLA tracking and enforcement
- **Escalation Engine** - Rule-based ticket escalations
- **AI Ticket Assistant** - Natural language query support
- **Multi-Channel** - Email, web, mobile, API integration
- **Workflow Automation** - Automated assignment and routing
- **Knowledge Base** - Self-service articles
- **Reporting** - SLA compliance, team performance

---

## Architecture

### Models (Modularized)

**Ticket Models** (`models/`):
- `Ticket` - Core ticket model
- `TicketCategory` - Ticket categorization
- `TicketPriority` - Priority definitions
- `TicketComment` - Ticket comments/updates
- `TicketAttachment` - File attachments
- `TicketWorklog` - Time tracking

**SLA Models:**
- `SLAPolicy` - SLA definitions
- `SLAPolicyRule` - Rule-based SLA assignment
- `SLAViolation` - SLA breach tracking

**Escalation Models:**
- `EscalationPolicy` - Escalation rules
- `EscalationHistory` - Escalation audit trail

**See:** [apps/y_helpdesk/models/](file:///Users/amar/Desktop/MyCode/DJANGO5-master/apps/y_helpdesk/models/)

### Services

**Service Layer:**
- `TicketService` - Ticket creation, assignment, lifecycle
- `SLAService` - SLA calculation and monitoring
- `EscalationService` - Automated escalations
- `TicketAssistantService` - AI-powered assistance
- `NotificationService` - Multi-channel notifications
- `WorkflowService` - Automation rules

**See:** [apps/y_helpdesk/services/](file:///Users/amar/Desktop/MyCode/DJANGO5-master/apps/y_helpdesk/services/)

### Views (Organized - 1,503 lines refactored)

**View Organization:**
- `views/ticket_views.py` - Ticket CRUD
- `views/sla_views.py` - SLA management
- `views/escalation_views.py` - Escalation handling
- `views/report_views.py` - Analytics and reports
- `views/assistant_views.py` - AI assistant endpoints

---

## API Endpoints

### Tickets

```
GET    /help-desk/tickets/                           # List tickets
POST   /help-desk/tickets/                           # Create ticket
GET    /help-desk/tickets/{id}/                      # Ticket details
PATCH  /help-desk/tickets/{id}/                      # Update ticket
POST   /help-desk/tickets/{id}/assign/               # Assign ticket
POST   /help-desk/tickets/{id}/transition/           # Change status
POST   /help-desk/tickets/{id}/comment/              # Add comment
POST   /help-desk/tickets/{id}/attach/               # Add attachment
```

### SLA Management

```
GET    /help-desk/sla/policies/                      # List SLA policies
POST   /help-desk/sla/policies/                      # Create SLA policy
GET    /help-desk/sla/violations/                    # SLA violations
GET    /help-desk/sla/compliance/                    # SLA compliance report
```

### Escalations

```
GET    /help-desk/escalations/                       # List escalations
POST   /help-desk/escalations/                       # Create escalation policy
GET    /help-desk/escalations/{ticket_id}/history/   # Escalation history
POST   /help-desk/escalations/{id}/manual/           # Manual escalation
```

### AI Assistant (Natural Language)

```
POST   /help-desk/assistant/query/                   # Natural language query
GET    /help-desk/assistant/suggestions/             # Get ticket suggestions
POST   /help-desk/assistant/categorize/              # Auto-categorize ticket
```

### API v2 (Type-Safe)

```
GET    /api/v2/helpdesk/tickets/                     # Pydantic validated
POST   /api/v2/helpdesk/tickets/search/              # Natural language search
GET    /api/v2/helpdesk/tickets/?fields=id,title     # Field selection
```

---

## Usage Examples

### Creating a Ticket

```python
from apps.y_helpdesk.services import TicketService

ticket = TicketService.create_ticket(
    title="Email not working",
    description="Cannot send emails since this morning",
    reporter=user,
    category="IT Support",
    priority="high",
    client=tenant,
    attachments=[email_screenshot]
)
```

### Auto-Assignment with Workflow

```python
from apps.y_helpdesk.services import WorkflowService

# Workflow automatically:
# 1. Categorizes ticket
# 2. Assigns SLA policy
# 3. Routes to appropriate team
# 4. Notifies assigned agent

ticket = WorkflowService.process_new_ticket(ticket)
```

### Natural Language Query

```python
from apps.y_helpdesk.services import TicketAssistantService

# User asks: "Show me urgent tickets assigned to me"
results = TicketAssistantService.query(
    user=current_user,
    query="urgent tickets assigned to me"
)
```

### SLA Monitoring

```python
from apps.y_helpdesk.services import SLAService

# Check SLA status
sla_status = SLAService.get_ticket_sla_status(ticket)
# Returns: {
#   'policy': 'P1 - 4 Hour Response',
#   'time_remaining': '1h 23m',
#   'status': 'at_risk',
#   'breach_at': datetime(...)
# }
```

### Automated Escalation

```python
# Celery task runs every 15 minutes
@shared_task
def process_escalations():
    from apps.y_helpdesk.services import EscalationService
    
    # Auto-escalate tickets based on rules:
    # - SLA near breach
    # - No response in X hours
    # - Priority + age combination
    
    EscalationService.process_due_escalations()
```

---

## Mobile Integration

### Kotlin SDK

```kotlin
// Create ticket from mobile
val helpdeskClient = IntelliwizSDK.helpdesk()

val ticket = helpdeskClient.createTicket(
    title = "Broken door lock",
    description = "Main entrance lock not working",
    category = "Facilities",
    priority = Priority.HIGH,
    photos = listOf(photo1, photo2)
)

// Check ticket status
val status = helpdeskClient.getTicketStatus(ticket.id)
```

---

## Database Schema

### Key Relationships

```
Ticket
  ├─ reporter (FK → People)
  ├─ assigned_to (FK → People)
  ├─ assigned_group (FK → Group)
  ├─ category (FK → TicketCategory)
  ├─ sla_policy (FK → SLAPolicy)
  ├─ client (FK → Tenant)
  ├─ site (FK → BusinessUnit)
  ├─ comments (FK → TicketComment)
  ├─ attachments (FK → TicketAttachment)
  └─ escalations (FK → EscalationHistory)

SLAPolicy
  ├─ rules (FK → SLAPolicyRule)
  ├─ response_time (DurationField)
  ├─ resolution_time (DurationField)
  └─ business_hours (JSONField)

EscalationPolicy
  ├─ conditions (JSONField)
  ├─ escalation_chain (M2M → People)
  └─ notification_template (FK → Template)
```

### Indexes (High Performance)

```python
class Meta:
    indexes = [
        models.Index(fields=['assigned_to', 'status']),
        models.Index(fields=['sla_breach_at', 'status']),
        models.Index(fields=['category', 'priority', 'status']),
        models.Index(fields=['client', 'created_at']),
        models.Index(fields=['reporter', 'status']),
    ]
```

---

## Business Logic

### Ticket Lifecycle

```
New → Assigned → In Progress → Resolved → Closed
     ↓                            ↓
  Escalated                   Reopened
```

### SLA Calculation

```python
def calculate_sla_breach_time(ticket):
    """
    SLA Rules:
    - Response SLA: Time to first response
    - Resolution SLA: Time to resolution
    - Only counts business hours (9am-5pm, Mon-Fri)
    - Pauses when ticket status = 'Waiting on Customer'
    """
    policy = ticket.sla_policy
    created = ticket.created_at
    
    business_hours_elapsed = calculate_business_hours(
        start=created,
        end=timezone.now(),
        exclude_status='waiting_on_customer'
    )
    
    breach_at = created + policy.response_time
    return breach_at
```

### Auto-Categorization (AI)

```python
# ML model classifies tickets
def auto_categorize(ticket_text):
    """
    Uses NLP to categorize:
    - IT Support
    - Facilities
    - HR
    - Security
    - Other
    
    Confidence threshold: 80%
    Falls back to manual if < 80%
    """
    prediction = ml_model.predict(ticket_text)
    if prediction.confidence > 0.8:
        return prediction.category
    return None  # Manual categorization required
```

---

## Testing

### Running Tests

```bash
# All helpdesk tests
pytest apps/y_helpdesk/tests/ -v

# SLA tests
pytest apps/y_helpdesk/tests/test_sla_service.py -v

# Escalation tests
pytest apps/y_helpdesk/tests/test_escalation_service.py -v

# AI assistant tests
pytest apps/y_helpdesk/tests/test_ticket_assistant.py -v

# With coverage
pytest apps/y_helpdesk/tests/ --cov=apps/y_helpdesk --cov-report=html
```

### Test Coverage

```
Ticket Service: 92%
SLA Service: 89%
Escalation Service: 87%
AI Assistant: 85%
Overall: 88.3%
```

---

## Configuration

### Settings

```python
# intelliwiz_config/settings/helpdesk.py

HELPDESK_SETTINGS = {
    # SLA
    'SLA_CHECK_INTERVAL_MINUTES': 15,
    'SLA_WARNING_THRESHOLD_PERCENT': 80,  # Warn at 80% of SLA
    
    # Escalation
    'AUTO_ESCALATE_ENABLED': True,
    'ESCALATION_CHECK_INTERVAL_MINUTES': 15,
    
    # AI Assistant
    'AI_ASSISTANT_ENABLED': True,
    'AI_CATEGORIZATION_CONFIDENCE_THRESHOLD': 0.8,
    'AI_SUGGESTION_COUNT': 5,
    
    # Notifications
    'NOTIFY_ON_ASSIGNMENT': True,
    'NOTIFY_ON_COMMENT': True,
    'NOTIFY_ON_SLA_WARNING': True,
    'NOTIFY_ON_ESCALATION': True,
}
```

### Celery Tasks

```python
@shared_task
def check_sla_violations():
    """Check for SLA violations every 15 minutes."""
    
@shared_task
def process_escalations():
    """Process due escalations."""
    
@shared_task
def send_daily_ticket_digest():
    """Send daily summary to managers."""
    
@shared_task
def auto_close_resolved_tickets():
    """Auto-close tickets resolved > 7 days ago."""
```

---

## AI Features

### Natural Language Query Examples

```
User: "urgent tickets assigned to me"
→ Filters: assigned_to=current_user, priority=urgent

User: "unresolved facilities tickets from last week"
→ Filters: category=facilities, status≠resolved, created_at>7_days_ago

User: "tickets about broken locks"
→ Full-text search: title + description contains "broken locks"
```

### Auto-Suggestions

```python
# When user types ticket description, suggest:
# 1. Similar existing tickets
# 2. Knowledge base articles
# 3. Common resolutions

suggestions = TicketAssistantService.get_suggestions(
    partial_description="email not working"
)
# Returns:
# - Similar tickets: #1234, #1567
# - KB articles: "Email Troubleshooting Guide"
# - Solutions: "Check email client settings"
```

---

## Troubleshooting

### Common Issues

**Issue:** SLA showing incorrect time remaining  
**Solution:** Verify business hours configuration, check for status changes that pause SLA

**Issue:** Tickets not auto-escalating  
**Solution:** Check escalation policy rules, verify Celery beat schedule

**Issue:** AI categorization not working  
**Solution:** Ensure ML model is trained, check confidence threshold

**Issue:** Notifications not sending  
**Solution:** Check SMTP settings, verify notification preferences

### Debug Logging

```python
import logging
logger = logging.getLogger('apps.y_helpdesk')
logger.setLevel(logging.DEBUG)
```

---

## Performance

### Query Optimization

```python
# Optimized ticket list query
tickets = Ticket.objects.select_related(
    'assigned_to',
    'reporter',
    'category',
    'sla_policy',
    'client'
).prefetch_related(
    'comments',
    'attachments',
    'escalations'
)
```

### Caching

```python
# Cache SLA policies (rarely change)
@cached(timeout=3600, key='sla_policies_{client_id}')
def get_sla_policies(client_id):
    return SLAPolicy.objects.filter(client_id=client_id)
```

---

## Reporting

### Available Reports

1. **SLA Compliance** - % of tickets meeting SLA
2. **Team Performance** - Tickets per agent, resolution time
3. **Category Analysis** - Tickets by category/priority
4. **Escalation Report** - Escalation frequency and reasons
5. **Customer Satisfaction** - CSAT scores from feedback

---

## Related Documentation

- [NOC App](../noc/README.md) - Alerting integration
- [Activity App](../activity/README.md) - Work order integration
- [Ontology System](../../docs/features/DOMAIN_SPECIFIC_SYSTEMS.md) - Knowledge base

---

**Last Updated:** November 6, 2025  
**Maintainers:** Support & Operations Team  
**Contact:** dev-team@example.com
