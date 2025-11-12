# ML Conflict Prediction - Phase 2 Feature

**Status**: NOT IMPLEMENTED (Stub only)
**Priority**: Phase 2+ (After core sync functionality stabilizes)
**Blocked By**: Missing SyncLog and ConflictResolution models
**Impact**: Medium - Proactive conflict warnings would improve UX

---

## Overview

Machine learning model to predict conflict likelihood when multiple users edit the same entity concurrently. Provides proactive warnings to users: "High conflict risk detected - another user is editing this."

**Current State**: Framework exists but returns empty DataFrame (no data to train on)

---

## Architecture

### Data Flow

```
Sync Operation
  ↓
SyncLog.objects.create()  ← MISSING MODEL
  ↓
Conflict Detected?
  ↓
ConflictResolution.objects.create()  ← MISSING MODEL
  ↓
ConflictDataExtractor.extract_training_data()
  ↓
ML Model Training
  ↓
Conflict Prediction API
```

### Required Models

#### 1. SyncLog Model

**Location**: `apps/core/models/sync_tracking.py`

```python
from django.db import models
from apps.core.models import TenantAwareModel

class SyncLog(TenantAwareModel):
    """
    Track all sync operations for ML training.

    Every time a mobile client syncs data (create/update/delete),
    log the operation here for conflict prediction training.
    """

    user = models.ForeignKey('peoples.People', on_delete=models.CASCADE)
    entity_type = models.CharField(max_length=100)  # 'Task', 'Attendance', etc.
    entity_id = models.CharField(max_length=100)
    operation = models.CharField(max_length=20, choices=[
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
    ])
    timestamp = models.DateTimeField(auto_now_add=True)

    # ML features
    concurrent_editors = models.PositiveIntegerField(default=0)
    hours_since_last_sync = models.FloatField(default=0.0)

    class Meta:
        db_table = 'core_sync_log'
        indexes = [
            models.Index(fields=['entity_type', 'entity_id', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['timestamp']),  # For time-range queries
        ]
        ordering = ['-timestamp']
```

#### 2. ConflictResolution Model

**Location**: `apps/core/models/sync_tracking.py`

```python
class ConflictResolution(models.Model):
    """
    Track conflict occurrences and how they were resolved.

    Created when sync engine detects two users edited same entity
    within conflict window (typically 5-10 minutes).
    """

    sync_log = models.ForeignKey(SyncLog, on_delete=models.CASCADE)
    conflicted_with = models.ForeignKey(
        SyncLog,
        on_delete=models.CASCADE,
        related_name='caused_conflicts'
    )

    resolution_strategy = models.CharField(max_length=50, choices=[
        ('server_wins', 'Server Wins'),
        ('client_wins', 'Client Wins'),
        ('manual', 'Manual Resolution'),
        ('field_merge', 'Field-level Merge'),
    ])

    resolved_at = models.DateTimeField(auto_now_add=True)

    # Metadata
    field_conflicts = models.JSONField(default=dict)  # Which fields conflicted
    user_notified = models.BooleanField(default=False)

    class Meta:
        db_table = 'core_conflict_resolution'
        indexes = [
            models.Index(fields=['resolved_at']),
            models.Index(fields=['resolution_strategy']),
        ]
```

### ML Features

| Feature | Description | Computation |
|---------|-------------|-------------|
| `concurrent_editors` | Number of users editing same entity in ±5 min window | `SyncLog.objects.filter(entity=X, time_window).distinct('user_id').count()` |
| `hours_since_last_sync` | Hours since user's last sync for this entity | `(current_time - last_sync_time).total_seconds() / 3600` |
| `user_conflict_rate` | User's historical conflict rate (%) | `user_conflicts / user_total_syncs * 100` |
| `entity_edit_frequency` | How often this entity is edited | `syncs_per_day = SyncLog.objects.filter(entity=X).count() / days` |
| `field_overlap_score` | Likelihood fields overlap (0-1) | Based on common field edit patterns |
| **Target**: `conflict_occurred` | Did a conflict happen? (binary) | `ConflictResolution.objects.filter(sync_log=X).exists()` |

### ML Model

**Algorithm**: Random Forest Classifier (scikit-learn)
**Training Data**: 90 days of sync logs
**Prediction**: Probability of conflict (0-1)
**Threshold**: 0.7 (70% probability triggers warning)

**API Endpoint**: `POST /api/ml/predict-conflict/`

```json
{
  "user_id": 123,
  "entity_type": "Task",
  "entity_id": "task_456",
  "timestamp": "2025-11-11T10:30:00Z"
}
```

**Response**:
```json
{
  "conflict_probability": 0.85,
  "risk_level": "high",
  "warning_message": "Another user is likely editing this task. Consider coordinating to avoid conflicts.",
  "concurrent_editors_detected": 2
}
```

---

## Implementation Timeline

### Phase 2.1: Model Creation (1 week)
- Create SyncLog and ConflictResolution models
- Write migrations
- Add model admin interfaces

### Phase 2.2: Data Collection (2-4 weeks)
- Instrument sync operations to populate SyncLog
- Implement conflict detection in sync engine
- Collect real data (need minimum 1000 sync events)

### Phase 2.3: Feature Implementation (1 week)
- Implement all feature extraction methods
- Test with real data
- Validate feature quality

### Phase 2.4: Model Training (1 week)
- Train Random Forest model
- Evaluate performance (precision/recall)
- Tune hyperparameters

### Phase 2.5: API Deployment (1 week)
- Create prediction API endpoint
- Add to mobile apps
- Monitor prediction accuracy

**Total Estimated Time**: 6-8 weeks

---

## Dependencies

**Blocked By**:
1. SyncLog model implementation
2. Sync engine instrumentation
3. Conflict detection logic
4. Data collection period (need historical data)

**Blocks**:
- Proactive conflict warnings in mobile apps
- Sync optimization recommendations
- User education (conflict-prone users)

---

## Success Metrics

**Model Performance**:
- Precision > 70% (avoid false warnings)
- Recall > 60% (catch most conflicts)
- Latency < 100ms (real-time prediction)

**Business Metrics**:
- Reduce actual conflicts by 30%
- Improve user satisfaction (fewer data loss incidents)
- Reduce support tickets related to sync conflicts

---

## Current Stub Behavior

**apps/ml/services/data_extractors/conflict_data_extractor.py**:
- Returns empty DataFrame with correct schema
- All feature methods return default values (0, 0.0, 168.0)
- Defensive: Training pipeline handles empty data gracefully
- No errors: API returns "Insufficient training data"

**No Immediate Action Required**: Stub is safe and documented.

---

## References

- **Stub Implementation**: `apps/ml/services/data_extractors/conflict_data_extractor.py`
- **ML Training Pipeline**: `apps/ml_training/` (dataset management, labeling)
- **Mobile Sync**: Kotlin/Swift apps with offline-first architecture
- **Related**: `docs/features/DOMAIN_SPECIFIC_SYSTEMS.md` (ML infrastructure)

---

**Last Updated**: November 11, 2025
**Next Review**: When sync infrastructure stabilizes (Q1 2026)
**Owner**: ML/Data Science Team
