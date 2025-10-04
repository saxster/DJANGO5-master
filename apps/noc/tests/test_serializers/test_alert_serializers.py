"""
NOC Alert Serializer Tests.

Tests for alert serializers with PII masking and field validation.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from apps.noc.serializers import (
    NOCAlertEventSerializer,
    NOCAlertEventListSerializer,
    AlertAcknowledgeSerializer,
    BulkAlertActionSerializer,
)


@pytest.mark.django_db
class TestNOCAlertEventListSerializer:
    """Tests for NOCAlertEventListSerializer."""

    def test_serializer_structure(self, sample_alert):
        """Test serializer returns expected fields."""
        serializer = NOCAlertEventListSerializer(sample_alert)
        data = serializer.data

        assert 'id' in data
        assert 'alert_type' in data
        assert 'severity' in data
        assert 'status' in data
        assert 'message' in data
        assert 'client_name' in data

    def test_display_fields(self, sample_alert):
        """Test display fields are included."""
        serializer = NOCAlertEventListSerializer(sample_alert)
        data = serializer.data

        assert 'severity_display' in data
        assert 'status_display' in data

    def test_suppressed_count(self, sample_alert):
        """Test suppressed count is included."""
        sample_alert.suppressed_count = 5
        sample_alert.save()

        serializer = NOCAlertEventListSerializer(sample_alert)
        data = serializer.data

        assert data['suppressed_count'] == 5


@pytest.mark.django_db
class TestNOCAlertEventSerializer:
    """Tests for NOCAlertEventSerializer with PII masking."""

    def test_full_serialization(self, sample_alert, mock_user):
        """Test full alert serialization."""
        serializer = NOCAlertEventSerializer(sample_alert, context={'user': mock_user})
        data = serializer.data

        assert data['id'] == sample_alert.id
        assert data['alert_type'] == sample_alert.alert_type
        assert data['severity'] == sample_alert.severity
        assert data['message'] == sample_alert.message

    def test_pii_masking_without_permission(self, sample_alert_with_assignee, user_without_pii_permission):
        """Test PII fields are masked for users without permission."""
        serializer = NOCAlertEventSerializer(
            sample_alert_with_assignee,
            context={'user': user_without_pii_permission}
        )
        data = serializer.data

        assert '***' in data.get('acknowledged_by_name', '')

    def test_pii_visible_with_permission(self, sample_alert_with_assignee, admin_user):
        """Test PII fields are visible for admin users."""
        serializer = NOCAlertEventSerializer(
            sample_alert_with_assignee,
            context={'user': admin_user}
        )
        data = serializer.data

        assert data.get('acknowledged_by_name') == sample_alert_with_assignee.acknowledged_by.peoplename

    def test_time_to_ack_display(self, sample_alert):
        """Test time_to_ack display field."""
        sample_alert.acknowledged_at = sample_alert.cdtz + timedelta(minutes=15)
        sample_alert.time_to_ack = timedelta(minutes=15)
        sample_alert.save()

        serializer = NOCAlertEventSerializer(sample_alert)
        data = serializer.data

        assert data['time_to_ack_display'] is not None


@pytest.mark.django_db
class TestAlertAcknowledgeSerializer:
    """Tests for AlertAcknowledgeSerializer."""

    def test_valid_data(self):
        """Test serializer validates correct data."""
        data = {'comment': 'Acknowledged by operator'}
        serializer = AlertAcknowledgeSerializer(data=data)

        assert serializer.is_valid()

    def test_optional_comment(self):
        """Test comment field is optional."""
        data = {}
        serializer = AlertAcknowledgeSerializer(data=data)

        assert serializer.is_valid()

    def test_blank_comment_allowed(self):
        """Test blank comment is allowed."""
        data = {'comment': ''}
        serializer = AlertAcknowledgeSerializer(data=data)

        assert serializer.is_valid()


@pytest.mark.django_db
class TestBulkAlertActionSerializer:
    """Tests for BulkAlertActionSerializer."""

    def test_valid_bulk_acknowledge(self):
        """Test valid bulk acknowledge data."""
        data = {
            'alert_ids': [1, 2, 3],
            'action': 'acknowledge',
            'comment': 'Bulk acknowledged'
        }
        serializer = BulkAlertActionSerializer(data=data)

        assert serializer.is_valid()

    def test_alert_ids_required(self):
        """Test alert_ids is required."""
        data = {'action': 'acknowledge'}
        serializer = BulkAlertActionSerializer(data=data)

        assert not serializer.is_valid()
        assert 'alert_ids' in serializer.errors

    def test_action_validation(self):
        """Test action must be from valid choices."""
        data = {
            'alert_ids': [1, 2],
            'action': 'invalid_action'
        }
        serializer = BulkAlertActionSerializer(data=data)

        assert not serializer.is_valid()
        assert 'action' in serializer.errors

    def test_max_alert_limit(self):
        """Test alert_ids has max limit of 100."""
        data = {
            'alert_ids': list(range(101)),
            'action': 'acknowledge'
        }
        serializer = BulkAlertActionSerializer(data=data)

        assert not serializer.is_valid()