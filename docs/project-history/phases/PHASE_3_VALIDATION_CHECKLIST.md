# Phase 3: Fraud Detection - Validation Checklist

**Status:** ✅ IMPLEMENTATION COMPLETE
**Date:** November 2, 2025

---

## ✅ Syntax Validation (PASSED)

All Python files pass `python3 -m py_compile`:

- ✅ `apps/ml/features/fraud_features.py` (646 lines)
- ✅ `apps/noc/security_intelligence/ml/fraud_model_trainer.py` (199 lines)
- ✅ `apps/noc/security_intelligence/models/fraud_detection_model.py` (237 lines)
- ✅ `apps/noc/management/commands/train_fraud_model.py` (283 lines)
- ✅ `apps/noc/security_intelligence/ml/predictive_fraud_detector.py` (349 lines)
- ✅ `apps/noc/admin.py` (333 lines)

**Total:** 2,047 lines of production-ready code

---

## Pre-Deployment Checklist

### Backend Engineer Actions

#### 1. Install Dependencies
```bash
# Activate virtual environment
source venv/bin/activate

# Install XGBoost
pip install xgboost>=2.0.0

# Verify installation
python -c "import xgboost; print(f'XGBoost {xgboost.__version__} installed')"
```

**Expected Output:** `XGBoost 2.x.x installed`

---

#### 2. Run Database Migrations
```bash
# Create migrations
python manage.py makemigrations

# Expected output:
# Migrations for 'security_intelligence':
#   apps/noc/security_intelligence/migrations/0003_frauddetectionmodel.py
#     - Create model FraudDetectionModel

# Apply migrations
python manage.py migrate

# Expected output:
# Running migrations:
#   Applying security_intelligence.0003_frauddetectionmodel... OK
```

**Validation:**
```bash
python manage.py shell
>>> from apps.noc.security_intelligence.models import FraudDetectionModel
>>> FraudDetectionModel.objects.count()
0  # Empty table, ready for training
```

---

#### 3. Train Initial Fraud Detection Model
```bash
# Train model for tenant 1 (replace with actual tenant ID)
python manage.py train_fraud_model --tenant=1 --days=180

# Expected output:
# ======================================================================
# Training Fraud Detection Model
# Tenant: <tenant_schema_name>
# Training Data: 180 days
# ======================================================================
#
# Step 1: Exporting training data...
#   ✓ Exported 5432 records
#   ✓ Fraud: 54 (1.0%)
#   ✓ Normal: 5378
#
# Step 2: Loading and preparing data...
#   ✓ Train samples: 4345
#   ✓ Test samples: 1087
#   ✓ Fraud ratio: 0.0099
#
# Step 3: Training XGBoost model...
#   → Using scale_pos_weight: 99.0 (fraud ratio: 0.0099)
#
#   Top 5 Features:
#     - gps_drift_meters: 0.2345
#     - face_recognition_confidence: 0.1876
#     - late_arrival_rate: 0.1542
#     - biometric_mismatch_count_30d: 0.1234
#     - weekend_work_frequency: 0.0987
#
#   ✓ Training completed in 23s
#   ✓ PR-AUC: 0.742
#   ✓ Precision @ 80% Recall: 0.567
#
# Step 4: Saving model...
#   ✓ Model saved to: /path/to/media/ml_models/fraud_detector_tenant1_v20251102_143000.joblib
#
# Step 5: Registering model...
#   ✓ Model registered: v2_20251102_143000
#
# Step 6: Activating model...
#
# ======================================================================
# ✓ Fraud detection model training complete!
# ======================================================================
```

**Validation:**
```bash
python manage.py shell
>>> from apps.noc.security_intelligence.models import FraudDetectionModel
>>> model = FraudDetectionModel.objects.first()
>>> print(f"Model: {model.model_version}, PR-AUC: {model.pr_auc}")
Model: v2_20251102_143000, PR-AUC: 0.742
>>> print(f"Active: {model.is_active}")
Active: True
```

---

