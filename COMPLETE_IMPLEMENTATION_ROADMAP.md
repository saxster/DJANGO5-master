# Complete Implementation Roadmap
## Onboarding Security & Reliability Enhancements

**Project Status:** Phase 1 Complete (33%), Phases 2-3 In Progress
**Date:** 2025-10-01
**Author:** Claude Code

---

## ✅ COMPLETED (Phase 1 - 100%)

### Phase 1.1: Enhanced Rate Limiter ✅
- Circuit breaker pattern with 5-failure threshold
- In-memory fallback cache (50 req/hour)
- Critical resource fail-closed strategy
- Retry-After header calculation (RFC 7231 compliant)
- Correlation ID tracking and structured logging
- **File:** `apps/onboarding_api/services/security.py` (427 lines enhanced)

### Phase 1.2: File Upload Rate Limiting ✅
- Session quotas (50 photos, 20 documents, 100MB)
- Burst protection (10 photos/min)
- File type validation (MIME checking)
- Concurrent upload limits (max 3)
- EXIF validation, auto-compression, geolocation requirements
- **Files:**
  - `intelliwiz_config/settings/security/onboarding_upload.py` (146 lines)
  - `apps/onboarding_api/services/upload_throttling.py` (430 lines)
  - `apps/onboarding_api/views/site_audit_views.py` (modified)

---

## 🚧 IN PROGRESS (Phase 2 - 40%)

### Phase 2.1: Dead Letter Queue Integration

#### 2.1.1: Base Task Class ✅ COMPLETE
**File:** `background_tasks/onboarding_base_task.py` (385 lines)

**Features:**
- `OnboardingBaseTask` - Base class with auto-DLQ integration
- `get_correlation_id()` - Tracking helper
- `task_success()` / `task_failure()` - Standard response formats
- `handle_task_error()` - Comprehensive error handling with DLQ
- `with_transaction()` - Transaction wrapper
- `safe_execute()` - Error-safe function execution
- Specialized classes: `OnboardingDatabaseTask`, `OnboardingLLMTask`, `OnboardingNetworkTask`

**Usage Pattern:**
```python
@shared_task(bind=True, base=OnboardingLLMTask, **llm_api_task_config())
def my_task(self, arg1, arg2, correlation_id=None):
    correlation_id = self.get_correlation_id(correlation_id)
    try:
        result = do_work(arg1, arg2)
        return self.task_success(result, correlation_id)
    except Exception as e:
        return self.handle_task_error(e, correlation_id, {'arg1': arg1})
```

#### 2.1.2: DLQ Admin Dashboard (TODO - HIGH PRIORITY)
**New File:** `apps/onboarding_api/views/dlq_admin_views.py` (est. 450 lines)

**Required Endpoints:**
1. `GET /api/v1/admin/dlq/tasks/` - List failed tasks
2. `GET /api/v1/admin/dlq/tasks/{task_id}/` - Task details
3. `POST /api/v1/admin/dlq/tasks/{task_id}/retry/` - Manual retry
4. `DELETE /api/v1/admin/dlq/tasks/{task_id}/` - Remove from DLQ
5. `GET /api/v1/admin/dlq/stats/` - DLQ statistics
6. `DELETE /api/v1/admin/dlq/clear/` - Bulk clear (with filters)

**Implementation:**
```python
class DLQTaskListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        """List tasks in DLQ with filtering"""
        task_name_filter = request.query_params.get('task_name')
        limit = int(request.query_params.get('limit', 100))

        tasks = dlq_handler.list_dlq_tasks(
            limit=limit,
            task_name_filter=task_name_filter
        )

        return Response({
            'tasks': tasks,
            'total': len(tasks),
            'filters': {'task_name': task_name_filter}
        })

class DLQTaskRetryView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, task_id):
        """Retry a task from DLQ"""
        success = dlq_handler.retry_dlq_task(task_id)

        if success:
            return Response({'status': 'queued', 'task_id': task_id})
        return Response(
            {'error': 'Task not found or retry failed'},
            status=404
        )
```

#### 2.1.3: DLQ Alerting System (TODO - MEDIUM PRIORITY)
**New File:** `apps/onboarding_api/services/dlq_alerting.py` (est. 280 lines)

**Features:**
- Critical task failure alerts (Slack, email, SMS)
- DLQ size monitoring (alert at 80% capacity)
- Aging task detection (tasks > 24h old)
- Failure pattern analysis (repeated failures)

---

### Phase 2.2: Complete Funnel Analytics

#### 2.2.1: Fix Syntax Error ✅ (Quick Win)
**File:** `apps/onboarding_api/services/funnel_analytics.py`

