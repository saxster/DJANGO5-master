"""
Geofence compliance analytics manager for PeopleEventlog.

Handles geofence compliance tracking and violation analysis.
"""
import logging

logger = logging.getLogger("django")


class ComplianceAnalyticsManagerMixin:
    """
    Manager mixin for geofence compliance analytics.

    Provides methods for:
    - Geofence compliance rate calculations
    - BU-level compliance tracking
    - People-level compliance tracking
    - Daily compliance trends
    """

    def get_geofence_compliance_analytics(self, client_id, date_from, date_to, bu_ids=None):
        """Analyze geofence compliance patterns and statistics"""
        base_query = self.filter(
            client_id=client_id,
            datefor__range=(date_from, date_to),
            peventtype__tacode__in=['SELF', 'SELFATTENDANCE', 'MARK', 'MARKATTENDANCE'],
            startlocation__isnull=False
        )

        if bu_ids:
            base_query = base_query.filter(bu_id__in=bu_ids)

        # Overall compliance statistics
        total_records = base_query.count()

        # Parse JSON extras for geofence compliance data
        compliance_data = base_query.extra(
            select={
                'start_in_geofence': "peventlogextras->>'isStartLocationInGeofence'",
                'end_in_geofence': "peventlogextras->>'isEndLocationInGeofence'"
            }
        ).values(
            'bu_id', 'bu__buname', 'people_id', 'people__peoplename',
            'start_in_geofence', 'end_in_geofence', 'datefor'
        )

        # Compliance by business unit
        bu_compliance = {}
        people_compliance = {}
        daily_compliance = {}

        for record in compliance_data:
            bu_id = record['bu_id']
            people_id = record['people_id']
            date_key = record['datefor'].strftime('%Y-%m-%d')

            # Initialize counters
            if bu_id not in bu_compliance:
                bu_compliance[bu_id] = {
                    'name': record['bu__buname'],
                    'total': 0, 'compliant_start': 0, 'compliant_end': 0
                }

            if people_id not in people_compliance:
                people_compliance[people_id] = {
                    'name': record['people__peoplename'],
                    'total': 0, 'compliant_start': 0, 'compliant_end': 0
                }

            if date_key not in daily_compliance:
                daily_compliance[date_key] = {
                    'total': 0, 'compliant_start': 0, 'compliant_end': 0
                }

            # Count compliance
            bu_compliance[bu_id]['total'] += 1
            people_compliance[people_id]['total'] += 1
            daily_compliance[date_key]['total'] += 1

            if record['start_in_geofence'] == 'true':
                bu_compliance[bu_id]['compliant_start'] += 1
                people_compliance[people_id]['compliant_start'] += 1
                daily_compliance[date_key]['compliant_start'] += 1

            if record['end_in_geofence'] == 'true':
                bu_compliance[bu_id]['compliant_end'] += 1
                people_compliance[people_id]['compliant_end'] += 1
                daily_compliance[date_key]['compliant_end'] += 1

        # Calculate compliance percentages
        for bu_data in bu_compliance.values():
            if bu_data['total'] > 0:
                bu_data['start_compliance_rate'] = (bu_data['compliant_start'] / bu_data['total']) * 100
                bu_data['end_compliance_rate'] = (bu_data['compliant_end'] / bu_data['total']) * 100

        return {
            'total_records': total_records,
            'bu_compliance': bu_compliance,
            'people_compliance': dict(list(people_compliance.items())[:20]),  # Top 20 for performance
            'daily_trends': daily_compliance,
            'overall_compliance_rate': (
                sum(data['compliant_start'] for data in bu_compliance.values()) /
                max(sum(data['total'] for data in bu_compliance.values()), 1)
            ) * 100 if bu_compliance else 0
        }
