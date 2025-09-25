# Escalation Setup Guide - UI Manual Configuration

## Prerequisites
Before setting up escalation, ensure you have:
- ✅ Ticket Categories configured (Found: Electrical, Site Crisis, Maintenance, Security, Operational)
- ✅ Active Users for assignment (Found: Test users and regular users)
- ✅ Groups for assignment (Found: Multiple groups)
- ✅ Business Units configured (Found: YTPL, SPS, SITE1, SITE2)

## Step-by-Step Guide

### Step 1: Access Escalation Matrix

1. **Login** to your YOUTILITY5 application
2. Navigate to: **`/helpdesk/escalationmatrix/`**
   - Or from menu: **Helpdesk → Escalation Matrix**

### Step 2: View Escalation List

The escalation list page shows all configured escalation rules. Initially, this will be empty.

### Step 3: Create New Escalation Rule

1. Click **"Add New"** or **"Create Escalation"** button
2. You'll be redirected to the escalation form

### Step 4: Configure Escalation Levels

#### A. Select Ticket Category
1. In the **"Escalation Template"** dropdown, select a ticket category:
   - Electrical
   - Site Crisis  
   - Maintenance
   - Security
   - Operational
   
   This determines which type of tickets will follow this escalation rule.

#### B. Add Escalation Levels

For each level, configure:

**Level 1 (First Escalation):**
1. Click **"New"** in the table
2. Set:
   - **Level**: 1
   - **Frequency**: Choose unit (MINUTE, HOUR, DAY, WEEK)
   - **Frequency Value**: Number (e.g., 2 for "2 hours")
   - **Assigned For**: Select "PEOPLE" or "GROUP"
   - If "PEOPLE": Select a user from dropdown
   - If "GROUP": Select a group from dropdown
3. Click **"Create"**

**Level 2 (Second Escalation):**
1. Click **"New"** again
2. Set:
   - **Level**: 2
   - **Frequency**: HOUR
   - **Frequency Value**: 4 (escalates after 4 hours)
   - **Assigned For**: GROUP
   - **Assigned Group**: Select "Youtility Group"
3. Click **"Create"**

**Level 3 (Final Escalation):**
1. Click **"New"** again
2. Set:
   - **Level**: 3
   - **Frequency**: DAY
   - **Frequency Value**: 1 (escalates after 1 day)
   - **Assigned For**: PEOPLE
   - **Assigned Person**: Select a senior manager
3. Click **"Create"**

### Step 5: Save Configuration

Click **"Save"** or **"Submit"** to save the escalation matrix.

## Example Configuration

### For "Site Crisis" Category:

| Level | After | Unit | Assign To | Who |
|-------|-------|------|-----------|-----|
| 1 | 30 | MINUTE | PEOPLE | SURESH SINGH |
| 2 | 2 | HOUR | GROUP | Security Team |
| 3 | 1 | DAY | PEOPLE | Site Manager |

### For "Maintenance" Category:

| Level | After | Unit | Assign To | Who |
|-------|-------|------|-----------|-----|
| 1 | 2 | HOUR | PEOPLE | Maintenance Staff |
| 2 | 6 | HOUR | GROUP | Youtility Group |
| 3 | 2 | DAY | PEOPLE | Operations Head |

## How Escalation Works

1. **Ticket Creation**: When a ticket is created with a category that has escalation configured
2. **Timer Starts**: The escalation timer begins from ticket creation time
3. **Level 1 Trigger**: If ticket is not resolved within Level 1 time, it escalates:
   - Ticket reassigned to Level 1 person/group
   - `isescalated` flag set to true
   - Notification sent (if email configured)
4. **Level 2 Trigger**: If still unresolved after Level 2 time, escalates again
5. **Continue**: Process continues through all configured levels

## Testing Your Configuration

### Manual Test:
1. Create a test ticket:
   - Go to **`/helpdesk/ticket/`**
   - Create new ticket
   - Select category with escalation configured
   - Set status to "OPEN"
   
2. Wait for escalation time or manually trigger:
   ```python
   # In Django shell
   from background_tasks.tasks import ticket_escalation
   result = ticket_escalation()
   ```

3. Check ticket details:
   - Level should increase
   - Assignment should change
   - `isescalated` should be true

## Important Notes

1. **Celery Required**: For automatic escalation, ensure Celery Beat is running:
   ```bash
   celery -A intelliwiz_config beat -l info
   celery -A intelliwiz_config worker -l info
   ```

2. **Time Calculation**: 
   - Escalation time is cumulative from ticket creation
   - Not from the previous escalation level

3. **Email Notifications**:
   - Optional email field in escalation matrix
   - Sends notifications when escalation occurs

4. **Business Unit Specific**:
   - Escalation rules are per BU and Client
   - Different sites can have different escalation rules

## Troubleshooting

### Escalation Not Working?
1. Check if escalation matrix is configured for the ticket category
2. Verify ticket status is eligible (OPEN, NEW)
3. Check if Celery is running
4. Verify time has passed for escalation

### View Escalation History:
Check ticket's `ticketlog` field for escalation history

### Manual Override:
Admins can manually change ticket level and assignment if needed

## URL Reference

- **List View**: `/helpdesk/escalationmatrix/`
- **Add/Edit Form**: `/helpdesk/escalationmatrix/?action=get_escalationlevels&id={category_id}`
- **Ticket List**: `/helpdesk/ticket/`

## Database Check

To verify your escalation configuration via Django shell:

```python
from apps.y_helpdesk.models import EscalationMatrix

# Check all escalation rules
rules = EscalationMatrix.objects.all()
for rule in rules:
    print(f"Level {rule.level}: {rule.frequencyvalue} {rule.frequency}")
    if rule.assignedperson:
        print(f"  -> Assigned to: {rule.assignedperson.peoplename}")
    if rule.assignedgroup:
        print(f"  -> Assigned to group: {rule.assignedgroup.groupname}")
```

## Next Steps

After configuration:
1. Test with a sample ticket
2. Monitor escalation logs
3. Adjust timing based on your SLA requirements
4. Train staff on escalation notifications