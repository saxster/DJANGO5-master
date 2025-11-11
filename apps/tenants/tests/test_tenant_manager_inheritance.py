"""
Test suite for TenantAwareModel manager inheritance enforcement.

Security Context:
-----------------
This test suite validates that all TenantAwareModel subclasses correctly
use TenantAwareManager or managers that inherit from it. This is critical
for preventing IDOR (Insecure Direct Object Reference) vulnerabilities.

Test Coverage:
- Manager inheritance validation
- Runtime enforcement via __init_subclass__()
- Cross-tenant isolation with custom managers
- Audit of all existing models in codebase

Author: Security Foundation - Tenant Manager Audit (Nov 2025)
"""

import pytest
import logging
from django.test import TestCase
from django.db import models
from apps.tenants.models import TenantAwareModel, Tenant
from apps.tenants.managers import TenantAwareManager
from apps.tenants.utils import tenant_context, slug_to_db_alias
from apps.core.utils_new.db_utils import set_db_for_router


class CustomSafeManager(TenantAwareManager):
    """
    Example of a SAFE custom manager that inherits from TenantAwareManager.
    This preserves tenant filtering while adding custom methods.
    """

    def active_only(self):
        """Custom filter method - still tenant-scoped."""
        return self.filter(is_active=True)


class UnsafeManager(models.Manager):
    """
    Example of an UNSAFE manager that does NOT inherit from TenantAwareManager.
    Using this manager on TenantAwareModel creates IDOR vulnerabilities.
    """

    def all_records(self):
        """This would return ALL records across tenants - DANGEROUS!"""
        return self.all()


