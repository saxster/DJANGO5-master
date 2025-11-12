"""
Advanced Spatial Query Service demonstrating GeoDjango's full spatial capabilities.

This service showcases enterprise-grade spatial query patterns including:
- Advanced spatial lookups (within, intersects, overlaps, etc.)
- Spatial joins and relationships
- Coordinate system transformations
- Complex geometric operations
- Spatial aggregations and statistics
- PostGIS function integration

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive field validation and use constants instead of magic numbers
- Service layer methods < 150 lines
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime, date

from django.contrib.gis.db.models import Extent, Union as GISUnion, Collect
from django.contrib.gis.db.models.functions import (
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS

    Distance, Area, Length, Perimeter, Centroid, PointOnSurface,
    Transform, AsGeoJSON, AsKML, AsWKT, MakeValid,
    Intersection, Difference, SymDifference, Union as GeomUnion
)
from django.contrib.gis.geos import Point, Polygon, LineString, MultiPoint, GEOSGeometry
from django.contrib.gis.measure import Distance as DistanceMeasure
from django.db.models import Q, F, Count, Avg, Max, Min, Sum
from django.db.models.functions import Cast
from django.core.exceptions import ValidationError

from apps.attendance.models import PeopleEventlog
from apps.activity.models import Asset, Location
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import GeofenceMaster
from apps.core.constants.spatial_constants import METERS_PER_DEGREE_LAT

logger = logging.getLogger(__name__)


@dataclass
class SpatialQueryResult:
    """Result container for spatial query operations"""
    success: bool
    data: Any = None
    count: int = 0
    extent: Optional[Tuple] = None
    metadata: Dict[str, Any] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.metadata is None:
            self.metadata = {}


class AdvancedSpatialQueryService:
    """
    Enterprise-grade spatial query service showcasing advanced GeoDjango capabilities.

    Provides comprehensive spatial analysis tools for attendance, asset, and location management
    with performance optimization and error handling.
    """

    def __init__(self):
        self.default_srid = 4326

    # ===========================================
    # SPATIAL RELATIONSHIP QUERIES
    # ===========================================

    def find_attendance_within_polygon(self, polygon: Union[Polygon, str],
                                     date_from: date = None,
                                     date_to: date = None,
                                     client_id: int = None) -> SpatialQueryResult:
        """
        Find attendance records within a polygon boundary using 'within' lookup.

        Args:
            polygon: Polygon geometry or WKT string
            date_from: Optional start date filter
            date_to: Optional end date filter
            client_id: Optional client filter

        Returns:
            SpatialQueryResult with attendance records and spatial statistics
        """
        try:
            # Convert WKT to geometry if needed
            if isinstance(polygon, str):
                polygon = GEOSGeometry(polygon, srid=self.default_srid)

            # Build query
            query = PeopleEventlog.objects.filter(
                startlocation__within=polygon
            ).select_related('people', 'bu', 'peventtype')

            if date_from and date_to:
                query = query.filter(datefor__range=(date_from, date_to))

            if client_id:
                query = query.filter(client_id=client_id)

            # Get data with spatial annotations
            results = query.annotate(
                distance_to_centroid=Distance('startlocation', polygon.centroid),
                coords_geojson=AsGeoJSON('startlocation')
            ).values(
                'id', 'uuid', 'people__peoplename', 'bu__buname',
                'datefor', 'punchintime', 'distance', 'coords_geojson',
                'distance_to_centroid'
            )

            # Calculate spatial statistics
            stats = query.aggregate(
                total_count=Count('id'),
                avg_distance=Avg('distance'),
                spatial_extent=Extent('startlocation')
            )

            return SpatialQueryResult(
                success=True,
                data=list(results),
                count=stats['total_count'] or 0,
                extent=stats['spatial_extent'],
                metadata={
                    'polygon_area': polygon.area,
                    'polygon_centroid': tuple(polygon.centroid.coords),
                    'avg_distance': stats['avg_distance'],
                    'query_type': 'within_polygon'
                }
            )

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Within polygon query failed: {str(e)}")
            return SpatialQueryResult(
                success=False,
                errors=[f"Query failed: {str(e)}"]
            )

    def find_assets_intersecting_buffer(self, center_point: Point,
                                      buffer_distance_m: float,
                                      client_id: int = None,
                                      asset_types: List[str] = None) -> SpatialQueryResult:
        """
        Find assets that intersect with a buffer around a center point.

        Args:
            center_point: Center point for buffer
            buffer_distance_m: Buffer distance in meters
            client_id: Optional client filter
            asset_types: Optional asset type filter

        Returns:
            SpatialQueryResult with intersecting assets
        """
        try:
            # Create buffer around center point
            buffer_geom = center_point.buffer(buffer_distance_m / METERS_PER_DEGREE_LAT)  # Convert meters to degrees

            # Build query using intersects
            query = Asset.objects.filter(
                gpslocation__intersects=buffer_geom,
                enable=True
            ).select_related('type', 'client', 'bu', 'location')

            if client_id:
                query = query.filter(client_id=client_id)

            if asset_types:
                query = query.filter(type__tacode__in=asset_types)

            # Annotate with spatial calculations
            results = query.annotate(
                distance_from_center=Distance('gpslocation', center_point),
                asset_coords=AsGeoJSON('gpslocation'),
                is_critical_near_center=F('iscritical')
            ).values(
                'id', 'assetcode', 'assetname', 'type__tacode',
                'bu__buname', 'iscritical', 'runningstatus',
                'distance_from_center', 'asset_coords', 'is_critical_near_center'
            ).order_by('distance_from_center')

            # Aggregate statistics
            stats = query.aggregate(
                total_assets=Count('id'),
                critical_assets=Count('id', filter=Q(iscritical=True)),
                avg_distance=Avg(Distance('gpslocation', center_point)),
                nearest_distance=Min(Distance('gpslocation', center_point)),
                farthest_distance=Max(Distance('gpslocation', center_point))
            )

            return SpatialQueryResult(
                success=True,
                data=list(results),
                count=stats['total_assets'] or 0,
                metadata={
                    'center_point': tuple(center_point.coords),
                    'buffer_distance_m': buffer_distance_m,
                    'critical_assets': stats['critical_assets'] or 0,
                    'avg_distance_m': stats['avg_distance'].m if stats['avg_distance'] else 0,
                    'distance_range': {
                        'nearest': stats['nearest_distance'].m if stats['nearest_distance'] else 0,
                        'farthest': stats['farthest_distance'].m if stats['farthest_distance'] else 0
                    }
                }
            )

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Intersecting buffer query failed: {str(e)}")
            return SpatialQueryResult(
                success=False,
                errors=[f"Query failed: {str(e)}"]
            )

    def analyze_spatial_clusters(self, model_class, location_field: str,
                               cluster_distance_km: float = 1.0,
                               min_cluster_size: int = 3,
                               client_id: int = None) -> SpatialQueryResult:
        """
        Analyze spatial clustering using ST_ClusterDBSCAN PostGIS function.

        Args:
            model_class: Django model class to analyze
            location_field: Name of the spatial field
            cluster_distance_km: Distance threshold for clustering
            min_cluster_size: Minimum points to form cluster
            client_id: Optional client filter

        Returns:
            SpatialQueryResult with cluster analysis
        """
        try:
            # Build base query
            query = model_class.objects.filter(
                **{f"{location_field}__isnull": False}
            )

            if client_id and hasattr(model_class, 'client_id'):
                query = query.filter(client_id=client_id)

            # Use raw SQL for advanced PostGIS clustering
            cluster_sql = f"""
            SELECT
                id,
                {location_field},
                ST_ClusterDBSCAN({location_field}, eps := %s, minpoints := %s)
                    OVER () AS cluster_id,
                ST_X({location_field}::geometry) as longitude,
                ST_Y({location_field}::geometry) as latitude
            FROM {model_class._meta.db_table}
            WHERE {location_field} IS NOT NULL
            """

            if client_id and hasattr(model_class, 'client_id'):
                cluster_sql += " AND client_id = %s"
                params = [cluster_distance_km / (METERS_PER_DEGREE_LAT / 1000), min_cluster_size, client_id]  # Convert km to degrees
            else:
                params = [cluster_distance_km / (METERS_PER_DEGREE_LAT / 1000), min_cluster_size]

            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(cluster_sql, params)
                cluster_results = cursor.fetchall()

            # Process cluster results
            clusters = {}
            noise_points = []

            for row in cluster_results:
                record_id, geom, cluster_id, lon, lat = row

                if cluster_id is None:  # Noise point
                    noise_points.append({
                        'id': record_id,
                        'longitude': lon,
                        'latitude': lat
                    })
                else:
                    if cluster_id not in clusters:
                        clusters[cluster_id] = {
                            'cluster_id': cluster_id,
                            'points': [],
                            'count': 0,
                            'center': None
                        }

                    clusters[cluster_id]['points'].append({
                        'id': record_id,
                        'longitude': lon,
                        'latitude': lat
                    })
                    clusters[cluster_id]['count'] += 1

            # Calculate cluster centers
            for cluster in clusters.values():
                if cluster['points']:
                    avg_lon = sum(p['longitude'] for p in cluster['points']) / len(cluster['points'])
                    avg_lat = sum(p['latitude'] for p in cluster['points']) / len(cluster['points'])
                    cluster['center'] = {'longitude': avg_lon, 'latitude': avg_lat}

            return SpatialQueryResult(
                success=True,
                data={
                    'clusters': list(clusters.values()),
                    'noise_points': noise_points,
                    'summary': {
                        'total_clusters': len(clusters),
                        'total_clustered_points': sum(c['count'] for c in clusters.values()),
                        'noise_points_count': len(noise_points),
                        'largest_cluster_size': max([c['count'] for c in clusters.values()]) if clusters else 0
                    }
                },
                count=len(cluster_results),
                metadata={
                    'cluster_distance_km': cluster_distance_km,
                    'min_cluster_size': min_cluster_size,
                    'model': model_class.__name__
                }
            )

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Spatial clustering analysis failed: {str(e)}")
            return SpatialQueryResult(
                success=False,
                errors=[f"Clustering analysis failed: {str(e)}"]
            )

    # ===========================================
    # COORDINATE TRANSFORMATION QUERIES
    # ===========================================

    def transform_coordinates_bulk(self, coordinates: List[Tuple[float, float]],
                                 source_srid: int, target_srid: int) -> SpatialQueryResult:
        """
        Transform coordinates from one SRID to another using PostGIS.

        Args:
            coordinates: List of (lon, lat) tuples
            source_srid: Source coordinate system SRID
            target_srid: Target coordinate system SRID

        Returns:
            SpatialQueryResult with transformed coordinates
        """
        try:
            from django.db import connection

            # Prepare SQL for bulk coordinate transformation
            transform_sql = """
            SELECT
                ST_X(ST_Transform(ST_SetSRID(ST_Point(%s, %s), %s), %s)) as x,
                ST_Y(ST_Transform(ST_SetSRID(ST_Point(%s, %s), %s), %s)) as y
            """

            transformed_coords = []

            with connection.cursor() as cursor:
                for lon, lat in coordinates:
                    cursor.execute(transform_sql, [
                        lon, lat, source_srid, target_srid,  # For X calculation
                        lon, lat, source_srid, target_srid   # For Y calculation
                    ])
                    result = cursor.fetchone()
                    if result:
                        transformed_coords.append({
                            'original': {'longitude': lon, 'latitude': lat},
                            'transformed': {'x': result[0], 'y': result[1]}
                        })

            return SpatialQueryResult(
                success=True,
                data=transformed_coords,
                count=len(transformed_coords),
                metadata={
                    'source_srid': source_srid,
                    'target_srid': target_srid,
                    'transformation_count': len(transformed_coords)
                }
            )

        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Coordinate transformation failed: {str(e)}")
            return SpatialQueryResult(
                success=False,
                errors=[f"Transformation failed: {str(e)}"]
            )

    # ===========================================
    # ADVANCED GEOMETRIC OPERATIONS
    # ===========================================

    def calculate_service_coverage_areas(self, service_points: List[Point],
                                       coverage_radius_km: float = 5.0,
                                       merge_overlapping: bool = True) -> SpatialQueryResult:
        """
        Calculate service coverage areas using buffer operations and union.

        Args:
            service_points: List of service point geometries
            coverage_radius_km: Coverage radius in kilometers
            merge_overlapping: Whether to merge overlapping coverage areas

        Returns:
            SpatialQueryResult with coverage analysis
        """
        try:
            from django.contrib.gis.geos import MultiPolygon
            from django.db import connection

            coverage_areas = []
            total_coverage_area = 0

            # Create buffers for each service point
            for i, point in enumerate(service_points):
                # Convert km to degrees
                buffer_degrees = coverage_radius_km / (METERS_PER_DEGREE_LAT / 1000)
                coverage_buffer = point.buffer(buffer_degrees)

                # Convert square degrees to square kilometers
                KM_PER_DEGREE = METERS_PER_DEGREE_LAT / 1000
                coverage_areas.append({
                    'service_point_id': i,
                    'center': {'longitude': point.x, 'latitude': point.y},
                    'coverage_area_wkt': coverage_buffer.wkt,
                    'coverage_area_geojson': coverage_buffer.geojson,
                    'area_sq_km': coverage_buffer.area * (KM_PER_DEGREE ** 2)  # Convert square degrees to square km
                })

                total_coverage_area += coverage_buffer.area * (KM_PER_DEGREE ** 2)

            # Merge overlapping areas if requested
            merged_coverage = None
            if merge_overlapping and len(service_points) > 1:
                try:
                    # Use PostGIS for efficient union operation
                    union_sql = """
                    SELECT ST_AsText(ST_Union(geom)) as merged_geom
                    FROM (
                        SELECT ST_Buffer(ST_SetSRID(ST_Point(%s, %s), 4326), %s) as geom
                    ) as buffers
                    """

                    # Create query for all points
                    KM_PER_DEGREE = METERS_PER_DEGREE_LAT / 1000
                    points_data = []
                    for point in service_points:
                        points_data.extend([point.x, point.y, coverage_radius_km / KM_PER_DEGREE])

                    # Build dynamic union query
                    union_queries = []
                    params = []
                    for point in service_points:
                        union_queries.append("ST_Buffer(ST_SetSRID(ST_Point(%s, %s), 4326), %s)")
                        params.extend([point.x, point.y, coverage_radius_km / KM_PER_DEGREE])

                    final_sql = f"SELECT ST_AsText(ST_Union(ARRAY[{','.join(union_queries)}])) as merged_geom"

                    with connection.cursor() as cursor:
                        cursor.execute(final_sql, params)
                        result = cursor.fetchone()
                        if result and result[0]:
                            merged_geom = GEOSGeometry(result[0])
                            KM_PER_DEGREE = METERS_PER_DEGREE_LAT / 1000
                            merged_coverage = {
                                'merged_coverage_wkt': merged_geom.wkt,
                                'merged_coverage_geojson': merged_geom.geojson,
                                'total_merged_area_sq_km': merged_geom.area * (KM_PER_DEGREE ** 2),
                                'overlap_reduction_percent': (
                                    (total_coverage_area - (merged_geom.area * (KM_PER_DEGREE ** 2))) / total_coverage_area
                                ) * 100 if total_coverage_area > 0 else 0
                            }

                except NETWORK_EXCEPTIONS as merge_error:
                    logger.warning(f"Coverage merging failed: {merge_error}")

            return SpatialQueryResult(
                success=True,
                data={
                    'individual_coverage_areas': coverage_areas,
                    'merged_coverage': merged_coverage,
                    'summary': {
                        'service_points_count': len(service_points),
                        'total_individual_area_sq_km': total_coverage_area,
                        'coverage_radius_km': coverage_radius_km
                    }
                },
                count=len(service_points),
                metadata={
                    'coverage_radius_km': coverage_radius_km,
                    'merge_overlapping': merge_overlapping
                }
            )

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Coverage area calculation failed: {str(e)}")
            return SpatialQueryResult(
                success=False,
                errors=[f"Coverage calculation failed: {str(e)}"]
            )

    # ===========================================
    # SPATIAL JOINS AND RELATIONSHIPS
    # ===========================================

    def perform_spatial_join(self, primary_model, primary_location_field: str,
                           secondary_model, secondary_location_field: str,
                           join_operation: str = 'within',
                           distance_threshold_km: float = None) -> SpatialQueryResult:
        """
        Perform spatial join between two models using various spatial relationships.

        Args:
            primary_model: Primary model class
            primary_location_field: Spatial field name in primary model
            secondary_model: Secondary model class
            secondary_location_field: Spatial field name in secondary model
            join_operation: Spatial relationship ('within', 'intersects', 'distance_lte')
            distance_threshold_km: Distance threshold for distance-based joins

        Returns:
            SpatialQueryResult with joined spatial data
        """
        try:
            # Build spatial join query
            primary_field = f"{primary_location_field}"
            secondary_field = f"secondary__{secondary_location_field}"

            if join_operation == 'within':
                join_filter = {f"{primary_field}__within": F(secondary_field)}
            elif join_operation == 'intersects':
                join_filter = {f"{primary_field}__intersects": F(secondary_field)}
            elif join_operation == 'distance_lte' and distance_threshold_km:
                distance_m = distance_threshold_km * 1000
                join_filter = {f"{primary_field}__distance_lte": (F(secondary_field), distance_m)}
            else:
                raise ValueError(f"Unsupported join operation: {join_operation}")

            # Perform the join using subqueries (Django doesn't support direct spatial joins)
            secondary_ids = secondary_model.objects.filter(
                **{f"{secondary_location_field}__isnull": False}
            ).values_list('id', flat=True)

            joined_results = []
            for sec_id in secondary_ids[:100]:  # Limit for performance
                secondary_obj = secondary_model.objects.get(id=sec_id)
                secondary_location = getattr(secondary_obj, secondary_location_field)

                if not secondary_location:
                    continue

                # Find primary objects related to this secondary object
                if join_operation == 'within':
                    primary_matches = primary_model.objects.filter(
                        **{f"{primary_location_field}__within": secondary_location}
                    )
                elif join_operation == 'intersects':
                    primary_matches = primary_model.objects.filter(
                        **{f"{primary_location_field}__intersects": secondary_location}
                    )
                elif join_operation == 'distance_lte' and distance_threshold_km:
                    distance_m = distance_threshold_km * 1000
                    primary_matches = primary_model.objects.filter(
                        **{f"{primary_location_field}__distance_lte": (secondary_location, distance_m)}
                    )

                # Collect results
                for primary_obj in primary_matches:
                    primary_location = getattr(primary_obj, primary_location_field)
                    if primary_location and secondary_location:
                        distance = primary_location.distance(secondary_location) * METERS_PER_DEGREE_LAT  # Convert degrees to meters

                        joined_results.append({
                            'primary_id': primary_obj.id,
                            'secondary_id': secondary_obj.id,
                            'distance_m': distance,
                            'primary_coords': {
                                'longitude': primary_location.x,
                                'latitude': primary_location.y
                            },
                            'secondary_coords': {
                                'longitude': secondary_location.x,
                                'latitude': secondary_location.y
                            },
                            'join_operation': join_operation
                        })

            # Calculate statistics
            if joined_results:
                distances = [r['distance_m'] for r in joined_results]
                avg_distance = sum(distances) / len(distances)
                min_distance = min(distances)
                max_distance = max(distances)
            else:
                avg_distance = min_distance = max_distance = 0

            return SpatialQueryResult(
                success=True,
                data=joined_results,
                count=len(joined_results),
                metadata={
                    'join_operation': join_operation,
                    'distance_threshold_km': distance_threshold_km,
                    'primary_model': primary_model.__name__,
                    'secondary_model': secondary_model.__name__,
                    'distance_stats': {
                        'avg_distance_m': avg_distance,
                        'min_distance_m': min_distance,
                        'max_distance_m': max_distance
                    }
                }
            )

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Spatial join failed: {str(e)}")
            return SpatialQueryResult(
                success=False,
                errors=[f"Spatial join failed: {str(e)}"]
            )

    # ===========================================
    # CONVENIENCE METHODS FOR COMMON QUERIES
    # ===========================================

    def find_nearest_assets_to_point(self, point: Point, limit: int = 10,
                                    asset_types: List[str] = None,
                                    client_id: int = None) -> SpatialQueryResult:
        """Find nearest assets to a given point."""
        try:
            query = Asset.objects.filter(
                gpslocation__isnull=False,
                enable=True
            ).annotate(
                distance=Distance('gpslocation', point)
            ).order_by('distance')

            if asset_types:
                query = query.filter(type__tacode__in=asset_types)

            if client_id:
                query = query.filter(client_id=client_id)

            results = query[:limit].values(
                'id', 'assetcode', 'assetname', 'type__tacode',
                'distance'
            ).annotate(
                distance_km=F('distance') * (METERS_PER_DEGREE_LAT / 1000)  # Convert degrees to km
            )

            return SpatialQueryResult(
                success=True,
                data=list(results),
                count=len(results),
                metadata={
                    'search_point': tuple(point.coords),
                    'limit': limit,
                    'query_type': 'nearest_assets'
                }
            )

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Nearest assets query failed: {str(e)}")
            return SpatialQueryResult(
                success=False,
                errors=[f"Query failed: {str(e)}"]
            )


# Singleton instance for easy access
spatial_query_service = AdvancedSpatialQueryService()