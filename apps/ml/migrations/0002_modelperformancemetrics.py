"""
Migration: Add ModelPerformanceMetrics model

Part of Phase 2: Model Drift Monitoring & Auto-Retraining
Enables daily performance tracking and drift detection.

Generated manually for feature/phase2-drift-monitoring
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ml', '0001_add_confidence_intervals_to_predictionlog'),
        ('tenants', '0001_initial'),  # Assuming tenants app exists
    ]

    operations = [
        migrations.CreateModel(
            name='ModelPerformanceMetrics',
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
                        choices=[
                            ('conflict_predictor', 'Conflict Predictor'),
                            ('fraud_detector', 'Fraud Detector')
                        ],
                        db_index=True,
                        help_text='Type of ML model',
                        max_length=50
                    )
                ),
                (
                    'model_version',
                    models.CharField(
                        help_text='Model version identifier (e.g., 1.0, 2.5)',
                        max_length=50
                    )
                ),
                (
                    'metric_date',
                    models.DateField(
                        db_index=True,
                        help_text='Date of metrics (e.g., 2025-11-01 for Nov 1 predictions)'
                    )
                ),
                (
                    'window_start',
                    models.DateTimeField(
                        help_text='Start of aggregation window (inclusive)'
                    )
                ),
                (
                    'window_end',
                    models.DateTimeField(
                        help_text='End of aggregation window (inclusive)'
                    )
                ),
                (
                    'total_predictions',
                    models.IntegerField(
                        default=0,
                        help_text='Total predictions made in window'
                    )
                ),
                (
                    'predictions_with_outcomes',
                    models.IntegerField(
                        default=0,
                        help_text='Predictions with ground truth (actual outcome known)'
                    )
                ),
                (
                    'accuracy',
                    models.FloatField(
                        blank=True,
                        help_text='Accuracy (correct predictions / total predictions)',
                        null=True
                    )
                ),
                (
                    'precision',
                    models.FloatField(
                        blank=True,
                        help_text='Precision (true positives / predicted positives)',
                        null=True
                    )
                ),
                (
                    'recall',
                    models.FloatField(
                        blank=True,
                        help_text='Recall (true positives / actual positives)',
                        null=True
                    )
                ),
                (
                    'f1_score',
                    models.FloatField(
                        blank=True,
                        help_text='F1 score (harmonic mean of precision and recall)',
                        null=True
                    )
                ),
                (
                    'pr_auc',
                    models.FloatField(
                        blank=True,
                        help_text='Precision-Recall AUC (for imbalanced datasets)',
                        null=True
                    )
                ),
                ('true_positives', models.IntegerField(default=0)),
                ('false_positives', models.IntegerField(default=0)),
                ('true_negatives', models.IntegerField(default=0)),
                ('false_negatives', models.IntegerField(default=0)),
                (
                    'avg_confidence_interval_width',
                    models.FloatField(
                        blank=True,
                        help_text='Average CI width (narrow = high confidence)',
                        null=True
                    )
                ),
                (
                    'narrow_interval_percentage',
                    models.FloatField(
                        blank=True,
                        help_text='Percentage of predictions with width < 0.2',
                        null=True
                    )
                ),
                (
                    'avg_calibration_score',
                    models.FloatField(
                        blank=True,
                        help_text='Average conformal prediction calibration quality',
                        null=True
                    )
                ),
                (
                    'statistical_drift_pvalue',
                    models.FloatField(
                        blank=True,
                        help_text='KS test p-value (< 0.01 indicates drift)',
                        null=True
                    )
                ),
                (
                    'performance_delta_from_baseline',
                    models.FloatField(
                        blank=True,
                        help_text='Accuracy change vs baseline (negative = degradation)',
                        null=True
                    )
                ),
                (
                    'is_degraded',
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text='True if performance dropped > 10%'
                    )
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'tenant',
                    models.ForeignKey(
                        blank=True,
                        help_text='Tenant (for fraud models) or null (for global models)',
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to='tenants.tenant'
                    )
                ),
            ],
            options={
                'db_table': 'ml_model_performance_metrics',
                'verbose_name': 'Model Performance Metric',
                'verbose_name_plural': 'Model Performance Metrics',
                'ordering': ['-metric_date'],
            },
        ),
        migrations.AddIndex(
            model_name='modelperformancemetrics',
            index=models.Index(
                fields=['model_type', '-metric_date'],
                name='perf_model_date_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='modelperformancemetrics',
            index=models.Index(
                fields=['model_version', '-metric_date'],
                name='perf_version_date_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='modelperformancemetrics',
            index=models.Index(
                fields=['is_degraded', '-metric_date'],
                name='perf_degraded_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='modelperformancemetrics',
            index=models.Index(
                fields=['tenant', 'model_type', '-metric_date'],
                name='perf_tenant_model_idx'
            ),
        ),
        migrations.AlterUniqueTogether(
            name='modelperformancemetrics',
            unique_together={('model_type', 'model_version', 'tenant', 'metric_date')},
        ),
    ]
