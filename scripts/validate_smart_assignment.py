#!/usr/bin/env python
"""
Validate Smart Assignment Implementation

Checks:
1. Model integrity
2. Service functionality
3. Admin registration
4. File compliance with CLAUDE.md
"""

import os
import sys


def validate_files_exist():
    """Check all required files exist."""
    print("✓ Checking files exist...")
    
    files = [
        'apps/peoples/models/agent_skill.py',
        'apps/peoples/admin/skill_admin.py',
        'apps/core/services/smart_assignment_service.py',
        'apps/peoples/migrations/0010_add_agent_skill_model.py',
        'templates/admin/y_helpdesk/ticket/change_form.html',
        'SMART_ASSIGNMENT_IMPLEMENTATION.md',
    ]
    
    for filepath in files:
        if os.path.exists(filepath):
            print(f"  ✅ {filepath}")
        else:
            print(f"  ❌ {filepath} NOT FOUND")
            return False
    
    return True


def validate_file_sizes():
    """Check files comply with CLAUDE.md limits."""
    print("\n✓ Checking file size limits...")
    
    limits = {
        'apps/peoples/models/agent_skill.py': 150,  # Models < 150 lines
        'apps/peoples/admin/skill_admin.py': 100,   # Admin < 100 lines
        'apps/core/services/smart_assignment_service.py': 500,  # Service (no strict limit)
    }
    
    for filepath, max_lines in limits.items():
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                line_count = len(f.readlines())
            
            status = "✅" if line_count <= max_lines else "⚠️"
            print(f"  {status} {filepath}: {line_count} lines (limit: {max_lines})")
        else:
            print(f"  ❌ {filepath} NOT FOUND")
    
    return True


def validate_imports():
    """Check critical imports are correct."""
    print("\n✓ Checking imports...")
    
    # Check model imports
    model_file = 'apps/peoples/models/agent_skill.py'
    if os.path.exists(model_file):
        with open(model_file, 'r') as f:
            content = f.read()
        
        required_imports = [
            'from apps.peoples.models.base_model import BaseModel',
            'from apps.tenants.models import TenantAwareModel',
            'from apps.tenants.managers import TenantAwareManager',
        ]
        
        for imp in required_imports:
            if imp in content:
                print(f"  ✅ {imp}")
            else:
                print(f"  ❌ Missing: {imp}")
                return False
    
    # Check service imports
    service_file = 'apps/core/services/smart_assignment_service.py'
    if os.path.exists(service_file):
        with open(service_file, 'r') as f:
            content = f.read()
        
        required_imports = [
            'from apps.peoples.models import People, AgentSkill',
            'from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS',
        ]
        
        for imp in required_imports:
            if imp in content:
                print(f"  ✅ {imp}")
            else:
                print(f"  ❌ Missing: {imp}")
                return False
    
    return True


def validate_model_features():
    """Check model has required features."""
    print("\n✓ Checking model features...")
    
    model_file = 'apps/peoples/models/agent_skill.py'
    if os.path.exists(model_file):
        with open(model_file, 'r') as f:
            content = f.read()
        
        features = [
            'class AgentSkill',
            'BaseModel',
            'TenantAwareModel',
            'objects = TenantAwareManager()',
            'skill_level',
            'certified',
            'total_handled',
            'avg_completion_time',
            'success_rate',
            'unique_together',
            'class Meta:',
        ]
        
        for feature in features:
            if feature in content:
                print(f"  ✅ {feature}")
            else:
                print(f"  ❌ Missing: {feature}")
                return False
    
    return True


def validate_service_methods():
    """Check service has required methods."""
    print("\n✓ Checking service methods...")
    
    service_file = 'apps/core/services/smart_assignment_service.py'
    if os.path.exists(service_file):
        with open(service_file, 'r') as f:
            content = f.read()
        
        methods = [
            'def suggest_assignee',
            'def auto_assign',
            'def _calculate_agent_score',
            'def _score_skill_match',
            'def _score_availability',
            'def _score_performance',
            'def _score_recent_experience',
            'def _is_on_shift',
            'def _send_assignment_notification',
        ]
        
        for method in methods:
            if method in content:
                print(f"  ✅ {method}")
            else:
                print(f"  ❌ Missing: {method}")
                return False
    
    return True


def validate_admin_integration():
    """Check admin files are updated."""
    print("\n✓ Checking admin integration...")
    
    # Check skill admin
    skill_admin = 'apps/peoples/admin/skill_admin.py'
    if os.path.exists(skill_admin):
        with open(skill_admin, 'r') as f:
            content = f.read()
        
        if '@admin.register(AgentSkill)' in content:
            print(f"  ✅ AgentSkillAdmin registered")
        else:
            print(f"  ❌ AgentSkillAdmin not registered")
            return False
    
    # Check ticket admin
    ticket_admin = 'apps/y_helpdesk/admin.py'
    if os.path.exists(ticket_admin):
        with open(ticket_admin, 'r') as f:
            content = f.read()
        
        if 'SmartAssignmentService' in content:
            print(f"  ✅ SmartAssignmentService imported")
        else:
            print(f"  ❌ SmartAssignmentService not imported")
            return False
        
        if 'assignment_suggestions' in content:
            print(f"  ✅ Assignment suggestions added")
        else:
            print(f"  ❌ Assignment suggestions not added")
            return False
        
        if 'def smart_assign' in content:
            print(f"  ✅ Smart assign action added")
        else:
            print(f"  ❌ Smart assign action not added")
            return False
    
    return True


def main():
    """Run all validations."""
    print("=" * 60)
    print("Smart Assignment Implementation Validation")
    print("=" * 60)
    
    checks = [
        ("Files Exist", validate_files_exist),
        ("File Sizes", validate_file_sizes),
        ("Imports", validate_imports),
        ("Model Features", validate_model_features),
        ("Service Methods", validate_service_methods),
        ("Admin Integration", validate_admin_integration),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(result for _, result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL VALIDATIONS PASSED")
        print("\nNext steps:")
        print("1. Run migrations: python manage.py migrate peoples")
        print("2. Create test agent skills in admin")
        print("3. Test smart assignment on tickets")
        return 0
    else:
        print("❌ SOME VALIDATIONS FAILED")
        print("\nPlease fix the issues above before deploying.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
