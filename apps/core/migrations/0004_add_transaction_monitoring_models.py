"""
Migration for Transaction Monitoring Models

Adds tables for tracking transaction health, failures, and performance metrics.

Complies with: .claude/rules.md - Rule #17: Transaction Management
"""

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_file_upload_audit_log'),
    ]

    operations = [
        migrations.CreateModel(
            name='TransactionFailureLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_name', models.CharField(db_index=True, max_length=255)),
                ('view_name', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('error_type', models.CharField(db_index=True, max_length=100)),
                ('error_message', models.TextField()),
                ('error_traceback', models.TextField(blank=True, null=True)),
                ('correlation_id', models.CharField(blank=True, db_index=True, max_length=36, null=True)),
                ('user_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('request_path', models.CharField(blank=True, max_length=500, null=True)),
                ('request_method', models.CharField(blank=True, max_length=10, null=True)),
                ('database_alias', models.CharField(default='default', max_length=50)),
                ('transaction_id', models.CharField(blank=True, max_length=100, null=True)),
                ('occurred_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('is_resolved', models.BooleanField(db_index=True, default=False)),
                ('resolution_notes', models.TextField(blank=True, null=True)),
                ('additional_context', models.JSONField(blank=True, default=dict)),
                ('tenant_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('client_id', models.IntegerField(blank=True, db_index=True, null=True)),
            ],
            options={
                'db_table': 'transaction_failure_log',
                'ordering': ['-occurred_at'],
            },
        ),
        migrations.CreateModel(
            name='TransactionMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation_name', models.CharField(db_index=True, max_length=255)),
                ('metric_date', models.DateField(db_index=True, default=django.utils.timezone.now)),
                ('hour_of_day', models.IntegerField(blank=True, null=True)),
                ('total_attempts', models.IntegerField(default=0)),
                ('successful_commits', models.IntegerField(default=0)),
                ('failed_commits', models.IntegerField(default=0)),
                ('rollbacks', models.IntegerField(default=0)),
                ('avg_duration_ms', models.FloatField(blank=True, null=True)),
                ('max_duration_ms', models.FloatField(blank=True, null=True)),
                ('min_duration_ms', models.FloatField(blank=True, null=True)),
                ('integrity_errors', models.IntegerField(default=0)),
                ('validation_errors', models.IntegerField(default=0)),
                ('deadlocks', models.IntegerField(default=0)),
                ('timeouts', models.IntegerField(default=0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('tenant_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('client_id', models.IntegerField(blank=True, db_index=True, null=True)),
            ],
            options={
                'db_table': 'transaction_metrics',
                'ordering': ['-metric_date', '-hour_of_day'],
            },
        ),
        migrations.CreateModel(
            name='SagaExecutionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('saga_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('saga_name', models.CharField(max_length=255)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('executing', 'Executing'),
                        ('committed', 'Committed'),
                        ('failed', 'Failed'),
                        ('compensating', 'Compensating'),
                        ('compensated', 'Compensated'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20
                )),
                ('total_steps', models.IntegerField(default=0)),
                ('executed_steps', models.IntegerField(default=0)),
                ('compensated_steps', models.IntegerField(default=0)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('duration_ms', models.FloatField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('execution_details', models.JSONField(default=dict)),
                ('user_id', models.IntegerField(blank=True, null=True)),
                ('tenant_id', models.IntegerField(blank=True, db_index=True, null=True)),
                ('client_id', models.IntegerField(blank=True, db_index=True, null=True)),
            ],
            options={
                'db_table': 'saga_execution_log',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='TransactionHealthCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('check_timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('total_transactions_last_hour', models.IntegerField(default=0)),
                ('failed_transactions_last_hour', models.IntegerField(default=0)),
                ('avg_transaction_duration_ms', models.FloatField(blank=True, null=True)),
                ('deadlock_count_last_hour', models.IntegerField(default=0)),
                ('timeout_count_last_hour', models.IntegerField(default=0)),
                ('health_status', models.CharField(
                    choices=[
                        ('healthy', 'Healthy'),
                        ('degraded', 'Degraded'),
                        ('critical', 'Critical'),
                    ],
                    default='healthy',
                    max_length=20
                )),
                ('alerts_triggered', models.JSONField(default=list)),
                ('recommendations', models.JSONField(default=list)),
            ],
            options={
                'db_table': 'transaction_health_check',
                'ordering': ['-check_timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='transactionfailurelog',
            index=models.Index(fields=['operation_name', 'occurred_at'], name='txn_fail_op_occurred_idx'),
        ),
        migrations.AddIndex(
            model_name='transactionfailurelog',
            index=models.Index(fields=['error_type', 'is_resolved'], name='txn_fail_err_resolved_idx'),
        ),
        migrations.AddIndex(
            model_name='transactionfailurelog',
            index=models.Index(fields=['user_id', 'occurred_at'], name='txn_fail_user_occurred_idx'),
        ),
        migrations.AddIndex(
            model_name='transactionmetrics',
            index=models.Index(fields=['operation_name', 'metric_date'], name='txn_metrics_op_date_idx'),
        ),
        migrations.AddIndex(
            model_name='transactionmetrics',
            index=models.Index(fields=['metric_date', 'hour_of_day'], name='txn_metrics_date_hour_idx'),
        ),
        migrations.AddIndex(
            model_name='sagaexecutionlog',
            index=models.Index(fields=['status', 'started_at'], name='saga_status_started_idx'),
        ),
        migrations.AddIndex(
            model_name='sagaexecutionlog',
            index=models.Index(fields=['saga_name', 'status'], name='saga_name_status_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='transactionmetrics',
            unique_together={('operation_name', 'metric_date', 'hour_of_day', 'tenant_id', 'client_id')},
        ),
    ]