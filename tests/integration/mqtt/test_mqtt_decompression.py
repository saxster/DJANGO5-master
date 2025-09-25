#!/usr/bin/env python3
"""
Test script for MQTT message decompression functionality.
This will test the unzip_string function with various scenarios.
"""
import os
import sys
import json
import base64
from zlib import compress

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
import django
django.setup()

from scripts.utilities.paho_client import unzip_string

def test_scenario(name, test_data, expected_success=True):
    """Test a specific decompression scenario"""
    print(f"\n{'='*60}")
    print(f"TESTING: {name}")
    print(f"{'='*60}")

    try:
        result = unzip_string(test_data)
        # Try to parse as JSON to verify
        json_data = json.loads(result)

        if expected_success:
            print(f"✅ SUCCESS: {result[:100]}{'...' if len(result) > 100 else ''}")
            return True
        else:
            print(f"❌ UNEXPECTED SUCCESS: Expected failure but got: {result[:100]}")
            return False

    except Exception as e:
        if expected_success:
            print(f"❌ FAILED: {e}")
            return False
        else:
            print(f"✅ EXPECTED FAILURE: {e}")
            return True

def main():
    print("MQTT MESSAGE DECOMPRESSION TEST")
    print("=" * 60)

    # Test data scenarios
    test_json = {"mutation": "test", "variables": {"id": 123}}
    test_json_str = json.dumps(test_json)

    results = []

    # Scenario 1: Plain JSON (uncompressed)
    results.append(test_scenario(
        "Plain JSON (uncompressed)",
        test_json_str,
        expected_success=True
    ))

    # Scenario 2: Compressed and base64 encoded JSON
    compressed = compress(test_json_str.encode('utf-8'))
    encoded = base64.b64encode(compressed).decode('utf-8')
    results.append(test_scenario(
        "Compressed and base64 encoded JSON",
        encoded,
        expected_success=True
    ))

    # Scenario 3: Just base64 encoded (no compression)
    just_encoded = base64.b64encode(test_json_str.encode('utf-8')).decode('utf-8')
    results.append(test_scenario(
        "Base64 encoded JSON (no compression)",
        just_encoded,
        expected_success=True
    ))

    # Scenario 4: Invalid base64
    results.append(test_scenario(
        "Invalid base64 data",
        "invalid_base64_data!@#$%",
        expected_success=False
    ))

    # Scenario 5: Base64 but invalid compressed data
    invalid_compressed = base64.b64encode(b"invalid compressed data").decode('utf-8')
    results.append(test_scenario(
        "Base64 encoded invalid compressed data",
        invalid_compressed,
        expected_success=False
    ))

    # Scenario 6: Empty string
    results.append(test_scenario(
        "Empty string",
        "",
        expected_success=False
    ))

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")

    passed = sum(results)
    total = len(results)

    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED")

    print(f"{'='*60}")

if __name__ == "__main__":
    main()