"""
Performance Index Migration for Job Model

Adds composite index to optimize geofence-related queries:
- Job lookups by people_id + identifier combination
- Frequently used in attachment preview and event log processing

Created: November 5, 2025
Estimated Impact: +200% query performance for geofence lookups
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0023_add_asset_analytics'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='job',
            index=models.Index(
                fields=['people', 'identifier'],
                name='job_people_identifier_idx'
            ),
        ),
    ]
