"""
Tests for Webhook Models and Migration (Nov 2025).

Tests:
- WebhookConfiguration model validation
- WebhookEvent many-to-many relationships
- WebhookDeliveryLog audit tracking
- Data migration from TypeAssist
- Backward compatibility
- Query capabilities
"""

import pytest
import uuid
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.integrations.models import (
    WebhookConfiguration,
    WebhookEvent,
    WebhookDeliveryLog
)
from apps.tenants.models import Tenant


class TestWebhookConfigurationModel(TestCase):
    """Test WebhookConfiguration model."""

    def setUp(self):
        """Set up test environment."""
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

    def test_create_webhook_configuration(self):
        """Test creating webhook configuration."""
        webhook = WebhookConfiguration.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://api.example.com/webhook",
            secret="test_secret_123",
            webhook_type="generic"
        )

        assert webhook.webhook_id is not None
        assert webhook.name == "Test Webhook"
        assert webhook.enabled is True  # Default
        assert webhook.retry_count == 3  # Default
        assert webhook.timeout_seconds == 30  # Default

    def test_webhook_encrypted_secret(self):
        """Test webhook secret is encrypted."""
        webhook = WebhookConfiguration.objects.create(
            tenant=self.tenant,
            name="Test",
            url="https://example.com",
            secret="my_secret_key_123",
            webhook_type="generic"
        )

        # Refresh from database
        webhook.refresh_from_db()

        # Secret should be decrypted automatically by encrypted_model_fields
        assert webhook.secret == "my_secret_key_123"

    def test_webhook_type_choices(self):
        """Test webhook type validation."""
        # Valid types
        for wtype in ['generic', 'slack', 'teams', 'discord', 'custom']:
            webhook = WebhookConfiguration.objects.create(
                tenant=self.tenant,
                name=f"Test {wtype}",
                url=f"https://{wtype}.example.com",
                secret="secret",
                webhook_type=wtype
            )
            assert webhook.webhook_type == wtype

    def test_webhook_url_validation(self):
        """Test URL validator enforces valid URLs."""
        # Invalid URL should fail validation
        webhook = WebhookConfiguration(
            tenant=self.tenant,
            name="Invalid URL",
            url="not-a-valid-url",
            secret="secret"
        )

        with pytest.raises(ValidationError):
            webhook.full_clean()

    def test_retry_count_validation(self):
        """Test retry count must be 0-10."""
        # Valid range
        webhook = WebhookConfiguration.objects.create(
            tenant=self.tenant,
            name="Test",
            url="https://example.com",
            secret="secret",
            retry_count=5
        )
        assert webhook.retry_count == 5

        # Invalid: too high
        webhook.retry_count = 20
        with pytest.raises(ValidationError):
            webhook.full_clean()

    def test_is_active_property(self):
        """Test is_active property."""
        webhook = WebhookConfiguration.objects.create(
            tenant=self.tenant,
            name="Test",
            url="https://example.com",
            secret="secret",
            enabled=True
        )
        assert webhook.is_active is True

        # Disabled webhook
        webhook.enabled = False
        webhook.save()
        assert webhook.is_active is False


class TestWebhookEventModel(TestCase):
    """Test WebhookEvent many-to-many model."""

    def setUp(self):
        """Set up test environment."""
        self.tenant = Tenant.objects.create(
            tenantname="Test",
            subdomain_prefix="test"
        )

        self.webhook = WebhookConfiguration.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com",
            secret="secret"
        )

    def test_create_webhook_event(self):
        """Test creating webhook event subscription."""
        event = WebhookEvent.objects.create(
            webhook=self.webhook,
            event_type="ticket.created"
        )

        assert event.event_type == "ticket.created"
        assert event.webhook == self.webhook

    def test_unique_webhook_event_constraint(self):
        """Test webhook cannot subscribe to same event twice."""
        WebhookEvent.objects.create(
            webhook=self.webhook,
            event_type="alert.escalated"
        )

        # Duplicate should fail
        with pytest.raises(IntegrityError):
            WebhookEvent.objects.create(
                webhook=self.webhook,
                event_type="alert.escalated"
            )

    def test_webhook_can_subscribe_to_multiple_events(self):
        """Test webhook can listen to multiple events."""
        events = ['ticket.created', 'ticket.updated', 'alert.escalated']

        for event_type in events:
            WebhookEvent.objects.create(
                webhook=self.webhook,
                event_type=event_type
            )

        assert self.webhook.webhook_events.count() == 3

        # Verify all events registered
        registered_events = list(
            self.webhook.webhook_events.values_list('event_type', flat=True)
        )
        assert set(registered_events) == set(events)

    def test_delete_webhook_cascades_to_events(self):
        """Test deleting webhook deletes associated events."""
        WebhookEvent.objects.create(
            webhook=self.webhook,
            event_type="ticket.created"
        )
        WebhookEvent.objects.create(
            webhook=self.webhook,
            event_type="alert.escalated"
        )

        webhook_id = self.webhook.webhook_id

        # Delete webhook
        self.webhook.delete()

        # Events should be deleted (cascade)
        assert WebhookEvent.objects.filter(webhook_id=webhook_id).count() == 0


