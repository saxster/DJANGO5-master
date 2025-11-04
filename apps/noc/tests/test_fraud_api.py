"""
Fraud Intelligence API Tests.

Tests for fraud detection REST API endpoints:
- fraud_scores_live_view
- fraud_scores_history_view
- fraud_scores_heatmap_view
- ml_model_performance_view

Covers:
- 4 endpoint tests (one per endpoint)
- Caching behavior
- RBAC (capability checks)
- Performance (<500ms)

Follows .claude/rules.md Rule #9: Specific exceptions.
"""

import pytest
import time
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.tenants.models import Tenant
from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.onboarding.models import Tacode
from apps.noc.security_intelligence.models import (
    FraudPredictionLog,
    FraudDetectionModel
)


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    return Tenant.objects.create(
        domain_url='test-fraud.example.com',
        schema_name='public',
        name='Fraud Test Tenant'
    )


@pytest.fixture
def fraud_user(tenant, db):
    """Create user with fraud view capability."""
    user = People.objects.create_user(
        loginid='frauduser',
        email='fraud@example.com',
        peoplename='Fraud Analyst',
        tenant=tenant
    )
    user.capabilities = {'security:fraud:view': True}
    user.save()
    return user


@pytest.fixture
def user_without_fraud_permission(tenant, db):
    """Create user without fraud view permission."""
    user = People.objects.create_user(
        loginid='nofraud',
        email='nofraud@example.com',
        peoplename='No Fraud User',
        tenant=tenant
    )
    user.capabilities = {}
    user.save()
    return user


@pytest.fixture
def test_site(tenant, db):
    """Create test site."""
    client_tacode = Tacode.objects.get_or_create(
        tacode='CLIENT',
        defaults={'taname': 'Client'}
    )[0]

    client = Bt.objects.create(
        tenant=tenant,
        bucode='FRAUDCLIENT',
        buname='Fraud Test Client',
        identifier=client_tacode
    )

    site = Bt.objects.create(
        tenant=tenant,
        bucode='FRAUDSITE',
        buname='Fraud Test Site',
        parent=client
    )
    return site


@pytest.fixture
def test_person(tenant, test_site, db):
    """Create test person."""
    from apps.peoples.models import PeopleOrganizational

    person = People.objects.create_user(
        loginid='guarduser',
        email='guard@example.com',
        peoplename='Guard User',
        tenant=tenant
    )

    PeopleOrganizational.objects.create(
        people=person,
        bu=test_site,
        tenant=tenant
    )

    return person


@pytest.fixture
def high_risk_predictions(tenant, test_person, test_site, db):
    """Create high-risk fraud predictions."""
    predictions = []
    for i in range(5):
        pred = FraudPredictionLog.objects.create(
            tenant=tenant,
            person=test_person,
            site=test_site,
            prediction_type='ATTENDANCE',
            fraud_probability=0.6 + (i * 0.05),
            risk_level='HIGH' if i < 3 else 'CRITICAL',
            model_confidence=0.85,
            baseline_deviation=0.7,
            anomaly_indicators=['unusual_hours', 'location_mismatch'],
            model_version='v1_test',
            model_type='xgboost'
        )
        predictions.append(pred)
    return predictions


@pytest.fixture
def historical_predictions(tenant, test_person, test_site, db):
    """Create historical predictions over 30 days."""
    predictions = []
    for days_ago in range(30):
        pred_time = timezone.now() - timedelta(days=days_ago)
        pred = FraudPredictionLog.objects.create(
            tenant=tenant,
            person=test_person,
            site=test_site,
            predicted_at=pred_time,
            prediction_type='ATTENDANCE',
            fraud_probability=0.3 + (days_ago * 0.01),
            risk_level='MEDIUM',
            model_confidence=0.80,
            baseline_deviation=0.5,
            anomaly_indicators=[],
            model_version='v1_test',
            model_type='xgboost'
        )
        predictions.append(pred)
    return predictions


@pytest.fixture
def active_fraud_model(tenant, db):
    """Create active fraud detection model."""
    model = FraudDetectionModel.objects.create(
        tenant=tenant,
        model_version='v1_20251102_test',
        model_path='/media/ml_models/test_model.joblib',
        pr_auc=0.75,
        precision_at_80_recall=0.60,
        optimal_threshold=0.45,
        train_samples=1000,
        fraud_samples=50,
        normal_samples=950,
        class_imbalance_ratio=0.05,
        is_active=True,
        activated_at=timezone.now(),
        metadata={},
        xgboost_params={'max_depth': 6, 'learning_rate': 0.1},
        feature_importance={
            'unusual_hours': 0.35,
            'location_deviation': 0.28,
            'frequency_anomaly': 0.22,
            'device_mismatch': 0.15
        }
    )
    return model


@pytest.fixture
def fraud_client(fraud_user):
    """Create API client with fraud capability."""
    client = APIClient()
    client.force_authenticate(user=fraud_user)
    return client


@pytest.fixture
def client_without_permission(user_without_fraud_permission):
    """Create API client without fraud permission."""
    client = APIClient()
    client.force_authenticate(user=user_without_fraud_permission)
    return client


