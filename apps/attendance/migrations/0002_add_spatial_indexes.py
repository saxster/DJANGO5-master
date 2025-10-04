# Generated for GeoDjango Performance Optimization
from django.contrib.postgres.operations import AddIndexConcurrently, RemoveIndexConcurrently
from django.contrib.postgres.indexes import GistIndex
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        # Add GIST indexes for spatial fields on PeopleEventlog
        AddIndexConcurrently(
            model_name='peopleeventlog',
            index=GistIndex(
                fields=['startlocation'],
                name='pel_startlocation_gist_idx',
                condition=models.Q(startlocation__isnull=False)
            )
        ),
        AddIndexConcurrently(
            model_name='peopleeventlog',
            index=GistIndex(
                fields=['endlocation'],
                name='pel_endlocation_gist_idx',
                condition=models.Q(endlocation__isnull=False)
            )
        ),
        AddIndexConcurrently(
            model_name='peopleeventlog',
            index=GistIndex(
                fields=['journeypath'],
                name='pel_journeypath_gist_idx',
                condition=models.Q(journeypath__isnull=False)
            )
        ),
        # Add GIST index for Tracking model gpslocation
        AddIndexConcurrently(
            model_name='tracking',
            index=GistIndex(
                fields=['gpslocation'],
                name='tracking_gpslocation_gist_idx',
                condition=models.Q(gpslocation__isnull=False)
            )
        ),
        # Add compound indexes for common queries
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY pel_datefor_startloc_idx
            ON peopleeventlog USING btree(datefor)
            WHERE startlocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pel_datefor_startloc_idx;"
        ),
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY pel_people_datefor_idx
            ON peopleeventlog USING btree(people_id, datefor)
            WHERE startlocation IS NOT NULL OR endlocation IS NOT NULL;
            """,
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pel_people_datefor_idx;"
        ),
    ]

    atomic = False  # Required for CONCURRENTLY operations