#!/bin/bash

# Redis Secure Setup Script for IntelliWiz Django Platform
# This script sets up Redis with security hardening and optimization

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

# Default values
ENVIRONMENT="${1:-development}"  # development or production
REDIS_VERSION="7.2"
REDIS_PORT=6379
REDIS_DATA_DIR="/var/lib/redis"
REDIS_LOG_DIR="/var/log/redis"

echo -e "${BLUE}🔧 Redis Secure Setup - Environment: $ENVIRONMENT${NC}"
echo "=================================================="

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

# Check if running as root or with sudo
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. This is recommended for system-wide installation."
    elif ! command -v sudo &> /dev/null; then
        print_error "sudo is required for system configuration. Please run with sudo or as root."
        exit 1
    fi
}

# Install Redis
install_redis() {
    echo -e "${BLUE}📦 Installing Redis...${NC}"

    if command -v redis-server &> /dev/null; then
        INSTALLED_VERSION=$(redis-server --version | grep -oP '(?<=v=)[0-9.]+')
        print_status "Redis already installed: v$INSTALLED_VERSION"
    else
        # Install based on OS
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if command -v apt-get &> /dev/null; then
                # Ubuntu/Debian
                sudo apt-get update
                sudo apt-get install -y redis-server redis-tools
            elif command -v yum &> /dev/null; then
                # CentOS/RHEL
                sudo yum install -y redis
            elif command -v dnf &> /dev/null; then
                # Fedora
                sudo dnf install -y redis
            else
                print_error "Unsupported Linux distribution"
                exit 1
            fi
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            if command -v brew &> /dev/null; then
                brew install redis
            else
                print_error "Homebrew is required for macOS installation"
                exit 1
            fi
        else
            print_error "Unsupported operating system: $OSTYPE"
            exit 1
        fi
        print_status "Redis installed successfully"
    fi
}

# Create Redis user and directories
setup_redis_user() {
    echo -e "${BLUE}👤 Setting up Redis user and directories...${NC}"

    # Create redis user if it doesn't exist
    if ! id "redis" &>/dev/null; then
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            sudo useradd --system --home-dir /var/lib/redis --shell /bin/false redis
        fi
        print_status "Created redis user"
    fi

    # Create directories
    sudo mkdir -p "$REDIS_DATA_DIR"
    sudo mkdir -p "$REDIS_LOG_DIR"
    sudo mkdir -p "/etc/redis"

    # Set permissions
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo chown redis:redis "$REDIS_DATA_DIR"
        sudo chown redis:redis "$REDIS_LOG_DIR"
        sudo chmod 750 "$REDIS_DATA_DIR"
        sudo chmod 750 "$REDIS_LOG_DIR"
    fi

    print_status "Redis directories created and configured"
}

# Generate secure password
generate_redis_password() {
    if [[ "$ENVIRONMENT" == "production" ]]; then
        # Generate a strong password for production
        REDIS_PASSWORD=$(openssl rand -base64 32)
        echo "REDIS_PASSWORD=$REDIS_PASSWORD" > "$PROJECT_ROOT/.env.redis.production"
        print_status "Generated secure Redis password for production"
        print_warning "Password saved to .env.redis.production - KEEP THIS SECURE!"
    else
        # Use a fixed password for development
        REDIS_PASSWORD="dev_redis_password_2024"
        echo "REDIS_PASSWORD=$REDIS_PASSWORD" > "$PROJECT_ROOT/.env.redis.development"
        print_status "Set development Redis password"
    fi
}

# Configure Redis
configure_redis() {
    echo -e "${BLUE}⚙️  Configuring Redis...${NC}"

    # Copy appropriate configuration
    if [[ "$ENVIRONMENT" == "production" ]]; then
        CONFIG_SOURCE="$REDIS_CONFIG_DIR/redis-production.conf"
        CONFIG_DEST="/etc/redis/redis.conf"
    else
        CONFIG_SOURCE="$REDIS_CONFIG_DIR/redis-development.conf"
        CONFIG_DEST="/etc/redis/redis-dev.conf"
    fi

    # Substitute environment variables in config
    envsubst < "$CONFIG_SOURCE" | sudo tee "$CONFIG_DEST" > /dev/null

    # Set permissions
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo chown redis:redis "$CONFIG_DEST"
        sudo chmod 640 "$CONFIG_DEST"
    fi

    print_status "Redis configuration installed: $CONFIG_DEST"
}

# Setup systemd service (Linux only)
setup_systemd_service() {
    if [[ "$OSTYPE" == "linux-gnu"* ]] && command -v systemctl &> /dev/null; then
        echo -e "${BLUE}🔄 Setting up systemd service...${NC}"

        cat << EOF | sudo tee /etc/systemd/system/redis-youtility.service > /dev/null
[Unit]
Description=Advanced key-value store (IntelliWiz Redis)
After=network.target
Documentation=http://redis.io/documentation, man:redis-server(1)

[Service]
Type=notify
ExecStart=/usr/bin/redis-server /etc/redis/redis.conf
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

        sudo systemctl daemon-reload
        print_status "Systemd service created: redis-youtility"

        if [[ "$ENVIRONMENT" == "production" ]]; then
            sudo systemctl enable redis-youtility
            print_status "Redis service enabled for auto-start"
        fi
    fi
}

