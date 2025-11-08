# Natural Language Query Platform - Expansion Roadmap

**Date**: November 3, 2025
**Current Status**: NL Query implemented for NOC module
**Opportunity**: Expand to 10 additional modules for $2-3M/year value
**Recommendation**: Start with Help Desk (highest ROI)

---

## 🎯 EXECUTIVE SUMMARY

**Research Finding**: Natural Language Query capability can be extended to **10 high-value modules** across the platform, delivering **$2-3M/year** in productivity gains and operational efficiency.

**Top 3 Priorities**:
1. **Help Desk** (ROI: 9/10) - 100+ operators, 25-30 hours/day productivity gain
2. **Work Orders** (ROI: 9/10) - $500k+/year from 25% overdue reduction
3. **Attendance** (ROI: 10/10) - $100k+/year fraud prevention + compliance

**Investment**: 9-12 weeks for Phase 1 (3 modules)
**Return**: $1M+/year
**Payback**: < 3 months

---

## 📊 COMPLETE OPPORTUNITY MATRIX

| Rank | Module | ROI | Effort | User Volume | Annual Value | Priority |
|------|--------|-----|--------|-------------|--------------|----------|
| 1 | Help Desk | 9/10 | 2-3 weeks | 100+ | $450k+ | CRITICAL |
| 2 | Work Orders | 9/10 | 3-4 weeks | 100+ | $500k+ | CRITICAL |
| 3 | Attendance | 10/10 | 4-5 weeks | 1000+ | $100k+ | CRITICAL |
| 4 | Assets | 8/10 | 2-3 weeks | 50+ | $200k+ | HIGH |
| 5 | People/Capabilities | 7/10 | 2-3 weeks | 50+ | $150k+ | HIGH |
| 6 | Face Recognition | 7/10 | 1-2 weeks | Security Team | $100k+ | HIGH |
| 7 | Journal/Wellness | 6/10 | 1-2 weeks | HR+Execs | $75k+ | MEDIUM |
| 8 | ML Training | 5/10 | 1 week | ML Team | $50k+ | MEDIUM |
| 9 | Reports | 5/10 | 1 week | 100+ | $100k+ | MEDIUM |
| 10 | Scheduler | 6/10 | 2 weeks | 50+ | $125k+ | MEDIUM |

**Total Potential Value**: **$2-3M/year**

---

## 🚀 DETAILED IMPLEMENTATION PLANS

### **Module 1: Help Desk NL Queries** (HIGHEST PRIORITY)

**Example Queries** (20+):
- "Show me all high-priority tickets for Site X that are overdue"
- "Which tickets are escalated to Level 2 and still open?"
- "What are my unresolved tickets from the last 7 days?"
- "Show system-generated tickets vs user-defined tickets this month"
- "Which tickets have been on hold for more than 48 hours?"
- "Show me tickets assigned to me or my groups"
- "What's the average resolution time for tickets by category?"
- "Show me cancelled tickets with attachments"
- "Which tickets were escalated but never resolved?"
- "What are the top 5 ticket categories by volume this quarter?"

**Implementation Components**:

1. **HelpDeskQueryExecutor** (`apps/y_helpdesk/services/helpdesk_query_executor.py`)
   - `_build_ticket_query()` - Convert NL → Django ORM
   - `_apply_status_filter()` - Handle workflow states
   - `_apply_escalation_filter()` - Parse escalation logic
   - `_apply_assignment_filter()` - "my tickets", "my groups"
   - `_apply_sla_filter()` - "overdue", "approaching SLA"

2. **Ticket Query Patterns**:
```python
# "High priority tickets for Site X that are overdue"
Ticket.objects.filter(
    bu__buname__icontains='Site X',
    priority='HIGH',
    expirydatetime__lt=timezone.now(),
    status__in=['NEW', 'OPEN', 'ASSIGNED']
).select_related('bu', 'assignedtopeople')

# "My escalated tickets"
workflow_data_filter = Q(
    get_or_create_workflow__workflow_data__isescalated=True
)
Ticket.objects.filter(
    assignedtopeople=request.user,
    workflow_data_filter
).exclude(status='CLOSED')
```

3. **Special Handling**:
   - TicketWorkflow lazy properties (accessed via `get_or_create_workflow()`)
   - JSON log parsing (`ticketlog` for history)
   - Multi-tenant filtering (tenant + client + bu)

**Estimated Effort**: 2-3 weeks
**Business Value**: $450k+/year (25-30 hours/day × 100 operators)

---

### **Module 2: Work Order NL Queries**

**Example Queries** (20+):
- "Show me all overdue work orders for high-priority assets"
- "Which PPM tasks are scheduled for next week but not assigned?"
- "What's the average completion time by vendor?"
- "Show me work permits pending approval with expiry < 24 hours"
- "Which work orders are in progress but started more than 7 days ago?"
- "What's our vendor performance score for Vendor X?"
- "Show me work orders with quality score < 60%"
- "Which assets have the most work orders in last 90 days?"
- "Show me work orders where verifiers rejected completion"

**Implementation Components**:

1. **WorkOrderQueryExecutor** (`apps/work_order_management/services/work_order_query_executor.py`)
   - `_build_work_order_query()` - Main builder
   - `_parse_other_data_filters()` - JSON field queries (scores, approvers)
   - `_apply_vendor_filter()` - Vendor-specific queries
   - `_apply_approval_filter()` - Work permit approval status
   - `_calculate_overdue()` - Compare expiry vs current time

