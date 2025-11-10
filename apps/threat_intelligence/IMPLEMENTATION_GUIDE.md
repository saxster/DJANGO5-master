# Threat Intelligence System - Implementation Guide

## Integration Status

✅ **Phase 1 Complete** (Nov 2025):
- V2 API endpoints implemented
- Work order auto-creation integrated
- Celery beat schedule configured
- WebSocket routing added
- URL patterns registered

## Overview

The Intelligent Threat & Event Monitoring (ITEM) system provides proactive security intelligence for multi-tenant facility management through OSINT aggregation, ML-powered analysis, and context-aware alerting.

## Architecture

### Core Components

1. **Data Ingestion Layer** (`IntelligenceSource`)
   - Multi-source data collection (News APIs, Weather, Government alerts, Social media)
   - Configurable refresh intervals and priority-based fetching
   - Rate limit handling and failure recovery

2. **Analysis Pipeline** (`ThreatEvent` + `IntelligenceAnalyzer`)
   - NLP classification (category, severity, confidence scoring)
   - Entity extraction and keyword analysis
   - Geospatial impact radius calculation

3. **Multi-Tenant Matching** (`TenantIntelligenceProfile`)
   - PostGIS geofence monitoring with buffer zones
   - Per-tenant category filters and severity thresholds
   - Customizable alert urgency levels

4. **Alert Distribution** (`IntelligenceAlert` + `AlertDistributor`)
   - Multi-channel delivery (WebSocket, SMS, Email)
   - Auto-work order creation for critical threats
   - Operational hours and digest mode support

5. **Learning & Optimization** (`TenantLearningProfile` + feedback loop)
   - ML auto-tuning based on tenant responses
   - Category-specific sensitivity adjustment
   - Source trust scoring

6. **Collective Intelligence** (`CollectiveIntelligencePattern`)
   - Privacy-preserving cross-tenant pattern sharing
   - Response protocol effectiveness tracking
   - Anonymized best practices recommendations

## Database Schema

### Key Models

```
IntelligenceSource (1) ──> (N) ThreatEvent
ThreatEvent (1) ──> (N) IntelligenceAlert
ThreatEvent (1) ──> (N) EventEscalationHistory
TenantIntelligenceProfile (1) ──> (N) IntelligenceAlert
TenantIntelligenceProfile (1) ──> (1) TenantLearningProfile
CollectiveIntelligencePattern (independent - aggregated data)
```

### Future-Proofing Features

**Already Built-In:**
- `IntelligenceAlert.tenant_response` - Feedback loop for ML learning
- `EventEscalationHistory` - Predictive escalation tracking
- `CollectiveIntelligencePattern` - Cross-tenant learning infrastructure
- `TenantLearningProfile` - Per-tenant ML model storage
- JSON fields for extensibility without migrations

**ML Placeholders:**
- `confidence_score` fields ready for ML confidence outputs
- `category_weights` for feature importance
- `source_trust_scores` for Bayesian source reliability
- `feature_importance` for explainability

## Implementation Phases

### Phase 1: Core Intelligence (2-3 weeks)
**Goal:** Single-source ingestion, basic classification, email alerts

**Tasks:**
1. ✅ Create models and admin interface
2. ✅ Build `IntelligenceAnalyzer` (keyword-based NLP)
3. ✅ Build `AlertDistributor` (geospatial matching)
4. ✅ Create Celery tasks for ingestion/processing
5. 🔲 Implement NewsAPI or OpenWeather integration
6. 🔲 Add email notification delivery
7. 🔲 Create Django admin dashboard for monitoring
8. 🔲 Write tests for core matching logic

**Deliverable:** Tenants receive email alerts for weather warnings near their facilities

### Phase 2: Multi-Channel & Integration (3-4 weeks)
**Goal:** WebSocket delivery, work order creation, expanded sources

**Tasks:**
1. 🔲 Integrate with existing WebSocket infrastructure (NOC dashboards)
2. 🔲 Build work order auto-creation service
3. 🔲 Add SMS delivery (Twilio integration)
4. 🔲 Create V2 REST API endpoints for alert retrieval
5. 🔲 Add multiple news sources (GDELT, Reuters RSS)
6. 🔲 Build admin analytics dashboard (alert metrics)
7. 🔲 Implement operational hours/digest mode

