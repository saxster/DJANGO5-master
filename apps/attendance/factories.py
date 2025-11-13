"""
Factory definitions for attendance app testing.

Uses factory_boy for generating PeopleEventlog, Geofence, Post, and related data
with realistic geospatial and biometric verification attributes.

Complies with .claude/rules.md standards.
"""
import factory
from datetime import datetime, timezone as dt_timezone, timedelta, time
from factory.django import DjangoModelFactory
from django.contrib.gis.geos import Point, Polygon
from apps.attendance.models import PeopleEventlog, Geofence
from apps.attendance.models.people_eventlog import peventlog_json


class BtFactory(DjangoModelFactory):
    """Factory for creating test tenants (business units)."""

    class Meta:
        model = "client_onboarding.Bt"
        django_get_or_create = ("bucode",)

    bucode = factory.Sequence(lambda n: f"ATT{n:03d}")
    buname = factory.LazyAttribute(lambda obj: f"Attendance Tenant {obj.bucode}")
    enable = True


class ShiftFactory(DjangoModelFactory):
    """Factory for creating test shifts."""

    class Meta:
        model = "client_onboarding.Shift"

    shiftname = factory.Sequence(lambda n: f"Shift {n}")
    starttime = time(9, 0)
    endtime = time(17, 0)
    client = factory.SubFactory(BtFactory)


class PeopleFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = "peoples.People"
        django_get_or_create = ("loginid",)

    peoplecode = factory.Sequence(lambda n: f"ATTUSR{n:04d}")
    peoplename = factory.Faker("name")
    loginid = factory.LazyAttribute(lambda obj: obj.peoplename.lower().replace(" ", "_"))
    email = factory.LazyAttribute(lambda obj: f"{obj.loginid}@example.com")
    mobno = factory.Faker("numerify", text="##########")
    password = factory.django.Password("TestPass123!")
    client = factory.SubFactory(BtFactory)
    enable = True


class TypeAssistFactory(DjangoModelFactory):
    """Factory for creating TypeAssist entries (event types)."""

    class Meta:
        model = "core_onboarding.TypeAssist"

    typename = "EventType"
    typeval = factory.Sequence(lambda n: f"Event Type {n}")
    client = factory.SubFactory(BtFactory)
    enable = True


class GeofenceFactory(DjangoModelFactory):
    """
    Factory for creating Geofence instances.

    Generates realistic geofences with:
    - Polygon or circle boundaries
    - GPS coordinates
    - Hysteresis buffer for boundary flapping prevention
    """

    class Meta:
        model = Geofence

    name = factory.Sequence(lambda n: f"Geofence {n}")
    geofence_type = Geofence.GeofenceType.CIRCLE
    center_point = factory.LazyFunction(lambda: Point(103.8198, 1.3521))  # Singapore coordinates
    radius = factory.Faker("pyfloat", min_value=50.0, max_value=500.0, right_digits=1)
    hysteresis_meters = 1.0
    bu = factory.SubFactory(BtFactory)
    client = factory.SelfAttribute("bu")
    is_active = True
    description = factory.Faker("sentence")
    tenant = factory.LazyAttribute(lambda obj: obj.bu.bucode if obj.bu else "default")


class PolygonGeofenceFactory(GeofenceFactory):
    """Factory for creating polygon-based geofences."""

    geofence_type = Geofence.GeofenceType.POLYGON
    boundary = factory.LazyFunction(lambda: Polygon((
        (103.8198, 1.3521),
        (103.8208, 1.3521),
        (103.8208, 1.3531),
        (103.8198, 1.3531),
        (103.8198, 1.3521),
    )))
    center_point = None
    radius = None


