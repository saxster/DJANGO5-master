#!/usr/bin/env python3
"""
Task 9 Integration Verification Script

Verifies that anomaly WebSocket broadcasts are properly integrated.
"""

import ast
import sys


def check_method_exists(filepath, class_name, method_name):
    """Check if a method exists in a class."""
    with open(filepath, 'r') as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    return True, len(item.body)
    return False, 0


def check_method_call(filepath, method_name):
    """Check if a method is called in a file."""
    with open(filepath, 'r') as f:
        content = f.read()
    return method_name in content


def main():
    """Run verification checks."""
    print("=" * 60)
    print("TASK 9 INTEGRATION VERIFICATION")
    print("=" * 60)
    print()

    checks_passed = 0
    checks_total = 0

    # Check 1: NOCWebSocketService.broadcast_anomaly exists
    print("1. Checking NOCWebSocketService.broadcast_anomaly()...")
    checks_total += 1
    exists, lines = check_method_exists(
        'apps/noc/services/websocket_service.py',
        'NOCWebSocketService',
        'broadcast_anomaly'
    )
    if exists:
        print(f"   ✅ Method exists ({lines} lines)")
        checks_passed += 1
    else:
        print("   ❌ Method NOT FOUND")

    # Check 2: NOCDashboardConsumer.anomaly_detected exists
    print("2. Checking NOCDashboardConsumer.anomaly_detected()...")
    checks_total += 1
    exists, lines = check_method_exists(
        'apps/noc/consumers/noc_dashboard_consumer.py',
        'NOCDashboardConsumer',
        'anomaly_detected'
    )
    if exists:
        print(f"   ✅ Method exists ({lines} lines)")
        checks_passed += 1
    else:
        print("   ❌ Method NOT FOUND")

    # Check 3: SecurityAnomalyOrchestrator calls broadcast_anomaly
    print("3. Checking SecurityAnomalyOrchestrator integration...")
    checks_total += 1
    if check_method_call(
        'apps/noc/security_intelligence/services/security_anomaly_orchestrator.py',
        'broadcast_anomaly'
    ):
        print("   ✅ broadcast_anomaly() called in orchestrator")
        checks_passed += 1
    else:
        print("   ❌ broadcast_anomaly() NOT called in orchestrator")

    # Check 4: Test file exists
    print("4. Checking test file exists...")
    checks_total += 1
    try:
        with open('apps/noc/tests/test_services/test_websocket_anomaly_broadcast.py', 'r') as f:
            content = f.read()
            test_count = content.count('def test_')
            print(f"   ✅ Test file exists ({test_count} tests)")
            checks_passed += 1
    except FileNotFoundError:
        print("   ❌ Test file NOT FOUND")

    # Check 5: Test coverage for broadcast_anomaly
    print("5. Checking test coverage...")
    checks_total += 1
    try:
        with open('apps/noc/tests/test_services/test_websocket_anomaly_broadcast.py', 'r') as f:
            content = f.read()
            if 'test_broadcast_anomaly_success' in content:
                print("   ✅ Broadcast tests present")
                checks_passed += 1
            else:
                print("   ❌ Broadcast tests NOT FOUND")
    except FileNotFoundError:
        print("   ❌ Test file NOT FOUND")

    # Check 6: Test coverage for consumer
    print("6. Checking consumer test coverage...")
    checks_total += 1
    try:
        with open('apps/noc/tests/test_services/test_websocket_anomaly_broadcast.py', 'r') as f:
            content = f.read()
            if 'test_consumer_receives_anomaly' in content:
                print("   ✅ Consumer tests present")
                checks_passed += 1
            else:
                print("   ❌ Consumer tests NOT FOUND")
    except FileNotFoundError:
        print("   ❌ Test file NOT FOUND")

    # Check 7: Integration test exists
    print("7. Checking integration test...")
    checks_total += 1
    try:
        with open('apps/noc/tests/test_services/test_websocket_anomaly_broadcast.py', 'r') as f:
            content = f.read()
            if 'test_end_to_end_anomaly_broadcast' in content:
                print("   ✅ Integration test present")
                checks_passed += 1
            else:
                print("   ❌ Integration test NOT FOUND")
    except FileNotFoundError:
        print("   ❌ Test file NOT FOUND")

    # Summary
    print()
    print("=" * 60)
    print(f"VERIFICATION SUMMARY: {checks_passed}/{checks_total} checks passed")
    print("=" * 60)

    if checks_passed == checks_total:
        print("✅ All integration checks passed!")
        print()
        print("Next steps:")
        print("  1. Run tests: pytest apps/noc/tests/test_services/test_websocket_anomaly_broadcast.py")
        print("  2. Update frontend to handle 'anomaly_detected' WebSocket messages")
        print("  3. Configure Redis channel layer for production")
        return 0
    else:
        print("❌ Some checks failed. Review implementation.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
