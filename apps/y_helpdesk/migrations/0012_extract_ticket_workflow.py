# Generated migration for extracting TicketWorkflow model

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from django.core.serializers.json import DjangoJSONEncoder


def migrate_workflow_data(apps, schema_editor):
    """
    Migrate workflow data from Ticket to TicketWorkflow model.
    """
    Ticket = apps.get_model('y_helpdesk', 'Ticket')
    TicketWorkflow = apps.get_model('y_helpdesk', 'TicketWorkflow')

    db_alias = schema_editor.connection.alias

    # Process tickets in batches to avoid memory issues
    batch_size = 1000
    ticket_count = Ticket.objects.using(db_alias).count()

    for offset in range(0, ticket_count, batch_size):
        tickets = Ticket.objects.using(db_alias).all()[offset:offset + batch_size]

        workflow_objects = []
        for ticket in tickets:
            # Extract workflow data from ticket
            workflow_data = ticket.ticketlog or {}

            # Convert legacy ticketlog format to new workflow_data format
            if isinstance(workflow_data, dict):
                new_workflow_data = {
                    "workflow_history": workflow_data.get("ticket_history", []),
                    "escalation_attempts": [],
                    "assignment_history": [],
                    "status_transitions": []
                }
                # Include any additional data from old ticketlog
                for key, value in workflow_data.items():
                    if key not in ["ticket_history"]:
                        new_workflow_data[key] = value

                # Add events if present
                if hasattr(ticket, 'events') and ticket.events:
                    new_workflow_data["events"] = ticket.events
            else:
                new_workflow_data = {
                    "workflow_history": [],
                    "escalation_attempts": [],
                    "assignment_history": [],
                    "status_transitions": []
                }

            # Create TicketWorkflow instance
            workflow = TicketWorkflow(
                ticket=ticket,
                escalation_level=getattr(ticket, 'level', 0),
                is_escalated=getattr(ticket, 'isescalated', False),
                escalation_count=1 if getattr(ticket, 'isescalated', False) else 0,
                last_escalated_at=ticket.mdtz if getattr(ticket, 'isescalated', False) else None,
                workflow_status='ACTIVE',
                workflow_started_at=ticket.cdtz,
                last_activity_at=getattr(ticket, 'modifieddatetime', ticket.mdtz),
                activity_count=len(new_workflow_data.get("workflow_history", [])),
                workflow_data=new_workflow_data,
                # Copy tenant and audit fields
                tenant=getattr(ticket, 'tenant', None),
                bu=getattr(ticket, 'bu', None),
                client=getattr(ticket, 'client', None),
                cuser=getattr(ticket, 'cuser', None),
                muser=getattr(ticket, 'muser', None),
                cdtz=ticket.cdtz,
                mdtz=ticket.mdtz,
                ctzoffset=getattr(ticket, 'ctzoffset', 0)
            )
            workflow_objects.append(workflow)

        # Bulk create workflow objects for this batch
        if workflow_objects:
            TicketWorkflow.objects.using(db_alias).bulk_create(
                workflow_objects,
                batch_size=500
            )


def reverse_migrate_workflow_data(apps, schema_editor):
    """
    Reverse migration: copy data back from TicketWorkflow to Ticket.
    """
    Ticket = apps.get_model('y_helpdesk', 'Ticket')
    TicketWorkflow = apps.get_model('y_helpdesk', 'TicketWorkflow')

    db_alias = schema_editor.connection.alias

    # Update tickets with workflow data
    for workflow in TicketWorkflow.objects.using(db_alias).select_related('ticket'):
        ticket = workflow.ticket

        # Convert new workflow_data format back to legacy ticketlog
        legacy_ticketlog = {
            "ticket_history": workflow.workflow_data.get("workflow_history", [])
        }
        # Include any additional data
        for key, value in workflow.workflow_data.items():
            if key not in ["workflow_history", "escalation_attempts", "assignment_history", "status_transitions"]:
                legacy_ticketlog[key] = value

        # Update ticket fields
        Ticket.objects.using(db_alias).filter(pk=ticket.pk).update(
            level=workflow.escalation_level,
            isescalated=workflow.is_escalated,
            modifieddatetime=workflow.last_activity_at,
            ticketlog=legacy_ticketlog,
            events=workflow.workflow_data.get("events", "")
        )