class TestWebhookQueryCapabilities(TestCase):
    """
    Test queryability improvements from proper models.

    These queries were IMPOSSIBLE with TypeAssist JSON blobs.
    """

    def setUp(self):
        """Set up test environment."""
        self.tenant1 = Tenant.objects.create(
            tenantname="Tenant 1",
            subdomain_prefix="tenant1"
        )
        self.tenant2 = Tenant.objects.create(
            tenantname="Tenant 2",
            subdomain_prefix="tenant2"
        )

    def test_find_all_slack_webhooks(self):
        """Test query: Find all Slack webhooks."""
        # Create mixed webhook types
        slack1 = WebhookConfiguration.objects.create(
            tenant=self.tenant1,
            name="Slack Operations",
            url="https://hooks.slack.com/services/T123/B456/abc",
            secret="secret1",
            webhook_type="slack"
        )

        generic = WebhookConfiguration.objects.create(
            tenant=self.tenant1,
            name="Generic Webhook",
            url="https://api.example.com/webhook",
            secret="secret2",
            webhook_type="generic"
        )

        slack2 = WebhookConfiguration.objects.create(
            tenant=self.tenant2,
            name="Slack Alerts",
            url="https://hooks.slack.com/services/T789/B012/xyz",
            secret="secret3",
            webhook_type="slack"
        )

        # Query all Slack webhooks
        slack_webhooks = WebhookConfiguration.objects.filter(
            webhook_type='slack',
            enabled=True
        )

        assert slack_webhooks.count() == 2
        assert slack1 in slack_webhooks
        assert slack2 in slack_webhooks
        assert generic not in slack_webhooks

    def test_find_webhooks_for_specific_event(self):
        """Test query: Find all webhooks listening to specific event."""
        # Create webhooks with different event subscriptions
        webhook1 = WebhookConfiguration.objects.create(
            tenant=self.tenant1,
            name="Ticket Webhook",
            url="https://example.com/tickets",
            secret="secret1"
        )
        WebhookEvent.objects.create(
            webhook=webhook1,
            event_type="ticket.created"
        )
        WebhookEvent.objects.create(
            webhook=webhook1,
            event_type="ticket.updated"
        )

        webhook2 = WebhookConfiguration.objects.create(
            tenant=self.tenant1,
            name="Alert Webhook",
            url="https://example.com/alerts",
            secret="secret2"
        )
        WebhookEvent.objects.create(
            webhook=webhook2,
            event_type="alert.escalated"
        )

        webhook3 = WebhookConfiguration.objects.create(
            tenant=self.tenant1,
            name="Multi Webhook",
            url="https://example.com/multi",
            secret="secret3"
        )
        WebhookEvent.objects.create(
            webhook=webhook3,
            event_type="ticket.created"
        )
        WebhookEvent.objects.create(
            webhook=webhook3,
            event_type="alert.escalated"
        )

        # Query: Find all webhooks listening to "ticket.created"
        ticket_webhooks = WebhookConfiguration.objects.filter(
            webhook_events__event_type='ticket.created',
            enabled=True
        ).distinct()

        assert ticket_webhooks.count() == 2
        assert webhook1 in ticket_webhooks
        assert webhook3 in ticket_webhooks
        assert webhook2 not in ticket_webhooks

    def test_find_webhooks_by_tenant_and_type(self):
        """Test query: Find all enabled Slack webhooks for specific tenant."""
        # Tenant 1 webhooks
        slack_t1 = WebhookConfiguration.objects.create(
            tenant=self.tenant1,
            name="Slack T1",
            url="https://slack.com/webhook1",
            secret="secret1",
            webhook_type="slack"
        )

        # Tenant 2 webhooks
        slack_t2 = WebhookConfiguration.objects.create(
            tenant=self.tenant2,
            name="Slack T2",
            url="https://slack.com/webhook2",
            secret="secret2",
            webhook_type="slack"
        )

        teams_t1 = WebhookConfiguration.objects.create(
            tenant=self.tenant1,
            name="Teams T1",
            url="https://office.com/webhook",
            secret="secret3",
            webhook_type="teams"
        )

        # Query: Tenant 1 Slack webhooks
        result = WebhookConfiguration.objects.filter(
            tenant=self.tenant1,
            webhook_type='slack',
            enabled=True
        )

        assert result.count() == 1
        assert slack_t1 in result
        assert slack_t2 not in result
        assert teams_t1 not in result


