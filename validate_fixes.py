#!/usr/bin/env python3
"""
Validation script for code review fixes.
Checks syntax and imports without requiring Django runtime.
"""

import ast
import sys
from pathlib import Path

def check_syntax(filepath):
    """Check Python file syntax."""
    try:
        with open(filepath, 'r') as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, str(e)

def check_imports(filepath):
    """Extract and validate imports."""
    imports = []
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module)
        return True, imports
    except Exception as e:
        return False, str(e)

def main():
    """Run validation checks."""
    files_to_check = [
        'apps/core/middleware/query_optimization_middleware.py',
        'apps/noc/serializers/alert_serializers.py',
        'apps/work_order_management/api/viewsets/work_permit_viewset.py',
    ]
    
    print("=" * 80)
    print("CODE REVIEW FIXES - VALIDATION REPORT")
    print("=" * 80)
    print()
    
    all_passed = True
    
    for filepath in files_to_check:
        print(f"Checking: {filepath}")
        print("-" * 80)
        
        # Check syntax
        valid, error = check_syntax(filepath)
        if valid:
            print("  ✅ Syntax: PASS")
        else:
            print(f"  ❌ Syntax: FAIL - {error}")
            all_passed = False
        
        # Check imports
        valid, imports = check_imports(filepath)
        if valid:
            print(f"  ✅ Imports: PASS ({len(imports)} imports found)")
            if filepath == 'apps/core/middleware/query_optimization_middleware.py':
                required_imports = ['django.core.cache', 'django.conf', 
                                   'django.utils.deprecation', 
                                   'apps.core.utils_new.sanitized_logging']
                missing = [imp for imp in required_imports if imp not in imports]
                if missing:
                    print(f"  ⚠️  Missing required imports: {missing}")
                    all_passed = False
                else:
                    print("  ✅ All required imports present")
        else:
            print(f"  ❌ Imports: FAIL - {imports}")
            all_passed = False
        
        print()
    
    print("=" * 80)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
        print()
        print("Summary:")
        print("  - 3 files validated")
        print("  - 0 syntax errors")
        print("  - 0 import errors")
        print("  - Ready for testing")
    else:
        print("❌ SOME CHECKS FAILED")
        print("Please review errors above")
        sys.exit(1)
    print("=" * 80)

if __name__ == '__main__':
    main()
