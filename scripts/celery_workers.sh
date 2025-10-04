#!/bin/bash

# Celery Worker Deployment Script - Optimized Multi-Queue Architecture
# This script starts specialized workers for different business domains
# Usage: ./scripts/celery_workers.sh [start|stop|restart|status]

set -e  # Exit on any error

# Configuration
PROJECT_DIR="/Users/amar/Desktop/MyCode/DJANGO5-master"
CELERY_APP="intelliwiz_config"
LOG_LEVEL="INFO"
LOG_DIR="${PROJECT_DIR}/logs/celery"
PIDFILE_DIR="${PROJECT_DIR}/run"

# Worker Configuration
declare -A WORKERS=(
    # Critical Priority Workers - Immediate response
    ["critical"]="--queues=critical --concurrency=4 --prefetch-multiplier=2 --max-tasks-per-child=500"

    # High Priority Workers - User-facing operations
    ["high_priority"]="--queues=high_priority --concurrency=6 --prefetch-multiplier=3 --max-tasks-per-child=1000"

    # Email Workers - Dedicated email processing
    ["email"]="--queues=email --concurrency=4 --prefetch-multiplier=4 --max-tasks-per-child=1000"

    # Report Workers - Background analytics
    ["reports"]="--queues=reports --concurrency=4 --prefetch-multiplier=5 --max-tasks-per-child=800"

    # External API Workers - With circuit breaker protection
    ["external_api"]="--queues=external_api --concurrency=3 --prefetch-multiplier=2 --max-tasks-per-child=500"

    # Maintenance Workers - Cleanup and background tasks
    ["maintenance"]="--queues=maintenance,default --concurrency=2 --prefetch-multiplier=10 --max-tasks-per-child=2000"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create necessary directories
create_directories() {
    mkdir -p "$LOG_DIR"
    mkdir -p "$PIDFILE_DIR"
    echo -e "${BLUE}Created directories: $LOG_DIR, $PIDFILE_DIR${NC}"
}

# Check if worker is running
is_worker_running() {
    local worker_name=$1
    local pidfile="${PIDFILE_DIR}/celery_${worker_name}.pid"

    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            return 0  # Running
        else
            rm -f "$pidfile"  # Clean up stale pidfile
            return 1  # Not running
        fi
    fi
    return 1  # Not running
}

# Start a specific worker
start_worker() {
    local worker_name=$1
    local worker_config=${WORKERS[$worker_name]}

    if is_worker_running "$worker_name"; then
        echo -e "${YELLOW}Worker $worker_name is already running${NC}"
        return 0
    fi

    echo -e "${BLUE}Starting $worker_name worker...${NC}"

    # Start worker in background with comprehensive logging
    nohup celery -A "$CELERY_APP" worker \
        $worker_config \
        --hostname="${worker_name}_worker@%h" \
        --loglevel="$LOG_LEVEL" \
        --logfile="${LOG_DIR}/celery_${worker_name}.log" \
        --pidfile="${PIDFILE_DIR}/celery_${worker_name}.pid" \
        --time-limit=3600 \
        --soft-time-limit=1800 \
        --without-gossip \
        --without-mingle \
        --without-heartbeat \
        --optimization=fair \
        > "${LOG_DIR}/celery_${worker_name}_startup.log" 2>&1 &

    # Wait a moment and check if it started successfully
    sleep 2
    if is_worker_running "$worker_name"; then
        echo -e "${GREEN}✓ Worker $worker_name started successfully${NC}"
    else
        echo -e "${RED}✗ Failed to start worker $worker_name${NC}"
        echo "Check logs: ${LOG_DIR}/celery_${worker_name}_startup.log"
        return 1
    fi
}

# Stop a specific worker
stop_worker() {
    local worker_name=$1
    local pidfile="${PIDFILE_DIR}/celery_${worker_name}.pid"

    if ! is_worker_running "$worker_name"; then
        echo -e "${YELLOW}Worker $worker_name is not running${NC}"
        return 0
    fi

    echo -e "${BLUE}Stopping $worker_name worker...${NC}"

    local pid=$(cat "$pidfile")

    # Send TERM signal first (graceful shutdown)
    kill -TERM "$pid"

    # Wait for graceful shutdown
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt 30 ]; do
        sleep 1
        ((count++))
    done

    # Force kill if still running
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}Forcing termination of $worker_name worker...${NC}"
        kill -KILL "$pid"
    fi

    rm -f "$pidfile"
    echo -e "${GREEN}✓ Worker $worker_name stopped${NC}"
}

