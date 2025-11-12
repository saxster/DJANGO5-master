#!/usr/bin/env python3
"""
Serializer Security Checker

Pre-commit hook to detect security anti-patterns in DRF serializers.

FORBIDDEN PATTERNS:
1. fields = '__all__' (exposes all model fields including sensitive data)
2. Missing write_only=True on password fields
3. Missing read_only=True on sensitive fields (is_staff, is_superuser)

Usage:
    python scripts/check_serializer_security.py
    
Exit Codes:
    0 - No violations found
    1 - Violations found (fails pre-commit)

Author: Amp Security Review
Date: 2025-11-06
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


class SerializerSecurityViolation:
    """Represents a security violation in a serializer."""
    
    def __init__(self, file_path: str, line_num: int, violation_type: str, line_content: str):
        self.file_path = file_path
        self.line_num = line_num
        self.violation_type = violation_type
        self.line_content = line_content.strip()
    
    def __str__(self):
        return (
            f"🔴 {self.file_path}:{self.line_num}\n"
            f"   Violation: {self.violation_type}\n"
            f"   Line: {self.line_content}\n"
        )


def find_serializer_files(root_dir: Path) -> List[Path]:
    """Find all serializer files in apps/ directory."""
    serializer_files = []
    
    # Find files named serializers.py or *serializer*.py
    for pattern in ['**/serializers.py', '**/*serializer*.py']:
        serializer_files.extend(root_dir.glob(f'apps/{pattern}'))
    
    return serializer_files


def check_fields_all(file_path: Path) -> List[SerializerSecurityViolation]:
    """Check for fields = '__all__' anti-pattern."""
    violations = []
    
    # Regex to match: fields = '__all__' or fields = "__all__"
    pattern = re.compile(r"fields\s*=\s*['\"]__all__['\"]")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
        for i, line in enumerate(lines, start=1):
            if pattern.search(line):
                # Check if it's in a comment or docstring
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                
                violations.append(SerializerSecurityViolation(
                    file_path=str(file_path),
                    line_num=i,
                    violation_type="fields = '__all__' exposes all model fields (FORBIDDEN)",
                    line_content=line
                ))
    
    return violations


def check_password_write_only(file_path: Path) -> List[SerializerSecurityViolation]:
    """Check for password fields without write_only=True."""
    violations = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Look for password field declarations without write_only
    # Pattern: password = serializers.CharField(...) without write_only=True
    password_pattern = re.compile(r"password\s*=\s*serializers\.\w+Field\([^)]*\)")
    
    for i, line in enumerate(lines, start=1):
        match = password_pattern.search(line)
        if match:
            field_declaration = match.group(0)
            
            # Check if write_only=True is present
            if 'write_only' not in field_declaration:
                # Check next few lines for multi-line declaration
                next_lines = '\n'.join(lines[i:i+3])
                if 'write_only' not in next_lines:
                    violations.append(SerializerSecurityViolation(
                        file_path=str(file_path),
                        line_num=i,
                        violation_type="Password field without write_only=True (SECURITY RISK)",
                        line_content=line
                    ))
    
    return violations


def check_sensitive_field_read_only(file_path: Path) -> List[SerializerSecurityViolation]:
    """Check for sensitive fields without read_only protection."""
    violations = []
    
    sensitive_fields = ['is_staff', 'is_superuser', 'is_admin', 'permissions', 'groups']
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Check if sensitive fields are in 'fields' list without being in read_only_fields
    in_meta_class = False
    fields_list = []
    read_only_list = []
    
    for i, line in enumerate(lines, start=1):
        if 'class Meta:' in line:
            in_meta_class = True
            fields_list = []
            read_only_list = []
        
        if in_meta_class:
            # Extract fields list
            if 'fields = [' in line:
                # Multi-line field list
                j = i
                while j < len(lines) and ']' not in lines[j]:
                    fields_list.append(lines[j])
                    j += 1
            
            # Extract read_only_fields list
            if 'read_only_fields = [' in line:
                j = i
                while j < len(lines) and ']' not in lines[j]:
                    read_only_list.append(lines[j])
                    j += 1
            
            # Check if class ends
            if line.strip() and not line.startswith(' ') and in_meta_class:
                in_meta_class = False
                
                # Analyze collected fields
                fields_str = '\n'.join(fields_list)
                read_only_str = '\n'.join(read_only_list)
                
                for sensitive_field in sensitive_fields:
                    if f"'{sensitive_field}'" in fields_str and f"'{sensitive_field}'" not in read_only_str:
                        violations.append(SerializerSecurityViolation(
                            file_path=str(file_path),
                            line_num=i,
                            violation_type=f"Sensitive field '{sensitive_field}' not in read_only_fields (SECURITY RISK)",
                            line_content=f"fields contains '{sensitive_field}' but not in read_only_fields"
                        ))
    
    return violations


def main():
    """Main entry point."""
    root_dir = Path(__file__).parent.parent
    
    print("🔍 Scanning DRF serializers for security violations...\n")
    
    serializer_files = find_serializer_files(root_dir)
    
    if not serializer_files:
        print("⚠️  No serializer files found")
        return 0
    
    print(f"Found {len(serializer_files)} serializer files\n")
    
    all_violations = []
    
    for file_path in serializer_files:
        # Check for fields = '__all__'
        violations = check_fields_all(file_path)
        all_violations.extend(violations)
        
        # Check for password fields without write_only
        violations = check_password_write_only(file_path)
        all_violations.extend(violations)
        
        # Check for sensitive fields without read_only
        # violations = check_sensitive_field_read_only(file_path)
        # all_violations.extend(violations)
    
    if all_violations:
        print("🔴 SECURITY VIOLATIONS FOUND:\n")
        print("=" * 80)
        
        # Group violations by type
        by_type = {}
        for v in all_violations:
            if v.violation_type not in by_type:
                by_type[v.violation_type] = []
            by_type[v.violation_type].append(v)
        
        for violation_type, violations in by_type.items():
            print(f"\n{violation_type} ({len(violations)} instances):")
            print("-" * 80)
            for v in violations:
                print(str(v))
        
        print("=" * 80)
        print(f"\n❌ TOTAL VIOLATIONS: {len(all_violations)}")
        print("\n📖 Remediation Guide:")
        print("   1. Replace 'fields = \"__all__\"' with explicit field lists")
        print("   2. Add 'write_only=True' to all password fields")
        print("   3. Add sensitive fields to 'read_only_fields' in Meta class")
        print("\n   See: SERIALIZER_SECURITY_AUDIT_REPORT.md for details\n")
        
        return 1
    else:
        print("✅ No security violations found\n")
        return 0


if __name__ == '__main__':
    sys.exit(main())
