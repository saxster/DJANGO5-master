"""
ML Configuration

Feature flags and thresholds for ML drift monitoring and auto-retraining.

Phase 2: Model Drift Monitoring & Auto-Retraining

Usage:
    from django.conf import settings
    if settings.ML_CONFIG['ENABLE_AUTO_RETRAIN']:
        ...

Follows .claude/rules.md:
- Configuration best practices
- Secure defaults (auto-retrain OFF by default)
"""

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

ML_CONFIG = {
    # ========================================================================
    # FEATURE FLAGS
    # ========================================================================

    # Enable drift monitoring tasks (daily metrics, drift detection)
    'ENABLE_DRIFT_MONITORING': True,

    # Enable drift alert creation in NOC
    'ENABLE_DRIFT_ALERTS': True,

    # Enable automatic model retraining (default OFF for safety)
    # Gradual rollout: Enable for pilot tenants first
    'ENABLE_AUTO_RETRAIN': False,

    # Whitelist for gradual auto-retrain rollout (tenant IDs)
    # Empty list = disabled for all tenants
    # [1, 5, 10] = enabled for tenants 1, 5, 10 only
    'AUTO_RETRAIN_ENABLED_TENANTS': [],

    # Enable auto-retraining for fraud models (tenant-scoped)
    # Lower risk than global conflict models
    'ENABLE_AUTO_RETRAIN_FRAUD': False,

    # Enable auto-retraining for conflict models (global)
    # Higher risk - enable after fraud models proven stable
    'ENABLE_AUTO_RETRAIN_CONFLICT': False,

    # Require manual approval for CRITICAL drift (safety override)
    # Even if AUTO_RETRAIN enabled, CRITICAL drift waits for human review
    'REQUIRE_MANUAL_APPROVAL_CRITICAL_DRIFT': True,

    # ========================================================================
    # DRIFT DETECTION THRESHOLDS
    # ========================================================================

    # Statistical Drift (Kolmogorov-Smirnov test p-value thresholds)
    # Lower p-value = higher confidence of distribution shift
    'STATISTICAL_DRIFT_PVALUE_CRITICAL': 0.001,  # 99.9% confidence
    'STATISTICAL_DRIFT_PVALUE_HIGH': 0.01,       # 99% confidence
    'STATISTICAL_DRIFT_PVALUE_MEDIUM': 0.05,     # 95% confidence

    # Performance Drift (accuracy drop percentage thresholds)
    'PERFORMANCE_DRIFT_CRITICAL': 0.20,  # 20%+ accuracy drop = CRITICAL
    'PERFORMANCE_DRIFT_HIGH': 0.10,      # 10-20% accuracy drop = HIGH
    'PERFORMANCE_DRIFT_MEDIUM': 0.05,    # 5-10% accuracy drop = MEDIUM

    # Precision drift threshold (secondary metric)
    'PRECISION_DRIFT_HIGH': 0.15,  # 15%+ precision drop = HIGH

    # Recall drift threshold (secondary metric)
    'RECALL_DRIFT_HIGH': 0.15,  # 15%+ recall drop = HIGH

    # ========================================================================
    # AUTO-RETRAINING SAFEGUARDS
    # ========================================================================

    # Minimum days between retraining attempts (prevents overtraining)
    'RETRAIN_COOLDOWN_DAYS': 7,

    # Minimum training samples required before retraining
    # Prevents retraining with insufficient data
    'RETRAIN_MIN_TRAINING_SAMPLES': 100,

    # Minimum validation samples for model evaluation
    'RETRAIN_MIN_VALIDATION_SAMPLES': 30,

    # Maximum concurrent retraining jobs (prevents resource exhaustion)
    'MAX_CONCURRENT_RETRAIN_JOBS': 2,

    # ========================================================================
    # PERFORMANCE VALIDATION THRESHOLDS
    # ========================================================================

    # Conflict Predictor minimum thresholds (new model must meet these)
    'CONFLICT_MIN_ACCURACY': 0.70,    # 70% accuracy minimum
    'CONFLICT_MIN_PRECISION': 0.60,   # 60% precision minimum
    'CONFLICT_MIN_RECALL': 0.50,      # 50% recall minimum
    'CONFLICT_MIN_ROC_AUC': 0.70,     # 70% ROC-AUC minimum

    # Fraud Detector minimum thresholds (imbalanced dataset)
    'FRAUD_MIN_PR_AUC': 0.70,                    # 70% PR-AUC minimum
    'FRAUD_MIN_PRECISION_AT_80_RECALL': 0.50,    # 50% precision at 80% recall

    # ========================================================================
    # ROLLBACK SETTINGS
    # ========================================================================

    # Hours after activation to check for rollback (24h monitoring)
    'ROLLBACK_CHECK_HOURS': 24,

    # Accuracy drop threshold that triggers automatic rollback
    # If new model accuracy drops > 5% vs previous, rollback
    'ROLLBACK_ACCURACY_DROP_THRESHOLD': 0.05,

    # Precision drop threshold for rollback
    'ROLLBACK_PRECISION_DROP_THRESHOLD': 0.10,

    # Enable automatic rollback (vs manual only)
    'ENABLE_AUTO_ROLLBACK': True,

    # ========================================================================
    # DATA COLLECTION SETTINGS
    # ========================================================================

    # Days of historical data to use for model training
    'TRAINING_DATA_DAYS': 180,  # 6 months

    # Recent days window for drift detection
    'DRIFT_DETECTION_RECENT_DAYS': 7,

    # Baseline window for drift comparison (30-60 days ago)
    'DRIFT_BASELINE_START_DAYS': 30,
    'DRIFT_BASELINE_END_DAYS': 60,

    # Minimum predictions per day to compute metrics
    # Skip metric computation if < 10 predictions with outcomes
    'MIN_DAILY_PREDICTIONS_WITH_OUTCOMES': 10,

    # ========================================================================
    # ALERT SETTINGS
    # ========================================================================

    # Alert deduplication window (hours)
    # Prevents duplicate drift alerts for same model
    'DRIFT_ALERT_DEDUP_HOURS': 24,

    # Auto-escalate CRITICAL drift alerts (minutes)
    'CRITICAL_DRIFT_AUTO_ESCALATE_MINUTES': 60,

    # Notification channels for drift alerts
    'DRIFT_ALERT_CHANNELS': ['noc_dashboard', 'email', 'websocket'],

    # Target team for drift alerts
    'DRIFT_ALERT_TARGET_TEAM': 'ml_engineering',

    # ========================================================================
    # TASK SCHEDULING
    # ========================================================================

    # Task timeout settings (seconds)
    'DAILY_METRICS_TIMEOUT': SECONDS_IN_HOUR,      # 1 hour for all tenants
    'DRIFT_DETECTION_TIMEOUT': 600,     # 10 minutes
    'RETRAINING_TIMEOUT': 1800,         # 30 minutes for XGBoost
    'ROLLBACK_CHECK_TIMEOUT': 300,      # 5 minutes

    # ========================================================================
    # MONITORING & LOGGING
    # ========================================================================

    # Log drift detection results even if no drift detected
    'LOG_ALL_DRIFT_CHECKS': True,

    # Log detailed model performance metrics
    'LOG_DETAILED_METRICS': True,

    # Enable performance monitoring for drift detection tasks
    'MONITOR_DRIFT_TASK_PERFORMANCE': True,
}


