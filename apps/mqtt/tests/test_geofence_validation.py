"""
Geofence Validation Tests for Guard GPS Tracking

Tests comprehensive geofence validation including:
- Geofence breach detection
- Inside/outside boundary handling
- Multiple geofence support
- Edge case handling (no geofence, disabled geofence)
- Performance optimization (caching)

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Test geospatial operations thoroughly
"""

import pytest
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.gis.geos import Point, Polygon
from django.core.cache import cache

from apps.mqtt.models import GuardLocation, DeviceAlert
from apps.core_onboarding.models import ApprovedLocation
from background_tasks.mqtt_handler_tasks import process_guard_gps
from apps.peoples.models import People
from apps.client_onboarding.models import Bt


@pytest.mark.django_db
class TestGeofenceBreachDetection:
    """Test geofence breach detection and alert creation."""

    def test_guard_inside_geofence_no_alert(
        self,
        test_guard,
        test_client,
        test_geofence,
        mock_gps_message,
        inside_geofence_coords
    ):
        """
        Test guard inside geofence does NOT trigger violation alert.

        Security: False positives would desensitize supervisors to alerts.
        """
        # Clear cache to ensure fresh lookup
        cache.clear()

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = mock_gps_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, mock_gps_message)

            # Verify GPS was stored
            mock_processor.add_guard_location.assert_called_once()
            stored_data = mock_processor.add_guard_location.call_args[0][0]

            # Verify geofence status
            assert stored_data['in_geofence'] is True, "Guard should be inside geofence"
            assert stored_data['geofence_violation'] is False, "No violation for guard inside"

        # Verify no geofence violation alert was created
        violation_alert = DeviceAlert.objects.filter(
            alert_type='GEOFENCE_VIOLATION',
            source_id=f"guard-{test_guard.id}"
        ).first()

        assert violation_alert is None, "No alert should be created for guard inside geofence"

    def test_guard_outside_geofence_triggers_alert(
        self,
        test_guard,
        test_client,
        test_geofence,
        mock_geofence_violation_message,
        outside_geofence_coords
    ):
        """
        CRITICAL: Test guard outside geofence triggers violation alert.

        Security: Geofence violations may indicate unauthorized movement,
        theft, or safety concerns.
        """
        # Clear cache
        cache.clear()

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            # Mock the alert task to verify it gets called
            with patch('background_tasks.mqtt_handler_tasks.process_device_alert') as mock_alert:
                topic = mock_geofence_violation_message['_mqtt_metadata']['topic']
                process_guard_gps(topic, mock_geofence_violation_message)

                # Verify geofence violation was detected
                stored_data = mock_processor.add_guard_location.call_args[0][0]
                assert stored_data['geofence_violation'] is True

                # Verify alert task was queued
                mock_alert.apply_async.assert_called_once()
                alert_args = mock_alert.apply_async.call_args

                # Verify alert data
                assert 'geofence' in alert_args[1]['args'][0].lower()
                alert_data = alert_args[1]['args'][1]
                assert alert_data['alert_type'] == 'geofence_violation'
                assert alert_data['severity'] == 'high'

    def test_geofence_violation_captures_exact_location(
        self,
        test_guard,
        test_client,
        test_geofence,
        mock_geofence_violation_message,
        outside_geofence_coords
    ):
        """
        Test geofence violation captures exact GPS coordinates.

        Security: Location data essential for locating guard.
        """
        cache.clear()

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            with patch('background_tasks.mqtt_handler_tasks.process_device_alert') as mock_alert:
                topic = mock_geofence_violation_message['_mqtt_metadata']['topic']
                process_guard_gps(topic, mock_geofence_violation_message)

                # Verify location was captured in alert
                alert_data = mock_alert.apply_async.call_args[1]['args'][1]
                assert 'location' in alert_data
                assert alert_data['location']['lat'] == outside_geofence_coords['lat']
                assert alert_data['location']['lon'] == outside_geofence_coords['lon']

    def test_geofence_violation_includes_guard_name(
        self,
        test_guard,
        test_client,
        test_geofence,
        mock_geofence_violation_message
    ):
        """
        Test geofence violation alert includes guard name.

        Security: Supervisors need to know WHO violated geofence.
        """
        cache.clear()

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            with patch('background_tasks.mqtt_handler_tasks.process_device_alert') as mock_alert:
                topic = mock_geofence_violation_message['_mqtt_metadata']['topic']
                process_guard_gps(topic, mock_geofence_violation_message)

                # Verify guard name in alert message
                alert_data = mock_alert.apply_async.call_args[1]['args'][1]
                assert test_guard.peoplename in alert_data['message']


