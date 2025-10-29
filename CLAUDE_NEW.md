# CLAUDE.md

> Quick Start for Django 5.2.1 | Multi-tenant | REST API | PostgreSQL

---

## 🎯 Quick Navigation

**I need to...**
- [⚡ Get started](#-5-minute-setup) → Setup environment in 5 minutes
- [📋 Run a command](#-daily-commands) → Find command in single table
- [🔥 Check a rule](#-critical-rules) → Zero-tolerance violations
- [🚨 Fix an issue](#-emergency-procedures) → Troubleshoot broken services
- [📚 Learn more](#-deep-dives) → Complete documentation

---

## ⚡ 5-Minute Setup

### Step 1: Python 3.11.9 (REQUIRED)

```bash
# Install Python 3.11.9 (recommended for stability)
pyenv install 3.11.9
pyenv local 3.11.9

# Create virtual environment
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate

# Verify
python --version  # Should show: Python 3.11.9
```

**Why 3.11.9?** Stable with all data science packages, fewer issues than 3.13

### Step 2: Install Dependencies

**macOS (Apple Silicon/Intel):**
```bash
source venv/bin/activate
pip install -r requirements/base-macos.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
```

**Linux with CUDA GPU:**
```bash
pip install -r requirements/base-linux.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
```

### Step 3: Verify Installation

```bash
python manage.py check              # Should show "0 errors"
python manage.py migrate            # Setup database
python manage.py runserver          # Start server → http://localhost:8000
```

✅ **Success:** Browser shows Django welcome page

→ **Detailed setup:** Run into issues? See troubleshooting in [Emergency Procedures](#-emergency-procedures)

---

## 📋 Daily Commands

### Development Workflow

| Task | Command | When to Use |
|------|---------|-------------|
| **Start dev server** | `python manage.py runserver` | Local development (HTTP only) |
| **Start with WebSockets** | `daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application` | Real-time features needed |
| **Run all tests** | `pytest --cov=apps --cov-report=html --tb=short -v` | Pre-commit, full coverage |
| **Run unit tests only** | `pytest -m unit` | Fast feedback (<10s) |
| **Create migrations** | `python manage.py makemigrations` | After model changes |
| **Apply migrations** | `python manage.py migrate` | Deploy migrations |
| **Initialize system** | `python manage.py init_intelliwiz default` | Fresh database setup |

### Celery Operations

| Task | Command | When to Use |
|------|---------|-------------|
| **Start all workers** | `./scripts/celery_workers.sh start` | Background task processing |
| **Monitor workers** | `./scripts/celery_workers.sh monitor` | Real-time task dashboard |
| **Validate schedules** | `python manage.py validate_schedules --verbose` | Beat schedule errors |
| **Check duplicates** | `python manage.py validate_schedules --check-duplicates` | Multiple tasks same time |
| **Find orphaned tasks** | `python manage.py validate_schedules --check-orphaned-tasks` | Task not registered |
| **Audit tasks** | `python scripts/audit_celery_tasks.py --generate-report` | Duplicate detection |

### Code Quality

| Task | Command | When to Use |
|------|---------|-------------|
| **Validate all rules** | `python scripts/validate_code_quality.py --verbose` | Pre-commit, pre-PR |
| **Check for print()** | `flake8 apps/` | Find T001 violations |
| **Find unused code** | `python scripts/detect_unused_code.py --verbose` | Code cleanup |
| **Detect code smells** | `python scripts/detect_code_smells.py --report` | Quality audit |

→ **Full command catalog:** See complete reference with all flags and options (coming in specialized docs)

---

## 🔥 Critical Rules

**Before ANY code changes, verify against these zero-tolerance violations:**

| # | Violation | Forbidden Pattern | Required Pattern |
|---|-----------|-------------------|------------------|
| **1** | SQL injection bypass | Hardcoded `/graphql/` paths | Import from config |
| **2** | Bare except blocks | `except:` or `except Exception:` | Use `DATABASE_EXCEPTIONS`, `NETWORK_EXCEPTIONS` |
| **3** | Print statements | `print("debug")` in production | Use `logger.info()` or `logger.debug()` |
| **4** | Missing timeouts | `requests.get(url)` | `requests.get(url, timeout=(5, 15))` |
| **5** | CSRF bypass | `@csrf_exempt` without docs | Document alternative protection |
| **6** | Unsafe file upload | Direct `file.save()` | Use `perform_secure_uploadattachment()` |
| **7** | Hardcoded secrets | Credentials in code | Validate on settings load (fail-fast) |
| **8** | Blocking I/O | `time.sleep()` in views | Use `with_retry()` decorator |

**Enforcement:** Pre-commit hooks + flake8 + CI/CD pipeline = Automated PR rejection

### Architecture Limits (MANDATORY)

| Component | Max Size | Reason | Enforcement |
|-----------|----------|--------|-------------|
| Settings files | 200 lines | Split by concern | Lint check |
| Model classes | 150 lines | Single responsibility | Lint check |
| View methods | 30 lines | Delegate to services | Complexity check |
| Form classes | 100 lines | Focused validation | Lint check |
| Utility functions | 50 lines | Atomic operations | Complexity check |

→ **All 15 rules with examples:** See complete patterns and fixes (coming in docs/RULES.md)

---

## 🚨 Emergency Procedures

### System Down

**Symptom:** Server won't start, errors on page load

```bash
# 1. Check Django
python manage.py check

# 2. Check services
redis-cli ping                           # Should return "PONG"
psql -U postgres -c "SELECT 1"           # Test database

# 3. Restart services
./scripts/celery_workers.sh restart
python manage.py runserver

# 4. Check logs
tail -f logs/intelliwiz.log
```

### Celery Beat Scheduler Broken

**Symptom:** Scheduled tasks not running, beat errors in logs

```bash
# Diagnose
python manage.py validate_schedules --check-orphaned-tasks --verbose

# Common issues:
# "Task 'X' in schedule but not registered" → Register task or remove from schedule
# "Duplicate tasks at same time" → Stagger schedules or enable idempotency

# Fix duplicate task definitions
python scripts/audit_celery_tasks.py --duplicates-only
```

### Security Alert

**Symptom:** NOC dashboard shows RED status, email alerts

```bash
# Run security scorecard
python manage.py shell
>>> from background_tasks.non_negotiables_tasks import evaluate_non_negotiables
>>> evaluate_non_negotiables.delay()

# View dashboard
open http://localhost:8000/helpbot/security_scorecard/
```

### Redis Cache Issues

**Symptom:** Slow performance, cache errors in logs

```bash
# Verify configuration
python scripts/verify_redis_cache_config.py

# Check TLS certificates (expires soon?)
python manage.py check_redis_certificates --alert-days 30

# Monitor performance
open http://localhost:8000/admin/redis/dashboard/
```

### Tests Failing

**Symptom:** `pytest` shows failures

```bash
# Run specific test category
pytest -m unit              # Fast unit tests
pytest -m integration       # Integration tests
pytest -m security          # Security tests

# Run with verbose output
pytest apps/path/to/test.py -v --tb=short

# Check for race conditions
pytest -k "race" -v
```

---

## 📚 Deep Dives

For comprehensive documentation, see specialized guides:

### Architecture & Design
**Coming:** `docs/ARCHITECTURE.md`
- System profile (Django 5.2.1, PostgreSQL 14.2 + PostGIS, REST APIs)
- Business domains (Operations, Assets, People, Security, Help Desk, Reports)
- Multi-tenant architecture patterns
- Security architecture (multi-layer middleware)
- API design (REST, type-safe contracts, Pydantic validation)
- Design decisions log (why REST over GraphQL, etc.)

### Background Processing
**Coming:** `docs/CELERY.md`
- Complete Celery configuration guide
- Task decorator standards (@shared_task vs @app.task)
- Queue routing strategies (6 priority queues)
- Idempotency framework (prevent duplicate execution)
- Schedule management and validation
- Troubleshooting flowcharts

### Configuration & Commands
**Coming:** `docs/REFERENCE.md`
- Complete command catalog (by domain + use case)
- Environment variables reference
- Database configuration (PostgreSQL, PostGIS)
- Redis cache strategies
- Testing strategies (unit, integration, security, race condition)
- Code quality tools (flake8, pytest, validation scripts)
- API contracts (OpenAPI schema, Pydantic models)

### Mandatory Patterns
**Coming:** `docs/RULES.md`
- All 15 zero-tolerance rules with code examples
- Architecture limits enforcement
- Exception handling patterns
- DateTime standards (Python 3.12+ compatible)
- Network call requirements
- File operation security
- Pre-commit checklist

---

## 📊 Quick Stats

- **Framework:** Django 5.2.1 | Python 3.11.9
- **Database:** PostgreSQL 14.2 + PostGIS
- **API:** REST (GraphQL removed Oct 2025)
- **Task Queue:** Celery with 6 priority queues
- **Testing:** pytest with 80%+ coverage target
- **Security:** Multi-layer middleware, PCI DSS Level 1 (Redis TLS)

---

## 🔍 Find More

### Documentation
- **This file:** Core reference for daily tasks
- **Design document:** `docs/plans/2025-10-29-claude-md-optimization-design.md`
- **Implementation roadmap:** `IMPLEMENTATION_ROADMAP.md`
- **Archive:** `docs/archive/` (historical content)

### Key Files
- **Settings:** `intelliwiz_config/settings/` (base, development, production)
- **URLs:** `intelliwiz_config/urls_optimized.py` (domain-driven structure)
- **User model:** `apps/peoples/models/` (split architecture)
- **Celery config:** `intelliwiz_config/celery.py` (single source of truth)

### Support
- **Security issues:** Contact security team immediately
- **Documentation feedback:** `docs/plans/` or team discussion
- **Help:** `/help` command or `https://github.com/anthropics/claude-code/issues`

---

**Last Updated:** 2025-10-29
**Maintainer:** Development Team
**Review Cycle:** Weekly (high-traffic content)

---

## Recent Changes

### October 29, 2025
- ✅ REST API migration complete (GraphQL removed)
- ✅ Documentation optimization (this streamlined version)
- ✅ Archive structure created for historical content
- ✅ Command reference consolidated into single table

### October 2025
- schedhuler → scheduler app rename (719 occurrences)
- Select2 PostgreSQL migration (Redis → materialized views)
- Celery task refactoring (eliminated 29 duplicates)
- Code smell detection system implemented

### September 2025
- DateTime refactoring (Python 3.12+ compatible)
- God file elimination (reports, onboarding, services)
- Custom user model split (3 focused models)
- Exception handling refactoring (bare except → specific types)

---

*For complete implementation details and historical context, see archived documentation in `docs/archive/`*
