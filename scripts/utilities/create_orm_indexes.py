#!/usr/bin/env python
"""
Create database indexes to optimize Django ORM performance.
This script generates a Django migration to add indexes for frequently queried fields.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from django.core.management import call_command
from django.db import connection

def check_existing_indexes():
    """Check which indexes already exist"""
    with connection.cursor() as cursor:
        # Get indexes for jobneed table
        cursor.execute("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'jobneed' 
            AND schemaname = 'public'
            ORDER BY indexname;
        """)
        
        print("Existing indexes on jobneed table:")
        print("-" * 80)
        for row in cursor.fetchall():
            print(f"{row[0]}: {row[1]}")
        print("-" * 80)
        
def create_index_migration():
    """Create migration file for performance indexes"""
    
    migration_content = '''# Generated migration for ORM performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', 'XXXX_previous_migration'),  # Update this with actual previous migration
    ]

    operations = [
        # Composite index for job queries
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['bu_id', 'client_id', 'people_id'],
                name='jobneed_bu_client_people_idx',
            ),
        ),
        
        # Date range queries
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['plandatetime', 'expirydatetime'],
                name='jobneed_date_range_idx',
            ),
        ),
        
        # Identifier and status queries
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['identifier', 'jobstatus'],
                name='jobneed_ident_status_idx',
            ),
        ),
        
        # Group assignment queries
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['pgroup_id'],
                name='jobneed_pgroup_idx',
            ),
        ),
        
        # Asset queries
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(
                fields=['bu_id', 'enable', 'mdtz'],
                name='asset_bu_enable_mdtz_idx',
            ),
        ),
        
        # Asset identifier
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(
                fields=['identifier'],
                name='asset_identifier_idx',
            ),
        ),
        
        # Business unit hierarchy
        migrations.AddIndex(
            model_name='bt',
            index=models.Index(
                fields=['parent_id', 'enable'],
                name='bt_parent_enable_idx',
            ),
        ),
        
        # Capability hierarchy
        migrations.AddIndex(
            model_name='capability',
            index=models.Index(
                fields=['parent_id', 'cfor', 'enable'],
                name='capability_parent_cfor_idx',
            ),
        ),
        
        # People group belonging
        migrations.AddIndex(
            model_name='pgbelonging',
            index=models.Index(
                fields=['people_id', 'pgroup_id'],
                name='pgbelonging_people_group_idx',
            ),
        ),
    ]
'''
    
    # Save migration file
    migration_dir = 'apps/activity/migrations'
    if not os.path.exists(migration_dir):
        print(f"Error: Migration directory not found: {migration_dir}")
        return
        
    # Find the latest migration number
    import glob
    migrations = glob.glob(os.path.join(migration_dir, '*.py'))
    if migrations:
        latest = max([os.path.basename(m).split('_')[0] for m in migrations if m.endswith('.py') and not m.endswith('__init__.py')])
        try:
            next_number = f"{int(latest):04d}"
        except:
            next_number = "0001"
    else:
        next_number = "0001"
    
    filename = f"{migration_dir}/{next_number}_add_orm_performance_indexes.py"
    
    print(f"\nCreating migration file: {filename}")
    print("\nIMPORTANT: Update the 'dependencies' line with the actual previous migration!")
    print("\nMigration content preview:")
    print("=" * 80)
    print(migration_content)
    print("=" * 80)
    
    response = input("\nCreate this migration file? (y/n): ")
    if response.lower() == 'y':
        with open(filename, 'w') as f:
            f.write(migration_content)
        print(f"\nMigration created: {filename}")
        print("\nNext steps:")
        print("1. Update the dependencies line in the migration")
        print("2. Run: python manage.py migrate")
    else:
        print("\nMigration not created.")

def analyze_query_patterns():
    """Analyze current query patterns for optimization opportunities"""
    print("\n\nQuery Pattern Analysis")
    print("=" * 80)
    
    queries = [
        {
            'name': 'Job needs by person',
            'sql': '''
                SELECT COUNT(*) FROM jobneed 
                WHERE bu_id = 1 AND client_id = 1 
                AND (people_id = 1 OR cuser_id = 1 OR muser_id = 1)
            '''
        },
        {
            'name': 'Jobs by date range',
            'sql': '''
                SELECT COUNT(*) FROM jobneed 
                WHERE plandatetime >= CURRENT_DATE - INTERVAL '30 days'
                AND expirydatetime <= CURRENT_DATE + INTERVAL '30 days'
            '''
        },
        {
            'name': 'External tour jobs',
            'sql': '''
                SELECT COUNT(*) FROM jobneed 
                WHERE identifier = 'EXTERNALTOUR' AND client_id = 1
            '''
        },
    ]
    
    with connection.cursor() as cursor:
        for query in queries:
            try:
                # Explain analyze
                cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS) {query['sql']}")
                print(f"\n{query['name']}:")
                print("-" * 40)
                for row in cursor.fetchall():
                    print(row[0])
            except Exception as e:
                print(f"\nError analyzing {query['name']}: {e}")

def main():
    """Main function"""
    print("Django ORM Performance Index Creator")
    print("=" * 80)
    
    # Check existing indexes
    check_existing_indexes()
    
    # Analyze query patterns
    analyze_query_patterns()
    
    # Create migration
    print("\n\nCreate Performance Indexes")
    print("=" * 80)
    print("This will create a Django migration to add performance indexes.")
    print("Indexes will improve query performance for:")
    print("- Job queries by person, BU, and client")
    print("- Date range filtering")
    print("- Identifier and status filtering")
    print("- Hierarchical queries (BT, Capability)")
    
    response = input("\nProceed with migration creation? (y/n): ")
    if response.lower() == 'y':
        create_index_migration()
    else:
        print("\nOperation cancelled.")

if __name__ == "__main__":
    main()
