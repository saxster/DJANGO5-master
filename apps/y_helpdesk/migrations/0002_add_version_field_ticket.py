"""
Add version field for optimistic locking on Ticket model

Enables detection of concurrent modifications to prevent race conditions
in ticket escalation, status updates, and ticketlog JSON updates.

Following .claude/rules.md security and architecture patterns.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('y_helpdesk', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='version',
            field=models.IntegerField(
                default=0,
                help_text='Version number for optimistic locking. Incremented on each update.'
            ),
        ),

        migrations.AddField(
            model_name='ticket',
            name='last_modified_by',
            field=models.CharField(
                max_length=100,
                null=True,
                blank=True,
                help_text='System component or user that last modified this record'
            ),
        ),

        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(
                fields=['id', 'version'],
                name='ticket_id_version_idx'
            ),
        ),

        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(
                fields=['uuid', 'version', 'status'],
                name='ticket_uuid_ver_status_idx'
            ),
        ),

        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(
                fields=['level', 'version', 'isescalated'],
                name='ticket_level_ver_esc_idx'
            ),
        ),

        migrations.AddConstraint(
            model_name='ticket',
            constraint=models.CheckConstraint(
                check=models.Q(version__gte=0),
                name='ticket_version_gte_zero'
            ),
        ),

        migrations.AddConstraint(
            model_name='ticket',
            constraint=models.CheckConstraint(
                check=models.Q(level__gte=0),
                name='ticket_level_gte_zero'
            ),
        ),
    ]