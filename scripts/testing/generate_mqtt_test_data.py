#!/usr/bin/env python3
"""
MQTT Test Data Generator

Generates realistic MQTT test messages for all topic types to verify
the complete message bus pipeline: MQTT → Subscriber → Celery → Database → WebSocket

Usage:
    python scripts/testing/generate_mqtt_test_data.py --broker localhost --count 10
    python scripts/testing/generate_mqtt_test_data.py --scenario all
    python scripts/testing/generate_mqtt_test_data.py --scenario panic --verbose

Scenarios:
    - device_telemetry: Device battery, signal, temperature
    - guard_gps: Guard GPS coordinates (in/out of geofence)
    - sensor_readings: Facility sensors (door, motion, smoke)
    - critical_alerts: Panic buttons, SOS, intrusion
    - system_health: Edge server health metrics
    - all: All scenarios combined

Requirements:
    pip install paho-mqtt

Author: DevOps Team
Date: November 1, 2025
"""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion


class MQTTTestDataGenerator:
    """Generates realistic MQTT test data for pipeline verification."""

    def __init__(self, broker_host: str = 'localhost', broker_port: int = 1883):
        """
        Initialize MQTT test data generator.

        Args:
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = None
        self.published_count = 0
        self.failed_count = 0

    def connect(self):
        """Connect to MQTT broker."""
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_publish = self.on_publish
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        print(f"✅ Connected to MQTT broker at {self.broker_host}:{self.broker_port}")

    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        print(f"\n📊 Summary: {self.published_count} published, {self.failed_count} failed")

    def on_publish(self, client, userdata, mid):
        """Callback when message is published."""
        self.published_count += 1

    def publish_message(self, topic: str, payload: Dict[str, Any], qos: int = 1):
        """
        Publish MQTT message.

        Args:
            topic: MQTT topic
            payload: Message payload dictionary
            qos: Quality of Service level (0, 1, or 2)
        """
        try:
            payload_json = json.dumps(payload)
            result = self.client.publish(topic, payload_json, qos=qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"✓ Published to {topic} (QoS {qos}): {payload_json[:100]}...")
            else:
                print(f"✗ Failed to publish to {topic}: rc={result.rc}")
                self.failed_count += 1

            # Small delay to prevent flooding
            time.sleep(0.1)

        except Exception as e:
            print(f"✗ Error publishing to {topic}: {e}")
            self.failed_count += 1

    # ========================================================================
    # SCENARIO 1: Device Telemetry
    # ========================================================================

    def generate_device_telemetry(self, count: int = 5):
        """
        Generate device telemetry messages (battery, signal, temperature).

        Simulates IoT sensors reporting health metrics every 30 seconds.
        """
        print("\n📡 Generating Device Telemetry Messages...")

        device_ids = ['sensor-001', 'sensor-002', 'sensor-003', 'edge-server-01']

        for i in range(count):
            device_id = random.choice(device_ids)

            payload = {
                'battery': random.randint(20, 100),  # 20-100%
                'signal': random.randint(-90, -50),  # -90 to -50 dBm
                'temperature': round(random.uniform(15.0, 35.0), 1),  # 15-35°C
                'connectivity': random.choice(['ONLINE', 'ONLINE', 'ONLINE', 'POOR']),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            self.publish_message(f"device/{device_id}/telemetry", payload, qos=1)

    # ========================================================================
    # SCENARIO 2: Guard GPS Tracking
    # ========================================================================

    def generate_guard_gps(self, count: int = 5, include_violations: bool = True):
        """
        Generate guard GPS messages (some in geofence, some violations).

        Simulates guards moving around with GPS updates every 30 seconds.
        """
        print("\n📍 Generating Guard GPS Messages...")

        # Bangalore coordinates (example geofence center)
        center_lat = 12.9716
        center_lon = 77.5946

        guard_ids = [101, 102, 103, 104, 105]

        for i in range(count):
            guard_id = random.choice(guard_ids)

            # 70% in geofence, 30% violations
            if include_violations and random.random() > 0.7:
                # Simulate out of bounds (far from center)
                lat = center_lat + random.uniform(0.05, 0.1)  # ~5-10km away
                lon = center_lon + random.uniform(0.05, 0.1)
            else:
                # Simulate in bounds (close to center)
                lat = center_lat + random.uniform(-0.01, 0.01)  # ~1km radius
                lon = center_lon + random.uniform(-0.01, 0.01)

            payload = {
                'lat': round(lat, 6),
                'lon': round(lon, 6),
                'accuracy': round(random.uniform(5.0, 25.0), 1),  # 5-25 meters
                'guard_id': guard_id,
                'client_id': 1,  # Assuming client_id=1 for testing
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            self.publish_message(f"guard/guard-{guard_id}/gps", payload, qos=1)

    # ========================================================================
    # SCENARIO 3: Sensor Readings
    # ========================================================================

    def generate_sensor_readings(self, count: int = 5):
        """
        Generate facility sensor readings (door, motion, smoke, temperature).

        Simulates various facility sensors reporting state changes.
        """
        print("\n🚪 Generating Sensor Readings...")

        sensor_types = [
            ('door-101', 'door', None, 'OPEN'),
            ('door-102', 'door', None, 'CLOSED'),
            ('motion-201', 'motion', None, 'DETECTED'),
            ('smoke-301', 'smoke', 45, 'NORMAL'),
            ('temp-401', 'temperature', 24.5, 'NORMAL'),
        ]

        for i in range(count):
            sensor_id, sensor_type, value, state = random.choice(sensor_types)

            # Occasionally simulate alarm state
            if sensor_type == 'smoke' and random.random() > 0.8:
                value = random.randint(120, 200)  # High smoke level
                state = 'ALARM'

            payload = {
                'type': sensor_type,
                'value': value,
                'state': state,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            self.publish_message(f"sensor/{sensor_id}/status", payload, qos=1)

    # ========================================================================
    # SCENARIO 4: Critical Alerts
    # ========================================================================

    def generate_critical_alerts(self, count: int = 3):
        """
        Generate critical device alerts (panic, SOS, intrusion).

        Simulates emergency situations requiring immediate response.
        """
        print("\n🚨 Generating Critical Alerts...")

        alert_scenarios = [
            {
                'topic': 'alert/panic/guard-101',
                'data': {
                    'alert_type': 'panic',
                    'severity': 'critical',
                    'message': 'Panic button pressed by guard',
                    'location': {'lat': 12.9716, 'lon': 77.5946},
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                'qos': 2  # Exactly once for critical
            },
            {
                'topic': 'alert/sos/guard-102',
                'data': {
                    'alert_type': 'sos',
                    'severity': 'critical',
                    'message': 'SOS distress signal activated',
                    'location': {'lat': 12.9720, 'lon': 77.5950},
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                'qos': 2
            },
            {
                'topic': 'alert/intrusion/sensor-301',
                'data': {
                    'alert_type': 'intrusion',
                    'severity': 'high',
                    'message': 'Unauthorized entry detected at Zone A',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                'qos': 2
            },
        ]

        for i in range(min(count, len(alert_scenarios))):
            scenario = alert_scenarios[i]
            self.publish_message(scenario['topic'], scenario['data'], qos=scenario['qos'])
            time.sleep(0.5)  # Slight delay between critical alerts

    # ========================================================================
    # SCENARIO 5: System Health
    # ========================================================================

    def generate_system_health(self, count: int = 3):
        """
        Generate system health messages from edge servers.

        Simulates edge servers reporting health metrics.
        """
        print("\n💻 Generating System Health Messages...")

        servers = ['edge-server-01', 'edge-server-02', 'edge-gateway-01']

        for i in range(count):
            server_id = random.choice(servers)

            payload = {
                'cpu': random.randint(30, 90),  # 30-90% CPU
                'memory': random.randint(40, 85),  # 40-85% memory
                'disk': random.randint(30, 70),  # 30-70% disk
                'uptime': random.randint(3600, 864000),  # 1 hour to 10 days in seconds
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

            self.publish_message(f"system/health/{server_id}", payload, qos=0)

    # ========================================================================
    # SCENARIO: All Combined
    # ========================================================================

    def run_all_scenarios(self, count_per_scenario: int = 5):
        """Run all test scenarios."""
        print("\n🎯 Running ALL Test Scenarios...")
        print(f"Generating {count_per_scenario} messages per scenario\n")

        self.generate_device_telemetry(count_per_scenario)
        time.sleep(1)

        self.generate_guard_gps(count_per_scenario, include_violations=True)
        time.sleep(1)

        self.generate_sensor_readings(count_per_scenario)
        time.sleep(1)

        self.generate_critical_alerts(min(count_per_scenario, 3))
        time.sleep(1)

        self.generate_system_health(count_per_scenario)

        print("\n✅ All scenarios completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate MQTT test data for message bus pipeline verification'
    )

    parser.add_argument(
        '--broker',
        default='localhost',
        help='MQTT broker hostname (default: localhost)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=1883,
        help='MQTT broker port (default: 1883)'
    )

    parser.add_argument(
        '--scenario',
        choices=['device_telemetry', 'guard_gps', 'sensor_readings', 'critical_alerts', 'system_health', 'all'],
        default='all',
        help='Test scenario to generate (default: all)'
    )

    parser.add_argument(
        '--count',
        type=int,
        default=5,
        help='Number of messages per scenario (default: 5)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("MQTT Test Data Generator")
    print("=" * 60)
    print(f"Broker: {args.broker}:{args.port}")
    print(f"Scenario: {args.scenario}")
    print(f"Count: {args.count}")
    print("=" * 60)

    # Create generator
    generator = MQTTTestDataGenerator(args.broker, args.port)

    try:
        # Connect to broker
        generator.connect()
        time.sleep(1)  # Wait for connection

        # Run scenarios
        if args.scenario == 'all':
            generator.run_all_scenarios(args.count)
        elif args.scenario == 'device_telemetry':
            generator.generate_device_telemetry(args.count)
        elif args.scenario == 'guard_gps':
            generator.generate_guard_gps(args.count)
        elif args.scenario == 'sensor_readings':
            generator.generate_sensor_readings(args.count)
        elif args.scenario == 'critical_alerts':
            generator.generate_critical_alerts(args.count)
        elif args.scenario == 'system_health':
            generator.generate_system_health(args.count)

        # Wait for messages to be published
        time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        generator.disconnect()

    print("\n" + "=" * 60)
    print("✅ Test data generation complete")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Check MQTT subscriber logs: tail -f /var/log/mqtt_subscriber.log")
    print("2. Check Celery logs: tail -f /var/log/celery/general.log")
    print("3. Verify database: python scripts/testing/verify_mqtt_pipeline.py")
    print("4. Check Grafana dashboards for metrics")


if __name__ == "__main__":
    main()
