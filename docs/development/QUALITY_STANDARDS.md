# Quality Standards & Enforcement

> **Last Updated**: November 4, 2025  
> **Status**: Active - Enforced via Pre-commit Hooks & CI/CD Pipeline  
> **Authority**: `.claude/rules.md` - Zero-tolerance violations

---

## Table of Contents

- [Overview](#overview)
- [Architecture Limits](#architecture-limits)
- [Code Quality Metrics](#code-quality-metrics)
- [Enforcement Mechanisms](#enforcement-mechanisms)
- [Validation Scripts](#validation-scripts)
- [CI/CD Pipeline](#cicd-pipeline)
- [Pre-commit Hooks](#pre-commit-hooks)
- [Remediation Guide](#remediation-guide)

---

## Overview

This document defines the **automated quality enforcement** standards for the Django 5.2.1 enterprise facility management platform. All standards are derived from `.claude/rules.md` and are enforced through:

1. **Pre-commit hooks** - Block violations before commits
2. **CI/CD pipeline** - Fail builds on violations
3. **Validation scripts** - Manual and automated checks

**Philosophy**: Quality is not optional. Automated gates prevent technical debt from entering the codebase.

---

## Architecture Limits

### File Size Limits

These limits enforce **single responsibility principle** and prevent "god files":

| File Type | Max Lines | Severity if Exceeded | Rationale |
|-----------|-----------|---------------------|-----------|
| **Settings** | 200 | CRITICAL | Split by environment (base, dev, prod) |
| **Models** | 150 | CRITICAL | One model per file or use models/ directory |
| **View Methods** | 30 | HIGH | Delegate to services, keep views thin |
| **Forms** | 100 | HIGH | Split complex forms into composable pieces |
| **Utilities** | 50/function | MEDIUM | Atomic, testable functions |

**Validation**: `scripts/check_file_sizes.py`

### Cyclomatic Complexity

**Max Complexity per Method**: 10

Complexity is measured by counting decision points:
- `if`, `elif`, `else`
- `for`, `while`
- `try`, `except`, `finally`
- Boolean operators (`and`, `or`)

**Rationale**:
- Methods with complexity > 10 are hard to test
- Indicates poor separation of concerns
- Makes debugging difficult

**Validation**: Radon CC, Xenon, Pre-commit hooks

### Method Line Count

**Max Lines per Method**: 30

**Rationale**:
- Should fit on one screen
- Forces proper decomposition
- Improves testability

**Validation**: Pre-commit hooks (architecture-rules-validation)

---

## Code Quality Metrics

### Test Coverage

**Minimum Coverage**: 75%

**Measured by**: pytest-cov

**Enforcement**: CI/CD pipeline fails if coverage < 75%

**How to Check**:
```bash
pytest --cov=apps --cov-report=term --cov-report=html:coverage_reports/html
```

### Maintainability Index (Radon MI)

**Target Range**: B or better (65-100)

**Grades**:
- A (85-100): Excellent
- B (65-84): Good
- C (50-64): Needs improvement
- D (25-49): Poor
- F (0-24): Critical

**How to Check**:
```bash
radon mi apps/ -s -n B
```

### Security Scanning

**Tools**:
- **Bandit**: Python security linting
- **Safety**: Dependency vulnerability checking
- **Semgrep**: Security-focused static analysis
- **Gitleaks**: Secret scanning

**All must pass** before merging to main/develop.

---

## Enforcement Mechanisms

### 1. Pre-commit Hooks

**Location**: `.pre-commit-config.yaml`

**Automatic Checks**:
- File size limits
- Cyclomatic complexity (< 10)
- Network timeout validation
- Circular dependency detection
- Logging security (no passwords/tokens in logs)
- Query optimization (N+1 detection)
- Encryption validation
- Import organization
- Django checks (migrations, system checks)
- Celery beat task validation

**How to Install**:
```bash
pip install pre-commit
pre-commit install
```

**Manual Run**:
```bash
# All files
pre-commit run --all-files

# Specific hook
pre-commit run file-size-validation --all-files
```

### 2. CI/CD Pipeline

**Location**: `.github/workflows/code-quality.yml`

**Jobs**:
1. **Security Scan**: Bandit, Safety, Semgrep, Pip-Audit
2. **Architecture Validation**: File sizes, complexity (Radon, Xenon)
3. **Test Coverage**: pytest with 75% threshold
4. **Pattern Enforcement**: Forbidden patterns detection
5. **Quality Report**: Aggregated report posted to PRs

**Triggers**:
- Push to main/develop
- Pull requests to main/develop

**Failure Conditions**:
- Critical security patterns detected
- Architecture rules violated
- Test coverage < 75%

### 3. Validation Scripts

Located in `scripts/`:

| Script | Purpose | Usage |
|--------|---------|-------|
| `check_file_sizes.py` | Validate file size limits | `python scripts/check_file_sizes.py --verbose` |
| `check_network_timeouts.py` | Ensure all network calls have timeouts | `python scripts/check_network_timeouts.py --ci` |
| `check_circular_deps.py` | Detect circular imports | `python scripts/check_circular_deps.py --verbose` |
| `validate_code_quality.py` | Comprehensive quality validation | `python scripts/validate_code_quality.py --report report.md` |

**All scripts support**:
- `--verbose`: Detailed output
- `--ci`: CI-friendly format
- `--pre-commit`: Fast validation for hooks

---

## Validation Scripts

### check_file_sizes.py

**Purpose**: Validate all files meet architecture size limits

**Usage**:
```bash
# Basic check
python scripts/check_file_sizes.py

# Verbose with details
python scripts/check_file_sizes.py --verbose

# CI mode (strict)
python scripts/check_file_sizes.py --ci

# Pre-commit mode (fast)
python scripts/check_file_sizes.py --pre-commit
```

**Checks**:
- Settings files < 200 lines
- Model files < 150 lines
- Form files < 100 lines
- View files (flags if > 500 lines)
- Utility files (flags if > 300 lines)

**Output**:
```
==================================================================
FILE SIZE VALIDATION
==================================================================
✅ Checking settings files...
✅ PASS: base.py (187 lines)
✅ PASS: dev.py (45 lines)
❌ VIOLATION: apps/core/models.py: models has 245 lines (max: 150) [critical]
==================================================================
FAILED: 1 file size violations found
==================================================================
```

### check_network_timeouts.py

**Purpose**: Ensure all network calls include timeout parameters

**Critical Rule**: Missing timeouts can cause workers to hang indefinitely.

**Usage**:
```bash
python scripts/check_network_timeouts.py --verbose
```

**Checks**:
- `requests.get()`, `requests.post()`, etc.
- `httpx` calls
- `urllib` calls

**Timeout Guidelines** (from CLAUDE.md):
- API/metadata: `timeout=(5, 15)` - 5s connect, 15s read
- File downloads: `timeout=(5, 30)`
- Long operations: `timeout=(5, 60)`

**Example Fix**:
```python
# ❌ WRONG
response = requests.get(url)

# ✅ CORRECT
response = requests.get(url, timeout=(5, 15))
```

### check_circular_deps.py

**Purpose**: Detect circular imports that cause initialization issues

**Usage**:
```bash
# Basic detection
python scripts/check_circular_deps.py

# With graph generation (requires pydeps)
python scripts/check_circular_deps.py --graph deps.svg
```

**Severity Levels**:
- **Critical**: Cycles ≤ 3 modules
- **Warning**: Cycles 4-5 modules
- **Info**: Cycles > 5 modules

**Remediation**:
1. Use dependency injection
2. Extract shared code into separate modules
3. Move imports inside functions (lazy imports)
4. Refactor architecture to reduce coupling

---

## CI/CD Pipeline

### Pipeline Structure

**Location**: `.github/workflows/code-quality.yml`

**Jobs**:

#### 1. Security Scan
- Bandit (Python security)
- Safety (dependency vulnerabilities)
- Pip-Audit (supply chain security)
- Semgrep (security rules)
- **Artifacts**: JSON reports

#### 2. Architecture Validation
- File size limits (all categories)
- Cyclomatic complexity (Radon CC)
- Maintainability index (Radon MI)
- Complexity thresholds (Xenon)
- Network timeout validation
- Circular dependency detection
- **Artifacts**: radon-complexity.json, radon-maintainability.json

#### 3. Test Coverage
- Run pytest with coverage
- Check 75% threshold
- Generate HTML reports
- **Artifacts**: coverage_reports/, coverage.json

#### 4. Pattern Enforcement
- Generic exception handling (`except Exception`)
- CSRF exempt on API endpoints without alternative protection
- Sensitive data in logs
- **Failure Mode**: Hard fail on any critical pattern

#### 5. Quality Report
- Aggregate all results
- Generate markdown report
- Post comment on PRs
- **Artifacts**: quality-report.md

#### 6. Pipeline Status
- Overall pass/fail determination
- Exit with error if critical violations found

### Pipeline Behavior

**On Success**:
```
✅ PIPELINE PASSED: All quality checks successful!
🎉 Code meets all quality and security standards
```

**On Failure**:
```
💥 PIPELINE FAILED: Critical security patterns detected!
🚨 Code contains patterns that WILL cause vulnerabilities
📖 Review .claude/rules.md for required fixes
```

---

## Pre-commit Hooks

### Hook Categories

#### 1. AI Mentor System Hooks (Legacy - being phased out)
- mentor-guard-validation
- mentor-security-scan
- mentor-quality-check
- mentor-secret-scan
- gitleaks-protect

#### 2. Architecture & Compliance Hooks
- **settings-line-count-compliance**: Settings < 200 lines
- **architecture-rules-validation**: Method < 30 lines
- **file-size-validation**: Comprehensive file size checks
- **cyclomatic-complexity-check**: Complexity < 10

#### 3. Security Hooks
- **logging-security-validation**: No passwords/tokens in logs
- **secure-encryption-validation**: No insecure zlib patterns
- **network-timeout-validation**: All network calls have timeouts

#### 4. Code Quality Hooks
- **query-optimization-validation**: N+1 detection
- **circular-dependency-check**: Import cycle detection

#### 5. Import Organization Hooks
- **import-validation**: Standalone import analyzer
- **import-style-check**: Style consistency
- **unused-imports-check**: Detect unused imports

#### 6. Django-Specific Hooks
- **django-check**: `python manage.py check`
- **django-makemigrations-check**: Detect missing migrations
- **celery-beat-task-validation**: Orphaned task detection

#### 7. Standard Python Hooks
- Black (formatting)
- isort (import sorting)
- flake8 (linting with E722 for generic exceptions)
- Bandit (security)
- detect-secrets (secret scanning)

### Hook Bypass (NOT RECOMMENDED)

```bash
# Skip hooks (ONLY for emergencies)
git commit --no-verify -m "Emergency fix"

# Better: Fix the violations
python scripts/check_file_sizes.py --verbose
# Address issues, then commit normally
```

---

## Remediation Guide

### File Size Violations

**Problem**: File exceeds size limits

**Solutions**:

1. **Settings Files** (>200 lines):
   ```python
   # Split into: base.py, dev.py, prod.py, test.py
   intelliwiz_config/settings/
   ├── __init__.py
   ├── base.py          # Common settings
   ├── dev.py           # Development overrides
   ├── prod.py          # Production settings
   └── test.py          # Test settings
   ```

2. **Model Files** (>150 lines):
   ```python
   # Convert models.py to models/ directory
   apps/myapp/models/
   ├── __init__.py      # Import all models
   ├── user.py          # User model
   ├── profile.py       # Profile model
   └── organization.py  # Organization model
   ```

3. **View Methods** (>30 lines):
   ```python
   # Delegate to services
   class MyView(APIView):
       def post(self, request):
           # ❌ Don't: All logic here (50 lines)
           
           # ✅ Do: Delegate to service
           service = MyService()
           result = service.process(request.data)
           return Response(result)
   ```

### Cyclomatic Complexity

**Problem**: Method complexity > 10

**Solutions**:

1. **Extract Methods**:
   ```python
   # ❌ Complex method
   def process_order(order):
       if order.status == 'pending':
           if order.payment_method == 'card':
               if order.amount > 1000:
                   # ... 20 more lines
   
   # ✅ Refactored
   def process_order(order):
       if not is_processable(order):
           return
       
       payment_handler = get_payment_handler(order)
       return payment_handler.process()
   ```

2. **Use Polymorphism**:
   ```python
   # ❌ Long if-elif chain
   if payment_type == 'card':
       # ... logic
   elif payment_type == 'paypal':
       # ... logic
   elif payment_type == 'bank':
       # ... logic
   
   # ✅ Strategy pattern
   handlers = {
       'card': CardPaymentHandler,
       'paypal': PayPalHandler,
       'bank': BankTransferHandler,
   }
   handler = handlers[payment_type]()
   handler.process()
   ```

3. **Guard Clauses** (early returns):
   ```python
   # ❌ Nested ifs
   def process(data):
       if data.is_valid:
           if data.user.is_active:
               if data.amount > 0:
                   # ... main logic
   
   # ✅ Guard clauses
   def process(data):
       if not data.is_valid:
           return error("Invalid data")
       if not data.user.is_active:
           return error("Inactive user")
       if data.amount <= 0:
           return error("Invalid amount")
       
       # Main logic at top level
   ```

### Network Timeout Violations

**Problem**: Network call without timeout

**Solution**:
```python
# ❌ Missing timeout
response = requests.get(api_url)
response = requests.post(webhook_url, json=data)

# ✅ With timeout
response = requests.get(api_url, timeout=(5, 15))
response = requests.post(webhook_url, json=data, timeout=(5, 30))
```

**Guidelines**:
- Connect timeout: 5 seconds (fast fail on connection issues)
- Read timeout: 15-60 seconds depending on operation
- Always use tuple: `(connect_timeout, read_timeout)`

### Circular Dependencies

**Problem**: Module A imports B, B imports A

**Solutions**:

1. **Dependency Injection**:
   ```python
   # ❌ Circular import
   # module_a.py
   from module_b import ServiceB
   
   # module_b.py
   from module_a import ServiceA
   
   # ✅ Inject dependencies
   # module_a.py
   class ServiceA:
       def __init__(self, service_b):
           self.service_b = service_b
   
   # module_b.py (no import of module_a)
   class ServiceB:
       pass
   ```

2. **Extract Shared Code**:
   ```python
   # Create shared.py for common utilities
   # module_a.py and module_b.py both import from shared.py
   ```

3. **Lazy Imports**:
   ```python
   # Import inside function instead of module level
   def my_function():
       from module_b import ServiceB  # Only imported when needed
       service = ServiceB()
   ```

---

## Tool Installation

### Install All Quality Tools

```bash
# In project virtual environment
pip install radon xenon pydeps bandit safety
pip install pytest pytest-cov pytest-django coverage
pip install pre-commit

# Install pre-commit hooks
pre-commit install
```

### Verify Installation

```bash
# Check tools
radon --version
xenon --version
bandit --version
safety --version

# Check pre-commit
pre-commit --version
pre-commit run --all-files  # Dry run
```

---

## Quick Reference

### Daily Workflow

```bash
# 1. Before committing
pre-commit run --all-files

# 2. If violations found
python scripts/check_file_sizes.py --verbose
python scripts/check_network_timeouts.py --verbose
python scripts/check_circular_deps.py --verbose

# 3. Fix violations
# ... make changes ...

# 4. Re-run checks
pre-commit run --all-files

# 5. Commit
git add .
git commit -m "feat: implement feature with quality compliance"
```

### Common Commands

```bash
# File sizes
python scripts/check_file_sizes.py --verbose

# Network timeouts
python scripts/check_network_timeouts.py --ci

# Circular dependencies
python scripts/check_circular_deps.py --verbose

# Complexity analysis
radon cc apps/ -a -s -n C
radon mi apps/ -s -n B
xenon --max-absolute C --max-modules B --max-average A apps/

# Test coverage
pytest --cov=apps --cov-report=term --cov-report=html:coverage_reports/html

# Full validation
python scripts/validate_code_quality.py --verbose --report quality_report.md
```

---

## Support & Resources

### Documentation
- **Architecture Rules**: `.claude/rules.md` (MANDATORY reading)
- **System Architecture**: `docs/architecture/SYSTEM_ARCHITECTURE.md`
- **Testing Guide**: `docs/testing/TESTING_AND_QUALITY_GUIDE.md`
- **Common Issues**: `docs/troubleshooting/COMMON_ISSUES.md`

### Key Principles
1. **Quality is not optional** - Automated gates enforce standards
2. **Fail fast** - Pre-commit hooks catch issues early
3. **Continuous improvement** - Metrics track progress
4. **Zero tolerance** - Critical violations block merges

### Getting Help
- Review validation script output (includes remediation hints)
- Check `docs/` for patterns and examples
- Run scripts with `--verbose` for detailed diagnostics

---

**Version**: 1.0  
**Effective Date**: November 4, 2025  
**Next Review**: February 1, 2026  
**Maintainer**: Quality Gates Engineer / Development Team
