# Worker Performance Analytics - Design Specification

**Date**: November 5, 2025  
**Purpose**: Individual vs Group performance benchmarking for field force management  
**Target Users**: Security guards, facility workers, supervisors, operations managers  

---

## Executive Summary

Design a **comprehensive performance analytics system** that tracks individual workers, teams, sites, and company-wide metrics across operational, quality, and compliance dimensions. Focus on **actionable insights** and **benchmarking** to drive operational excellence.

### Key Objectives
1. **Individual Accountability** - Track each worker's performance across all dimensions
2. **Team Benchmarking** - Compare teams, shifts, sites against each other
3. **Operational Intelligence** - Identify top performers and improvement areas
4. **Predictive Staffing** - Use performance data to optimize scheduling
5. **Client Reporting** - Demonstrate value to facility owners

---

## 📊 Performance Dimensions & Metrics

### 1. ATTENDANCE & RELIABILITY (30% weight)

#### Individual Metrics
```python
AttendanceMetrics:
    # Punctuality
    - on_time_punch_rate: float  # % punches within 5 min of scheduled
    - avg_late_minutes: float  # Average minutes late per shift
    - early_departure_rate: float  # % left early
    - perfect_attendance_streak: int  # Consecutive days on-time
    
    # Reliability
    - attendance_rate: float  # Worked hours / scheduled hours
    - no_call_no_show_count: int  # NCNS incidents
    - last_minute_callout_rate: float  # <4hr notice callouts
    - overtime_acceptance_rate: float  # Accepted OT / offered OT
    
    # Location Compliance
    - geofence_compliance_rate: float  # Punches within assigned location
    - wrong_site_incidents: int  # Punched at incorrect site
    - unauthorized_location_alerts: int  # GPS violations
    
    # Shift Adherence
    - scheduled_hours: float
    - worked_hours: float
    - overtime_hours: float
    - undertime_hours: float
```

#### Group Metrics (Team/Site/Company)
```python
TeamAttendanceMetrics:
    - team_attendance_rate: float
    - avg_on_time_rate: float
    - total_ncns_incidents: int
    - coverage_gap_hours: float  # Unfilled shifts
    - overtime_utilization_rate: float
    - geofence_compliance_rate: float
    
    # Distributions
    - on_time_rate_p25_p50_p75: tuple  # Quartiles
    - attendance_variance: float  # Team consistency
    - top_10_percent_avg: float  # Best performers
    - bottom_10_percent_avg: float  # Needs improvement
```

---

### 2. TASK & JOB PERFORMANCE (25% weight)

#### Individual Metrics
```python
TaskPerformanceMetrics:
    # Completion
    - tasks_assigned: int
    - tasks_completed: int
    - task_completion_rate: float
    - avg_completion_time_minutes: float
    
    # Quality
    - first_time_pass_rate: float  # No rework needed
    - rework_rate: float  # Tasks requiring redo
    - quality_audit_score_avg: float  # 0-100
    - defect_rate: float  # Tasks with issues
    
    # SLA Compliance
    - tasks_within_sla: int
    - sla_hit_rate: float  # %
    - avg_sla_buffer_minutes: float  # How early completed
    - sla_miss_rate: float
    
    # Productivity
    - tasks_per_worked_hour: float  # By task_type
    - high_priority_completion_rate: float
    - multi_tasking_efficiency: float  # Parallel tasks handled
    
    # Documentation
    - evidence_completeness_rate: float  # Photos/notes per SOP
    - report_quality_score: float  # Supervisor rating
```

#### Group Metrics
```python
TeamTaskMetrics:
    - total_tasks_completed: int
    - team_sla_hit_rate: float
    - avg_quality_score: float
    - task_distribution_fairness: float  # Std dev of tasks/person
    - cross_coverage_index: float  # Task types covered by team
    - escalation_rate: float  # Tasks escalated / total
```

---

### 3. TOUR & PATROL QUALITY (20% weight)

#### Individual Metrics
```python
PatrolMetrics:
    # Coverage
    - tours_assigned: int
    - tours_completed: int
    - tour_completion_rate: float
    - checkpoints_scanned: int
    - checkpoint_coverage_rate: float  # Scanned / expected
    
    # Timing
    - on_time_checkpoint_rate: float  # Within time window
    - avg_checkpoint_delay_minutes: float
    - tour_duration_variance: float  # Consistency
    - missed_checkpoint_count: int
    
    # Quality
    - incident_detection_count: int  # Issues found
    - patrol_thoroughness_score: float  # Time at checkpoints
    - route_adherence_rate: float  # Followed planned route
    - observation_report_quality: float  # Supervisor rating
    
    # Coverage Map
    - area_coverage_percentage: float  # Geographic coverage
    - high_risk_zone_visits: int  # Priority area attention
```

#### Group Metrics
```python
TeamPatrolMetrics:
    - site_coverage_rate: float  # % of site covered
    - checkpoint_hit_rate_avg: float
    - patrol_gaps_count: int  # Missed tours
    - incident_detection_rate: float  # Found / occurred
    - geographic_coverage_heatmap: dict  # PostGIS data
```

---

### 4. WORK ORDER & SERVICE (15% weight)

#### Individual Metrics
```python
WorkOrderMetrics:
    # Assignment
    - work_orders_assigned: int
    - work_orders_completed: int
    - avg_resolution_time_hours: float
    
    # Quality
    - first_fix_rate: float  # No return visits
    - customer_satisfaction_avg: float  # Requester rating
    - work_quality_score: float  # Inspector rating
    - rework_rate: float
    
    # Efficiency
    - planned_vs_actual_time_variance: float
    - parts_accuracy_rate: float  # Correct parts first time
    - emergency_response_time_avg: float
```

#### Group Metrics
```python
TeamWorkOrderMetrics:
    - team_resolution_time_median: float
    - backlog_per_person: float
    - sla_compliance_rate: float
    - customer_satisfaction_avg: float
```

---

### 5. COMPLIANCE & SAFETY (10% weight)

#### Individual Metrics
```python
ComplianceMetrics:
    # Certifications
    - certifications_current: int
    - certifications_expired: int
    - training_completion_rate: float
    - certification_renewal_on_time_rate: float
    
    # Safety
    - incident_rate_per_100_hours: float
    - near_miss_reports: int  # Positive indicator
    - ppe_compliance_rate: float  # Equipment checks
    - safety_violation_count: int
    
    # Documentation
    - daily_report_submission_rate: float
    - shift_handover_quality_score: float
    - sop_adherence_rate: float  # Follows procedures
    
    # Device Usage
    - device_check_in_rate: float  # Equipment accountability
    - device_damage_incidents: int
    - lost_equipment_incidents: int
```

---

## 💯 Balanced Performance Index (BPI)

### Formula: 0-100 Score
```python
BPI = (
    (Attendance & Reliability × 0.30) +
    (Task & Job Performance × 0.25) +
    (Tour & Patrol Quality × 0.20) +
    (Work Order & Service × 0.15) +
    (Compliance & Safety × 0.10)
)

# Normalization within cohort:
Cohort = (same site, same role, same shift_type, same tenure_band, same month)

BPI_normalized = (BPI_raw - cohort_mean) / cohort_std_dev
BPI_percentile = percentile_within_cohort(BPI_normalized)

# Display bands:
90-100: Exceptional
75-89:  Strong
60-74:  Solid
40-59:  Developing
<40:    Needs Support
```

