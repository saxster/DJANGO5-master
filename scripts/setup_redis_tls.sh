#!/bin/bash
#
# Redis TLS/SSL Setup Script
# Automates certificate generation for PCI DSS Level 1 compliance
#
# PCI DSS 4.0.1 Requirement 4.2.1:
# - Use TLS 1.2+ for cardholder data transmission
# - Maintain certificate inventory
# - Track expiration and renewal
# - Effective: April 1, 2025 (mandatory)
#
# Usage:
#   sudo ./scripts/setup_redis_tls.sh
#   sudo ./scripts/setup_redis_tls.sh --organization "MyCompany" --country "US"
#

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================

# Default certificate parameters
COUNTRY="${1:-IN}"
STATE="${2:-Maharashtra}"
CITY="${3:-Mumbai}"
ORGANIZATION="${4:-Youtility}"
COMMON_NAME_CA="${5:-Redis Certificate Authority}"
COMMON_NAME_SERVER="${6:-redis.youtility.internal}"

# Certificate validity periods
CA_VALIDITY_DAYS=3650      # 10 years for CA
SERVER_VALIDITY_DAYS=730   # 2 years for server cert (recommended for PCI DSS)

# Certificate directory
CERT_DIR="${REDIS_TLS_CERT_DIR:-/etc/redis/tls}"
REDIS_USER="${REDIS_USER:-redis}"
REDIS_GROUP="${REDIS_GROUP:-redis}"

# Output colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# FUNCTIONS
# ============================================================================

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
    print_success "Running as root"

    # Check for openssl
    if ! command -v openssl &> /dev/null; then
        print_error "openssl not found - required for certificate generation"
        exit 1
    fi
    print_success "openssl available: $(openssl version)"

    # Check if Redis user exists
    if id "$REDIS_USER" &>/dev/null; then
        print_success "Redis user exists: $REDIS_USER"
    else
        print_warning "Redis user not found: $REDIS_USER (will use current user)"
        REDIS_USER=$(whoami)
        REDIS_GROUP=$(id -gn)
    fi
}

