#!/bin/bash

# YOUTILITY5 AI Infrastructure Deployment Script
# This script sets up the complete AI infrastructure for the application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="youtility5"
AI_ENV_FILE=".env.ai.local"
COMPOSE_FILE="docker-compose.ai.yml"
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker is not running. Please start Docker first."
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null; then
        if ! docker compose version &> /dev/null; then
            error "Docker Compose is not available. Please install docker-compose."
        fi
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    # Check available disk space (minimum 5GB)
    available_space=$(df . | awk 'NR==2 {print $4}')
    min_space=5000000  # 5GB in KB
    
    if [ "$available_space" -lt "$min_space" ]; then
        warning "Available disk space is less than 5GB. AI models may require more space."
    fi
    
    # Check available memory (minimum 8GB)
    if command -v free &> /dev/null; then
        available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')
        min_memory=8000  # 8GB in MB
        
        if [ "$available_memory" -lt "$min_memory" ]; then
            warning "Available memory is less than 8GB. Performance may be impacted."
        fi
    fi
    
    log "Prerequisites check completed."
}

# Function to setup environment
setup_environment() {
    log "Setting up environment..."
    
    # Create necessary directories
    mkdir -p logs backups ai_models vector_indexes temp
    
    # Copy environment file if it doesn't exist
    if [ ! -f "$AI_ENV_FILE" ]; then
        if [ -f ".env.ai" ]; then
            cp .env.ai "$AI_ENV_FILE"
            info "Created $AI_ENV_FILE from template. Please customize it for your environment."
        else
            error "Environment template file .env.ai not found."
        fi
    fi
    
    # Generate secret keys if not set
    if grep -q "your-secret-key-here" "$AI_ENV_FILE"; then
        SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
        sed -i "s/your-secret-key-here/$SECRET_KEY/g" "$AI_ENV_FILE"
        info "Generated Django secret key."
    fi
    
    if grep -q "your-jwt-secret-here" "$AI_ENV_FILE"; then
        JWT_SECRET=$(openssl rand -base64 64 | tr -d '\n')
        sed -i "s/your-jwt-secret-here/$JWT_SECRET/g" "$AI_ENV_FILE"
        info "Generated JWT secret key."
    fi
    
    # Set proper permissions
    chmod 600 "$AI_ENV_FILE"
    chmod +x scripts/*.sh
    
    log "Environment setup completed."
}

# Function to build Docker images
build_images() {
    log "Building Docker images..."
    
    # Build main application image
    $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache celery-worker
    
    # Build model server image
    $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache model-server
    
    log "Docker images built successfully."
}

# Function to start AI services
start_services() {
    log "Starting AI services..."
    
    # Start infrastructure services first
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d redis mindsdb prometheus grafana
    
    # Wait for services to be ready
    info "Waiting for services to initialize..."
    sleep 30
    
    # Start application services
    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d celery-worker celery-beat model-server nginx-ai-gateway
    
    # Wait for all services to be ready
    sleep 20
    
    log "AI services started successfully."
}

# Function to check service health
check_service_health() {
    log "Checking service health..."
    
    services=("redis:6379" "mindsdb:47334" "model-server:8001")
    
    for service in "${services[@]}"; do
        IFS=':' read -r host port <<< "$service"
        
        info "Checking $host:$port..."
        
        # Use docker exec to check from within the network
        if $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T nginx-ai-gateway wget -q --spider "http://$service" 2>/dev/null; then
            log "$host:$port is healthy"
        else
            warning "$host:$port is not responding"
        fi
    done
    
    # Check Nginx gateway
    if curl -f http://localhost:8080/health &>/dev/null; then
        log "Nginx gateway is healthy"
    else
        warning "Nginx gateway is not responding"
    fi
    
    log "Health check completed."
}

# Function to run database migrations
run_migrations() {
    log "Running database migrations..."
    
    # Wait for database to be ready
    info "Waiting for database..."
    sleep 10
    
    # Run migrations for AI apps
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T celery-worker python manage.py migrate txtai_engine --noinput
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T celery-worker python manage.py migrate mindsdb_engine --noinput
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T celery-worker python manage.py migrate ai_orchestrator --noinput
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T celery-worker python manage.py migrate smart_dashboard --noinput
    
    log "Database migrations completed."
}

# Function to load initial data
load_initial_data() {
    log "Loading initial AI data..."
    
    # Create default dashboard templates
    $COMPOSE_CMD -f "$COMPOSE_FILE" exec -T celery-worker python manage.py shell << 'EOF'
from apps.smart_dashboard.models import DashboardTemplate
from apps.peoples.models import Client

# Get first client for demo data
client = Client.objects.first()
if client:
    # Executive Dashboard Template
    if not DashboardTemplate.objects.filter(name="Executive AI Dashboard", client=client).exists():
        DashboardTemplate.objects.create(
            name="Executive AI Dashboard",
            description="High-level AI insights for executives",
            category="EXECUTIVE",
            template_config={
                "dashboard_type": "EXECUTIVE",
                "layout_config": {"columns": 12, "rows": 8},
                "theme_config": {"theme": "executive"},
                "widgets": [
                    {
                        "name": "AI Insights Feed",
                        "widget_type": "AI_INSIGHTS_FEED",
                        "position_x": 0, "position_y": 0,
                        "width": 6, "height": 4,
                        "config": {"limit": 5}
                    },
                    {
                        "name": "Predictive Analytics",
                        "widget_type": "PREDICTION_CHART",
                        "position_x": 6, "position_y": 0,
                        "width": 6, "height": 4,
                        "config": {"chart_type": "line"}
                    }
                ]
            },
            use_cases=["Executive reporting", "Strategic insights"],
            required_data_sources=["ai_insights", "predictions"],
            client=client
        )
        print("Created Executive AI Dashboard template")
    
    # Operational Dashboard Template
    if not DashboardTemplate.objects.filter(name="Operational AI Dashboard", client=client).exists():
        DashboardTemplate.objects.create(
            name="Operational AI Dashboard",
            description="Real-time operational AI monitoring",
            category="OPERATIONAL",
            template_config={
                "dashboard_type": "OPERATIONAL",
                "layout_config": {"columns": 12, "rows": 10},
                "theme_config": {"theme": "operational"},
                "widgets": [
                    {
                        "name": "Workflow Status",
                        "widget_type": "WORKFLOW_STATUS",
                        "position_x": 0, "position_y": 0,
                        "width": 8, "height": 4,
                        "config": {"limit": 10}
                    },
                    {
                        "name": "Anomaly Alerts",
                        "widget_type": "ANOMALY_ALERTS",
                        "position_x": 8, "position_y": 0,
                        "width": 4, "height": 4,
                        "config": {"limit": 5}
                    }
                ]
            },
            use_cases=["Operations monitoring", "Real-time alerts"],
            required_data_sources=["workflows", "alerts"],
            client=client
        )
        print("Created Operational AI Dashboard template")

EOF
    
    log "Initial AI data loaded."
}

# Function to show deployment summary
show_deployment_summary() {
    log "Deployment Summary"
    echo "===================="
    echo ""
    echo "🚀 AI Infrastructure URLs:"
    echo "   • AI Gateway: http://localhost:8080"
    echo "   • MindsDB API: http://localhost:47334"
    echo "   • Model Server: http://localhost:8001"
    echo "   • Grafana: http://localhost:3000 (admin/admin123)"
    echo "   • Prometheus: http://localhost:9090"
    echo ""
    echo "🔧 Management Commands:"
    echo "   • View logs: $COMPOSE_CMD -f $COMPOSE_FILE logs -f [service]"
    echo "   • Scale workers: $COMPOSE_CMD -f $COMPOSE_FILE up -d --scale celery-worker=3"
    echo "   • Stop services: $COMPOSE_CMD -f $COMPOSE_FILE down"
    echo "   • Full cleanup: $COMPOSE_CMD -f $COMPOSE_FILE down -v"
    echo ""
    echo "📁 Important Directories:"
    echo "   • AI Models: ./ai_models/"
    echo "   • Vector Indexes: ./vector_indexes/"
    echo "   • Logs: ./logs/"
    echo "   • Backups: ./backups/"
    echo ""
    echo "🎯 Next Steps:"
    echo "   1. Configure API keys in $AI_ENV_FILE"
    echo "   2. Upload AI models to ./ai_models/"
    echo "   3. Create vector indexes via Django admin"
    echo "   4. Set up monitoring alerts in Grafana"
    echo ""
}

# Main deployment function
main() {
    log "Starting YOUTILITY5 AI Infrastructure Deployment"
    
    check_prerequisites
    setup_environment
    build_images
    start_services
    check_service_health
    run_migrations
    load_initial_data
    
    log "AI Infrastructure deployment completed successfully!"
    show_deployment_summary
}

# Script options
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "check-health")
        check_service_health
        ;;
    "start")
        start_services
        ;;
    "stop")
        $COMPOSE_CMD -f "$COMPOSE_FILE" down
        ;;
    "restart")
        $COMPOSE_CMD -f "$COMPOSE_FILE" restart
        ;;
    "logs")
        $COMPOSE_CMD -f "$COMPOSE_FILE" logs -f "${2:-}"
        ;;
    "clean")
        warning "This will remove all data. Are you sure? (y/N)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            $COMPOSE_CMD -f "$COMPOSE_FILE" down -v --remove-orphans
            docker system prune -f
            log "Cleanup completed."
        fi
        ;;
    *)
        echo "Usage: $0 {deploy|check-health|start|stop|restart|logs|clean}"
        echo ""
        echo "Commands:"
        echo "  deploy       - Full deployment (default)"
        echo "  check-health - Check service health"
        echo "  start        - Start services"
        echo "  stop         - Stop services"
        echo "  restart      - Restart services"
        echo "  logs         - View logs (optional service name)"
        echo "  clean        - Clean up all data"
        exit 1
        ;;
esac