# Show worker status
show_worker_status() {
    local worker_name=$1

    if is_worker_running "$worker_name"; then
        local pid=$(cat "${PIDFILE_DIR}/celery_${worker_name}.pid")
        local memory=$(ps -o rss= -p "$pid" | awk '{print int($1/1024)}')
        echo -e "${GREEN}✓ $worker_name\t\tRunning\t\tPID: $pid\t\tMemory: ${memory}MB${NC}"
    else
        echo -e "${RED}✗ $worker_name\t\tStopped${NC}"
    fi
}

# Start all workers
start_all() {
    echo -e "${BLUE}Starting all Celery workers...${NC}"
    create_directories

    # Start workers in priority order
    local workers_order=("critical" "high_priority" "email" "reports" "external_api" "maintenance")

    for worker in "${workers_order[@]}"; do
        start_worker "$worker"
        sleep 1  # Brief pause between worker starts
    done

    echo -e "${GREEN}All workers started${NC}"
}

# Stop all workers
stop_all() {
    echo -e "${BLUE}Stopping all Celery workers...${NC}"

    for worker in "${!WORKERS[@]}"; do
        stop_worker "$worker"
    done

    echo -e "${GREEN}All workers stopped${NC}"
}

# Show status of all workers
status_all() {
    echo -e "${BLUE}Celery Worker Status:${NC}"
    echo -e "Worker Name\t\tStatus\t\tProcess Info"
    echo "--------------------------------------------------------"

    for worker in "${!WORKERS[@]}"; do
        show_worker_status "$worker"
    done

    # Show queue statistics if available
    echo ""
    echo -e "${BLUE}Queue Statistics:${NC}"
    celery -A "$CELERY_APP" inspect active_queues 2>/dev/null || echo "Unable to retrieve queue stats"
}

# Health check for workers
health_check() {
    echo -e "${BLUE}Performing health check...${NC}"

    local unhealthy_workers=()

    for worker in "${!WORKERS[@]}"; do
        if ! is_worker_running "$worker"; then
            unhealthy_workers+=("$worker")
        fi
    done

    if [ ${#unhealthy_workers[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ All workers are healthy${NC}"
        return 0
    else
        echo -e "${RED}✗ Unhealthy workers: ${unhealthy_workers[*]}${NC}"
        return 1
    fi
}

# Monitor worker performance
monitor() {
    echo -e "${BLUE}Celery Worker Monitoring (Press Ctrl+C to exit)${NC}"

    while true; do
        clear
        echo "=== Celery Worker Monitor - $(date) ==="
        status_all

        # Show active tasks
        echo ""
        echo -e "${BLUE}Active Tasks:${NC}"
        celery -A "$CELERY_APP" inspect active 2>/dev/null | head -20 || echo "No active tasks"

        sleep 5
    done
}

# Main script logic
case "$1" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_all
        ;;
    status)
        status_all
        ;;
    health)
        health_check
        ;;
    monitor)
        monitor
        ;;
    worker)
        if [ -n "$2" ]; then
            case "$3" in
                start)
                    create_directories
                    start_worker "$2"
                    ;;
                stop)
                    stop_worker "$2"
                    ;;
                status)
                    show_worker_status "$2"
                    ;;
                *)
                    echo "Usage: $0 worker <worker_name> [start|stop|status]"
                    exit 1
                    ;;
            esac
        else
            echo "Available workers: ${!WORKERS[*]}"
        fi
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|status|health|monitor]"
        echo "       $0 worker <worker_name> [start|stop|status]"
        echo ""
        echo "Available workers: ${!WORKERS[*]}"
        echo ""
        echo "Examples:"
        echo "  $0 start              # Start all workers"
        echo "  $0 worker critical start    # Start only critical worker"
        echo "  $0 status             # Show all worker status"
        echo "  $0 monitor            # Real-time monitoring"
        exit 1
        ;;
esac