"""
Shared test fixtures for MQTT tests.

Provides fixtures for:
- Test users (guards, supervisors, managers)
- Test devices
- Test locations and geofences
- Mock MQTT messages
"""

import pytest
from datetime import datetime, timezone as dt_timezone
from django.contrib.gis.geos import Point, Polygon
from django.contrib.auth import get_user_model

from apps.peoples.models import People
from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt
from apps.attendance.models.post import Post
from apps.core_onboarding.models import ApprovedLocation


@pytest.fixture
def test_client(db):
    """Create test client/tenant (Bt model)."""
    client = Bt.objects.create(
        buname="Test Security Company",
        bucode="TSC001",
        enable=True
    )
    return client


@pytest.fixture
def test_supervisor(db, test_client):
    """Create test supervisor user."""
    supervisor = People.objects.create(
        peoplename="John Supervisor",
        email="supervisor@test.com",
        phone="+919876543210",
        bt=test_client,
        active=True
    )
    return supervisor


@pytest.fixture
def test_guard(db, test_client):
    """Create test guard user."""
    guard = People.objects.create(
        peoplename="Mike Guard",
        email="guard@test.com",
        phone="+918765432109",
        bt=test_client,
        active=True
    )
    return guard


@pytest.fixture
def test_post(db, test_client):
    """Create test security post."""
    post = Post.objects.create(
        postname="Main Gate",
        bt=test_client,
        active=True
    )
    return post


@pytest.fixture
def test_geofence(db, test_client, test_post):
    """
    Create test geofence around a location (Bangalore Tech Park).

    Coordinates: 12.9716° N, 77.5946° E (Bangalore)
    Radius: 100 meters
    """
    # Create polygon representing geofence boundary
    center_lat = 12.9716
    center_lon = 77.5946

    # Create simple square geofence (100m x 100m roughly)
    # ~0.001 degrees ≈ 111 meters at equator
    offset = 0.0009  # ~100 meters

    geofence_polygon = Polygon([
        (center_lon - offset, center_lat - offset),  # SW corner
        (center_lon + offset, center_lat - offset),  # SE corner
        (center_lon + offset, center_lat + offset),  # NE corner
        (center_lon - offset, center_lat + offset),  # NW corner
        (center_lon - offset, center_lat - offset),  # Close polygon
    ], srid=4326)

    approved_location = ApprovedLocation.objects.create(
        bt=test_client,
        locationpost=test_post,
        locationname="Tech Park Main Entrance",
        locationcoordinates=geofence_polygon,
        enable=True
    )

    return approved_location


@pytest.fixture
def inside_geofence_coords():
    """Coordinates inside test geofence (Bangalore Tech Park)."""
    return {
        'lat': 12.9716,  # Center of geofence
        'lon': 77.5946
    }


@pytest.fixture
def outside_geofence_coords():
    """Coordinates outside test geofence (1 km away)."""
    return {
        'lat': 12.9800,  # ~1 km north
        'lon': 77.6000
    }


@pytest.fixture
def mock_device_telemetry_message():
    """Mock MQTT device telemetry message."""
    return {
        'device_id': 'device-12345',
        'battery': 85,
        'signal': -60,
        'temperature': 32.5,
        'connectivity': 'ONLINE',
        'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        '_mqtt_metadata': {
            'topic': 'device/device-12345/telemetry',
            'qos': 1,
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': 'localhost'
        }
    }


@pytest.fixture
def mock_panic_button_message(test_guard, inside_geofence_coords):
    """Mock MQTT panic button message."""
    return {
        'alert_type': 'panic',
        'severity': 'critical',
        'message': 'Emergency! Guard pressed panic button',
        'source_id': f"guard-{test_guard.id}",
        'guard_id': test_guard.id,
        'location': inside_geofence_coords,
        'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        '_mqtt_metadata': {
            'topic': f'alert/guard-{test_guard.id}/panic',
            'qos': 2,  # Critical alerts use QoS 2
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': 'localhost'
        }
    }


@pytest.fixture
def mock_gps_message(test_guard, test_client, inside_geofence_coords):
    """Mock MQTT GPS location message."""
    return {
        'guard_id': test_guard.id,
        'client_id': test_client.id,
        'lat': inside_geofence_coords['lat'],
        'lon': inside_geofence_coords['lon'],
        'accuracy': 8.5,
        'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        '_mqtt_metadata': {
            'topic': f'guard/guard-{test_guard.id}/gps',
            'qos': 1,
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': 'localhost'
        }
    }


@pytest.fixture
def mock_geofence_violation_message(test_guard, test_client, outside_geofence_coords):
    """Mock MQTT GPS message with coordinates outside geofence."""
    return {
        'guard_id': test_guard.id,
        'client_id': test_client.id,
        'lat': outside_geofence_coords['lat'],
        'lon': outside_geofence_coords['lon'],
        'accuracy': 12.0,
        'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        '_mqtt_metadata': {
            'topic': f'guard/guard-{test_guard.id}/gps',
            'qos': 1,
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': 'localhost'
        }
    }


@pytest.fixture
def mock_sensor_reading_message():
    """Mock MQTT sensor reading message (door sensor)."""
    return {
        'sensor_id': 'door-sensor-456',
        'type': 'door',
        'state': 'open',
        'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        '_mqtt_metadata': {
            'topic': 'sensor/door-sensor-456/status',
            'qos': 1,
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': 'localhost'
        }
    }


@pytest.fixture
def mock_fire_alarm_message():
    """Mock MQTT fire alarm message (smoke detector)."""
    return {
        'sensor_id': 'smoke-detector-789',
        'type': 'smoke',
        'value': 150,  # Above critical threshold
        'state': 'alarm',
        'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        '_mqtt_metadata': {
            'topic': 'sensor/smoke-detector-789/alarm',
            'qos': 2,  # Critical
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': 'localhost'
        }
    }


@pytest.fixture
def mock_device_alert_message():
    """Mock generic device alert message."""
    return {
        'alert_type': 'equipment_failure',
        'severity': 'high',
        'message': 'Device malfunction detected',
        'source_id': 'device-xyz-789',
        'timestamp': datetime.now(dt_timezone.utc).isoformat(),
        '_mqtt_metadata': {
            'topic': 'alert/device-xyz-789/failure',
            'qos': 2,
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': 'localhost'
        }
    }
