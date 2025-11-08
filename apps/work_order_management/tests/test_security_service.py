"""
Work Order Management - Security Service Tests

Tests for IDOR prevention and authorization checks.

Created: November 2025
Part of: CRITICAL SECURITY FIX 2
"""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from apps.work_order_management.models.work_order_model import Wom
from apps.work_order_management.services.work_order_security_service import (
    WorkOrderSecurityService
)
from apps.peoples.models import People
from apps.core_onboarding.models import ClientOffice

User = get_user_model()


@pytest.mark.django_db
class TestWorkOrderSecurityService:
    """Test work order security and IDOR protection."""

    @pytest.fixture
    def client_office(self):
        """Create test client office."""
        return ClientOffice.objects.create(
            clientofficename="Test Office",
            clientcode="TEST001"
        )

    @pytest.fixture
    def other_client(self):
        """Create another client office for cross-tenant tests."""
        return ClientOffice.objects.create(
            clientofficename="Other Office",
            clientcode="TEST002"
        )

    @pytest.fixture
    def user1(self, client_office):
        """Create first test user."""
        return User.objects.create_user(
            username="user1",
            email="user1@test.com",
            client_id=client_office.id,
            peoplename="User One"
        )

    @pytest.fixture
    def user2(self, client_office):
        """Create second test user (same tenant)."""
        return User.objects.create_user(
            username="user2",
            email="user2@test.com",
            client_id=client_office.id,
            peoplename="User Two"
        )

    @pytest.fixture
    def user3(self, other_client):
        """Create user from different tenant."""
        return User.objects.create_user(
            username="user3",
            email="user3@test.com",
            client_id=other_client.id,
            peoplename="User Three"
        )

    @pytest.fixture
    def work_order(self, client_office, user1):
        """Create test work order."""
        token = WorkOrderSecurityService.generate_secure_token()
        return Wom.objects.create(
            client_id=client_office.id,
            bu_id=1,
            cuser_id=user1.id,
            description="Test Work Order",
            workstatus=Wom.Workstatus.ASSIGNED,
            other_data={"token": token}
        )

    def test_generate_secure_token(self):
        """Test secure token generation."""
        token1 = WorkOrderSecurityService.generate_secure_token()
        token2 = WorkOrderSecurityService.generate_secure_token()

        # Tokens should be unique
        assert token1 != token2

        # Tokens should be sufficiently long
        assert len(token1) >= 16
        assert len(token2) >= 16

    def test_owner_can_access_work_order(self, work_order, user1):
        """Test work order owner has full access."""
        result = WorkOrderSecurityService.validate_work_order_access(
            work_order.id,
            user1,
            require_ownership=True
        )
        assert result == work_order

    def test_non_owner_cannot_access_with_ownership_required(
        self, work_order, user2
    ):
        """Test non-owner cannot access when ownership is required."""
        with pytest.raises(PermissionDenied, match="permission to access"):
            WorkOrderSecurityService.validate_work_order_access(
                work_order.id,
                user2,
                require_ownership=True
            )

    def test_same_tenant_can_access_work_order(self, work_order, user2):
        """Test same-tenant user can access work order."""
        result = WorkOrderSecurityService.validate_work_order_access(
            work_order.id,
            user2,
            allow_tenant_access=True
        )
        assert result == work_order

    def test_cross_tenant_access_denied(self, work_order, user3):
        """Test IDOR protection: cross-tenant access is blocked."""
        with pytest.raises(PermissionDenied, match="permission to access"):
            WorkOrderSecurityService.validate_work_order_access(
                work_order.id,
                user3,
                allow_tenant_access=True
            )

    def test_invalid_work_order_raises_not_found(self, user1):
        """Test accessing non-existent work order."""
        with pytest.raises(Wom.DoesNotExist):
            WorkOrderSecurityService.validate_work_order_access(
                99999,
                user1
            )

    def test_valid_token_grants_access(self, work_order):
        """Test valid token allows vendor access."""
        token = work_order.other_data["token"]
        result = WorkOrderSecurityService.validate_token_access(
            work_order.id,
            token
        )
        assert result == work_order

    def test_invalid_token_denied(self, work_order):
        """Test invalid token is rejected."""
        with pytest.raises(PermissionDenied, match="Invalid or expired token"):
            WorkOrderSecurityService.validate_token_access(
                work_order.id,
                "invalid_token_12345"
            )

    def test_missing_token_denied(self, work_order):
        """Test missing token is rejected."""
        with pytest.raises(ValidationError, match="Invalid token format"):
            WorkOrderSecurityService.validate_token_access(
                work_order.id,
                ""
            )

    def test_short_token_denied(self, work_order):
        """Test short/weak token is rejected."""
        with pytest.raises(ValidationError, match="Invalid token format"):
            WorkOrderSecurityService.validate_token_access(
                work_order.id,
                "short"
            )

    def test_vendor_cannot_modify_completed_work_order(self, work_order):
        """Test vendor access denied for completed work orders."""
        work_order.workstatus = Wom.Workstatus.COMPLETED
        work_order.save()

        token = work_order.other_data["token"]
        with pytest.raises(PermissionDenied, match="already been completed"):
            WorkOrderSecurityService.validate_vendor_access(
                work_order.id,
                token
            )

    def test_owner_can_delete_work_order(self, work_order, user1):
        """Test work order owner can delete."""
        result = WorkOrderSecurityService.validate_delete_permission(
            work_order.id,
            user1
        )
        assert result == work_order

    def test_non_owner_cannot_delete(self, work_order, user2):
        """Test non-owner cannot delete work order."""
        with pytest.raises(PermissionDenied):
            WorkOrderSecurityService.validate_delete_permission(
                work_order.id,
                user2
            )

    def test_cannot_delete_in_progress_work_order(self, work_order, user1):
        """Test in-progress work orders cannot be deleted."""
        work_order.workstatus = Wom.Workstatus.INPROGRESS
        work_order.save()

        with pytest.raises(PermissionDenied, match="in progress"):
            WorkOrderSecurityService.validate_delete_permission(
                work_order.id,
                user1
            )

    def test_owner_can_close_work_order(self, work_order, user1):
        """Test work order owner can close."""
        result = WorkOrderSecurityService.validate_close_permission(
            work_order.id,
            user1
        )
        assert result == work_order

    def test_same_tenant_can_close_work_order(self, work_order, user2):
        """Test same-tenant user can close work order."""
        result = WorkOrderSecurityService.validate_close_permission(
            work_order.id,
            user2
        )
        assert result == work_order

    def test_queryset_filtered_by_tenant(
        self, work_order, user2, other_client, user3
    ):
        """Test queryset filtering enforces tenant isolation."""
        # Create work order for other tenant
        other_wo = Wom.objects.create(
            client_id=other_client.id,
            bu_id=1,
            cuser_id=user3.id,
            description="Other Tenant Work Order",
            workstatus=Wom.Workstatus.ASSIGNED,
            other_data={}
        )

        # User2's queryset should only contain their tenant's work orders
        queryset = WorkOrderSecurityService.get_user_work_orders_queryset(user2)
        work_order_ids = list(queryset.values_list('id', flat=True))

        assert work_order.id in work_order_ids
        assert other_wo.id not in work_order_ids

    def test_approver_validation_success(self, work_order):
        """Test authorized approver can access work order."""
        # Create approver
        approver = People.objects.create(
            peoplename="Approver One",
            peoplecode="APP001",
            client_id=work_order.client_id
        )

        # Add approver to work order
        work_order.other_data["wp_approvers"] = [
            {"peoplecode": "APP001", "name": "Approver One"}
        ]
        work_order.save()

        # Validate approver access
        wom, person = WorkOrderSecurityService.validate_approver_access(
            work_order.id,
            approver.id
        )

        assert wom == work_order
        assert person == approver

    def test_unauthorized_approver_denied(self, work_order):
        """Test unauthorized person cannot approve work order."""
        # Create person who is NOT an approver
        unauthorized = People.objects.create(
            peoplename="Random Person",
            peoplecode="RAND001",
            client_id=work_order.client_id
        )

        # Set different approvers in work order
        work_order.other_data["wp_approvers"] = [
            {"peoplecode": "APP001", "name": "Approver One"}
        ]
        work_order.save()

        with pytest.raises(PermissionDenied, match="not authorized to approve"):
            WorkOrderSecurityService.validate_approver_access(
                work_order.id,
                unauthorized.id
            )


