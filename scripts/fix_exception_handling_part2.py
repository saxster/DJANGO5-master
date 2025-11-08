#!/usr/bin/env python3
"""
Exception Handling Remediation Part 2: Batch Fixer
Fixes broad exception handlers in helpdesk, reports, and inventory apps.
"""

import os
import re
import sys
from pathlib import Path

# File paths to fix
FILES_TO_FIX = [
    # Helpdesk management commands
    "apps/y_helpdesk/management/commands/analyze_ticket_performance.py",
    "apps/y_helpdesk/management/commands/warm_ticket_cache.py",
    "apps/y_helpdesk/management/commands/generate_security_report.py",
    "apps/y_helpdesk/middleware/ticket_security_middleware.py",
    
    # Reports services
    "apps/reports/services/frappe_service.py",
    "apps/reports/services/report_export_service.py",
    "apps/reports/services/report_generation_service.py",
    "apps/reports/services/data_export_service.py",
    "apps/reports/services/executive_scorecard_service.py",
    "apps/reports/services/report_template_service.py",
    "apps/reports/tasks.py",
]

# Common exception patterns per context
EXCEPTION_PATTERNS = {
    'database': 'DATABASE_EXCEPTIONS',
    'network': 'NETWORK_EXCEPTIONS',
    'file': 'FILE_EXCEPTIONS',
    'json': 'JSON_EXCEPTIONS',
    'parsing': 'PARSING_EXCEPTIONS',
    'business': 'BUSINESS_LOGIC_EXCEPTIONS',
}

def analyze_context(file_path, line_before_except):
    """Determine what exception types to use based on context."""
    line_lower = line_before_except.lower()
    
    # Database operations
    if any(keyword in line_lower for keyword in ['save()', 'create()', 'update()', 'delete()', 'objects.', 'queryset', 'filter(']):
        return ['DATABASE_EXCEPTIONS']
    
    # Network operations
    if any(keyword in line_lower for keyword in ['requests.', 'http', 'api', 'webhook', 'url']):
        return ['NETWORK_EXCEPTIONS', 'JSON_EXCEPTIONS']
    
    # File operations
    if any(keyword in line_lower for keyword in ['open(', 'file', 'path', 'read(', 'write(', 'export', 'csv']):
        return ['FILE_EXCEPTIONS']
    
    # JSON operations
    if any(keyword in line_lower for keyword in ['json.', 'loads', 'dumps', 'parse']):
        return ['JSON_EXCEPTIONS']
    
    # Default to business logic
    return ['BUSINESS_LOGIC_EXCEPTIONS']


def count_exceptions(file_path):
    """Count 'except Exception' patterns in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return len(re.findall(r'except Exception', content))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0


def main():
    project_root = Path(__file__).parent.parent
    
    total_found = 0
    total_files = 0
    
    print("=" * 80)
    print("Exception Handling Remediation Part 2 - Analysis")
    print("=" * 80)
    
    for file_rel in FILES_TO_FIX:
        file_path = project_root / file_rel
        if not file_path.exists():
            print(f"⚠️  File not found: {file_rel}")
            continue
        
        count = count_exceptions(file_path)
        if count > 0:
            total_found += count
            total_files += 1
            print(f"✓ {file_rel}: {count} exception(s)")
    
    print("\n" + "=" * 80)
    print(f"Total: {total_found} broad exceptions in {total_files} files")
    print("=" * 80)
    
    print("\nRecommendation:")
    print("Use Amp's edit_file tool to fix each file with appropriate exception types:")
    print("- Database operations → DATABASE_EXCEPTIONS")
    print("- Network/API calls → NETWORK_EXCEPTIONS + JSON_EXCEPTIONS")
    print("- File operations → FILE_EXCEPTIONS")
    print("- Data parsing → PARSING_EXCEPTIONS")
    print("- Business logic → BUSINESS_LOGIC_EXCEPTIONS")


if __name__ == '__main__':
    main()