**Deliverable:** Real-time alerts on NOC dashboards with auto-work orders

### Phase 3: ML & Predictive Features (4-6 weeks)
**Goal:** ML classification, feedback learning, predictive escalation

**Tasks:**
1. 🔲 Replace keyword NLP with transformer-based classification (BERT/DistilBERT)
2. 🔲 Implement feedback loop ML pipeline
3. 🔲 Build escalation prediction model
4. 🔲 Create collective intelligence aggregation jobs
5. 🔲 Add explainability features (SHAP values)
6. 🔲 Build pattern recommendation engine
7. 🔲 Optimize geospatial queries with PostGIS indexing

**Deliverable:** Self-tuning alerts with predictive warnings 24-48hrs ahead

## Integration Points

### Existing Apps

**`apps.noc`** - Security monitoring dashboards
- Display intelligence feed in real-time
- Integrate with existing alert panels
- Map overlay for geospatial threats

**`apps.work_order_management`** - Work orders
- Auto-create response work orders for CRITICAL/HIGH threats
- Link alerts to work orders for audit trail
- Template-based protocols (evacuation, lockdown, etc.)

**`apps.scheduler`** - Patrol scheduling
- Adjust patrol routes to avoid threat zones
- Increase patrols near active threats
- Notify scheduled personnel of threats

**`apps.peoples`** - Personnel management
- Notify on-duty staff by role/location
- Track who acknowledged alerts
- Emergency contact management

**`apps.reports`** - Analytics
- Intelligence briefing reports
- Trend analysis (threat frequency, response effectiveness)
- Executive dashboards

## Configuration

### Celery Beat Schedule

Add to `intelliwiz_config/celery_config.py`:

```python
'intelligence-fetch-sources': {
    'task': 'threat_intelligence.fetch_intelligence_from_sources',
    'schedule': crontab(minute='*/15'),  # Every 15 minutes
    'options': {'queue': 'intelligence'},
},
'intelligence-update-learning-profiles': {
    'task': 'threat_intelligence.update_learning_profiles',
    'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    'options': {'queue': 'ml'},
},
```

### Queue Configuration

Add specialized queues:
- `intelligence` - Data ingestion and processing
- `alerts` - Alert distribution
- `ml` - ML training and pattern analysis

### Required Environment Variables

```bash
# API Keys (store in secrets management)
NEWSAPI_KEY=your_key_here
OPENWEATHER_API_KEY=your_key_here
TWILIO_ACCOUNT_SID=your_sid_here
TWILIO_AUTH_TOKEN=your_token_here

# Configuration
INTELLIGENCE_ENABLED=true
INTELLIGENCE_MIN_CONFIDENCE=0.6
```

### PostGIS Setup

Ensure PostGIS extension is enabled:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

## Usage Examples

### 1. Create Intelligence Profile for Tenant

```python
from django.contrib.gis.geos import Polygon
from apps.threat_intelligence.models import TenantIntelligenceProfile
from apps.tenants.models import Tenant

tenant = Tenant.objects.get(name='ACME Security')

# Define geofence around facilities (example: NYC area)
geofence = Polygon((
    (-74.0, 40.7), (-73.9, 40.7), (-73.9, 40.8), (-74.0, 40.8), (-74.0, 40.7)
))

profile = TenantIntelligenceProfile.objects.create(
    tenant=tenant,
    monitored_locations=geofence,
    buffer_radius_km=10.0,
    threat_categories=['POLITICAL', 'WEATHER', 'CRIME'],
    minimum_severity='MEDIUM',
    minimum_confidence=0.6,
    alert_urgency_critical='IMMEDIATE',
    enable_websocket=True,
    enable_sms=True,
    enable_work_order_creation=True,
)
```

### 2. Add Intelligence Source

