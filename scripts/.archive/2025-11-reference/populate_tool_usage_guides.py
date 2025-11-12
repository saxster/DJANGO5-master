#!/usr/bin/env python3
"""
Populate Help Center with Developer Tool Usage Guides

Creates comprehensive documentation for all automation tools with:
- Step-by-step instructions
- Command-line examples
- Expected output
- Troubleshooting tips
- Links to source code

Usage:
    python scripts/populate_tool_usage_guides.py --dry-run
    python scripts/populate_tool_usage_guides.py --execute

Author: Amp Documentation Team
Date: 2025-11-06
"""

import os
import sys
import django
from pathlib import Path
from typing import Dict, List

# Setup Django environment
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.db import transaction
from apps.help_center.models import HelpCategory, HelpArticle
from apps.peoples.models import People


# Tool Documentation Content
TOOL_CATEGORIES = {
    'security': {
        'name': 'Security Tools',
        'description': 'Tools for security analysis and vulnerability detection',
        'icon': 'fa-shield-alt',
        'color': '#d32f2f',
        'tools': [
            {
                'title': 'How to Use check_serializer_security.py',
                'slug': 'check-serializer-security',
                'summary': 'Detect security anti-patterns in DRF serializers',
                'script': 'scripts/check_serializer_security.py',
                'tags': ['security', 'serializers', 'drf'],
            },
            {
                'title': 'How to Verify Secure File Downloads',
                'slug': 'verify-secure-file-downloads',
                'summary': 'Test file download security and permission validation',
                'script': 'verify_secure_file_download.py',
                'tags': ['security', 'files', 'permissions'],
            },
            {
                'title': 'How to Test for IDOR Vulnerabilities',
                'slug': 'test-idor-vulnerabilities',
                'summary': 'Run comprehensive IDOR security tests',
                'script': 'tests/security/test_idor_*.py',
                'tags': ['security', 'idor', 'testing'],
            },
        ]
    },
    'performance': {
        'name': 'Performance Tools',
        'description': 'Tools for performance analysis and optimization',
        'icon': 'fa-tachometer-alt',
        'color': '#f57c00',
        'tools': [
            {
                'title': 'How to Use validate_n1_optimization.py',
                'slug': 'validate-n1-optimization',
                'summary': 'Validate N+1 query fixes and optimization patterns',
                'script': 'scripts/validate_n1_optimization.py',
                'tags': ['performance', 'database', 'n+1'],
            },
            {
                'title': 'How to Benchmark Performance',
                'slug': 'benchmark-performance',
                'summary': 'Run performance benchmarks for critical operations',
                'script': 'scripts/benchmark_predictive_tasks.py',
                'tags': ['performance', 'benchmarking'],
            },
            {
                'title': 'How to Generate Performance Reports',
                'slug': 'generate-performance-reports',
                'summary': 'Create detailed performance analysis reports',
                'script': 'scripts/test_performance_optimizations.py',
                'tags': ['performance', 'reporting'],
            },
        ]
    },
    'code_quality': {
        'name': 'Code Quality Tools',
        'description': 'Tools for code quality analysis and refactoring',
        'icon': 'fa-code',
        'color': '#388e3c',
        'tools': [
            {
                'title': 'How to Use remediate_exception_handling.py',
                'slug': 'remediate-exception-handling',
                'summary': 'Fix exception handling anti-patterns automatically',
                'script': 'scripts/remediate_exception_handling.py',
                'tags': ['code-quality', 'exceptions', 'refactoring'],
            },
            {
                'title': 'How to Detect God Files',
                'slug': 'detect-god-files',
                'summary': 'Identify files violating architecture limits',
                'script': 'scripts/detect_god_files.py',
                'tags': ['code-quality', 'architecture', 'refactoring'],
            },
            {
                'title': 'How to Detect Deep Nesting',
                'slug': 'detect-deep-nesting',
                'summary': 'Find and flatten deeply nested code blocks',
                'script': 'scripts/detect_deep_nesting.py',
                'tags': ['code-quality', 'complexity', 'refactoring'],
            },
            {
                'title': 'How to Detect Magic Numbers',
                'slug': 'detect-magic-numbers',
                'summary': 'Extract magic numbers into named constants',
                'script': 'scripts/detect_magic_numbers.py',
                'tags': ['code-quality', 'maintainability'],
            },
            {
                'title': 'How to Check Circular Dependencies',
                'slug': 'check-circular-dependencies',
                'summary': 'Detect and resolve circular import issues',
                'script': 'scripts/detect_circular_dependencies.py',
                'tags': ['code-quality', 'imports', 'architecture'],
            },
            {
                'title': 'How to Verify Model Meta Completeness',
                'slug': 'verify-model-meta-completeness',
                'summary': 'Ensure Django models have complete Meta classes',
                'script': 'scripts/check_model_meta_completeness.py',
                'tags': ['code-quality', 'models', 'django'],
            },
        ]
    },
    'testing': {
        'name': 'Testing Tools',
        'description': 'Tools for test coverage and quality assurance',
        'icon': 'fa-flask',
        'color': '#1976d2',
        'tools': [
            {
                'title': 'How to Find Untested Services',
                'slug': 'find-untested-services',
                'summary': 'Identify service classes without test coverage',
                'script': 'scripts/find_untested_services.py',
                'tags': ['testing', 'coverage', 'services'],
            },
            {
                'title': 'How to Generate Coverage Reports',
                'slug': 'generate-coverage-reports',
                'summary': 'Create HTML coverage reports with pytest',
                'script': 'scripts/run_tests_with_coverage.py',
                'tags': ['testing', 'coverage', 'reporting'],
            },
            {
                'title': 'How to Run IDOR Tests',
                'slug': 'run-idor-tests',
                'summary': 'Execute IDOR vulnerability test suite',
                'script': 'tests/security/',
                'tags': ['testing', 'security', 'idor'],
            },
        ]
    },
}


