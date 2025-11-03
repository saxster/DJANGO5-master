"""
Migration: Add SHAP explainability fields

Phase 4, Feature 1: Instance-level ML explanations

Adds shap_values (JSON) and explanation_text (human-readable)
to both PredictionLog and FraudPredictionLog models.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ml', '0003_add_inference_metrics_to_performance'),
        ('noc', '0003_frauddetectionmodel'),
    ]

    operations = [
        # PredictionLog
        migrations.AddField(
            model_name='predictionlog',
            name='shap_values',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='SHAP feature contributions for this prediction',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='predictionlog',
            name='explanation_text',
            field=models.TextField(
                blank=True,
                help_text='Human-readable explanation (top contributing features)'
            ),
        ),
    ]
