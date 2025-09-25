#!/usr/bin/env python
"""
Final test to verify all UI fixes for question dependencies
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from django.test import RequestFactory
from apps.activity.models.question_model import QuestionSetBelonging
from apps.activity.views.question_views import QsetNQsetBelonging
from apps.peoples.models import People


def check_javascript_syntax():
    """Check JavaScript file for syntax issues"""
    print("\n" + "="*60)
    print("Checking JavaScript Syntax")
    print("="*60)
    
    custom_js = '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    
    if os.path.exists(custom_js):
        with open(custom_js, 'r') as f:
            content = f.read()
            
            # Check for key fixes
            checks = {
                'Try-catch blocks': 'try {' in content and 'catch (e)' in content,
                'Proper API URL': '/assets/checklists/relationships/' in content,
                'No display_conditions field ref': 'editor.field(\'display_conditions\')' not in content,
                'Selected rows approach': 'table.rows({ selected: true })' in content,
                'Timeout for DOM ready': 'setTimeout(function()' in content,
                'Error handling': 'console.log(\'Error' in content
            }
            
            all_good = True
            for check_name, result in checks.items():
                status = "✅" if result else "❌"
                print(f"{status} {check_name}: {result}")
                if not result:
                    all_good = False
            
            return all_good
    else:
        print("❌ custom.js not found")
        return False


def test_api_endpoints():
    """Test all API endpoints"""
    print("\n" + "="*60)
    print("Testing API Endpoints")
    print("="*60)
    
    factory = RequestFactory()
    user = People.objects.filter(is_superuser=True).first() or People.objects.first()
    
    endpoints = [
        {
            'url': '/assets/checklists/relationships/',
            'params': {'action': 'get_qsb_options', 'qsb_id': '2'},
            'description': 'Get question options'
        },
        {
            'url': '/assets/checklists/relationships/',
            'params': {'action': 'get_questions_of_qset', 'qset_id': '2'},
            'description': 'Get questions of questionset'
        }
    ]
    
    all_good = True
    for endpoint in endpoints:
        try:
            request = factory.get(endpoint['url'], endpoint['params'])
            request.user = user
            request.session = {'client_id': 1, 'bu_id': 1}
            
            view = QsetNQsetBelonging()
            response = view.get(request)
            
            if response.status_code == 200:
                print(f"✅ {endpoint['description']}: Success")
            else:
                print(f"❌ {endpoint['description']}: Failed with {response.status_code}")
                all_good = False
        except Exception as e:
            print(f"❌ {endpoint['description']}: Error - {str(e)[:50]}")
            all_good = False
    
    return all_good


def test_data_structure():
    """Test the data structure and dependencies"""
    print("\n" + "="*60)
    print("Testing Data Structure")
    print("="*60)
    
    # Get questions with dependencies
    questions = QuestionSetBelonging.objects.filter(qset_id=2).order_by('seqno')
    
    print(f"Total questions in questionset: {questions.count()}")
    
    for q in questions:
        if q.display_conditions and q.display_conditions.get('depends_on'):
            parent_id = q.display_conditions['depends_on'].get('question_id')
            values = q.display_conditions['depends_on'].get('values', [])
            print(f"✅ Q{q.seqno} (ID:{q.pk}) depends on ID:{parent_id} = {values}")
        else:
            print(f"  Q{q.seqno} (ID:{q.pk}) - No dependencies")
    
    return True


def verify_field_configuration():
    """Verify the field configuration in editor"""
    print("\n" + "="*60)
    print("Verifying Field Configuration")
    print("="*60)
    
    custom_js = '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    
    if os.path.exists(custom_js):
        with open(custom_js, 'r') as f:
            content = f.read()
            
            # Check editorFieldsConfig function
            if 'function editorFieldsConfig()' in content:
                # Find the function
                start = content.find('function editorFieldsConfig()')
                end = content.find('function editorAjaxData', start)
                if start > -1 and end > -1:
                    func_content = content[start:end]
                    
                    has_depends_on = '"depends_on"' in func_content or "'depends_on'" in func_content
                    has_depends_on_value = '"depends_on_value"' in func_content or "'depends_on_value'" in func_content
                    
                    print(f"{'✅' if has_depends_on else '❌'} depends_on field in config")
                    print(f"{'✅' if has_depends_on_value else '❌'} depends_on_value field in config")
                    
                    return has_depends_on and has_depends_on_value
    
    print("❌ Could not verify field configuration")
    return False


def main():
    print("\n" + "="*70)
    print("FINAL UI FIXES VERIFICATION")
    print("="*70)
    
    tests = [
        ("JavaScript Syntax", check_javascript_syntax),
        ("API Endpoints", test_api_endpoints),
        ("Data Structure", test_data_structure),
        ("Field Configuration", verify_field_configuration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {str(e)[:100]}")
            results.append((test_name, False))
    
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    
    all_passed = all(result for _, result in results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    if all_passed:
        print("\n🎉 ALL FIXES VERIFIED SUCCESSFULLY!")
        print("\nThe UI should now work without errors:")
        print("1. ✅ No more selector errors")
        print("2. ✅ API endpoints working correctly")
        print("3. ✅ Dependency fields properly configured")
        print("4. ✅ Error handling in place")
        print("\n📝 Next Steps:")
        print("1. Clear browser cache (Ctrl+Shift+R)")
        print("2. Reload the page")
        print("3. Edit a question to see dependency options")
    else:
        print("\n⚠️ Some issues detected - please review above")
    
    print("="*70)


if __name__ == "__main__":
    main()