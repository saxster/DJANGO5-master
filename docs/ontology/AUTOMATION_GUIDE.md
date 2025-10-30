# Ontology System - Complete Automation Guide

> **Mission**: Maintain a living, self-updating business glossary extracted directly from code decorators with zero manual overhead.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Git Hook Automation](#git-hook-automation)
4. [Slash Command Usage](#slash-command-usage)
5. [MCP Server Setup](#mcp-server-setup)
6. [IDE Integration](#ide-integration)
7. [Coverage Dashboard](#coverage-dashboard)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Ontology System provides **7 layers of automation** to ensure comprehensive business term documentation with minimal developer friction:

### Automation Layers

1. **Pre-commit Hooks** - Strict enforcement (blocks commits missing decorators)
2. **Post-commit Hooks** - Auto-extraction after successful commit
3. **Slash Commands** - Claude Code integration (`/ontology`)
4. **MCP Server** - Industry-standard AI integration
5. **IDE Snippets** - 30-second decoration with VSCode/PyCharm templates
6. **Coverage Dashboard** - Real-time metrics and gap identification
7. **CI/CD Integration** - Automated validation in build pipeline

### Supported Decorator Types

- `@ontology_class` - Django models (business entities)
- `@ontology_service` - Service layer classes (business operations)
- `@ontology_api` - API views/viewsets (integrations)
- `@ontology_middleware` - Middleware components (cross-cutting concerns)

---

## Quick Start

### 1. Install Git Hooks (One-Time Setup)

```bash
# From project root
bash scripts/install-ontology-hooks.sh

# Verify installation
ls -la .git/hooks/ | grep ontology
# Should show: pre-commit and post-commit
```

### 2. Decorate Your First Class

```python
from apps.ontology.decorators import ontology_class

@ontology_class(
    business_term='Task Assignment',
    definition='Represents the assignment of a task to a security guard',
    domain='OPERATIONS',
    criticality='HIGH',
    tags=['task-management', 'guard-assignment'],
    examples=['Patrol task assigned to Guard #123 for Site A'],
    context={'assignment_type': 'patrol', 'requires_approval': True}
)
class TaskAssignment(models.Model):
    """
    Represents a task assignment in the facility management system.
    """
    pass
```

### 3. Commit and Watch Automation

```bash
git add apps/activity/models/task_assignment.py
git commit -m "feat: Add TaskAssignment model with ontology"

# Pre-commit hook validates decorator fields
# Post-commit hook auto-extracts to registry
# JSON exported to /exports/ontology/
```

---

## Git Hook Automation

### Pre-Commit Hook (Enforcement)

**Purpose**: Prevent commits of critical files without ontology decorators.

**Validation Rules**:
- Models in `**/models.py` or `**/models/*.py` must have `@ontology_class`
- Services in `**/services/*.py` must have `@ontology_service`
- API views in `**/api/*views*.py` or `**/api/*viewsets*.py` must have `@ontology_api`
- Security middleware must have `@ontology_middleware`

**Bypass (Use Sparingly)**:
```bash
# When legitimate reason exists (migrations, abstract base classes)
git commit -m "fix: migration" --no-verify
```

### Post-Commit Hook (Extraction)

**Purpose**: Automatically extract decorated terms to ontology registry.

**What It Does**:
1. Scans all `.py` files in the commit
2. Extracts decorator metadata using AST parsing
3. Updates in-memory registry
4. Exports JSON to `exports/ontology/business_terms.json`
5. Generates human-readable glossary

**Output Files**:
- `exports/ontology/business_terms.json` - Machine-readable registry
- `exports/ontology/glossary.md` - Human-readable glossary
- `exports/ontology/domains/*.json` - Per-domain exports

---

## Slash Command Usage

### `/ontology` Command (Claude Code)

**Purpose**: Add ontology decorators via natural language conversation.

**Usage**:
```bash
# In Claude Code CLI
/ontology Add decorator to TaskAssignment model in operations domain
```

**Features**:
- Conversational interface for decorator creation
- Smart field suggestions based on code context
- Validates completeness before adding
- Supports batch decoration of multiple classes

**Example Session**:
```
User: /ontology I need to decorate the User model in peoples app

Claude: I'll help you add an ontology decorator to the User model.

Let me ask a few questions:

1. What business term best describes this? (e.g., "User Account", "Employee Profile")
2. What domain does this belong to? (PEOPLE, OPERATIONS, SECURITY, etc.)
3. What's the criticality level? (CRITICAL, HIGH, MEDIUM, LOW)

User: "Security Guard Profile", PEOPLE domain, HIGH criticality

Claude: Perfect! Here's the decorator I'll add:

@ontology_class(
    business_term='Security Guard Profile',
    definition='Represents a security guard user account with authentication and profile data',
    domain='PEOPLE',
    criticality='HIGH',
    tags=['authentication', 'user-management', 'security-guard'],
    examples=['Guard #123 with access to Site A and Site B'],
    context={'requires_background_check': True}
)

Shall I proceed?
```

---

## MCP Server Setup

### What is MCP?

**Model Context Protocol (MCP)** is Anthropic's industry-standard interface for connecting AI assistants to external tools and data sources.

### Installation for Claude Desktop

1. **Install MCP Server**:
```bash
# From project root
cd apps/ontology/mcp
pip install -e .
```

2. **Configure Claude Desktop**:

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ontology": {
      "command": "/path/to/your/venv/bin/python",
      "args": [
        "-m",
        "ontology_mcp_server"
      ],
      "env": {
        "DJANGO_SETTINGS_MODULE": "intelliwiz_config.settings.development",
        "PYTHONPATH": "/Users/amar/Desktop/MyCode/DJANGO5-master"
      }
    }
  }
}
```

3. **Restart Claude Desktop**

4. **Verify Connection**:
```
In Claude Desktop, type:
"List all business terms in the OPERATIONS domain"

Claude will use MCP to query the ontology registry.
```

### MCP Server Capabilities

- **Search Terms**: Query business terms by domain, criticality, tags
- **Add Decorators**: Conversational decorator creation
- **Validate Coverage**: Check decoration status of files
- **Export Glossary**: Generate documentation on demand

---

## IDE Integration

### VSCode Snippets

**Installation**: Snippets are auto-loaded from `.vscode/ontology.code-snippets`

**Available Snippets**:

| Prefix | Description | Tab Stops |
|--------|-------------|-----------|
| `ontology-model` | Full model decorator | 12 fields |
| `ontology-service` | Full service decorator | 11 fields |
| `ontology-api` | Full API decorator | 10 fields |
| `ontology-middleware` | Full middleware decorator | 9 fields |
| `ont-model` | Quick model decorator | 6 fields (minimal) |
| `ont-service` | Quick service decorator | 6 fields (minimal) |
| `ontology-import` | Import statement | 0 fields |
| `ont-field-doc` | Field reference comment | 0 fields |

**Usage Example**:

1. Type `ont-model` in a Python file
2. Press `Tab` to expand
3. Fill in fields using `Tab` navigation
4. Press `Enter` to commit

**Demo**:
```python
# Type: ont-model<Tab>
# Result after filling fields:

@ontology_class(
    business_term='Guard Shift',
    definition='Represents a scheduled work shift for a security guard',
    domain='OPERATIONS',
    criticality='HIGH'
)
class GuardShift(models.Model):
    """A scheduled shift for guard assignment"""
    pass
```

**Time Savings**: ~30 seconds per decoration vs. 3+ minutes manual typing.

### PyCharm Live Templates

**Installation**: Import templates from `.idea/templates/ontology.xml`

**Steps**:
1. Open PyCharm Settings (`Cmd+,`)
2. Navigate to Editor → Live Templates
3. Click "+" → Import Settings
4. Select `.idea/templates/ontology.xml`
5. Click "OK"

**Available Templates**:

- `ont-model` - Model decorator
- `ont-service` - Service decorator
- `ont-api` - API decorator
- `ont-middleware` - Middleware decorator
- `ont-import` - Import statement
- `ont-quick` - Minimal model decorator

**Usage**: Same as VSCode - type prefix and press `Tab`.

---

## Coverage Dashboard

### Accessing the Dashboard

**URL**: `http://localhost:8000/ontology/dashboard/`

**Requirements**:
- Staff member account (is_staff=True)
- Development server running

**Start Server**:
```bash
python manage.py runserver
```

### Dashboard Features

#### 1. Summary Metrics
- Total files analyzed
- Decorated files count
- Overall coverage percentage
- Class-level coverage

#### 2. Domain Coverage Chart
- Bar chart showing coverage % by business domain
- Identifies high/low coverage areas
- Sortable by coverage percentage

#### 3. Criticality Breakdown
- Doughnut chart for CRITICAL/HIGH/MEDIUM/LOW
- Prioritizes critical gaps
- Shows decorated vs. total for each level

#### 4. Trend Analysis (30 Days)
- Line chart of decoration commits over time
- Tracks team adoption velocity
- Identifies commitment spikes

#### 5. App-Level Metrics Table
- Coverage % for each Django app
- Total files and decorated count
- Progress bars for visual scanning

#### 6. Top Coverage Gaps
- Critical files missing decorators
- Prioritized by class count
- Direct file paths for quick access

#### 7. Developer Leaderboard
- Top contributors by decoration count
- Gamification for adoption
- Recognition for team members

### API Endpoints

**Full Metrics** (JSON):
```bash
curl http://localhost:8000/ontology/api/metrics/
```

**Summary Only** (JSON):
```bash
curl http://localhost:8000/ontology/api/coverage/
```

**Use Cases**:
- CI/CD integration
- External monitoring
- Custom dashboards
- Slack/Teams notifications

---

## Best Practices

### 1. Decoration Standards

**DO**:
- Use clear, business-friendly terms (not technical jargon)
- Write definitions for non-developers
- Include realistic examples
- Tag with searchable keywords
- Set appropriate criticality

**DON'T**:
- Use vague definitions ("This is a model")
- Skip examples field
- Over-tag (3-5 tags is ideal)
- Use developer-only acronyms

### 2. Domain Assignment

| Domain | Use For |
|--------|---------|
| OPERATIONS | Tasks, tours, work orders, scheduling |
| ASSETS | Inventory, maintenance, asset tracking |
| PEOPLE | Users, attendance, authentication |
| HELPDESK | Tickets, escalations, SLAs |
| REPORTS | Analytics, dashboards, scheduled reports |
| SECURITY | AI monitoring, face recognition, biometrics |
| WELLNESS | Journal entries, wellbeing interventions |
| CORE | Framework components, utilities |
| ONBOARDING | Conversational AI, site setup |

### 3. Criticality Guidelines

| Level | Criteria |
|-------|----------|
| CRITICAL | Data loss risk, security implications, payment processing |
| HIGH | Core business logic, user authentication, regulatory compliance |
| MEDIUM | Standard CRUD operations, reporting, notifications |
| LOW | Utility classes, logging, caching |

### 4. Tag Strategy

**Good Tags**:
- `authentication`, `authorization`
- `payment-processing`, `billing`
- `task-management`, `scheduling`
- `reporting`, `analytics`
- `mobile-sync`, `offline-support`

**Bad Tags**:
- `django`, `python` (too generic)
- `model`, `view` (technical, not business)
- `stuff`, `things` (meaningless)

### 5. Context Field Usage

**Common Context Keys**:
```python
context={
    # Service-specific
    'idempotent': True,
    'async_capable': False,
    'timeout_seconds': 30,

    # API-specific
    'version': 'v2',
    'authentication': 'JWT',
    'rate_limit': '100/hour',

    # Business-specific
    'requires_approval': True,
    'audit_required': True,
    'pii_fields': ['email', 'phone']
}
```

---

## Troubleshooting

### Pre-Commit Hook Failing

**Symptom**: `git commit` blocked with "Missing ontology decorator" error.

**Solutions**:

1. **Add the decorator** (preferred):
```python
from apps.ontology.decorators import ontology_class

@ontology_class(...)
class MyModel(models.Model):
    pass
```

2. **Verify file is critical** (should it be enforced?):
   - Check if it's a real model or abstract base class
   - Check if it's in a test file (excluded automatically)

3. **Bypass if legitimate** (migrations, auto-generated):
```bash
git commit --no-verify -m "chore: database migration"
```

### Post-Commit Hook Not Running

**Symptom**: JSON not updating after commit.

**Diagnosis**:
```bash
# Check hook exists
ls -la .git/hooks/post-commit

# Check execute permission
ls -l .git/hooks/post-commit
# Should show: -rwxr-xr-x

# Test extraction manually
python apps/ontology/extractors/git_hook_extractor.py apps/activity/models/task.py
```

**Fix**:
```bash
# Reinstall hooks
bash scripts/install-ontology-hooks.sh --force
```

### Dashboard Not Loading

**Symptom**: 404 error or permission denied.

**Checks**:

1. **URL configured in main urls.py**:
```python
# intelliwiz_config/urls_optimized.py
path('ontology/', include('apps.ontology.urls')),
```

2. **Staff permissions**:
```python
# Django shell
python manage.py shell

>>> from peoples.models import People
>>> user = People.objects.get(username='youruser')
>>> user.is_staff = True
>>> user.save()
```

3. **Templates directory**:
```bash
ls -la apps/ontology/dashboard/templates/ontology/
# Should show: dashboard.html
```

### VSCode Snippets Not Appearing

**Symptom**: Typing `ont-model` doesn't trigger autocomplete.

**Solutions**:

1. **Reload VSCode**:
   - `Cmd+Shift+P` → "Reload Window"

2. **Check snippets file**:
```bash
ls -la .vscode/ontology.code-snippets
# Should exist and have content
```

3. **Enable user snippets**:
   - VSCode Settings → search "snippet suggestions"
   - Set to "inline" or "top"

### MCP Server Connection Failed

**Symptom**: Claude Desktop shows "MCP server not responding".

**Debug Steps**:

1. **Test server manually**:
```bash
cd apps/ontology/mcp
python -m ontology_mcp_server
# Should start without errors
```

2. **Check paths in config**:
```json
{
  "command": "/full/path/to/venv/bin/python",  // Must be absolute
  "env": {
    "PYTHONPATH": "/full/path/to/project"  // Must be absolute
  }
}
```

3. **Restart Claude Desktop completely**:
```bash
# macOS
killall "Claude Desktop"
open /Applications/Claude\ Desktop.app
```

4. **Check logs**:
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp-server-ontology.log
```

### Coverage Metrics Inaccurate

**Symptom**: Dashboard shows 0% coverage despite decorators.

**Diagnosis**:
```bash
# Check registry
python manage.py shell

>>> from apps.ontology.registry import OntologyRegistry
>>> registry = OntologyRegistry()
>>> len(registry.get_all())  # Should be > 0
```

**Fix**:
```bash
# Re-extract all decorators
python apps/ontology/extractors/full_codebase_extractor.py

# Restart server
python manage.py runserver
```

---

## Advanced Topics

### Custom Decorator Types

**Create new decorator types** for specialized components:

```python
# apps/ontology/decorators.py

def ontology_task(business_term, definition, **kwargs):
    """Decorator for Celery tasks."""
    def decorator(task_func):
        metadata = {
            'type': 'celery_task',
            'business_term': business_term,
            'definition': definition,
            **kwargs
        }
        OntologyRegistry().register(task_func.__name__, metadata)
        return task_func
    return decorator
```

### CI/CD Integration

**GitHub Actions Example**:

```yaml
# .github/workflows/ontology-check.yml
name: Ontology Coverage Check

on: [pull_request]

jobs:
  check-coverage:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements/base-linux.txt
      - name: Check ontology coverage
        run: |
          python apps/ontology/extractors/full_codebase_extractor.py
          python scripts/validate_ontology_coverage.py --min-coverage 80
```

### Slack Notifications

**Post coverage updates to Slack**:

```python
# scripts/post_coverage_to_slack.py
import requests
from apps.ontology.dashboard.metrics_generator import CoverageMetricsGenerator

generator = CoverageMetricsGenerator()
summary = generator.get_summary_metrics()

message = f"""
*Ontology Coverage Report*
Total Files: {summary['total_files']}
Decorated: {summary['decorated_files']}
Coverage: {summary['coverage_percentage']}%
"""

requests.post(
    'https://hooks.slack.com/services/YOUR/WEBHOOK/URL',
    json={'text': message}
)
```

---

## Support

**Documentation**: `docs/ontology/`
**Source Code**: `apps/ontology/`
**Issues**: Contact development team
**Questions**: Ask in #ontology-system Slack channel

---

**Last Updated**: October 30, 2025
**Version**: 1.0.0
**Status**: Production Ready
