#!/usr/bin/env python3
"""
Test script to validate model imports after refactoring.
This checks that the refactored model structure maintains backward compatibility.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/Users/amar/Desktop/MyCode/DJANGO5-master')

def test_imports():
    """Test that all model imports work correctly."""
    print("Testing model imports after refactoring...")

    try:
        # Test 1: Basic model imports should work
        print("1. Testing basic model imports...")
        from apps.onboarding.models import Bt, Shift, TypeAssist, GeofenceMaster
        print("   ✓ Core business models imported successfully")

        # Test 2: Infrastructure models
        print("2. Testing infrastructure model imports...")
        from apps.onboarding.models import Device, Subscription, DownTimeHistory
        print("   ✓ Infrastructure models imported successfully")

        # Test 3: AI models
        print("3. Testing AI model imports...")
        from apps.onboarding.models import ConversationSession, LLMRecommendation
        print("   ✓ AI models imported successfully")

        # Test 4: Helper functions
        print("4. Testing helper function imports...")
        from apps.onboarding.models import bu_defaults, shiftdata_json
        print("   ✓ Helper functions imported successfully")

        # Test 5: Direct module imports
        print("5. Testing direct module imports...")
        from apps.onboarding.models.business_unit import Bt as BtDirect
        from apps.onboarding.models.scheduling import Shift as ShiftDirect
        print("   ✓ Direct module imports working")

        # Test 6: Check model classes are the same
        print("6. Testing model class consistency...")
        assert Bt == BtDirect, "Bt model classes should be identical"
        assert Shift == ShiftDirect, "Shift model classes should be identical"
        print("   ✓ Model class consistency verified")

        print("\n🎉 ALL TESTS PASSED! Refactoring maintains backward compatibility.")
        return True

    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False
    except AssertionError as e:
        print(f"   ❌ Assertion error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

def validate_file_structure():
    """Validate that all expected files exist."""
    print("\nValidating file structure...")

    base_path = '/Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding'
    expected_files = [
        'models/__init__.py',
        'models/business_unit.py',
        'models/scheduling.py',
        'models/classification.py',
        'models/infrastructure.py',
        'models/conversational_ai.py',
        'models.py',
        'models_original_backup.py',
    ]

    all_exist = True
    for file_path in expected_files:
        full_path = os.path.join(base_path, file_path)
        if os.path.exists(full_path):
            print(f"   ✓ {file_path}")
        else:
            print(f"   ❌ {file_path} - NOT FOUND")
            all_exist = False

    return all_exist

def check_line_counts():
    """Check that all new model files are under the 150-line limit."""
    print("\nChecking file line counts (150-line architectural limit)...")

    base_path = '/Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding/models'
    model_files = [
        'business_unit.py',
        'scheduling.py',
        'classification.py',
        'infrastructure.py',
        'conversational_ai.py',
    ]

    all_compliant = True
    for file_name in model_files:
        file_path = os.path.join(base_path, file_name)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                line_count = len(f.readlines())

            status = "✓" if line_count <= 150 else "❌"
            print(f"   {status} {file_name}: {line_count} lines")

            if line_count > 150:
                all_compliant = False
        else:
            print(f"   ❌ {file_name}: FILE NOT FOUND")
            all_compliant = False

    return all_compliant

if __name__ == "__main__":
    print("=" * 60)
    print("MODEL REFACTORING VALIDATION")
    print("=" * 60)

    # Run all validation checks
    structure_ok = validate_file_structure()
    line_counts_ok = check_line_counts()
    imports_ok = test_imports()

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"File Structure: {'✓ PASS' if structure_ok else '❌ FAIL'}")
    print(f"Line Counts:    {'✓ PASS' if line_counts_ok else '❌ FAIL'}")
    print(f"Import Tests:   {'✓ PASS' if imports_ok else '❌ FAIL'}")

    if structure_ok and line_counts_ok and imports_ok:
        print("\n🎉 REFACTORING VALIDATION SUCCESSFUL!")
        print("The 2,656-line architectural violation has been resolved.")
        exit(0)
    else:
        print("\n❌ REFACTORING VALIDATION FAILED!")
        print("Some issues need to be addressed.")
        exit(1)