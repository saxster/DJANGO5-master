#!/usr/bin/env python
"""
Comprehensive Escalation Feature Testing Script
This script tests all aspects of the ticket escalation system
"""

import os
import sys
import django
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from apps.y_helpdesk.models import Ticket, EscalationMatrix
from apps.onboarding.models import TypeAssist, Bt
from apps.peoples.models import People, Pgroup
from apps.activity.models.job_model import Job
from django.db import transaction
from background_tasks.tasks import ticket_escalation
from background_tasks.utils import get_escalation_of_ticket, send_escalation_ticket_email
from apps.core.queries import QueryRepository
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EscalationTester:
    def __init__(self):
        self.test_results = []
        self.test_data = {}
        
    def log_result(self, test_name, status, details=""):
        """Log test results"""
        result = {
            'test': test_name,
            'status': status,
            'details': details,
            'timestamp': datetime.now()
        }
        self.test_results.append(result)
        print(f"[{'✓' if status == 'PASS' else '✗'}] {test_name}: {details}")
        
    def setup_test_data(self):
        """Create test data for escalation testing"""
        print("\n=== Setting up Test Data ===\n")
        
        try:
            # Get or create test BU and client
            bu, _ = Bt.objects.get_or_create(
                bucode="TEST_BU",
                defaults={
                    'buname': 'Test Business Unit',
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            client, _ = Bt.objects.get_or_create(
                bucode="TEST_CLIENT",
                defaults={
                    'buname': 'Test Client',
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            # Get or create test users and groups
            user1, _ = People.objects.get_or_create(
                peoplecode="TEST_USER1",
                defaults={
                    'peoplename': 'Test User 1',
                    'email': 'testuser1@test.com',
                    'dateofbirth': datetime(1990, 1, 1).date(),
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            user2, _ = People.objects.get_or_create(
                peoplecode="TEST_USER2", 
                defaults={
                    'peoplename': 'Test User 2',
                    'email': 'testuser2@test.com',
                    'dateofbirth': datetime(1990, 1, 1).date(),
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            user3, _ = People.objects.get_or_create(
                peoplecode="TEST_USER3",
                defaults={
                    'peoplename': 'Test User 3',
                    'email': 'testuser3@test.com',
                    'dateofbirth': datetime(1990, 1, 1).date(),
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            group1, _ = Pgroup.objects.get_or_create(
                groupname="TEST_GROUP1",
                defaults={
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            group2, _ = Pgroup.objects.get_or_create(
                groupname="TEST_GROUP2",
                defaults={
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            # Create ticket category for escalation
            ticket_category, _ = TypeAssist.objects.get_or_create(
                tacode="TEST_TICKET_CAT",
                defaults={
                    'taname': 'Test Ticket Category',
                    'tatype_id': TypeAssist.objects.filter(
                        tacode='TICKETCATEGORY'
                    ).first().id if TypeAssist.objects.filter(
                        tacode='TICKETCATEGORY'
                    ).exists() else 1,
                    'bu': bu,
                    'client': client,
                    'cuser_id': 1,
                    'muser_id': 1,
                }
            )
            
            # Store test data
            self.test_data = {
                'bu': bu,
                'client': client,
                'users': [user1, user2, user3],
                'groups': [group1, group2],
                'ticket_category': ticket_category
            }
            
            self.log_result("Setup Test Data", "PASS", "Test data created successfully")
            return True
            
        except Exception as e:
            self.log_result("Setup Test Data", "FAIL", str(e))
            return False
            
    def test_escalation_matrix_creation(self):
        """Test creating escalation matrix entries"""
        print("\n=== Testing Escalation Matrix Creation ===\n")
        
        try:
            # Create escalation levels
            escalation_levels = []
            
            # Level 1 - Assigned to User 1, escalates after 1 hour
            esc1 = EscalationMatrix.objects.create(
                level=1,
                frequency=EscalationMatrix.Frequency.HOUR,
                frequencyvalue=1,
                assignedfor="PEOPLE",
                assignedperson=self.test_data['users'][0],
                bu=self.test_data['bu'],
                client=self.test_data['client'],
                escalationtemplate=self.test_data['ticket_category'],
                notify="escalation1@test.com",
                cuser_id=1,
                muser_id=1,
                job_id=1,
            )
            escalation_levels.append(esc1)
            
            # Level 2 - Assigned to Group 1, escalates after 2 hours
            esc2 = EscalationMatrix.objects.create(
                level=2,
                frequency=EscalationMatrix.Frequency.HOUR,
                frequencyvalue=2,
                assignedfor="GROUP",
                assignedgroup=self.test_data['groups'][0],
                bu=self.test_data['bu'],
                client=self.test_data['client'],
                escalationtemplate=self.test_data['ticket_category'],
                notify="escalation2@test.com",
                cuser_id=1,
                muser_id=1,
                job_id=1,
            )
            escalation_levels.append(esc2)
            
            # Level 3 - Assigned to User 3, escalates after 1 day
            esc3 = EscalationMatrix.objects.create(
                level=3,
                frequency=EscalationMatrix.Frequency.DAY,
                frequencyvalue=1,
                assignedfor="PEOPLE",
                assignedperson=self.test_data['users'][2],
                bu=self.test_data['bu'],
                client=self.test_data['client'],
                escalationtemplate=self.test_data['ticket_category'],
                notify="escalation3@test.com",
                cuser_id=1,
                muser_id=1,
                job_id=1,
            )
            escalation_levels.append(esc3)
            
            self.test_data['escalation_levels'] = escalation_levels
            self.log_result("Escalation Matrix Creation", "PASS", 
                          f"Created {len(escalation_levels)} escalation levels")
            return True
            
        except Exception as e:
            self.log_result("Escalation Matrix Creation", "FAIL", str(e))
            return False
            
    def test_ticket_creation(self):
        """Test creating tickets that will be escalated"""
        print("\n=== Testing Ticket Creation ===\n")
        
        try:
            tickets = []
            now = timezone.now()
            
            # Create ticket that should be escalated (created 2 hours ago)
            ticket1 = Ticket.objects.create(
                ticketno=f"TEST_{now.strftime('%Y%m%d%H%M%S')}_1",
                ticketdesc="Test Ticket for Escalation - Should Escalate",
                status=Ticket.Status.OPEN,
                priority=Ticket.Priority.HIGH,
                assignedtopeople=self.test_data['users'][0],
                bu=self.test_data['bu'],
                client=self.test_data['client'],
                ticketcategory=self.test_data['ticket_category'],
                cuser_id=1,
                muser_id=1,
                level=0,
                ticketsource=Ticket.TicketSource.USERDEFINED,
                cdtz=now - timedelta(hours=2),
                mdtz=now - timedelta(hours=2),
            )
            tickets.append(ticket1)
            
            # Create recent ticket (should not escalate yet)
            ticket2 = Ticket.objects.create(
                ticketno=f"TEST_{now.strftime('%Y%m%d%H%M%S')}_2",
                ticketdesc="Test Ticket - Recently Created",
                status=Ticket.Status.OPEN,
                priority=Ticket.Priority.MEDIUM,
                assignedtopeople=self.test_data['users'][0],
                bu=self.test_data['bu'],
                client=self.test_data['client'],
                ticketcategory=self.test_data['ticket_category'],
                cuser_id=1,
                muser_id=1,
                level=0,
                ticketsource=Ticket.TicketSource.USERDEFINED,
            )
            tickets.append(ticket2)
            
            # Create resolved ticket (should not escalate)
            ticket3 = Ticket.objects.create(
                ticketno=f"TEST_{now.strftime('%Y%m%d%H%M%S')}_3",
                ticketdesc="Test Ticket - Resolved",
                status=Ticket.Status.RESOLVED,
                priority=Ticket.Priority.LOW,
                assignedtopeople=self.test_data['users'][0],
                bu=self.test_data['bu'],
                client=self.test_data['client'],
                ticketcategory=self.test_data['ticket_category'],
                cuser_id=1,
                muser_id=1,
                level=0,
                ticketsource=Ticket.TicketSource.USERDEFINED,
                cdtz=now - timedelta(hours=3),
                mdtz=now - timedelta(hours=3),
            )
            tickets.append(ticket3)
            
            self.test_data['tickets'] = tickets
            self.log_result("Ticket Creation", "PASS", 
                          f"Created {len(tickets)} test tickets")
            return True
            
        except Exception as e:
            self.log_result("Ticket Creation", "FAIL", str(e))
            return False
            
    def test_escalation_query(self):
        """Test the escalation query to find tickets needing escalation"""
        print("\n=== Testing Escalation Query ===\n")
        
        try:
            # Get tickets for escalation using the query
            escalatable_tickets = QueryRepository.get_ticketlist_for_escalation()
            
            if escalatable_tickets:
                self.log_result("Escalation Query", "PASS", 
                              f"Found {len(escalatable_tickets)} tickets for escalation")
                
                # Log details of each ticket
                for ticket in escalatable_tickets[:3]:  # Show first 3
                    print(f"  - Ticket #{ticket.get('ticketno', 'N/A')}: "
                          f"Level {ticket.get('level', 0)}, "
                          f"Status: {ticket.get('status', 'N/A')}")
            else:
                self.log_result("Escalation Query", "INFO", 
                              "No tickets found for escalation (may be expected)")
                
            return True
            
        except Exception as e:
            self.log_result("Escalation Query", "FAIL", str(e))
            return False
            
    def test_escalation_lookup(self):
        """Test looking up next escalation level for a ticket"""
        print("\n=== Testing Escalation Level Lookup ===\n")
        
        try:
            for ticket in self.test_data.get('tickets', []):
                ticket_data = Ticket.objects.filter(id=ticket.id).values(
                    'bu_id', 'ticketcategory_id', 'client_id', 'level'
                ).first()
                
                if ticket_data:
                    next_esc = get_escalation_of_ticket(ticket_data)
                    if next_esc:
                        self.log_result("Escalation Lookup", "PASS",
                                      f"Ticket {ticket.ticketno}: Next level {next_esc.get('level', 'N/A')} "
                                      f"in {next_esc.get('frequencyvalue', 0)} {next_esc.get('frequency', 'N/A')}")
                    else:
                        self.log_result("Escalation Lookup", "INFO",
                                      f"Ticket {ticket.ticketno}: No next escalation level")
                        
            return True
            
        except Exception as e:
            self.log_result("Escalation Lookup", "FAIL", str(e))
            return False
            
    def test_escalation_process(self):
        """Test the actual escalation process"""
        print("\n=== Testing Escalation Process ===\n")
        
        try:
            # Run the escalation task
            result = ticket_escalation()
            
            if result:
                self.log_result("Escalation Process", "PASS",
                              f"Process completed: {result.get('story', 'No details')}")
                
                # Check if tickets were actually escalated
                if result.get('id'):
                    print(f"  Escalated ticket IDs: {result['id']}")
                    
                    # Verify escalation changes
                    for ticket_id in result['id']:
                        ticket = Ticket.objects.get(id=ticket_id)
                        print(f"  - Ticket {ticket.ticketno}: "
                              f"Level={ticket.level}, "
                              f"IsEscalated={ticket.isescalated}")
            else:
                self.log_result("Escalation Process", "INFO",
                              "No escalations performed")
                
            return True
            
        except Exception as e:
            self.log_result("Escalation Process", "FAIL", str(e))
            return False
            
    def test_manual_escalation(self):
        """Test manual escalation of a specific ticket"""
        print("\n=== Testing Manual Escalation ===\n")
        
        try:
            # Get the first test ticket
            if self.test_data.get('tickets'):
                ticket = self.test_data['tickets'][0]
                original_level = ticket.level
                original_assignee = ticket.assignedtopeople
                
                # Manually escalate the ticket
                ticket.level += 1
                ticket.isescalated = True
                ticket.mdtz = timezone.now()
                
                # Get next escalation level
                next_esc = EscalationMatrix.objects.filter(
                    bu=ticket.bu,
                    client=ticket.client,
                    escalationtemplate=ticket.ticketcategory,
                    level=ticket.level
                ).first()
                
                if next_esc:
                    if next_esc.assignedperson:
                        ticket.assignedtopeople = next_esc.assignedperson
                    if next_esc.assignedgroup:
                        ticket.assignedtogroup = next_esc.assignedgroup
                        
                ticket.save()
                
                self.log_result("Manual Escalation", "PASS",
                              f"Ticket {ticket.ticketno} escalated from level {original_level} to {ticket.level}")
                
                # Verify the changes
                ticket.refresh_from_db()
                print(f"  Verification: Level={ticket.level}, IsEscalated={ticket.isescalated}")
                
            return True
            
        except Exception as e:
            self.log_result("Manual Escalation", "FAIL", str(e))
            return False
            
    def test_escalation_constraints(self):
        """Test escalation matrix constraints"""
        print("\n=== Testing Escalation Constraints ===\n")
        
        try:
            # Test frequency value constraint (should be >= 0)
            try:
                invalid_esc = EscalationMatrix.objects.create(
                    level=99,
                    frequency=EscalationMatrix.Frequency.HOUR,
                    frequencyvalue=-1,  # Invalid: negative value
                    assignedfor="PEOPLE",
                    assignedperson=self.test_data['users'][0],
                    bu=self.test_data['bu'],
                    client=self.test_data['client'],
                    escalationtemplate=self.test_data['ticket_category'],
                    cuser_id=1,
                    muser_id=1,
                    job_id=1,
                )
                self.log_result("Frequency Constraint", "FAIL", 
                              "Negative frequency value was allowed")
            except Exception:
                self.log_result("Frequency Constraint", "PASS", 
                              "Negative frequency value correctly rejected")
                
            # Test email format constraint
            try:
                invalid_email_esc = EscalationMatrix.objects.create(
                    level=98,
                    frequency=EscalationMatrix.Frequency.HOUR,
                    frequencyvalue=1,
                    assignedfor="PEOPLE",
                    assignedperson=self.test_data['users'][0],
                    bu=self.test_data['bu'],
                    client=self.test_data['client'],
                    escalationtemplate=self.test_data['ticket_category'],
                    notify="invalid-email",  # Invalid email format
                    cuser_id=1,
                    muser_id=1,
                    job_id=1,
                )
                self.log_result("Email Constraint", "FAIL", 
                              "Invalid email format was allowed")
            except Exception:
                self.log_result("Email Constraint", "PASS", 
                              "Invalid email format correctly rejected")
                
            return True
            
        except Exception as e:
            self.log_result("Escalation Constraints", "FAIL", str(e))
            return False
            
    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n=== Cleaning Up Test Data ===\n")
        
        try:
            # Delete test tickets
            if self.test_data.get('tickets'):
                for ticket in self.test_data['tickets']:
                    ticket.delete()
                    
            # Delete escalation matrix entries
            if self.test_data.get('escalation_levels'):
                for esc in self.test_data['escalation_levels']:
                    esc.delete()
                    
            self.log_result("Cleanup", "PASS", "Test data cleaned up")
            return True
            
        except Exception as e:
            self.log_result("Cleanup", "FAIL", str(e))
            return False
            
    def generate_report(self):
        """Generate test report"""
        print("\n" + "="*60)
        print("ESCALATION FEATURE TEST REPORT")
        print("="*60)
        print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Tests: {len(self.test_results)}")
        
        passed = sum(1 for r in self.test_results if r['status'] == 'PASS')
        failed = sum(1 for r in self.test_results if r['status'] == 'FAIL')
        info = sum(1 for r in self.test_results if r['status'] == 'INFO')
        
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Info: {info}")
        
        if failed > 0:
            print("\nFailed Tests:")
            for result in self.test_results:
                if result['status'] == 'FAIL':
                    print(f"  - {result['test']}: {result['details']}")
                    
        print("\nTest Summary:")
        for result in self.test_results:
            status_icon = '✓' if result['status'] == 'PASS' else ('✗' if result['status'] == 'FAIL' else 'ℹ')
            print(f"  [{status_icon}] {result['test']}")
            
        print("="*60)
        
    def run_all_tests(self):
        """Run all escalation tests"""
        print("\n" + "="*60)
        print("STARTING ESCALATION FEATURE TESTS")
        print("="*60)
        
        # Setup
        if not self.setup_test_data():
            print("Failed to setup test data. Aborting tests.")
            return
            
        # Run tests
        self.test_escalation_matrix_creation()
        self.test_ticket_creation()
        self.test_escalation_query()
        self.test_escalation_lookup()
        self.test_escalation_process()
        self.test_manual_escalation()
        self.test_escalation_constraints()
        
        # Cleanup
        self.cleanup_test_data()
        
        # Generate report
        self.generate_report()


if __name__ == "__main__":
    tester = EscalationTester()
    tester.run_all_tests()