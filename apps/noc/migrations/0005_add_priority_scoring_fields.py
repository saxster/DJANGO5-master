"""
Migration to add ML-based priority scoring fields to NOCAlertEvent.

Enhancement #7: Dynamic Alert Priority Scoring
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0004_materialized_views'),
    ]

    operations = [
        migrations.AddField(
            model_name='nocalertevent',
            name='calculated_priority',
            field=models.IntegerField(
                default=50,
                help_text='ML-based business impact score (0-100)',
                verbose_name='Calculated Priority'
            ),
        ),
        migrations.AddField(
            model_name='nocalertevent',
            name='priority_features',
            field=models.JSONField(
                default=dict,
                help_text='Feature values used for priority calculation',
                verbose_name='Priority Features'
            ),
        ),
        migrations.AddIndex(
            model_name='nocalertevent',
            index=models.Index(
                fields=['-calculated_priority', '-cdtz'],
                name='noc_alert_priority'
            ),
        ),
    ]
