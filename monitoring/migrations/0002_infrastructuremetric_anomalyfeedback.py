# Generated migration for InfrastructureMetric and AnomalyFeedback models

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InfrastructureMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created DateTime')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified DateTime')),
                ('timestamp', models.DateTimeField(db_index=True, help_text='Metric collection time')),
                ('metric_name', models.CharField(db_index=True, help_text='Name of the metric (cpu_percent, memory_percent, etc.)', max_length=100)),
                ('value', models.FloatField(help_text='Metric value')),
                ('tags', models.JSONField(default=dict, help_text='Tags for categorization (type, environment, host, etc.)')),
                ('metadata', models.JSONField(default=dict, help_text='Additional metric metadata (unit, percentile, etc.)')),
            ],
            options={
                'verbose_name': 'Infrastructure Metric',
                'verbose_name_plural': 'Infrastructure Metrics',
                'db_table': 'monitoring_infrastructure_metric',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='AnomalyFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created DateTime')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified DateTime')),
                ('metric_name', models.CharField(help_text='Name of the metric', max_length=100, unique=True)),
                ('false_positive_count', models.IntegerField(default=0, help_text='Number of false positive anomaly detections')),
                ('threshold_adjustment', models.FloatField(default=0.0, help_text='Current threshold adjustment factor (positive = more lenient)')),
                ('last_adjusted', models.DateTimeField(default=django.utils.timezone.now, help_text='Last time threshold was adjusted')),
            ],
            options={
                'verbose_name': 'Anomaly Feedback',
                'verbose_name_plural': 'Anomaly Feedback',
                'db_table': 'monitoring_anomaly_feedback',
                'ordering': ['-last_adjusted'],
            },
        ),
        migrations.AddIndex(
            model_name='infrastructuremetric',
            index=models.Index(fields=['metric_name', 'timestamp'], name='infra_metric_name_time'),
        ),
        migrations.AddIndex(
            model_name='infrastructuremetric',
            index=models.Index(fields=['timestamp', 'metric_name', 'value'], name='infra_time_name_value'),
        ),
        migrations.AddIndex(
            model_name='infrastructuremetric',
            index=models.Index(fields=['timestamp'], name='infra_timestamp'),
        ),
    ]
