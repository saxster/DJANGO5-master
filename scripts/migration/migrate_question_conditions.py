#!/usr/bin/env python
"""
Migration script to update display_conditions from question_seqno to question_id
"""
import os
import sys
import django
import json

# Default to development; override with DJANGO_ENV/ DJANGO_SETTINGS_MODULE as needed.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from apps.activity.models.question_model import QuestionSetBelonging


def migrate_conditions():
    """
    Update all display_conditions to use question_id instead of question_seqno
    """
    print("\n" + "="*60)
    print("Migrating display_conditions to use question_id")
    print("="*60)
    
    # Get all records with display conditions
    questions_with_conditions = QuestionSetBelonging.objects.exclude(
        display_conditions__isnull=True
    ).exclude(
        display_conditions={}
    )
    
    print(f"\nFound {questions_with_conditions.count()} questions with conditions")
    
    updated_count = 0
    errors = []
    
    for qsb in questions_with_conditions:
        try:
            if qsb.display_conditions and qsb.display_conditions.get('depends_on'):
                depends_on = qsb.display_conditions['depends_on']
                
                # Check if still using old format (question_seqno)
                if 'question_seqno' in depends_on:
                    parent_seqno = depends_on.pop('question_seqno')
                    
                    # Find the parent question by seqno in the same questionset
                    parent_qsb = QuestionSetBelonging.objects.filter(
                        qset_id=qsb.qset_id,
                        seqno=parent_seqno
                    ).first()
                    
                    if parent_qsb:
                        # Update to use question_id
                        depends_on['question_id'] = parent_qsb.pk
                        qsb.save()
                        updated_count += 1
                        print(f"  ✓ Updated Q{qsb.seqno} (ID:{qsb.pk}) - depends on ID:{parent_qsb.pk} (was seqno:{parent_seqno})")
                    else:
                        errors.append(f"Could not find parent with seqno={parent_seqno} for question ID={qsb.pk}")
                elif 'question_id' in depends_on:
                    print(f"  ⚠ Q{qsb.seqno} (ID:{qsb.pk}) already uses question_id")
                
        except Exception as e:
            errors.append(f"Error processing question ID={qsb.pk}: {str(e)}")
    
    print(f"\n{'='*60}")
    print(f"Migration Results:")
    print(f"  ✓ Updated: {updated_count} records")
    print(f"  ⚠ Already migrated: {questions_with_conditions.count() - updated_count} records")
    
    if errors:
        print(f"  ✗ Errors: {len(errors)}")
        for error in errors[:5]:  # Show first 5 errors
            print(f"    - {error}")
    
    print("="*60)
    
    return updated_count, errors


def verify_migration():
    """
    Verify that all conditions now use question_id
    """
    print("\n" + "="*60)
    print("Verifying Migration")
    print("="*60)
    
    questions_with_conditions = QuestionSetBelonging.objects.exclude(
        display_conditions__isnull=True
    ).exclude(
        display_conditions={}
    )
    
    using_old_format = 0
    using_new_format = 0
    
    for qsb in questions_with_conditions:
        if qsb.display_conditions and qsb.display_conditions.get('depends_on'):
            depends_on = qsb.display_conditions['depends_on']
            if 'question_seqno' in depends_on:
                using_old_format += 1
                print(f"  ⚠ Still using old format: ID={qsb.pk}")
            elif 'question_id' in depends_on:
                using_new_format += 1
    
    print(f"\nResults:")
    print(f"  Using question_id (new): {using_new_format}")
    print(f"  Using question_seqno (old): {using_old_format}")
    
    if using_old_format == 0:
        print(f"\n✅ Migration successful! All conditions use question_id")
    else:
        print(f"\n⚠ Migration incomplete! {using_old_format} records still use question_seqno")
    
    print("="*60)
    
    return using_old_format == 0


if __name__ == "__main__":
    # Run migration
    updated, errors = migrate_conditions()
    
    # Verify
    success = verify_migration()
    
    # Show example
    if success:
        print("\n📋 Example of migrated data:")
        qsb = QuestionSetBelonging.objects.filter(
            qset_id=2,
            seqno=2
        ).first()
        if qsb and qsb.display_conditions:
            print(f"Question: {qsb.question.quesname}")
            print(f"Display conditions: {json.dumps(qsb.display_conditions, indent=2)}")
    
    sys.exit(0 if success else 1)
