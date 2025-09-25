#!/usr/bin/env python
"""
Test script to debug dependency saving issue
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from django.test import RequestFactory
from django.http import QueryDict
from apps.activity.models.question_model import QuestionSetBelonging
from apps.activity.managers.question_manager import QsetBlngManager
from apps.activity.views.question_views import QsetNQsetBelonging
from apps.peoples.models import People


def test_form_submission():
    """Test form submission with dependency data"""
    print("\n" + "="*60)
    print("Testing Form Submission with Dependencies")
    print("="*60)
    
    factory = RequestFactory()
    user = People.objects.filter(is_superuser=True).first() or People.objects.first()
    
    # Get a question to edit (let's use question ID 3 - Type of work)
    question = QuestionSetBelonging.objects.filter(pk=3).first()
    
    if not question:
        print("❌ Question ID 3 not found")
        return False
    
    print(f"📝 Current question: {question.question.quesname if question.question else 'No question'}")
    print(f"   Current display_conditions: {question.display_conditions}")
    
    # Simulate form data for setting a dependency
    # Question 3 (Type of work) depends on Question 2 (Is there any work going on?) = "Yes"
    form_data = {
        'action': 'edit',  # Required action field
        'parent_id': '2',  # QuestionSet ID
        'question': 'true',
        'pk': '3',  # Question ID to edit
        'question_id': '17',  # The actual question_id field
        'answertype': 'CHECKBOX',
        'options': 'No Work,Electrical,Cleaning,Fabrication,Painting,Civil,Plumbing',
        'min': '0.00',
        'max': '0.00',
        'ismandatory': 'true',
        'isavpt': 'false',
        'avpttype': 'NONE',
        'seqno': '2',
        'alerton': '""',
        'alertbelow': '',
        'alertabove': '',
        'ctzoffset': '-1',
        'display_conditions': json.dumps({
            "depends_on": {
                "question_id": 2,  # Depends on question ID 2 (Is there any work going on?)
                "operator": "EQUALS",
                "values": ["Yes"]
            },
            "show_if": True,
            "cascade_hide": False,
            "group": None
        }),
        'csrfmiddlewaretoken': 'test-token'
    }
    
    # Create POST request
    request = factory.post('/assets/checklists/relationships/', form_data)
    request.user = user
    request.session = {'client_id': 1, 'bu_id': 1}
    
    try:
        # Test the actual view that handles the form submission
        view = QsetNQsetBelonging()
        response = view.post(request)
        print(f"✅ Form processing succeeded - Response: {response.status_code}")
        if response.status_code != 200:
            print(f"   Response content: {response.content}")
            return False
        
        # Now check if the question was actually updated
        updated_question = QuestionSetBelonging.objects.filter(pk=3).first()
        print(f"📝 Updated display_conditions: {updated_question.display_conditions}")
        
        if updated_question.display_conditions and updated_question.display_conditions.get('depends_on'):
            print("✅ Display conditions saved successfully!")
            return True
        else:
            print("❌ Display conditions not saved to database")
            return False
            
    except Exception as e:
        print(f"❌ Error processing form: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_direct_update():
    """Test direct update to verify database field works"""
    print("\n" + "="*60)
    print("Testing Direct Database Update")
    print("="*60)
    
    question = QuestionSetBelonging.objects.filter(pk=4).first()
    
    if not question:
        print("❌ Question ID 4 not found")
        return False
    
    print(f"📝 Question: {question.question.quesname if question.question else 'No question'}")
    print(f"   Before: {question.display_conditions}")
    
    # Set dependency directly
    question.display_conditions = {
        "depends_on": {
            "question_id": 2,
            "operator": "EQUALS", 
            "values": ["Yes"]
        },
        "show_if": True
    }
    
    try:
        question.save()
        print("✅ Direct update succeeded")
        
        # Verify it was saved
        updated = QuestionSetBelonging.objects.filter(pk=4).first()
        print(f"   After: {updated.display_conditions}")
        
        if updated.display_conditions and updated.display_conditions.get('depends_on'):
            print("✅ Direct database update works!")
            return True
        else:
            print("❌ Direct update failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in direct update: {str(e)}")
        return False


def main():
    print("\n" + "="*70)
    print("DEPENDENCY SAVING DEBUG TEST")
    print("="*70)
    
    tests = [
        ("Direct Database Update", test_direct_update),
        ("Form Submission", test_form_submission)
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
    print("TEST RESULTS")
    print("="*70)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print("="*70)


if __name__ == "__main__":
    main()