# Configure firewall (if needed)
configure_firewall() {
    if [[ "$ENVIRONMENT" == "production" ]] && command -v ufw &> /dev/null; then
        echo -e "${BLUE}🔒 Configuring firewall...${NC}"

        # Allow Redis port only from localhost by default
        sudo ufw allow from 127.0.0.1 to any port $REDIS_PORT
        print_status "Firewall configured for Redis"
        print_warning "Adjust firewall rules as needed for your network setup"
    fi
}

# Setup Redis monitoring
setup_monitoring() {
    echo -e "${BLUE}📊 Setting up Redis monitoring...${NC}"

    # Create monitoring script
    cat << 'EOF' > "$PROJECT_ROOT/scripts/monitor_redis.sh"
#!/bin/bash
# Redis monitoring script

REDIS_CLI="redis-cli"
if [ ! -z "$REDIS_PASSWORD" ]; then
    REDIS_CLI="redis-cli -a $REDIS_PASSWORD"
fi

echo "Redis Status:"
echo "============="
$REDIS_CLI ping
echo "Connected clients: $($REDIS_CLI info clients | grep connected_clients | cut -d: -f2 | tr -d '\r')"
echo "Used memory: $($REDIS_CLI info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')"
echo "Total commands: $($REDIS_CLI info stats | grep total_commands_processed | cut -d: -f2 | tr -d '\r')"
echo "Keyspace hits: $($REDIS_CLI info stats | grep keyspace_hits | cut -d: -f2 | tr -d '\r')"
echo "Keyspace misses: $($REDIS_CLI info stats | grep keyspace_misses | cut -d: -f2 | tr -d '\r')"

# Calculate hit ratio
HITS=$($REDIS_CLI info stats | grep keyspace_hits | cut -d: -f2 | tr -d '\r')
MISSES=$($REDIS_CLI info stats | grep keyspace_misses | cut -d: -f2 | tr -d '\r')
if [ "$HITS" -gt 0 ] || [ "$MISSES" -gt 0 ]; then
    HIT_RATIO=$(echo "scale=2; $HITS / ($HITS + $MISSES) * 100" | bc -l)
    echo "Hit ratio: ${HIT_RATIO}%"
fi
EOF

    chmod +x "$PROJECT_ROOT/scripts/monitor_redis.sh"
    print_status "Redis monitoring script created"
}

# Create backup script
create_backup_script() {
    echo -e "${BLUE}💾 Creating backup script...${NC}"

    cat << 'EOF' > "$PROJECT_ROOT/scripts/backup_redis.sh"
#!/bin/bash
# Redis backup script

BACKUP_DIR="/var/backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)
REDIS_DATA_DIR="/var/lib/redis"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup
echo "Creating Redis backup..."
cp "$REDIS_DATA_DIR/dump.rdb" "$BACKUP_DIR/dump_$DATE.rdb"
cp "$REDIS_DATA_DIR/appendonly.aof" "$BACKUP_DIR/appendonly_$DATE.aof" 2>/dev/null || true

# Compress backups
gzip "$BACKUP_DIR/dump_$DATE.rdb"
[ -f "$BACKUP_DIR/appendonly_$DATE.aof" ] && gzip "$BACKUP_DIR/appendonly_$DATE.aof"

# Remove old backups (older than 7 days)
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"
EOF

    chmod +x "$PROJECT_ROOT/scripts/backup_redis.sh"
    print_status "Redis backup script created"
}

# Optimize system settings
optimize_system() {
    if [[ "$ENVIRONMENT" == "production" ]] && [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo -e "${BLUE}🚀 Optimizing system settings...${NC}"

        # Add Redis-specific sysctl settings
        cat << EOF | sudo tee /etc/sysctl.d/50-redis.conf > /dev/null
# Redis optimizations
vm.overcommit_memory = 1
net.core.somaxconn = 65535
EOF

        # Disable transparent huge pages
        echo "echo never > /sys/kernel/mm/transparent_hugepage/enabled" | sudo tee -a /etc/rc.local > /dev/null

        # Apply settings
        sudo sysctl -p /etc/sysctl.d/50-redis.conf

        print_status "System optimizations applied"
    fi
}

# Main installation flow
main() {
    echo -e "${BLUE}Starting Redis secure setup for $ENVIRONMENT environment...${NC}"
    echo

    check_permissions
    install_redis
    setup_redis_user
    generate_redis_password
    configure_redis
    setup_systemd_service
    configure_firewall
    setup_monitoring
    create_backup_script
    optimize_system

    echo
    echo -e "${GREEN}🎉 Redis setup completed successfully!${NC}"
    echo "=================================================="
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Update your Django settings to use the new Redis configuration"
    echo "2. Start Redis service: sudo systemctl start redis-youtility"
    echo "3. Check Redis status: sudo systemctl status redis-youtility"
    echo "4. Monitor Redis: ./scripts/monitor_redis.sh"
    echo "5. Setup regular backups: ./scripts/backup_redis.sh"
    echo

    if [[ "$ENVIRONMENT" == "production" ]]; then
        print_warning "PRODUCTION SETUP COMPLETE"
        echo "- Review firewall settings"
        echo "- Configure SSL/TLS if needed"
        echo "- Set up Redis Sentinel for high availability"
        echo "- Configure monitoring and alerting"
    fi
}

# Run main function
main "$@"