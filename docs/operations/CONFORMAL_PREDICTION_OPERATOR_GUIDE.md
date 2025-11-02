# Conformal Prediction Operator Guide

**Phase 1: Confidence Intervals & Uncertainty Quantification**

**Version:** 1.0
**Date:** November 2, 2025
**Audience:** NOC Operators, ML Engineers, System Administrators

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Loading Calibration Data](#loading-calibration-data)
- [Understanding Confidence Intervals](#understanding-confidence-intervals)
- [Confidence-Aware Auto-Escalation](#confidence-aware-auto-escalation)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)
- [Advanced Topics](#advanced-topics)

---

## Overview

### What is Conformal Prediction?

Conformal prediction adds **uncertainty quantification** to ML fraud predictions. Instead of just a point estimate (e.g., "75% fraud probability"), it provides:

- **Lower Bound**: Minimum likely fraud probability
- **Upper Bound**: Maximum likely fraud probability
- **Confidence Interval Width**: How certain the model is
- **Calibration Score**: Quality of the interval

### Why It Matters

**Before Conformal Prediction:**
- ❌ All HIGH/CRITICAL predictions create tickets (some false positives)
- ❌ No way to distinguish confident vs uncertain predictions
- ❌ 75% automation rate

**After Conformal Prediction:**
- ✅ Only high-confidence predictions auto-create tickets
- ✅ Uncertain predictions flagged for human review
- ✅ 85-90% automation rate with fewer false positives
- ✅ Better resource allocation

### Key Benefits

1. **Reduced False Positives** - Wide intervals signal uncertainty → human review
2. **Improved Automation** - Narrow intervals signal confidence → auto-ticket
3. **Transparency** - Operators see model uncertainty explicitly
4. **Guaranteed Coverage** - 90%/95%/99% statistical guarantees

---

## Quick Start

### 1. Check System Status

```bash
# List current calibration sets
python manage.py load_calibration_data --list
```

**Expected Output:**
```
Current Calibration Sets (Cache)
=============================================================

✓ fraud_detector v1.0: 150 samples (created: 2025-11-02T10:30:00)
✓ conflict_predictor v2.0: 200 samples (created: 2025-11-02T09:15:00)
```

### 2. Load Calibration Data (First Time)

```bash
# Load from existing fraud prediction logs (last 30 days)
python manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source fraud_log \
    --days 30
```

**Expected Output:**
```
Loading Calibration Data
=============================================================
Model Type: fraud_detector
Version: 1.0
Source: fraud_log
=============================================================

Found 150 calibration samples from FraudPredictionLog

✓ Successfully stored 150 calibration samples
✓ Cache key: conformal_calib_fraud_detector_1.0
✓ Cache TTL: 1 hour (3600 seconds)

Calibration Statistics:
  Mean Prediction: 0.425
  Mean Actual: 0.380
  Std Dev Prediction: 0.285
  Positive Rate: 38.0%
```

### 3. Verify Conformal Prediction Active

Check recent fraud prediction logs:

```python
from apps.noc.security_intelligence.models import FraudPredictionLog

# Get most recent prediction
recent = FraudPredictionLog.objects.order_by('-predicted_at').first()

print(f"Fraud Probability: {recent.fraud_probability:.2%}")
print(f"Confidence Interval: [{recent.prediction_lower_bound:.3f}, {recent.prediction_upper_bound:.3f}]")
print(f"Interval Width: {recent.confidence_interval_width:.3f}")
print(f"Is Narrow Interval: {recent.is_narrow_interval}")
```

**Expected Output:**
```
Fraud Probability: 75.00%
Confidence Interval: [0.550, 0.850]
Interval Width: 0.300
Is Narrow Interval: False  # Wide interval → alert for human review
```

---

## Loading Calibration Data

### Source 1: Fraud Prediction Logs (Recommended)

Use historical fraud predictions with known outcomes:

```bash
python manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source fraud_log \
    --days 30 \
    --min-samples 50
```

**Requirements:**
- FraudPredictionLog entries with `actual_fraud_detected` field populated
- At least 30-50 samples (more is better)
- Ideally from same model version

### Source 2: General Prediction Logs

For non-fraud models (e.g., conflict predictor):

```bash
python manage.py load_calibration_data \
    --model-type conflict_predictor \
    --version 2.0 \
    --source prediction_log \
    --days 60
```

### Source 3: CSV Import

For manually prepared calibration data:

**CSV Format:**
```csv
prediction,actual
0.75,1
0.25,0
0.60,1
0.40,0
...
```

**Load Command:**
```bash
python manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source csv \
    --file /path/to/calibration.csv
```

### Calibration Best Practices

✅ **DO:**
- Load calibration data from same model version
- Use recent data (last 30-90 days)
- Aim for 100+ calibration samples
- Refresh calibration data monthly
- Monitor calibration quality scores

❌ **DON'T:**
- Mix data from different model versions
- Use outdated data (> 6 months old)
- Load < 30 samples (unreliable intervals)
- Forget to refresh after model retraining

---

## Understanding Confidence Intervals

### Interpreting Intervals

**Example Prediction:**
```
Fraud Probability: 75%
Lower Bound: 0.55
Upper Bound: 0.85
Interval Width: 0.30
Calibration Score: 0.75
Is Narrow Interval: False  # Width >= 0.2
```

**What This Means:**
- Model predicts 75% fraud probability (point estimate)
- True fraud probability likely between 55-85% (90% confidence)
- Width of 0.30 indicates **uncertainty** → human review recommended
- Calibration score of 0.75 is moderate (0-1 scale)

### Narrow vs Wide Intervals

| Characteristic | Narrow Interval | Wide Interval |
|----------------|----------------|---------------|
| **Width** | < 0.2 (e.g., 0.15) | ≥ 0.2 (e.g., 0.35) |
| **Model Certainty** | High | Low |
| **Action** | Auto-create ticket | Alert for human review |
| **Example** | [0.70, 0.85] | [0.40, 0.75] |
| **Automation** | ✅ Eligible | ❌ Not eligible |

### Coverage Levels

The system uses **90% coverage** by default:

- **90% Coverage**: 9 out of 10 predictions will have true value within interval
- **95% Coverage**: 19 out of 20 predictions (wider intervals)
- **99% Coverage**: 99 out of 100 predictions (widest intervals)

**Trade-off:**
- Higher coverage → wider intervals → more human review
- Lower coverage → narrower intervals → more automation (but less reliable)

---

## Confidence-Aware Auto-Escalation

### Decision Logic

```
┌─────────────────────────────────────────────────────────────┐
│                    Fraud Prediction                          │
│                 (with Confidence Interval)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
            ┌──────────▼──────────┐
            │  Risk Level Check   │
            │  HIGH or CRITICAL?  │
            └──────┬───────┬──────┘
                   │       │
              YES  │       │  NO
                   │       │
        ┌──────────▼────┐ │  ┌──────────────┐
        │ Is Narrow      │ │  │ Monitor Only │
        │ Interval?      │ │  │ (No Action)  │
        │ (width < 0.2)  │ │  └──────────────┘
        └──┬─────────┬───┘ │
           │         │     │
      YES  │         │ NO  │
           │         │     │
  ┌────────▼───┐ ┌──▼─────▼──────────┐
  │ Create     │ │ Create Alert for  │
  │ Ticket     │ │ Human Review      │
  │ (Auto)     │ │ (Manual Decision) │
  └────────────┘ └───────────────────┘
```

### Escalation Scenarios

**Scenario 1: High Confidence, High Risk → Auto-Ticket**
```
Fraud Probability: 85%
Risk Level: CRITICAL
Interval: [0.75, 0.92]
Width: 0.17 (narrow)

→ AUTO-CREATE TICKET
   Priority: HIGH
   Assigned To: Site Security Manager
   Source: SYSTEMGENERATED
```

**Scenario 2: Low Confidence, High Risk → Manual Review**
```
Fraud Probability: 85%
Risk Level: CRITICAL
Interval: [0.50, 0.95]
Width: 0.45 (wide)

→ CREATE ALERT ONLY
   Severity: CRITICAL
   Type: ML_FRAUD_PREDICTION
   Action Required: Human review needed (uncertain prediction)
```

**Scenario 3: Medium Risk → Monitor Only**
```
Fraud Probability: 55%
Risk Level: MEDIUM
Interval: [0.40, 0.68]
Width: 0.28

→ NO AUTO-ACTION
   Logged for monitoring
```

### Ticket Metadata

Auto-created tickets include full prediction context:

**Ticket Fields:**
- `subject`: "High-Confidence ML Fraud Prediction: {person_name}"
- `priority`: HIGH
- `workflow_id`: 'ml_fraud_investigation'
- `workflow_data`:
  ```json
  {
    "auto_created": true,
    "created_by": "MLFraudDetector",
    "prediction": {
      "fraud_probability": 0.85,
      "risk_level": "CRITICAL",
      "confidence_interval_width": 0.17,
      "model_version": "1.0",
      "is_narrow_interval": true
    },
    "person_id": 123,
    "features": {...}
  }
  ```

---

## Monitoring & Maintenance

### Daily Checks

**1. Verify Calibration Data Exists:**
```bash
python manage.py load_calibration_data --list
```

**2. Check Automation Rate:**
```sql
-- High/Critical predictions in last 24h
SELECT COUNT(*) as total_high_risk
FROM noc_fraud_prediction_log
WHERE predicted_at >= NOW() - INTERVAL '24 hours'
  AND risk_level IN ('HIGH', 'CRITICAL');

-- Auto-ticketed (narrow intervals)
SELECT COUNT(*) as auto_ticketed
FROM noc_fraud_prediction_log
WHERE predicted_at >= NOW() - INTERVAL '24 hours'
  AND risk_level IN ('HIGH', 'CRITICAL')
  AND confidence_interval_width < 0.2;

-- Automation rate = auto_ticketed / total_high_risk
```

**Target Metrics:**
- Automation rate: 70-90%
- Average interval width: 0.15-0.35
- Calibration score: > 0.70

### Weekly Maintenance

**1. Refresh Calibration Data:**
```bash
# Re-load from last 30 days of predictions
python manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source fraud_log \
    --days 30
```

**2. Review False Positives:**
```sql
-- Narrow-interval predictions that were false positives
SELECT *
FROM noc_fraud_prediction_log
WHERE predicted_at >= NOW() - INTERVAL '7 days'
  AND confidence_interval_width < 0.2
  AND risk_level IN ('HIGH', 'CRITICAL')
  AND actual_fraud_detected = false;
```

**3. Review False Negatives:**
```sql
-- Wide-interval predictions that were actual fraud
SELECT *
FROM noc_fraud_prediction_log
WHERE predicted_at >= NOW() - INTERVAL '7 days'
  AND confidence_interval_width >= 0.2
  AND actual_fraud_detected = true;
```

### Monthly Review

1. **Calibration Quality:** Check calibration scores trending upward
2. **Coverage Validation:** Empirical coverage should be ~90%
3. **Interval Width Distribution:** Should see mix of narrow/wide
4. **Model Performance:** PR-AUC, precision, recall stable

---

## Troubleshooting

### Issue 1: No Confidence Intervals Generated

**Symptoms:**
- `prediction_lower_bound` is NULL
- `confidence_interval_width` is NULL
- Only point predictions available

**Causes & Solutions:**

**Cause 1:** No calibration data loaded
```bash
# Check calibration sets
python manage.py load_calibration_data --list

# If empty, load calibration data
python manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source fraud_log \
    --days 30
```

**Cause 2:** Model version mismatch
```python
# Check prediction log model_version matches calibration
from apps.noc.security_intelligence.models import FraudPredictionLog
recent = FraudPredictionLog.objects.order_by('-predicted_at').first()
print(f"Prediction model version: {recent.model_version}")

# Load calibration for correct version
```

**Cause 3:** Cache expired (1-hour TTL)
```bash
# Re-load calibration data
python manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source fraud_log \
    --days 30
```

### Issue 2: All Intervals are Wide (No Auto-Tickets)

**Symptoms:**
- All `confidence_interval_width` > 0.3
- No auto-ticket creation
- High manual review load

**Causes & Solutions:**

**Cause 1:** Insufficient calibration samples
```bash
# Load more data (increase --days)
python manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source fraud_log \
    --days 90  # Increase from 30 to 90
```

**Cause 2:** High model uncertainty (normal for complex cases)
- Review features for high-variance patterns
- Consider model retraining with more diverse data

**Cause 3:** Calibration data not representative
- Ensure calibration set matches production distribution
- Re-load with more recent data

### Issue 3: Too Many False Positive Tickets

**Symptoms:**
- Narrow intervals creating tickets
- Tickets resolved as "No fraud found"
- Operator fatigue

**Causes & Solutions:**

**Cause 1:** Narrow interval threshold too loose (0.2)
- Adjust threshold in `apps/ml/models/ml_models.py:134`
- Consider stricter threshold (e.g., 0.15)

**Cause 2:** Model needs retraining
- Review precision@recall metrics
- Consider active learning with false positive examples

---

## Advanced Topics

### Adjusting Coverage Levels

Default is 90% coverage. To use 95%:

**Code Change:**
```python
# File: apps/noc/security_intelligence/ml/predictive_fraud_detector.py
# Line 345

interval = ConformalPredictorService.predict_with_intervals(
    point_prediction=fraud_probability,
    model_type='fraud_detector',
    model_version=model_version,
    coverage_level=95  # Change from 90 to 95
)
```

**Trade-off:**
- 95% coverage → wider intervals → less automation
- Use for critical systems requiring higher confidence

### Custom Narrow Interval Threshold

Default threshold is 0.2. To adjust:

**Code Change:**
```python
# File: apps/ml/models/ml_models.py
# Line 134

@property
def is_narrow_interval(self):
    if self.confidence_interval_width is None:
        return False
    return self.confidence_interval_width < 0.15  # Change from 0.2
```

**Impact:**
- Lower threshold (e.g., 0.15) → Stricter automation → fewer tickets
- Higher threshold (e.g., 0.25) → Looser automation → more tickets

### Calibration Refresh Automation

**Create Cron Job:**
```bash
# /etc/cron.d/conformal-calibration
# Refresh calibration data daily at 2 AM
0 2 * * * /path/to/venv/bin/python /path/to/manage.py load_calibration_data \
    --model-type fraud_detector \
    --version 1.0 \
    --source fraud_log \
    --days 30 \
    >> /var/log/conformal_calibration.log 2>&1
```

---

## Appendix: API Reference

### CalibrationDataManager

```python
from apps.ml.services.conformal_predictor import CalibrationDataManager

# Store calibration set
CalibrationDataManager.store_calibration_set(
    model_type='fraud_detector',
    model_version='1.0',
    calibration_predictions=[0.2, 0.5, 0.8, ...],
    calibration_actuals=[0.0, 1.0, 1.0, ...]
)

# Retrieve calibration set
predictions, actuals = CalibrationDataManager.get_calibration_set(
    model_type='fraud_detector',
    model_version='1.0'
)
```

### ConformalPredictorService

```python
from apps.ml.services.conformal_predictor import ConformalPredictorService

# Generate prediction interval
interval = ConformalPredictorService.predict_with_intervals(
    point_prediction=0.75,
    model_type='fraud_detector',
    model_version='1.0',
    coverage_level=90
)

# Check if narrow interval
is_narrow = ConformalPredictorService.is_narrow_interval(
    interval_width=0.15,
    threshold=0.2
)
```

---

## Support

**Questions?** Contact ML Engineering Team

**Issues?** Create ticket in Help Desk with tag `#conformal-prediction`

**Documentation:** `docs/operations/CONFORMAL_PREDICTION_OPERATOR_GUIDE.md`

---

**Last Updated:** November 2, 2025
**Version:** 1.0
**Maintainer:** ML Engineering Team