**Issue:** Line 15 has orphaned closing parenthesis
**Fix:**
```python
# BEFORE (Line 15):
)  # ❌ Orphaned parenthesis

# AFTER:
from typing import List, Dict, Any, Optional  # ✅ Fixed imports
from apps.onboarding.models import ConversationSession
```

#### 2.2.2: Complete Calculation Methods (TODO - HIGH PRIORITY)
**File:** `apps/onboarding_api/services/funnel_analytics.py` (continue from line 100)

**Required Methods:**
```python
def _calculate_avg_stage_time(self, stage_sessions):
    """Calculate average time users spend in stage"""
    # Implementation: Analyze mdtz timestamps between states

def _calculate_drop_off_rate(self, stage_config, all_sessions):
    """Calculate % of users dropping off at this stage"""
    # Implementation: Compare current stage to next stage counts

def _calculate_overall_conversion(self, sessions):
    """Calculate % completing full onboarding"""
    # Filter sessions with state=COMPLETED

def _calculate_avg_completion_time(self, sessions):
    """Calculate average time from start to completion"""
    # Filter completed sessions, calc time delta

def _identify_top_drop_off_points(self, stages_data):
    """Find stages with highest drop-off rates"""
    # Sort by drop_off_rate, return top 3

def _perform_cohort_analysis(self, sessions):
    """Analyze by user segments (language, device, time)"""
    # Group by language, analyze conversion per cohort

def _generate_optimization_recommendations(self, stages_data):
    """AI-powered recommendations based on funnel data"""
    # Rules: If drop_off > 30% at stage, recommend simplification
```

#### 2.2.3: Funnel API Endpoints (TODO - HIGH PRIORITY)
**New File:** `apps/onboarding_api/views/funnel_analytics_views.py` (est. 320 lines)

**Endpoints:**
```python
GET /api/v1/onboarding/analytics/funnel/
    - Query params: start_date, end_date, client_id, cohort
    - Returns: Complete funnel metrics with stages

GET /api/v1/onboarding/analytics/drop-off-heatmap/
    - Returns: Heat map data for visualization

GET /api/v1/onboarding/analytics/cohort-comparison/
    - Compare conversion rates across cohorts

GET /api/v1/onboarding/analytics/recommendations/
    - AI-generated optimization suggestions
```

---

## 📋 PHASE 3: High-Impact Enhancements (TODO)

### Phase 3.1: Session Recovery System

#### Architecture Decision:
**Storage:** Redis for active checkpoints (TTL 1h), PostgreSQL for historical recovery

**New File:** `apps/onboarding_api/services/session_recovery.py` (est. 580 lines)

**Key Features:**
1. **Checkpoint Management**
```python
class SessionRecoveryService:
    def create_checkpoint(self, session_id, checkpoint_data):
        """Save session state every 30 seconds"""
        cache_key = f"session:checkpoint:{session_id}"
        checkpoint = {
            'session_id': session_id,
            'current_state': checkpoint_data['state'],
            'collected_data': checkpoint_data['data'],
            'question_history': checkpoint_data['history'],
            'created_at': timezone.now().isoformat(),
            'version': checkpoint_data.get('version', 1)
        }
        cache.set(cache_key, checkpoint, timeout=3600)

    def get_latest_checkpoint(self, session_id):
        """Retrieve most recent checkpoint for resume"""
        cache_key = f"session:checkpoint:{session_id}"
        return cache.get(cache_key)

    def resume_session(self, session_id, user):
        """Smart session resume with context restoration"""
        checkpoint = self.get_latest_checkpoint(session_id)
        if not checkpoint:
            raise CheckpointNotFound()

        # Restore session state
        session = ConversationSession.objects.get(session_id=session_id)
        session.current_state = checkpoint['current_state']
        session.collected_data.update(checkpoint['collected_data'])
        session.save()

        return {
            'session_id': session_id,
            'resumed_at': checkpoint['current_state'],
            'questions_answered': len(checkpoint['question_history']),
            'next_action': self._determine_next_action(checkpoint)
        }
```

