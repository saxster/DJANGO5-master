#!/usr/bin/env python3
"""
Automated Code Smell Detection Script

Detects and reports on Python code quality issues:
1. Bare except blocks (violates .claude/rules.md Rule #11)
2. Backup/stub files creating import ambiguity
3. Oversized modules violating CLAUDE.md architectural limits

Usage:
    python scripts/detect_code_smells.py --report REPORT.md
    python scripts/detect_code_smells.py --json  # JSON output for CI/CD
    python scripts/detect_code_smells.py --check  # Exit 1 if violations found
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
APPS_DIR = BASE_DIR / "apps"
BACKGROUND_TASKS_DIR = BASE_DIR / "background_tasks"
SCRIPTS_DIR = BASE_DIR / "scripts"

# Architectural limits from CLAUDE.md
LIMITS = {
    'settings_file': 200,      # Settings files
    'model_class': 150,         # Model classes
    'view_method': 30,          # View methods (not enforced here, but documented)
    'form_class': 100,          # Form classes
    'utility_function': 50,     # Utility functions (not enforced here)
    'service_class': 150,       # Service classes
    'general_file': 500,        # General Python files (reasonable default)
}

# Patterns to detect
BARE_EXCEPT_PATTERN = re.compile(r'^\s*except\s*:\s*$', re.MULTILINE)
BACKUP_FILE_PATTERNS = [
    r'.*_refactored\.py$',
    r'.*_backup\.py$',
    r'.*_old\.py$',
    r'.*_temp\.py$',
    r'.*_stub\.py$',
    r'.*_legacy\.py$',
    r'.*\.bak.*$',
]

# Files to skip (documentation, migrations, etc.)
SKIP_PATTERNS = [
    r'.*/migrations/.*',
    r'.*/tests/.*\.py$',        # Tests allowed to have bare except for testing
    r'.*_test\.py$',
    r'.*\.md$',
    r'.*\.txt$',
    r'.*\.json$',
    r'.*\.yml$',
    r'.*\.yaml$',
]


@dataclass
class BareExceptViolation:
    """Represents a bare except block violation"""
    file_path: str
    line_number: int
    line_content: str
    context_before: List[str]
    context_after: List[str]
    severity: str = "HIGH"


@dataclass
class BackupFileViolation:
    """Represents a backup/stub file violation"""
    file_path: str
    pattern_matched: str
    file_size_bytes: int
    last_modified: str
    severity: str = "MEDIUM"


@dataclass
class OversizedFileViolation:
    """Represents an oversized file violation"""
    file_path: str
    line_count: int
    limit: int
    violation_ratio: float
    file_type: str
    severity: str


@dataclass
class CodeSmellReport:
    """Complete code smell detection report"""
    timestamp: str
    total_files_scanned: int
    bare_except_violations: List[BareExceptViolation]
    backup_file_violations: List[BackupFileViolation]
    oversized_file_violations: List[OversizedFileViolation]
    summary: Dict[str, int]


class CodeSmellDetector:
    """Main detector class for code smells"""

    def __init__(self, paths: List[Path], skip_tests: bool = False):
        self.paths = paths
        self.skip_tests = skip_tests
        self.files_scanned = 0
        self.bare_except_violations = []
        self.backup_file_violations = []
        self.oversized_file_violations = []

    def should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped"""
        file_str = str(file_path)

        # Skip test files if requested
        if self.skip_tests:
            if '/tests/' in file_str or file_str.endswith('_test.py'):
                return True

        # Skip based on patterns
        for pattern in SKIP_PATTERNS:
            if re.match(pattern, file_str):
                # But don't skip test files if we're not skipping tests
                if self.skip_tests or '/tests/' not in pattern:
                    return True

        return False

    def detect_bare_except(self, file_path: Path) -> List[BareExceptViolation]:
        """Detect bare except blocks in a Python file"""
        violations = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                if BARE_EXCEPT_PATTERN.match(line):
                    # Extract context
                    context_before = lines[max(0, i-3):i]
                    context_after = lines[i+1:min(len(lines), i+4)]

                    violations.append(BareExceptViolation(
                        file_path=str(file_path.relative_to(BASE_DIR)),
                        line_number=i + 1,
                        line_content=line.rstrip(),
                        context_before=[l.rstrip() for l in context_before],
                        context_after=[l.rstrip() for l in context_after],
                        severity="HIGH"
                    ))

        except Exception as e:
            print(f"Warning: Could not scan {file_path}: {e}", file=sys.stderr)

        return violations

    def detect_backup_files(self, file_path: Path) -> Optional[BackupFileViolation]:
        """Detect backup/stub files based on naming patterns"""
        file_str = str(file_path)

        for pattern in BACKUP_FILE_PATTERNS:
            if re.match(pattern, file_str):
                try:
                    stat = file_path.stat()
                    return BackupFileViolation(
                        file_path=str(file_path.relative_to(BASE_DIR)),
                        pattern_matched=pattern,
                        file_size_bytes=stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        severity="MEDIUM"
                    )
                except Exception as e:
                    print(f"Warning: Could not stat {file_path}: {e}", file=sys.stderr)

        return None

    def detect_oversized_file(self, file_path: Path) -> Optional[OversizedFileViolation]:
        """Detect files exceeding size limits"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)

            # Determine file type and limit
            file_str = str(file_path)
            file_type = "general"
            limit = LIMITS['general_file']

            if '/models/' in file_str or file_str.endswith('models.py'):
                file_type = "model"
                limit = LIMITS['model_class']
            elif '/services/' in file_str:
                file_type = "service"
                limit = LIMITS['service_class']
            elif '/forms/' in file_str or file_str.endswith('forms.py'):
                file_type = "form"
                limit = LIMITS['form_class']
            elif '/settings/' in file_str or 'settings.py' in file_str:
                file_type = "settings"
                limit = LIMITS['settings_file']

            if line_count > limit:
                violation_ratio = line_count / limit

                # Determine severity based on violation ratio
                if violation_ratio >= 10:
                    severity = "CRITICAL"
                elif violation_ratio >= 5:
                    severity = "HIGH"
                elif violation_ratio >= 2:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                return OversizedFileViolation(
                    file_path=str(file_path.relative_to(BASE_DIR)),
                    line_count=line_count,
                    limit=limit,
                    violation_ratio=round(violation_ratio, 1),
                    file_type=file_type,
                    severity=severity
                )

        except Exception as e:
            print(f"Warning: Could not check size of {file_path}: {e}", file=sys.stderr)

        return None

    def scan(self) -> CodeSmellReport:
        """Scan all files and generate report"""
        print(f"Scanning paths: {[str(p) for p in self.paths]}")

        for path in self.paths:
            if not path.exists():
                print(f"Warning: Path does not exist: {path}", file=sys.stderr)
                continue

            # Walk directory tree
            for root, dirs, files in os.walk(path):
                # Skip __pycache__ and .git directories
                dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'node_modules', '.venv', 'venv']]

                for file in files:
                    if not file.endswith('.py'):
                        continue

                    file_path = Path(root) / file

                    if self.should_skip_file(file_path):
                        continue

                    self.files_scanned += 1

                    # Run all detectors
                    self.bare_except_violations.extend(self.detect_bare_except(file_path))

                    backup_violation = self.detect_backup_files(file_path)
                    if backup_violation:
                        self.backup_file_violations.append(backup_violation)

                    oversized_violation = self.detect_oversized_file(file_path)
                    if oversized_violation:
                        self.oversized_file_violations.append(oversized_violation)

        # Generate summary
        summary = {
            'total_violations': (
                len(self.bare_except_violations) +
                len(self.backup_file_violations) +
                len(self.oversized_file_violations)
            ),
            'bare_except_count': len(self.bare_except_violations),
            'backup_file_count': len(self.backup_file_violations),
            'oversized_file_count': len(self.oversized_file_violations),
            'files_with_bare_except': len(set(v.file_path for v in self.bare_except_violations)),
            'critical_oversized_files': len([v for v in self.oversized_file_violations if v.severity == "CRITICAL"]),
        }

        return CodeSmellReport(
            timestamp=datetime.now().isoformat(),
            total_files_scanned=self.files_scanned,
            bare_except_violations=self.bare_except_violations,
            backup_file_violations=self.backup_file_violations,
            oversized_file_violations=self.oversized_file_violations,
            summary=summary
        )


def generate_markdown_report(report: CodeSmellReport, output_path: Optional[Path] = None) -> str:
    """Generate a human-readable Markdown report"""
    lines = []

    lines.append("# Code Smell Detection Report")
    lines.append(f"\n**Generated**: {report.timestamp}")
    lines.append(f"**Files Scanned**: {report.total_files_scanned}")
    lines.append(f"\n---\n")

    # Summary
    lines.append("## 📊 Executive Summary\n")
    lines.append(f"- **Total Violations**: {report.summary['total_violations']}")
    lines.append(f"- **Bare Except Blocks**: {report.summary['bare_except_count']} occurrences in {report.summary['files_with_bare_except']} files")
    lines.append(f"- **Backup/Stub Files**: {report.summary['backup_file_count']}")
    lines.append(f"- **Oversized Files**: {report.summary['oversized_file_count']} (including {report.summary['critical_oversized_files']} CRITICAL)")
    lines.append(f"\n---\n")

    # Bare Except Violations
    if report.bare_except_violations:
        lines.append("## ⚠️ Bare Except Blocks (HIGH Priority)\n")
        lines.append(f"**Total**: {len(report.bare_except_violations)} occurrences\n")
        lines.append("**Violates**: `.claude/rules.md` Rule #11 - Exception Handling Specificity\n")

        # Group by file
        by_file = defaultdict(list)
        for v in report.bare_except_violations:
            by_file[v.file_path].append(v)

        lines.append(f"**Files Affected**: {len(by_file)}\n")

        # Top 10 worst files
        sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)[:10]
        lines.append("### Top 10 Files by Violation Count\n")
        lines.append("| File | Occurrences | Lines |")
        lines.append("|------|-------------|-------|")
        for file_path, violations in sorted_files:
            line_numbers = ", ".join(str(v.line_number) for v in violations[:5])
            if len(violations) > 5:
                line_numbers += f", ... (+{len(violations)-5} more)"
            lines.append(f"| `{file_path}` | {len(violations)} | {line_numbers} |")

        lines.append("\n")

    # Backup File Violations
    if report.backup_file_violations:
        lines.append("## 🗑️ Backup/Stub Files (MEDIUM Priority)\n")
        lines.append(f"**Total**: {len(report.backup_file_violations)} files\n")
        lines.append("**Issue**: Creates import ambiguity and confusion\n")

        lines.append("### Files to Archive/Delete\n")
        lines.append("| File | Size | Last Modified |")
        lines.append("|------|------|---------------|")
        for v in sorted(report.backup_file_violations, key=lambda x: x.file_size_bytes, reverse=True):
            size_kb = v.file_size_bytes / 1024
            lines.append(f"| `{v.file_path}` | {size_kb:.1f} KB | {v.last_modified[:10]} |")

        lines.append("\n")

    # Oversized File Violations
    if report.oversized_file_violations:
        lines.append("## 📏 Oversized Files (CLAUDE.md Violations)\n")
        lines.append(f"**Total**: {len(report.oversized_file_violations)} files\n")

        # Group by severity
        by_severity = defaultdict(list)
        for v in report.oversized_file_violations:
            by_severity[v.severity].append(v)

        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            if severity not in by_severity:
                continue

            violations = by_severity[severity]
            lines.append(f"\n### {severity} Priority ({len(violations)} files)\n")
            lines.append("| File | Lines | Limit | Violation | Type |")
            lines.append("|------|-------|-------|-----------|------|")

            for v in sorted(violations, key=lambda x: x.violation_ratio, reverse=True):
                lines.append(f"| `{v.file_path}` | {v.line_count} | {v.limit} | **{v.violation_ratio}x** | {v.file_type} |")

        lines.append("\n")

    # Recommendations
    lines.append("## 🎯 Recommended Actions\n")

    if report.bare_except_violations:
        lines.append("### 1. Fix Bare Except Blocks")
        lines.append("```bash")
        lines.append("# Use the migration script:")
        lines.append("python scripts/migrate_exception_handling.py --analyze")
        lines.append("python scripts/migrate_exception_handling.py --fix --confidence HIGH")
        lines.append("```\n")

    if report.backup_file_violations:
        lines.append("### 2. Archive Backup Files")
        lines.append("```bash")
        lines.append("# Move to archive:")
        lines.append("mkdir -p .archive/removed_backup_files_$(date +%Y%m%d)")
        for v in report.backup_file_violations:
            lines.append(f"mv {v.file_path} .archive/removed_backup_files_$(date +%Y%m%d)/")
        lines.append("```\n")

    if report.oversized_file_violations:
        critical_files = [v for v in report.oversized_file_violations if v.severity == "CRITICAL"]
        if critical_files:
            lines.append("### 3. Refactor Critical Oversized Files (Priority 0)")
            for v in sorted(critical_files, key=lambda x: x.violation_ratio, reverse=True)[:5]:
                lines.append(f"- `{v.file_path}` ({v.line_count} lines → target: {v.limit} lines)")
        lines.append("\n")

    lines.append("---")
    lines.append(f"\n*Report generated by `scripts/detect_code_smells.py` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    report_content = "\n".join(lines)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"\n✅ Report saved to: {output_path}")

    return report_content


def main():
    parser = argparse.ArgumentParser(description="Detect Python code smells")
    parser.add_argument('--report', type=str, help='Output Markdown report to file')
    parser.add_argument('--json', action='store_true', help='Output JSON format')
    parser.add_argument('--check', action='store_true', help='Exit 1 if violations found (for CI/CD)')
    parser.add_argument('--skip-tests', action='store_true', help='Skip test files')
    parser.add_argument('--paths', nargs='*', help='Custom paths to scan (default: apps/ background_tasks/)')

    args = parser.parse_args()

    # Determine paths to scan
    if args.paths:
        scan_paths = [BASE_DIR / p for p in args.paths]
    else:
        scan_paths = [APPS_DIR, BACKGROUND_TASKS_DIR]

    # Run detection
    detector = CodeSmellDetector(scan_paths, skip_tests=args.skip_tests)
    report = detector.scan()

    # Output results
    if args.json:
        # Convert dataclasses to dict
        report_dict = asdict(report)
        print(json.dumps(report_dict, indent=2))
    else:
        # Generate markdown report
        output_path = Path(args.report) if args.report else None
        markdown = generate_markdown_report(report, output_path)

        if not args.report:
            print(markdown)

    # Check mode for CI/CD
    if args.check:
        if report.summary['total_violations'] > 0:
            print(f"\n❌ Found {report.summary['total_violations']} code smell violations", file=sys.stderr)
            sys.exit(1)
        else:
            print("\n✅ No code smell violations found")
            sys.exit(0)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Scan Complete: {report.summary['total_violations']} violations found")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
