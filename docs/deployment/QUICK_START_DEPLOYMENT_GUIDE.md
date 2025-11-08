# Quick Start Deployment Guide
## Strategic Features - November 2025

**For**: Development & Operations Teams  
**Purpose**: Deploy Phase 1-2 features in production  
**Time**: 2-4 hours for complete deployment

---

## 📋 Pre-Deployment Checklist

### System Requirements
- [ ] Python 3.11.9 installed
- [ ] PostgreSQL 14.2+ running
- [ ] Redis 6+ running  
- [ ] Django 5.2+ environment
- [ ] Celery workers active
- [ ] SMTP configured (for notifications)

### New Dependencies
```bash
# Install additional packages
pip install channels==4.0.0
pip install channels-redis==4.1.0
pip install daphne==4.0.0
```

---

## 🚀 Phase 1: Foundation Features

### Step 1: Alert Suppression (5 minutes)

**Files Already Created**:
- `apps/noc/services/alert_rules_service.py`
- `background_tasks/alert_suppression_tasks.py`

**Integration**:
Add to your alert creation code:

```python
# In apps/noc/views.py or wherever alerts are created
from apps.noc.services.alert_rules_service import AlertRulesService

def create_alert(alert_data):
    # Check suppression BEFORE creating alert
    should_suppress, reason = AlertRulesService.should_suppress_alert({
        'device_id': alert_data['device_id'],
        'alert_type': alert_data['alert_type'],
        'severity': alert_data['severity'],
        'site_id': alert_data['site_id'],
        'tenant_id': alert_data['tenant_id']
    })
    
    if should_suppress:
        logger.info(f"Alert suppressed: {reason}")
        return None  # Don't create alert
    
    # Create alert as normal
    alert = Alert.objects.create(**alert_data)
    return alert
```

**Celery Beat Configuration**:
```python
# In settings/base.py or celerybeat_schedule
CELERYBEAT_SCHEDULE = {
    'monitor_suppression_effectiveness': {
        'task': 'apps.noc.monitor_suppression_effectiveness',
        'schedule': crontab(hour='*'),  # Every hour
        'args': (1,),  # Replace with actual tenant_id or iterate
    },
}
```

**Test**:
```python
python manage.py shell
>>> from apps.noc.services.alert_rules_service import AlertRulesService
>>> AlertRulesService.set_maintenance_window(site_id=1, start_time=timezone.now(), end_time=timezone.now() + timedelta(hours=2))
>>> # Create test alert and verify it's suppressed
```

---

### Step 2: Daily Activity Reports (10 minutes)

**Files Already Created**:
- `apps/reports/services/dar_service.py`
- `apps/reports/report_designs/daily_activity_report.html`

**Create View** (if not exists):
```python
# apps/reports/views.py
from apps.reports.services.dar_service import DARService
from apps.reports.utils.pdf_generator import generate_pdf  # Assuming this exists
from django.http import FileResponse

def generate_dar_view(request, site_id):
    shift_date = request.GET.get('date', timezone.now().date())
    shift_type = request.GET.get('shift_type', 'DAY')
    supervisor_notes = request.POST.get('notes', '')
    
    # Generate report data
    report_data = DARService.generate_dar(
        site_id=site_id,
        shift_date=shift_date,
        shift_type=shift_type,
        supervisor_notes=supervisor_notes
    )
    
    # Generate PDF
    pdf_file = generate_pdf('daily_activity_report.html', report_data)
    
    response = FileResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="DAR_{site_id}_{shift_date}.pdf"'
    return response
```

**URL Configuration**:
```python
# apps/reports/urls.py
path('dar/<int:site_id>/', views.generate_dar_view, name='generate_dar'),
```

**Test**:
```bash
# Visit in browser
http://localhost:8000/reports/dar/1/?date=2025-11-06&shift_type=DAY
```

---

### Step 3: Outbound Webhooks (15 minutes)

**Files Already Created**:
- `apps/integrations/` (complete app)
- `apps/integrations/services/webhook_dispatcher.py`
- `apps/integrations/services/teams_connector.py`

**Add to INSTALLED_APPS**:
```python
# settings/base.py
INSTALLED_APPS = [
    # ... existing
    'apps.integrations',
]
```

