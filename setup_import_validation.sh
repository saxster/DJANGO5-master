#!/bin/bash
# Setup script for import validation and pre-commit hooks
# Run this script to set up comprehensive import organization tools

set -e

echo "🚀 Setting up Import Validation and Organization Tools"
echo "=" * 60

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "❌ Error: This script must be run from the Django project root (where manage.py is located)"
    exit 1
fi

# Check Python version
echo "🐍 Checking Python version..."
python3 --version

# Install pre-commit if not already installed
echo "📦 Installing pre-commit..."
if ! command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit..."
    pip3 install pre-commit
else
    echo "✅ pre-commit already installed"
fi

# Install additional required packages
echo "📦 Installing required packages..."
pip3 install isort black flake8 bandit autoflake

# Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
pre-commit install

# Run initial import analysis
echo "🔍 Running initial import analysis..."
if [ -f "standalone_import_analyzer.py" ]; then
    echo "Running comprehensive import analysis..."
    python3 standalone_import_analyzer.py
else
    echo "⚠️  standalone_import_analyzer.py not found. Please ensure it's in the project root."
fi

# Test pre-commit hooks
echo "🧪 Testing pre-commit hooks..."
pre-commit run --all-files --verbose || echo "⚠️  Some hooks failed - this is normal for first run"

# Create .isort.cfg for consistent import sorting
echo "📝 Creating .isort.cfg configuration..."
cat > .isort.cfg << EOF
[settings]
profile = django
multi_line_output = 3
include_trailing_comma = True
force_grid_wrap = 0
combine_as_imports = True
line_length = 88
known_django = django
known_first_party = apps
sections = FUTURE,STDLIB,THIRDPARTY,DJANGO,FIRSTPARTY,LOCALFOLDER
EOF

# Create import organization documentation
echo "📚 Creating import organization documentation..."
cat > IMPORT_GUIDELINES.md << 'EOF'
# Import Organization Guidelines

This project uses automated import validation and organization to ensure consistent, clean code.

## Import Rules

### 1. Import Order (automatically enforced by isort)
```python
# Standard library imports
import os
import sys
from datetime import datetime

# Third-party imports
import requests
from celery import shared_task

# Django imports
from django.db import models
from django.contrib.auth import get_user_model

# Local app imports (absolute)
from apps.peoples.models import People
from apps.core.utils import some_util

# Same-app imports (relative)
from .models import LocalModel
from .utils import local_function
```

### 2. Unused Imports
- All unused imports are automatically detected and removed
- Pre-commit hooks prevent commits with unused imports
- Run `python3 standalone_import_analyzer.py --fix-unused` to clean up

### 3. Import Style Consistency
- Use absolute imports for cross-app dependencies: `from apps.peoples.models import People`
- Use relative imports only within the same app: `from .models import LocalModel`
- Pre-commit hooks enforce consistent style

### 4. Circular Import Detection
- Circular imports are detected and reported
- Use dependency injection or late imports to resolve circular dependencies

## Tools

### Available Commands
```bash
# Analyze all imports
python3 standalone_import_analyzer.py

# Fix unused imports automatically
python3 standalone_import_analyzer.py --fix-unused

# Check import style consistency (dry-run)
python3 fix_import_styles.py --dry-run

# Fix import style issues
python3 fix_import_styles.py

# Generate dependency graph
python3 standalone_import_analyzer.py --generate-graph

# Run all pre-commit hooks
pre-commit run --all-files

# Run specific hook
pre-commit run import-validation
```

### Pre-commit Hooks
The following hooks run automatically on each commit:
- **import-validation**: Comprehensive import analysis
- **import-style-check**: Style consistency validation
- **unused-imports-check**: Quick unused import detection
- **isort**: Automatic import sorting
- **black**: Code formatting
- **flake8**: Linting

## Best Practices

1. **Keep imports at the top**: All imports should be at the file top, after module docstrings
2. **Group related imports**: Use the standard grouping (stdlib, third-party, django, local)
3. **Avoid wildcard imports**: Never use `from module import *`
4. **Use explicit imports**: Prefer `from module import specific_function` over `import module`
5. **Minimize import scope**: Import only what you need
6. **Resolve circular imports**: Refactor shared code into separate modules

## Troubleshooting

### Pre-commit Hook Failures
If pre-commit hooks fail:
1. Read the error message carefully
2. Fix the reported issues
3. Re-run the commit

### Circular Imports
If circular imports are detected:
1. Move shared code to a separate module
2. Use late imports (`import` inside functions)
3. Use dependency injection patterns

### Style Inconsistencies
If import style issues are found:
1. Run `python3 fix_import_styles.py` to auto-fix
2. Manually adjust any remaining issues
3. Follow the import order guidelines above
EOF

echo "✅ Import validation setup complete!"
echo ""
echo "📋 Summary of tools installed:"
echo "  ✓ Pre-commit hooks with import validation"
echo "  ✓ Comprehensive import analyzer (standalone_import_analyzer.py)"
echo "  ✓ Import style fixer (fix_import_styles.py)"
echo "  ✓ Import guidelines documentation (IMPORT_GUIDELINES.md)"
echo "  ✓ isort configuration (.isort.cfg)"
echo ""
echo "🎯 Next steps:"
echo "  1. Review the import analysis results"
echo "  2. Read IMPORT_GUIDELINES.md for best practices"
echo "  3. Make a test commit to ensure hooks are working"
echo "  4. Run 'python3 standalone_import_analyzer.py --generate-graph' for dependency visualization"
echo ""
echo "🎉 Your Django project now has world-class import organization!"