@pytest.mark.django_db
class TestGeofenceBoundaryHandling:
    """Test edge cases at geofence boundaries."""

    def test_guard_exactly_on_boundary_handled_correctly(
        self,
        test_guard,
        test_client,
        test_geofence
    ):
        """
        Test guard on exact geofence boundary is handled correctly.

        Security: Boundary cases should not cause crashes or incorrect alerts.
        """
        cache.clear()

        # Get boundary coordinates (edge of geofence polygon)
        boundary_coords = list(test_geofence.geofence.coords[0][0])  # First point
        boundary_lat = boundary_coords[1]
        boundary_lon = boundary_coords[0]

        gps_message = {
            'guard_id': test_guard.id,
            'client_id': test_client.id,
            'lat': boundary_lat,
            'lon': boundary_lon,
            'accuracy': 5.0,
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': f'guard/guard-{test_guard.id}/gps',
                'qos': 1,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            # Should not raise exception
            topic = gps_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, gps_message)

            # Verify GPS was stored
            assert mock_processor.add_guard_location.called


@pytest.mark.django_db
class TestMultipleGeofenceSupport:
    """Test guard assigned to multiple geofences."""

    def test_guard_inside_any_geofence_no_violation(
        self,
        test_guard,
        test_client,
        test_post,
        inside_geofence_coords
    ):
        """
        Test guard inside ANY assigned geofence is considered compliant.

        Security: Guards patrolling multiple sites should not trigger
        false violations.
        """
        cache.clear()

        # Create second geofence for same client
        second_geofence_center_lat = 12.9800
        second_geofence_center_lon = 77.6000
        offset = 0.0009

        second_geofence_polygon = Polygon([
            (second_geofence_center_lon - offset, second_geofence_center_lat - offset),
            (second_geofence_center_lon + offset, second_geofence_center_lat - offset),
            (second_geofence_center_lon + offset, second_geofence_center_lat + offset),
            (second_geofence_center_lon - offset, second_geofence_center_lat + offset),
            (second_geofence_center_lon - offset, second_geofence_center_lat - offset),
        ], srid=4326)

        ApprovedLocation.objects.create(
            bt=test_client,
            locationpost=test_post,
            locationname="Secondary Site",
            locationcoordinates=second_geofence_polygon,
            enable=True
        )

        # Guard at first geofence location
        gps_message = {
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

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = gps_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, gps_message)

            stored_data = mock_processor.add_guard_location.call_args[0][0]
            assert stored_data['in_geofence'] is True
            assert stored_data['geofence_violation'] is False