---

## 📱 Dashboard Designs by Role

### WORKER: "My Performance Dashboard"

```
┌─────────────────────────────────────────────────────┐
│  MY PERFORMANCE SNAPSHOT                            │
│  Security Guard: John Smith                         │
│  Site: Downtown Plaza • Shift: Night (10PM-6AM)     │
└─────────────────────────────────────────────────────┘

┌──────────────── THIS WEEK ────────────────┐
│ 🎯 Balanced Performance Index: 78/100     │
│ ▓▓▓▓▓▓▓▓░░  Strong (Top 30% of night shift)│
│                                            │
│ 📊 Your Breakdown:                         │
│ ✓ Attendance:      92/100  ▓▓▓▓▓▓▓▓▓░     │
│ ✓ Task Performance: 85/100  ▓▓▓▓▓▓▓▓░░     │
│ ✓ Patrol Quality:   81/100  ▓▓▓▓▓▓▓▓░░     │
│ ⚠ Documentation:   65/100  ▓▓▓▓▓▓░░░░     │
│ ✓ Safety:          90/100  ▓▓▓▓▓▓▓▓▓░     │
└────────────────────────────────────────────┘

┌──────────────── STREAKS & ACHIEVEMENTS ───┐
│ 🔥 21 days on-time (Personal best!)       │
│ ⭐ 15 perfect patrols (95%+ checkpoints)  │
│ 🏆 Zero missed checkpoints this month     │
│ 👍 3 kudos from supervisors this week     │
└────────────────────────────────────────────┘

┌──────────────── FOCUS AREAS ──────────────┐
│ 📝 Documentation Improvement Needed:       │
│    • Upload photos at 3+ checkpoints/tour │
│    • Complete shift notes within 1 hour   │
│    • Current: 65% → Target: 80%           │
│                                            │
│ 💡 Quick Win This Week:                   │
│    Submit daily reports on time (currently│
│    2/5 days) to boost to 82/100 BPI       │
└────────────────────────────────────────────┘

┌──────────────── vs NIGHT SHIFT TEAM ──────┐
│ You vs Team Average:                       │
│ ✓ On-time rate:    96% (team: 89%) +7%   │
│ ✓ Checkpoint hit:  94% (team: 87%) +7%   │
│ ⚠ Documentation:  65% (team: 78%) -13%   │
│ ✓ Task SLA:        91% (team: 84%) +7%   │
└────────────────────────────────────────────┘

┌──────────────── RECENT HIGHLIGHTS ────────┐
│ Nov 3: Perfect patrol (100% checkpoints)  │
│ Nov 2: Detected broken lock (great catch!)│
│ Nov 1: Helped cover overtime (team player)│
│ Oct 31: Supervisor kudos for report detail│
└────────────────────────────────────────────┘
```

**Key Features**:
- ✅ Personal BPI with percentile band (not raw rank)
- ✅ Concrete improvement suggestions
- ✅ Positive reinforcement (streaks, achievements)
- ✅ Comparison to team average (not individuals)
- ✅ Recent wins highlighted

---

### SUPERVISOR: "Team Performance Dashboard"

```
┌─────────────────────────────────────────────────────┐
│  TEAM HEALTH - DOWNTOWN PLAZA NIGHT SHIFT           │
│  15 Active Guards • Nov 1-5, 2025                   │
└─────────────────────────────────────────────────────┘

┌──────────────── TEAM SCORECARD ───────────┐
│ Team BPI: 74/100 (Solid) ↑ +3 vs last week│
│                                            │
│ Performance Distribution:                  │
│ Exceptional (90+):   2 guards (13%)       │
│ Strong (75-89):      6 guards (40%)       │
│ Solid (60-74):       5 guards (33%)       │
│ Developing (40-59):  2 guards (13%) ⚠     │
│ Needs Support (<40): 0 guards             │
└────────────────────────────────────────────┘

┌──────────────── METRICS HEATMAP ──────────┐
│                   vs Site Avg  Trend       │
│ On-Time Rate:     89%  (+2%)   ↗ Improving│
│ Task SLA Hit:     84%  (-1%)   → Stable   │
│ Patrol Coverage:  87%  (+5%)   ↗ Improving│
│ Documentation:    78%  (same)  → Stable   │
│ Incident Rate:    2.1/100h (-15%) ↗ Better│
└────────────────────────────────────────────┘

┌──────────────── COACHING QUEUE ───────────┐
│ 🔔 2 guards need attention:                │
│                                            │
│ 1. Mike Johnson (BPI: 58, ↓ -8 this week) │
│    Issues: 3 late starts, 2 missed patrols│
│    Last 1:1: Oct 15 (3 weeks ago)         │
│    → Schedule coaching session            │
│                                            │
│ 2. Sarah Chen (BPI: 55, documentation low) │
│    Issues: 4/7 reports incomplete         │
│    Strength: 100% on-time, great patrols  │
│    → Quick documentation training         │
└────────────────────────────────────────────┘

┌──────────────── TOP PERFORMERS ───────────┐
│ 🏆 This Week's MVPs:                       │
│ 1. James Wilson     BPI: 94  (5th week 90+)│
│ 2. Lisa Rodriguez   BPI: 91  (Perfect patrol)│
│ 3. David Park       BPI: 88  (Zero late days)│
│                                            │
│ 💡 Recommend for:                          │
│ • Lead guard opportunities                │
│ • Training mentor roles                   │
│ • Premium client sites                    │
└────────────────────────────────────────────┘

┌──────────────── SHIFT COMPARISON ─────────┐
│ Night Shift (yours): BPI 74               │
│ Day Shift:           BPI 81  (+7) ↑       │
│ Evening Shift:       BPI 72  (-2) ↓       │
│                                            │
│ Gap Analysis:                              │
│ • Night shift documentation 13% below day │
│ • Task completion rate on par             │
│ • Better incident detection (+18%)        │
└────────────────────────────────────────────┘

┌──────────────── STAFFING INTELLIGENCE ────┐
│ Optimal Assignments (AI-recommended):      │
│                                            │
│ High-Risk Night Posts → James W., Lisa R. │
│   (Top BPI + incident detection track)    │
│                                            │
│ Client VIP Events → David P., Amy L.      │
│   (CSAT 4.8+, zero complaints)            │
│                                            │
│ Training/Mentoring → James W. (94 BPI)    │
│   (Available 2hr/week for new guard onboarding)│
└────────────────────────────────────────────┘
```

**Key Features**:
- ✅ Team overview with distribution (not individual ranking)
- ✅ Coaching queue with specific action items
- ✅ Top performers for recognition/promotion
- ✅ Shift comparison for staffing decisions
- ✅ AI-recommended optimal assignments

---

### OPERATIONS MANAGER: "Multi-Site Analytics"

