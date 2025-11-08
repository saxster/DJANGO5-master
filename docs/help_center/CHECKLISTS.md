# Development Checklists

**Purpose:** Quick-reference checklists for common development tasks

**Last Updated:** November 6, 2025

---

## 📋 Table of Contents

1. [Pre-Commit Checklist](#pre-commit-checklist)
2. [Code Review Checklist](#code-review-checklist)
3. [Security Review Checklist](#security-review-checklist)
4. [Performance Review Checklist](#performance-review-checklist)
5. [Refactoring Checklist](#refactoring-checklist)
6. [Pre-Deployment Checklist](#pre-deployment-checklist)

---

## Pre-Commit Checklist

**Use before every `git commit`**

### Code Quality

- [ ] **File size limits respected**
  - Settings files: < 200 lines
  - Model classes: < 150 lines
  - View methods: < 30 lines
  - Form classes: < 100 lines
  - Functions: < 50 lines

- [ ] **No deep nesting**
  - Max 3 levels of conditionals/loops
  - Complex logic extracted to helper functions

- [ ] **No magic numbers**
  - All numbers have descriptive constant names
  - Constants defined in `apps/core/constants/`

- [ ] **Clean imports**
  - No wildcard imports (except settings)
  - Imports organized: stdlib → third-party → local
  - Unused imports removed

### Exception Handling

- [ ] **No bare `except:` clauses**
- [ ] **No generic `except Exception:` without re-raising**
- [ ] **Specific exception types from `apps/core/exceptions/patterns.py`**
- [ ] **Structured logging with context**

### Security

- [ ] **No `@csrf_exempt` without alternative authentication**
- [ ] **File downloads use `SecureFileDownloadService`**
- [ ] **Database queries filter by tenant first**
- [ ] **User input validated and sanitized**
- [ ] **No secrets in code (use environment variables)**
- [ ] **Network calls include timeout parameters**

### Performance

- [ ] **ForeignKey access uses `select_related()`**
- [ ] **ManyToMany access uses `prefetch_related()`**
- [ ] **No queries in loops**
- [ ] **Large querysets paginated**

### Testing

- [ ] **New code has tests (min 80% coverage)**
- [ ] **Tests pass: `pytest -v`**
- [ ] **Security tests for sensitive endpoints**
- [ ] **Query count assertions for list views**

### Commands to Run

```bash
# 1. Code quality validation
python scripts/validate_code_quality.py --verbose

# 2. File size check
python scripts/check_file_sizes.py --verbose

# 3. God file detection
python scripts/detect_god_files.py --path apps/

# 4. Run tests
python -m pytest --cov=apps --cov-report=html -v

# 5. Django checks
python manage.py check

# 6. Pre-commit hooks (auto-runs on commit)
pre-commit run --all-files
```

---

## Code Review Checklist

**Use when reviewing pull requests**

### Architecture

- [ ] **Business logic in service layer, not views**
- [ ] **Views are < 30 lines (routing only)**
- [ ] **Services independent of HTTP request object**
- [ ] **No circular dependencies**
- [ ] **Models follow Single Responsibility Principle**

### Code Quality

- [ ] **Code follows existing patterns in codebase**
- [ ] **Variable/function names are descriptive**
- [ ] **No code duplication (DRY principle)**
- [ ] **Complex logic has explanatory comments**
- [ ] **Error messages are user-friendly**

### Database

- [ ] **Migrations included for model changes**
- [ ] **Queries optimized (select_related/prefetch_related)**
- [ ] **No N+1 queries introduced**
- [ ] **Database indexes added for filtered fields**
- [ ] **Model Meta classes complete**

### Security

- [ ] **Authentication required for sensitive endpoints**
- [ ] **Authorization checks before data access**
- [ ] **IDOR vulnerabilities prevented**
- [ ] **CSRF protection enabled**
- [ ] **SQL injection prevented (using ORM)**
- [ ] **XSS prevented (template auto-escaping)**

### Testing

- [ ] **Tests cover new functionality**
- [ ] **Tests cover edge cases**
- [ ] **Security tests for sensitive operations**
- [ ] **Test names clearly describe what they test**
- [ ] **All tests pass in CI/CD**

### Documentation

- [ ] **README updated if public API changed**
- [ ] **Docstrings added for public methods**
- [ ] **CHANGELOG.md updated**
- [ ] **Migration notes in PR description**

### Review Questions to Ask

- **Is this code maintainable?** Will someone understand it in 6 months?
- **Is this code testable?** Can it be tested without complex mocking?
- **Is this code secure?** Does it handle untrusted input safely?
- **Is this code performant?** Will it scale with more data?
- **Is this code reusable?** Can other parts of the system use it?

---

## Security Review Checklist

**Use for security-sensitive changes (auth, files, payments, etc.)**

### Authentication

- [ ] **All endpoints require authentication (no `@csrf_exempt` without reason)**
- [ ] **Tokens in Authorization header, not URL params**
- [ ] **Token rotation mechanism implemented**
- [ ] **Failed auth attempts logged and rate-limited**
- [ ] **Session timeout configured**

### Authorization

- [ ] **Ownership validated before file access**
- [ ] **Tenant isolation enforced in queries**
- [ ] **Permission checks before sensitive operations**
- [ ] **IDOR tests written and passing**
- [ ] **Cross-tenant access tests written**

### Input Validation

- [ ] **All user input validated with forms/serializers**
- [ ] **File uploads validated (type, size, content)**
- [ ] **Path traversal prevention for file operations**
- [ ] **SQL injection impossible (using ORM)**
- [ ] **XSS prevented (no `|safe` without sanitization)**

### Sensitive Data

- [ ] **Passwords hashed (never plaintext)**
- [ ] **Sensitive fields excluded from serializers**
- [ ] **PII not logged**
- [ ] **Secrets not in code (use env vars)**
- [ ] **HTTPS enforced in production**

### Rate Limiting

- [ ] **Login endpoints rate-limited**
- [ ] **API endpoints rate-limited**
- [ ] **Password reset rate-limited**
- [ ] **File upload rate-limited**

### Audit Logging

- [ ] **Authentication failures logged**
- [ ] **File access logged**
- [ ] **Permission denials logged**
- [ ] **Sensitive operations logged (with correlation ID)**

### Security Tests

- [ ] **IDOR tests written**
- [ ] **Authentication tests written**
- [ ] **Authorization tests written**
- [ ] **Path traversal tests written**
- [ ] **Rate limiting tests written**

### Tools to Run

```bash
# 1. Security test suite
python -m pytest tests/security/ -v

# 2. IDOR tests
python -m pytest tests/security/test_idor.py -v

# 3. Verify secure file download
python verify_secure_file_download.py

# 4. Check for secrets in code
git secrets --scan
```

---

## Performance Review Checklist

**Use when performance is critical (reports, APIs, dashboards)**

### Database Queries

- [ ] **Query count measured and acceptable**
- [ ] **No N+1 queries (verified with Django Debug Toolbar)**
- [ ] **select_related() used for ForeignKey**
- [ ] **prefetch_related() used for ManyToMany/reverse FK**
- [ ] **Indexes added for filtered/sorted fields**
- [ ] **Aggregation done in database, not Python**
- [ ] **Large querysets paginated**
- [ ] **Unused fields excluded with .only()/.values()**

### Caching

- [ ] **Expensive queries cached**
- [ ] **Cache invalidation strategy defined**
- [ ] **Cache keys namespaced by tenant**
- [ ] **Cache timeout appropriate for data**

### Background Processing

- [ ] **Long operations moved to Celery**
- [ ] **No blocking I/O in request path**
- [ ] **Retry mechanism for transient failures**
- [ ] **Circuit breaker for external services**

### Frontend

- [ ] **Large datasets paginated**
- [ ] **Heavy assets lazy-loaded**
- [ ] **Static files cached with far-future expires**
- [ ] **Database queries not in templates**

### Performance Tests

- [ ] **Query count assertions in tests**
- [ ] **Load tests for high-traffic endpoints**
- [ ] **Performance baseline measured**
- [ ] **No performance regression vs baseline**

### Tools to Run

```bash
# 1. Query optimization validation
python validate_n1_optimization.py

# 2. Performance baseline
python phase1_performance_verification.py

# 3. Query count for endpoint
# Add ?debug=1 to URL with Django Debug Toolbar

# 4. Load testing
locust -f tests/load/locustfile.py
```

---

## Refactoring Checklist

**Use when splitting god files or refactoring large modules**

### Before Refactoring

- [ ] **Read [Refactoring Playbook](../architecture/REFACTORING_PLAYBOOK.md)**
- [ ] **Identify refactoring pattern (by domain, by type, by feature)**
- [ ] **Write tests for existing behavior (if missing)**
- [ ] **Verify all tests pass**
- [ ] **Document current file size and complexity**

### During Refactoring

- [ ] **Create new module structure**
- [ ] **Move code incrementally (one file at a time)**
- [ ] **Update imports in moved files**
- [ ] **Update imports in files that import moved code**
- [ ] **Run tests after each move**
- [ ] **Verify no circular dependencies introduced**

### After Refactoring

- [ ] **All tests still pass**
- [ ] **No new linting errors**
- [ ] **File sizes under limits**
- [ ] **No god files remain**
- [ ] **Django check passes**
- [ ] **Migrations generated if needed**
- [ ] **Documentation updated**
- [ ] **Backward compatibility maintained**

### Verification Commands

```bash
# 1. Verify model refactoring
python scripts/verify_attendance_models_refactoring.py

# 2. Check file sizes
python scripts/check_file_sizes.py --verbose

# 3. Detect remaining god files
python scripts/detect_god_files.py --path apps/

# 4. Validate imports
python manage.py check

# 5. Run full test suite
python -m pytest --cov=apps -v

# 6. Check for circular dependencies
python scripts/check_circular_dependencies.py
```

---

## Pre-Deployment Checklist

**Use before deploying to production**

### Code Quality

- [ ] **All tests pass in CI/CD**
- [ ] **No god files (verified with detection script)**
- [ ] **Code quality gates pass**
- [ ] **No failing pre-commit hooks**
- [ ] **All linting errors resolved**

### Database

- [ ] **Migrations reviewed and tested**
- [ ] **Migrations tested on production-like data**
- [ ] **Rollback plan documented**
- [ ] **Database backup scheduled**
- [ ] **Indexes added for new queries**

### Security

- [ ] **Security tests pass**
- [ ] **Secrets in environment variables (not code)**
- [ ] **HTTPS enforced**
- [ ] **CSRF protection enabled**
- [ ] **Rate limiting configured**
- [ ] **Security headers configured**

### Performance

- [ ] **Performance tests pass**
- [ ] **No performance regression vs baseline**
- [ ] **Caching configured**
- [ ] **CDN configured for static files**
- [ ] **Database connection pooling enabled**

### Monitoring

- [ ] **Error tracking configured (Sentry)**
- [ ] **Logging configured**
- [ ] **Metrics collection enabled**
- [ ] **Alerts configured for critical errors**
- [ ] **Health check endpoint working**

### Documentation

- [ ] **CHANGELOG.md updated**
- [ ] **Deployment notes written**
- [ ] **Rollback procedure documented**
- [ ] **Team notified of deployment**

### Final Commands

```bash
# 1. Full test suite
python -m pytest --cov=apps --cov-report=html -v

# 2. Validate code quality
python scripts/validate_code_quality.py --verbose

# 3. Check migrations
python manage.py makemigrations --check --dry-run

# 4. Django system check
python manage.py check --deploy

# 5. Collect static files
python manage.py collectstatic --noinput

# 6. Verify deployment checklist
python apps/help_center/verify_deployment.py
```

---

## Quick Reference: Command Summary

| Task | Command |
|------|---------|
| **Run tests** | `pytest --cov=apps -v` |
| **Code quality** | `python scripts/validate_code_quality.py --verbose` |
| **File sizes** | `python scripts/check_file_sizes.py --verbose` |
| **God files** | `python scripts/detect_god_files.py --path apps/` |
| **Django check** | `python manage.py check` |
| **Security tests** | `pytest tests/security/ -v` |
| **Pre-commit** | `pre-commit run --all-files` |
| **Migrations** | `python manage.py makemigrations` |
| **Performance** | `python validate_n1_optimization.py` |

---

## Checklist Templates

### For Your IDE

Create snippets for common checklists:

```python
# pre-commit.md template
"""
## Pre-Commit Checklist

- [ ] Code quality: `python scripts/validate_code_quality.py --verbose`
- [ ] Tests pass: `pytest -v`
- [ ] File sizes: `python scripts/check_file_sizes.py --verbose`
- [ ] Django check: `python manage.py check`
- [ ] Pre-commit hooks: `pre-commit run --all-files`
"""
```

### For PR Templates

```markdown
## Pull Request Checklist

### Code Quality
- [ ] File size limits respected
- [ ] No deep nesting (max 3 levels)
- [ ] Exception handling uses specific types
- [ ] Tests pass with >80% coverage

### Security
- [ ] Authentication required
- [ ] Authorization validated
- [ ] IDOR tests written
- [ ] No secrets in code

### Performance
- [ ] Queries optimized (select_related/prefetch_related)
- [ ] No N+1 queries
- [ ] Query count assertions added

### Documentation
- [ ] README updated if needed
- [ ] Docstrings added
- [ ] CHANGELOG.md updated
```

---

## References

- **[.claude/rules.md](../.claude/rules.md)** - Mandatory development rules
- **[Pre-Deployment Checklist](../../MULTI_TENANCY_COMPREHENSIVE_RESOLUTION_STATUS.md)** - Complete deployment guide
- **[Testing Guide](../testing/TESTING_AND_QUALITY_GUIDE.md)** - Comprehensive testing docs
- **[Refactoring Playbook](../architecture/REFACTORING_PLAYBOOK.md)** - Refactoring patterns

---

**Questions?** Submit a Help Desk ticket with tag `best-practices-checklists`
