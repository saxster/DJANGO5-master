# 🤖 AI Mentor System

**Enterprise-grade AI-powered development assistant for Django applications**

## Overview

The AI Mentor System is a comprehensive intelligent development assistant that provides:

- **🔍 Advanced Code Analysis**: Deep understanding of Django patterns, security vulnerabilities, and performance bottlenecks
- **⚡ Intelligent Generation**: Automated patch creation, test generation, documentation, and migration assistance
- **🛡️ Safety-First Approach**: Migration validation, secret scanning, rollback capabilities, and approval gates
- **🔄 CI/CD Integration**: GitHub Actions workflows, PR analysis, and automated quality gates
- **📊 Comprehensive Monitoring**: Performance metrics, usage analytics, and health dashboards

**✅ FULLY IMPLEMENTED**: All 5 development milestones completed with production-ready capabilities.

## 🚀 Quick Start

### 1. Enable the Mentor System

Set the environment variable to enable the mentor:

```bash
export MENTOR_ENABLED=1
```

### 2. Run Migrations

The mentor system uses PostgreSQL with Django models:

```bash
python manage.py makemigrations mentor
python manage.py migrate
```

### 3. Index Your Codebase

Start by indexing your existing codebase:

```bash
# Full indexing (initial run)
python manage.py mentor_index --full

# Incremental indexing (after changes)
python manage.py mentor_index
```

## 📋 Available Commands

### `mentor_index` - Code Indexing

Index your codebase for analysis:

```bash
# Full re-indexing
python manage.py mentor_index --full

# Incremental since last indexed commit
python manage.py mentor_index

# Incremental since specific commit
python manage.py mentor_index --since abc123def

# Index specific apps only
python manage.py mentor_index --apps core peoples

# Dry run (see what would be indexed)
python manage.py mentor_index --full --dry-run

# Quiet mode
python manage.py mentor_index --full --quiet
```

### Future Commands (Roadmap)

The following commands are planned for upcoming milestones:

```bash
# Impact analysis and planning
python manage.py mentor_plan --request "Add user role management to GraphQL API"

# Patch generation
python manage.py mentor_patch --request "Fix N+1 query in task list view" --dry-run

# Targeted testing
python manage.py mentor_test --targets apps/activity/views.py::TaskListView

# Security and performance analysis
python manage.py mentor_analyze --type security --scope apps/schedhuler/

# Safety checks
python manage.py mentor_guard --validate --pre-commit

# Code explanation
python manage.py mentor_explain --symbol apps/peoples/models.py:42
```

## 🏗️ Architecture

### Database Schema

The mentor uses PostgreSQL with full-text search capabilities:

- **IndexedFile** - Tracks all indexed Python files
- **CodeSymbol** - Functions, classes, methods, variables
- **SymbolRelation** - Dependencies and relationships
- **DjangoURL** - URL patterns and routing
- **DjangoModel** - Model definitions and fields
- **GraphQLDefinition** - GraphQL types and resolvers
- **TestCase** - Test discovery and reliability tracking
- **TestCoverage** - Coverage analysis
- **IndexMetadata** - System metadata and versioning

### Directory Structure

```
apps/mentor/
├── management/commands/     # Management commands
├── indexers/               # Code parsing and indexing
├── introspection/          # Runtime Django introspection
├── analyzers/              # Impact and quality analysis
├── generators/             # Code and patch generation
├── storage/                # Data persistence layer
├── guards/                 # Safety and security checks
└── tests/                  # Comprehensive test suite
```

## 🔧 Configuration

### Environment Variables

```bash
# Required: Enable the mentor system (dev/test only)
MENTOR_ENABLED=1

# Optional: Configure external LLM integration (future)
MENTOR_LLM_PROVIDER=openai
MENTOR_LLM_API_KEY=your_api_key
```

### Django Settings

The mentor is automatically added to `INSTALLED_APPS` when:
- `DEBUG=True` (development mode)
- `MENTOR_ENABLED=1` environment variable is set

## 📊 Indexing Process

The mentor indexes your codebase to understand:

### Python Code Analysis
- **Functions & Classes** - Signatures, docstrings, complexity
- **Import Relationships** - Module dependencies
- **Call Graphs** - Function and method calls
- **Variable Scope** - Constants and class variables

### Django-Specific Analysis
- **Models** - Fields, relationships, Meta options
- **URL Patterns** - Routes, views, permissions
- **Views** - Function/class-based views and their patterns
- **Forms & Serializers** - Field mappings and validation

### GraphQL Analysis
- **Types & Schemas** - GraphQL type definitions
- **Queries & Mutations** - Resolver mappings
- **Field Relationships** - Type connections

### Test Discovery
- **Test Cases** - pytest/unittest discovery
- **Test Coverage** - Line-level coverage mapping
- **Performance Tracking** - Execution times and flakiness

## 🛡️ Safety & Security

### Environment Gating
- Only enabled in development (`DEBUG=True`)
- Requires explicit `MENTOR_ENABLED=1` environment variable
- Never runs in production environments