```
┌─────────────────────────────────────────────────────┐
│  OPERATIONS DASHBOARD - ALL SITES                   │
│  12 Sites • 247 Active Workers • October 2025       │
└─────────────────────────────────────────────────────┘

┌──────────────── SITE COMPARISON ──────────┐
│ Site          Workers  BPI   SLA%  NCNS  Coverage│
│ Downtown Plaza   15    74↑   84%   0     ████░│
│ Tech Campus      23    81↑   91%   1     █████│
│ Warehouse Park   18    69↓   76%   3     ███░░│
│ Airport Terminal 42    77→   88%   2     ████░│
│ Medical Center   31    85↑   94%   0     █████│
│ ...                                             │
│                                                 │
│ ⚠ 2 sites below target (BPI < 70):             │
│   → Warehouse Park: High turnover, low coverage│
│   → Retail Complex: Documentation issues      │
└─────────────────────────────────────────────────┘

┌──────────────── PERFORMANCE BANDS ────────┐
│ Company-Wide Distribution:                 │
│                                            │
│ Exceptional (90+):  31 workers (13%)      │
│   └─ Promotion pool: 12 eligible          │
│                                            │
│ Strong (75-89):     98 workers (40%)      │
│   └─ Solid performers, standard roles     │
│                                            │
│ Solid (60-74):      89 workers (36%)      │
│   └─ Meeting expectations                 │
│                                            │
│ Developing (40-59): 24 workers (10%) ⚠    │
│   └─ Active coaching: 18 in progress      │
│   └─ PIP: 6 workers                       │
│                                            │
│ Needs Support (<40): 5 workers (2%) 🔴    │
│   └─ Immediate intervention required      │
└────────────────────────────────────────────┘

┌──────────────── ACTIONABLE INSIGHTS ──────┐
│ 🎯 Optimization Opportunities:             │
│                                            │
│ 1. Promote 12 exceptional performers      │
│    → Unlock 31 lead guard positions       │
│    → Avg BPI: 93 (qualified)              │
│                                            │
│ 2. Redeploy mid-performers to better fit  │
│    → 15 guards scoring higher at patrol   │
│      than admin tasks                     │
│    → Reassign to patrol-heavy sites       │
│                                            │
│ 3. Intensive support for 5 struggling     │
│    → All <6mo tenure, need mentoring      │
│    → Pair with top performers             │
└────────────────────────────────────────────┘

┌──────────────── FINANCIAL IMPACT ─────────┐
│ Performance-Linked Metrics:                │
│                                            │
│ Client Satisfaction: 4.3/5.0 (↑ 0.2)     │
│   └─ Correlated with BPI > 80 sites       │
│                                            │
│ SLA Penalty Savings: $12,400 this month   │
│   └─ 94% SLA hit vs 88% baseline          │
│                                            │
│ Overtime Cost Reduction: -18%             │
│   └─ Better on-time starts = less makeup  │
│                                            │
│ Retention Impact: 12% better (BPI > 75)   │
│   └─ High performers stay 22% longer      │
└────────────────────────────────────────────┘
```

**Key Features**:
- ✅ Multi-site comparison
- ✅ Distribution view (no individual lists)
- ✅ Actionable optimization opportunities
- ✅ Financial impact tied to performance
- ✅ Staffing intelligence

---

### CLIENT/EXECUTIVE: "Service Quality Report"

```
┌─────────────────────────────────────────────────────┐
│  QUARTERLY PERFORMANCE REPORT - Q4 2025             │
│  Client: Acme Properties • 8 Sites • 156 Guards     │
└─────────────────────────────────────────────────────┘

┌──────────────── EXECUTIVE SUMMARY ────────┐
│ Overall Service Quality: 82/100 (Strong)   │
│ Trend: ↑ +5 points vs Q3                  │
│                                            │
│ Key Achievements:                          │
│ ✓ 94.2% SLA compliance (target: 90%)      │
│ ✓ Zero critical incidents                 │
│ ✓ 4.4/5.0 avg customer satisfaction       │
│ ✓ 97.8% coverage (target: 95%)            │
└────────────────────────────────────────────┘

┌──────────────── WORKFORCE QUALITY ────────┐
│ Guard Performance Distribution:            │
│                                            │
│ █████████████░░░░░░  66% Strong or Better │
│                                            │
│ Exceptional:  13%  (20 guards)            │
│ Strong:       53%  (83 guards)            │
│ Solid:        28%  (44 guards)            │
│ Developing:    6%  ( 9 guards)            │
│                                            │
│ Retention Rate: 88% (industry avg: 76%)   │
│ Avg Tenure: 2.3 years (excellent)         │
└────────────────────────────────────────────┘

┌──────────────── VALUE DELIVERED ──────────┐
│ Tours Completed: 2,847 (99.2% of scheduled)│
│ Incidents Detected: 47 (prevented issues)  │
│ Tasks Completed: 1,234 (92% within SLA)   │
│ Emergency Response: 4.2 min avg (excellent)│
│                                            │
│ Cost Efficiency:                           │
│ • Overtime: -12% vs budget                │
│ • Turnover cost avoided: $47,000          │
│ • SLA penalties: $0 (100% compliant)      │
└────────────────────────────────────────────┘

┌──────────────── CONTINUOUS IMPROVEMENT ───┐
│ Training Investments Paying Off:           │
│ • Documentation quality: +18% since Aug   │
│ • First-time task completion: +12%        │
│ • Customer satisfaction: +0.3 points      │
│                                            │
│ Focus for Next Quarter:                   │
│ 1. Reduce checkpoint missed rate by 15%  │
│ 2. Increase evidence photo rate to 90%   │
│ 3. Cross-train 20 guards on new systems  │
└────────────────────────────────────────────┘
```

**Key Features**:
- ✅ Executive-level KPIs
- ✅ Workforce quality distribution (no names)
- ✅ Value delivered and ROI
- ✅ Continuous improvement tracking

---

## 🗄️ Data Model Design

### Core Tables (New)

