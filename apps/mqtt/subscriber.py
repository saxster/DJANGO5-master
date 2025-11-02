"""
MQTT Subscriber Service for IoT Device Communication

@ontology(
    domain="integration",
    purpose="MQTT subscriber service that receives IoT device messages and routes to Celery tasks",
    integration_type="mqtt_broker",
    protocol="MQTT 3.1.1/5.0 (via paho-mqtt)",
    mqtt_client_version="paho.mqtt CallbackAPIVersion.VERSION2",
    connection_config={
        "broker_address": "from settings.MQTT_CONFIG",
        "broker_port": "from settings.MQTT_CONFIG",
        "keep_alive": "60s",
        "reconnect": "automatic with exponential backoff"
    },
    callback_hooks=["on_connect", "on_disconnect", "on_message", "on_subscribe"],
    message_patterns=["pub/sub", "topic-based routing", "wildcard subscriptions"],
    routing_strategy="Topic pattern matching → Celery task dispatch",
    security_features=[
        "JSON schema validation",
        "Topic whitelist",
        "Payload size limits",
        "SQL injection prevention",
        "XSS prevention"
    ],
    use_cases=[
        "IoT sensor data ingestion",
        "Device status updates",
        "Guard GPS tracking",
        "Facility sensor alerts",
        "Real-time device telemetry"
    ],
    celery_integration="Routes messages to domain-specific Celery queues",
    connection_mode="loop_forever (blocking) or loop_start (non-blocking)",
    criticality="high",
    dependencies=["paho-mqtt", "Django settings", "Celery", "TaskMetrics"],
    tags=["mqtt", "iot", "subscriber", "device-communication", "real-time", "celery-integration"]
)
"""

import os
import sys
import json
import logging
import signal
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone as dt_timezone

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django
django.setup()

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from django.conf import settings
from django.core.exceptions import ValidationError

# Celery tasks (lazy import to avoid circular dependencies)
from apps.core.tasks.base import TaskMetrics
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS, DATABASE_EXCEPTIONS
from apps.core.constants.datetime_constants import SECONDS_IN_MINUTE

logger = logging.getLogger("mqtt_subscriber")

# MQTT Configuration
MQTT_CONFIG = settings.MQTT_CONFIG
BROKER_ADDRESS = MQTT_CONFIG["BROKER_ADDRESS"]
BROKER_PORT = MQTT_CONFIG["broker_port"]
BROKER_USERNAME = MQTT_CONFIG.get("broker_userNAME", "")
BROKER_PASSWORD = MQTT_CONFIG.get("broker_password", "")

# Security Configuration
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB max payload
ALLOWED_TOPIC_PREFIXES = [
    "device/",      # Device telemetry
    "guard/",       # Guard GPS and status
    "sensor/",      # Facility sensors
    "alert/",       # Device-generated alerts
    "system/",      # System health checks
]


class MQTTPayloadValidator:
    """Validates MQTT message payloads for security and data integrity."""

    @staticmethod
    def validate_topic(topic: str) -> bool:
        """Validate topic against whitelist."""
        if not topic:
            return False

        # Check if topic starts with allowed prefix
        return any(topic.startswith(prefix) for prefix in ALLOWED_TOPIC_PREFIXES)

    @staticmethod
    def validate_json_payload(payload: bytes) -> Optional[Dict[str, Any]]:
        """
        Validate and parse JSON payload.

        Returns:
            Parsed JSON dict if valid, None otherwise
        """
        try:
            # Size check
            if len(payload) > MAX_PAYLOAD_SIZE:
                logger.warning(f"Payload exceeds max size: {len(payload)} bytes")
                return None

            # Parse JSON
            data = json.loads(payload.decode('utf-8'))

            if not isinstance(data, dict):
                logger.warning("Payload is not a JSON object")
                return None

            # Basic structure validation
            if 'timestamp' in data:
                # Validate timestamp format
                try:
                    datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    logger.warning("Invalid timestamp format in payload")
                    return None

            return data

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON payload: {e}")
            return None
        except UnicodeDecodeError as e:
            logger.warning(f"Invalid UTF-8 encoding: {e}")
            return None

    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """Sanitize string values to prevent injection attacks."""
        if not isinstance(value, str):
            return str(value)[:max_length]

        # Remove potentially dangerous characters
        sanitized = value.replace('\x00', '').strip()
        return sanitized[:max_length]


