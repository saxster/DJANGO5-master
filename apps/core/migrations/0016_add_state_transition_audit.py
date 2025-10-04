# Generated migration for StateTransitionAudit model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0015_add_refresh_token_blacklist'),
    ]

    operations = [
        migrations.CreateModel(
            name='StateTransitionAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('entity_type', models.CharField(db_index=True, help_text="State machine class name (e.g., 'TaskStateMachine')", max_length=100)),
                ('entity_id', models.CharField(db_index=True, help_text='Primary key of the entity being transitioned', max_length=100)),
                ('from_state', models.CharField(help_text='Previous state', max_length=50)),
                ('to_state', models.CharField(db_index=True, help_text='New state after transition', max_length=50)),
                ('reason', models.CharField(choices=[('user_action', 'User Action'), ('system_auto', 'System Automation'), ('scheduled', 'Scheduled Task'), ('api_call', 'API Call'), ('webhook', 'Webhook Trigger'), ('escalation', 'Escalation Rule'), ('timeout', 'Timeout/Expiry')], default='user_action', max_length=50)),
                ('comments', models.TextField(blank=True, help_text='Human-readable description of why transition occurred')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional context (sanitized, no PII)')),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now, help_text='When transition occurred (UTC)')),
                ('success', models.BooleanField(default=True, help_text='Whether transition succeeded')),
                ('error_message', models.TextField(blank=True, help_text='Error details if transition failed')),
                ('execution_time_ms', models.IntegerField(blank=True, help_text='Total execution time in milliseconds', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('lock_acquisition_time_ms', models.IntegerField(blank=True, help_text='Time spent acquiring distributed lock (ms)', null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('lock_key', models.CharField(blank=True, help_text='Distributed lock key used', max_length=255)),
                ('isolation_level', models.CharField(blank=True, help_text="Database isolation level (e.g., 'SERIALIZABLE')", max_length=50)),
                ('retry_attempt', models.IntegerField(default=0, help_text='Which retry attempt succeeded (0 = first try)', validators=[django.core.validators.MinValueValidator(0)])),
                ('user', models.ForeignKey(blank=True, help_text='User who initiated transition (null for system)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='state_transitions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'State Transition Audit',
                'verbose_name_plural': 'State Transition Audits',
                'db_table': 'core_state_transition_audit',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='statetransitionaudit',
            index=models.Index(fields=['entity_type', 'entity_id', '-timestamp'], name='audit_entity_lookup'),
        ),
        migrations.AddIndex(
            model_name='statetransitionaudit',
            index=models.Index(fields=['to_state', '-timestamp'], name='audit_state_lookup'),
        ),
        migrations.AddIndex(
            model_name='statetransitionaudit',
            index=models.Index(fields=['user', '-timestamp'], name='audit_user_lookup'),
        ),
        migrations.AddIndex(
            model_name='statetransitionaudit',
            index=models.Index(fields=['success', '-timestamp'], name='audit_failure_lookup'),
        ),
    ]
