# Generated migration for adding performance indexes



class Migration(migrations.Migration):

    dependencies = [
        ('peoples', '0002_add_capabilities_field'),
    ]

    operations = [
        # Add database indexes for frequently queried fields
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_email_active ON people (email) WHERE isverified = true AND enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_people_email_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_loginid_active ON people (loginid) WHERE isverified = true AND enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_people_loginid_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_department_bu ON people (department_id, bu_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_people_department_bu;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_reportto_active ON people (reportto_id) WHERE enable = true AND reportto_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_people_reportto_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_capabilities_gin ON people USING GIN (capabilities) WHERE capabilities IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_people_capabilities_gin;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_modified_recent ON people (mdtz) WHERE mdtz >= (CURRENT_TIMESTAMP - INTERVAL '30 days');",
            reverse_sql="DROP INDEX IF EXISTS idx_people_modified_recent;"
        ),

        # Add indexes for Pgroup model
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_pgroup_grouplead_enable ON pgroup (grouplead_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_pgroup_grouplead_enable;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_pgroup_client_identifier ON pgroup (client_id, identifier_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_pgroup_client_identifier;"
        ),

        # Add indexes for Pgbelonging model
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_pgbelonging_people_groups ON pgbelonging (people_id, pgroup_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_pgbelonging_people_groups;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_pgbelonging_grouplead ON pgbelonging (people_id) WHERE isgrouplead = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_pgbelonging_grouplead;"
        ),

        # Add indexes for Capability model
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_capability_parent_enable ON capability (parent_id) WHERE enable = true AND parent_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS idx_capability_parent_enable;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_capability_cfor_client ON capability (cfor, client_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_capability_cfor_client;"
        ),

        # Add composite indexes for common query patterns
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_search_active ON people (peoplename, peoplecode, email) WHERE isverified = true AND enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_people_search_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_people_hierarchy ON people (bu_id, department_id, reportto_id) WHERE enable = true;",
            reverse_sql="DROP INDEX IF EXISTS idx_people_hierarchy;"
        ),
    ]