```python
# apps/performance_analytics/models.py

class WorkerDailyMetrics(TenantAwareModel, BaseModel):
    """
    Daily performance snapshot per worker.
    Aggregated nightly from attendance, tasks, tours, work orders.
    """
    # Dimensions
    date = models.DateField(db_index=True)
    worker = models.ForeignKey('peoples.People', on_delete=models.CASCADE)
    site = models.ForeignKey('onboarding.Bt', on_delete=models.CASCADE)
    role = models.CharField(max_length=50)  # security_guard, supervisor, etc.
    shift_type = models.CharField(max_length=20)  # day, night, evening
    
    # Exposure (denominator for rates)
    scheduled_hours = models.DecimalField(max_digits=5, decimal_places=2)
    worked_hours = models.DecimalField(max_digits=5, decimal_places=2)
    scheduled_shifts = models.IntegerField()
    
    # Attendance Metrics
    on_time_punches = models.IntegerField()
    late_punches = models.IntegerField()
    total_late_minutes = models.IntegerField()
    geofence_violations = models.IntegerField()
    
    # Task Metrics
    tasks_assigned = models.IntegerField()
    tasks_completed = models.IntegerField()
    tasks_within_sla = models.IntegerField()
    task_quality_avg = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Patrol Metrics
    tours_completed = models.IntegerField()
    checkpoints_scanned = models.IntegerField()
    checkpoints_missed = models.IntegerField()
    patrol_coverage_rate = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Quality & Compliance
    incidents_reported = models.IntegerField()
    near_misses_reported = models.IntegerField()
    daily_reports_submitted = models.IntegerField()
    evidence_photos_uploaded = models.IntegerField()
    
    # Computed Scores
    attendance_score = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100
    task_score = models.DecimalField(max_digits=5, decimal_places=2)
    patrol_score = models.DecimalField(max_digits=5, decimal_places=2)
    compliance_score = models.DecimalField(max_digits=5, decimal_places=2)
    balanced_performance_index = models.DecimalField(max_digits=5, decimal_places=2)  # BPI
    
    # Cohort Comparison
    cohort_key = models.CharField(max_length=100)  # site|role|shift|tenure_band|month
    bpi_percentile = models.IntegerField()  # 0-100 within cohort
    
    class Meta:
        db_table = 'perf_worker_daily_metrics'
        unique_together = [['tenant', 'date', 'worker']]
        indexes = [
            models.Index(fields=['tenant', 'date', 'worker']),
            models.Index(fields=['tenant', 'date', 'site']),
            models.Index(fields=['tenant', 'cohort_key', 'date']),
        ]


class TeamDailyMetrics(TenantAwareModel, BaseModel):
    """
    Team/site-level aggregated metrics.
    Rolled up from WorkerDailyMetrics.
    """
    date = models.DateField(db_index=True)
    site = models.ForeignKey('onboarding.Bt', on_delete=models.CASCADE)
    shift_type = models.CharField(max_length=20, null=True, blank=True)
    
    # Aggregates
    active_workers = models.IntegerField()
    total_worked_hours = models.DecimalField(max_digits=8, decimal_places=2)
    team_bpi_avg = models.DecimalField(max_digits=5, decimal_places=2)
    team_bpi_median = models.DecimalField(max_digits=5, decimal_places=2)
    
    # Distribution
    workers_exceptional = models.IntegerField()  # BPI 90+
    workers_strong = models.IntegerField()  # BPI 75-89
    workers_solid = models.IntegerField()  # BPI 60-74
    workers_developing = models.IntegerField()  # BPI 40-59
    workers_needs_support = models.IntegerField()  # BPI <40
    
    # Key Metrics
    on_time_rate_avg = models.DecimalField(max_digits=5, decimal_places=2)
    sla_hit_rate_avg = models.DecimalField(max_digits=5, decimal_places=2)
    patrol_coverage_avg = models.DecimalField(max_digits=5, decimal_places=2)
    incident_rate_per_100h = models.DecimalField(max_digits=6, decimal_places=3)
    
    # Operational KPIs
    coverage_gap_hours = models.DecimalField(max_digits=6, decimal_places=2)
    ncns_incidents = models.IntegerField()
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2)
    
    class Meta:
        db_table = 'perf_team_daily_metrics'
        unique_together = [['tenant', 'date', 'site', 'shift_type']]


class CohortBenchmark(TenantAwareModel, BaseModel):
    """
    Statistical benchmarks per cohort for comparison.
    Updated weekly from WorkerDailyMetrics.
    """
    cohort_key = models.CharField(max_length=100)  # site|role|shift|tenure|month
    metric_name = models.CharField(max_length=50)
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Statistics
    sample_size = models.IntegerField()
    mean = models.DecimalField(max_digits=8, decimal_places=3)
    median = models.DecimalField(max_digits=8, decimal_places=3)
    std_dev = models.DecimalField(max_digits=8, decimal_places=3)
    p25 = models.DecimalField(max_digits=8, decimal_places=3)
    p75 = models.DecimalField(max_digits=8, decimal_places=3)
    p90 = models.DecimalField(max_digits=8, decimal_places=3)
    
    # Control limits
    lower_control_limit = models.DecimalField(max_digits=8, decimal_places=3)
    upper_control_limit = models.DecimalField(max_digits=8, decimal_places=3)
    
    class Meta:
        db_table = 'perf_cohort_benchmarks'
        unique_together = [['tenant', 'cohort_key', 'metric_name', 'period_start']]


class PerformanceStreak(TenantAwareModel, BaseModel):
    """
    Track positive streaks for gamification.
    """
    worker = models.ForeignKey('peoples.People', on_delete=models.CASCADE)
    streak_type = models.CharField(max_length=50)  # on_time, perfect_patrol, sla_hit
    current_count = models.IntegerField(default=0)
    best_count = models.IntegerField(default=0)
    started_date = models.DateField()
    last_updated = models.DateField()
    
    class Meta:
        db_table = 'perf_streaks'
        unique_together = [['tenant', 'worker', 'streak_type']]


class Kudos(TenantAwareModel, BaseModel):
    """
    Peer/supervisor recognition.
    """
    recipient = models.ForeignKey('peoples.People', on_delete=models.CASCADE, related_name='kudos_received')
    giver = models.ForeignKey('peoples.People', on_delete=models.CASCADE, related_name='kudos_given')
    kudos_type = models.CharField(max_length=50)  # teamwork, quality, initiative, safety
    message = models.TextField()
    related_task = models.ForeignKey('activity.Job', null=True, blank=True, on_delete=models.SET_NULL)
    related_tour = models.ForeignKey('scheduler.Tour', null=True, blank=True, on_delete=models.SET_NULL)
    visibility = models.CharField(max_length=20, default='team')  # team, site, company
    
    class Meta:
        db_table = 'perf_kudos'


class CoachingSession(TenantAwareModel, BaseModel):
    """
    Track 1:1 coaching sessions and action items.
    """
    worker = models.ForeignKey('peoples.People', on_delete=models.CASCADE, related_name='coaching_received')
    coach = models.ForeignKey('peoples.People', on_delete=models.CASCADE, related_name='coaching_given')
    session_date = models.DateTimeField()
    focus_areas = models.JSONField()  # ['documentation', 'task_sla']
    action_items = models.JSONField()  # [{'item': '...', 'due_date': '...', 'completed': False}]
    notes = models.TextField()
    follow_up_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'perf_coaching_sessions'
```

---

## 🔄 ETL Pipeline Design

### Nightly Aggregation Job

```python
# Create: background_tasks/performance_analytics_tasks.py

@shared_task(name='apps.performance.aggregate_daily_metrics')
def aggregate_daily_metrics_task(target_date=None):
    """
    Aggregate worker performance metrics for previous day.
    Runs at 2 AM daily.
    
    Steps:
    1. Aggregate attendance data
    2. Aggregate task/job completions
    3. Aggregate tour/patrol data
    4. Aggregate work orders/helpdesk
    5. Compute individual scores
    6. Compute cohort benchmarks
    7. Identify coaching opportunities
    8. Update streaks
    """
    from apps.performance_analytics.services.metrics_aggregator import MetricsAggregator
    
    if target_date is None:
        target_date = (timezone.now() - timedelta(days=1)).date()
    
    # Step 1: Aggregate attendance
    attendance_metrics = MetricsAggregator.aggregate_attendance_metrics(target_date)
    
    # Step 2: Aggregate tasks
    task_metrics = MetricsAggregator.aggregate_task_metrics(target_date)
    
    # Step 3: Aggregate patrols
    patrol_metrics = MetricsAggregator.aggregate_patrol_metrics(target_date)
    
    # Step 4: Aggregate work orders
    wo_metrics = MetricsAggregator.aggregate_work_order_metrics(target_date)
    
    # Step 5: Compute BPI scores
    bpi_results = MetricsAggregator.compute_bpi_scores(target_date)
    
    # Step 6: Update cohort benchmarks
    MetricsAggregator.update_cohort_benchmarks(target_date)
    
    # Step 7: Identify coaching opportunities
    MetricsAggregator.identify_coaching_opportunities(target_date)
    
    # Step 8: Update streaks
    MetricsAggregator.update_performance_streaks(target_date)
    
    return {
        'date': target_date.isoformat(),
        'workers_processed': bpi_results['count'],
        'cohorts_updated': bpi_results['cohort_count']
    }


# Add to Celery beat schedule:
# Run daily at 2:00 AM
'aggregate-daily-performance-metrics': {
    'task': 'apps.performance.aggregate_daily_metrics',
    'schedule': crontab(hour=2, minute=0),
},
```

