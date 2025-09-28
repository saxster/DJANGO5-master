#!/usr/bin/env python3
"""
Exception Pattern Scanner - AST-based Generic Exception Detector

Identifies all generic 'except Exception:' patterns in the codebase,
categorizes by risk level, and generates detailed remediation reports.

Usage:
    python scripts/exception_scanner.py
    python scripts/exception_scanner.py --path apps/peoples
    python scripts/exception_scanner.py --format json --output report.json
"""

import ast
import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass, asdict


@dataclass
class ExceptionOccurrence:
    """Data class for tracking exception occurrences"""
    file_path: str
    line_number: int
    column_offset: int
    function_name: str
    class_name: str
    exception_type: str
    context_code: str
    risk_level: str
    suggested_exceptions: List[str]
    remediation_notes: str


class ExceptionScanner(ast.NodeVisitor):
    """AST visitor to identify generic exception handling patterns"""

    RISK_CATEGORIES = {
        'CRITICAL': ['auth', 'login', 'password', 'token', 'csrf', 'security', 'permission'],
        'HIGH': ['database', 'db', 'query', 'sql', 'transaction', 'integrity', 'migration'],
        'MEDIUM': ['graphql', 'mutation', 'api', 'service', 'file', 'upload', 'validation'],
        'LOW': ['util', 'helper', 'format', 'parse', 'cache', 'log']
    }

    EXCEPTION_SUGGESTIONS = {
        'auth': ['AuthenticationError', 'NoClientPeopleError', 'WrongCredsError', 'PermissionDeniedError'],
        'database': ['DatabaseError', 'IntegrityError', 'DatabaseIntegrityException', 'DoesNotExist'],
        'graphql': ['GraphQLException', 'ValidationError', 'SecurityException'],
        'file': ['FileValidationException', 'FileUploadSecurityException', 'FileOperationError'],
        'validation': ['EnhancedValidationException', 'FormValidationException', 'ModelValidationException'],
        'business': ['BusinessLogicException', 'BusinessRuleValidationException'],
        'integration': ['IntegrationException', 'APIException', 'LLMServiceException', 'MQTTException'],
        'system': ['SystemException', 'ConfigurationException', 'ServiceUnavailableException'],
    }

    def __init__(self, file_path: str, source_code: str):
        self.file_path = file_path
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.occurrences: List[ExceptionOccurrence] = []
        self.current_function = None
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track current function context"""
        parent_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = parent_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track current async function context"""
        parent_function = self.current_function
        self.current_function = f"async_{node.name}"
        self.generic_visit(node)
        self.current_function = parent_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track current class context"""
        parent_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = parent_class

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Identify generic exception handling patterns"""
        if node.type:
            exception_name = self._get_exception_name(node.type)

            if exception_name == "Exception" or exception_name == "BaseException":
                occurrence = self._create_occurrence(node, exception_name)
                self.occurrences.append(occurrence)
        else:
            occurrence = self._create_occurrence(node, "bare_except")
            self.occurrences.append(occurrence)

        self.generic_visit(node)

    def _get_exception_name(self, node: ast.expr) -> str:
        """Extract exception name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Tuple):
            return "Multiple"
        elif isinstance(node, ast.Attribute):
            return node.attr
        return "Unknown"

    def _create_occurrence(self, node: ast.ExceptHandler, exception_type: str) -> ExceptionOccurrence:
        """Create detailed occurrence record"""
        context_code = self._get_context_code(node.lineno)
        risk_level = self._determine_risk_level()
        suggested_exceptions = self._suggest_exceptions()
        remediation_notes = self._generate_remediation_notes(risk_level)

        return ExceptionOccurrence(
            file_path=self.file_path,
            line_number=node.lineno,
            column_offset=node.col_offset,
            function_name=self.current_function or "module_level",
            class_name=self.current_class or "N/A",
            exception_type=exception_type,
            context_code=context_code,
            risk_level=risk_level,
            suggested_exceptions=suggested_exceptions,
            remediation_notes=remediation_notes
        )

    def _get_context_code(self, line_number: int, context_lines: int = 3) -> str:
        """Extract code context around exception"""
        start = max(0, line_number - context_lines - 1)
        end = min(len(self.source_lines), line_number + context_lines)

        context = []
        for i in range(start, end):
            prefix = ">>> " if i == line_number - 1 else "    "
            context.append(f"{prefix}{i+1:4d}: {self.source_lines[i]}")

        return "\n".join(context)

    def _determine_risk_level(self) -> str:
        """Determine risk level based on file path and context"""
        file_lower = self.file_path.lower()
        func_lower = (self.current_function or "").lower()

        for risk_level, keywords in self.RISK_CATEGORIES.items():
            if any(keyword in file_lower or keyword in func_lower for keyword in keywords):
                return risk_level

        return "LOW"

    def _suggest_exceptions(self) -> List[str]:
        """Suggest appropriate exception types based on context"""
        file_lower = self.file_path.lower()
        func_lower = (self.current_function or "").lower()
        class_lower = (self.current_class or "").lower()
        suggestions = set()

        for category, exceptions in self.EXCEPTION_SUGGESTIONS.items():
            if (category in file_lower or
                category in func_lower or
                category in class_lower or
                any(keyword in file_lower for keyword in self._get_category_keywords(category))):
                suggestions.update(exceptions)

        if not suggestions:
            suggestions = {'ValidationError', 'DatabaseError', 'BusinessLogicException'}

        return sorted(list(suggestions))[:5]

    def _get_category_keywords(self, category: str) -> List[str]:
        """Get additional keywords for better context detection"""
        keyword_map = {
            'auth': ['login', 'authenticate', 'permission', 'token', 'credential'],
            'database': ['query', 'filter', 'save', 'create', 'update', 'delete', 'orm'],
            'graphql': ['mutation', 'resolver', 'schema', 'query_type'],
            'file': ['upload', 'download', 'path', 'storage'],
            'validation': ['clean', 'validate', 'form', 'is_valid'],
            'business': ['process', 'handle', 'execute', 'perform'],
            'integration': ['api', 'client', 'service', 'external'],
        }
        return keyword_map.get(category, [])

    def _generate_remediation_notes(self, risk_level: str) -> str:
        """Generate context-specific remediation guidance"""
        notes = []

        if risk_level == "CRITICAL":
            notes.append("🚨 CRITICAL: Security vulnerability - immediate fix required")
            notes.append("Review for authentication bypass, credential exposure, or CSRF vulnerabilities")
            notes.append("Priority: FIX IMMEDIATELY")
        elif risk_level == "HIGH":
            notes.append("⚠️ HIGH: Data integrity risk - prioritize fix")
            notes.append("Review for database errors, data corruption, or transaction failures")
            notes.append("Priority: FIX IN PHASE 2")
        elif risk_level == "MEDIUM":
            notes.append("⚡ MEDIUM: Business logic risk - schedule fix")
            notes.append("Review for API errors, validation failures, or integration issues")
            notes.append("Priority: FIX IN PHASE 3")
        else:
            notes.append("ℹ️ LOW: Code quality improvement - fix when convenient")
            notes.append("Priority: FIX IN PHASE 4")

        notes.append(f"Location: {self.file_path}:{self.current_function or 'module'}")
        notes.append("Action: Replace with specific exception types from apps.core.exceptions")
        notes.append(f"Automated fixer: python scripts/exception_fixer.py --file {self.file_path} --line {self.occurrences[-1].line_number if self.occurrences else 0}" if hasattr(self, 'occurrences') else "")

        return " | ".join(notes)


class ExceptionScannerReport:
    """Generate comprehensive remediation reports"""

    def __init__(self, occurrences: List[ExceptionOccurrence]):
        self.occurrences = occurrences
        self.stats = self._calculate_statistics()

    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate comprehensive statistics"""
        files = defaultdict(int)
        risk_levels = defaultdict(int)
        modules = defaultdict(int)

        for occ in self.occurrences:
            files[occ.file_path] += 1
            risk_levels[occ.risk_level] += 1

            module = self._extract_module(occ.file_path)
            modules[module] += 1

        return {
            'total_occurrences': len(self.occurrences),
            'affected_files': len(files),
            'by_risk_level': dict(risk_levels),
            'by_module': dict(modules),
            'top_offenders': sorted(files.items(), key=lambda x: x[1], reverse=True)[:10]
        }

    def _extract_module(self, file_path: str) -> str:
        """Extract module name from file path"""
        if '/apps/' in file_path:
            parts = file_path.split('/apps/')[1].split('/')
            return f"apps.{parts[0]}"
        return "other"

    def generate_console_report(self) -> str:
        """Generate human-readable console report"""
        lines = []
        lines.append("=" * 80)
        lines.append("🔍 GENERIC EXCEPTION HANDLING SCANNER REPORT")
        lines.append("=" * 80)
        lines.append("")

        lines.append("📊 SUMMARY STATISTICS")
        lines.append("-" * 80)
        lines.append(f"Total occurrences found: {self.stats['total_occurrences']}")
        lines.append(f"Affected files: {self.stats['affected_files']}")
        lines.append("")

        lines.append("🚨 BY RISK LEVEL")
        lines.append("-" * 80)
        for risk_level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = self.stats['by_risk_level'].get(risk_level, 0)
            percentage = (count / self.stats['total_occurrences'] * 100) if self.stats['total_occurrences'] > 0 else 0
            lines.append(f"{risk_level:10s}: {count:5d} ({percentage:5.1f}%)")
        lines.append("")

        lines.append("🏆 TOP 10 OFFENDERS")
        lines.append("-" * 80)
        for i, (file_path, count) in enumerate(self.stats['top_offenders'], 1):
            lines.append(f"{i:2d}. {file_path:60s} ({count:3d} occurrences)")
        lines.append("")

        lines.append("📦 BY MODULE")
        lines.append("-" * 80)
        sorted_modules = sorted(self.stats['by_module'].items(), key=lambda x: x[1], reverse=True)
        for module, count in sorted_modules[:15]:
            lines.append(f"{module:30s}: {count:5d} occurrences")
        lines.append("")

        lines.append("🎯 CRITICAL INSTANCES REQUIRING IMMEDIATE ATTENTION")
        lines.append("-" * 80)
        critical = [occ for occ in self.occurrences if occ.risk_level == "CRITICAL"][:5]
        for occ in critical:
            lines.append(f"\nFile: {occ.file_path}:{occ.line_number}")
            lines.append(f"Function: {occ.function_name}")
            lines.append(f"Suggested: {', '.join(occ.suggested_exceptions[:3])}")
            lines.append(f"Notes: {occ.remediation_notes[:100]}")

        lines.append("")
        lines.append("=" * 80)
        lines.append("📋 REMEDIATION RECOMMENDATIONS")
        lines.append("=" * 80)
        lines.append("")
        lines.append("1. Start with CRITICAL risk files (authentication, security)")
        lines.append("2. Use automated fixer tool: python scripts/exception_fixer.py")
        lines.append("3. Review suggested exceptions in detailed report")
        lines.append("4. Run tests after each module remediation")
        lines.append("5. Enable pre-commit hooks to prevent new violations")
        lines.append("")

        return "\n".join(lines)

    def generate_json_report(self) -> Dict[str, Any]:
        """Generate machine-readable JSON report"""
        return {
            'metadata': {
                'scan_timestamp': str(Path.cwd()),
                'total_occurrences': self.stats['total_occurrences'],
                'affected_files': self.stats['affected_files']
            },
            'statistics': self.stats,
            'occurrences': [asdict(occ) for occ in self.occurrences]
        }

    def generate_csv_report(self) -> str:
        """Generate CSV report for spreadsheet analysis"""
        lines = []
        lines.append("File,Line,Function,Class,Risk Level,Exception Type,Suggested Exceptions")

        for occ in self.occurrences:
            suggested = "; ".join(occ.suggested_exceptions)
            lines.append(f'"{occ.file_path}",{occ.line_number},"{occ.function_name}","{occ.class_name}",{occ.risk_level},{occ.exception_type},"{suggested}"')

        return "\n".join(lines)

    def generate_priority_fix_list(self) -> str:
        """Generate prioritized list of files to fix in order"""
        lines = []
        lines.append("=" * 80)
        lines.append("🎯 PRIORITIZED FIX LIST - Execute in this order")
        lines.append("=" * 80)
        lines.append("")

        priority_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        file_groups = defaultdict(lambda: {'count': 0, 'risk': 'LOW', 'occurrences': []})

        for occ in self.occurrences:
            file_groups[occ.file_path]['count'] += 1
            file_groups[occ.file_path]['occurrences'].append(occ)
            current_risk_idx = priority_order.index(file_groups[occ.file_path]['risk'])
            new_risk_idx = priority_order.index(occ.risk_level)
            if new_risk_idx < current_risk_idx:
                file_groups[occ.file_path]['risk'] = occ.risk_level

        sorted_files = sorted(
            file_groups.items(),
            key=lambda x: (priority_order.index(x[1]['risk']), -x[1]['count'])
        )

        for risk_level in priority_order:
            risk_files = [(f, data) for f, data in sorted_files if data['risk'] == risk_level]
            if not risk_files:
                continue

            lines.append(f"\n{'='*80}")
            lines.append(f"{risk_level} PRIORITY - {len(risk_files)} files")
            lines.append(f"{'='*80}\n")

            for idx, (file_path, data) in enumerate(risk_files, 1):
                lines.append(f"{idx}. {file_path}")
                lines.append(f"   Occurrences: {data['count']}")
                lines.append(f"   Risk Level: {data['risk']}")
                unique_suggestions = set()
                for occ in data['occurrences']:
                    unique_suggestions.update(occ.suggested_exceptions)
                lines.append(f"   Suggested Exceptions: {', '.join(sorted(list(unique_suggestions))[:5])}")
                lines.append(f"   Fix Command: python scripts/exception_fixer.py --file {file_path}")
                lines.append("")

        return "\n".join(lines)