2. **Abandonment Risk Detection**
```python
def detect_abandonment_risk(self, session):
    """ML-based abandonment prediction"""
    risk_factors = []
    risk_score = 0

    # Factor 1: Inactivity time
    time_inactive = (timezone.now() - session.mdtz).seconds
    if time_inactive > 300:  # 5 minutes
        risk_factors.append('inactivity_5min')
        risk_score += 30

    # Factor 2: Question repetition (stuck)
    if session.metadata.get('same_question_count', 0) > 2:
        risk_factors.append('question_confusion')
        risk_score += 25

    # Factor 3: Session complexity
    total_questions = len(session.metadata.get('question_history', []))
    if total_questions > 15:
        risk_factors.append('fatigue_risk')
        risk_score += 20

    # Factor 4: Error frequency
    errors = session.metadata.get('error_count', 0)
    if errors > 3:
        risk_factors.append('technical_issues')
        risk_score += 25

    return {
        'risk_score': min(risk_score, 100),
        'risk_level': 'high' if risk_score > 70 else 'medium' if risk_score > 40 else 'low',
        'risk_factors': risk_factors,
        'intervention': self._recommend_intervention(risk_factors)
    }

def _recommend_intervention(self, risk_factors):
    """Recommend proactive intervention"""
    if 'question_confusion' in risk_factors:
        return {
            'type': 'simplify_question',
            'action': 'Offer simpler alternative or skip question',
            'urgency': 'high'
        }
    if 'fatigue_risk' in risk_factors:
        return {
            'type': 'save_progress',
            'action': 'Suggest saving and continuing later',
            'urgency': 'medium'
        }
    if 'technical_issues' in risk_factors:
        return {
            'type': 'support_escalation',
            'action': 'Offer live support chat',
            'urgency': 'high'
        }
    return None
```

### Phase 3.2: Analytics Dashboard

**New File:** `apps/onboarding_api/views/analytics_dashboard_views.py` (est. 720 lines)

**Dashboard Sections:**

1. **Real-Time Funnel Visualization**
```python
GET /api/v1/onboarding/dashboard/funnel-realtime/
Response:
{
    "timestamp": "2025-10-01T12:00:00Z",
    "active_sessions": 45,
    "stages": [
        {
            "stage": "started",
            "current_count": 45,
            "completion_rate": 100.0,
            "avg_time_seconds": 0
        },
        {
            "stage": "engaged",
            "current_count": 38,
            "completion_rate": 84.4,
            "avg_time_seconds": 120
        },
        {
            "stage": "recommendations_generated",
            "current_count": 31,
            "completion_rate": 68.9,
            "avg_time_seconds": 420
        },
        {
            "stage": "approval_decision",
            "current_count": 28,
            "completion_rate": 62.2,
            "avg_time_seconds": 180
        },
        {
            "stage": "completed",
            "current_count": 24,
            "completion_rate": 53.3,
            "avg_time_seconds": 300
        }
    ],
    "conversion_funnel": [100, 84.4, 68.9, 62.2, 53.3]
}
```

2. **Drop-Off Heatmap**
```python
class DropOffHeatmapView(APIView):
    def get(self, request):
        """Generate drop-off heatmap data"""
        time_range = request.query_params.get('range', '24h')

        # Group by hour and stage
        heatmap_data = []
        for hour in range(24):
            hour_data = {'hour': hour, 'drop_offs': {}}

            for stage in FUNNEL_STAGES:
                drop_off_count = self._count_drop_offs(stage, hour)
                hour_data['drop_offs'][stage] = drop_off_count

            heatmap_data.append(hour_data)

        return Response({
            'heatmap': heatmap_data,
            'peak_drop_off_time': self._find_peak_drop_off_time(heatmap_data),
            'recommendations': self._generate_timing_recommendations(heatmap_data)
        })
```

3. **Session Replay**
```python
class SessionReplayView(APIView):
    def get(self, request, session_id):
        """Get complete session timeline for replay"""
        session = ConversationSession.objects.get(session_id=session_id)

        timeline = [
            {
                'timestamp': session.cdtz.isoformat(),
                'event': 'session_started',
                'data': {'language': session.language}
            }
        ]

        # Add all state changes from metadata
        for state_change in session.metadata.get('state_history', []):
            timeline.append({
                'timestamp': state_change['timestamp'],
                'event': 'state_change',
                'data': {
                    'from': state_change['from_state'],
                    'to': state_change['to_state']
                }
            })

        # Add all questions asked
        for q in session.metadata.get('question_history', []):
            timeline.append({
                'timestamp': q['asked_at'],
                'event': 'question_asked',
                'data': {
                    'question': q['question'],
                    'answer': q.get('answer'),
                    'answer_time': q.get('answered_at')
                }
            })

        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])

        return Response({
            'session_id': session_id,
            'timeline': timeline,
            'duration_seconds': (session.mdtz - session.cdtz).total_seconds(),
            'final_state': session.current_state
        })
```

### Phase 3.3: Error Recovery System

**New File:** `apps/onboarding_api/services/error_recovery.py` (est. 520 lines)

