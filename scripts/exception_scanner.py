#!/usr/bin/env python3
"""
Exception Handling Quality Scanner

Scans Python code for generic exception patterns that violate Rule #11 from .claude/rules.md.
Identifies 'except Exception:' and similar broad exception handlers that can hide real errors.

Usage:
    python scripts/exception_scanner.py --path apps --format json --output scan_report.json
    python scripts/exception_scanner.py --path apps --priority-list --output PRIORITY_FIX_LIST.md
    python scripts/exception_scanner.py --path apps --verbose

Exit codes:
    0: Scan completed successfully
    1: Critical violations found (when --strict flag is used)

Author: Quality Gates Engineer
Date: 2025-11-14
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import List, Dict, Set
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class ExceptionViolation:
    """Container for exception handling violation"""
    file_path: str
    line_number: int
    exception_type: str
    context: str
    risk_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    
    def to_dict(self):
        return asdict(self)


class ExceptionScanner:
    """Scans for generic exception handling patterns"""
    
    # Risk levels for different exception types
    RISK_LEVELS = {
        'Exception': 'CRITICAL',  # Too broad, hides all errors
        'BaseException': 'CRITICAL',  # Even broader, catches SystemExit
        'except:': 'CRITICAL',  # Bare except catches everything
    }
    
    def __init__(self, root_path: str, verbose: bool = False):
        self.root_path = Path(root_path).resolve()
        self.verbose = verbose
        self.violations: List[ExceptionViolation] = []
        
    def log(self, message: str, level: str = 'INFO'):
        """Log message if verbose mode enabled"""
        if self.verbose:
            prefix = {
                'INFO': 'ℹ️ ',
                'SUCCESS': '✅',
                'WARNING': '⚠️ ',
                'ERROR': '❌',
            }.get(level, '')
            print(f"{prefix} {message}")
    
    def scan_file(self, filepath: Path) -> List[ExceptionViolation]:
        """Scan a single Python file for exception violations"""
        violations = []
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Simple pattern matching for generic exception handlers
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                
                # Skip comments
                if stripped.startswith('#'):
                    continue
                
                # Check for generic exception patterns
                if 'except Exception' in line and ':' in line:
                    violations.append(ExceptionViolation(
                        file_path=str(filepath.relative_to(self.root_path.parent)),
                        line_number=i,
                        exception_type='Exception',
                        context=stripped[:100],
                        risk_level='CRITICAL'
                    ))
                elif 'except BaseException' in line and ':' in line:
                    violations.append(ExceptionViolation(
                        file_path=str(filepath.relative_to(self.root_path.parent)),
                        line_number=i,
                        exception_type='BaseException',
                        context=stripped[:100],
                        risk_level='CRITICAL'
                    ))
                elif stripped.startswith('except:'):
                    violations.append(ExceptionViolation(
                        file_path=str(filepath.relative_to(self.root_path.parent)),
                        line_number=i,
                        exception_type='bare_except',
                        context=stripped[:100],
                        risk_level='CRITICAL'
                    ))
                    
        except Exception as e:
            self.log(f"Error scanning {filepath}: {e}", 'WARNING')
        
        return violations
    
    def scan_directory(self, exclude_dirs: Set[str] = None) -> List[ExceptionViolation]:
        """Recursively scan directory for Python files"""
        if exclude_dirs is None:
            exclude_dirs = {
                'venv', 'env', '.venv', 'migrations', 'node_modules',
                '__pycache__', '.git', 'tests', 'test_', '.pytest_cache'
            }
        
        self.log(f"Scanning {self.root_path} for exception handling violations...")
        
        if not self.root_path.exists():
            self.log(f"Path {self.root_path} does not exist", 'ERROR')
            return []
        
        py_files = []
        for py_file in self.root_path.rglob('*.py'):
            # Skip excluded directories
            skip = False
            for exclude in exclude_dirs:
                if exclude in str(py_file):
                    skip = True
                    break
            if not skip:
                py_files.append(py_file)
        
        self.log(f"Found {len(py_files)} Python files to scan")
        
        violations = []
        for py_file in py_files:
            file_violations = self.scan_file(py_file)
            violations.extend(file_violations)
        
        return violations
    
    def generate_report(self) -> Dict:
        """Generate comprehensive scan report"""
        # Group violations by file
        by_file = defaultdict(list)
        for v in self.violations:
            by_file[v.file_path].append(v)
        
        # Count by risk level
        by_risk = defaultdict(int)
        for v in self.violations:
            by_risk[v.risk_level] += 1
        
        report = {
            'metadata': {
                'total_occurrences': len(self.violations),
                'scan_path': str(self.root_path),
                'tool': 'exception_scanner.py',
                'version': '1.0.0'
            },
            'statistics': {
                'total_occurrences': len(self.violations),
                'affected_files': len(by_file),
                'by_risk_level': dict(by_risk)
            },
            'violations': [v.to_dict() for v in self.violations],
            'files': {
                filepath: [v.to_dict() for v in violations]
                for filepath, violations in by_file.items()
            }
        }
        
        return report
    
    def generate_priority_list(self) -> str:
        """Generate markdown priority fix list"""
        report = self.generate_report()
        stats = report['statistics']
        
        md = "# Exception Handling Priority Fix List\n\n"
        md += f"**Total Violations:** {stats['total_occurrences']}\n"
        md += f"**Affected Files:** {stats['affected_files']}\n\n"
        
        md += "## By Risk Level\n\n"
        for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
            count = stats['by_risk_level'].get(level, 0)
            if count > 0:
                emoji = {'CRITICAL': '🚨', 'HIGH': '⚠️', 'MEDIUM': '⚡', 'LOW': 'ℹ️'}.get(level, '')
                md += f"- {emoji} **{level}:** {count}\n"
        
        md += "\n## Violations by File\n\n"
        
        # Group and sort by file
        by_file = defaultdict(list)
        for v in self.violations:
            by_file[v.file_path].append(v)
        
        for filepath in sorted(by_file.keys()):
            violations = by_file[filepath]
            md += f"\n### {filepath}\n"
            md += f"**Count:** {len(violations)}\n\n"
            
            for v in violations[:5]:  # Show first 5 violations per file
                md += f"- Line {v.line_number}: `{v.exception_type}` ({v.risk_level})\n"
                md += f"  ```python\n  {v.context}\n  ```\n"
            
            if len(violations) > 5:
                md += f"\n*... and {len(violations) - 5} more violations*\n"
        
        md += "\n## Remediation Guide\n\n"
        md += "Replace generic exception handlers with specific exception types:\n\n"
        md += "```python\n"
        md += "# ❌ FORBIDDEN: Generic exception\n"
        md += "try:\n"
        md += "    user.save()\n"
        md += "except Exception as e:\n"
        md += "    logger.error(f'Error: {e}')\n\n"
        md += "# ✅ CORRECT: Specific exceptions\n"
        md += "from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS\n\n"
        md += "try:\n"
        md += "    user.save()\n"
        md += "except DATABASE_EXCEPTIONS as e:\n"
        md += "    logger.error(f'Database error: {e}', exc_info=True)\n"
        md += "    raise\n"
        md += "```\n\n"
        md += "See `.claude/rules.md` Rule #11 for complete guidance.\n"
        
        return md
    
    def run(self, output_format: str = 'text', output_file: str = None,
            priority_list: bool = False) -> bool:
        """Run scanner and generate output"""
        self.violations = self.scan_directory()
        
        if priority_list:
            # Generate priority list
            content = self.generate_priority_list()
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(content)
                self.log(f"Priority list written to {output_file}", 'SUCCESS')
            else:
                print(content)
            return True
        
        # Generate report
        report = self.generate_report()
        
        if output_format == 'json':
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(report, f, indent=2)
                self.log(f"JSON report written to {output_file}", 'SUCCESS')
            else:
                print(json.dumps(report, indent=2))
        else:
            # Text output
            stats = report['statistics']
            print(f"\n{'=' * 70}")
            print("EXCEPTION HANDLING QUALITY REPORT")
            print(f"{'=' * 70}")
            print(f"Total Violations: {stats['total_occurrences']}")
            print(f"Affected Files: {stats['affected_files']}")
            print("\nBy Risk Level:")
            for level, count in stats['by_risk_level'].items():
                print(f"  {level}: {count}")
            print(f"{'=' * 70}\n")
        
        return len(self.violations) == 0


def main():
    parser = argparse.ArgumentParser(
        description='Scan for generic exception handling patterns'
    )
    parser.add_argument('--path', default='apps',
                        help='Path to scan (default: apps)')
    parser.add_argument('--format', choices=['json', 'text'], default='text',
                        help='Output format')
    parser.add_argument('--output', '-o',
                        help='Output file path')
    parser.add_argument('--priority-list', action='store_true',
                        help='Generate priority fix list')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--strict', action='store_true',
                        help='Exit with code 1 if violations found')
    
    args = parser.parse_args()
    
    # Create scanner
    scanner = ExceptionScanner(args.path, verbose=args.verbose)
    
    # Run scan
    success = scanner.run(
        output_format=args.format,
        output_file=args.output,
        priority_list=args.priority_list
    )
    
    # Exit with appropriate code
    if args.strict and not success:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
