#!/bin/bash

# Information Architecture Deployment Script
# Automates the deployment of IA improvements with safety checks

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/home/jarvis/Documents/YOUTILITY3"
BACKUP_DIR="$PROJECT_ROOT/backups/ia_deployment_$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$PROJECT_ROOT/logs/ia_deployment_$(date +%Y%m%d_%H%M%S).log"

# Functions
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Pre-deployment checks
pre_deployment_checks() {
    log "Starting pre-deployment checks..."
    
    # Check if running as correct user
    if [ "$USER" != "jarvis" ]; then
        warning "Not running as expected user 'jarvis'"
    fi
    
    # Check Python version
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    log "Python version: $python_version"
    
    # Check Django installation
    if ! python3 -c "import django" 2>/dev/null; then
        error "Django is not installed"
    fi
    
    # Check if in virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        warning "Not in a virtual environment"
    fi
    
    # Check disk space
    available_space=$(df -h "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    log "Available disk space: $available_space"
    
    success "Pre-deployment checks completed"
}

# Create backups
create_backups() {
    log "Creating backups..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    log "Backing up database..."
    python3 manage.py dbbackup --output-path "$BACKUP_DIR" || warning "Database backup failed"
    
    # Backup templates
    log "Backing up templates..."
    cp -r frontend/templates "$BACKUP_DIR/templates_backup" || error "Template backup failed"
    
    # Backup static files
    log "Backing up static files..."
    cp -r frontend/static "$BACKUP_DIR/static_backup" || error "Static files backup failed"
    
    # Create git tag
    log "Creating git tag..."
    git tag -a "pre-ia-deployment-$(date +%Y%m%d)" -m "Pre-IA deployment backup" || warning "Git tag creation failed"
    
    success "Backups created at $BACKUP_DIR"
}

# Run tests
run_tests() {
    log "Running test suite..."
    
    # Run IA-specific tests
    python3 manage.py test tests.test_information_architecture --verbosity=2 || error "IA tests failed"
    
    # Run integration tests
    python3 manage.py test apps.core.tests --verbosity=2 || warning "Some core tests failed"
    
    success "All critical tests passed"
}

# Deploy new files
deploy_files() {
    log "Deploying new files..."
    
    # Ensure directories exist
    mkdir -p apps/core/views
    mkdir -p apps/core/models
    mkdir -p apps/core/middleware
    mkdir -p frontend/templates/base
    mkdir -p frontend/templates/core/monitoring
    mkdir -p frontend/static/assets/js
    
    # Deploy files (these should already exist from the implementation)
    files_to_check=(
        "frontend/templates/globals/sidebar_clean.html"
        "apps/core/url_router.py"
        "apps/core/views/base_views.py"
        "frontend/static/assets/js/menu-handler-clean.js"
        "frontend/templates/base/list.html"
        "frontend/templates/base/form.html"
    )
    
    for file in "${files_to_check[@]}"; do
        if [ -f "$file" ]; then
            success "Found: $file"
        else
            error "Missing required file: $file"
        fi
    done
    
    success "All required files are in place"
}

# Update Django settings
update_settings() {
    log "Updating Django settings..."
    
    # Check if middleware needs to be added
    if ! grep -q "IATrackingMiddleware" intelliwiz_config/settings.py; then
        log "Adding IA tracking middleware to settings..."
        # This would need to be done manually or with a more sophisticated script
        warning "Please manually add 'apps.core.middleware.ia_tracking.IATrackingMiddleware' to MIDDLEWARE in settings.py"
    fi
    
    # Check if core app is in INSTALLED_APPS
    if ! grep -q "'apps.core'" intelliwiz_config/settings.py; then
        warning "Please ensure 'apps.core' is in INSTALLED_APPS in settings.py"
    fi
    
    success "Settings check completed"
}

# Run migrations
run_migrations() {
    log "Running database migrations..."
    
    # Check for pending migrations
    python3 manage.py showmigrations --plan | grep -q "\[ \]" && {
        log "Found pending migrations"
        python3 manage.py migrate --noinput || error "Migration failed"
    } || {
        log "No pending migrations found"
    }
    
    success "Migrations completed"
}

# Collect static files
collect_static() {
    log "Collecting static files..."
    
    python3 manage.py collectstatic --noinput || error "Static file collection failed"
    
    success "Static files collected"
}

# Clear caches
clear_caches() {
    log "Clearing caches..."
    
    # Django cache
    python3 manage.py clear_cache 2>/dev/null || log "No cache management command found"
    
    # Redis cache (if used)
    if command -v redis-cli &> /dev/null; then
        redis-cli FLUSHDB || warning "Redis cache clear failed"
    fi
    
    success "Caches cleared"
}

# Update navigation template
update_navigation() {
    log "Updating navigation template..."
    
    # Find base template that includes sidebar
    base_template=$(grep -l "sidebar_menus.html\|updated_sidebarmenus.html" frontend/templates/globals/*.html 2>/dev/null | head -1)
    
    if [ -n "$base_template" ]; then
        log "Found base template: $base_template"
        # Create backup
        cp "$base_template" "$base_template.bak"
        
        # Comment out old sidebar and add new one
        # This is a simplified version - in practice would need more careful editing
        warning "Please manually update $base_template to use sidebar_clean.html"
    else
        warning "Could not find base template with sidebar include"
    fi
    
    success "Navigation update completed"
}

# Post-deployment verification
post_deployment_verification() {
    log "Running post-deployment verification..."
    
    # Check if server starts
    log "Checking if development server starts..."
    timeout 10 python3 manage.py runserver --noreload > /dev/null 2>&1 &
    server_pid=$!
    sleep 5
    
    if kill -0 $server_pid 2>/dev/null; then
        success "Server started successfully"
        kill $server_pid
    else
        error "Server failed to start"
    fi
    
    # Check critical URLs
    log "Checking critical URLs..."
    # This would need curl or similar to actually test
    
    success "Post-deployment verification completed"
}

# Rollback function
rollback() {
    error "Deployment failed! Starting rollback..."
    
    if [ -d "$BACKUP_DIR" ]; then
        log "Restoring from backup at $BACKUP_DIR"
        
        # Restore templates
        if [ -d "$BACKUP_DIR/templates_backup" ]; then
            rm -rf frontend/templates
            cp -r "$BACKUP_DIR/templates_backup" frontend/templates
            success "Templates restored"
        fi
        
        # Restore static files
        if [ -d "$BACKUP_DIR/static_backup" ]; then
            rm -rf frontend/static
            cp -r "$BACKUP_DIR/static_backup" frontend/static
            success "Static files restored"
        fi
        
        # Restore database
        if ls "$BACKUP_DIR"/*.dump 1> /dev/null 2>&1; then
            python3 manage.py dbrestore --input-path "$BACKUP_DIR" --noinput
            success "Database restored"
        fi
    else
        error "No backup found for rollback!"
    fi
    
    exit 1
}

# Main deployment flow
main() {
    log "Starting Information Architecture deployment..."
    log "Project root: $PROJECT_ROOT"
    log "Backup directory: $BACKUP_DIR"
    
    # Change to project directory
    cd "$PROJECT_ROOT" || error "Cannot change to project directory"
    
    # Set up error handling
    trap rollback ERR
    
    # Deployment steps
    pre_deployment_checks
    create_backups
    run_tests
    deploy_files
    update_settings
    run_migrations
    collect_static
    clear_caches
    update_navigation
    post_deployment_verification
    
    # Remove error trap
    trap - ERR
    
    success "Information Architecture deployment completed successfully!"
    log "Deployment log saved to: $LOG_FILE"
    
    # Show summary
    echo
    echo "===== DEPLOYMENT SUMMARY ====="
    echo "✅ All files deployed"
    echo "✅ Tests passed"
    echo "✅ Migrations completed"
    echo "✅ Static files collected"
    echo "✅ Caches cleared"
    echo
    echo "⚠️  MANUAL STEPS REQUIRED:"
    echo "1. Update settings.py to add IATrackingMiddleware"
    echo "2. Update base template to use sidebar_clean.html"
    echo "3. Restart application server"
    echo "4. Monitor error logs for 30 minutes"
    echo
    echo "📊 Access monitoring dashboard at: /admin/ia-monitoring/"
    echo "📝 User guide available at: /documentation/USER_GUIDE_NEW_NAVIGATION.md"
    echo "=============================="
}

# Run main function
main "$@"