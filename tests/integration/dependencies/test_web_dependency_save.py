#!/usr/bin/env python
"""
Test script to verify that web form submissions save dependencies correctly
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from django.test import Client
from django.contrib.auth import authenticate
from apps.activity.models.question_model import QuestionSetBelonging
from apps.peoples.models import People


def test_web_form_submission():
    """Test web form submission with dependency data"""
    print("\n" + "="*60)
    print("Testing Web Form Submission")
    print("="*60)
    
    # Get or create a test user
    user = People.objects.filter(is_superuser=True).first()
    if not user:
        user = People.objects.first()
    
    if not user:
        print("❌ No users found in database")
        return False
    
    # Create a test client and login
    client = Client()
    
    # Since we can't easily login with the test client without passwords,
    # let's simulate the exact form data that would be sent
    
    # First, clear any existing dependency from question 5
    question = QuestionSetBelonging.objects.filter(pk=5).first()
    if question:
        question.display_conditions = {}
        question.save()
        print(f"📝 Cleared existing dependencies from: {question.question.quesname if question.question else 'Question 5'}")
    
    # Simulate the form data that would be sent when editing question 5
    # to depend on question 2 with value "Yes"
    form_data = {
        'action': 'edit',
        'parent_id': '2',  # QuestionSet ID
        'question': 'true',
        'pk': '5',  # Question ID to edit
        'question_id': '21',  # The actual question_id field
        'answertype': 'NUMERIC',
        'options': '',
        'min': '0.00',
        'max': '100.00',
        'ismandatory': 'true',
        'isavpt': 'false',
        'avpttype': 'NONE',
        'seqno': '4',
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
    
    # Make a POST request to the endpoint
    try:
        # Set session data
        session = client.session
        session['client_id'] = 1
        session['bu_id'] = 1
        session.save()
        
        # Force login the user
        client.force_login(user)
        
        response = client.post('/assets/checklists/relationships/', form_data)
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            # Check if the dependency was saved
            updated_question = QuestionSetBelonging.objects.filter(pk=5).first()
            print(f"📝 Updated question: {updated_question.question.quesname if updated_question.question else 'Question 5'}")
            print(f"   Display conditions: {updated_question.display_conditions}")
            
            if updated_question.display_conditions and updated_question.display_conditions.get('depends_on'):
                depends_on = updated_question.display_conditions['depends_on']
                parent_id = depends_on.get('question_id')
                values = depends_on.get('values', [])
                print(f"✅ Dependency saved: Question 5 depends on Question ID {parent_id} = {values}")
                return True
            else:
                print("❌ Dependency not saved")
                return False
        else:
            print(f"❌ Request failed with status {response.status_code}")
            if hasattr(response, 'content'):
                print(f"   Response: {response.content.decode()[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ Error in web form submission: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def verify_current_dependencies():
    """Check current dependencies in the database"""
    print("\n" + "="*60)
    print("Current Dependencies in Database")
    print("="*60)
    
    questions = QuestionSetBelonging.objects.filter(qset_id=2).order_by('seqno')
    
    for q in questions:
        question_name = q.question.quesname if q.question else f"Question {q.pk}"
        if q.display_conditions and q.display_conditions.get('depends_on'):
            depends_on = q.display_conditions['depends_on']
            parent_id = depends_on.get('question_id')
            values = depends_on.get('values', [])
            print(f"📋 {question_name} (ID:{q.pk}) depends on ID:{parent_id} = {values}")
        else:
            print(f"📋 {question_name} (ID:{q.pk}) - No dependencies")
    
    return True


def main():
    print("\n" + "="*70)
    print("WEB DEPENDENCY SAVE TEST")
    print("="*70)
    
    tests = [
        ("Current Dependencies", verify_current_dependencies),
        ("Web Form Submission", test_web_form_submission),
        ("Final Dependencies", verify_current_dependencies)
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