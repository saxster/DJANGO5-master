"""
Add GIST spatial indexes to Geofence model for performance.

Critical Performance Fix:
- Adds GIST indexes on boundary (PolygonField) and center_point (PointField)
- Without these indexes, geofence validation performs full table scans
- With 100+ geofences, this causes significant performance degradation

PostGIS Index Types:
- GIST (Generalized Search Tree): Best for spatial queries (ST_Contains, ST_DWithin)
- Provides O(log n) lookups instead of O(n) full table scans

Expected Performance Impact:
- Geofence validation: 10-100x faster with indexes
- Critical for mobile clock-in/out with real-time validation
"""

from django.db import migrations
from django.contrib.postgres.operations import AddIndexConcurrently
from django.contrib.gis.db.models import GistIndex


class Migration(migrations.Migration):

    atomic = False  # Required for CREATE INDEX CONCURRENTLY

    dependencies = [
        ('attendance', '0020_add_geofence_model'),
    ]

    operations = [
        # Add GIST index on boundary field (for polygon geofences)
        AddIndexConcurrently(
            model_name='geofence',
            index=GistIndex(
                fields=['boundary'],
                name='geofence_boundary_gist_idx',
                # Opclass 'gist_geometry_ops_2d' optimized for 2D spatial queries
            ),
        ),
        # Add GIST index on center_point field (for circle geofences)
        AddIndexConcurrently(
            model_name='geofence',
            index=GistIndex(
                fields=['center_point'],
                name='geofence_center_point_gist_idx',
            ),
        ),
    ]
