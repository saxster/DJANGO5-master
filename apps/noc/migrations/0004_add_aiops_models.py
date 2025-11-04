"""
Migration: Add AIOps Enhancement Models.

Creates models for:
- AlertCluster (ML-based alert clustering for noise reduction)
- ExecutablePlaybook (automated remediation workflows)
- PlaybookExecution (playbook execution tracking)
- NOCMetricSnapshot1Hour (hourly aggregated metrics)
- NOCMetricSnapshot1Day (daily aggregated metrics)
- IncidentContext (incident enrichment cache)
"""

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0003_frauddetectionmodel'),
        ('peoples', '0001_initial'),
        ('onboarding', '0001_initial'),
        ('tenants', '0001_initial'),
        ('noc_security_intelligence', '0002_add_intelligence_fields'),
    ]

    operations = [
        # ========== AlertCluster Model (Enhancement #1) ==========
        migrations.CreateModel(
            name='AlertCluster',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cluster_id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False
                )),
                ('cluster_signature', models.CharField(max_length=200, db_index=True)),
                ('cluster_confidence', models.FloatField(default=0.0)),
                ('cluster_method', models.CharField(max_length=50, default='xgboost_similarity')),
                ('feature_vector', models.JSONField(default=dict)),
                ('combined_severity', models.CharField(max_length=20)),
                ('affected_sites', models.JSONField(default=list)),
                ('affected_people', models.JSONField(default=list)),
                ('alert_types_in_cluster', models.JSONField(default=list)),
                ('first_alert_at', models.DateTimeField(db_index=True)),
                ('last_alert_at', models.DateTimeField()),
                ('alert_count', models.IntegerField(default=1)),
                ('is_active', models.BooleanField(default=True, db_index=True)),
                ('suppressed_alert_count', models.IntegerField(default=0)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('primary_alert', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='noc.nocalertevent',
                    related_name='primary_for_cluster'
                )),
                ('related_alerts', models.ManyToManyField(
                    to='noc.nocalertevent',
                    related_name='alert_clusters'
                )),
            ],
            options={
                'db_table': 'noc_alert_cluster',
                'ordering': ['-last_alert_at'],
            },
        ),

        # Indexes for AlertCluster
        migrations.AddIndex(
            model_name='alertcluster',
            index=models.Index(
                fields=['tenant', 'is_active', '-last_alert_at'],
                name='noc_cluster_active'
            ),
        ),
        migrations.AddIndex(
            model_name='alertcluster',
            index=models.Index(
                fields=['cluster_signature'],
                name='noc_cluster_signature'
            ),
        ),

        # ========== ExecutablePlaybook Model (Enhancement #2) ==========
        migrations.CreateModel(
            name='ExecutablePlaybook',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('playbook_id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False
                )),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('finding_types', models.JSONField(default=list)),
                ('severity_threshold', models.CharField(max_length=20)),
                ('auto_execute', models.BooleanField(default=False)),
                ('actions', models.JSONField(default=list)),
                ('is_active', models.BooleanField(default=True, db_index=True)),
                ('total_executions', models.IntegerField(default=0)),
                ('successful_executions', models.IntegerField(default=0)),
                ('failed_executions', models.IntegerField(default=0)),
                ('avg_execution_time_seconds', models.FloatField(default=0.0)),
                ('success_rate', models.FloatField(default=0.0)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
            ],
            options={
                'db_table': 'noc_executable_playbook',
                'ordering': ['-updated_at'],
            },
        ),

        migrations.AddIndex(
            model_name='executableplaybook',
            index=models.Index(
                fields=['tenant', 'auto_execute', 'is_active'],
                name='noc_playbook_active'
            ),
        ),

        # ========== PlaybookExecution Model (Enhancement #2) ==========
        migrations.CreateModel(
            name='PlaybookExecution',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('execution_id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False
                )),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('PENDING', 'Pending Approval'),
                        ('RUNNING', 'Running'),
                        ('SUCCESS', 'Success'),
                        ('PARTIAL', 'Partial Success'),
                        ('FAILED', 'Failed'),
                        ('CANCELLED', 'Cancelled'),
                    ],
                    default='PENDING',
                    db_index=True
                )),
                ('action_results', models.JSONField(default=list)),
                ('started_at', models.DateTimeField(null=True, blank=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('duration_seconds', models.FloatField(null=True, blank=True)),
                ('requires_approval', models.BooleanField(default=False)),
                ('approved_at', models.DateTimeField(null=True, blank=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('playbook', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='noc.executableplaybook'
                )),
                ('finding', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='noc_security_intelligence.auditfinding'
                )),
                ('approved_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    blank=True,
                    to='peoples.people'
                )),
            ],
            options={
                'db_table': 'noc_playbook_execution',
                'ordering': ['-created_at'],
            },
        ),

        migrations.AddIndex(
            model_name='playbookexecution',
            index=models.Index(
                fields=['tenant', 'status', '-created_at'],
                name='noc_exec_status'
            ),
        ),

        # ========== NOCMetricSnapshot1Hour Model (Enhancement #3) ==========
        migrations.CreateModel(
            name='NOCMetricSnapshot1Hour',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('window_start', models.DateTimeField(db_index=True)),
                ('window_end', models.DateTimeField()),
                # Aggregate fields (avg, min, max, sum for each metric)
                ('tickets_open_avg', models.FloatField(default=0.0)),
                ('tickets_open_min', models.IntegerField(default=0)),
                ('tickets_open_max', models.IntegerField(default=0)),
                ('tickets_open_sum', models.IntegerField(default=0)),
                ('tickets_overdue_avg', models.FloatField(default=0.0)),
                ('tickets_overdue_min', models.IntegerField(default=0)),
                ('tickets_overdue_max', models.IntegerField(default=0)),
                ('work_orders_pending_avg', models.FloatField(default=0.0)),
                ('work_orders_overdue_avg', models.FloatField(default=0.0)),
                ('attendance_present_avg', models.FloatField(default=0.0)),
                ('attendance_missing_avg', models.FloatField(default=0.0)),
                ('security_anomalies_sum', models.IntegerField(default=0)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('client', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='client_onboarding.bt'
                )),
            ],
            options={
                'db_table': 'noc_metric_snapshot_1hour',
                'ordering': ['-window_start'],
            },
        ),

        migrations.AddIndex(
            model_name='nocmetricsnapshot1hour',
            index=models.Index(
                fields=['tenant', 'client', 'window_start'],
                name='noc_1h_tenant_client'
            ),
        ),

        # ========== NOCMetricSnapshot1Day Model (Enhancement #3) ==========
        migrations.CreateModel(
            name='NOCMetricSnapshot1Day',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('date', models.DateField(db_index=True)),
                # Aggregate fields
                ('tickets_open_avg', models.FloatField(default=0.0)),
                ('tickets_open_min', models.IntegerField(default=0)),
                ('tickets_open_max', models.IntegerField(default=0)),
                ('work_orders_pending_avg', models.FloatField(default=0.0)),
                ('attendance_present_avg', models.FloatField(default=0.0)),
                ('security_anomalies_sum', models.IntegerField(default=0)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('client', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='client_onboarding.bt'
                )),
            ],
            options={
                'db_table': 'noc_metric_snapshot_1day',
                'ordering': ['-date'],
            },
        ),

        migrations.AddConstraint(
            model_name='nocmetricsnapshot1day',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'client', 'date'],
                name='unique_daily_snapshot_per_client'
            ),
        ),

        migrations.AddIndex(
            model_name='nocmetricsnapshot1day',
            index=models.Index(
                fields=['tenant', 'client', 'date'],
                name='noc_1d_tenant_client'
            ),
        ),

        # ========== IncidentContext Model (Enhancement #6) ==========
        migrations.CreateModel(
            name='IncidentContext',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('context_data', models.JSONField(default=dict)),
                ('enriched_at', models.DateTimeField(auto_now_add=True)),
                ('cache_expires_at', models.DateTimeField()),
                ('related_alerts_count', models.IntegerField(default=0)),
                ('recent_changes_count', models.IntegerField(default=0)),
                ('historical_incidents_count', models.IntegerField(default=0)),
                ('affected_resources_count', models.IntegerField(default=0)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('incident', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='noc.nocincident',
                    related_name='context'
                )),
            ],
            options={
                'db_table': 'noc_incident_context',
            },
        ),
    ]
