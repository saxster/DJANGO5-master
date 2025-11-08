"""
Migration: Create Team Dashboard Database View

Creates a unified view aggregating tickets, incidents, jobs, and work orders
for the Team Dashboard feature.

Following CLAUDE.md:
- Rule #11: Database constraints and indexes
- Rule #17: Multi-tenant security with tenant_id filtering
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0019_add_quality_metrics_model'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE VIEW v_team_dashboard AS
            -- Tickets
            SELECT 
                'TICKET' as item_type,
                t.id as item_id,
                t.ticketno as item_number,
                t.ticketdesc as title,
                t.priority,
                t.status,
                t.assignedtopeople_id as assignee_id,
                t.tenant_id,
                t.cdtz as created_at,
                t.mdtz as updated_at,
                t.client_id,
                t.bu_id as site_id,
                CASE t.priority
                    WHEN 'HIGH' THEN 80
                    WHEN 'MEDIUM' THEN 50
                    ELSE 20
                END as priority_score,
                NULL::timestamp as sla_due_at,
                NULL::text as severity,
                'ticket' as url_namespace
            FROM ticket t
            WHERE t.status IN ('NEW', 'OPEN', 'ONHOLD')
            
            UNION ALL
            
            -- NOC Incidents
            SELECT
                'INCIDENT' as item_type,
                i.id,
                CONCAT('INC-', LPAD(i.id::text, 5, '0')) as item_number,
                i.title,
                i.severity as priority,
                i.state as status,
                i.assigned_to_id as assignee_id,
                i.tenant_id,
                i.cdtz as created_at,
                i.mdtz as updated_at,
                i.client_id,
                i.site_id,
                CASE i.severity
                    WHEN 'CRITICAL' THEN 100
                    WHEN 'HIGH' THEN 80
                    WHEN 'MEDIUM' THEN 50
                    WHEN 'LOW' THEN 20
                    ELSE 10
                END as priority_score,
                i.sla_due_at,
                i.severity,
                'noc_incident' as url_namespace
            FROM noc_incident i
            WHERE i.state NOT IN ('RESOLVED', 'CLOSED')
            
            UNION ALL
            
            -- Jobs (Tasks/Tours)
            SELECT
                'JOB' as item_type,
                j.id,
                CONCAT('JOB-', LPAD(j.id::text, 5, '0')) as item_number,
                j.jobname as title,
                j.priority,
                CASE 
                    WHEN j.enable THEN 'ACTIVE'
                    ELSE 'DISABLED'
                END as status,
                j.people_id as assignee_id,
                j.tenant_id,
                j.cdtz as created_at,
                j.mdtz as updated_at,
                j.client_id,
                j.bu_id as site_id,
                CASE j.priority
                    WHEN 'CRITICAL' THEN 100
                    WHEN 'HIGH' THEN 80
                    WHEN 'NORMAL' THEN 50
                    WHEN 'MEDIUM' THEN 50
                    ELSE 20
                END as priority_score,
                j.uptodate as sla_due_at,
                NULL::text as severity,
                'activity_job' as url_namespace
            FROM job j
            WHERE j.enable = true
                AND j.uptodate >= CURRENT_TIMESTAMP
            """,
            reverse_sql="DROP VIEW IF EXISTS v_team_dashboard;",
        ),
        
        # Create index on the underlying tables for performance
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_ticket_dashboard 
            ON ticket(tenant_id, status, priority, assignedtopeople_id) 
            WHERE status IN ('NEW', 'OPEN', 'ONHOLD');
            
            CREATE INDEX IF NOT EXISTS idx_incident_dashboard 
            ON noc_incident(tenant_id, state, severity, assigned_to_id) 
            WHERE state NOT IN ('RESOLVED', 'CLOSED');
            
            CREATE INDEX IF NOT EXISTS idx_job_dashboard 
            ON job(tenant_id, enable, priority, people_id) 
            WHERE enable = true;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_ticket_dashboard;
            DROP INDEX IF EXISTS idx_incident_dashboard;
            DROP INDEX IF EXISTS idx_job_dashboard;
            """,
        ),
    ]
