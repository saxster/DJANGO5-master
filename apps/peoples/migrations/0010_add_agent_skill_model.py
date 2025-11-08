"""
Migration: Add AgentSkill model for smart assignment.

Created: Nov 7, 2025
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        ('onboarding', '0001_initial'),
        ('peoples', '0002_encrypt_existing_data'),
    ]

    operations = [
        migrations.CreateModel(
            name='AgentSkill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cuser', models.ForeignKey(blank=True, help_text='User who created this record', null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='%(class)s_cusers', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('muser', models.ForeignKey(blank=True, help_text='User who last modified this record', null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='%(class)s_musers', to=settings.AUTH_USER_MODEL, verbose_name='Modified by')),
                ('cdtz', models.DateTimeField(default='apps.peoples.models.base_model.now', help_text='When this record was created', verbose_name='Created date')),
                ('mdtz', models.DateTimeField(default='apps.peoples.models.base_model.now', help_text='When this record was last modified', verbose_name='Modified date')),
                ('ctzoffset', models.IntegerField(default=-1, help_text="User's timezone offset in minutes", verbose_name='Timezone offset')),
                ('skill_level', models.IntegerField(choices=[(1, '⭐ Learning (can handle basic tasks)'), (2, '⭐⭐ Good (can work independently)'), (3, '⭐⭐⭐ Expert (go-to person)'), (4, '⭐⭐⭐⭐ Master (can train others)')], default=2, help_text='How skilled are they?')),
                ('certified', models.BooleanField(default=False, help_text='Have they completed official training?')),
                ('last_used', models.DateTimeField(blank=True, help_text='Last time they worked on this type of task', null=True)),
                ('total_handled', models.IntegerField(default=0, help_text="Total tasks of this type they've completed")),
                ('avg_completion_time', models.DurationField(blank=True, help_text='Average time to complete this type of task', null=True)),
                ('success_rate', models.DecimalField(blank=True, decimal_places=2, help_text='% of tasks completed successfully first time', max_digits=5, null=True)),
                ('agent', models.ForeignKey(help_text='Who has this skill', on_delete=django.db.models.deletion.CASCADE, related_name='skills', to=settings.AUTH_USER_MODEL)),
                ('category', models.ForeignKey(help_text='What type of task', on_delete=django.db.models.deletion.CASCADE, to='onboarding.typeassist')),
                ('tenant', models.ForeignKey(blank=True, help_text='Tenant that owns this record', null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Agent Skill',
                'verbose_name_plural': 'Agent Skills',
                'ordering': ['mdtz'],
                'indexes': [
                    models.Index(fields=['mdtz'], name='agentskill_mdtz_idx'),
                    models.Index(fields=['cdtz'], name='agentskill_cdtz_idx'),
                    models.Index(fields=['agent', 'category'], name='agentskill_agent_category_idx'),
                    models.Index(fields=['skill_level'], name='agentskill_skill_level_idx'),
                    models.Index(fields=['certified'], name='agentskill_certified_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='agentskill',
            constraint=models.UniqueConstraint(fields=('agent', 'category', 'tenant'), name='unique_agent_category_tenant'),
        ),
    ]