class Migration(migrations.Migration):

    dependencies = [
        ('y_helpdesk', '0011_add_mobile_sync_fields'),
    ]

    operations = [
        # Create TicketWorkflow model
        migrations.CreateModel(
            name='TicketWorkflow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant', models.CharField(blank=True, default='default', max_length=100, null=True)),
                ('cdtz', models.DateTimeField(default=django.utils.timezone.now)),
                ('mdtz', models.DateTimeField(default=django.utils.timezone.now)),
                ('ctzoffset', models.IntegerField(default=0)),
                ('escalation_level', models.IntegerField(default=0, help_text='Current escalation level')),
                ('is_escalated', models.BooleanField(default=False, help_text='Whether ticket has been escalated')),
                ('escalation_count', models.IntegerField(default=0, help_text='Total number of escalations')),
                ('last_escalated_at', models.DateTimeField(blank=True, help_text='When ticket was last escalated', null=True)),
                ('workflow_status', models.CharField(choices=[('ACTIVE', 'Active'), ('PAUSED', 'Paused'), ('COMPLETED', 'Completed'), ('CANCELLED', 'Cancelled')], default='ACTIVE', help_text='Current workflow status', max_length=20)),
                ('workflow_started_at', models.DateTimeField(default=django.utils.timezone.now, help_text='When workflow was initiated')),
                ('workflow_completed_at', models.DateTimeField(blank=True, help_text='When workflow was completed', null=True)),
                ('last_activity_at', models.DateTimeField(default=django.utils.timezone.now, help_text='Last activity timestamp')),
                ('activity_count', models.IntegerField(default=0, help_text='Total number of activities')),
                ('workflow_data', models.JSONField(default=dict, encoder=DjangoJSONEncoder, help_text='Workflow history and metadata')),
                ('response_time_hours', models.DecimalField(blank=True, decimal_places=2, help_text='Time to first response in hours', max_digits=10, null=True)),
                ('resolution_time_hours', models.DecimalField(blank=True, decimal_places=2, help_text='Time to resolution in hours', max_digits=10, null=True)),
                ('bu', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, to='client_onboarding.bt')),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='ticketworkflow_clients', to='client_onboarding.bt')),
                ('cuser', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='ticketworkflow_cuser', to='peoples.people')),
                ('muser', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='ticketworkflow_muser', to='peoples.people')),
                ('ticket', models.OneToOneField(help_text='Related ticket for this workflow', on_delete=django.db.models.deletion.CASCADE, related_name='workflow', to='y_helpdesk.ticket')),
            ],
            options={
                'db_table': 'ticket_workflow',
            },
        ),

        # Add indexes
        migrations.AddIndex(
            model_name='ticketworkflow',
            index=models.Index(fields=['escalation_level', 'is_escalated'], name='ticket_workflow_escalation_idx'),
        ),
        migrations.AddIndex(
            model_name='ticketworkflow',
            index=models.Index(fields=['workflow_status', 'last_activity_at'], name='ticket_workflow_status_activity_idx'),
        ),
        migrations.AddIndex(
            model_name='ticketworkflow',
            index=models.Index(fields=['ticket', 'escalation_level'], name='ticket_workflow_ticket_escalation_idx'),
        ),

        # Add constraints
        migrations.AddConstraint(
            model_name='ticketworkflow',
            constraint=models.CheckConstraint(check=models.Q(('escalation_level__gte', 0)), name='escalation_level_non_negative'),
        ),
        migrations.AddConstraint(
            model_name='ticketworkflow',
            constraint=models.CheckConstraint(check=models.Q(('escalation_count__gte', 0)), name='escalation_count_non_negative'),
        ),
        migrations.AddConstraint(
            model_name='ticketworkflow',
            constraint=models.CheckConstraint(check=models.Q(('activity_count__gte', 0)), name='activity_count_non_negative'),
        ),

        # Migrate data from Ticket to TicketWorkflow
        migrations.RunPython(
            migrate_workflow_data,
            reverse_migrate_workflow_data,
            hints={'model_name': 'ticketworkflow'}
        ),

        # Remove old fields from Ticket model
        # Note: These will be handled by backward compatibility properties
        # migrations.RemoveField(model_name='ticket', name='level'),
        # migrations.RemoveField(model_name='ticket', name='isescalated'),
        # migrations.RemoveField(model_name='ticket', name='modifieddatetime'),
        # migrations.RemoveField(model_name='ticket', name='ticketlog'),
        # migrations.RemoveField(model_name='ticket', name='events'),
    ]