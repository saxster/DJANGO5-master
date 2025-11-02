#!/bin/bash
#
# Message Bus Health Check Script
#
# Verifies all message bus components are healthy:
# - Redis (Celery broker, result backend, channel layers)
# - MQTT Broker (mosquitto)
# - Celery Workers (critical, general, ML)
# - MQTT Subscriber
# - WebSocket Channel Layer
# - Prometheus Metrics Endpoint
#
# Exit Codes:
#   0 = All healthy
#   1 = One or more components unhealthy
#
# Usage:
#   ./scripts/health_check_message_bus.sh
#   ./scripts/health_check_message_bus.sh --verbose
#
# Author: DevOps Team
# Date: November 1, 2025

set -e  # Exit on first error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

VERBOSE=false
if [[ "$1" == "--verbose" ]]; then
    VERBOSE=true
fi

# Track overall health
ALL_HEALTHY=true

echo "========================================"
echo "Message Bus Health Check"
echo "========================================"
echo ""

# Function to check component
check_component() {
    local name="$1"
    local command="$2"
    local expected="$3"

    if $VERBOSE; then
        echo -n "Checking $name... "
    fi

    if output=$(eval "$command" 2>&1); then
        if [[ -n "$expected" ]]; then
            if echo "$output" | grep -q "$expected"; then
                if $VERBOSE; then
                    echo -e "${GREEN}✓ HEALTHY${NC}"
                else
                    echo -e "${GREEN}✓${NC} $name"
                fi
                return 0
            else
                if $VERBOSE; then
                    echo -e "${RED}✗ UNHEALTHY${NC} (expected: $expected, got: $output)"
                else
                    echo -e "${RED}✗${NC} $name (unexpected output)"
                fi
                ALL_HEALTHY=false
                return 1
            fi
        else
            if $VERBOSE; then
                echo -e "${GREEN}✓ HEALTHY${NC}"
            else
                echo -e "${GREEN}✓${NC} $name"
            fi
            return 0
        fi
    else
        if $VERBOSE; then
            echo -e "${RED}✗ UNHEALTHY${NC} (command failed: $output)"
        else
            echo -e "${RED}✗${NC} $name (command failed)"
        fi
        ALL_HEALTHY=false
        return 1
    fi
}

# 1. Redis Health Check
echo "1. Redis..."
check_component "Redis DB 0 (Celery broker)" \
    "redis-cli -n 0 ping" \
    "PONG"

check_component "Redis DB 1 (Celery results)" \
    "redis-cli -n 1 ping" \
    "PONG"

check_component "Redis DB 2 (Channel layers)" \
    "redis-cli -n 2 ping" \
    "PONG"

# 2. MQTT Broker Health Check
echo ""
echo "2. MQTT Broker..."
check_component "Mosquitto broker" \
    "mosquitto_sub -h localhost -t '\$SYS/broker/uptime' -C 1 -W 2" \
    ""

# 3. Celery Workers Health Check
echo ""
echo "3. Celery Workers..."

# Check if celery command is available
if command -v celery &> /dev/null; then
    check_component "Celery workers ping" \
        "celery -A intelliwiz_config inspect ping -t 5 2>&1" \
        "pong"

    # Check specific queues are being consumed
    if $VERBOSE; then
        echo "   Checking active queues..."
        celery -A intelliwiz_config inspect active_queues 2>&1 | grep -E "(critical|high_priority|external_api|ml_training)" || true
    fi
else
    echo -e "${YELLOW}⚠${NC} Celery command not found (workers may be running in containers)"
fi

# 4. MQTT Subscriber Health Check
echo ""
echo "4. MQTT Subscriber..."
if pgrep -f "mqtt_subscriber.py" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} MQTT Subscriber process running"

    # Check if log file shows recent activity
    if [[ -f "/var/log/mqtt_subscriber.log" ]]; then
        recent_lines=$(tail -n 5 /var/log/mqtt_subscriber.log 2>/dev/null || echo "")
        if $VERBOSE && [[ -n "$recent_lines" ]]; then
            echo "   Recent activity:"
            echo "$recent_lines" | sed 's/^/   /'
        fi
    fi
else
    echo -e "${RED}✗${NC} MQTT Subscriber process NOT running"
    ALL_HEALTHY=false
fi

# 5. WebSocket Channel Layer Health Check
echo ""
echo "5. WebSocket Channel Layer..."

# Use Python to check channel layer
if command -v python3 &> /dev/null; then
    check_component "Django Channels layer" \
        "python3 -c 'import os; os.environ[\"DJANGO_SETTINGS_MODULE\"]=\"intelliwiz_config.settings\"; import django; django.setup(); from channels.layers import get_channel_layer; assert get_channel_layer() is not None; print(\"OK\")' 2>&1" \
        "OK"
else
    echo -e "${YELLOW}⚠${NC} Python not available, skipping channel layer check"
fi

# 6. Prometheus Metrics Endpoint
echo ""
echo "6. Prometheus Metrics..."
check_component "Prometheus /metrics/export/" \
    "curl -sf http://localhost:8000/metrics/export/ 2>&1" \
    "celery"

# 7. Django Health Endpoint
echo ""
echo "7. Django Application..."
check_component "Django /monitoring/health/" \
    "curl -sf http://localhost:8000/monitoring/health/ 2>&1" \
    "healthy"

# Summary
echo ""
echo "========================================"
if $ALL_HEALTHY; then
    echo -e "${GREEN}✅ ALL COMPONENTS HEALTHY${NC}"
    echo "========================================"
    exit 0
else
    echo -e "${RED}❌ SOME COMPONENTS UNHEALTHY${NC}"
    echo "========================================"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check service status: systemctl status {redis,mosquitto,celery,mqtt-subscriber}"
    echo "  - Check logs: journalctl -u SERVICE_NAME -n 50"
    echo "  - See runbook: docs/operations/MESSAGE_BUS_RUNBOOK.md"
    exit 1
fi
