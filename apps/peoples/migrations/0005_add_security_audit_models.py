# Generated migration for security audit models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('peoples', '0004_add_preferred_language'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginAttemptLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(db_index=True, help_text='Username attempted', max_length=255)),
                ('ip_address', models.GenericIPAddressField(db_index=True, help_text='Client IP address')),
                ('success', models.BooleanField(db_index=True, default=False, help_text='Whether login was successful')),
                ('failure_reason', models.CharField(blank=True, choices=[('invalid_credentials', 'Invalid Credentials'), ('user_not_found', 'User Not Found'), ('account_locked', 'Account Locked'), ('ip_throttled', 'IP Address Throttled'), ('username_throttled', 'Username Throttled'), ('authentication_exception', 'Authentication Exception'), ('access_denied', 'Access Denied')], help_text='Reason for failure', max_length=100)),
                ('user_agent', models.TextField(blank=True, help_text='Browser user agent string')),
                ('access_type', models.CharField(choices=[('Web', 'Web'), ('Mobile', 'Mobile'), ('API', 'API')], default='Web', help_text='Access method', max_length=20)),
                ('correlation_id', models.CharField(blank=True, help_text='Correlation ID for tracing', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'verbose_name': 'Login Attempt Log',
                'verbose_name_plural': 'Login Attempt Logs',
                'db_table': 'login_attempt_log',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AccountLockout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(db_index=True, help_text='Locked username', max_length=255, unique=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address that triggered lockout (if applicable)', null=True)),
                ('lockout_type', models.CharField(choices=[('ip', 'IP Address Lockout'), ('username', 'Username Lockout'), ('manual', 'Manual Lockout')], help_text='Type of lockout', max_length=20)),
                ('reason', models.TextField(help_text='Reason for lockout')),
                ('locked_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('locked_until', models.DateTimeField(db_index=True, help_text='When lockout expires')),
                ('attempt_count', models.IntegerField(default=0, help_text='Number of failed attempts that triggered lockout')),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Whether lockout is still active')),
                ('unlocked_at', models.DateTimeField(blank=True, help_text='When lockout was manually removed', null=True)),
                ('unlocked_by', models.ForeignKey(blank=True, help_text='Admin who manually unlocked', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='unlocked_accounts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Account Lockout',
                'verbose_name_plural': 'Account Lockouts',
                'db_table': 'account_lockout',
                'ordering': ['-locked_at'],
            },
        ),
        migrations.AddIndex(
            model_name='loginattemptlog',
            index=models.Index(fields=['username', 'created_at'], name='login_attem_usernam_idx'),
        ),
        migrations.AddIndex(
            model_name='loginattemptlog',
            index=models.Index(fields=['ip_address', 'created_at'], name='login_attem_ip_addr_idx'),
        ),
        migrations.AddIndex(
            model_name='loginattemptlog',
            index=models.Index(fields=['success', 'created_at'], name='login_attem_success_idx'),
        ),
        migrations.AddIndex(
            model_name='accountlockout',
            index=models.Index(fields=['username', 'is_active'], name='account_loc_usernam_idx'),
        ),
        migrations.AddIndex(
            model_name='accountlockout',
            index=models.Index(fields=['lockout_type', 'is_active'], name='account_loc_lockout_idx'),
        ),
        migrations.AddIndex(
            model_name='accountlockout',
            index=models.Index(fields=['locked_until'], name='account_loc_locked__idx'),
        ),
    ]