**Configure Webhook** (via Django admin or shell):
```python
# Create TypeAssist configuration for webhooks
from apps.onboarding.models import TypeAssist

config, created = TypeAssist.objects.get_or_create(
    client_id=1,  # Your tenant ID
    type='webhook_config',
    defaults={
        'other_data': {
            'webhooks': [
                {
                    'id': 'webhook-001',
                    'name': 'Primary Webhook',
                    'url': 'https://your-endpoint.com/webhook',
                    'events': ['ticket.created', 'alert.escalated'],
                    'secret': 'your-secret-key',
                    'enabled': True,
                    'retry_count': 3,
                    'timeout_seconds': 30
                }
            ],
            'teams': {
                'enabled': True,
                'webhook_url': 'https://outlook.office.com/webhook/YOUR_WEBHOOK_URL',
                'events': ['sos.triggered', 'sla.at_risk']
            }
        }
    }
)
config.save()
```

**Integration Example** (send webhook on ticket creation):
```python
# In apps/y_helpdesk/signals.py or views.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.y_helpdesk.models import Ticket
from apps.integrations.services.webhook_dispatcher import WebhookDispatcher

@receiver(post_save, sender=Ticket)
def ticket_created_webhook(sender, instance, created, **kwargs):
    if created:
        WebhookDispatcher.dispatch_event(
            tenant_id=instance.tenant_id,
            event_type='ticket.created',
            payload={
                'ticket_id': instance.id,
                'title': instance.title,
                'priority': instance.priority,
                'created_by': instance.created_by.username,
                'url': f"https://your-domain.com/tickets/{instance.id}/"
            }
        )
```

**Test**:
```python
python manage.py shell
>>> from apps.integrations.services.webhook_dispatcher import WebhookDispatcher
>>> result = WebhookDispatcher.dispatch_event(
...     tenant_id=1,
...     event_type='ticket.created',
...     payload={'test': 'data'}
... )
>>> print(result)
```

---

## 🎯 Phase 2: Premium Features

### Step 4: Real-Time Command Center (30 minutes)

**Files Already Created**:
- `apps/dashboard/` (complete app with WebSocket)

**Add to INSTALLED_APPS**:
```python
# settings/base.py
INSTALLED_APPS = [
    # ... existing
    'channels',
    'apps.dashboard',
]
```

**Configure Channel Layers** (Redis):
```python
# settings/base.py
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

**Update ASGI Configuration**:
```python
# intelliwiz_config/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from apps.dashboard import routing as dashboard_routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            dashboard_routing.websocket_urlpatterns
        )
    ),
})
```

**Add URL Routes**:
```python
# intelliwiz_config/urls.py
path('dashboard/', include('apps.dashboard.urls')),
```

**Run with Daphne** (for WebSocket support):
```bash
# Development
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application

# Production (supervisor/systemd)
daphne -u /tmp/daphne.sock intelliwiz_config.asgi:application
```

**Test WebSocket**:
1. Navigate to: `http://localhost:8000/dashboard/command-center/`
2. Check browser console: Should see "Command Center WebSocket connected"
3. Verify live data appears in panels

**Send Test Event**:
```python
from apps.dashboard.consumers import send_command_center_event

send_command_center_event(
    tenant_id=1,
    event_type='alert.created',
    data={
        'alert_id': 999,
        'severity': 'HIGH',
        'description': 'Test alert'
    }
)
# Should appear in real-time on command center dashboard
```

---

### Step 5: Predictive SLA Prevention (20 minutes)

**Files Already Created**:
- `background_tasks/sla_prevention_tasks.py`
- `apps/y_helpdesk/templates/tickets/sla_risk_badge.html`

**Add to Celery Beat**:
```python
# settings/base.py
CELERYBEAT_SCHEDULE = {
    # ... existing
    'predict_sla_breaches': {
        'task': 'apps.helpdesk.predict_sla_breaches',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}
```

**Restart Celery Beat**:
```bash
pkill -f celery
celery -A intelliwiz_config worker -l info &
celery -A intelliwiz_config beat -l info &
```

**Add Badge to Ticket Templates**:
```html
<!-- In apps/y_helpdesk/templates/tickets/list.html -->
<!-- Add after ticket title -->
{% include "tickets/sla_risk_badge.html" with ticket=ticket %}
```

**Test**:
```python
# Manually trigger task
from background_tasks.sla_prevention_tasks import predict_sla_breaches_task
result = predict_sla_breaches_task()
print(result)
# Check ticket.other_data for sla_predictions
```

---

### Step 6: Device Health & Assurance (20 minutes)

**Files Already Created**:
- `apps/monitoring/services/device_health_service.py`
- `background_tasks/device_monitoring_tasks.py`

