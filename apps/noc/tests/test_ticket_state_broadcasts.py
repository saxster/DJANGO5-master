"""
Tests for Ticket State Change Broadcasts.

TASK 10: Gap #13 - Ticket State Change Broadcasts

Tests:
1. Signal handler detects status change
2. Broadcast method sends to correct channels
3. Consumer receives and processes messages

Following CLAUDE.md testing standards.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.y_helpdesk.models import Ticket
from apps.y_helpdesk.signals import track_ticket_status_change, broadcast_ticket_state_change
from apps.noc.services.websocket_service import NOCWebSocketService
from apps.noc.consumers import NOCDashboardConsumer
from apps.peoples.models import People
from apps.onboarding.models import Bt
from apps.tenants.models import Tenant


@pytest.mark.django_db
class TestTicketStatusChangeSignal:
    """Test signal handler for ticket status changes."""

    def test_track_status_on_existing_ticket(self):
        """Test that original status is tracked for existing tickets."""
        # Create a ticket
        tenant = Tenant.objects.first()
        site = Bt.objects.filter(tenant=tenant).first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket.objects.create(
            ticketdesc="Test ticket",
            status='NEW',
            tenant=tenant,
            bu=site,
            cuser=person,
            muser=person
        )

        # Simulate pre_save signal
        ticket.status = 'OPEN'
        track_ticket_status_change(Ticket, ticket)

        # Verify original status was tracked
        assert hasattr(ticket, '_original_status')
        assert ticket._original_status == 'NEW'

    def test_no_tracking_for_new_ticket(self):
        """Test that new tickets don't have original status tracked."""
        tenant = Tenant.objects.first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket(
            ticketdesc="New ticket",
            status='NEW',
            tenant=tenant,
            cuser=person,
            muser=person
        )

        # Simulate pre_save signal for new ticket
        track_ticket_status_change(Ticket, ticket)

        # Verify _original_status is None for new tickets
        assert hasattr(ticket, '_original_status')
        assert ticket._original_status is None

    @patch('apps.y_helpdesk.signals.NOCWebSocketService')
    def test_broadcast_called_on_status_change(self, mock_websocket_service):
        """Test that broadcast is called when ticket status changes."""
        tenant = Tenant.objects.first()
        site = Bt.objects.filter(tenant=tenant).first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket.objects.create(
            ticketdesc="Test ticket",
            status='NEW',
            tenant=tenant,
            bu=site,
            cuser=person,
            muser=person
        )

        # Manually set _original_status to simulate pre_save tracking
        ticket._original_status = 'NEW'
        ticket.status = 'IN_PROGRESS'

        # Simulate post_save signal
        broadcast_ticket_state_change(Ticket, ticket, created=False)

        # Verify broadcast was called
        mock_websocket_service.broadcast_ticket_update.assert_called_once_with(
            ticket, 'NEW'
        )

    @patch('apps.y_helpdesk.signals.NOCWebSocketService')
    def test_no_broadcast_on_creation(self, mock_websocket_service):
        """Test that no broadcast is sent when ticket is created."""
        tenant = Tenant.objects.first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket(
            ticketdesc="New ticket",
            status='NEW',
            tenant=tenant,
            cuser=person,
            muser=person
        )
        ticket._original_status = None

        # Simulate post_save signal for new ticket
        broadcast_ticket_state_change(Ticket, ticket, created=True)

        # Verify broadcast was not called
        mock_websocket_service.broadcast_ticket_update.assert_not_called()

    @patch('apps.y_helpdesk.signals.NOCWebSocketService')
    def test_no_broadcast_when_status_unchanged(self, mock_websocket_service):
        """Test that no broadcast when status doesn't change."""
        tenant = Tenant.objects.first()
        site = Bt.objects.filter(tenant=tenant).first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket.objects.create(
            ticketdesc="Test ticket",
            status='NEW',
            tenant=tenant,
            bu=site,
            cuser=person,
            muser=person
        )

        # Manually set _original_status to same as current
        ticket._original_status = 'NEW'

        # Simulate post_save signal
        broadcast_ticket_state_change(Ticket, ticket, created=False)

        # Verify broadcast was not called
        mock_websocket_service.broadcast_ticket_update.assert_not_called()


