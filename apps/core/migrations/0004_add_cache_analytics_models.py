"""
Migration to add cache analytics models for TTL monitoring.

Creates CacheMetrics and CacheAnomalyLog models for time-series analysis.
"""

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_file_upload_audit_log'),
    ]

    operations = [
        migrations.CreateModel(
            name='CacheMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pattern_name', models.CharField(db_index=True, max_length=100)),
                ('pattern_key', models.CharField(max_length=200)),
                ('timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('interval', models.CharField(
                    choices=[('hourly', 'Hourly'), ('daily', 'Daily'), ('weekly', 'Weekly')],
                    db_index=True,
                    default='hourly',
                    max_length=20
                )),
                ('total_hits', models.BigIntegerField(default=0)),
                ('total_misses', models.BigIntegerField(default=0)),
                ('hit_ratio', models.DecimalField(decimal_places=4, default=0, max_digits=5)),
                ('avg_ttl_at_hit', models.IntegerField(default=0, help_text='Average TTL remaining when cache hit occurs')),
                ('configured_ttl', models.IntegerField(default=0)),
                ('memory_bytes', models.BigIntegerField(default=0, help_text='Estimated memory usage for pattern')),
                ('key_count', models.IntegerField(default=0, help_text='Number of active keys for pattern')),
            ],
            options={
                'db_table': 'core_cache_metrics',
                'verbose_name': 'Cache Metric',
                'verbose_name_plural': 'Cache Metrics',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='CacheAnomalyLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pattern_name', models.CharField(db_index=True, max_length=100)),
                ('anomaly_type', models.CharField(
                    choices=[
                        ('low_hit_ratio', 'Low Hit Ratio'),
                        ('high_miss_rate', 'High Miss Rate'),
                        ('memory_spike', 'Memory Usage Spike'),
                        ('ttl_mismatch', 'TTL Configuration Mismatch'),
                        ('key_explosion', 'Excessive Key Count'),
                    ],
                    db_index=True,
                    max_length=50
                )),
                ('detected_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('severity', models.CharField(
                    choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
                    default='medium',
                    max_length=20
                )),
                ('hit_ratio_at_detection', models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
                ('description', models.TextField()),
                ('recommendation', models.TextField(blank=True)),
                ('resolved', models.BooleanField(db_index=True, default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('resolution_notes', models.TextField(blank=True)),
            ],
            options={
                'db_table': 'core_cache_anomaly_log',
                'verbose_name': 'Cache Anomaly',
                'verbose_name_plural': 'Cache Anomalies',
                'ordering': ['-detected_at'],
            },
        ),
        migrations.AddIndex(
            model_name='cachemetrics',
            index=models.Index(fields=['pattern_name', '-timestamp'], name='idx_cache_pattern_time'),
        ),
        migrations.AddIndex(
            model_name='cachemetrics',
            index=models.Index(fields=['interval', '-timestamp'], name='idx_cache_interval_time'),
        ),
        migrations.AddIndex(
            model_name='cachemetrics',
            index=models.Index(fields=['-hit_ratio'], name='idx_cache_hit_ratio'),
        ),
        migrations.AddConstraint(
            model_name='cachemetrics',
            constraint=models.CheckConstraint(
                check=models.Q(('hit_ratio__gte', 0), ('hit_ratio__lte', 1)),
                name='cache_hit_ratio_bounds'
            ),
        ),
        migrations.AddConstraint(
            model_name='cachemetrics',
            constraint=models.CheckConstraint(
                check=models.Q(('total_hits__gte', 0), ('total_misses__gte', 0)),
                name='cache_counts_positive'
            ),
        ),
        migrations.AddIndex(
            model_name='cacheanomalylog',
            index=models.Index(fields=['pattern_name', '-detected_at'], name='idx_anomaly_pattern_time'),
        ),
        migrations.AddIndex(
            model_name='cacheanomalylog',
            index=models.Index(fields=['resolved', '-detected_at'], name='idx_anomaly_resolved'),
        ),
        migrations.AddIndex(
            model_name='cacheanomalylog',
            index=models.Index(fields=['severity', '-detected_at'], name='idx_anomaly_severity'),
        ),
    ]