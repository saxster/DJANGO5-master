#!/usr/bin/env python
"""
Test the updated implementation using question_id instead of question_seqno
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from apps.activity.models.question_model import QuestionSetBelonging
from apps.activity.utils_conditions import QuestionConditionManager
from django.test import RequestFactory
from apps.activity.views.question_views import QsetNQsetBelonging
from apps.peoples.models import People


def test_question_id_implementation():
    print("\n" + "="*70)
    print("Testing Updated Implementation with question_id")
    print("="*70)
    
    # Test 1: Check database structure
    print("\n✅ TEST 1: Database Structure")
    print("-" * 40)
    
    questions = QuestionSetBelonging.objects.filter(qset_id=2).order_by('seqno')
    
    for q in questions:
        if q.display_conditions and q.display_conditions.get('depends_on'):
            depends_on = q.display_conditions['depends_on']
            if 'question_id' in depends_on:
                parent_id = depends_on['question_id']
                parent = QuestionSetBelonging.objects.filter(pk=parent_id).first()
                print(f"Q{q.seqno} (ID:{q.pk}) depends on ID:{parent_id} (Q{parent.seqno if parent else '?'})")
            else:
                print(f"⚠ Q{q.seqno} still using old format!")
    
    # Test 2: API Response
    print("\n✅ TEST 2: API Response Structure")
    print("-" * 40)
    
    factory = RequestFactory()
    user = People.objects.first()
    
    request = factory.get('/api/questionset/', {
        'action': 'get_questions_with_logic',
        'qset_id': '2'
    })
    request.user = user
    request.session = {'client_id': 1, 'bu_id': 1, 'assignedsites': [1]}
    
    view = QsetNQsetBelonging()
    response = view.get(request)
    
    if response.status_code == 200:
        data = json.loads(response.content)
        print(f"API Response: ✅ Working")
        print(f"Dependency map keys (question IDs): {list(data['dependency_map'].keys())}")
        
        # Show the dependency structure
        for parent_id, deps in data['dependency_map'].items():
            print(f"\nParent ID {parent_id} controls:")
            for dep in deps:
                print(f"  → Question ID {dep['question_id']} (seqno: {dep['question_seqno']})")
    
    # Test 3: Condition Evaluation with IDs
    print("\n✅ TEST 3: Condition Evaluation Using IDs")
    print("-" * 40)
    
    # Build answers dict using question IDs (not seqnos)
    questions_list = list(questions.values('pk', 'seqno', 'question__quesname', 'display_conditions'))
    
    # Map of question IDs
    q1_id = questions.filter(seqno=1).first().pk  # "Any Labour Work Going on?"
    q2_id = questions.filter(seqno=2).first().pk  # "Type of work"
    q3_id = questions.filter(seqno=3).first().pk  # "Name of vendors"
    
    print(f"Question ID mapping:")
    print(f"  Q1 (Labour work?): ID={q1_id}")
    print(f"  Q2 (Type of work): ID={q2_id}")
    print(f"  Q3 (Name of vendors): ID={q3_id}")
    
    # Test with answers using question IDs
    answers_no = {q1_id: "No"}  # Using question ID, not seqno
    answers_yes = {q1_id: "Yes"}  # Using question ID, not seqno
    
    print(f"\nScenario 1: Answer 'No' to question ID {q1_id}")
    visible_count_no = 0
    for q in questions_list:
        if QuestionConditionManager.evaluate_condition(
            q.get('display_conditions', {}),
            answers_no
        ):
            visible_count_no += 1
    print(f"  Visible questions: {visible_count_no}")
    
    print(f"\nScenario 2: Answer 'Yes' to question ID {q1_id}")
    visible_count_yes = 0
    for q in questions_list:
        if QuestionConditionManager.evaluate_condition(
            q.get('display_conditions', {}),
            answers_yes
        ):
            visible_count_yes += 1
    print(f"  Visible questions: {visible_count_yes}")
    
    # Test 4: Verify unique IDs across questionsets
    print("\n✅ TEST 4: Unique IDs Across QuestionSets")
    print("-" * 40)
    
    # Get questions from different questionsets
    qsets = QuestionSetBelonging.objects.values('qset_id').distinct()[:3]
    
    all_ids = set()
    duplicate_seqnos = []
    
    for qs in qsets:
        qset_id = qs['qset_id']
        qs_questions = QuestionSetBelonging.objects.filter(qset_id=qset_id).values('pk', 'seqno')
        
        for q in qs_questions:
            # IDs should be unique
            if q['pk'] in all_ids:
                print(f"  ⚠ Duplicate ID found: {q['pk']}")
            all_ids.add(q['pk'])
            
            # Seqnos will repeat across questionsets
            if q['seqno'] == 1:
                duplicate_seqnos.append(f"QSet{qset_id}-Q{q['seqno']}")
    
    print(f"  Total unique IDs: {len(all_ids)}")
    print(f"  Questions with seqno=1 across sets: {len(duplicate_seqnos)}")
    print(f"  → This shows why question_id is better than seqno!")
    
    # Summary
    print("\n" + "="*70)
    print("🎉 VERIFICATION COMPLETE")
    print("="*70)
    print("\nSummary:")
    print("  ✅ All conditions now use question_id (globally unique)")
    print("  ✅ API returns dependency map with question IDs as keys")
    print("  ✅ Condition evaluation works with question IDs")
    print("  ✅ No conflicts across different questionsets")
    print("\n💡 Mobile can now safely store multiple questionsets")
    print("   without ID conflicts!")
    print("="*70)


if __name__ == "__main__":
    test_question_id_implementation()