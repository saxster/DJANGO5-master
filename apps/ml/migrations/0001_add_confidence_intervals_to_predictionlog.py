"""
Migration: Add confidence interval fields to PredictionLog

Part of Phase 1: Confidence Intervals & Uncertainty Quantification
Implements conformal prediction support for human-out-of-loop automation.

Generated manually for feature/ai-first-ops-enhancement
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ConflictPredictionModel',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID'
                    )
                ),
                ('version', models.CharField(max_length=50, unique=True)),
                ('algorithm', models.CharField(max_length=100)),
                (
                    'accuracy',
                    models.FloatField(help_text='Model accuracy score (ROC-AUC)')
                ),
                ('precision', models.FloatField(default=0.0)),
                ('recall', models.FloatField(default=0.0)),
                ('f1_score', models.FloatField(default=0.0)),
                ('trained_on_samples', models.IntegerField()),
                ('feature_count', models.IntegerField()),
                ('model_path', models.CharField(max_length=500)),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'ml_conflict_prediction_model',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PredictionLog',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID'
                    )
                ),
                (
                    'model_type',
                    models.CharField(
                        default='conflict_predictor',
                        help_text='Type of ML model (conflict_predictor, fraud_detector, etc.)',
                        max_length=50
                    )
                ),
                ('model_version', models.CharField(max_length=50)),
                (
                    'entity_type',
                    models.CharField(
                        help_text='Type of entity (sync_event, attendance, etc.)',
                        max_length=50
                    )
                ),
                ('entity_id', models.CharField(max_length=255, null=True)),
                ('predicted_conflict', models.BooleanField()),
                ('conflict_probability', models.FloatField()),
                (
                    'features_json',
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text='Features used for prediction'
                    )
                ),
                # Conformal prediction confidence intervals (Phase 1)
                (
                    'prediction_lower_bound',
                    models.FloatField(
                        blank=True,
                        null=True,
                        help_text='Lower bound of prediction interval (90% coverage)'
                    )
                ),
                (
                    'prediction_upper_bound',
                    models.FloatField(
                        blank=True,
                        null=True,
                        help_text='Upper bound of prediction interval (90% coverage)'
                    )
                ),
                (
                    'confidence_interval_width',
                    models.FloatField(
                        blank=True,
                        null=True,
                        help_text='Width of confidence interval (upper - lower)'
                    )
                ),
                (
                    'calibration_score',
                    models.FloatField(
                        blank=True,
                        null=True,
                        help_text='Conformal predictor calibration quality (0-1)'
                    )
                ),
                (
                    'actual_conflict_occurred',
                    models.BooleanField(blank=True, null=True)
                ),
                (
                    'prediction_correct',
                    models.BooleanField(blank=True, null=True)
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'ml_prediction_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='predictionlog',
            index=models.Index(
                fields=['model_type', 'created_at'],
                name='ml_predicti_model_t_74a90b_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='predictionlog',
            index=models.Index(
                fields=['predicted_conflict'],
                name='ml_predicti_predict_f07e1a_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='predictionlog',
            index=models.Index(
                fields=['actual_conflict_occurred'],
                name='ml_predicti_actual__e62a6e_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='predictionlog',
            index=models.Index(
                fields=['confidence_interval_width'],
                name='ml_pred_log_ci_width_idx'
            ),
        ),
    ]
