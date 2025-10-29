# Reference Guide

**Complete command catalog and configuration reference**

→ **Quick start:** See [CLAUDE.md](../CLAUDE.md#daily-commands) for most common commands

---

## Table of Contents

- [Commands Catalog](#commands-catalog)
- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Testing Reference](#testing-reference)
- [Code Quality Tools](#code-quality-tools)

---

## Commands Catalog

### By Domain

#### Development

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `python manage.py runserver` | Start HTTP dev server | "Starting development server..." |
| `daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application` | Start with WebSockets | "Listening on TCP address..." |
| `python manage.py shell` | Django shell | Interactive Python prompt |
| `python manage.py check` | System check | "System check identified 0 issues" |
| `python manage.py makemigrations` | Create migrations | "Migrations for 'app_name':" |
| `python manage.py migrate` | Apply migrations | "Applying migrations..." |
| `python manage.py init_intelliwiz default` | Initialize system | "Initialization complete" |

#### Celery

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `./scripts/celery_workers.sh start` | Start all workers | "Workers started" |
| `./scripts/celery_workers.sh stop` | Stop workers | "Workers stopped" |
| `./scripts/celery_workers.sh monitor` | Real-time dashboard | Opens dashboard |
| `python manage.py validate_schedules --verbose` | Validate beat schedule | "Validation complete: X tasks" |
| `python manage.py validate_schedules --check-duplicates` | Check duplicate schedules | Lists duplicates or "No duplicates" |
| `python manage.py validate_schedules --check-orphaned-tasks` | Find orphaned tasks | Lists orphaned or "All tasks registered" |
| `python scripts/audit_celery_tasks.py --generate-report` | Audit all tasks | Generates CELERY_TASK_INVENTORY_REPORT.md |

#### Database

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `python manage.py dbshell` | Database shell | PostgreSQL prompt |
| `python manage.py flush` | Clear database | "Are you sure? (yes/no)" |
| `python manage.py loaddata fixture.json` | Load fixtures | "Installed X objects" |
| `python manage.py dumpdata app.Model` | Export data | JSON output |
| `psql -U postgres -c "SELECT 1"` | Test PostgreSQL | "1\n---\n1 row" |

#### Testing

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `pytest --cov=apps --cov-report=html` | All tests with coverage | "X passed, coverage: Y%" |
| `pytest -m unit` | Unit tests only | "X passed" |
| `pytest -m integration` | Integration tests | "X passed" |
| `pytest -m security` | Security tests | "X passed" |
| `pytest -k "race" -v` | Race condition tests | Verbose output |
| `pytest apps/path/to/test.py -v` | Specific test file | Detailed results |

#### Code Quality

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `python scripts/validate_code_quality.py --verbose` | Validate all rules | "X issues found" or "All checks passed" |
| `flake8 apps/` | Style check | Lists violations or "0 errors" |
| `python scripts/detect_unused_code.py --verbose` | Find unused code | Lists unused files |
| `python scripts/detect_code_smells.py --report` | Detect anti-patterns | Generates CODE_SMELL_REPORT.md |
| `python scripts/audit_celery_tasks.py --duplicates-only` | Find duplicate tasks | Lists duplicates |

#### Monitoring

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `python scripts/verify_redis_cache_config.py` | Verify Redis config | "All checks passed" |
| `python manage.py check_redis_certificates --alert-days 30` | Check TLS certs | "Certificates valid for X days" |
| `tail -f logs/intelliwiz.log` | View logs | Live log stream |
| `redis-cli ping` | Test Redis | "PONG" |

### By Use Case

#### Daily Workflow
```bash
# 1. Start services
python manage.py runserver
./scripts/celery_workers.sh start

# 2. Run tests before committing
pytest -m unit  # Fast tests
flake8 apps/    # Style check

# 3. Create migrations if models changed
python manage.py makemigrations
python manage.py migrate

# 4. Validate code quality
python scripts/validate_code_quality.py --verbose
```

#### Debugging
```bash
# Check system health
python manage.py check
redis-cli ping
psql -U postgres -c "SELECT 1"

# View logs
tail -f logs/intelliwiz.log

# Django shell for investigation
python manage.py shell

# Celery worker status
./scripts/celery_workers.sh monitor
```

#### Performance Tuning
```bash
# Analyze query performance
python manage.py shell
>>> from django.db import connection
>>> connection.queries  # Recent queries

# Check cache hit rate
python scripts/verify_redis_cache_config.py

# Profile specific endpoint
# Add django-debug-toolbar to settings.INSTALLED_APPS
```

#### Security Audit
```bash
# Run security tests
pytest -m security

# Check for code smells
python scripts/detect_code_smells.py --report

# Validate all quality rules
python scripts/validate_code_quality.py --verbose

# Security scorecard
python manage.py shell
>>> from background_tasks.non_negotiables_tasks import evaluate_non_negotiables
>>> evaluate_non_negotiables.delay()
```

---

## Environment Variables

### Required Variables

| Variable | Purpose | Example | Validation |
|----------|---------|---------|------------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:pass@localhost/db` | Fail-fast on startup |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/1` | Fail-fast on startup |
| `SECRET_KEY` | Django secret key | Random 50+ chars | Fail-fast on startup |
| `REDIS_PASSWORD` | Redis authentication | `secure_password_here` | Warning if missing in dev |

### Optional Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `DEBUG` | Debug mode | `False` | NEVER True in production |
| `ALLOWED_HOSTS` | Allowed hostnames | `localhost,127.0.0.1` | Comma-separated |
| `DJANGO_SETTINGS_MODULE` | Settings module | `intelliwiz_config.settings.development` | Auto-detected |
| `CELERY_BROKER_URL` | Celery broker | Same as `REDIS_URL` | Redis backend |
| `AWS_ACCESS_KEY_ID` | AWS credentials | None | For S3 uploads |
| `SENTRY_DSN` | Error tracking | None | Production monitoring |

### Environment-Specific Overrides

**Development (`.env.dev.secure`):**
```bash
DEBUG=True
DATABASE_URL=postgresql://postgres:postgres@localhost/intelliwiz_dev
REDIS_URL=redis://localhost:6379/1
SECRET_KEY=dev-secret-key-change-in-production
```

**Production (`.env.production`):**
```bash
DEBUG=False
DATABASE_URL=postgresql://user:pass@rds.amazonaws.com/intelliwiz_prod
REDIS_URL=rediss://elasticache.amazonaws.com:6380/1
SECRET_KEY=<generated-secret-key>
REDIS_PASSWORD=<secure-password>
SENTRY_DSN=https://...@sentry.io/project
```

### Security Considerations

- **Never commit** `.env.production` to git
- **Always use** environment variables for secrets (not hardcoded)
- **Validate** required variables on Django startup (fail-fast)
- **Rotate** `SECRET_KEY` and `REDIS_PASSWORD` quarterly

---

## Configuration Files

### Settings Structure

```
intelliwiz_config/settings/
├── base.py               # Core Django settings (imports only)
├── development.py        # Dev overrides (DEBUG=True)
├── production.py         # Production overrides (DEBUG=False)
└── security/
    ├── middleware.py     # Security middleware config
    └── csp.py            # Content Security Policy
```

**Loading order:** `base.py` → environment-specific → security modules

### Redis Configuration

**Centralized in** `intelliwiz_config/settings/redis_optimized.py`:

```python
# Production: Optimized Redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100,
                'socket_timeout': 5,
                'socket_connect_timeout': 5,
            },
            'PASSWORD': os.getenv('REDIS_PASSWORD'),
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',  # JSON (compliance)
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        }
    },
    'select2': {
        'BACKEND': 'apps.core.cache.materialized_view_select2.MaterializedViewCache',
        'LOCATION': '',  # PostgreSQL materialized views (not Redis)
    }
}
```

**Cache backends:**
- **default:** Redis DB 1 (general caching)
- **select2:** PostgreSQL materialized views (dropdowns)
- **sessions:** PostgreSQL (django_session table)

### Database Settings

```python
# PostgreSQL with PostGIS
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.getenv('DB_NAME', 'intelliwiz'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'postgres'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # 10 min connection pooling
    }
}
```

### Logging Configuration

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/intelliwiz.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
        },
        'apps': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
        }
    }
}
```

---

## Testing Reference

### Test Categories

```python
# Markers in pytest.ini
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (database, external services)
    security: Security tests (penetration, vulnerability)
    race: Race condition tests (concurrency)
