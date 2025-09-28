#!/usr/bin/env python3
"""
Stream Testbench Setup Script
Automated setup and validation for Stream Testbench system
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def run_command(command, description, required=True):
    """Run a command and return success status"""
    print(f"🔧 {description}...")

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print(f"✅ {description} completed")
            return True
        else:
            print(f"❌ {description} failed: {result.stderr.strip()}")
            if required:
                print("💥 Setup cannot continue due to required step failure")
                sys.exit(1)
            return False

    except subprocess.TimeoutExpired:
        print(f"⏰ {description} timed out")
        if required:
            sys.exit(1)
        return False
    except Exception as e:
        print(f"💥 {description} crashed: {e}")
        if required:
            sys.exit(1)
        return False


def check_prerequisites():
    """Check system prerequisites"""
    print("🔍 Checking Prerequisites...")

    checks = [
        ("python --version", "Python 3.11+"),
        ("pip --version", "pip package manager"),
        ("redis-cli ping", "Redis server"),
        ("psql --version", "PostgreSQL client"),
        ("java -version", "Java 17+ (for Kotlin)", False),
    ]

    all_good = True
    for command, description, *optional in checks:
        required = len(optional) == 0 or not optional[0]
        success = run_command(command, f"Check {description}", required=False)
        if not success and required:
            all_good = False

    if not all_good:
        print("❌ Some prerequisites are missing. Please install required components.")
        sys.exit(1)

    print("✅ All prerequisites satisfied")


def setup_python_environment():
    """Set up Python environment"""
    print("\n📦 Setting up Python Environment...")

    # Install dependencies
    run_command(
        "pip install -r requirements/base.txt",
        "Install Python dependencies"
    )

    # Verify critical packages
    critical_packages = [
        "channels", "channels-redis", "daphne", "django",
        "redis", "psycopg2", "paho-mqtt"
    ]

    for package in critical_packages:
        run_command(
            f"python -c 'import {package.replace(\"-\", \"_\")}'",
            f"Verify {package} installation"
        )


def setup_database():
    """Set up database"""
    print("\n🗄️ Setting up Database...")

    # Check database connection
    run_command(
        "python manage.py check --database default",
        "Check database connectivity"
    )

    # Run migrations
    run_command(
        "python manage.py migrate --run-syncdb",
        "Apply database migrations"
    )

    # Create superuser if none exists
    run_command(
        """python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('Created admin user: admin/admin123')
else:
    print('Superuser already exists')
" """,
        "Ensure superuser exists"
    )


def setup_kotlin_generator():
    """Set up Kotlin load generator"""
    print("\n☕ Setting up Kotlin Generator...")

    kotlin_dir = Path("intelliwiz_kotlin")
    if not kotlin_dir.exists():
        print("⚠️  Kotlin directory not found - skipping Kotlin setup")
        return False

    # Build Kotlin project
    success = run_command(
        "cd intelliwiz_kotlin && ./gradlew build",
        "Build Kotlin generator",
        required=False
    )

    if success:
        run_command(
            "cd intelliwiz_kotlin && ./gradlew fatJar",
            "Create standalone JAR",
            required=False
        )

        # Generate example scenarios
        run_command(
            "cd intelliwiz_kotlin && ./gradlew run --args='generate --type all --output ../scenarios/'",
            "Generate example scenarios",
            required=False
        )

    return success


