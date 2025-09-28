"""
SQL Injection Static Analysis Scanner

This module provides static analysis tools to detect potential SQL injection
vulnerabilities in Python code, specifically targeting dangerous f-string
and string concatenation patterns in SQL queries.
"""

import ast
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SQLInjectionVulnerability:
    """Represents a potential SQL injection vulnerability found in code."""
    file_path: str
    line_number: int
    column: int
    vulnerability_type: str
    code_snippet: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    description: str
    recommendation: str


class SQLInjectionScanner:
    """Static analysis scanner for SQL injection vulnerabilities."""

    def __init__(self):
        self.vulnerabilities: List[SQLInjectionVulnerability] = []

        # Dangerous SQL patterns using f-strings
        self.dangerous_fstring_patterns = [
            r'f".*SELECT.*{.*}.*"',
            r'f".*INSERT.*{.*}.*"',
            r'f".*UPDATE.*{.*}.*"',
            r'f".*DELETE.*{.*}.*"',
            r'f".*DROP.*{.*}.*"',
            r'f".*CREATE.*{.*}.*"',
            r'f".*ALTER.*{.*}.*"',
            r'f".*EXEC.*{.*}.*"',
        ]

        # Dangerous string concatenation patterns
        self.dangerous_concat_patterns = [
            r'"SELECT.*"\s*\+.*\+.*"',
            r'"INSERT.*"\s*\+.*\+.*"',
            r'"UPDATE.*"\s*\+.*\+.*"',
            r'"DELETE.*"\s*\+.*\+.*"',
        ]

        # Safe patterns that are allowed
        self.safe_patterns = [
            r'\.execute\(["\'].*["\'],\s*\[.*\]',  # Parameterized queries
            r'SecureSQL\.',  # Using SecureSQL utilities
            r'cursor\.execute\(["\'].*%s.*["\'],',  # Parameterized with %s
        ]

    def scan_file(self, file_path: Path) -> List[SQLInjectionVulnerability]:
        """
        Scan a single Python file for SQL injection vulnerabilities.

        Args:
            file_path: Path to the Python file to scan

        Returns:
            List of vulnerabilities found
        """
        vulnerabilities = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()

            # Parse AST for more accurate analysis
            tree = ast.parse(content)
            vulnerabilities.extend(self._analyze_ast(tree, file_path, lines))

            # Pattern-based analysis as backup
            vulnerabilities.extend(self._analyze_patterns(content, file_path, lines))

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            logger.error(f"Error scanning file {file_path}: {e}")

        return vulnerabilities

    def scan_directory(self, directory: Path, exclude_dirs: Optional[Set[str]] = None) -> List[SQLInjectionVulnerability]:
        """
        Recursively scan a directory for SQL injection vulnerabilities.

        Args:
            directory: Directory to scan
            exclude_dirs: Set of directory names to exclude

        Returns:
            List of all vulnerabilities found
        """
        if exclude_dirs is None:
            exclude_dirs = {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'venv', 'env'}

        vulnerabilities = []

        for python_file in directory.rglob('*.py'):
            # Skip excluded directories
            if any(excluded in python_file.parts for excluded in exclude_dirs):
                continue

            file_vulnerabilities = self.scan_file(python_file)
            vulnerabilities.extend(file_vulnerabilities)

        return vulnerabilities

    def _analyze_ast(self, tree: ast.AST, file_path: Path, lines: List[str]) -> List[SQLInjectionVulnerability]:
        """Analyze AST for SQL injection patterns."""
        vulnerabilities = []

        class SQLInjectionVisitor(ast.NodeVisitor):
            def __init__(self, scanner):
                self.scanner = scanner
                self.vulnerabilities = []

            def visit_JoinedStr(self, node):
                """Visit f-string nodes."""
                # Check if this f-string contains SQL keywords
                if hasattr(node, 'lineno') and node.lineno <= len(lines):
                    line_content = lines[node.lineno - 1]
                    if self._contains_sql_keywords(line_content):
                        vuln = SQLInjectionVulnerability(
                            file_path=str(file_path),
                            line_number=node.lineno,
                            column=getattr(node, 'col_offset', 0),
                            vulnerability_type='f-string SQL injection',
                            code_snippet=line_content.strip(),
                            severity='critical',
                            description='F-string interpolation in SQL query detected',
                            recommendation='Use parameterized queries or SecureSQL utilities'
                        )
                        self.vulnerabilities.append(vuln)

                self.generic_visit(node)

            def visit_BinOp(self, node):
                """Visit binary operations (string concatenation)."""
                if isinstance(node.op, ast.Add):
                    # Check for string concatenation with SQL
                    if hasattr(node, 'lineno') and node.lineno <= len(lines):
                        line_content = lines[node.lineno - 1]
                        if self._contains_sql_keywords(line_content) and '+' in line_content:
                            vuln = SQLInjectionVulnerability(
                                file_path=str(file_path),
                                line_number=node.lineno,
                                column=getattr(node, 'col_offset', 0),
                                vulnerability_type='string concatenation SQL injection',
                                code_snippet=line_content.strip(),
                                severity='high',
                                description='String concatenation in SQL query detected',
                                recommendation='Use parameterized queries instead of string concatenation'
                            )
                            self.vulnerabilities.append(vuln)

                self.generic_visit(node)

            def _contains_sql_keywords(self, line: str) -> bool:
                """Check if line contains SQL keywords."""
                sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'EXEC']
                line_upper = line.upper()
                return any(keyword in line_upper for keyword in sql_keywords)

        visitor = SQLInjectionVisitor(self)
        visitor.visit(tree)
        vulnerabilities.extend(visitor.vulnerabilities)

        return vulnerabilities

    def _analyze_patterns(self, content: str, file_path: Path, lines: List[str]) -> List[SQLInjectionVulnerability]:
        """Pattern-based analysis for SQL injection vulnerabilities."""
        vulnerabilities = []

        # Check for dangerous f-string patterns
        for pattern in self.dangerous_fstring_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                line_no = content[:match.start()].count('\n') + 1

                # Skip if this is a safe pattern
                line_content = lines[line_no - 1] if line_no <= len(lines) else ""
                if self._is_safe_pattern(line_content):
                    continue

                vuln = SQLInjectionVulnerability(
                    file_path=str(file_path),
                    line_number=line_no,
                    column=match.start(),
                    vulnerability_type='f-string SQL injection',
                    code_snippet=line_content.strip(),
                    severity='critical',
                    description='Dangerous f-string SQL pattern detected',
                    recommendation='Use SecureSQL.build_safe_sqlite_count_query() or parameterized queries'
                )
                vulnerabilities.append(vuln)

        # Check for dangerous concatenation patterns
        for pattern in self.dangerous_concat_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                line_no = content[:match.start()].count('\n') + 1
                line_content = lines[line_no - 1] if line_no <= len(lines) else ""

                if self._is_safe_pattern(line_content):
                    continue

                vuln = SQLInjectionVulnerability(
                    file_path=str(file_path),
                    line_number=line_no,
                    column=match.start(),
                    vulnerability_type='string concatenation SQL injection',
                    code_snippet=line_content.strip(),
                    severity='high',
                    description='Dangerous string concatenation SQL pattern detected',
                    recommendation='Use parameterized queries with %s placeholders'
                )
                vulnerabilities.append(vuln)

        return vulnerabilities

    def _is_safe_pattern(self, line: str) -> bool:
        """Check if a line matches safe SQL patterns."""
        return any(re.search(pattern, line, re.IGNORECASE) for pattern in self.safe_patterns)

    def generate_report(self, vulnerabilities: List[SQLInjectionVulnerability]) -> Dict[str, Any]:
        """
        Generate a comprehensive security report.

        Args:
            vulnerabilities: List of vulnerabilities to include in report

        Returns:
            Dictionary containing the security report
        """
        report = {
            'scan_timestamp': str(datetime.now()),
            'total_vulnerabilities': len(vulnerabilities),
            'severity_breakdown': {
                'critical': len([v for v in vulnerabilities if v.severity == 'critical']),
                'high': len([v for v in vulnerabilities if v.severity == 'high']),
                'medium': len([v for v in vulnerabilities if v.severity == 'medium']),
                'low': len([v for v in vulnerabilities if v.severity == 'low']),
            },
            'vulnerability_types': {},
            'affected_files': set(),
            'vulnerabilities': []
        }

        # Group by vulnerability type
        for vuln in vulnerabilities:
            vuln_type = vuln.vulnerability_type
            if vuln_type not in report['vulnerability_types']:
                report['vulnerability_types'][vuln_type] = 0
            report['vulnerability_types'][vuln_type] += 1

            report['affected_files'].add(vuln.file_path)

            # Add to detailed list
            report['vulnerabilities'].append({
                'file': vuln.file_path,
                'line': vuln.line_number,
                'column': vuln.column,
                'type': vuln.vulnerability_type,
                'severity': vuln.severity,
                'code': vuln.code_snippet,
                'description': vuln.description,
                'recommendation': vuln.recommendation
            })

        report['affected_files'] = list(report['affected_files'])
        return report

    def save_report(self, report: Dict[str, Any], output_path: Path) -> None:
        """Save security report to JSON file."""
        import json

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Security report saved to {output_path}")


