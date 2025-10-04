"""
Add Query Execution Plan Monitoring Models

Creates models for storing and analyzing PostgreSQL query execution plans:
- QueryExecutionPlan: Stores EXPLAIN ANALYZE output with performance metrics
- PlanRegressionAlert: Alerts for detected plan performance regressions

Features:
- Execution plan storage and versioning
- Performance regression detection
- Plan structure comparison
- Optimization opportunity identification

Benefits:
- Identify when query plans change and cause performance issues
- Track execution plan history over time
- Automatic detection of plan regressions
- Detailed performance analysis capabilities

Compliance: Rule #7 (Migration < 200 lines), Enterprise monitoring standards
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_enable_pg_stat_statements'),
    ]

    operations = [
        # Query Execution Plan model
        migrations.CreateModel(
            name='QueryExecutionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query_hash', models.BigIntegerField(db_index=True, help_text='PostgreSQL query hash (queryid from pg_stat_statements)')),
                ('plan_hash', models.CharField(db_index=True, help_text='Hash of the execution plan structure', max_length=64)),
                ('query_text', models.TextField(help_text='Full query text (truncated if necessary)')),
                ('execution_plan', models.JSONField(help_text='Full EXPLAIN ANALYZE output as JSON')),
                ('plan_summary', models.TextField(help_text='Human-readable plan summary')),
                ('execution_time', models.DecimalField(decimal_places=2, help_text='Actual execution time in milliseconds', max_digits=10)),
                ('planning_time', models.DecimalField(decimal_places=2, help_text='Query planning time in milliseconds', max_digits=10)),
                ('total_cost', models.DecimalField(decimal_places=2, help_text='PostgreSQL cost estimate', max_digits=15)),
                ('rows_returned', models.BigIntegerField(default=0, help_text='Number of rows returned')),
                ('shared_hit_blocks', models.BigIntegerField(default=0, help_text='Shared buffer blocks hit')),
                ('shared_read_blocks', models.BigIntegerField(default=0, help_text='Shared buffer blocks read')),
                ('temp_read_blocks', models.BigIntegerField(default=0, help_text='Temporary blocks read')),
                ('temp_written_blocks', models.BigIntegerField(default=0, help_text='Temporary blocks written')),
                ('captured_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, help_text='When this plan was captured')),
                ('capture_method', models.CharField(choices=[('automatic', 'Automatic (slow query detection)'), ('manual', 'Manual capture'), ('scheduled', 'Scheduled analysis')], default='automatic', help_text='How this plan was captured', max_length=20)),
                ('optimization_opportunities', models.JSONField(blank=True, default=list, help_text='List of identified optimization opportunities')),
                ('regression_detected', models.BooleanField(db_index=True, default=False, help_text='Whether this plan represents a performance regression')),
                ('captured_by', models.ForeignKey(blank=True, help_text='User who captured this plan (if manual)', null=True, on_delete=django.db.models.deletion.SET_NULL, to='peoples.people')),
            ],
            options={
                'verbose_name': 'Query Execution Plan',
                'verbose_name_plural': 'Query Execution Plans',
                'db_table': 'query_execution_plans',
                'ordering': ['-captured_at'],
            },
        ),

        # Plan Regression Alert model
        migrations.CreateModel(
            name='PlanRegressionAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query_hash', models.BigIntegerField(db_index=True, help_text='Query hash that experienced regression')),
                ('performance_degradation', models.DecimalField(decimal_places=2, help_text='Performance degradation percentage', max_digits=8)),
                ('regression_type', models.CharField(choices=[('execution_time', 'Execution Time Regression'), ('plan_change', 'Plan Structure Change'), ('index_not_used', 'Index No Longer Used'), ('sequential_scan', 'Sequential Scan Introduced'), ('temp_storage', 'Temporary Storage Usage')], help_text='Type of regression detected', max_length=50)),
                ('detected_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, help_text='When the regression was detected')),
                ('severity', models.CharField(choices=[('info', 'Informational'), ('warning', 'Warning - Performance Degraded'), ('critical', 'Critical - Severe Regression')], db_index=True, default='warning', help_text='Regression severity level', max_length=20)),
                ('status', models.CharField(choices=[('new', 'New'), ('acknowledged', 'Acknowledged'), ('investigating', 'Under Investigation'), ('resolved', 'Resolved'), ('false_positive', 'False Positive')], db_index=True, default='new', help_text='Current alert status', max_length=20)),
                ('acknowledged_at', models.DateTimeField(blank=True, help_text='When this alert was acknowledged', null=True)),
                ('resolution_notes', models.TextField(blank=True, help_text='Notes about investigation and resolution')),
                ('acknowledged_by', models.ForeignKey(blank=True, help_text='User who acknowledged this alert', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acknowledged_plan_regressions', to='peoples.people')),
                ('baseline_plan', models.ForeignKey(help_text='Previous (baseline) execution plan', on_delete=django.db.models.deletion.CASCADE, related_name='regression_alerts_baseline', to='core.queryexecutionplan')),
                ('current_plan', models.ForeignKey(help_text='Current (regressed) execution plan', on_delete=django.db.models.deletion.CASCADE, related_name='regression_alerts_current', to='core.queryexecutionplan')),
            ],
            options={
                'verbose_name': 'Plan Regression Alert',
                'verbose_name_plural': 'Plan Regression Alerts',
                'db_table': 'plan_regression_alerts',
                'ordering': ['-detected_at'],
            },
        ),

        # Add indexes for QueryExecutionPlan
        migrations.AddIndex(
            model_name='queryexecutionplan',
            index=models.Index(fields=['query_hash', 'captured_at'], name='query_execution_plans_query_hash_captured_at_idx'),
        ),
        migrations.AddIndex(
            model_name='queryexecutionplan',
            index=models.Index(fields=['plan_hash'], name='query_execution_plans_plan_hash_idx'),
        ),
        migrations.AddIndex(
            model_name='queryexecutionplan',
            index=models.Index(fields=['execution_time'], name='query_execution_plans_execution_time_idx'),
        ),
        migrations.AddIndex(
            model_name='queryexecutionplan',
            index=models.Index(fields=['regression_detected', 'captured_at'], name='query_execution_plans_regression_detected_captured_at_idx'),
        ),

        # Add indexes for PlanRegressionAlert
        migrations.AddIndex(
            model_name='planregressionalert',
            index=models.Index(fields=['query_hash', 'detected_at'], name='plan_regression_alerts_query_hash_detected_at_idx'),
        ),
        migrations.AddIndex(
            model_name='planregressionalert',
            index=models.Index(fields=['status', 'severity'], name='plan_regression_alerts_status_severity_idx'),
        ),
        migrations.AddIndex(
            model_name='planregressionalert',
            index=models.Index(fields=['regression_type', 'status'], name='plan_regression_alerts_regression_type_status_idx'),
        ),
    ]