---

## 📈 Specific Metric Calculations

### Example: On-Time Rate (Normalized)

```python
# apps/performance_analytics/services/metrics_calculator.py

class AttendanceMetricsCalculator:
    """Calculate attendance-related metrics."""
    
    @classmethod
    def calculate_on_time_rate(cls, worker, date):
        """
        Calculate on-time punch rate for a worker on a specific date.
        
        On-time = punch within ±5 minutes of scheduled time
        """
        from apps/attendance.models import Attendance
        from apps/scheduler.models import Schedule
        
        # Get scheduled shifts for date
        schedules = Schedule.objects.filter(
            assigned_people=worker,
            date=date,
            tenant=worker.tenant
        )
        
        total_punches = 0
        on_time_punches = 0
        total_late_minutes = 0
        
        for schedule in schedules:
            # Get attendance record
            try:
                attendance = Attendance.objects.get(
                    people=worker,
                    date=date,
                    shift=schedule
                )
                
                total_punches += 1
                
                # Check if punch-in within ±5 minutes
                scheduled_start = schedule.start_time
                actual_start = attendance.checkin_time
                
                diff_minutes = (actual_start - scheduled_start).total_seconds() / 60
                
                if abs(diff_minutes) <= 5:
                    on_time_punches += 1
                elif diff_minutes > 5:
                    total_late_minutes += diff_minutes
                    
            except Attendance.DoesNotExist:
                # No-show counts as not on-time
                total_punches += 1
        
        on_time_rate = (on_time_punches / total_punches * 100) if total_punches > 0 else 0
        avg_late_minutes = total_late_minutes / total_punches if total_punches > 0 else 0
        
        return {
            'on_time_rate': round(on_time_rate, 2),
            'on_time_punches': on_time_punches,
            'total_punches': total_punches,
            'avg_late_minutes': round(avg_late_minutes, 2)
        }
```

### Example: Task Performance Score

```python
class TaskMetricsCalculator:
    """Calculate task performance metrics."""
    
    @classmethod
    def calculate_task_score(cls, worker, date):
        """
        Calculate task performance score (0-100).
        
        Components:
        - Completion rate: 40%
        - SLA hit rate: 40%
        - Quality/first-time-pass: 20%
        """
        from apps.activity.models import Job
        
        # Get tasks for date
        tasks = Job.objects.filter(
            assigned_people=worker,
            date=date
        )
        
        total_tasks = tasks.count()
        
        if total_tasks == 0:
            return {'task_score': 0, 'tasks_assigned': 0}
        
        # Completion rate
        completed_tasks = tasks.filter(status='COMPLETED').count()
        completion_rate = completed_tasks / total_tasks
        
        # SLA hit rate
        tasks_with_sla = tasks.exclude(sla_deadline__isnull=True)
        within_sla = tasks_with_sla.filter(
            completed_at__lte=F('sla_deadline')
        ).count()
        sla_hit_rate = within_sla / tasks_with_sla.count() if tasks_with_sla.count() > 0 else 1.0
        
        # First-time pass (no rework)
        tasks_no_rework = tasks.filter(rework_count=0).count()
        first_time_pass_rate = tasks_no_rework / total_tasks
        
        # Weighted score
        task_score = (
            (completion_rate * 0.40) +
            (sla_hit_rate * 0.40) +
            (first_time_pass_rate * 0.20)
        ) * 100
        
        return {
            'task_score': round(task_score, 2),
            'tasks_assigned': total_tasks,
            'tasks_completed': completed_tasks,
            'sla_hit_rate': round(sla_hit_rate * 100, 2),
            'first_time_pass_rate': round(first_time_pass_rate * 100, 2)
        }
```

### Example: BPI Calculation

```python
class BalancedPerformanceIndexCalculator:
    """Calculate overall BPI score."""
    
    @classmethod
    def calculate_bpi(cls, worker, date):
        """
        Calculate Balanced Performance Index (0-100).
        
        Weights:
        - Attendance: 30%
        - Tasks: 25%
        - Patrols: 20%
        - Work Orders: 15%
        - Compliance: 10%
        """
        # Get component scores
        attendance_score = AttendanceMetricsCalculator.calculate_attendance_score(worker, date)
        task_score = TaskMetricsCalculator.calculate_task_score(worker, date)
        patrol_score = PatrolMetricsCalculator.calculate_patrol_score(worker, date)
        wo_score = WorkOrderMetricsCalculator.calculate_wo_score(worker, date)
        compliance_score = ComplianceMetricsCalculator.calculate_compliance_score(worker, date)
        
        # Weighted BPI
        bpi = (
            (attendance_score['score'] * 0.30) +
            (task_score['task_score'] * 0.25) +
            (patrol_score['score'] * 0.20) +
            (wo_score['score'] * 0.15) +
            (compliance_score['score'] * 0.10)
        )
        
        # Normalize within cohort
        cohort_key = cls._build_cohort_key(worker, date)
        percentile = cls._calculate_percentile(worker, bpi, cohort_key, date)
        
        return {
            'bpi': round(bpi, 2),
            'percentile': percentile,
            'cohort_key': cohort_key,
            'components': {
                'attendance': attendance_score['score'],
                'tasks': task_score['task_score'],
                'patrols': patrol_score['score'],
                'work_orders': wo_score['score'],
                'compliance': compliance_score['score']
            }
        }
    
    @classmethod
    def _build_cohort_key(cls, worker, date):
        """
        Build cohort key for fair comparison.
        Format: site_id|role|shift_type|tenure_band|month
        """
        # Get worker's typical shift type
        shift_type = cls._get_primary_shift_type(worker, date)
        
        # Get tenure band (0-3mo, 3-6mo, 6-12mo, 1-2yr, 2yr+)
        tenure_days = (date - worker.date_joined.date()).days
        if tenure_days < 90:
            tenure_band = '0-3mo'
        elif tenure_days < 180:
            tenure_band = '3-6mo'
        elif tenure_days < 365:
            tenure_band = '6-12mo'
        elif tenure_days < 730:
            tenure_band = '1-2yr'
        else:
            tenure_band = '2yr+'
        
        site_id = worker.bu_id  # Primary site
        role = worker.role or 'security_guard'
        month = date.strftime('%Y-%m')
        
        return f"{site_id}|{role}|{shift_type}|{tenure_band}|{month}"
```

