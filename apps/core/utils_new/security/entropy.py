"""Entropy calculation for cryptographic keys."""

import math
import logging
from typing import Dict
from collections import Counter

logger = logging.getLogger("key_strength_analyzer")


def calculate_shannon_entropy(key: str) -> float:
    """Calculate Shannon entropy of a key."""
    if not key:
        return 0.0

    counter = Counter(key)
    key_length = len(key)

    entropy = 0.0
    for count in counter.values():
        probability = count / key_length
        if probability > 0:
            entropy -= probability * math.log2(probability)

    entropy_bits = entropy * key_length

    return round(entropy_bits, 2)


def calculate_character_diversity(key: str) -> Dict:
    """Analyze character diversity in key."""
    has_lowercase = any(c.islower() for c in key)
    has_uppercase = any(c.isupper() for c in key)
    has_digits = any(c.isdigit() for c in key)
    has_special = any(not c.isalnum() for c in key)

    diversity_score = sum([has_lowercase, has_uppercase, has_digits, has_special])

    return {
        'has_lowercase': has_lowercase,
        'has_uppercase': has_uppercase,
        'has_digits': has_digits,
        'has_special_chars': has_special,
        'diversity_score': diversity_score,
        'max_diversity_score': 4
    }


def contains_common_patterns(key: str) -> bool:
    """Check for common weak patterns in key."""
    key_lower = key.lower()

    common_patterns = [
        'password', 'secret', 'admin', 'test', 'demo',
        '12345', '123456', 'abcdef', 'qwerty',
        'django-insecure'
    ]

    for pattern in common_patterns:
        if pattern in key_lower:
            return True

    sequential_patterns = ['012', '123', '234', 'abc', 'bcd']
    for pattern in sequential_patterns:
        if pattern in key_lower:
            return True

    return False


def is_potentially_weak(key: str) -> bool:
    """Check if key appears weak based on statistical analysis."""
    if len(key) < 20:
        return True

    unique_ratio = len(set(key)) / len(key)
    if unique_ratio < 0.5:
        return True

    return False


def analyze_secret_key_strength() -> None:
    """Report SECRET_KEY strength analysis to console."""
    from .key_analysis import KeyStrengthAnalyzer

    result = KeyStrengthAnalyzer.validate_django_secret_key()

    print("="*70)
    print("SECRET_KEY STRENGTH ANALYSIS")
    print("="*70)

    if not result.get('valid'):
        print(f"❌ INVALID: {result.get('error', 'Unknown error')}")
        return

    score = result['strength_score']
    level = result['strength_level']

    status_icon = '✅' if score >= 75 else '⚠️' if score >= 60 else '❌'

    print(f"{status_icon} Strength Score: {score}/100")
    print(f"{status_icon} Strength Level: {level}")
    print("")

    print("COMPLIANCE STATUS:")
    for standard, checks in result['compliance'].items():
        compliant = checks.get('compliant', False)
        icon = '✅' if compliant else '❌'
        print(f"  {icon} {standard}: {'COMPLIANT' if compliant else 'NON-COMPLIANT'}")

    if result.get('vulnerabilities'):
        print("")
        print("VULNERABILITIES:")
        for vuln in result['vulnerabilities']:
            print(f"  ❌ {vuln}")

    if result.get('recommendations'):
        print("")
        print("RECOMMENDATIONS:")
        for rec in result['recommendations']:
            print(f"  💡 {rec}")

    print("="*70)
