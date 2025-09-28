"""
Attendance and People report queries.

Handles people attendance summary reports.
"""

from typing import List, Dict
from django.db.models import F, Min, Max
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AttendanceReports:
    """Report queries for attendance."""

    @staticmethod
    def peopleattendancesummary_report(timezone_str: str, siteids: str, from_date, upto_date) -> List[Dict]:
        """People attendance summary report."""
        from apps.attendance.models import PeopleEventlog
        from apps.peoples.models import People

        site_id_list = [int(id.strip()) for id in siteids.split(',') if id.strip()]

        if isinstance(from_date, str):
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
        if isinstance(upto_date, str):
            upto_date = datetime.strptime(upto_date, '%Y-%m-%d').date()

        aggregated_attendance = (
            PeopleEventlog.objects
            .filter(
                bu_id__in=site_id_list,
                datefor__range=[from_date, upto_date],
                punchouttime__date=F('datefor'),
                peventtype__tacode__in=['SELF', 'MARK']
            )
            .values('people_id', 'datefor')
            .annotate(
                min_punchintime=Min('punchintime'),
                max_punchouttime=Max('punchouttime')
            )
        )

        result = []
        for attendance in aggregated_attendance:
            try:
                person = People.objects.select_related(
                    'designation', 'department'
                ).get(id=attendance['people_id'])

                punch_in = attendance['min_punchintime']
                punch_out = attendance['max_punchouttime']

                if punch_in and punch_out:
                    total_seconds = (punch_out - punch_in).total_seconds()
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    total_time = f"{hours}:{minutes:02d}"
                else:
                    total_time = "0:00"

                result.append({
                    'department': person.designation.taname if person.designation else '',
                    'designation': person.department.taname if person.department else '',
                    'peoplename': person.peoplename,
                    'peoplecode': person.peoplecode,
                    'day': attendance['datefor'].day,
                    'day_of_week': attendance['datefor'].strftime('%A'),
                    'punch_intime': punch_in.strftime('%H:%M') if punch_in else '',
                    'punch_outtime': punch_out.strftime('%H:%M') if punch_out else '',
                    'totaltime': total_time
                })

            except People.DoesNotExist:
                continue

        result.sort(key=lambda x: x['day'])

        return result