@pytest.mark.django_db
class TestIDORProtection:
    """
    Test IDOR (Insecure Direct Object Reference) vulnerability protection.
    
    These tests simulate real-world attack scenarios.
    """

    @pytest.fixture
    def setup_multi_tenant(self):
        """Set up multi-tenant test environment."""
        # Tenant A
        client_a = ClientOffice.objects.create(
            clientofficename="Company A",
            clientcode="COMPA"
        )
        user_a = User.objects.create_user(
            username="usera",
            email="usera@companya.com",
            client_id=client_a.id,
            peoplename="User A"
        )
        wo_a = Wom.objects.create(
            client_id=client_a.id,
            bu_id=1,
            cuser_id=user_a.id,
            description="Company A Work Order",
            workstatus=Wom.Workstatus.ASSIGNED,
            other_data={"token": WorkOrderSecurityService.generate_secure_token()}
        )

        # Tenant B
        client_b = ClientOffice.objects.create(
            clientofficename="Company B",
            clientcode="COMPB"
        )
        user_b = User.objects.create_user(
            username="userb",
            email="userb@companyb.com",
            client_id=client_b.id,
            peoplename="User B"
        )
        wo_b = Wom.objects.create(
            client_id=client_b.id,
            bu_id=1,
            cuser_id=user_b.id,
            description="Company B Work Order",
            workstatus=Wom.Workstatus.ASSIGNED,
            other_data={"token": WorkOrderSecurityService.generate_secure_token()}
        )

        return {
            "user_a": user_a,
            "wo_a": wo_a,
            "user_b": user_b,
            "wo_b": wo_b
        }

    def test_idor_attack_blocked(self, setup_multi_tenant):
        """
        Simulate IDOR attack: User B tries to access User A's work order.
        
        This should be BLOCKED by tenant isolation.
        """
        data = setup_multi_tenant

        # User B attempts to access User A's work order (IDOR attack)
        with pytest.raises(PermissionDenied, match="permission to access"):
            WorkOrderSecurityService.validate_work_order_access(
                data["wo_a"].id,
                data["user_b"],
                allow_tenant_access=True
            )

    def test_token_guessing_attack_blocked(self, setup_multi_tenant):
        """
        Simulate token guessing attack: Attacker tries random tokens.
        
        This should be BLOCKED by token validation.
        """
        data = setup_multi_tenant

        # Attacker tries various fake tokens
        fake_tokens = [
            "fake_token_123",
            "12345678901234567890",
            data["wo_b"].other_data["token"]  # Token from different work order
        ]

        for fake_token in fake_tokens:
            with pytest.raises(PermissionDenied):
                WorkOrderSecurityService.validate_token_access(
                    data["wo_a"].id,
                    fake_token
                )

    def test_parameter_tampering_blocked(self, setup_multi_tenant):
        """
        Simulate parameter tampering: User changes womid in URL.
        
        This should be BLOCKED by authorization checks.
        """
        data = setup_multi_tenant

        # User B has valid session but tampers with womid parameter
        with pytest.raises(PermissionDenied):
            WorkOrderSecurityService.validate_work_order_access(
                data["wo_a"].id,  # Tampered ID (belongs to User A)
                data["user_b"],   # Authenticated as User B
                require_ownership=True
            )
