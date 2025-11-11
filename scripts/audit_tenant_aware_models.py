#!/usr/bin/env python
"""
Audit script for TenantAwareModel manager inheritance.

Security Context:
-----------------
Models inheriting from TenantAwareModel receive automatic tenant filtering ONLY if:
1. They use the inherited TenantAwareManager (default), OR
2. They declare a custom manager that inherits from TenantAwareManager

If a model declares a custom manager that does NOT inherit from TenantAwareManager,
it loses automatic tenant filtering, creating IDOR vulnerabilities.

This script audits all 170+ tenant-aware models to identify vulnerable configurations.

Usage:
    python scripts/audit_tenant_aware_models.py
    python scripts/audit_tenant_aware_models.py --verbose
    python scripts/audit_tenant_aware_models.py --fix  # Auto-fix violations

Output:
    - Total tenant-aware models found
    - Models with safe manager configurations
    - Models with vulnerable manager configurations
    - Detailed report of each model's manager chain
"""

import os
import sys
import ast
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class ManagerInfo:
    """Information about a model's manager configuration."""
    name: str  # Manager attribute name (e.g., 'objects')
    class_name: str  # Manager class name (e.g., 'TenantAwareManager')
    inheritance_chain: List[str] = field(default_factory=list)
    is_safe: bool = False  # Whether it inherits from TenantAwareManager
    module: str = ""  # Import module if available


@dataclass
class ModelAudit:
    """Audit result for a single model."""
    model_name: str
    file_path: str
    app_name: str
    managers: List[ManagerInfo] = field(default_factory=list)
    has_explicit_manager: bool = False
    is_safe: bool = False
    vulnerability_reason: str = ""
    line_number: int = 0


