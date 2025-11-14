#!/usr/bin/env python3
"""
Test for exception_scanner.py dataclass decorator fix

This test validates that the ExceptionViolation class is properly
decorated with @dataclass and can be instantiated correctly.

Issue: Missing @ symbol before dataclass decorator on line 47
Fix: Added @ symbol to make it a proper dataclass
"""

import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from exception_scanner import ExceptionViolation
from dataclasses import asdict, is_dataclass


def test_exception_violation_is_dataclass():
    """Test that ExceptionViolation is a proper dataclass"""
    assert is_dataclass(ExceptionViolation), "ExceptionViolation should be a dataclass"
    print("✅ ExceptionViolation is a dataclass")


def test_exception_violation_instantiation():
    """Test that ExceptionViolation can be instantiated with positional args"""
    violation = ExceptionViolation(
        file_path='test.py',
        line_number=10,
        exception_type='Exception',
        context='test context',
        severity='high',
        violation_type='GENERIC_EXCEPTION'
    )
    
    assert violation.file_path == 'test.py'
    assert violation.line_number == 10
    assert violation.exception_type == 'Exception'
    assert violation.context == 'test context'
    assert violation.severity == 'high'
    assert violation.violation_type == 'GENERIC_EXCEPTION'
    print("✅ ExceptionViolation instantiation works correctly")


def test_exception_violation_asdict():
    """Test that ExceptionViolation can be converted to dict"""
    violation = ExceptionViolation(
        file_path='test.py',
        line_number=10,
        exception_type='Exception',
        context='test context',
        severity='high',
        violation_type='GENERIC_EXCEPTION'
    )
    
    violation_dict = asdict(violation)
    
    assert isinstance(violation_dict, dict)
    assert violation_dict['file_path'] == 'test.py'
    assert violation_dict['line_number'] == 10
    assert violation_dict['exception_type'] == 'Exception'
    assert violation_dict['context'] == 'test context'
    assert violation_dict['severity'] == 'high'
    assert violation_dict['violation_type'] == 'GENERIC_EXCEPTION'
    print("✅ ExceptionViolation asdict() works correctly")


def test_exception_violation_str():
    """Test that ExceptionViolation has correct string representation"""
    violation = ExceptionViolation(
        file_path='test.py',
        line_number=10,
        exception_type='Exception',
        context='test context',
        severity='high',
        violation_type='GENERIC_EXCEPTION'
    )
    
    str_repr = str(violation)
    assert 'test.py:10' in str_repr
    assert 'GENERIC_EXCEPTION' in str_repr
    assert 'Exception' in str_repr
    print("✅ ExceptionViolation __str__() works correctly")


def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing exception_scanner.py dataclass fix")
    print("=" * 70)
    
    try:
        test_exception_violation_is_dataclass()
        test_exception_violation_instantiation()
        test_exception_violation_asdict()
        test_exception_violation_str()
        
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
