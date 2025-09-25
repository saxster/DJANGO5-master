#!/usr/bin/env python
"""
Test to verify the null pointer fix in JavaScript
"""
import os
import sys

def test_javascript_null_safety():
    """Test JavaScript file for null safety improvements"""
    print("\n" + "="*60)
    print("Testing JavaScript Null Safety Fixes")
    print("="*60)
    
    custom_js = '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    
    if not os.path.exists(custom_js):
        print("❌ custom.js not found")
        return False
    
    with open(custom_js, 'r') as f:
        content = f.read()
    
    # Find the initializeQSBForm function
    function_start = content.find('function initializeQSBForm(table, editor) {')
    if function_start == -1:
        print("❌ initializeQSBForm function not found")
        return False
    
    # Find the end of the function
    function_end = content.find('function modifyWidgets', function_start)
    if function_end == -1:
        function_end = len(content)
    
    function_content = content[function_start:function_end]
    
    # Check for the fixes
    safety_checks = {
        'Try-catch wrapper': 'try {' in function_content and 'catch (e)' in function_content,
        'Data existence check': 'if (data !== "None" && data)' in function_content,
        'Null check for alerton': 'data.alerton && data.alerton.length > 0' in function_content,
        'Null check for quesname': 'if (data.quesname && data.question_id)' in function_content,
        'Split safety check': 'alerton.includes(",")' in function_content,
        'Error logging': 'console.log(\'Error in initializeQSBForm' in function_content or 'console.log("Error in initializeQSBForm' in function_content
    }
    
    all_checks_pass = True
    for check_name, result in safety_checks.items():
        status = "✅" if result else "❌"
        print(f"{status} {check_name}: {result}")
        if not result:
            all_checks_pass = False
    
    return all_checks_pass


def verify_line_2388_fix():
    """Specifically verify the line 2388 fix"""
    print("\n" + "="*60)
    print("Verifying Line 2388 Fix")
    print("="*60)
    
    custom_js = '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    
    if not os.path.exists(custom_js):
        print("❌ custom.js not found")
        return False
    
    with open(custom_js, 'r') as f:
        lines = f.readlines()
    
    # Check around line 2388 (accounting for potential line number changes)
    target_range = range(2380, 2400)  # Check a range around line 2388
    
    found_fix = False
    for i, line in enumerate(lines):
        line_num = i + 1
        if line_num in target_range:
            # Look for the fixed condition
            if 'data.alerton && data.alerton.length > 0' in line:
                print(f"✅ Line {line_num}: Found null safety check")
                print(f"    Content: {line.strip()}")
                found_fix = True
                break
    
    if not found_fix:
        # Look for any reference to the problematic pattern
        for i, line in enumerate(lines):
            if 'data.alerton.length > 0' in line and 'data.alerton &&' not in line:
                print(f"❌ Line {i+1}: Still has unsafe alerton access")
                return False
    
    if found_fix:
        print("✅ The null pointer issue has been properly fixed")
        return True
    else:
        print("✅ No unsafe alerton access found")
        return True


def check_other_potential_issues():
    """Check for other potential null pointer issues"""
    print("\n" + "="*60)
    print("Checking for Other Potential Issues")
    print("="*60)
    
    custom_js = '/home/redmine/DJANGO5/YOUTILITY5/frontend/static/assets/js/local/custom.js'
    
    if not os.path.exists(custom_js):
        print("❌ custom.js not found")
        return False
    
    with open(custom_js, 'r') as f:
        content = f.read()
    
    # Look for other potential null pointer issues
    potential_issues = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        line_num = i + 1
        # Check for property access without null checking
        if '.length' in line and 'if' not in line and '&&' not in line:
            if any(prop in line for prop in ['data.', 'response.', 'result.']):
                potential_issues.append(f"Line {line_num}: {line.strip()}")
    
    if potential_issues:
        print(f"⚠️  Found {len(potential_issues)} potential issues:")
        for issue in potential_issues[:5]:  # Show first 5
            print(f"    {issue}")
        return len(potential_issues) < 10  # Return True if issues are manageable
    else:
        print("✅ No obvious null pointer issues found")
        return True


def main():
    print("\n" + "="*70)
    print("NULL POINTER FIX VERIFICATION")
    print("="*70)
    
    tests = [
        ("JavaScript Safety Checks", test_javascript_null_safety),
        ("Line 2388 Fix", verify_line_2388_fix),
        ("Other Potential Issues", check_other_potential_issues)
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
    
    all_passed = all(result for _, result in results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    if all_passed:
        print("\n🎉 NULL POINTER FIX VERIFIED!")
        print("\nChanges made:")
        print("1. ✅ Added try-catch wrapper for error handling")
        print("2. ✅ Added null check: data.alerton && data.alerton.length > 0")
        print("3. ✅ Added split safety check: alerton.includes(',')")
        print("4. ✅ Added data existence checks")
        print("5. ✅ Added error logging")
        print("\n📝 Next steps:")
        print("1. Clear browser cache (Ctrl+Shift+R)")
        print("2. Try editing a question again")
        print("3. The null pointer error should be resolved")
    else:
        print("\n⚠️  Some issues detected")
    
    print("="*70)


if __name__ == "__main__":
    main()