**Error Categorization Engine:**
```python
class ErrorRecoveryService:
    def categorize_error(self, exception, context=None):
        """Intelligent error categorization"""
        category = {
            'type': type(exception).__name__,
            'severity': self._determine_severity(exception),
            'recoverable': self._is_recoverable(exception),
            'user_impact': self._assess_user_impact(exception),
            'recommended_action': None
        }

        # Categorize by exception type
        if isinstance(exception, (ConnectionError, TimeoutError)):
            category.update({
                'category': 'transient_network',
                'user_message': 'Connection issue. Retrying automatically...',
                'recovery_strategy': 'exponential_backoff_retry',
                'max_retries': 3,
                'recommended_action': 'AUTO_RETRY'
            })

        elif isinstance(exception, ValidationError):
            category.update({
                'category': 'user_input',
                'user_message': self._generate_friendly_validation_message(exception),
                'recovery_strategy': 'prompt_correction',
                'max_retries': 0,
                'recommended_action': 'USER_CORRECTION'
            })

        elif isinstance(exception, (DatabaseError, OperationalError)):
            category.update({
                'category': 'database_failure',
                'user_message': 'Service temporarily unavailable. Please try again in a moment.',
                'recovery_strategy': 'circuit_breaker_fallback',
                'max_retries': 2,
                'recommended_action': 'AUTO_RETRY_WITH_BACKOFF'
            })

        elif 'rate limit' in str(exception).lower():
            category.update({
                'category': 'rate_limit',
                'user_message': 'Too many requests. Please wait a moment.',
                'recovery_strategy': 'wait_and_retry',
                'retry_after': self._extract_retry_after(exception),
                'recommended_action': 'DELAYED_RETRY'
            })

        else:
            category.update({
                'category': 'unknown',
                'user_message': 'An unexpected error occurred. Our team has been notified.',
                'recovery_strategy': 'manual_intervention',
                'max_retries': 0,
                'recommended_action': 'ALERT_ADMIN'
            })

        return category

    def auto_recover(self, error_category, original_function, *args, **kwargs):
        """Automatic recovery based on error category"""
        strategy = error_category['recovery_strategy']

        if strategy == 'exponential_backoff_retry':
            return self._retry_with_backoff(
                original_function,
                max_retries=error_category['max_retries'],
                *args,
                **kwargs
            )

        elif strategy == 'circuit_breaker_fallback':
            return self._execute_with_fallback(
                original_function,
                fallback_value=self._generate_fallback_response(error_category),
                *args,
                **kwargs
            )

        elif strategy == 'wait_and_retry':
            retry_after = error_category.get('retry_after', 60)
            time.sleep(retry_after)
            return original_function(*args, **kwargs)

        else:
            raise Exception(f"Cannot auto-recover: {error_category['user_message']}")
```

---

## 🧪 COMPREHENSIVE TEST SUITE

### Test Organization
```
apps/onboarding_api/tests/
├── test_rate_limiter_comprehensive.py          # 8 tests
├── test_upload_throttling_comprehensive.py     # 7 tests
├── test_dlq_integration.py                     # 5 tests
├── test_funnel_analytics.py                    # 6 tests
├── test_session_recovery.py                    # 6 tests
├── test_analytics_dashboard.py                 # 4 tests
└── test_error_recovery.py                      # 4 tests
```

### Critical Tests to Implement

**Rate Limiter Tests (apps/onboarding_api/tests/test_rate_limiter_comprehensive.py):**
```python
class RateLimiterResilienceTests(TestCase):
    def test_cache_failure_circuit_breaker_opens(self):
        """Test circuit breaker opens after threshold failures"""

    def test_critical_resource_fails_closed_on_cache_failure(self):
        """Test critical resources block when cache fails"""

    def test_fallback_cache_provides_conservative_limits(self):
        """Test fallback cache enforces 50/hour limit"""

    def test_retry_after_header_calculation_accuracy(self):
        """Test Retry-After header matches next reset time"""

    def test_circuit_breaker_auto_reset_after_timeout(self):
        """Test circuit breaker closes after 5 minutes"""
```

**Upload Throttling Tests:**
```python
class UploadThrottlingTests(TestCase):
    def test_photo_quota_enforcement_per_session(self):
        """Test max 50 photos per session enforced"""

    def test_burst_protection_limits_rapid_uploads(self):
        """Test max 10 photos/minute limit"""

    def test_file_type_validation_rejects_invalid_types(self):
        """Test .exe files rejected for photo uploads"""
```

