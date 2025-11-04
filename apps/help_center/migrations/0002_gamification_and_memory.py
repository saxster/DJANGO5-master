"""
Migration for gamification and conversation memory models.

Adds:
- HelpBadge: Badge definitions
- HelpUserBadge: User-earned badges
- HelpUserPoints: Points accumulation
- HelpConversationMemory: AI conversation context

Dependencies: 0001_initial
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('help_center', '0001_initial'),
        ('peoples', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        # HelpBadge model
        migrations.CreateModel(
            name='HelpBadge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(db_index=True, max_length=100)),
                ('slug', models.SlugField(max_length=120, unique=True)),
                ('description', models.TextField(max_length=500)),
                ('icon', models.CharField(help_text="Icon/emoji (e.g., '🏆', '⭐', '🎖️')", max_length=50)),
                ('color', models.CharField(default='#ffd700', help_text='Hex color for badge display', max_length=7)),
                ('criteria', models.JSONField(help_text='Earning criteria as JSON')),
                ('points_awarded', models.IntegerField(default=10, help_text='Points awarded when badge is earned')),
                ('rarity', models.CharField(choices=[('COMMON', 'Common'), ('RARE', 'Rare'), ('EPIC', 'Epic'), ('LEGENDARY', 'Legendary')], db_index=True, default='COMMON', max_length=20)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'db_table': 'help_center_badge',
                'ordering': ['name'],
                'unique_together': {('tenant', 'slug')},
            },
        ),

        # HelpUserBadge model
        migrations.CreateModel(
            name='HelpUserBadge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('earned_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('notified_at', models.DateTimeField(blank=True, help_text='When user was notified of badge', null=True)),
                ('badge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_badges', to='help_center.helpbadge')),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_badges_earned', to='peoples.people')),
            ],
            options={
                'db_table': 'help_center_user_badge',
                'ordering': ['-earned_at'],
                'unique_together': {('user', 'badge')},
            },
        ),

        # HelpUserPoints model
        migrations.CreateModel(
            name='HelpUserPoints',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('total_points', models.IntegerField(db_index=True, default=0)),
                ('feedback_points', models.IntegerField(default=0)),
                ('suggestion_points', models.IntegerField(default=0)),
                ('contribution_points', models.IntegerField(default=0)),
                ('badge_bonus_points', models.IntegerField(default=0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='help_points', to='peoples.people')),
            ],
            options={
                'db_table': 'help_center_user_points',
                'ordering': ['-total_points'],
            },
        ),

        # HelpConversationMemory model
        migrations.CreateModel(
            name='HelpConversationMemory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('session_id', models.UUIDField(db_index=True, help_text='Session UUID for grouping memories')),
                ('memory_type', models.CharField(choices=[('SHORT_TERM', 'Short-term (current session)'), ('LONG_TERM', 'Long-term (user preferences)'), ('FACT', 'Fact (permanent)')], db_index=True, default='SHORT_TERM', max_length=20)),
                ('key', models.CharField(db_index=True, help_text="Memory key (e.g., 'preferred_language', 'common_issue')", max_length=200)),
                ('value', models.JSONField(help_text='Memory value (can be string, number, object, array)')),
                ('confidence', models.FloatField(default=1.0, help_text='Confidence score (0-1) for this memory')),
                ('expires_at', models.DateTimeField(blank=True, db_index=True, help_text='When memory expires (null = never)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_memories', to='peoples.people')),
            ],
            options={
                'db_table': 'help_center_conversation_memory',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'session_id', 'key')},
            },
        ),

        # Add indexes
        migrations.AddIndex(
            model_name='helpconversationmemory',
            index=models.Index(fields=['user', 'session_id'], name='help_memory_user_session_idx'),
        ),
        migrations.AddIndex(
            model_name='helpconversationmemory',
            index=models.Index(fields=['memory_type', 'expires_at'], name='help_memory_type_expires_idx'),
        ),
        migrations.AddIndex(
            model_name='helpconversationmemory',
            index=models.Index(fields=['key'], name='help_memory_key_idx'),
        ),
    ]