@pytest.mark.django_db
class TestTicketBroadcastService:
    """Test NOCWebSocketService.broadcast_ticket_update method."""

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_broadcast_to_tenant_group(self, mock_get_channel_layer):
        """Test that ticket update broadcasts to tenant group."""
        mock_channel_layer = Mock()
        mock_get_channel_layer.return_value = mock_channel_layer

        tenant = Tenant.objects.first()
        site = Bt.objects.filter(tenant=tenant).first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket.objects.create(
            ticketdesc="Test ticket",
            status='IN_PROGRESS',
            tenant=tenant,
            bu=site,
            cuser=person,
            muser=person,
            assignedtopeople=person,
            priority='HIGH'
        )

        # Call broadcast
        NOCWebSocketService.broadcast_ticket_update(ticket, 'NEW')

        # Verify group_send was called
        assert mock_channel_layer.group_send.called
        call_args = mock_channel_layer.group_send.call_args_list

        # Check tenant group broadcast
        tenant_call = call_args[0]
        assert tenant_call[0][0] == f"noc_tenant_{tenant.id}"

        message = tenant_call[0][1]
        assert message['type'] == 'ticket_updated'
        assert message['ticket_id'] == ticket.id
        assert message['old_status'] == 'NEW'
        assert message['new_status'] == 'IN_PROGRESS'
        assert message['priority'] == 'HIGH'

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_broadcast_to_site_group(self, mock_get_channel_layer):
        """Test that ticket update broadcasts to site group when site exists."""
        mock_channel_layer = Mock()
        mock_get_channel_layer.return_value = mock_channel_layer

        tenant = Tenant.objects.first()
        site = Bt.objects.filter(tenant=tenant).first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket.objects.create(
            ticketdesc="Test ticket",
            status='RESOLVED',
            tenant=tenant,
            bu=site,
            cuser=person,
            muser=person
        )

        # Call broadcast
        NOCWebSocketService.broadcast_ticket_update(ticket, 'IN_PROGRESS')

        # Verify both tenant and site broadcasts
        assert mock_channel_layer.group_send.call_count == 2
        call_args = mock_channel_layer.group_send.call_args_list

        # Check site group broadcast
        site_call = call_args[1]
        assert site_call[0][0] == f"noc_site_{site.id}"

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_broadcast_handles_missing_channel_layer(self, mock_get_channel_layer):
        """Test that broadcast handles missing channel layer gracefully."""
        mock_get_channel_layer.return_value = None

        tenant = Tenant.objects.first()
        person = People.objects.filter(tenant=tenant).first()

        ticket = Ticket.objects.create(
            ticketdesc="Test ticket",
            status='CLOSED',
            tenant=tenant,
            cuser=person,
            muser=person
        )

        # Should not raise exception
        NOCWebSocketService.broadcast_ticket_update(ticket, 'RESOLVED')


@pytest.mark.django_db
@pytest.mark.asyncio
class TestTicketConsumerHandler:
    """Test NOCDashboardConsumer.ticket_updated handler."""

    async def test_consumer_receives_ticket_update(self):
        """Test that consumer receives and processes ticket update messages."""
        # Create test data
        tenant = await self._get_tenant()
        site = await self._get_site(tenant)
        person = await self._get_person(tenant)

        ticket = await self._create_ticket(tenant, site, person)

        # Create mock consumer
        consumer = NOCDashboardConsumer()
        consumer.send = MagicMock()

        # Create event data (as would come from channel layer)
        event = {
            'type': 'ticket_updated',
            'ticket_id': ticket.id,
            'ticket_no': ticket.ticketno,
            'old_status': 'NEW',
            'new_status': 'IN_PROGRESS',
            'priority': 'HIGH',
            'assigned_to': person.peoplename,
            'site_id': site.id,
            'site_name': site.buname,
            'description': ticket.ticketdesc,
            'updated_at': timezone.now().isoformat()
        }

        # Call handler
        await consumer.ticket_updated(event)

        # Verify send was called
        assert consumer.send.called
        call_args = consumer.send.call_args[1]
        sent_data = json.loads(call_args['text_data'])

        # Verify message structure
        assert sent_data['type'] == 'ticket_updated'
        assert sent_data['ticket_id'] == ticket.id
        assert sent_data['old_status'] == 'NEW'
        assert sent_data['new_status'] == 'IN_PROGRESS'
        assert sent_data['priority'] == 'HIGH'

    @staticmethod
    async def _get_tenant():
        """Helper to get tenant asynchronously."""
        from asgiref.sync import sync_to_async
        return await sync_to_async(Tenant.objects.first)()

    @staticmethod
    async def _get_site(tenant):
        """Helper to get site asynchronously."""
        from asgiref.sync import sync_to_async
        return await sync_to_async(
            lambda: Bt.objects.filter(tenant=tenant).first()
        )()

    @staticmethod
    async def _get_person(tenant):
        """Helper to get person asynchronously."""
        from asgiref.sync import sync_to_async
        return await sync_to_async(
            lambda: People.objects.filter(tenant=tenant).first()
        )()

    @staticmethod
    async def _create_ticket(tenant, site, person):
        """Helper to create ticket asynchronously."""
        from asgiref.sync import sync_to_async
        return await sync_to_async(Ticket.objects.create)(
            ticketdesc="Test ticket",
            status='IN_PROGRESS',
            tenant=tenant,
            bu=site,
            cuser=person,
            muser=person,
            assignedtopeople=person,
            priority='HIGH'
        )


@pytest.mark.django_db
class TestTicketStatusChangeIntegration:
    """Integration tests for complete ticket status change flow."""

    @patch('apps.noc.services.websocket_service.get_channel_layer')
    def test_end_to_end_status_change_broadcast(self, mock_get_channel_layer):
        """Test complete flow: status change -> signal -> broadcast."""
        mock_channel_layer = Mock()
        mock_get_channel_layer.return_value = mock_channel_layer

        tenant = Tenant.objects.first()
        site = Bt.objects.filter(tenant=tenant).first()
        person = People.objects.filter(tenant=tenant).first()

        # Create ticket
        ticket = Ticket.objects.create(
            ticketdesc="Integration test ticket",
            status='NEW',
            tenant=tenant,
            bu=site,
            cuser=person,
            muser=person
        )

        # Change status (this should trigger signals)
        ticket.status = 'RESOLVED'
        ticket.save()

        # Verify broadcast was called
        assert mock_channel_layer.group_send.called

        # Verify message structure
        call_args = mock_channel_layer.group_send.call_args_list
        tenant_call = call_args[0]
        message = tenant_call[0][1]

        assert message['type'] == 'ticket_updated'
        assert message['ticket_id'] == ticket.id
        assert message['new_status'] == 'RESOLVED'
