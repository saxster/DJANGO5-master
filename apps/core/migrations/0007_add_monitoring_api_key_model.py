"""
Migration: Add Monitoring API Key Models

Creates tables for monitoring API key authentication system
that replaces @csrf_exempt on monitoring endpoints.

Security: Rule #3 Alternative Protection - API key authentication
Date: 2025-09-27
"""

from django.conf import settings
from django.db import migrations, models
import django.contrib.postgres.fields
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_add_initial_deprecation_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MonitoringAPIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text="Descriptive name (e.g., 'Prometheus Production', 'Grafana Dashboard')", max_length=100)),
                ('description', models.TextField(blank=True, help_text='Purpose and usage notes for this API key')),
                ('key_hash', models.CharField(db_index=True, help_text='SHA-256 hash of the API key', max_length=64, unique=True)),
                ('monitoring_system', models.CharField(choices=[('prometheus', 'Prometheus'), ('grafana', 'Grafana'), ('datadog', 'Datadog'), ('new_relic', 'New Relic'), ('cloudwatch', 'AWS CloudWatch'), ('stackdriver', 'Google Cloud Monitoring'), ('custom', 'Custom Monitoring System')], default='custom', help_text='Type of monitoring system using this key', max_length=50)),
                ('permissions', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(choices=[('health', 'Health Check Access'), ('metrics', 'Metrics Access'), ('performance', 'Performance Data Access'), ('alerts', 'Alerts Access'), ('dashboard', 'Dashboard Data Access'), ('admin', 'Full Monitoring Admin Access')], max_length=50), default=list, help_text='List of monitoring permissions granted to this key', size=None)),
                ('allowed_ips', django.contrib.postgres.fields.ArrayField(base_field=models.GenericIPAddressField(), blank=True, help_text='Whitelisted IP addresses (null = all IPs allowed)', null=True, size=None)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this API key is currently active')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this API key was created')),
                ('expires_at', models.DateTimeField(blank=True, help_text='When this API key expires (null = never expires)', null=True)),
                ('last_used_at', models.DateTimeField(blank=True, help_text='Last time this API key was used', null=True)),
                ('usage_count', models.IntegerField(default=0, help_text='Total number of times this key has been used')),
                ('rotation_schedule', models.CharField(choices=[('never', 'Never Rotate'), ('monthly', 'Monthly Rotation'), ('quarterly', 'Quarterly Rotation'), ('yearly', 'Yearly Rotation')], default='quarterly', help_text='Automatic rotation schedule', max_length=20)),
                ('next_rotation_at', models.DateTimeField(blank=True, help_text='When this key should be rotated next', null=True)),
                ('rotation_grace_period_hours', models.IntegerField(default=168, help_text='Hours to keep old key valid after rotation (default: 1 week)')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional metadata (contact info, escalation procedures, etc.)')),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created this API key', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_monitoring_keys', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Monitoring API Key',
                'verbose_name_plural': 'Monitoring API Keys',
                'db_table': 'monitoring_api_keys',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MonitoringAPIAccessLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.CharField(help_text='Endpoint accessed', max_length=200)),
                ('method', models.CharField(help_text='HTTP method used', max_length=10)),
                ('ip_address', models.GenericIPAddressField(help_text='IP address of the request')),
                ('user_agent', models.TextField(blank=True, help_text='User agent string')),
                ('response_status', models.IntegerField(help_text='HTTP response status code')),
                ('response_time_ms', models.IntegerField(help_text='Response time in milliseconds')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When the access occurred')),
                ('correlation_id', models.CharField(blank=True, help_text='Request correlation ID for tracing', max_length=36)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional request metadata')),
                ('api_key', models.ForeignKey(help_text='The monitoring API key used', on_delete=django.db.models.deletion.CASCADE, related_name='access_logs', to='core.monitoringapikey')),
            ],
            options={
                'verbose_name': 'Monitoring API Access Log',
                'verbose_name_plural': 'Monitoring API Access Logs',
                'db_table': 'monitoring_api_access_logs',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='monitoringapikey',
            index=models.Index(fields=['key_hash'], name='monitoring_key_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapikey',
            index=models.Index(fields=['is_active', 'expires_at'], name='monitoring_active_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapikey',
            index=models.Index(fields=['next_rotation_at'], name='monitoring_rotation_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapikey',
            index=models.Index(fields=['monitoring_system'], name='monitoring_system_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapiaccesslog',
            index=models.Index(fields=['timestamp'], name='monitoring_log_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapiaccesslog',
            index=models.Index(fields=['api_key', 'timestamp'], name='monitoring_log_key_time_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapiaccesslog',
            index=models.Index(fields=['endpoint', 'timestamp'], name='monitoring_log_endpoint_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapiaccesslog',
            index=models.Index(fields=['ip_address', 'timestamp'], name='monitoring_log_ip_idx'),
        ),
        migrations.AddIndex(
            model_name='monitoringapiaccesslog',
            index=models.Index(fields=['response_status'], name='monitoring_log_status_idx'),
        ),
    ]