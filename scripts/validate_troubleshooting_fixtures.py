#!/usr/bin/env python3
"""
Validate Troubleshooting Guide Fixtures

Validates JSON structure and content of troubleshooting guide fixtures.
"""

import json
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURES_DIR = BASE_DIR / 'apps' / 'help_center' / 'fixtures'

FIXTURES = [
    'troubleshooting_guides_nov_2025.json',
    'troubleshooting_articles_security.json',
    'troubleshooting_articles_performance.json',
    'troubleshooting_articles_code_quality.json',
]

def validate_json_syntax(filepath):
    """Validate JSON syntax."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return True, len(data), None
    except json.JSONDecodeError as e:
        return False, 0, str(e)

def validate_fixture_structure(filepath):
    """Validate fixture structure."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    errors = []
    stats = {
        'categories': 0,
        'articles': 0,
        'tags': 0
    }
    
    for i, item in enumerate(data):
        # Check required keys
        if 'model' not in item:
            errors.append(f"Item {i}: Missing 'model' key")
        if 'pk' not in item:
            errors.append(f"Item {i}: Missing 'pk' key")
        if 'fields' not in item:
            errors.append(f"Item {i}: Missing 'fields' key")
            continue
        
        # Count by model type
        model = item.get('model', '')
        if 'category' in model:
            stats['categories'] += 1
        elif 'article' in model:
            stats['articles'] += 1
        elif 'tag' in model:
            stats['tags'] += 1
        
        # Validate article structure
        if 'article' in model:
            fields = item['fields']
            required = ['title', 'slug', 'summary', 'content', 'category_id', 
                       'difficulty_level', 'status']
            for field in required:
                if field not in fields:
                    errors.append(f"Article {item['pk']}: Missing '{field}' field")
    
    return errors, stats

def main():
    print("=" * 70)
    print("📊 Troubleshooting Guide Fixtures Validation")
    print("=" * 70)
    
    total_items = 0
    total_errors = []
    global_stats = {
        'categories': 0,
        'articles': 0,
        'tags': 0
    }
    
    for fixture in FIXTURES:
        filepath = FIXTURES_DIR / fixture
        
        print(f"\n📄 {fixture}")
        print("-" * 70)
        
        # Check file exists
        if not filepath.exists():
            print(f"  ❌ File not found: {filepath}")
            continue
        
        # Validate JSON syntax
        valid, count, error = validate_json_syntax(filepath)
        if not valid:
            print(f"  ❌ JSON syntax error: {error}")
            continue
        
        print(f"  ✅ JSON syntax valid ({count} items)")
        total_items += count
        
        # Validate structure
        errors, stats = validate_fixture_structure(filepath)
        
        if errors:
            print(f"  ⚠️  Structure issues found:")
            for error in errors[:5]:  # Show first 5
                print(f"     - {error}")
            if len(errors) > 5:
                print(f"     ... and {len(errors) - 5} more")
            total_errors.extend(errors)
        else:
            print(f"  ✅ Structure valid")
        
        # Show stats
        if stats['categories']:
            print(f"  📁 Categories: {stats['categories']}")
            global_stats['categories'] += stats['categories']
        if stats['articles']:
            print(f"  📝 Articles: {stats['articles']}")
            global_stats['articles'] += stats['articles']
        if stats['tags']:
            print(f"  🏷️  Tags: {stats['tags']}")
            global_stats['tags'] += stats['tags']
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)
    print(f"Total items: {total_items}")
    print(f"Categories: {global_stats['categories']}")
    print(f"Articles: {global_stats['articles']}")
    print(f"Tags: {global_stats['tags']}")
    
    if total_errors:
        print(f"\n⚠️  Total errors: {len(total_errors)}")
        print("\nTo fix errors, review the fixture files and ensure:")
        print("  1. All JSON is properly formatted")
        print("  2. All required fields are present")
        print("  3. PKs are unique")
        print("  4. category_id references exist")
    else:
        print("\n✅ All fixtures validated successfully!")
        print("\nTo load fixtures, run:")
        print("  python manage.py load_troubleshooting_guides")
    
    print("=" * 70)

if __name__ == '__main__':
    main()
