#!/bin/bash

###############################################################################
# PgBouncer Setup Script for Django 5 Enterprise Application
#
# This script automates the installation and configuration of PgBouncer
# for optimal PostgreSQL connection pooling.
#
# Features:
# - Automated installation across different Linux distributions
# - Security-hardened configuration
# - Monitoring and alerting setup
# - Integration with systemd
# - Log rotation configuration
#
# Usage:
#   sudo ./setup_pgbouncer.sh [environment]
#
# Environments: production, staging, development
#
# Requirements:
# - Root or sudo access
# - PostgreSQL server accessible
# - Network connectivity to database server
###############################################################################

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVIRONMENT="${1:-production}"
PGBOUNCER_USER="pgbouncer"
PGBOUNCER_GROUP="pgbouncer"
CONFIG_DIR="/etc/pgbouncer"
LOG_DIR="/var/log/pgbouncer"
RUN_DIR="/var/run/pgbouncer"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        exit 1
    fi
}

# Detect Linux distribution
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        DISTRO="$ID"
        VERSION="$VERSION_ID"
    else
        log_error "Cannot detect Linux distribution"
        exit 1
    fi

    log_info "Detected distribution: $DISTRO $VERSION"
}

# Install PgBouncer
install_pgbouncer() {
    log_info "Installing PgBouncer..."

    case "$DISTRO" in
        ubuntu|debian)
            apt-get update
            apt-get install -y pgbouncer postgresql-client
            ;;
        centos|rhel|fedora)
            if command -v dnf &> /dev/null; then
                dnf install -y pgbouncer postgresql
            else
                yum install -y pgbouncer postgresql
            fi
            ;;
        amazon)
            yum install -y pgbouncer postgresql
            ;;
        *)
            log_error "Unsupported distribution: $DISTRO"
            exit 1
            ;;
    esac

    log_info "PgBouncer installed successfully"
}

# Create system user and directories
setup_user_and_directories() {
    log_info "Setting up system user and directories..."

    # Create pgbouncer user if it doesn't exist
    if ! id "$PGBOUNCER_USER" &>/dev/null; then
        useradd --system --home-dir /var/lib/pgbouncer --shell /bin/false "$PGBOUNCER_USER"
        log_info "Created system user: $PGBOUNCER_USER"
    fi

    # Create directories
    mkdir -p "$CONFIG_DIR" "$LOG_DIR" "$RUN_DIR"

    # Set permissions
    chown -R "$PGBOUNCER_USER:$PGBOUNCER_GROUP" "$CONFIG_DIR" "$LOG_DIR" "$RUN_DIR"
    chmod 750 "$CONFIG_DIR" "$LOG_DIR" "$RUN_DIR"

    log_info "Directories created and permissions set"
}

# Install configuration files
install_configuration() {
    log_info "Installing PgBouncer configuration..."

    # Copy configuration files
    cp "$SCRIPT_DIR/pgbouncer.ini" "$CONFIG_DIR/"
    cp "$SCRIPT_DIR/userlist.txt" "$CONFIG_DIR/"

    # Set secure permissions on configuration files
    chmod 640 "$CONFIG_DIR/pgbouncer.ini"
    chmod 600 "$CONFIG_DIR/userlist.txt"
    chown "$PGBOUNCER_USER:$PGBOUNCER_GROUP" "$CONFIG_DIR"/*

    log_info "Configuration files installed"

    # Environment-specific adjustments
    case "$ENVIRONMENT" in
        production)
            sed -i 's/listen_addr = 127.0.0.1/listen_addr = 0.0.0.0/' "$CONFIG_DIR/pgbouncer.ini"
            sed -i 's/pool_mode = transaction/pool_mode = transaction/' "$CONFIG_DIR/pgbouncer.ini"
            sed -i 's/max_client_conn = 200/max_client_conn = 500/' "$CONFIG_DIR/pgbouncer.ini"
            ;;
        staging)
            sed -i 's/max_client_conn = 200/max_client_conn = 100/' "$CONFIG_DIR/pgbouncer.ini"
            ;;
        development)
            sed -i 's/max_client_conn = 200/max_client_conn = 50/' "$CONFIG_DIR/pgbouncer.ini"
            sed -i 's/log_connections = 1/log_connections = 0/' "$CONFIG_DIR/pgbouncer.ini"
            ;;
    esac

    log_info "Environment-specific configuration applied for: $ENVIRONMENT"
}

# Setup systemd service
setup_systemd_service() {
    log_info "Setting up systemd service..."

    cat > /etc/systemd/system/pgbouncer.service << EOF
[Unit]
Description=PgBouncer PostgreSQL Connection Pooler
Documentation=man:pgbouncer(1)
After=network.target postgresql.service
Requires=network.target

[Service]
Type=forking
User=$PGBOUNCER_USER
Group=$PGBOUNCER_GROUP
ExecStart=/usr/bin/pgbouncer -d $CONFIG_DIR/pgbouncer.ini
ExecReload=/bin/kill -HUP \$MAINPID
PIDFile=$RUN_DIR/pgbouncer.pid
LimitNOFILE=65536

# Security settings
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$LOG_DIR $RUN_DIR
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes

# Restart policy
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable pgbouncer

    log_info "Systemd service configured and enabled"
}

# Setup log rotation
setup_log_rotation() {
    log_info "Setting up log rotation..."

    cat > /etc/logrotate.d/pgbouncer << EOF
$LOG_DIR/pgbouncer.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 $PGBOUNCER_USER $PGBOUNCER_GROUP
    postrotate
        systemctl reload pgbouncer > /dev/null 2>&1 || true
    endscript
}
EOF

    log_info "Log rotation configured"
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring scripts..."

    # Create monitoring script
    cat > /usr/local/bin/pgbouncer_monitor.sh << 'EOF'
#!/bin/bash

# PgBouncer monitoring script
# Checks pool status and alerts on issues

PGBOUNCER_HOST="localhost"
PGBOUNCER_PORT="6432"
PGBOUNCER_USER="pgbouncer_admin"

# Check if PgBouncer is running
if ! systemctl is-active --quiet pgbouncer; then
    echo "CRITICAL: PgBouncer service is not running"
    exit 2
fi

# Check pool status
POOL_STATS=$(psql -h "$PGBOUNCER_HOST" -p "$PGBOUNCER_PORT" -U "$PGBOUNCER_USER" -d pgbouncer -t -c "SHOW POOLS;" 2>/dev/null)

if [[ -z "$POOL_STATS" ]]; then
    echo "WARNING: Unable to retrieve pool statistics"
    exit 1
fi

# Check for pool saturation (>90% usage)
while IFS='|' read -r database user cl_active cl_waiting sv_active sv_idle sv_used sv_tested sv_login maxwait pool_mode; do
    if [[ -n "$cl_active" && -n "$sv_active" ]]; then
        # Remove whitespace
        cl_active=$(echo "$cl_active" | xargs)
        sv_active=$(echo "$sv_active" | xargs)
        database=$(echo "$database" | xargs)

        # Skip header row
        if [[ "$database" != "database" && "$cl_active" -gt 0 ]]; then
            if [[ "$sv_active" -gt 0 ]]; then
                usage_percent=$(( (sv_active * 100) / (sv_active + sv_idle) ))
                if [[ "$usage_percent" -gt 90 ]]; then
                    echo "WARNING: Pool $database usage at $usage_percent%"
                fi
            fi
        fi
    fi
done <<< "$POOL_STATS"

echo "OK: PgBouncer pools are healthy"
exit 0
EOF

    chmod +x /usr/local/bin/pgbouncer_monitor.sh

    # Create cron job for monitoring
    cat > /etc/cron.d/pgbouncer-monitor << EOF
# PgBouncer monitoring - run every 5 minutes
*/5 * * * * $PGBOUNCER_USER /usr/local/bin/pgbouncer_monitor.sh >> $LOG_DIR/monitor.log 2>&1
EOF

    log_info "Monitoring configured"
}

