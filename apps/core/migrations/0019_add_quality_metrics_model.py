# Generated migration for QualityMetric model - Phase 7

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_add_task_idempotency_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='QualityMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When this metric was recorded')),
                ('code_quality_score', models.FloatField(default=0, help_text='Overall code quality score (0-100)', validators=[models.validators.MinValueValidator(0), models.validators.MaxValueValidator(100)])),
                ('test_coverage', models.FloatField(default=0, help_text='Test code coverage percentage', validators=[models.validators.MinValueValidator(0), models.validators.MaxValueValidator(100)])),
                ('complexity_score', models.FloatField(default=0, help_text='Average cyclomatic complexity')),
                ('security_issues', models.IntegerField(default=0, help_text='Total number of security issues found')),
                ('security_critical', models.IntegerField(default=0, help_text='Count of critical severity security issues')),
                ('security_high', models.IntegerField(default=0, help_text='Count of high severity security issues')),
                ('file_violations', models.IntegerField(default=0, help_text='Number of file size compliance violations')),
                ('overall_grade', models.CharField(
                    choices=[('A', 'Excellent'), ('B', 'Good'), ('C', 'Acceptable'), ('D', 'Poor'), ('F', 'Failing')],
                    default='C',
                    help_text='Overall quality grade (A-F)',
                    max_length=1
                )),
                ('overall_score', models.FloatField(
                    default=0,
                    help_text='Overall quality score (0-100)',
                    validators=[models.validators.MinValueValidator(0), models.validators.MaxValueValidator(100)]
                )),
                ('report_json', models.JSONField(default=dict, help_text='Full report data as JSON')),
                ('is_weekly', models.BooleanField(default=False, help_text='Whether this is a weekly (vs daily) snapshot')),
            ],
            options={
                'verbose_name_plural': 'Quality Metrics',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='qualitymetric',
            index=models.Index(fields=['timestamp'], name='core_quality_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='qualitymetric',
            index=models.Index(fields=['-timestamp'], name='core_quality_timestamp_desc_idx'),
        ),
        migrations.AddIndex(
            model_name='qualitymetric',
            index=models.Index(fields=['is_weekly', '-timestamp'], name='core_quality_weekly_idx'),
        ),
    ]