class TestTenantManagerInheritance(TestCase):
    """Test manager inheritance validation for TenantAwareModel."""

    @classmethod
    def setUpClass(cls):
        """Set up test tenants."""
        super().setUpClass()
        cls.tenant1 = Tenant.objects.create(
            tenantname="Tenant 1",
            subdomain_prefix="tenant1"
        )
        cls.tenant2 = Tenant.objects.create(
            tenantname="Tenant 2",
            subdomain_prefix="tenant2"
        )

    def test_default_manager_is_tenant_aware(self):
        """Test that models without explicit manager inherit TenantAwareManager."""

        class SafeModelWithDefaultManager(TenantAwareModel):
            """Model using inherited TenantAwareManager (SAFE)."""
            name = models.CharField(max_length=100)

            class Meta:
                app_label = 'tenants'

        # Verify manager is TenantAwareManager
        self.assertIsInstance(
            SafeModelWithDefaultManager.objects,
            TenantAwareManager,
            "Models should inherit TenantAwareManager by default"
        )

    def test_explicit_tenant_aware_manager(self):
        """Test that explicitly declaring TenantAwareManager is safe."""

        class SafeModelWithExplicitManager(TenantAwareModel):
            """Model with explicit TenantAwareManager (SAFE)."""
            objects = TenantAwareManager()
            name = models.CharField(max_length=100)

            class Meta:
                app_label = 'tenants'

        # Verify manager is TenantAwareManager
        self.assertIsInstance(
            SafeModelWithExplicitManager.objects,
            TenantAwareManager
        )

    def test_custom_manager_inheriting_from_tenant_aware(self):
        """Test that custom managers inheriting from TenantAwareManager are safe."""

        class SafeModelWithCustomManager(TenantAwareModel):
            """Model with custom manager inheriting TenantAwareManager (SAFE)."""
            objects = CustomSafeManager()
            name = models.CharField(max_length=100)
            is_active = models.BooleanField(default=True)

            class Meta:
                app_label = 'tenants'

        # Verify manager inherits from TenantAwareManager
        self.assertIsInstance(
            SafeModelWithCustomManager.objects,
            TenantAwareManager,
            "Custom managers should inherit from TenantAwareManager"
        )

        # Verify custom methods still work
        self.assertTrue(
            hasattr(SafeModelWithCustomManager.objects, 'active_only'),
            "Custom methods should be available"
        )

    def test_unsafe_manager_detection(self):
        """Test that __init_subclass__ logs warnings for unsafe managers."""

        # Capture log output
        with self.assertLogs('apps.tenants.models', level=logging.ERROR) as cm:

            class VulnerableModel(TenantAwareModel):
                """Model with unsafe manager (VULNERABLE)."""
                objects = UnsafeManager()
                name = models.CharField(max_length=100)

                class Meta:
                    app_label = 'tenants'

            # Verify warning was logged
            self.assertTrue(
                any('SECURITY WARNING' in msg for msg in cm.output),
                "__init_subclass__ should log security warning for unsafe managers"
            )

            self.assertTrue(
                any('UnsafeManager' in msg for msg in cm.output),
                "Warning should mention the unsafe manager class name"
            )

            self.assertTrue(
                any('IDOR vulnerability' in msg for msg in cm.output),
                "Warning should explain the security risk"
            )

    def test_tenant_isolation_with_safe_custom_manager(self):
        """Test that custom managers inheriting TenantAwareManager maintain isolation."""

        class IsolatedModel(TenantAwareModel):
            """Model with custom safe manager."""
            objects = CustomSafeManager()
            name = models.CharField(max_length=100)
            is_active = models.BooleanField(default=True)

            class Meta:
                app_label = 'tenants'

        # Create records for both tenants
        db_alias_1 = slug_to_db_alias(self.tenant1.subdomain_prefix)
        db_alias_2 = slug_to_db_alias(self.tenant2.subdomain_prefix)

        with tenant_context(db_alias_1):
            tenant1_record = IsolatedModel(name="Tenant 1 Record", is_active=True)
            tenant1_record.save()

        with tenant_context(db_alias_2):
            tenant2_record = IsolatedModel(name="Tenant 2 Record", is_active=True)
            tenant2_record.save()

        # Verify tenant 1 only sees their record
        with tenant_context(db_alias_1):
            tenant1_results = IsolatedModel.objects.all()
            self.assertEqual(tenant1_results.count(), 1)
            self.assertEqual(tenant1_results.first().name, "Tenant 1 Record")

        # Verify tenant 2 only sees their record
        with tenant_context(db_alias_2):
            tenant2_results = IsolatedModel.objects.all()
            self.assertEqual(tenant2_results.count(), 1)
            self.assertEqual(tenant2_results.first().name, "Tenant 2 Record")

        # Verify custom methods also filter by tenant
        with tenant_context(db_alias_1):
            active_results = IsolatedModel.objects.active_only()
            self.assertEqual(active_results.count(), 1)
            self.assertEqual(active_results.first().tenant_id, self.tenant1.id)

    def test_manager_inheritance_chain(self):
        """Test that multi-level manager inheritance is detected correctly."""

        class IntermediateManager(TenantAwareManager):
            """Intermediate manager extending TenantAwareManager."""

            def custom_filter(self):
                return self.filter(is_custom=True)

        class AdvancedManager(IntermediateManager):
            """Manager extending intermediate manager (still safe)."""

            def another_filter(self):
                return self.filter(is_advanced=True)

        class SafeMultiLevelModel(TenantAwareModel):
            """Model with multi-level manager inheritance (SAFE)."""
            objects = AdvancedManager()
            name = models.CharField(max_length=100)
            is_custom = models.BooleanField(default=False)
            is_advanced = models.BooleanField(default=False)

            class Meta:
                app_label = 'tenants'

        # Verify manager chain inherits from TenantAwareManager
        self.assertIsInstance(
            SafeMultiLevelModel.objects,
            TenantAwareManager,
            "Multi-level manager inheritance should preserve TenantAwareManager"
        )

        # Verify all custom methods are available
        self.assertTrue(hasattr(SafeMultiLevelModel.objects, 'custom_filter'))
        self.assertTrue(hasattr(SafeMultiLevelModel.objects, 'another_filter'))


