# Priority Alerts - Quick Start Guide

**User-friendly deadline tracking for tickets**

---

## What is Priority Alerts?

Priority Alerts automatically monitors your tickets and warns you when they might miss their deadlines. No complex metrics—just simple, actionable advice.

**You see:**  
✅ "⚠️ This ticket might miss its deadline"  
✅ "👤 Assign to someone now"  
✅ "🔄 Reassign to John (only 3 tasks)"

**NOT:**  
❌ "High SLA breach probability: 87.3%"  
❌ "Escalation threshold exceeded by 142 minutes"

---

## Quick Setup (5 minutes)

### 1. Run Migration

```bash
python manage.py makemigrations y_helpdesk
python manage.py migrate y_helpdesk
```

### 2. Start Celery

```bash
# Terminal 1: Worker
celery -A intelliwiz_config worker -l info

# Terminal 2: Beat (scheduler)
celery -A intelliwiz_config beat -l info
```

### 3. Configure Email (Optional)

Add to your `.env`:
```
DEFAULT_FROM_EMAIL=alerts@yourcompany.com
SITE_URL=https://yoursite.com
```

**Done!** Alerts will start appearing in 10 minutes.

---

## Using Priority Alerts

### View Alerts in Admin

1. **Go to:** Django Admin → Y-Helpdesk → Tickets
2. **Look for:** Alert badge in first column
   - 🔴 **Urgent** - Needs attention NOW
   - 🟠 **Soon** - Check on these
   - 🟢 **On Track** - All good

3. **Filter tickets:**
   - Click "Priority Level" filter
   - Select "🔴 Urgent" to see critical tickets

### View Alert Details

1. **Click on any ticket**
2. **Scroll down** to see Priority Alert card
3. **Review:**
   - 💡 **Why it needs attention** - Clear reasons
   - ✅ **What to do** - Clickable suggestions
   - 📊 **SLA info** - Time remaining/elapsed

4. **Acknowledge:** Click "I've got this ✓"

---

## Understanding Risk Scores

### How Alerts Work

Priority Alerts checks 4 things:

1. **⏰ Time pressure**  
   → Deadline < 2 hours = High risk  
   → Deadline < 6 hours = Medium risk

2. **📚 Team workload**  
   → Assignee has > 10 tasks = Medium risk  
   → No assignee = High risk

3. **🚨 Already overdue**  
   → Any overdue ticket = High risk

4. **📊 Historical data**  
   → Similar tickets usually take longer = Medium risk

### Risk Levels

| Level | Score | What to do |
|-------|-------|------------|
| 🔴 **Urgent** | 70+ | **Drop everything** - Assign or reassign NOW |
| 🟠 **Soon** | 40-69 | **Check today** - Review and plan |
| 🟢 **On Track** | 0-39 | **Monitor** - Keep an eye on it |

---

## Smart Suggestions

### What You'll See

**If ticket is unassigned:**
```
👤 Assign to someone now
```

**If assignee is overloaded:**
```
🔄 Reassign to Sarah (only 4 tasks)
```

**If ticket is overdue:**
```
📞 Call customer for quick update
⬆️ Escalate to manager
```

### Taking Action

Suggestions are **clickable buttons** in the admin:
1. Click suggestion button
2. System guides you through action
3. Alert updates automatically

---

## Email Notifications

### Who Gets Emails?

**Automatic emails sent to:**
- Ticket assignee (if set)
- For HIGH RISK tickets only
- Maximum once every 2 hours (no spam)

### Email Content

```
Hi John,

This ticket might miss its deadline:

Install new security camera at Gate 3

Here's why we're worried:
  • ⏰ Deadline in 47 minutes
  • 📚 You have 12 other tasks

What you can do:
  1. 🔄 Reassign to Sarah (only 3 tasks)
  2. 📞 Call customer for quick update

View ticket: https://yoursite.com/admin/y_helpdesk/ticket/123/

Need help? Reply to this email.
```

### Stop Notifications

Click **"I've got this ✓"** in admin to acknowledge and stop emails.

---

## Dashboard Integration

### Top Alerts Widget (Coming Soon)

See your top 10 priority alerts on the dashboard:

