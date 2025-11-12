"""Key strength scoring and recommendations."""

from typing import Dict, List


MINIMUM_KEY_LENGTH = 32
RECOMMENDED_KEY_LENGTH = 50
MINIMUM_ENTROPY_BITS = 128
RECOMMENDED_ENTROPY_BITS = 256


def calculate_strength_score(analysis: Dict) -> int:
    """Calculate overall strength score (0-100)."""
    score = 0

    # Length contribution (up to 30 points)
    score += min(
        30,
        (analysis['key_length'] / RECOMMENDED_KEY_LENGTH) * 30
    )

    # Entropy contribution (up to 30 points)
    score += min(
        30,
        (analysis['shannon_entropy_bits'] / RECOMMENDED_ENTROPY_BITS) * 30
    )

    # Diversity contribution (up to 20 points)
    score += (analysis['character_diversity']['diversity_score'] / 4) * 20

    # Compliance contribution (up to 20 points)
    compliance_score = sum(
        1 for c in analysis['compliance'].values()
        if c.get('compliant', False)
    )
    score += (compliance_score / len(analysis['compliance'])) * 20

    return min(100, int(score))


def determine_strength_level(score: int) -> str:
    """Determine strength level from score."""
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


def generate_recommendations(analysis: Dict) -> List[str]:
    """Generate recommendations for improvement."""
    recommendations = []

    if analysis['key_length'] < RECOMMENDED_KEY_LENGTH:
        recommendations.append(
            f"Increase key length to {RECOMMENDED_KEY_LENGTH}+ characters"
        )

    if analysis['character_diversity']['diversity_score'] < 4:
        missing = []
        diversity = analysis['character_diversity']
        if not diversity['has_lowercase']:
            missing.append('lowercase')
        if not diversity['has_uppercase']:
            missing.append('uppercase')
        if not diversity['has_digits']:
            missing.append('digits')
        if not diversity['has_special_chars']:
            missing.append('special chars')
        if missing:
            recommendations.append(f"Add: {', '.join(missing)}")

    if analysis['shannon_entropy_bits'] < RECOMMENDED_ENTROPY_BITS:
        recommendations.append(
            f"Increase entropy to {RECOMMENDED_ENTROPY_BITS}+ bits"
        )

    if analysis['vulnerabilities']:
        recommendations.append(
            "Address vulnerabilities: "
            + "; ".join(analysis['vulnerabilities'][:2])
        )

    if not recommendations:
        recommendations.append("Key strength is excellent")

    return recommendations
