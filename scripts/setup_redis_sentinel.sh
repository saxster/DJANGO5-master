#!/bin/bash

# Redis Sentinel High Availability Setup Script
# Sets up 3-node Sentinel cluster with master-replica Redis configuration

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REDIS_CONFIG_DIR="$PROJECT_ROOT/config/redis"
SENTINEL_CONFIG_DIR="$REDIS_CONFIG_DIR/sentinel"

# Default configuration
REDIS_PASSWORD=""
SENTINEL_PASSWORD=""
SETUP_MODE="${1:-single-machine}"  # single-machine or multi-machine

echo -e "${BLUE}🏗️  Redis Sentinel High Availability Setup${NC}"
echo "=================================================="
echo "Setup Mode: $SETUP_MODE"
echo

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Generate secure passwords
generate_passwords() {
    echo -e "${BLUE}🔐 Generating secure passwords...${NC}"

    REDIS_PASSWORD=$(openssl rand -base64 32)
    SENTINEL_PASSWORD=$(openssl rand -base64 32)

    # Save to environment file
    cat > "$PROJECT_ROOT/.env.sentinel" << EOF
# Redis Sentinel Configuration
REDIS_SENTINEL_ENABLED=true

# Redis Authentication
REDIS_PASSWORD=$REDIS_PASSWORD

# Sentinel Authentication
SENTINEL_PASSWORD=$SENTINEL_PASSWORD

# IP Configuration (update these for your network)
REDIS_MASTER_IP=127.0.0.1
REDIS_MASTER_PORT=6379
REDIS_REPLICA_IP=127.0.0.1
REDIS_REPLICA_PORT=6380

SENTINEL_1_IP=127.0.0.1
SENTINEL_1_PORT=26379
SENTINEL_2_IP=127.0.0.1
SENTINEL_2_PORT=26380
SENTINEL_3_IP=127.0.0.1
SENTINEL_3_PORT=26381

# Sentinel IDs (auto-generated)
SENTINEL_1_ID=$(openssl rand -hex 20)
SENTINEL_2_ID=$(openssl rand -hex 20)
SENTINEL_3_ID=$(openssl rand -hex 20)

# Random strings for command renaming
RANDOM_STRING_1=$(openssl rand -base64 16)
RANDOM_STRING_2=$(openssl rand -base64 16)
RANDOM_STRING_3=$(openssl rand -base64 16)

# Service Names
REDIS_MASTER_NAME=mymaster
EOF

    chmod 600 "$PROJECT_ROOT/.env.sentinel"
    print_status "Secure passwords generated and saved to .env.sentinel"
    print_warning "IMPORTANT: Keep .env.sentinel file secure and backed up!"
}

