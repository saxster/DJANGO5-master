"""
Migration for health monitoring models.
Adds HealthCheckLog, ServiceAvailability, and AlertThreshold models.
"""

from django.db import migrations, models
import django.core.validators
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_transaction_monitoring_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='HealthCheckLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('check_name', models.CharField(db_index=True, max_length=100)),
                ('status', models.CharField(choices=[('healthy', 'Healthy'), ('degraded', 'Degraded'), ('error', 'Error')], db_index=True, max_length=20)),
                ('message', models.TextField()),
                ('details', models.JSONField(blank=True, default=dict)),
                ('duration_ms', models.FloatField(validators=[django.core.validators.MinValueValidator(0)])),
                ('checked_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('correlation_id', models.UUIDField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Health Check Log',
                'verbose_name_plural': 'Health Check Logs',
                'db_table': 'core_health_check_log',
                'ordering': ['-checked_at'],
            },
        ),
        migrations.CreateModel(
            name='ServiceAvailability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_name', models.CharField(db_index=True, max_length=100, unique=True)),
                ('total_checks', models.IntegerField(default=0)),
                ('successful_checks', models.IntegerField(default=0)),
                ('failed_checks', models.IntegerField(default=0)),
                ('degraded_checks', models.IntegerField(default=0)),
                ('last_check_at', models.DateTimeField(blank=True, null=True)),
                ('last_success_at', models.DateTimeField(blank=True, null=True)),
                ('last_failure_at', models.DateTimeField(blank=True, null=True)),
                ('uptime_percentage', models.FloatField(default=100.0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Service Availability',
                'verbose_name_plural': 'Service Availabilities',
                'db_table': 'core_service_availability',
                'ordering': ['-uptime_percentage'],
            },
        ),
        migrations.CreateModel(
            name='AlertThreshold',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_type', models.CharField(choices=[('disk_usage', 'Disk Usage %'), ('memory_usage', 'Memory Usage %'), ('cpu_load', 'CPU Load'), ('response_time', 'Response Time (ms)'), ('error_rate', 'Error Rate %'), ('queue_depth', 'Queue Depth')], db_index=True, max_length=50)),
                ('alert_level', models.CharField(choices=[('warning', 'Warning'), ('critical', 'Critical')], max_length=20)),
                ('threshold_value', models.FloatField()),
                ('enabled', models.BooleanField(default=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Alert Threshold',
                'verbose_name_plural': 'Alert Thresholds',
                'db_table': 'core_alert_threshold',
                'ordering': ['metric_type', 'alert_level'],
            },
        ),
        migrations.AddIndex(
            model_name='healthchecklog',
            index=models.Index(fields=['check_name', '-checked_at'], name='core_health_check_n_idx'),
        ),
        migrations.AddIndex(
            model_name='healthchecklog',
            index=models.Index(fields=['status', '-checked_at'], name='core_health_status_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='alertthreshold',
            unique_together={('metric_type', 'alert_level')},
        ),
    ]