"""
MQTT Message Handler Tasks

@ontology(
    domain="integration",
    purpose="Celery tasks that process MQTT messages received from IoT devices",
    task_types=[
        "Device telemetry processing",
        "Guard GPS tracking",
        "Facility sensor data",
        "Critical device alerts",
        "System health monitoring"
    ],
    routing={
        "device_telemetry": "external_api queue (priority 5)",
        "guard_gps": "high_priority queue (priority 8)",
        "sensor_data": "external_api queue (priority 6)",
        "device_alert": "critical queue (priority 10)",
        "system_health": "maintenance queue (priority 2)"
    },
    data_flows=[
        "MQTT subscriber → Celery task → Database",
        "MQTT subscriber → Celery task → WebSocket broadcast",
        "MQTT subscriber → Celery task → Alert creation"
    ],
    criticality="high",
    dependencies=["Celery", "Django ORM", "TaskMetrics", "GeoDjango (for GPS)"],
    tags=["mqtt", "celery", "iot", "device-handling", "real-time"]
)
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.core.tasks.base import BaseTask, TaskMetrics
from apps.core.tasks.websocket_broadcast import WebSocketBroadcastTask
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE, SECONDS_IN_HOUR

logger = logging.getLogger("mqtt_handler_tasks")


@shared_task(
    base=BaseTask,
    bind=True,
    name='background_tasks.mqtt_handler_tasks.process_device_telemetry',
    max_retries=3,
    default_retry_delay=30,
)
def process_device_telemetry(self, topic: str, data: Dict[str, Any]):
    """
    Process device telemetry messages (temperature, battery, connectivity, etc.).

    Args:
        topic: MQTT topic (e.g., "device/sensor-12345/telemetry")
        data: Validated message payload with telemetry data

    Telemetry types:
        - Battery level
        - Signal strength
        - Temperature/humidity
        - Device health metrics
        - Connectivity status
    """
    try:
        # Extract device ID from topic (device/<device_id>/...)
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            logger.error(f"Invalid device topic format: {topic}")
            return

        device_id = topic_parts[1]
        metadata = data.get('_mqtt_metadata', {})

        logger.info(f"Processing telemetry from device {device_id}")

        # Extract common telemetry fields
        battery_level = data.get('battery')
        signal_strength = data.get('signal')
        temperature = data.get('temperature')
        timestamp_str = data.get('timestamp')

        # Parse timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = timezone.now()
        else:
            timestamp = timezone.now()

        # Store telemetry data (Phase A3 - IMPLEMENTED)
        from apps.mqtt.models import DeviceTelemetry

        telemetry = DeviceTelemetry.objects.create(
            device_id=device_id,
            battery_level=battery_level,
            signal_strength=signal_strength,
            temperature=temperature,
            connectivity_status=data.get('connectivity'),
            timestamp=timestamp,
            raw_data=data
        )

        logger.info(
            f"Device {device_id} telemetry stored (ID: {telemetry.id}): "
            f"battery={battery_level}%, signal={signal_strength}"
        )

        # Record metrics
        TaskMetrics.increment_counter('mqtt_device_telemetry_processed', {
            'device_id': device_id[:20],  # Truncate for cardinality
        })

        # Check for low battery alerts
        if battery_level and battery_level < 20:
            logger.warning(f"Low battery alert for device {device_id}: {battery_level}%")
            TaskMetrics.increment_counter('mqtt_device_low_battery', {
                'device_id': device_id[:20],
            })
            # TODO: Create low battery alert

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error processing device telemetry: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error processing device telemetry from {topic}: {e}", exc_info=True)
        TaskMetrics.increment_counter('mqtt_device_telemetry_error', {
            'error_type': type(e).__name__
        })


@shared_task(
    base=BaseTask,
    bind=True,
    name='background_tasks.mqtt_handler_tasks.process_guard_gps',
    max_retries=3,
    default_retry_delay=15,  # Shorter delay for GPS
)
def process_guard_gps(self, topic: str, data: Dict[str, Any]):
    """
    Process guard GPS location updates and geofence validation.

    Args:
        topic: MQTT topic (e.g., "guard/guard-789/gps")
        data: GPS coordinates and metadata

    Expected data format:
        {
            "lat": 12.9716,
            "lon": 77.5946,
            "accuracy": 10.5,
            "timestamp": "2025-11-01T10:00:00Z",
            "guard_id": 789,
            "client_id": 123
        }
    """
    try:
        # Extract guard ID from topic
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            logger.error(f"Invalid guard topic format: {topic}")
            return

        guard_topic_id = topic_parts[1]
        guard_id = data.get('guard_id')
        client_id = data.get('client_id')

        # Validate GPS coordinates
        lat = data.get('lat')
        lon = data.get('lon')

        if lat is None or lon is None:
            logger.error(f"Missing GPS coordinates in message from {topic}")
            return

        # Validate coordinate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            logger.error(f"Invalid GPS coordinates: lat={lat}, lon={lon}")
            return

        logger.info(f"Processing GPS for guard {guard_id}: ({lat}, {lon})")

        # Create PostGIS Point
        location = Point(lon, lat, srid=4326)  # WGS84
        accuracy = data.get('accuracy', 0)
        timestamp_str = data.get('timestamp')

        # Parse timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = timezone.now()
        else:
            timestamp = timezone.now()

        # Phase A3 + A4: Geofence validation (IMPLEMENTED)
        from apps.mqtt.models import GuardLocation
        from apps.core_onboarding.models import ApprovedLocation
        from apps.peoples.models import People

        # Get guard record
        try:
            guard = People.objects.get(id=guard_id)
        except People.DoesNotExist:
            logger.error(f"Guard {guard_id} not found in database")
            return

        # Check geofence compliance
        in_geofence = False
        geofence_violation = False

        try:
            # Query approved locations for this client
            approved_locations = ApprovedLocation.objects.filter(
                client_id=client_id,
                is_active=True
            )

            # Check if guard is within ANY approved geofence
            for approved_location in approved_locations:
                if approved_location.is_within_geofence(lat, lon):
                    in_geofence = True
                    break

            # If guard should be in geofence but isn't
            if not in_geofence and approved_locations.exists():
                geofence_violation = True

        except Exception as e:
            logger.warning(f"Geofence validation error for guard {guard_id}: {e}")
            # Continue with storage even if validation fails

        # Store GPS location (Phase A3 - IMPLEMENTED)
        guard_location = GuardLocation.objects.create(
            guard=guard,
            location=location,
            accuracy=accuracy,
            in_geofence=in_geofence,
            geofence_violation=geofence_violation,
            timestamp=timestamp,
            raw_data=data
        )

        logger.info(
            f"GPS location stored for guard {guard_id} (ID: {guard_location.id}): "
            f"({lat}, {lon}), geofence={'IN' if in_geofence else 'OUT'}"
        )

        # Trigger geofence violation alert if needed (Phase A4)
        if geofence_violation:
            logger.warning(f"GEOFENCE VIOLATION: Guard {guard_id} at ({lat}, {lon})")

            # Trigger critical alert
            geofence_alert_data = {
                'source_id': f"guard-{guard_id}",
                'alert_type': 'geofence_violation',
                'severity': 'high',
                'message': f'Guard {guard.peoplename} ({guard_id}) is outside assigned geofence',
                'location': {'lat': lat, 'lon': lon},
                'timestamp': timestamp.isoformat()
            }

            # Queue geofence violation as critical alert
            process_device_alert.apply_async(
                args=[f"alert/geofence/guard-{guard_id}", geofence_alert_data],
                queue='critical',
                priority=9
            )

        # Record metrics
        TaskMetrics.increment_counter('mqtt_guard_gps_processed', {
            'guard_id': str(guard_id)[:20],
        })

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error processing guard GPS: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error processing guard GPS from {topic}: {e}", exc_info=True)
        TaskMetrics.increment_counter('mqtt_guard_gps_error', {
            'error_type': type(e).__name__
        })


@shared_task(
    base=BaseTask,
    bind=True,
    name='background_tasks.mqtt_handler_tasks.process_sensor_data',
    max_retries=3,
    default_retry_delay=30,
)
def process_sensor_data(self, topic: str, data: Dict[str, Any]):
    """
    Process facility sensor data (motion, door, smoke, temperature, etc.).

    Args:
        topic: MQTT topic (e.g., "sensor/door-456/status")
        data: Sensor reading data

    Sensor types:
        - Motion detectors
        - Door/window sensors
        - Smoke/fire alarms
        - Temperature/humidity sensors
        - Water leak detectors
    """
    try:
        # Extract sensor ID from topic
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            logger.error(f"Invalid sensor topic format: {topic}")
            return

        sensor_id = topic_parts[1]
        sensor_type = data.get('type', 'unknown')
        sensor_value = data.get('value')
        sensor_state = data.get('state')  # open/closed, on/off, etc.
        timestamp_str = data.get('timestamp')

        logger.info(f"Processing sensor data from {sensor_id}: type={sensor_type}, value={sensor_value}")

        # Parse timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = timezone.now()
        else:
            timestamp = timezone.now()

        # Store sensor data (Phase A3 - IMPLEMENTED)
        from apps.mqtt.models import SensorReading

        sensor_reading = SensorReading.objects.create(
            sensor_id=sensor_id,
            sensor_type=sensor_type.upper() if sensor_type else 'UNKNOWN',
            value=sensor_value,
            state=sensor_state.upper() if sensor_state else None,
            timestamp=timestamp,
            raw_data=data
        )

        logger.info(
            f"Sensor reading stored (ID: {sensor_reading.id}): "
            f"{sensor_type} {sensor_id} = {sensor_value or sensor_state}"
        )

        # Check for anomalies and trigger critical alerts
        if sensor_type == 'smoke' and sensor_value and sensor_value > 100:
            logger.critical(f"Smoke detector alert from sensor {sensor_id}: {sensor_value}")
            TaskMetrics.increment_counter('mqtt_sensor_critical_alert', {
                'sensor_type': 'smoke',
                'sensor_id': sensor_id[:20],
            })

            # Trigger fire alarm alert via critical queue
            fire_alert_data = {
                'source_id': sensor_id,
                'alert_type': 'fire',
                'severity': 'critical',
                'message': f'Fire alarm: Smoke level {sensor_value} detected at sensor {sensor_id}',
                'timestamp': timestamp.isoformat()
            }

            process_device_alert.apply_async(
                args=[f"alert/fire/{sensor_id}", fire_alert_data],
                queue='critical',
                priority=10
            )

        # Record metrics
        TaskMetrics.increment_counter('mqtt_sensor_data_processed', {
            'sensor_type': sensor_type,
        })

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error processing sensor data: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error processing sensor data from {topic}: {e}", exc_info=True)
        TaskMetrics.increment_counter('mqtt_sensor_data_error', {
            'error_type': type(e).__name__
        })


@shared_task(
    base=WebSocketBroadcastTask,
    bind=True,
    name='background_tasks.mqtt_handler_tasks.process_device_alert',
    max_retries=5,
    default_retry_delay=10,  # Fast retry for critical alerts
)
def process_device_alert(self, topic: str, data: Dict[str, Any]):
    """
    Process critical device alerts (panic button, SOS, intrusion, etc.).

    Args:
        topic: MQTT topic (e.g., "alert/guard-789/panic")
        data: Alert details

    Alert types:
        - Panic button pressed
        - SOS distress signal
        - Intrusion detected
        - Equipment failure
        - Emergency situations
    """
    try:
        # Extract device/user ID from topic
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            logger.error(f"Invalid alert topic format: {topic}")
            return

        source_id = topic_parts[1]
        alert_type = data.get('alert_type', 'unknown')
        alert_severity = data.get('severity', 'high')
        alert_message = data.get('message', 'Critical alert received')
        location = data.get('location')  # GPS coordinates if available
        timestamp_str = data.get('timestamp')

        logger.critical(f"CRITICAL ALERT from {source_id}: {alert_type} - {alert_message}")

        # Parse timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = timezone.now()
        else:
            timestamp = timezone.now()

        # Create alert record (Phase A3 - IMPLEMENTED)
        from apps.mqtt.models import DeviceAlert
        from django.contrib.gis.geos import Point

        # Parse location if provided
        alert_location = None
        if location:
            try:
                if isinstance(location, dict) and 'lat' in location and 'lon' in location:
                    alert_location = Point(location['lon'], location['lat'], srid=4326)
            except Exception as e:
                logger.warning(f"Failed to parse alert location: {e}")

        device_alert = DeviceAlert.objects.create(
            source_id=source_id,
            alert_type=alert_type.upper() if alert_type else 'PANIC',
            severity=alert_severity.upper() if alert_severity else 'CRITICAL',
            message=alert_message,
            location=alert_location,
            timestamp=timestamp,
            raw_data=data,
            status='NEW'
        )

        logger.critical(
            f"Device alert stored (ID: {device_alert.id}): "
            f"{alert_type} from {source_id} ({alert_severity})"
        )

        # Phase B2: Trigger immediate notifications (IMPLEMENTED)
        from apps.mqtt.services.alert_notification_service import (
            AlertNotificationService,
            AlertNotification
        )

        # Create notification object
        notification = AlertNotification(
            alert_id=device_alert.id,
            alert_type=alert_type,
            severity=alert_severity,
            message=alert_message,
            source_id=source_id,
            timestamp=timestamp,
            location=location,
            metadata=data
        )

        # Determine recipients based on alert severity
        # TODO: Query actual supervisor contacts from database
        # For now, use settings-based configuration
        recipients = {
            'sms': getattr(settings, 'ALERT_SMS_RECIPIENTS', []),
            'email': getattr(settings, 'ALERT_EMAIL_RECIPIENTS', ['alerts@example.com']),
            'push': getattr(settings, 'ALERT_PUSH_TOKENS', [])
        }

        # Send notifications
        notification_results = AlertNotificationService.notify_alert(notification, recipients)

        # Update alert record with notification status
        device_alert.sms_sent = any(r.channel == 'sms' and r.success for r in notification_results)
        device_alert.email_sent = any(r.channel == 'email' and r.success for r in notification_results)
        device_alert.push_sent = any(r.channel == 'push' and r.success for r in notification_results)
        device_alert.save(update_fields=['sms_sent', 'email_sent', 'push_sent'])

        logger.info(
            f"Notifications sent for alert {device_alert.id}: "
            f"SMS={device_alert.sms_sent}, Email={device_alert.email_sent}, Push={device_alert.push_sent}"
        )

        # Broadcast to NOC dashboard via WebSocket (Phase 2.1 - IMPLEMENTED)
        self.broadcast_to_noc_dashboard(
            message_type='critical_alert',
            data={
                'source_id': source_id,
                'alert_type': alert_type,
                'severity': alert_severity,
                'message': alert_message,
                'location': location,
                'timestamp': timestamp.isoformat()
            },
            priority='critical'
        )

        # Record metrics
        TaskMetrics.increment_counter('mqtt_critical_alert_processed', {
            'alert_type': alert_type,
            'severity': alert_severity,
        })

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error processing device alert: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error processing device alert from {topic}: {e}", exc_info=True)
        TaskMetrics.increment_counter('mqtt_critical_alert_error', {
            'error_type': type(e).__name__
        })


@shared_task(
    base=BaseTask,
    bind=True,
    name='background_tasks.mqtt_handler_tasks.process_system_health',
    max_retries=2,
    default_retry_delay=60,
)
def process_system_health(self, topic: str, data: Dict[str, Any]):
    """
    Process system health check messages from IoT devices and edge servers.

    Args:
        topic: MQTT topic (e.g., "system/health/edge-server-01")
        data: Health metrics

    Health metrics:
        - CPU usage
        - Memory usage
        - Disk space
        - Network connectivity
        - Service status
    """
    try:
        # Extract system ID from topic
        topic_parts = topic.split('/')
        if len(topic_parts) < 2:
            logger.error(f"Invalid system topic format: {topic}")
            return

        system_id = topic_parts[-1]  # Last part is system ID
        cpu_usage = data.get('cpu')
        memory_usage = data.get('memory')
        disk_usage = data.get('disk')
        uptime = data.get('uptime')
        timestamp_str = data.get('timestamp')

        logger.debug(f"System health from {system_id}: CPU={cpu_usage}%, MEM={memory_usage}%")

        # Parse timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except ValueError:
                timestamp = timezone.now()
        else:
            timestamp = timezone.now()

        # Store health metrics (placeholder)
        # Example: SystemHealth.objects.create(
        #     system_id=system_id,
        #     cpu_usage=cpu_usage,
        #     memory_usage=memory_usage,
        #     disk_usage=disk_usage,
        #     uptime=uptime,
        #     timestamp=timestamp,
        #     raw_data=data
        # )

        # Check for resource exhaustion
        if cpu_usage and cpu_usage > 90:
            logger.warning(f"High CPU usage on {system_id}: {cpu_usage}%")
            TaskMetrics.increment_counter('mqtt_system_high_cpu', {
                'system_id': system_id[:20],
            })

        if memory_usage and memory_usage > 90:
            logger.warning(f"High memory usage on {system_id}: {memory_usage}%")
            TaskMetrics.increment_counter('mqtt_system_high_memory', {
                'system_id': system_id[:20],
            })

        # Record metrics
        TaskMetrics.increment_counter('mqtt_system_health_processed', {
            'system_id': system_id[:20],
        })

    except DATABASE_EXCEPTIONS as e:
        logger.error(f"Database error processing system health: {e}", exc_info=True)
        raise self.retry(exc=e)
    except Exception as e:
        logger.error(f"Error processing system health from {topic}: {e}", exc_info=True)
        TaskMetrics.increment_counter('mqtt_system_health_error', {
            'error_type': type(e).__name__
        })
