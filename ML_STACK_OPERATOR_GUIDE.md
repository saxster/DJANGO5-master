# ML Stack - Operator Guide & Deployment Checklist

**Audience:** DevOps, ML Engineers, Backend Developers
**Purpose:** Daily operations, troubleshooting, deployment procedures
**Last Updated:** November 2, 2025

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Deployment Checklist](#deployment-checklist)
3. [Monitoring & Alerts](#monitoring--alerts)
4. [Troubleshooting](#troubleshooting)
5. [Model Management](#model-management)
6. [Performance Tuning](#performance-tuning)

---

## Daily Operations

### Morning Health Check (5 minutes)

**1. Check Training Data Capture:**
```bash
# Navigate to: http://your-domain/admin/ml-training/metrics/

# Or via Django shell:
python manage.py shell
>>> from apps.ml_training.monitoring import TrainingDataMetrics
>>> metrics = TrainingDataMetrics.get_capture_rate_metrics(days_back=1)
>>> print(f"Captured yesterday: {metrics['last_24h_count']} (target: 10-20)")
>>> print(f"Alert status: {metrics['alert_status']}")
```

**Expected:** 10-20 examples captured in last 24h, status = 'ok'

**2. Check Model Prediction Volume:**
```python
>>> from apps.ml.models.ml_models import PredictionLog
>>> from datetime import timedelta
>>> from django.utils import timezone
>>> yesterday = timezone.now() - timedelta(days=1)
>>> conflict_predictions = PredictionLog.objects.filter(
...     model_type='conflict_predictor',
...     created_at__gte=yesterday
... ).count()
>>> print(f"Conflict predictions: {conflict_predictions}")
```

**Expected:** >50 predictions/day (varies by traffic)

**3. Check Fraud Alerts:**
```python
>>> from apps.noc.security_intelligence.models import FraudPredictionLog
>>> high_risk = FraudPredictionLog.objects.filter(
...     risk_level='high',
...     created_at__gte=yesterday
... ).count()
>>> print(f"High-risk fraud predictions: {high_risk}")
```

**Expected:** <5% of attendance events flagged as high-risk

**4. Check Celery Tasks:**
```bash
# Verify all tasks completed
celery -A intelliwiz_config inspect stats | grep -A 5 "ml_training\|ai_processing\|monitoring"

# Check for failures
tail -100 logs/celery-worker.log | grep -i error
```

**Expected:** No errors, all tasks succeeded

---

## Deployment Checklist

### Pre-Deployment (Complete Before Production)

**Environment Setup:**
- [ ] Python 3.11.9 installed via pyenv
- [ ] Virtual environment created and activated
- [ ] All requirements installed: `pip install -r requirements/ai_requirements.txt`
- [ ] PostgreSQL 14.2+ with PostGIS extension
- [ ] Redis 6+ for Celery broker

**Database Preparation:**
- [ ] Run migrations: `python manage.py migrate ml_training ml noc monitoring`
- [ ] Verify tables created: Check `ml_training_dataset`, `ml_prediction_log`, etc.
- [ ] Create `media/ml_models/` directory: `mkdir -p media/ml_models media/ml_training_data`
- [ ] Set permissions: `chmod 755 media/ml_models media/ml_training_data`

**Model Training:**
- [ ] Extract conflict training data: `python manage.py extract_conflict_training_data`
- [ ] Train conflict model: `python manage.py train_conflict_model`
- [ ] Verify ROC-AUC > 0.75 in output
- [ ] Activate conflict model in Django shell
- [ ] Train fraud model per tenant: `python manage.py train_fraud_model --tenant-id 1`
- [ ] Verify PR-AUC > 0.70 in output
- [ ] Activate fraud model in Django shell
- [ ] Train drift detector: `python manage.py train_drift_detector --days=30`

**Celery Configuration:**
- [ ] Add queues to worker config: `ml_training`, `ai_processing`, `monitoring`
- [ ] Verify beat schedule loaded: Check `intelliwiz_config/celery.py` lines 353-394
- [ ] Start workers: `celery -A intelliwiz_config worker -Q ml_training,ai_processing,monitoring -c 4`
- [ ] Start beat: `celery -A intelliwiz_config beat`
- [ ] Verify tasks registered: `celery -A intelliwiz_config inspect registered`

**Integration Testing:**
- [ ] Upload low-confidence meter image, verify `TrainingExample` created
- [ ] Submit user correction via API, verify uncertainty_score=1.0
- [ ] Make conflict prediction API call, verify `PredictionLog` created
- [ ] Trigger attendance event, verify fraud prediction logged
- [ ] Wait 5 minutes, check `InfrastructureMetric` has data
- [ ] Check unified dashboard loads: `/admin/monitoring/unified-dashboard/`

**Security Validation:**
- [ ] Test cross-tenant access (should be blocked with 403)
- [ ] Verify API authentication required
- [ ] Check model files have proper permissions (not world-readable)
- [ ] Confirm joblib used (not insecure serialization)

### Post-Deployment (First 24 Hours)

**Hour 1-2:**
- [ ] Monitor Celery logs for errors
- [ ] Check training data capture (should have 1-2 examples)
- [ ] Verify predictions being made and logged

**Hour 6-8:**
- [ ] First outcome tracking task runs (check logs)
- [ ] Verify some predictions have outcomes
- [ ] Check accuracy calculations

**Hour 24:**
- [ ] Should have 10-20 training examples
- [ ] Should have 100+ predictions logged
- [ ] Should have 10-20 infrastructure anomalies detected
- [ ] Review dashboards for data quality

### Post-Deployment (First Week)

**Day 2-3:**
- [ ] Review false positive alerts
- [ ] Tune thresholds if FP rate >20%
- [ ] Check model accuracy (need 100+ predictions)

**Day 7 (Sunday):**
- [ ] Active learning task runs at 2am
- [ ] Verify 50 samples selected for labeling
- [ ] Check `LabelingTask` records created
- [ ] Review samples in admin interface

**Day 7 (Monday):**
- [ ] Weekly conflict model retraining runs at 3am
- [ ] Verify new model trained
- [ ] Check if auto-activated (>5% improvement)
- [ ] Review model comparison logs

---

## Monitoring & Alerts

### Critical Alerts (Immediate Action Required)

**1. Zero Training Examples in 24 Hours**
- **Alert:** "CRITICAL: Zero training examples captured in past 24 hours"
- **Impact:** ML training pipeline is broken
- **Action:**
  ```python
  # Check OCR service status
  from apps.activity.services.meter_reading_service import MeterReadingService
  service = MeterReadingService()
  # Verify OCR service initialized (not None)

  # Check recent meter readings
  from apps.activity.models import MeterReading
  recent = MeterReading.objects.order_by('-created_at')[:10]
  # All readings have confidence_score > 0.7? Lower threshold.
  ```

**2. Model Accuracy Drop <70%**
- **Alert:** "Model accuracy dropped to X% (threshold: 70%)"
- **Impact:** Model predictions unreliable
- **Action:**
  ```bash
  # Trigger manual retraining
  python manage.py extract_conflict_training_data --days-back 90
  python manage.py train_conflict_model

  # Review data quality
  # Check if recent data distribution shifted
  ```

**3. Celery Task Failure (3+ consecutive)**
- **Alert:** "Celery task <name> failed 3 times consecutively"
- **Impact:** Outcome tracking, retraining, or metrics collection stopped
- **Action:**
  ```bash
  # Check Celery logs
  tail -100 logs/celery-worker.log | grep -i error

  # Restart failed queue
  celery -A intelliwiz_config control shutdown
  # Then restart with proper config
  ```

### Warning Alerts (Review Within 24 Hours)

**1. Low Capture Rate (<5/day)**
- **Alert:** "WARNING: Low capture rate (X/day, target: 10-20/day)"
- **Impact:** Insufficient training data
- **Action:** Review OCR confidence threshold, check production volume

**2. High False Positive Rate (>20%)**
- **Alert:** "Fraud detector FP rate: X% (threshold: 20%)"
- **Impact:** Alert fatigue, supervisors ignoring alerts
- **Action:** Mark false positives in admin, auto-tuning will adjust

**3. Model Drift Detected**
- **Alert:** "Prediction distribution shifted (K-S test p<0.01)"
- **Impact:** Model may be stale
- **Action:** Trigger manual retraining, review recent data

---

## Troubleshooting

### Common Issues

#### Issue 1: Models Not Loading

**Symptoms:**
- Logs show "Using heuristic prediction (no trained model available)"
- Predictions always return default probabilities

**Diagnosis:**
```python
from apps.ml.models.ml_models import ConflictPredictionModel
import os

active = ConflictPredictionModel.objects.filter(is_active=True).first()
if not active:
    print("ERROR: No active model found")
else:
    print(f"Model: {active.model_version}")
    print(f"Path: {active.model_path}")
    print(f"Exists: {os.path.exists(active.model_path)}")
```

**Solutions:**
1. **No active model:** Train model, then activate
2. **File missing:** Check `media/ml_models/` directory permissions
3. **Cache stale:** Clear cache with `ConflictPredictor.clear_model_cache()`

#### Issue 2: XGBoost Installation Failure

**Symptoms:**
- `ModuleNotFoundError: No module named 'xgboost'`
- `train_fraud_model` command fails

**Solution:**
```bash
# macOS (with Homebrew)
brew install libomp
pip install xgboost==2.0.3

# Linux
pip install xgboost==2.0.3

# Verify
python -c "import xgboost; print(xgboost.__version__)"
```

#### Issue 3: Celery Beat Not Starting

**Symptoms:**
- Scheduled tasks never run
- `celery inspect scheduled` returns empty

**Diagnosis:**
```bash
# Check if beat is running
ps aux | grep "celery.*beat"

# Check beat schedule file
ls -la celerybeat-schedule

# Check logs
tail -50 logs/celery-beat.log
```

**Solutions:**
1. **Not running:** `celery -A intelliwiz_config beat --loglevel=info`
2. **Schedule file corrupted:** `rm celerybeat-schedule`, restart beat
3. **Wrong settings module:** Verify `DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.production`

#### Issue 4: High Memory Usage

**Symptoms:**
- Workers consuming >4GB RAM
- OOM errors in logs

**Diagnosis:**
```bash
# Check worker memory
ps aux | grep celery | awk '{print $6, $11}'

# Check model cache size
python manage.py shell
>>> from apps.ml.services.conflict_predictor import ConflictPredictor
>>> import sys
>>> print(f"Cache size: {len(ConflictPredictor._model_cache)}")
```

**Solutions:**
1. **Model cache too large:** Reduce worker concurrency (`-c 2` instead of `-c 4`)
2. **Memory leak:** Restart workers daily via cron
3. **Too many models:** Keep only 3 recent models per type

#### Issue 5: Slow Feature Extraction

**Symptoms:**
- Fraud detection takes >500ms
- Feature extraction logs show >2s

**Diagnosis:**
```python
import time
from apps.ml.features.fraud_features import FraudFeatureExtractor

# Time feature extraction
extractor = FraudFeatureExtractor()
start = time.time()
features = extractor.extract_temporal_features(df)
elapsed = time.time() - start
print(f"Temporal features: {elapsed:.3f}s")
```

**Solutions:**
1. **N+1 queries:** Use `select_related()` in data fetching
2. **Large datasets:** Add indexes on `people_id`, `event_date`
3. **Cache features:** Store computed features in Redis for 1 hour

---

## Model Management

### Training a New Model

**Conflict Predictor:**
```bash
# 1. Extract fresh data
python manage.py extract_conflict_training_data --days-back 90 \
  --output-path media/ml_training_data/conflict_$(date +%Y%m%d).csv

# 2. Train model
python manage.py train_conflict_model \
  --data-path media/ml_training_data/conflict_20251102.csv

# 3. Review metrics
# Output shows: Test ROC-AUC: 0.8234

# 4. Activate if better than current
python manage.py shell
>>> from apps.ml.models.ml_models import ConflictPredictionModel
>>> new_model = ConflictPredictionModel.objects.latest('created_at')
>>> current_model = ConflictPredictionModel.objects.filter(is_active=True).first()
>>> if new_model.test_roc_auc > current_model.test_roc_auc + 0.05:
...     new_model.activate()
...     print("Model activated!")
```

**Fraud Detector:**
```bash
# 1. Train for specific tenant
python manage.py train_fraud_model --tenant-id 1 --months-back 6

# 2. Review metrics
# Output shows: PR-AUC: 0.7234, Precision @ 80% Recall: 0.5456

# 3. Activate
python manage.py shell
>>> from apps.noc.security_intelligence.models import FraudDetectionModel
>>> FraudDetectionModel.objects.filter(tenant_id=1).latest('created_at').activate()
```

### Deactivating a Model

**If model performance degrades:**
```python
from apps.ml.models.ml_models import ConflictPredictionModel

# Deactivate current model
current = ConflictPredictionModel.objects.filter(is_active=True).first()
current.is_active = False
current.save()

# System will fall back to heuristics
# Train new model and activate to restore ML predictions
```

### A/B Testing Models

**Deploy new model to 10% of traffic:**
```python
from apps.ml.models.ml_models import ConflictPredictionModel

# Set traffic percentage (requires A/B test support)
new_model = ConflictPredictionModel.objects.latest('created_at')
new_model.ab_test_traffic_percentage = 10.0
new_model.is_active = True
new_model.save()

# Current model serves 90% traffic
current_model.ab_test_traffic_percentage = 90.0
current_model.save()

# After 1 week, compare accuracy and roll out winner
```

### Cleaning Up Old Models

**Keep only 5 recent models:**
```python
from apps.ml.models.ml_models import ConflictPredictionModel
import os

# Get all models sorted by creation
all_models = ConflictPredictionModel.objects.order_by('-created_at')

# Keep 5 most recent
models_to_delete = all_models[5:]

for model in models_to_delete:
    # Delete model file
    if os.path.exists(model.model_path):
        os.remove(model.model_path)
    # Delete database record
    model.delete()

print(f"Deleted {len(models_to_delete)} old models")
```

---

## Monitoring & Alerts

### Dashboard Access

**ML Training Metrics:**
- **URL:** http://your-domain/admin/ml-training/metrics/
- **Frequency:** Check daily
- **Look for:** Capture rate health, labeling backlog, quality degradation

**Conflict Prediction:**
- **URL:** http://your-domain/admin/ml/conflictpredictionmodel/
- **Frequency:** Check weekly
- **Look for:** Accuracy trends, active model version

**Fraud Detection:**
- **URL:** http://your-domain/admin/noc/frauddetectionmodel/performance-dashboard/
- **Frequency:** Check daily (high impact)
- **Look for:** False positive rate, precision degradation

**Unified Monitoring:**
- **URL:** http://your-domain/admin/monitoring/unified-dashboard/
- **Frequency:** Check daily
- **Look for:** Infrastructure anomalies, ML drift alerts

### Alert Thresholds

**Training Data Capture:**
- **Critical:** Zero examples in 24h → Check OCR service
- **Warning:** <5 examples/day → Review confidence threshold

**Model Accuracy:**
- **Critical:** <60% accuracy → Immediate retraining
- **Warning:** <70% accuracy → Schedule retraining
- **Info:** >80% accuracy → Model performing well

**False Positives:**
- **Critical:** >30% FP rate → Disable alerts, retrain
- **Warning:** >20% FP rate → Tune thresholds
- **Info:** <10% FP rate → Optimal performance

**Infrastructure:**
- **Critical:** CPU >95% for 5 min → Scale up
- **Warning:** Memory >80% → Check for leaks
- **Info:** Normal operations

---

## Troubleshooting Runbook

### Runbook 1: Training Data Not Being Captured

**Step 1: Verify OCR Services Running**
```bash
# Check recent meter readings
python manage.py shell
>>> from apps.activity.models import MeterReading
>>> MeterReading.objects.count()  # Should be > 0
```

**Step 2: Check Confidence Scores**
```python
>>> recent = MeterReading.objects.order_by('-created_at')[:20]
>>> confidences = [r.confidence_score for r in recent if r.confidence_score]
>>> print(f"Min: {min(confidences)}, Max: {max(confidences)}, Avg: {sum(confidences)/len(confidences)}")
```

**Step 3: Verify Integration Hook**
```bash
# Check if import exists
grep -n "from apps.ml_training.integrations import" apps/activity/services/meter_reading_service.py
# Should show line 28

# Check if call exists
grep -n "track_meter_reading_result" apps/activity/services/meter_reading_service.py
# Should show line 127
```

**Step 4: Check Logs**
```bash
# Look for debug messages
grep "Low-confidence meter reading tracked" logs/django.log

# Look for errors
grep -A 5 "Failed to track meter reading" logs/django.log
```

**Resolution Paths:**
- **All confidences >0.7:** Lower threshold or force capture for testing
- **Import missing:** Re-add import (may have been removed)
- **Exceptions in logs:** Fix database connection, permissions, etc.

### Runbook 2: Model Accuracy Degrading

**Step 1: Check Recent Predictions**
```python
from apps.ml.models.ml_models import PredictionLog
from datetime import timedelta
from django.utils import timezone

# Last 7 days
cutoff = timezone.now() - timedelta(days=7)
recent = PredictionLog.objects.filter(
    model_type='conflict_predictor',
    created_at__gte=cutoff,
    actual_conflict_occurred__isnull=False  # Only scored predictions
)

correct = recent.filter(prediction_correct=True).count()
total = recent.count()
accuracy = correct / total if total > 0 else 0.0

print(f"7-day accuracy: {accuracy:.2%} ({correct}/{total})")
```

**Step 2: Analyze Failure Patterns**
```python
# Get incorrect predictions
incorrect = recent.filter(prediction_correct=False)

# Check feature distributions
for pred in incorrect[:10]:
    print(f"Features: {pred.features_json}")
    print(f"Predicted: {pred.predicted_conflict}, Actual: {pred.actual_conflict_occurred}")
```

**Step 3: Retrain Immediately**
```bash
# Force retraining (don't wait for Monday)
python manage.py extract_conflict_training_data --days-back 90
python manage.py train_conflict_model

# Activate new model
python manage.py shell
>>> ConflictPredictionModel.objects.latest('created_at').activate()
```

**Step 4: Review Data Distribution**
```python
# Check if data has shifted (concept drift)
# Compare recent vs historical feature distributions
```

### Runbook 3: Celery Queue Buildup

**Step 1: Check Queue Depth**
```bash
celery -A intelliwiz_config inspect active_queues | grep -A 3 "ml_training\|ai_processing"
```

**Step 2: Identify Slow Tasks**
```bash
# Check task execution times
grep "Task.*succeeded" logs/celery-worker.log | grep -E "ml\.|fraud" | tail -20
```

**Step 3: Scale Workers**
```bash
# Add more workers for bottleneck queue
celery -A intelliwiz_config worker -Q ml_training -c 4 --loglevel=info &

# Or increase concurrency
celery -A intelliwiz_config control pool_grow 2
```

**Step 4: Optimize Slow Tasks**
- Review task code for N+1 queries
- Add database indexes
- Cache intermediate results
- Reduce batch sizes

---

## Performance Tuning

### Prediction Latency Optimization

**Target:** <50ms (p95)

**Techniques:**
1. **Model Caching:**
   - Current: Class-level cache (loaded once per worker)
   - Optimization: Redis cache with 1-hour TTL

2. **Feature Computation:**
   - Current: Calculated on-demand
   - Optimization: Pre-compute and cache in Redis for frequent entities

3. **Batch Predictions:**
   - Use `model.predict_proba(batch)` instead of individual calls
   - Reduces overhead from ~15ms → ~5ms per prediction

### Database Query Optimization

**Check Slow Queries:**
```sql
-- PostgreSQL: Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE query LIKE '%ml_%' OR query LIKE '%fraud%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Add Missing Indexes:**
```python
# If queries are slow, add indexes
from django.db import connection
cursor = connection.cursor()
cursor.execute("""
    CREATE INDEX CONCURRENTLY idx_predictionlog_created_model
    ON ml_prediction_log (created_at, model_type);
""")
```

### Celery Task Optimization

**Reduce Task Overhead:**
```python
# In apps/ml/tasks.py

# Before: Many small database calls
for prediction in predictions:
    prediction.actual_conflict_occurred = check_conflict(prediction)
    prediction.save()  # N queries

# After: Bulk update
prediction_updates = []
for prediction in predictions:
    prediction.actual_conflict_occurred = check_conflict(prediction)
    prediction_updates.append(prediction)

PredictionLog.objects.bulk_update(
    prediction_updates,
    ['actual_conflict_occurred', 'prediction_correct'],
    batch_size=500
)  # 1 query
```

---

## Backup & Recovery

### Model Backups

**Automated Backups (Daily):**
```bash
# Add to cron (daily 4am)
0 4 * * * tar -czf /backups/ml_models_$(date +\%Y\%m\%d).tar.gz /path/to/media/ml_models/
```

**Manual Backup:**
```bash
# Backup all models + metadata
python manage.py dumpdata ml.ConflictPredictionModel ml.PredictionLog \
  noc.FraudDetectionModel > ml_models_backup_$(date +%Y%m%d).json

# Backup model files
tar -czf ml_models_$(date +%Y%m%d).tar.gz media/ml_models/
```

**Restore:**
```bash
# Restore metadata
python manage.py loaddata ml_models_backup_20251102.json

# Restore model files
tar -xzf ml_models_20251102.tar.gz
```

### Database Backups

**Include ML tables in regular PostgreSQL backups:**
```bash
pg_dump -U postgres -d intelliwiz \
  -t ml_training_dataset \
  -t ml_training_example \
  -t ml_prediction_log \
  -t noc_fraud_prediction_log \
  -t monitoring_infrastructure_metric \
  > ml_stack_backup_$(date +%Y%m%d).sql
```

---

## Security Checklist

**Before Production:**
- [ ] Model files not world-readable: `chmod 640 media/ml_models/*.joblib`
- [ ] API endpoints require authentication
- [ ] Tenant isolation tested (cross-tenant access blocked)
- [ ] No sensitive data in logs (PII redacted)
- [ ] joblib used for serialization (not insecure formats)
- [ ] Input validation on all API endpoints
- [ ] SQL injection prevention (Django ORM only, no raw queries)
- [ ] XSS prevention (template auto-escaping enabled)

**Periodic Audits:**
- [ ] Review API access logs for unusual patterns
- [ ] Check model file integrity (hashes)
- [ ] Audit training data for PII leakage
- [ ] Review Celery task permissions
- [ ] Scan for vulnerable dependencies: `pip-audit`

---

## Rollback Procedure

**If ML predictions cause production issues:**

**Step 1: Immediate Mitigation (5 minutes)**
```python
# Deactivate all ML models (fall back to heuristics)
from apps.ml.models.ml_models import ConflictPredictionModel
from apps.noc.security_intelligence.models import FraudDetectionModel

ConflictPredictionModel.objects.update(is_active=False)
FraudDetectionModel.objects.update(is_active=False)

# Clear caches
from apps.ml.services.conflict_predictor import ConflictPredictor
from apps.noc.security_intelligence.ml.predictive_fraud_detector import PredictiveFraudDetector

ConflictPredictor.clear_model_cache()
PredictiveFraudDetector.clear_model_cache()
```

**Step 2: Verify Fallback (2 minutes)**
```bash
# Test predictions still work (using heuristics)
curl -X POST http://localhost:8000/api/v2/predict/conflict/ \
  -H "Authorization: Bearer <token>" \
  -d '{"domain": "voice", "user_id": 1}'

# Check response has model_version='heuristic_v1' or 'fallback'
```

**Step 3: Root Cause Analysis (30 minutes)**
- Review recent prediction logs
- Check model file integrity
- Identify bad predictions
- Analyze feature distributions

**Step 4: Fix & Redeploy (varies)**
- Retrain model with corrected data
- Test in staging
- Gradual rollout (10% → 50% → 100%)

---

## Performance Benchmarks

### Expected Performance (Production)

**Prediction Latency:**
- Conflict: 15ms (p50), 25ms (p95)
- Fraud: 20ms (p50), 35ms (p95)
- Anomaly: N/A (batch processing every 5 min)

**Training Time:**
- Conflict model: 2-3 minutes (10K samples)
- Fraud model: 5-10 minutes (50K samples, XGBoost)
- Drift detector: 3-5 minutes (30 days multivariate data)

**Storage Usage:**
- Models: ~15MB per tenant
- Training data: ~90MB (90-day retention)
- Metrics: ~20MB (30-day retention)
- Total: ~125MB per tenant

**Database Load:**
- Metrics collection: +540 INSERTs/hour
- Prediction logging: +100-500 INSERTs/day (varies)
- Outcome tracking: +50-200 UPDATEs/day

---

## Contact & Escalation

**For Critical Issues:**
1. Deactivate models (rollback to heuristics)
2. Contact ML team lead
3. Create incident ticket
4. Review logs and share with team

**For Questions:**
- Model training: See `docs/plans/2025-11-01-ml-stack-remediation-design.md`
- Feature engineering: See docstrings in `apps/ml/features/fraud_features.py`
- Celery configuration: See `docs/workflows/CELERY_CONFIGURATION_GUIDE.md`

**For Improvements:**
- Submit feature requests via GitHub issues
- Propose new ML features with business justification
- Suggest threshold adjustments based on production data

---

## Quick Reference Commands

**Daily Operations:**
```bash
# Check training data capture (last 24h)
python manage.py shell -c "from apps.ml_training.monitoring import TrainingDataMetrics; print(TrainingDataMetrics.get_capture_rate_metrics(1))"

# Check model accuracy (last 7 days)
python manage.py shell -c "from apps.ml.models.ml_models import PredictionLog; from datetime import timedelta; from django.utils import timezone; recent = PredictionLog.objects.filter(created_at__gte=timezone.now()-timedelta(days=7), actual_conflict_occurred__isnull=False); print(f'{recent.filter(prediction_correct=True).count()}/{recent.count()} correct')"

# Check Celery health
celery -A intelliwiz_config inspect active | wc -l  # Active tasks
celery -A intelliwiz_config inspect stats | grep -A 2 "ml_training"  # Queue stats
```

**Model Management:**
```bash
# Train new conflict model
python manage.py extract_conflict_training_data && python manage.py train_conflict_model

# Train new fraud model
python manage.py train_fraud_model --tenant-id 1

# Activate latest model (in shell)
ConflictPredictionModel.objects.latest('created_at').activate()

# Deactivate all models (emergency rollback)
ConflictPredictionModel.objects.update(is_active=False)
```

**Monitoring:**
```bash
# Check logs for errors
tail -100 logs/celery-worker.log | grep -i error
tail -100 logs/django.log | grep -E "ml|fraud|anomaly" | grep -i error

# Check metrics collection
python manage.py shell -c "from monitoring.models import InfrastructureMetric; print(f'{InfrastructureMetric.objects.count()} metrics collected')"

# Check prediction volume
python manage.py shell -c "from apps.ml.models.ml_models import PredictionLog; from datetime import timedelta; from django.utils import timezone; print(f'{PredictionLog.objects.filter(created_at__gte=timezone.now()-timedelta(hours=24)).count()} predictions today')"
```

---

## Appendix: File Manifest

**Phase 1 (OCR Feedback - 7 files):**
- apps/ml_training/migrations/0001_initial.py
- apps/ml_training/monitoring/training_data_metrics.py
- apps/ml_training/monitoring/__init__.py
- apps/activity/services/meter_reading_service.py (modified)
- apps/activity/services/vehicle_entry_service.py (modified)
- apps/api/v2/views/ml_views.py (modified)
- apps/api/v2/urls.py (modified)

**Phase 2 (Conflict Prediction - 17 files):**
- apps/ml/services/data_extractors/conflict_data_extractor.py
- apps/ml/services/training/conflict_model_trainer.py
- apps/ml/management/commands/extract_conflict_training_data.py
- apps/ml/management/commands/train_conflict_model.py
- apps/ml/services/conflict_predictor.py (modified)
- apps/ml/tasks.py
- apps/ml/admin.py
- Plus migration, docs, validation scripts (10+ files)

**Phase 3 (Fraud Detection - 15 files):**
- apps/ml/features/fraud_features.py
- apps/noc/security_intelligence/ml/fraud_model_trainer.py
- apps/noc/security_intelligence/models/fraud_detection_model.py
- apps/noc/management/commands/train_fraud_model.py
- apps/noc/security_intelligence/ml/predictive_fraud_detector.py (modified)
- apps/noc/admin.py
- Plus migration, templates, docs (9+ files)

**Phase 4 (Anomaly Detection - 16 files):**
- monitoring/collectors/infrastructure_collector.py
- monitoring/services/anomaly_alert_service.py
- monitoring/services/anomaly_feedback_service.py
- monitoring/models.py (modified)
- monitoring/tasks.py
- apps/ml/monitoring/drift_detection.py
- Plus migration, templates, commands (10+ files)

**Testing (11 files):**
- tests/ml/* (8 test files)
- tests/noc/* (2 test files)
- tests/api/v2/* (1 test file)

**Documentation (8 files):**
- docs/features/ML_STACK_COMPLETE.md
- ML_STACK_OPERATOR_GUIDE.md
- ML_STACK_IMPLEMENTATION_PROGRESS.md
- Plus 5 phase-specific implementation guides

**Total:** 74 files created/modified, ~15,000 lines of code

---

**End of Operator Guide**

**Last Updated:** November 2, 2025
**Version:** 1.0
**Status:** Production-Ready
**Next Review:** After 1 month of production operation
