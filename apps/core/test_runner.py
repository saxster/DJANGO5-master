"""
Custom test runner that ensures test database has correct schema.
Handles models that inherit from TenantAwareModel but don't have proper migrations.
"""

from django.test.runner import DiscoverRunner
from django.db import connection
import logging

logger = logging.getLogger(__name__)


class TenantAwareTestRunner(DiscoverRunner):
    """
    Custom test runner that adds missing tenant_id columns to tables
    that should have them due to TenantAwareModel inheritance.
    """

    def setup_databases(self, **kwargs):
        """Override to add missing columns after database creation."""
        # First, let Django create the test database normally
        old_names = super().setup_databases(**kwargs)

        # Then add missing columns
        self._add_missing_tenant_columns()
        self._ensure_session_table_exists()
        self._ensure_reports_tables_exist()

        return old_names

    def _add_missing_tenant_columns(self):
        """Add tenant_id columns to tables that are missing them."""
        with connection.cursor() as cursor:
            # Ensure default tenant exists to prevent foreign key violations
            self._ensure_default_tenant_exists()

            # List of tables that should have tenant_id but might not due to migration issues
            tables_needing_tenant = [
                'typeassist',
                'bt',
                'geofencemaster',
                'shift',
                'location',  # Add location to the list
            ]

            for table in tables_needing_tenant:
                try:
                    # Check if column already exists
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = %s AND column_name = 'tenant_id'
                    """, [table])

                    if not cursor.fetchone():
                        # Add tenant_id column if it doesn't exist
                        logger.info(f"Adding tenant_id column to {table}")
                        cursor.execute(f"""
                            ALTER TABLE {table}
                            ADD COLUMN IF NOT EXISTS tenant_id bigint
                            REFERENCES tenants_tenant(id)
                            ON DELETE CASCADE
                        """)

                        # Create index for better performance
                        cursor.execute(f"""
                            CREATE INDEX IF NOT EXISTS {table}_tenant_id_idx
                            ON {table}(tenant_id)
                        """)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not add tenant_id to {table}: {e}")

    def _ensure_default_tenant_exists(self):
        """Ensure a default tenant with ID=1 exists to prevent foreign key violations."""
        with connection.cursor() as cursor:
            try:
                # Check if tenant with ID=1 exists
                cursor.execute("SELECT id FROM tenants_tenant WHERE id = 1")
                if not cursor.fetchone():
                    # Create default tenant with ID=1
                    logger.info("Creating default tenant with ID=1")
                    cursor.execute("""
                        INSERT INTO tenants_tenant (id, tenantname, subdomain_prefix, created_at)
                        VALUES (1, 'Test Tenant', 'test', CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO NOTHING
                    """)
                    # Reset sequence to prevent ID conflicts
                    cursor.execute("SELECT setval('tenants_tenant_id_seq', (SELECT MAX(id) FROM tenants_tenant))")
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not ensure default tenant: {e}")

    def _ensure_session_table_exists(self):
        """Ensure django_session table exists for session-based tests."""
        with connection.cursor() as cursor:
            try:
                # Check if django_session table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'django_session'
                    )
                """)

                if not cursor.fetchone()[0]:
                    logger.info("Creating django_session table")
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS django_session (
                            session_key varchar(40) NOT NULL PRIMARY KEY,
                            session_data text NOT NULL,
                            expire_date timestamp with time zone NOT NULL
                        )
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS django_session_expire_date_idx
                        ON django_session(expire_date)
                    """)
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not ensure django_session table: {e}")

    def _ensure_reports_tables_exist(self):
        """Ensure reports app tables exist."""
        with connection.cursor() as cursor:
            try:
                # Create generatepdf table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS generatepdf (
                        id bigserial PRIMARY KEY,
                        document_type varchar(50),
                        company varchar(50),
                        additional_filter varchar(50),
                        form_type varchar(50),
                        period varchar(100),
                        cdtz timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                        mdtz timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
                        ctzoffset integer DEFAULT -1,
                        cuser_id bigint,
                        muser_id bigint
                    )
                """)
                logger.info("Ensured generatepdf table exists")
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not create generatepdf table: {e}")