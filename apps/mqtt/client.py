"""
MQTT IoT Client for Device Communication

@ontology(
    domain="integration",
    purpose="MQTT client for IoT device communication and pub/sub messaging patterns",
    integration_type="mqtt_broker",
    protocol="MQTT 3.1.1/5.0 (via paho-mqtt)",
    mqtt_client_version="paho.mqtt CallbackAPIVersion.VERSION2",
    connection_config={
        "BROKER_ADDRESS": "from settings.MQTT_CONFIG",
        "BROKER_PORT": "from settings.MQTT_CONFIG",
        "keep_alive": "default (60s)",
        "reconnect": "automatic"
    },
    callback_hooks=["on_connect", "on_disconnect"],
    message_patterns=["pub/sub", "topic-based routing"],
    use_cases=[
        "IoT sensor data ingestion",
        "Device command/control",
        "Real-time alerts to devices"
    ],
    connection_mode="loop_forever (blocking)",
    criticality="medium",
    dependencies=["paho-mqtt", "Django settings"],
    tags=["mqtt", "iot", "pubsub", "device-communication", "real-time"]
)
"""

import os
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django

django.setup()

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import logging

log = logging.getLogger("mobile_service_log")
from django.conf import settings

MQTT_CONFIG = settings.MQTT_CONFIG

# MQTT broker settings
BROKER_ADDRESS = MQTT_CONFIG.get("BROKER_ADDRESS", "localhost")
BROKER_PORT = MQTT_CONFIG.get("BROKER_PORT", 1883)

class MqttClient:
    """
    MQTT client class
    """

    def __init__(self):
        """
        Initializes the MQTT client
        """
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    # MQTT client callback functions
    def on_connect(self, client, userdata, flags, rc, props):
        if rc == 0:
            log.info("Connected to MQTT Broker!")
        else:
            fail = f"Failed to connect, return code {rc}"
            log.info(fail)

    def on_disconnect(self, client, userdata, disconnect_flags, rc, props):
        log.info("Disconnected from MQTT broker", userdata)

    def loop_forever(self):
        backoff_seconds = 1
        max_backoff_seconds = 60

        while True:
            try:
                self.client.connect(BROKER_ADDRESS, BROKER_PORT)
                self.client.loop_forever()
                backoff_seconds = 1
            except KeyboardInterrupt:
                log.info("MQTT client interrupted; shutting down")
                break
            except Exception as exc:  # noqa: BLE001 - reconnect loop
                log.error(
                    "mqtt_connection_failed",
                    extra={
                        'broker': BROKER_ADDRESS,
                        'port': BROKER_PORT,
                        'retry_in': backoff_seconds
                    },
                    exc_info=True
                )
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, max_backoff_seconds)


if __name__ == "__main__":
    client = MqttClient()
    client.loop_forever()
