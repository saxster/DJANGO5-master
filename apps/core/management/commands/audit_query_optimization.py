"""
Management command to audit and fix database query optimization issues.

This command identifies views and code patterns that may cause N+1 query problems
and provides recommendations or automatic fixes for optimization.
"""
import os
import re
from typing import List, Tuple
from django.apps import apps
from django.db import models
from django.core.management.base import BaseCommand
from apps.core.services.query_optimization_service import QueryOptimizer


class Command(BaseCommand):
    help = """
    Audit database queries across the codebase for N+1 query problems and
    provide optimization recommendations.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Automatically apply query optimizations where possible',
        )
        parser.add_argument(
            '--app',
            type=str,
            help='Audit specific app only',
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Audit specific model only (format: app.Model)',
        )
        parser.add_argument(
            '--exclude',
            type=str,
            nargs='*',
            default=['migrations', '__pycache__', '.git', 'tests'],
            help='Directories to exclude from audit',
        )

    def handle(self, *args, **options):
        """Main audit handler."""
        fix_mode = options['fix']
        target_app = options['app']
        target_model = options['model']
        exclude_dirs = options['exclude']

        self.stdout.write(
            self.style.WARNING("🔍 DATABASE QUERY OPTIMIZATION AUDIT")
        )

        if fix_mode:
            self.stdout.write(
                self.style.WARNING("⚠️  FIX MODE ENABLED - Code will be modified!")
            )

        # Model analysis
        self._analyze_models(target_app, target_model)

        # Code analysis
        if target_app:
            apps_to_audit = [target_app]
        else:
            apps_to_audit = [app.name for app in apps.get_app_configs()
                           if app.name.startswith('apps.')]

        total_issues = 0
        total_fixes = 0

        for app_name in apps_to_audit:
            if app_name.startswith('apps.'):
                app_path = app_name.replace('.', '/')
            else:
                app_path = f"apps/{app_name}"

            if os.path.exists(app_path):
                issues, fixes = self._audit_app_queries(app_path, fix_mode, exclude_dirs)
                total_issues += issues
                total_fixes += fixes

        # Print summary
        self._print_summary(total_issues, total_fixes, fix_mode)

    def _analyze_models(self, target_app: str = None, target_model: str = None):
        """Analyze model relationships for optimization opportunities."""
        self.stdout.write("\n📊 MODEL RELATIONSHIP ANALYSIS")
        self.stdout.write("=" * 80)

        if target_model:
            try:
                app_label, model_name = target_model.split('.')
                model = apps.get_model(app_label, model_name)
                models_to_analyze = [model]
            except (ValueError, LookupError) as e:
                self.stderr.write(f"Invalid model specification: {e}")
                return
        elif target_app:
            try:
                app_config = apps.get_app_config(target_app)
                models_to_analyze = app_config.get_models()
            except LookupError as e:
                self.stderr.write(f"Invalid app: {e}")
                return
        else:
            # Analyze all models in apps.*
            models_to_analyze = []
            for app_config in apps.get_app_configs():
                if app_config.name.startswith('apps.'):
                    models_to_analyze.extend(app_config.get_models())

        for model in models_to_analyze:
            self._analyze_single_model(model)

    def _analyze_single_model(self, model: models.Model):
        """Analyze a single model for optimization opportunities."""
        model_name = f"{model._meta.app_label}.{model._meta.model_name}"

        # Force analysis
        QueryOptimizer._analyze_model_relationships(model)
        relationships = QueryOptimizer._relationship_cache.get(model_name, {})

        # Count relationships
        fk_count = len(relationships.get('foreign_keys', []))
        m2m_count = len(relationships.get('many_to_many', []))
        reverse_fk_count = len(relationships.get('reverse_foreign_keys', []))

        total_relationships = fk_count + m2m_count + reverse_fk_count

        if total_relationships == 0:
            return  # Skip models with no relationships

        self.stdout.write(f"\n📋 {model_name}")
        self.stdout.write(f"  Foreign Keys: {fk_count}")
        self.stdout.write(f"  Many-to-Many: {m2m_count}")
        self.stdout.write(f"  Reverse Relations: {reverse_fk_count}")

        # High-impact relationships
        high_impact_fks = [fk for fk in relationships.get('foreign_keys', [])
                          if fk['performance_impact'] == 'high']
        if high_impact_fks:
            self.stdout.write(f"  🚨 High-impact FKs: {[fk['name'] for fk in high_impact_fks]}")

        # Optimization recommendations
        recommendations = []
        if fk_count > 0:
            recommendations.append(f"Use select_related({', '.join([fk['name'] for fk in relationships.get('foreign_keys', [])])})")

        if m2m_count > 0:
            recommendations.append(f"Use prefetch_related({', '.join([m2m['name'] for m2m in relationships.get('many_to_many', [])])})")

        if recommendations:
            self.stdout.write(f"  💡 Recommendations:")
            for rec in recommendations:
                self.stdout.write(f"    - {rec}")

    def _audit_app_queries(self, app_path: str, fix_mode: bool, exclude_dirs: List[str]) -> Tuple[int, int]:
        """
        Audit query patterns in an app's code.

        Args:
            app_path: Path to the app directory
            fix_mode: Whether to apply automatic fixes
            exclude_dirs: Directories to exclude

        Returns:
            Tuple of (issues found, fixes applied)
        """
        self.stdout.write(f"\n🔍 AUDITING QUERIES IN: {app_path}")
        self.stdout.write("─" * 80)

        python_files = self._find_python_files(app_path, exclude_dirs)
        total_issues = 0
        total_fixes = 0

        for file_path in python_files:
            issues, fixes = self._audit_file_queries(file_path, fix_mode)
            total_issues += issues
            total_fixes += fixes

        return total_issues, total_fixes

    def _find_python_files(self, path: str, exclude_dirs: List[str]) -> List[str]:
        """Find Python files in the given path."""
        python_files = []

        for root, dirs, files in os.walk(path):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))

        return python_files

    def _audit_file_queries(self, file_path: str, fix_mode: bool) -> Tuple[int, int]:
        """
        Audit query patterns in a single file.

        Args:
            file_path: Path to the file to audit
            fix_mode: Whether to apply automatic fixes

        Returns:
            Tuple of (issues found, fixes applied)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            issues = 0
            fixes = 0

            # Patterns that indicate potential N+1 queries
            problematic_patterns = [
                # .objects.all() without optimization
                (
                    re.compile(r'(\w+)\.objects\.all\(\)(?!\.(?:select_related|prefetch_related))', re.MULTILINE),
                    'Unoptimized .objects.all() call',
                    lambda m: f"{m.group(1)}.objects.all().select_related()"  # Simple fix
                ),
                # .objects.filter() without optimization
                (
                    re.compile(r'(\w+)\.objects\.filter\([^)]+\)(?!\.(?:select_related|prefetch_related))', re.MULTILINE),
                    'Unoptimized .objects.filter() call',
                    lambda m: f"{m.group(0)}.select_related()"  # Simple fix
                ),
                # .objects.get() in loops (potential N+1)
                (
                    re.compile(r'for\s+\w+\s+in\s+.*?:\s*\n\s*.*\.objects\.get\(', re.MULTILINE | re.DOTALL),
                    'Potential N+1: .objects.get() in loop',
                    None  # No automatic fix - requires manual review
                ),
                # Accessing related objects without optimization
                (
                    re.compile(r'for\s+\w+\s+in\s+.*?:\s*\n\s*.*\.\w+\.\w+', re.MULTILINE | re.DOTALL),
                    'Potential N+1: Related field access in loop',
                    None  # No automatic fix - requires manual review
                ),
            ]

            original_content = content
            modified_content = content

            for pattern, issue_type, fix_func in problematic_patterns:
                matches = list(pattern.finditer(content))
                if matches:
                    issues += len(matches)

                    # Report issues
                    if not hasattr(self, '_reported_files'):
                        self._reported_files = set()

                    if file_path not in self._reported_files:
                        self.stdout.write(f"\n📁 {file_path}")
                        self._reported_files.add(file_path)

                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        self.stdout.write(f"  Line {line_num}: {issue_type}")
                        self.stdout.write(f"    Code: {match.group(0)[:80]}...")

                        # Apply fix if possible and in fix mode
                        if fix_mode and fix_func:
                            try:
                                fixed_code = fix_func(match)
                                modified_content = modified_content.replace(match.group(0), fixed_code, 1)
                                fixes += 1
                                self.stdout.write(f"    🔧 FIXED: {fixed_code[:80]}...")
                            except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
                                self.stdout.write(f"    ❌ Fix failed: {e}")

            # Write back fixed content
            if fix_mode and fixes > 0:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)

            return issues, fixes

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            self.stderr.write(f"Error auditing {file_path}: {e}")
            return 0, 0

    def _print_summary(self, total_issues: int, total_fixes: int, fix_mode: bool):
        """Print audit summary."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📊 QUERY OPTIMIZATION AUDIT SUMMARY")
        self.stdout.write("=" * 80)

        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS("✅ No query optimization issues found!"))
        else:
            self.stdout.write(f"🚨 Total optimization opportunities: {total_issues}")

            if fix_mode:
                self.stdout.write(f"🔧 Issues automatically fixed: {total_fixes}")
                self.stdout.write(f"⚠️  Issues requiring manual fix: {total_issues - total_fixes}")
            else:
                self.stdout.write("💡 Run with --fix to automatically fix some issues")

        self.stdout.write("\n🔧 RECOMMENDED NEXT STEPS:")
        self.stdout.write("1. Add QueryOptimizationMiddleware to MIDDLEWARE in settings")
        self.stdout.write("2. Use QueryOptimizer.optimize_queryset() for automatic optimization")
        self.stdout.write("3. Apply select_related() for foreign key relationships")
        self.stdout.write("4. Apply prefetch_related() for many-to-many relationships")
        self.stdout.write("5. Review and optimize queries in loops")
        self.stdout.write("6. Use get_optimized_people() and get_optimized_activities() helpers")
        self.stdout.write("7. Monitor query performance with Django Debug Toolbar in development")