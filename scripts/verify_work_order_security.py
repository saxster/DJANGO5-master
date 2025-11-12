#!/usr/bin/env python
"""
Work Order Security Verification Script

Verifies that all work order views have proper authentication and authorization.

Usage:
    python scripts/verify_work_order_security.py

Created: November 6, 2025
Part of: CRITICAL SECURITY FIX 2
"""

import os
import re
import sys
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_file(filepath):
    """Check a Python file for security patterns."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    results = {
        'file': filepath,
        'has_login_required': False,
        'has_security_service': False,
        'has_permission_denied': False,
        'has_validate_access': False,
        'vulnerable_patterns': [],
        'class_security': {}
    }
    
    # Check for LoginRequiredMixin
    if 'LoginRequiredMixin' in content:
        results['has_login_required'] = True
    
    # Check for security service import
    if 'WorkOrderSecurityService' in content:
        results['has_security_service'] = True
    
    # Check for PermissionDenied
    if 'PermissionDenied' in content:
        results['has_permission_denied'] = True
    
    # Check for validation methods
    validation_methods = [
        'validate_work_order_access',
        'validate_token_access',
        'validate_approver_access',
        'validate_vendor_access',
        'validate_delete_permission',
        'validate_close_permission'
    ]
    
    for method in validation_methods:
        if method in content:
            results['has_validate_access'] = True
            break
    
    # Find all class definitions
    class_pattern = r'class\s+(\w+)\(([^)]+)\):'
    classes = re.findall(class_pattern, content)
    
    for class_name, bases in classes:
        has_login = 'LoginRequiredMixin' in bases
        is_view = 'View' in bases
        
        results['class_security'][class_name] = {
            'has_login_required': has_login,
            'is_view': is_view,
            'is_protected': has_login or not is_view
        }
    
    # Check for vulnerable patterns (direct object access without validation)
    vulnerable_patterns = [
        (r'Wom\.objects\.get\(id=.*\)', 'Direct Wom.objects.get() without validation'),
        (r'Wom\.objects\.filter\(id=.*\)\.update\(', 'Direct update without validation'),
        (r'\.delete\(\)', 'Delete without permission check'),
    ]
    
    for pattern, description in vulnerable_patterns:
        matches = re.findall(pattern, content)
        if matches:
            # Check if it's within a try-except with validation
            for match in matches:
                # Simple heuristic: if validate_* appears near the match, it's probably safe
                context_start = max(0, content.find(match) - 500)
                context_end = min(len(content), content.find(match) + 500)
                context = content[context_start:context_end]
                
                if not any(val in context for val in validation_methods):
                    results['vulnerable_patterns'].append({
                        'pattern': match,
                        'description': description
                    })
    
    return results


def analyze_views_directory(views_dir):
    """Analyze all Python files in views directory."""
    results = []
    
    for filepath in Path(views_dir).glob('**/*.py'):
        if filepath.name.startswith('__'):
            continue
        
        result = check_file(filepath)
        results.append(result)
    
    return results


def print_summary(results):
    """Print security analysis summary."""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}WORK ORDER SECURITY VERIFICATION REPORT{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")
    
    total_files = len(results)
    files_with_security = sum(1 for r in results if r['has_security_service'])
    files_with_login = sum(1 for r in results if r['has_login_required'])
    
    print(f"📁 Total files analyzed: {total_files}")
    print(f"🔒 Files using LoginRequiredMixin: {files_with_login}")
    print(f"🛡️  Files using WorkOrderSecurityService: {files_with_security}")
    print()
    
    # Analyze each file
    for result in results:
        filename = os.path.basename(result['file'])
        
        print(f"\n{BLUE}{'─'*80}{RESET}")
        print(f"{YELLOW}File: {filename}{RESET}")
        print(f"{BLUE}{'─'*80}{RESET}")
        
        # Security features
        features = []
        if result['has_login_required']:
            features.append(f"{GREEN}✓ LoginRequiredMixin{RESET}")
        if result['has_security_service']:
            features.append(f"{GREEN}✓ WorkOrderSecurityService{RESET}")
        if result['has_permission_denied']:
            features.append(f"{GREEN}✓ PermissionDenied handling{RESET}")
        if result['has_validate_access']:
            features.append(f"{GREEN}✓ Access validation{RESET}")
        
        if features:
            print(f"\n{GREEN}Security Features:{RESET}")
            for feature in features:
                print(f"  {feature}")
        
        # Class analysis
        if result['class_security']:
            print(f"\n{YELLOW}Classes:{RESET}")
            for class_name, class_info in result['class_security'].items():
                if class_info['is_view']:
                    status = f"{GREEN}✓ Protected{RESET}" if class_info['is_protected'] else f"{RED}✗ UNPROTECTED{RESET}"
                    print(f"  {class_name}: {status}")
                    if not class_info['has_login_required'] and class_info['is_view']:
                        print(f"    {YELLOW}⚠ Public view - ensure token validation{RESET}")
        
        # Vulnerable patterns
        if result['vulnerable_patterns']:
            print(f"\n{RED}⚠ Potential Security Issues:{RESET}")
            for vuln in result['vulnerable_patterns']:
                print(f"  {RED}✗{RESET} {vuln['description']}")
                print(f"    Pattern: {vuln['pattern'][:80]}...")
        else:
            print(f"\n{GREEN}✓ No obvious security issues detected{RESET}")
    
    print(f"\n{BLUE}{'='*80}{RESET}")
    
    # Overall summary
    total_classes = sum(len(r['class_security']) for r in results)
    protected_classes = sum(
        1 for r in results 
        for class_info in r['class_security'].values() 
        if class_info['is_protected']
    )
    
    total_vulnerabilities = sum(len(r['vulnerable_patterns']) for r in results)
    
    print(f"\n{BLUE}OVERALL SECURITY SCORE{RESET}")
    print(f"{'─'*80}")
    
    if total_classes > 0:
        protection_rate = (protected_classes / total_classes) * 100
        print(f"View Classes: {protected_classes}/{total_classes} protected ({protection_rate:.1f}%)")
    
    print(f"Security Service Integration: {files_with_security}/{total_files} files")
    print(f"Potential Issues: {total_vulnerabilities}")
    
    if total_vulnerabilities == 0 and files_with_security > 0:
        print(f"\n{GREEN}✓ SECURITY FIX VERIFIED: No critical issues detected{RESET}")
        return 0
    elif total_vulnerabilities > 0:
        print(f"\n{YELLOW}⚠ WARNING: {total_vulnerabilities} potential security issues found{RESET}")
        return 1
    else:
        print(f"\n{YELLOW}⚠ INCOMPLETE: Security service not yet integrated{RESET}")
        return 1


def main():
    """Main execution."""
    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    views_dir = project_root / 'apps' / 'work_order_management' / 'views'
    
    if not views_dir.exists():
        print(f"{RED}Error: Views directory not found: {views_dir}{RESET}")
        return 1
    
    print(f"{BLUE}Analyzing views in: {views_dir}{RESET}")
    
    # Analyze views
    results = analyze_views_directory(views_dir)
    
    # Print summary
    exit_code = print_summary(results)
    
    # Additional recommendations
    print(f"\n{BLUE}RECOMMENDATIONS{RESET}")
    print(f"{'─'*80}")
    print(f"1. All authenticated views should use LoginRequiredMixin")
    print(f"2. All public views should validate tokens")
    print(f"3. All work order access should use WorkOrderSecurityService")
    print(f"4. All exceptions should be caught and logged")
    print(f"5. Run comprehensive tests: pytest apps/work_order_management/tests/test_security_service.py")
    print()
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