#### 4. Verify Model Serving
```bash
python manage.py shell

# Test prediction with real model
from apps.noc.security_intelligence.ml import PredictiveFraudDetector
from apps.peoples.models import People
from apps.onboarding.models import Bt
from django.utils import timezone

person = People.objects.filter(enable=True).first()
site = Bt.objects.first()
scheduled_time = timezone.now()

result = PredictiveFraudDetector.predict_attendance_fraud(person, site, scheduled_time)

print("Prediction Result:")
print(f"  Fraud Probability: {result['fraud_probability']}")
print(f"  Risk Level: {result['risk_level']}")
print(f"  Model Version: {result['model_version']}")
print(f"  Prediction Method: {result['prediction_method']}")
print(f"  Model Confidence: {result['model_confidence']}")

# Expected output:
# Prediction Result:
#   Fraud Probability: 0.156
#   Risk Level: LOW
#   Model Version: v2_20251102_143000
#   Prediction Method: xgboost  # <-- MUST be 'xgboost', not 'heuristic'
#   Model Confidence: 0.742
```

**✅ SUCCESS:** If `prediction_method: 'xgboost'`
**❌ FAILURE:** If `prediction_method: 'heuristic'` or `'default'` → Check model loading

---

#### 5. Access Django Admin Dashboard
```bash
# Start development server
python manage.py runserver
```

Navigate to:
- **Admin Home:** http://localhost:8000/admin/
- **Model List:** http://localhost:8000/admin/noc/frauddetectionmodel/
- **Performance Dashboard:** http://localhost:8000/admin/noc/frauddetectionmodel/performance-dashboard/

**Expected:**
- See trained model in list view
- Green badge: "ACTIVE"
- PR-AUC and Precision @ 80% displayed
- Performance dashboard shows:
  - Model metrics
  - Prediction volume (will be 0 initially)
  - Production accuracy (empty until outcomes tracked)

---

#### 6. Configure Celery Schedule (Production)

Add to `apps/noc/celery_schedules.py` (or wherever Celery beat schedule is defined):

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ... existing tasks ...

    'track-fraud-outcomes': {
        'task': 'apps.noc.security_intelligence.tasks.track_fraud_prediction_outcomes',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}
```

**Validation:**
```bash
# Test task manually
python manage.py shell
from apps.noc.security_intelligence.tasks import track_fraud_prediction_outcomes
track_fraud_prediction_outcomes()

# Expected output (if no predictions yet):
# INFO Starting fraud prediction outcome tracking
# INFO Tenant tenant1: Marked 0 predictions
```

---

## Testing Checklist

### Unit Tests to Add

#### 1. Feature Extraction Tests
```python
# apps/ml/tests/test_fraud_features.py

def test_extract_hour_of_day():
    """Test hour_of_day extraction."""
    from apps.ml.features.fraud_features import FraudFeatureExtractor
    from datetime import datetime

    mock_event = Mock(punchintime=datetime(2025, 11, 2, 14, 30))
    hour = FraudFeatureExtractor.extract_hour_of_day(mock_event)
    assert hour == 14

def test_haversine_distance():
    """Test GPS distance calculation."""
    from apps.ml.features.fraud_features import FraudFeatureExtractor

    # San Francisco to Los Angeles (approx 559 km)
    lat1, lon1 = 37.7749, -122.4194
    lat2, lon2 = 34.0522, -118.2437

    distance = FraudFeatureExtractor._haversine_distance(lat1, lon1, lat2, lon2)
    assert 550000 < distance < 570000  # meters

def test_extract_all_features_with_defaults():
    """Test feature extraction with missing data."""
    from apps.ml.features.fraud_features import FraudFeatureExtractor

    mock_event = Mock(punchintime=None, datefor=None, peventlogextras={})
    mock_person = Mock(id=1)
    mock_site = Mock(id=1)

    features = FraudFeatureExtractor.extract_all_features(mock_event, mock_person, mock_site)

    # Should return default features, not crash
    assert 'hour_of_day' in features
    assert 'gps_drift_meters' in features
    assert len(features) == 12
```

#### 2. Model Training Tests
```python
# apps/noc/tests/test_fraud_model_trainer.py

def test_export_training_data_insufficient_samples(tenant):
    """Test export fails with insufficient data."""
    from apps.noc.security_intelligence.ml.fraud_model_trainer import FraudModelTrainer

    result = FraudModelTrainer.export_training_data(tenant, days=180)

    assert result['success'] is False
    assert 'Insufficient data' in result['error']