def generate_article_content(tool_info: Dict) -> str:
    """Generate comprehensive article content for a tool."""
    
    script_name = tool_info['script']
    title = tool_info['title']
    
    content = f"""
# {title}

## Overview

{tool_info['summary']}

**Script Location:** `{script_name}`

## Prerequisites

Before using this tool, ensure:

1. **Python virtual environment is activated:**
   ```bash
   source venv/bin/activate
   ```

2. **Django environment is configured:**
   ```bash
   export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings.development
   ```

3. **Required dependencies are installed:**
   ```bash
   pip install -r requirements/base-macos.txt  # macOS
   pip install -r requirements/base-linux.txt  # Linux
   ```

## Usage

### Basic Usage

```bash
python {script_name}
```

### Advanced Options

"""
    
    # Add tool-specific sections
    if 'check_serializer_security' in script_name:
        content += """
#### Check Specific Files

```bash
python scripts/check_serializer_security.py --file apps/myapp/serializers.py
```

#### Check Entire App

```bash
python scripts/check_serializer_security.py --app myapp
```

#### Output JSON Report

```bash
python scripts/check_serializer_security.py --json > security_report.json
```

## Expected Output

### No Violations

```
✅ Serializer Security Check Complete
Files checked: 45
Violations found: 0
Status: PASS
```

### Violations Found

```
🔴 apps/peoples/serializers.py:23
   Violation: fields = '__all__' exposes all model fields (FORBIDDEN)
   Line: fields = '__all__'

🔴 apps/auth/serializers.py:45
   Violation: password field missing write_only=True
   Line: password = serializers.CharField()

Total violations: 2
Status: FAIL
```

## How to Interpret Results

| Violation Type | Risk Level | Action Required |
|----------------|------------|-----------------|
| `fields = '__all__'` | 🔴 CRITICAL | Replace with explicit field list |
| Missing `write_only` on password | 🔴 CRITICAL | Add `write_only=True` |
| Missing `read_only` on sensitive fields | 🟠 HIGH | Add `read_only=True` |

## Fixing Violations

### Fix 1: Replace `fields = '__all__'`

**Before:**
```python
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
```

**After:**
```python
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
```

### Fix 2: Add `write_only=True` to passwords

**Before:**
```python
password = serializers.CharField()
```

**After:**
```python
password = serializers.CharField(write_only=True)
```

## Integration with CI/CD

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: check-serializer-security
      name: Check Serializer Security
      entry: python scripts/check_serializer_security.py
      language: system
      pass_filenames: false
      always_run: true
```

## Troubleshooting

### Error: ModuleNotFoundError

**Problem:** Django not in PYTHONPATH

**Solution:**
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python scripts/check_serializer_security.py
```

### Error: No module named 'apps'

**Problem:** Not running from project root

**Solution:**
```bash
cd /path/to/project/root
python scripts/check_serializer_security.py
```

### False Positives

If you have legitimate use of `fields = '__all__'` (rare), add comment:

```python
class InternalSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternalModel
        fields = '__all__'  # SECURITY_REVIEW_APPROVED: Internal use only
```
"""

    elif 'detect_god_files' in script_name:
        content += """
#### Generate Full Report

```bash
python scripts/detect_god_files.py --report GOD_FILES.md
```

#### Check Against Threshold

```bash
python scripts/detect_god_files.py --check --threshold 150
```

#### Analyze Specific File

```bash
python scripts/detect_god_files.py --analyze --file apps/myapp/views.py
```

#### Generate Burndown Chart

```bash
python scripts/detect_god_files.py --burndown --chart burndown.png
```

## Expected Output

### Summary Report

```
🔍 God File Detection Report
Generated: 2025-11-06 10:30:00

📊 Summary:
Total files scanned: 234
God files found: 12
Total violations: 15,234 lines over limit

Severity Breakdown:
🔴 CRITICAL (>1000 lines): 2 files
🟠 HIGH (500-999): 4 files
🟡 MEDIUM (300-499): 6 files
```

### Detailed File List

```
apps/peoples/views.py
  Lines: 1,234 (1,084 over limit of 150)
  Severity: CRITICAL
  Category: views
  
apps/work_order_management/models.py
  Lines: 678 (528 over limit of 150)
  Severity: HIGH
  Category: models
```

## Architecture Limits (CLAUDE.md)

| File Type | Line Limit | Reasoning |
|-----------|------------|-----------|
| Views | 150 | Single responsibility per view |
| Models | 150 | Extract to mixins/managers |
| Services | 150 | Decompose into smaller services |
| Forms | 100 | Split complex forms |
| Settings | 200 | Split by environment |

## Refactoring Strategy

### Step 1: Identify Violations

```bash
python scripts/detect_god_files.py --report GOD_FILES.md
```

### Step 2: Prioritize by Severity

Focus on CRITICAL and HIGH severity files first.

### Step 3: Use Refactoring Tool

```bash
python scripts/refactor_god_file.py --file apps/myapp/views.py --strategy split-by-function
```

### Step 4: Verify Tests Pass

```bash
python -m pytest apps/myapp/tests/
```

### Step 5: Track Progress

```bash
python scripts/detect_god_files.py --burndown --chart burndown.png
```

## Troubleshooting

### High False Positive Rate

**Problem:** Counting comment blocks and imports

**Solution:** Script already excludes:
- Empty lines
- Comment-only lines
- Import statements (partially)

### File Category Not Detected

**Problem:** Custom naming convention

**Solution:** Update `get_file_category()` in script:

```python
elif 'mycustom' in name:
    return 'views'  # or appropriate category
```

### Tracking Historical Progress

**Problem:** Want to show reduction over time

**Solution:** Generate weekly reports:

```bash
python scripts/detect_god_files.py --report "GOD_FILES_$(date +%Y%m%d).md"
```
"""

    elif 'detect_deep_nesting' in script_name:
        content += """
#### Generate Full Report

```bash
python scripts/detect_deep_nesting.py --report DEEP_NESTING.md
```

#### Check Specific Directory

```bash
python scripts/detect_deep_nesting.py --path apps/myapp/
```

#### Set Custom Threshold

```bash
python scripts/detect_deep_nesting.py --max-depth 2
```

#### Auto-Fix Simple Cases

```bash
python scripts/detect_deep_nesting.py --fix --backup
```

## Expected Output

### Violation Report

```
🔍 Deep Nesting Detection Report

apps/peoples/views.py:45-78
  Max depth: 5 (exceeds limit of 3)
  Function: create_user_with_profile
  Lines: 34 lines
  
  Nesting structure:
    Level 1: if user_form.is_valid():
      Level 2: if profile_form.is_valid():
        Level 3: if organizational_form.is_valid():
          Level 4: try:
            Level 5: with transaction.atomic():
```

### Refactoring Suggestion

```
💡 Suggested refactoring:
- Extract validation to helper: validate_user_forms()
- Extract transaction logic to service method
- Use early returns to reduce nesting
```

## Refactoring Patterns

### Pattern 1: Early Returns

**Before (Depth 4):**
```python
def process_request(request):
    if request.user.is_authenticated:
        if request.method == 'POST':
            if form.is_valid():
                if has_permission(request.user):
                    # Process
```

**After (Depth 1):**
```python
def process_request(request):
    if not request.user.is_authenticated:
        return HttpResponse(status=401)
    
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    if not form.is_valid():
        return JsonResponse(form.errors, status=400)
    
    if not has_permission(request.user):
        return HttpResponse(status=403)
    
    # Process
```

### Pattern 2: Extract Helper Functions

**Before:**
```python
def complex_view(request):
    if condition1:
        if condition2:
            if condition3:
                # Complex logic
```

**After:**
```python
def complex_view(request):
    if not _validate_request(request):
        return error_response()
    
    return _process_validated_request(request)

def _validate_request(request):
    return condition1 and condition2 and condition3

def _process_validated_request(request):
    # Complex logic
```

### Pattern 3: Use Comprehensions

**Before:**
```python
results = []
for item in items:
    if item.active:
        if item.valid:
            results.append(item.process())
```

**After:**
```python
results = [
    item.process()
    for item in items
    if item.active and item.valid
]
```

## Troubleshooting

### Script Not Finding Violations

**Problem:** Custom code patterns not detected

**Solution:** Check AST parsing works for your syntax:

```bash
python -c "import ast; ast.parse(open('myfile.py').read())"
```

### Auto-Fix Breaking Code

**Problem:** Automated refactoring introduced bugs

**Solution:** Always use `--backup` flag and verify:

```bash
python scripts/detect_deep_nesting.py --fix --backup
python -m pytest  # Verify tests still pass
```
"""

    elif 'validate_n1_optimization' in script_name:
        content += """
#### Validate All Optimizations

```bash
python scripts/validate_n1_optimization.py
```

#### Test Specific App

```bash
python scripts/validate_n1_optimization.py --app peoples
```

#### Generate Performance Report

```bash
python scripts/validate_n1_optimization.py --report performance.json
```

#### Compare Before/After

```bash
python scripts/validate_n1_optimization.py --benchmark --iterations 100
```

## Expected Output

### Validation Success

```
✅ N+1 Query Optimization Validation

Checking: PeopleQueryService
  ✓ select_related used: profile, organizational
  ✓ prefetch_related used: assigned_tasks, permissions
  ✓ Query count: 3 (optimized from 45)
  ✓ Performance: 23ms (improved by 87%)

Checking: TaskQueryService
  ✓ select_related used: client, site, assigned_people
  ✓ Query count: 2 (optimized from 12)
  ✓ Performance: 15ms (improved by 75%)

Total validations: 12
Passed: 12
Failed: 0
```

### Performance Comparison

```
📊 Before/After Comparison:

peoples.views.user_list
  Before: 45 queries, 178ms
  After:  3 queries, 23ms
  Improvement: 87% faster, 42 fewer queries

work_orders.views.dashboard
  Before: 89 queries, 456ms
  After:  8 queries, 67ms
  Improvement: 85% faster, 81 fewer queries
```

## Understanding N+1 Queries

### The Problem

```python
# ❌ N+1 PROBLEM: 1 query + N queries for profiles
users = People.objects.all()  # 1 query
for user in users:
    print(user.profile.department)  # N additional queries
```

### The Solution

```python
# ✅ OPTIMIZED: 2 queries total
users = People.objects.select_related('profile').all()
for user in users:
    print(user.profile.department)  # No additional queries
```

## Optimization Patterns

### Pattern 1: select_related (Foreign Keys)

Use for **one-to-one** and **foreign key** relationships:

```python
# Optimize FK and O2O
users = People.objects.select_related(
    'profile',          # OneToOneField
    'organizational',   # OneToOneField
    'site'             # ForeignKey
).all()
```

### Pattern 2: prefetch_related (Many-to-Many)

Use for **many-to-many** and **reverse foreign keys**:

```python
# Optimize M2M and reverse FK
tasks = Task.objects.prefetch_related(
    'assigned_people',  # ManyToManyField
    'attachments',      # Reverse ForeignKey
    'tags'             # ManyToManyField
).all()
```

### Pattern 3: Custom QuerySet Managers

```python
class PeopleQuerySet(models.QuerySet):
    def with_full_details(self):
        return self.select_related(
            'profile',
            'organizational'
        ).prefetch_related(
            'assigned_tasks',
            'permissions'
        )

# Usage
users = People.objects.with_full_details()
```

## Troubleshooting

### Validation Failing After Optimization

**Problem:** Query count increased instead of decreased

**Diagnosis:**
```bash
python scripts/validate_n1_optimization.py --verbose --app myapp
```

**Common Causes:**
1. Accessing fields not in select_related
2. Filtering prefetched querysets
3. Missing related field in optimization

### False Negatives

**Problem:** N+1 not detected

**Solution:** Enable Django query logging:

```python
# settings/development.py
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
        }
    }
}
```

Then check for repeated similar queries.
"""

    elif 'find_untested_services' in script_name:
        content += """
#### Find All Untested Services

```bash
python scripts/find_untested_services.py
```

#### Check Specific App

```bash
python scripts/find_untested_services.py --app peoples
```

#### Generate Coverage Report

```bash
python scripts/find_untested_services.py --report coverage.html
```

#### Include Test Stubs

```bash
python scripts/find_untested_services.py --generate-stubs
```

## Expected Output

### Service Coverage Report

```
🔍 Untested Services Report

apps/peoples/services/user_service.py
  Class: UserCreationService
  Methods: 8
  Tested: 3
  Coverage: 37.5%
  
  Untested methods:
    - create_bulk_users
    - update_user_permissions
    - deactivate_users_by_site
    - export_user_data
    - validate_organizational_hierarchy

apps/work_order_management/services/approval_service.py
  Class: ApprovalWorkflowService
  Methods: 12
  Tested: 12
  Coverage: 100% ✅
```

### Summary Statistics

```
📊 Overall Coverage:
Total services: 45
Fully tested: 23 (51%)
Partially tested: 15 (33%)
Not tested: 7 (16%)

Total methods: 234
Tested: 178 (76%)
Untested: 56 (24%)
```

## Generated Test Stubs

With `--generate-stubs`, the script creates:

```python
# tests/services/test_user_service.py

import pytest
from apps.peoples.services.user_service import UserCreationService


class TestUserCreationService:
    # Tests for UserCreationService
    
    @pytest.fixture
    def service(self):
        return UserCreationService()
    
    def test_create_bulk_users(self, service):
        # Test create_bulk_users method
        # TODO: Implement test
        assert False, "Test not implemented"
    
    def test_update_user_permissions(self, service):
        # Test update_user_permissions method
        # TODO: Implement test
        assert False, "Test not implemented"
```

## Best Practices for Service Testing

### Pattern 1: Test Public Interface

```python
class TestUserCreationService:
    def test_create_user_success(self):
        service = UserCreationService()
        user = service.create_user(
            username='testuser',
            email='test@example.com'
        )
        assert user.id is not None
        assert user.username == 'testuser'
```

### Pattern 2: Use Fixtures

```python
@pytest.fixture
def user_data():
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User'
    }

def test_create_user(user_data):
    service = UserCreationService()
    user = service.create_user(**user_data)
    assert user.username == user_data['username']
```

### Pattern 3: Mock External Dependencies

```python
from unittest.mock import patch

def test_send_welcome_email():
    service = UserCreationService()
    
    with patch('apps.peoples.services.user_service.send_email') as mock_email:
        user = service.create_user(username='test')
        mock_email.assert_called_once_with(
            to=user.email,
            subject='Welcome'
        )
```

## Troubleshooting

### Script Not Finding Services

**Problem:** Custom service organization

**Solution:** Configure search patterns:

```python
# In script
SERVICE_PATTERNS = [
    '**/services/*.py',
    '**/service_*.py',
    '**/handlers/*.py',  # Add custom patterns
]
```

### Coverage Calculation Incorrect

**Problem:** Private methods counted

**Solution:** Script already excludes methods starting with `_`:

```python
def _private_method(self):  # Not counted
    pass

def public_method(self):    # Counted
    pass
```
"""

    # Add common sections for all tools
    content += """

## Related Documentation

- [CLAUDE.md](file:///CLAUDE.md) - Development best practices
- [Testing Guide](file:///docs/testing/TESTING_AND_QUALITY_GUIDE.md)
- [Architecture Documentation](file:///docs/architecture/SYSTEM_ARCHITECTURE.md)

## Source Code

View the complete script:
[{script_name}](file:///{script_name})

## Getting Help

If you encounter issues:

1. Check this troubleshooting section
2. Review [Common Issues](file:///docs/troubleshooting/COMMON_ISSUES.md)
3. Ask in #engineering-help Slack channel
4. Create issue with reproduction steps

## Contributing

Found a bug or improvement? Submit a PR:

1. Fork the script
2. Add your improvements
3. Update this documentation
4. Submit PR with tests

---

**Last Updated:** 2025-11-06  
**Maintainer:** Engineering Team  
**Version:** 1.0
""".format(script_name=script_name)
    
    return content.strip()


