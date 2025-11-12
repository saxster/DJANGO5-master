"""Key Strength Analysis Utility

Analyzes encryption key strength and entropy compliance with NIST,
FIPS 140-2, and OWASP standards.

Usage:
    from apps.core.utils_new.security import KeyStrengthAnalyzer

    analyzer = KeyStrengthAnalyzer(secret_key)
    result = analyzer.analyze()
    logger.debug(result['strength_score'])
"""

import logging
from typing import Dict, List

from .entropy import calculate_shannon_entropy, calculate_character_diversity
from .compliance import check_all_compliance
from .vulnerabilities import detect_vulnerabilities
from .scoring import (
    MINIMUM_KEY_LENGTH, RECOMMENDED_KEY_LENGTH,
    MINIMUM_ENTROPY_BITS, RECOMMENDED_ENTROPY_BITS,
    calculate_strength_score, determine_strength_level,
    generate_recommendations
)

logger = logging.getLogger("key_strength_analyzer")


class KeyStrengthAnalyzer:
    """Analyze cryptographic key strength and entropy.

    Implements validation per:
    - NIST SP 800-57 (Key Management)
    - NIST SP 800-90B (Entropy Estimation)
    - FIPS 140-2 (Key Generation Requirements)
    """

    def __init__(self, key: str):
        """Initialize analyzer.

        Args:
            key: Encryption key to analyze

        Raises:
            TypeError: If key is not a string
        """
        if not isinstance(key, str):
            raise TypeError("Key must be a string")
        self.key = key
        self.key_bytes = key.encode('utf-8')

    def analyze(self) -> Dict:
        """Perform comprehensive key strength analysis.

        Returns:
            Dict: Analysis results with scores and recommendations
        """
        analysis = {
            'key_length': len(self.key),
            'key_length_bytes': len(self.key_bytes),
            'shannon_entropy_bits': calculate_shannon_entropy(self.key),
            'character_diversity': calculate_character_diversity(self.key),
            'unique_characters': len(set(self.key)),
            'strength_score': 0,
            'strength_level': '',
            'compliance': {},
            'vulnerabilities': [],
            'recommendations': []
        }

        analysis['compliance'] = check_all_compliance(analysis)
        analysis['vulnerabilities'] = detect_vulnerabilities(
            self.key, analysis,
            analysis['key_length'],
            analysis['unique_characters']
        )
        analysis['strength_score'] = calculate_strength_score(analysis)
        analysis['strength_level'] = determine_strength_level(
            analysis['strength_score']
        )
        analysis['recommendations'] = generate_recommendations(analysis)

        return analysis

    @classmethod
    def validate_django_secret_key(cls) -> Dict:
        """Validate Django SECRET_KEY strength.

        Returns:
            Dict: Validation results
        """
        from django.conf import settings

        if not hasattr(settings, 'SECRET_KEY'):
            return {
                'valid': False,
                'error': 'SECRET_KEY not configured',
                'strength_level': 'N/A'
            }

        analyzer = cls(settings.SECRET_KEY)
        analysis = analyzer.analyze()

        return {
            'valid': analysis['strength_score'] >= 60,
            'strength_score': analysis['strength_score'],
            'strength_level': analysis['strength_level'],
            'compliance': analysis['compliance'],
            'vulnerabilities': analysis['vulnerabilities'],
            'recommendations': analysis['recommendations']
        }

    @classmethod
    def generate_strong_key(cls, length: int = 50) -> str:
        """Generate a cryptographically strong key.

        Args:
            length: Desired key length (default: 50)

        Returns:
            str: Strong random key
        """
        from django.core.management.utils import get_random_secret_key

        key = get_random_secret_key()
        while len(key) < length:
            key += get_random_secret_key()
        return key[:length]


def validate_django_secret_key() -> Dict:
    """Validate Django SECRET_KEY strength (module function)."""
    return KeyStrengthAnalyzer.validate_django_secret_key()
