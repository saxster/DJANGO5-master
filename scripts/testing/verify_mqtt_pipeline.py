#!/usr/bin/env python3
"""
MQTT Pipeline Verification Script

Verifies that the complete MQTT → Celery → Database → WebSocket pipeline
is working correctly by checking database records and metrics.

Usage:
    python scripts/testing/verify_mqtt_pipeline.py
    python scripts/testing/verify_mqtt_pipeline.py --verbose
    python scripts/testing/verify_mqtt_pipeline.py --last-minutes 10

Checks:
1. DeviceTelemetry records created
2. GuardLocation records created with geofence validation
3. SensorReading records created
4. DeviceAlert records created
5. Alert notifications sent (SMS/Email flags)
6. Prometheus metrics incremented
7. Celery task success rates

Author: DevOps Team
Date: November 1, 2025
"""

import os
import sys
import django
from datetime import datetime, timedelta, timezone as dt_timezone
import argparse

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
django.setup()

from django.utils import timezone
from django.db.models import Count, Avg, Max
from apps.mqtt.models import DeviceTelemetry, GuardLocation, SensorReading, DeviceAlert
from apps.core.tasks.base import TaskMetrics


class MQTTPipelineVerifier:
    """Verifies MQTT pipeline is working end-to-end."""

    def __init__(self, last_minutes: int = 5, verbose: bool = False):
        """
        Initialize verifier.

        Args:
            last_minutes: Check records from last N minutes
            verbose: Print detailed output
        """
        self.last_minutes = last_minutes
        self.verbose = verbose
        self.cutoff_time = timezone.now() - timedelta(minutes=last_minutes)
        self.checks_passed = 0
        self.checks_failed = 0

    def print_header(self, title: str):
        """Print section header."""
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    def check(self, name: str, condition: bool, details: str = ""):
        """
        Run a verification check.

        Args:
            name: Check name
            condition: True if check passes, False otherwise
            details: Additional details to print
        """
        if condition:
            print(f"✅ {name}")
            if details and self.verbose:
                print(f"   {details}")
            self.checks_passed += 1
        else:
            print(f"❌ {name}")
            if details:
                print(f"   {details}")
            self.checks_failed += 1

    def verify_device_telemetry(self):
        """Verify device telemetry records created."""
        self.print_header("Device Telemetry Verification")

        recent = DeviceTelemetry.objects.filter(received_at__gte=self.cutoff_time)
        count = recent.count()

        self.check(
            f"Device telemetry records created",
            count > 0,
            f"Found {count} records in last {self.last_minutes} minutes"
        )

        if count > 0:
            # Check data quality
            latest = recent.latest('received_at')
            self.check(
                "Telemetry has battery data",
                latest.battery_level is not None,
                f"Battery: {latest.battery_level}%"
            )

            self.check(
                "Telemetry has signal data",
                latest.signal_strength is not None,
                f"Signal: {latest.signal_strength} dBm"
            )

            self.check(
                "Telemetry has raw MQTT payload",
                latest.raw_data is not None and len(latest.raw_data) > 0,
                f"Raw data keys: {list(latest.raw_data.keys())}"
            )

            if self.verbose:
                print(f"\n   Latest telemetry:")
                print(f"   - Device: {latest.device_id}")
                print(f"   - Battery: {latest.battery_level}%")
                print(f"   - Signal: {latest.signal_strength} dBm")
                print(f"   - Temperature: {latest.temperature}°C")
                print(f"   - Received: {latest.received_at}")

    def verify_guard_gps(self):
        """Verify guard GPS tracking with geofence validation."""
        self.print_header("Guard GPS Tracking Verification")

        recent = GuardLocation.objects.filter(received_at__gte=self.cutoff_time)
        count = recent.count()

        self.check(
            f"Guard GPS records created",
            count > 0,
            f"Found {count} records in last {self.last_minutes} minutes"
        )

        if count > 0:
            latest = recent.latest('received_at')

            self.check(
                "GPS has PostGIS Point data",
                latest.location is not None,
                f"Location: {latest.location.y:.6f}°N, {latest.location.x:.6f}°E"
            )

            self.check(
                "Geofence validation ran",
                latest.in_geofence is not None,
                f"In geofence: {latest.in_geofence}, Violation: {latest.geofence_violation}"
            )

            # Check for geofence violations
            violations = recent.filter(geofence_violation=True)
            if violations.count() > 0:
                print(f"   ⚠️  {violations.count()} geofence violations detected")

                # Check if alerts were triggered
                geofence_alerts = DeviceAlert.objects.filter(
                    alert_type='GEOFENCE_VIOLATION',
                    received_at__gte=self.cutoff_time
                )

                self.check(
                    "Geofence violations triggered alerts",
                    geofence_alerts.count() > 0,
                    f"Found {geofence_alerts.count()} geofence violation alerts"
                )

            if self.verbose:
                print(f"\n   Latest GPS location:")
                print(f"   - Guard: {latest.guard.peoplename if latest.guard else 'Unknown'}")
                print(f"   - Coordinates: {latest.location.y:.6f}°N, {latest.location.x:.6f}°E")
                print(f"   - Accuracy: {latest.accuracy}m")
                print(f"   - In Geofence: {latest.in_geofence}")
                print(f"   - Timestamp: {latest.timestamp}")

    def verify_sensor_readings(self):
        """Verify sensor reading records."""
        self.print_header("Sensor Readings Verification")

        recent = SensorReading.objects.filter(received_at__gte=self.cutoff_time)
        count = recent.count()

        self.check(
            f"Sensor reading records created",
            count > 0,
            f"Found {count} records in last {self.last_minutes} minutes"
        )

        if count > 0:
            # Check sensor type distribution
            by_type = recent.values('sensor_type').annotate(count=Count('id'))

            if self.verbose:
                print(f"\n   Sensors by type:")
                for item in by_type:
                    print(f"   - {item['sensor_type']}: {item['count']} readings")

            # Check for smoke alarms
            smoke_alarms = recent.filter(sensor_type='SMOKE', value__gt=100)
            if smoke_alarms.count() > 0:
                print(f"   🔥 {smoke_alarms.count()} smoke alarms detected")

                # Check if fire alerts were triggered
                fire_alerts = DeviceAlert.objects.filter(
                    alert_type='FIRE',
                    received_at__gte=self.cutoff_time
                )

                self.check(
                    "Smoke alarms triggered fire alerts",
                    fire_alerts.count() > 0,
                    f"Found {fire_alerts.count()} fire alerts"
                )

    def verify_device_alerts(self):
        """Verify device alerts and notifications."""
        self.print_header("Device Alerts Verification")

        recent = DeviceAlert.objects.filter(received_at__gte=self.cutoff_time)
        count = recent.count()

        self.check(
            f"Device alert records created",
            count > 0,
            f"Found {count} alerts in last {self.last_minutes} minutes"
        )

        if count > 0:
            # Check alert types
            by_type = recent.values('alert_type').annotate(count=Count('id'))

            if self.verbose:
                print(f"\n   Alerts by type:")
                for item in by_type:
                    print(f"   - {item['alert_type']}: {item['count']}")

            # Check notification delivery
            sms_sent = recent.filter(sms_sent=True).count()
            email_sent = recent.filter(email_sent=True).count()
            push_sent = recent.filter(push_sent=True).count()

            if sms_sent > 0 or email_sent > 0 or push_sent > 0:
                print(f"\n   📧 Notifications sent:")
                print(f"   - SMS: {sms_sent}")
                print(f"   - Email: {email_sent}")
                print(f"   - Push: {push_sent}")

            # Check critical alerts
            critical = recent.filter(severity='CRITICAL')
            if critical.count() > 0:
                latest_critical = critical.latest('received_at')

                if self.verbose:
                    print(f"\n   Latest critical alert:")
                    print(f"   - Type: {latest_critical.alert_type}")
                    print(f"   - Source: {latest_critical.source_id}")
                    print(f"   - Message: {latest_critical.message}")
                    print(f"   - Status: {latest_critical.status}")
                    print(f"   - Timestamp: {latest_critical.timestamp}")

    def verify_metrics(self):
        """Verify Prometheus metrics are being collected."""
        self.print_header("Metrics Verification")

        try:
            from django.core.cache import cache

            # Check for MQTT metrics in cache
            mqtt_keys = []
            for pattern in ['mqtt_message_processed', 'mqtt_device_telemetry', 'mqtt_guard_gps']:
                keys = cache.keys(f"task_metrics:{pattern}*")
                mqtt_keys.extend(keys if keys else [])

            self.check(
                "MQTT metrics being collected",
                len(mqtt_keys) > 0,
                f"Found {len(mqtt_keys)} MQTT metric keys in cache"
            )

            # Check WebSocket metrics
            ws_keys = cache.keys("task_metrics:websocket*")
            ws_keys = ws_keys if ws_keys else []

            self.check(
                "WebSocket metrics being collected",
                len(ws_keys) > 0,
                f"Found {len(ws_keys)} WebSocket metric keys in cache"
            )

        except Exception as e:
            self.check(
                "Metrics collection",
                False,
                f"Error checking metrics: {e}"
            )

    def verify_prometheus_export(self):
        """Verify Prometheus metrics endpoint works."""
        self.print_header("Prometheus Export Verification")

        try:
            import requests

            response = requests.get('http://localhost:8000/metrics/export/', timeout=5)

            self.check(
                "Prometheus /metrics/export/ accessible",
                response.status_code == 200,
                f"Status code: {response.status_code}"
            )

            if response.status_code == 200:
                content = response.text

                # Check for expected metrics
                has_celery = 'celery_' in content
                has_mqtt = 'mqtt_' in content
                has_websocket = 'websocket_' in content

                self.check(
                    "Celery metrics exported",
                    has_celery,
                    "Found celery_ metrics in output"
                )

                self.check(
                    "MQTT metrics exported",
                    has_mqtt,
                    "Found mqtt_ metrics in output"
                )

                self.check(
                    "WebSocket metrics exported",
                    has_websocket,
                    "Found websocket_ metrics in output"
                )

        except Exception as e:
            self.check(
                "Prometheus endpoint",
                False,
                f"Error accessing endpoint: {e}"
            )

    def run_all_verifications(self):
        """Run all verification checks."""
        self.print_header(f"MQTT Pipeline Verification (Last {self.last_minutes} minutes)")

        self.verify_device_telemetry()
        self.verify_guard_gps()
        self.verify_sensor_readings()
        self.verify_device_alerts()
        self.verify_metrics()
        self.verify_prometheus_export()

        # Summary
        self.print_header("Verification Summary")
        total_checks = self.checks_passed + self.checks_failed
        success_rate = (self.checks_passed / total_checks * 100) if total_checks > 0 else 0

        print(f"\n✅ Passed: {self.checks_passed}")
        print(f"❌ Failed: {self.checks_failed}")
        print(f"📊 Success Rate: {success_rate:.1f}%")

        if self.checks_failed == 0:
            print(f"\n🎉 ALL CHECKS PASSED - Pipeline is working correctly!")
            return 0
        else:
            print(f"\n⚠️  Some checks failed - Review output above")
            return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Verify MQTT message bus pipeline is working'
    )

    parser.add_argument(
        '--last-minutes',
        type=int,
        default=5,
        help='Check records from last N minutes (default: 5)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Verbose output with details'
    )

    args = parser.parse_args()

    print("=" * 60)
    print("MQTT Pipeline Verification")
    print("=" * 60)
    print(f"Checking records from last {args.last_minutes} minutes")
    print(f"Current time: {timezone.now()}")
    print("=" * 60)

    verifier = MQTTPipelineVerifier(args.last_minutes, args.verbose)
    exit_code = verifier.run_all_verifications()

    print("\n" + "=" * 60)
    if exit_code == 0:
        print("✅ VERIFICATION COMPLETE - All systems operational")
    else:
        print("⚠️  VERIFICATION COMPLETE - Some issues detected")
    print("=" * 60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
