"""
Unit tests for Twilio webhook signature validation.

Tests the @validate_twilio_request decorator to ensure:
1. Valid Twilio signatures are accepted
2. Invalid signatures are rejected with 403
3. Missing signatures are rejected with 403
4. Configuration errors are handled gracefully

Security: These tests verify CVSS 7.5 vulnerability mitigation (Rule #3).
"""

import pytest
from django.test import RequestFactory, override_settings
from django.http import HttpResponse
from unittest.mock import patch, MagicMock
from apps.noc.security_intelligence.ivr.decorators import validate_twilio_request


@pytest.fixture
def request_factory():
    """Request factory for creating test requests."""
    return RequestFactory()


@pytest.fixture
def sample_view():
    """Sample view function for testing decorator."""
    def view(request):
        return HttpResponse('Success', status=200)
    return view


@pytest.mark.django_db
class TestTwilioSignatureValidation:
    """Test suite for Twilio signature validation decorator."""

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    def test_valid_signature_allows_request(self, mock_validator_class, request_factory, sample_view):
        """Test that valid Twilio signature allows request through."""
        # Setup mock validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_validator_class.return_value = mock_validator

        # Create request with valid signature
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={'CallSid': 'CA123', 'CallStatus': 'completed'},
            HTTP_X_TWILIO_SIGNATURE='valid_signature_hash'
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 200
        assert response.content == b'Success'
        mock_validator.validate.assert_called_once()

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    def test_invalid_signature_rejects_request(self, mock_validator_class, request_factory, sample_view):
        """Test that invalid Twilio signature rejects request with 403."""
        # Setup mock validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = False  # Invalid signature
        mock_validator_class.return_value = mock_validator

        # Create request with invalid signature
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={'CallSid': 'CA123'},
            HTTP_X_TWILIO_SIGNATURE='invalid_signature'
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 403
        assert b'Invalid signature' in response.content

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    def test_missing_signature_rejects_request(self, request_factory, sample_view):
        """Test that missing X-Twilio-Signature header rejects request with 403."""
        # Create request WITHOUT signature header
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={'CallSid': 'CA123'}
            # No HTTP_X_TWILIO_SIGNATURE header
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 403
        assert b'Missing signature' in response.content

    @override_settings(TWILIO_AUTH_TOKEN='')
    def test_missing_auth_token_returns_500(self, request_factory, sample_view):
        """Test that missing TWILIO_AUTH_TOKEN in settings returns 500."""
        # Create request with signature
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={'CallSid': 'CA123'},
            HTTP_X_TWILIO_SIGNATURE='some_signature'
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 500
        assert b'configuration error' in response.content.lower()

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    def test_twilio_sdk_not_installed_returns_500(self, mock_validator_class, request_factory, sample_view):
        """Test that missing twilio package returns 500."""
        # Simulate ImportError for twilio package
        mock_validator_class.side_effect = ImportError("No module named 'twilio'")

        # Create request
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={'CallSid': 'CA123'},
            HTTP_X_TWILIO_SIGNATURE='some_signature'
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 500
        assert b'configuration error' in response.content.lower()

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    def test_validation_error_returns_403(self, mock_validator_class, request_factory, sample_view):
        """Test that validation errors return 403."""
        # Setup mock validator to raise ValueError
        mock_validator = MagicMock()
        mock_validator.validate.side_effect = ValueError("Invalid signature format")
        mock_validator_class.return_value = mock_validator

        # Create request
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={'CallSid': 'CA123'},
            HTTP_X_TWILIO_SIGNATURE='malformed_signature'
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 403

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    def test_get_request_validation(self, mock_validator_class, request_factory, sample_view):
        """Test that GET requests are also validated (rare for webhooks)."""
        # Setup mock validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_validator_class.return_value = mock_validator

        # Create GET request
        request = request_factory.get(
            '/api/ivr/twilio/status',
            HTTP_X_TWILIO_SIGNATURE='valid_signature'
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 200
        # Verify validator was called with empty dict for GET
        mock_validator.validate.assert_called_once()
        call_args = mock_validator.validate.call_args
        assert call_args[0][1] == {}  # Second argument should be empty dict

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    def test_signature_validation_with_special_characters(self, mock_validator_class, request_factory, sample_view):
        """Test signature validation with special characters in POST data."""
        # Setup mock validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_validator_class.return_value = mock_validator

        # Create request with special characters
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={
                'CallSid': 'CA123',
                'From': '+1 (555) 123-4567',
                'RecordingUrl': 'https://api.twilio.com/recording.mp3?Expires=12345&Signature=abc123'
            },
            HTTP_X_TWILIO_SIGNATURE='valid_signature_hash'
        )

        # Apply decorator and call view
        decorated_view = validate_twilio_request(sample_view)
        response = decorated_view(request)

        # Assert
        assert response.status_code == 200
        mock_validator.validate.assert_called_once()


@pytest.mark.integration
@pytest.mark.django_db
class TestTwilioWebhookIntegration:
    """Integration tests for Twilio webhook views with signature validation."""

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    @patch('apps.noc.security_intelligence.ivr.services.AIIVRService')
    def test_twilio_status_callback_with_valid_signature(self, mock_service, mock_validator_class, request_factory):
        """Integration test: twilio_status_callback view with valid signature."""
        from apps.noc.security_intelligence.ivr.views.webhook_views import twilio_status_callback

        # Setup mock validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_validator_class.return_value = mock_validator

        # Setup mock service
        mock_service.process_call_callback.return_value = None

        # Create request
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={
                'CallSid': 'CA1234567890abcdef',
                'CallStatus': 'completed',
                'Duration': '45'
            },
            HTTP_X_TWILIO_SIGNATURE='valid_signature_hash'
        )

        # Call view
        response = twilio_status_callback(request)

        # Assert
        assert response.status_code == 200
        assert b'<Response>' in response.content  # TwiML response

    @override_settings(TWILIO_AUTH_TOKEN='test_auth_token')
    @patch('apps.noc.security_intelligence.ivr.decorators.RequestValidator')
    def test_twilio_status_callback_with_invalid_signature(self, mock_validator_class, request_factory):
        """Integration test: twilio_status_callback rejects invalid signature."""
        from apps.noc.security_intelligence.ivr.views.webhook_views import twilio_status_callback

        # Setup mock validator for INVALID signature
        mock_validator = MagicMock()
        mock_validator.validate.return_value = False
        mock_validator_class.return_value = mock_validator

        # Create request
        request = request_factory.post(
            '/api/ivr/twilio/status',
            data={'CallSid': 'CA123', 'CallStatus': 'completed'},
            HTTP_X_TWILIO_SIGNATURE='invalid_signature'
        )

        # Call view
        response = twilio_status_callback(request)

        # Assert - should be rejected before reaching view logic
        assert response.status_code == 403
        assert b'Invalid signature' in response.content
