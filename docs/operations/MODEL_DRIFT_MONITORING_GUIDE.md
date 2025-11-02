# Model Drift Monitoring Operator Guide

**Phase 2: Automated Drift Detection & Retraining**
**Version:** 1.0
**Date:** November 2, 2025

---

## Quick Reference

### What is Drift Monitoring?

**Model drift** = ML model performance degrades over time
**Detection** = Automated daily checks (statistical + performance)
**Response** = Alerts → Auto-retraining (if enabled) → Rollback if needed

### Daily Schedule (All Times UTC)

```
1:00 AM - Track conflict prediction outcomes
2:00 AM - Compute daily performance metrics
3:00 AM - Detect statistical drift (KS test)
4:00 AM - Detect performance drift (accuracy drops)
```

### Key Features

✅ **Automatic Detection** - Daily drift checks without manual intervention
✅ **Dual Detection** - Statistical (distribution) + Performance (accuracy)
✅ **Smart Alerts** - Only alerts on significant drift (HIGH/CRITICAL)
✅ **Safe Auto-Retraining** - 5 safeguards + 24h rollback check
✅ **Real-Time Notifications** - NOC dashboard WebSocket alerts

---

## Understanding Drift Types

### 1. Statistical Drift (Distribution Shift)

**What**: Prediction distribution changes vs baseline

**Detection**: Kolmogorov-Smirnov test (p-value < 0.01)

**Example**:
- **Baseline** (30-60d ago): Mean fraud probability = 0.42
- **Recent** (last 7d): Mean fraud probability = 0.61
- **KS p-value**: 0.003 (< 0.01) → **DRIFT DETECTED**

**Interpretation**: Model is predicting higher fraud rates than historical baseline

### 2. Performance Drift (Accuracy Degradation)

**What**: Model accuracy/precision drops over time

**Detection**: Compare recent (7d) vs baseline (30-60d ago) metrics

**Example**:
- **Baseline accuracy**: 87%
- **Recent accuracy**: 72%
- **Drop**: 15% → **HIGH DRIFT**

**Interpretation**: Model is making more mistakes

---

## Drift Severity Levels

| Severity | Statistical (p-value) | Performance (accuracy drop) | Action |
|----------|----------------------|----------------------------|--------|
| **CRITICAL** | < 0.001 | > 20% | Immediate retraining |
| **HIGH** | < 0.01 | 10-20% | Retraining recommended |
| **MEDIUM** | < 0.05 | 5-10% | Monitor closely |
| **NONE** | >= 0.05 | < 5% | Normal variance |

---

## Monitoring Drift Alerts

### NOC Dashboard

Drift alerts appear in real-time via WebSocket:

**Alert Type**: `ML_DRIFT_DETECTED`
**Severities**: MEDIUM, HIGH, CRITICAL
**Metadata**:
- Model type (conflict / fraud)
- Drift type (statistical / performance)
- Metrics (KS stat, accuracy drop, etc.)
- Recommendation

### SQL Monitoring Query

```sql
-- Recent drift alerts (last 7 days)
SELECT
    created_at,
    severity,
    message,
    status,
    metadata->>'drift_report'->>'drift_severity' AS drift_severity,
    metadata->>'recommendation' AS recommendation
FROM noc_alert_event
WHERE alert_type = 'ML_DRIFT_DETECTED'
  AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

---

## Auto-Retraining Safeguards

### 5-Layer Safety System

1. **Feature Flags** - Must be explicitly enabled
2. **Cooldown** - 7 days minimum between retraining
3. **Data Threshold** - 100+ training samples required
4. **Drift Severity** - Only HIGH/CRITICAL triggers retraining
5. **Validation** - New model must meet performance thresholds

### Feature Flag Configuration

```python
# File: intelliwiz_config/settings/ml_config.py

ML_CONFIG = {
    'ENABLE_AUTO_RETRAIN': False,  # Master switch (default OFF)
    'ENABLE_AUTO_RETRAIN_FRAUD': False,  # Fraud models
    'ENABLE_AUTO_RETRAIN_CONFLICT': False,  # Conflict models
    'REQUIRE_MANUAL_APPROVAL_CRITICAL_DRIFT': True,  # Safety override
}
```

**Default**: Auto-retraining **DISABLED** (alerts only)

**To Enable** (gradual rollout):
1. Enable for 1 pilot tenant first
2. Monitor for 2 weeks
3. Expand to all fraud models
4. Enable conflict models after 1 month

---

## Rollback Mechanism

### Automatic Rollback (24h Check)

**When**: 24 hours after new model activation
**Check**: Compare new model accuracy vs previous model
**Rollback If**: Accuracy drops > 5%

**Example**:
```
Day 0, 10:00 AM: Drift detected → retraining triggered
Day 0, 10:30 AM: New model trained + activated
Day 1, 10:30 AM: Rollback check runs
  - New model accuracy: 68%
  - Previous model accuracy: 85%
  - Drop: 17% (> 5% threshold)
  → AUTOMATIC ROLLBACK EXECUTED
```

### Manual Rollback Procedure

If automatic rollback fails, use this emergency procedure:

```bash
# 1. Disable auto-retraining immediately
python manage.py shell
>>> from django.conf import settings
>>> settings.ML_CONFIG['ENABLE_AUTO_RETRAIN'] = False