class TestWebhookDeliveryLog(TestCase):
    """Test webhook delivery audit logging."""

    def setUp(self):
        """Set up test environment."""
        self.tenant = Tenant.objects.create(
            tenantname="Test",
            subdomain_prefix="test"
        )

        self.webhook = WebhookConfiguration.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="secret"
        )

    def test_create_delivery_log(self):
        """Test creating delivery log."""
        log = WebhookDeliveryLog.objects.create(
            tenant=self.tenant,
            webhook=self.webhook,
            event_type="ticket.created",
            http_status_code=200,
            response_time_ms=150,
            success=True,
            attempt_number=1
        )

        assert log.success is True
        assert log.http_status_code == 200
        assert log.response_time_ms == 150

    def test_failed_delivery_log(self):
        """Test failed delivery log with error message."""
        log = WebhookDeliveryLog.objects.create(
            tenant=self.tenant,
            webhook=self.webhook,
            event_type="alert.escalated",
            http_status_code=500,
            response_time_ms=5000,
            success=False,
            error_message="Internal Server Error",
            attempt_number=2,
            retry_after_seconds=300
        )

        assert log.success is False
        assert log.error_message == "Internal Server Error"
        assert log.attempt_number == 2
        assert log.retry_after_seconds == 300

    def test_query_webhook_success_rate(self):
        """Test querying webhook delivery success rate."""
        # Create successful deliveries
        for i in range(8):
            WebhookDeliveryLog.objects.create(
                tenant=self.tenant,
                webhook=self.webhook,
                event_type="test.event",
                success=True,
                http_status_code=200
            )

        # Create failed deliveries
        for i in range(2):
            WebhookDeliveryLog.objects.create(
                tenant=self.tenant,
                webhook=self.webhook,
                event_type="test.event",
                success=False,
                http_status_code=500
            )

        # Query success rate
        total_logs = self.webhook.delivery_logs.count()
        successful_logs = self.webhook.delivery_logs.filter(success=True).count()

        success_rate = (successful_logs / total_logs * 100)

        assert total_logs == 10
        assert successful_logs == 8
        assert success_rate == 80.0


