#!/usr/bin/env python
"""
Test to help debug JavaScript form submission
"""
import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from apps.activity.models.question_model import QuestionSetBelonging


def check_current_state():
    """Check the current state before and after user testing"""
    print("Current State of Question 5 (Number of labours working):")
    
    question = QuestionSetBelonging.objects.filter(pk=5).first()
    if question:
        print(f"  Name: {question.question.quesname}")
        print(f"  Display Conditions: {question.display_conditions}")
        
        if question.display_conditions and question.display_conditions.get('depends_on'):
            depends_on = question.display_conditions['depends_on']
            parent_id = depends_on.get('question_id')
            values = depends_on.get('values', [])
            print(f"  ✅ HAS DEPENDENCY: Depends on Question ID {parent_id} = {values}")
        else:
            print(f"  ❌ NO DEPENDENCY: display_conditions is empty")
    else:
        print("  ❌ Question not found")


def instructions():
    print("\n" + "="*70)
    print("TESTING INSTRUCTIONS")
    print("n" + "="*70)
    print("\n1. 🔄 Clear browser cache (Ctrl+Shift+R)")
    print("2. 🌐 Go to the question assignment page")
    print("3. ✏️  Edit 'Number of labours working' question")
    print("4. 🎯 Set dependency:")
    print("   - Depends On: Select 'Any Labour Work Going on ?'")
    print("   - When Value Is: Select 'Yes'")
    print("5. 💾 Save the question")
    print("6. 👀 Check browser console for debug messages:")
    print("   - Look for '🔍 Dependency Debug:'")
    print("   - Look for 'dependsOn: 2'")
    print("   - Look for 'dependsOnValue: Yes'")
    print("7. 🔄 Run this script again to check if it was saved")
    print("\nIf you don't see the debug messages, there's a JavaScript issue.")
    print("If you see the messages but it's not saved, there's a backend issue.")


def main():
    print("="*70)
    print("JAVASCRIPT DEBUG TEST")
    print("="*70)
    
    check_current_state()
    instructions()
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()