# Generated for GeoDjango Performance Optimization
from django.contrib.postgres.operations import AddIndexConcurrently, RemoveIndexConcurrently
from django.contrib.postgres.indexes import GistIndex
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        # Note: Converted to RunSQL with IF NOT EXISTS for idempotency
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS pel_startlocation_gist_idx ON peopleeventlog USING GIST(startlocation) WHERE startlocation IS NOT NULL;",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pel_startlocation_gist_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS pel_endlocation_gist_idx ON peopleeventlog USING GIST(endlocation) WHERE endlocation IS NOT NULL;",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pel_endlocation_gist_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS pel_journeypath_gist_idx ON peopleeventlog USING GIST(journeypath) WHERE journeypath IS NOT NULL;",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pel_journeypath_gist_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS tracking_gpslocation_gist_idx ON tracking USING GIST(gpslocation) WHERE gpslocation IS NOT NULL;",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS tracking_gpslocation_gist_idx;"
        ),
        # Add compound indexes for common queries
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS pel_datefor_startloc_idx ON peopleeventlog USING btree(datefor) WHERE startlocation IS NOT NULL;",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS pel_datefor_startloc_idx;"
        ),
        # Note: Removed pel_people_datefor_idx - people_id column doesn't exist in PeopleEventlog model
    ]

    atomic = False  # Required for CONCURRENTLY operations