def create_developer_tools_category(tenant, author):
    """Create Developer Tools parent category."""
    category, created = HelpCategory.objects.get_or_create(
        tenant=tenant,
        slug='developer-tools',
        defaults={
            'name': 'Developer Tools',
            'description': 'Comprehensive guides for using automation and analysis tools',
            'icon': 'fa-tools',
            'color': '#6a1b9a',
            'display_order': 100,
            'is_active': True,
        }
    )
    
    if created:
        print(f"✅ Created parent category: Developer Tools")
    else:
        print(f"ℹ️  Using existing category: Developer Tools")
    
    return category


def create_tool_categories(parent_category, tenant):
    """Create tool subcategories."""
    categories = {}
    
    for key, cat_info in TOOL_CATEGORIES.items():
        category, created = HelpCategory.objects.get_or_create(
            tenant=tenant,
            slug=f"developer-tools-{key}",
            defaults={
                'name': cat_info['name'],
                'description': cat_info['description'],
                'icon': cat_info['icon'],
                'color': cat_info['color'],
                'parent': parent_category,
                'display_order': list(TOOL_CATEGORIES.keys()).index(key) * 10,
                'is_active': True,
            }
        )
        
        categories[key] = category
        
        if created:
            print(f"  ✅ Created subcategory: {cat_info['name']}")
        else:
            print(f"  ℹ️  Using existing: {cat_info['name']}")
    
    return categories


