"""
Migration: Add inference metrics to ModelPerformanceMetrics

Closes Recommendation #8 gap (observability) by adding:
- Average inference latency tracking
- P95 latency tracking
- Decision count tracking (total, automated, manual review)

Part of comprehensive gap closure
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ml', '0002_modelperformancemetrics'),
    ]

    operations = [
        migrations.AddField(
            model_name='modelperformancemetrics',
            name='avg_inference_latency_ms',
            field=models.FloatField(
                blank=True,
                help_text='Average inference latency in milliseconds',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='modelperformancemetrics',
            name='p95_inference_latency_ms',
            field=models.FloatField(
                blank=True,
                help_text='95th percentile inference latency (ms)',
                null=True
            ),
        ),
        migrations.AddField(
            model_name='modelperformancemetrics',
            name='total_decisions',
            field=models.IntegerField(
                default=0,
                help_text='Total decisions made (tickets + alerts)'
            ),
        ),
        migrations.AddField(
            model_name='modelperformancemetrics',
            name='automated_decisions',
            field=models.IntegerField(
                default=0,
                help_text='Decisions made automatically (no human review)'
            ),
        ),
        migrations.AddField(
            model_name='modelperformancemetrics',
            name='manual_review_decisions',
            field=models.IntegerField(
                default=0,
                help_text='Decisions requiring manual review'
            ),
        ),
    ]
