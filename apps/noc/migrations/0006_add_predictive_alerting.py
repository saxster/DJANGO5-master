"""
Migration: Add Predictive Alerting Model.

Creates:
- PredictiveAlertTracking (tracks prediction accuracy for ML models)
"""

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0005_add_priority_scoring_fields'),
        ('peoples', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # ========== PredictiveAlertTracking Model (Enhancement #5) ==========
        migrations.CreateModel(
            name='PredictiveAlertTracking',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('prediction_id', models.UUIDField(
                    primary_key=True,
                    default=uuid.uuid4,
                    editable=False,
                    serialize=False
                )),
                ('prediction_type', models.CharField(
                    max_length=50,
                    choices=[
                        ('sla_breach', 'SLA Breach'),
                        ('device_failure', 'Device Failure'),
                        ('staffing_gap', 'Staffing Gap'),
                    ],
                    db_index=True
                )),
                ('predicted_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('predicted_probability', models.FloatField(
                    validators=[
                        django.core.validators.MinValueValidator(0.0),
                        django.core.validators.MaxValueValidator(1.0)
                    ]
                )),
                ('confidence_level', models.CharField(
                    max_length=20,
                    choices=[
                        ('very_high', 'Very High (>90%)'),
                        ('high', 'High (75-90%)'),
                        ('medium', 'Medium (60-75%)'),
                        ('low', 'Low (<60%)'),
                    ]
                )),
                ('entity_type', models.CharField(max_length=50)),
                ('entity_id', models.IntegerField()),
                ('entity_snapshot', models.JSONField(default=dict)),
                ('features', models.JSONField(default=dict)),
                ('validation_deadline', models.DateTimeField(db_index=True)),
                ('actual_outcome', models.BooleanField(null=True, blank=True)),
                ('validated_at', models.DateTimeField(null=True, blank=True)),
                ('prediction_correct', models.BooleanField(null=True, blank=True)),
                ('prevented_by_action', models.BooleanField(default=False)),
                ('prevention_notes', models.TextField(blank=True)),
                ('tenant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
                ('alert', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True,
                    blank=True,
                    to='noc.nocalertevent',
                    related_name='predictive_tracking'
                )),
            ],
            options={
                'db_table': 'noc_predictive_alert_tracking',
                'ordering': ['-predicted_at'],
            },
        ),

        # Indexes for PredictiveAlertTracking
        migrations.AddIndex(
            model_name='predictivealerttracking',
            index=models.Index(
                fields=['tenant', 'prediction_type', '-predicted_at'],
                name='noc_pred_type_date'
            ),
        ),
        migrations.AddIndex(
            model_name='predictivealerttracking',
            index=models.Index(
                fields=['validation_deadline', 'actual_outcome'],
                name='noc_pred_validation'
            ),
        ),
        migrations.AddIndex(
            model_name='predictivealerttracking',
            index=models.Index(
                fields=['entity_type', 'entity_id'],
                name='noc_pred_entity'
            ),
        ),
    ]