# Test 1: Live Fraud Scores Endpoint
@pytest.mark.django_db
class TestFraudScoresLiveView:
    """Test live fraud scores endpoint."""

    def test_live_scores_returns_high_risk_predictions(
        self, fraud_client, high_risk_predictions
    ):
        """Test that live endpoint returns high-risk predictions."""
        url = '/api/v2/noc/security/fraud-scores/live/'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['total_count'] == 5
        assert len(data['data']['predictions']) == 5

        # Verify predictions are sorted by fraud_probability
        scores = [p['fraud_probability'] for p in data['data']['predictions']]
        assert scores == sorted(scores, reverse=True)

    def test_live_scores_filters_by_min_score(
        self, fraud_client, high_risk_predictions
    ):
        """Test filtering by minimum fraud score."""
        url = '/api/v2/noc/security/fraud-scores/live/?min_score=0.7'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        # Only 3 predictions should have score >= 0.7
        assert data['data']['total_count'] == 3

    def test_live_scores_filters_by_site(
        self, fraud_client, high_risk_predictions, test_site
    ):
        """Test filtering by site."""
        url = f'/api/v2/noc/security/fraud-scores/live/?site_id={test_site.id}'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['data']['total_count'] == 5

        # Verify all predictions are for the test site
        for pred in data['data']['predictions']:
            assert pred['site_id'] == test_site.id

    def test_live_scores_respects_limit(
        self, fraud_client, high_risk_predictions
    ):
        """Test limit parameter."""
        url = '/api/v2/noc/security/fraud-scores/live/?limit=2'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert len(data['data']['predictions']) == 2


# Test 2: Fraud History Endpoint
@pytest.mark.django_db
class TestFraudScoresHistoryView:
    """Test fraud score history endpoint."""

    def test_history_returns_daily_aggregates(
        self, fraud_client, historical_predictions, test_person
    ):
        """Test that history endpoint returns daily aggregated scores."""
        url = f'/api/v2/noc/security/fraud-scores/history/{test_person.id}/'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['person_id'] == test_person.id
        assert len(data['data']['history']) > 0

        # Verify aggregated fields exist
        first_entry = data['data']['history'][0]
        assert 'date' in first_entry
        assert 'avg_fraud_score' in first_entry
        assert 'max_fraud_score' in first_entry
        assert 'prediction_count' in first_entry
        assert 'high_risk_count' in first_entry

    def test_history_respects_days_parameter(
        self, fraud_client, historical_predictions, test_person
    ):
        """Test days parameter for lookback period."""
        url = f'/api/v2/noc/security/fraud-scores/history/{test_person.id}/?days=7'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['data']['days'] == 7
        # Should have at most 7 days of data
        assert len(data['data']['history']) <= 7

    def test_history_returns_404_for_invalid_person(self, fraud_client):
        """Test 404 for non-existent person."""
        url = '/api/v2/noc/security/fraud-scores/history/99999/'

        response = fraud_client.get(url)

        assert response.status_code == 404
        data = response.json()
        assert data['status'] == 'error'
        assert 'not found' in data['message'].lower()


# Test 3: Fraud Heatmap Endpoint
@pytest.mark.django_db
class TestFraudScoresHeatmapView:
    """Test fraud heatmap endpoint."""

    def test_heatmap_returns_site_aggregates(
        self, fraud_client, high_risk_predictions
    ):
        """Test that heatmap returns site-level aggregations."""
        url = '/api/v2/noc/security/fraud-scores/heatmap/'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['total_sites'] >= 1

        # Verify site aggregation structure
        if len(data['data']['sites']) > 0:
            site_data = data['data']['sites'][0]
            assert 'site_id' in site_data
            assert 'site_name' in site_data
            assert 'avg_fraud_score' in site_data
            assert 'max_fraud_score' in site_data
            assert 'total_predictions' in site_data
            assert 'high_risk_count' in site_data
            assert 'critical_risk_count' in site_data
            assert 'risk_percentage' in site_data

    def test_heatmap_filters_by_min_predictions(
        self, fraud_client, high_risk_predictions
    ):
        """Test filtering by minimum predictions per site."""
        url = '/api/v2/noc/security/fraud-scores/heatmap/?min_predictions=10'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        # With only 5 predictions, no sites should match
        assert data['data']['total_sites'] == 0

    def test_heatmap_respects_time_window(
        self, fraud_client, high_risk_predictions
    ):
        """Test time window parameter."""
        url = '/api/v2/noc/security/fraud-scores/heatmap/?hours=1'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['data']['filters']['hours'] == 1


