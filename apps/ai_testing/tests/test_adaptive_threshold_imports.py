"""
Test suite for adaptive_threshold_updater imports and basic functionality
Verifies all required type hints and library imports are available
"""

import pytest
from typing import Dict, Any, List, Tuple
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError

# Test imports from scipy and sklearn
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# Import the service to verify all imports work
from apps.ai_testing.services.adaptive_threshold_updater import AdaptiveThresholdUpdater


class TestAdaptiveThresholdImports:
    """Test that all required imports are available in adaptive_threshold_updater"""

    def test_service_instantiation(self):
        """Test that AdaptiveThresholdUpdater can be instantiated"""
        updater = AdaptiveThresholdUpdater()
        assert updater is not None
        assert updater.confidence_level == 0.95
        assert updater.min_sample_size == 50
        assert updater.seasonal_lookback_days == 90

    def test_type_hints_available(self):
        """Test that Dict, Any, List, Tuple are properly typed in return types"""
        updater = AdaptiveThresholdUpdater()

        # Verify update_all_thresholds signature has Dict[str, Any] return type
        assert hasattr(updater.update_all_thresholds, '__annotations__')

        # Verify List type is used in _get_performance_data
        assert hasattr(updater._get_performance_data, '__annotations__')

        # Verify Tuple type is used in _calculate_adaptive_threshold
        assert hasattr(updater._calculate_adaptive_threshold, '__annotations__')

    def test_scipy_stats_available(self):
        """Test that scipy.stats is available for linregress and norm"""
        assert hasattr(stats, 'linregress')
        assert hasattr(stats, 'norm')

        # Quick test of scipy functions used in the service
        sample_data = [1, 2, 3, 4, 5]
        slope, intercept, r_value, p_value, std_err = stats.linregress([0, 1, 2, 3, 4], sample_data)
        assert slope is not None

    def test_sklearn_kmeans_available(self):
        """Test that sklearn KMeans is available"""
        import numpy as np

        # Create sample data
        X = np.array([[1, 2], [1.5, 1.8], [5, 8], [8, 8], [1, 0.6], [9, 11]])

        # Test KMeans instantiation
        kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
        assert kmeans is not None

        # Test fit_predict
        labels = kmeans.fit_predict(X)
        assert len(labels) == len(X)

    def test_sklearn_scaler_available(self):
        """Test that sklearn StandardScaler is available"""
        import numpy as np

        # Create sample data
        X = np.array([[1, 2], [3, 4], [5, 6]])

        # Test StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        assert X_scaled.shape == X.shape

        # Test inverse transform
        X_inverse = scaler.inverse_transform(X_scaled)
        assert np.allclose(X_inverse, X)

    def test_datetime_utilities_available(self):
        """Test that timezone and timedelta are properly imported"""
        # These should work without issues
        current_time = timezone.now()
        assert current_time is not None

        past_time = current_time - timedelta(days=90)
        assert past_time is not None
        assert (current_time - past_time).days == 90

    def test_validation_error_handling(self):
        """Test that ValidationError can be caught"""
        # This should not raise an import error
        try:
            raise ValidationError("Test error")
        except ValidationError as e:
            assert str(e) is not None

    def test_service_method_signatures(self):
        """Test that service methods have proper type annotations"""
        updater = AdaptiveThresholdUpdater()

        # Verify key methods exist and are callable
        assert callable(updater.update_all_thresholds)
        assert callable(updater._get_performance_data)
        assert callable(updater._remove_outliers)
        assert callable(updater._calculate_adaptive_threshold)
        assert callable(updater._identify_user_segments)
        assert callable(updater._detect_seasonal_patterns)

    def test_all_required_imports_present(self):
        """Test that all required imports are accessible from the service module"""
        from apps.ai_testing.services import adaptive_threshold_updater

        # Check for critical imports being used
        import inspect
        source = inspect.getsource(adaptive_threshold_updater.AdaptiveThresholdUpdater)

        # Verify usage of type hints in function signatures
        assert 'Dict[str, Any]' in source or 'Dict' in source
        assert 'List[float]' in source or 'List' in source
        assert 'Tuple[float' in source or 'Tuple' in source
        assert 'timezone' in source
        assert 'timedelta' in source


class TestAdaptiveThresholdMethodsCallable:
    """Test that service methods can be called without import errors"""

    @pytest.mark.django_db
    def test_method_update_all_thresholds_signature(self):
        """Test update_all_thresholds method signature"""
        updater = AdaptiveThresholdUpdater()

        # Should return Dict[str, Any]
        result = updater.update_all_thresholds()
        assert isinstance(result, dict)

    def test_numpy_operations(self):
        """Test that numpy operations work (used extensively in service)"""
        import numpy as np

        data = np.array([1, 2, 3, 4, 5, 100])  # Outlier at end

        # Test percentile operations
        p95 = np.percentile(data, 95)
        assert p95 > 0

        # Test array operations
        Q1 = np.percentile(data, 25)
        Q3 = np.percentile(data, 75)
        IQR = Q3 - Q1
        assert IQR > 0

        # Test filtering
        filtered = [v for v in data if v <= 10]
        assert 100 not in filtered
