#!/usr/bin/env python3
"""
MQTT Broker Message Size Limit Tester
This script tests the maximum message size that your MQTT broker accepts.
"""

import os
import sys
import time
import json
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django
django.setup()

from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from django.conf import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

MQTT_CONFIG = settings.MQTT_CONFIG
BROKER_ADDRESS = MQTT_CONFIG["BROKER_ADDRESS"]
BROKER_PORT = MQTT_CONFIG["broker_port"]

# Test configuration
TEST_TOPIC = "test/size_limit"
TEST_SIZES_KB = [1, 10, 50, 100, 256, 512, 1024, 2048, 5120, 10240]  # Test sizes in KB

class MQTTLimitTester:
    def __init__(self):
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"limit_tester_{int(time.time())}")
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        
        # Track results
        self.connected = False
        self.last_publish_success = None
        self.max_successful_size = 0
        self.results = []
        
    def on_connect(self, client, userdata, flags, rc, props=None):
        if rc == 0:
            log.info(f"✓ Connected to MQTT Broker at {BROKER_ADDRESS}:{BROKER_PORT}")
            self.connected = True
            # Subscribe to test topic to verify message delivery
            client.subscribe(TEST_TOPIC)
        else:
            log.error(f"✗ Failed to connect, return code {rc}")
            self.connected = False
    
    def on_publish(self, client, userdata, mid):
        log.debug(f"Message {mid} published")
        self.last_publish_success = True
    
    def on_message(self, client, userdata, msg):
        log.debug(f"Received message on {msg.topic}: {len(msg.payload)} bytes")
    
    def on_disconnect(self, client, userdata, rc, props=None):
        if rc != 0:
            log.warning(f"Unexpected disconnect with code {rc}")
    
    def test_message_size(self, size_kb):
        """Test sending a message of specified size in KB"""
        size_bytes = size_kb * 1024
        
        # Create test payload
        test_data = {
            "timestamp": datetime.now().isoformat(),
            "size_kb": size_kb,
            "test_data": "X" * (size_bytes - 100)  # Fill with data, leaving room for JSON overhead
        }
        payload = json.dumps(test_data)
        actual_size = len(payload.encode('utf-8'))
        
        log.info(f"\nTesting {size_kb}KB message (actual: {actual_size:,} bytes)...")
        
        try:
            # Reset success flag
            self.last_publish_success = None
            
            # Attempt to publish
            result = self.client.publish(TEST_TOPIC, payload, qos=1)
            
            # Wait for publish callback or timeout
            timeout = min(30, max(5, size_kb / 100))  # Dynamic timeout based on size
            start_time = time.time()
            
            while (time.time() - start_time) < timeout:
                if self.last_publish_success is not None:
                    break
                time.sleep(0.1)
            
            # Check result
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                if self.last_publish_success:
                    log.info(f"✓ {size_kb}KB - SUCCESS: Message published and confirmed")
                    self.max_successful_size = max(self.max_successful_size, size_kb)
                    self.results.append({"size_kb": size_kb, "size_bytes": actual_size, "status": "SUCCESS"})
                    return True
                else:
                    log.warning(f"⚠ {size_kb}KB - UNCERTAIN: Published but no confirmation (timeout)")
                    self.results.append({"size_kb": size_kb, "size_bytes": actual_size, "status": "TIMEOUT"})
                    return False
            else:
                log.error(f"✗ {size_kb}KB - FAILED: Error code {result.rc}")
                self.results.append({"size_kb": size_kb, "size_bytes": actual_size, "status": f"ERROR_{result.rc}"})
                return False
                
        except Exception as e:
            log.error(f"✗ {size_kb}KB - EXCEPTION: {str(e)}")
            self.results.append({"size_kb": size_kb, "size_bytes": actual_size, "status": f"EXCEPTION: {str(e)}"})
            
            # Check if connection was lost
            if not self.client.is_connected():
                log.warning("Connection lost, attempting to reconnect...")
                try:
                    self.client.reconnect()
                    time.sleep(2)
                except:
                    log.error("Reconnection failed")
            return False
    
    def run_tests(self):
        """Run the complete test suite"""
        log.info("=" * 60)
        log.info("MQTT BROKER MESSAGE SIZE LIMIT TEST")
        log.info("=" * 60)
        log.info(f"Broker: {BROKER_ADDRESS}:{BROKER_PORT}")
        log.info(f"Test sizes: {TEST_SIZES_KB} KB")
        log.info("=" * 60)
        
        # Connect to broker
        try:
            self.client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                log.error("Failed to connect to MQTT broker within timeout")
                return
            
            # Test each size
            for size_kb in TEST_SIZES_KB:
                success = self.test_message_size(size_kb)
                
                # If we start failing, try one more smaller increment to find exact limit
                if not success and self.max_successful_size > 0:
                    log.info("\nNarrowing down exact limit...")
                    prev_size = TEST_SIZES_KB[TEST_SIZES_KB.index(size_kb) - 1] if size_kb in TEST_SIZES_KB else 0
                    if prev_size > 0:
                        test_size = (prev_size + size_kb) // 2
                        if test_size not in TEST_SIZES_KB:
                            self.test_message_size(test_size)
                    break
                
                time.sleep(1)  # Brief pause between tests
            
        except Exception as e:
            log.error(f"Test failed: {e}")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        log.info("\n" + "=" * 60)
        log.info("TEST RESULTS SUMMARY")
        log.info("=" * 60)
        
        for result in self.results:
            status_symbol = "✓" if result["status"] == "SUCCESS" else "✗"
            log.info(f"{status_symbol} {result['size_kb']:5}KB ({result['size_bytes']:,} bytes): {result['status']}")
        
        log.info("-" * 60)
        
        if self.max_successful_size > 0:
            log.info(f"\n🎯 MAXIMUM SUCCESSFUL MESSAGE SIZE: {self.max_successful_size}KB")
            log.info(f"   ({self.max_successful_size * 1024:,} bytes)")
            
            # Recommendations
            log.info("\n📋 RECOMMENDATIONS:")
            safe_limit = int(self.max_successful_size * 0.8)
            log.info(f"1. Set application limit to {safe_limit}KB (80% of max) for safety margin")
            log.info(f"2. Implement chunking for messages larger than {safe_limit}KB")
            log.info(f"3. Add size validation before sending attachments")
            
            if self.max_successful_size < 1024:
                log.warning("\n⚠️  WARNING: Broker limit is less than 1MB!")
                log.warning("   This is quite restrictive for file attachments.")
                log.warning("   Consider:")
                log.warning("   - Increasing broker's max_packet_size configuration")
                log.warning("   - Using a different transfer mechanism for large files")
                log.warning("   - Implementing aggressive compression")
        else:
            log.error("\n❌ No successful messages sent. Check broker connection and configuration.")
        
        log.info("\n" + "=" * 60)

