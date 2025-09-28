"""
Centralized write policy enforcement for the AI Mentor system.

This module provides a unified policy framework for validating
all write operations across the mentor system, ensuring consistent
security and safety controls.
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass
from enum import Enum



class PolicyViolation(Enum):
    """Types of policy violations."""
    DENIED_PATH = "denied_path"
    CRITICAL_FILE = "critical_file"
    FILE_TOO_LARGE = "file_too_large"
    TOTAL_SIZE_EXCEEDED = "total_size_exceeded"
    MAX_FILES_EXCEEDED = "max_files_exceeded"
    SECURITY_RISK = "security_risk"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"


@dataclass
class PolicyResult:
    """Result of policy validation."""
    allowed: bool
    violations: List[Dict[str, Any]]
    recommendations: List[str]
    risk_level: str  # 'low', 'medium', 'high', 'critical'

    def add_violation(self, violation_type: PolicyViolation, message: str,
                     file_path: str = None, details: Dict[str, Any] = None):
        """Add a policy violation."""
        self.violations.append({
            'type': violation_type.value,
            'message': message,
            'file_path': file_path,
            'details': details or {}
        })
        self.allowed = False

    def add_recommendation(self, message: str):
        """Add a recommendation for the user."""
        self.recommendations.append(message)


@dataclass
class WriteRequest:
    """Container for write operation requests."""
    operation_type: str  # 'create', 'modify', 'delete'
    file_path: str
    content_size: int = 0
    user_id: Optional[int] = None
    request_ip: Optional[str] = None
    content_preview: Optional[str] = None  # First 500 chars for analysis


@dataclass
class PolicyLimits:
    """Configuration limits for write operations."""
    max_files_per_operation: int = 50
    max_lines_per_file: int = 500
    max_total_lines: int = 2000
    max_file_size_kb: int = 100
    max_total_size_kb: int = 1000
    allowed_extensions: Set[str] = None
    denied_extensions: Set[str] = None

    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = {'.py', '.js', '.html', '.css', '.md', '.json', '.yaml', '.yml'}
        if self.denied_extensions is None:
            self.denied_extensions = {'.exe', '.dll', '.so', '.dylib', '.bin'}


class WritePolicy:
    """Centralized write policy enforcement engine."""

    def __init__(self):
        self.limits = self._load_limits()
        self.allowlist = self._load_allowlist()
        self.denylist = self._load_denylist()
        self.critical_files = self._load_critical_files()
        self.security_patterns = self._load_security_patterns()
        self.user_overrides = self._load_user_overrides()

    def _load_limits(self) -> PolicyLimits:
        """Load policy limits from settings/environment."""
        return PolicyLimits(
            max_files_per_operation=int(os.getenv('MENTOR_MAX_FILES_PER_OP', 50)),
            max_lines_per_file=int(os.getenv('MENTOR_MAX_LINES_PER_FILE', 500)),
            max_total_lines=int(os.getenv('MENTOR_MAX_TOTAL_LINES', 2000)),
            max_file_size_kb=int(os.getenv('MENTOR_MAX_FILE_SIZE_KB', 100)),
            max_total_size_kb=int(os.getenv('MENTOR_MAX_TOTAL_SIZE_KB', 1000)),
        )

    def _load_allowlist(self) -> Set[str]:
        """Load allowed paths from configuration."""
        default_allowlist = {
            'apps/',
            'frontend/templates/',
            'static/',
            'docs/',
            'tests/',
            'scripts/'
        }

        # Load from environment variable
        env_allowlist = os.getenv('MENTOR_WRITE_ALLOWLIST', '')
        if env_allowlist:
            env_paths = {path.strip() for path in env_allowlist.split(',') if path.strip()}
            return default_allowlist.union(env_paths)

        return default_allowlist

    def _load_denylist(self) -> Set[str]:
        """Load denied paths from configuration."""
        default_denylist = {
            # System files
            '/',
            '/etc/',
            '/usr/',
            '/bin/',
            '/sbin/',
            '/var/',
            '/tmp/',

            # Django sensitive areas
            'intelliwiz_config/settings.py',
            'intelliwiz_config/settings/',
            '.env',
            '.env.local',
            '.env.production',
            'requirements/',
            'Dockerfile',
            'docker-compose.yml',
            'docker-compose.yaml',

            # Git and version control
            '.git/',
            '.gitignore',
            '.github/',

            # Python/Django system files
            'manage.py',
            '__pycache__/',
            '*.pyc',
            'db.sqlite3',

            # Security files
            '.ssh/',
            '.aws/',
            '.gcp/',
            'credentials.json',
            'service-account.json',

            # Dependency files (read-only)
            'node_modules/',
            'venv/',
            '.venv/',
            'env/',
        }

        # Load from environment variable
        env_denylist = os.getenv('MENTOR_WRITE_DENYLIST', '')
        if env_denylist:
            env_paths = {path.strip() for path in env_denylist.split(',') if path.strip()}
            return default_denylist.union(env_paths)

        return default_denylist

    def _load_critical_files(self) -> Set[str]:
        """Load critical files that require special handling."""
        return {
            # Django core
            'intelliwiz_config/settings.py',
            'intelliwiz_config/urls.py',
            'intelliwiz_config/wsgi.py',
            'intelliwiz_config/asgi.py',
            'manage.py',

            # Database
            'db.sqlite3',

            # Migrations (require special handling)
            # Note: migrations are handled separately in migration_safety.py

            # Security configurations
            '.env',
            '.env.local',
            'requirements/base.txt',
            'requirements/production.txt',

            # Infrastructure
            'Dockerfile',
            'docker-compose.yml',
            'docker-compose.yaml',
            '.github/workflows/',
        }

    def _load_security_patterns(self) -> List[Dict[str, str]]:
        """Load security-sensitive patterns to detect in content."""
        return [
            {
                'pattern': r'(?i)(password|pwd|secret|key|token)\s*[=:]\s*["\']?[\w\-\.@]+["\']?',
                'description': 'Potential hardcoded credentials',
                'severity': 'high'
            },
            {
                'pattern': r'(?i)(api[_\-]?key|access[_\-]?token|auth[_\-]?token)\s*[=:]\s*["\']?[\w\-]+["\']?',
                'description': 'Potential API keys or tokens',
                'severity': 'high'
            },
            {
                'pattern': r'(?i)(database|db)[_\-]?(url|uri|connection)\s*[=:]\s*["\']?[\w\-\./:@]+["\']?',
                'description': 'Database connection strings',
                'severity': 'medium'
            },
            {
                'pattern': r'(?i)eval\s*\(',
                'description': 'Use of eval() function',
                'severity': 'high'
            },
            {
                'pattern': r'(?i)exec\s*\(',
                'description': 'Use of exec() function',
                'severity': 'high'
            },
            {
                'pattern': r'import\s+os.*system',
                'description': 'OS system command execution',
                'severity': 'medium'
            },
            {
                'pattern': r'shell=True',
                'description': 'Shell command execution',
                'severity': 'medium'
            }
        ]

    def _load_user_overrides(self) -> Dict[str, Dict[str, Any]]:
        """Load user-specific policy overrides."""
        # In a real system, this would load from database
        return {}

    def validate_write(self, request: WriteRequest) -> PolicyResult:
        """Validate a write operation against all policies."""
        result = PolicyResult(
            allowed=True,
            violations=[],
            recommendations=[],
            risk_level='low'
        )

        # Apply all validation checks
        self._check_path_policy(request, result)
        self._check_file_limits(request, result)
        self._check_security_patterns(request, result)
        self._check_user_permissions(request, result)
        self._check_rate_limits(request, result)

        # Determine final risk level
        result.risk_level = self._calculate_risk_level(result)

        # Add recommendations based on violations
        self._add_contextual_recommendations(result)

        return result

    def validate_batch_write(self, requests: List[WriteRequest]) -> PolicyResult:
        """Validate a batch of write operations."""
        result = PolicyResult(
            allowed=True,
            violations=[],
            recommendations=[],
            risk_level='low'
        )

        # Check batch-level limits
        total_size = sum(req.content_size for req in requests)
        if len(requests) > self.limits.max_files_per_operation:
            result.add_violation(
                PolicyViolation.MAX_FILES_EXCEEDED,
                f"Batch operation exceeds maximum file limit ({len(requests)} > {self.limits.max_files_per_operation})"
            )

        if total_size > self.limits.max_total_size_kb * 1024:
            result.add_violation(
                PolicyViolation.TOTAL_SIZE_EXCEEDED,
                f"Total size exceeds limit ({total_size / 1024:.1f}KB > {self.limits.max_total_size_kb}KB)"
            )

        # Validate each individual request
        for request in requests:
            individual_result = self.validate_write(request)
            if not individual_result.allowed:
                result.allowed = False
                result.violations.extend(individual_result.violations)

        # Determine overall risk level
        result.risk_level = self._calculate_risk_level(result)
        self._add_contextual_recommendations(result)

        return result

    def _check_path_policy(self, request: WriteRequest, result: PolicyResult):
        """Check if the file path is allowed by allowlist/denylist."""
        file_path = request.file_path

        # Normalize path
        normalized_path = os.path.normpath(file_path)

        # Check denylist first (more restrictive)
        for denied_pattern in self.denylist:
            if self._path_matches_pattern(normalized_path, denied_pattern):
                result.add_violation(
                    PolicyViolation.DENIED_PATH,
                    f"Path '{file_path}' matches denied pattern '{denied_pattern}'",
                    file_path=file_path
                )
                return

        # Check allowlist
        allowed = False
        for allowed_pattern in self.allowlist:
            if self._path_matches_pattern(normalized_path, allowed_pattern):
                allowed = True
                break

        if not allowed:
            result.add_violation(
                PolicyViolation.DENIED_PATH,
                f"Path '{file_path}' is not in allowed paths",
                file_path=file_path
            )

        # Check critical files
        if self._is_critical_file(file_path):
            result.add_violation(
                PolicyViolation.CRITICAL_FILE,
                f"Path '{file_path}' is a critical system file",
                file_path=file_path,
                details={'requires_manual_review': True}
            )

    def _check_file_limits(self, request: WriteRequest, result: PolicyResult):
        """Check file size and content limits."""
        file_path = request.file_path

        # Check file size
        if request.content_size > self.limits.max_file_size_kb * 1024:
            result.add_violation(
                PolicyViolation.FILE_TOO_LARGE,
                f"File size ({request.content_size / 1024:.1f}KB) exceeds limit ({self.limits.max_file_size_kb}KB)",
                file_path=file_path
            )

        # Check file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext in self.limits.denied_extensions:
            result.add_violation(
                PolicyViolation.SECURITY_RISK,
                f"File extension '{file_ext}' is not allowed",
                file_path=file_path
            )
        elif self.limits.allowed_extensions and file_ext not in self.limits.allowed_extensions:
            result.add_violation(
                PolicyViolation.SECURITY_RISK,
                f"File extension '{file_ext}' is not in allowed extensions list",
                file_path=file_path
            )

    def _check_security_patterns(self, request: WriteRequest, result: PolicyResult):
        """Check content for security-sensitive patterns."""
        if not request.content_preview:
            return

        content = request.content_preview

        for pattern_info in self.security_patterns:
            pattern = pattern_info['pattern']
            matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)

            for match in matches:
                result.add_violation(
                    PolicyViolation.SECURITY_RISK,
                    f"Security pattern detected: {pattern_info['description']}",
                    file_path=request.file_path,
                    details={
                        'pattern': pattern,
                        'severity': pattern_info['severity'],
                        'match_text': match.group()[:50] + '...' if len(match.group()) > 50 else match.group()
                    }
                )

    def _check_user_permissions(self, request: WriteRequest, result: PolicyResult):
        """Check user-specific permissions."""
        if not request.user_id:
            return  # Skip if no user context

        # Check user overrides
        user_overrides = self.user_overrides.get(str(request.user_id), {})

        # Apply user-specific limits if configured
        if 'max_files_per_day' in user_overrides:
            # Implementation would check daily usage against limit
            # For now, just add to result for tracking
            result.add_recommendation(
                f"User has daily file limit of {user_overrides['max_files_per_day']}"
            )

    def _check_rate_limits(self, request: WriteRequest, result: PolicyResult):
        """Check rate limiting policies."""
        # Implementation would check recent activity
        # For demo, we'll just add a placeholder
        pass

    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a pattern (supports wildcards)."""
        # Convert simple wildcard patterns to regex
        if '*' in pattern:
            regex_pattern = pattern.replace('*', '.*')
            return bool(re.match(f"^{regex_pattern}", path))

        # Direct string match or prefix match
        return path.startswith(pattern) or path == pattern

    def _is_critical_file(self, file_path: str) -> bool:
        """Check if a file is marked as critical."""
        normalized_path = os.path.normpath(file_path)

        for critical_pattern in self.critical_files:
            if self._path_matches_pattern(normalized_path, critical_pattern):
                return True

        return False

    def _calculate_risk_level(self, result: PolicyResult) -> str:
        """Calculate overall risk level based on violations."""
        if not result.violations:
            return 'low'

        severity_scores = {
            PolicyViolation.CRITICAL_FILE: 10,
            PolicyViolation.SECURITY_RISK: 8,
            PolicyViolation.DENIED_PATH: 6,
            PolicyViolation.FILE_TOO_LARGE: 3,
            PolicyViolation.MAX_FILES_EXCEEDED: 4,
            PolicyViolation.TOTAL_SIZE_EXCEEDED: 4,
            PolicyViolation.PERMISSION_DENIED: 7,
            PolicyViolation.RATE_LIMITED: 2
        }

        total_score = 0
        for violation in result.violations:
            violation_type = PolicyViolation(violation['type'])
            score = severity_scores.get(violation_type, 1)

            # Increase score for high-severity security issues
            if violation.get('details', {}).get('severity') == 'high':
                score *= 1.5

            total_score += score

        if total_score >= 10:
            return 'critical'
        elif total_score >= 6:
            return 'high'
        elif total_score >= 3:
            return 'medium'
        else:
            return 'low'

    def _add_contextual_recommendations(self, result: PolicyResult):
        """Add helpful recommendations based on violations."""
        violation_types = {v['type'] for v in result.violations}

        if PolicyViolation.DENIED_PATH.value in violation_types:
            result.add_recommendation(
                "Consider updating your scope to target allowed directories like 'apps/', 'tests/', or 'docs/'"
            )

        if PolicyViolation.FILE_TOO_LARGE.value in violation_types:
            result.add_recommendation(
                "Break large changes into smaller, more focused modifications"
            )

        if PolicyViolation.SECURITY_RISK.value in violation_types:
            result.add_recommendation(
                "Review the flagged content for sensitive information before proceeding"
            )

        if PolicyViolation.CRITICAL_FILE.value in violation_types:
            result.add_recommendation(
                "Critical file changes require manual review and approval"
            )

    def get_policy_summary(self) -> Dict[str, Any]:
        """Get a summary of current policy configuration."""
        return {
            'limits': {
                'max_files_per_operation': self.limits.max_files_per_operation,
                'max_lines_per_file': self.limits.max_lines_per_file,
                'max_total_lines': self.limits.max_total_lines,
                'max_file_size_kb': self.limits.max_file_size_kb,
                'max_total_size_kb': self.limits.max_total_size_kb,
            },
            'paths': {
                'allowlist_count': len(self.allowlist),
                'denylist_count': len(self.denylist),
                'critical_files_count': len(self.critical_files),
            },
            'security': {
                'patterns_count': len(self.security_patterns),
                'extensions_allowed': list(self.limits.allowed_extensions),
                'extensions_denied': list(self.limits.denied_extensions),
            }
        }


# Singleton instance for global access
_write_policy_instance = None

def get_write_policy() -> WritePolicy:
    """Get the global WritePolicy instance."""
    global _write_policy_instance
    if _write_policy_instance is None:
        _write_policy_instance = WritePolicy()
    return _write_policy_instance


# Convenience functions for common use cases
def validate_single_write(file_path: str, content_size: int = 0,
                         content_preview: str = None, user_id: int = None) -> PolicyResult:
    """Validate a single write operation."""
    request = WriteRequest(
        operation_type='modify',
        file_path=file_path,
        content_size=content_size,
        user_id=user_id,
        content_preview=content_preview
    )
    return get_write_policy().validate_write(request)


def is_path_allowed(file_path: str) -> bool:
    """Quick check if a path is allowed."""
    result = validate_single_write(file_path)
    return result.allowed


def get_path_violations(file_path: str) -> List[Dict[str, Any]]:
    """Get violations for a specific path."""
    result = validate_single_write(file_path)
    return result.violations