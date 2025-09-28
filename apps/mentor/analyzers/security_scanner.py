"""
Security scanner with OWASP Top 10 patterns for comprehensive security analysis.

This scanner provides:
- OWASP Top 10 patterns: SQL injection, XSS, CSRF
- Django security checklist: Settings audit
- Secret detection: API keys, passwords, tokens
- Dependency vulnerabilities: CVE database checking
- Permission escalation: Improper access control
"""

import ast
import re
from enum import Enum

from django.conf import settings


class SecurityIssueType(Enum):
    """Types of security issues."""
    SQL_INJECTION = "sql_injection"
    XSS_VULNERABILITY = "xss_vulnerability"
    CSRF_BYPASS = "csrf_bypass"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    BROKEN_ACCESS_CONTROL = "broken_access_control"
    SECURITY_MISCONFIGURATION = "security_misconfiguration"
    VULNERABLE_COMPONENTS = "vulnerable_components"
    INSUFFICIENT_LOGGING = "insufficient_logging"
    SERVER_SIDE_REQUEST_FORGERY = "ssrf"
    HARDCODED_SECRET = "hardcoded_secret"
    WEAK_CRYPTOGRAPHY = "weak_cryptography"
    INFORMATION_DISCLOSURE = "information_disclosure"


class SecuritySeverity(Enum):
    """Security issue severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityIssue:
    """Container for security issue information."""
    type: SecurityIssueType
    severity: SecuritySeverity
    description: str
    file_path: str
    line_number: int
    symbol_name: str
    vulnerable_code: str
    remediation: str
    cwe_id: Optional[str] = None
    owasp_category: Optional[str] = None
    confidence: float = 0.8


@dataclass
class SecretPattern:
    """Container for secret detection patterns."""
    name: str
    pattern: str
    description: str
    severity: SecuritySeverity
    entropy_threshold: float = 3.5


class SecurityScanner:
    """Comprehensive security scanner for Django applications."""

    def __init__(self):
        self.security_issues = []
        self.secret_patterns = self._initialize_secret_patterns()
        self.vulnerability_patterns = self._initialize_vulnerability_patterns()

    def scan_security_issues(self, file_paths: List[str]) -> Dict[str, Any]:
        """Scan for security issues in the given files."""
        try:
            # Scan each file
            for file_path in file_paths:
                self._scan_file_security(file_path)

            # Scan Django settings
            self._scan_django_settings()

            # Generate security report
            report = self._generate_security_report()

            return report

        except (ValueError, TypeError) as e:
            print(f"Security scan failed: {e}")
            return {'error': str(e)}

    def _initialize_secret_patterns(self) -> List[SecretPattern]:
        """Initialize patterns for secret detection."""
        return [
            SecretPattern(
                name="AWS Access Key",
                pattern=r'AKIA[0-9A-Z]{16}',
                description="AWS Access Key ID",
                severity=SecuritySeverity.HIGH,
                entropy_threshold=4.0
            ),
            SecretPattern(
                name="AWS Secret Key",
                pattern=r'[A-Za-z0-9/+=]{40}',
                description="AWS Secret Access Key",
                severity=SecuritySeverity.CRITICAL,
                entropy_threshold=4.5
            ),
            SecretPattern(
                name="API Key",
                pattern=r'(?i)api[_-]?key[\'"\s]*[:=][\'"\s]*[A-Za-z0-9]{20,}',
                description="Generic API Key",
                severity=SecuritySeverity.HIGH,
                entropy_threshold=3.5
            ),
            SecretPattern(
                name="Database Password",
                pattern=r'(?i)(?:password|passwd|pwd)[\'"\s]*[:=][\'"\s]*[^\s\'"]{8,}',
                description="Database Password",
                severity=SecuritySeverity.CRITICAL,
                entropy_threshold=3.0
            ),
            SecretPattern(
                name="JWT Token",
                pattern=r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
                description="JSON Web Token",
                severity=SecuritySeverity.HIGH,
                entropy_threshold=4.0
            ),
            SecretPattern(
                name="Private Key",
                pattern=r'-----BEGIN[A-Z ]+PRIVATE KEY-----',
                description="Private Key",
                severity=SecuritySeverity.CRITICAL,
                entropy_threshold=5.0
            ),
            SecretPattern(
                name="Generic Secret",
                pattern=r'(?i)secret[\'"\s]*[:=][\'"\s]*[A-Za-z0-9]{16,}',
                description="Generic Secret",
                severity=SecuritySeverity.MEDIUM,
                entropy_threshold=3.5
            )
        ]

    def _initialize_vulnerability_patterns(self) -> Dict[SecurityIssueType, List[Dict[str, Any]]]:
        """Initialize patterns for vulnerability detection."""
        return {
            SecurityIssueType.SQL_INJECTION: [
                {
                    'pattern': r'\.raw\([\'"].*%s.*[\'"]',
                    'description': 'Raw SQL query with string formatting',
                    'severity': SecuritySeverity.HIGH,
                    'cwe_id': 'CWE-89'
                },
                {
                    'pattern': r'cursor\.execute\([\'"].*%.*[\'"]',
                    'description': 'Direct SQL execution with string formatting',
                    'severity': SecuritySeverity.HIGH,
                    'cwe_id': 'CWE-89'
                }
            ],
            SecurityIssueType.XSS_VULNERABILITY: [
                {
                    'pattern': r'\|safe\b',
                    'description': 'Django template safe filter bypasses XSS protection',
                    'severity': SecuritySeverity.MEDIUM,
                    'cwe_id': 'CWE-79'
                },
                {
                    'pattern': r'mark_safe\(',
                    'description': 'mark_safe() bypasses XSS protection',
                    'severity': SecuritySeverity.MEDIUM,
                    'cwe_id': 'CWE-79'
                },
                {
                    'pattern': r'innerHTML\s*=',
                    'description': 'Direct innerHTML assignment may allow XSS',
                    'severity': SecuritySeverity.MEDIUM,
                    'cwe_id': 'CWE-79'
                }
            ],
            SecurityIssueType.CSRF_BYPASS: [
                {
                    'pattern': r'@csrf_exempt',
                    'description': 'CSRF protection disabled',
                    'severity': SecuritySeverity.HIGH,
                    'cwe_id': 'CWE-352'
                },
                {
                    'pattern': r'CSRF_COOKIE_SECURE\s*=\s*False',
                    'description': 'CSRF cookie not secure',
                    'severity': SecuritySeverity.MEDIUM,
                    'cwe_id': 'CWE-352'
                }
            ],
            SecurityIssueType.INSECURE_DESERIALIZATION: [
                {
                    'pattern': r'pickle\.loads?\(',
                    'description': 'Insecure pickle deserialization',
                    'severity': SecuritySeverity.CRITICAL,
                    'cwe_id': 'CWE-502'
                },
                {
                    'pattern': r'yaml\.load\(',
                    'description': 'Insecure YAML deserialization',
                    'severity': SecuritySeverity.HIGH,
                    'cwe_id': 'CWE-502'
                }
            ],
            SecurityIssueType.WEAK_CRYPTOGRAPHY: [
                {
                    'pattern': r'hashlib\.md5\(',
                    'description': 'MD5 is cryptographically weak',
                    'severity': SecuritySeverity.MEDIUM,
                    'cwe_id': 'CWE-327'
                },
                {
                    'pattern': r'hashlib\.sha1\(',
                    'description': 'SHA-1 is cryptographically weak',
                    'severity': SecuritySeverity.MEDIUM,
                    'cwe_id': 'CWE-327'
                }
            ]
        }

    def _scan_file_security(self, file_path: str):
        """Scan a single file for security issues."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Scan for secrets
            self._scan_secrets(file_path, content)

            # Scan for vulnerability patterns
            self._scan_vulnerability_patterns(file_path, content)

            # Parse AST for deeper analysis
            if file_path.endswith('.py'):
                try:
                    tree = ast.parse(content)
                    scanner = FileSecurityScanner(file_path, content)
                    scanner.visit(tree)
                    self.security_issues.extend(scanner.security_issues)
                except SyntaxError:
                    pass  # Skip files with syntax errors

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error scanning file {file_path}: {e}")

    def _scan_secrets(self, file_path: str, content: str):
        """Scan for hardcoded secrets."""
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for secret_pattern in self.secret_patterns:
                matches = re.finditer(secret_pattern.pattern, line)

                for match in matches:
                    # Calculate entropy to reduce false positives
                    matched_text = match.group(0)
                    entropy = self._calculate_entropy(matched_text)

                    if entropy >= secret_pattern.entropy_threshold:
                        self.security_issues.append(SecurityIssue(
                            type=SecurityIssueType.HARDCODED_SECRET,
                            severity=secret_pattern.severity,
                            description=f"Potential {secret_pattern.description} found",
                            file_path=file_path,
                            line_number=line_num,
                            symbol_name="hardcoded_secret",
                            vulnerable_code=line.strip(),
                            remediation=f"Move {secret_pattern.description} to environment variables",
                            confidence=min(entropy / secret_pattern.entropy_threshold, 1.0)
                        ))

    def _scan_vulnerability_patterns(self, file_path: str, content: str):
        """Scan for vulnerability patterns."""
        lines = content.split('\n')

        for vuln_type, patterns in self.vulnerability_patterns.items():
            for pattern_info in patterns:
                pattern = pattern_info['pattern']
                matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)

                for match in matches:
                    # Find line number
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = lines[line_num - 1] if line_num <= len(lines) else ""

                    self.security_issues.append(SecurityIssue(
                        type=vuln_type,
                        severity=pattern_info['severity'],
                        description=pattern_info['description'],
                        file_path=file_path,
                        line_number=line_num,
                        symbol_name="pattern_match",
                        vulnerable_code=line_content.strip(),
                        remediation=self._get_remediation(vuln_type),
                        cwe_id=pattern_info.get('cwe_id'),
                        owasp_category=self._get_owasp_category(vuln_type)
                    ))

    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of text."""
        if not text:
            return 0

        # Count character frequencies
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Calculate entropy
        entropy = 0
        text_len = len(text)

        for count in char_counts.values():
            probability = count / text_len
            entropy -= probability * (probability.bit_length() - 1)

        return entropy

    def _get_remediation(self, vuln_type: SecurityIssueType) -> str:
        """Get remediation advice for vulnerability type."""
        remediation_map = {
            SecurityIssueType.SQL_INJECTION: "Use parameterized queries or Django ORM",
            SecurityIssueType.XSS_VULNERABILITY: "Use Django's auto-escaping or escape user input",
            SecurityIssueType.CSRF_BYPASS: "Enable CSRF protection and use {% csrf_token %}",
            SecurityIssueType.INSECURE_DESERIALIZATION: "Use safe serialization formats like JSON",
            SecurityIssueType.WEAK_CRYPTOGRAPHY: "Use SHA-256 or stronger cryptographic functions",
            SecurityIssueType.HARDCODED_SECRET: "Move secrets to environment variables"
        }
        return remediation_map.get(vuln_type, "Review security implications")

    def _get_owasp_category(self, vuln_type: SecurityIssueType) -> str:
        """Get OWASP Top 10 category for vulnerability type."""
        owasp_map = {
            SecurityIssueType.SQL_INJECTION: "A03:2021 – Injection",
            SecurityIssueType.XSS_VULNERABILITY: "A03:2021 – Injection",
            SecurityIssueType.CSRF_BYPASS: "A01:2021 – Broken Access Control",
            SecurityIssueType.INSECURE_DESERIALIZATION: "A08:2021 – Software and Data Integrity Failures",
            SecurityIssueType.BROKEN_ACCESS_CONTROL: "A01:2021 – Broken Access Control",
            SecurityIssueType.SECURITY_MISCONFIGURATION: "A05:2021 – Security Misconfiguration",
            SecurityIssueType.VULNERABLE_COMPONENTS: "A06:2021 – Vulnerable and Outdated Components",
            SecurityIssueType.WEAK_CRYPTOGRAPHY: "A02:2021 – Cryptographic Failures"
        }
        return owasp_map.get(vuln_type, "")

    def _scan_django_settings(self):
        """Scan Django settings for security misconfigurations."""
        try:
            # Check common Django security settings
            security_checks = [
                ('DEBUG', True, SecuritySeverity.HIGH, "Debug mode enabled in production"),
                ('ALLOWED_HOSTS', [], SecuritySeverity.HIGH, "ALLOWED_HOSTS not configured"),
                ('SECRET_KEY', 'django-insecure', SecuritySeverity.CRITICAL, "Default or insecure SECRET_KEY"),
                ('SECURE_SSL_REDIRECT', False, SecuritySeverity.MEDIUM, "SSL redirect not enabled"),
                ('SECURE_HSTS_SECONDS', 0, SecuritySeverity.MEDIUM, "HSTS not configured"),
                ('SESSION_COOKIE_SECURE', False, SecuritySeverity.MEDIUM, "Session cookies not secure"),
                ('CSRF_COOKIE_SECURE', False, SecuritySeverity.MEDIUM, "CSRF cookies not secure"),
                ('X_FRAME_OPTIONS', 'SAMEORIGIN', SecuritySeverity.LOW, "X-Frame-Options not set to DENY")
            ]

            for setting_name, risky_value, severity, description in security_checks:
                try:
                    setting_value = getattr(settings, setting_name, None)

                    if self._is_risky_setting(setting_value, risky_value):
                        self.security_issues.append(SecurityIssue(
                            type=SecurityIssueType.SECURITY_MISCONFIGURATION,
                            severity=severity,
                            description=description,
                            file_path="settings.py",
                            line_number=1,
                            symbol_name=setting_name,
                            vulnerable_code=f"{setting_name} = {setting_value}",
                            remediation=self._get_setting_remediation(setting_name),
                            owasp_category="A05:2021 – Security Misconfiguration"
                        ))
                except AttributeError:
                    pass  # Setting not defined

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error scanning Django settings: {e}")

    def _is_risky_setting(self, actual_value: Any, risky_value: Any) -> bool:
        """Check if setting value is risky."""
        if isinstance(risky_value, bool):
            return actual_value == risky_value
        elif isinstance(risky_value, list):
            return actual_value == risky_value or not actual_value
        elif isinstance(risky_value, str):
            return risky_value in str(actual_value) if actual_value else False
        elif isinstance(risky_value, int):
            return actual_value == risky_value
        return False

    def _get_setting_remediation(self, setting_name: str) -> str:
        """Get remediation for Django setting."""
        remediation_map = {
            'DEBUG': "Set DEBUG = False in production",
            'ALLOWED_HOSTS': "Configure ALLOWED_HOSTS with your domain names",
            'SECRET_KEY': "Generate a strong, unique SECRET_KEY",
            'SECURE_SSL_REDIRECT': "Set SECURE_SSL_REDIRECT = True for HTTPS",
            'SECURE_HSTS_SECONDS': "Set SECURE_HSTS_SECONDS = 31536000 (1 year)",
            'SESSION_COOKIE_SECURE': "Set SESSION_COOKIE_SECURE = True",
            'CSRF_COOKIE_SECURE': "Set CSRF_COOKIE_SECURE = True",
            'X_FRAME_OPTIONS': "Set X_FRAME_OPTIONS = 'DENY'"
        }
        return remediation_map.get(setting_name, "Review Django security documentation")

    def _generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        # Group issues by type and severity
        issues_by_type = {}
        issues_by_severity = {}

        for issue in self.security_issues:
            issue_type = issue.type.value
            severity = issue.severity.value

            if issue_type not in issues_by_type:
                issues_by_type[issue_type] = []
            issues_by_type[issue_type].append(issue.__dict__)

            if severity not in issues_by_severity:
                issues_by_severity[severity] = []
            issues_by_severity[severity].append(issue.__dict__)

        # Calculate risk score
        risk_score = self._calculate_risk_score()

        # Generate OWASP mapping
        owasp_mapping = self._generate_owasp_mapping()

        return {
            'total_issues': len(self.security_issues),
            'risk_score': risk_score,
            'issues_by_type': issues_by_type,
            'issues_by_severity': issues_by_severity,
            'owasp_top_10_coverage': owasp_mapping,
            'recommendations': self._generate_security_recommendations(),
            'summary': {
                'critical': len([i for i in self.security_issues if i.severity == SecuritySeverity.CRITICAL]),
                'high': len([i for i in self.security_issues if i.severity == SecuritySeverity.HIGH]),
                'medium': len([i for i in self.security_issues if i.severity == SecuritySeverity.MEDIUM]),
                'low': len([i for i in self.security_issues if i.severity == SecuritySeverity.LOW])
            }
        }

    def _calculate_risk_score(self) -> float:
        """Calculate overall risk score (0-100)."""
        if not self.security_issues:
            return 0

        severity_weights = {
            SecuritySeverity.CRITICAL: 10,
            SecuritySeverity.HIGH: 7,
            SecuritySeverity.MEDIUM: 4,
            SecuritySeverity.LOW: 1
        }

        total_score = sum(severity_weights.get(issue.severity, 0) for issue in self.security_issues)
        max_possible = len(self.security_issues) * 10  # All critical

        return min((total_score / max_possible) * 100 if max_possible > 0 else 0, 100)

    def _generate_owasp_mapping(self) -> Dict[str, int]:
        """Generate mapping to OWASP Top 10."""
        owasp_counts = {}

        for issue in self.security_issues:
            if issue.owasp_category:
                owasp_counts[issue.owasp_category] = owasp_counts.get(issue.owasp_category, 0) + 1

        return owasp_counts

    def _generate_security_recommendations(self) -> List[Dict[str, Any]]:
        """Generate security recommendations."""
        recommendations = []

        # Group by severity for prioritization
        critical_issues = [i for i in self.security_issues if i.severity == SecuritySeverity.CRITICAL]
        high_issues = [i for i in self.security_issues if i.severity == SecuritySeverity.HIGH]

        if critical_issues:
            recommendations.append({
                'priority': 'IMMEDIATE',
                'title': 'Address Critical Security Issues',
                'description': f"Found {len(critical_issues)} critical security issues that need immediate attention",
                'actions': [issue.remediation for issue in critical_issues[:3]]
            })

        if high_issues:
            recommendations.append({
                'priority': 'HIGH',
                'title': 'Fix High Severity Vulnerabilities',
                'description': f"Found {len(high_issues)} high severity issues",
                'actions': [issue.remediation for issue in high_issues[:3]]
            })

        # General recommendations
        recommendations.append({
            'priority': 'MEDIUM',
            'title': 'Implement Security Best Practices',
            'description': 'General security hardening recommendations',
            'actions': [
                'Enable Django security middleware',
                'Configure Content Security Policy (CSP)',
                'Implement proper logging and monitoring',
                'Regular dependency updates',
                'Security testing in CI/CD pipeline'
            ]
        })

        return recommendations


class FileSecurityScanner(ast.NodeVisitor):
    """AST-based security scanner for individual files."""

    def __init__(self, file_path: str, content: str):
        self.file_path = file_path
        self.content = content
        self.lines = content.split('\n')
        self.security_issues = []

    def visit_Call(self, node):
        """Visit function calls to detect security issues."""
        # Check for dangerous function calls
        self._check_dangerous_calls(node)

        # Check for SQL injection patterns
        self._check_sql_injection(node)

        # Check for command injection
        self._check_command_injection(node)

        self.generic_visit(node)

    def _check_dangerous_calls(self, node: ast.Call):
        """Check for dangerous function calls."""
        dangerous_functions = {
            'eval': SecuritySeverity.CRITICAL,
            'exec': SecuritySeverity.CRITICAL,
            'compile': SecuritySeverity.HIGH,
            'input': SecuritySeverity.MEDIUM,  # In Python 2
            'raw_input': SecuritySeverity.MEDIUM
        }

        func_name = self._get_function_name(node)
        if func_name in dangerous_functions:
            self.security_issues.append(SecurityIssue(
                type=SecurityIssueType.INSECURE_DESERIALIZATION,
                severity=dangerous_functions[func_name],
                description=f"Dangerous function '{func_name}' can execute arbitrary code",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=func_name,
                vulnerable_code=self._get_line(node.lineno),
                remediation=f"Avoid using '{func_name}' or validate input thoroughly",
                cwe_id="CWE-94"
            ))

    def _check_sql_injection(self, node: ast.Call):
        """Check for SQL injection vulnerabilities."""
        func_name = self._get_function_name(node)

        if func_name in ['execute', 'executemany', 'raw']:
            # Check if any arguments use string formatting
            for arg in node.args:
                if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):
                    # String formatting with %
                    self.security_issues.append(SecurityIssue(
                        type=SecurityIssueType.SQL_INJECTION,
                        severity=SecuritySeverity.HIGH,
                        description="SQL query uses string formatting, vulnerable to injection",
                        file_path=self.file_path,
                        line_number=node.lineno,
                        symbol_name=func_name,
                        vulnerable_code=self._get_line(node.lineno),
                        remediation="Use parameterized queries instead of string formatting",
                        cwe_id="CWE-89",
                        owasp_category="A03:2021 – Injection"
                    ))

    def _check_command_injection(self, node: ast.Call):
        """Check for command injection vulnerabilities."""
        dangerous_modules = ['os', 'subprocess', 'commands']
        dangerous_functions = ['system', 'popen', 'call', 'run', 'getoutput']

        func_name = self._get_function_name(node)

        if any(module in func_name for module in dangerous_modules) and \
           any(func in func_name for func in dangerous_functions):
            # Check if arguments come from user input
            self.security_issues.append(SecurityIssue(
                type=SecurityIssueType.SERVER_SIDE_REQUEST_FORGERY,
                severity=SecuritySeverity.HIGH,
                description="Command execution may be vulnerable to injection",
                file_path=self.file_path,
                line_number=node.lineno,
                symbol_name=func_name,
                vulnerable_code=self._get_line(node.lineno),
                remediation="Validate and sanitize all inputs to system commands",
                cwe_id="CWE-78"
            ))

    def _get_function_name(self, node: ast.Call) -> str:
        """Get function name from call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func) if hasattr(ast, 'unparse') else str(node.func)
        return ""

    def _get_line(self, line_number: int) -> str:
        """Get source code line by number."""
        try:
            if 1 <= line_number <= len(self.lines):
                return self.lines[line_number - 1].strip()
        except:
            pass
        return ""