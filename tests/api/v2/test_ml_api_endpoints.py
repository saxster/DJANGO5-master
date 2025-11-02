"""
Tests for ML API Endpoints

Tests REST API endpoints for:
- OCR corrections submission
- Conflict prediction
- Fraud detection
- Active learning task management

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Type-Safe API Contracts compliance
"""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status


@pytest.mark.django_db
class TestOCRCorrectionAPI:
    """Test OCR correction API endpoints."""

    def test_submit_ocr_correction_success(self):
        """Test successful OCR correction submission."""
        from apps.peoples.models import People
        from apps.ml_training.models import TrainingExample

        # Create user
        user = People.objects.create_user(
            username='test_user',
            email='test@example.com',
            password='testpass123'
        )

        # Create training example
        example = TrainingExample.objects.create(
            example_type='METER_READING',
            entity_id='METER_001',
            extracted_value='12345',
            confidence_score=0.65,
            uncertainty_score=0.35
        )

        # Authenticate
        client = APIClient()
        client.force_authenticate(user=user)

        # Submit correction
        url = reverse('api:v2:ml-training:submit-correction')
        data = {
            'example_id': example.id,
            'corrected_value': '12346'
        }

        response = client.post(url, data, format='json')

        # Should succeed
        assert response.status_code == status.HTTP_200_OK

        # Verify example updated
        example.refresh_from_db()
        assert example.ground_truth_value == '12346'
        assert example.is_correction is True

    def test_submit_ocr_correction_unauthenticated(self):
        """Test that unauthenticated requests are rejected."""
        client = APIClient()

        url = reverse('api:v2:ml-training:submit-correction')
        data = {'example_id': 1, 'corrected_value': '12345'}

        response = client.post(url, data, format='json')

        # Should return 401 Unauthorized
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_submit_ocr_correction_validation_error(self):
        """Test validation errors are returned."""
        from apps.peoples.models import People

        user = People.objects.create_user(
            username='test_user2',
            email='test2@example.com',
            password='testpass123'
        )

        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse('api:v2:ml-training:submit-correction')

        # Missing required fields
        data = {}

        response = client.post(url, data, format='json')

        # Should return 400 Bad Request
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'example_id' in response.data or 'error' in response.data

    def test_submit_ocr_correction_nonexistent_example(self):
        """Test correction for nonexistent example."""
        from apps.peoples.models import People

        user = People.objects.create_user(
            username='test_user3',
            email='test3@example.com',
            password='testpass123'
        )

        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse('api:v2:ml-training:submit-correction')
        data = {
            'example_id': 99999,  # Nonexistent
            'corrected_value': '12345'
        }

        response = client.post(url, data, format='json')

        # Should return 404 Not Found
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestConflictPredictionAPI:
    """Test conflict prediction API endpoints."""

    def test_predict_conflict_success(self):
        """Test successful conflict prediction."""
        from apps.peoples.models import People

        user = People.objects.create_user(
            username='predict_user',
            email='predict@example.com',
            password='testpass123'
        )

        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse('api:v2:ml:predict-conflict')
        data = {
            'entity_type': 'schedule',
            'entity_id': 123,
            'user_id': user.id
        }

        response = client.post(url, data, format='json')

        # Should succeed
        assert response.status_code == status.HTTP_200_OK

        # Verify response format
        assert 'probability' in response.data
        assert 'risk_level' in response.data
        assert 'recommendation' in response.data
        assert 'model_version' in response.data

        # Verify probability range
        assert 0.0 <= response.data['probability'] <= 1.0

        # Verify risk level
        assert response.data['risk_level'] in ['low', 'medium', 'high']

    def test_predict_conflict_creates_prediction_log(self):
        """Test that prediction creates PredictionLog record."""
        from apps.peoples.models import People
        from apps.ml.models.ml_models import PredictionLog

        user = People.objects.create_user(
            username='log_user',
            email='log@example.com',
            password='testpass123'
        )

        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse('api:v2:ml:predict-conflict')
        data = {
            'entity_type': 'schedule',
            'entity_id': 456,
            'user_id': user.id
        }

        response = client.post(url, data, format='json')

        # Verify log created
        log = PredictionLog.objects.filter(
            model_type='conflict_predictor',
            entity_id='456'
        ).first()

        assert log is not None
        assert log.conflict_probability == response.data['probability']

    def test_predict_conflict_validation_error(self):
        """Test validation errors in conflict prediction."""
        from apps.peoples.models import People

        user = People.objects.create_user(
            username='validation_user',
            email='validation@example.com',
            password='testpass123'
        )

        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse('api:v2:ml:predict-conflict')

        # Missing required fields
        data = {}

        response = client.post(url, data, format='json')

        # Should return 400 Bad Request
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestTenantIsolation:
    """Test tenant isolation in ML APIs."""

    def test_ocr_correction_tenant_isolation(self):
        """Test that users can only correct examples in their tenant."""
        from apps.peoples.models import People
        from apps.tenants.models import Tenant
        from apps.ml_training.models import TrainingExample

        # Create two tenants
        tenant1 = Tenant.objects.create(
            schema_name='tenant1',
            name='Tenant 1'
        )
        tenant2 = Tenant.objects.create(
            schema_name='tenant2',
            name='Tenant 2'
        )

        # Create users in different tenants
        user1 = People.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            tenant=tenant1
        )

        # Create example in tenant2
        example = TrainingExample.objects.create(
            example_type='METER_READING',
            entity_id='METER_002',
            extracted_value='11111',
            tenant=tenant2
        )

        # User1 tries to correct example from tenant2
        client = APIClient()
        client.force_authenticate(user=user1)

        url = reverse('api:v2:ml-training:submit-correction')
        data = {
            'example_id': example.id,
            'corrected_value': '22222'
        }

        response = client.post(url, data, format='json')

        # Should be denied (403 Forbidden or 404 Not Found)
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]

        # Example should not be modified
        example.refresh_from_db()
        assert example.ground_truth_value is None

    def test_prediction_log_tenant_isolation(self):
        """Test that prediction logs are tenant-isolated."""
        from apps.peoples.models import People
        from apps.tenants.models import Tenant
        from apps.ml.models.ml_models import PredictionLog

        tenant1 = Tenant.objects.create(
            schema_name='tenant3',
            name='Tenant 3'
        )
        tenant2 = Tenant.objects.create(
            schema_name='tenant4',
            name='Tenant 4'
        )

        user1 = People.objects.create_user(
            username='user3',
            email='user3@example.com',
            password='testpass123',
            tenant=tenant1
        )

        # Create prediction log in tenant2
        log = PredictionLog.objects.create(
            model_type='conflict_predictor',
            model_version='v1',
            entity_type='schedule',
            entity_id='789',
            predicted_conflict=False,
            conflict_probability=0.2,
            tenant=tenant2
        )

        # User1 should not be able to see tenant2's logs
        # This would be tested in a list/detail view
        # For now, verify log has tenant
        assert log.tenant == tenant2