# Configure firewall
configure_firewall() {
    log_info "Configuring firewall..."

    if command -v ufw &> /dev/null; then
        # Ubuntu/Debian with UFW
        ufw allow 6432/tcp comment "PgBouncer"
        log_info "UFW firewall rule added"
    elif command -v firewall-cmd &> /dev/null; then
        # CentOS/RHEL/Fedora with firewalld
        firewall-cmd --permanent --add-port=6432/tcp
        firewall-cmd --reload
        log_info "Firewalld rule added"
    else
        log_warn "No supported firewall found. Please manually open port 6432"
    fi
}

# Validate configuration
validate_configuration() {
    log_info "Validating PgBouncer configuration..."

    # Test configuration syntax
    if pgbouncer -T "$CONFIG_DIR/pgbouncer.ini"; then
        log_info "Configuration syntax is valid"
    else
        log_error "Configuration syntax error"
        exit 1
    fi
}

# Start services
start_services() {
    log_info "Starting PgBouncer service..."

    systemctl start pgbouncer

    if systemctl is-active --quiet pgbouncer; then
        log_info "PgBouncer started successfully"
    else
        log_error "Failed to start PgBouncer"
        systemctl status pgbouncer
        exit 1
    fi
}

# Display post-installation information
show_post_install_info() {
    cat << EOF

${GREEN}========================================
PgBouncer Installation Complete!
========================================${NC}

Environment: $ENVIRONMENT
Configuration: $CONFIG_DIR/pgbouncer.ini
Logs: $LOG_DIR/pgbouncer.log
Service: systemctl {start|stop|restart|status} pgbouncer

${YELLOW}Next Steps:${NC}
1. Update database credentials in $CONFIG_DIR/userlist.txt
2. Modify connection strings in Django settings:
   - Change port from 5432 to 6432
   - Keep hostname as database server
3. Test connections: psql -h localhost -p 6432 -U your_user your_database
4. Monitor with: psql -h localhost -p 6432 -U pgbouncer_admin -d pgbouncer

${YELLOW}Monitoring Commands:${NC}
- SHOW POOLS;       # Pool status
- SHOW DATABASES;   # Database configuration
- SHOW STATS;       # Connection statistics
- SHOW CLIENTS;     # Active clients

${YELLOW}Security Notes:${NC}
- Update passwords in userlist.txt
- Use SCRAM-SHA-256 for production
- Restrict network access to port 6432
- Monitor logs regularly

${GREEN}Happy connection pooling!${NC}

EOF
}

# Main installation function
main() {
    log_info "Starting PgBouncer installation for $ENVIRONMENT environment..."

    check_root
    detect_distro
    install_pgbouncer
    setup_user_and_directories
    install_configuration
    setup_systemd_service
    setup_log_rotation
    setup_monitoring
    configure_firewall
    validate_configuration
    start_services
    show_post_install_info

    log_info "PgBouncer setup completed successfully!"
}

# Run main function
main "$@"