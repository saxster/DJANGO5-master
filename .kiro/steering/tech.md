# Technology Stack & Build System

## Core Technology Stack

### Backend Framework
- **Django 5.2+** - Main web framework with Python 3.8+
- **PostgreSQL 12+ with PostGIS** - Primary database with spatial extensions
- **Redis 6+** - Caching, sessions, and message broker
- **Celery** - Background task processing and scheduling
- **GraphQL (Graphene-Django)** - Modern API layer for mobile applications

### AI & Machine Learning
- **TensorFlow/PyTorch** - AI model training and inference
- **OpenCV** - Computer vision and face recognition
- **NLTK/spaCy** - Natural language processing
- **MindsDB** - Predictive analytics integration
- **DeepFace** - Face recognition and biometric authentication

### Frontend & UI
- **Django Templates + Jinja2** - Server-side rendering
- **Bootstrap 4.x** - UI framework and responsive design
- **DataTables** - Advanced grid interfaces
- **Select2** - Enhanced form components
- **Leaflet.js** - Interactive mapping and geolocation

### Infrastructure & Deployment
- **Docker** - Containerization and deployment
- **Nginx** - Reverse proxy and static file serving
- **Gunicorn** - WSGI application server
- **WhiteNoise** - Static file management
- **Prometheus + Grafana** - Monitoring and metrics

## Build System & Dependencies

### Package Management
```bash
# Python dependencies are managed in requirements/ directory
pip install -r requirements/base.txt        # Core dependencies
pip install -r requirements/ai_requirements.txt  # AI/ML packages
```

### Frontend Assets
```bash
# Node.js for frontend tooling
npm install                    # Install frontend dependencies
npm run build                 # Build production assets
```

### Environment Configuration
The system uses a 4-tier environment approach:
- `.env.dev` - Development (DEBUG=True)
- `.env.dev.secure` - Secure development testing
- `.env.prod` - Current production
- `.env.prod.secure` - Production-ready secure config

## Common Commands

### Development
```bash
# Start development server
python manage.py runserver

# Run database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Start Celery worker (separate terminal)
celery -A intelliwiz_config worker -l info

# Start Celery beat scheduler (separate terminal)
celery -A intelliwiz_config beat -l info
```

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.activity

# Run with coverage
coverage run --source='.' manage.py test
coverage report
coverage html

# Run AI-specific tests
./scripts/run_tests.sh -t unit -c face_recognition
./scripts/run_tests.sh -t performance
```

### Database Operations
```bash
# Create migrations
python manage.py makemigrations

# Show migration status
python manage.py showmigrations

# Database shell
python manage.py dbshell

# Django shell with models loaded
python manage.py shell_plus
```

### Production Deployment
```bash
# Build Docker image
docker build -f deploy/Dockerfile.production -t youtility5:latest .

# Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Run production migrations
python manage.py migrate --settings=intelliwiz_config.settings_production

# Collect static files for production
python manage.py collectstatic --noinput --settings=intelliwiz_config.settings_production
```

### Monitoring & Maintenance
```bash
# Check system health
python manage.py check --deploy

# Monitor performance
python scripts/analyze_query_performance.py

# Generate test reports
python scripts/generate_test_report.py

# Clean up old logs and data
python manage.py cleanup_old_data
```

## Key Libraries & Frameworks

### Django Extensions
- `django-extensions` - Enhanced management commands
- `django-debug-toolbar` - Development debugging
- `django-import-export` - Data import/export functionality
- `django-filter` - Advanced filtering capabilities
- `django-cors-headers` - CORS handling for API access

### Security & Authentication
- `django-graphql-jwt` - JWT authentication for GraphQL
- `djangorestframework` - REST API framework
- `django-redis` - Redis integration for caching
- `django-cleanup` - Automatic file cleanup

### Reporting & Documents
- `django-weasyprint` - PDF generation
- `openpyxl` - Excel file handling
- `qrcode` - QR code generation
- `Pillow` - Image processing

### IoT & Communication
- `paho-mqtt` - MQTT client for IoT devices
- `channels` - WebSocket support for real-time features
- `celery` - Background task processing

## Configuration Notes

### Settings Structure
- Main settings: `intelliwiz_config/settings.py`
- Environment-specific: `intelliwiz_config/envs/`
- Test settings: `intelliwiz_config/settings_test.py`
- Local overrides: `intelliwiz_config/settings_local.py`

### Database Configuration
- Multi-tenant support with tenant-aware models
- PostgreSQL with PostGIS for spatial data
- Redis for caching and session storage
- Connection pooling and optimization settings

### Security Configuration
- Rate limiting with PostgreSQL backend
- CSP (Content Security Policy) headers
- HTTPS enforcement in production
- Session security and CSRF protection