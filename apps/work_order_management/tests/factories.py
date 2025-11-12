"""
Factory definitions for work_order_management app testing.

Uses factory_boy for generating work orders, vendors, and related data
with realistic defaults and relationships.
"""
import factory
from datetime import datetime, timezone as dt_timezone, timedelta
from django.contrib.gis.geos import Point
from factory.django import DjangoModelFactory
from apps.work_order_management.models import Wom, Vendor, WomDetails, Approver


class BtFactory(DjangoModelFactory):
    """Factory for creating test tenants (business units)."""

    class Meta:
        model = "client_onboarding.Bt"
        django_get_or_create = ("bucode",)

    bucode = factory.Sequence(lambda n: f"WOM{n:03d}")
    buname = factory.LazyAttribute(lambda obj: f"WO Tenant {obj.bucode}")
    enable = True


class LocationFactory(DjangoModelFactory):
    """Factory for creating test locations."""

    class Meta:
        model = "activity.Location"
        django_get_or_create = ("site", "location")

    site = factory.Sequence(lambda n: f"WOSITE{n:03d}")
    location = factory.Sequence(lambda n: f"WO Location {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    gpslocation = factory.LazyFunction(lambda: Point(103.8198, 1.3521))


class AssetFactory(DjangoModelFactory):
    """Factory for creating test assets."""

    class Meta:
        model = "activity.Asset"

    assetname = factory.Sequence(lambda n: f"Asset {n}")
    assetcode = factory.Sequence(lambda n: f"ASSET{n:04d}")
    location = factory.SubFactory(LocationFactory)
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    enable = True


class QuestionSetFactory(DjangoModelFactory):
    """Factory for creating test question sets."""

    class Meta:
        model = "activity.QuestionSet"

    qsetname = factory.Sequence(lambda n: f"Checklist {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    enable = True


class TypeAssistFactory(DjangoModelFactory):
    """Factory for creating TypeAssist entries."""

    class Meta:
        model = "core_onboarding.TypeAssist"

    typename = "VendorType"
    typeval = factory.Sequence(lambda n: f"Vendor Type {n}")
    client = factory.SubFactory(BtFactory)
    enable = True


class VendorFactory(DjangoModelFactory):
    """
    Factory for creating vendor instances.

    Generates realistic vendor data with contact details and GPS location.
    """

    class Meta:
        model = Vendor
        django_get_or_create = ("code", "client")

    code = factory.Sequence(lambda n: f"VEND{n:04d}")
    name = factory.LazyAttribute(lambda obj: f"Vendor {obj.code}")
    type = factory.SubFactory(TypeAssistFactory, typename="VendorType")
    address = factory.Faker("address")
    gpslocation = factory.LazyFunction(lambda: Point(103.8198, 1.3521))
    enable = True
    mobno = factory.Faker("numerify", text="##########")
    email = factory.LazyAttribute(lambda obj: f"{obj.code.lower()}@vendor.example.com")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    show_to_all_sites = False
    description = factory.Faker("sentence")


class PeopleFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = "peoples.People"
        django_get_or_create = ("loginid",)

    peoplecode = factory.Sequence(lambda n: f"WOUSR{n:04d}")
    peoplename = factory.Faker("name")
    loginid = factory.LazyAttribute(lambda obj: obj.peoplename.lower().replace(" ", "_"))
    email = factory.LazyAttribute(lambda obj: f"{obj.loginid}@example.com")
    mobno = factory.Faker("numerify", text="##########")
    password = factory.django.Password("TestPass123!")
    client = factory.SubFactory(BtFactory)
    enable = True


class WomFactory(DjangoModelFactory):
    """
    Factory for creating work order (Wom) instances.

    Generates realistic work orders with proper relationships
    and lifecycle state.
    """

    class Meta:
        model = Wom

    name = factory.Sequence(lambda n: f"Work Order {n}")
    workstatus = "ASSIGNED"
    identifier = "WO"
    asset = factory.SubFactory(AssetFactory)
    location = factory.SubFactory(LocationFactory)
    qset = factory.SubFactory(QuestionSetFactory)
    vendor = factory.SubFactory(VendorFactory)
    priority = factory.Iterator(["LOW", "MEDIUM", "HIGH"])
    plandatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) + timedelta(days=1)
    )
    expirydatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) + timedelta(days=7)
    )
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    gpslocation = factory.LazyFunction(lambda: Point(103.8198, 1.3521))
    workpermit = "NOT_REQUIRED"
    cdby = factory.SubFactory(PeopleFactory)
    mdby = factory.SelfAttribute("cdby")
    other_data = factory.LazyFunction(lambda: {
        "token": None,
        "token_expiration": None,
        "overall_score": None,
        "section_weightage": {},
        "reply_from_vendor": None
    })
    wo_history = factory.LazyFunction(lambda: [])


class WorkPermitFactory(WomFactory):
    """
    Factory for creating work permit (WP) instances.

    Extends WomFactory with work permit specific configuration.
    """

    identifier = "WP"
    workpermit = "REQUIRED"
    priority = "HIGH"
    approvers = factory.LazyFunction(lambda: [])
    verifiers = factory.LazyFunction(lambda: [])


class OverdueWorkOrderFactory(WomFactory):
    """
    Factory for creating overdue work orders for testing escalation.

    Sets expiry date in the past.
    """

    workstatus = "ASSIGNED"
    priority = "HIGH"
    plandatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(days=5)
    )
    expirydatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(days=2)
    )


class CompletedWorkOrderFactory(WomFactory):
    """
    Factory for creating completed work orders.

    Sets status to COMPLETED with realistic start/end times.
    """

    workstatus = "COMPLETED"
    starttime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(hours=4)
    )
    endtime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(hours=1)
    )


class InProgressWorkOrderFactory(WomFactory):
    """
    Factory for creating in-progress work orders.

    Sets status to INPROGRESS with start time.
    """

    workstatus = "INPROGRESS"
    starttime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(hours=2)
    )


class WomDetailsFactory(DjangoModelFactory):
    """
    Factory for creating WomDetails (work order checklist answers).

    Links to work order and question set items.
    """

    class Meta:
        model = WomDetails

    wom = factory.SubFactory(WomFactory)
    # Additional fields depend on WomDetails model structure
    # Placeholder for actual field configuration


class ApproverFactory(DjangoModelFactory):
    """
    Factory for creating Approver instances.

    Manages work permit approval workflow.
    """

    class Meta:
        model = Approver

    wom = factory.SubFactory(WorkPermitFactory)
    people = factory.SubFactory(PeopleFactory)
    approved = False
    # Additional fields depend on Approver model structure
    # Placeholder for actual field configuration
