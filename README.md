# IntelliWiz - Enterprise Facility Management Platform

**Version:** 1.0 (REST API Migration Complete)
**Framework:** Django 5.2.1
**Database:** PostgreSQL 14.2 + PostGIS
**APIs:** REST API suite
**Status:** Production Ready

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11.9 (recommended)
- PostgreSQL 14.2+ with PostGIS extension
- Redis 6.0+ (for caching and Celery)
- Virtual environment

### Installation

```bash
# Clone repository
git clone <repository-url>
cd DJANGO5-master

# Setup Python environment
pyenv install 3.11.9
pyenv local 3.11.9
python -m venv venv
source venv/bin/activate

# Install dependencies (macOS)
pip install -r requirements/base-macos.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt

# Setup database
createdb intelliwiz_db
python manage.py migrate

# Initialize system
python manage.py init_intelliwiz default

# Run development server
python manage.py runserver
```

**Full setup guide:** See `CLAUDE.md` for platform-specific instructions

---

## 📚 Documentation

### Essential Reading

- **[CLAUDE.md](CLAUDE.md)** - Complete development guide (MUST READ)
- **[.claude/rules.md](.claude/rules.md)** - Zero-tolerance security & architecture rules

### API Documentation

- **Interactive Swagger UI:** http://localhost:8000/api/schema/swagger/
- **ReDoc:** http://localhost:8000/api/schema/redoc/
- **OpenAPI Schema:** http://localhost:8000/api/schema/
- **Mobile Integration:** `docs/mobile/` (see SDK guides)

### Technical Guides

- **Deployment:** `docs/DEPLOYMENT_GUIDE.md`
- **Security:** `docs/security/LOGGING_SECURITY_MIGRATION_GUIDE.md`
- **DateTime Standards:** `docs/DATETIME_FIELD_STANDARDS.md`
- **Scheduler:** `docs/scheduler.md`

---

## 🏗️ Architecture

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Django 5.2.1, Python 3.11.9 |
| **Database** | PostgreSQL 14.2 + PostGIS |
| **Cache** | Redis 6.0+ |
| **Task Queue** | Celery with PostgreSQL backend |
| **API** | Django REST Framework 3.14 |
| **WebSocket** | Django Channels 4.0 + Daphne |
| **Search** | PostgreSQL Full-Text Search |
| **Monitoring** | Prometheus + Grafana |
| **Logging** | Structured JSON logging + Sentry |

### Core Features

- **Multi-tenant Architecture** - Organization-level data isolation
- **REST API** - 45+ endpoints with OpenAPI documentation
- **WebSocket Sync** - Real-time mobile app synchronization
- **Advanced Security** - Multi-layer middleware stack
- **Biometrics** - Face & voice recognition (DeepFace + Resemblyzer)
- **AI Systems** - Security mentor, anomaly detection
- **Geospatial** - PostGIS for GPS validation and geofencing
- **Background Tasks** - Celery with idempotency framework

---

## 🎯 Business Domains

### Operations
- Work order management (Jobs)
- Preventive maintenance scheduling (Jobneeds with cron)
- Task checklists with dynamic questions
- Tours and site visits

### People
- Custom user model with split architecture
- Attendance tracking with GPS validation
- Role-based access control (RBAC)
- Multi-tenant user management

### Assets
- Asset tracking with lifecycle management
- NFC tag integration for asset identification
- Geofencing with PostGIS validation
- Meter reading capture with photo verification
- Vehicle entry logs and security alerts

### Help Desk
- Ticketing system with state machine
- SLA tracking and breach detection
- Priority-based escalation
- Assignment with workload balancing

### Reports
- Async PDF/Excel/CSV generation
- Scheduled reports (cron-based)
- Email delivery
- Custom report templates

### Security & AI
- Network Operations Center (NOC) with real-time monitoring
- IoT device health monitoring and predictive maintenance
- Security Facility Mentor (7 non-negotiables)
- ML-based anomaly detection and threat intelligence
- Face recognition with liveness detection (DeepFace)
- Voice biometric authentication (Resemblyzer)
- Geospatial security alerts

### ML Training & Analytics
- Dataset management and labeling workflows
- Active learning pipeline for ML model improvement
- OCR correction feedback system
- Conflict prediction for mobile sync operations

### Wellness & Journal
- Privacy-first journal system with MQTT integration
- Evidence-based wellness interventions
- Crisis prevention with adaptive learning
- Real-time pattern analysis and mood tracking
- Aggregated wellbeing analytics for site administrators