def create_tool_articles(categories, tenant, author, dry_run=False):
    """Create articles for all tools."""
    
    created_count = 0
    updated_count = 0
    
    for cat_key, cat_info in TOOL_CATEGORIES.items():
        category = categories[cat_key]
        
        print(f"\n📝 Creating articles for {cat_info['name']}:")
        
        for tool in cat_info['tools']:
            article_data = {
                'tenant': tenant,
                'title': tool['title'],
                'slug': tool['slug'],
                'summary': tool['summary'],
                'content': generate_article_content(tool),
                'category': category,
                'difficulty_level': HelpArticle.DifficultyLevel.INTERMEDIATE,
                'status': HelpArticle.Status.PUBLISHED if not dry_run else HelpArticle.Status.DRAFT,
                'created_by': author,
                'updated_by': author,
                'view_count': 0,
                'is_featured': False,
                'enable_feedback': True,
            }
            
            if dry_run:
                print(f"  [DRY RUN] Would create: {tool['title']}")
                created_count += 1
            else:
                article, created = HelpArticle.objects.update_or_create(
                    tenant=tenant,
                    slug=tool['slug'],
                    defaults=article_data
                )
                
                # Add tags
                from apps.help_center.models import HelpTag
                for tag_name in tool['tags']:
                    tag, _ = HelpTag.objects.get_or_create(
                        tenant=tenant,
                        name=tag_name,
                        defaults={'slug': tag_name}
                    )
                    article.tags.add(tag)
                
                if created:
                    print(f"  ✅ Created: {tool['title']}")
                    created_count += 1
                else:
                    print(f"  🔄 Updated: {tool['title']}")
                    updated_count += 1
    
    return created_count, updated_count


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate help center with tool usage guides')
    parser.add_argument('--dry-run', action='store_true', help='Preview without creating')
    parser.add_argument('--execute', action='store_true', help='Execute creation')
    parser.add_argument('--tenant', type=str, default='default', help='Tenant slug')
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        print("❌ Error: Must specify --dry-run or --execute")
        sys.exit(1)
    
    print("🚀 Developer Tools Documentation Generator\n")
    
    # Get tenant and author
    from apps.tenants.models import Tenant
    
    try:
        tenant = Tenant.objects.get(slug=args.tenant)
    except Tenant.DoesNotExist:
        print(f"❌ Tenant '{args.tenant}' not found")
        sys.exit(1)
    
    # Use first superuser as author
    author = People.objects.filter(is_superuser=True).first()
    if not author:
        print("❌ No superuser found. Create one first.")
        sys.exit(1)
    
    print(f"Tenant: {tenant.name}")
    print(f"Author: {author.username}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}\n")
    
    try:
        with transaction.atomic():
            # Create category structure
            parent_category = create_developer_tools_category(tenant, author)
            categories = create_tool_categories(parent_category, tenant)
            
            # Create articles
            created, updated = create_tool_articles(
                categories, 
                tenant, 
                author, 
                dry_run=args.dry_run
            )
            
            print("\n" + "="*60)
            print("📊 Summary:")
            print(f"  Categories created: {len(categories) + 1}")
            print(f"  Articles created: {created}")
            print(f"  Articles updated: {updated}")
            print(f"  Total articles: {created + updated}")
            print("="*60)
            
            if args.dry_run:
                print("\n⚠️  DRY RUN - No changes committed")
                raise Exception("Dry run - rolling back")
            else:
                print("\n✅ All documentation created successfully!")
                
    except Exception as e:
        if args.dry_run and "Dry run" in str(e):
            print("\n✅ Dry run completed successfully")
        else:
            print(f"\n❌ Error: {e}")
            raise


if __name__ == '__main__':
    main()