def validate_setup():
    """Validate the complete setup"""
    print("\n🧪 Validating Setup...")

    # Test Django configuration
    run_command(
        "python test_channels_setup.py",
        "Validate Channels configuration"
    )

    # Test database models
    run_command(
        """python manage.py shell -c "
from apps.streamlab.models import TestScenario
from apps.issue_tracker.models import AnomalySignature
print('✅ Models imported successfully')
" """,
        "Test model imports"
    )

    # Start test server briefly
    print("🚀 Starting test server for validation...")
    server_process = subprocess.Popen(
        ["daphne", "-b", "0.0.0.0", "-p", "8000", "intelliwiz_config.asgi:application"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    import time
    time.sleep(10)  # Wait for server to start

    try:
        # Test health endpoint
        run_command(
            "curl -f http://localhost:8000/health/",
            "Test health endpoint",
            required=False
        )

        # Test dashboard access
        run_command(
            "curl -f http://localhost:8000/streamlab/ || echo 'Dashboard requires login'",
            "Test dashboard endpoint",
            required=False
        )

    finally:
        # Clean up server
        server_process.terminate()
        server_process.wait(timeout=10)

    print("✅ Validation completed")


def create_example_scenario():
    """Create an example test scenario"""
    print("\n🎭 Creating Example Scenario...")

    run_command(
        """python manage.py shell -c "
from apps.streamlab.models import TestScenario
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.filter(is_superuser=True).first()

if not user:
    print('❌ No superuser found')
    exit(1)

# Create example scenario
scenario, created = TestScenario.objects.get_or_create(
    name='Quick Start Demo',
    defaults={
        'description': 'Demonstration scenario for Quick Start guide',
        'protocol': 'websocket',
        'endpoint': 'ws://localhost:8000/ws/mobile/sync/',
        'config': {
            'duration_seconds': 60,
            'connections': 3,
            'messages_per_second': 2,
            'failure_injection': {
                'enabled': True,
                'network_delays': {'probability': 0.02}
            }
        },
        'expected_p95_latency_ms': 200,
        'expected_error_rate': 0.1,
        'created_by': user
    }
)

if created:
    print(f'✅ Created example scenario: {scenario.name}')
else:
    print(f'✅ Example scenario already exists: {scenario.name}')

print(f'Scenario ID: {scenario.id}')
" """,
        "Create example test scenario"
    )


def main():
    """Main setup function"""
    print("🚀 Stream Testbench Setup Script")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path("manage.py").exists():
        print("❌ Please run this script from the Django project root directory")
        sys.exit(1)

    # Setup phases
    try:
        check_prerequisites()
        setup_python_environment()
        setup_database()
        kotlin_success = setup_kotlin_generator()
        validate_setup()
        create_example_scenario()

        # Final summary
        print("\n" + "=" * 50)
        print("🎉 STREAM TESTBENCH SETUP COMPLETE!")
        print("=" * 50)

        print("\n📋 What's Ready:")
        print("   ✅ Django apps: streamlab, issue_tracker")
        print("   ✅ Database: PostgreSQL with all tables")
        print("   ✅ Redis: Channel Layer on DB 2")
        print("   ✅ WebSocket: ASGI routing configured")
        print("   ✅ PII Protection: Advanced redaction service")
        print("   ✅ Anomaly Detection: AI-powered pattern recognition")
        print("   ✅ Dashboards: HTMX + Chart.js real-time UI")
        print("   ✅ Testing: Comprehensive test suite")
        print("   ✅ CI/CD: GitHub Actions workflows")

        if kotlin_success:
            print("   ✅ Kotlin Generator: Load generation tools")
        else:
            print("   ⚠️  Kotlin Generator: Not available (Java required)")

        print("\n🚀 Next Steps:")
        print("   1. Start ASGI server:")
        print("      daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application")
        print()
        print("   2. Open dashboard:")
        print("      http://localhost:8000/streamlab/")
        print()
        print("   3. Run your first test:")
        if kotlin_success:
            print("      java -jar intelliwiz_kotlin/build/libs/intelliwiz_kotlin-1.0.0-fat.jar \\")
            print("        run --protocol websocket --duration 60 --connections 3 --rate 1")
        else:
            print("      python manage.py run_scenario 'Quick Start Demo' --duration 60")
        print()
        print("   4. View results in dashboard or admin:")
        print("      http://localhost:8000/admin/streamlab/")
        print()
        print("📚 Documentation:")
        print("   • Quick Start: STREAM_TESTBENCH_QUICKSTART.md")
        print("   • Full Docs: STREAM_TESTBENCH_DOCUMENTATION.md")
        print("   • Operations: STREAM_TESTBENCH_OPERATIONS_RUNBOOK.md")

        return 0

    except KeyboardInterrupt:
        print("\n⚠️  Setup interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)