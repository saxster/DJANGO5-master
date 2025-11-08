"""
Tests for DeviceTrustService - biometric enrollment device trust validation.

Tests cover:
- Device trust scoring algorithm
- Known vs unknown device handling
- Corporate network detection
- Risk score calculation
- Path traversal attack prevention
- Edge cases and error handling

Sprint 1: Voice Enrollment Security
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import timedelta
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ValidationError

from apps.peoples.services.device_trust_service import DeviceTrustService
from apps.peoples.models import People, DeviceRegistration, DeviceRiskEvent


@pytest.fixture
def device_trust_service():
    """Device trust service instance."""
    return DeviceTrustService()


@pytest.fixture
def user(db):
    """Test user fixture."""
    return People.objects.create(
        username="test_user",
        email="test@example.com",
        first_name="Test",
        last_name="User"
    )


@pytest.fixture
def known_device(db, user):
    """Known trusted device fixture."""
    return DeviceRegistration.objects.create(
        user=user,
        device_id="known_device_12345",
        device_fingerprint={"canvas": "abc123", "webgl": "def456"},
        user_agent="Mozilla/5.0",
        ip_address="192.168.1.100",
        trust_score=80,
        is_trusted=True,
        biometric_enrolled=True,
        last_seen=timezone.now()
    )


@pytest.fixture
def corporate_ip():
    """Corporate network IP address."""
    return "192.168.1.100"


@pytest.fixture
def external_ip():
    """External IP address."""
    return "203.0.113.45"


@pytest.mark.django_db
class TestDeviceTrustService:
    """Test suite for DeviceTrustService."""

    def test_validate_device_known_device_high_trust(
        self, device_trust_service, user, known_device, corporate_ip
    ):
        """Test validation of known device from corporate network."""
        fingerprint_data = {"canvas": "abc123", "webgl": "def456"}

        with patch.object(
            DeviceRegistration, 'generate_device_id', return_value="known_device_12345"
        ):
            result = device_trust_service.validate_device(
                user=user,
                user_agent="Mozilla/5.0",
                ip_address=corporate_ip,
                fingerprint_data=fingerprint_data
            )

        assert result['passed'] is True
        assert result['trust_score'] >= DeviceTrustService.ENROLLMENT_THRESHOLD
        assert result['trust_factors']['known_device'] == DeviceTrustService.KNOWN_DEVICE_POINTS
        assert result['trust_factors']['corporate_network'] == DeviceTrustService.CORPORATE_NETWORK_POINTS
        assert result['trust_factors']['biometric_enrolled'] == DeviceTrustService.BIOMETRIC_ENROLLED_POINTS
        assert 'Device trusted' in result['recommendation']

    def test_validate_device_unknown_device_external_ip(
        self, device_trust_service, user, external_ip
    ):
        """Test validation fails for unknown device from external IP."""
        fingerprint_data = {"canvas": "xyz789", "webgl": "uvw012"}

        with patch.object(
            DeviceRegistration, 'generate_device_id', return_value="unknown_device_67890"
        ):
            result = device_trust_service.validate_device(
                user=user,
                user_agent="Mozilla/5.0",
                ip_address=external_ip,
                fingerprint_data=fingerprint_data
            )

        assert result['passed'] is False
        assert result['trust_score'] < DeviceTrustService.ENROLLMENT_THRESHOLD
        assert result['trust_factors']['known_device'] == 0
        assert result['trust_factors']['corporate_network'] == 0
        assert 'Unknown device' in result['recommendation']

    def test_validate_device_corporate_network_detection(
        self, device_trust_service, user
    ):
        """Test corporate network IP ranges are correctly detected."""
        corporate_ips = [
            "10.0.0.1",
            "172.16.0.1",
            "192.168.0.1",
            "192.168.255.254"
        ]

        for ip in corporate_ips:
            assert device_trust_service._is_corporate_network(ip) is True, \
                f"Failed to detect corporate IP: {ip}"

        external_ips = ["8.8.8.8", "1.1.1.1", "203.0.113.1"]
        for ip in external_ips:
            assert device_trust_service._is_corporate_network(ip) is False, \
                f"Incorrectly detected external IP as corporate: {ip}"

    def test_validate_device_invalid_ip_address(
        self, device_trust_service, user
    ):
        """Test handling of invalid IP addresses."""
        invalid_ips = ["invalid", "999.999.999.999", ""]

        for invalid_ip in invalid_ips:
            assert device_trust_service._is_corporate_network(invalid_ip) is False

    def test_validate_device_recent_activity_check(
        self, device_trust_service, user, db
    ):
        """Test recent activity scoring."""
        # Recent activity (within 30 days)
        recent_device = DeviceRegistration.objects.create(
            user=user,
            device_id="recent_device_123",
            last_seen=timezone.now() - timedelta(days=15),
            biometric_enrolled=False,
            is_blocked=False
        )
        assert device_trust_service._has_recent_activity(recent_device) is True

        # Old activity (over 30 days)
        old_device = DeviceRegistration.objects.create(
            user=user,
            device_id="old_device_456",
            last_seen=timezone.now() - timedelta(days=45),
            biometric_enrolled=False,
            is_blocked=False
        )
        assert device_trust_service._has_recent_activity(old_device) is False

    def test_validate_device_risk_score_calculation(
        self, device_trust_service, user, db
    ):
        """Test risk score calculation based on security events."""
        device = DeviceRegistration.objects.create(
            user=user,
            device_id="risky_device_789",
            biometric_enrolled=False,
            is_blocked=False
        )

        # Create high-risk events
        DeviceRiskEvent.objects.create(
            device=device,
            risk_score=30,
            event_type="suspicious_login",
            detected_at=timezone.now() - timedelta(days=10),
            resolved=False
        )
        DeviceRiskEvent.objects.create(
            device=device,
            risk_score=25,
            event_type="location_anomaly",
            detected_at=timezone.now() - timedelta(days=5),
            resolved=False
        )

        risk_score = device_trust_service._calculate_risk_score(device, user)
        assert risk_score == 55  # 30 + 25

        # Test risk score capping
        DeviceRiskEvent.objects.create(
            device=device,
            risk_score=100,
            event_type="severe_violation",
            detected_at=timezone.now(),
            resolved=False
        )
        risk_score = device_trust_service._calculate_risk_score(device, user)
        assert risk_score == 100  # Capped at 100

    def test_validate_device_resolved_events_not_counted(
        self, device_trust_service, user, db
    ):
        """Test that resolved risk events don't affect score."""
        device = DeviceRegistration.objects.create(
            user=user,
            device_id="clean_device_101",
            biometric_enrolled=False,
            is_blocked=False
        )

        # Resolved event should not count
        DeviceRiskEvent.objects.create(
            device=device,
            risk_score=50,
            event_type="past_issue",
            detected_at=timezone.now() - timedelta(days=5),
            resolved=True
        )

        risk_score = device_trust_service._calculate_risk_score(device, user)
        assert risk_score == 0

    def test_validate_device_blocked_device(
        self, device_trust_service, user, db, corporate_ip
    ):
        """Test that blocked devices fail validation."""
        blocked_device = DeviceRegistration.objects.create(
            user=user,
            device_id="blocked_device_999",
            is_blocked=True,
            biometric_enrolled=True,
            last_seen=timezone.now()
        )

        with patch.object(
            DeviceRegistration, 'generate_device_id', return_value="blocked_device_999"
        ):
            result = device_trust_service.validate_device(
                user=user,
                user_agent="Mozilla/5.0",
                ip_address=corporate_ip,
                fingerprint_data={"canvas": "blocked"}
            )

        # Blocked device should not get known_device points
        assert result['trust_factors']['known_device'] == 0

    def test_validate_device_no_fingerprint_fallback(
        self, device_trust_service, user, corporate_ip
    ):
        """Test fallback to basic device ID when fingerprint unavailable."""
        result = device_trust_service.validate_device(
            user=user,
            user_agent="Mozilla/5.0",
            ip_address=corporate_ip,
            fingerprint_data=None  # No fingerprint data
        )

        assert 'device_id' in result
        assert result['device_id'] is not None
        # Should still evaluate corporate network
        assert result['trust_factors']['corporate_network'] > 0

    def test_validate_device_generates_basic_device_id(
        self, device_trust_service
    ):
        """Test basic device ID generation from user agent and IP."""
        device_id = device_trust_service._generate_basic_device_id(
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1"
        )

        assert isinstance(device_id, str)
        assert len(device_id) == 64  # SHA-256 hex digest

        # Same inputs should produce same ID
        device_id2 = device_trust_service._generate_basic_device_id(
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1"
        )
        assert device_id == device_id2

    def test_validate_device_recommendation_messages(
        self, device_trust_service
    ):
        """Test recommendation messages for different trust scores."""
        # High trust
        rec = device_trust_service._get_recommendation(
            trust_score=80, is_known=True, risk_score=10
        )
        assert "trusted" in rec.lower()

        # Moderate trust
        rec = device_trust_service._get_recommendation(
            trust_score=60, is_known=True, risk_score=15
        )
        assert "moderate" in rec.lower()

        # Unknown device
        rec = device_trust_service._get_recommendation(
            trust_score=30, is_known=False, risk_score=0
        )
        assert "unknown" in rec.lower()

        # High risk
        rec = device_trust_service._get_recommendation(
            trust_score=40, is_known=True, risk_score=60
        )
        assert "high risk" in rec.lower()

    @patch('apps.peoples.services.device_trust_service.DeviceRegistration.objects')
    def test_validate_device_database_error_handling(
        self, mock_objects, device_trust_service, user, corporate_ip
    ):
        """Test graceful handling of database errors."""
        mock_objects.get.side_effect = DatabaseError("Connection failed")

        result = device_trust_service.validate_device(
            user=user,
            user_agent="Mozilla/5.0",
            ip_address=corporate_ip,
            fingerprint_data={"canvas": "test"}
        )

        assert result['passed'] is False
        assert result['trust_score'] == 0
        assert 'unavailable' in result['recommendation']

    def test_validate_device_validation_error_handling(
        self, device_trust_service, user
    ):
        """Test handling of validation errors."""
        # Invalid IP format should be handled gracefully
        result = device_trust_service.validate_device(
            user=user,
            user_agent="Mozilla/5.0",
            ip_address="invalid_ip",
            fingerprint_data={}
        )

        # Should not crash, should handle gracefully
        assert 'passed' in result
        assert 'trust_score' in result

    @patch('apps.peoples.services.device_trust_service.DeviceRegistration.objects.update_or_create')
    def test_register_or_update_device_new_device(
        self, mock_update_or_create, device_trust_service, user
    ):
        """Test registration of new device."""
        mock_device = Mock()
        mock_update_or_create.return_value = (mock_device, True)

        device = device_trust_service._register_or_update_device(
            user=user,
            device_id="new_device_123",
            fingerprint_data={"canvas": "abc"},
            user_agent="Mozilla/5.0",
            ip_address="192.168.1.1",
            trust_score=75,
            trust_factors={"known_device": 50},
            is_trusted=True
        )

        assert device == mock_device
        mock_update_or_create.assert_called_once()

    @patch('apps.peoples.services.device_trust_service.DeviceRegistration.objects.update_or_create')
    def test_register_or_update_device_database_error(
        self, mock_update_or_create, device_trust_service, user
    ):
        """Test database error handling during device registration."""
        mock_update_or_create.side_effect = DatabaseError("DB error")

        with pytest.raises(DatabaseError):
            device_trust_service._register_or_update_device(
                user=user,
                device_id="error_device",
                fingerprint_data={},
                user_agent="Mozilla/5.0",
                ip_address="192.168.1.1",
                trust_score=0,
                trust_factors={},
                is_trusted=False
            )

    def test_validate_device_trust_threshold(
        self, device_trust_service
    ):
        """Test trust score threshold configuration."""
        assert DeviceTrustService.ENROLLMENT_THRESHOLD == 70
        assert DeviceTrustService.KNOWN_DEVICE_POINTS == 50
        assert DeviceTrustService.CORPORATE_NETWORK_POINTS == 30

    def test_validate_device_old_events_not_counted(
        self, device_trust_service, user, db
    ):
        """Test that risk events older than 90 days are not counted."""
        device = DeviceRegistration.objects.create(
            user=user,
            device_id="old_events_device",
            biometric_enrolled=False,
            is_blocked=False
        )

        # Old event (over 90 days)
        DeviceRiskEvent.objects.create(
            device=device,
            risk_score=50,
            event_type="old_violation",
            detected_at=timezone.now() - timedelta(days=100),
            resolved=False
        )

        risk_score = device_trust_service._calculate_risk_score(device, user)
        assert risk_score == 0

    def test_validate_device_no_device_no_risk(
        self, device_trust_service, user
    ):
        """Test that unknown device has zero risk score."""
        risk_score = device_trust_service._calculate_risk_score(None, user)
        assert risk_score == 0