**Create Monitoring App** (if doesn't exist):
```bash
mkdir -p apps/monitoring/services
touch apps/monitoring/__init__.py
touch apps/monitoring/apps.py
touch apps/monitoring/models.py
# Copy device_health_service.py from implementation
```

**Add to INSTALLED_APPS**:
```python
INSTALLED_APPS = [
    # ... existing
    'apps.monitoring',
]
```

**Add to Celery Beat**:
```python
CELERYBEAT_SCHEDULE = {
    # ... existing
    'monitor_device_health': {
        'task': 'apps.monitoring.monitor_device_health',
        'schedule': crontab(hour='*'),  # Hourly
        'args': (1,),  # Tenant ID
    },
}
```

**Test Health Score**:
```python
from apps.monitoring.services.device_health_service import DeviceHealthService

# Compute health for a device
health = DeviceHealthService.compute_health_score('CAM-001', tenant_id=1)
print(health)
# Output: {'health_score': 85.2, 'health_status': 'EXCELLENT', ...}

# Get all at-risk devices
at_risk = DeviceHealthService.get_devices_below_threshold(tenant_id=1, threshold=70)
print(f"Found {len(at_risk)} devices at risk")
```

---

## 🧪 Testing Deployment

### Smoke Tests

**1. Alert Suppression**:
```python
# Create 3 rapid alerts (should trigger flapping detection)
from apps.noc.services.alert_rules_service import AlertRulesService

for i in range(3):
    should_suppress, reason = AlertRulesService.should_suppress_alert({
        'device_id': 'TEST-001',
        'alert_type': 'OFFLINE',
        'severity': 'HIGH',
        'site_id': 1,
        'tenant_id': 1
    })
    print(f"Attempt {i+1}: Suppressed={should_suppress}, Reason={reason}")
# 3rd attempt should be suppressed due to flapping
```

**2. DAR Generation**:
```bash
curl -u username:password "http://localhost:8000/reports/dar/1/?date=2025-11-06&shift_type=DAY" > test_dar.pdf
# Open test_dar.pdf and verify content
```

**3. Webhooks**:
```python
from apps.integrations.services.webhook_dispatcher import WebhookDispatcher

result = WebhookDispatcher.dispatch_event(
    tenant_id=1,
    event_type='ticket.created',
    payload={'ticket_id': 123, 'title': 'Test'}
)
assert result['success'] == True
# Check your webhook endpoint for delivery
```

**4. Command Center**:
```bash
# Open browser
http://localhost:8000/dashboard/command-center/
# Check console: Should connect via WebSocket
# Verify all 6 panels load data
# Create a test SOS alert and verify it appears in real-time
```

**5. SLA Prevention**:
```python
from background_tasks.sla_prevention_tasks import predict_sla_breaches_task
result = predict_sla_breaches_task()
print(f"Processed {result['processed']} tickets, escalated {result['escalated']}")
```

**6. Device Health**:
```python
from apps.monitoring.services.device_health_service import DeviceHealthService
health = DeviceHealthService.compute_health_score('DEVICE-001', tenant_id=1)
assert 'health_score' in health
assert 0 <= health['health_score'] <= 100
```

---

## 📊 Monitoring & Verification

### Check Logs
```bash
# Application logs
tail -f logs/django.log | grep -E "alert_suppressed|dar_generated|webhook_sent|command_center|sla_prediction|device_health"

# Celery logs
tail -f logs/celery.log | grep -E "predict_sla_breaches|monitor_device_health|monitor_suppression"
```

### Verify Celery Tasks
```bash
# List scheduled tasks
celery -A intelliwiz_config inspect scheduled

# Check active tasks
celery -A intelliwiz_config inspect active

# Verify beat is running
ps aux | grep celery.*beat
```

### Verify Redis
```bash
# Check Redis connection
redis-cli ping
# Should return PONG

# Check suppression markers
redis-cli KEYS "alert_*"

# Check command center cache
redis-cli KEYS "command_center_summary:*"
```

### Verify WebSocket
```bash
# Check Daphne is running
ps aux | grep daphne

# Check WebSocket connections
netstat -an | grep :8000 | grep ESTABLISHED
```

---

## 🔧 Troubleshooting

### Issue: Alerts Not Being Suppressed
**Solution**:
```python
# Check if AlertRulesService is being called
# Add to alert creation code:
logger.info(f"Checking suppression for alert: {alert_data}")
should_suppress, reason = AlertRulesService.should_suppress_alert(alert_data)
logger.info(f"Suppression result: {should_suppress}, Reason: {reason}")
```

### Issue: DAR PDF Not Generating
**Solution**:
```bash
# Verify WeasyPrint is installed
pip install weasyprint
# Check template exists
ls apps/reports/report_designs/daily_activity_report.html
# Test PDF generation manually
python manage.py shell
>>> from apps.reports.services.dar_service import DARService
>>> data = DARService.generate_dar(1, date.today(), 'DAY')
>>> print(data.keys())
```

### Issue: Webhooks Not Delivering
**Solution**:
```python
# Check configuration
from apps.onboarding.models import TypeAssist
config = TypeAssist.objects.get(client_id=1, type='webhook_config')
print(config.other_data)

# Check rate limiting
from django.core.cache import cache
rate_key = "webhook_rate_limit:1"
print(f"Current rate limit count: {cache.get(rate_key, 0)}")

# Check dead-letter queue
# (Implementation needed for viewing DLQ)
```

### Issue: WebSocket Not Connecting
**Solution**:
```bash
# Verify Daphne is running (not runserver)
ps aux | grep daphne

# Check Redis connection
redis-cli ping

# Verify channel layers config
python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> print(channel_layer)

# Test send/receive
>>> from asgiref.sync import async_to_sync
>>> async_to_sync(channel_layer.send)('test_channel', {'type': 'test.message'})
```

### Issue: Celery Tasks Not Running
**Solution**:
```bash
# Check Celery worker is running
ps aux | grep celery.*worker

# Check Celery beat is running
ps aux | grep celery.*beat

# Check task registration
celery -A intelliwiz_config inspect registered

# Manually trigger task
python manage.py shell
>>> from background_tasks.sla_prevention_tasks import predict_sla_breaches_task
>>> result = predict_sla_breaches_task()
>>> print(result)
```

---

## 🎓 Best Practices

### 1. Logging
Always log key events:
```python
logger.info("feature_action_performed", extra={
    'user': request.user.username,
    'tenant_id': tenant_id,
    'feature': 'command_center',
    'action': 'dashboard_loaded'
})
```

### 2. Error Handling
Use specific exceptions:
```python
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

try:
    data = SomeService.operation()
except DATABASE_EXCEPTIONS as e:
    logger.error("operation_failed", extra={'error': str(e)}, exc_info=True)
    raise
```

### 3. Caching
Use appropriate TTLs:
```python
from django.core.cache import cache

# Short TTL for frequently changing data
cache.set('command_center_summary:1', data, 30)  # 30 seconds

# Long TTL for stable data
cache.set('device_health:CAM-001', health, 3600)  # 1 hour
```

### 4. Performance
Optimize queries:
```python
# Always use select_related and prefetch_related
tickets = Ticket.objects.filter(...).select_related('assigned_to', 'created_by').prefetch_related('attachments')
```

---

## 📞 Support

### Getting Help
- **Code Issues**: Review CLAUDE.md for standards
- **Integration Issues**: See PHASES_2_6_IMPLEMENTATION_COMPLETE.md
- **Architecture Questions**: See COMPREHENSIVE_IMPLEMENTATION_PLAN_NOV_2025.md
- **Business Questions**: See docs/PRD_STRATEGIC_FEATURES_NOV_2025.md

### Key Documents
1. FINAL_IMPLEMENTATION_STATUS_NOV_6_2025.md - Complete status
2. COMPREHENSIVE_IMPLEMENTATION_PLAN_NOV_2025.md - Full technical specs
3. IMPLEMENTATION_SUMMARY_NOV_6_2025.md - Integration patterns
4. STRATEGIC_FEATURES_COMPLETION_REPORT.md - Business value

---

## ✅ Post-Deployment Checklist

- [ ] All 6 features deployed to staging
- [ ] Smoke tests passed
- [ ] Celery tasks scheduled and running
- [ ] WebSocket connections working
- [ ] Webhooks delivering successfully
- [ ] Logs showing no errors
- [ ] Performance acceptable (<2s page loads)
- [ ] Pilot clients identified
- [ ] Training materials prepared
- [ ] Rollback plan documented

---

**Estimated Deployment Time**: 2-4 hours  
**Prerequisites**: Django 5.2+, PostgreSQL, Redis, Celery  
**Dependencies**: channels, channels-redis, daphne  
**Risk Level**: Low (zero schema changes, backward compatible)

**Next**: Deploy to 5-10 pilot clients and gather feedback before general availability.

---

*End of Quick Start Deployment Guide*
