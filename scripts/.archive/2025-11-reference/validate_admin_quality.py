#!/usr/bin/env python
"""
Admin Quality Validation Script

Validates that all Django admin classes follow IntelliWiz enhancement guidelines.

Usage:
    python scripts/validate_admin_quality.py
    python scripts/validate_admin_quality.py --report ADMIN_QUALITY_REPORT.md

Author: Claude Code
Date: 2025-10-12
"""
import django
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.contrib import admin
from collections import defaultdict


def validate_admin_quality():
    """
    Validate all registered admin classes against enhancement guidelines.

    Returns:
        tuple: (total_admins, issues, compliant_admins)
    """
    total_admins = len(admin.site._registry)
    issues = defaultdict(list)
    compliant_count = 0

    for model, model_admin in admin.site._registry.items():
        model_name = f"{model._meta.app_label}.{model.__name__}"
        admin_class = model_admin.__class__.__name__

        # Check 1: search_fields
        if not hasattr(model_admin, 'search_fields') or not model_admin.search_fields:
            issues[model_name].append("❌ Missing search_fields")
        else:
            if len(model_admin.search_fields) < 2:
                issues[model_name].append("⚠️  search_fields has < 2 fields (add more)")

        # Check 2: list_filter
        if not hasattr(model_admin, 'list_filter') or not model_admin.list_filter:
            issues[model_name].append("⚠️  Missing list_filter (consider adding)")

        # Check 3: list_select_related (for performance)
        has_fk_in_display = False
        if hasattr(model_admin, 'list_display'):
            for field_name in model_admin.list_display:
                if not callable(field_name):
                    try:
                        field = model._meta.get_field(field_name)
                        if field.many_to_one:  # ForeignKey
                            has_fk_in_display = True
                            break
                    except Exception:
                        pass

        if has_fk_in_display:
            if not hasattr(model_admin, 'list_select_related') or not model_admin.list_select_related:
                issues[model_name].append("⚠️  ForeignKey in list_display but no list_select_related (performance issue)")

        # Check 4: actions (bulk operations)
        default_actions = {'delete_selected'}  # Django default
        admin_actions = set(getattr(model_admin, 'actions', []))
        custom_actions = admin_actions - default_actions

        if not custom_actions:
            issues[model_name].append("💡 No custom actions (consider adding bulk_enable, export_to_csv)")

        # Count as compliant if no critical issues
        critical_issues = [i for i in issues[model_name] if i.startswith('❌')]
        if not critical_issues:
            compliant_count += 1

    return total_admins, issues, compliant_count


def print_report(total, issues, compliant):
    """Print validation report to console"""
    print("\n" + "="*80)
    print("  IntelliWiz Admin Quality Validation Report")
    print("="*80)
    print(f"\n📊 Summary:")
    print(f"   Total admin classes: {total}")
    print(f"   Fully compliant: {compliant} ({compliant/total*100:.1f}%)")
    print(f"   With issues: {len(issues)} ({len(issues)/total*100:.1f}%)")

    # Compliance score
    compliance_score = compliant / total * 100
    if compliance_score >= 90:
        status = "✅ EXCELLENT"
    elif compliance_score >= 75:
        status = "✓ GOOD"
    elif compliance_score >= 50:
        status = "⚠️  NEEDS IMPROVEMENT"
    else:
        status = "❌ POOR"

    print(f"\n🎯 Compliance Score: {compliance_score:.1f}% - {status}\n")

    # Details
    if issues:
        print("="*80)
        print("  Issues Found (by model)")
        print("="*80 + "\n")

        for model_name, model_issues in sorted(issues.items()):
            print(f"📦 {model_name}")
            for issue in model_issues:
                print(f"   {issue}")
            print()

    # Recommendations
    print("="*80)
    print("  Recommendations")
    print("="*80)
    print("""
    Priority 1 (Critical - Fix Now):
    - Add search_fields to all models (❌ issues)

    Priority 2 (Important - This Week):
    - Add list_filter for better UX (⚠️  issues)
    - Add list_select_related for performance (⚠️  issues)

    Priority 3 (Nice to Have - This Month):
    - Add custom bulk actions (💡 issues)
    - Add display decorators and badges
    - Organize fieldsets

    See docs/ADMIN_ENHANCEMENT_GUIDE.md for detailed patterns.
    """)


def write_markdown_report(total, issues, compliant, filename):
    """Write validation report to markdown file"""
    with open(filename, 'w') as f:
        f.write("# Admin Quality Validation Report\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- **Total admin classes**: {total}\n")
        f.write(f"- **Fully compliant**: {compliant} ({compliant/total*100:.1f}%)\n")
        f.write(f"- **With issues**: {len(issues)} ({len(issues)/total*100:.1f}%)\n\n")

        f.write("## Issues by Model\n\n")
        for model_name, model_issues in sorted(issues.items()):
            f.write(f"### {model_name}\n\n")
            for issue in model_issues:
                f.write(f"- {issue}\n")
            f.write("\n")


if __name__ == '__main__':
    from datetime import datetime

    # Run validation
    total, issues, compliant = validate_admin_quality()

    # Print to console
    print_report(total, issues, compliant)

    # Write markdown if requested
    if '--report' in sys.argv:
        try:
            idx = sys.argv.index('--report')
            filename = sys.argv[idx + 1]
            write_markdown_report(total, issues, compliant, filename)
            print(f"\n✅ Report written to: {filename}\n")
        except IndexError:
            print("❌ Error: --report requires filename")
            sys.exit(1)

    # Exit code based on compliance
    sys.exit(0 if compliant == total else 1)
