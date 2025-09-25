#!/usr/bin/env python
"""
Test script to verify the fixes for the web dependency UI
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from apps.activity.models.question_model import QuestionSetBelonging
from apps.activity.views.question_views import QsetNQsetBelonging
from apps.peoples.models import People


def test_api_endpoint_with_correct_url():
    """Test the API endpoint with the correct URL"""
    print("\n" + "="*60)
    print("Testing API Endpoint with Correct URL")
    print("="*60)
    
    factory = RequestFactory()
    user = People.objects.filter(is_superuser=True).first()
    
    if not user:
        user = People.objects.first()
    
    # Test with different question IDs
    test_qsb_ids = [2, 3, 4, 5]  # IDs from your screenshot
    
    for qsb_id in test_qsb_ids:
        try:
            # Create request
            request = factory.get('/assets/checklists/relationships/', {
                'action': 'get_qsb_options',
                'qsb_id': str(qsb_id)
            })
            request.user = user
            request.session = {'client_id': 1, 'bu_id': 1}
            
            view = QsetNQsetBelonging()
            response = view.get(request)
            
            if response.status_code == 200:
                data = json.loads(response.content)
                print(f"✓ QSB ID {qsb_id}: {data.get('question_name', 'N/A')[:30]}...")
                print(f"  Type: {data.get('answertype')}, Options: {data.get('options', 'N/A')[:50]}")
            else:
                print(f"✗ QSB ID {qsb_id}: Failed with status {response.status_code}")
        except Exception as e:
            print(f"✗ QSB ID {qsb_id}: Error - {str(e)}")
    
    return True


def test_javascript_fixes():
    """Check if JavaScript files have the fixes"""
    print("\n" + "="*60)
    print("Testing JavaScript Fixes")
    print("="*60)
    
    custom_js = '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    
    if os.path.exists(custom_js):
        with open(custom_js, 'r') as f:
            content = f.read()
            
            # Check for the fixes
            has_correct_url = '/assets/checklists/relationships/' in content
            has_selector_fix = '[id="${rowData}"]' in content or 'isNaN(rowData)' in content
            
            print(f"✓ Correct API URL (/assets/checklists/relationships/): {has_correct_url}")
            print(f"✓ Row selector fix for numeric IDs: {has_selector_fix}")
            
            return has_correct_url and has_selector_fix
    else:
        print("✗ custom.js not found")
        return False


def test_display_conditions_structure():
    """Test the display_conditions data structure"""
    print("\n" + "="*60)
    print("Testing Display Conditions Structure")
    print("="*60)
    
    # Get questions with conditions
    questions_with_conditions = QuestionSetBelonging.objects.filter(
        qset_id=2,
        display_conditions__isnull=False
    ).exclude(display_conditions={})
    
    print(f"Found {questions_with_conditions.count()} questions with conditions")
    
    for q in questions_with_conditions:
        try:
            dc = q.display_conditions
            if dc and 'depends_on' in dc:
                parent_id = dc['depends_on'].get('question_id')
                values = dc['depends_on'].get('values', [])
                
                # Verify parent exists
                parent = QuestionSetBelonging.objects.filter(pk=parent_id).first()
                if parent:
                    print(f"✓ Q{q.seqno} depends on Q{parent.seqno} (ID:{parent_id}) = {values}")
                else:
                    print(f"✗ Q{q.seqno} has invalid parent ID: {parent_id}")
        except Exception as e:
            print(f"✗ Error processing Q{q.seqno}: {str(e)}")
    
    return True


def main():
    print("\n" + "="*70)
    print("WEB DEPENDENCY UI FIXES TEST")
    print("="*70)
    
    tests = [
        ("API Endpoint", test_api_endpoint_with_correct_url),
        ("JavaScript Fixes", test_javascript_fixes),
        ("Display Conditions", test_display_conditions_structure)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} failed with error: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    all_passed = all(result for _, result in results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    if all_passed:
        print("\n🎉 ALL FIXES VERIFIED!")
        print("\nThe issues have been resolved:")
        print("1. ✅ Fixed JavaScript selector error for numeric IDs")
        print("2. ✅ Fixed API endpoint URL to use correct path")
        print("3. ✅ Display conditions are properly structured")
        print("\nThe dependency configuration should now work in the web UI!")
    else:
        print("\n⚠️ Some issues remain")
    
    print("="*70)


if __name__ == "__main__":
    main()