# Setup directory structure
setup_directories() {
    echo -e "${BLUE}📁 Setting up directory structure...${NC}"

    # Create Redis data directories
    sudo mkdir -p /var/lib/redis/master
    sudo mkdir -p /var/lib/redis/replica
    sudo mkdir -p /var/lib/redis/sentinel-1
    sudo mkdir -p /var/lib/redis/sentinel-2
    sudo mkdir -p /var/lib/redis/sentinel-3

    # Create log directories
    sudo mkdir -p /var/log/redis

    # Create backup directories
    sudo mkdir -p /var/backups/redis

    # Set permissions
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo chown -R redis:redis /var/lib/redis
        sudo chown -R redis:redis /var/log/redis
        sudo chown -R redis:redis /var/backups/redis

        sudo chmod 750 /var/lib/redis/*
        sudo chmod 750 /var/log/redis
        sudo chmod 750 /var/backups/redis
    fi

    print_status "Directory structure created"
}

# Install Sentinel configuration files
install_configurations() {
    echo -e "${BLUE}⚙️  Installing Redis and Sentinel configurations...${NC}"

    # Source environment variables
    if [[ -f "$PROJECT_ROOT/.env.sentinel" ]]; then
        source "$PROJECT_ROOT/.env.sentinel"
    else
        print_error ".env.sentinel file not found. Run generate_passwords first."
        exit 1
    fi

    # Install Redis configurations
    envsubst < "$SENTINEL_CONFIG_DIR/redis-master.conf" | sudo tee /etc/redis/redis-master.conf > /dev/null
    envsubst < "$SENTINEL_CONFIG_DIR/redis-replica.conf" | sudo tee /etc/redis/redis-replica.conf > /dev/null

    # Install Sentinel configurations
    envsubst < "$SENTINEL_CONFIG_DIR/redis-sentinel-1.conf" | sudo tee /etc/redis/sentinel-1.conf > /dev/null
    envsubst < "$SENTINEL_CONFIG_DIR/redis-sentinel-2.conf" | sudo tee /etc/redis/sentinel-2.conf > /dev/null
    envsubst < "$SENTINEL_CONFIG_DIR/redis-sentinel-3.conf" | sudo tee /etc/redis/sentinel-3.conf > /dev/null

    # Set permissions
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo chown redis:redis /etc/redis/redis-*.conf
        sudo chown redis:redis /etc/redis/sentinel-*.conf
        sudo chmod 640 /etc/redis/redis-*.conf
        sudo chmod 640 /etc/redis/sentinel-*.conf
    fi

    print_status "Configuration files installed"
}

# Create systemd services (Linux only)
create_systemd_services() {
    if [[ "$OSTYPE" == "linux-gnu"* ]] && command -v systemctl &> /dev/null; then
        echo -e "${BLUE}🔄 Creating systemd services...${NC}"

        # Redis Master service
        cat << EOF | sudo tee /etc/systemd/system/redis-master.service > /dev/null
[Unit]
Description=Redis Master Server (IntelliWiz HA)
After=network.target
Documentation=http://redis.io/documentation

[Service]
Type=notify
ExecStart=/usr/bin/redis-server /etc/redis/redis-master.conf
ExecReload=/bin/kill -USR2 \$MAINPID
TimeoutStopSec=0
Restart=always
User=redis
Group=redis

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectHome=yes
ProtectSystem=strict
ReadWritePaths=-/var/lib/redis
ReadWritePaths=-/var/log/redis

# Performance settings
LimitNOFILE=65536
LimitNPROC=65536

[Install]
WantedBy=multi-user.target
EOF

        # Redis Replica service
        cat << EOF | sudo tee /etc/systemd/system/redis-replica.service > /dev/null
[Unit]
Description=Redis Replica Server (IntelliWiz HA)
After=network.target redis-master.service
Documentation=http://redis.io/documentation

[Service]
Type=notify
ExecStart=/usr/bin/redis-server /etc/redis/redis-replica.conf
ExecReload=/bin/kill -USR2 \$MAINPID
TimeoutStopSec=0
Restart=always
User=redis
Group=redis

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectHome=yes
ProtectSystem=strict
ReadWritePaths=-/var/lib/redis
ReadWritePaths=-/var/log/redis

# Performance settings
LimitNOFILE=65536
LimitNPROC=65536

[Install]
WantedBy=multi-user.target
EOF

        # Sentinel services
        for i in {1..3}; do
            cat << EOF | sudo tee /etc/systemd/system/redis-sentinel-$i.service > /dev/null
[Unit]
Description=Redis Sentinel $i (IntelliWiz HA)
After=network.target
Documentation=http://redis.io/documentation

[Service]
Type=notify
ExecStart=/usr/bin/redis-sentinel /etc/redis/sentinel-$i.conf
ExecReload=/bin/kill -USR2 \$MAINPID
TimeoutStopSec=0
Restart=always
User=redis
Group=redis

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectHome=yes
ProtectSystem=strict
ReadWritePaths=-/var/lib/redis
ReadWritePaths=-/var/log/redis

# Performance settings
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
        done

        sudo systemctl daemon-reload
        print_status "Systemd services created for Redis Sentinel cluster"
    fi
}

# Create management scripts
create_management_scripts() {
    echo -e "${BLUE}🛠️  Creating management scripts...${NC}"

    # Sentinel cluster control script
    cat << 'EOF' > "$PROJECT_ROOT/scripts/sentinel_cluster.sh"
#!/bin/bash
# Redis Sentinel Cluster Management Script

SERVICES=(
    "redis-master"
    "redis-replica"
    "redis-sentinel-1"
    "redis-sentinel-2"
    "redis-sentinel-3"
)

case "$1" in
    start)
        echo "Starting Redis Sentinel cluster..."
        for service in "${SERVICES[@]}"; do
            echo "Starting $service..."
            sudo systemctl start $service
            sleep 2
        done
        echo "Cluster start completed"
        ;;
    stop)
        echo "Stopping Redis Sentinel cluster..."
        # Stop in reverse order
        for ((i=${#SERVICES[@]}-1; i>=0; i--)); do
            service="${SERVICES[$i]}"
            echo "Stopping $service..."
            sudo systemctl stop $service
            sleep 1
        done
        echo "Cluster stop completed"
        ;;
    restart)
        $0 stop
        sleep 5
        $0 start
        ;;
    status)
        echo "Redis Sentinel Cluster Status:"
        echo "=============================="
        for service in "${SERVICES[@]}"; do
            status=$(sudo systemctl is-active $service 2>/dev/null || echo "inactive")
            if [[ "$status" == "active" ]]; then
                echo "✅ $service: $status"
            else
                echo "❌ $service: $status"
            fi
        done
        ;;
    health)
        echo "Running health checks..."
        cd PROJECT_ROOT_PLACEHOLDER
        python manage.py sentinel_admin --status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|health}"
        exit 1
        ;;
esac
EOF

    # Replace placeholder with actual project root
    sed -i "s|PROJECT_ROOT_PLACEHOLDER|$PROJECT_ROOT|g" "$PROJECT_ROOT/scripts/sentinel_cluster.sh"
    chmod +x "$PROJECT_ROOT/scripts/sentinel_cluster.sh"

    # Failover test script
    cat << 'EOF' > "$PROJECT_ROOT/scripts/test_sentinel_failover.sh"
#!/bin/bash
# Redis Sentinel Failover Testing Script

echo "🧪 Redis Sentinel Failover Test"
echo "==============================="

# Load environment
if [[ -f .env.sentinel ]]; then
    source .env.sentinel
fi

echo "1. Checking cluster status..."
python manage.py sentinel_admin --status

echo -e "\n2. Testing failover capability..."
python manage.py sentinel_admin --failover-test

echo -e "\n3. Current master information..."
python manage.py sentinel_admin --masters

echo -e "\n4. Current replica information..."
python manage.py sentinel_admin --replicas

echo -e "\n✅ Sentinel failover test completed"
echo "To trigger actual failover (DANGEROUS):"
echo "redis-cli -p 26379 SENTINEL FAILOVER mymaster"
EOF

    chmod +x "$PROJECT_ROOT/scripts/test_sentinel_failover.sh"

    print_status "Management scripts created"
}

# Configure Django settings
configure_django_integration() {
    echo -e "${BLUE}⚙️  Configuring Django Sentinel integration...${NC}"

    # Create Django settings snippet
    cat << 'EOF' > "$PROJECT_ROOT/intelliwiz_config/settings/sentinel_integration.py"
# Redis Sentinel Integration - Auto-generated
# Include this in your environment-specific settings

import os

# Enable Sentinel mode
os.environ.setdefault('REDIS_SENTINEL_ENABLED', 'true')

# Import Sentinel configurations
from .redis_sentinel import SENTINEL_CACHES, SENTINEL_CHANNEL_LAYERS, SENTINEL_CELERY

# Override default configurations with Sentinel
CACHES = SENTINEL_CACHES
CHANNEL_LAYERS = SENTINEL_CHANNEL_LAYERS

# Update Celery configuration
CELERY_BROKER_URL = SENTINEL_CELERY['broker_url']
CELERY_RESULT_BACKEND = SENTINEL_CELERY['result_backend']
CELERY_BROKER_TRANSPORT_OPTIONS = SENTINEL_CELERY['broker_transport_options']
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = SENTINEL_CELERY['result_backend_transport_options']

# Sentinel-specific settings
REDIS_HA_ENABLED = True
REDIS_SENTINEL_MONITORING = True
REDIS_AUTOMATIC_FAILOVER = True

print("🔗 Redis Sentinel integration loaded - High Availability enabled")
EOF

    print_status "Django Sentinel integration configured"
    print_warning "Add 'from .sentinel_integration import *' to your settings file to enable"
}

# Validate setup
validate_setup() {
    echo -e "${BLUE}🔍 Validating Sentinel setup...${NC}"

    # Check if configuration files exist
    required_configs=(
        "/etc/redis/redis-master.conf"
        "/etc/redis/redis-replica.conf"
        "/etc/redis/sentinel-1.conf"
        "/etc/redis/sentinel-2.conf"
        "/etc/redis/sentinel-3.conf"
    )

    for config in "${required_configs[@]}"; do
        if [[ -f "$config" ]]; then
            print_status "Configuration exists: $(basename $config)"
        else
            print_error "Missing configuration: $config"
        fi
    done

    # Check if services are created
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        services=(
            "redis-master.service"
            "redis-replica.service"
            "redis-sentinel-1.service"
            "redis-sentinel-2.service"
            "redis-sentinel-3.service"
        )

        for service in "${services[@]}"; do
            if sudo systemctl list-unit-files | grep -q "$service"; then
                print_status "Service created: $service"
            else
                print_warning "Service not found: $service"
            fi
        done
    fi

    # Check Django integration
    if [[ -f "$PROJECT_ROOT/intelliwiz_config/settings/sentinel_integration.py" ]]; then
        print_status "Django Sentinel integration ready"
    else
        print_warning "Django integration not found"
    fi
}

# Display next steps
show_next_steps() {
    echo
    echo -e "${GREEN}🎉 Redis Sentinel setup completed!${NC}"
    echo "=================================================="
    echo -e "${YELLOW}Next steps:${NC}"
    echo
    echo "1. Update IP addresses in .env.sentinel for multi-machine setup"
    echo "2. Start the cluster: ./scripts/sentinel_cluster.sh start"
    echo "3. Check cluster status: ./scripts/sentinel_cluster.sh status"
    echo "4. Enable Django integration by adding to settings:"
    echo "   from .sentinel_integration import *"
    echo "5. Test failover: ./scripts/test_sentinel_failover.sh"
    echo "6. Monitor cluster health: python manage.py sentinel_admin --status"
    echo
    echo -e "${YELLOW}Configuration files:${NC}"
    echo "- Redis configs: /etc/redis/redis-{master,replica}.conf"
    echo "- Sentinel configs: /etc/redis/sentinel-{1,2,3}.conf"
    echo "- Environment: .env.sentinel"
    echo "- Management: scripts/sentinel_cluster.sh"
    echo
    echo -e "${YELLOW}Important:${NC}"
    echo "- Test failover procedures regularly"
    echo "- Monitor Sentinel logs for cluster events"
    echo "- Ensure network connectivity between all nodes"
    echo "- Configure firewall to allow Redis and Sentinel ports"

    if [[ "$SETUP_MODE" == "single-machine" ]]; then
        echo
        print_warning "SINGLE MACHINE SETUP - NOT RECOMMENDED FOR PRODUCTION"
        echo "For true high availability, deploy Redis and Sentinel on separate machines"
    fi
}

# Main setup flow
main() {
    echo "Starting Redis Sentinel setup..."
    echo

    # Check if running with proper permissions
    if [[ $EUID -ne 0 ]] && ! command -v sudo &> /dev/null; then
        print_error "This script requires root privileges or sudo access"
        exit 1
    fi

    # Run setup steps
    generate_passwords
    setup_directories
    install_configurations
    create_systemd_services
    create_management_scripts
    configure_django_integration
    validate_setup
    show_next_steps
}

# Run main function
main "$@"