create_certificate_directory() {
    print_header "Creating Certificate Directory"

    if [[ -d "$CERT_DIR" ]]; then
        print_warning "Directory already exists: $CERT_DIR"

        # Check if certificates already exist
        if [[ -f "$CERT_DIR/redis-cert.pem" ]]; then
            print_warning "Certificates already exist in $CERT_DIR"
            read -p "Do you want to regenerate certificates? (yes/no): " REGENERATE

            if [[ "$REGENERATE" != "yes" ]]; then
                print_info "Keeping existing certificates"
                print_info "To regenerate, remove existing certificates first or answer 'yes'"
                exit 0
            fi

            # Backup existing certificates
            BACKUP_DIR="$CERT_DIR/backup_$(date +%Y%m%d_%H%M%S)"
            print_info "Backing up existing certificates to: $BACKUP_DIR"
            mkdir -p "$BACKUP_DIR"
            cp -r "$CERT_DIR"/*.pem "$BACKUP_DIR/" 2>/dev/null || true
            print_success "Backup created"
        fi
    else
        print_info "Creating directory: $CERT_DIR"
        mkdir -p "$CERT_DIR"
        print_success "Directory created"
    fi

    # Set proper permissions on directory
    chmod 755 "$CERT_DIR"
    chown "$REDIS_USER:$REDIS_GROUP" "$CERT_DIR"
}

generate_ca_certificate() {
    print_header "Generating Certificate Authority (CA)"

    print_info "Generating CA private key (4096-bit RSA)..."
    openssl genrsa -out "$CERT_DIR/ca-key.pem" 4096

    print_info "Generating CA certificate (valid for $CA_VALIDITY_DAYS days)..."
    openssl req -new -x509 \
        -days "$CA_VALIDITY_DAYS" \
        -key "$CERT_DIR/ca-key.pem" \
        -out "$CERT_DIR/ca-cert.pem" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORGANIZATION/CN=$COMMON_NAME_CA"

    print_success "CA certificate generated"
    print_info "  CA Certificate: $CERT_DIR/ca-cert.pem"
    print_info "  CA Private Key: $CERT_DIR/ca-key.pem"
}

generate_server_certificate() {
    print_header "Generating Redis Server Certificate"

    print_info "Generating server private key (2048-bit RSA)..."
    openssl genrsa -out "$CERT_DIR/redis-key.pem" 2048

    print_info "Generating certificate signing request (CSR)..."
    openssl req -new \
        -key "$CERT_DIR/redis-key.pem" \
        -out "$CERT_DIR/redis-cert.csr" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORGANIZATION/CN=$COMMON_NAME_SERVER"

    print_info "Signing server certificate with CA (valid for $SERVER_VALIDITY_DAYS days)..."
    openssl x509 -req \
        -days "$SERVER_VALIDITY_DAYS" \
        -in "$CERT_DIR/redis-cert.csr" \
        -CA "$CERT_DIR/ca-cert.pem" \
        -CAkey "$CERT_DIR/ca-key.pem" \
        -CAcreateserial \
        -out "$CERT_DIR/redis-cert.pem"

    print_success "Server certificate generated"
    print_info "  Server Certificate: $CERT_DIR/redis-cert.pem"
    print_info "  Server Private Key: $CERT_DIR/redis-key.pem"

    # Clean up CSR file
    rm -f "$CERT_DIR/redis-cert.csr"
}

set_certificate_permissions() {
    print_header "Setting Certificate Permissions"

    # Private keys: Read-only for Redis user only (600)
    chmod 600 "$CERT_DIR/ca-key.pem"
    chmod 600 "$CERT_DIR/redis-key.pem"
    print_success "Private keys: 600 (owner read/write only)"

    # Certificates: Readable by all, writable by owner (644)
    chmod 644 "$CERT_DIR/ca-cert.pem"
    chmod 644 "$CERT_DIR/redis-cert.pem"
    print_success "Certificates: 644 (publicly readable)"

    # Set ownership
    chown -R "$REDIS_USER:$REDIS_GROUP" "$CERT_DIR"
    print_success "Owner: $REDIS_USER:$REDIS_GROUP"
}

verify_certificates() {
    print_header "Verifying Certificates"

    # Verify CA certificate
    print_info "Verifying CA certificate..."
    if openssl x509 -in "$CERT_DIR/ca-cert.pem" -noout -text &>/dev/null; then
        print_success "CA certificate is valid"

        # Show expiration
        EXPIRY=$(openssl x509 -in "$CERT_DIR/ca-cert.pem" -noout -enddate | cut -d= -f2)
        print_info "  CA Expires: $EXPIRY"
    else
        print_error "CA certificate validation failed"
        exit 1
    fi

    # Verify server certificate
    print_info "Verifying server certificate..."
    if openssl x509 -in "$CERT_DIR/redis-cert.pem" -noout -text &>/dev/null; then
        print_success "Server certificate is valid"

        # Show expiration
        EXPIRY=$(openssl x509 -in "$CERT_DIR/redis-cert.pem" -noout -enddate | cut -d= -f2)
        print_info "  Server Cert Expires: $EXPIRY"

        # Calculate days until expiration
        EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "$EXPIRY" +%s)
        NOW_EPOCH=$(date +%s)
        DAYS_REMAINING=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

        if [[ $DAYS_REMAINING -lt 30 ]]; then
            print_warning "  ⚠️  Certificate expires in $DAYS_REMAINING days - RENEW SOON"
        elif [[ $DAYS_REMAINING -lt 90 ]]; then
            print_info "  Certificate expires in $DAYS_REMAINING days"
        else
            print_success "  Certificate valid for $DAYS_REMAINING days"
        fi
    else
        print_error "Server certificate validation failed"
        exit 1
    fi

    # Verify certificate chain
    print_info "Verifying certificate chain..."
    if openssl verify -CAfile "$CERT_DIR/ca-cert.pem" "$CERT_DIR/redis-cert.pem" &>/dev/null; then
        print_success "Certificate chain is valid"
    else
        print_error "Certificate chain validation failed"
        exit 1
    fi
}

generate_environment_variables() {
    print_header "Generating Environment Configuration"

    ENV_FILE="$CERT_DIR/redis_tls.env"

    cat > "$ENV_FILE" << EOF
# Redis TLS/SSL Configuration
# Generated: $(date)
# For PCI DSS Level 1 Compliance

# Enable TLS/SSL
REDIS_SSL_ENABLED=true

# Certificate paths
REDIS_SSL_CA_CERT=$CERT_DIR/ca-cert.pem
REDIS_SSL_CERT=$CERT_DIR/redis-cert.pem
REDIS_SSL_KEY=$CERT_DIR/redis-key.pem

# Redis connection
# Note: Use 'rediss://' protocol (with double 's') for TLS
# Example: REDIS_URL=rediss://localhost:6379/0
EOF

    chmod 644 "$ENV_FILE"
    print_success "Environment file created: $ENV_FILE"
    print_info "  Add these variables to your .env.production file"
}

print_next_steps() {
    print_header "Next Steps"

    echo "1. Configure Redis Server for TLS:"
    echo "   Edit /etc/redis/redis.conf and add:"
    echo ""
    echo "   # Enable TLS"
    echo "   tls-port 6379"
    echo "   port 0  # Disable non-TLS port in production"
    echo ""
    echo "   # Certificates"
    echo "   tls-cert-file $CERT_DIR/redis-cert.pem"
    echo "   tls-key-file $CERT_DIR/redis-key.pem"
    echo "   tls-ca-cert-file $CERT_DIR/ca-cert.pem"
    echo ""
    echo "   # Security (PCI DSS compliant)"
    echo "   tls-auth-clients yes"
    echo "   tls-protocols \"TLSv1.2 TLSv1.3\""
    echo "   tls-prefer-server-ciphers yes"
    echo ""
    echo "2. Add environment variables to production:"
    echo "   cat $CERT_DIR/redis_tls.env >> .env.production"
    echo ""
    echo "3. Restart Redis:"
    echo "   sudo systemctl restart redis"
    echo ""
    echo "4. Test TLS connection:"
    echo "   redis-cli --tls \\"
    echo "     --cert $CERT_DIR/redis-cert.pem \\"
    echo "     --key $CERT_DIR/redis-key.pem \\"
    echo "     --cacert $CERT_DIR/ca-cert.pem \\"
    echo "     PING"
    echo ""
    echo "5. Verify Django configuration:"
    echo "   python scripts/verify_redis_cache_config.py --environment production"
    echo ""
    echo "6. Monitor certificate expiration:"
    echo "   python manage.py check_redis_certificates"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Certificate generation complete! PCI DSS Level 1 ready.${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════${NC}"
}

print_pci_dss_info() {
    print_header "PCI DSS Level 1 Compliance Information"

    echo "Requirement 4.2.1: Encryption in Transit"
    echo "  - TLS 1.2 or higher REQUIRED"
    echo "  - Certificate inventory MANDATORY (from April 1, 2025)"
    echo "  - Strong cipher suites only"
    echo ""
    echo "Certificate Renewal Schedule:"
    echo "  - Review: Every 6 months"
    echo "  - Renew: 30 days before expiration"
    echo "  - Alert: Automated monitoring daily"
    echo ""
    echo "Compliance Verification:"
    echo "  - Quarterly security audits"
    echo "  - Automated certificate monitoring"
    echo "  - Documentation maintained"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    print_header "Redis TLS/SSL Certificate Generation"
    echo "Organization: $ORGANIZATION"
    echo "Common Name (Server): $COMMON_NAME_SERVER"
    echo "Certificate Directory: $CERT_DIR"
    echo ""

    # Run all steps
    check_prerequisites
    create_certificate_directory
    generate_ca_certificate
    generate_server_certificate
    set_certificate_permissions
    verify_certificates
    generate_environment_variables
    print_pci_dss_info
    print_next_steps
}

# Run main function
main "$@"
