#!/usr/bin/env python
"""
Model inspection tool for Django ORM migration.
Provides detailed information about models and their relationships.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.apps import apps
from django.db import models
from django.db.models import ForeignKey, ManyToManyField, OneToOneField
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


class ModelInspector:
    """Inspect Django models and generate detailed reports"""
    
    def __init__(self):
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'apps': {},
            'summary': {
                'total_apps': 0,
                'total_models': 0,
                'total_fields': 0,
                'total_relationships': 0
            }
        }
        
        # Apps to focus on
        self.target_apps = [
            'onboarding',
            'peoples',
            'core',
            'activity',
            'attendance',
            'y_helpdesk',
            'reports'
        ]
    
    def print_header(self, text, level=1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Fore.BLUE}{'=' * 80}")
            print(f"{Fore.BLUE}{text.center(80)}")
            print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.CYAN}{text}")
            print(f"{Fore.CYAN}{'-' * len(text)}{Style.RESET_ALL}")
    
    def get_field_info(self, field: models.Field) -> Dict[str, Any]:
        """Extract detailed field information"""
        field_info = {
            'name': field.name,
            'type': field.__class__.__name__,
            'verbose_name': str(field.verbose_name),
            'null': field.null,
            'blank': field.blank,
            'default': str(field.default) if field.default != models.fields.NOT_PROVIDED else None,
            'db_index': field.db_index,
            'unique': field.unique,
            'primary_key': field.primary_key,
            'editable': field.editable,
        }
        
        # Additional info for specific field types
        if hasattr(field, 'max_length'):
            field_info['max_length'] = field.max_length
        
        if hasattr(field, 'choices') and field.choices:
            field_info['choices'] = [choice[0] for choice in field.choices]
        
        if isinstance(field, (ForeignKey, OneToOneField, ManyToManyField)):
            field_info['related_model'] = field.related_model._meta.label
            if hasattr(field, 'on_delete'):
                field_info['on_delete'] = str(field.remote_field.on_delete).split('.')[-1]
            field_info['related_name'] = field.related_query_name()
        
        return field_info
    
    def inspect_model(self, model: models.Model) -> Dict[str, Any]:
        """Inspect a single model"""
        meta = model._meta
        
        model_info = {
            'name': model.__name__,
            'app_label': meta.app_label,
            'db_table': meta.db_table,
            'verbose_name': str(meta.verbose_name),
            'verbose_name_plural': str(meta.verbose_name_plural),
            'abstract': meta.abstract,
            'managed': meta.managed,
            'proxy': meta.proxy,
            'fields': {},
            'relationships': {
                'foreign_keys': [],
                'one_to_one': [],
                'many_to_many': []
            },
            'indexes': [],
            'unique_together': list(meta.unique_together) if meta.unique_together else [],
            'ordering': list(meta.ordering) if meta.ordering else [],
            'permissions': list(meta.permissions) if meta.permissions else []
        }
        
        # Inspect fields
        for field in meta.get_fields():
            field_info = self.get_field_info(field)
            model_info['fields'][field.name] = field_info
            
            # Categorize relationships
            if isinstance(field, ForeignKey):
                model_info['relationships']['foreign_keys'].append({
                    'field': field.name,
                    'to': field.related_model._meta.label,
                    'on_delete': str(field.remote_field.on_delete).split('.')[-1]
                })
                self.report['summary']['total_relationships'] += 1
            elif isinstance(field, OneToOneField):
                model_info['relationships']['one_to_one'].append({
                    'field': field.name,
                    'to': field.related_model._meta.label
                })
                self.report['summary']['total_relationships'] += 1
            elif isinstance(field, ManyToManyField):
                model_info['relationships']['many_to_many'].append({
                    'field': field.name,
                    'to': field.related_model._meta.label,
                    'through': field.remote_field.through._meta.label if field.remote_field.through else None
                })
                self.report['summary']['total_relationships'] += 1
        
        # Get indexes
        for index in meta.indexes:
            model_info['indexes'].append({
                'name': index.name,
                'fields': list(index.fields),
                'condition': str(index.condition) if index.condition else None
            })
        
        self.report['summary']['total_fields'] += len(model_info['fields'])
        
        return model_info
    
    def inspect_app(self, app_config) -> Dict[str, Any]:
        """Inspect all models in an app"""
        app_info = {
            'name': app_config.name,
            'label': app_config.label,
            'verbose_name': app_config.verbose_name,
            'models': {}
        }
        
        models = app_config.get_models()
        for model in models:
            model_info = self.inspect_model(model)
            app_info['models'][model.__name__] = model_info
            self.report['summary']['total_models'] += 1
        
        return app_info
    
    def generate_relationship_diagram(self):
        """Generate a simple text-based relationship diagram"""
        self.print_header("Model Relationships Diagram", 2)
        
        relationships = []
        
        for app_label in self.target_apps:
            try:
                app_config = apps.get_app_config(app_label)
                models = app_config.get_models()
                
                for model in models:
                    model_name = f"{app_label}.{model.__name__}"
                    
                    for field in model._meta.get_fields():
                        if isinstance(field, ForeignKey):
                            related_model = field.related_model
                            related_name = f"{related_model._meta.app_label}.{related_model.__name__}"
                            relationships.append(f"{model_name} -> {related_name} [{field.name}]")
            except LookupError:
                continue
        
        # Print relationships
        print("\nForeign Key Relationships:")
        for rel in sorted(relationships):
            print(f"  {rel}")
        
        return relationships
    
    def check_model_usage_in_queries(self):
        """Check which models are used in our ORM queries"""
        self.print_header("Models Used in ORM Queries", 2)
        
        # Models referenced in our queries
        used_models = {
            'Capability': ['Tree traversal', 'Permission checks'],
            'Bt': ['Site hierarchy', 'Client management', 'BU structure'],
            'People': ['User management', 'Access control', 'Attendance'],
            'Ticket': ['Helpdesk', 'Escalation', 'Email notifications'],
            'Task': ['Task management', 'Scheduling', 'Reports'],
            'Asset': ['Asset tracking', 'Status management'],
            'Activity': ['Activity logging', 'Tour management'],
            'Attendance': ['Time tracking', 'Reports'],
            'TypeAssist': ['Master data', 'Lookups'],
            'Geofence': ['Location tracking'],
            'Shift': ['Shift management'],
            'ScheduleReport': ['Report scheduling', 'Background tasks']
        }
        
        for model_name, usage in used_models.items():
            print(f"\n{Fore.GREEN}{model_name}:{Style.RESET_ALL}")
            for use_case in usage:
                print(f"  - {use_case}")
        
        return used_models
    
    def generate_model_documentation(self):
        """Generate markdown documentation for models"""
        doc_path = project_root / 'docs' / 'MODEL_REFERENCE.md'
        
        with open(doc_path, 'w') as f:
            f.write("# Model Reference Documentation\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Table of Contents\n\n")
            
            # Write TOC
            for app_label in sorted(self.report['apps'].keys()):
                f.write(f"- [{app_label}](#{app_label})\n")
                app_data = self.report['apps'][app_label]
                for model_name in sorted(app_data['models'].keys()):
                    f.write(f"  - [{model_name}](#{app_label}-{model_name.lower()})\n")
            
            f.write("\n---\n\n")
            
            # Write model details
            for app_label in sorted(self.report['apps'].keys()):
                f.write(f"## {app_label}\n\n")
                app_data = self.report['apps'][app_label]
                
                for model_name, model_data in sorted(app_data['models'].items()):
                    f.write(f"### {app_label}.{model_name}\n\n")
                    f.write(f"**Database Table**: `{model_data['db_table']}`\n\n")
                    
                    # Fields table
                    f.write("#### Fields\n\n")
                    f.write("| Field | Type | Null | Index | Description |\n")
                    f.write("|-------|------|------|-------|-------------|\n")
                    
                    for field_name, field_info in sorted(model_data['fields'].items()):
                        field_type = field_info['type']
                        if 'max_length' in field_info:
                            field_type += f"({field_info['max_length']})"
                        
                        null = "Yes" if field_info['null'] else "No"
                        index = "Yes" if field_info['db_index'] or field_info['primary_key'] else "No"
                        desc = field_info['verbose_name']
                        
                        f.write(f"| {field_name} | {field_type} | {null} | {index} | {desc} |\n")
                    
                    # Relationships
                    if any(model_data['relationships'].values()):
                        f.write("\n#### Relationships\n\n")
                        
                        if model_data['relationships']['foreign_keys']:
                            f.write("**Foreign Keys**:\n")
                            for fk in model_data['relationships']['foreign_keys']:
                                f.write(f"- `{fk['field']}` -> {fk['to']} (ON DELETE {fk['on_delete']})\n")
                        
                        if model_data['relationships']['many_to_many']:
                            f.write("\n**Many to Many**:\n")
                            for m2m in model_data['relationships']['many_to_many']:
                                f.write(f"- `{m2m['field']}` <-> {m2m['to']}\n")
                    
                    # Indexes
                    if model_data['indexes']:
                        f.write("\n#### Indexes\n\n")
                        for idx in model_data['indexes']:
                            f.write(f"- {idx['name']}: {', '.join(idx['fields'])}\n")
                    
                    f.write("\n---\n\n")
        
        print(f"\nModel documentation generated: {doc_path}")
    
    def run_inspection(self):
        """Run complete model inspection"""
        self.print_header("DJANGO MODEL INSPECTION", 1)
        
        print(f"Inspecting models in apps: {', '.join(self.target_apps)}\n")
        
        # Inspect each app
        for app_label in self.target_apps:
            try:
                app_config = apps.get_app_config(app_label)
                print(f"Inspecting {Fore.CYAN}{app_label}{Style.RESET_ALL}...", end='')
                
                app_info = self.inspect_app(app_config)
                self.report['apps'][app_label] = app_info
                self.report['summary']['total_apps'] += 1
                
                print(f" {Fore.GREEN}✓{Style.RESET_ALL} ({len(app_info['models'])} models)")
                
            except LookupError:
                print(f" {Fore.RED}✗ App not found{Style.RESET_ALL}")
        
        # Generate relationship diagram
        self.generate_relationship_diagram()
        
        # Check model usage
        self.check_model_usage_in_queries()
        
        # Generate summary
        self.print_header("INSPECTION SUMMARY", 1)
        
        print(f"Total Apps Inspected: {self.report['summary']['total_apps']}")
        print(f"Total Models Found: {self.report['summary']['total_models']}")
        print(f"Total Fields: {self.report['summary']['total_fields']}")
        print(f"Total Relationships: {self.report['summary']['total_relationships']}")
        
        # Save detailed report
        report_path = project_root / 'tests' / 'model_inspection_report.json'
        with open(report_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        # Generate documentation
        self.generate_model_documentation()
        
        return True


def print_model_summary():
    """Print a quick summary of key models"""
    print(f"\n{Fore.CYAN}Key Models Summary:{Style.RESET_ALL}\n")
    
    key_models = [
        ('onboarding.Bt', 'Business units and site hierarchy'),
        ('peoples.People', 'User management and authentication'),
        ('core.Capability', 'Permission and capability tree'),
        ('y_helpdesk.Ticket', 'Helpdesk ticket management'),
        ('activity.Task', 'Task scheduling and management'),
        ('attendance.Attendance', 'Employee attendance tracking')
    ]
    
    for model_path, description in key_models:
        try:
            app_label, model_name = model_path.split('.')
            model = apps.get_model(app_label, model_name)
            count = model.objects.count()
            print(f"{model_path}: {description}")
            print(f"  - Records: {count}")
            print(f"  - Table: {model._meta.db_table}")
            print()
        except Exception as e:
            print(f"{model_path}: {Fore.RED}Error - {str(e)}{Style.RESET_ALL}\n")


def main():
    """Main entry point"""
    inspector = ModelInspector()
    
    # Run inspection
    success = inspector.run_inspection()
    
    # Print summary
    print_model_summary()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())