"""
Migration to add API deprecation tracking models.
Supports RFC 9745 (Deprecation Header) and RFC 8594 (Sunset Header) standards.
"""

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_cache_analytics_models'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIDeprecation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('endpoint_pattern', models.CharField(
                    help_text='URL pattern or GraphQL field path (e.g., /api/v1/people/ or Mutation.upload_attachment)',
                    max_length=255
                )),
                ('api_type', models.CharField(
                    choices=[
                        ('rest', 'REST API'),
                        ('graphql_query', 'GraphQL Query'),
                        ('graphql_mutation', 'GraphQL Mutation'),
                        ('graphql_field', 'GraphQL Field')
                    ],
                    default='rest',
                    max_length=20
                )),
                ('version_deprecated', models.CharField(help_text='Version when deprecated (e.g., v1.5)', max_length=10)),
                ('version_removed', models.CharField(
                    blank=True,
                    help_text='Version when removed (e.g., v2.0)',
                    max_length=10,
                    null=True
                )),
                ('deprecated_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('sunset_date', models.DateTimeField(
                    blank=True,
                    help_text='Date when endpoint will be removed (RFC 8594)',
                    null=True
                )),
                ('status', models.CharField(
                    choices=[
                        ('active', 'Active - No deprecation'),
                        ('deprecated', 'Deprecated - Still functional'),
                        ('sunset_warning', 'Sunset Warning - Removal imminent'),
                        ('removed', 'Removed - No longer available')
                    ],
                    default='active',
                    max_length=20
                )),
                ('replacement_endpoint', models.CharField(
                    blank=True,
                    help_text='Recommended replacement endpoint',
                    max_length=255,
                    null=True
                )),
                ('migration_url', models.URLField(
                    blank=True,
                    help_text='Link to migration documentation',
                    max_length=500,
                    null=True
                )),
                ('deprecation_reason', models.TextField(help_text='Why this endpoint was deprecated')),
                ('notify_on_usage', models.BooleanField(
                    default=True,
                    help_text='Send alerts when deprecated endpoint is used'
                )),
                ('tenant', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='tenants.tenant'
                )),
            ],
            options={
                'verbose_name': 'API Deprecation',
                'verbose_name_plural': 'API Deprecations',
                'db_table': 'api_deprecation',
            },
        ),
        migrations.CreateModel(
            name='APIDeprecationUsage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user_id', models.IntegerField(blank=True, null=True)),
                ('client_version', models.CharField(
                    blank=True,
                    help_text='Mobile app or SDK version',
                    max_length=50,
                    null=True
                )),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=500, null=True)),
                ('response_time_ms', models.IntegerField(blank=True, null=True)),
                ('deprecation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='usage_logs',
                    to='core.apideprecation'
                )),
            ],
            options={
                'verbose_name': 'API Deprecation Usage',
                'verbose_name_plural': 'API Deprecation Usage Logs',
                'db_table': 'api_deprecation_usage',
            },
        ),
        migrations.AddIndex(
            model_name='apideprecation',
            index=models.Index(fields=['endpoint_pattern', 'status'], name='api_depreca_endpoin_idx'),
        ),
        migrations.AddIndex(
            model_name='apideprecation',
            index=models.Index(fields=['sunset_date'], name='api_depreca_sunset__idx'),
        ),
        migrations.AddIndex(
            model_name='apideprecation',
            index=models.Index(fields=['api_type', 'status'], name='api_depreca_api_typ_idx'),
        ),
        migrations.AddIndex(
            model_name='apideprecationusage',
            index=models.Index(fields=['deprecation', 'timestamp'], name='api_depreca_depreca_idx'),
        ),
        migrations.AddIndex(
            model_name='apideprecationusage',
            index=models.Index(fields=['client_version'], name='api_depreca_client__idx'),
        ),
        migrations.AddIndex(
            model_name='apideprecationusage',
            index=models.Index(fields=['-timestamp'], name='api_depreca_timesta_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='apideprecation',
            unique_together={('endpoint_pattern', 'version_deprecated')},
        ),
    ]