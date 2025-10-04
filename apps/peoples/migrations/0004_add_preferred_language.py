# Generated migration for adding preferred_language field to People model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('peoples', '0003_add_query_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='people',
            name='preferred_language',
            field=models.CharField(
                choices=[
                    ('en', 'English'),
                    ('hi', 'हिन्दी (Hindi)'),
                    ('te', 'తెలుగు (Telugu)'),
                    ('es', 'Español (Spanish)'),
                    ('fr', 'Français (French)'),
                    ('ar', 'العربية (Arabic)'),
                    ('zh', '中文 (Chinese)'),
                ],
                default='en',
                help_text="User's preferred language for conversations and content",
                max_length=10,
                verbose_name='Preferred Language'
            ),
        ),
        migrations.AddIndex(
            model_name='people',
            index=models.Index(fields=['preferred_language'], name='people_preferred_language_idx'),
        ),
    ]