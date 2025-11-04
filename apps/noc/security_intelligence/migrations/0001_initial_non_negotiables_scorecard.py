# Generated migration for NonNegotiablesScorecard model
# Date: 2025-10-03

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('onboarding', '__latest__'),
        ('tenants', '__latest__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NonNegotiablesScorecard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified At')),
                ('ctzoffset', models.CharField(blank=True, max_length=20, null=True, verbose_name='Created Timezone Offset')),
                ('mtzoffset', models.CharField(blank=True, max_length=20, null=True, verbose_name='Modified Timezone Offset')),

                # Scorecard-specific fields
                ('check_date', models.DateField(db_index=True, help_text='Date of this evaluation')),

                # Overall health metrics
                ('overall_health_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    help_text='Overall health: RED if any pillar is RED, AMBER if any is AMBER, else GREEN',
                    max_length=10
                )),
                ('overall_health_score', models.IntegerField(default=100, help_text='Overall health score 0-100 (weighted average of pillar scores)')),
                ('total_violations', models.IntegerField(default=0, help_text='Total number of violations across all pillars')),
                ('critical_violations', models.IntegerField(default=0, help_text='Number of critical (RED) violations requiring immediate action')),

                # Pillar 1: Right Guard at Right Post
                ('pillar_1_score', models.IntegerField(default=100, help_text='Pillar 1: Right Guard at Right Post (coverage, attendance, geofence)')),
                ('pillar_1_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    max_length=10
                )),

                # Pillar 2: Supervise Relentlessly
                ('pillar_2_score', models.IntegerField(default=100, help_text='Pillar 2: Supervise Relentlessly (tours, spot checks, checkpoint compliance)')),
                ('pillar_2_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    max_length=10
                )),

                # Pillar 3: 24/7 Control Desk
                ('pillar_3_score', models.IntegerField(default=100, help_text='Pillar 3: 24/7 Control Desk (alert ack, escalation SLA, stale alerts)')),
                ('pillar_3_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    max_length=10
                )),

                # Pillar 4: Legal & Professional
                ('pillar_4_score', models.IntegerField(default=100, help_text='Pillar 4: Legal & Professional (PF/ESIC/UAN, payroll, compliance)')),
                ('pillar_4_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    max_length=10
                )),

                # Pillar 5: Support the Field
                ('pillar_5_score', models.IntegerField(default=100, help_text='Pillar 5: Support the Field (uniforms, logistics, work orders)')),
                ('pillar_5_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    max_length=10
                )),

                # Pillar 6: Record Everything
                ('pillar_6_score', models.IntegerField(default=100, help_text='Pillar 6: Record Everything (daily/weekly/monthly reports, documentation)')),
                ('pillar_6_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    max_length=10
                )),

                # Pillar 7: Respond to Emergencies
                ('pillar_7_score', models.IntegerField(default=100, help_text='Pillar 7: Respond to Emergencies (crisis response, IVR, panic button)')),
                ('pillar_7_status', models.CharField(
                    choices=[('GREEN', 'Green - Compliant'), ('AMBER', 'Amber - Minor Issues'), ('RED', 'Red - Critical Violations')],
                    default='GREEN',
                    max_length=10
                )),

                # JSON fields
                ('violations_detail', models.JSONField(blank=True, default=dict, help_text='Detailed breakdown of violations per pillar with remediation actions')),
                ('recommendations', models.JSONField(blank=True, default=list, help_text='AI-generated recommendations for improvement')),
                ('auto_escalated_alerts', models.JSONField(blank=True, default=list, help_text='List of NOC alert IDs that were auto-created from violations')),

                # Foreign keys
                ('client', models.ForeignKey(
                    help_text='Client/business unit',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='non_negotiables_scorecards',
                    to='client_onboarding.bt'
                )),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='non_negotiables_scorecards',
                    to='tenants.tenant'
                )),
                ('cuser', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_non_negotiables_scorecards',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Created By'
                )),
                ('muser', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='modified_non_negotiables_scorecards',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Modified By'
                )),
            ],
            options={
                'verbose_name': 'Non-Negotiables Scorecard',
                'verbose_name_plural': 'Non-Negotiables Scorecards',
                'db_table': 'noc_non_negotiables_scorecard',
                'ordering': ['-check_date', '-cdtz'],
                'get_latest_by': ['check_date', 'cdtz'],
            },
        ),
        migrations.AddIndex(
            model_name='nonnegotiablesscorecard',
            index=models.Index(fields=['client', 'check_date'], name='scorecard_client_date_idx'),
        ),
        migrations.AddIndex(
            model_name='nonnegotiablesscorecard',
            index=models.Index(fields=['overall_health_status', 'check_date'], name='scorecard_health_date_idx'),
        ),
        migrations.AddIndex(
            model_name='nonnegotiablesscorecard',
            index=models.Index(fields=['check_date'], name='scorecard_date_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='nonnegotiablesscorecard',
            unique_together={('tenant', 'client', 'check_date')},
        ),
    ]
