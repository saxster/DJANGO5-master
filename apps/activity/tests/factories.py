"""
Factory definitions for activity app testing.

Uses factory_boy for generating Jobs, Jobneeds, Assets, and related data
with realistic defaults and relationships.
"""
import factory
from datetime import datetime, timezone as dt_timezone, timedelta
from django.contrib.gis.geos import Point, LineString
from factory.django import DjangoModelFactory


class BtFactory(DjangoModelFactory):
    """Factory for creating test tenants (business units)."""

    class Meta:
        model = "client_onboarding.Bt"
        django_get_or_create = ("bucode",)

    bucode = factory.Sequence(lambda n: f"ACT{n:03d}")
    buname = factory.LazyAttribute(lambda obj: f"Activity Tenant {obj.bucode}")
    enable = True


class LocationFactory(DjangoModelFactory):
    """Factory for creating test locations."""

    class Meta:
        model = "activity.Location"
        django_get_or_create = ("site", "location")

    site = factory.Sequence(lambda n: f"ACTSITE{n:03d}")
    location = factory.Sequence(lambda n: f"Activity Location {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    gpslocation = factory.LazyFunction(lambda: Point(103.8198, 1.3521))


class TypeAssistFactory(DjangoModelFactory):
    """Factory for creating TypeAssist entries."""

    class Meta:
        model = "core_onboarding.TypeAssist"

    typename = "AssetType"
    typeval = factory.Sequence(lambda n: f"Type {n}")
    client = factory.SubFactory(BtFactory)
    enable = True


class QuestionSetFactory(DjangoModelFactory):
    """Factory for creating question sets."""

    class Meta:
        model = "activity.QuestionSet"

    qsetname = factory.Sequence(lambda n: f"Checklist {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    enable = True


class PeopleFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = "peoples.People"
        django_get_or_create = ("loginid",)

    peoplecode = factory.Sequence(lambda n: f"ACTUSR{n:04d}")
    peoplename = factory.Faker("name")
    loginid = factory.LazyAttribute(lambda obj: obj.peoplename.lower().replace(" ", "_"))
    email = factory.LazyAttribute(lambda obj: f"{obj.loginid}@example.com")
    mobno = factory.Faker("numerify", text="##########")
    password = factory.django.Password("TestPass123!")
    client = factory.SubFactory(BtFactory)
    enable = True


class AssetFactory(DjangoModelFactory):
    """
    Factory for creating asset instances.

    Generates realistic assets with GPS location and taxonomy.
    """

    class Meta:
        model = "activity.Asset"
        django_get_or_create = ("assetcode", "client")

    assetname = factory.Sequence(lambda n: f"Asset {n}")
    assetcode = factory.Sequence(lambda n: f"ASSET{n:04d}")
    location = factory.SubFactory(LocationFactory)
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    type = factory.SubFactory(TypeAssistFactory, typename="AssetType")
    category = factory.SubFactory(TypeAssistFactory, typename="AssetCategory", typeval="General")
    enable = True
    gpslocation = factory.LazyFunction(lambda: Point(103.8198, 1.3521))
    runningstatus = "WORKING"
    iscritical = False
    asset_json = factory.LazyFunction(lambda: {
        "service": "",
        "ismeter": False,
        "meter": "",
        "bill_val": 0.0,
        "supplier": "",
        "msn": "",
        "purchase_date": "",
        "model": "",
        "multifactor": 1,
        "is_nonengg_asset": False
    })


class CriticalAssetFactory(AssetFactory):
    """Factory for creating critical assets."""

    iscritical = True
    runningstatus = "WORKING"


class JobFactory(DjangoModelFactory):
    """
    Factory for creating Job (task template) instances.

    Generates realistic jobs with scheduling and relationships.
    """

    class Meta:
        model = "activity.Job"

    jobname = factory.Sequence(lambda n: f"Job {n}")
    asset = factory.SubFactory(AssetFactory)
    qset = factory.SubFactory(QuestionSetFactory)
    location = factory.SubFactory(LocationFactory)
    startdate = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc).date())
    enddate = factory.LazyFunction(
        lambda: (datetime.now(dt_timezone.utc) + timedelta(days=365)).date()
    )
    starttime = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc).time())
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    identifier = "TASK"
    enable = True
    cdby = factory.SubFactory(PeopleFactory)
    mdby = factory.SelfAttribute("cdby")
    other_info = factory.LazyFunction(lambda: {
        "tour_frequency": 1,
        "is_randomized": False,
        "distance": None,
        "breaktime": 0,
        "deviation": False
    })


class TourJobFactory(JobFactory):
    """
    Factory for creating tour jobs (parent jobs with checkpoints).

    Tours have parent=NULL and identifier=TOUR.
    """

    identifier = "TOUR"
    parent = None
    asset = None  # Tours don't have specific assets


class CheckpointJobFactory(JobFactory):
    """
    Factory for creating checkpoint jobs (children of tours).

    Checkpoints have parent=tour_job.
    """

    parent = factory.SubFactory(TourJobFactory)
    identifier = "TASK"


class JobneedFactory(DjangoModelFactory):
    """
    Factory for creating Jobneed (job instance) instances.

    Generates realistic jobneed executions linked to jobs.
    """

    class Meta:
        model = "activity.Jobneed"

    jobname = factory.LazyAttribute(lambda obj: f"{obj.job.jobname} - Instance")
    job = factory.SubFactory(JobFactory)
    jobdate = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc).date())
    startdatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) + timedelta(hours=1)
    )
    enddatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) + timedelta(hours=2)
    )
    jobstatus = "ASSIGNED"
    client = factory.LazyAttribute(lambda obj: obj.job.client)
    bu = factory.LazyAttribute(lambda obj: obj.job.bu)
    cdby = factory.SubFactory(PeopleFactory)
    mdby = factory.SelfAttribute("cdby")


class CompletedJobneedFactory(JobneedFactory):
    """Factory for creating completed jobneeds."""

    jobstatus = "COMPLETED"
    actualstartdatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(hours=2)
    )
    actualenddatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(hours=1)
    )
    startdatetime = factory.LazyAttribute(lambda obj: obj.actualstartdatetime)
    enddatetime = factory.LazyAttribute(lambda obj: obj.actualenddatetime)


class InProgressJobneedFactory(JobneedFactory):
    """Factory for creating in-progress jobneeds."""

    jobstatus = "INPROGRESS"
    actualstartdatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(minutes=30)
    )


class OverdueJobneedFactory(JobneedFactory):
    """Factory for creating overdue jobneeds."""

    jobstatus = "ASSIGNED"
    startdatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(days=2)
    )
    enddatetime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(days=1)
    )


class JobneedDetailsFactory(DjangoModelFactory):
    """
    Factory for creating JobneedDetails (checklist answers).

    Links to jobneed and question.
    """

    class Meta:
        model = "activity.JobneedDetails"

    jobneed = factory.SubFactory(JobneedFactory)
    seqno = factory.Sequence(lambda n: n + 1)
    # Additional fields depend on JobneedDetails model structure
    # Placeholder for actual field configuration


class AssetLogFactory(DjangoModelFactory):
    """
    Factory for creating AssetLog (audit trail) entries.

    Tracks asset state changes and maintenance history.
    """

    class Meta:
        model = "activity.AssetLog"

    asset = factory.SubFactory(AssetFactory)
    action = factory.Iterator(["CREATE", "UPDATE", "MAINTENANCE", "STATUS_CHANGE"])
    description = factory.Faker("sentence")
    cdby = factory.SubFactory(PeopleFactory)
    # Additional fields depend on AssetLog model structure