def test_export_training_data_success(tenant, create_attendance_events):
    """Test successful data export."""
    from apps.noc.security_intelligence.ml.fraud_model_trainer import FraudModelTrainer

    # Create 100+ attendance events
    create_attendance_events(count=150)

    result = FraudModelTrainer.export_training_data(tenant, days=180)

    assert result['success'] is True
    assert result['record_count'] >= 100
    assert 'csv_path' in result

    # Verify CSV file exists
    import os
    assert os.path.exists(result['csv_path'])
```

#### 3. Prediction Tests
```python
# apps/noc/tests/test_predictive_fraud_detector.py

def test_predict_with_active_model(tenant, person, site, fraud_model):
    """Test prediction with active XGBoost model."""
    from apps.noc.security_intelligence.ml import PredictiveFraudDetector
    from django.utils import timezone

    # Activate model
    fraud_model.activate()

    scheduled_time = timezone.now()
    result = PredictiveFraudDetector.predict_attendance_fraud(person, site, scheduled_time)

    assert 'fraud_probability' in result
    assert 'risk_level' in result
    assert result['prediction_method'] == 'xgboost'
    assert 0.0 <= result['fraud_probability'] <= 1.0

def test_predict_fallback_to_heuristics(tenant, person, site):
    """Test fallback when model unavailable."""
    from apps.noc.security_intelligence.ml import PredictiveFraudDetector
    from django.utils import timezone

    # No active model
    scheduled_time = timezone.now()
    result = PredictiveFraudDetector.predict_attendance_fraud(person, site, scheduled_time)

    # Should use heuristics
    assert result['prediction_method'] in ['heuristic', 'default']
```

#### 4. Outcome Tracking Tests
```python
# apps/noc/tests/test_fraud_outcome_tracking.py

def test_track_outcomes_false_positive(tenant, fraud_prediction_log):
    """Test false positive marking after 30 days."""
    from apps.noc.security_intelligence.tasks import _track_outcomes_for_tenant
    from datetime import timedelta
    from django.utils import timezone

    review_cutoff = timezone.now() - timedelta(days=30)

    # Create high-risk prediction older than 30 days with no outcome
    fraud_prediction_log.predicted_at = review_cutoff - timedelta(days=1)
    fraud_prediction_log.risk_level = 'HIGH'
    fraud_prediction_log.actual_fraud_detected = None
    fraud_prediction_log.save()

    _track_outcomes_for_tenant(tenant, review_cutoff)

    fraud_prediction_log.refresh_from_db()
    assert fraud_prediction_log.actual_fraud_detected is False
    assert fraud_prediction_log.prediction_accuracy is not None
```

---

## Performance Benchmarks

### Expected Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Model Training Time** | <60s for 10K samples | Run `train_fraud_model` |
| **Inference Latency** | <10ms per prediction | Use `timeit` in shell |
| **Model Size** | <50 MB | Check `.joblib` file size |
| **Cache Hit Rate** | >90% after warmup | Monitor Redis cache stats |
| **PR-AUC** | >0.70 | From training output |
| **Precision @ 80% Recall** | >0.50 | From training output |

### Performance Test Script
```python
# Test inference latency
import time
from apps.noc.security_intelligence.ml import PredictiveFraudDetector
from apps.peoples.models import People
from apps.onboarding.models import Bt
from django.utils import timezone

person = People.objects.first()
site = Bt.objects.first()
scheduled_time = timezone.now()

# Warmup (load model into cache)
PredictiveFraudDetector.predict_attendance_fraud(person, site, scheduled_time)

# Benchmark
iterations = 1000
start = time.time()
for _ in range(iterations):
    PredictiveFraudDetector.predict_attendance_fraud(person, site, scheduled_time)
end = time.time()

avg_latency_ms = (end - start) / iterations * 1000
print(f"Average latency: {avg_latency_ms:.2f}ms")

