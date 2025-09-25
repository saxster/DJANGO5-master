#!/usr/bin/env python
"""
Diagnostic script to test escalation saving issue
"""

import os
import sys
import django
from datetime import datetime
from django.utils import timezone

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from apps.y_helpdesk.models import EscalationMatrix
from apps.onboarding.models import TypeAssist, Bt
from apps.peoples.models import People, Pgroup

print("=== ESCALATION SAVE DIAGNOSTIC ===\n")

# 1. Check if there are any escalation records
print("1. Current Escalation Records:")
existing = EscalationMatrix.objects.all()
print(f"   Total records in database: {existing.count()}")
if existing:
    for esc in existing[:3]:
        print(f"   - Level {esc.level}, Template: {esc.escalationtemplate}, BU: {esc.bu}, Client: {esc.client}")

# 2. Check required data exists
print("\n2. Required Data Check:")

# Business Units
bus = Bt.objects.exclude(bucode='')
print(f"   Business Units: {bus.count()}")
if bus:
    default_bu = bus.first()
    print(f"   Default BU: {default_bu.buname} (ID: {default_bu.id})")
else:
    print("   ⚠️  No business units found!")

# Clients  
clients = Bt.objects.exclude(bucode='')
print(f"   Clients: {clients.count()}")
if clients:
    default_client = clients.first()
    print(f"   Default Client: {default_client.buname} (ID: {default_client.id})")
else:
    print("   ⚠️  No clients found!")

# Ticket Categories
categories = TypeAssist.objects.filter(tatype__tacode__in=['TICKETCATEGORY', 'TICKET_CATEGORY'])
print(f"   Ticket Categories: {categories.count()}")
if categories:
    test_category = categories.first()
    print(f"   Test Category: {test_category.taname} (ID: {test_category.id})")
else:
    print("   ⚠️  No ticket categories found!")

# Users
users = People.objects.filter(enable=True).exclude(peoplecode='')
print(f"   Active Users: {users.count()}")
if users:
    test_user = users.first()
    print(f"   Test User: {test_user.peoplename} (ID: {test_user.id})")

# 3. Try to create a test escalation record directly
print("\n3. Testing Direct Database Save:")

if bus and clients and categories and users:
    try:
        # Delete any test records first
        EscalationMatrix.objects.filter(
            escalationtemplate=test_category,
            level=99
        ).delete()
        
        # Create new test record
        test_esc = EscalationMatrix.objects.create(
            level=99,
            frequency='HOUR',
            frequencyvalue=2,
            assignedfor='PEOPLE',
            assignedperson=test_user,
            bu=default_bu,
            client=default_client,
            escalationtemplate=test_category,
            job_id=1,
            cuser_id=1,
            muser_id=1,
            ctzoffset=0
        )
        print(f"   ✅ Successfully created test record with ID: {test_esc.id}")
        
        # Verify it was saved
        verify = EscalationMatrix.objects.filter(id=test_esc.id).first()
        if verify:
            print(f"   ✅ Record verified in database")
            print(f"      Level: {verify.level}")
            print(f"      Frequency: {verify.frequencyvalue} {verify.frequency}")
            print(f"      Assigned to: {verify.assignedperson.peoplename if verify.assignedperson else 'N/A'}")
            
            # Clean up test record
            verify.delete()
            print("   ✅ Test record cleaned up")
        else:
            print("   ❌ Record not found after save!")
            
    except Exception as e:
        print(f"   ❌ Error creating record: {e}")
        import traceback
        traceback.print_exc()
else:
    print("   ⚠️  Missing required data for test")

# 4. Check for common issues
print("\n4. Common Issues Check:")

# Check if session middleware is enabled
from django.conf import settings
if 'django.contrib.sessions.middleware.SessionMiddleware' in settings.MIDDLEWARE:
    print("   ✅ Session middleware is enabled")
else:
    print("   ❌ Session middleware not found!")

# Check database connection
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM escalationmatrix")
    count = cursor.fetchone()[0]
    print(f"   ✅ Direct database query works (found {count} records)")

print("\n5. Troubleshooting Steps:")
print("   1. Check browser console for JavaScript errors")
print("   2. Check Network tab to see if POST request is being sent")
print("   3. Check Django logs for any errors during save")
print("   4. Verify session has bu_id and client_id set")

print("\n6. Manual Test Command:")
print("   Run in Django shell to manually create escalation:")
print("""
from apps.y_helpdesk.models import EscalationMatrix
from apps.onboarding.models import TypeAssist, Bt
from apps.peoples.models import People

# Get required objects
bu = Bt.objects.exclude(bucode='').first()
client = Bt.objects.exclude(bucode='').last()
category = TypeAssist.objects.filter(tatype__tacode='TICKETCATEGORY').first()
user = People.objects.filter(enable=True).exclude(peoplecode='').first()

# Create escalation
esc = EscalationMatrix.objects.create(
    level=1,
    frequency='HOUR',
    frequencyvalue=2,
    assignedfor='PEOPLE',
    assignedperson=user,
    bu=bu,
    client=client,
    escalationtemplate=category,
    job_id=1,
    cuser_id=1,
    muser_id=1
)
print(f"Created: {esc.id}")
""")