```
🔴 Urgent (3 tickets)
├─ T00045: Camera install - 23 min left
├─ T00082: Access card issue - Overdue 15 min
└─ T00091: Broken gate - No assignee

🟠 Soon (7 tickets)
├─ T00103: Visitor badge - 3 hours left
└─ ...
```

---

## Troubleshooting

### "No alerts appearing"

**Check Celery is running:**
```bash
celery -A intelliwiz_config inspect active
```

**Manually trigger check:**
```python
from apps.core.tasks.priority_alert_tasks import check_priority_alerts
result = check_priority_alerts.delay()
print(result.get())
```

### "Wrong risk level"

**View calculation details:**
```python
from apps.y_helpdesk.services.priority_alert_service import PriorityAlertService
from apps.y_helpdesk.models import Ticket

service = PriorityAlertService()
ticket = Ticket.objects.get(ticketno='T00123')
risk = service.check_ticket_risk(ticket)

print(f"Score: {risk['score']}")
print(f"Factors: {risk['risk_factors']}")
```

### "No emails sending"

**Check email settings:**
```python
# In Django shell
from django.core.mail import send_mail

send_mail(
    'Test',
    'This is a test',
    'from@example.com',
    ['to@example.com']
)
```

---

## Configuration

### Adjust Check Frequency

Edit `intelliwiz_config/settings/priority_alerts_schedule.py`:

```python
'check-priority-alerts': {
    'schedule': 900.0,  # Change to 15 minutes (900 seconds)
},
```

### Customize Risk Thresholds

Edit `apps/y_helpdesk/services/priority_alert_service.py`:

```python
# Time pressure
if remaining_minutes < 60:  # Change from 120 to 60 (1 hour)
    score += 40

# Assignee workload  
if other_tasks > 15:  # Change from 10 to 15
    score += 30
```

### Change Risk Levels

```python
# Determine risk level
if score >= 80:  # Change from 70 to 80
    risk_level = 'high'
elif score >= 50:  # Change from 40 to 50
    risk_level = 'medium'
```

---

## Best Practices

### For Team Leads

1. **Check urgent filter daily**  
   → Filter by "🔴 Urgent" every morning

2. **Review workload distribution**  
   → If same person keeps appearing, redistribute

3. **Track acknowledgment rate**  
   → Low rate = team ignoring alerts

4. **Adjust thresholds**  
   → Too many false alarms? Increase score requirements

### For Agents

1. **Acknowledge when you act**  
   → Click "I've got this ✓" so team knows

2. **Follow suggestions**  
   → They're based on real data

3. **Don't ignore urgent alerts**  
   → These tickets need immediate attention

4. **Update ticket status**  
   → Keeps alerts accurate

---

## Performance

### Database Impact

**Minimal:**
- Runs every 10 minutes
- Optimized queries with select_related
- Indexes on all filtered fields

**For 10,000+ tickets:**
- Consider every 15-30 minutes
- Add Redis caching
- Partition by tenant

### Memory Usage

**Lightweight:**
- ~50KB per prediction record
- 10,000 tickets = ~500MB
- Old predictions auto-cleaned after 30 days

---

## FAQs

**Q: Why don't I see alerts for all tickets?**  
A: Alerts only show for tickets with deadlines (SLA due date set)

**Q: Can I disable alerts for certain tickets?**  
A: Yes, acknowledge the alert - it won't send more emails

**Q: How accurate are the suggestions?**  
A: Based on real workload data and historical patterns

**Q: Can I customize the email template?**  
A: Yes, edit `apps/core/tasks/priority_alert_tasks.py`

**Q: Does this work with work orders too?**  
A: Not yet, but coming soon! Currently tickets only.

**Q: How do I export alert data?**  
A: Django Admin → Priority Alerts → Export (coming soon)

---

## Next Steps

1. ✅ **Test with sample tickets** - Create test tickets with various deadlines
2. ✅ **Configure email** - Set up email notifications
3. ✅ **Train team** - Show agents how to use alerts
4. ✅ **Monitor accuracy** - Adjust thresholds if needed
5. ✅ **Request features** - Tell us what would help!

---

**Questions?** See [Full Implementation Guide](../../PRIORITY_ALERTS_IMPLEMENTATION.md)

**Need help?** Contact the development team.
