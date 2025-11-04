"""
Migration: Add Intelligence System Models.

Creates:
- CorrelatedIncident (signal-alert correlation)
- MLModelMetrics (ML model performance tracking)
- NOCEventLog (WebSocket event audit trail)
"""

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0001_initial'),
        ('peoples', '0001_initial'),
        ('onboarding', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # ========== CorrelatedIncident Model ==========
        migrations.CreateModel(
            name='CorrelatedIncident',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('incident_id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False
                )),
                ('signals', models.JSONField(default=dict)),
                ('combined_severity', models.CharField(
                    max_length=20,
                    choices=[
                        ('CRITICAL', 'Critical'),
                        ('HIGH', 'High'),
                        ('MEDIUM', 'Medium'),
                        ('LOW', 'Low'),
                        ('INFO', 'Info'),
                    ],
                    default='INFO',
                    db_index=True
                )),
                ('correlation_window_minutes', models.IntegerField(default=15)),
                ('correlation_score', models.FloatField(default=0.0)),
                ('correlation_type', models.CharField(max_length=50, default='TIME_ENTITY')),
                ('detected_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('investigated', models.BooleanField(default=False)),
                ('investigated_at', models.DateTimeField(null=True, blank=True)),
                ('investigation_notes', models.TextField(blank=True)),
                ('root_cause_identified', models.BooleanField(default=False)),
                ('root_cause_description', models.TextField(blank=True)),
                ('person', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='peoples.people',
                    related_name='correlated_incidents'
                )),
                ('site', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='client_onboarding.bt',
                    related_name='correlated_incidents'
                )),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('investigated_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    blank=True,
                    to='peoples.people',
                    related_name='investigated_incidents'
                )),
                ('related_alerts', models.ManyToManyField(
                    to='noc.nocalertevent',
                    related_name='correlated_incidents',
                    blank=True
                )),
            ],
            options={
                'db_table': 'noc_correlated_incident',
                'ordering': ['-detected_at'],
            },
        ),

        # Indexes for CorrelatedIncident
        migrations.AddIndex(
            model_name='correlatedincident',
            index=models.Index(
                fields=['tenant', 'person', 'detected_at'],
                name='noc_corr_tn_pr_dt'
            ),
        ),
        migrations.AddIndex(
            model_name='correlatedincident',
            index=models.Index(
                fields=['tenant', 'site', 'detected_at'],
                name='noc_corr_tn_st_dt'
            ),
        ),
        migrations.AddIndex(
            model_name='correlatedincident',
            index=models.Index(
                fields=['combined_severity', 'investigated'],
                name='noc_corr_sv_inv'
            ),
        ),

        # ========== MLModelMetrics Model ==========
        migrations.CreateModel(
            name='MLModelMetrics',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('model_id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False
                )),
                ('model_version', models.IntegerField()),
                ('model_type', models.CharField(
                    max_length=50,
                    choices=[
                        ('fraud_detection', 'Fraud Detection'),
                        ('anomaly_detection', 'Anomaly Detection'),
                        ('risk_prediction', 'Risk Prediction'),
                    ],
                    default='fraud_detection',
                    db_index=True
                )),
                ('precision', models.FloatField(
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0)
                    ]
                )),
                ('recall', models.FloatField(
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0)
                    ]
                )),
                ('f1_score', models.FloatField(
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0)
                    ]
                )),
                ('accuracy', models.FloatField(
                    null=True,
                    blank=True,
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0)
                    ]
                )),
                ('training_samples', models.IntegerField()),
                ('test_samples', models.IntegerField(null=True, blank=True)),
                ('fraud_samples', models.IntegerField(null=True, blank=True)),
                ('normal_samples', models.IntegerField(null=True, blank=True)),
                ('training_date', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('is_active', models.BooleanField(default=False, db_index=True)),
                ('validation_passed', models.BooleanField(default=False)),
                ('model_file_path', models.CharField(max_length=500, blank=True)),
                ('model_size_bytes', models.BigIntegerField(null=True, blank=True)),
                ('hyperparameters', models.JSONField(default=dict)),
                ('feature_names', models.JSONField(default=list)),
                ('training_notes', models.TextField(blank=True)),
                ('error_message', models.TextField(blank=True)),
            ],
            options={
                'db_table': 'noc_ml_model_metrics',
                'ordering': ['-training_date'],
            },
        ),

        # Indexes for MLModelMetrics
        migrations.AddIndex(
            model_name='mlmodelmetrics',
            index=models.Index(
                fields=['model_type', '-training_date'],
                name='noc_ml_tp_dt'
            ),
        ),
        migrations.AddIndex(
            model_name='mlmodelmetrics',
            index=models.Index(
                fields=['model_type', 'is_active'],
                name='noc_ml_tp_act'
            ),
        ),
        migrations.AddIndex(
            model_name='mlmodelmetrics',
            index=models.Index(
                fields=['is_active', 'model_type', '-training_date'],
                name='noc_ml_act_tp_dt'
            ),
        ),

        # Constraint: Only one active model per type
        migrations.AddConstraint(
            model_name='mlmodelmetrics',
            constraint=models.UniqueConstraint(
                fields=['model_type'],
                condition=models.Q(is_active=True),
                name='unique_active_model_per_type'
            ),
        ),

        # ========== NOCEventLog Model ==========
        migrations.CreateModel(
            name='NOCEventLog',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False
                )),
                ('event_type', models.CharField(
                    max_length=50,
                    choices=[
                        ('alert_created', 'Alert Created'),
                        ('alert_updated', 'Alert Updated'),
                        ('finding_created', 'Finding Created'),
                        ('anomaly_detected', 'Anomaly Detected'),
                        ('ticket_updated', 'Ticket Updated'),
                        ('incident_updated', 'Incident Updated'),
                        ('correlation_identified', 'Correlation Identified'),
                        ('maintenance_window', 'Maintenance Window'),
                        ('metrics_refresh', 'Metrics Refresh'),
                    ],
                    db_index=True
                )),
                ('payload', models.JSONField(default=dict)),
                ('broadcast_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('recipient_count', models.IntegerField(default=0)),
                ('alert_id', models.IntegerField(null=True, blank=True, db_index=True)),
                ('finding_id', models.IntegerField(null=True, blank=True, db_index=True)),
                ('ticket_id', models.IntegerField(null=True, blank=True, db_index=True)),
                ('broadcast_success', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True)),
                ('broadcast_latency_ms', models.IntegerField(null=True, blank=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
            ],
            options={
                'db_table': 'noc_event_log',
                'ordering': ['-broadcast_at'],
            },
        ),

        # Indexes for NOCEventLog
        migrations.AddIndex(
            model_name='noceventlog',
            index=models.Index(
                fields=['tenant', '-broadcast_at'],
                name='noc_evt_tn_time'
            ),
        ),
        migrations.AddIndex(
            model_name='noceventlog',
            index=models.Index(
                fields=['event_type', '-broadcast_at'],
                name='noc_evt_tp_time'
            ),
        ),
        migrations.AddIndex(
            model_name='noceventlog',
            index=models.Index(
                fields=['broadcast_at', 'event_type'],
                name='noc_evt_time_tp'
            ),
        ),
        migrations.AddIndex(
            model_name='noceventlog',
            index=models.Index(
                fields=['alert_id', '-broadcast_at'],
                name='noc_evt_al_time'
            ),
        ),
        migrations.AddIndex(
            model_name='noceventlog',
            index=models.Index(
                fields=['finding_id', '-broadcast_at'],
                name='noc_evt_fn_time'
            ),
        ),
        migrations.AddIndex(
            model_name='noceventlog',
            index=models.Index(
                fields=['ticket_id', '-broadcast_at'],
                name='noc_evt_tk_time'
            ),
        ),
    ]