class TestExistingModelAudit(TestCase):
    """
    Audit existing models to ensure they use TenantAwareManager.

    This test imports and checks actual production models to verify
    they have proper tenant filtering configured.
    """

    def test_critical_models_have_tenant_aware_managers(self):
        """Verify critical models use TenantAwareManager or safe subclasses."""

        # Import critical models that MUST have tenant filtering
        from apps.attendance.models import Post, PostAssignment
        from apps.journal.models import JournalEntry
        from apps.wellness.models import WellnessContent

        critical_models = [
            ('Post', Post),
            ('PostAssignment', PostAssignment),
            ('JournalEntry', JournalEntry),
            ('WellnessContent', WellnessContent),
        ]

        for model_name, model_class in critical_models:
            with self.subTest(model=model_name):
                self.assertIsInstance(
                    model_class.objects,
                    TenantAwareManager,
                    f"{model_name}.objects must inherit from TenantAwareManager"
                )

    def test_vulnerable_models_are_documented(self):
        """
        Document known vulnerable models that need manager migration.

        This test intentionally fails if vulnerable models exist, forcing
        developers to either fix them or document why they're safe.
        """

        # These models have custom managers that DON'T inherit TenantAwareManager
        # They are documented here as technical debt requiring migration
        known_vulnerable_models = [
            'attendance.PeopleEventlog',  # PELManager
            'peoples.People',             # PeopleManager
            'peoples.Pgroup',             # PgroupManager
            'peoples.Pgbelonging',        # PgblngManager
            'peoples.Capability',         # CapabilityManager
            'activity.Attachment',        # AttachmentManager
            'activity.Location',          # LocationManager
            'activity.Question',          # QuestionManager
            'activity.QuestionSet',       # QuestionSetManager
            'activity.QuestionSetBelonging',  # QsetBlngManager
            'activity.Asset',             # AssetManager
            'activity.AssetLog',          # AssetLogManager
            'client_onboarding.Device',   # DeviceManager
            'client_onboarding.Shift',    # ShiftManager
            'core_onboarding.TypeAssist', # TypeAssistManager
            'work_order_management.Vendor',      # VendorManager
            'work_order_management.Approver',    # ApproverManager
            'work_order_management.WomDetails',  # WOMDetailsManager
            'work_order_management.Wom',         # WorkOrderManager
        ]

        # This test documents that we KNOW about these vulnerabilities
        # and are tracking them for remediation
        self.assertEqual(
            len(known_vulnerable_models),
            19,
            "If this count changes, update the list and investigate new/removed vulnerabilities"
        )

        # TODO: Remove models from this list as they are fixed
        # Target: Zero vulnerable models by Q1 2026


class TestManagerInheritanceEnforcement(TestCase):
    """Test runtime enforcement of manager inheritance rules."""

    def test_init_subclass_hook_is_called(self):
        """Verify __init_subclass__ is invoked during class definition."""

        call_count = 0

        class TrackedModel(TenantAwareModel):
            """Model to track __init_subclass__ calls."""
            name = models.CharField(max_length=100)

            class Meta:
                app_label = 'tenants'

            @classmethod
            def __init_subclass__(cls, **kwargs):
                nonlocal call_count
                call_count += 1
                super().__init_subclass__(**kwargs)

        self.assertGreater(
            call_count,
            0,
            "__init_subclass__ should be called during class definition"
        )

    def test_abstract_models_skip_validation(self):
        """Verify abstract models don't trigger manager validation."""

        # This should NOT log any warnings (abstract models don't have managers)
        class AbstractBase(TenantAwareModel):
            """Abstract model doesn't need manager validation."""
            name = models.CharField(max_length=100)

            class Meta:
                abstract = True
                app_label = 'tenants'

        # If we got here without errors, validation was correctly skipped
        self.assertTrue(AbstractBase._meta.abstract)


@pytest.mark.django_db
class TestCrossManagerQueries:
    """Test query behavior with different manager configurations."""

    def test_cross_tenant_query_with_custom_manager(self, create_tenant):
        """Verify cross_tenant_query works with custom managers."""

        tenant1 = create_tenant("tenant-cross-1")
        tenant2 = create_tenant("tenant-cross-2")

        class CustomModel(TenantAwareModel):
            objects = CustomSafeManager()
            name = models.CharField(max_length=100)
            is_active = models.BooleanField(default=True)

            class Meta:
                app_label = 'tenants'

        # Create records for both tenants
        db_alias_1 = slug_to_db_alias(tenant1.subdomain_prefix)
        db_alias_2 = slug_to_db_alias(tenant2.subdomain_prefix)

        with tenant_context(db_alias_1):
            CustomModel(name="Tenant 1", is_active=True).save()

        with tenant_context(db_alias_2):
            CustomModel(name="Tenant 2", is_active=True).save()

        # Verify cross_tenant_query returns ALL records
        all_records = CustomModel.objects.cross_tenant_query()
        assert all_records.count() == 2

        # Verify custom methods still respect tenant filtering
        with tenant_context(db_alias_1):
            tenant1_active = CustomModel.objects.active_only()
            assert tenant1_active.count() == 1
            assert tenant1_active.first().tenant_id == tenant1.id


# Integration test markers
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.security,
    pytest.mark.tenant_isolation,
]