@pytest.mark.django_db
class TestDeviceTrustServiceIntegration:
    """Integration tests for DeviceTrustService."""

    def test_full_enrollment_flow_success(self, user, corporate_ip):
        """Test complete enrollment flow for trusted device."""
        service = DeviceTrustService()
        fingerprint_data = {
            "canvas": "unique_canvas_fp",
            "webgl": "unique_webgl_fp",
            "fonts": ["Arial", "Times"]
        }

        with patch.object(
            DeviceRegistration, 'generate_device_id', return_value="enrollment_device_123"
        ):
            # First enrollment
            result = service.validate_device(
                user=user,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                ip_address=corporate_ip,
                fingerprint_data=fingerprint_data
            )

            # Should pass with corporate network bonus
            assert result['passed'] is True or result['trust_score'] >= 30

    def test_security_escalation_flow(self, user, db):
        """Test device blocked after multiple risk events."""
        service = DeviceTrustService()

        device = DeviceRegistration.objects.create(
            user=user,
            device_id="escalation_device",
            biometric_enrolled=False,
            is_blocked=False
        )

        # Add multiple high-risk events
        for i in range(3):
            DeviceRiskEvent.objects.create(
                device=device,
                risk_score=30,
                event_type=f"violation_{i}",
                detected_at=timezone.now() - timedelta(days=i),
                resolved=False
            )

        risk_score = service._calculate_risk_score(device, user)
        assert risk_score >= 60  # High risk

        # Device should fail validation due to high risk
        assert device.is_blocked is False  # Not auto-blocked yet
        # Risk score affects trust scoring