@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting for ML APIs (if implemented)."""

    def test_prediction_api_rate_limiting(self):
        """Test that prediction API has rate limiting."""
        # Placeholder for rate limiting tests
        # Would test excessive requests return 429 Too Many Requests
        pass


@pytest.mark.django_db
class TestAPIResponseFormat:
    """Test API response format compliance."""

    def test_conflict_prediction_response_format(self):
        """Test that conflict prediction response matches API contract."""
        from apps.peoples.models import People

        user = People.objects.create_user(
            username='format_user',
            email='format@example.com',
            password='testpass123'
        )

        client = APIClient()
        client.force_authenticate(user=user)

        url = reverse('api:v2:ml:predict-conflict')
        data = {
            'entity_type': 'schedule',
            'entity_id': 999,
            'user_id': user.id
        }

        response = client.post(url, data, format='json')

        # Verify all required fields present
        required_fields = [
            'probability',
            'risk_level',
            'recommendation',
            'model_version',
            'features_used'
        ]

        for field in required_fields:
            assert field in response.data, f"Missing field: {field}"

        # Verify field types
        assert isinstance(response.data['probability'], (int, float))
        assert isinstance(response.data['risk_level'], str)
        assert isinstance(response.data['recommendation'], str)
        assert isinstance(response.data['model_version'], str)
        assert isinstance(response.data['features_used'], dict)


# ========== URL PLACEHOLDERS ==========
# These URLs need to be implemented in actual URL configuration

# Example URL patterns (add to intelliwiz_config/urls_optimized.py):
"""
from apps.api.v2.views.ml_views import (
    SubmitOCRCorrectionView,
    PredictConflictView
)

urlpatterns = [
    path(
        'api/v2/ml-training/corrections/',
        SubmitOCRCorrectionView.as_view(),
        name='api:v2:ml-training:submit-correction'
    ),
    path(
        'api/v2/ml/predict/conflict/',
        PredictConflictView.as_view(),
        name='api:v2:ml:predict-conflict'
    ),
]
"""