# 2. Find previous model
python manage.py shell
>>> from apps.noc.security_intelligence.models import FraudDetectionModel
>>> from apps.tenants.models import Tenant
>>> tenant = Tenant.objects.get(schema_name='tenant_name')
>>> previous = FraudDetectionModel.objects.filter(
...     tenant=tenant,
...     is_active=False
... ).order_by('-deactivated_at').first()
>>> previous.activate()  # Reactivates and clears cache
```

---

## Troubleshooting

### Issue 1: No Metrics Being Computed

**Symptoms**: `ModelPerformanceMetrics` table empty

**Possible Causes**:
1. Outcome tracking not populated
2. < 10 predictions with outcomes per day
3. Task not running

**Solution**:
```sql
-- Check if outcomes are populated
SELECT
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE actual_conflict_occurred IS NOT NULL) AS with_outcomes
FROM ml_prediction_log
WHERE created_at >= NOW() - INTERVAL '7 days';

-- If with_outcomes = 0, outcome tracking task not working
-- Check Celery logs: celery -A intelliwiz_config.celery inspect active
```

### Issue 2: False Drift Alerts

**Symptoms**: Drift alerts for stable models

**Possible Causes**:
1. Thresholds too sensitive
2. Insufficient baseline data
3. Normal variance flagged as drift

**Solution**:
Adjust thresholds in `ml_config.py`:
```python
# More conservative thresholds
'STATISTICAL_DRIFT_PVALUE_HIGH': 0.001,  # Was 0.01
'PERFORMANCE_DRIFT_HIGH': 0.15,  # Was 0.10
```

### Issue 3: Auto-Retraining Not Triggering

**Symptoms**: Drift alerts created but no retraining

**Check**:
```python
python manage.py shell
>>> from django.conf import settings
>>> settings.ML_CONFIG['ENABLE_AUTO_RETRAIN']  # Should be True
>>> settings.ML_CONFIG['ENABLE_AUTO_RETRAIN_FRAUD']  # For fraud models
```

If False, auto-retraining is disabled (expected default).

---

## Performance Metrics Queries

### Model Health Dashboard

```sql
-- Last 30 days of model performance
SELECT
    metric_date,
    ROUND(accuracy::numeric, 3) AS accuracy,
    ROUND(precision::numeric, 3) AS precision,
    ROUND(recall::numeric, 3) AS recall,
    total_predictions,
    predictions_with_outcomes,
    ROUND((predictions_with_outcomes::float / total_predictions * 100)::numeric, 1) AS completeness_pct,
    is_degraded
FROM ml_model_performance_metrics
WHERE model_type = 'fraud_detector'
  AND metric_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY metric_date DESC;
```

### Drift Trend Analysis

```sql
-- Accuracy trend (30 days)
SELECT
    metric_date,
    ROUND(accuracy::numeric, 3) AS accuracy,
    ROUND(performance_delta_from_baseline::numeric, 3) AS delta_from_baseline,
    CASE
        WHEN is_degraded THEN 'DEGRADED'
        WHEN accuracy >= 0.85 THEN 'EXCELLENT'
        WHEN accuracy >= 0.75 THEN 'GOOD'
        ELSE 'POOR'
    END AS health_status
FROM ml_model_performance_metrics
WHERE model_type = 'fraud_detector'
  AND metric_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY metric_date DESC;
```

---

## Operational Procedures

### Daily Checks

**Morning Review** (9:00 AM):
1. Check drift alerts from overnight:
   ```sql
   SELECT * FROM noc_alert_event
   WHERE alert_type = 'ML_DRIFT_DETECTED'
     AND created_at >= CURRENT_DATE;
   ```

2. Review metrics from yesterday:
   ```sql
   SELECT * FROM ml_model_performance_metrics
   WHERE metric_date = CURRENT_DATE - 1;
   ```

3. If drift alert exists: Review recommendation, acknowledge alert

### Weekly Review

**Every Monday**:
1. Review 7-day accuracy trends
2. Check if any models are consistently degraded
3. Review auto-retraining history (if enabled)
4. Validate rollback mechanism (check logs)

### Monthly Review

**First Monday of month**:
1. Performance trend analysis (full month)
2. Drift alert frequency (target: < 2 per month)
3. Auto-retraining success rate (if enabled)
4. Rollback events (should be rare: < 1 per quarter)

---

## Feature Flag Rollout Plan

### Phase 2.1: Foundation (Week 1)
- ✅ Metrics collection active
- ✅ Drift detection active
- ✅ Alerts enabled
- ❌ Auto-retraining DISABLED

### Phase 2.2: Pilot (Week 3)
- ✅ Enable for 1 tenant: `AUTO_RETRAIN_ENABLED_TENANTS = [pilot_tenant_id]`
- Monitor for 2 weeks

### Phase 2.3: Fraud Rollout (Week 5)
- ✅ Enable for all fraud models: `ENABLE_AUTO_RETRAIN_FRAUD = True`
- Monitor for 1 month

### Phase 2.4: Full Rollout (Week 9)
- ✅ Enable for conflict models: `ENABLE_AUTO_RETRAIN_CONFLICT = True`
- ✅ Global enable: `ENABLE_AUTO_RETRAIN = True`

---

## Support & Escalation

**Drift Alerts**: NOC team reviews and acknowledges
**Auto-Retraining Issues**: Escalate to ML Engineering team
**Rollback Events**: Immediate escalation to ML Team Lead
**Emergency Disable**: Contact DevOps for feature flag update

**Documentation**: See `PHASE2_IMPLEMENTATION_PLAN.md` for technical details

---

**Last Updated**: November 2, 2025
**Maintainer**: ML Engineering Team
