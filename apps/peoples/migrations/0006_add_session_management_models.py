"""
Migration: Session Management Models

Creates tables for multi-device session tracking with device fingerprinting.

Security Features:
    - Device fingerprinting and tracking
    - Suspicious activity detection
    - Session revocation support
    - Comprehensive audit logging
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sessions', '0001_initial'),
        ('peoples', '0005_add_security_audit_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_fingerprint', models.CharField(
                    db_index=True,
                    help_text='SHA256 hash of device characteristics',
                    max_length=64
                )),
                ('device_name', models.CharField(
                    blank=True,
                    help_text='Human-readable device name',
                    max_length=255
                )),
                ('device_type', models.CharField(
                    choices=[
                        ('mobile', 'Mobile'),
                        ('tablet', 'Tablet'),
                        ('desktop', 'Desktop'),
                        ('unknown', 'Unknown')
                    ],
                    default='unknown',
                    max_length=20
                )),
                ('user_agent', models.TextField(
                    blank=True,
                    help_text='Full user agent string'
                )),
                ('browser', models.CharField(blank=True, max_length=50)),
                ('browser_version', models.CharField(blank=True, max_length=20)),
                ('os', models.CharField(blank=True, max_length=50)),
                ('os_version', models.CharField(blank=True, max_length=20)),
                ('ip_address', models.GenericIPAddressField(
                    help_text='IP address at session creation'
                )),
                ('last_ip_address', models.GenericIPAddressField(
                    blank=True,
                    help_text='Most recent IP address used',
                    null=True
                )),
                ('country', models.CharField(blank=True, max_length=100)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('expires_at', models.DateTimeField(
                    db_index=True,
                    help_text='Session expiration time'
                )),
                ('is_current', models.BooleanField(
                    default=False,
                    help_text='Is this the current active session'
                )),
                ('is_suspicious', models.BooleanField(
                    db_index=True,
                    default=False,
                    help_text='Flagged as suspicious activity'
                )),
                ('suspicious_reason', models.TextField(
                    blank=True,
                    help_text='Reason for suspicious flag'
                )),
                ('revoked', models.BooleanField(
                    db_index=True,
                    default=False,
                    help_text='Session manually revoked'
                )),
                ('revoked_at', models.DateTimeField(
                    blank=True,
                    help_text='When session was revoked',
                    null=True
                )),
                ('revoke_reason', models.CharField(
                    blank=True,
                    choices=[
                        ('user_action', 'User Revoked'),
                        ('admin_action', 'Admin Revoked'),
                        ('security_threat', 'Security Threat'),
                        ('password_change', 'Password Changed'),
                        ('suspicious_activity', 'Suspicious Activity'),
                        ('other', 'Other')
                    ],
                    max_length=50
                )),
                ('revoked_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='revoked_sessions',
                    to=settings.AUTH_USER_MODEL
                )),
                ('session', models.OneToOneField(
                    help_text='Django session object',
                    on_delete=django.db.models.deletion.CASCADE,
                    to='sessions.session'
                )),
                ('user', models.ForeignKey(
                    help_text='User who owns this session',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sessions',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'User Session',
                'verbose_name_plural': 'User Sessions',
                'ordering': ['-last_activity'],
                'indexes': [
                    models.Index(fields=['user', '-last_activity'], name='peoples_use_user_id_last_ac_idx'),
                    models.Index(fields=['user', 'revoked'], name='peoples_use_user_id_revoked_idx'),
                    models.Index(fields=['device_fingerprint'], name='peoples_use_device_idx'),
                    models.Index(fields=['is_suspicious', 'revoked'], name='peoples_use_suspicious_idx'),
                    models.Index(fields=['expires_at'], name='peoples_use_expires_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='SessionActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(
                    choices=[
                        ('login', 'Login'),
                        ('logout', 'Logout'),
                        ('page_view', 'Page View'),
                        ('api_call', 'API Call'),
                        ('password_change', 'Password Change'),
                        ('settings_change', 'Settings Change'),
                        ('suspicious', 'Suspicious Activity'),
                        ('other', 'Other')
                    ],
                    db_index=True,
                    max_length=50
                )),
                ('description', models.TextField(help_text='Activity description')),
                ('ip_address', models.GenericIPAddressField()),
                ('url', models.CharField(blank=True, max_length=500)),
                ('metadata', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Additional activity metadata'
                )),
                ('is_suspicious', models.BooleanField(
                    db_index=True,
                    default=False,
                    help_text='Flagged as suspicious'
                )),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('session', models.ForeignKey(
                    help_text='Associated user session',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activity_logs',
                    to='peoples.usersession'
                )),
            ],
            options={
                'verbose_name': 'Session Activity Log',
                'verbose_name_plural': 'Session Activity Logs',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['session', '-timestamp'], name='peoples_ses_session_timestamp_idx'),
                    models.Index(fields=['activity_type', '-timestamp'], name='peoples_ses_activity_timestamp_idx'),
                    models.Index(fields=['is_suspicious'], name='peoples_ses_suspicious_idx'),
                ],
            },
        ),
    ]
