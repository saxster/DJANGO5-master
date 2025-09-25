# Production Support Setup Guide

## Overview

This guide covers setting up production support for the Django ORM migration system, including on-call procedures, incident management, and continuous improvement processes.

## Support Structure

### Support Tiers

#### Tier 1: Monitoring Alerts (Automated)
- **Response Time**: Immediate
- **Handles**: Automated alerts and notifications
- **Escalates**: Based on severity rules

#### Tier 2: On-Call Engineers  
- **Response Time**: 15 minutes
- **Handles**: Alert investigation, immediate fixes
- **Escalates**: Complex issues requiring code changes

#### Tier 3: Development Team
- **Response Time**: 1 hour
- **Handles**: Code fixes, architectural issues
- **Escalates**: Major incidents requiring rollback

### On-Call Rotation

```yaml
# on-call-schedule.yaml
schedule:
  timezone: UTC
  rotation_period: weekly
  
  primary:
    - name: Engineer A
      phone: +1-xxx-xxx-xxxx
      email: engineer.a@youtility.com
    - name: Engineer B
      phone: +1-xxx-xxx-xxxx
      email: engineer.b@youtility.com
      
  secondary:
    - name: Senior Engineer C
      phone: +1-xxx-xxx-xxxx
      email: engineer.c@youtility.com
      
  escalation:
    - name: Engineering Manager
      phone: +1-xxx-xxx-xxxx
      email: manager@youtility.com
```

## Alert Configuration

### PagerDuty Setup

```python
# monitoring/config.py
PAGERDUTY_CONFIG = {
    'integration_key': os.environ.get('PAGERDUTY_INTEGRATION_KEY'),
    'escalation_policy': {
        'critical': {
            'timeout': 5,  # minutes
            'escalate_to': 'secondary'
        },
        'high': {
            'timeout': 15,
            'escalate_to': 'secondary'
        },
        'medium': {
            'timeout': 30,
            'escalate_to': None
        }
    }
}
```

### Alert Rules

```python
# monitoring/alert_rules.py
ALERT_RULES = {
    'response_time_critical': {
        'condition': 'response_time_p99 > 2000',  # 2 seconds
        'severity': 'critical',
        'channels': ['pagerduty', 'slack', 'email'],
        'runbook': 'https://wiki.youtility.com/runbooks/high-response-time'
    },
    'database_connection_error': {
        'condition': 'db_connection_errors > 0',
        'severity': 'critical',
        'channels': ['pagerduty', 'slack'],
        'runbook': 'https://wiki.youtility.com/runbooks/database-connection'
    },
    'high_error_rate': {
        'condition': 'error_rate > 0.05',  # 5%
        'severity': 'high',
        'channels': ['slack', 'email'],
        'runbook': 'https://wiki.youtility.com/runbooks/high-error-rate'
    },
    'cache_degraded': {
        'condition': 'cache_hit_rate < 0.5',  # 50%
        'severity': 'medium',
        'channels': ['slack'],
        'runbook': 'https://wiki.youtility.com/runbooks/cache-issues'
    }
}
```

## Incident Management

### Incident Response Process

```markdown
# Incident Response Checklist

## 1. Detection (0-5 minutes)
- [ ] Alert received via PagerDuty/Slack/Email
- [ ] Acknowledge alert in PagerDuty
- [ ] Join incident channel (#incident-YYYYMMDD-XXX)

## 2. Triage (5-15 minutes)
- [ ] Verify the issue is real (not false positive)
- [ ] Determine severity (SEV1-SEV4)
- [ ] Identify affected systems/users
- [ ] Post initial assessment in incident channel

## 3. Investigation (15-30 minutes)
- [ ] Check monitoring dashboard
- [ ] Review recent deployments
- [ ] Analyze logs and metrics
- [ ] Run diagnostic commands

## 4. Mitigation (30-60 minutes)
- [ ] Implement temporary fix if possible
- [ ] Consider rollback if necessary
- [ ] Update status page
- [ ] Communicate with stakeholders

## 5. Resolution
- [ ] Verify fix is working
- [ ] Monitor for stability
- [ ] Close incident
- [ ] Schedule post-mortem
```

### Severity Levels

| Level | Response Time | Example | Escalation |
|-------|--------------|---------|------------|
| SEV1 | 5 minutes | Complete outage | Immediate page to all |
| SEV2 | 15 minutes | Partial outage, >10% users affected | Page primary on-call |
| SEV3 | 1 hour | Performance degradation | Slack notification |
| SEV4 | Next business day | Minor issues | Ticket creation |

### Communication Templates