class TestWebhookMigration(TestCase):
    """Test TypeAssist → WebhookConfiguration migration."""

    def setUp(self):
        """Set up test environment."""
        from apps.client_onboarding.models.classification import TypeAssist

        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        # Create TypeAssist with webhook configuration
        self.typeassist = TypeAssist.objects.create(
            tenant=self.tenant,
            tatype="webhook_config",
            other_data={
                'webhooks': [
                    {
                        'id': str(uuid.uuid4()),
                        'name': 'Primary Webhook',
                        'url': 'https://api.example.com/webhook',
                        'events': ['ticket.created', 'alert.escalated'],
                        'secret': 'hmac_secret_123',
                        'enabled': True,
                        'retry_count': 3,
                        'timeout_seconds': 30
                    },
                    {
                        'id': str(uuid.uuid4()),
                        'name': 'Slack Notifications',
                        'url': 'https://hooks.slack.com/services/T123/B456/xyz',
                        'events': ['alert.escalated'],
                        'secret': 'slack_secret',
                        'enabled': True,
                        'retry_count': 2,
                        'timeout_seconds': 15
                    }
                ]
            }
        )

    def test_migration_creates_webhook_models(self):
        """Test migration converts TypeAssist JSON to models."""
        from django.core.management import call_command

        # Run migration
        call_command('migrate_typeassist_webhooks')

        # Verify webhooks created
        webhooks = WebhookConfiguration.objects.filter(tenant=self.tenant)
        assert webhooks.count() == 2

        # Verify first webhook
        webhook1 = webhooks.get(name='Primary Webhook')
        assert webhook1.url == 'https://api.example.com/webhook'
        assert webhook1.secret == 'hmac_secret_123'
        assert webhook1.retry_count == 3
        assert webhook1.timeout_seconds == 30
        assert webhook1.webhook_type == 'generic'

        # Verify events created
        events1 = list(webhook1.webhook_events.values_list('event_type', flat=True))
        assert set(events1) == {'ticket.created', 'alert.escalated'}

        # Verify second webhook
        webhook2 = webhooks.get(name='Slack Notifications')
        assert webhook2.webhook_type == 'slack'  # Auto-detected from URL
        events2 = list(webhook2.webhook_events.values_list('event_type', flat=True))
        assert events2 == ['alert.escalated']

    def test_migration_preserves_typeassist(self):
        """Test migration preserves original TypeAssist data."""
        from django.core.management import call_command

        original_data = self.typeassist.other_data.copy()

        # Run migration
        call_command('migrate_typeassist_webhooks')

        # TypeAssist should still exist
        self.typeassist.refresh_from_db()
        assert self.typeassist.other_data['webhooks'] == original_data['webhooks']

        # Should have migration metadata
        assert 'webhook_migration' in self.typeassist.other_data
        assert 'migrated_at' in self.typeassist.other_data['webhook_migration']

    def test_dry_run_doesnt_create_models(self):
        """Test dry-run mode doesn't create models."""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()

        # Run dry-run
        call_command('migrate_typeassist_webhooks', '--dry-run', stdout=out)

        # No webhooks should be created
        assert WebhookConfiguration.objects.count() == 0
        assert WebhookEvent.objects.count() == 0

        # Output should show what would be migrated
        output = out.getvalue()
        assert 'DRY RUN' in output
        assert 'Primary Webhook' in output

    def test_rollback_deletes_migrated_models(self):
        """Test rollback removes migrated models."""
        from django.core.management import call_command

        # Run migration
        call_command('migrate_typeassist_webhooks')
        assert WebhookConfiguration.objects.count() == 2

        # Run rollback
        call_command('migrate_typeassist_webhooks', '--rollback')

        # All webhooks should be deleted
        assert WebhookConfiguration.objects.count() == 0
        assert WebhookEvent.objects.count() == 0


class TestBackwardCompatibility(TestCase):
    """Test webhook dispatcher works with both old and new storage."""

    def setUp(self):
        """Set up test environment."""
        from apps.client_onboarding.models.classification import TypeAssist

        self.tenant = Tenant.objects.create(
            tenantname="Test",
            subdomain_prefix="test"
        )

        # Create legacy TypeAssist webhook
        self.typeassist = TypeAssist.objects.create(
            tenant=self.tenant,
            tatype="webhook_config",
            other_data={
                'webhooks': [
                    {
                        'id': str(uuid.uuid4()),
                        'name': 'Legacy Webhook',
                        'url': 'https://legacy.example.com/webhook',
                        'events': ['ticket.created'],
                        'secret': 'legacy_secret',
                        'enabled': True,
                        'retry_count': 3,
                        'timeout_seconds': 30
                    }
                ]
            }
        )

        # Create new WebhookConfiguration
        self.webhook = WebhookConfiguration.objects.create(
            tenant=self.tenant,
            name="New Webhook",
            url="https://new.example.com/webhook",
            secret="new_secret"
        )
        WebhookEvent.objects.create(
            webhook=self.webhook,
            event_type="ticket.created"
        )

    def test_dispatcher_prefers_new_models(self):
        """Test dispatcher uses new models when available."""
        from apps.integrations.services.webhook_dispatcher import WebhookDispatcher

        # Get webhooks for ticket.created event
        webhooks = WebhookDispatcher._get_webhook_configs(
            tenant_id=self.tenant.id,
            event_type='ticket.created'
        )

        # Should return new model webhooks first
        assert len(webhooks) == 1
        assert webhooks[0]['name'] == 'New Webhook'
        assert webhooks[0]['source'] == 'webhook_configuration'

    def test_dispatcher_falls_back_to_typeassist(self):
        """Test dispatcher falls back to TypeAssist if models don't exist."""
        # Delete new webhook
        WebhookConfiguration.objects.all().delete()

        from apps.integrations.services.webhook_dispatcher import WebhookDispatcher

        # Should fall back to TypeAssist
        webhooks = WebhookDispatcher._get_webhook_configs(
            tenant_id=self.tenant.id,
            event_type='ticket.created'
        )

        assert len(webhooks) == 1
        assert webhooks[0]['name'] == 'Legacy Webhook'
        assert webhooks[0]['source'] == 'typeassist'
