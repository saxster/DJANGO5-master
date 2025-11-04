# Ticket Assistant Quick Start Guide

**For Developers**: Get started with the Enhanced HelpDesk Chatbot in 5 minutes.

---

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install parlant>=3.0
```

### 2. Configure Settings
```python
# settings/base.py or .env
ENABLE_PARLANT_AGENT=True
TXTAI_ENABLED=True
```

### 3. Initialize Knowledge Base
```bash
python manage.py seed_knowledge_base
```

---

## 💬 Basic Usage

### Start Ticket Assistant Session
```python
from apps.helpbot.services.conversation_service import HelpBotConversationService

service = HelpBotConversationService()
session = service.start_ticket_assistant_session(
    user=request.user,
    language='en'
)
```

### Send Message
```python
response = service.process_message(
    session=session,
    user_message="What's the status of ticket T00123?"
)

print(response['response']['content'])
# Output: "Ticket T00123 is currently OPEN with MEDIUM priority..."
```

---

## 🔧 API Usage

### Start Session
```bash
POST /api/v1/helpbot/sessions/
Content-Type: application/json

{
    "agent_type": "ticket_assistant",
    "context": "I need help with tickets"
}
```

### Send Message
```bash
POST /api/v1/helpbot/sessions/{session_id}/messages/
Content-Type: application/json

{
    "message": "Show me my open tickets"
}
```

---

## 🎯 Common Use Cases

### 1. Check Ticket Status
**User**: "What's the status of ticket T00123?"
**Tool**: `check_ticket_status`
**Result**: Status, priority, assigned to, days open

### 2. Create Ticket (with Deflection)
**User**: "The AC is not working"
**Flow**: Search KB → No solution → Create draft → Confirm → Submit
**Tools**: `search_knowledge_base`, `create_ticket_draft`, `submit_ticket`

### 3. List My Tickets
**User**: "Show me my tickets"
**Tool**: `get_my_open_tickets`
**Result**: List with priority summary

### 4. Escalate Ticket
**User**: "This is taking too long, escalate ticket T00123"
**Tool**: `escalate_ticket`
**Result**: Priority upgraded, supervisor notified

### 5. Deflection (No Ticket)
**User**: "How do I reset my password?"
**Flow**: Search KB → High confidence → Present solution → User confirms → No ticket created
**Tool**: `search_knowledge_base`

---

## 🧪 Testing

### Run Tests
```bash
pytest apps/helpbot/tests/test_ticket_assistant.py -v
```

### Test Coverage
- Intent classification
- Parlant tools
- Conversation flows
- Deflection metrics

---

## 📊 Monitor Deflection Rate

```python
from apps.helpbot.models import HelpBotSession
from django.db.models import Count

# Calculate deflection rate
total = HelpBotSession.objects.filter(
    context_data__agent_type='ticket_assistant'
).count()

deflected = HelpBotSession.objects.filter(
    context_data__agent_type='ticket_assistant',
    messages__metadata__deflected=True
).distinct().count()

rate = (deflected / total) * 100
print(f"Deflection Rate: {rate:.1f}%")  # Target: ≥60%
```

---

## 🔍 Debug Mode

### Enable Verbose Logging
```python
import logging
logging.getLogger('helpbot.parlant').setLevel(logging.DEBUG)
logging.getLogger('helpbot.ticket_intent').setLevel(logging.DEBUG)
```

### Check Parlant Service
```python
from apps.helpbot.services.parlant_agent_service import ParlantAgentService

service = ParlantAgentService()
print(f"Parlant enabled: {service.enabled}")
print(f"Server initialized: {service._server_initialized}")
```

---

## 🎓 Extend Functionality

### Add Custom Parlant Tool
```python
# apps/helpbot/parlant/tools/ticket_assistant_tools.py

@p.tool
async def my_custom_tool(context: p.ToolContext, param: str) -> p.ToolResult:
    """My custom tool description."""
    try:
        # Your logic here
        result = await sync_to_async(some_function)(param)
        return p.ToolResult({'success': True, 'data': result})
    except Exception as e:
        return p.ToolResult(success=False, error=str(e))

# Add to ALL_TICKET_TOOLS
ALL_TICKET_TOOLS = [..., my_custom_tool]
```

### Add Custom Guideline
```python
# apps/helpbot/parlant/guidelines/ticket_support_guidelines.py

async def _create_my_guidelines(agent) -> List:
    g = await agent.create_guideline(
        condition="User asks about X",
        action="1. Call tool\n2. Present result",
        tools=[my_tool]
    )
    return [g]

# Add to create_all_ticket_guidelines()
```

---

## 📚 Key Files

| File | Purpose |
|------|---------|
| `apps/helpbot/parlant/guidelines/ticket_support_guidelines.py` | Conversational guidelines |
| `apps/helpbot/parlant/tools/ticket_assistant_tools.py` | 7 Parlant tools |
| `apps/helpbot/services/ticket_intent_classifier.py` | Intent classification |
| `apps/helpbot/services/conversation_service.py` | Session management |
| `apps/helpbot/tests/test_ticket_assistant.py` | Test suite |

---

## 🆘 Troubleshooting

### Parlant Not Enabled
**Issue**: `parlant_service is None`
**Fix**: Set `ENABLE_PARLANT_AGENT=True` and install Parlant SDK

### Knowledge Base Empty
**Issue**: No search results
**Fix**: Run `python manage.py seed_knowledge_base`

### Low Deflection Rate
**Issue**: Deflection rate < 60%
**Check**: Knowledge base coverage, guideline effectiveness, intent classification accuracy

---

## 📖 Full Documentation

See `ENHANCED_HELPDESK_CHATBOT_IMPLEMENTATION.md` for complete implementation details.