class PeopleEventlogFactory(DjangoModelFactory):
    """
    Factory for creating PeopleEventlog (attendance record) instances.

    Generates realistic attendance records with:
    - Geospatial validation (GPS coordinates, geofences)
    - Biometric verification (face recognition)
    - Post assignment tracking
    - Fraud detection scoring
    - Transport mode tracking
    """

    class Meta:
        model = PeopleEventlog

    people = factory.SubFactory(PeopleFactory)
    client = factory.LazyAttribute(lambda obj: obj.people.client)
    bu = factory.SelfAttribute("client")
    shift = factory.SubFactory(ShiftFactory, client=factory.SelfAttribute("..client"))
    geofence = factory.SubFactory(GeofenceFactory, bu=factory.SelfAttribute("..bu"))
    peventtype = factory.SubFactory(TypeAssistFactory, client=factory.SelfAttribute("..client"))
    tenant = factory.LazyAttribute(lambda obj: obj.client)

    # Date and time fields
    datefor = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc).date())
    punchintime = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc).replace(hour=9, minute=0))
    punchouttime = factory.LazyAttribute(
        lambda obj: obj.punchintime + timedelta(hours=8) if obj.punchintime else None
    )

    # GPS locations
    startlocation = factory.LazyFunction(lambda: Point(103.8198, 1.3521))
    endlocation = factory.LazyAttribute(
        lambda obj: Point(
            103.8198 + factory.Faker("pyfloat", min_value=-0.01, max_value=0.01).evaluate(None, None, {}),
            1.3521 + factory.Faker("pyfloat", min_value=-0.01, max_value=0.01).evaluate(None, None, {})
        )
    )

    # Distance and duration
    distance = factory.Faker("pyfloat", min_value=0.5, max_value=50.0, right_digits=2)
    duration = factory.Faker("random_int", min=240, max=600)  # 4-10 hours in minutes
    accuracy = factory.Faker("pyfloat", min_value=5.0, max_value=50.0, right_digits=1)

    # Device info
    deviceid = factory.Faker("uuid4")

    # Face recognition flags
    facerecognitionin = True
    facerecognitionout = True

    # Encrypted JSON field with biometric verification data
    peventlogextras = factory.LazyFunction(lambda: {
        **peventlog_json(),
        "verified_in": True,
        "distance_in": factory.Faker("pyfloat", min_value=0.1, max_value=0.9, right_digits=2).evaluate(None, None, {}),
        "verified_out": True,
        "distance_out": factory.Faker("pyfloat", min_value=0.1, max_value=0.9, right_digits=2).evaluate(None, None, {}),
        "threshold": "0.3",
        "model": "Facenet512",
        "similarity_metric": "cosine",
        "verification_attempts": 1,
        "error_logs": []
    })

    # Transport modes
    transportmodes = factory.LazyFunction(lambda: [
        factory.Iterator([
            PeopleEventlog.TransportMode.BUS,
            PeopleEventlog.TransportMode.TRAIN,
            PeopleEventlog.TransportMode.CAR,
            PeopleEventlog.TransportMode.BIKE,
        ]).evaluate(None, None, {})
    ])

    # Remarks
    remarks = factory.Faker("sentence")

    # Fraud detection (Phase 2.1)
    fraud_score = factory.Faker("pyfloat", min_value=0.0, max_value=0.3, right_digits=3)  # Low fraud
    fraud_risk_level = "MINIMAL"
    fraud_anomalies = factory.LazyFunction(list)

    # Archival flags
    is_archived = False
    gps_purged = False


class CompletedAttendanceFactory(PeopleEventlogFactory):
    """Factory for creating completed attendance records with punch-out."""

    punchintime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc).replace(hour=9, minute=0) - timedelta(hours=10)
    )
    punchouttime = factory.LazyAttribute(
        lambda obj: obj.punchintime + timedelta(hours=8)
    )
    duration = 480  # 8 hours


class OngoingAttendanceFactory(PeopleEventlogFactory):
    """Factory for creating ongoing attendance records (no punch-out yet)."""

    punchintime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(hours=2)
    )
    punchouttime = None
    endlocation = None
    duration = None


class HighFraudAttendanceFactory(PeopleEventlogFactory):
    """Factory for creating attendance records with high fraud scores."""

    fraud_score = factory.Faker("pyfloat", min_value=0.7, max_value=1.0, right_digits=3)
    fraud_risk_level = "HIGH"
    fraud_anomalies = factory.LazyFunction(lambda: [
        {
            "type": "unusual_location",
            "severity": "high",
            "details": "Check-in location far from assigned geofence"
        },
        {
            "type": "velocity_impossible",
            "severity": "critical",
            "details": "Travel speed between locations exceeds human capability"
        }
    ])
    fraud_analyzed_at = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc))


class ArchivedAttendanceFactory(PeopleEventlogFactory):
    """Factory for creating archived attendance records (>2 years old)."""

    datefor = factory.LazyFunction(
        lambda: (datetime.now(dt_timezone.utc) - timedelta(days=800)).date()
    )
    punchintime = factory.LazyFunction(
        lambda: datetime.now(dt_timezone.utc) - timedelta(days=800)
    )
    punchouttime = factory.LazyAttribute(
        lambda obj: obj.punchintime + timedelta(hours=8)
    )
    is_archived = True
    archived_at = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc) - timedelta(days=30))
    gps_purged = True
    gps_purged_at = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc) - timedelta(days=700))
    startlocation = None  # GPS purged
    endlocation = None


class FailedBiometricAttendanceFactory(PeopleEventlogFactory):
    """Factory for creating attendance records with failed biometric verification."""

    facerecognitionin = False
    facerecognitionout = False
    peventlogextras = factory.LazyFunction(lambda: {
        **peventlog_json(),
        "verified_in": False,
        "distance_in": None,
        "verified_out": False,
        "distance_out": None,
        "verification_attempts": 5,  # Max attempts
        "error_logs": [
            f"{datetime.now(dt_timezone.utc).isoformat()}: Face not detected",
            f"{datetime.now(dt_timezone.utc).isoformat()}: Low confidence score",
            f"{datetime.now(dt_timezone.utc).isoformat()}: Multiple faces detected"
        ]
    })


__all__ = [
    'PeopleEventlogFactory',
    'CompletedAttendanceFactory',
    'OngoingAttendanceFactory',
    'HighFraudAttendanceFactory',
    'ArchivedAttendanceFactory',
    'FailedBiometricAttendanceFactory',
    'GeofenceFactory',
    'PolygonGeofenceFactory',
    'BtFactory',
    'PeopleFactory',
    'ShiftFactory',
    'TypeAssistFactory',
]
