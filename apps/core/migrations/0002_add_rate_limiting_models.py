"""
Migration to add rate limiting models.

Implements Rule #9 - Comprehensive Rate Limiting
CVSS 7.2 vulnerability remediation
"""

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_add_encryption_key_metadata'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RateLimitBlockedIP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(
                    help_text='Blocked IP address (IPv4 or IPv6)',
                    unique=True,
                    validators=[django.core.validators.validate_ipv46_address]
                )),
                ('blocked_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='When the IP was blocked'
                )),
                ('blocked_until', models.DateTimeField(
                    help_text='When the block expires'
                )),
                ('violation_count', models.PositiveIntegerField(
                    default=0,
                    help_text='Total number of violations that triggered the block'
                )),
                ('endpoint_type', models.CharField(
                    default='unknown',
                    help_text='Type of endpoint that triggered the block (admin, api, etc.)',
                    max_length=50
                )),
                ('last_violation_path', models.CharField(
                    blank=True,
                    help_text='Last URL path that triggered a violation',
                    max_length=255
                )),
                ('reason', models.TextField(
                    blank=True,
                    help_text='Reason for blocking (auto-generated)'
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Whether the block is currently active'
                )),
                ('notes', models.TextField(
                    blank=True,
                    help_text='Admin notes about this block'
                )),
            ],
            options={
                'db_table': 'core_rate_limit_blocked_ip',
                'ordering': ['-blocked_at'],
                'verbose_name': 'Blocked IP Address',
                'verbose_name_plural': 'Blocked IP Addresses',
            },
        ),
        migrations.CreateModel(
            name='RateLimitTrustedIP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(
                    help_text='Trusted IP address (IPv4 or IPv6)',
                    unique=True,
                    validators=[django.core.validators.validate_ipv46_address]
                )),
                ('description', models.CharField(
                    help_text="Description of the trusted source (e.g., 'Internal monitoring service')",
                    max_length=255
                )),
                ('added_at', models.DateTimeField(
                    auto_now_add=True,
                    help_text='When the IP was added to the trusted list'
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Whether the trust is currently active'
                )),
                ('expires_at', models.DateTimeField(
                    blank=True,
                    help_text='Optional expiration date for temporary trust',
                    null=True
                )),
                ('notes', models.TextField(
                    blank=True,
                    help_text='Additional notes about this trusted IP'
                )),
                ('added_by', models.ForeignKey(
                    blank=True,
                    help_text='Admin who added this trusted IP',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='trusted_ips_added',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'core_rate_limit_trusted_ip',
                'ordering': ['-added_at'],
                'verbose_name': 'Trusted IP Address',
                'verbose_name_plural': 'Trusted IP Addresses',
            },
        ),
        migrations.CreateModel(
            name='RateLimitViolationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='When the violation occurred'
                )),
                ('client_ip', models.GenericIPAddressField(
                    help_text='IP address that triggered the violation',
                    validators=[django.core.validators.validate_ipv46_address]
                )),
                ('endpoint_path', models.CharField(
                    db_index=True,
                    help_text='The endpoint path that was accessed',
                    max_length=255
                )),
                ('endpoint_type', models.CharField(
                    db_index=True,
                    help_text='Type of endpoint (admin, api, graphql, etc.)',
                    max_length=50
                )),
                ('violation_reason', models.CharField(
                    help_text='Reason for violation (ip_rate_limit, user_rate_limit, etc.)',
                    max_length=100
                )),
                ('request_count', models.PositiveIntegerField(
                    help_text='Number of requests at the time of violation'
                )),
                ('rate_limit', models.PositiveIntegerField(
                    help_text='The rate limit threshold that was exceeded'
                )),
                ('correlation_id', models.CharField(
                    db_index=True,
                    help_text='Correlation ID for request tracking',
                    max_length=36
                )),
                ('user_agent', models.TextField(
                    blank=True,
                    help_text='User agent string of the violating request'
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    help_text='User if authenticated',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rate_limit_violations',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'db_table': 'core_rate_limit_violation_log',
                'ordering': ['-timestamp'],
                'verbose_name': 'Rate Limit Violation',
                'verbose_name_plural': 'Rate Limit Violations',
            },
        ),
        migrations.AddIndex(
            model_name='ratelimitblockedip',
            index=models.Index(fields=['ip_address', 'is_active'], name='core_rate_l_ip_addr_a1b2c3_idx'),
        ),
        migrations.AddIndex(
            model_name='ratelimitblockedip',
            index=models.Index(fields=['blocked_until'], name='core_rate_l_blocked_d4e5f6_idx'),
        ),
        migrations.AddIndex(
            model_name='ratelimitblockedip',
            index=models.Index(fields=['endpoint_type'], name='core_rate_l_endpoin_g7h8i9_idx'),
        ),
        migrations.AddIndex(
            model_name='ratelimittrustedip',
            index=models.Index(fields=['ip_address', 'is_active'], name='core_rate_t_ip_addr_j1k2l3_idx'),
        ),
        migrations.AddIndex(
            model_name='ratelimittrustedip',
            index=models.Index(fields=['expires_at'], name='core_rate_t_expires_m4n5o6_idx'),
        ),
        migrations.AddIndex(
            model_name='ratelimitviolationlog',
            index=models.Index(fields=['timestamp', 'endpoint_type'], name='core_rate_v_timesta_p7q8r9_idx'),
        ),
        migrations.AddIndex(
            model_name='ratelimitviolationlog',
            index=models.Index(fields=['client_ip', 'timestamp'], name='core_rate_v_client__s1t2u3_idx'),
        ),
        migrations.AddIndex(
            model_name='ratelimitviolationlog',
            index=models.Index(fields=['user', 'timestamp'], name='core_rate_v_user_id_v4w5x6_idx'),
        ),
    ]