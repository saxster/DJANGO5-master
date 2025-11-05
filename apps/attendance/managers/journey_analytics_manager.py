"""
Journey analytics manager for PeopleEventlog.

Handles journey pattern analysis and transport mode tracking.
"""
from django.db.models import Count, Avg, Max, Min, Sum, F
import logging

logger = logging.getLogger("django")


class JourneyAnalyticsManagerMixin:
    """
    Manager mixin for journey pattern analysis.

    Provides methods for:
    - Journey statistics aggregation
    - Transport mode analysis
    - People-wise journey patterns
    - Journey efficiency metrics
    """

    def get_spatial_journey_analytics(self, client_id, date_from, date_to, people_ids=None):
        """Analyze journey patterns using spatial data"""
        base_query = (self.filter(
            client_id=client_id,
            datefor__range=(date_from, date_to),
            journeypath__isnull=False,
            startlocation__isnull=False,
            endlocation__isnull=False,
            distance__isnull=False,
            duration__isnull=False
        ).exclude(distance=0))

        if people_ids:
            base_query = base_query.filter(people_id__in=people_ids)

        # Journey aggregations
        journey_stats = base_query.aggregate(
            total_journeys=Count('id'),
            avg_distance=Avg('distance'),
            total_distance=Sum('distance'),
            max_distance=Max('distance'),
            min_distance=Min('distance'),
            avg_duration=Avg('duration'),
            total_duration=Sum('duration'),
            max_duration=Max('duration'),
            min_duration=Min('duration'),
            unique_travelers=Count('people_id', distinct=True)
        )

        # Journey efficiency (distance/duration ratio)
        efficiency_data = base_query.extra(
            select={'efficiency': 'distance / NULLIF(duration, 0)'}
        ).aggregate(
            avg_efficiency=Avg('efficiency'),
            max_efficiency=Max('efficiency'),
            min_efficiency=Min('efficiency')
        )

        # People-wise journey patterns
        people_patterns = (base_query
            .values('people_id', 'people__peoplename')
            .annotate(
                journey_count=Count('id'),
                total_distance=Sum('distance'),
                avg_distance=Avg('distance'),
                total_duration=Sum('duration'),
                avg_duration=Avg('duration'),
                avg_efficiency=Avg(F('distance') / F('duration'))
            )
            .filter(journey_count__gte=2)
            .order_by('-total_distance')[:20]
        )

        # Transport mode analysis
        transport_records = base_query.values_list('transportmodes', flat=True)
        transport_counts = {}
        for modes in transport_records:
            if modes:
                for mode in modes:
                    transport_counts[mode] = transport_counts.get(mode, 0) + 1

        transport_analysis = [
            {'mode': mode, 'count': count, 'percentage': (count/len(transport_records))*100}
            for mode, count in sorted(transport_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            'journey_stats': journey_stats,
            'efficiency_metrics': efficiency_data,
            'people_patterns': list(people_patterns),
            'transport_mode_analysis': transport_analysis
        }