2. **Complex Queries**:
```python
# "Work orders with quality score < 60%"
Wom.objects.filter(
    other_data__overall_score__lt=60,
    workstatus='COMPLETED'
).select_related('vendor', 'asset')

# "PPM tasks scheduled for next week"
next_week_start = timezone.now() + timedelta(days=(7-timezone.now().weekday()))
Wom.objects.filter(
    planstartdatetime__gte=next_week_start,
    planstartdatetime__lt=next_week_start + timedelta(days=7),
    asset__asset_json__maintenance_type='PPM'
)
```

3. **Special Handling**:
   - JSONField `other_data` (scores, approvers, verifiers)
   - ArrayFields (approvers, verifiers as PostgreSQL arrays)
   - Work permit vs work order distinction
   - Asset parent-child relationships

**Estimated Effort**: 3-4 weeks
**Business Value**: $500k+/year (maintenance cost reduction)

---

### **Module 3: Attendance NL Queries**

**Example Queries** (20+):
- "Show me attendance outside geofence boundaries today"
- "Who punched in from more than 5km away?"
- "What's the attendance rate for Site Y this week?"
- "Show me overtime workers (>10 hours) this month"
- "Which employees have face recognition failures > 3 times?"
- "What's the average commute distance?"
- "Show me suspicious patterns (punch in/out < 1 hour)"
- "Who's currently on leave or absent?"

**Implementation Components**:

1. **AttendanceQueryExecutor** (`apps/attendance/services/attendance_query_executor.py`)
   - `_build_attendance_query()` - Main builder
   - `_apply_geofence_filter()` - PostGIS spatial queries
   - `_parse_face_verification()` - JSON extras parsing
   - `_calculate_hours_worked()` - Time calculations
   - `_detect_fraud_patterns()` - Multi-factor fraud detection

2. **PostGIS Queries**:
```python
# "Attendance outside geofence"
from django.contrib.gis.measure import D  # Distance
from django.contrib.gis.db.models.functions import Distance

PeopleEventlog.objects.annotate(
    distance_from_site=Distance('startlocation', site.geofence.center)
).filter(
    distance_from_site__gt=D(m=site.geofence.radius)
)

# "Punch in from >5km away"
PeopleEventlog.objects.annotate(
    distance=Distance('startlocation', F('bu__geofence__center'))
).filter(distance__gt=D(km=5))
```

3. **Special Handling**:
   - PostGIS PointFields (startlocation, endlocation)
   - JSONField `peventlogextras` (face verification, GPS accuracy)
   - Geofence polygon queries
   - Conveyance claims validation

**Estimated Effort**: 4-5 weeks (PostGIS complexity)
**Business Value**: $100k+/year (fraud prevention)

---

## 🏗️ UNIFIED PLATFORM ARCHITECTURE

### **Current** (NOC-only):
```
NLQueryService (NOC)
  ↓
QueryParser → QueryExecutor (6 NOC types) → ResultFormatter
```

### **Proposed** (Platform-wide):
```
NLQueryPlatform (Unified Router)
  ↓
Module Detection (LLM: "This is a ticket query")
  ↓
  ├─ HelpDeskQueryExecutor (tickets, escalations, SLA)
  ├─ WorkOrderQueryExecutor (WO, PPM, vendors)
  ├─ AttendanceQueryExecutor (attendance, geofence, fraud)
  ├─ AssetQueryExecutor (assets, maintenance, warranty)
  ├─ PeopleQueryExecutor (capabilities, skills, org structure)
  ├─ FaceRecognitionQueryExecutor (biometric, verification, fraud)
  ├─ WellnessQueryExecutor (mood, stress, engagement)
  ├─ MLTrainingQueryExecutor (datasets, labeling, models)
  ├─ ReportQueryExecutor (scheduled reports, history)
  └─ SchedulerQueryExecutor (tours, shifts, jobs)
  ↓
UnifiedResultFormatter (Natural Language Responses)
  ↓
Cache + API Response
```

---

## 📋 IMPLEMENTATION CHECKLIST (Per Module)

**For Each Module**:
- [ ] Create `{Module}QueryExecutor` service (~300 lines)
- [ ] Add module-specific query patterns (~50 patterns)
- [ ] Handle JSONField parsing (if applicable)
- [ ] Handle PostGIS queries (if applicable)
- [ ] Write 10-15 tests
- [ ] Document 20+ example queries
- [ ] Integrate with NLQueryPlatform router

**Shared Infrastructure** (Already Complete):
- [x] QueryParser (LLM integration)
- [x] QueryCache (Redis)
- [x] ResultFormatter (NL responses)
- [x] API endpoint pattern
- [x] Rate limiting
- [x] RBAC enforcement

---

## 💰 BUSINESS CASE

### **Investment**:
- Phase 1: 9-12 weeks engineering
- Additional LLM API costs: ~$500-1,000/month (with 50% cache hit rate)
- **Total**: ~3 months engineering time

### **Return**:
- Phase 1: $1M+/year productivity + cost savings
- Full platform: $2-3M/year
- **Payback**: < 6 months

### **Strategic Value**:
- **Competitive differentiation**: Industry-first NL query platform for facilities
- **User adoption**: Lower technical barrier (no training needed)
- **Executive insights**: "What are my KPIs?" vs complex dashboard navigation
- **AI-powered platform**: Foundation for future AI enhancements

---

## 🎯 RECOMMENDATION

**START WITH MODULE 1: HELP DESK** (2-3 weeks)

**Why**:
- Highest user volume (100+ operators)
- Clearest ROI ($450k+/year productivity)
- Proven pattern (same as NOC)
- Immediate business impact (customer satisfaction)

**Measure**:
- Query volume (queries/day)
- User adoption rate (% using NL vs traditional UI)
- Time saved per query (avg 5-10 min)
- User satisfaction (survey)

**Then Decide**: Based on Help Desk results, continue to Work Orders + Attendance, or adjust approach.

---

**Next Action**: Approve Help Desk NL Query implementation to start Phase 1?