```

### Running Tests

```bash
# All tests with coverage
pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v

# By category
pytest -m unit              # Fast (<10s)
pytest -m integration       # Medium (~1 min)
pytest -m security          # Security suite
pytest -m race              # Race conditions

# Specific app
pytest apps/peoples/tests/

# Specific test file
pytest apps/peoples/tests/test_models/test_people_model.py -v

# Specific test function
pytest apps/peoples/tests/test_models/test_people_model.py::test_create_user -v

# With verbose output
pytest -v --tb=short

# Stop on first failure
pytest -x
```

### Coverage Requirements

- **Overall:** 80%+ coverage target
- **Critical paths:** 95%+ (authentication, payments, security)
- **New code:** 90%+ (enforced in CI/CD)

### Test Patterns

#### Unit Test Example

```python
import pytest
from apps.peoples.models import People

@pytest.mark.unit
def test_create_user():
    """Test user creation with required fields"""
    user = People.objects.create_user(
        loginid='testuser',
        email='test@example.com',
        password='SecurePass123!'
    )
    assert user.loginid == 'testuser'
    assert user.check_password('SecurePass123!')
```

#### Integration Test Example

```python
import pytest
from django.test import Client

@pytest.mark.integration
@pytest.mark.django_db
def test_login_flow():
    """Test complete login workflow"""
    client = Client()
    response = client.post('/api/v1/auth/login/', {
        'loginid': 'testuser',
        'password': 'SecurePass123!'
    })
    assert response.status_code == 200
    assert 'token' in response.json()
