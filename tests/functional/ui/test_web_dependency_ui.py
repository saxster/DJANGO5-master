#!/usr/bin/env python
"""
Test script to verify the web interface for question dependency configuration
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from apps.activity.models.question_model import QuestionSetBelonging, QuestionSet
from apps.activity.forms.question_form import QsetBelongingForm
from apps.peoples.models import People


def test_form_dependency_fields():
    """Test that the form includes dependency fields"""
    print("\n" + "="*60)
    print("Testing Form Dependency Fields")
    print("="*60)
    
    # Get a questionset and belonging for testing
    qsb = QuestionSetBelonging.objects.filter(qset_id=2, seqno=2).first()
    
    if qsb:
        # Create form instance
        form = QsetBelongingForm(instance=qsb)
        
        # Check if dependency fields exist
        has_depends_on = 'depends_on' in form.fields
        has_depends_on_value = 'depends_on_value' in form.fields
        
        print(f"✓ depends_on field present: {has_depends_on}")
        print(f"✓ depends_on_value field present: {has_depends_on_value}")
        
        # Check if fields are properly initialized
        if has_depends_on:
            choices = form.fields['depends_on'].choices
            print(f"✓ depends_on has {len(choices)} choices")
            
        if has_depends_on_value:
            print(f"✓ depends_on_value field configured")
            
        return has_depends_on and has_depends_on_value
    else:
        print("❌ No test data found")
        return False


def test_api_endpoint():
    """Test the API endpoint for fetching question options"""
    print("\n" + "="*60)
    print("Testing API Endpoint")
    print("="*60)
    
    factory = RequestFactory()
    user = People.objects.filter(is_superuser=True).first()
    
    if not user:
        user = People.objects.first()
    
    # Test the get_qsb_options endpoint
    qsb = QuestionSetBelonging.objects.filter(qset_id=2, seqno=1).first()
    
    if qsb:
        from apps.activity.views.question_views import QsetNQsetBelonging
        
        request = factory.get('/assets/checklists/', {
            'action': 'get_qsb_options',
            'qsb_id': str(qsb.pk)
        })
        request.user = user
        request.session = {'client_id': 1, 'bu_id': 1}
        
        view = QsetNQsetBelonging()
        response = view.get(request)
        
        if response.status_code == 200:
            data = json.loads(response.content)
            print(f"✓ API endpoint working")
            print(f"  - Answer type: {data.get('answertype')}")
            print(f"  - Options: {data.get('options')}")
            print(f"  - Question: {data.get('question_name')[:50]}...")
            return True
        else:
            print(f"❌ API failed with status: {response.status_code}")
            return False
    else:
        print("❌ No test data found")
        return False


def test_save_dependency():
    """Test saving dependency data"""
    print("\n" + "="*60)
    print("Testing Save Dependency")
    print("="*60)
    
    factory = RequestFactory()
    user = People.objects.filter(is_superuser=True).first()
    
    if not user:
        user = People.objects.first()
    
    # Get test questions
    parent_q = QuestionSetBelonging.objects.filter(qset_id=2, seqno=1).first()
    dependent_q = QuestionSetBelonging.objects.filter(qset_id=2, seqno=2).first()
    
    if parent_q and dependent_q:
        from apps.activity.views.question_views import QsetNQsetBelonging
        
        # Prepare POST data with dependency
        post_data = {
            'action': 'edit',
            'pk': str(dependent_q.pk),
            'parent_id': str(dependent_q.qset_id),
            'question_id': str(dependent_q.question_id),
            'answertype': dependent_q.answertype,
            'min': str(dependent_q.min or 0),
            'max': str(dependent_q.max or 0),
            'options': dependent_q.options or '',
            'alerton': dependent_q.alerton or '',
            'ismandatory': 'true' if dependent_q.ismandatory else 'false',
            'isavpt': 'true' if dependent_q.isavpt else 'false',
            'avpttype': dependent_q.avpttype or 'NONE',
            'seqno': str(dependent_q.seqno),
            'ctzoffset': '-330',
            'question': 'true',
            'display_conditions': json.dumps({
                'depends_on': {
                    'question_id': parent_q.pk,
                    'operator': 'EQUALS',
                    'values': ['Yes']
                },
                'show_if': True,
                'cascade_hide': False,
                'group': 'test_group'
            })
        }
        
        request = factory.post('/assets/checklists/', post_data)
        request.user = user
        request.session = {
            'client_id': 1,
            'bu_id': 1,
            'assignedsites': [1]
        }
        
        view = QsetNQsetBelonging()
        response = view.post(request)
        
        if response.status_code == 200:
            # Reload the question to check if display_conditions was saved
            dependent_q.refresh_from_db()
            
            if dependent_q.display_conditions:
                print(f"✓ Dependency saved successfully")
                print(f"  - Depends on question ID: {dependent_q.display_conditions['depends_on']['question_id']}")
                print(f"  - Operator: {dependent_q.display_conditions['depends_on']['operator']}")
                print(f"  - Values: {dependent_q.display_conditions['depends_on']['values']}")
                return True
            else:
                print("❌ display_conditions not saved")
                return False
        else:
            print(f"❌ Save failed with status: {response.status_code}")
            return False
    else:
        print("❌ No test data found")
        return False


def test_javascript_files():
    """Check if JavaScript files are in place"""
    print("\n" + "="*60)
    print("Testing JavaScript Files")
    print("="*60)
    
    js_files = [
        '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/js/question_dependency.js',
        '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    ]
    
    all_present = True
    for js_file in js_files:
        if os.path.exists(js_file):
            print(f"✓ {os.path.basename(js_file)} exists")
        else:
            print(f"❌ {os.path.basename(js_file)} missing")
            all_present = False
    
    # Check if custom.js has the updated functions
    custom_js = '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    if os.path.exists(custom_js):
        with open(custom_js, 'r') as f:
            content = f.read()
            has_dependency_fields = 'depends_on' in content and 'depends_on_value' in content
            has_init_function = 'initializeDependencyFields' in content
            
            print(f"✓ Dependency fields in editorFieldsConfig: {has_dependency_fields}")
            print(f"✓ initializeDependencyFields function: {has_init_function}")
    
    return all_present


def main():
    print("\n" + "="*70)
    print("WEB INTERFACE DEPENDENCY CONFIGURATION TEST")
    print("="*70)
    
    tests = [
        ("Form Fields", test_form_dependency_fields),
        ("API Endpoint", test_api_endpoint),
        ("Save Functionality", test_save_dependency),
        ("JavaScript Files", test_javascript_files)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {str(e)}")
            results.append((test_name, False))
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    all_passed = all(result for _, result in results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe web interface for dependency configuration is ready!")
        print("\nHow to use:")
        print("1. Go to Question Set Form (/assets/checklists/?action=form&id=2)")
        print("2. Click 'Edit' on any question")
        print("3. You'll see 'Depends On' and 'When Value Is' fields")
        print("4. Select a parent question and the trigger value")
        print("5. Save to apply the dependency")
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("Please check the errors above")
    
    print("="*70)


if __name__ == "__main__":
    main()