---

## 🎮 Gamification Elements

### Achievements & Badges

```python
# apps/performance_analytics/models/achievements.py

class Achievement(TenantAwareModel, BaseModel):
    """
    Achievement definitions.
    """
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50)  # emoji or icon class
    criteria = models.JSONField()  # Unlock criteria
    points = models.IntegerField(default=10)
    rarity = models.CharField(max_length=20)  # common, rare, epic, legendary
    
    # Examples:
    # {
    #   "code": "perfect_month",
    #   "name": "Perfect Month",
    #   "criteria": {"on_time_rate": 100, "days": 30},
    #   "icon": "🏆",
    #   "rarity": "epic"
    # }


class WorkerAchievement(TenantAwareModel, BaseModel):
    """
    Achievements earned by workers.
    """
    worker = models.ForeignKey('peoples.People', on_delete=models.CASCADE)
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_date = models.DateField()
    count = models.IntegerField(default=1)  # Times earned
    
    class Meta:
        unique_together = [['tenant', 'worker', 'achievement']]


# Achievement Types:
ACHIEVEMENTS = [
    {"code": "on_time_week", "name": "Perfect Week", "criteria": {"on_time_rate": 100, "days": 7}},
    {"code": "on_time_month", "name": "Perfect Month", "criteria": {"on_time_rate": 100, "days": 30}},
    {"code": "on_time_quarter", "name": "Perfect Quarter", "criteria": {"on_time_rate": 100, "days": 90}, "rarity": "epic"},
    {"code": "patrol_pro", "name": "Patrol Pro", "criteria": {"checkpoint_rate": 100, "tours": 50}},
    {"code": "sla_champion", "name": "SLA Champion", "criteria": {"sla_hit_rate": 95, "tasks": 100}},
    {"code": "zero_ncns_year", "name": "Year Without NCNS", "criteria": {"ncns_count": 0, "days": 365}, "rarity": "legendary"},
    {"code": "quality_excellence", "name": "Quality Excellence", "criteria": {"quality_score": 90, "audits": 20}},
    {"code": "team_player", "name": "Team Player", "criteria": {"kudos_received": 10, "days": 30}},
    {"code": "safety_champion", "name": "Safety Champion", "criteria": {"near_miss_reports": 5, "days": 30}},
]
```

### Leaderboards (Team-Level Only)

```python
# Show team/site rankings, not individuals
TeamLeaderboards:
    - Top Sites by BPI (this month)
    - Best Shift Teams (day/night/evening)
    - Most Improved Sites (vs last quarter)
    - Highest SLA Compliance Teams
    - Best Coverage Teams
    - Safety Leader Sites (lowest incident rate)
```

---

## 📊 Sample Reports & Insights

### Report 1: "Worker Performance Profile"

```
WORKER PERFORMANCE PROFILE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: James Wilson
Role: Senior Security Guard
Site: Downtown Plaza
Tenure: 2.5 years
Review Period: October 2025

BALANCED PERFORMANCE INDEX: 94/100 (Exceptional)
Ranking: Top 5% of security guards (night shift cohort)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERFORMANCE BREAKDOWN

✓ ATTENDANCE & RELIABILITY: 96/100
  • On-time rate: 100% (31/31 shifts)
  • Zero late punches this month
  • Zero NCNS (career: 0 incidents)
  • Geofence compliance: 100%
  • Overtime acceptance: 80% (available when needed)

✓ TASK PERFORMANCE: 92/100
  • Tasks completed: 48/50 (96%)
  • SLA hit rate: 94% (45/48)
  • First-time pass: 90% (43/48)
  • Avg completion time: 15% faster than peers
  • Quality rating: 4.8/5.0

✓ PATROL QUALITY: 95/100
  • Tours completed: 62/62 (100%)
  • Checkpoint coverage: 97% (602/620)
  • On-time checkpoints: 95%
  • Incidents detected: 3 (prevented break-ins)
  • Patrol thoroughness: Excellent

✓ DOCUMENTATION: 88/100
  • Daily reports: 100% on-time
  • Evidence photos: 92% of checkpoints
  • Shift handover: Complete and detailed
  • Observation quality: Above average

✓ SAFETY & COMPLIANCE: 98/100
  • Certifications: All current (4/4)
  • PPE compliance: 100%
  • Near-miss reports: 2 (proactive)
  • Safety incidents: 0
  • Device accountability: 100%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRENGTHS & RECOGNITION

🏆 ACHIEVEMENTS EARNED THIS MONTH:
  ✓ Perfect Month (100% on-time)
  ✓ Patrol Pro (97% checkpoint coverage)
  ✓ SLA Champion (94% hit rate)
  ✓ Safety Champion (proactive reporting)

👍 KUDOS RECEIVED (4):
  • "Excellent incident detection" - Supervisor Mike
  • "Always reliable for overtime" - Ops Manager
  • "Helped train new guard" - Peer David
  • "Thorough patrol notes" - Supervisor Mike

🎯 TOP 5% PERFORMANCE INDICATORS:
  • Consistency (zero late days)
  • Patrol quality (incidents detected)
  • Reliability (overtime acceptance)
  • Documentation quality

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEVELOPMENT OPPORTUNITIES

📝 FOCUS AREA: Documentation Enhancement
  Current: 88/100 (Good)
  Target: 95/100 (Exceptional)
  
  Actions:
  1. Upload photos at ALL checkpoints (not just high-risk)
  2. Add incident context in observation notes
  3. Complete equipment check forms daily
  
  Impact: Would increase overall BPI from 94 to 96

💡 CAREER PROGRESSION:
  ✓ Qualified for Lead Guard role (BPI > 90)
  ✓ Eligible for VIP client sites (94 BPI, 2.5yr tenure)
  ✓ Recommended for training mentor program
  
  Next Opportunity: Lead Guard opening at Tech Campus
  Expected: Q1 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERFORMANCE TREND (Last 6 Months)

 BPI
100 │                              ●
 95 │                         ●    │
 90 │                    ●    │    │
 85 │               ●    │    │    │
 80 │          ●    │    │    │    │
 75 │     ●    │    │    │    │    │
    └────────────────────────────────
    May  Jun  Jul  Aug  Sep  Oct

Trend: ↗ Consistently improving (+18 points since May)
Consistency: Excellent (std dev: 3.2)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PEER COMPARISON (Night Shift, Downtown Plaza)

           You    Team Avg   Best in Team
BPI        94     74         96
On-time    100%   89%        100%
Task SLA   94%    84%        97%
Patrol     97%    87%        98%
Quality    4.8    4.2        4.9

Position: 2nd of 15 guards (Top 13%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Report 2: "Team Performance Comparison"

```
TEAM PERFORMANCE COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Site: Downtown Plaza
All Shifts: Day, Evening, Night
Period: October 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHIFT COMPARISON

Shift         Guards  BPI   On-Time  SLA%  Coverage  NCNS
─────────────────────────────────────────────────────────
Day (6A-2P)     12    81    94%      91%   95%       0
Evening (2P-10P) 10    72    87%      82%   88%       2
Night (10P-6A)   15    74    89%      84%   87%       1
Weekend Days     8    78    91%      88%   92%       0

