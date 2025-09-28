"""
Database Index Audit Management Command

Comprehensive analysis of database indexes across all Django models.
Identifies missing indexes, recommends PostgreSQL-specific optimizations,
and generates actionable migration scripts.

Usage:
    python manage.py audit_database_indexes
    python manage.py audit_database_indexes --app y_helpdesk
    python manage.py audit_database_indexes --generate-migrations
    python manage.py audit_database_indexes --export report.json
"""

import logging
from collections import defaultdict
from typing import Dict, List, Any, Set, Tuple
from pathlib import Path

from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import models, connection
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


class IndexAuditor:
    """Analyzes models for missing database indexes and optimization opportunities."""

    INDEXED_LOOKUP_TYPES = {'exact', 'iexact', 'contains', 'icontains', 'in', 'gt', 'gte', 'lt', 'lte', 'range'}

    def __init__(self):
        self.findings = defaultdict(list)
        self.stats = {
            'total_models': 0,
            'models_with_indexes': 0,
            'missing_indexes': 0,
            'recommended_indexes': 0,
            'json_fields_without_gin': 0,
            'date_fields_without_brin': 0,
        }

    def audit_all_models(self, app_label: str = None) -> Dict[str, Any]:
        """Audit all models for index optimization opportunities."""
        model_list = apps.get_models() if not app_label else apps.get_app_config(app_label).get_models()

        for model in model_list:
            if model._meta.app_label in ['contenttypes', 'auth', 'sessions', 'admin']:
                continue

            self.stats['total_models'] += 1
            self._audit_model(model)

        return {
            'findings': dict(self.findings),
            'stats': self.stats,
            'timestamp': timezone.now().isoformat(),
        }

    def _audit_model(self, model):
        """Audit a single model for index opportunities."""
        app_label = model._meta.app_label
        model_name = model._meta.object_name
        model_key = f"{app_label}.{model_name}"

        existing_indexes = self._get_existing_indexes(model)
        if existing_indexes:
            self.stats['models_with_indexes'] += 1

        self._check_status_priority_fields(model, model_key, existing_indexes)
        self._check_date_fields(model, model_key, existing_indexes)
        self._check_foreign_keys(model, model_key, existing_indexes)
        self._check_json_fields(model, model_key, existing_indexes)
        self._check_boolean_fields(model, model_key, existing_indexes)
        self._suggest_composite_indexes(model, model_key, existing_indexes)

    def _get_existing_indexes(self, model) -> Set[str]:
        """Extract existing indexes from model Meta."""
        existing = set()

        for field in model._meta.fields:
            if field.db_index or field.unique:
                existing.add(field.name)

        if hasattr(model._meta, 'indexes'):
            for index in model._meta.indexes:
                for field in index.fields:
                    field_name = field.lstrip('-')
                    existing.add(field_name)

        return existing

    def _check_status_priority_fields(self, model, model_key: str, existing: Set[str]):
        """Check for missing indexes on status/priority fields."""
        priority_fields = ['status', 'priority', 'workstatus', 'identifier']

        for field in model._meta.fields:
            if field.name in priority_fields and field.name not in existing:
                if isinstance(field, models.CharField) and field.choices:
                    self.findings[model_key].append({
                        'type': 'missing_status_priority_index',
                        'severity': 'HIGH',
                        'field': field.name,
                        'recommendation': f"Add db_index=True or Meta.indexes for '{field.name}'",
                        'reason': 'Frequently filtered choice field without index',
                        'migration_code': self._generate_index_code(model, field.name, 'single'),
                    })
                    self.stats['missing_indexes'] += 1
                    self.stats['recommended_indexes'] += 1

    def _check_date_fields(self, model, model_key: str, existing: Set[str]):
        """Check for missing indexes on date/datetime fields."""
        date_fields = []

        for field in model._meta.fields:
            if isinstance(field, (models.DateField, models.DateTimeField)):
                if field.name not in existing and not field.auto_now and not field.auto_now_add:
                    date_fields.append(field)

        for field in date_fields:
            should_use_brin = field.name in ['fromdate', 'uptodate', 'plandatetime',
                                              'expirydatetime', 'punchintime', 'punchouttime',
                                              'datetime', 'created_at', 'modified_at']

            self.findings[model_key].append({
                'type': 'missing_date_index',
                'severity': 'MEDIUM',
                'field': field.name,
                'recommendation': f"Add {'BRIN' if should_use_brin else 'B-Tree'} index for '{field.name}'",
                'reason': 'Date/time field used in range queries and ordering',
                'migration_code': self._generate_index_code(
                    model, field.name, 'brin' if should_use_brin else 'single'
                ),
            })
            self.stats['missing_indexes'] += 1
            self.stats['recommended_indexes'] += 1

            if should_use_brin:
                self.stats['date_fields_without_brin'] += 1

    def _check_foreign_keys(self, model, model_key: str, existing: Set[str]):
        """Check foreign key indexes (Django auto-creates these, but verify)."""
        fk_fields = []

        for field in model._meta.fields:
            if isinstance(field, models.ForeignKey):
                db_column = field.column
                if db_column not in existing:
                    fk_fields.append(field)

        if fk_fields:
            for field in fk_fields[:3]:
                self.findings[model_key].append({
                    'type': 'fk_index_verification',
                    'severity': 'LOW',
                    'field': field.name,
                    'recommendation': f"Verify auto-created index exists for FK '{field.name}'",
                    'reason': 'Foreign keys should have automatic indexes',
                })

    def _check_json_fields(self, model, model_key: str, existing: Set[str]):
        """Check for missing GIN indexes on JSON fields."""
        json_fields = []

        for field in model._meta.fields:
            if isinstance(field, models.JSONField):
                json_fields.append(field)

        for field in json_fields:
            self.findings[model_key].append({
                'type': 'missing_gin_index',
                'severity': 'MEDIUM',
                'field': field.name,
                'recommendation': f"Add GIN index for JSON field '{field.name}' if queried",
                'reason': 'JSON fields benefit from GIN indexes for containment queries',
                'migration_code': self._generate_index_code(model, field.name, 'gin'),
            })
            self.stats['json_fields_without_gin'] += 1
            self.stats['recommended_indexes'] += 1

    def _check_boolean_fields(self, model, model_key: str, existing: Set[str]):
        """Check for indexes on frequently filtered boolean fields."""
        important_booleans = ['enable', 'is_active', 'isverified', 'isescalated', 'is_staff']

        for field in model._meta.fields:
            if isinstance(field, models.BooleanField) and field.name in important_booleans:
                if field.name not in existing:
                    self.findings[model_key].append({
                        'type': 'missing_boolean_index',
                        'severity': 'LOW',
                        'field': field.name,
                        'recommendation': f"Consider partial index for '{field.name}=True' cases",
                        'reason': 'Boolean fields can use partial indexes for active records',
                        'migration_code': self._generate_index_code(model, field.name, 'partial_boolean'),
                    })
                    self.stats['recommended_indexes'] += 1

    def _suggest_composite_indexes(self, model, model_key: str, existing: Set[str]):
        """Suggest composite indexes for common query patterns."""
        composite_patterns = [
            (['status', 'priority'], 'Status + priority filtering'),
            (['bu', 'status'], 'Tenant + status filtering'),
            (['client', 'status'], 'Client + status filtering'),
            (['people', 'datefor'], 'User + date filtering'),
            (['bu', 'datefor'], 'Tenant + date filtering'),
            (['identifier', 'enable'], 'Type + active filtering'),
            (['status', 'modifieddatetime'], 'Status + modification tracking'),
            (['workstatus', 'priority'], 'Work status + priority'),
        ]

        model_fields = {f.name for f in model._meta.fields}

        for field_combo, reason in composite_patterns:
            if all(f in model_fields for f in field_combo):
                if not self._has_composite_index(model, field_combo):
                    self.findings[model_key].append({
                        'type': 'suggested_composite_index',
                        'severity': 'MEDIUM',
                        'fields': field_combo,
                        'recommendation': f"Add composite index on {field_combo}",
                        'reason': reason,
                        'migration_code': self._generate_index_code(model, field_combo, 'composite'),
                    })
                    self.stats['recommended_indexes'] += 1

    def _has_composite_index(self, model, field_combo: List[str]) -> bool:
        """Check if a composite index exists for the field combination."""
        if not hasattr(model._meta, 'indexes'):
            return False

        for index in model._meta.indexes:
            index_fields = [f.lstrip('-') for f in index.fields]
            if set(index_fields) == set(field_combo):
                return True

        return False

    def _generate_index_code(self, model, fields, index_type: str) -> str:
        """Generate Django migration code for index creation."""
        model_name = model._meta.object_name.lower()

        if index_type == 'single':
            field_name = fields if isinstance(fields, str) else fields[0]
            return f"""
        migrations.AlterField(
            model_name='{model_name}',
            name='{field_name}',
            field=models.{model._meta.get_field(field_name).__class__.__name__}(
                ...,
                db_index=True,
            ),
        ),"""

        elif index_type == 'composite':
            field_list = "', '".join(fields)
            index_name = f"{model._meta.db_table}_{'_'.join(fields)}_idx"[:63]
            return f"""
        migrations.AddIndex(
            model_name='{model_name}',
            index=models.Index(fields=['{field_list}'], name='{index_name}'),
        ),"""

        elif index_type == 'gin':
            field_name = fields if isinstance(fields, str) else fields[0]
            index_name = f"{model._meta.db_table}_{field_name}_gin_idx"[:63]
            return f"""
        migrations.AddIndex(
            model_name='{model_name}',
            index=GinIndex(fields=['{field_name}'], name='{index_name}'),
        ),"""

        elif index_type == 'brin':
            field_name = fields if isinstance(fields, str) else fields[0]
            index_name = f"{model._meta.db_table}_{field_name}_brin_idx"[:63]
            return f"""
        migrations.AddIndex(
            model_name='{model_name}',
            index=BrinIndex(fields=['{field_name}'], name='{index_name}'),
        ),"""

        elif index_type == 'partial_boolean':
            field_name = fields if isinstance(fields, str) else fields[0]
            index_name = f"{model._meta.db_table}_{field_name}_true_idx"[:63]
            return f"""
        migrations.AddIndex(
            model_name='{model_name}',
            index=models.Index(
                fields=['{field_name}'],
                name='{index_name}',
                condition=models.Q({field_name}=True)
            ),
        ),"""

        return ""