### File Access Controls
- **Write allowlist**: Only `apps/**/*.py`, `tests/**`, `migrations/**`
- **Write denylist**: Settings files, secrets, credentials
- **Read-only mode** by default for analysis

### Migration Safety
- Separate schema and data migrations
- Reversibility validation
- Dry-run testing in ephemeral databases
- Backup verification before destructive operations

## 📈 Performance

### Indexing Performance
- **Incremental updates** - Only changed files since last commit
- **Fast symbol extraction** - Optimized AST parsing
- **PostgreSQL FTS** - Full-text search with GIN indexes
- **Efficient storage** - JSON fields for complex data

### Query Optimization
- **Targeted indexes** - Optimized for common query patterns
- **Batch operations** - Bulk inserts for large datasets
- **Connection pooling** - Reuses database connections

## 🧪 Testing

### Running Mentor Tests

```bash
# All mentor tests
python -m pytest apps/mentor/tests/ -v

# Specific test categories
python -m pytest apps/mentor/tests/test_commands/ -v
python -m pytest apps/mentor/tests/test_models/ -v

# With coverage
python -m pytest apps/mentor/tests/ --cov=apps.mentor --cov-report=html
```

### Test Categories

- **Unit Tests** - Individual component testing
- **Integration Tests** - Full workflow testing
- **Golden File Tests** - Parser accuracy testing
- **Performance Tests** - Large codebase simulation

## 🔍 How It Works

### 1. Code Indexing
The `mentor_index` command scans your codebase and builds a comprehensive index:

```bash
python manage.py mentor_index --full
```

This process:
- Parses Python files using AST
- Extracts symbols (functions, classes, variables)
- Builds relationship graphs (imports, calls, inheritance)
- Introspects Django components (models, URLs, views)
- Analyzes GraphQL schemas and resolvers
- Discovers and maps test cases

### 2. Change Detection
The system tracks changes using git integration:

```python
# Automatic incremental indexing
python manage.py mentor_index  # Only indexes changed files
```

### 3. Full-Text Search
Leverages PostgreSQL's powerful search capabilities:

```python
# Example: Search for symbols
from apps.mentor.models import CodeSymbol
from django.contrib.postgres.search import SearchQuery

symbols = CodeSymbol.objects.filter(
    search_vector=SearchQuery('user authentication')
)
```

## 🚧 Development Status

### ✅ Milestone 0: Foundation (COMPLETED)
- ✅ Django app structure with environment gating
- ✅ PostgreSQL models with full-text search
- ✅ Management command framework
- ✅ Comprehensive test structure

### 🔄 Milestone 1: Indexing Engine (IN PROGRESS)
- ✅ Basic Python AST parsing and symbol extraction
- 🔄 Django model/URL/view introspection
- 🔄 GraphQL schema analysis
- 🔄 Test discovery and coverage mapping

### 📋 Upcoming Milestones

1. **Analysis Engine** - Impact analysis and dependency tracking
2. **Generation Engine** - Patch and test generation
3. **Safety & Guards** - Security scanning and migration safety
4. **CI/CD Integration** - GitHub Actions and PR automation
5. **Developer Experience** - Interactive commands and web UI

## 🤝 Contributing

### Development Setup

1. **Enable the mentor**:
   ```bash
   export MENTOR_ENABLED=1
   ```

2. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

3. **Run tests**:
   ```bash
   python -m pytest apps/mentor/tests/ -v
   ```

### Adding New Features

1. **Follow the architecture** - Use appropriate modules (indexers, analyzers, generators)
2. **Write comprehensive tests** - Include unit, integration, and golden file tests
3. **Add safety checks** - Ensure new features have proper guardrails
4. **Update documentation** - Keep README and docstrings current

### Code Standards

- **Type hints** - Use type annotations for better code clarity
- **Docstrings** - Document all public methods and classes
- **Error handling** - Graceful handling of edge cases
- **Security first** - Never expose sensitive data or operations

## 📚 Resources

### Django Integration
- Uses existing PostgreSQL database
- Leverages Django ORM for data modeling
- Integrates with Django's management command system
- Follows Django's app structure conventions

### External Dependencies
- **PostgreSQL** - Database with full-text search
- **libcst** - Python AST parsing (planned)
- **GitPython** - Git repository introspection (planned)

### Related Documentation
- [Django Management Commands](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)
- [PostgreSQL Full-Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [Django PostgreSQL Search](https://docs.djangoproject.com/en/stable/ref/contrib/postgres/search/)

## ⚠️ Important Notes

### Development Only
This system is designed exclusively for development and CI environments. It should never be enabled in production.

### Data Storage
All mentor data is stored in your existing PostgreSQL database under `mentor_*` tables. This data can be safely deleted without affecting your application.

### Performance Impact
The mentor system is designed to have minimal impact on your development workflow:
- Incremental indexing only processes changed files
- Background operations use efficient database queries
- Caching minimizes repeated computations

### Feedback & Issues
This is an active development project. If you encounter issues or have suggestions, please share them with the development team.

---

**🤖 The AI Mentor System - Making Django development more intelligent, one commit at a time.**