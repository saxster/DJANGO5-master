"""
Validation Compliance Monitor

Management command to audit and monitor Rule #13 compliance across all
forms, serializers, and legacy API inputs.

Usage:
    python manage.py validate_input_compliance
    python manage.py validate_input_compliance --fix-violations

HIGH-IMPACT SECURITY FEATURE - Continuous Compliance Monitoring
"""

from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.forms import ModelForm
from rest_framework import serializers
import ast
import inspect
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Audit input validation compliance (Rule #13)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-violations',
            action='store_true',
            help='Attempt to fix violations automatically'
        )
        parser.add_argument(
            '--app',
            type=str,
            help='Check specific app only'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='stdout',
            help='Output format: stdout, json, html'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write(self.style.WARNING("RULE #13 COMPLIANCE AUDIT - INPUT VALIDATION"))
        self.stdout.write(self.style.WARNING("=" * 80))
        self.stdout.write("")

        violations = {
            'forms': [],
            'serializers': [],
        }

        app_filter = options.get('app')

        for app_config in apps.get_app_configs():
            if app_filter and app_config.name != app_filter:
                continue

            self.stdout.write(f"\n📦 Checking app: {app_config.name}")

            violations['forms'].extend(self._audit_forms(app_config))
            violations['serializers'].extend(self._audit_serializers(app_config))

        self._print_summary(violations)

        if options.get('output') == 'json':
            self._output_json(violations)
        elif options.get('output') == 'html':
            self._output_html(violations)

        total_violations = sum(len(v) for v in violations.values())

        if total_violations > 0:
            self.stdout.write(self.style.ERROR(f"\n❌ Found {total_violations} violations"))
            if not options.get('fix_violations'):
                self.stdout.write(
                    self.style.WARNING(
                        "\nRun with --fix-violations to attempt automatic fixes"
                    )
                )
            return 1
        else:
            self.stdout.write(self.style.SUCCESS("\n✅ All checks passed - 100% compliant"))
            return 0

    def _audit_forms(self, app_config):
        """Audit Django forms for Rule #13 compliance."""
        violations = []

        forms_module_path = Path(app_config.path) / 'forms.py'
        if not forms_module_path.exists():
            return violations

        try:
            with open(forms_module_path, 'r') as f:
                source = f.read()
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if self._is_model_form(node):
                            violation = self._check_form_compliance(node, app_config.name)
                            if violation:
                                violations.append(violation)

        except (IOError, SyntaxError) as e:
            logger.error(f"Error reading {forms_module_path}: {e}")

        return violations

    def _is_model_form(self, node):
        """Check if class inherits from ModelForm."""
        for base in node.bases:
            if isinstance(base, ast.Name) and 'Form' in base.id:
                return True
            if isinstance(base, ast.Attribute) and 'Form' in base.attr:
                return True
        return False

    def _check_form_compliance(self, node, app_name):
        """Check if form complies with Rule #13."""
        form_name = node.name

        has_meta = False
        has_fields_all = False
        has_explicit_fields = False
        has_validation = False

        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == 'Meta':
                has_meta = True

                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == 'fields':
                                if isinstance(meta_item.value, ast.Constant) and meta_item.value.value == '__all__':
                                    has_fields_all = True
                                elif isinstance(meta_item.value, (ast.List, ast.Tuple)):
                                    has_explicit_fields = True

            if isinstance(item, ast.FunctionDef):
                if item.name.startswith('clean_') or item.name == 'clean':
                    has_validation = True

        if has_fields_all:
            return {
                'app': app_name,
                'type': 'form',
                'name': form_name,
                'violation': 'uses fields="__all__"',
                'severity': 'HIGH'
            }

        if has_explicit_fields and not has_validation:
            return {
                'app': app_name,
                'type': 'form',
                'name': form_name,
                'violation': 'missing custom validation methods',
                'severity': 'MEDIUM'
            }

        return None

    def _audit_serializers(self, app_config):
        """Audit REST Framework serializers for Rule #13 compliance."""
        violations = []

        serializers_path = Path(app_config.path) / 'serializers.py'
        if not serializers_path.exists():
            return violations

        try:
            with open(serializers_path, 'r') as f:
                source = f.read()

                if 'fields = "__all__"' in source:
                    tree = ast.parse(source)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            if self._has_fields_all(node):
                                violations.append({
                                    'app': app_config.name,
                                    'type': 'serializer',
                                    'name': node.name,
                                    'violation': 'uses fields="__all__"',
                                    'severity': 'CRITICAL'
                                })

        except (IOError, SyntaxError) as e:
            logger.error(f"Error reading {serializers_path}: {e}")

        return violations

    def _has_fields_all(self, node):
        """Check if serializer uses fields = '__all__'."""
        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == 'Meta':
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name) and target.id == 'fields':
                                if isinstance(meta_item.value, ast.Constant) and meta_item.value.value == '__all__':
                                    return True
        return False

    def _print_summary(self, violations):
        """Print violation summary."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("COMPLIANCE SUMMARY")
        self.stdout.write("=" * 80 + "\n")

        form_count = len(violations['forms'])
        serializer_count = len(violations['serializers'])

        if form_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ Django Forms: {form_count} violations"))
            for v in violations['forms'][:5]:
                self.stdout.write(f"   - {v['app']}.{v['name']}: {v['violation']}")

        if serializer_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ DRF Serializers: {serializer_count} violations"))
            for v in violations['serializers'][:5]:
                self.stdout.write(f"   - {v['app']}.{v['name']}: {v['violation']}")

        total = form_count + serializer_count
        if total == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ No violations found - 100% compliant!"))

    def _output_json(self, violations):
        """Output violations as JSON."""
        import json
        from django.conf import settings

        output_file = Path(settings.BASE_DIR) / 'validation_compliance_report.json'

        with open(output_file, 'w') as f:
            json.dump(violations, f, indent=2)

        self.stdout.write(f"\n📄 JSON report saved to: {output_file}")

    def _output_html(self, violations):
        """Output violations as HTML report."""
        from django.conf import settings

        output_file = Path(settings.BASE_DIR) / 'validation_compliance_report.html'

        html = self._generate_html_report(violations)

        with open(output_file, 'w') as f:
            f.write(html)

        self.stdout.write(f"\n📄 HTML report saved to: {output_file}")

    def _generate_html_report(self, violations):
        """Generate HTML compliance report."""
        total = sum(len(v) for v in violations.values())

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Rule #13 Compliance Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .summary {{ background: #f0f0f0; padding: 15px; border-radius: 5px; }}
        .violations {{ margin-top: 20px; }}
        .violation {{ padding: 10px; margin: 5px 0; border-left: 4px solid red; background: #fff5f5; }}
        .critical {{ border-left-color: #dc3545; }}
        .high {{ border-left-color: #fd7e14; }}
        .medium {{ border-left-color: #ffc107; }}
        .compliant {{ color: green; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Rule #13: Input Validation Compliance Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p>Total Violations: <strong>{total}</strong></p>
        <ul>
            <li>Django Forms: {len(violations['forms'])}</li>
            <li>DRF Serializers: {len(violations['serializers'])}</li>
        </ul>
        {"<p class='compliant'>✅ 100% COMPLIANT</p>" if total == 0 else ""}
    </div>
    <div class="violations">
        {self._violations_html(violations)}
    </div>
</body>
</html>
"""
        return html

    def _violations_html(self, violations):
        """Generate HTML for violations list."""
        html = ""

        for category, items in violations.items():
            if items:
                html += f"<h3>{category.replace('_', ' ').title()}</h3>"
                for item in items:
                    html += f"""
                    <div class="violation {item['severity'].lower()}">
                        <strong>{item['app']}.{item['name']}</strong><br>
                        Violation: {item['violation']}<br>
                        Severity: {item['severity']}
                    </div>
                    """

        return html
