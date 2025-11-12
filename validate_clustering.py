#!/usr/bin/env python
"""
Quick validation script for alert clustering implementation.

Verifies that the clustering service can be imported and basic logic works.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def validate_imports():
    """Validate all required imports."""
    print("✓ Validating imports...")

    try:
        from apps.noc.models.alert_cluster import AlertCluster
        print("  ✓ AlertCluster model imports successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import AlertCluster: {e}")
        return False

    try:
        from apps.noc.services.alert_clustering_service import AlertClusteringService
        print("  ✓ AlertClusteringService imports successfully")
    except ImportError as e:
        print(f"  ✗ Failed to import AlertClusteringService: {e}")
        return False

    try:
        from apps.noc.services.correlation_service import AlertCorrelationService
        print("  ✓ AlertCorrelationService imports successfully (with clustering integration)")
    except ImportError as e:
        print(f"  ✗ Failed to import AlertCorrelationService: {e}")
        return False

    return True


def validate_feature_extraction():
    """Validate feature extraction logic."""
    print("\n✓ Validating feature extraction...")

    from apps.noc.services.alert_clustering_service import AlertClusteringService

    # Mock alert object
    class MockAlert:
        def __init__(self):
            self.alert_type = 'DEVICE_OFFLINE'
            self.entity_type = 'device'
            self.severity = 'HIGH'
            self.correlation_id = None
            self.bu = None
            from django.utils import timezone
            self.cdtz = timezone.now()

    mock_alert = MockAlert()
    features = AlertClusteringService._extract_features(mock_alert)

    required_features = [
        'alert_type', 'alert_type_encoded', 'entity_type', 'entity_type_encoded',
        'site_id', 'severity_score', 'hour_of_day', 'day_of_week',
        'correlation_id_hash', 'time_since_last_alert', 'affected_entity_count'
    ]

    for feature in required_features:
        if feature not in features:
            print(f"  ✗ Missing feature: {feature}")
            return False

    print(f"  ✓ All {len(required_features)} features extracted successfully")
    print(f"  ✓ Sample features: severity_score={features['severity_score']}, hour={features['hour_of_day']}")
    return True


def validate_similarity_calculation():
    """Validate similarity calculation."""
    print("\n✓ Validating similarity calculation...")

    from apps.noc.services.alert_clustering_service import AlertClusteringService

    # Identical features
    features1 = {
        'alert_type_encoded': 1,
        'entity_type_encoded': 100,
        'site_id': 5,
        'severity_score': 4,
        'hour_of_day': 14,
        'day_of_week': 2,
        'correlation_id_hash': 500,
        'time_since_last_alert': 0,
        'affected_entity_count': 1,
    }
    features2 = features1.copy()

    similarity = AlertClusteringService._calculate_similarity(features1, features2)

    if abs(similarity - 1.0) < 0.001:
        print(f"  ✓ Identical features similarity: {similarity:.3f} (expected: 1.0)")
    else:
        print(f"  ✗ Identical features similarity: {similarity:.3f} (expected: 1.0)")
        return False

    # Different features
    features3 = {
        'alert_type_encoded': 10,
        'entity_type_encoded': 500,
        'site_id': 99,
        'severity_score': 1,
        'hour_of_day': 3,
        'day_of_week': 6,
        'correlation_id_hash': 999,
        'time_since_last_alert': 7200,
        'affected_entity_count': 50,
    }

    similarity_diff = AlertClusteringService._calculate_similarity(features1, features3)

    if similarity_diff < 0.5:
        print(f"  ✓ Different features similarity: {similarity_diff:.3f} (expected: <0.5)")
    else:
        print(f"  ✗ Different features similarity: {similarity_diff:.3f} (expected: <0.5)")
        return False

    return True


def validate_severity_scoring():
    """Validate severity scoring."""
    print("\n✓ Validating severity scoring...")

    from apps.noc.services.alert_clustering_service import AlertClusteringService

    expected_scores = {
        'INFO': 1,
        'LOW': 2,
        'MEDIUM': 3,
        'HIGH': 4,
        'CRITICAL': 5,
    }

    for severity, expected_score in expected_scores.items():
        actual_score = AlertClusteringService._severity_score(severity)
        if actual_score != expected_score:
            print(f"  ✗ {severity}: got {actual_score}, expected {expected_score}")
            return False

    print(f"  ✓ All {len(expected_scores)} severity scores correct")
    return True


def validate_model_structure():
    """Validate AlertCluster model structure."""
    print("\n✓ Validating AlertCluster model structure...")

    from apps.noc.models.alert_cluster import AlertCluster

    required_fields = [
        'cluster_id', 'cluster_signature', 'primary_alert', 'related_alerts',
        'cluster_confidence', 'cluster_method', 'feature_vector',
        'combined_severity', 'affected_sites', 'affected_people',
        'alert_types_in_cluster', 'first_alert_at', 'last_alert_at',
        'alert_count', 'is_active', 'suppressed_alert_count'
    ]

    model_fields = [f.name for f in AlertCluster._meta.get_fields()]

    for field in required_fields:
        if field not in model_fields:
            print(f"  ✗ Missing field: {field}")
            return False

    print(f"  ✓ All {len(required_fields)} required fields present")
    return True


def main():
    """Run all validations."""
    print("=" * 60)
    print("Alert Clustering Implementation Validation")
    print("=" * 60)

    all_passed = True

    # Run validations
    all_passed &= validate_imports()
    all_passed &= validate_model_structure()
    all_passed &= validate_feature_extraction()
    all_passed &= validate_similarity_calculation()
    all_passed &= validate_severity_scoring()

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL VALIDATIONS PASSED")
        print("=" * 60)
        print("\nImplementation Summary:")
        print("  • AlertCluster model created with 16 fields")
        print("  • AlertClusteringService with cosine similarity")
        print("  • 9-feature extraction from alerts")
        print("  • Integration with AlertCorrelationService")
        print("  • Comprehensive test suite (unit + integration)")
        print("\nNext Steps:")
        print("  1. Create migration: python manage.py makemigrations noc")
        print("  2. Apply migration: python manage.py migrate")
        print("  3. Run tests: pytest apps/noc/tests/test_services/test_alert_clustering_service.py")
        return 0
    else:
        print("❌ SOME VALIDATIONS FAILED")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
