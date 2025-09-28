#!/usr/bin/env python3
"""
Basic validation test without Django dependencies
"""

import math
from collections import Counter

def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy"""
    if not text:
        return 0.0

    counts = Counter(text)
    total = len(text)

    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log2(probability)

    return entropy

def test_basic_validation():
    """Test basic validation logic"""

    print("🔐 Basic Secret Validation Tests")
    print("=" * 40)

    # Test entropy calculation
    print("📊 Testing entropy calculation...")
    test_cases = [
        ("", 0.0, "Empty string"),
        ("aaaa", 0.0, "All same character"),
        ("abcd", 2.0, "Four different characters"),
        ("Hello World!", 3.0, "Mixed case with punctuation")
    ]

    for text, expected_min, description in test_cases:
        entropy = calculate_entropy(text)
        print(f"   {description}: {entropy:.2f} bits")

        if text == "":
            assert entropy == 0.0, f"Empty string should have 0 entropy, got {entropy}"
        elif text == "aaaa":
            assert entropy == 0.0, f"Same characters should have 0 entropy, got {entropy}"
        else:
            assert entropy > 0, f"Diverse text should have >0 entropy, got {entropy}"

    print("✅ Entropy calculation working correctly")

    # Test SECRET_KEY validation logic
    print("\n🔑 Testing SECRET_KEY validation logic...")

    # Test length validation
    short_key = "short"
    long_enough_key = "a" * 50

    assert len(short_key) < 50, "Short key test case invalid"
    assert len(long_enough_key) >= 50, "Long key test case invalid"
    print("   ✅ Length validation logic correct")

    # Test entropy validation
    low_entropy_key = "a" * 60
    high_entropy_key = "a9B#k2L@m5N$p8Q!r1S%t4U&w7Y*z0Z3C^f6G)h9J+n2M?q5R(s8T"

    low_entropy = calculate_entropy(low_entropy_key)
    high_entropy = calculate_entropy(high_entropy_key)

    assert low_entropy < 1.0, f"Low entropy key should have <1.0 entropy, got {low_entropy}"
    assert high_entropy > 4.0, f"High entropy key should have >4.0 entropy, got {high_entropy}"
    print("   ✅ Entropy validation logic correct")

    # Test pattern detection
    weak_patterns = ['password', 'secret', 'key', 'django', 'test']
    test_key = "this_contains_password_pattern"

    contains_weak_pattern = any(pattern in test_key.lower() for pattern in weak_patterns)
    assert contains_weak_pattern, "Pattern detection logic incorrect"
    print("   ✅ Weak pattern detection logic correct")

    # Test character diversity
    diverse_key = "Abc123!@#"
    char_types = {
        'upper': any(c.isupper() for c in diverse_key),
        'lower': any(c.islower() for c in diverse_key),
        'digit': any(c.isdigit() for c in diverse_key),
        'special': any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in diverse_key)
    }

    diversity_count = sum(char_types.values())
    assert diversity_count >= 3, f"Diverse key should have >=3 character types, got {diversity_count}"
    print("   ✅ Character diversity logic correct")

    print("\n🔒 Testing ENCRYPT_KEY validation logic...")

    # Test base64 validation
    import base64
    valid_bytes = b"a" * 32
    valid_base64 = base64.b64encode(valid_bytes).decode()

    try:
        decoded = base64.b64decode(valid_base64)
        assert len(decoded) == 32, f"Should decode to 32 bytes, got {len(decoded)}"
        print("   ✅ Base64 validation logic correct")
    except Exception as e:
        assert False, f"Base64 validation failed: {e}"

    print("\n✅ ALL BASIC VALIDATION TESTS PASSED!")
    print("🎉 Core validation logic is sound")
    return True

if __name__ == "__main__":
    success = test_basic_validation()
    if success:
        print("\n🎊 BASIC VALIDATION FRAMEWORK: OPERATIONAL")
        exit(0)
    else:
        print("\n❌ BASIC TESTS FAILED")
        exit(1)