```

---

## Code Quality Tools

### Scripts

#### validate_code_quality.py

**Purpose:** Comprehensive code quality validation

```bash
# Full validation
python scripts/validate_code_quality.py --verbose

# Generate report
python scripts/validate_code_quality.py --report quality_report.md
```

**Checks:**
- ✅ Wildcard imports (except Django settings pattern)
- ✅ Generic exception handling
- ✅ Network timeout parameters
- ✅ Code injection (eval/exec)
- ✅ Blocking I/O (time.sleep in request paths)
- ✅ sys.path manipulation
- ✅ Production print statements

#### detect_unused_code.py

**Purpose:** Find backup files and unused code

```bash
# Scan for unused code
python scripts/detect_unused_code.py --verbose

# Generate detailed report
python scripts/detect_unused_code.py --report unused_code_report.md
```

**Detects:**
- Backup files: `*_refactored.py`, `*_backup.py`, `*_old.py`
- Deprecated directories: `*UNUSED*`, `*_deprecated`
- Large commented code blocks (>10 lines)

#### detect_code_smells.py

**Purpose:** Detect anti-patterns

```bash
# Detect all smells
python scripts/detect_code_smells.py --report CODE_SMELL_REPORT.md

# Skip test files
python scripts/detect_code_smells.py --skip-tests

# JSON output for CI/CD
python scripts/detect_code_smells.py --json > code_smells.json
```

**Detects:**
- Bare except blocks
- Oversized files (violates architectural limits)
- Backup/stub files

### Flake8 Configuration

**File:** `.flake8`

```ini
[flake8]
max-line-length = 120
max-complexity = 10
exclude = migrations,__pycache__,.git,venv

# Enforced rules
select = E,W,F,C,T
# E722: Bare except blocks (STRICT)
# T001: Print statements in production
# C901: Cyclomatic complexity > 10

# Per-file ignores
per-file-ignores =
    scripts/*.py:T001                # CLI output OK
    test_*.py:T001,E501,C901         # Test complexity OK
    */management/commands/*.py:T001  # CLI output OK
```

### Pre-Commit Hooks

**Installation:**
```bash
./scripts/setup-git-hooks.sh  # Install hooks
pre-commit install            # Enable pre-commit framework
```

**Hooks run on commit:**
- Flake8 style check
- Bare except validation
- Print statement detection
- Celery beat schedule validation
- Markdown link checking

---

## Additional Resources

### Related Documentation

- **Quick Start:** [CLAUDE.md](../CLAUDE.md) - Daily commands and setup
- **Celery Guide:** [CELERY.md](CELERY.md) - Background processing
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- **Rules:** `RULES.md` - Mandatory patterns (to be created)

### Key Files

- **Settings:** `intelliwiz_config/settings/`
- **URLs:** `intelliwiz_config/urls_optimized.py`
- **Celery:** `intelliwiz_config/celery.py`
- **Test config:** `pytest.ini`

---

**Last Updated:** 2025-10-29
**Maintainer:** Team Collective
**Review Cycle:** As-needed