Analysis:
✓ Day shift strongest overall (81 BPI, 94% on-time)
⚠ Evening shift needs attention (72 BPI, 2 NCNS)
→ Recommend: Evening shift coaching, scheduling review

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOP PERFORMERS (All Shifts)

Rank  Name             BPI   Shift   Strengths
────────────────────────────────────────────────
1.    Sarah Martinez   96    Day     Perfect attendance, 98% SLA
2.    James Wilson     94    Night   Zero late, incident detection
3.    Lisa Rodriguez   91    Day     Quality leader, training mentor
4.    David Park       88    Evening Reliable, great customer service
5.    Amy Chen         87    Night   Thorough patrols, documentation

Recognition Program:
→ Guard of the Month: Sarah Martinez
→ Lead Guard candidates: Sarah, James, Lisa
→ Training mentors: James, Lisa

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEEDS IMPROVEMENT (Confidential - Supervisor Only)

Name           BPI   Issue Areas              Action Plan
─────────────────────────────────────────────────────────
Mike Johnson    58   Late starts (3), missed   1:1 scheduled
                     patrols (2)               Nov 8
                     
Sarah Chen      55   Documentation (4/7 low)   Training session
                     Quality needs work        Nov 10

Tom Anderson    48   NCNS (1), poor quality    PIP initiated
                     Tasks incomplete          Oct 28

Actions This Week:
✓ Schedule 3 coaching sessions
✓ Documentation training for 5 guards
✓ Monitor Tom Anderson daily (PIP week 2)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PERFORMANCE DISTRIBUTION

BPI Range       Count   %      Graph
────────────────────────────────────────
90-100          5      11%    ███
75-89          18      40%    ████████████
60-74          15      33%    ██████████
40-59           7      16%    █████
<40             0       0%    

Target Distribution:
✓ 51% Strong or Better (target: 50%) ✓
⚠ 16% Developing (target: <10%)
→ Focus coaching on 7 developing guards

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPERATIONAL INTELLIGENCE

Staffing Optimization:
• 5 guards scoring 90+ → Deploy to VIP sites/shifts
• 18 guards (75-89) → Standard rotation, reliable
• 7 guards (40-59) → Pair with mentors, lighter duties
• Shift rebalancing: Move 2 strong day guards to evening

Skill Gaps Identified:
• Documentation: 15 guards below 75% completion
  → Group training session needed
• Emergency response: 3 guards slow on drills
  → Additional drill practice
• Customer service: Evening shift CSAT 3.8/5.0
  → Customer interaction workshop

Retention Risk:
• 3 high performers (BPI 85+) due for promotion
  → Create lead roles or risk losing to competitors
• 2 struggling guards (BPI <50) at 90-day mark
  → Intensive support or probable turnover

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Report 3: "Multi-Site Executive Dashboard"

```
EXECUTIVE OPERATIONS DASHBOARD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Portfolio: Acme Security Services
12 Sites • 247 Active Guards • Q4 2025

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WORKFORCE QUALITY INDEX

Company BPI: 77/100 (Strong)
Trend: ↑ +4 points vs Q3 2025

Performance Distribution:
  Exceptional (90+):   32 guards (13%) ████
  Strong (75-89):      99 guards (40%) ████████████
  Solid (60-74):       88 guards (36%) ███████████
  Developing (40-59):  23 guards (9%)  ███
  Needs Support (<40):  5 guards (2%)  █

Target Allocation:
✓ 53% in Strong+ (target: 50%) ✓
✓ Top performer pool growing (13% vs 9% in Q3)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SITE BENCHMARKING

Best Performing Sites:
1. Medical Center    BPI: 85  ■■■■■■■■■ (31 guards)
2. Tech Campus       BPI: 81  ■■■■■■■■  (23 guards)
3. Airport Terminal  BPI: 77  ■■■■■■■   (42 guards)

Underperforming Sites:
10. Warehouse Park   BPI: 69  ■■■■■     (18 guards)
11. Retail Complex   BPI: 67  ■■■■      (21 guards)
12. Industrial Site  BPI: 64  ■■■■      (14 guards)

Gap Analysis:
• Medical Center success factors: Strong supervisor (BPI 91),
  low turnover (6%), consistent training
• Warehouse Park challenges: High turnover (24%), supervisor
  changed 2x, inconsistent scheduling

Recommendations:
→ Assign experienced supervisor to Warehouse Park
→ Deploy 2 top performers to stabilize team
→ Intensive training program for Retail Complex

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY PERFORMANCE INDICATORS

                      Current  Target   Status  Trend
─────────────────────────────────────────────────────
SLA Compliance        91.2%    90%      ✓       ↗
On-Time Attendance    90.3%    85%      ✓       ↗
Patrol Coverage       88.7%    90%      ⚠       ↗
Task Completion       87.4%    85%      ✓       →
Customer Satisfaction  4.3/5    4.0/5    ✓       ↑
Incident Rate         1.8/100h  <2.5    ✓       ↓
NCNS Rate             1.2%     <2%      ✓       ↓
Turnover (Annual)     18%      <20%     ✓       ↓

Overall Status: 7/8 targets met or exceeded ✓

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINANCIAL IMPACT

Performance-Linked Outcomes:
• SLA penalties avoided: $43,200 (Q4)
• Reduced overtime costs: -14% ($31,800 saved)
• Lower turnover costs: $89,000 saved (vs Q3)
• Client retention: 100% (all contracts renewed)

ROI on Workforce Quality:
Investment in training/coaching: $12,000
Return (penalties + OT + turnover): $164,000
Net ROI: 1,267%

Premium Billing Justification:
• 53% workforce in Strong+ tier (industry: 35%)
• 91% SLA compliance (industry: 78%)
• 4.3/5 CSAT (industry: 3.7/5)
→ Supports 15-20% premium pricing

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STAFFING INTELLIGENCE

Promotion-Ready (32 guards, BPI 90+):
• Immediate: 12 guards (>1yr tenure, 93+ BPI)
• 6 months: 20 guards (6mo+ tenure, 90-92 BPI)

Deployment Optimization:
• VIP/High-Value Sites: Deploy BPI 85+ only
• Standard Sites: BPI 70-84 acceptable
• Training Sites: Pair BPI <60 with 90+ mentors

Retention Risk Management:
• 8 top performers due for promotion/raise
• 12 guards in month 5-6 (critical retention period)
• 5 struggling guards requiring PIP or exit

Recommended Headcount Adjustments:
• Promote 6 to lead guard → backfill with new hires
• Exit 3 persistently low performers → quality gain
• Net hiring need: +9 guards for growth

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🎯 Benchmarking Dimensions

### 1. Individual vs Individual (Same Cohort)
- Compare guards at same site, role, shift type, tenure
- Show percentile band (top 10%, top 25%, median, bottom 25%)
- Identify outliers (exceptional or needs support)

### 2. Individual vs Team Average
- Worker score vs their team/shift average
- Gaps highlighted (above/below average)
- Strengths to leverage, weaknesses to address

### 3. Team vs Team
- Shift comparison (day vs night vs evening)
- Site comparison (12 sites ranked)
- Role comparison (guards vs supervisors vs technicians)

### 4. Site vs Site
- Multi-site portfolio comparison
- Best practices identification
- Underperformance root cause analysis

### 5. Current vs Historical
- Month-over-month trends
- Quarter-over-quarter improvements
- Year-over-year benchmarks

### 6. Actual vs Target
- Goals set per metric
- Performance against targets
- Gap analysis and action plans

---

## 🔧 Implementation Plan

### Phase 1: Foundation (Week 1-2)

**Data Model**:
- Create `WorkerDailyMetrics`, `TeamDailyMetrics`, `CohortBenchmark` models
- Create `PerformanceStreak`, `Kudos`, `Achievement` models
- Add indexes for fast queries

**ETL Pipeline**:
- Create `MetricsAggregator` service
- Implement attendance metrics calculation
- Implement task metrics calculation
- Implement patrol metrics calculation
- Create nightly Celery task

**Effort**: 1-2 weeks, 1 backend developer

---

### Phase 2: Worker Dashboard (Week 3)

**API Endpoints**:
```python
# apps/performance_analytics/api/views.py

