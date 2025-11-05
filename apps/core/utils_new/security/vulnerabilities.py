"""Vulnerability detection for cryptographic keys."""

from typing import List
from .entropy import contains_common_patterns, is_potentially_weak
from .scoring import MINIMUM_KEY_LENGTH, MINIMUM_ENTROPY_BITS


def detect_vulnerabilities(
    key: str, analysis: dict, key_length: int, unique_chars: int
) -> List[str]:
    """Detect potential key vulnerabilities."""
    vulns = []

    if key_length < MINIMUM_KEY_LENGTH:
        vulns.append(
            f"Key too short: {key_length} chars (min: {MINIMUM_KEY_LENGTH})"
        )

    entropy = analysis.get('shannon_entropy_bits', 0)
    if entropy < MINIMUM_ENTROPY_BITS:
        vulns.append(
            f"Low entropy: {entropy} bits (min: {MINIMUM_ENTROPY_BITS})"
        )

    diversity = analysis['character_diversity']['diversity_score']
    if diversity < 3:
        vulns.append(f"Low diversity: {diversity}/4")

    if unique_chars < 20:
        vulns.append(f"Low uniqueness: {unique_chars} chars (rec: >20)")

    if contains_common_patterns(key):
        vulns.append("Contains common patterns")

    if is_potentially_weak(key):
        vulns.append("Appears weak or predictable")

    return vulns