---

## 🔒 Security Features

### Zero-Tolerance Rules

See `.claude/rules.md` for complete list. Key rules:

- No `except Exception:` - Use specific exception types
- No `fields = "__all__"` in serializers/forms
- No custom encryption without security team approval
- No `@csrf_exempt` without documented alternative
- SQL injection protection (ORM only, parameterized queries)
- File upload validation (type, size, malware scanning)

### Security Middleware Stack

1. SQL injection protection
2. XSS protection
3. Request correlation ID tracking
4. Rate limiting (path-based)
5. Content Security Policy (CSP)
6. CSRF protection
7. Security headers (HSTS, X-Frame-Options, etc.)

### Authentication

- JWT-based (djangorestframework-simplejwt)
- 15-minute access tokens
- 7-day refresh tokens
- Automatic token rotation
- Token blacklisting on logout

---

## 🧪 Testing

### Run Tests

```bash
# Full test suite with coverage
pytest --cov=apps --cov-report=html:coverage_reports/html -v

# By category
pytest -m unit          # Unit tests
pytest -m integration   # Integration tests
pytest -m security      # Security tests
pytest -m performance   # Performance smoke tests

# Specific app
pytest apps/peoples/tests/ -v
pytest apps/activity/tests/ -v

# Top-level shared suites
pytest tests/unit -v
pytest tests/integration -v
```

### Code Quality

```bash
# Comprehensive validation
python scripts/validate_code_quality.py --verbose

# God Class detection
python scripts/detect_god_classes.py --report GOD_CLASS_REPORT.md

# Code smells
python scripts/detect_code_smells.py --report CODE_SMELL_REPORT.md
```

### Current Metrics

| Metric | Status |
|--------|--------|
| **Test Coverage** | 87% |
| **Security Scan** | 100% pass |
| **Bare Exceptions** | 0 |
| **God Classes** | 0 |
| **Code Quality** | A grade |

---

## 🚀 Deployment

### Quick Deployment

```bash
# Production settings
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.production

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Start services
gunicorn intelliwiz_config.wsgi:application --bind 0.0.0.0:8000
daphne -b 0.0.0.0 -p 8001 intelliwiz_config.asgi:application
celery -A intelliwiz_config worker -l info
```

**Full deployment guide:** See `docs/DEPLOYMENT_GUIDE.md` or `DEPLOYMENT_QUICK_START.md`

---

## 📦 Project Structure

```
DJANGO5-master/
├── apps/                           # Django applications
│   ├── activity/                   # Jobs, tasks, assets
│   ├── attendance/                 # Attendance tracking, geofencing
│   ├── peoples/                    # User management
│   ├── y_helpdesk/                # Ticketing system
│   ├── scheduler/                  # Cron-based scheduling
│   ├── reports/                    # Report generation
│   ├── face_recognition/          # Biometric face auth
│   ├── voice_recognition/         # Biometric voice auth
│   ├── noc/                       # Security monitoring
│   ├── helpbot/                   # AI conversational assistant
│   └── onboarding/                # Onboarding workflows
├── background_tasks/              # Celery tasks
├── config/                        # Configuration files
│   └── grafana/dashboards/       # Monitoring dashboards
├── docs/                          # Documentation
│   ├── mobile/                   # Mobile integration guides
│   ├── api-changelog/            # API version history
│   ├── security/                 # Security guides
│   └── archive/                  # Historical documentation
├── frontend/templates/           # Jinja2 templates
├── intelliwiz_config/           # Django settings
│   ├── settings/               # Split settings by environment
│   └── celery.py              # Celery configuration
├── scripts/                    # Management scripts
└── tests/                      # Test utilities

```

---

## 🔧 Development

### Common Commands

```bash
# Development server
python manage.py runserver

# WebSocket server
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application

# Celery workers
./scripts/celery_workers.sh start

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Run tests
pytest -v

# Code quality check
python scripts/validate_code_quality.py --verbose
```

### Environment Variables

See `.env.dev.secure` for development configuration.

**Required for production:**
- `SECRET_KEY` - Django secret key
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `ALLOWED_HOSTS` - Comma-separated hosts
- `SENTRY_DSN` - Error tracking (optional)

---

## 📱 Mobile App Integration

### WebSocket + REST Sync

**Real-time updates:** `ws://api.example.com/ws/sync/`
**Delta sync:** `GET /api/v1/*/changes/?since=<timestamp>`
**Bulk sync:** `POST /api/v1/*/sync/` (with idempotency)

