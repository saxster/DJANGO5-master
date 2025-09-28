# Generated manually for performance optimization
# This migration adds database indexes to frequently queried fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0006_add_transcript_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='job',
            name='identifier',
            field=models.CharField(
                choices=[
                    ('TASK', 'Task'),
                    ('TICKET', 'Ticket'),
                    ('INTERNALTOUR', 'Internal Tour'),
                    ('EXTERNALTOUR', 'External Tour'),
                    ('PPM', 'PPM'),
                    ('OTHER', 'Other'),
                    ('SITEREPORT', 'Site Report'),
                    ('INCIDENTREPORT', 'Incident Report'),
                    ('ASSETLOG', 'Asset Log'),
                    ('ASSETMAINTENANCE', 'Asset Maintenance'),
                    ('GEOFENCE', 'Geofence')
                ],
                db_index=True,
                max_length=100,
                null=True,
                verbose_name='Job Type'
            ),
        ),
        migrations.AlterField(
            model_name='jobneed',
            name='identifier',
            field=models.CharField(
                choices=[
                    ('TASK', 'Task'),
                    ('TICKET', 'Ticket'),
                    ('INTERNALTOUR', 'Internal Tour'),
                    ('EXTERNALTOUR', 'External Tour'),
                    ('PPM', 'PPM'),
                    ('OTHER', 'Other'),
                    ('SITEREPORT', 'Site Report'),
                    ('INCIDENTREPORT', 'Incident Report'),
                    ('ASSETLOG', 'Asset Log'),
                    ('ASSETMAINTENANCE', 'Asset Maintenance'),
                    ('GEOFENCE', 'Geofence')
                ],
                db_index=True,
                max_length=50,
                null=True,
                verbose_name='Jobneed Type'
            ),
        ),
    ]