# Test 4: ML Model Performance Endpoint
@pytest.mark.django_db
class TestMLModelPerformanceView:
    """Test ML model performance endpoint."""

    def test_performance_returns_active_model_metrics(
        self, fraud_client, active_fraud_model
    ):
        """Test that performance endpoint returns active model metrics."""
        url = '/api/v2/noc/security/ml-models/performance/'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['has_active_model'] is True

        # Verify model metrics
        model = data['data']['model']
        assert model['model_version'] == 'v1_20251102_test'
        assert model['pr_auc'] == 0.75
        assert model['precision_at_80_recall'] == 0.60
        assert model['optimal_threshold'] == 0.45
        assert model['train_samples'] == 1000
        assert model['fraud_samples'] == 50
        assert model['normal_samples'] == 950
        assert model['is_active'] is True

        # Verify feature importance
        assert 'top_features' in model
        assert len(model['top_features']) > 0

    def test_performance_returns_no_model_message_when_inactive(
        self, fraud_client, tenant
    ):
        """Test response when no active model exists."""
        url = '/api/v2/noc/security/ml-models/performance/'

        response = fraud_client.get(url)

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['data']['has_active_model'] is False
        assert 'No active fraud detection model' in data['data']['message']


# Test 5: Caching Behavior
@pytest.mark.django_db
class TestFraudAPICaching:
    """Test caching behavior across all endpoints."""

    def test_live_scores_uses_cache(
        self, fraud_client, high_risk_predictions
    ):
        """Test that live scores endpoint uses cache."""
        url = '/api/v2/noc/security/fraud-scores/live/'

        # Clear cache before test
        cache.clear()

        # First request - should NOT be cached
        response1 = fraud_client.get(url)
        assert response1.status_code == 200
        assert response1.json()['cached'] is False

        # Second request - should be cached
        response2 = fraud_client.get(url)
        assert response2.status_code == 200
        assert response2.json()['cached'] is True

    def test_model_performance_uses_cache(
        self, fraud_client, active_fraud_model
    ):
        """Test that model performance endpoint uses cache."""
        url = '/api/v2/noc/security/ml-models/performance/'

        # Clear cache before test
        cache.clear()

        # First request
        response1 = fraud_client.get(url)
        assert response1.status_code == 200
        assert response1.json()['cached'] is False

        # Second request
        response2 = fraud_client.get(url)
        assert response2.status_code == 200
        assert response2.json()['cached'] is True

    def test_cache_ttl_is_5_minutes(
        self, fraud_client, high_risk_predictions
    ):
        """Test that cache TTL is set to 5 minutes (300 seconds)."""
        from apps.noc.api.v2.fraud_views import FRAUD_CACHE_TTL

        assert FRAUD_CACHE_TTL == 300


# Test 6: RBAC (Capability Checks)
@pytest.mark.django_db
class TestFraudAPIRBAC:
    """Test RBAC enforcement across all endpoints."""

    def test_live_scores_requires_fraud_view_capability(
        self, client_without_permission, high_risk_predictions
    ):
        """Test that fraud view capability is required."""
        url = '/api/v2/noc/security/fraud-scores/live/'

        response = client_without_permission.get(url)

        # Should be forbidden (403) due to missing capability
        assert response.status_code == 403

    def test_history_requires_fraud_view_capability(
        self, client_without_permission, test_person
    ):
        """Test RBAC for history endpoint."""
        url = f'/api/v2/noc/security/fraud-scores/history/{test_person.id}/'

        response = client_without_permission.get(url)

        assert response.status_code == 403

    def test_heatmap_requires_fraud_view_capability(
        self, client_without_permission
    ):
        """Test RBAC for heatmap endpoint."""
        url = '/api/v2/noc/security/fraud-scores/heatmap/'

        response = client_without_permission.get(url)

        assert response.status_code == 403

    def test_model_performance_requires_fraud_view_capability(
        self, client_without_permission
    ):
        """Test RBAC for model performance endpoint."""
        url = '/api/v2/noc/security/ml-models/performance/'

        response = client_without_permission.get(url)

        assert response.status_code == 403


# Test 7: Performance (<500ms)
@pytest.mark.django_db
class TestFraudAPIPerformance:
    """Test performance requirements (<500ms response time)."""

    def test_live_scores_performance(
        self, fraud_client, high_risk_predictions
    ):
        """Test that live scores endpoint responds in <500ms."""
        url = '/api/v2/noc/security/fraud-scores/live/'

        # Warm up cache
        fraud_client.get(url)

        # Measure response time
        start_time = time.time()
        response = fraud_client.get(url)
        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 500, f"Response took {elapsed_ms:.2f}ms (>500ms)"

    def test_heatmap_performance(
        self, fraud_client, high_risk_predictions
    ):
        """Test that heatmap endpoint responds in <500ms."""
        url = '/api/v2/noc/security/fraud-scores/heatmap/'

        # Warm up cache
        fraud_client.get(url)

        # Measure response time
        start_time = time.time()
        response = fraud_client.get(url)
        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 500, f"Response took {elapsed_ms:.2f}ms (>500ms)"

    def test_model_performance_endpoint_performance(
        self, fraud_client, active_fraud_model
    ):
        """Test that model performance endpoint responds in <500ms."""
        url = '/api/v2/noc/security/ml-models/performance/'

        # Warm up cache
        fraud_client.get(url)

        # Measure response time
        start_time = time.time()
        response = fraud_client.get(url)
        elapsed_ms = (time.time() - start_time) * 1000

        assert response.status_code == 200
        assert elapsed_ms < 500, f"Response took {elapsed_ms:.2f}ms (>500ms)"