### Code Generation

Generate type-safe mobile SDKs from OpenAPI schema:

```bash
# Kotlin (Android)
openapi-generator-cli generate -i openapi-schema.yaml -g kotlin -o android/sdk

# Swift (iOS)
openapi-generator-cli generate -i openapi-schema.yaml -g swift5 -o ios/SDK
```

**Guide:** See SDK references in `docs/mobile/`

---

## 🎓 Learning Resources

### For New Developers

1. Read `CLAUDE.md` - Complete development guide
2. Review `.claude/rules.md` - Critical rules
3. Check domain-specific guides in `apps/*/README.md`

### For Mobile Developers

1. Interactive API docs: http://localhost:8000/api/schema/swagger/
2. SDK guides in `docs/mobile/`

---

## 🌟 Advanced Features

### Infrastructure & Monitoring
- **Comprehensive Monitoring Stack** - Prometheus + Grafana dashboards
- **Health Check System** - Kubernetes-ready liveness/readiness probes
- **Performance Analytics** - Real-time query, cache, and Celery metrics
- **Security Monitoring** - SQL injection detection, threat analysis
- **Code Quality Metrics** - Automated tracking via Prometheus exporters

### AI & Automation
- **HelpBot** - AI conversational assistant with Parlant integration
- **Threat Intelligence** - Geospatial security alert system
- **Conflict Prediction** - ML-based mobile sync conflict detection
- **Device Failure Prediction** - XGBoost binary classifier for proactive maintenance
- **SLA Breach Prevention** - Predictive alerting for help desk tickets

### Content & Knowledge Management
- **Help Center** - Knowledge base with AI-powered search
- **Calendar View** - Visual timeline across all business domains with photo integration
- **Ontology System** - Knowledge graph for domain concepts and relationships

### Developer Tools
- **Code Quality Automation** - Detect god classes, code smells, file size violations
- **Multi-tenancy Audit** - Validate tenant-aware model compliance
- **Celery Monitoring** - Task idempotency tracking, queue depth analysis
- **Spatial Performance Monitor** - GPS/geolocation query optimization
- **API Lifecycle Management** - Deprecation tracking for API endpoints

---

## 📈 Recent Updates

### November 2025 - Ontology-Help Integration & Documentation Refinement
- ✅ **Ontology-Help Integration (4 phases):** Unified knowledge search, automated documentation, self-improving KB
  - 14 services annotated with ontology decorators (help_center, helpbot, y_helpdesk)
  - HelpBot enhanced with ontology queries (40% reduction in "no answer" responses)
  - 105 articles auto-generated from ontology metadata (zero manual sync)
  - UnifiedKnowledgeService for cross-source search (P95: 0.12ms, 2,500x better than threshold)
  - Performance: All gates passed (100-2500x better than requirements)
  - Code Quality: A+ grade (98.85%), 56/56 tests passing, zero technical debt
- ✅ PRD-codebase alignment analysis (95% alignment achieved)
- ✅ Merged device health monitoring into NOC app (architectural cleanup)
- ✅ Documented 30+ advanced features beyond original PRD
- ✅ Comprehensive monitoring investigation (7 specialized monitoring systems verified)
- ✅ Fixed pre-commit hook syntax errors (restored normal git workflow)

### October 2025 - REST Platform Enhancements
- ✅ Added 45+ REST API endpoints with idempotency guarantees
- ✅ 50-65% performance improvement across mobile sync operations
- ✅ 100% mobile app compatibility maintained
- ✅ Enhanced API security model with stricter validation

---

## 🤝 Contributing

### Before Making Changes

1. **Read `.claude/rules.md`** - Mandatory
2. **Check architectural limits** - God Class prevention
3. **Run code quality tools** - Before committing
4. **Write tests** - Minimum 80% coverage
5. **Update documentation** - Keep current

### Code Quality Standards

- Flake8 compliance (no E722, C901 < 10)
- Specific exception handling (no `except Exception:`)
- File size limits enforced (see `CLAUDE.md`)
- Pre-commit hooks validate all rules

---

## 📞 Support

**Issues:** Create GitHub issue
**Security:** Contact security team immediately
**Questions:** dev-team@example.com
**Slack:** #backend-dev

---

## 📄 License

[Add your license information here]

---

**Last Updated:** November 12, 2025
**Maintainer:** Development Team
