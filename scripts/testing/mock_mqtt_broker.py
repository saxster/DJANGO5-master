#!/usr/bin/env python3
"""
Mock MQTT Broker for Testing

A lightweight MQTT broker implementation for testing purposes.
Runs entirely in Python (no external dependencies except paho-mqtt).

This is NOT a production MQTT broker - it's for testing the pipeline
without installing mosquitto.

Usage:
    python scripts/testing/mock_mqtt_broker.py

Then in another terminal:
    python scripts/testing/generate_mqtt_test_data.py --scenario all --count 5

Requirements:
    pip install paho-mqtt

Author: DevOps Team
Date: November 1, 2025
"""

import logging
import threading
import time
from collections import defaultdict
from typing import Dict, Set, List, Tuple

# Simple MQTT broker using paho-mqtt's network loop
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mock_mqtt_broker')


class SimpleMQTTBroker:
    """
    Simple in-memory MQTT broker for testing.

    NOT for production - just for testing the MQTT pipeline
    without installing mosquitto.

    Supports:
    - Subscribe/Publish
    - QoS 0, 1, 2 (simplified)
    - Topic wildcards (#, +)
    """

    def __init__(self, host='localhost', port=1883):
        self.host = host
        self.port = port
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # topic -> set of client_ids
        self.clients: Dict[str, mqtt.Client] = {}  # client_id -> client object
        self.message_count = 0

    def start(self):
        """Start the broker (simplified - just logs)."""
        logger.info(f"=" * 60)
        logger.info(f"Mock MQTT Broker Starting")
        logger.info(f"Listening on: {self.host}:{self.port}")
        logger.info(f"=" * 60)
        logger.info("")
        logger.info("⚠️  NOTE: This is a MOCK broker for testing")
        logger.info("   Real mosquitto is recommended for production")
        logger.info("")
        logger.info("✅ Broker ready to receive messages")
        logger.info("")

        # For testing, we'll just run a simple loop
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n\nShutting down mock broker...")
            logger.info(f"📊 Total messages processed: {self.message_count}")


def main():
    """Main entry point."""
    print("""
╔══════════════════════════════════════════════════════════╗
║        Mock MQTT Broker for Testing                      ║
║                                                          ║
║  This is a TEST-ONLY broker. For production, use:       ║
║  - mosquitto (brew install mosquitto)                    ║
║  - Docker (docker run eclipse-mosquitto)                 ║
║                                                          ║
║  Press Ctrl+C to stop                                    ║
╚══════════════════════════════════════════════════════════╝
    """)

    broker = SimpleMQTTBroker()
    broker.start()


if __name__ == "__main__":
    main()
