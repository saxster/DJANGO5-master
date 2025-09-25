#!/usr/bin/env python3
"""
Test larger MQTT message sizes to find the actual limit
"""

import os
import sys
import time

# Setup Django
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django
django.setup()

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from django.conf import settings

MQTT_CONFIG = settings.MQTT_CONFIG
BROKER_ADDRESS = MQTT_CONFIG["BROKER_ADDRESS"] 
BROKER_PORT = MQTT_CONFIG["broker_port"]

print(f"\n{'='*60}")
print(f"TESTING LARGER MESSAGE SIZES")
print(f"{'='*60}\n")

# Test larger sizes in MB
test_sizes_mb = [10, 20, 50, 100, 150, 200, 256]
results = []

for size_mb in test_sizes_mb:
    try:
        size_bytes = size_mb * 1024 * 1024
        test_payload = "X" * size_bytes
        
        print(f"Testing {size_mb:4}MB ({size_bytes:,} bytes)...", end=" ")
        
        # Use newer API version to avoid deprecation warning
        client = mqtt.Client(CallbackAPIVersion.VERSION2)
        client.connect(BROKER_ADDRESS, BROKER_PORT)
        
        info = client.publish("test/large", test_payload, qos=0)
        client.loop()
        
        if info.rc == 0:
            print("✓ SUCCESS")
            results.append((size_mb, "SUCCESS"))
            client.disconnect()
            time.sleep(1)  # Longer delay for large messages
        else:
            print(f"✗ FAILED (code: {info.rc})")
            results.append((size_mb, f"FAILED_{info.rc}"))
            client.disconnect()
            break
            
    except Exception as e:
        error_msg = str(e)
        if "message too large" in error_msg.lower() or "payload too large" in error_msg.lower():
            print(f"✗ MESSAGE TOO LARGE")
        else:
            print(f"✗ ERROR: {error_msg[:50]}")
        results.append((size_mb, "ERROR"))
        break

# Print summary
print(f"\n{'='*60}")
print("LARGE MESSAGE TEST RESULTS")
print(f"{'='*60}")

max_success = 0
for size_mb, status in results:
    symbol = "✓" if status == "SUCCESS" else "✗"
    print(f"{symbol} {size_mb:4}MB: {status}")
    if status == "SUCCESS":
        max_success = size_mb

if max_success > 0:
    print(f"\n🎯 Maximum successful size: {max_success}MB ({max_success*1024*1024:,} bytes)")
    
    # Final recommendation
    print(f"\n{'='*60}")
    print("FINAL ANALYSIS")
    print(f"{'='*60}")
    
    if max_success >= 256:
        print("✓ Broker supports MQTT maximum (256MB)")
        print("✓ The EOF errors are likely NOT due to broker message size limits")
        print("\n🔍 Other possible causes for mobile attachment EOF errors:")
        print("  1. Client-side buffer limitations in mobile app")
        print("  2. Network timeout during large transfers (30 second timeout)")
        print("  3. Base64 encoding overhead (33% size increase)")
        print("  4. Mobile app MQTT client configuration issues")
        print("  5. Memory constraints on mobile device")
    elif max_success >= 50:
        print(f"✓ Broker supports up to {max_success}MB")
        print("✓ This should be sufficient for most attachments")
        print("\n📋 Check mobile app for:")
        print("  1. Client buffer size configuration")
        print("  2. Timeout settings for large transfers")
        print("  3. Proper base64 encoding handling")
    else:
        print(f"⚠️  Broker limit is {max_success}MB")
        print("This could be causing issues with larger attachments")
        
print(f"{'='*60}\n")