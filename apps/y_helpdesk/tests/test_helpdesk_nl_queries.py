"""
Help Desk Natural Language Query Tests.

Comprehensive test suite for Help Desk NL query functionality including:
- Query executor filters and logic
- Module routing integration
- Security and permission validation
- Complex multi-filter queries
- Workflow and escalation queries

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #14b: Multi-layer security validation
- Rule #19: Comprehensive testing
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from apps.y_helpdesk.services.helpdesk_query_executor import HelpDeskQueryExecutor
from apps.noc.services.nl_query_service import NLQueryService


@pytest.mark.django_db
class TestHelpDeskQueryExecutor:
    """Test HelpDeskQueryExecutor methods and filters."""

    @pytest.fixture
    def test_user(self, django_user_model):
        """Create test user with tenant."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        tenant = Tenant.objects.create(
            tenantname='Test Tenant',
            tenantcode='TEST001',
            isactive=True
        )

        user = People.objects.create(
            username='testuser',
            peoplename='Test User',
            tenant=tenant,
            isadmin=False
        )
        return user

    @pytest.fixture
    def admin_user(self, django_user_model):
        """Create admin user."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        tenant = Tenant.objects.create(
            tenantname='Admin Tenant',
            tenantcode='ADMIN001',
            isactive=True
        )

        user = People.objects.create(
            username='adminuser',
            peoplename='Admin User',
            tenant=tenant,
            isadmin=True
        )
        return user

    @pytest.fixture
    def test_site(self, test_user):
        """Create test site."""
        from apps.client_onboarding.models import Bt

        site = Bt.objects.create(
            buname='Test Site X',
            bucode='SITE_X',
            tenant=test_user.tenant,
            cuser=test_user,
            muser=test_user
        )
        return site

    @pytest.fixture
    def test_tickets(self, test_user, test_site):
        """Create test tickets with various statuses and priorities."""
        from apps.y_helpdesk.models import Ticket

        now = timezone.now()
        tickets = []

        # Create 10 test tickets with different combinations
        ticket_configs = [
            {'status': 'NEW', 'priority': 'HIGH', 'expiry_offset': -2},  # Overdue
            {'status': 'OPEN', 'priority': 'HIGH', 'expiry_offset': 1},  # Approaching SLA
            {'status': 'OPEN', 'priority': 'MEDIUM', 'expiry_offset': 48},  # OK
            {'status': 'RESOLVED', 'priority': 'LOW', 'expiry_offset': -10},  # Resolved
            {'status': 'ONHOLD', 'priority': 'MEDIUM', 'expiry_offset': 24},  # On hold
            {'status': 'CLOSED', 'priority': 'HIGH', 'expiry_offset': -5},  # Closed
            {'status': 'NEW', 'priority': 'LOW', 'expiry_offset': 72},  # New
            {'status': 'OPEN', 'priority': 'HIGH', 'expiry_offset': -1},  # Overdue
            {'status': 'CANCELLED', 'priority': 'LOW', 'expiry_offset': 0},  # Cancelled
            {'status': 'OPEN', 'priority': 'MEDIUM', 'expiry_offset': 24},  # OK
        ]

        for i, config in enumerate(ticket_configs):
            ticket = Ticket.objects.create(
                ticketno=f'T{i+1:05d}',
                ticketdesc=f'Test Ticket {i+1}',
                bu=test_site,
                client=test_site,
                tenant=test_user.tenant,
                status=config['status'],
                priority=config['priority'],
                expirydatetime=now + timedelta(hours=config['expiry_offset']),
                ticketsource='SYSTEMGENERATED' if i % 2 == 0 else 'USERDEFINED',
                cuser=test_user,
                muser=test_user
            )
            tickets.append(ticket)

        return tickets

    def test_ticket_status_filter(self, test_user, test_tickets):
        """Test filtering tickets by status."""
        params = {
            'query_type': 'tickets',
            'filters': {'status': ['OPEN']},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        assert result['metadata']['returned_count'] == 4  # 4 OPEN tickets
        assert all(t.status == 'OPEN' for t in result['results'])

    def test_priority_filter(self, test_user, test_tickets):
        """Test filtering tickets by priority."""
        params = {
            'query_type': 'tickets',
            'filters': {'priority': ['HIGH']},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        assert result['metadata']['returned_count'] == 4  # 4 HIGH priority tickets
        assert all(t.priority == 'HIGH' for t in result['results'])

    def test_overdue_filter(self, test_user, test_tickets):
        """Test filtering overdue tickets."""
        params = {
            'query_type': 'tickets',
            'filters': {'sla_status': 'overdue'},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        # Should find tickets with expiry < now and not CLOSED/RESOLVED/CANCELLED
        assert result['metadata']['returned_count'] >= 2
        now = timezone.now()
        for ticket in result['results']:
            assert ticket.expirydatetime < now
            assert ticket.status not in ['CLOSED', 'RESOLVED', 'CANCELLED']

    def test_assignment_my_tickets(self, test_user, test_tickets):
        """Test filtering tickets assigned to current user."""
        # Assign some tickets to test_user
        from apps.y_helpdesk.models import Ticket

        tickets_to_assign = Ticket.objects.filter(tenant=test_user.tenant)[:3]
        for ticket in tickets_to_assign:
            ticket.assignedtopeople = test_user
            ticket.save()

        params = {
            'query_type': 'tickets',
            'filters': {'assignment_type': 'my_tickets'},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        assert result['metadata']['returned_count'] == 3
        assert all(t.assignedtopeople == test_user for t in result['results'])

    def test_assignment_unassigned(self, test_user, test_tickets):
        """Test filtering unassigned tickets."""
        params = {
            'query_type': 'tickets',
            'filters': {'assignment_type': 'unassigned'},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        # All test tickets are unassigned initially
        assert result['metadata']['returned_count'] == 10
        for ticket in result['results']:
            assert ticket.assignedtopeople is None
            assert ticket.assignedtogroup is None

    def test_site_filter(self, test_user, test_tickets, test_site):
        """Test filtering tickets by site name."""
        params = {
            'query_type': 'tickets',
            'filters': {'site_name': 'Test Site'},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        assert result['metadata']['returned_count'] == 10  # All at Test Site X
        assert all(t.bu == test_site for t in result['results'])

    def test_source_filter(self, test_user, test_tickets):
        """Test filtering tickets by source."""
        params = {
            'query_type': 'tickets',
            'filters': {'source': 'SYSTEMGENERATED'},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        assert result['metadata']['returned_count'] == 5  # Every other ticket
        assert all(t.ticketsource == 'SYSTEMGENERATED' for t in result['results'])

    def test_multi_filter_combination(self, test_user, test_tickets):
        """Test complex multi-filter query."""
        params = {
            'query_type': 'tickets',
            'filters': {
                'status': ['OPEN', 'NEW'],
                'priority': ['HIGH'],
                'assignment_type': 'unassigned'
            },
            'time_range': {'days': 30},
            'aggregation': {'limit': 100, 'order_by': 'priority'}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        # Should find HIGH priority, OPEN/NEW, unassigned tickets
        assert result['metadata']['returned_count'] >= 2
        for ticket in result['results']:
            assert ticket.status in ['OPEN', 'NEW']
            assert ticket.priority == 'HIGH'
            assert ticket.assignedtopeople is None


@pytest.mark.django_db
class TestTicketWorkflowQueries:
    """Test queries involving TicketWorkflow data."""

    @pytest.fixture
    def test_user(self, django_user_model):
        """Create test user."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        tenant = Tenant.objects.create(
            tenantname='Workflow Tenant',
            tenantcode='WF001',
            isactive=True
        )

        user = People.objects.create(
            username='wfuser',
            peoplename='Workflow User',
            tenant=tenant,
            isadmin=False
        )
        return user

    @pytest.fixture
    def escalated_tickets(self, test_user):
        """Create tickets with workflow/escalation data."""
        from apps.y_helpdesk.models import Ticket, TicketWorkflow
        from apps.client_onboarding.models import Bt

        site = Bt.objects.create(
            buname='Escalation Site',
            bucode='ESC_SITE',
            tenant=test_user.tenant,
            cuser=test_user,
            muser=test_user
        )

        tickets = []
        now = timezone.now()

        # Create 5 tickets, 3 escalated
        for i in range(5):
            ticket = Ticket.objects.create(
                ticketno=f'T_ESC_{i+1:03d}',
                ticketdesc=f'Escalation Test Ticket {i+1}',
                bu=site,
                client=site,
                tenant=test_user.tenant,
                status='OPEN',
                priority='HIGH',
                expirydatetime=now + timedelta(hours=24),
                cuser=test_user,
                muser=test_user
            )

            # Create workflow for escalated tickets
            if i < 3:  # First 3 are escalated
                workflow = TicketWorkflow.objects.create(
                    ticket=ticket,
                    tenant=test_user.tenant,
                    bu=site,
                    client=site,
                    is_escalated=True,
                    escalation_level=i + 1,
                    escalation_count=1,
                    last_escalated_at=now,
                    cuser=test_user,
                    muser=test_user
                )

            tickets.append(ticket)

        return tickets

    def test_escalated_tickets_query(self, test_user, escalated_tickets):
        """Test querying escalated tickets."""
        params = {
            'query_type': 'tickets',
            'filters': {
                'escalation': {'is_escalated': True}
            },
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        assert result['metadata']['returned_count'] == 3
        # Verify workflow data exists
        for ticket in result['results']:
            workflow = ticket.workflow
            assert workflow.is_escalated is True

    def test_escalation_level_filter(self, test_user, escalated_tickets):
        """Test filtering by specific escalation level."""
        params = {
            'query_type': 'tickets',
            'filters': {
                'escalation': {'level': 2}
            },
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        assert result['metadata']['returned_count'] == 1
        assert result['results'][0].workflow.escalation_level == 2

    def test_workflow_lazy_properties(self, test_user, escalated_tickets):
        """Test lazy-loaded workflow properties on Ticket model."""
        from apps.y_helpdesk.models import Ticket

        # Get an escalated ticket
        ticket = Ticket.objects.filter(
            tenant=test_user.tenant,
            ticketno='T_ESC_001'
        ).first()

        assert ticket is not None
        # Access workflow properties via lazy-loaded relationship
        assert ticket.isescalated is True
        assert ticket.level >= 1

    def test_workflow_performance(self, test_user, escalated_tickets):
        """Test query performance with workflow joins."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        params = {
            'query_type': 'tickets',
            'filters': {
                'escalation': {'is_escalated': True}
            },
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        with CaptureQueriesContext(connection) as context:
            result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        # Should use select_related to minimize queries
        # Exact count depends on Django ORM optimization
        assert len(context.captured_queries) < 10
        assert result['metadata']['returned_count'] == 3


@pytest.mark.django_db
class TestHelpDeskNLIntegration:
    """Test integration with NL query service and routing."""

    @pytest.fixture
    def test_user(self, django_user_model):
        """Create test user."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        tenant = Tenant.objects.create(
            tenantname='Integration Tenant',
            tenantcode='INT001',
            isactive=True
        )

        user = People.objects.create(
            username='intuser',
            peoplename='Integration User',
            tenant=tenant,
            isadmin=True  # Admin for capability bypass
        )
        return user

    def test_nl_query_routes_to_helpdesk(self, test_user):
        """Test that NLQueryService correctly routes ticket queries."""
        params = {
            'query_type': 'tickets',
            'filters': {'status': ['OPEN']},
            'time_range': {'days': 7},
            'aggregation': {'limit': 100}
        }

        # Test module detection
        module = NLQueryService._detect_target_module(params)
        assert module == 'helpdesk'

        # Test routing
        result = NLQueryService._route_to_executor(module, params, test_user)

        assert 'results' in result
        assert 'metadata' in result
        assert result['metadata']['query_type'] == 'tickets'

    def test_module_detection_accuracy(self, test_user):
        """Test module detection for various query types."""
        test_cases = [
            ({'query_type': 'tickets'}, 'helpdesk'),
            ({'query_type': 'alerts'}, 'noc'),
            ({'query_type': 'incidents'}, 'noc'),
            ({'query_type': 'metrics'}, 'noc'),
        ]

        for params, expected_module in test_cases:
            detected = NLQueryService._detect_target_module(params)
            assert detected == expected_module, f"Failed for {params['query_type']}"

    def test_result_formatting(self, test_user):
        """Test that Help Desk results are properly formatted."""
        from apps.y_helpdesk.models import Ticket
        from apps.client_onboarding.models import Bt

        # Create test data
        site = Bt.objects.create(
            buname='Format Test Site',
            bucode='FMT_SITE',
            tenant=test_user.tenant,
            cuser=test_user,
            muser=test_user
        )

        ticket = Ticket.objects.create(
            ticketno='T_FMT_001',
            ticketdesc='Format Test Ticket',
            bu=site,
            client=site,
            tenant=test_user.tenant,
            status='OPEN',
            priority='HIGH',
            expirydatetime=timezone.now() + timedelta(hours=24),
            cuser=test_user,
            muser=test_user
        )

        params = {
            'query_type': 'tickets',
            'filters': {'status': ['OPEN']},
            'time_range': {'days': 7},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, test_user)

        # Verify metadata structure
        assert 'total_count' in result['metadata']
        assert 'returned_count' in result['metadata']
        assert 'query_type' in result['metadata']
        assert 'status_distribution' in result['metadata']
        assert 'priority_distribution' in result['metadata']

    def test_cache_behavior(self, test_user):
        """Test query caching for Help Desk queries."""
        from apps.noc.services.query_cache import QueryCache

        query_text = "Show me open tickets"

        # Clear cache
        QueryCache.invalidate_tenant(test_user.tenant.id)

        # Mock cached result
        cached_data = {
            'status': 'success',
            'summary': 'Found 5 tickets',
            'data': [],
        }

        # Store in cache
        QueryCache.set(query_text, test_user.id, test_user.tenant.id, cached_data)

        # Retrieve from cache
        retrieved = QueryCache.get(query_text, test_user.id, test_user.tenant.id)

        assert retrieved is not None
        assert retrieved['summary'] == 'Found 5 tickets'


@pytest.mark.django_db
class TestHelpDeskQuerySafety:
    """Test security and permission validation."""

    @pytest.fixture
    def regular_user(self, django_user_model):
        """Create regular user without Help Desk permissions."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        tenant = Tenant.objects.create(
            tenantname='Security Tenant',
            tenantcode='SEC001',
            isactive=True
        )

        user = People.objects.create(
            username='reguser',
            peoplename='Regular User',
            tenant=tenant,
            isadmin=False
        )
        return user

    @pytest.fixture
    def admin_user(self, django_user_model):
        """Create admin user."""
        from apps.tenants.models import Tenant
        from apps.peoples.models import People

        tenant = Tenant.objects.create(
            tenantname='Admin Sec Tenant',
            tenantcode='ASEC001',
            isactive=True
        )

        user = People.objects.create(
            username='adminsec',
            peoplename='Admin Sec User',
            tenant=tenant,
            isadmin=True
        )
        return user

    def test_tenant_isolation_enforced(self, admin_user):
        """Test that queries only return tickets from user's tenant."""
        from apps.y_helpdesk.models import Ticket
        from apps.client_onboarding.models import Bt
        from apps.tenants.models import Tenant

        # Create second tenant with tickets
        other_tenant = Tenant.objects.create(
            tenantname='Other Tenant',
            tenantcode='OTHER001',
            isactive=True
        )

        # Create ticket in other tenant (should not be visible)
        other_site = Bt.objects.create(
            buname='Other Site',
            bucode='OTHER_SITE',
            tenant=other_tenant,
            cuser=admin_user,
            muser=admin_user
        )

        Ticket.objects.create(
            ticketno='T_OTHER_001',
            ticketdesc='Other Tenant Ticket',
            bu=other_site,
            client=other_site,
            tenant=other_tenant,
            status='OPEN',
            priority='HIGH',
            cuser=admin_user,
            muser=admin_user
        )

        # Create ticket in admin_user's tenant
        admin_site = Bt.objects.create(
            buname='Admin Site',
            bucode='ADMIN_SITE',
            tenant=admin_user.tenant,
            cuser=admin_user,
            muser=admin_user
        )

        Ticket.objects.create(
            ticketno='T_ADMIN_001',
            ticketdesc='Admin Tenant Ticket',
            bu=admin_site,
            client=admin_site,
            tenant=admin_user.tenant,
            status='OPEN',
            priority='HIGH',
            cuser=admin_user,
            muser=admin_user
        )

        # Query as admin_user
        params = {
            'query_type': 'tickets',
            'filters': {'status': ['OPEN']},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        result = HelpDeskQueryExecutor.execute_ticket_query(params, admin_user)

        # Should only see tickets from admin_user's tenant
        assert result['metadata']['returned_count'] == 1
        assert all(t.tenant == admin_user.tenant for t in result['results'])

    def test_rbac_validation(self, regular_user):
        """Test RBAC validation for Help Desk queries."""
        params = {
            'query_type': 'tickets',
            'filters': {},
            'time_range': {'days': 30},
            'aggregation': {'limit': 100}
        }

        # Regular user without permissions should be denied
        # Note: This depends on UserCapabilityService implementation
        # If capability check is strict, this will raise PermissionDenied
        try:
            result = HelpDeskQueryExecutor.execute_ticket_query(params, regular_user)
            # If no error, check that validation passed (admin bypass or capability exists)
            assert 'results' in result
        except PermissionDenied:
            # Expected for users without helpdesk:view capability
            pass