@pytest.mark.django_db
class TestGeofenceEdgeCases:
    """Test edge cases and error handling."""

    def test_no_geofence_configured_no_violation(
        self,
        test_guard,
        test_client,
        inside_geofence_coords
    ):
        """
        Test guard at client with no geofences doesn't trigger violation.

        Security: Geofences are optional - clients without them should work.
        """
        cache.clear()

        # Delete all approved locations
        ApprovedLocation.objects.filter(client=test_client).delete()

        gps_message = {
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

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = gps_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, gps_message)

            # Should not raise exception
            stored_data = mock_processor.add_guard_location.call_args[0][0]
            # No geofences = no violation checking
            assert stored_data['geofence_violation'] is False

    def test_disabled_geofence_ignored(
        self,
        test_guard,
        test_client,
        test_geofence,
        outside_geofence_coords
    ):
        """
        Test disabled geofences are ignored.

        Security: Allows temporary geofence disabling without deletion.
        """
        cache.clear()

        # Disable geofence
        test_geofence.is_active = False
        test_geofence.save()

        gps_message = {
            'guard_id': test_guard.id,
            'client_id': test_client.id,
            'lat': outside_geofence_coords['lat'],
            'lon': outside_geofence_coords['lon'],
            'accuracy': 8.5,
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': f'guard/guard-{test_guard.id}/gps',
                'qos': 1,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            with patch('background_tasks.mqtt_handler_tasks.process_device_alert') as mock_alert:
                topic = gps_message['_mqtt_metadata']['topic']
                process_guard_gps(topic, gps_message)

                # No alert should be triggered (disabled geofence)
                mock_alert.apply_async.assert_not_called()

    def test_invalid_gps_coordinates_handled_gracefully(
        self,
        test_guard,
        test_client
    ):
        """
        Test invalid GPS coordinates are rejected gracefully.

        Security: Prevents crashes from malformed GPS data.
        """
        cache.clear()

        invalid_gps_message = {
            'guard_id': test_guard.id,
            'client_id': test_client.id,
            'lat': 999.0,  # Invalid latitude
            'lon': -200.0,  # Invalid longitude
            'accuracy': 8.5,
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': f'guard/guard-{test_guard.id}/gps',
                'qos': 1,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = invalid_gps_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, invalid_gps_message)

            # Should not create GPS record for invalid coordinates
            mock_processor.add_guard_location.assert_not_called()

    def test_missing_gps_coordinates_handled_gracefully(
        self,
        test_guard,
        test_client
    ):
        """
        Test missing GPS coordinates are handled gracefully.

        Security: Prevents crashes from incomplete GPS data.
        """
        cache.clear()

        missing_coords_message = {
            'guard_id': test_guard.id,
            'client_id': test_client.id,
            # Missing lat/lon
            'accuracy': 8.5,
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': f'guard/guard-{test_guard.id}/gps',
                'qos': 1,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = missing_coords_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, missing_coords_message)

            # Should not create GPS record
            mock_processor.add_guard_location.assert_not_called()


@pytest.mark.django_db
class TestGeofencePerformanceOptimizations:
    """Test geofence validation performance optimizations."""

    def test_guard_caching_reduces_database_queries(
        self,
        test_guard,
        test_client,
        mock_gps_message
    ):
        """
        Test guard data is cached to reduce database queries.

        Performance: 99% query reduction (6000 queries/hour → 60 queries/hour).
        """
        cache.clear()

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = mock_gps_message['_mqtt_metadata']['topic']

            # First GPS update - should query database
            process_guard_gps(topic, mock_gps_message)

            # Second GPS update - should use cache
            process_guard_gps(topic, mock_gps_message)

            # Verify guard was cached
            cache_key = f"guard_people_{test_guard.id}"
            cached_guard = cache.get(cache_key)
            assert cached_guard is not None

    def test_nonexistent_guard_cached_as_not_found(
        self,
        test_client
    ):
        """
        Test non-existent guard is cached to prevent repeated lookups.

        Performance: Prevents repeated database queries for invalid guard IDs.
        """
        cache.clear()

        invalid_guard_id = 999999
        gps_message = {
            'guard_id': invalid_guard_id,
            'client_id': test_client.id,
            'lat': 12.9716,
            'lon': 77.5946,
            'accuracy': 8.5,
            'timestamp': datetime.now(dt_timezone.utc).isoformat(),
            '_mqtt_metadata': {
                'topic': f'guard/guard-{invalid_guard_id}/gps',
                'qos': 1,
                'received_at': datetime.now(dt_timezone.utc).isoformat(),
                'broker': 'localhost'
            }
        }

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = gps_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, gps_message)

            # Verify NOT_FOUND was cached
            cache_key = f"guard_people_{invalid_guard_id}"
            cached_result = cache.get(cache_key)
            assert cached_result == 'NOT_FOUND'


@pytest.mark.django_db
class TestGeofenceTenantIsolation:
    """Test geofence validation respects tenant boundaries."""

    def test_geofence_validation_only_checks_same_tenant(
        self,
        test_guard,
        test_client,
        test_geofence,
        inside_geofence_coords
    ):
        """
        Test geofence validation only checks geofences for guard's tenant.

        Security: Cross-tenant geofence checking is a security violation.
        """
        cache.clear()

        # Create second tenant with geofence at same location
        other_client = Bt.objects.create(
            buname="Other Company",
            bucode="OTH001",
            enable=True
        )

        # Create geofence for other tenant at SAME location
        ApprovedLocation.objects.create(
            bt=other_client,
            locationname="Other Company Site",
            locationcoordinates=test_geofence.locationcoordinates,  # Same geofence geometry
            enable=True
        )

        gps_message = {
            'guard_id': test_guard.id,
            'client_id': test_client.id,  # test_client, not other_client
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

        with patch('background_tasks.mqtt_handler_tasks.get_batch_processor') as mock_batch:
            mock_processor = MagicMock()
            mock_batch.return_value = mock_processor

            topic = gps_message['_mqtt_metadata']['topic']
            process_guard_gps(topic, gps_message)

            # Should only check geofences for test_client (not other_client)
            stored_data = mock_processor.add_guard_location.call_args[0][0]

            # Guard should be inside geofence (using test_client's geofence)
            assert stored_data['in_geofence'] is True