```markdown
# Initial Response Template
**Incident**: [Brief description]
**Severity**: SEV[1-4]
**Impact**: [Who/what is affected]
**Status**: Investigating
**ETA**: [Initial estimate]
**Lead**: @[on-call-engineer]

# Update Template (every 30 min for SEV1/2)
**Update** ([timestamp])
- Current status: [Investigating/Mitigating/Monitoring]
- Actions taken: [What was done]
- Next steps: [What's planned]
- ETA: [Updated estimate]

# Resolution Template
**Resolved** ([timestamp])
- Root cause: [Brief description]
- Resolution: [What fixed it]
- Impact duration: [Start - End time]
- Follow-up: Post-mortem scheduled for [date/time]
```

## Diagnostic Tools

### Quick Health Check Script

```bash
#!/bin/bash
# quick_health_check.sh

echo "=== YOUTILITY3 Health Check ==="
echo "Timestamp: $(date)"
echo ""

# Check application status
echo "1. Application Status:"
systemctl status youtility3 | grep Active

# Check database connectivity
echo -e "\n2. Database Status:"
python manage.py dbshell -c "SELECT 'Database OK';" 2>&1 | grep -E "OK|ERROR"

# Check cache status
echo -e "\n3. Cache Status:"
python -c "from django.core.cache import cache; print('Cache OK' if cache.set('test', '1', 1) else 'Cache ERROR')"

# Check recent errors
echo -e "\n4. Recent Errors (last 10):"
grep ERROR /var/log/youtility3/application.log | tail -10

# Check performance metrics
echo -e "\n5. Current Performance:"
curl -s http://localhost:8000/monitoring/dashboard/ | jq '.performance_summary'
```

### Performance Analysis Script

```python
#!/usr/bin/env python
# analyze_performance.py

import sys
import json
from datetime import datetime, timedelta
import requests

def analyze_performance(hours=1):
    """Analyze performance for the last N hours"""
    
    # Get metrics
    response = requests.get(
        'http://localhost:8000/monitoring/metrics/',
        params={'hours': hours}
    )
    metrics = response.json()
    
    # Analyze patterns
    print(f"Performance Analysis - Last {hours} hours")
    print("=" * 50)
    
    # Response times
    rt = metrics.get('response_times', {})
    print(f"\nResponse Times:")
    print(f"  P50: {rt.get('p50', 'N/A')}ms")
    print(f"  P95: {rt.get('p95', 'N/A')}ms")
    print(f"  P99: {rt.get('p99', 'N/A')}ms")
    
    # Database queries
    db = metrics.get('database', {})
    print(f"\nDatabase Performance:")
    print(f"  Query P95: {db.get('query_time_p95', 'N/A')}ms")
    print(f"  Queries/Request: {db.get('queries_per_request', 'N/A')}")
    
    # Cache performance
    cache = metrics.get('cache', {})
    print(f"\nCache Performance:")
    print(f"  Hit Rate: {cache.get('hit_rate', 'N/A')}%")
    print(f"  Operations/min: {cache.get('ops_per_minute', 'N/A')}")
    
    # Identify issues
    issues = []
    if rt.get('p95', 0) > 1000:
        issues.append("High response time (>1s)")
    if db.get('query_time_p95', 0) > 100:
        issues.append("Slow database queries (>100ms)")
    if cache.get('hit_rate', 100) < 70:
        issues.append("Low cache hit rate (<70%)")
    
    if issues:
        print(f"\n⚠️  Issues Detected:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print(f"\n✅ No issues detected")

if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    analyze_performance(hours)
```

## Monitoring Dashboard

### Grafana Alerts

```json
{
  "alert": {
    "name": "High Response Time",
    "conditions": [
      {
        "type": "query",
        "query": {
          "model": {
            "expr": "django_response_time_seconds{quantile=\"0.95\"} > 1.0"
          }
        },
        "reducer": {
          "type": "avg"
        },
        "evaluator": {
          "type": "gt",
          "params": [1.0]
        }
      }
    ],
    "notifications": [
      {
        "uid": "slack-channel"
      },
      {
        "uid": "pagerduty-integration"
      }
    ]
  }
}
```

### Custom Dashboard Queries

```sql
-- Top slow endpoints
SELECT 
    endpoint,
    COUNT(*) as requests,
    AVG(response_time) as avg_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time) as p95_time
FROM request_logs
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY endpoint
HAVING COUNT(*) > 10
ORDER BY p95_time DESC
LIMIT 10;

-- Cache effectiveness by prefix
SELECT 
    SPLIT_PART(cache_key, ':', 1) as key_prefix,
    SUM(CASE WHEN hit THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as hit_rate,
    COUNT(*) as total_requests
FROM cache_logs
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY key_prefix
ORDER BY total_requests DESC;
```

## Post-Incident Process

### Post-Mortem Template

