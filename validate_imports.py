#!/usr/bin/env python3
"""
Import validation script for security fixes.
"""

import ast
import os
from pathlib import Path


def validate_file_imports(file_path):
    """Validate imports in a Python file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        tree = ast.parse(content)
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        return imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []


def main():
    """Validate critical imports."""
    print("🔍 Validating imports...\n")

    critical_files = [
        "apps/schedhuler/views.py",
        "apps/service/utils.py",
        "apps/activity/managers/job_manager.py",
        "apps/core/utils_new/sentinel_resolvers.py"
    ]

    all_good = True

    for file_path in critical_files:
        full_path = Path(file_path)
        if not full_path.exists():
            print(f"❌ File not found: {file_path}")
            all_good = False
            continue

        imports = validate_file_imports(full_path)

        print(f"📄 {file_path}")

        # Check expected imports
        expected_imports = {
            "apps/schedhuler/views.py": [
                "apps.core.utils_new.sentinel_resolvers",
                "apps.core.constants"
            ],
            "apps/service/utils.py": [
                "apps.core.utils_new.sentinel_resolvers",
                "apps.core.constants"
            ],
            "apps/activity/managers/job_manager.py": [
                "apps.core.constants"
            ]
        }

        if file_path in expected_imports:
            missing = []
            for expected in expected_imports[file_path]:
                if expected not in imports:
                    missing.append(expected)

            if missing:
                print(f"  ❌ Missing imports: {missing}")
                all_good = False
            else:
                print(f"  ✅ All expected imports present")
        else:
            print(f"  ℹ️  No specific imports expected")

        print()

    # Check that constants file has the needed values
    constants_path = Path("apps/core/constants.py")
    if constants_path.exists():
        with open(constants_path) as f:
            content = f.read()

        required_constants = [
            "class JobConstants",
            "class DatabaseConstants",
            "TASK = \"TASK\"",
            "INTERNALTOUR = \"INTERNALTOUR\"",
            "EXTERNALTOUR = \"EXTERNALTOUR\"",
            "ID_SYSTEM = 1"
        ]

        print("📄 apps/core/constants.py")
        missing_constants = []
        for const in required_constants:
            if const not in content:
                missing_constants.append(const)

        if missing_constants:
            print(f"  ❌ Missing constants: {missing_constants}")
            all_good = False
        else:
            print("  ✅ All required constants present")
    else:
        print("❌ Constants file not found")
        all_good = False

    print("\n" + "="*50)
    if all_good:
        print("🎉 All imports validated successfully!")
        return 0
    else:
        print("⚠️  Import validation issues found")
        return 1


if __name__ == "__main__":
    exit(main())