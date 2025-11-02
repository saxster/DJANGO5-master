"""
Migration: Add Checkpoint Query Performance Index.

Optimizes tour checkpoint collection queries by adding composite index
on (people, parent, endtime) for Gap #1 telemetry collection.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0001_initial'),
    ]

    operations = [
        # Add composite index for tour checkpoint queries
        # Query pattern: Filter by people + parent__isnull=False + endtime range
        migrations.AddIndex(
            model_name='jobneed',
            index=models.Index(
                fields=['people', 'parent', 'endtime'],
                name='jobneed_ckpt_query'
            ),
        ),
    ]