class Command(BaseCommand):
    help = 'Audit database indexes and recommend optimizations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            help='Audit specific app only'
        )
        parser.add_argument(
            '--generate-migrations',
            action='store_true',
            help='Generate migration file templates'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export report to JSON file'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed analysis'
        )

    def handle(self, *args, **options):
        app_label = options.get('app')
        generate_migrations = options.get('generate_migrations')
        export_path = options.get('export')
        verbose = options.get('verbose')

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('🔍 DATABASE INDEX AUDIT'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')

        auditor = IndexAuditor()

        try:
            results = auditor.audit_all_models(app_label)
        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stdout.write(self.style.ERROR(f'❌ Audit failed: {type(e).__name__}: {str(e)}'))
            return

        self._display_summary(results['stats'])
        self._display_findings(results['findings'], verbose)

        if generate_migrations:
            self._generate_migration_templates(results['findings'])

        if export_path:
            self._export_results(results, export_path)

        self.stdout.write('')
        self._display_recommendations(results)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Audit completed successfully'))

    def _display_summary(self, stats: Dict[str, int]):
        """Display audit statistics summary."""
        self.stdout.write(self.style.WARNING('📊 AUDIT SUMMARY'))
        self.stdout.write('-' * 80)
        self.stdout.write(f"Total Models Analyzed:        {stats['total_models']}")
        self.stdout.write(f"Models with Indexes:          {stats['models_with_indexes']}")
        self.stdout.write(f"Missing Indexes Found:        {stats['missing_indexes']}")
        self.stdout.write(f"Recommended Indexes:          {stats['recommended_indexes']}")
        self.stdout.write(f"JSON Fields without GIN:      {stats['json_fields_without_gin']}")
        self.stdout.write(f"Date Fields without BRIN:     {stats['date_fields_without_brin']}")
        self.stdout.write('')

    def _display_findings(self, findings: Dict[str, List], verbose: bool):
        """Display detailed findings by model."""
        if not findings:
            self.stdout.write(self.style.SUCCESS('✅ No index issues found!'))
            return

        self.stdout.write(self.style.WARNING('🔎 DETAILED FINDINGS'))
        self.stdout.write('-' * 80)

        high_priority_models = []
        medium_priority_models = []
        low_priority_models = []

        for model_key, issues in findings.items():
            high_count = sum(1 for i in issues if i['severity'] == 'HIGH')
            medium_count = sum(1 for i in issues if i['severity'] == 'MEDIUM')
            low_count = sum(1 for i in issues if i['severity'] == 'LOW')

            if high_count > 0:
                high_priority_models.append((model_key, issues, high_count, medium_count, low_count))
            elif medium_count > 0:
                medium_priority_models.append((model_key, issues, high_count, medium_count, low_count))
            else:
                low_priority_models.append((model_key, issues, high_count, medium_count, low_count))

        for priority_list, label, style_func in [
            (high_priority_models, '🔴 HIGH PRIORITY', self.style.ERROR),
            (medium_priority_models, '🟡 MEDIUM PRIORITY', self.style.WARNING),
            (low_priority_models, '⚪ LOW PRIORITY', self.style.NOTICE),
        ]:
            if priority_list:
                self.stdout.write('')
                self.stdout.write(style_func(label))
                for model_key, issues, h, m, l in priority_list:
                    self.stdout.write(f"\n{model_key} (H:{h}, M:{m}, L:{l})")
                    if verbose:
                        for issue in issues:
                            self.stdout.write(f"  • {issue['field'] if 'field' in issue else issue.get('fields', 'N/A')}")
                            self.stdout.write(f"    {issue['recommendation']}")
                            self.stdout.write(f"    Reason: {issue['reason']}")

    def _generate_migration_templates(self, findings: Dict[str, List]):
        """Generate migration file templates for each app."""
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('📝 MIGRATION TEMPLATES'))
        self.stdout.write('-' * 80)

        apps_with_findings = defaultdict(list)
        for model_key, issues in findings.items():
            app_label = model_key.split('.')[0]
            apps_with_findings[app_label].extend(issues)

        for app_label, issues in apps_with_findings.items():
            migration_content = self._create_migration_content(app_label, issues)
            self.stdout.write(f"\n{app_label}/migrations/XXXX_add_performance_indexes.py")
            self.stdout.write(migration_content[:500] + "..." if len(migration_content) > 500 else migration_content)

    def _create_migration_content(self, app_label: str, issues: List[Dict]) -> str:
        """Create migration file content."""
        operations = []
        for issue in issues:
            if 'migration_code' in issue:
                operations.append(issue['migration_code'])

        unique_operations = list(dict.fromkeys(operations))[:10]

        return f"""# Generated by audit_database_indexes command
from django.db import migrations, models
from django.contrib.postgres.indexes import GinIndex, BrinIndex


class Migration(migrations.Migration):

    dependencies = [
        ('{app_label}', 'XXXX_previous_migration'),
    ]

    operations = [{''.join(unique_operations)}
    ]
"""

    def _export_results(self, results: Dict, export_path: str):
        """Export results to JSON file."""
        import json
        with open(export_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        self.stdout.write(self.style.SUCCESS(f'✅ Results exported to {export_path}'))

    def _display_recommendations(self, results: Dict):
        """Display prioritized recommendations."""
        self.stdout.write(self.style.WARNING('💡 TOP RECOMMENDATIONS'))
        self.stdout.write('-' * 80)

        all_issues = []
        for model_key, issues in results['findings'].items():
            for issue in issues:
                issue['model'] = model_key
                all_issues.append(issue)

        high_priority = sorted(
            [i for i in all_issues if i['severity'] == 'HIGH'],
            key=lambda x: x.get('field', '')
        )[:10]

        if high_priority:
            self.stdout.write('\n🔴 Implement these HIGH priority indexes first:')
            for i, issue in enumerate(high_priority, 1):
                field_info = issue.get('field') or ', '.join(issue.get('fields', []))
                self.stdout.write(f"{i}. {issue['model']}.{field_info}")
                self.stdout.write(f"   {issue['recommendation']}")
        else:
            self.stdout.write('✅ No high priority issues found!')

        stats = results['stats']
        if stats['recommended_indexes'] > 0:
            self.stdout.write('')
            self.stdout.write(f"Total of {stats['recommended_indexes']} indexes recommended for optimal performance")