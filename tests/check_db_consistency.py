#!/usr/bin/env python
"""
Database consistency checker for Django ORM migration.
Validates referential integrity and data consistency.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import json
from typing import Dict, List, Tuple, Any
from collections import defaultdict

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

from django.db import connection, models
from django.apps import apps
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


class ConsistencyChecker:
    """Check database consistency and referential integrity"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'checks': [],
            'issues': [],
            'warnings': [],
            'summary': {
                'total_checks': 0,
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }
        
        # Critical relationships to check
        self.critical_relations = [
            # (model, field, related_model, description)
            ('peoples.People', 'client', 'onboarding.Bt', 'People must belong to valid client'),
            ('peoples.People', 'bu', 'onboarding.Bt', 'People must belong to valid BU'),
            ('y_helpdesk.Ticket', 'site', 'onboarding.Bt', 'Ticket must belong to valid site'),
            ('y_helpdesk.Ticket', 'createdby', 'peoples.People', 'Ticket must have valid creator'),
            ('activity.Task', 'site', 'onboarding.Bt', 'Task must belong to valid site'),
            ('activity.Asset', 'site', 'onboarding.Bt', 'Asset must belong to valid site'),
            ('attendance.Attendance', 'people', 'peoples.People', 'Attendance must have valid person'),
            ('attendance.Attendance', 'site', 'onboarding.Bt', 'Attendance must have valid site'),
            ('onboarding.Bt', 'parent', 'onboarding.Bt', 'BU parent must be valid (self-reference)'),
            ('core.Capability', 'parent', 'core.Capability', 'Capability parent must be valid (self-reference)')
        ]
        
        # Data consistency rules
        self.consistency_rules = [
            ('check_orphaned_records', 'Check for orphaned records'),
            ('check_date_consistency', 'Check date field consistency'),
            ('check_status_consistency', 'Check status field consistency'),
            ('check_hierarchy_loops', 'Check for circular references in hierarchies'),
            ('check_required_data', 'Check required fields have data')
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
    
    def check_referential_integrity(self):
        """Check foreign key referential integrity"""
        self.print_header("Checking Referential Integrity", 2)
        
        for model_path, field_name, related_model_path, description in self.critical_relations:
            check_result = {
                'type': 'referential_integrity',
                'model': model_path,
                'field': field_name,
                'related_model': related_model_path,
                'description': description,
                'status': 'unknown',
                'details': {}
            }
            
            try:
                # Get models
                app_label, model_name = model_path.split('.')
                model = apps.get_model(app_label, model_name)
                
                related_app_label, related_model_name = related_model_path.split('.')
                related_model = apps.get_model(related_app_label, related_model_name)
                
                # Check for invalid references
                if field_name == 'parent' and model_path == related_model_path:
                    # Self-referential check
                    invalid_refs = model.objects.exclude(
                        models.Q(parent_id__isnull=True) | 
                        models.Q(parent_id__in=model.objects.values_list('id', flat=True))
                    ).count()
                else:
                    # Normal foreign key check
                    field = model._meta.get_field(field_name)
                    if field.null:
                        # Nullable field
                        invalid_refs = model.objects.exclude(
                            models.Q(**{f"{field_name}_id__isnull": True}) |
                            models.Q(**{f"{field_name}_id__in": related_model.objects.values_list('id', flat=True)})
                        ).count()
                    else:
                        # Non-nullable field
                        invalid_refs = model.objects.exclude(
                            **{f"{field_name}_id__in": related_model.objects.values_list('id', flat=True)}
                        ).count()
                
                total_records = model.objects.count()
                check_result['details'] = {
                    'total_records': total_records,
                    'invalid_references': invalid_refs
                }
                
                if invalid_refs == 0:
                    check_result['status'] = 'passed'
                    print(f"{Fore.GREEN}✓ {description}: All {total_records} records valid{Style.RESET_ALL}")
                    self.results['summary']['passed'] += 1
                else:
                    check_result['status'] = 'failed'
                    print(f"{Fore.RED}✗ {description}: {invalid_refs} invalid references out of {total_records}{Style.RESET_ALL}")
                    self.results['summary']['failed'] += 1
                    self.results['issues'].append({
                        'type': 'invalid_reference',
                        'model': model_path,
                        'field': field_name,
                        'count': invalid_refs
                    })
                
            except Exception as e:
                check_result['status'] = 'error'
                check_result['error'] = str(e)
                print(f"{Fore.YELLOW}⚠ {description}: Error - {str(e)}{Style.RESET_ALL}")
                self.results['summary']['warnings'] += 1
            
            self.results['checks'].append(check_result)
            self.results['summary']['total_checks'] += 1
    
    def check_orphaned_records(self):
        """Check for orphaned records in the database"""
        print("\nChecking for orphaned records...")
        
        orphan_checks = [
            # Check tickets without valid sites
            ("SELECT COUNT(*) FROM y_helpdesk_ticket t "
             "LEFT JOIN onboarding_bt b ON t.site_id = b.id "
             "WHERE t.site_id IS NOT NULL AND b.id IS NULL", 
             "Tickets with invalid sites"),
            
            # Check tasks without valid sites
            ("SELECT COUNT(*) FROM activity_task t "
             "LEFT JOIN onboarding_bt b ON t.site_id = b.id "
             "WHERE t.site_id IS NOT NULL AND b.id IS NULL",
             "Tasks with invalid sites"),
            
            # Check people without valid clients
            ("SELECT COUNT(*) FROM peoples_people p "
             "LEFT JOIN onboarding_bt b ON p.client_id = b.id "
             "WHERE p.client_id IS NOT NULL AND b.id IS NULL",
             "People with invalid clients")
        ]
        
        with connection.cursor() as cursor:
            for query, description in orphan_checks:
                try:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    
                    if count == 0:
                        print(f"{Fore.GREEN}✓ {description}: No orphaned records{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ {description}: {count} orphaned records found{Style.RESET_ALL}")
                        self.results['issues'].append({
                            'type': 'orphaned_records',
                            'description': description,
                            'count': count
                        })
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠ {description}: Error - {str(e)}{Style.RESET_ALL}")
    
    def check_date_consistency(self):
        """Check date field consistency"""
        print("\nChecking date consistency...")
        
        date_checks = [
            # Check tickets where resolved date is before created date
            ("SELECT COUNT(*) FROM y_helpdesk_ticket "
             "WHERE resolvedon IS NOT NULL AND resolvedon < createdon",
             "Tickets resolved before creation"),
            
            # Check attendance where checkout is before checkin
            ("SELECT COUNT(*) FROM attendance_attendance "
             "WHERE checkout_time IS NOT NULL AND checkout_time < checkin_time",
             "Attendance checkout before checkin"),
            
            # Check tasks where completed date is before scheduled date
            ("SELECT COUNT(*) FROM activity_taskschedule "
             "WHERE completedon IS NOT NULL AND completedon < scheduledon",
             "Tasks completed before scheduled")
        ]
        
        with connection.cursor() as cursor:
            for query, description in date_checks:
                try:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    
                    if count == 0:
                        print(f"{Fore.GREEN}✓ {description}: No inconsistencies{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.YELLOW}⚠ {description}: {count} records with date issues{Style.RESET_ALL}")
                        self.results['warnings'].append({
                            'type': 'date_inconsistency',
                            'description': description,
                            'count': count
                        })
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠ {description}: Error - {str(e)}{Style.RESET_ALL}")
    
    def check_hierarchy_loops(self):
        """Check for circular references in hierarchical data"""
        print("\nChecking for hierarchy loops...")
        
        # Check BT hierarchy
        try:
            with connection.cursor() as cursor:
                # Simple check for self-referencing records
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM onboarding_bt 
                    WHERE id = parent_id AND parent_id IS NOT NULL
                """)
                self_refs = cursor.fetchone()[0]
                
                if self_refs == 0:
                    print(f"{Fore.GREEN}✓ BT hierarchy: No self-referencing records{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}✗ BT hierarchy: {self_refs} self-referencing records{Style.RESET_ALL}")
                    self.results['issues'].append({
                        'type': 'hierarchy_loop',
                        'model': 'onboarding.Bt',
                        'count': self_refs
                    })
                
                # Check capability hierarchy
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM core_capability 
                    WHERE id = parent_id AND parent_id IS NOT NULL
                """)
                cap_self_refs = cursor.fetchone()[0]
                
                if cap_self_refs == 0:
                    print(f"{Fore.GREEN}✓ Capability hierarchy: No self-referencing records{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}✗ Capability hierarchy: {cap_self_refs} self-referencing records{Style.RESET_ALL}")
                    self.results['issues'].append({
                        'type': 'hierarchy_loop',
                        'model': 'core.Capability',
                        'count': cap_self_refs
                    })
                    
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ Hierarchy check error: {str(e)}{Style.RESET_ALL}")
    
    def check_required_data(self):
        """Check that required fields have valid data"""
        print("\nChecking required field data...")
        
        required_checks = [
            # Check for empty required string fields
            ("SELECT COUNT(*) FROM peoples_people WHERE loginid = '' OR loginid IS NULL",
             "People with empty loginid"),
            
            ("SELECT COUNT(*) FROM onboarding_bt WHERE bucode = '' OR bucode IS NULL",
             "BUs with empty bucode"),
            
            ("SELECT COUNT(*) FROM y_helpdesk_ticket WHERE ticketcode = '' OR ticketcode IS NULL",
             "Tickets with empty ticketcode"),
            
            # Check for invalid status values
            ("SELECT COUNT(*) FROM y_helpdesk_ticket WHERE status_id NOT IN "
             "(SELECT id FROM y_helpdesk_ticketstatustype WHERE enable = true)",
             "Tickets with invalid status")
        ]
        
        with connection.cursor() as cursor:
            for query, description in required_checks:
                try:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    
                    if count == 0:
                        print(f"{Fore.GREEN}✓ {description}: All data valid{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ {description}: {count} invalid records{Style.RESET_ALL}")
                        self.results['issues'].append({
                            'type': 'invalid_required_data',
                            'description': description,
                            'count': count
                        })
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠ {description}: Error - {str(e)}{Style.RESET_ALL}")
    
    def check_data_statistics(self):
        """Generate data statistics for key tables"""
        self.print_header("Data Statistics", 2)
        
        stats_queries = [
            ("SELECT COUNT(*) FROM onboarding_bt WHERE identifier_id = "
             "(SELECT id FROM onboarding_typeassist WHERE tacode = 'CLIENT' LIMIT 1)",
             "Total Clients"),
            
            ("SELECT COUNT(*) FROM onboarding_bt WHERE identifier_id = "
             "(SELECT id FROM onboarding_typeassist WHERE tacode = 'SITE' LIMIT 1)",
             "Total Sites"),
            
            ("SELECT COUNT(*) FROM peoples_people WHERE enable = true",
             "Active Users"),
            
            ("SELECT COUNT(*) FROM y_helpdesk_ticket WHERE status_id IN "
             "(SELECT id FROM y_helpdesk_ticketstatustype WHERE tacode IN ('OPEN', 'NEW'))",
             "Open Tickets"),
            
            ("SELECT COUNT(*) FROM activity_task WHERE enable = true",
             "Active Tasks"),
            
            ("SELECT COUNT(*) FROM core_capability",
             "Total Capabilities")
        ]
        
        stats = {}
        with connection.cursor() as cursor:
            for query, label in stats_queries:
                try:
                    cursor.execute(query)
                    count = cursor.fetchone()[0]
                    stats[label] = count
                    print(f"{label}: {Fore.CYAN}{count}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{label}: {Fore.YELLOW}Error - {str(e)}{Style.RESET_ALL}")
        
        return stats
    
    def generate_fix_scripts(self):
        """Generate SQL scripts to fix found issues"""
        if not self.results['issues']:
            return
        
        self.print_header("Fix Suggestions", 2)
        
        scripts = []
        
        for issue in self.results['issues']:
            if issue['type'] == 'invalid_reference':
                # Generate script to nullify invalid references
                scripts.append(f"""
-- Fix invalid references in {issue['model']}.{issue['field']}
-- First, identify invalid records:
SELECT id, {issue['field']}_id 
FROM {issue['model'].replace('.', '_').lower()}
WHERE {issue['field']}_id NOT IN (
    SELECT id FROM {issue['field']}_table
);

-- To fix (uncomment to run):
-- UPDATE {issue['model'].replace('.', '_').lower()}
-- SET {issue['field']}_id = NULL
-- WHERE {issue['field']}_id NOT IN (
--     SELECT id FROM {issue['field']}_table
-- );
""")
            
            elif issue['type'] == 'hierarchy_loop':
                scripts.append(f"""
-- Fix self-referencing records in {issue['model']}
-- First, identify self-referencing records:
SELECT id, parent_id 
FROM {issue['model'].replace('.', '_').lower()}
WHERE id = parent_id;

-- To fix (uncomment to run):
-- UPDATE {issue['model'].replace('.', '_').lower()}
-- SET parent_id = NULL
-- WHERE id = parent_id;
""")
        
        # Save scripts
        if scripts:
            script_path = project_root / 'tests' / 'consistency_fixes.sql'
            with open(script_path, 'w') as f:
                f.write("-- Database Consistency Fix Scripts\n")
                f.write(f"-- Generated: {datetime.now()}\n")
                f.write("-- Review carefully before running!\n\n")
                
                for script in scripts:
                    f.write(script)
                    f.write("\n" + "-" * 60 + "\n")
            
            print(f"Fix scripts saved to: {script_path}")
    
    def run_checks(self):
        """Run all consistency checks"""
        self.print_header("DATABASE CONSISTENCY CHECK", 1)
        
        print(f"Database: {connection.settings_dict['NAME']}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Run checks
        self.check_referential_integrity()
        
        self.print_header("Data Consistency Checks", 2)
        self.check_orphaned_records()
        self.check_date_consistency()
        self.check_hierarchy_loops()
        self.check_required_data()
        
        # Generate statistics
        stats = self.check_data_statistics()
        
        # Generate report
        self.generate_report()
        
        # Generate fix scripts if issues found
        if self.results['issues']:
            self.generate_fix_scripts()
        
        return len(self.results['issues']) == 0
    
    def generate_report(self):
        """Generate consistency check report"""
        self.print_header("CONSISTENCY CHECK SUMMARY", 1)
        
        print(f"Total Checks: {self.results['summary']['total_checks']}")
        print(f"Passed: {Fore.GREEN}{self.results['summary']['passed']}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{self.results['summary']['failed']}{Style.RESET_ALL}")
        print(f"Warnings: {Fore.YELLOW}{self.results['summary']['warnings']}{Style.RESET_ALL}")
        
        if self.results['issues']:
            print(f"\n{Fore.RED}Critical Issues Found:{Style.RESET_ALL}")
            for issue in self.results['issues'][:10]:  # Show first 10
                print(f"  - {issue}")
        
        if self.results['warnings']:
            print(f"\n{Fore.YELLOW}Warnings:{Style.RESET_ALL}")
            for warning in self.results['warnings'][:5]:  # Show first 5
                print(f"  - {warning}")
        
        # Save detailed report
        report_path = project_root / 'tests' / 'consistency_check_report.json'
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nDetailed report saved to: {report_path}")
        
        if len(self.results['issues']) == 0:
            print(f"\n{Fore.GREEN}✓ Database consistency check passed!{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED}✗ Found {len(self.results['issues'])} consistency issues{Style.RESET_ALL}")


def main():
    """Main entry point"""
    checker = ConsistencyChecker()
    success = checker.run_checks()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())