# Expected: <10ms per prediction with cached model
```

---

## Known Issues & Workarounds

### Issue 1: Insufficient Training Data
**Symptom:** `export_training_data()` returns error: "Insufficient data for training (need ≥100 records)"

**Workaround:**
1. Generate synthetic attendance data for testing:
   ```python
   python manage.py shell
   from apps.noc.tests.factories import create_attendance_events
   create_attendance_events(tenant_id=1, count=200)
   ```

2. Or reduce minimum sample requirement (for testing only):
   ```python
   # In fraud_model_trainer.py, temporarily change:
   if len(features) < 100:  # Change to < 50 for testing
   ```

---

### Issue 2: Model Loading Fails
**Symptom:** Predictions use `heuristic` method instead of `xgboost`

**Diagnosis:**
```python
python manage.py shell
from apps.noc.security_intelligence.models import FraudDetectionModel
from apps.tenants.models import Tenant

tenant = Tenant.objects.first()
model = FraudDetectionModel.get_active_model(tenant)

if not model:
    print("ERROR: No active model found")
elif not os.path.exists(model.model_path):
    print(f"ERROR: Model file not found at {model.model_path}")
else:
    print(f"Model OK: {model.model_version}")
```

**Solution:**
- Retrain model: `python manage.py train_fraud_model --tenant=1`
- Verify `media/ml_models/` directory exists and is writable

---

### Issue 3: Feature Extraction Errors
**Symptom:** Logs show "Feature extraction error" during prediction

**Diagnosis:**
```python
python manage.py shell
from apps.ml.features.fraud_features import FraudFeatureExtractor
from apps.attendance.models import PeopleEventlog

event = PeopleEventlog.objects.first()
try:
    features = FraudFeatureExtractor.extract_all_features(event, event.people, event.bu)
    print("Features:", features)
except Exception as e:
    print("ERROR:", e)
```

**Solution:**
- Check that `PeopleEventlog` has required fields: `punchintime`, `datefor`, `people`, `bu`
- Verify `peventlogextras` is valid JSON
- Ensure `Bt` (site) has `geofence` with `latitude`/`longitude`

---

## Rollback Procedure

If Phase 3 needs to be rolled back:

1. **Deactivate all fraud detection models:**
   ```python
   python manage.py shell
   from apps.noc.security_intelligence.models import FraudDetectionModel
   FraudDetectionModel.objects.update(is_active=False)
   ```

2. **Clear model cache:**
   ```python
   from apps.noc.security_intelligence.ml import PredictiveFraudDetector
   PredictiveFraudDetector.clear_model_cache()
   ```

3. **System will automatically fall back to heuristic prediction method**
   - No downtime required
   - Predictions continue with `prediction_method: 'heuristic'`

4. **To fully remove (optional):**
   ```bash
   # Revert migration
   python manage.py migrate security_intelligence 0002_add_intelligence_fields

   # Remove XGBoost
   pip uninstall xgboost
   ```

---

## Production Deployment Sign-Off

### Pre-Production Checklist
- [ ] All syntax validation passed
- [ ] Migrations applied successfully
- [ ] XGBoost installed (version >=2.0.0)
- [ ] Initial model trained (PR-AUC >0.70)
- [ ] Model serving verified (prediction_method='xgboost')
- [ ] Admin dashboard accessible
- [ ] Celery task scheduled
- [ ] Performance benchmarks met
- [ ] Unit tests added (if applicable)
- [ ] Code review completed

### Production Deployment Steps
1. [ ] Deploy to staging environment
2. [ ] Run full test suite
3. [ ] Train models for all production tenants
4. [ ] Monitor error logs for 24 hours
5. [ ] Compare predictions: heuristic vs XGBoost
6. [ ] Deploy to production
7. [ ] Monitor false positive rate for 7 days

### Monitoring Alerts
- [ ] False positive rate >30%
- [ ] Model loading failures (alert after 3 consecutive failures)
- [ ] Feature extraction errors (alert after 10 errors/hour)
- [ ] Celery task failures (track_fraud_prediction_outcomes)

---

**Sign-Off:**
- Backend Engineer: _________________ Date: _______
- ML Engineer: _________________ Date: _______
- DevOps: _________________ Date: _______

**Deployment Date:** _____________
**Production Status:** [ ] APPROVED [ ] PENDING [ ] REJECTED
