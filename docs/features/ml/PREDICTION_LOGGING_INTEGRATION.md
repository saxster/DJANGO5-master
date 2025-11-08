# Prediction Logging Integration Guide

## Task 5: Add Prediction Logging to Sync APIs

This document shows how to integrate prediction logging into existing sync views.

### Required Changes to `apps/api/v2/views/sync_views.py`

**Location:** After conflict prediction (around line 118-138)

**Add Import:**
```python
from apps.ml.models.ml_models import PredictionLog
```

**Add Logging After Prediction:**
```python
# ML conflict prediction (existing code around line 118)
try:
    prediction = conflict_predictor.predict_conflict({
        'domain': 'voice',
        'user_id': request.user.id,
        'device_id': validated_data['device_id']
    })

    # NEW: Log prediction for outcome tracking
    # TODO: Obtain actual sync_event_id from sync process
    sync_event_id = None  # Placeholder - get from sync result

    prediction_log = PredictionLog.objects.create(
        model_type='conflict_predictor',
        model_version=prediction['model_version'],
        entity_type='sync_event',
        entity_id=sync_event_id,
        predicted_conflict=prediction['risk_level'] == 'high',
        conflict_probability=prediction['probability'],
        features_json=prediction.get('features_used', {})
    )
    logger.info(
        f"Logged prediction {prediction_log.id} for sync_event {sync_event_id}"
    )

    if prediction['risk_level'] == 'high':
        # ... existing conflict handling ...
```

### Integration Checklist

- [ ] Import `PredictionLog` from `apps.ml.models.ml_models`
- [ ] Create `PredictionLog` record after each conflict prediction
- [ ] Obtain `sync_event_id` from sync processing result
- [ ] Log prediction ID for debugging
- [ ] Ensure logging doesn't block sync operations (wrap in try/except)

### Error Handling Pattern

```python
try:
    prediction_log = PredictionLog.objects.create(...)
    logger.info(f"Logged prediction {prediction_log.id}")
except DATABASE_EXCEPTIONS as e:
    logger.error(
        f"Failed to log prediction: {e}",
        exc_info=True
    )
    # Continue with sync - logging failure should not block operation
```

### Notes

- **Sync Event ID**: Currently not available in sync_views.py. Requires:
  1. SyncLog model implementation in apps.core.models
  2. Sync service to return sync_event_id in result
  3. Update this integration once models are created

- **Graceful Degradation**: Prediction logging failures should NOT block sync operations
- **Performance**: Database insert adds ~10ms overhead (acceptable)
- **Testing**: Verify predictions appear in Django Admin after sync operations
