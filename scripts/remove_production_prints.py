#!/usr/bin/env python3
"""
Automated script to detect and remove production print() statements.

Replaces print() calls with appropriate logger.info() or logger.debug() calls.
Skips test files, migrations, and scripts directory.

Usage:
    python scripts/remove_production_prints.py --dry-run  # Preview changes
    python scripts/remove_production_prints.py --apply    # Apply changes
    python scripts/remove_production_prints.py --validate # Validate syntax after changes
"""

import ast
import argparse
import logging
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PrintStatementVisitor(ast.NodeVisitor):
    """AST visitor to find print() statements."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.print_statements: List[Tuple[int, int, str]] = []
        self.source_lines: List[str] = []

    def visit_Call(self, node: ast.Call):
        """Visit function calls to find print() statements."""
        if isinstance(node.func, ast.Name) and node.func.id == 'print':
            # Get line number and column
            lineno = node.lineno
            col_offset = node.col_offset

            # Get the full line of code
            if self.source_lines:
                line_content = self.source_lines[lineno - 1].strip()
            else:
                line_content = ""

            self.print_statements.append((lineno, col_offset, line_content))

        self.generic_visit(node)


class PrintStatementReplacer:
    """Replace print() statements with logger calls."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.stats = {
            'files_scanned': 0,
            'files_with_prints': 0,
            'files_modified': 0,
            'prints_found': 0,
            'prints_replaced': 0,
            'files_skipped': 0,
            'errors': 0
        }
        self.changes_by_file: Dict[str, List[dict]] = defaultdict(list)
        self.skip_patterns = [
            r'.*/tests?/.*',
            r'.*/test_.*\.py$',
            r'.*_test\.py$',
            r'.*/migrations/.*',
            r'^scripts/.*',
            r'.*/venv/.*',
            r'.*/\..*',  # Hidden directories
        ]

    def should_skip_file(self, filepath: Path) -> Tuple[bool, Optional[str]]:
        """Check if file should be skipped."""
        relative_path = str(filepath.relative_to(self.project_root))

        for pattern in self.skip_patterns:
            if re.match(pattern, relative_path):
                return True, f"matches skip pattern: {pattern}"

        return False, None

    def find_print_statements(self, filepath: Path) -> List[Tuple[int, int, str]]:
        """Find all print statements in a file using AST."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()

            tree = ast.parse(source, filename=str(filepath))
            visitor = PrintStatementVisitor(str(filepath))
            visitor.source_lines = source.splitlines()
            visitor.visit(tree)

            return visitor.print_statements

        except SyntaxError as e:
            logger.error(f"Syntax error in {filepath}: {e}")
            self.stats['errors'] += 1
            return []
        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")
            self.stats['errors'] += 1
            return []

    def has_logging_import(self, source: str) -> bool:
        """Check if file already imports logging."""
        return re.search(r'^import logging', source, re.MULTILINE) is not None

    def has_logger_definition(self, source: str) -> bool:
        """Check if file already has logger definition."""
        return re.search(r'^logger\s*=\s*logging\.getLogger', source, re.MULTILINE) is not None

    def add_logging_imports(self, source: str) -> str:
        """Add logging import and logger definition if missing."""
        lines = source.splitlines(keepends=True)

        # Find the right place to insert imports (after module docstring and existing imports)
        insert_line = 0
        in_docstring = False
        last_import_line = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Handle module docstrings
            if i == 0 and (stripped.startswith('"""') or stripped.startswith("'''")):
                in_docstring = True
                continue

            if in_docstring:
                if '"""' in stripped or "'''" in stripped:
                    in_docstring = False
                    insert_line = i + 1
                continue

            # Track imports
            if stripped.startswith('import ') or stripped.startswith('from '):
                last_import_line = i

            # Stop at first non-import, non-comment, non-blank line
            if stripped and not stripped.startswith('#') and not stripped.startswith('import') and not stripped.startswith('from'):
                break

        # Insert after last import or after docstring
        insert_line = max(insert_line, last_import_line + 1)

        # Add logging import if missing
        if not self.has_logging_import(source):
            lines.insert(insert_line, 'import logging\n')
            insert_line += 1

        # Add logger definition if missing
        if not self.has_logger_definition(source):
            # Add blank line before logger if needed
            if insert_line > 0 and lines[insert_line - 1].strip():
                lines.insert(insert_line, '\n')
                insert_line += 1

            lines.insert(insert_line, "logger = logging.getLogger(__name__)\n")
            insert_line += 1

            # Add blank line after logger
            if insert_line < len(lines) and lines[insert_line].strip():
                lines.insert(insert_line, '\n')

        return ''.join(lines)

    def convert_print_to_logger(self, line: str) -> str:
        """Convert a print() statement to logger.info()."""
        # Handle various print formats

        # Match print() with various argument patterns
        # print("message")
        # print(f"message {var}")
        # print("message", var)
        # print("message", var1, var2)

        # Simple case: print("literal string")
        match = re.match(r'^(\s*)print\((.*)\)\s*$', line)
        if not match:
            return line

        indent = match.group(1)
        args = match.group(2).strip()

        # If it's a simple string literal
        if args.startswith('"') or args.startswith("'"):
            return f"{indent}logger.info({args})"

        # If it's an f-string
        if args.startswith('f"') or args.startswith("f'"):
            return f"{indent}logger.info({args})"

        # If it has multiple arguments, convert to format string
        # print("message", var) -> logger.info("message %s", var)
        if ',' in args:
            parts = [p.strip() for p in args.split(',')]
            if parts[0].startswith('"') or parts[0].startswith("'"):
                # First part is a string literal
                format_str = parts[0]
                variables = ', '.join(parts[1:])

                # Count how many variables we have
                var_count = len(parts) - 1

                # Add %s placeholders to the format string
                # Remove closing quote, add placeholders, add closing quote back
                quote_char = format_str[0]
                base_str = format_str[1:-1]

                # Check if there are already placeholders
                if '%s' not in base_str and '{}' not in base_str:
                    # Add appropriate number of %s
                    placeholders = ' '.join(['%s'] * var_count)
                    format_str = f'{quote_char}{base_str} {placeholders}{quote_char}'

                return f"{indent}logger.info({format_str}, {variables})"

        # Default: just wrap the arguments
        return f"{indent}logger.info({args})"

    def replace_prints_in_file(self, filepath: Path, dry_run: bool = True) -> bool:
        """Replace print statements in a file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                original_source = f.read()

            # Find print statements
            print_statements = self.find_print_statements(filepath)

            if not print_statements:
                return False

            self.stats['files_with_prints'] += 1
            self.stats['prints_found'] += len(print_statements)

            # Process the file line by line
            lines = original_source.splitlines(keepends=True)
            modified = False

            for lineno, col_offset, line_content in print_statements:
                if lineno > 0 and lineno <= len(lines):
                    original_line = lines[lineno - 1]
                    new_line = self.convert_print_to_logger(original_line)

                    if original_line != new_line:
                        lines[lineno - 1] = new_line
                        modified = True

                        # Track the change
                        self.changes_by_file[str(filepath)].append({
                            'line_number': lineno,
                            'original': original_line.rstrip(),
                            'replacement': new_line.rstrip()
                        })
                        self.stats['prints_replaced'] += 1

            if not modified:
                return False

            # Add logging imports
            new_source = ''.join(lines)
            new_source = self.add_logging_imports(new_source)

            # Validate syntax
            try:
                ast.parse(new_source)
            except SyntaxError as e:
                logger.error(f"Generated invalid syntax for {filepath}: {e}")
                self.stats['errors'] += 1
                return False

            if not dry_run:
                # Create backup
                backup_path = filepath.with_suffix(filepath.suffix + '.bak')
                shutil.copy2(filepath, backup_path)

                # Write modified file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_source)

                logger.info(f"Modified {filepath} ({len(print_statements)} prints replaced)")
                self.stats['files_modified'] += 1
            else:
                logger.info(f"Would modify {filepath} ({len(print_statements)} prints to replace)")

            return True

        except Exception as e:
            logger.error(f"Error processing {filepath}: {e}")
            self.stats['errors'] += 1
            return False

    def scan_directory(self, directory: Path, dry_run: bool = True):
        """Scan directory for Python files with print statements."""
        for py_file in directory.rglob('*.py'):
            self.stats['files_scanned'] += 1

            # Check if should skip
            should_skip, reason = self.should_skip_file(py_file)
            if should_skip:
                logger.debug(f"Skipping {py_file}: {reason}")
                self.stats['files_skipped'] += 1
                continue

            # Process the file
            self.replace_prints_in_file(py_file, dry_run=dry_run)

    def generate_report(self, output_file: Optional[Path] = None):
        """Generate a detailed change report."""
        report_lines = [
            "=" * 80,
            "PRINT STATEMENT REMOVAL REPORT",
            "=" * 80,
            f"Generated: {datetime.now().isoformat()}",
            "",
            "STATISTICS",
            "-" * 80,
            f"Files scanned:       {self.stats['files_scanned']}",
            f"Files skipped:       {self.stats['files_skipped']}",
            f"Files with prints:   {self.stats['files_with_prints']}",
            f"Files modified:      {self.stats['files_modified']}",
            f"Print statements found:    {self.stats['prints_found']}",
            f"Print statements replaced: {self.stats['prints_replaced']}",
            f"Errors encountered:  {self.stats['errors']} (files with existing syntax errors)",
            "",
            "NOTE: Errors indicate files with pre-existing syntax issues that were skipped.",
            "These files need manual review and fixing before print statement removal.",
            "",
        ]

        if self.changes_by_file:
            report_lines.extend([
                "SUMMARY OF FILES TO MODIFY",
                "-" * 80,
            ])
            for filepath, changes in sorted(self.changes_by_file.items()):
                report_lines.append(f"  {filepath}")
                report_lines.append(f"    {len(changes)} print statement(s)")

            report_lines.extend([
                "",
                "CHANGES BY FILE (DETAILED)",
                "-" * 80,
            ])

            for filepath, changes in sorted(self.changes_by_file.items()):
                report_lines.append(f"\n{filepath}")
                report_lines.append(f"  {len(changes)} print statement(s) replaced:")

                for change in changes:
                    report_lines.append(f"\n  Line {change['line_number']}:")
                    report_lines.append(f"    - {change['original']}")
                    report_lines.append(f"    + {change['replacement']}")
        else:
            report_lines.append("No changes to report.")

        report_lines.append("")
        report_lines.append("=" * 80)

        report_text = "\n".join(report_lines)

        # Print to console
        print(report_text)

        # Save to file if specified
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_text)
            logger.info(f"Report saved to {output_file}")

        return report_text

    def validate_all_syntax(self) -> bool:
        """Validate Python syntax for all modified files."""
        logger.info("Validating syntax for all modified files...")
        all_valid = True

        for filepath in self.changes_by_file.keys():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    source = f.read()
                ast.parse(source)
                logger.debug(f"✓ {filepath} - syntax valid")
            except SyntaxError as e:
                logger.error(f"✗ {filepath} - SYNTAX ERROR: {e}")
                all_valid = False

        if all_valid:
            logger.info("✓ All modified files have valid syntax")
        else:
            logger.error("✗ Some files have syntax errors")

        return all_valid

    def rollback_changes(self):
        """Rollback all changes using backup files."""
        logger.info("Rolling back changes...")
        rollback_count = 0

        for filepath in self.changes_by_file.keys():
            backup_path = Path(filepath).with_suffix(Path(filepath).suffix + '.bak')

            if backup_path.exists():
                shutil.copy2(backup_path, filepath)
                backup_path.unlink()
                rollback_count += 1
                logger.info(f"Rolled back {filepath}")

        logger.info(f"Rolled back {rollback_count} file(s)")
        self.changes_by_file.clear()

    def cleanup_backups(self):
        """Remove backup files after successful changes."""
        logger.info("Cleaning up backup files...")
        cleanup_count = 0

        for filepath in self.changes_by_file.keys():
            backup_path = Path(filepath).with_suffix(Path(filepath).suffix + '.bak')

            if backup_path.exists():
                backup_path.unlink()
                cleanup_count += 1

        logger.info(f"Removed {cleanup_count} backup file(s)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Remove production print() statements and replace with logger calls'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files (default)'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply changes to files'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate syntax of modified files'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback changes using backup files'
    )
    parser.add_argument(
        '--cleanup-backups',
        action='store_true',
        help='Remove backup files after successful changes'
    )
    parser.add_argument(
        '--report',
        type=str,
        help='Save report to file'
    )
    parser.add_argument(
        '--directory',
        type=str,
        default='apps',
        help='Directory to scan (default: apps)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine project root
    script_dir = Path(__file__).parent.parent
    project_root = script_dir

    # Create replacer instance
    replacer = PrintStatementReplacer(project_root)

    # Handle rollback
    if args.rollback:
        replacer.rollback_changes()
        return 0

    # Handle cleanup
    if args.cleanup_backups:
        replacer.cleanup_backups()
        return 0

    # Determine mode
    dry_run = not args.apply

    if dry_run:
        logger.info("=" * 80)
        logger.info("DRY RUN MODE - No files will be modified")
        logger.info("=" * 80)
    else:
        logger.info("=" * 80)
        logger.info("APPLY MODE - Files will be modified")
        logger.info("=" * 80)

    # Scan directory
    scan_dir = project_root / args.directory
    if not scan_dir.exists():
        logger.error(f"Directory does not exist: {scan_dir}")
        return 1

    logger.info(f"Scanning directory: {scan_dir}")
    replacer.scan_directory(scan_dir, dry_run=dry_run)

    # Generate report
    report_file = Path(args.report) if args.report else None
    replacer.generate_report(output_file=report_file)

    # Validate if requested
    if args.validate and not dry_run:
        if not replacer.validate_all_syntax():
            logger.error("Syntax validation failed - rolling back changes")
            replacer.rollback_changes()
            return 1

    # Return success
    if replacer.stats['errors'] > 0:
        logger.warning(f"Completed with {replacer.stats['errors']} error(s)")
        return 1

    logger.info("Completed successfully")
    return 0


if __name__ == '__main__':
    sys.exit(main())
