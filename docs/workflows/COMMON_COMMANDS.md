# Common Commands Reference

> **Complete command reference organized by category**

---

## Development Server

### HTTP Server (Django runserver)

```bash
python manage.py runserver
```

### ASGI Server (with WebSocket support)

```bash
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

---

## Testing

### Full test suite with coverage

```bash
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v
```

### Test by category

```bash
python -m pytest -m unit          # Unit tests only
python -m pytest -m integration   # Integration tests
python -m pytest -m security      # Security tests
```

### Specific test suites

```bash
python -m pytest apps/peoples/tests/test_models/test_people_model_comprehensive.py -v
python -m pytest apps/core/tests/test_datetime_refactoring_comprehensive.py -v
python -m pytest apps/scheduler/tests/test_schedule_uniqueness_comprehensive.py -v
```

### Race condition tests

```bash
python -m pytest -k "race" -v
python -m pytest apps/core/tests/test_background_task_race_conditions.py -v
python -m pytest apps/y_helpdesk/tests/test_ticket_escalation_race_conditions.py -v
```

### Pre-configured test subset

```bash
./run_working_tests.sh
```

### Stream testing

```bash
python -m pytest apps/streamlab/tests/ apps/issue_tracker/tests/ -v
python run_stream_tests.py                              # Complete suite
python testing/stream_load_testing/spike_test.py        # Performance validation
```

---

## Celery Workers

### Start all optimized workers

```bash
./scripts/celery_workers.sh start
```

### Real-time dashboard

```bash
./scripts/celery_workers.sh monitor
```

---

## Database

### Migrations

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py makemigrations && python manage.py migrate  # Combined
```

### Initialize with defaults

```bash
python manage.py init_intelliwiz default
```

### Database shell with SQL logging

```bash
python manage.py shell_plus --print-sql
```

### Model visualization

```bash
# Requires django-extensions
python manage.py graph_models --all-applications --group-models -o models.png
```

---

## Code Quality Validation

### Full validation

```bash
python scripts/validate_code_quality.py --verbose
```

### Generate quality report

```bash
python scripts/validate_code_quality.py --report quality_report.md
```

### Flake8 validation

```bash
flake8 apps/
```

---

## Schedule Health & Celery Beat Validation

### Comprehensive validation

```bash
python manage.py validate_schedules --verbose
```

### Check specific issues

```bash
python manage.py validate_schedules --check-duplicates          # Duplicate schedules
python manage.py validate_schedules --check-hotspots            # Overloaded time slots
python manage.py validate_schedules --check-idempotency         # Duplicate execution
python manage.py validate_schedules --check-orphaned-tasks      # Beat → task mapping ✨ NEW
```

### Fix schedule issues (dry run)

```bash
python manage.py validate_schedules --fix --dry-run
```

### Orphaned task detection

```bash
# Validates that ALL beat schedule tasks are registered
# CRITICAL: Orphaned tasks cause Celery beat scheduler to fail silently
python manage.py validate_schedules --check-orphaned-tasks --verbose
```

---

## Task Idempotency

### Analyze tasks for migration

```bash
python scripts/migrate_to_idempotent_tasks.py --analyze
```

### Migrate specific task

```bash
python scripts/migrate_to_idempotent_tasks.py --task auto_close_jobs
```

---

## Celery Task Auditing

### Full task inventory

```bash
python scripts/audit_celery_tasks.py --generate-report --output CELERY_TASK_INVENTORY_REPORT.md
```

### Show only duplicates

```bash
python scripts/audit_celery_tasks.py --duplicates-only
```

---

## Unused Code Detection

### Find backup files

```bash
python scripts/detect_unused_code.py --verbose
```

### Generate report

```bash
python scripts/detect_unused_code.py --report unused.md
```

---

## Code Smell Detection

### Detect all code smells

```bash
python scripts/detect_code_smells.py --report CODE_SMELL_REPORT.md
```

### Skip test files

```bash
python scripts/detect_code_smells.py --skip-tests --report REPORT.md
```

### JSON output for CI/CD

```bash
python scripts/detect_code_smells.py --json > code_smells.json
```

### CI/CD integration (exit 1 if violations)

```bash
python scripts/detect_code_smells.py --check
```

---

## Exception Handling Migration

### Analyze generic exception patterns

```bash
python scripts/migrate_exception_handling.py --analyze
```

### Generate migration report

```bash
python scripts/migrate_exception_handling.py --report exception_migration_report.md
```

### Auto-fix high confidence issues

```bash
python scripts/migrate_exception_handling.py --fix --confidence HIGH
```

---

## Security Scorecard

### Manual evaluation (runs daily at 6 AM automatic)

```bash
python manage.py shell
>>> from background_tasks.non_negotiables_tasks import evaluate_non_negotiables
>>> evaluate_non_negotiables.delay()
```

---

## Redis & Cache Monitoring

### Comprehensive verification

```bash
python scripts/verify_redis_cache_config.py
```

### Test specific environment

```bash
python scripts/verify_redis_cache_config.py --environment production
```

### Performance dashboard

```bash
open http://localhost:8000/admin/redis/dashboard/
```

---

## Redis TLS/SSL (PCI DSS Level 1 compliance)

### Check certificate expiration

```bash
python manage.py check_redis_certificates --alert-days 30
```

### Email if expiring soon

```bash
python manage.py check_redis_certificates --send-email
```

---

## Static Files

### Production collection

```bash
python manage.py collectstatic --no-input
```

---

## API Schema & Documentation

### OpenAPI schema (REST v1/v2)

```bash
curl http://localhost:8000/api/schema/swagger.json > openapi.json
```

### WebSocket message schema

```bash
cat docs/api-contracts/websocket-messages.json
```

### Interactive API docs

```bash
open http://localhost:8000/api/schema/swagger/
open http://localhost:8000/api/schema/redoc/
```

### Schema metadata

```bash
curl http://localhost:8000/api/schema/metadata/
```

---

## Git Hooks Setup

### Install validation hooks

```bash
./scripts/setup-git-hooks.sh
```

### Enable pre-commit framework

```bash
pre-commit install
```

---

## Python Environment

### Using pyenv (recommended)

```bash
# Install Python 3.11.9
pyenv install 3.11.9
pyenv local 3.11.9

# Create fresh virtual environment
rm -rf venv
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate

# Verify Python version
python --version  # Should show: Python 3.11.9
```

### Install dependencies (macOS)

```bash
# Activate virtual environment first
source venv/bin/activate

# Install core dependencies
pip install -r requirements/base-macos.txt

# Install additional requirements
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
```

### Install dependencies (Linux)

```bash
# Install core dependencies with CUDA support
pip install -r requirements/base-linux.txt

# Install additional requirements
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
pip install -r requirements/ai_requirements.txt
```

---

**Last Updated**: October 29, 2025
**Maintainer**: Development Team
**Related**: [Quick Start](../../CLAUDE.md#quick-start)
