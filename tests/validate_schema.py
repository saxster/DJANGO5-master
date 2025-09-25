#!/usr/bin/env python
"""
Database schema validation for Django ORM migration.
Ensures all models, fields, and relationships are properly configured.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Set, Tuple, Any

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.db import connection
from django.apps import apps
from django.db.models import Model, Field, ForeignKey, ManyToManyField
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


class SchemaValidator:
    """Validate database schema against Django models"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'models_validated': 0,
            'fields_validated': 0,
            'issues': [],
            'warnings': [],
            'model_details': {}
        }
        
        # Models used in our ORM queries
        self.critical_models = [
            'onboarding.Bt',
            'onboarding.TypeAssist',
            'onboarding.Geofence',
            'onboarding.Shift',
            'peoples.People',
            'peoples.Pgroup',
            'peoples.Pgbelonging',
            'core.Capability',
            'activity.Asset',
            'activity.Task',
            'activity.Taskschedule',
            'activity.Activity',
            'attendance.Attendance',
            'attendance.Employeeattendance',
            'y_helpdesk.Ticket',
            'y_helpdesk.TicketStatusType',
            'y_helpdesk.TicketCategory',
            'reports.ScheduleReport'
        ]
        
        # Required fields for each model (used in queries)
        self.required_fields = {
            'Capability': ['id', 'capsname', 'capscode', 'parent_id', 'cfor'],
            'Bt': ['id', 'bucode', 'buname', 'parent_id', 'identifier_id', 'enable'],
            'People': ['id', 'peoplecode', 'peoplename', 'loginid', 'email', 'isadmin', 'client_id', 'bu_id'],
            'Ticket': ['id', 'ticketcode', 'description', 'status_id', 'category_id', 'site_id', 'priority'],
            'Task': ['id', 'taskcode', 'taskname', 'site_id', 'enable'],
            'Asset': ['id', 'assetcode', 'assetname', 'assettype_id', 'site_id', 'status'],
            'TypeAssist': ['id', 'tacode', 'taname', 'tatype_id', 'enable'],
            'Activity': ['id', 'activitycode', 'activityname', 'activitytype_id', 'site_id'],
            'Attendance': ['id', 'people_id', 'site_id', 'date', 'status'],
            'ScheduleReport': ['id', 'report_type', 'client_id', 'enable', 'crontype']
        }
        
        # Database indexes needed for performance
        self.required_indexes = {
            'Capability': [('parent_id',), ('cfor',), ('capscode',)],
            'Bt': [('parent_id',), ('identifier_id',), ('bucode',), ('enable',)],
            'People': [('loginid',), ('email',), ('client_id', 'bu_id'), ('isadmin',)],
            'Ticket': [('status_id',), ('category_id',), ('site_id',), ('priority',), ('escalation_time',)],
            'Task': [('site_id',), ('enable',), ('taskcode',)],
            'Asset': [('assettype_id',), ('site_id',), ('status',)],
            'Activity': [('activitytype_id',), ('site_id',), ('scheduled_date',)],
            'Attendance': [('people_id', 'date'), ('site_id',), ('status',)]
        }
    
    def print_header(self, text, level=1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Fore.BLUE}{'=' * 80}")
            print(f"{Fore.BLUE}{text.center(80)}")
            print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.CYAN}{text}")
            print(f"{Fore.CYAN}{'-' * len(text)}{Style.RESET_ALL}")
    
    def validate_model_exists(self, app_label: str, model_name: str) -> Tuple[bool, Model]:
        """Check if model exists in Django"""
        try:
            model = apps.get_model(app_label, model_name)
            return True, model
        except LookupError:
            self.results['issues'].append({
                'type': 'missing_model',
                'model': f"{app_label}.{model_name}",
                'severity': 'critical'
            })
            return False, None
    
    def validate_model_fields(self, model: Model) -> Dict[str, Any]:
        """Validate model fields"""
        model_name = model.__name__
        field_info = {
            'model': model_name,
            'fields': {},
            'missing_required': [],
            'field_types': {}
        }
        
        # Get all fields
        fields = model._meta.get_fields()
        field_names = {f.name for f in fields}
        
        # Check required fields
        if model_name in self.required_fields:
            for req_field in self.required_fields[model_name]:
                if req_field not in field_names:
                    field_info['missing_required'].append(req_field)
                    self.results['issues'].append({
                        'type': 'missing_field',
                        'model': model_name,
                        'field': req_field,
                        'severity': 'high'
                    })
        
        # Document field types
        for field in fields:
            field_info['fields'][field.name] = {
                'type': field.__class__.__name__,
                'null': getattr(field, 'null', None),
                'blank': getattr(field, 'blank', None),
                'db_index': getattr(field, 'db_index', False)
            }
            
            # Check foreign keys
            if isinstance(field, ForeignKey):
                field_info['fields'][field.name]['related_model'] = field.related_model.__name__
                field_info['fields'][field.name]['on_delete'] = str(field.remote_field.on_delete)
        
        self.results['fields_validated'] += len(fields)
        return field_info
    
    def validate_database_tables(self) -> Dict[str, List[str]]:
        """Check actual database tables"""
        tables_info = {}
        
        with connection.cursor() as cursor:
            # Get all tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            
            db_tables = {row[0] for row in cursor.fetchall()}
            
            # Check each model's table
            for model_path in self.critical_models:
                app_label, model_name = model_path.split('.')
                exists, model = self.validate_model_exists(app_label, model_name)
                
                if exists:
                    table_name = model._meta.db_table
                    if table_name not in db_tables:
                        self.results['issues'].append({
                            'type': 'missing_table',
                            'model': model_name,
                            'table': table_name,
                            'severity': 'critical'
                        })
                    else:
                        # Get table columns
                        cursor.execute("""
                            SELECT column_name, data_type, is_nullable
                            FROM information_schema.columns
                            WHERE table_name = %s
                            ORDER BY ordinal_position
                        """, [table_name])
                        
                        columns = cursor.fetchall()
                        tables_info[table_name] = [
                            {'name': col[0], 'type': col[1], 'nullable': col[2]}
                            for col in columns
                        ]
        
        return tables_info
    
    def validate_indexes(self) -> Dict[str, List[str]]:
        """Validate database indexes"""
        index_info = {}
        
        with connection.cursor() as cursor:
            for model_path in self.critical_models:
                app_label, model_name = model_path.split('.')
                exists, model = self.validate_model_exists(app_label, model_name)
                
                if exists:
                    table_name = model._meta.db_table
                    
                    # Get indexes for this table
                    cursor.execute("""
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE tablename = %s
                    """, [table_name])
                    
                    indexes = cursor.fetchall()
                    index_info[table_name] = [idx[0] for idx in indexes]
                    
                    # Check required indexes
                    if model_name in self.required_indexes:
                        for required_idx in self.required_indexes[model_name]:
                            # This is a simplified check - in practice you'd parse indexdef
                            idx_found = any(
                                all(field in idx[1] for field in required_idx)
                                for idx in indexes
                            )
                            
                            if not idx_found:
                                self.results['warnings'].append({
                                    'type': 'missing_index',
                                    'model': model_name,
                                    'fields': required_idx,
                                    'severity': 'performance'
                                })
        
        return index_info
    
    def validate_relationships(self):
        """Validate model relationships used in queries"""
        self.print_header("Validating Model Relationships", 2)
        
        relationship_issues = []
        
        # Critical relationships used in our queries
        critical_relationships = [
            ('Bt', 'parent', 'Bt'),
            ('Bt', 'identifier', 'TypeAssist'),
            ('Capability', 'parent', 'Capability'),
            ('People', 'client', 'Bt'),
            ('People', 'bu', 'Bt'),
            ('Ticket', 'status', 'TicketStatusType'),
            ('Ticket', 'category', 'TicketCategory'),
            ('Ticket', 'site', 'Bt'),
            ('Task', 'site', 'Bt'),
            ('Asset', 'assettype', 'TypeAssist'),
            ('Asset', 'site', 'Bt'),
            ('Activity', 'activitytype', 'TypeAssist'),
            ('Activity', 'site', 'Bt'),
            ('Attendance', 'people', 'People'),
            ('Attendance', 'site', 'Bt')
        ]
        
        for model_name, field_name, related_model_name in critical_relationships:
            # Find the model
            model = None
            for app in apps.get_app_configs():
                try:
                    model = apps.get_model(app.label, model_name)
                    break
                except LookupError:
                    continue
            
            if not model:
                relationship_issues.append({
                    'issue': f"Model {model_name} not found",
                    'severity': 'critical'
                })
                continue
            
            # Check field exists
            try:
                field = model._meta.get_field(field_name)
                if isinstance(field, ForeignKey):
                    actual_related = field.related_model.__name__
                    if actual_related != related_model_name:
                        relationship_issues.append({
                            'issue': f"{model_name}.{field_name} points to {actual_related}, expected {related_model_name}",
                            'severity': 'high'
                        })
                    else:
                        print(f"{Fore.GREEN}✓ {model_name}.{field_name} -> {related_model_name}{Style.RESET_ALL}")
                else:
                    relationship_issues.append({
                        'issue': f"{model_name}.{field_name} is not a ForeignKey",
                        'severity': 'high'
                    })
            except Exception as e:
                relationship_issues.append({
                    'issue': f"{model_name}.{field_name} not found: {str(e)}",
                    'severity': 'critical'
                })
        
        return relationship_issues
    
    def check_query_compatibility(self):
        """Check if models support our ORM queries"""
        self.print_header("Checking Query Compatibility", 2)
        
        compatibility_issues = []
        
        # Check TreeTraversal compatibility
        tree_models = ['Capability', 'Bt']
        for model_name in tree_models:
            model = None
            for app in apps.get_app_configs():
                try:
                    model = apps.get_model(app.label, model_name)
                    break
                except LookupError:
                    continue
            
            if model:
                # Check for required fields for tree traversal
                required = ['id', 'parent_id'] if model_name == 'Capability' else ['id', 'parent_id']
                fields = {f.name for f in model._meta.get_fields()}
                
                for req_field in required:
                    if req_field not in fields and req_field.replace('_id', '') not in fields:
                        compatibility_issues.append({
                            'model': model_name,
                            'issue': f"Missing {req_field} for tree traversal",
                            'severity': 'critical'
                        })
                
                print(f"{Fore.GREEN}✓ {model_name} supports tree traversal{Style.RESET_ALL}")
        
        # Check aggregation compatibility
        aggregation_models = {
            'Task': ['site_id', 'enable'],
            'Activity': ['scheduled_date', 'completed_date', 'status'],
            'Attendance': ['date', 'checkin_time', 'checkout_time', 'status']
        }
        
        for model_name, required_fields in aggregation_models.items():
            model = None
            for app in apps.get_app_configs():
                try:
                    model = apps.get_model(app.label, model_name)
                    break
                except LookupError:
                    continue
            
            if model:
                fields = {f.name for f in model._meta.get_fields()}
                missing = [f for f in required_fields if f not in fields and f.replace('_id', '') not in fields]
                
                if missing:
                    compatibility_issues.append({
                        'model': model_name,
                        'issue': f"Missing fields for aggregation: {missing}",
                        'severity': 'high'
                    })
                else:
                    print(f"{Fore.GREEN}✓ {model_name} supports aggregation queries{Style.RESET_ALL}")
        
        return compatibility_issues
    
    def generate_migration_suggestions(self):
        """Generate Django migration suggestions for issues found"""
        if not self.results['issues']:
            return []
        
        suggestions = []
        
        # Group issues by model
        model_issues = {}
        for issue in self.results['issues']:
            if 'model' in issue:
                model_name = issue['model']
                if model_name not in model_issues:
                    model_issues[model_name] = []
                model_issues[model_name].append(issue)
        
        # Generate suggestions
        for model_name, issues in model_issues.items():
            migration_code = f"# Migration for {model_name}\n"
            migration_code += "from django.db import migrations, models\n\n"
            migration_code += "class Migration(migrations.Migration):\n"
            migration_code += "    operations = [\n"
            
            for issue in issues:
                if issue['type'] == 'missing_field':
                    migration_code += f"        migrations.AddField(\n"
                    migration_code += f"            model_name='{model_name.lower()}',\n"
                    migration_code += f"            name='{issue['field']}',\n"
                    migration_code += f"            field=models.CharField(max_length=255, null=True),\n"
                    migration_code += f"        ),\n"
            
            migration_code += "    ]\n"
            
            suggestions.append({
                'model': model_name,
                'migration_code': migration_code
            })
        
        return suggestions
    
    def run_validation(self):
        """Run complete schema validation"""
        self.print_header("DATABASE SCHEMA VALIDATION", 1)
        
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"Engine: {connection.settings_dict['ENGINE']}")
        print(f"Django Version: {django.VERSION}\n")
        
        # 1. Validate models exist
        self.print_header("Validating Critical Models", 2)
        for model_path in self.critical_models:
            app_label, model_name = model_path.split('.')
            exists, model = self.validate_model_exists(app_label, model_name)
            
            if exists:
                print(f"{Fore.GREEN}✓ {model_path}{Style.RESET_ALL}")
                self.results['models_validated'] += 1
                
                # Validate fields
                field_info = self.validate_model_fields(model)
                self.results['model_details'][model_name] = field_info
                
                if field_info['missing_required']:
                    print(f"  {Fore.YELLOW}⚠ Missing fields: {field_info['missing_required']}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}✗ {model_path} NOT FOUND{Style.RESET_ALL}")
        
        # 2. Validate database tables
        self.print_header("Validating Database Tables", 2)
        tables_info = self.validate_database_tables()
        print(f"Found {len(tables_info)} tables in database")
        
        # 3. Validate indexes
        self.print_header("Validating Indexes", 2)
        index_info = self.validate_indexes()
        
        if self.results['warnings']:
            print(f"{Fore.YELLOW}Found {len(self.results['warnings'])} performance warnings{Style.RESET_ALL}")
            for warning in self.results['warnings'][:5]:  # Show first 5
                if warning['type'] == 'missing_index':
                    print(f"  - {warning['model']} missing index on {warning['fields']}")
        
        # 4. Validate relationships
        relationship_issues = self.validate_relationships()
        if relationship_issues:
            self.results['issues'].extend(relationship_issues)
        
        # 5. Check query compatibility
        compatibility_issues = self.check_query_compatibility()
        if compatibility_issues:
            self.results['issues'].extend(compatibility_issues)
        
        # Generate report
        self.generate_report()
        
        return len(self.results['issues']) == 0
    
    def generate_report(self):
        """Generate validation report"""
        self.print_header("VALIDATION SUMMARY", 1)
        
        print(f"Models Validated: {self.results['models_validated']}")
        print(f"Fields Validated: {self.results['fields_validated']}")
        print(f"Critical Issues: {Fore.RED}{len(self.results['issues'])}{Style.RESET_ALL}")
        print(f"Warnings: {Fore.YELLOW}{len(self.results['warnings'])}{Style.RESET_ALL}")
        
        if self.results['issues']:
            print(f"\n{Fore.RED}Critical Issues:{Style.RESET_ALL}")
            for issue in self.results['issues'][:10]:  # Show first 10
                print(f"  - [{issue.get('severity', 'unknown')}] {issue}")
        
        # Generate migration suggestions
        if self.results['issues']:
            suggestions = self.generate_migration_suggestions()
            if suggestions:
                print(f"\n{Fore.CYAN}Migration Suggestions:{Style.RESET_ALL}")
                print("Create new migrations to fix missing fields:")
                for suggestion in suggestions[:3]:  # Show first 3
                    print(f"\n{suggestion['migration_code']}")
        
        # Save detailed report
        report_path = project_root / 'tests' / 'schema_validation_report.json'
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        if len(self.results['issues']) == 0:
            print(f"\n{Fore.GREEN}✓ Schema validation passed!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}✗ Schema validation found {len(self.results['issues'])} issues{Style.RESET_ALL}")


def main():
    """Main entry point"""
    validator = SchemaValidator()
    success = validator.run_validation()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())