def scan_file(file_path: str) -> List[ExceptionOccurrence]:
    """Scan a single Python file for generic exceptions"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()

        tree = ast.parse(source_code, filename=file_path)
        scanner = ExceptionScanner(file_path, source_code)
        scanner.visit(tree)

        return scanner.occurrences

    except SyntaxError as e:
        print(f"⚠️  Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"❌ Error scanning {file_path}: {e}", file=sys.stderr)
        return []


def scan_directory(directory: str, exclude_patterns: List[str] = None) -> List[ExceptionOccurrence]:
    """Recursively scan directory for Python files"""
    if exclude_patterns is None:
        exclude_patterns = ['venv', 'migrations', '__pycache__', '.git', 'node_modules']

    all_occurrences = []
    directory_path = Path(directory)

    for py_file in directory_path.rglob('*.py'):
        if any(pattern in str(py_file) for pattern in exclude_patterns):
            continue

        print(f"Scanning: {py_file}")
        occurrences = scan_file(str(py_file))
        all_occurrences.extend(occurrences)

    return all_occurrences


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Scan codebase for generic exception handling patterns'
    )
    parser.add_argument(
        '--path',
        default='apps',
        help='Path to scan (default: apps)'
    )
    parser.add_argument(
        '--format',
        choices=['console', 'json', 'csv'],
        default='console',
        help='Output format (default: console)'
    )
    parser.add_argument(
        '--output',
        help='Output file path (default: stdout)'
    )
    parser.add_argument(
        '--exclude',
        nargs='+',
        default=['venv', 'migrations', '__pycache__', '.git'],
        help='Patterns to exclude'
    )
    parser.add_argument(
        '--priority-list',
        action='store_true',
        help='Generate prioritized fix list'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Fail with exit code 1 if any violations found (CI/CD mode)'
    )
    parser.add_argument(
        '--fail-on-violations',
        action='store_true',
        help='Fail with exit code 1 if any violations found (alias for --strict)'
    )

    args = parser.parse_args()

    print(f"🔍 Scanning directory: {args.path}")
    print(f"📝 Output format: {args.format}")
    if args.strict or args.fail_on_violations:
        print(f"⚠️  Strict mode enabled - will fail on violations")
    print("")

    occurrences = scan_directory(args.path, args.exclude)
    report = ExceptionScannerReport(occurrences)

    if args.priority_list:
        output = report.generate_priority_fix_list()
    elif args.format == 'console':
        output = report.generate_console_report()
    elif args.format == 'json':
        output = json.dumps(report.generate_json_report(), indent=2)
    elif args.format == 'csv':
        output = report.generate_csv_report()

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"✅ Report saved to: {args.output}")
    else:
        print(output)

    print(f"\n✅ Scan complete: {len(occurrences)} occurrences found in {report.stats['affected_files']} files")

    if occurrences:
        critical_count = sum(1 for occ in occurrences if occ.risk_level == "CRITICAL")
        if critical_count > 0:
            print(f"\n🚨 WARNING: {critical_count} CRITICAL security issues found - immediate action required!")
            if args.strict or args.fail_on_violations:
                sys.exit(1)
        elif args.strict or args.fail_on_violations:
            print(f"\n❌ STRICT MODE: {len(occurrences)} violations found - failing build")
            sys.exit(1)


if __name__ == '__main__':
    main()