def check_broker_info():
    """Try to get broker information if possible"""
    log.info("\n" + "=" * 60)
    log.info("CHECKING BROKER CONFIGURATION")
    log.info("=" * 60)
    
    # Check if it's Mosquitto by trying to read config
    mosquitto_configs = [
        "/etc/mosquitto/mosquitto.conf",
        "/usr/local/etc/mosquitto/mosquitto.conf",
        "/mosquitto/config/mosquitto.conf"
    ]
    
    for config_path in mosquitto_configs:
        if os.path.exists(config_path):
            log.info(f"Found Mosquitto config at: {config_path}")
            try:
                with open(config_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        if 'message_size_limit' in line and not line.strip().startswith('#'):
                            log.info(f"Configured limit: {line.strip()}")
                            break
                    else:
                        log.info("No explicit message_size_limit found (using Mosquitto default: unlimited)")
            except:
                log.warning("Could not read config file")
            break
    
    # Try to get broker version via $SYS topics (if available)
    class VersionChecker:
        def __init__(self):
            self.version_info = {}
            self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            
        def on_connect(self, client, userdata, flags, rc, props=None):
            if rc == 0:
                client.subscribe("$SYS/broker/version")
                client.subscribe("$SYS/broker/config/max_packet_size")
            
        def on_message(self, client, userdata, msg):
            self.version_info[msg.topic] = msg.payload.decode('utf-8')
            
        def check(self):
            try:
                self.client.connect(BROKER_ADDRESS, BROKER_PORT)
                self.client.loop_start()
                time.sleep(2)
                self.client.loop_stop()
                self.client.disconnect()
                
                if self.version_info:
                    log.info("Broker information from $SYS topics:")
                    for topic, value in self.version_info.items():
                        log.info(f"  {topic}: {value}")
            except:
                pass
    
    VersionChecker().check()
    log.info("=" * 60)

if __name__ == "__main__":
    # First check broker configuration if possible
    check_broker_info()
    
    # Run the size limit tests
    tester = MQTTLimitTester()
    tester.run_tests()