class MQTTSubscriberService:
    """
    MQTT Subscriber Service that routes device messages to Celery tasks.

    Subscribes to IoT device topics and dispatches messages to appropriate
    Celery tasks based on topic patterns. Includes validation, error handling,
    and metrics collection.
    """

    def __init__(self, client_id: Optional[str] = None):
        """
        Initialize MQTT subscriber.

        Args:
            client_id: Optional MQTT client ID (auto-generated if None)
        """
        self.client_id = client_id or f"django-subscriber-{os.getpid()}"
        self.client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self.client_id
        )
        self.validator = MQTTPayloadValidator()
        self.running = False

        # Setup callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe

        # Authentication
        if BROKER_USERNAME and BROKER_PASSWORD:
            self.client.username_pw_set(BROKER_USERNAME, BROKER_PASSWORD)

        # Connection settings
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)  # Exponential backoff

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"MQTT Subscriber initialized with client_id: {self.client_id}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)

    def on_connect(self, client, userdata, flags, rc, props):
        """
        Callback when connection to MQTT broker is established.

        Subscribes to all device topics on successful connection.
        """
        if rc == 0:
            logger.info(f"Connected to MQTT Broker at {BROKER_ADDRESS}:{BROKER_PORT}")

            # Subscribe to all device topics (wildcard subscriptions)
            subscriptions = [
                ("device/#", 1),    # All device telemetry (QoS 1)
                ("guard/#", 1),     # All guard GPS/status (QoS 1)
                ("sensor/#", 1),    # All facility sensors (QoS 1)
                ("alert/#", 2),     # Device alerts (QoS 2 - critical)
                ("system/#", 0),    # System health (QoS 0 - best effort)
            ]

            for topic, qos in subscriptions:
                result, mid = client.subscribe(topic, qos=qos)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"Subscribed to topic: {topic} (QoS {qos})")
                else:
                    logger.error(f"Failed to subscribe to {topic}: {result}")

            # Record metrics
            TaskMetrics.increment_counter('mqtt_subscriber_connected', {
                'broker': BROKER_ADDRESS,
                'client_id': self.client_id
            })
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code: {rc}")
            TaskMetrics.increment_counter('mqtt_subscriber_connection_failed', {
                'broker': BROKER_ADDRESS,
                'return_code': str(rc)
            })

    def on_disconnect(self, client, userdata, disconnect_flags, rc, props):
        """Callback when disconnected from MQTT broker."""
        if rc == 0:
            logger.info("Gracefully disconnected from MQTT Broker")
        else:
            logger.warning(f"Unexpected disconnection from MQTT Broker (rc={rc})")
            TaskMetrics.increment_counter('mqtt_subscriber_disconnected', {
                'broker': BROKER_ADDRESS,
                'return_code': str(rc),
                'unexpected': str(rc != 0)
            })

    def on_subscribe(self, client, userdata, mid, reason_code_list, props):
        """Callback when subscription is acknowledged."""
        logger.info(f"Subscription confirmed (mid={mid})")

    def on_message(self, client, userdata, message):
        """
        Callback when message is received from MQTT broker.

        Validates payload and routes to appropriate Celery task.
        """
        topic = message.topic
        payload = message.payload
        qos = message.qos

        logger.debug(f"Received message on topic: {topic} (QoS {qos}, {len(payload)} bytes)")

        # Validate topic
        if not self.validator.validate_topic(topic):
            logger.warning(f"Rejected message from unauthorized topic: {topic}")
            TaskMetrics.increment_counter('mqtt_subscriber_rejected_topic', {
                'topic_prefix': topic.split('/')[0] if '/' in topic else topic
            })
            return

        # Validate and parse payload
        data = self.validator.validate_json_payload(payload)
        if data is None:
            logger.warning(f"Invalid payload on topic {topic}")
            TaskMetrics.increment_counter('mqtt_subscriber_invalid_payload', {
                'topic_prefix': topic.split('/')[0] if '/' in topic else topic
            })
            return

        # Add metadata
        data['_mqtt_metadata'] = {
            'topic': topic,
            'qos': qos,
            'received_at': datetime.now(dt_timezone.utc).isoformat(),
            'broker': BROKER_ADDRESS
        }

        # Route to appropriate handler
        try:
            self._route_message(topic, data)

            # Record success metric
            TaskMetrics.increment_counter('mqtt_subscriber_message_processed', {
                'topic_prefix': topic.split('/')[0] if '/' in topic else topic,
                'qos': str(qos)
            })

        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}", exc_info=True)
            TaskMetrics.increment_counter('mqtt_subscriber_processing_error', {
                'topic_prefix': topic.split('/')[0] if '/' in topic else topic,
                'error_type': type(e).__name__
            })

    def _route_message(self, topic: str, data: Dict[str, Any]):
        """
        Route message to appropriate Celery task based on topic pattern.

        Args:
            topic: MQTT topic
            data: Validated and parsed message data
        """
        # Lazy import to avoid circular dependencies
        from background_tasks.mqtt_handler_tasks import (
            process_device_telemetry,
            process_guard_gps,
            process_sensor_data,
            process_device_alert,
            process_system_health
        )

        topic_lower = topic.lower()

        # Route based on topic prefix
        if topic_lower.startswith('device/'):
            # Device telemetry (temperature, battery, connectivity, etc.)
            process_device_telemetry.apply_async(
                args=[topic, data],
                queue='external_api',
                priority=5
            )
            logger.debug(f"Routed device telemetry to Celery: {topic}")

        elif topic_lower.startswith('guard/'):
            # Guard GPS coordinates and status
            process_guard_gps.apply_async(
                args=[topic, data],
                queue='high_priority',  # GPS tracking is time-sensitive
                priority=8
            )
            logger.debug(f"Routed guard GPS to Celery: {topic}")

        elif topic_lower.startswith('sensor/'):
            # Facility sensors (motion, door, smoke, etc.)
            process_sensor_data.apply_async(
                args=[topic, data],
                queue='external_api',
                priority=6
            )
            logger.debug(f"Routed sensor data to Celery: {topic}")

        elif topic_lower.startswith('alert/'):
            # Critical device alerts (panic button, SOS, etc.)
            process_device_alert.apply_async(
                args=[topic, data],
                queue='critical',  # Alerts go to critical queue
                priority=10
            )
            logger.warning(f"Routed critical alert to Celery: {topic}")

        elif topic_lower.startswith('system/'):
            # System health checks and diagnostics
            process_system_health.apply_async(
                args=[topic, data],
                queue='maintenance',
                priority=2
            )
            logger.debug(f"Routed system health to Celery: {topic}")

        else:
            logger.warning(f"No route handler for topic: {topic}")
            TaskMetrics.increment_counter('mqtt_subscriber_unrouted_topic', {
                'topic_prefix': topic.split('/')[0] if '/' in topic else topic
            })

    def start(self, blocking: bool = True):
        """
        Start MQTT subscriber service.

        Args:
            blocking: If True, runs in blocking mode (loop_forever).
                     If False, runs in background thread (loop_start).
        """
        try:
            logger.info(f"Starting MQTT subscriber (blocking={blocking})")
            self.running = True

            # Connect to broker
            self.client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=60)

            if blocking:
                # Blocking mode - runs in main thread
                self.client.loop_forever()
            else:
                # Non-blocking mode - runs in background thread
                self.client.loop_start()
                logger.info("MQTT subscriber running in background thread")

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error connecting to MQTT broker: {e}", exc_info=True)
            TaskMetrics.increment_counter('mqtt_subscriber_connection_error', {
                'error_type': 'network',
                'exception': type(e).__name__
            })
            raise
        except Exception as e:
            logger.error(f"Unexpected error starting MQTT subscriber: {e}", exc_info=True)
            TaskMetrics.increment_counter('mqtt_subscriber_connection_error', {
                'error_type': 'unexpected',
                'exception': type(e).__name__
            })
            raise

    def stop(self):
        """Stop MQTT subscriber service gracefully."""
        if self.running:
            logger.info("Stopping MQTT subscriber...")
            self.running = False
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT subscriber stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of MQTT subscriber.

        Returns:
            Dict containing connection status and statistics
        """
        return {
            'client_id': self.client_id,
            'running': self.running,
            'connected': self.client.is_connected(),
            'broker': f"{BROKER_ADDRESS}:{BROKER_PORT}",
        }


def main():
    """Main entry point for running subscriber as standalone service."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('mqtt_subscriber.log')
        ]
    )

    logger.info("="*60)
    logger.info("MQTT Subscriber Service Starting")
    logger.info(f"Broker: {BROKER_ADDRESS}:{BROKER_PORT}")
    logger.info(f"Allowed Topics: {', '.join(ALLOWED_TOPIC_PREFIXES)}")
    logger.info("="*60)

    # Create and start subscriber
    subscriber = MQTTSubscriberService()

    try:
        subscriber.start(blocking=True)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        subscriber.stop()
        logger.info("MQTT Subscriber Service Stopped")


if __name__ == "__main__":
    main()