# Development environment overrides
ML_CONFIG_DEVELOPMENT = {
    **ML_CONFIG,
    # Enable auto-retrain in dev for testing
    'ENABLE_AUTO_RETRAIN': True,
    'ENABLE_AUTO_RETRAIN_FRAUD': True,
    'ENABLE_AUTO_RETRAIN_CONFLICT': True,
    # Lower thresholds for easier testing
    'RETRAIN_MIN_TRAINING_SAMPLES': 20,
    'RETRAIN_COOLDOWN_DAYS': 1,
}


# Staging environment overrides
ML_CONFIG_STAGING = {
    **ML_CONFIG,
    # Enable auto-retrain in staging for validation
    'ENABLE_AUTO_RETRAIN_FRAUD': True,
    # Keep conflict disabled until fraud proven stable
    'ENABLE_AUTO_RETRAIN_CONFLICT': False,
}


# Production environment (use base ML_CONFIG with explicit enablement)
ML_CONFIG_PRODUCTION = {
    **ML_CONFIG,
    # Production starts with auto-retrain DISABLED
    # Must be explicitly enabled via feature flag rollout
    'ENABLE_AUTO_RETRAIN': False,
    'ENABLE_AUTO_RETRAIN_FRAUD': False,
    'ENABLE_AUTO_RETRAIN_CONFLICT': False,
    # Require manual approval for all CRITICAL drift in production
    'REQUIRE_MANUAL_APPROVAL_CRITICAL_DRIFT': True,
}
