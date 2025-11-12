"""
Heatmap and outlier detection manager for PeopleEventlog.

Handles spatial heatmap generation and statistical outlier detection.
"""
from django.db import models
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.db.models import Avg, Max, Min
import logging

logger = logging.getLogger("django")


class HeatmapOutlierManagerMixin:
    """
    Manager mixin for heatmap generation and outlier detection.

    Provides methods for:
    - Attendance density heatmaps
    - Distance outlier detection
    - Time-based outlier detection
    """

    def get_attendance_heatmap_data(self, client_id, date_from, date_to, bu_ids=None, grid_size=0.01):
        """
        Generate spatial heatmap data for attendance locations.

        Args:
            client_id: Client ID
            date_from, date_to: Date range
            bu_ids: Optional business unit filter
            grid_size: Grid size in degrees for aggregation (~0.01° = 1.1 km)

        Returns:
            List of coordinate grids with attendance counts
        """
        query = (self.filter(
            client_id=client_id,
            datefor__range=(date_from, date_to),
            startlocation__isnull=False
        ).exclude(id=1))

        if bu_ids:
            query = query.filter(bu_id__in=bu_ids)

        # Extract coordinates and create grid
        coords_data = query.extra(
            select={
                'lat': 'ST_Y(startlocation::geometry)',
                'lon': 'ST_X(startlocation::geometry)'
            }
        ).values('lat', 'lon', 'people_id', 'datefor')

        # Grid aggregation
        grid_data = {}
        for record in coords_data:
            if record['lat'] and record['lon']:
                # Round to grid
                grid_lat = round(record['lat'] / grid_size) * grid_size
                grid_lon = round(record['lon'] / grid_size) * grid_size
                grid_key = f"{grid_lat},{grid_lon}"

                if grid_key not in grid_data:
                    grid_data[grid_key] = {
                        'lat': grid_lat,
                        'lon': grid_lon,
                        'count': 0,
                        'unique_people': set()
                    }

                grid_data[grid_key]['count'] += 1
                grid_data[grid_key]['unique_people'].add(record['people_id'])

        # Convert sets to counts and prepare final data
        heatmap_points = []
        for grid_point in grid_data.values():
            heatmap_points.append({
                'lat': grid_point['lat'],
                'lon': grid_point['lon'],
                'count': grid_point['count'],
                'unique_people_count': len(grid_point['unique_people']),
                'intensity': min(grid_point['count'] / 10.0, 1.0)  # Normalize for heatmap
            })

        return sorted(heatmap_points, key=lambda x: x['count'], reverse=True)

    def find_attendance_outliers(self, client_id, date_from, date_to, std_deviation_threshold=2):
        """
        Find spatial and temporal outliers in attendance data.

        Returns:
            Dictionary with location outliers, time outliers, and anomaly patterns
        """
        base_query = self.filter(
            client_id=client_id,
            datefor__range=(date_from, date_to),
            startlocation__isnull=False,
            distance__isnull=False
        ).exclude(id=1)

        # Calculate statistical baselines
        stats = base_query.aggregate(
            avg_distance=Avg('distance'),
            distance_std=models.StdDev('distance'),
            distance_variance=models.Variance('distance')
        )

        # Distance outliers
        distance_threshold = stats['avg_distance'] + (std_deviation_threshold * (stats['distance_std'] or 0))
        distance_outliers = base_query.filter(
            distance__gt=distance_threshold
        ).select_related('people', 'bu').values(
            'id', 'uuid', 'people_id', 'people__peoplename',
            'bu_id', 'bu__buname', 'datefor', 'distance',
            'punchintime', 'punchouttime'
        ).annotate(
            start_coords=AsGeoJSON('startlocation'),
            end_coords=AsGeoJSON('endlocation')
        )

        # Time-based outliers (unusual punch times)
        time_outliers = base_query.extra(
            select={
                'punch_hour': 'EXTRACT(hour FROM punchintime)',
                'punch_dow': 'EXTRACT(dow FROM punchintime)'  # Day of week
            }
        ).exclude(
            punch_hour__range=(6, 22)  # Normal working hours
        ).values(
            'id', 'uuid', 'people_id', 'people__peoplename',
            'datefor', 'punchintime', 'punch_hour', 'punch_dow'
        )

        return {
            'distance_outliers': list(distance_outliers),
            'time_outliers': list(time_outliers),
            'statistical_baseline': stats,
            'thresholds': {
                'distance_threshold': distance_threshold,
                'std_deviation_threshold': std_deviation_threshold
            }
        }
