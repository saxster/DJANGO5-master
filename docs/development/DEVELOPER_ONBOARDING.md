# Developer Onboarding Guide

> **Last Updated**: November 5, 2025
> **Status**: Complete - Phase 7 IDE Integration
> **Target**: New developers joining the enterprise facility management platform

---

## Table of Contents

1. [Quick Start (15 minutes)](#quick-start-15-minutes)
2. [Environment Setup](#environment-setup)
3. [IDE Configuration](#ide-configuration)
4. [Project Structure](#project-structure)
5. [Quality Standards](#quality-standards)
6. [Common Workflows](#common-workflows)
7. [Testing Guide](#testing-guide)
8. [Troubleshooting](#troubleshooting)
9. [Getting Help](#getting-help)

---

## Quick Start (15 minutes)

### Prerequisites

- Python 3.11.9 (required for scikit-learn compatibility)
- Git
- PostgreSQL 14.2+ (local or Docker)
- Docker & Docker Compose (optional, for PostgreSQL)
- A code editor: VSCode or PyCharm

### 1. Clone & Navigate

```bash
# Clone the repository
git clone <repo-url>
cd DJANGO5-master

# Verify Python version
python --version  # Should show: Python 3.11.9
```

### 2. Setup Virtual Environment

```bash
# Remove old environment (if exists)
rm -rf venv

# Create fresh Python 3.11.9 environment
~/.pyenv/versions/3.11.9/bin/python -m venv venv

# Activate environment
source venv/bin/activate  # macOS/Linux
# or on Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

**macOS:**
```bash
pip install -r requirements/base-macos.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
```

**Linux:**
```bash
pip install -r requirements/base-linux.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
pip install -r requirements/ai_requirements.txt
```

### 4. Configure Database

```bash
# Create .env file in project root
cp .env.example .env

# Edit .env and set DATABASE_URL:
# DATABASE_URL=postgresql://user:password@localhost:5432/intelliwiz

# Or use Docker:
docker-compose up -d postgres redis

# Run migrations
python manage.py migrate

# Create initial data
python manage.py init_intelliwiz default
```

### 5. Start Development Server

```bash
# HTTP only (simple)
python manage.py runserver

# With WebSocket support (recommended)
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

Visit `http://localhost:8000` to verify setup.

---

## Environment Setup

### Python Version Management

We use **Python 3.11.9** exclusively. This ensures compatibility with:
- scikit-learn (ML feature engineering)
- cryptography (encryption)
- Django 5.2.1
- All data science packages

**Using pyenv (recommended):**

```bash
# Install pyenv if not present
brew install pyenv  # macOS
# For Linux: https://github.com/pyenv/pyenv#installation

# Install Python 3.11.9
pyenv install 3.11.9

# Set local version
pyenv local 3.11.9

# Verify
python --version  # Python 3.11.9
```

**Verify in IDE:**

- **VSCode**: Select Python interpreter from `venv/bin/python`
- **PyCharm**: Settings → Project → Python Interpreter → Add → Existing environment → `venv/bin/python`

### Environment Variables

**Create `.env` file from template:**

```bash
cp .env.example .env
```

**Essential variables:**

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/intelliwiz
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_USER=intelliwiz
DATABASE_PASSWORD=secure_password

# Redis (for caching & Celery)
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_URL=redis://localhost:6379/1

# Django
DEBUG=True  # NEVER True in production
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Email (development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Celery (optional for development)
CELERY_BROKER_URL=redis://localhost:6379/0
```

**Never commit `.env` to Git!** It's in `.gitignore`.

### PostgreSQL Setup

**Option A: Local Installation**
```bash
# macOS
brew install postgresql@14

# Linux
sudo apt-get install postgresql-14

# Start service
brew services start postgresql@14  # macOS
sudo systemctl start postgresql    # Linux
```

**Option B: Docker (Recommended)**
```bash
# Start PostgreSQL + Redis
docker-compose up -d

# Verify
docker-compose ps
```

**Option C: Docker Desktop**
- Download from https://www.docker.com/products/docker-desktop
- Run `docker-compose up -d`

### Redis Setup

```bash
# macOS
brew install redis
brew services start redis

# Linux
sudo apt-get install redis-server
sudo systemctl start redis-server

# Docker (included in docker-compose.yml)
docker-compose up -d redis
```

---

## IDE Configuration

### VSCode (Recommended for Teams)

**Install Extensions:**

1. Open VSCode
2. Go to Extensions (Cmd+Shift+X or Ctrl+Shift+X)
3. Install recommended extensions:
   - Python (ms-python.python) - REQUIRED
   - Pylance (ms-python.vscode-pylance) - Code intelligence
   - Black Formatter (ms-python.black-formatter) - Formatting
   - Pylint (ms-python.pylint) - Linting
   - Django (batisteo.vscode-django) - Django support
   - Pytest (ms-python.pytest) - Test integration
   - GitLens (eamodio.gitlens) - Git integration

**Quick Setup:**

```bash
# Copy settings to project (if not already present)
cp .vscode/settings.json .vscode/settings.json  # Already configured

# Verify extensions in VSCode:
# Extensions tab → "Recommended" section
# Or: Ctrl+Shift+X, search "ext install ms-python.python"
```

**Key Shortcuts:**

| Action | Shortcut |
|--------|----------|
| Format code | Shift+Alt+F |
| Run tests | Ctrl+Shift+; |
| Go to definition | F12 |
| Quick fix | Ctrl+. |
| Rename symbol | F2 |
| Find usages | Shift+Ctrl+F |
| Show problems | Ctrl+Shift+M |

**Features Configured:**

- ✅ Automatic Python formatting on save (Black)
- ✅ Import sorting (isort)
- ✅ Linting with pylint & flake8
- ✅ Type checking with Pylance
- ✅ File size warnings (rulers at 150, 200 lines)
- ✅ Complexity warnings
- ✅ Django ORM intelligence
- ✅ Test runner integration

### PyCharm (Enterprise Standard)

**Version**: 2024.3 or newer

**Initial Setup:**

1. Open project directory
2. Configure Python interpreter:
   - Settings → Project → Python Interpreter
   - Click gear icon → Add
   - Select "Existing environment" → `/path/to/venv/bin/python`
3. Enable Django support:
   - Settings → Django
   - Check "Enable Django support"
   - Set Django project root: `/path/to/project`
   - Settings module: `intelliwiz_config.settings`
4. Apply inspection profile:
   - Import: File → Manage IDE Settings → Import Settings
   - Or: Copy `.idea/inspectionProfiles/ProjectDefault.xml` to `.idea/inspectionProfiles/`

**Key Shortcuts:**

| Action | Shortcut |
|--------|----------|
| Reformat code | Ctrl+Alt+L (Linux/Windows) or Cmd+Alt+L (macOS) |
| Optimize imports | Ctrl+Alt+O (Linux/Windows) or Cmd+Alt+O (macOS) |
| Run tests | Shift+F10 or Ctrl+Shift+F10 |
| Debug | Shift+F9 |
| Go to definition | Ctrl+B or Cmd+B |
| Find usages | Ctrl+Alt+F7 or Cmd+Alt+F7 |
| Show intentions/fixes | Alt+Enter |
| Terminal | Alt+F12 |

**Key Inspections Enabled:**

- ✅ Cyclomatic complexity (max 10)
- ✅ Method length (max 30 lines)
- ✅ Broad exception handling (ERROR level)
- ✅ Circular dependencies
- ✅ SQL injection detection
- ✅ Security issues (insecure hashing, etc.)
- ✅ Django-specific rules
- ✅ Import organization

**Live Templates:**

Enabled for common Django patterns:
- `@ontology_class` - Model decorator template
- `@ontology_service` - Service decorator template
- Django ORM patterns
- Test patterns

---

## Project Structure

```
DJANGO5-master/
├── .vscode/                           # VSCode configuration
│   ├── settings.json                 # Linting, formatting, testing
│   └── extensions.json               # Recommended extensions
├── .idea/                             # PyCharm configuration
│   └── inspectionProfiles/           # Custom inspection rules
│       └── ProjectDefault.xml
├── .editorconfig                      # Universal editor config
├── .pre-commit-config.yaml           # Code quality gates
├── pytest.ini                         # Test configuration
├── CLAUDE.md                          # Project guidelines (READ FIRST)
├── .claude/
│   └── rules.md                      # Quality rules (MANDATORY)
├── intelliwiz_config/                # Django configuration
│   ├── settings/                     # Settings (base, dev, prod, test)
│   ├── urls_optimized.py             # URL routing
│   ├── asgi.py                       # WebSocket support
│   └── celery.py                     # Celery configuration
├── apps/                             # Business logic (30+ apps)
│   ├── peoples/                      # Authentication & users
│   ├── attendance/                   # Attendance tracking with GPS
│   ├── work_order_management/        # Task management
│   ├── y_helpdesk/                   # Ticketing system
│   ├── reports/                      # Analytics & reporting
│   ├── ml_training/                  # ML training data platform
│   ├── journal/                      # Wellness journaling
│   ├── wellness/                     # Wellness content delivery
│   ├── core/                         # Shared utilities, security
│   └── ... (others)
├── docs/                             # Documentation
│   ├── architecture/                 # System design docs
│   ├── configuration/                # Setup & config guides
│   ├── development/                  # Developer guides
│   ├── workflows/                    # Common commands & patterns
│   ├── features/                     # Feature documentation
│   ├── testing/                      # Testing guides
│   └── troubleshooting/              # Issue resolution
├── scripts/                          # Utility scripts
│   ├── check_file_sizes.py          # Architecture validation
│   ├── check_network_timeouts.py    # Security validation
│   ├── celery_workers.sh            # Worker management
│   └── validate_code_quality.py     # Comprehensive checks
├── requirements/                     # Dependency files
│   ├── base-macos.txt               # macOS dependencies
│   ├── base-linux.txt               # Linux dependencies
│   ├── observability.txt            # Logging & monitoring
│   ├── encryption.txt               # Security packages
│   └── ai_requirements.txt          # ML packages
├── .env.example                      # Environment template
├── docker-compose.yml                # Local services (Postgres, Redis)
├── manage.py                         # Django CLI
└── README.md                         # Project overview
```

**Key Files to Review (in order):**

1. **CLAUDE.md** - Project guidelines, best practices, architecture overview
2. **.claude/rules.md** - Zero-tolerance security & quality rules
3. **docs/architecture/SYSTEM_ARCHITECTURE.md** - Complete system design
4. **docs/development/QUALITY_STANDARDS.md** - Quality enforcement details
5. **docs/workflows/COMMON_COMMANDS.md** - Development commands
6. **docs/testing/TESTING_AND_QUALITY_GUIDE.md** - Testing standards

---

## Quality Standards

### Architecture Limits (Non-Negotiable)

These limits prevent "god files" and enforce single responsibility:

| File Type | Max Lines | Why | Example |
|-----------|-----------|-----|---------|
| **Settings** | 200 | Easier to configure per environment | `intelliwiz_config/settings/base.py` |
| **Models** | 150 | One model per file OR use `models/` directory | `apps/peoples/models.py` |
| **Views** | 500 (warning) | Delegate to services (max method: 30 lines) | Views should call services |
| **Forms** | 100 | Split into composable form classes | One form per concern |
| **Utilities** | 50 per function | Atomic, testable functions | `apps/core/utils_new/` |

**Enforcement:** Pre-commit hooks block commits that violate these limits.

### Code Quality Metrics

| Metric | Target | Tool |
|--------|--------|------|
| **Test Coverage** | ≥75% | pytest-cov |
| **Cyclomatic Complexity** | <10 per method | pylint, Xenon |
| **Maintainability Index** | B+ or better | Radon |
| **Security Issues** | Zero critical | Bandit, Semgrep |
| **Broad Exceptions** | None | Pre-commit hooks |

### Pre-commit Hooks

**Automatically enforced before every commit:**

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files

# Specific hook
pre-commit run file-size-validation --all-files
```

**Hooks enabled:**

- ✅ File size validation
- ✅ Cyclomatic complexity checks
- ✅ Network timeout validation
- ✅ Generic exception detection
- ✅ Import organization
- ✅ Security scanning (Bandit)
- ✅ Secret detection (gitleaks)
- ✅ Django system checks

### Forbidden Patterns

**These patterns are FORBIDDEN and will cause pre-commit/CI-CD failures:**

```python
# ❌ FORBIDDEN: Generic exception handling
try:
    user.save()
except Exception as e:  # TOO BROAD - use specific exceptions
    logger.error(f"Error: {e}")

# ✅ CORRECT: Use specific exceptions
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
try:
    user.save()
except DATABASE_EXCEPTIONS as e:
    logger.error(f"Database error: {e}", exc_info=True)

# ❌ FORBIDDEN: Network calls without timeout
response = requests.get(api_url)  # Can hang forever

# ✅ CORRECT: Always include timeout
response = requests.get(api_url, timeout=(5, 15))  # (connect, read)

# ❌ FORBIDDEN: File operations without validation
file_path = request.GET['file']
with open(file_path, 'rb') as f:  # Path traversal vulnerability
    return FileResponse(f)

# ✅ CORRECT: Use SecureFileDownloadService
from apps.core.services.secure_file_download_service import SecureFileDownloadService
response = SecureFileDownloadService.validate_and_serve_file(
    filepath=attachment.filepath,
    user=request.user,
    owner_id=attachment.owner
)
```

---

## Common Workflows

### Starting a New Feature

**1. Create feature branch:**
```bash
git checkout -b feature/my-feature-name
```

**2. Read guidelines:**
```bash
# Know the rules before coding
cat CLAUDE.md
cat .claude/rules.md
```

**3. Write tests first:**
```bash
# Test-driven development ensures quality
# Create test file in apps/myapp/tests/
pytest tests/test_my_feature.py -v
```

**4. Write code:**
```bash
# Follow IDE guidance for violations
# Your IDE will highlight:
# - File size warnings at 150/200 lines
# - Complexity warnings
# - Missing timeouts in network calls
# - Broad exception handlers
```

**5. Check quality before commit:**
```bash
# Run all quality checks
python scripts/validate_code_quality.py --verbose

# Or just pre-commit
pre-commit run --all-files
```

**6. Commit with message:**
```bash
# Format: type(scope): description
# Examples:
git commit -m "feat(attendance): add GPS geofence validation"
git commit -m "fix(helpdesk): resolve ticket escalation race condition"
git commit -m "refactor(core): extract datetime utilities"
git commit -m "test(peoples): add comprehensive user model tests"
```

### Running Tests

**Full test suite:**
```bash
# With coverage report
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v

# Open coverage report
open coverage_reports/html/index.html  # macOS
# or browser: file:///Users/amar/Desktop/MyCode/DJANGO5-master/coverage_reports/html/index.html
```

**By category:**
```bash
# Unit tests only
python -m pytest -m unit -v

# Integration tests
python -m pytest -m integration -v

# Security tests
python -m pytest -m security -v

# Performance tests
python -m pytest -m performance -v

# Race condition tests (critical)
python -m pytest -k "race" -v
```

**Specific test:**
```bash
# Run single test file
python -m pytest apps/peoples/tests/test_models.py -v

# Run single test class
python -m pytest apps/peoples/tests/test_models.py::TestPeopleModel -v

# Run single test method
python -m pytest apps/peoples/tests/test_models.py::TestPeopleModel::test_create_user -v
```

**Debug a failing test:**
```bash
# With print output
python -m pytest apps/myapp/tests/test_module.py -v -s

# With debugger
python -m pytest apps/myapp/tests/test_module.py --pdb

# With verbose output
python -m pytest apps/myapp/tests/test_module.py -vv
```

### Database Migrations

**Create migration:**
```bash
python manage.py makemigrations

# Create migration with name
python manage.py makemigrations --name add_user_phone
```

**Apply migrations:**
```bash
# All pending migrations
python manage.py migrate

# Specific app
python manage.py migrate peoples

# Specific migration
python manage.py migrate peoples 0005_auto_20241105_1200
```

**Undo migrations (development only):**
```bash
# Undo last migration of app
python manage.py migrate peoples 0004_auto_20241101_1000

# Undo all migrations
python manage.py migrate peoples zero
```

### Starting Celery Workers

```bash
# All optimized workers (recommended)
./scripts/celery_workers.sh start

# Individual workers:

# Email worker (priority)
celery -A intelliwiz_config worker -Q email -c 4 -l info

# Task worker (general purpose)
celery -A intelliwiz_config worker -Q celery -c 8 -l info

# Scheduled tasks worker
celery -A intelliwiz_config beat -l info

# Monitor with Flower
celery -A intelliwiz_config events --broker redis://localhost:6379/0
flower -A intelliwiz_config --port=5555
# Open http://localhost:5555
```

### Code Formatting

**Auto-format entire file:**

VSCode:
- Ctrl+Shift+P → Format Document
- Or: Shift+Alt+F

PyCharm:
- Ctrl+Alt+L (Linux/Windows)
- Cmd+Alt+L (macOS)

**Format on save:** ✅ Enabled by default in both IDEs

**Manual formatting:**
```bash
# Black (code formatter)
black apps/

# isort (import sorter)
isort apps/

# Together
black apps/ && isort apps/
```

### Linting & Type Checking

```bash
# Pylint
pylint apps/myapp/models.py

# Flake8
flake8 apps/myapp/ --max-line-length=120

# Mypy (type checking)
mypy apps/myapp/ --ignore-missing-imports

# Bandit (security)
bandit -r apps/myapp/
```

---

## Testing Guide

### Test Structure

```python
# apps/peoples/tests/test_models.py

import pytest
from django.test import TestCase
from apps.peoples.models import People

# Use pytest fixtures for clarity
@pytest.fixture
def user(db):
    return People.objects.create_user(
        email='test@example.com',
        password='secure_password'
    )

# Test class format
class TestPeopleModel:
    """Tests for the People model."""

    def test_create_user(self, db):
        """Test user creation with email and password."""
        user = People.objects.create_user(
            email='new@example.com',
            password='password123'
        )
        assert user.email == 'new@example.com'
        assert user.is_active

    def test_user_string_representation(self, user):
        """Test user __str__ method."""
        assert str(user) == user.email
```

### Test Markers

Use pytest markers to organize tests:

```python
# Unit test (fast, no database)
@pytest.mark.unit
def test_calculate_tax():
    assert calculate_tax(100) == 10

# Integration test (uses database, external services)
@pytest.mark.integration
def test_user_creation_and_email():
    user = create_user('test@example.com')
    assert email_sent_to(user.email)

# Security test
@pytest.mark.security
def test_csrf_protection():
    response = client.post('/api/users/', {...})
    assert 'csrftoken' in response.cookies

# Performance test
@pytest.mark.performance
def test_user_list_performance():
    # Create 1000 users
    # Assert query time < 100ms
```

Run by marker:
```bash
pytest -m unit      # Fast unit tests only
pytest -m integration  # Slower integration tests
pytest -m security   # Security tests
pytest -m "not slow" # Skip slow tests
```

### Common Test Patterns

**Testing API endpoints:**
```python
@pytest.mark.integration
class TestUserAPI:
    def test_create_user_endpoint(self, client):
        response = client.post('/api/v1/users/', {
            'email': 'new@example.com',
            'password': 'secure123'
        })
        assert response.status_code == 201
        assert response.data['email'] == 'new@example.com'

    def test_list_users_requires_authentication(self, client):
        response = client.get('/api/v1/users/')
        assert response.status_code == 401
```

**Testing models:**
```python
@pytest.mark.unit
class TestUserModel:
    def test_email_is_unique(self, db):
        People.objects.create(email='test@example.com')
        with pytest.raises(IntegrityError):
            People.objects.create(email='test@example.com')

    def test_full_name_property(self, user):
        user.first_name = 'John'
        user.last_name = 'Doe'
        assert user.full_name == 'John Doe'
```

**Testing race conditions:**
```python
@pytest.mark.race
def test_concurrent_user_updates(db):
    user = People.objects.create(email='test@example.com', count=0)

    def increment():
        u = People.objects.get(id=user.id)
        u.count += 1
        u.save()

    # Run concurrently
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(increment) for _ in range(5)]
        for f in futures:
            f.result()

    # Should be 5 (or account for race condition)
    assert People.objects.get(id=user.id).count == 5
```

---

## Troubleshooting

### Python Version Issues

**Problem**: `ModuleNotFoundError: No module named 'sklearn'`

**Solution**:
```bash
# Verify Python version
python --version  # Must be 3.11.9

# If wrong version:
pyenv local 3.11.9
python -m venv venv
source venv/bin/activate
pip install -r requirements/base-macos.txt
```

### Database Connection Issues

**Problem**: `OperationalError: could not connect to server`

**Solution**:
```bash
# Check if PostgreSQL is running
psql -U postgres -d postgres

# Start PostgreSQL
brew services start postgresql@14  # macOS
sudo systemctl start postgresql     # Linux

# Or use Docker
docker-compose up -d postgres
docker-compose logs postgres
```

### Pre-commit Hook Failures

**Problem**: `❌ file-size-validation failed`

**Solution**:
```bash
# Check which file is too large
python scripts/check_file_sizes.py --verbose

# If model file > 150 lines:
# 1. Convert models.py to models/ directory
# 2. Split model into separate files

# If settings file > 200 lines:
# 1. Create intelliwiz_config/settings/
# 2. Split into base.py, dev.py, prod.py, test.py

# Skip temporarily (NOT RECOMMENDED)
git commit --no-verify -m "WIP: temporary bypass"
```

**Problem**: `❌ cyclomatic-complexity-check failed`

**Solution**:
```bash
# Find complex methods
radon cc apps/ -a -n C

# Refactor complex method:
# 1. Extract helper methods
# 2. Use guard clauses (early returns)
# 3. Use strategy pattern instead of if-elif chains
```

**Problem**: `❌ network-timeout-validation failed`

**Solution**:
```bash
# Find network calls without timeout
python scripts/check_network_timeouts.py --verbose

# Add timeout to all requests:
import requests
response = requests.get(url, timeout=(5, 15))  # (connect, read)
response = requests.post(url, json=data, timeout=(5, 30))
```

### Import Issues

**Problem**: `ModuleNotFoundError: No module named 'apps.myapp'`

**Solution**:
```bash
# 1. Verify app is in INSTALLED_APPS
grep -r "apps.myapp" intelliwiz_config/settings/

# 2. Verify apps/ is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd):$(pwd)/apps"

# 3. Restart IDE and/or Python interpreter
```

### IDE Issues

**VSCode: Pylance can't find modules**
- Settings → Python → Analysis → Extra Paths
- Add: `${workspaceFolder}/apps`, `${workspaceFolder}/intelliwiz_config`
- Restart VSCode

**PyCharm: Unresolved references**
- Settings → Project → Python Interpreter
- Verify correct venv selected
- Mark `apps/` as "Sources Root"

### Test Failures

**Problem**: `FAILED: ModuleNotFoundError: No module named 'apps'`

**Solution**:
```bash
# Verify pytest.ini exists
cat pytest.ini

# Should have:
# [tool:pytest]
# DJANGO_SETTINGS_MODULE = intelliwiz_config.settings_test
# testpaths = apps tests

# Run with correct settings
DJANGO_SETTINGS_MODULE=intelliwiz_config.settings_test pytest apps/
```

**Problem**: `FAILED: django.core.exceptions.ImproperlyConfigured`

**Solution**:
```bash
# Run Django system check
python manage.py check

# Run migrations
python manage.py migrate

# Run with test settings
python manage.py test --settings=intelliwiz_config.settings_test
```

### Performance Issues

**Problem**: Tests running slowly

**Solution**:
```bash
# Skip slow tests
pytest -m "not slow" -v

# Parallel testing
pytest -n auto  # Requires pytest-xdist

# Check what's slow
pytest --durations=10  # Top 10 slowest tests
```

**Problem**: Development server is slow

**Solution**:
```bash
# Disable debug toolbar in development
DEBUG_TOOLBAR = False

# Use cached queries
# Enable Django cache in settings/dev.py

# Check N+1 queries
python manage.py shell
>>> from django.db import connection
>>> from django.test.utils import CaptureQueriesContext
>>> with CaptureQueriesContext(connection) as ctx:
...     list(MyModel.objects.all())
>>> len(ctx)  # Should be small
```

---

## Getting Help

### Documentation Resources

**Must-Read (in order):**

1. **CLAUDE.md** - `~/DJANGO5-master/CLAUDE.md`
   - Project overview, architecture, quick start commands
   - Read this first!

2. **.claude/rules.md** - `~/.claude/rules.md`
   - Zero-tolerance security & quality rules
   - All forbidden patterns

3. **System Architecture** - `docs/architecture/SYSTEM_ARCHITECTURE.md`
   - Complete system design, business domains, data flow

4. **Quality Standards** - `docs/development/QUALITY_STANDARDS.md`
   - Code quality metrics, enforcement mechanisms, remediation

5. **Testing Guide** - `docs/testing/TESTING_AND_QUALITY_GUIDE.md`
   - Testing standards, patterns, CI/CD integration

6. **Common Commands** - `docs/workflows/COMMON_COMMANDS.md`
   - All development commands organized by category

7. **Troubleshooting** - `docs/troubleshooting/COMMON_ISSUES.md`
   - Solutions to common problems

### Development Team Communication

**Slack channels:**
- `#development` - General discussion
- `#quality-gates` - CI/CD failures, quality issues
- `#security` - Security concerns, vulnerability reports
- `#architecture` - Design discussions

### Code Review Checklist

Before creating a pull request, verify:

- [ ] **Read CLAUDE.md** - All guidelines followed
- [ ] **Pre-commit passes** - `pre-commit run --all-files`
- [ ] **Tests pass** - `pytest --tb=short -v`
- [ ] **Coverage ≥ 75%** - `pytest --cov=apps`
- [ ] **No violations** - `python scripts/validate_code_quality.py`
- [ ] **File sizes OK** - Models < 150, Settings < 200
- [ ] **Complexity < 10** - `radon cc apps/`
- [ ] **No generic exceptions** - Only specific exception types
- [ ] **Network calls have timeouts** - `timeout=(5, 15)`
- [ ] **Commit message clear** - `type(scope): description`

### Emergency Support

**Security issue?**
- Contact security team immediately
- Do NOT create public issue
- Mark as `[SECURITY]` in communication

**Production incident?**
- Notify on-call engineer
- Check `docs/troubleshooting/COMMON_ISSUES.md`
- Have logs ready

**Can't unblock yourself?**
- Document what you've tried
- Check relevant documentation section above
- Ask in #development with context

---

## Next Steps

### Day 1: Foundation
1. ✅ Clone repo and set up environment (follow Quick Start)
2. ✅ Install IDE extensions
3. ✅ Read CLAUDE.md and .claude/rules.md
4. ✅ Run test suite to verify setup

### Day 2: Understanding
1. ✅ Read System Architecture doc
2. ✅ Explore project structure (especially `apps/`)
3. ✅ Review existing code in your domain
4. ✅ Understand entity relationships

### Day 3: Contributing
1. ✅ Pick a small task or bug fix
2. ✅ Create feature branch
3. ✅ Write tests first (TDD)
4. ✅ Implement feature
5. ✅ Run quality checks
6. ✅ Submit PR

### Week 1+: Deepening
1. ✅ Contribute to multiple features
2. ✅ Participate in code reviews
3. ✅ Learn Celery background tasks
4. ✅ Study domain-specific systems (Helpdesk, Wellness, etc.)

---

## FAQ

**Q: Can I use Python 3.12 instead of 3.11.9?**
A: No. 3.11.9 is required for scikit-learn compatibility. Use `pyenv local 3.11.9` to enforce it.

**Q: How often do I need to run tests?**
A: Before every commit. Pre-commit hooks run key tests automatically.

**Q: Can I skip pre-commit hooks?**
A: Only in emergencies with `git commit --no-verify`. But fix issues immediately after.

**Q: What's the difference between `apps/` and `intelliwiz_config/`?**
A: `apps/` contains business logic (models, services, views). `intelliwiz_config/` contains Django configuration (settings, URLs, middleware).

**Q: How do I know which testing marker to use?**
A: Use `@pytest.mark.unit` for fast tests with no I/O. Use `@pytest.mark.integration` for tests that touch database/API. Use `@pytest.mark.security` for security-specific tests.

**Q: What's the 75% coverage threshold?**
A: At least 75% of code lines must be executed by tests. Run `pytest --cov=apps` to check.

**Q: How do I write a good commit message?**
A: Use format `type(scope): description`. Examples:
- `feat(attendance): add GPS geofence validation`
- `fix(helpdesk): resolve race condition in escalation`
- `test(core): add comprehensive encryption tests`
- `docs(onboarding): update developer guide`

---

**Document Version**: 1.0
**Last Updated**: November 5, 2025
**Status**: Phase 7 Complete
**Maintainer**: Development Team

**Revision History:**
- Nov 5, 2025 - Initial version (Phase 7: IDE Integration & Onboarding)

---

**Ready to start?** Follow the [Quick Start (15 minutes)](#quick-start-15-minutes) section above!
