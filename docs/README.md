# YOUTILITY5 - Advanced Django Enterprise Application

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://python.org)
[![Django Version](https://img.shields.io/badge/django-5.0%2B-green.svg)](https://djangoproject.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A comprehensive Django-based enterprise application featuring AI integration, real-time monitoring, advanced security, and scalable architecture.

## 🚀 Features

### Core Functionality
- **Asset Management**: Complete asset lifecycle management with QR code integration
- **People Management**: Employee onboarding, attendance tracking, and role management
- **Activity Tracking**: Real-time job scheduling and task management
- **Reporting System**: Advanced reporting with customizable templates
- **Work Order Management**: Service level agreements and vendor management

### AI & Analytics
- **AI Core Engine**: Integrated AI processing and orchestration
- **Face Recognition**: Advanced biometric authentication
- **NLP Engine**: Natural language processing for ticket analysis
- **Insights Engine**: Automated data insights and recommendations
- **Anomaly Detection**: Real-time anomaly detection and alerting
- **Behavioral Analytics**: User behavior analysis and fraud detection

### Security & Authentication
- **Multi-factor Authentication**: QR code and biometric authentication
- **Behavioral Biometrics**: Keystroke dynamics and interaction patterns
- **Voice Recognition**: Voice-based authentication and commands
- **Security Headers**: Comprehensive CSP and security middleware
- **Rate Limiting**: Advanced rate limiting and DDoS protection

### Real-time Features
- **WebSocket Support**: Real-time updates and notifications
- **MQTT Integration**: IoT device communication
- **Live Monitoring**: Real-time system monitoring and alerts
- **Heatmap Tracking**: User interaction analytics

### Performance & Scalability
- **PostgreSQL Optimization**: Advanced database optimization
- **Caching Strategy**: Multi-level caching with Redis
- **Static Asset Optimization**: Optimized frontend delivery
- **Background Tasks**: Celery-based task processing
- **Load Testing**: Comprehensive performance testing suite

## 🏗️ Architecture

### Project Structure

```
YOUTILITY5/
├── apps/                           # Django applications
│   ├── activity/                   # Asset and job management
│   ├── ai_core/                    # AI processing engine
│   ├── api/                        # REST API endpoints
│   ├── attendance/                 # Attendance tracking
│   ├── core/                       # Core utilities and middleware
│   ├── face_recognition/           # Biometric authentication
│   ├── insights_engine/            # Data insights
│   ├── nlp_engine/                 # Natural language processing
│   ├── onboarding/                 # Business unit management
│   ├── peoples/                    # User management
│   ├── reports/                    # Reporting system
│   ├── work_order_management/      # Service management
│   └── ...
├── background_tasks/               # Celery tasks
├── config/                         # Configuration files
│   ├── nginx/                      # Nginx configuration
│   ├── prometheus/                 # Monitoring configuration
│   └── grafana/                    # Dashboard configuration
├── deploy/                         # Deployment files
├── docs/                          # Documentation
├── frontend/                      # Frontend assets
│   ├── static/                    # Static files
│   └── templates/                 # Django templates
├── intelliwiz_config/             # Django settings
├── monitoring/                    # System monitoring
├── scripts/                       # Utility scripts
├── tests/                         # Test suite
└── requirements/                  # Dependencies
```

### Technology Stack

**Backend**
- Django 5.0+ with Python 3.8+
- PostgreSQL with advanced optimizations
- Redis for caching and sessions
- Celery for background tasks
- GraphQL API with Graphene

**AI & Machine Learning**
- TensorFlow/PyTorch for AI models
- OpenCV for computer vision
- NLTK/spaCy for NLP
- MindsDB for predictive analytics

**Frontend**
- Modern JavaScript (ES6+)
- CSS3 with responsive design
- WebSocket for real-time updates
- Select2 for enhanced UI components

**Infrastructure**
- Docker for containerization
- Nginx for reverse proxy
- Prometheus + Grafana for monitoring
- GitHub Actions for CI/CD

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Node.js 16+ (for frontend assets)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/ytpl65/DJANGO5.git
cd YOUTILITY5
```

2. **Create virtual environment**
```bash
python -m venv django5-env
source django5-env/bin/activate  # On Windows: django5-env\Scripts\activate
```

3. **Install Python dependencies**
```bash
pip install -r requirements/base.txt
```

4. **Install Node.js dependencies**
```bash
npm install
```

5. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

6. **Database setup**
```bash
# Create PostgreSQL database
createdb youtility5_db

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

7. **Collect static files**
```bash
python manage.py collectstatic
```

8. **Start development server**
```bash
python manage.py runserver
```

### Docker Setup (Alternative)

```bash
# Build and start with Docker Compose
docker-compose up --build

# Run migrations in container
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/youtility5_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

# AI Services
OPENAI_API_KEY=your-openai-key
MINDSDB_URL=http://localhost:47334

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# File Storage
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
```

### Database Configuration

The application supports advanced PostgreSQL features:

- **Materialized Views**: For optimized reporting
- **Full-text Search**: Enhanced search capabilities
- **JSON Fields**: Flexible data storage
- **Custom Functions**: Performance-optimized queries

## 🧪 Testing

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.activity

# Run with coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Load Testing

```bash
# Database performance tests
python scripts/test_performance_optimizations.py

# API load testing
cd testing/load_testing/
./run_load_tests.sh
```

## 📊 Monitoring

### Metrics Dashboard

Access monitoring dashboards:

- **Application Metrics**: http://localhost:3000 (Grafana)
- **System Metrics**: http://localhost:9090 (Prometheus)
- **Health Checks**: http://localhost:8000/health/

### Performance Monitoring

```bash
# Monitor ORM performance
python scripts/monitor_orm_performance.py

# Generate performance reports
python scripts/generate_test_report.py
```

## 🔒 Security

### Security Features

- **Content Security Policy (CSP)**: Prevents XSS attacks
- **SQL Injection Protection**: Parameterized queries and ORM validation
- **Rate Limiting**: API and authentication rate limiting
- **Security Headers**: HSTS, X-Frame-Options, etc.
- **Input Validation**: Comprehensive input sanitization

### Security Checklist

```bash
# Run security checks
python manage.py check --deploy

# Validate SQL security
python scripts/validate_sql_security.py

# Test authentication
python scripts/test_auth_security.py
```

## 🚀 Deployment

### Production Deployment

1. **Environment Setup**
```bash
# Install production dependencies
pip install -r requirements/production.txt

# Set production environment
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings_production
```

2. **Database Migration**
```bash
python manage.py migrate --settings=intelliwiz_config.settings_production
```

3. **Static Files**
```bash
python manage.py collectstatic --noinput
```

4. **Start Services**
```bash
# Start Gunicorn
gunicorn intelliwiz_config.wsgi:application

# Start Celery worker
celery -A intelliwiz_config worker -l info

# Start Celery beat
celery -A intelliwiz_config beat -l info
```

### Docker Production

```bash
# Build production image
docker build -f deploy/Dockerfile.production -t youtility5:latest .

# Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

## 📚 API Documentation

### REST API

- **API Documentation**: http://localhost:8000/api/docs/
- **OpenAPI Schema**: http://localhost:8000/api/schema/
- **GraphQL Playground**: http://localhost:8000/graphql/

### API Examples

```python
# Authentication
POST /api/auth/login/
{
    "username": "user@example.com",
    "password": "password"
}

# Asset Management
GET /api/v1/assets/
POST /api/v1/assets/
{
    "name": "Asset Name",
    "type": "equipment",
    "location": 1
}

# Real-time Updates
WebSocket: ws://localhost:8000/ws/updates/
```

## 🤝 Contributing

### Development Workflow

1. **Fork the repository**
2. **Create feature branch**
```bash
git checkout -b feature/amazing-feature
```

3. **Make changes and test**
```bash
python manage.py test
```

4. **Commit changes**
```bash
git commit -m "Add amazing feature"
```

5. **Push to branch**
```bash
git push origin feature/amazing-feature
```

6. **Create Pull Request**

### Code Standards

- **Python**: Follow PEP 8, use Black formatter
- **JavaScript**: Use ESLint configuration
- **Django**: Follow Django best practices
- **Documentation**: Update docs for new features

## 📖 Documentation

- **[API Documentation](docs/API.md)**: REST and GraphQL API reference
- **[Deployment Guide](docs/DEPLOYMENT.md)**: Production deployment instructions
- **[Development Guide](docs/DEVELOPMENT.md)**: Local development setup
- **[Security Guide](docs/SECURITY.md)**: Security implementation details
- **[Migration Guide](docs/MIGRATION.md)**: Database migration procedures

## 🆘 Support

### Getting Help

- **Issues**: [GitHub Issues](https://github.com/ytpl65/DJANGO5/issues)
- **Discussions**: [GitHub Discussions](https://github.com/ytpl65/DJANGO5/discussions)
- **Documentation**: [Project Wiki](https://github.com/ytpl65/DJANGO5/wiki)

### Troubleshooting

Common issues and solutions:

```bash
# Database connection issues
python manage.py dbshell

# Cache issues
python manage.py clear_cache

# Static files issues
python manage.py collectstatic --clear
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏆 Acknowledgments

- Django community for the excellent framework
- Contributors who have helped improve this project
- Open source libraries that made this possible

## 📈 Roadmap

### Upcoming Features

- [ ] Advanced AI model training interface
- [ ] Mobile application development
- [ ] Blockchain integration for asset tracking
- [ ] Advanced analytics dashboard
- [ ] Multi-tenant architecture
- [ ] Kubernetes deployment support

### Version History

- **v5.0.0**: Major AI integration and performance improvements
- **v4.5.0**: Advanced security features and monitoring
- **v4.0.0**: Complete UI/UX redesign
- **v3.5.0**: PostgreSQL optimization and caching
- **v3.0.0**: Microservices architecture implementation

---

**Made with ❤️ by the YOUTILITY5 Team**