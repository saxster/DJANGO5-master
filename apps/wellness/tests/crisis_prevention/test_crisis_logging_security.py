import pytest
import logging
from unittest.mock import Mock
from apps.wellness.services.crisis_prevention_system import CrisisPreventionSystem


@pytest.mark.security
class TestCrisisLoggingSecurity:

    def test_sanitize_risk_factors_removes_stigmatizing_terms(self):
        """Test that risk factor sanitizer removes stigmatizing terms."""
        service = CrisisPreventionSystem()

        risk_factors = [
            {'factor': 'suicidal_ideation', 'severity': 'high', 'category': 'primary'},
            {'factor': 'hopelessness', 'severity': 'high', 'category': 'primary'},
            {'factor': 'severe_depression_indicators', 'severity': 'medium', 'category': 'warning'},
        ]

        sanitized = service._sanitize_risk_factors_for_logging(risk_factors)

        # Should have summary counts, not specific factor names
        assert 'total_factors' in sanitized
        assert sanitized['total_factors'] == 3

        assert 'severity_distribution' in sanitized
        assert sanitized['severity_distribution']['high'] == 2
        assert sanitized['severity_distribution']['medium'] == 1

        assert 'category_distribution' in sanitized
        assert sanitized['category_distribution']['primary'] == 2
        assert sanitized['category_distribution']['warning'] == 1

        # Stigmatizing terms should NOT be in the output
        sanitized_str = str(sanitized)
        assert 'suicidal_ideation' not in sanitized_str
        assert 'hopelessness' not in sanitized_str
        assert 'severe_depression_indicators' not in sanitized_str

    def test_sanitize_handles_empty_risk_factors(self):
        """Test that sanitizer handles empty risk factor list."""
        service = CrisisPreventionSystem()

        sanitized = service._sanitize_risk_factors_for_logging([])

        assert sanitized['total_factors'] == 0
        assert sanitized['severity_distribution'] == {}
        assert sanitized['category_distribution'] == {}

    def test_crisis_team_notification_redacts_user_name(self, caplog):
        """Test crisis team notifications redact user names in notification data."""
        service = CrisisPreventionSystem()

        # Create a mock user
        mock_user = Mock()
        mock_user.id = 123
        mock_user.peoplename = 'John Doe'

        # Create a risk assessment with stigmatizing factors
        risk_assessment = {
            'crisis_risk_score': 0.95,
            'risk_level': 'immediate',
            'active_risk_factors': [
                {'factor': 'suicidal_ideation', 'severity': 'high', 'category': 'primary'},
                {'factor': 'hopelessness', 'severity': 'high', 'category': 'primary'}
            ]
        }

        with caplog.at_level(logging.CRITICAL):
            result = service._notify_crisis_team(mock_user, risk_assessment)

        log_output = caplog.text

        # Detailed factor names should NOT appear in logs
        assert 'suicidal_ideation' not in log_output
        assert 'hopelessness' not in log_output
        assert 'John Doe' not in log_output  # User name should not appear

        # Safe info SHOULD appear
        assert '123' in log_output  # User ID should appear
        assert 'CRISIS' in log_output or 'critical' in log_output.lower()
        assert result['success'] == True

    def test_notification_data_uses_redacted_name(self, caplog):
        """Test that notification data uses '[USER]' instead of real name."""
        service = CrisisPreventionSystem()

        mock_user = Mock()
        mock_user.id = 456
        mock_user.peoplename = 'Jane Smith'

        risk_assessment = {
            'crisis_risk_score': 0.85,
            'risk_level': 'high',
            'active_risk_factors': [
                {'factor': 'hopelessness', 'severity': 'high', 'category': 'primary'},
                {'factor': 'social_withdrawal', 'severity': 'medium', 'category': 'warning'}
            ]
        }

        with caplog.at_level(logging.CRITICAL):
            result = service._notify_crisis_team(mock_user, risk_assessment)

        # Check that notification was created
        assert result['success'] == True
        notification_data = result['notification_data']

        # Should have user_id
        assert notification_data['user_id'] == 456

        # Should have redacted name
        assert notification_data['user_name'] == '[USER]'
        assert 'Jane Smith' not in str(notification_data)

        # Should have safe risk summary, not detailed factors
        assert 'risk_factors_summary' in notification_data
        assert 'hopelessness' not in str(notification_data['risk_factors_summary'])
        assert 'active_risk_factors' not in notification_data  # Old field should not exist

    def test_risk_factors_summary_shows_only_counts(self):
        """Test that risk factors summary contains only counts, no factor names."""
        service = CrisisPreventionSystem()

        risk_factors = [
            {'factor': 'suicidal_ideation', 'severity': 'high', 'category': 'primary'},
            {'factor': 'hopelessness', 'severity': 'high', 'category': 'primary'},
            {'factor': 'self_harm', 'severity': 'high', 'category': 'primary'},
            {'factor': 'social_withdrawal', 'severity': 'medium', 'category': 'warning'},
            {'factor': 'substance_concerns', 'severity': 'medium', 'category': 'warning'},
        ]

        summary = service._sanitize_risk_factors_for_logging(risk_factors)

        # Should only contain counts
        assert summary['total_factors'] == 5
        assert summary['severity_distribution']['high'] == 3
        assert summary['severity_distribution']['medium'] == 2
        assert summary['category_distribution']['primary'] == 3
        assert summary['category_distribution']['warning'] == 2

        # No factor-specific data
        for factor in risk_factors:
            assert factor['factor'] not in str(summary)
