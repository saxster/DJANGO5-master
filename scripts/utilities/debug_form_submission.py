#!/usr/bin/env python
"""
Debug form submission issues
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from django.test import RequestFactory
from apps.activity.views.question_views import QsetNQsetBelonging
from apps.peoples.models import People
from apps.activity.models.question_model import QuestionSetBelonging


def simulate_exact_form_submission():
    """Simulate the exact form submission that should happen from the web UI"""
    print("\n" + "="*60)
    print("Simulating Exact Form Submission")
    print("="*60)
    
    factory = RequestFactory()
    user = People.objects.filter(is_superuser=True).first() or People.objects.first()
    
    # Get the exact data for question 5 (Number of labours working)
    question = QuestionSetBelonging.objects.filter(pk=5).first()
    if not question:
        print("❌ Question ID 5 not found")
        return False
    
    print(f"📝 Question to edit: {question.question.quesname}")
    print(f"   Current display_conditions: {question.display_conditions}")
    
    # This should match exactly what the web form sends when you edit question 5
    # to depend on question 2 ("Any Labour Work Going on ?") with value "Yes"
    form_data = {
        'action': 'edit',
        'parent_id': '2',  # QuestionSet ID
        'question': 'true',
        'pk': '5',  # Question to edit
        'question_id': str(question.question.pk) if question.question else '21',
        'answertype': question.answertype,
        'options': question.options or '',
        'min': str(question.min) if question.min else '0.00',
        'max': str(question.max) if question.max else '100.00',
        'ismandatory': str(question.ismandatory).lower(),
        'isavpt': str(question.isavpt).lower(),
        'avpttype': question.avpttype or 'NONE',
        'seqno': str(question.seqno),
        'alerton': f'"{question.alerton}"' if question.alerton else '""',
        'alertbelow': '',
        'alertabove': '',
        'ctzoffset': '-1',
        'display_conditions': json.dumps({
            "depends_on": {
                "question_id": 2,  # Depends on question ID 2 
                "operator": "EQUALS",
                "values": ["Yes"]
            },
            "show_if": True,
            "cascade_hide": False,
            "group": None
        }),
        'csrfmiddlewaretoken': 'test-token'
    }
    
    print("\n📤 Form data being sent:")
    for key, value in form_data.items():
        if key == 'display_conditions':
            print(f"   {key}: {value}")
        else:
            print(f"   {key}: {value}")
    
    # Create request
    request = factory.post('/assets/checklists/relationships/', form_data)
    request.user = user
    request.session = {'client_id': 1, 'bu_id': 1}
    
    try:
        # Call the view
        view = QsetNQsetBelonging()
        response = view.post(request)
        
        print(f"\n📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                response_data = json.loads(response.content)
                print(f"✅ Response data: {response_data}")
            except:
                print(f"📄 Response content: {response.content.decode()[:200]}")
        else:
            print(f"❌ Error response: {response.content.decode()[:300]}")
            
        # Check if the database was updated
        updated_question = QuestionSetBelonging.objects.filter(pk=5).first()
        print(f"\n📝 After submission:")
        print(f"   display_conditions: {updated_question.display_conditions}")
        
        if updated_question.display_conditions and updated_question.display_conditions.get('depends_on'):
            print("✅ Dependency was saved!")
            return True
        else:
            print("❌ Dependency was NOT saved")
            return False
            
    except Exception as e:
        print(f"❌ Exception during form submission: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def check_question_data():
    """Check the exact question data for debugging"""
    print("\n" + "="*60)
    print("Question Data Analysis")
    print("="*60)
    
    questions = QuestionSetBelonging.objects.filter(qset_id=2).order_by('seqno')
    
    for q in questions:
        print(f"\nQuestion ID {q.pk}:")
        print(f"  Name: {q.question.quesname if q.question else 'None'}")
        print(f"  Question FK: {q.question.pk if q.question else 'None'}")
        print(f"  Answer Type: {q.answertype}")
        print(f"  Sequence: {q.seqno}")
        print(f"  Min/Max: {q.min}/{q.max}")
        print(f"  Options: {q.options}")
        print(f"  Dependencies: {q.display_conditions}")


def main():
    print("\n" + "="*70)
    print("DEBUG FORM SUBMISSION")
    print("="*70)
    
    check_question_data()
    simulate_exact_form_submission()


if __name__ == "__main__":
    main()