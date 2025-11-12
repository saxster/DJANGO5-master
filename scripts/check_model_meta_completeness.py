#!/usr/bin/env python
"""
Check Django models for complete Meta class configuration.
Reports models missing verbose_name, verbose_name_plural, or ordering.
"""
import os
import re
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')

import django
django.setup()

from django.apps import apps


def check_model_meta():
    """Check all models for complete Meta configuration."""
    issues = []
    
    for model in apps.get_models():
        app_label = model._meta.app_label
        model_name = model.__name__
        
        # Skip abstract models
        if model._meta.abstract:
            continue
            
        # Skip proxy models
        if model._meta.proxy:
            continue
        
        meta_issues = []
        
        # Check verbose_name
        if not hasattr(model._meta, 'verbose_name') or model._meta.verbose_name == model_name.lower().replace('_', ' '):
            meta_issues.append('verbose_name')
        
        # Check verbose_name_plural
        if not hasattr(model._meta, 'verbose_name_plural') or model._meta.verbose_name_plural == f"{model_name.lower().replace('_', ' ')}s":
            meta_issues.append('verbose_name_plural')
        
        # Check ordering
        if not hasattr(model._meta, 'ordering') or not model._meta.ordering:
            meta_issues.append('ordering')
        
        if meta_issues:
            issues.append({
                'app': app_label,
                'model': model_name,
                'file': f"{app_label}/models",
                'missing': meta_issues
            })
    
    return issues


def main():
    print("=" * 80)
    print("DJANGO MODEL META COMPLETENESS CHECK")
    print("=" * 80)
    print()
    
    issues = check_model_meta()
    
    if not issues:
        print("✅ All models have complete Meta classes!")
        return 0
    
    print(f"Found {len(issues)} models with incomplete Meta classes:\n")
    
    # Group by app
    by_app = {}
    for issue in issues:
        app = issue['app']
        if app not in by_app:
            by_app[app] = []
        by_app[app].append(issue)
    
    for app, app_issues in sorted(by_app.items()):
        print(f"\n{app.upper()} ({len(app_issues)} models):")
        print("-" * 80)
        for issue in app_issues:
            print(f"  {issue['model']}")
            print(f"    Missing: {', '.join(issue['missing'])}")
            print(f"    File: apps/{issue['file']}")
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: {len(issues)} models need Meta updates")
    print("=" * 80)
    
    return 1


if __name__ == '__main__':
    sys.exit(main())
