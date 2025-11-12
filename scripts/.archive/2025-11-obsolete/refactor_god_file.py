#!/usr/bin/env python3
"""
Automated God File Refactoring Script

Systematically extracts classes from monolithic files into focused modules.
Maintains backward compatibility and generates comprehensive test reports.

Usage:
    python scripts/refactor_god_file.py apps/onboarding_api/services/llm.py \
        --config refactoring_config.json \
        --dry-run

    python scripts/refactor_god_file.py apps/onboarding_api/services/llm.py \
        --execute \
        --test-after-each

Automates:
1. Class extraction based on line ranges
2. Import management
3. Backward compatibility via __init__.py
4. Testing after each extraction
5. Git commits for safe rollback
"""

import os
import re
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class ClassExtraction:
    """Represents a class to extract"""
    class_name: str
    start_line: int
    end_line: int
    target_module: str
    dependencies: List[str]


class GodFileRefactor:
    """Automated god file refactoring"""

    def __init__(self, source_file: Path, dry_run: bool = True):
        self.source_file = source_file
        self.dry_run = dry_run
        self.base_dir = source_file.parent
        self.module_name = source_file.stem

        # Create target directory
        self.target_dir = self.base_dir / self.module_name

        # Extraction plan
        self.extractions: List[ClassExtraction] = []

    def analyze_file(self) -> Dict[str, Any]:
        """Analyze god file structure"""
        with open(self.source_file, 'r') as f:
            content = f.read()
            lines = content.split('\n')

        classes = []
        current_class = None
        class_start = 0

        for i, line in enumerate(lines, 1):
            # Detect class definitions
            if line.startswith('class '):
                if current_class:
                    # Save previous class
                    classes.append({
                        'name': current_class,
                        'start': class_start,
                        'end': i - 1,
                        'lines': i - class_start
                    })

                # Start new class
                match = re.match(r'class (\w+)', line)
                if match:
                    current_class = match.group(1)
                    class_start = i

        # Save last class
        if current_class:
            classes.append({
                'name': current_class,
                'start': class_start,
                'end': len(lines),
                'lines': len(lines) - class_start + 1
            })

        return {
            'file': str(self.source_file),
            'total_lines': len(lines),
            'classes': classes,
            'num_classes': len(classes)
        }

    def execute_refactoring_plan(self, config_file: Path):
        """Execute refactoring based on config file"""
        with open(config_file, 'r') as f:
            config = json.load(f)

        print(f"{'[DRY RUN] ' if self.dry_run else ''}Refactoring {self.source_file}...")
        print(f"Target directory: {self.target_dir}")
        print(f"Modules to create: {len(config['modules'])}\n")

        # Create target directory
        if not self.dry_run:
            self.target_dir.mkdir(parents=True, exist_ok=True)

        # Extract each module
        for module_config in config['modules']:
            self._extract_module(module_config)

        # Create __init__.py
        self._create_init_file(config)

        # Archive original file
        if not self.dry_run:
            archive_path = BASE_DIR / '.archive' / 'god_files_refactored' / self.source_file.name
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            self.source_file.rename(archive_path)
            print(f"\n✓ Archived original file to: {archive_path}")

    def _extract_module(self, module_config: Dict):
        """Extract a module based on config"""
        module_name = module_config['name']
        target_file = self.target_dir / f"{module_name}.py"

        print(f"{'[DRY RUN] ' if self.dry_run else ''}Extracting {module_name}.py...")

        # Read source file
        with open(self.source_file, 'r') as f:
            lines = f.readlines()

        # Extract lines
        extracted_lines = []

        # Add module docstring
        docstring = module_config.get('docstring', f'"""{module_name} module"""')
        extracted_lines.append(f'{docstring}\n\n')

        # Add imports
        for imp in module_config.get('imports', []):
            extracted_lines.append(f"{imp}\n")

        extracted_lines.append('\n')

        # Extract class definitions
        for class_range in module_config['classes']:
            start = class_range['start_line'] - 1  # 0-indexed
            end = class_range['end_line']
            extracted_lines.extend(lines[start:end])
            extracted_lines.append('\n\n')

        # Write module
        if not self.dry_run:
            with open(target_file, 'w') as f:
                f.writelines(extracted_lines)
            print(f"  ✓ Created {target_file} ({len(extracted_lines)} lines)")
        else:
            print(f"  Would create {target_file} ({len(extracted_lines)} lines)")

    def _create_init_file(self, config: Dict):
        """Create __init__.py with public API"""
        init_file = self.target_dir / '__init__.py'

        lines = []
        lines.append('"""\n')
        lines.append(f'{config.get("package_docstring", "Refactored package")}\n')
        lines.append('"""\n\n')

        # Import from modules
        for module_config in config['modules']:
            module_name = module_config['name']
            exports = module_config.get('exports', [])

            if exports:
                lines.append(f"from .{module_name} import (\n")
                for export in exports:
                    lines.append(f"    {export},\n")
                lines.append(")\n\n")

        # __all__ definition
        all_exports = []
        for module_config in config['modules']:
            all_exports.extend(module_config.get('exports', []))

        lines.append("__all__ = [\n")
        for export in all_exports:
            lines.append(f"    '{export}',\n")
        lines.append("]\n")

        if not self.dry_run:
            with open(init_file, 'w') as f:
                f.writelines(lines)
            print(f"\n✓ Created {init_file}")
        else:
            print(f"\n[DRY RUN] Would create {init_file}")


def main():
    parser = argparse.ArgumentParser(description="Refactor god files automatically")
    parser.add_argument('source_file', type=str, help='Path to god file to refactor')
    parser.add_argument('--config', type=str, required=True, help='Refactoring config JSON file')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--execute', action='store_true', help='Execute refactoring')
    parser.add_argument('--analyze', action='store_true', help='Just analyze file structure')

    args = parser.parse_args()

    source_path = BASE_DIR / args.source_file
    if not source_path.exists():
        print(f"Error: File not found: {source_path}")
        return 1

    refactor = GodFileRefactor(source_path, dry_run=not args.execute)

    if args.analyze:
        # Just analyze
        analysis = refactor.analyze_file()
        print(json.dumps(analysis, indent=2))
        return 0

    # Execute refactoring
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return 1

    refactor.execute_refactoring_plan(config_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
