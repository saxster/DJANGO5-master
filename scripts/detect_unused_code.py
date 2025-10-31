#!/usr/bin/env python3
"""
Automated Unused Code Detection Script

Scans codebase for potential unused/stale code artifacts:
- *_refactored.py backup files
- *_backup.py files
- *_old.py files
- *UNUSED* directories
- Commented-out code blocks (heuristic)

Usage:
    python scripts/detect_unused_code.py
    python scripts/detect_unused_code.py --verbose
    python scripts/detect_unused_code.py --report unused_code_report.md

Created: 2025-10-10
Purpose: Code Quality Remediation (Nice-To-Haves Phase 3)
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from datetime import datetime


class UnusedCodeDetector:
    """Detects potential unused code in the codebase"""

    def __init__(self, project_root: Path, verbose: bool = False):
        self.project_root = project_root
        self.verbose = verbose
        self.findings: Dict[str, List[Dict]] = defaultdict(list)

        # Exclusion patterns
        self.exclude_dirs = [
            'venv', 'env', '.venv', 'node_modules', '.git',
            '__pycache__', '.pytest_cache', '.mypy_cache',
            'build', 'dist', '.eggs', '*.egg-info',
            '.archive'  # Already archived
        ]

    def log(self, message: str, level: str = 'INFO'):
        """Log message if verbose"""
        if self.verbose or level == 'ERROR':
            prefix = {'INFO': 'ℹ️', 'WARN': '⚠️', 'ERROR': '❌'}.get(level, '')
            print(f"{prefix}  {message}")

    def should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded"""
        path_str = str(path)
        return any(excl in path_str for excl in self.exclude_dirs)

    def detect_backup_files(self):
        """Find *_refactored.py, *_backup.py, *_old.py files"""
        self.log("Searching for backup/refactored files...")

        patterns = ['*_refactored.py', '*_backup.py', '*_old.py', '*_temp.py']

        for pattern in patterns:
            for file in self.project_root.rglob(pattern):
                if self.should_exclude(file):
                    continue

                rel_path = file.relative_to(self.project_root)
                file_size = file.stat().st_size / 1024  # KB

                self.findings['backup_files'].append({
                    'path': str(rel_path),
                    'size_kb': round(file_size, 2),
                    'pattern': pattern,
                    'last_modified': datetime.fromtimestamp(file.stat().st_mtime).strftime('%Y-%m-%d')
                })

        self.log(f"Found {len(self.findings['backup_files'])} backup files")

    def detect_unused_directories(self):
        """Find *UNUSED*, *_old, *_deprecated directories"""
        self.log("Searching for unused/deprecated directories...")

        patterns = ['*UNUSED*', '*_old', '*_deprecated', '*_archive']

        for root, dirs, _ in os.walk(self.project_root):
            root_path = Path(root)

            if self.should_exclude(root_path):
                continue

            for dir_name in dirs:
                if any(re.match(pattern.replace('*', '.*'), dir_name) for pattern in patterns):
                    dir_path = root_path / dir_name
                    rel_path = dir_path.relative_to(self.project_root)

                    # Count files in directory
                    file_count = sum(1 for _ in dir_path.rglob('*') if _.is_file())

                    self.findings['unused_dirs'].append({
                        'path': str(rel_path),
                        'file_count': file_count,
                        'last_modified': datetime.fromtimestamp(dir_path.stat().st_mtime).strftime('%Y-%m-%d')
                    })

        self.log(f"Found {len(self.findings['unused_dirs'])} unused directories")

    def detect_commented_code(self):
        """Find large blocks of commented-out code (heuristic)"""
        self.log("Searching for large commented code blocks...")

        threshold = 10  # lines

        for py_file in self.project_root.rglob('*.py'):
            if self.should_exclude(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                comment_block = []
                in_block = False

                for line_num, line in enumerate(lines, 1):
                    stripped = line.strip()

                    # Detect comment lines
                    if stripped.startswith('#'):
                        if not in_block:
                            in_block = True
                            comment_block = [(line_num, line)]
                        else:
                            comment_block.append((line_num, line))
                    else:
                        # End of block
                        if in_block and len(comment_block) >= threshold:
                            # Heuristic: check if looks like code
                            code_like = sum(1 for _, l in comment_block if any(
                                keyword in l for keyword in
                                ['def ', 'class ', 'import ', 'from ', 'if ', 'for ', 'while ']
                            ))

                            if code_like > len(comment_block) * 0.3:  # >30% looks like code
                                rel_path = py_file.relative_to(self.project_root)
                                start_line = comment_block[0][0]
                                end_line = comment_block[-1][0]

                                self.findings['commented_code'].append({
                                    'path': str(rel_path),
                                    'start_line': start_line,
                                    'end_line': end_line,
                                    'lines': len(comment_block)
                                })

                        in_block = False
                        comment_block = []

            except Exception as e:
                if self.verbose:
                    self.log(f"Error scanning {py_file}: {e}", 'WARN')

        self.log(f"Found {len(self.findings['commented_code'])} large commented code blocks")

    def run_all_detections(self):
        """Run all detection methods"""
        self.detect_backup_files()
        self.detect_unused_directories()
        self.detect_commented_code()

    def generate_report(self, output_file: str = None) -> str:
        """Generate markdown report"""
        lines = [
            "# Unused Code Detection Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Project Root:** `{self.project_root}`",
            "",
            "---",
            ""
        ]

        # Summary
        total = sum(len(v) for v in self.findings.values())
        lines.extend([
            "## 📊 Summary",
            "",
            f"- **Total Issues:** {total}",
            f"- **Backup Files:** {len(self.findings['backup_files'])}",
            f"- **Unused Directories:** {len(self.findings['unused_dirs'])}",
            f"- **Commented Code Blocks:** {len(self.findings['commented_code'])}",
            "",
            "---",
            ""
        ])

        # Backup Files
        if self.findings['backup_files']:
            lines.extend([
                "## 🗑️  Backup/Refactored Files",
                "",
                f"Found **{len(self.findings['backup_files'])}** backup files to archive:",
                "",
                "| File | Size (KB) | Last Modified | Pattern |",
                "|------|-----------|---------------|---------|"
            ])

            for item in sorted(self.findings['backup_files'], key=lambda x: x['size_kb'], reverse=True):
                lines.append(
                    f"| `{item['path']}` | {item['size_kb']} | {item['last_modified']} | `{item['pattern']}` |"
                )

            lines.extend(["", "**Recommended Action:**", "```bash", "mkdir -p .archive/unused_code_$(date +%Y%m%d)"])
            for item in self.findings['backup_files']:
                lines.append(f"mv {item['path']} .archive/unused_code_$(date +%Y%m%d)/")
            lines.extend(["```", "", "---", ""])

        # Unused Directories
        if self.findings['unused_dirs']:
            lines.extend([
                "## 📁 Unused/Deprecated Directories",
                "",
                f"Found **{len(self.findings['unused_dirs'])}** unused directories:",
                "",
                "| Directory | Files | Last Modified |",
                "|-----------|-------|---------------|"
            ])

            for item in sorted(self.findings['unused_dirs'], key=lambda x: x['file_count'], reverse=True):
                lines.append(
                    f"| `{item['path']}` | {item['file_count']} | {item['last_modified']} |"
                )

            lines.extend(["", "**Recommended Action:** Review and archive if confirmed unused", "", "---", ""])

        # Commented Code
        if self.findings['commented_code']:
            lines.extend([
                "## 💬 Large Commented Code Blocks",
                "",
                f"Found **{len(self.findings['commented_code'])}** large commented code blocks:",
                "",
                "| File | Lines | Location |",
                "|------|-------|----------|"
            ])

            for item in sorted(self.findings['commented_code'], key=lambda x: x['lines'], reverse=True)[:20]:
                lines.append(
                    f"| `{item['path']}` | {item['lines']} | L{item['start_line']}-{item['end_line']} |"
                )

            if len(self.findings['commented_code']) > 20:
                lines.append(f"| ... | ... | *and {len(self.findings['commented_code']) - 20} more* |")

            lines.extend(["", "**Recommended Action:** Remove or document why preserved", "", "---", ""])

        # No issues
        if total == 0:
            lines.extend([
                "## ✅ No Unused Code Detected",
                "",
                "Codebase is clean! All backup files and unused directories have been archived.",
                ""
            ])

        lines.append("---")
        lines.append("")
        lines.append(f"*Generated by `scripts/detect_unused_code.py` on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        report = '\n'.join(lines)

        if output_file:
            output_path = self.project_root / output_file
            output_path.write_text(report)
            print(f"✅ Report written to: {output_path}")

        return report


def main():
    parser = argparse.ArgumentParser(
        description="Detect unused code in the codebase"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--report', '-r',
        type=str,
        metavar='FILE',
        help='Generate markdown report to FILE'
    )
    parser.add_argument(
        '--root',
        default='.',
        help='Project root directory (default: current directory)'
    )

    args = parser.parse_args()

    # Run detection
    project_root = Path(args.root).resolve()
    detector = UnusedCodeDetector(project_root, verbose=args.verbose)

    print("\n" + "="*70)
    print("  UNUSED CODE DETECTION")
    print("="*70 + "\n")

    detector.run_all_detections()

    # Generate report
    if args.report:
        detector.generate_report(args.report)
    else:
        # Print summary to console
        print("\n📊 SUMMARY:")
        print(f"  Backup files: {len(detector.findings['backup_files'])}")
        print(f"  Unused directories: {len(detector.findings['unused_dirs'])}")
        print(f"  Commented code blocks: {len(detector.findings['commented_code'])}")
        print()
        print("💡 Use --report FILENAME.md to generate detailed report")
        print()


if __name__ == '__main__':
    main()