class WorkerPerformanceView(APIView):
    """GET /api/performance/me/"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # Return worker's performance data
        # Last 30 days, 90 days, 12 months
        # BPI, components, streaks, achievements
        # Cohort comparison
        pass


class WorkerTrendsView(APIView):
    """GET /api/performance/me/trends/"""
    # Return time-series data for charts
    pass


class WorkerAchievementsView(APIView):
    """GET /api/performance/me/achievements/"""
    # Return earned achievements and progress
    pass
```

**Mobile UI** (Kotlin/Swift):
- Performance snapshot card
- Metric breakdowns with gauges
- Streaks and achievements
- Focus areas with suggestions
- Trend charts

**Effort**: 1 week, 1 frontend + 1 mobile developer

---

### Phase 3: Supervisor Dashboard (Week 4)

**API Endpoints**:
```python
class TeamPerformanceView(APIView):
    """GET /api/performance/team/{site_id}/"""
    permission_classes = [IsSupervisor]
    
    def get(self, request, site_id):
        # Return team metrics
        # Distribution, heatmap, coaching queue
        # Top performers, needs improvement
        pass


class CoachingQueueView(APIView):
    """GET /api/performance/coaching-queue/"""
    # Guards needing attention with specific issues
    pass


class TeamComparisonView(APIView):
    """GET /api/performance/team/comparison/"""
    # Shift vs shift, site vs site
    pass
```

**Web UI**:
- Team health dashboard
- Performance heatmaps
- Coaching queue with action buttons
- Shift/team comparison
- Export to PDF

**Effort**: 1 week, 1 frontend developer

---

### Phase 4: Executive Analytics (Week 5)

**Reports**:
- Multi-site executive dashboard
- Quarterly performance report
- Workforce quality report
- Staffing intelligence report

**Features**:
- Site ranking and comparison
- Portfolio-wide KPIs
- Financial impact analysis
- Predictive staffing recommendations

**Effort**: 1 week, 1 backend + 1 frontend developer

---

## 💰 Revenue & Pricing Model

### Feature Packaging

**Base Plan** (Included):
- Basic attendance tracking
- Task assignment
- Tour management
- Standard reports

**Performance Analytics Add-On**: +$10/active worker/month

Includes:
- Worker performance dashboard (mobile app)
- Individual BPI scores and trends
- Achievements and streaks
- Personal improvement suggestions

**Team Analytics Add-On**: +$100/site/month

Includes:
- Supervisor team dashboard
- Coaching queue
- Team comparisons
- Top performer identification
- Staffing optimization

**Executive Analytics Add-On**: +$300/month per client

Includes:
- Multi-site comparison
- Quarterly executive reports
- Workforce quality analysis
- Financial impact reporting
- Predictive staffing intelligence

### Revenue Projection

**Scenario**: 100 clients, avg 2 sites, avg 20 workers/site

- **Worker Analytics**: 100 clients × 40 workers × $10 = **$40,000/month**
- **Team Analytics**: 100 clients × 2 sites × $100 = **$20,000/month**
- **Executive Analytics**: 50 clients × $300 = **$15,000/month**

**Total New MRR**: $75,000/month = **$900K ARR**

---

## 🎯 Competitive Advantages

### vs Competitors

| Feature | YOUTILITY5 | Competitor A | Competitor B |
|---------|-----------|--------------|--------------|
| **Individual BPI** | ✅ Balanced 5-dimension | ❌ Attendance only | ⚠️ Basic 2-dimension |
| **Cohort Normalization** | ✅ Fair comparison | ❌ Raw rankings | ❌ No normalization |
| **Gamification** | ✅ Achievements/streaks | ❌ None | ⚠️ Points only |
| **Coaching Queue** | ✅ AI-recommended | ❌ Manual review | ❌ Not available |
| **Mobile Dashboard** | ✅ Real-time | ⚠️ Web only | ❌ Reports only |
| **Predictive Staffing** | ✅ AI-optimized | ❌ None | ❌ None |
| **Multi-Site Analytics** | ✅ Portfolio view | ⚠️ Basic | ❌ Single-site |

### Unique Differentiators

1. **Balanced Performance Index** - Not just attendance, holistic view
2. **Fair Cohort Comparison** - Apples-to-apples benchmarking
3. **Positive Reinforcement** - Achievements, not just penalties
4. **Actionable Coaching Queue** - AI identifies who needs what
5. **Financial Impact Tracking** - Tie performance to ROI

---

## 🚀 Quick Start: Ship MVP in 2 Weeks

### MVP Scope (Minimum Viable Product)

**Week 1**: Data Pipeline
- Create 3 core models (WorkerDailyMetrics, TeamDailyMetrics, CohortBenchmark)
- Implement attendance + task metrics only (skip patrols initially)
- Create nightly aggregation Celery task
- Backfill last 30 days

**Week 2**: Dashboards
- Worker API endpoint + mobile view (BPI + trends)
- Supervisor web view (team health + top/bottom lists)
- Simple PDF report

**Launch**: Beta with 3 pilot sites

**Iterate**: Add patrol metrics, work orders, achievements in Phase 2

---

## 📋 Success Metrics

### Adoption Metrics
- Worker dashboard usage: >70% weekly active
- Supervisor dashboard usage: >90% weekly
- Executive report opens: >80%

### Operational Metrics
- BPI improvement: +5-10 points portfolio-wide in 6 months
- Coaching effectiveness: 60% of developing guards improve
- Retention improvement: +10% for high performers

### Business Metrics
- Client satisfaction with analytics: 4.5/5.0 target
- Premium tier adoption: 40% of clients
- New client wins citing analytics: 20%

---

## 🎬 Recommended Next Steps

1. **Approve design** and prioritize dimensions
2. **Pilot with 2-3 sites** (1 high-performing, 1 struggling, 1 average)
3. **Gather feedback** from workers, supervisors, clients
4. **Iterate weights** and cohort definitions
5. **Build mobile-first** (field workers need app access)
6. **Market as premium tier** with ROI calculator

**Bottom Line**: You have all the data - just need to aggregate, benchmark, and visualize it. This creates a powerful retention tool (workers see growth), operations tool (supervisors coach better), and sales tool (demonstrate quality to clients).

Which dimension would you like to implement first?
