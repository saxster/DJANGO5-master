#!/usr/bin/env python3
"""
Simple MQTT Broker Message Size Limit Tester
"""

import os
import sys
import time
import json

# Setup Django
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django
django.setup()

from paho.mqtt import client as mqtt
from django.conf import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

MQTT_CONFIG = settings.MQTT_CONFIG
BROKER_ADDRESS = MQTT_CONFIG["BROKER_ADDRESS"] 
BROKER_PORT = MQTT_CONFIG["broker_port"]

print(f"\n{'='*60}")
print(f"MQTT BROKER SIZE LIMIT TEST")
print(f"{'='*60}")
print(f"Broker: {BROKER_ADDRESS}:{BROKER_PORT}")
print(f"{'='*60}\n")

# Test different message sizes
test_sizes_kb = [1, 10, 50, 100, 256, 512, 1024, 2048, 5120, 10240]
results = []

for size_kb in test_sizes_kb:
    try:
        # Create test message
        size_bytes = size_kb * 1024
        test_payload = "X" * size_bytes
        
        print(f"Testing {size_kb:5}KB ({size_bytes:,} bytes)...", end=" ")
        
        # Try to publish
        client = mqtt.Client()
        client.connect(BROKER_ADDRESS, BROKER_PORT)
        
        info = client.publish("test/size", test_payload, qos=0)
        client.loop()
        
        # Check if successful
        if info.rc == 0:
            print("✓ SUCCESS")
            results.append((size_kb, "SUCCESS"))
            client.disconnect()
            time.sleep(0.5)  # Small delay between tests
        else:
            print(f"✗ FAILED (code: {info.rc})")
            results.append((size_kb, f"FAILED_{info.rc}"))
            client.disconnect()
            break
            
    except Exception as e:
        print(f"✗ ERROR: {str(e)[:50]}")
        results.append((size_kb, "ERROR"))
        break

# Print summary
print(f"\n{'='*60}")
print("RESULTS SUMMARY")
print(f"{'='*60}")

max_success = 0
for size_kb, status in results:
    symbol = "✓" if status == "SUCCESS" else "✗"
    print(f"{symbol} {size_kb:5}KB: {status}")
    if status == "SUCCESS":
        max_success = size_kb

if max_success > 0:
    print(f"\n🎯 Maximum successful size: {max_success}KB ({max_success*1024:,} bytes)")
    safe_limit = int(max_success * 0.8)
    print(f"📋 Recommended application limit: {safe_limit}KB (80% safety margin)")
    
    if max_success < 1024:
        print(f"\n⚠️  WARNING: Limit is less than 1MB!")
        print(f"   Consider increasing broker's max_packet_size setting")
else:
    print("\n❌ No successful messages. Check broker connection.")

print(f"{'='*60}\n")