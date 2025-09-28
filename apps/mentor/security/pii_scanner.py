"""
PII and secrets scanning for AI Mentor system.

This module provides:
- PII detection and redaction
- Secrets scanning
- LLM request/response sanitization
- Diff content scrubbing
"""

import re
import json
from dataclasses import dataclass
from enum import Enum



class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"


class SecretType(Enum):
    """Types of secrets that can be detected."""
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"
    CERTIFICATE = "certificate"


@dataclass
class PIIMatch:
    """Detected PII match."""
    pii_type: PIIType
    value: str
    start_pos: int
    end_pos: int
    confidence: float
    context: str  # Surrounding text for context


@dataclass
class SecretMatch:
    """Detected secret match."""
    secret_type: SecretType
    value: str
    start_pos: int
    end_pos: int
    confidence: float
    context: str
    severity: str  # 'low', 'medium', 'high', 'critical'


@dataclass
class ScanResult:
    """Result of PII/secrets scanning."""
    original_text: str
    redacted_text: str
    pii_matches: List[PIIMatch]
    secret_matches: List[SecretMatch]
    risk_score: float
    safe_for_llm: bool


class PIISecretScanner:
    """Comprehensive PII and secrets scanner."""

    def __init__(self):
        self.pii_patterns = self._load_pii_patterns()
        self.secret_patterns = self._load_secret_patterns()
        self.allowlist_patterns = self._load_allowlist_patterns()

    def _load_pii_patterns(self) -> Dict[PIIType, List[Dict[str, Any]]]:
        """Load PII detection patterns."""
        return {
            PIIType.EMAIL: [
                {
                    'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                    'confidence': 0.9
                }
            ],
            PIIType.PHONE: [
                {
                    'pattern': r'(\+\d{1,3}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
                    'confidence': 0.8
                },
                {
                    'pattern': r'\b\d{3}-\d{3}-\d{4}\b',
                    'confidence': 0.9
                }
            ],
            PIIType.SSN: [
                {
                    'pattern': r'\b\d{3}-\d{2}-\d{4}\b',
                    'confidence': 0.95
                },
                {
                    'pattern': r'\b\d{9}\b',
                    'confidence': 0.6  # Lower confidence for plain 9 digits
                }
            ],
            PIIType.CREDIT_CARD: [
                {
                    'pattern': r'\b(?:\d{4}[\s-]?){3}\d{4}\b',
                    'confidence': 0.8
                }
            ],
            PIIType.IP_ADDRESS: [
                {
                    'pattern': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                    'confidence': 0.7
                }
            ]
        }

    def _load_secret_patterns(self) -> Dict[SecretType, List[Dict[str, Any]]]:
        """Load secret detection patterns."""
        return {
            SecretType.API_KEY: [
                {
                    'pattern': r'(?i)(api[_\-]?key|apikey)\s*[=:]\s*["\']?([a-z0-9_\-]{20,})["\']?',
                    'confidence': 0.9,
                    'severity': 'high'
                },
                {
                    'pattern': r'sk_[a-z0-9]{20,}',
                    'confidence': 0.95,
                    'severity': 'critical'
                }
            ],
            SecretType.PASSWORD: [
                {
                    'pattern': r'(?i)(password|pwd|pass)\s*[=:]\s*["\']?([^\s"\']{6,})["\']?',
                    'confidence': 0.8,
                    'severity': 'high'
                }
            ],
            SecretType.TOKEN: [
                {
                    'pattern': r'(?i)(token|auth[_\-]?token|access[_\-]?token)\s*[=:]\s*["\']?([a-z0-9_\-]{15,})["\']?',
                    'confidence': 0.85,
                    'severity': 'high'
                },
                {
                    'pattern': r'eyJ[a-zA-Z0-9_\-]*\.eyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*',  # JWT tokens
                    'confidence': 0.95,
                    'severity': 'high'
                }
            ],
            SecretType.PRIVATE_KEY: [
                {
                    'pattern': r'-----BEGIN (RSA )?PRIVATE KEY-----',
                    'confidence': 1.0,
                    'severity': 'critical'
                }
            ],
            SecretType.CONNECTION_STRING: [
                {
                    'pattern': r'(?i)(database|db)[_\-]?(url|uri|connection)\s*[=:]\s*["\']?([^\s"\']+)["\']?',
                    'confidence': 0.8,
                    'severity': 'medium'
                }
            ]
        }

    def _load_allowlist_patterns(self) -> List[str]:
        """Load patterns that should be ignored (false positives)."""
        return [
            r'example\.com',
            r'test@test\.com',
            r'user@example\.org',
            r'127\.0\.0\.1',
            r'localhost',
            r'0\.0\.0\.0',
            r'192\.168\.',
            r'10\.0\.',
            r'xxx-xxx-xxxx',
            r'000-00-0000',
            r'YOUR_API_KEY',
            r'your_password_here',
            r'<API_KEY>',
            r'\[PASSWORD\]'
        ]

    def scan_text(self, text: str, scan_pii: bool = True, scan_secrets: bool = True) -> ScanResult:
        """Scan text for PII and secrets."""
        pii_matches = []
        secret_matches = []

        if scan_pii:
            pii_matches = self._scan_for_pii(text)

        if scan_secrets:
            secret_matches = self._scan_for_secrets(text)

        # Generate redacted text
        redacted_text = self._redact_matches(text, pii_matches, secret_matches)

        # Calculate risk score
        risk_score = self._calculate_risk_score(pii_matches, secret_matches)

        # Determine if safe for LLM
        safe_for_llm = self._is_safe_for_llm(pii_matches, secret_matches, risk_score)

        return ScanResult(
            original_text=text,
            redacted_text=redacted_text,
            pii_matches=pii_matches,
            secret_matches=secret_matches,
            risk_score=risk_score,
            safe_for_llm=safe_for_llm
        )

    def _scan_for_pii(self, text: str) -> List[PIIMatch]:
        """Scan text for PII patterns."""
        matches = []

        for pii_type, patterns in self.pii_patterns.items():
            for pattern_info in patterns:
                pattern = pattern_info['pattern']
                confidence = pattern_info['confidence']

                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Check if this is a known false positive
                    if self._is_allowlisted(match.group()):
                        continue

                    # Get context around the match
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    context = text[start:end]

                    matches.append(PIIMatch(
                        pii_type=pii_type,
                        value=match.group(),
                        start_pos=match.start(),
                        end_pos=match.end(),
                        confidence=confidence,
                        context=context
                    ))

        return matches

    def _scan_for_secrets(self, text: str) -> List[SecretMatch]:
        """Scan text for secret patterns."""
        matches = []

        for secret_type, patterns in self.secret_patterns.items():
            for pattern_info in patterns:
                pattern = pattern_info['pattern']
                confidence = pattern_info['confidence']
                severity = pattern_info['severity']

                for match in re.finditer(pattern, text, re.IGNORECASE):
                    # Check if this is a known false positive
                    matched_text = match.group()
                    if self._is_allowlisted(matched_text):
                        continue

                    # Additional validation for specific secret types
                    if not self._validate_secret_match(secret_type, matched_text):
                        continue

                    # Get context
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    context = text[start:end]

                    matches.append(SecretMatch(
                        secret_type=secret_type,
                        value=matched_text,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        confidence=confidence,
                        context=context,
                        severity=severity
                    ))

        return matches

    def _is_allowlisted(self, text: str) -> bool:
        """Check if text matches allowlist patterns (known false positives)."""
        for pattern in self.allowlist_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _validate_secret_match(self, secret_type: SecretType, text: str) -> bool:
        """Additional validation for secret matches."""
        if secret_type == SecretType.CREDIT_CARD:
            # Use Luhn algorithm for credit card validation
            return self._luhn_check(re.sub(r'\D', '', text))

        if secret_type == SecretType.API_KEY:
            # API keys should have minimum entropy
            return self._has_sufficient_entropy(text, min_entropy=3.5)

        if secret_type == SecretType.TOKEN:
            # Tokens should be long enough and have good entropy
            return len(text) >= 15 and self._has_sufficient_entropy(text, min_entropy=3.0)

        return True  # Default to accepting the match

    def _luhn_check(self, card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm."""
        if not card_number.isdigit() or len(card_number) < 13:
            return False

        def luhn_sum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]

            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d * 2))
            return checksum % 10

        return luhn_sum(card_number) == 0

    def _has_sufficient_entropy(self, text: str, min_entropy: float) -> bool:
        """Check if text has sufficient entropy (not a placeholder)."""
        if len(text) < 4:
            return False

        # Calculate character frequency
        char_counts = {}
        for char in text.lower():
            char_counts[char] = char_counts.get(char, 0) + 1

        # Calculate entropy
        length = len(text)
        entropy = 0.0
        for count in char_counts.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)

        return entropy >= min_entropy

    def _redact_matches(self, text: str, pii_matches: List[PIIMatch],
                       secret_matches: List[SecretMatch]) -> str:
        """Redact PII and secrets from text."""
        redacted = text

        # Combine all matches and sort by position (reverse order for replacement)
        all_matches = []

        for match in pii_matches:
            all_matches.append((match.start_pos, match.end_pos, f"[{match.pii_type.value.upper()}_REDACTED]"))

        for match in secret_matches:
            all_matches.append((match.start_pos, match.end_pos, f"[{match.secret_type.value.upper()}_REDACTED]"))

        # Sort by start position in reverse order
        all_matches.sort(key=lambda x: x[0], reverse=True)

        # Apply redactions
        for start_pos, end_pos, replacement in all_matches:
            redacted = redacted[:start_pos] + replacement + redacted[end_pos:]

        return redacted

    def _calculate_risk_score(self, pii_matches: List[PIIMatch],
                            secret_matches: List[SecretMatch]) -> float:
        """Calculate risk score based on detected sensitive data."""
        risk_score = 0.0

        # PII risk weights
        pii_weights = {
            PIIType.EMAIL: 0.3,
            PIIType.PHONE: 0.4,
            PIIType.SSN: 1.0,
            PIIType.CREDIT_CARD: 1.0,
            PIIType.IP_ADDRESS: 0.2,
            PIIType.NAME: 0.3,
            PIIType.ADDRESS: 0.5,
            PIIType.DATE_OF_BIRTH: 0.6
        }

        for match in pii_matches:
            weight = pii_weights.get(match.pii_type, 0.5)
            risk_score += weight * match.confidence

        # Secret risk weights
        secret_weights = {
            SecretType.API_KEY: 2.0,
            SecretType.PASSWORD: 1.5,
            SecretType.TOKEN: 1.8,
            SecretType.PRIVATE_KEY: 3.0,
            SecretType.CONNECTION_STRING: 1.5,
            SecretType.CERTIFICATE: 2.5
        }

        for match in secret_matches:
            weight = secret_weights.get(match.secret_type, 1.0)
            severity_multiplier = {'low': 0.5, 'medium': 1.0, 'high': 1.5, 'critical': 2.0}.get(match.severity, 1.0)
            risk_score += weight * match.confidence * severity_multiplier

        return min(risk_score, 10.0)  # Cap at 10.0

    def _is_safe_for_llm(self, pii_matches: List[PIIMatch], secret_matches: List[SecretMatch],
                        risk_score: float) -> bool:
        """Determine if content is safe to send to LLM after redaction."""
        # High-risk secrets should never go to LLM
        critical_secrets = [m for m in secret_matches
                          if m.severity == 'critical' and m.confidence > 0.8]
        if critical_secrets:
            return False

        # High PII concentration is risky
        high_confidence_pii = [m for m in pii_matches if m.confidence > 0.9]
        if len(high_confidence_pii) > 3:
            return False

        # Overall risk threshold
        return risk_score < 5.0

    def scan_llm_request(self, request_data: Dict[str, Any]) -> Tuple[Dict[str, Any], ScanResult]:
        """Scan and sanitize LLM request data."""
        # Convert request to string for scanning
        request_text = json.dumps(request_data, default=str)

        # Scan for sensitive data
        scan_result = self.scan_text(request_text)

        if not scan_result.safe_for_llm:
            raise ValueError("Request contains sensitive data that cannot be sent to LLM")

        # Create sanitized request
        sanitized_request = json.loads(scan_result.redacted_text)

        return sanitized_request, scan_result

    def scan_llm_response(self, response_data: Dict[str, Any]) -> Tuple[Dict[str, Any], ScanResult]:
        """Scan LLM response for any leaked sensitive data."""
        response_text = json.dumps(response_data, default=str)

        scan_result = self.scan_text(response_text)

        if scan_result.secret_matches:
            # LLM response contains secrets - this shouldn't happen but we need to handle it
            print(f"WARNING: LLM response contains {len(scan_result.secret_matches)} potential secrets")

        # Return redacted response
        sanitized_response = json.loads(scan_result.redacted_text) if scan_result.redacted_text != response_text else response_data

        return sanitized_response, scan_result

    def scan_code_diff(self, diff_content: str) -> ScanResult:
        """Scan code diff for sensitive data before displaying."""
        return self.scan_text(diff_content)

    def scan_file_content(self, file_path: str, content: str) -> ScanResult:
        """Scan file content for sensitive data."""
        # Add file-specific context to scanning
        enhanced_content = f"File: {file_path}\n{content}"
        return self.scan_text(enhanced_content)


class LLMSanitizer:
    """Sanitizer for LLM requests and responses."""

    def __init__(self):
        self.scanner = PIISecretScanner()

    def sanitize_request(self, request_data: Dict[str, Any],
                        user_id: Optional[int] = None) -> Dict[str, Any]:
        """Sanitize LLM request data."""
        try:
            sanitized_request, scan_result = self.scanner.scan_llm_request(request_data)

            # Log sanitization results
            if scan_result.pii_matches or scan_result.secret_matches:
                self._log_sanitization(
                    'request',
                    user_id,
                    len(scan_result.pii_matches),
                    len(scan_result.secret_matches),
                    scan_result.risk_score
                )

            return sanitized_request

        except ValueError as e:
            # Request contains sensitive data - log and raise
            self._log_blocked_request(user_id, str(e), scan_result if 'scan_result' in locals() else None)
            raise

    def sanitize_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize LLM response data."""
        sanitized_response, scan_result = self.scanner.scan_llm_response(response_data)

        # Log any issues found in response
        if scan_result.secret_matches:
            self._log_response_sanitization(scan_result)

        return sanitized_response

    def _log_sanitization(self, direction: str, user_id: Optional[int],
                         pii_count: int, secret_count: int, risk_score: float):
        """Log sanitization activity."""
        log_entry = {
            'timestamp': time.time(),
            'direction': direction,
            'user_id': user_id,
            'pii_count': pii_count,
            'secret_count': secret_count,
            'risk_score': risk_score
        }

        # Store in cache for monitoring
        from django.core.cache import cache
        cache_key = f"mentor_sanitization_log_{int(time.time())}"
        cache.set(cache_key, log_entry, timeout=7 * 24 * 3600)  # Keep for 7 days

    def _log_blocked_request(self, user_id: Optional[int], reason: str,
                           scan_result: Optional[ScanResult]):
        """Log blocked request for security monitoring."""
        log_entry = {
            'timestamp': time.time(),
            'user_id': user_id,
            'reason': reason,
            'risk_score': scan_result.risk_score if scan_result else 0.0,
            'pii_types': [m.pii_type.value for m in scan_result.pii_matches] if scan_result else [],
            'secret_types': [m.secret_type.value for m in scan_result.secret_matches] if scan_result else []
        }

        from django.core.cache import cache
        cache_key = f"mentor_blocked_request_{int(time.time())}"
        cache.set(cache_key, log_entry, timeout=30 * 24 * 3600)  # Keep for 30 days

    def _log_response_sanitization(self, scan_result: ScanResult):
        """Log response sanitization (potential LLM leak)."""
        log_entry = {
            'timestamp': time.time(),
            'secret_count': len(scan_result.secret_matches),
            'secret_types': [m.secret_type.value for m in scan_result.secret_matches],
            'risk_score': scan_result.risk_score
        }

        from django.core.cache import cache
        cache_key = f"mentor_response_sanitization_{int(time.time())}"
        cache.set(cache_key, log_entry, timeout=30 * 24 * 3600)


# Middleware for automatic request/response sanitization
class LLMSanitizationMiddleware:
    """Middleware to automatically sanitize LLM interactions."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.sanitizer = LLMSanitizer()

    def __call__(self, request):
        # Pre-process request if it's going to an LLM endpoint
        if self._is_llm_endpoint(request.path):
            self._sanitize_request(request)

        response = self.get_response(request)

        # Post-process response if it came from an LLM endpoint
        if self._is_llm_endpoint(request.path):
            response = self._sanitize_response(response)

        return response

    def _is_llm_endpoint(self, path: str) -> bool:
        """Check if endpoint involves LLM interactions."""
        llm_endpoints = [
            '/api/mentor/plan/',
            '/api/mentor/patch/',
            '/api/mentor/explain/'
        ]
        return any(path.startswith(endpoint) for endpoint in llm_endpoints)

    def _sanitize_request(self, request):
        """Sanitize incoming request data."""
        if hasattr(request, 'data') and request.data:
            try:
                user_id = request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None
                sanitized_data = self.sanitizer.sanitize_request(request.data, user_id)
                request._sanitized_data = sanitized_data
            except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
                print(f"Request sanitization error: {e}")

    def _sanitize_response(self, response):
        """Sanitize outgoing response data."""
        if hasattr(response, 'data') and response.data:
            try:
                sanitized_data = self.sanitizer.sanitize_response(response.data)
                response.data = sanitized_data
            except (ConnectionError, LLMServiceException, TimeoutError, ValueError) as e:
                print(f"Response sanitization error: {e}")

        return response


# Global instances
_pii_scanner = PIISecretScanner()
_llm_sanitizer = LLMSanitizer()

def get_pii_scanner() -> PIISecretScanner:
    """Get global PII scanner instance."""
    return _pii_scanner

def get_llm_sanitizer() -> LLMSanitizer:
    """Get global LLM sanitizer instance."""
    return _llm_sanitizer

# Convenience functions
def scan_text_for_sensitive_data(text: str) -> ScanResult:
    """Convenience function to scan text."""
    return get_pii_scanner().scan_text(text)

def is_safe_for_llm(text: str) -> bool:
    """Check if text is safe to send to LLM."""
    result = scan_text_for_sensitive_data(text)
    return result.safe_for_llm

def redact_sensitive_data(text: str) -> str:
    """Redact sensitive data from text."""
    result = scan_text_for_sensitive_data(text)
    return result.redacted_text