"""
Optimized Attendance Managers

This module contains optimized manager methods that fix Django anti-patterns:
- Added missing select_related() and prefetch_related() calls
- Implemented proper query optimization for complex operations
- Fixed N+1 query problems
- Added proper error handling and logging
- Implemented query result caching where appropriate

This demonstrates the improved database access patterns.
"""

from datetime import timedelta, datetime, date
from django.db import models
from django.contrib.gis.db.models.functions import AsGeoJSON, AsWKT
from django.db.models import F, Q, Exists, CharField, OuterRef, Prefetch
from django.db.models.functions import Cast
from django.core.cache import cache
from apps.core import utils
from apps.activity.models.attachment_model import Attachment
from apps.activity.models.job_model import Job
from apps.client_onboarding.models import Shift
from apps.core_onboarding.models import GeofenceMaster
from itertools import chain
import json
import logging

logger = logging.getLogger("django")
Q = models.Q

# Import centralized JSON utility
from apps.core.json_utils import safe_json_parse_params


class OptimizedPELManager(models.Manager):
    """
    Optimized People Event Log Manager

    This manager fixes several Django anti-patterns:
    - Adds missing select_related() calls to prevent N+1 queries
    - Implements proper prefetch_related() for complex relationships
    - Adds query result caching for expensive operations
    - Implements proper error handling and logging
    """

    use_in_migrations = True

    def get_current_month_sitevisitorlog(self, peopleid):
        """
        Optimized: Added select_related to prevent N+1 queries
        """
        cache_key = f"sitevisitor_log_{peopleid}_{date.today()}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        qset = self.select_related(
            "bu", "peventtype", "people", "client"  # Added missing relationships
        ).filter(
            ~Q(people_id=-1),
            peventtype__tacode="AUDIT",
            people_id=peopleid,
            datefor__gte=date.today() - timedelta(days=7),
        ).order_by('-datefor')  # Added explicit ordering

        # Cache result for 5 minutes
        cache.set(cache_key, qset, 300)

        return qset or self.none()

    def get_people_attachment_optimized(self, pelogid, db=None):
        """
        Optimized: Added proper query optimization and error handling
        """
        try:
            # Define valid attachments subquery with select_related
            valid_attachments = Attachment.objects.select_related(
                'attachment_type'
            ).filter(
                owner=Cast(OuterRef('uuid'), CharField())
            ).exclude(
                Q(filename__iendswith='.3gp') |
                Q(filename__iendswith='.mp4') |
                Q(filename__iendswith='.csv') |
                Q(filename__iendswith='.txt')
            )

            # Build main query with optimizations
            queryset = self.select_related(
                'people', 'peventtype', 'bu', 'client'
            ).filter(
                uuid=pelogid,
                peventtype__tacode__in=['MARK', 'SELF', 'TAKE', 'AUDIT']
            ).annotate(
                has_valid_attachments=Exists(valid_attachments)
            ).filter(
                has_valid_attachments=True
            )

            # Apply database routing if specified
            if db:
                queryset = queryset.using(db)

            # Return first result with specific fields only
            result = queryset.values('people_id', 'id', 'uuid').first()
            return result if result else self.none()

        except Exception as e:
            logger.error(f"Error in get_people_attachment_optimized: {str(e)}", exc_info=True)
            return self.none()

    def get_peopleevents_listview_optimized(self, related, fields, request):
        """
        Optimized: Improved query performance with proper relationships and caching
        """
        try:
            R, S = request.GET, request.session
            P = safe_json_parse_params(R)

            # Cache key based on request parameters
            cache_key = f"peopleevents_{S.get('client_id')}_{P.get('from')}_{P.get('to')}"
            cached_result = cache.get(cache_key)

            if cached_result is not None:
                return cached_result

            # Optimized query with all necessary relationships
            qset = (
                self.select_related(
                    'people', 'peventtype', 'bu', 'client', 'shift', 'verifiedby', 'geofence'
                ).prefetch_related(
                    Prefetch(
                        'attachments',
                        queryset=Attachment.objects.select_related('attachment_type')
                    )
                ).annotate(
                    sL=AsGeoJSON("startlocation"),
                    eL=AsGeoJSON("endlocation")
                ).filter(
                    bu_id__in=S["assignedsites"],
                    client_id=S["client_id"],
                    datefor__gte=P["from"],
                    datefor__lte=P["to"],
                    peventtype__tacode__in=[
                        "SELF", "SELFATTENDANCE", "MARK", "MRKATTENDANCE",
                    ],
                ).exclude(id=1).values(*fields).order_by("-datefor")
            )

            # Cache result for 2 minutes
            cache.set(cache_key, qset, 120)

            return qset or self.none()

        except Exception as e:
            logger.error(f"Error in get_peopleevents_listview_optimized: {str(e)}", exc_info=True)
            return self.none()

    def get_lastmonth_conveyance_optimized(self, request, fields, related):
        """
        Optimized: Added proper relationship loading and reduced query complexity
        """
        try:
            R, S = request.GET, request.session
            P = safe_json_parse_params(R)

            # Build optimized query with all relationships loaded at once
            qset = (
                self.select_related(
                    "bu", "people", "client", "peventtype", "shift"
                ).prefetch_related(
                    Prefetch('people__bu', queryset=models.QuerySet()),  # Optimize people relationships
                ).annotate(
                    start=AsGeoJSON("startlocation"),
                    end=AsGeoJSON("endlocation")
                ).filter(
                    peventtype__tacode="CONVEYANCE",
                    punchintime__date__gte=P["from"],
                    punchintime__date__lte=P["to"],
                    client_id=S["client_id"],
                ).exclude(
                    endlocation__isnull=True
                ).values(*fields).order_by("-punchintime")
            )

            return qset or self.none()

        except Exception as e:
            logger.error(f"Error in get_lastmonth_conveyance_optimized: {str(e)}", exc_info=True)
            return self.none()

    def get_peopleeventlog_history_optimized(
        self, mdtz, people_id, bu_id, client_id, ctzoffset, peventtypeid
    ):
        """
        Optimized: Added comprehensive relationship loading to prevent N+1 queries
        """
        try:
            qset = (
                self.select_related(
                    "people",
                    "bu",
                    "client",
                    "verifiedby",
                    "peventtype",
                    "geofence",
                    "shift",
                    # Add related model optimizations
                    "people__bu",
                    "people__client"
                ).prefetch_related(
                    # Prefetch related attachments if needed
                    Prefetch(
                        'attachments',
                        queryset=Attachment.objects.select_related('attachment_type').order_by('id')
                    )
                ).filter(
                    mdtz__gte=mdtz,
                    people_id=people_id,
                    bu_id=bu_id,
                    client_id=client_id,
                    peventtype_id__in=peventtypeid,
                ).order_by("-datefor").values(
                    "uuid", "people_id", "client_id", "bu_id", "shift_id",
                    "verifiedby_id", "geofence_id", "id", "peventtype_id",
                    "punchintime", "punchouttime", "datefor", "distance",
                    "duration", "expamt", "accuracy", "deviceid",
                    "startlocation", "endlocation", "ctzoffset", "remarks",
                    "facerecognitionin", "facerecognitionout", "otherlocation",
                    "reference", "mdtz",
                )
            )

            return qset or self.none()

        except Exception as e:
            logger.error(f"Error in get_peopleeventlog_history_optimized: {str(e)}", exc_info=True)
            return self.none()

    def fetch_sos_events_optimized(self, start_date, end_date, session):
        """
        Optimized: Added proper relationship loading and field optimization
        """
        try:
            return (
                self.select_related(
                    "peventtype",
                    "people",
                    "bu",
                    "client"  # Added missing client relationship
                ).filter(
                    bu_id__in=session["assignedsites"],
                    client_id=session["client_id"],
                    peventtype__tacode="SOS",
                    datefor__gte=start_date,
                    datefor__lte=end_date,
                ).values(
                    "id", "ctzoffset", "people__peoplename", "cdtz", "uuid",
                    "people__peoplecode", "people__mobno", "people__email",
                    "bu__buname",
                ).order_by('-datefor')  # Added explicit ordering
            )

        except Exception as e:
            logger.error(f"Error in fetch_sos_events_optimized: {str(e)}", exc_info=True)
            return self.none()

    def get_sos_listview_optimized(self, request):
        """
        Optimized: Combined queries and added caching for attachment data
        """
        try:
            R, S = request.GET, request.session
            P = safe_json_parse_params(R)
            from_date, to_date = P["from"], P["to"]

            # Get events with optimized query
            events = list(self.fetch_sos_events_optimized(from_date, to_date, S))

            if not events:
                return []

            # Batch fetch attachments to avoid N+1 queries
            uuids = [event["uuid"] for event in events]
            attachments = self.fetch_attachments_optimized(uuids)

            # Merge events with attachments efficiently
            merged_events = list(self.merge_with_attachments(events, attachments))

            return merged_events

        except Exception as e:
            logger.error(f"Error in get_sos_listview_optimized: {str(e)}", exc_info=True)
            return []

    def fetch_attachments_optimized(self, uuids):
        """
        Optimized: Batch fetch attachments with proper relationships
        """
        try:
            attachments = Attachment.objects.select_related(
                'attachment_type'
            ).filter(
                owner__in=uuids
            ).values(
                "owner", "filepath", "filename", "attachment_type__name"
            )

            return {att["owner"]: att for att in attachments}

        except Exception as e:
            logger.error(f"Error in fetch_attachments_optimized: {str(e)}", exc_info=True)
            return {}

    def get_people_event_log_punch_ins_optimized(self, datefor, buid, peopleid):
        """
        Optimized: Added comprehensive relationship loading and proper date handling
        """
        try:
            event_type = (
                ["MARK", "MARKATTENDANCE"] if peopleid == -1 else ["SELF", "SELFATTENDANCE"]
            )
            given_date = datefor
            previous_date = given_date - timedelta(days=1)

            qset = (
                self.select_related(
                    "client", "bu", "shift", "verifiedby", "geofence",
                    "peventtype", "people"
                ).filter(
                    datefor__range=(previous_date, given_date),
                    punchouttime__isnull=True,
                    bu_id=buid,
                    peventtype__tacode__in=event_type,
                ).values(
                    "uuid", "people_id", "client_id", "bu_id", "shift_id",
                    "verifiedby_id", "geofence_id", "id", "peventtype_id",
                    "transportmodes", "punchintime", "punchouttime", "datefor",
                    "distance", "cuser_id", "muser_id", "cdtz", "mdtz",
                    "ctzoffset", "duration", "expamt", "accuracy", "deviceid",
                    "startlocation", "endlocation", "remarks", "facerecognitionin",
                    "facerecognitionout", "otherlocation", "reference", "tenant_id",
                ).order_by("punchintime")
            )

            # Process results efficiently
            results = []
            for entry in qset.iterator():  # Use iterator for memory efficiency
                entry["transportmodes"] = "NONE"
                results.append(entry)

            return results

        except Exception as e:
            logger.error(f"Error in get_people_event_log_punch_ins_optimized: {str(e)}", exc_info=True)
            return []

    def get_geofencetracking_optimized(self, request):
        """
        Optimized: Added proper pagination and relationship loading
        """
        try:
            qobjs, dir, fields, length, start = utils.get_qobjs_dir_fields_start_length(
                request.GET
            )
            last8days = date.today() - timedelta(days=8)

            # Base query with optimization
            base_query = (
                self.select_related(
                    "people", "peventtype", "geofence", "bu", "client"
                ).annotate(
                    slocation=AsWKT("startlocation"),
                    elocation=AsWKT("endlocation"),
                ).filter(
                    peventtype__tacode="GEOFENCE",
                    datefor__gte=last8days,
                    bu_id=request.session["bu_id"],
                )
            )

            # Get total count efficiently
            total = base_query.count()

            if qobjs:
                # Apply filters and get filtered count
                filtered_query = base_query.filter(qobjs)
                fcount = filtered_query.count()

                # Get paginated results
                filtered_results = filtered_query.values(*fields).order_by(dir)[start:start + length]
                return total, fcount, filtered_results

            # Get paginated results without additional filtering
            results = base_query.values(*fields).order_by(dir)[start:start + length]
            return total, total, results

        except Exception as e:
            logger.error(f"Error in get_geofencetracking_optimized: {str(e)}", exc_info=True)
            return 0, 0, self.none()

    def get_sitevisited_log_optimized(self, clientid, peopleid, ctzoffset):
        """
        Optimized: Added proper relationship loading and date calculation
        """
        try:
            seven_days_ago = (datetime.now() + timedelta(minutes=ctzoffset)) - timedelta(days=7)

            return (
                self.select_related(
                    "peventtype", "bu", "people", "client"
                ).filter(
                    people_id=peopleid,
                    client_id=clientid,
                    punchouttime__lte=seven_days_ago,
                    peventtype__tacode="SITEVISIT",
                ).annotate(
                    buname=F("bu__buname"),
                    bucode=F("bu__bucode")
                ).values(
                    "id", "bu_id", "punchintime", "punchouttime",
                    "ctzoffset", "buname", "bucode", "otherlocation",
                ).order_by('-punchouttime')  # Added explicit ordering
            )

        except Exception as e:
            logger.error(f"Error in get_sitevisited_log_optimized: {str(e)}", exc_info=True)
            return self.none()

    def get_sitecrisis_types_optimized(self):
        """
        Optimized: Added caching for frequently accessed data
        """
        cache_key = "sitecrisis_types"
        cached_types = cache.get(cache_key)

        if cached_types is not None:
            return cached_types

        try:
            from apps.core_onboarding.models import TypeAssist

            types = list(
                TypeAssist.objects.select_related("tatype").filter(
                    tatype__tacode="SITECRISIS"
                ).values_list("tacode", flat=True)
            )

            # Cache for 1 hour since this data doesn't change frequently
            cache.set(cache_key, types, 3600)

            return types

        except Exception as e:
            logger.error(f"Error in get_sitecrisis_types_optimized: {str(e)}", exc_info=True)
            return []

    def fetch_sitecrisis_events_optimized(self, start_date, end_date, session):
        """
        Optimized: Added proper relationship loading and efficient filtering
        """
        try:
            return (
                self.select_related(
                    "peventtype", "people", "bu", "client"
                ).filter(
                    Q(startlocation__isnull=False),
                    datefor__gte=start_date,
                    datefor__lte=end_date,
                    bu_id__in=session["assignedsites"],
                    peventtype__tacode__in=self.get_sitecrisis_types_optimized(),
                ).annotate(
                    gps=AsGeoJSON("startlocation")
                ).values(
                    "people__peoplename", "people__peoplecode", "gps",
                    "reference", "cdtz", "bu__buname", "bu__bucode",
                    "ctzoffset", "people__mobno", "people__email",
                    "uuid", "id",
                ).order_by('-datefor')  # Added explicit ordering
            )

        except Exception as e:
            logger.error(f"Error in fetch_sitecrisis_events_optimized: {str(e)}", exc_info=True)
            return self.none()

    # Keep the original method signatures for backward compatibility
    merge_with_attachments = OptimizedPELManager.merge_with_attachments if hasattr(lambda: None, 'merge_with_attachments') else lambda self, events, attachments: (
        {**event, **attachments.get(str(event["uuid"]), {"filepath": None, "filename": None})}
        for event in events
    )