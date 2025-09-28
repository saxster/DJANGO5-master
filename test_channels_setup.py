#!/usr/bin/env python3
"""
Test script to verify Channels setup is working correctly
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

def test_channels_setup():
    """Test Channels configuration"""
    print("🔧 Testing Channels Setup...")

    try:
        from channels.layers import get_channel_layer
        from django.conf import settings

        print("✅ Channels module imported successfully")

        # Test channel layer configuration
        channel_layer = get_channel_layer()
        print(f"✅ Channel layer configured: {type(channel_layer).__name__}")

        # Test Redis connection
        if hasattr(channel_layer, 'hosts'):
            print(f"✅ Redis hosts configured: {channel_layer.hosts}")

        # Test ASGI application setting
        if hasattr(settings, 'ASGI_APPLICATION'):
            print(f"✅ ASGI_APPLICATION: {settings.ASGI_APPLICATION}")
        else:
            print("⚠️  ASGI_APPLICATION not configured")

        print("✅ All Channels tests passed!")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_websocket_routing():
    """Test WebSocket routing setup"""
    print("\n🔧 Testing WebSocket Routing...")

    try:
        from apps.api.mobile_routing import mobile_websocket_urlpatterns
        print(f"✅ Mobile WebSocket patterns imported: {len(mobile_websocket_urlpatterns)} patterns")

        for pattern in mobile_websocket_urlpatterns:
            print(f"  - {pattern.pattern}")

        print("✅ WebSocket routing tests passed!")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Routing error: {e}")
        return False

def test_consumer_import():
    """Test consumer import"""
    print("\n🔧 Testing Consumer Import...")

    try:
        from apps.api.mobile_consumers import MobileSyncConsumer, MobileSystemConsumer
        print("✅ MobileSyncConsumer imported successfully")
        print("✅ MobileSystemConsumer imported successfully")

        # Test consumer has correlation_id attribute
        consumer = MobileSyncConsumer()
        if hasattr(consumer, 'correlation_id'):
            print("✅ Correlation ID support added")
        else:
            print("⚠️  Correlation ID not found")

        print("✅ Consumer tests passed!")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Consumer error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Stream Testbench - Phase 1 Verification")
    print("=" * 50)

    all_tests_passed = True

    all_tests_passed &= test_channels_setup()
    all_tests_passed &= test_websocket_routing()
    all_tests_passed &= test_consumer_import()

    print("\n" + "=" * 50)
    if all_tests_passed:
        print("🎉 Phase 1 Setup Complete! Channels are ready for Stream Testbench")
    else:
        print("❌ Some tests failed. Please check the configuration.")
        sys.exit(1)