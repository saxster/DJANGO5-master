"""
Factory definitions for peoples app testing.

Uses factory_boy for generating test data with realistic defaults
and relationships. Complies with .claude/rules.md standards.
"""
import factory
from datetime import datetime, timezone as dt_timezone, timedelta
from django.contrib.auth.hashers import make_password
from factory.django import DjangoModelFactory
from apps.peoples.models import (
    People,
    PeopleProfile,
    PeopleOrganizational,
    Pgroup,
    Pgbelonging,
    Capability
)


class BtFactory(DjangoModelFactory):
    """Factory for creating test tenants (business units)."""

    class Meta:
        model = "client_onboarding.Bt"
        django_get_or_create = ("bucode",)

    bucode = factory.Sequence(lambda n: f"TENANT{n:03d}")
    buname = factory.LazyAttribute(lambda obj: f"Test Tenant {obj.bucode}")
    enable = True


class LocationFactory(DjangoModelFactory):
    """Factory for creating test locations."""

    class Meta:
        model = "activity.Location"
        django_get_or_create = ("site", "location")

    site = factory.Sequence(lambda n: f"SITE{n:03d}")
    location = factory.Sequence(lambda n: f"Location {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")


class TypeAssistFactory(DjangoModelFactory):
    """Factory for creating TypeAssist entries (departments, designations)."""

    class Meta:
        model = "core_onboarding.TypeAssist"

    typename = "Department"
    typeval = factory.Sequence(lambda n: f"Department {n}")
    client = factory.SubFactory(BtFactory)
    enable = True


class PeopleFactory(DjangoModelFactory):
    """
    Factory for creating People (user) instances.

    Generates realistic user data with proper encryption for PII fields.
    Password defaults to 'TestPass123!' for all test users.
    """

    class Meta:
        model = People
        django_get_or_create = ("loginid",)

    peoplecode = factory.Sequence(lambda n: f"USR{n:04d}")
    peoplename = factory.Faker("name")
    loginid = factory.LazyAttribute(lambda obj: obj.peoplename.lower().replace(" ", "_"))
    email = factory.LazyAttribute(lambda obj: f"{obj.loginid}@example.com")
    mobno = factory.Faker("numerify", text="##########")
    password = factory.LazyFunction(lambda: make_password("TestPass123!"))
    client = factory.SubFactory(BtFactory)
    enable = True
    is_active = True
    is_staff = False
    is_superuser = False

    # Capabilities with default values
    capabilities = factory.LazyFunction(lambda: {
        "webcapability": [],
        "mobilecapability": [],
        "portletcapability": [],
        "reportcapability": [],
        "noccapability": [],
        "debug": False,
        "blacklist": False
    })


class PeopleProfileFactory(DjangoModelFactory):
    """
    Factory for creating PeopleProfile instances.

    Auto-creates associated People instance if not provided.
    Generates realistic demographic and employment data.
    """

    class Meta:
        model = PeopleProfile

    people = factory.SubFactory(PeopleFactory)
    gender = factory.Iterator(["Male", "Female", "Non-binary", "Prefer not to say"])
    dateofbirth = factory.LazyFunction(
        lambda: (datetime.now(dt_timezone.utc) - timedelta(days=365 * 30)).date()
    )
    dateofjoin = factory.LazyFunction(
        lambda: (datetime.now(dt_timezone.utc) - timedelta(days=365 * 2)).date()
    )
    dateofreport = factory.LazyAttribute(lambda obj: obj.dateofjoin)
    peopleimg = "master/people/blank.png"


class PeopleOrganizationalFactory(DjangoModelFactory):
    """
    Factory for creating PeopleOrganizational instances.

    Auto-creates associated People instance if not provided.
    Sets up organizational hierarchy with location, department, designation.
    """

    class Meta:
        model = PeopleOrganizational

    people = factory.SubFactory(PeopleFactory)
    location = factory.SubFactory(LocationFactory)
    department = factory.SubFactory(
        TypeAssistFactory,
        typename="Department"
    )
    designation = factory.SubFactory(
        TypeAssistFactory,
        typename="Designation",
        typeval=factory.Sequence(lambda n: f"Designation {n}")
    )
    peopletype = factory.SubFactory(
        TypeAssistFactory,
        typename="PeopleType",
        typeval="Employee"
    )
    worktype = factory.SubFactory(
        TypeAssistFactory,
        typename="WorkType",
        typeval="Full-time"
    )
    reportto = None  # Can be set explicitly for manager relationships


class PgroupFactory(DjangoModelFactory):
    """Factory for creating permission groups."""

    class Meta:
        model = Pgroup
        django_get_or_create = ("groupcode",)

    groupname = factory.Sequence(lambda n: f"Group {n}")
    groupcode = factory.Sequence(lambda n: f"GRP{n:03d}")
    description = factory.LazyAttribute(lambda obj: f"Description for {obj.groupname}")
    client = factory.SubFactory(BtFactory)


class PgbelongingFactory(DjangoModelFactory):
    """Factory for creating group memberships."""

    class Meta:
        model = Pgbelonging

    groupid = factory.SubFactory(PgroupFactory)
    peopleid = factory.SubFactory(PeopleFactory)


class CapabilityFactory(DjangoModelFactory):
    """Factory for creating capability definitions."""

    class Meta:
        model = Capability
        django_get_or_create = ("capability_name",)

    capability_name = factory.Sequence(lambda n: f"feature_{n}")
    category = factory.Iterator(["core", "advanced", "admin", "api"])
    display_name = factory.LazyAttribute(
        lambda obj: obj.capability_name.replace("_", " ").title()
    )
    description = factory.LazyAttribute(
        lambda obj: f"Description for {obj.display_name}"
    )
    is_active = True


class CompleteUserFactory(PeopleFactory):
    """
    Factory that creates a complete user with profile and organizational data.

    Convenience factory for tests requiring fully populated user objects.
    Creates People + PeopleProfile + PeopleOrganizational in one call.
    """

    profile = factory.RelatedFactory(
        PeopleProfileFactory,
        factory_related_name="people"
    )
    organizational = factory.RelatedFactory(
        PeopleOrganizationalFactory,
        factory_related_name="people"
    )


class AdminUserFactory(PeopleFactory):
    """Factory for creating admin/superuser instances."""

    is_staff = True
    is_superuser = True
    peoplecode = factory.Sequence(lambda n: f"ADM{n:04d}")
    peoplename = factory.Faker("name")


class ManagerUserFactory(CompleteUserFactory):
    """
    Factory for creating manager users with supervisory capabilities.

    Sets appropriate organizational designation and permissions.
    """

    organizational = factory.RelatedFactory(
        PeopleOrganizationalFactory,
        factory_related_name="people",
        designation__typeval="Manager"
    )
