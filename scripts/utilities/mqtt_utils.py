# mqtt_utils.py

import logging
from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from django.conf import settings

log = logging.getLogger("message_qlogs")

# Phase 4.2: Load broker config from settings (not hardcoded)
MQTT_CONFIG = getattr(settings, 'MQTT_CONFIG', {})
DEFAULT_BROKER_HOST = MQTT_CONFIG.get('BROKER_ADDRESS', 'localhost')
DEFAULT_BROKER_PORT = MQTT_CONFIG.get('BROKER_PORT', 1883)


def publish_message(topic, message, host=None, port=None, qos=1):
    """
    Publish MQTT message to broker.

    Args:
        topic: MQTT topic
        message: Message payload (string or JSON-serializable)
        host: Broker host (defaults to settings.MQTT_CONFIG['BROKER_ADDRESS'])
        port: Broker port (defaults to settings.MQTT_CONFIG['BROKER_PORT'])
        qos: Quality of Service level (0, 1, or 2)

    Phase 4.2: Fixed hardcoded broker address (was 'django5.youtility.in').
    """
    # Use defaults from settings if not provided
    host = host or DEFAULT_BROKER_HOST
    port = port or DEFAULT_BROKER_PORT

    try:
        log.info(f"Connecting to MQTT broker at {host}:{port}")
        client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        client.connect(host, port, 60)
        result = client.publish(topic, message, qos=qos)
        client.loop(2)
        client.disconnect()
        log.info(f"Published message to topic {topic}: {message}")
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            log.info(f"[MQTT] Message sent to topic {topic}")
        else:
            log.warning(f"[MQTT] Failed with result code {result.rc}")
    except Exception as e:
        log.error(f"[MQTT] Exception during publish: {e}", exc_info=True)
