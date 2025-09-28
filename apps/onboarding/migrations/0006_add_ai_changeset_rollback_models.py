# Generated migration for AI changeset and rollback models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0005_add_personalization_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIChangeSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('changeset_id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('applied', 'Applied'),
                        ('rolled_back', 'Rolled Back'),
                        ('failed', 'Failed'),
                        ('partially_applied', 'Partially Applied')
                    ],
                    default='pending',
                    max_length=50,
                    verbose_name='Status'
                )),
                ('applied_at', models.DateTimeField(blank=True, null=True, verbose_name='Applied At')),
                ('rolled_back_at', models.DateTimeField(blank=True, null=True, verbose_name='Rolled Back At')),
                ('description', models.TextField(help_text='Human-readable description of changes', verbose_name='Description')),
                ('total_changes', models.PositiveIntegerField(default=0, verbose_name='Total Changes')),
                ('successful_changes', models.PositiveIntegerField(default=0, verbose_name='Successful Changes')),
                ('failed_changes', models.PositiveIntegerField(default=0, verbose_name='Failed Changes')),
                ('rollback_reason', models.TextField(
                    blank=True,
                    help_text='Reason for rolling back changes',
                    null=True,
                    verbose_name='Rollback Reason'
                )),
                ('metadata', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Additional contextual information',
                    verbose_name='Additional Metadata'
                )),
                ('approved_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='approved_changesets',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Approved By'
                )),
                ('conversation_session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='changesets',
                    to='onboarding.conversationsession',
                    verbose_name='Conversation Session'
                )),
                ('rolled_back_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='rolled_back_changesets',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Rolled Back By'
                )),
                ('tenant', models.ForeignKey(
                    blank=True,
                    help_text='Tenant this record belongs to',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant',
                    verbose_name='Tenant'
                )),
            ],
            options={
                'verbose_name': 'AI Change Set',
                'verbose_name_plural': 'AI Change Sets',
                'db_table': 'onboarding_ai_changeset',
                'ordering': ['-cdtz'],
            },
        ),
        migrations.CreateModel(
            name='AIChangeRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('record_id', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('sequence_order', models.PositiveIntegerField(verbose_name='Sequence Order')),
                ('model_name', models.CharField(max_length=100, verbose_name='Model Name')),
                ('app_label', models.CharField(max_length=100, verbose_name='App Label')),
                ('object_id', models.CharField(max_length=100, verbose_name='Object ID')),
                ('action', models.CharField(
                    choices=[
                        ('create', 'Create'),
                        ('update', 'Update'),
                        ('delete', 'Delete')
                    ],
                    max_length=20,
                    verbose_name='Action'
                )),
                ('before_state', models.JSONField(
                    blank=True,
                    help_text='Object state before change (for UPDATE/DELETE)',
                    null=True,
                    verbose_name='Before State'
                )),
                ('after_state', models.JSONField(
                    blank=True,
                    help_text='Object state after change (for CREATE/UPDATE)',
                    null=True,
                    verbose_name='After State'
                )),
                ('field_changes', models.JSONField(
                    default=dict,
                    help_text='Specific field-level changes',
                    verbose_name='Field Changes'
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('success', 'Success'),
                        ('failed', 'Failed'),
                        ('rolled_back', 'Rolled Back')
                    ],
                    default='pending',
                    max_length=20,
                    verbose_name='Status'
                )),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='Error Message')),
                ('has_dependencies', models.BooleanField(
                    default=False,
                    help_text='Whether this change affects related objects',
                    verbose_name='Has Dependencies'
                )),
                ('dependency_info', models.JSONField(
                    blank=True,
                    default=dict,
                    verbose_name='Dependency Information'
                )),
                ('rollback_attempted_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Rollback Attempted At'
                )),
                ('rollback_success', models.BooleanField(
                    blank=True,
                    null=True,
                    verbose_name='Rollback Success'
                )),
                ('rollback_error', models.TextField(
                    blank=True,
                    null=True,
                    verbose_name='Rollback Error'
                )),
                ('changeset', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='change_records',
                    to='onboarding.aichangeset',
                    verbose_name='Change Set'
                )),
            ],
            options={
                'verbose_name': 'AI Change Record',
                'verbose_name_plural': 'AI Change Records',
                'db_table': 'onboarding_ai_change_record',
                'ordering': ['changeset', 'sequence_order'],
            },
        ),
        migrations.AddConstraint(
            model_name='aichangerecord',
            constraint=models.UniqueConstraint(
                fields=('changeset', 'sequence_order'),
                name='unique_changeset_sequence'
            ),
        ),
    ]