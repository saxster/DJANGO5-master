"""
Performance Tests for ML Stack

Benchmarks for all ML operations:
- Model prediction latency
- Feature extraction performance
- Model loading times
- Batch prediction throughput

Follows .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
import time
from datetime import timedelta
from django.utils import timezone
from unittest.mock import Mock, patch
import joblib


@pytest.mark.performance
class TestPredictionLatency:
    """Test prediction latency benchmarks."""

    @pytest.mark.slow
    def test_conflict_prediction_latency_p95_under_50ms(self):
        """Test that conflict prediction p95 latency < 50ms."""
        from apps.ml.services.conflict_predictor import ConflictPredictor

        predictor = ConflictPredictor()
        sync_request = {
            'user_id': 1,
            'entity_type': 'schedule',
            'entity_id': 123
        }

        latencies = []

        # Run 100 predictions
        for _ in range(100):
            start = time.perf_counter()
            prediction = predictor.predict_conflict(sync_request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

        # Calculate p95
        latencies.sort()
        p95 = latencies[94]  # 95th percentile

        # p95 should be < 50ms
        assert p95 < 50.0, f"p95 latency {p95:.2f}ms exceeds 50ms threshold"

    @pytest.mark.slow
    @pytest.mark.django_db
    def test_fraud_feature_extraction_latency_1000_samples_under_1s(self):
        """Test that fraud feature extraction for 1000 samples < 1s."""
        from apps.peoples.models import People
        from apps.onboarding.models import Bt
        from apps.ml.features.fraud_features import FraudFeatureExtractor

        person = People.objects.create(
            username='perf_test_user',
            email='perf@example.com'
        )
        site = Bt.objects.create(name='Perf Test Site')

        event = Mock()
        event.punchintime = timezone.now()
        event.datefor = timezone.now().date()
        event.startlat = 37.7749
        event.startlng = -122.4194
        event.peventlogextras = {'distance_in': 0.2, 'verified_in': True}

        start = time.perf_counter()

        # Extract features 1000 times
        for _ in range(1000):
            features = FraudFeatureExtractor.extract_all_features(
                event, person, site
            )

        elapsed = time.perf_counter() - start

        # Should complete in < 1 second
        assert elapsed < 1.0, f"Feature extraction took {elapsed:.2f}s (> 1s)"


@pytest.mark.performance
class TestModelLoadingPerformance:
    """Test model loading performance."""

    @pytest.mark.slow
    def test_model_first_load_under_500ms(self):
        """Test that first model load < 500ms."""
        import tempfile
        import pandas as pd
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        # Create and save a test model
        model = Pipeline([
            ('scaler', StandardScaler()),
            ('classifier', LogisticRegression())
        ])

        # Train on minimal data
        X = pd.DataFrame({
            'concurrent_editors': [0, 1, 2],
            'hours_since_last_sync': [1, 5, 24],
            'user_conflict_rate': [0.0, 0.1, 0.2],
            'entity_edit_frequency': [1, 2, 3]
        })
        y = [0, 0, 1]

        model.fit(X, y)

        # Save to temp file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.joblib', delete=False
        ) as tmp:
            model_path = tmp.name

        joblib.dump(model, model_path)

        # Measure load time
        start = time.perf_counter()
        loaded_model = joblib.load(model_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should load in < 500ms
        assert elapsed_ms < 500.0, (
            f"Model load took {elapsed_ms:.2f}ms (> 500ms)"
        )

        # Cleanup
        import os
        os.remove(model_path)

    @pytest.mark.slow
    def test_cached_model_load_under_5ms(self):
        """Test that cached model load < 5ms."""
        from apps.ml.services.conflict_predictor import ConflictPredictor

        predictor = ConflictPredictor()

        # First prediction (triggers model load)
        predictor.predict_conflict({'user_id': 1})

        # Second prediction (uses cached model)
        start = time.perf_counter()
        predictor.predict_conflict({'user_id': 2})
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Cached prediction should be very fast
        assert elapsed_ms < 5.0, (
            f"Cached prediction took {elapsed_ms:.2f}ms (> 5ms)"
        )


@pytest.mark.performance
class TestBatchPredictionPerformance:
    """Test batch prediction throughput."""

    @pytest.mark.slow
    def test_batch_prediction_1000_samples_under_2s(self):
        """Test that batch prediction for 1000 samples < 2s."""
        from apps.ml.services.conflict_predictor import ConflictPredictor

        predictor = ConflictPredictor()

        # Generate 1000 sync requests
        sync_requests = [
            {
                'user_id': i,
                'entity_type': 'schedule',
                'entity_id': i
            }
            for i in range(1000)
        ]

        start = time.perf_counter()

        # Predict for all requests
        predictions = []
        for request in sync_requests:
            prediction = predictor.predict_conflict(request)
            predictions.append(prediction)

        elapsed = time.perf_counter() - start

        # Should complete in < 2 seconds
        assert elapsed < 2.0, (
            f"Batch prediction took {elapsed:.2f}s (> 2s)"
        )
        assert len(predictions) == 1000


@pytest.mark.performance
class TestDatabaseQueryPerformance:
    """Test database query performance for ML operations."""

    @pytest.mark.slow
    @pytest.mark.django_db
    def test_prediction_log_insert_performance(self):
        """Test that prediction log inserts are fast."""
        from apps.ml.models.ml_models import PredictionLog

        start = time.perf_counter()

        # Insert 100 prediction logs
        for i in range(100):
            PredictionLog.objects.create(
                model_type='conflict_predictor',
                model_version='test_v1',
                entity_type='schedule',
                entity_id=str(i),
                predicted_conflict=False,
                conflict_probability=0.15,
                features_json={'test': True}
            )

        elapsed = time.perf_counter() - start

        # Should complete in < 1 second
        assert elapsed < 1.0, (
            f"100 prediction log inserts took {elapsed:.2f}s (> 1s)"
        )

    @pytest.mark.slow
    @pytest.mark.django_db
    def test_recent_predictions_query_performance(self):
        """Test that querying recent predictions is fast."""
        from apps.ml.models.ml_models import PredictionLog

        # Create 1000 prediction logs
        cutoff = timezone.now() - timedelta(days=7)

        for i in range(1000):
            PredictionLog.objects.create(
                model_type='conflict_predictor',
                model_version='test_v1',
                entity_type='schedule',
                entity_id=str(i),
                predicted_conflict=i % 10 == 0,
                conflict_probability=0.15,
                created_at=cutoff + timedelta(hours=i)
            )

        # Query recent predictions
        start = time.perf_counter()

        recent = PredictionLog.objects.filter(
            model_type='conflict_predictor',
            created_at__gte=cutoff
        ).count()

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should complete in < 100ms
        assert elapsed_ms < 100.0, (
            f"Query took {elapsed_ms:.2f}ms (> 100ms)"
        )
        assert recent == 1000


@pytest.mark.performance
class TestMemoryUsage:
    """Test memory usage for ML operations."""

    @pytest.mark.slow
    def test_feature_extraction_memory_efficiency(self):
        """Test that feature extraction doesn't leak memory."""
        import tracemalloc
        from apps.ml.features.fraud_features import FraudFeatureExtractor

        event = Mock()
        event.punchintime = timezone.now()
        event.datefor = timezone.now().date()
        event.startlat = 37.7749
        event.startlng = -122.4194
        event.peventlogextras = {'distance_in': 0.2}

        person = Mock()
        person.id = 1

        site = Mock()
        site.id = 1
        site.geofence = None

        # Start memory tracking
        tracemalloc.start()

        # Extract features 1000 times
        for _ in range(1000):
            features = FraudFeatureExtractor.extract_all_features(
                event, person, site
            )

        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Peak memory should be < 10 MB
        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 10.0, f"Peak memory {peak_mb:.2f}MB exceeds 10MB"