**DLQ Integration Tests:**
```python
class DLQIntegrationTests(TestCase):
    def test_task_sent_to_dlq_on_final_retry(self):
        """Test failed task appears in DLQ after max retries"""

    def test_dlq_task_manual_retry_succeeds(self):
        """Test admin can retry task from DLQ"""

    def test_critical_task_failure_triggers_alert(self):
        """Test Slack alert sent for critical task failures"""
```

---

## 📦 DEPLOYMENT CHECKLIST

### 1. Environment Configuration
```bash
# Required settings
export RATE_LIMITER_CIRCUIT_BREAKER_THRESHOLD=5
export ONBOARDING_MAX_PHOTOS_PER_SESSION=50
export DLQ_MAX_QUEUE_SIZE=1000
export ENABLE_SESSION_RECOVERY=true
export ENABLE_FUNNEL_ANALYTICS=true

# Optional: Alerting
export SLACK_WEBHOOK_URL=https://hooks.slack.com/...
export ADMIN_ALERT_EMAIL=admin@example.com
```

### 2. Database Migrations
```bash
# If adding session recovery models
python manage.py makemigrations onboarding
python manage.py migrate

# Verify migrations
python manage.py showmigrations onboarding
```

### 3. Redis Configuration
```bash
# Ensure Redis is running for:
# - Rate limiter
# - Upload throttling
# - Session checkpoints
# - DLQ cache

redis-cli ping  # Should return PONG
```

### 4. Celery Workers
```bash
# Start DLQ-aware workers
./scripts/celery_workers.sh start

# Verify DLQ handler is loaded
python manage.py shell
>>> from background_tasks.dead_letter_queue import dlq_handler
>>> dlq_handler.list_dlq_tasks(limit=10)
```

### 5. Monitoring Setup
```bash
# Add Grafana dashboards
cp config/grafana/dashboards/onboarding_funnel.json \
   /etc/grafana/provisioning/dashboards/

# Add Prometheus rules
cp config/prometheus/rules/dlq_alerts.yml \
   /etc/prometheus/rules/
```

---

## 🎯 SUCCESS METRICS

| Metric | Target | Measurement |
|--------|--------|-------------|
| Rate Limiter Uptime | 99.9% | During cache outages |
| Upload Quota Accuracy | 100% | No false positives/negatives |
| DLQ Processing Time | < 5 minutes | Time to alert and retry |
| Session Recovery Rate | 80% | Successful resumes after abandonment |
| Funnel Analytics Latency | < 200ms | Dashboard load time |
| Error Auto-Recovery Rate | 70% | Transient errors recovered |
| Overall Conversion Increase | +15% | Post-recovery implementation |

---

## 📚 PRIORITY RANKING

### IMMEDIATE (Week 1):
1. ✅ Fix funnel analytics syntax error (5 min)
2. 🔲 Complete funnel calculation methods (4 hours)
3. 🔲 Create DLQ admin dashboard (6 hours)
4. 🔲 Write critical tests for Phase 1 (4 hours)

### HIGH (Week 2):
5. 🔲 Implement session recovery service (8 hours)
6. 🔲 Create funnel analytics API (4 hours)
7. 🔲 Build error categorization engine (6 hours)
8. 🔲 Write integration tests (6 hours)

### MEDIUM (Week 3):
9. 🔲 Build analytics dashboard views (8 hours)
10. 🔲 Implement drop-off heatmap (4 hours)
11. 🔲 Create session replay functionality (6 hours)
12. 🔲 Add DLQ alerting system (4 hours)

### NICE-TO-HAVE (Week 4):
13. 🔲 Cohort analysis advanced features (6 hours)
14. 🔲 ML-based abandonment prediction (8 hours)
15. 🔲 A/B testing integration (6 hours)
16. 🔲 Advanced error recovery strategies (4 hours)

---

## 🔗 INTEGRATION POINTS

**Frontend Integration:**
- Dashboard: React/Vue components for funnel visualization
- Session Recovery: Auto-save every 30s, "Resume" button on return
- Error Messages: Display contextual, user-friendly errors from recovery service

**Mobile App Integration:**
- Upload throttling headers in API responses
- Session checkpoint sync on background/foreground
- Offline mode with checkpoint restoration

**Admin Tools:**
- DLQ management interface
- Funnel analytics reports
- Session replay debugger

---

**Total Estimated Effort:** 80 hours (2 weeks full-time)
**Current Progress:** 33% (Phase 1 complete, 26 hours invested)
**Remaining:** 54 hours across Phases 2-3

**Recommendation:** Prioritize DLQ dashboard (6h) and funnel analytics completion (8h) for immediate production value.