```python
from apps.threat_intelligence.models import IntelligenceSource

source = IntelligenceSource.objects.create(
    name='OpenWeather Severe Weather Alerts',
    source_type='WEATHER_API',
    endpoint_url='https://api.openweathermap.org/data/2.5/weather',
    api_key_name='OPENWEATHER_API_KEY',
    refresh_interval_minutes=30,
    priority=1,  # High priority
    config={
        'alerts_only': True,
        'severity_threshold': 'moderate',
    }
)
```

### 3. Process Feedback (Learning Loop)

```python
from apps.threat_intelligence.models import IntelligenceAlert

alert = IntelligenceAlert.objects.get(id=123)

# User marks as actionable
alert.mark_actionable(
    user=request.user,
    notes="Initiated facility lockdown protocol"
)

# Or mark as false positive
alert.mark_false_positive(
    user=request.user,
    notes="Event was outside our operational area"
)
```

## Testing Strategy

### Unit Tests
- NLP classification accuracy
- Geospatial matching logic
- Distance calculations
- Severity/urgency mapping

### Integration Tests
- End-to-end ingestion → alert flow
- Multi-tenant isolation
- Feedback loop updates

### Performance Tests
- Geospatial query optimization (PostGIS indexes)
- Concurrent alert processing
- Large-scale tenant matching

## Security Considerations

1. **API Key Management** - Store in environment variables, never in code
2. **Tenant Isolation** - All queries filtered by tenant (TenantAwareModel)
3. **Privacy** - Collective intelligence patterns are fully anonymized
4. **Rate Limiting** - Respect external API limits, handle 429 responses
5. **Data Retention** - Auto-archive old events (define retention policy)

## Performance Optimization

### Database Indexes
- PostGIS spatial indexes on all geography fields
- GIN indexes on JSON fields (entities, keywords)
- Composite indexes on common query patterns

### Caching Strategy
- Cache geofence calculations (Redis)
- Cache source configurations
- Cache ML model predictions (short TTL)

### Query Optimization
- Use `select_related()` for foreign keys
- Use `prefetch_related()` for M2M relationships
- Batch alert creation (bulk_create)

## Monitoring & Observability

### Key Metrics
- Ingestion latency per source
- Alert delivery success rate
- Tenant response rates (actionable vs false positive)
- ML model accuracy over time

### Alerts
- Source fetch failures (> 3 consecutive)
- Alert delivery failures
- Processing queue backlog
- ML confidence drift

### Dashboards
- Real-time threat map
- Source health status
- Tenant engagement metrics
- Pattern discovery trends

## Future Enhancements

### Short-term (3-6 months)
- [ ] Add more intelligence sources (GDELT, social media APIs)
- [ ] Implement proper NER (spaCy/transformers)
- [ ] Build mobile app alert delivery
- [ ] Add threat intelligence API for third-party integrations

### Long-term (6-12 months)
- [ ] Deep learning event classification (fine-tuned BERT)
- [ ] Predictive escalation models (LSTM/Prophet)
- [ ] Collaborative filtering for pattern recommendations
- [ ] Integration with insurance/compliance reporting
- [ ] Threat intelligence marketplace (share/purchase curated feeds)

## Support & Troubleshooting

### Common Issues

**Alerts not being created:**
- Check tenant geofences overlap with event locations
- Verify severity/confidence thresholds not too restrictive
- Review category filters

**Poor classification accuracy:**
- Start with Phase 1 keyword-based approach
- Collect feedback data before implementing ML
- Tune confidence thresholds per tenant

**Performance degradation:**
- Check PostGIS indexes are present
- Monitor queue backlogs
- Review slow query logs

## Contributing

When extending this system:

1. **Follow architecture limits** - Models < 150 lines, methods < 30 lines
2. **Add tests** - Minimum 80% coverage for new features
3. **Update this guide** - Document new sources, patterns, integrations
4. **Preserve future-proofing** - Don't remove ML-ready fields even if unused
5. **Maintain multi-tenancy** - Always test tenant isolation

---

**Last Updated:** November 10, 2025
**Maintainer:** Development Team
**Review Cycle:** After each phase completion
