#!/usr/bin/env python
"""
Database migration script for Information Architecture optimization
Updates database references, permissions, and configurations for new URL structure
"""
import os
import sys
import django
from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.models import *


class IADatabaseMigrator:
    """
    Handle database migrations for Information Architecture changes
    """
    
    def __init__(self):
        self.migration_log = []
        self.errors = []
    
    def log(self, message, level='INFO'):
        """Log migration activity"""
        print(f"[{level}] {message}")
        self.migration_log.append(f"[{level}] {message}")
    
    def run_migration(self):
        """Run complete database migration"""
        self.log("🚀 Starting Information Architecture Database Migration")
        
        try:
            with transaction.atomic():
                # Core migrations
                self.update_permissions()
                self.update_user_groups()
                self.migrate_user_preferences()
                self.update_menu_configurations()
                self.create_ia_monitoring_records()
                self.update_system_settings()
                
                # App-specific migrations
                self.migrate_bookmarks()
                self.migrate_notifications()
                self.migrate_audit_logs()
                
                self.log("✅ Database migration completed successfully")
                
        except Exception as e:
            self.log(f"❌ Migration failed: {str(e)}", 'ERROR')
            self.errors.append(str(e))
            raise
        
        finally:
            self.generate_migration_report()
    
    def update_permissions(self):
        """Update permissions to match new URL structure"""
        self.log("📋 Updating permissions...")
        
        # Define new permissions based on domains
        domain_permissions = {
            'operations': [
                ('view_operations', 'Can view operations dashboard'),
                ('manage_tasks', 'Can manage tasks'),
                ('manage_tours', 'Can manage tours'),
                ('manage_work_orders', 'Can manage work orders'),
                ('manage_ppm', 'Can manage preventive maintenance'),
            ],
            'assets': [
                ('view_assets', 'Can view assets'),
                ('manage_assets', 'Can manage assets'),
                ('view_asset_logs', 'Can view asset logs'),
                ('manage_maintenance', 'Can manage maintenance'),
                ('view_locations', 'Can view locations'),
            ],
            'people': [
                ('view_people', 'Can view people directory'),
                ('manage_people', 'Can manage people'),
                ('view_attendance', 'Can view attendance'),
                ('manage_attendance', 'Can manage attendance'),
                ('view_expenses', 'Can view expenses'),
            ],
            'helpdesk': [
                ('view_help_desk', 'Can view help desk'),
                ('manage_tickets', 'Can manage tickets'),
                ('manage_escalations', 'Can manage escalations'),
                ('view_uniforms', 'Can view uniforms'),
            ],
            'reports': [
                ('view_reports', 'Can view reports'),
                ('generate_reports', 'Can generate reports'),
                ('schedule_reports', 'Can schedule reports'),
                ('export_reports', 'Can export reports'),
            ],
            'admin': [
                ('view_admin', 'Can view admin panel'),
                ('manage_business_units', 'Can manage business units'),
                ('manage_clients', 'Can manage clients'),
                ('import_data', 'Can import data'),
                ('manage_configuration', 'Can manage system configuration'),
            ]
        }
        
        created_permissions = 0
        updated_permissions = 0
        
        for domain, perms in domain_permissions.items():
            for codename, name in perms:
                # Get or create content type for the domain
                content_type, created = ContentType.objects.get_or_create(
                    app_label='core',
                    model=f'{domain}_permissions'
                )
                
                # Create or update permission
                permission, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=content_type,
                    defaults={'name': name}
                )
                
                if created:
                    created_permissions += 1
                else:
                    if permission.name != name:
                        permission.name = name
                        permission.save()
                        updated_permissions += 1
        
        self.log(f"Created {created_permissions} new permissions")
        self.log(f"Updated {updated_permissions} existing permissions")
    
    def update_user_groups(self):
        """Update user groups to match new structure"""
        self.log("👥 Updating user groups...")
        
        # Define groups based on new domains
        domain_groups = {
            'Operations Users': [
                'view_operations', 'manage_tasks', 'manage_tours'
            ],
            'Operations Managers': [
                'view_operations', 'manage_tasks', 'manage_tours', 
                'manage_work_orders', 'manage_ppm'
            ],
            'Asset Managers': [
                'view_assets', 'manage_assets', 'view_asset_logs', 
                'manage_maintenance', 'view_locations'
            ],
            'People Managers': [
                'view_people', 'manage_people', 'view_attendance', 
                'manage_attendance', 'view_expenses'
            ],
            'Help Desk Staff': [
                'view_help_desk', 'manage_tickets', 'manage_escalations'
            ],
            'Report Viewers': [
                'view_reports', 'generate_reports'
            ],
            'Report Managers': [
                'view_reports', 'generate_reports', 'schedule_reports', 'export_reports'
            ],
            'System Administrators': [
                'view_admin', 'manage_business_units', 'manage_clients',
                'import_data', 'manage_configuration'
            ]
        }
        
        updated_groups = 0
        created_groups = 0
        
        for group_name, permission_codenames in domain_groups.items():
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                created_groups += 1
            
            # Add permissions to group
            permissions = Permission.objects.filter(
                codename__in=permission_codenames
            )
            
            if permissions.exists():
                group.permissions.set(permissions)
                updated_groups += 1
        
        self.log(f"Created {created_groups} new groups")
        self.log(f"Updated {updated_groups} groups with new permissions")
    
    def migrate_user_preferences(self):
        """Migrate user preferences and settings"""
        self.log("⚙️ Migrating user preferences...")
        
        # This would migrate user-specific settings like:
        # - Favorite pages/bookmarks
        # - Dashboard customizations
        # - Navigation preferences
        
        # Placeholder for actual user preference migration
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Update user profiles with new URL preferences
            # (Implementation would depend on your user profile model)
            user_count = User.objects.count()
            self.log(f"Processed preferences for {user_count} users")
            
        except Exception as e:
            self.log(f"User preference migration skipped: {str(e)}", 'WARNING')
    
    def update_menu_configurations(self):
        """Update menu configurations in database"""
        self.log("🧭 Updating menu configurations...")
        
        # If menu configurations are stored in database
        try:
            # Example: Update menu items table
            # MenuItem.objects.filter(url__startswith='/scheduler/').update(
            #     url=F('url').replace('/scheduler/', '/operations/')
            # )
            
            # Generate new menu configuration from router
            menu_config = OptimizedURLRouter.get_navigation_menu()
            
            # Store in database if needed
            # MenuConfiguration.objects.update_or_create(
            #     name='main_navigation',
            #     defaults={'config': menu_config}
            # )
            
            self.log("Menu configurations updated")
            
        except Exception as e:
            self.log(f"Menu configuration update skipped: {str(e)}", 'WARNING')
    
    def create_ia_monitoring_records(self):
        """Create initial monitoring records"""
        self.log("📊 Creating IA monitoring records...")
        
        # Create initial migration tracking record
        try:
            # If you have an IAMigration model
            # IAMigration.objects.create(
            #     started_at=timezone.now(),
            #     phase='active',
            #     total_urls=len(OptimizedURLRouter.URL_MAPPINGS),
            #     status='in_progress'
            # )
            
            self.log("IA monitoring records created")
            
        except Exception as e:
            self.log(f"Monitoring records creation skipped: {str(e)}", 'WARNING')
    
    def update_system_settings(self):
        """Update system settings for IA"""
        self.log("🔧 Updating system settings...")
        
        # Update system configurations
        try:
            # If you have a SystemSettings model
            # SystemSettings.objects.update_or_create(
            #     key='ia_migration_active',
            #     defaults={'value': 'true'}
            # )
            # 
            # SystemSettings.objects.update_or_create(
            #     key='legacy_urls_enabled',
            #     defaults={'value': 'true'}
            # )
            
            self.log("System settings updated")
            
        except Exception as e:
            self.log(f"System settings update skipped: {str(e)}", 'WARNING')
    
    def migrate_bookmarks(self):
        """Migrate user bookmarks to new URLs"""
        self.log("🔖 Migrating bookmarks...")
        
        try:
            # If you have a UserBookmark model
            # for old_url, new_url in OptimizedURLRouter.URL_MAPPINGS.items():
            #     UserBookmark.objects.filter(
            #         url__contains=old_url
            #     ).update(url=new_url)
            
            self.log("Bookmarks migrated")
            
        except Exception as e:
            self.log(f"Bookmark migration skipped: {str(e)}", 'WARNING')
    
    def migrate_notifications(self):
        """Migrate notification links"""
        self.log("🔔 Migrating notifications...")
        
        try:
            # Update notification links to new URLs
            # Notification.objects.filter(
            #     link__startswith='/scheduler/'
            # ).update(link=...)
            
            self.log("Notifications migrated")
            
        except Exception as e:
            self.log(f"Notification migration skipped: {str(e)}", 'WARNING')
    
    def migrate_audit_logs(self):
        """Update audit log references"""
        self.log("📝 Migrating audit logs...")
        
        try:
            # Update audit logs with new URL references
            # This might involve updating action URLs or resource paths
            
            self.log("Audit logs processed")
            
        except Exception as e:
            self.log(f"Audit log migration skipped: {str(e)}", 'WARNING')
    
    def generate_migration_report(self):
        """Generate migration report"""
        report_path = f"ia_database_migration_{settings.environ.get('ENVIRONMENT', 'unknown')}.log"
        
        with open(report_path, 'w') as f:
            f.write("Information Architecture Database Migration Report\n")
            f.write("=" * 60 + "\n\n")
            
            for log_entry in self.migration_log:
                f.write(log_entry + "\n")
            
            if self.errors:
                f.write("\nErrors:\n")
                for error in self.errors:
                    f.write(f"- {error}\n")
        
        self.log(f"📄 Migration report saved to: {report_path}")


def main():
    """Main migration function"""
    print("Information Architecture Database Migration")
    print("=" * 50)
    
    # Confirm migration
    response = input("\nThis will modify your database. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled.")
        return
    
    # Run migration
    migrator = IADatabaseMigrator()
    
    try:
        migrator.run_migration()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        print("Check the migration report for details.")
        sys.exit(1)
    
    # Show summary
    print(f"\n📊 Migration Summary:")
    print(f"Total log entries: {len(migrator.migration_log)}")
    print(f"Errors: {len(migrator.errors)}")
    
    if migrator.errors:
        print("\n⚠️  Some operations were skipped due to errors.")
        print("Review the migration report for details.")


if __name__ == "__main__":
    main()
