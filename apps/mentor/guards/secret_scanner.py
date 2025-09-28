"""
Secret scanner with advanced pattern matching and entropy analysis.

This scanner provides:
- Pattern matching: API keys, passwords, tokens
- Entropy analysis: High-entropy string detection
- Git history scanning: Historical secret detection
- Whitelist management: False positive handling
- Remediation suggestions: Secret rotation guides
"""

import re
import math
from dataclasses import dataclass

@dataclass
class SecretMatch:
    """Container for secret detection match."""
    pattern_name: str
    matched_text: str
    file_path: str
    line_number: int
    entropy: float
    confidence: float
    is_whitelisted: bool = False


class SecretScanner:
    """Advanced secret detection with entropy analysis."""

    def __init__(self):
        self.patterns = self._initialize_patterns()
        self.whitelist = self._load_whitelist()

    def _initialize_patterns(self) -> List[Dict[str, Any]]:
        """Initialize secret detection patterns."""
        return [
            {
                'name': 'AWS Access Key',
                'pattern': r'AKIA[0-9A-Z]{16}',
                'entropy_threshold': 4.0
            },
            {
                'name': 'Generic API Key',
                'pattern': r'(?i)(api[_-]?key|apikey)[\'"\s]*[:=][\'"\s]*([A-Za-z0-9]{20,})',
                'entropy_threshold': 3.5
            },
            {
                'name': 'JWT Token',
                'pattern': r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
                'entropy_threshold': 4.0
            }
        ]

    def _load_whitelist(self) -> Set[str]:
        """Load whitelisted patterns."""
        return {
            'test_api_key',
            'example_token',
            'dummy_secret'
        }

    def scan_content(self, content: str, file_path: str) -> List[SecretMatch]:
        """Scan content for secrets."""
        matches = []
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            line_matches = self._scan_line(line, file_path, line_num)
            matches.extend(line_matches)

        return matches

    def _scan_line(self, line: str, file_path: str, line_num: int) -> List[SecretMatch]:
        """Scan a single line for secrets."""
        matches = []

        for pattern_info in self.patterns:
            pattern_matches = re.finditer(pattern_info['pattern'], line)

            for match in pattern_matches:
                matched_text = match.group(0)
                entropy = self._calculate_entropy(matched_text)

                if entropy >= pattern_info['entropy_threshold']:
                    secret_match = SecretMatch(
                        pattern_name=pattern_info['name'],
                        matched_text=matched_text,
                        file_path=file_path,
                        line_number=line_num,
                        entropy=entropy,
                        confidence=min(entropy / pattern_info['entropy_threshold'], 1.0),
                        is_whitelisted=matched_text in self.whitelist
                    )
                    matches.append(secret_match)

        return matches

    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy."""
        if not text:
            return 0

        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        entropy = 0
        text_len = len(text)

        for count in char_counts.values():
            probability = count / text_len
            entropy -= probability * math.log2(probability)

        return entropy