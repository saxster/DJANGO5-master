"""
Add version field for optimistic locking on PeopleEventlog
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='peopleeventlog',
            name='version',
            field=models.IntegerField(default=0, help_text='Version for optimistic locking'),
        ),
        migrations.AddField(
            model_name='peopleeventlog',
            name='last_modified_by',
            field=models.CharField(
                max_length=100,
                null=True,
                blank=True,
                help_text='System or user that last modified this record'
            ),
        ),
        migrations.AddIndex(
            model_name='peopleeventlog',
            index=models.Index(fields=['uuid', 'version'], name='idx_pel_uuid_version'),
        ),
    ]