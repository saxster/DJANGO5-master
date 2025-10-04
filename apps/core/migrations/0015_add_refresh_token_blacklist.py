"""
Migration for RefreshTokenBlacklist model.

Adds token blacklist table for refresh token security.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_add_composite_spatial_indexes'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RefreshTokenBlacklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, help_text='Created timestamp')),
                ('mdtz', models.DateTimeField(auto_now=True, help_text='Modified timestamp')),
                ('token_jti', models.CharField(
                    db_index=True,
                    help_text='JWT token identifier (jti claim)',
                    max_length=255,
                    unique=True
                )),
                ('blacklisted_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='Timestamp when token was blacklisted'
                )),
                ('reason', models.CharField(
                    choices=[
                        ('rotated', 'Token Rotated'),
                        ('logout', 'User Logout'),
                        ('revoked', 'Admin Revoked'),
                        ('expired', 'Token Expired'),
                        ('security', 'Security Event')
                    ],
                    db_index=True,
                    default='rotated',
                    help_text='Reason for blacklisting',
                    max_length=50
                )),
                ('metadata', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Additional metadata (IP address, user agent, etc.)'
                )),
                ('user', models.ForeignKey(
                    help_text='User associated with this token',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='blacklisted_tokens',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Refresh Token Blacklist Entry',
                'verbose_name_plural': 'Refresh Token Blacklist Entries',
                'db_table': 'core_refresh_token_blacklist',
                'ordering': ['-blacklisted_at'],
            },
        ),
        migrations.AddIndex(
            model_name='refreshtokenblacklist',
            index=models.Index(fields=['token_jti'], name='idx_token_jti'),
        ),
        migrations.AddIndex(
            model_name='refreshtokenblacklist',
            index=models.Index(fields=['blacklisted_at', 'reason'], name='idx_blacklist_cleanup'),
        ),
        migrations.AddIndex(
            model_name='refreshtokenblacklist',
            index=models.Index(fields=['user', '-blacklisted_at'], name='idx_user_blacklist'),
        ),
    ]