def main():
    """Command-line interface for the SQL injection scanner."""
    import argparse
    from datetime import datetime

    parser = argparse.ArgumentParser(description='Scan for SQL injection vulnerabilities')
    parser.add_argument('path', help='Path to scan (file or directory)')
    parser.add_argument('--output', '-o', help='Output report file path')
    parser.add_argument('--format', choices=['json', 'text'], default='text', help='Output format')

    args = parser.parse_args()

    scanner = SQLInjectionScanner()
    scan_path = Path(args.path)

    if scan_path.is_file():
        vulnerabilities = scanner.scan_file(scan_path)
    else:
        vulnerabilities = scanner.scan_directory(scan_path)

    # Generate report
    report = scanner.generate_report(vulnerabilities)

    if args.output:
        if args.format == 'json':
            scanner.save_report(report, Path(args.output))
        else:
            # Text format
            with open(args.output, 'w') as f:
                f.write(f"SQL Injection Security Scan Report\n")
                f.write(f"Generated: {report['scan_timestamp']}\n\n")
                f.write(f"Total Vulnerabilities: {report['total_vulnerabilities']}\n")
                f.write(f"Critical: {report['severity_breakdown']['critical']}\n")
                f.write(f"High: {report['severity_breakdown']['high']}\n")
                f.write(f"Medium: {report['severity_breakdown']['medium']}\n")
                f.write(f"Low: {report['severity_breakdown']['low']}\n\n")

                for vuln in report['vulnerabilities']:
                    f.write(f"[{vuln['severity'].upper()}] {vuln['file']}:{vuln['line']}\n")
                    f.write(f"Type: {vuln['type']}\n")
                    f.write(f"Code: {vuln['code']}\n")
                    f.write(f"Description: {vuln['description']}\n")
                    f.write(f"Recommendation: {vuln['recommendation']}\n\n")
    else:
        # Print to console
        print(f"SQL Injection Security Scan Report")
        print(f"Total Vulnerabilities: {report['total_vulnerabilities']}")
        print(f"Critical: {report['severity_breakdown']['critical']}")
        print(f"High: {report['severity_breakdown']['high']}")

        for vuln in report['vulnerabilities']:
            print(f"\n[{vuln['severity'].upper()}] {vuln['file']}:{vuln['line']}")
            print(f"  {vuln['description']}")
            print(f"  Code: {vuln['code']}")


if __name__ == '__main__':
    main()