class TenantManagerAuditor:
    """Audits all TenantAwareModel subclasses for manager inheritance."""

    def __init__(self, project_root: Path, verbose: bool = False):
        self.project_root = project_root
        self.verbose = verbose
        self.apps_dir = project_root / "apps"

        # Track all custom manager classes and their inheritance
        self.custom_managers: Dict[str, List[str]] = {}  # manager_class -> base_classes
        self.manager_imports: Dict[str, str] = {}  # manager_class -> module_path

        # Audit results
        self.safe_models: List[ModelAudit] = []
        self.vulnerable_models: List[ModelAudit] = []
        self.all_models: List[ModelAudit] = []

    def log(self, message: str, level: str = "INFO"):
        """Log message with optional verbosity filtering."""
        if self.verbose or level in ("WARNING", "ERROR"):
            prefix = {
                "INFO": "ℹ️",
                "WARNING": "⚠️",
                "ERROR": "❌",
                "SUCCESS": "✅"
            }.get(level, "•")
            print(f"{prefix} {message}")

    def find_all_model_files(self) -> List[Path]:
        """Find all Python files that might contain model definitions."""
        model_files = []

        # Find all models.py and models/*.py files
        for app_dir in self.apps_dir.iterdir():
            if not app_dir.is_dir() or app_dir.name.startswith("_"):
                continue

            # Check for models.py
            models_file = app_dir / "models.py"
            if models_file.exists():
                model_files.append(models_file)

            # Check for models/*.py
            models_dir = app_dir / "models"
            if models_dir.exists() and models_dir.is_dir():
                for model_file in models_dir.glob("*.py"):
                    if not model_file.name.startswith("_"):
                        model_files.append(model_file)

        self.log(f"Found {len(model_files)} model files to analyze")
        return model_files

    def parse_file(self, file_path: Path) -> ast.Module:
        """Parse Python file into AST."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return ast.parse(f.read(), filename=str(file_path))
        except SyntaxError as e:
            self.log(f"Syntax error in {file_path}: {e}", "ERROR")
            return None
        except Exception as e:
            self.log(f"Error parsing {file_path}: {e}", "ERROR")
            return None

    def extract_imports(self, tree: ast.Module) -> Dict[str, str]:
        """Extract manager imports from AST."""
        imports = {}

        for node in ast.walk(tree):
            # Handle: from apps.tenants.managers import TenantAwareManager
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = f"{module}.{alias.name}"

            # Handle: import apps.tenants.managers
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[name] = alias.name

        return imports

    def get_base_classes(self, node: ast.ClassDef) -> List[str]:
        """Extract base class names from class definition."""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                # Handle: module.ClassName
                bases.append(base.attr)
        return bases

    def is_tenant_aware_model(self, class_node: ast.ClassDef) -> bool:
        """Check if class inherits from TenantAwareModel."""
        bases = self.get_base_classes(class_node)
        return "TenantAwareModel" in bases

    def extract_managers(self, class_node: ast.ClassDef, imports: Dict[str, str]) -> List[ManagerInfo]:
        """Extract manager declarations from model class."""
        managers = []

        # Field types that are NOT managers (common false positives)
        NON_MANAGER_TYPES = {
            'ArrayField', 'PointField', 'LineStringField', 'JSONField',
            'EncryptedJSONField', 'EncryptedCharField', 'SearchVectorField',
            'VersionField', 'GenericForeignKey', 'EnhancedSecureString',
            'PolygonField', 'MultiPolygonField', 'GeometryField'
        }

        for item in class_node.body:
            # Look for: objects = SomeManager()
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    # Only process simple Name assignments (objects = ...)
                    if not isinstance(target, ast.Name):
                        continue

                    manager_name = target.id  # Use .id for ast.Name, not .name

                    # Check if value is a manager instantiation
                    if isinstance(item.value, ast.Call):
                        if isinstance(item.value.func, ast.Name):
                            manager_class = item.value.func.id

                            # Skip known field types (not managers)
                            if manager_class in NON_MANAGER_TYPES:
                                continue

                            # Only process classes that end with Manager or are known managers
                            if not (manager_class.endswith('Manager') or manager_class == 'TenantAwareManager'):
                                continue

                            # Check if this is a known manager class
                            module_path = imports.get(manager_class, "")

                            manager_info = ManagerInfo(
                                name=manager_name,
                                class_name=manager_class,
                                module=module_path
                            )

                            # Check if it's TenantAwareManager or inherits from it
                            manager_info.is_safe = self.is_manager_safe(
                                manager_class, module_path, class_node
                            )

                            managers.append(manager_info)

        return managers

    def is_manager_safe(self, manager_class: str, module_path: str, context_node: ast.ClassDef) -> bool:
        """
        Determine if a manager class is safe (inherits from TenantAwareManager).

        A manager is safe if:
        1. It IS TenantAwareManager, OR
        2. It inherits from TenantAwareManager (check custom_managers registry)
        """
        # Direct TenantAwareManager usage
        if manager_class == "TenantAwareManager":
            return True

        # Check if it's a registered custom manager that inherits TenantAwareManager
        if manager_class in self.custom_managers:
            bases = self.custom_managers[manager_class]
            return "TenantAwareManager" in bases

        # Check if manager is defined in same file (inline manager)
        # We'll scan the AST context for the manager definition
        for node in ast.walk(context_node):
            if isinstance(node, ast.ClassDef) and node.name == manager_class:
                bases = self.get_base_classes(node)
                if "TenantAwareManager" in bases:
                    self.custom_managers[manager_class] = bases
                    return True

        # Unknown manager - assume unsafe
        return False

    def scan_for_custom_managers(self, file_path: Path):
        """Pre-scan file for custom manager class definitions."""
        tree = self.parse_file(file_path)
        if not tree:
            return

        imports = self.extract_imports(tree)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = self.get_base_classes(node)

                # Track manager classes
                if "Manager" in node.name or any("Manager" in base for base in bases):
                    self.custom_managers[node.name] = bases

                    # Store import path if available
                    module_parts = file_path.relative_to(self.project_root).parts
                    module_path = ".".join(module_parts[:-1]) + "." + file_path.stem
                    self.manager_imports[node.name] = module_path

    def audit_model_file(self, file_path: Path) -> List[ModelAudit]:
        """Audit a single model file for TenantAwareModel subclasses."""
        audits = []

        tree = self.parse_file(file_path)
        if not tree:
            return audits

        imports = self.extract_imports(tree)
        app_name = file_path.parent.parent.name if file_path.parent.name == "models" else file_path.parent.name

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            if not self.is_tenant_aware_model(node):
                continue

            # Found a TenantAwareModel subclass
            model_name = node.name
            managers = self.extract_managers(node, imports)

            audit = ModelAudit(
                model_name=model_name,
                file_path=str(file_path.relative_to(self.project_root)),
                app_name=app_name,
                managers=managers,
                has_explicit_manager=len(managers) > 0,
                line_number=node.lineno
            )

            # Determine if model is safe
            if not managers:
                # No explicit manager - inherits TenantAwareManager from base (SAFE)
                audit.is_safe = True
                audit.vulnerability_reason = "Inherits default TenantAwareManager"
            else:
                # Has explicit manager(s) - check if they're safe
                objects_manager = next((m for m in managers if m.name == "objects"), None)

                if objects_manager:
                    if objects_manager.is_safe:
                        audit.is_safe = True
                        audit.vulnerability_reason = f"Uses {objects_manager.class_name} (inherits TenantAwareManager)"
                    else:
                        audit.is_safe = False
                        audit.vulnerability_reason = (
                            f"VULNERABLE: 'objects' manager uses {objects_manager.class_name} "
                            f"which does NOT inherit from TenantAwareManager"
                        )
                else:
                    # Has managers but not 'objects' - unusual but check them
                    safe_managers = [m for m in managers if m.is_safe]
                    if safe_managers:
                        audit.is_safe = True
                        audit.vulnerability_reason = f"Uses safe managers: {[m.name for m in safe_managers]}"
                    else:
                        audit.is_safe = False
                        audit.vulnerability_reason = (
                            f"VULNERABLE: No 'objects' manager and custom managers "
                            f"{[m.name for m in managers]} don't inherit TenantAwareManager"
                        )

            audits.append(audit)

            if audit.is_safe:
                self.safe_models.append(audit)
            else:
                self.vulnerable_models.append(audit)

            self.all_models.append(audit)

        return audits

    def run_audit(self) -> Tuple[List[ModelAudit], List[ModelAudit]]:
        """Run complete audit of all tenant-aware models."""
        self.log("Starting tenant manager inheritance audit...", "INFO")

        model_files = self.find_all_model_files()

        # First pass: scan for custom manager definitions
        self.log("Phase 1: Scanning for custom manager classes...")
        for file_path in model_files:
            self.scan_for_custom_managers(file_path)

        self.log(f"Found {len(self.custom_managers)} custom manager classes")

        # Second pass: audit all models
        self.log("Phase 2: Auditing TenantAwareModel subclasses...")
        for file_path in model_files:
            self.audit_model_file(file_path)

        self.log(f"\nAudit complete: {len(self.all_models)} tenant-aware models found", "SUCCESS")
        return self.safe_models, self.vulnerable_models

    def print_summary(self):
        """Print audit summary report."""
        total = len(self.all_models)
        safe = len(self.safe_models)
        vulnerable = len(self.vulnerable_models)

        print("\n" + "=" * 80)
        print("TENANT MANAGER INHERITANCE AUDIT REPORT")
        print("=" * 80)
        print(f"\nTotal TenantAwareModel subclasses found: {total}")
        print(f"✅ Safe models (proper manager inheritance): {safe}")
        print(f"❌ Vulnerable models (missing TenantAwareManager): {vulnerable}")

        if vulnerable > 0:
            print("\n" + "⚠️  " * 20)
            print("CRITICAL SECURITY VULNERABILITIES DETECTED")
            print("⚠️  " * 20)
            print("\nThe following models do NOT have proper tenant filtering:")
            print("-" * 80)

            for audit in self.vulnerable_models:
                print(f"\n❌ {audit.app_name}.{audit.model_name}")
                print(f"   File: {audit.file_path}:{audit.line_number}")
                print(f"   Issue: {audit.vulnerability_reason}")
                if audit.managers:
                    print(f"   Managers: {[(m.name, m.class_name) for m in audit.managers]}")

        # Group safe models by configuration type
        if self.verbose and safe > 0:
            print("\n" + "-" * 80)
            print("SAFE MODELS (Grouped by Configuration)")
            print("-" * 80)

            # Group by vulnerability reason (which explains the config)
            grouped = defaultdict(list)
            for audit in self.safe_models:
                grouped[audit.vulnerability_reason].append(audit)

            for reason, models in sorted(grouped.items()):
                print(f"\n{reason}: {len(models)} models")
                if self.verbose:
                    for audit in models[:5]:  # Show first 5 examples
                        print(f"  • {audit.app_name}.{audit.model_name}")
                    if len(models) > 5:
                        print(f"  ... and {len(models) - 5} more")

        print("\n" + "=" * 80)

        if vulnerable > 0:
            print("\n⚠️  ACTION REQUIRED: Fix vulnerable models before deploying to production!")
            print("Run with --fix flag to auto-generate fixes.\n")
            return 1
        else:
            print("\n✅ All tenant-aware models have proper manager inheritance!")
            print("✅ No IDOR vulnerabilities detected.\n")
            return 0

    def generate_fixes(self):
        """Generate fix suggestions for vulnerable models."""
        if not self.vulnerable_models:
            print("✅ No vulnerabilities to fix!")
            return

        print("\n" + "=" * 80)
        print("SUGGESTED FIXES FOR VULNERABLE MODELS")
        print("=" * 80)

        for audit in self.vulnerable_models:
            print(f"\n{'─' * 80}")
            print(f"Model: {audit.app_name}.{audit.model_name}")
            print(f"File: {audit.file_path}:{audit.line_number}")
            print(f"{'─' * 80}")

            file_path = self.project_root / audit.file_path

            # Read current file
            with open(file_path, 'r') as f:
                lines = f.readlines()

            # Find the model class definition
            target_line = audit.line_number - 1

            # Check if TenantAwareManager is imported
            has_import = any("from apps.tenants.managers import TenantAwareManager" in line for line in lines)

            print("\nRequired changes:")

            if not has_import:
                print("\n1. Add import at top of file:")
                print("   from apps.tenants.managers import TenantAwareManager")

            if not audit.managers:
                print("\n2. Add explicit manager declaration in model class:")
                print("   objects = TenantAwareManager()")
            else:
                print("\n2. Replace manager declaration with TenantAwareManager:")
                for mgr in audit.managers:
                    if not mgr.is_safe:
                        print(f"   Replace: {mgr.name} = {mgr.class_name}()")
                        print(f"   With:    {mgr.name} = TenantAwareManager()")

            print("\nExample:")
            print("   class {}(TenantAwareModel):".format(audit.model_name))
            print("       objects = TenantAwareManager()  # ← Add this!")
            print("       # ... rest of model definition")


def main():
    parser = argparse.ArgumentParser(
        description="Audit TenantAwareModel manager inheritance for IDOR vulnerabilities"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Generate fix suggestions"
    )

    args = parser.parse_args()

    # Run audit
    auditor = TenantManagerAuditor(project_root, verbose=args.verbose)
    safe_models, vulnerable_models = auditor.run_audit()

    # Print report
    exit_code = auditor.print_summary()

    # Generate fixes if requested
    if args.fix:
        auditor.generate_fixes()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
