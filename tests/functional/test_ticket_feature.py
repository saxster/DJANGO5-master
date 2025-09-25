#!/usr/bin/env python
"""
Test script for Ticket feature in YOUTILITY5
Tests ticket creation, update, and history tracking
"""

import os
import sys
import django
import json
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from apps.y_helpdesk.models import Ticket
from apps.peoples.models import People, Pgroup
from apps.activity.models.location_model import Location
from apps.activity.models.asset_model import Asset
from apps.onboarding.models import Bt, TypeAssist
from apps.tenants.models import Tenant
from django.db import transaction
from apps.core.utils_new import db_utils
from django.utils import timezone


def create_test_data():
    """Create necessary test data for ticket testing"""
    print("\n=== Creating Test Data ===")
    
    # Ensure tenant exists
    tenant, _ = Tenant.objects.get_or_create(
        id=1,
        defaults={'tenantname': 'TEST', 'subdomain_prefix': 'test'}
    )
    print(f"✓ Tenant: {tenant.tenantname}")
    
    # Create test user (people)
    test_user, _ = People.objects.get_or_create(
        id=5,
        defaults={
            'peoplename': 'Test User',
            'email': 'test@example.com',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Test User: {test_user.peoplename}")
    
    # Create assigned user
    assigned_user, _ = People.objects.get_or_create(
        id=1,
        defaults={
            'peoplename': 'Admin User',
            'email': 'admin@example.com',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Assigned User: {assigned_user.peoplename}")
    
    # Create test group
    test_group, _ = Pgroup.objects.get_or_create(
        id=1,
        defaults={
            'groupname': 'Support Team',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Test Group: {test_group.groupname}")
    
    # Create test location
    test_location, _ = Location.objects.get_or_create(
        id=1,
        defaults={
            'locname': 'Main Office',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Test Location: {test_location.locname}")
    
    # Create test asset
    test_asset, _ = Asset.objects.get_or_create(
        id=563,
        defaults={
            'assetname': 'Test Equipment',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Test Asset: {test_asset.assetname}")
    
    # Create business units
    bu, _ = Bt.objects.get_or_create(
        id=5,
        defaults={
            'buname': 'IT Department',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Business Unit: {bu.buname}")
    
    client, _ = Bt.objects.get_or_create(
        id=4,
        defaults={
            'buname': 'Client Corp',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Client: {client.buname}")
    
    # Create ticket category
    ticket_category, _ = TypeAssist.objects.get_or_create(
        id=2,
        defaults={
            'taname': 'Hardware Issue',
            'tenant_id': 1,
            'cuser_id': 1,
            'muser_id': 1
        }
    )
    print(f"✓ Ticket Category: {ticket_category.taname}")
    
    return {
        'tenant': tenant,
        'user': test_user,
        'assigned_user': assigned_user,
        'group': test_group,
        'location': test_location,
        'asset': test_asset,
        'bu': bu,
        'client': client,
        'category': ticket_category
    }


def test_ticket_creation(test_data):
    """Test creating a new ticket"""
    print("\n=== Testing Ticket Creation ===")
    
    try:
        with transaction.atomic():
            ticket = Ticket.objects.create(
                ticketdesc="Test ticket for hardware issue\nMonitor not working",
                assignedtopeople=test_data['assigned_user'],
                assignedtogroup=test_data['group'],
                comments="Initial ticket creation test",
                priority=Ticket.Priority.MEDIUM,
                status=Ticket.Status.OPEN,
                ticketcategory=test_data['category'],
                location=test_data['location'],
                asset=test_data['asset'],
                performedby=test_data['user'],
                bu=test_data['bu'],
                client=test_data['client'],
                tenant=test_data['tenant'],
                cuser=test_data['user'],
                muser=test_data['user'],
                ticketsource=Ticket.TicketSource.USERDEFINED,
                level=1,
                isescalated=False,
                identifier=Ticket.Identifier.TICKET
            )
            
            # Store ticket history
            db_utils.store_ticket_history(instance=ticket, user=test_data['user'])
            
            print(f"✓ Ticket created: ID={ticket.id}, UUID={ticket.uuid}")
            print(f"  Description: {ticket.ticketdesc[:50]}...")
            print(f"  Status: {ticket.status}")
            print(f"  Priority: {ticket.priority}")
            print(f"  Assigned to: {ticket.assignedtopeople.peoplename}")
            print(f"  Location: {ticket.location.locname}")
            
            return ticket
            
    except Exception as e:
        print(f"✗ Error creating ticket: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_ticket_update(ticket, test_data):
    """Test updating an existing ticket"""
    print("\n=== Testing Ticket Update ===")
    
    if not ticket:
        print("✗ No ticket to update")
        return
    
    try:
        # Update ticket status
        ticket.status = Ticket.Status.RESOLVED
        ticket.comments = "Issue resolved by replacing monitor"
        ticket.muser = test_data['user']
        ticket.save()
        
        # Store updated history
        db_utils.store_ticket_history(instance=ticket, user=test_data['user'])
        
        print(f"✓ Ticket updated: ID={ticket.id}")
        print(f"  New Status: {ticket.status}")
        print(f"  New Comments: {ticket.comments}")
        
        return ticket
        
    except Exception as e:
        print(f"✗ Error updating ticket: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_ticket_history(ticket):
    """Test ticket history tracking"""
    print("\n=== Testing Ticket History ===")
    
    if not ticket:
        print("✗ No ticket to check history")
        return
    
    try:
        ticket.refresh_from_db()
        history = ticket.ticketlog.get('ticket_history', [])
        
        print(f"✓ Ticket history entries: {len(history)}")
        
        for i, entry in enumerate(history, 1):
            print(f"\nHistory Entry {i}:")
            print(f"  When: {entry.get('when')}")
            print(f"  Who: {entry.get('who')}")
            print(f"  Action: {entry.get('action')}")
            print(f"  Details: {entry.get('details')}")
            
    except Exception as e:
        print(f"✗ Error checking history: {e}")
        import traceback
        traceback.print_exc()


def test_ticket_without_location():
    """Test creating ticket without location (testing null handling)"""
    print("\n=== Testing Ticket Without Location ===")
    
    try:
        # Get minimal required data
        user = People.objects.get(id=5)
        tenant = Tenant.objects.get(id=1)
        
        ticket = Ticket.objects.create(
            ticketdesc="Test ticket without location",
            comments="Testing null location handling",
            priority=Ticket.Priority.LOW,
            status=Ticket.Status.NEW,
            tenant=tenant,
            cuser=user,
            muser=user,
            ticketsource=Ticket.TicketSource.USERDEFINED,
            identifier=Ticket.Identifier.TICKET
        )
        
        # This should not crash even without location
        db_utils.store_ticket_history(instance=ticket, user=user)
        
        print(f"✓ Ticket created without location: ID={ticket.id}")
        print(f"  Location field: {ticket.location}")
        
        return ticket
        
    except Exception as e:
        print(f"✗ Error creating ticket without location: {e}")
        import traceback
        traceback.print_exc()
        return None


def cleanup_test_data():
    """Clean up test tickets (optional)"""
    print("\n=== Cleanup ===")
    response = input("Do you want to delete test tickets? (y/n): ")
    
    if response.lower() == 'y':
        count = Ticket.objects.filter(
            ticketdesc__startswith="Test ticket"
        ).delete()[0]
        print(f"✓ Deleted {count} test tickets")
    else:
        print("✓ Test tickets retained for review")


def main():
    """Main test execution"""
    print("=" * 50)
    print("YOUTILITY5 Ticket Feature Test Suite")
    print("=" * 50)
    
    # Create test data
    test_data = create_test_data()
    
    # Run tests
    ticket = test_ticket_creation(test_data)
    
    if ticket:
        test_ticket_update(ticket, test_data)
        test_ticket_history(ticket)
    
    # Test edge cases
    test_ticket_without_location()
    
    # Optional cleanup
    cleanup_test_data()
    
    print("\n" + "=" * 50)
    print("Test Suite Completed")
    print("=" * 50)


if __name__ == "__main__":
    main()