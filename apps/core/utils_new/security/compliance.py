"""Compliance checking for cryptographic keys."""

from typing import Dict, List


def check_nist_compliance(key_length: int, entropy_bits: float) -> Dict:
    """Check NIST SP 800-57 compliance."""
    min_length = 32
    min_entropy = 128
    return {
        'min_key_length': key_length >= min_length,
        'min_entropy': entropy_bits >= min_entropy,
        'compliant': key_length >= min_length and entropy_bits >= min_entropy
    }


def check_fips_compliance(key_length: int, unique_chars: int) -> Dict:
    """Check FIPS 140-2 compliance."""
    return {
        'min_key_bits': (key_length * 8) >= 128,
        'sufficient_randomness': unique_chars > 20,
        'compliant': (key_length * 8) >= 128 and unique_chars > 20
    }


def check_owasp_compliance(key_length: int, diversity_score: int) -> Dict:
    """Check OWASP ASVS compliance."""
    return {
        'min_length': key_length >= 32,
        'character_diversity': diversity_score >= 3,
        'compliant': key_length >= 32 and diversity_score >= 3
    }


def check_all_compliance(analysis: Dict) -> Dict:
    """Check compliance with all standards."""
    return {
        'NIST_SP_800_57': check_nist_compliance(
            analysis['key_length'],
            analysis['shannon_entropy_bits']
        ),
        'FIPS_140_2': check_fips_compliance(
            analysis['key_length'],
            analysis['unique_characters']
        ),
        'OWASP_ASVS': check_owasp_compliance(
            analysis['key_length'],
            analysis['character_diversity']['diversity_score']
        )
    }