```markdown
# Post-Mortem: [Incident Title]

**Date**: [YYYY-MM-DD]
**Duration**: [Start time - End time]
**Severity**: SEV[1-4]
**Author**: [Your name]
**Reviewers**: [Team members]

## Summary
[1-2 sentence summary of what happened]

## Impact
- **Users affected**: [Number/%]
- **Features affected**: [List]
- **Revenue impact**: [$X or N/A]
- **SLA impact**: [Yes/No]

## Timeline
- **HH:MM** - Alert triggered
- **HH:MM** - On-call engineer acknowledged
- **HH:MM** - [Each significant event]
- **HH:MM** - Issue resolved
- **HH:MM** - Monitoring confirmed stable

## Root Cause
[Detailed explanation of why this happened]

## Contributing Factors
1. [Factor 1]
2. [Factor 2]

## What Went Well
- [Positive aspect 1]
- [Positive aspect 2]

## What Could Be Improved
- [Improvement 1]
- [Improvement 2]

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| [Action 1] | @person | YYYY-MM-DD | TODO |
| [Action 2] | @person | YYYY-MM-DD | TODO |

## Lessons Learned
[Key takeaways for the team]
```

### Action Item Tracking

```python
# scripts/track_action_items.py
#!/usr/bin/env python

import json
from datetime import datetime
from pathlib import Path

class ActionItemTracker:
    def __init__(self):
        self.items_file = Path("action_items.json")
        self.items = self.load_items()
    
    def load_items(self):
        if self.items_file.exists():
            with open(self.items_file) as f:
                return json.load(f)
        return []
    
    def add_item(self, action, owner, due_date, incident_id):
        item = {
            'id': len(self.items) + 1,
            'action': action,
            'owner': owner,
            'due_date': due_date,
            'incident_id': incident_id,
            'status': 'TODO',
            'created': datetime.now().isoformat()
        }
        self.items.append(item)
        self.save_items()
        return item
    
    def update_status(self, item_id, status):
        for item in self.items:
            if item['id'] == item_id:
                item['status'] = status
                item['updated'] = datetime.now().isoformat()
                self.save_items()
                return item
        return None
    
    def get_overdue_items(self):
        today = datetime.now().date()
        overdue = []
        for item in self.items:
            if item['status'] != 'DONE':
                due = datetime.fromisoformat(item['due_date']).date()
                if due < today:
                    overdue.append(item)
        return overdue
    
    def save_items(self):
        with open(self.items_file, 'w') as f:
            json.dump(self.items, f, indent=2)

# Usage
tracker = ActionItemTracker()
tracker.add_item(
    action="Add index on user_activity.created_at",
    owner="@engineer.a",
    due_date="2024-02-01",
    incident_id="INC-2024-001"
)
```

## Continuous Improvement

### Weekly Review Meeting

```markdown
# Weekly Operations Review Agenda

1. **Metrics Review** (10 min)
   - Availability %
   - Performance trends
   - Alert volume
   - MTTR (Mean Time To Recovery)

2. **Incident Review** (15 min)
   - Incidents this week
   - Post-mortem findings
   - Action item status

3. **Upcoming Changes** (10 min)
   - Planned deployments
   - Maintenance windows
   - Risk assessment

4. **Process Improvements** (10 min)
   - Runbook updates
   - Automation opportunities
   - Training needs

5. **Team Feedback** (5 min)
   - On-call experience
   - Tool improvements
   - Documentation gaps
```

### Performance Baseline Updates

```python
#!/usr/bin/env python
# update_performance_baseline.py

import json
from datetime import datetime, timedelta
from monitoring.views import get_performance_summary

def update_baseline():
    """Update performance baseline based on last 30 days"""
    
    # Get 30-day metrics
    summary = get_performance_summary(days=30)
    
    baseline = {
        'updated': datetime.now().isoformat(),
        'response_time': {
            'p50': summary['response_times']['p50'],
            'p95': summary['response_times']['p95'],
            'p99': summary['response_times']['p99']
        },
        'database': {
            'query_time_p95': summary['database']['query_time_p95'],
            'queries_per_request': summary['database']['avg_queries_per_request']
        },
        'cache': {
            'hit_rate': summary['cache']['hit_rate']
        },
        'error_rate': summary['error_rate']
    }
    
    # Save baseline
    with open('performance_baseline.json', 'w') as f:
        json.dump(baseline, f, indent=2)
    
    print(f"Baseline updated: {datetime.now()}")
    print(json.dumps(baseline, indent=2))
    
    # Check for degradation
    if baseline['response_time']['p95'] > 1000:
        print("⚠️  WARNING: Baseline P95 response time > 1s")
    
    return baseline

if __name__ == "__main__":
    update_baseline()
```

## Integration with External Tools

### Slack Integration

