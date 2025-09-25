#!/usr/bin/env python
"""
Test script for question conditional logic API
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from apps.activity.models.question_model import QuestionSetBelonging
import json


def test_question_logic(qset_id=2):
    """Test the conditional logic for a questionset"""
    
    print(f"\n{'='*60}")
    print(f"Testing Question Logic for QuestionSet ID: {qset_id}")
    print(f"{'='*60}\n")
    
    # Get questions with logic
    result = QuestionSetBelonging.objects.get_questions_with_logic(qset_id)
    
    print("📋 Questions in QuestionSet:")
    print("-" * 40)
    
    for q in result['questions']:
        print(f"\n{q['seqno']}. {q['quesname']}")
        print(f"   Type: {q['answertype']}")
        if q['options']:
            print(f"   Options: {q['options']}")
        
        if q.get('display_conditions') and q['display_conditions'].get('depends_on'):
            dc = q['display_conditions']
            depends = dc['depends_on']
            print(f"   ⚡ CONDITIONAL: Show if Q{depends['question_seqno']} {depends['operator']} {depends['values']}")
    
    print(f"\n{'='*60}")
    print("📊 Dependency Map:")
    print("-" * 40)
    
    if result['dependency_map']:
        for parent_seqno, dependencies in result['dependency_map'].items():
            print(f"\nQuestion {parent_seqno} controls:")
            for dep in dependencies:
                print(f"  → Question {dep['question_seqno']}: "
                      f"Show if {dep['operator']} {dep['values']}")
    else:
        print("No conditional logic configured")
    
    print(f"\n{'='*60}")
    print("🎯 Simulation: Different Answer Scenarios")
    print("-" * 40)
    
    # Import the utility
    from apps.activity.utils_conditions import QuestionConditionManager
    
    # Scenario 1: Answer "No" to question 1
    print("\n📝 Scenario 1: Answer 'No' to Question 1")
    answers = {1: "No"}
    visible_questions = []
    
    for q in result['questions']:
        if QuestionConditionManager.evaluate_condition(
            q.get('display_conditions', {}),
            answers
        ):
            visible_questions.append(f"Q{q['seqno']}: {q['quesname'][:30]}...")
    
    print(f"Visible questions: {len(visible_questions)}")
    for vq in visible_questions:
        print(f"  ✓ {vq}")
    
    # Scenario 2: Answer "Yes" to question 1
    print("\n📝 Scenario 2: Answer 'Yes' to Question 1")
    answers = {1: "Yes"}
    visible_questions = []
    
    for q in result['questions']:
        if QuestionConditionManager.evaluate_condition(
            q.get('display_conditions', {}),
            answers
        ):
            visible_questions.append(f"Q{q['seqno']}: {q['quesname'][:30]}...")
    
    print(f"Visible questions: {len(visible_questions)}")
    for vq in visible_questions:
        print(f"  ✓ {vq}")
    
    print(f"\n{'='*60}")
    print("✅ Test Complete!")
    print(f"{'='*60}\n")
    
    # Return the raw data for inspection
    return result


if __name__ == "__main__":
    import sys
    qset_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    test_question_logic(qset_id)