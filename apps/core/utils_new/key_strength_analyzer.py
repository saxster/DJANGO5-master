"""
Key Strength Analyzer Utility

Analyzes encryption key strength and entropy to ensure compliance with
security standards (NIST, FIPS, OWASP).

Features:
- Entropy calculation for keys
- Key strength validation
- Compliance checking (NIST SP 800-57, FIPS 140-2)
- Weak key detection
- Recommendations for improvement

Usage:
    from apps.core.utils_new.key_strength_analyzer import KeyStrengthAnalyzer

    analyzer = KeyStrengthAnalyzer(secret_key)
    result = analyzer.analyze()
    print(result['strength_score'])
"""

import math
import hashlib
import logging
from typing import Dict, List
from collections import Counter

logger = logging.getLogger("key_strength_analyzer")


class KeyStrengthAnalyzer:
    """
    Analyze cryptographic key strength and entropy.

    Implements validation per:
    - NIST SP 800-57 (Key Management)
    - NIST SP 800-90B (Entropy Estimation)
    - FIPS 140-2 (Key Generation Requirements)
    """

    MINIMUM_KEY_LENGTH = 32
    RECOMMENDED_KEY_LENGTH = 50
    MINIMUM_ENTROPY_BITS = 128
    RECOMMENDED_ENTROPY_BITS = 256

    def __init__(self, key: str):
        """
        Initialize analyzer with key to analyze.

        Args:
            key: Encryption key to analyze
        """
        if not isinstance(key, str):
            raise TypeError("Key must be a string")

        self.key = key
        self.key_bytes = key.encode('utf-8')

    def analyze(self) -> Dict:
        """
        Perform comprehensive key strength analysis.

        Returns:
            Dict: Analysis results with scores and recommendations
        """
        analysis = {
            'key_length': len(self.key),
            'key_length_bytes': len(self.key_bytes),
            'shannon_entropy_bits': self._calculate_shannon_entropy(),
            'character_diversity': self._calculate_character_diversity(),
            'unique_characters': len(set(self.key)),
            'strength_score': 0,
            'strength_level': '',
            'compliance': {},
            'vulnerabilities': [],
            'recommendations': []
        }

        analysis['compliance'] = self._check_compliance(analysis)

        analysis['vulnerabilities'] = self._detect_vulnerabilities(analysis)

        analysis['strength_score'] = self._calculate_strength_score(analysis)

        analysis['strength_level'] = self._determine_strength_level(analysis['strength_score'])

        analysis['recommendations'] = self._generate_recommendations(analysis)

        return analysis

    def _calculate_shannon_entropy(self) -> float:
        """
        Calculate Shannon entropy of the key.

        Returns:
            float: Entropy in bits
        """
        if not self.key:
            return 0.0

        counter = Counter(self.key)
        key_length = len(self.key)

        entropy = 0.0
        for count in counter.values():
            probability = count / key_length
            if probability > 0:
                entropy -= probability * math.log2(probability)

        entropy_bits = entropy * key_length

        return round(entropy_bits, 2)

    def _calculate_character_diversity(self) -> Dict:
        """
        Analyze character diversity in the key.

        Returns:
            Dict: Character diversity metrics
        """
        has_lowercase = any(c.islower() for c in self.key)
        has_uppercase = any(c.isupper() for c in self.key)
        has_digits = any(c.isdigit() for c in self.key)
        has_special = any(not c.isalnum() for c in self.key)

        diversity_score = sum([has_lowercase, has_uppercase, has_digits, has_special])

        return {
            'has_lowercase': has_lowercase,
            'has_uppercase': has_uppercase,
            'has_digits': has_digits,
            'has_special_chars': has_special,
            'diversity_score': diversity_score,
            'max_diversity_score': 4
        }

    def _check_compliance(self, analysis: Dict) -> Dict:
        """
        Check compliance with security standards.

        Args:
            analysis: Current analysis data

        Returns:
            Dict: Compliance status for each standard
        """
        compliance = {}

        compliance['NIST_SP_800_57'] = {
            'min_key_length': analysis['key_length'] >= self.MINIMUM_KEY_LENGTH,
            'min_entropy': analysis['shannon_entropy_bits'] >= self.MINIMUM_ENTROPY_BITS,
            'compliant': (
                analysis['key_length'] >= self.MINIMUM_KEY_LENGTH and
                analysis['shannon_entropy_bits'] >= self.MINIMUM_ENTROPY_BITS
            )
        }

        compliance['FIPS_140_2'] = {
            'min_key_bits': (analysis['key_length'] * 8) >= 128,
            'sufficient_randomness': analysis['unique_characters'] > 20,
            'compliant': (
                (analysis['key_length'] * 8) >= 128 and
                analysis['unique_characters'] > 20
            )
        }

        compliance['OWASP_ASVS'] = {
            'min_length': analysis['key_length'] >= 32,
            'character_diversity': analysis['character_diversity']['diversity_score'] >= 3,
            'compliant': (
                analysis['key_length'] >= 32 and
                analysis['character_diversity']['diversity_score'] >= 3
            )
        }

        return compliance

    def _detect_vulnerabilities(self, analysis: Dict) -> List[str]:
        """
        Detect potential key vulnerabilities.

        Args:
            analysis: Current analysis data

        Returns:
            List[str]: List of detected vulnerabilities
        """
        vulnerabilities = []

        if analysis['key_length'] < self.MINIMUM_KEY_LENGTH:
            vulnerabilities.append(
                f"Key too short: {analysis['key_length']} chars (minimum: {self.MINIMUM_KEY_LENGTH})"
            )

        if analysis['shannon_entropy_bits'] < self.MINIMUM_ENTROPY_BITS:
            vulnerabilities.append(
                f"Low entropy: {analysis['shannon_entropy_bits']} bits (minimum: {self.MINIMUM_ENTROPY_BITS})"
            )

        if analysis['character_diversity']['diversity_score'] < 3:
            vulnerabilities.append(
                f"Low character diversity: {analysis['character_diversity']['diversity_score']}/4"
            )

        if analysis['unique_characters'] < 20:
            vulnerabilities.append(
                f"Low character uniqueness: {analysis['unique_characters']} unique chars (recommended: > 20)"
            )

        if self._contains_common_patterns():
            vulnerabilities.append("Contains common patterns (dictionary words, sequences)")

        if self._is_potentially_weak():
            vulnerabilities.append("Key appears to be weak or predictable")

        return vulnerabilities

    def _contains_common_patterns(self) -> bool:
        """Check for common weak patterns in key."""
        key_lower = self.key.lower()

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

    def _is_potentially_weak(self) -> bool:
        """Check if key appears weak based on statistical analysis."""
        if len(self.key) < 20:
            return True

        unique_ratio = len(set(self.key)) / len(self.key)
        if unique_ratio < 0.5:
            return True

        return False

    def _calculate_strength_score(self, analysis: Dict) -> int:
        """
        Calculate overall strength score (0-100).

        Args:
            analysis: Current analysis data

        Returns:
            int: Strength score out of 100
        """
        score = 0

        score += min(30, (analysis['key_length'] / self.RECOMMENDED_KEY_LENGTH) * 30)

        score += min(30, (analysis['shannon_entropy_bits'] / self.RECOMMENDED_ENTROPY_BITS) * 30)

        score += (analysis['character_diversity']['diversity_score'] / 4) * 20

        compliance_score = sum(
            1 for c in analysis['compliance'].values()
            if c.get('compliant', False)
        )
        score += (compliance_score / len(analysis['compliance'])) * 20

        return min(100, int(score))

    def _determine_strength_level(self, score: int) -> str:
        """
        Determine strength level from score.

        Args:
            score: Strength score (0-100)

        Returns:
            str: Strength level description
        """
        if score >= 90:
            return "EXCELLENT"
        elif score >= 75:
            return "STRONG"
        elif score >= 60:
            return "ADEQUATE"
        elif score >= 40:
            return "WEAK"
        else:
            return "VERY WEAK"

    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """
        Generate recommendations for improvement.

        Args:
            analysis: Current analysis data

        Returns:
            List[str]: Recommendations
        """
        recommendations = []

        if analysis['key_length'] < self.RECOMMENDED_KEY_LENGTH:
            recommendations.append(
                f"Increase key length to at least {self.RECOMMENDED_KEY_LENGTH} characters"
            )

        if analysis['character_diversity']['diversity_score'] < 4:
            missing = []
            diversity = analysis['character_diversity']

            if not diversity['has_lowercase']:
                missing.append('lowercase letters')
            if not diversity['has_uppercase']:
                missing.append('uppercase letters')
            if not diversity['has_digits']:
                missing.append('digits')
            if not diversity['has_special_chars']:
                missing.append('special characters')

            if missing:
                recommendations.append(
                    f"Add character types: {', '.join(missing)}"
                )

        if analysis['shannon_entropy_bits'] < self.RECOMMENDED_ENTROPY_BITS:
            recommendations.append(
                f"Increase key entropy to at least {self.RECOMMENDED_ENTROPY_BITS} bits"
            )

        if analysis['vulnerabilities']:
            recommendations.append(
                "Address detected vulnerabilities: " + "; ".join(analysis['vulnerabilities'][:3])
            )

        if not recommendations:
            recommendations.append("Key strength is excellent - no improvements needed")

        return recommendations

    @classmethod
    def validate_django_secret_key(cls) -> Dict:
        """
        Validate Django SECRET_KEY strength.

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
        """
        Generate a cryptographically strong key.

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


def analyze_secret_key_strength() -> None:
    """
    Analyze and report SECRET_KEY strength (utility function).

    Prints detailed analysis to console.
    """
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