```python
# monitoring/integrations/slack.py
import requests
import json

class SlackNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
    
    def send_alert(self, alert):
        """Send formatted alert to Slack"""
        
        color = {
            'critical': '#FF0000',
            'high': '#FF9900',
            'medium': '#FFCC00',
            'low': '#00CC00'
        }.get(alert['severity'], '#808080')
        
        payload = {
            'attachments': [{
                'color': color,
                'title': f"{alert['severity'].upper()}: {alert['title']}",
                'text': alert['description'],
                'fields': [
                    {
                        'title': 'Metric',
                        'value': alert['metric'],
                        'short': True
                    },
                    {
                        'title': 'Value',
                        'value': alert['value'],
                        'short': True
                    }
                ],
                'footer': 'YOUTILITY3 Monitoring',
                'ts': alert['timestamp'],
                'actions': [
                    {
                        'type': 'button',
                        'text': 'View Dashboard',
                        'url': alert['dashboard_url']
                    },
                    {
                        'type': 'button',
                        'text': 'Runbook',
                        'url': alert['runbook_url']
                    }
                ]
            }]
        }
        
        response = requests.post(
            self.webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'}
        )
        
        return response.status_code == 200
```

### JIRA Integration

```python
# monitoring/integrations/jira.py
from jira import JIRA

class JiraIntegration:
    def __init__(self, server, username, api_token):
        self.jira = JIRA(
            server=server,
            basic_auth=(username, api_token)
        )
    
    def create_incident_ticket(self, incident):
        """Create JIRA ticket for incident tracking"""
        
        issue_dict = {
            'project': 'OPS',
            'summary': f"[{incident['severity']}] {incident['title']}",
            'description': self._format_description(incident),
            'issuetype': {'name': 'Incident'},
            'priority': {'name': self._map_priority(incident['severity'])},
            'labels': ['production', 'incident', 'orm-migration'],
            'customfield_12345': incident['incident_id']  # Custom field
        }
        
        issue = self.jira.create_issue(fields=issue_dict)
        return issue.key
    
    def _format_description(self, incident):
        return f"""
h3. Incident Details
* *Start Time*: {incident['start_time']}
* *Duration*: {incident['duration']}
* *Impact*: {incident['impact']}

h3. Root Cause
{incident['root_cause']}

h3. Resolution
{incident['resolution']}

h3. Action Items
{incident['action_items']}
        """
    
    def _map_priority(self, severity):
        return {
            'critical': 'Highest',
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low'
        }.get(severity, 'Medium')
```

## Training and Documentation

### On-Call Training Checklist

```markdown
# On-Call Engineer Training Checklist

## Prerequisites
- [ ] Access to production systems
- [ ] PagerDuty account configured
- [ ] Slack access to #incidents channel
- [ ] VPN setup for emergency access
- [ ] Phone configured for alerts

## Training Sessions
- [ ] System architecture overview (2 hours)
- [ ] Monitoring and alerting walkthrough (1 hour)
- [ ] Common issues and solutions (2 hours)
- [ ] Incident response procedures (1 hour)
- [ ] Shadow current on-call (1 week)

## Hands-On Practice
- [ ] Respond to test alert
- [ ] Run diagnostic scripts
- [ ] Access monitoring dashboards
- [ ] Create test incident ticket
- [ ] Perform rollback procedure (staging)

## Knowledge Verification
- [ ] Explain ORM migration architecture
- [ ] Identify slow query from logs
- [ ] Demonstrate cache clearing
- [ ] Show performance analysis
- [ ] Draft incident communication

## Sign-Off
- [ ] Manager approval
- [ ] Current on-call approval
- [ ] Added to rotation schedule
```

### Documentation Maintenance

```bash
#!/bin/bash
# update_docs.sh

# Check for outdated documentation
echo "Checking documentation currency..."

# Find docs not updated in 90 days
find docs/ -name "*.md" -mtime +90 -print | while read file; do
    echo "⚠️  $file - Not updated in 90+ days"
done

# Verify runbook links
echo -e "\nVerifying runbook links..."
grep -r "wiki.youtility.com/runbooks" docs/ | while read line; do
    url=$(echo $line | grep -oE 'https://[^ ]+')
    if ! curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200"; then
        echo "❌ Broken link: $url"
    fi
done

# Check for missing runbooks
echo -e "\nChecking for missing runbooks..."
for alert in $(grep -oE "'[^']+'" monitoring/config.py | grep -v runbook); do
    if ! grep -q "$alert" docs/PRODUCTION_RUNBOOKS.md; then
        echo "📝 Missing runbook for: $alert"
    fi
done
```

## Summary

This production support setup ensures:
1. **Rapid Response**: Clear escalation paths and procedures
2. **Effective Diagnosis**: Tools and scripts for quick analysis
3. **Continuous Improvement**: Regular reviews and updates
4. **Knowledge Sharing**: Documentation and training programs
5. **Integration**: Works with existing tools and workflows

Remember: Good production support is about preparation, clear communication, and continuous learning from incidents.