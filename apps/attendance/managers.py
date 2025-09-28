from datetime import timedelta, datetime, date
from django.db import models
from django.contrib.gis.db.models.functions import AsGeoJSON, AsWKT
from apps.core import utils
from apps.activity.models.attachment_model import Attachment
from apps.activity.models.job_model import Job
from apps.onboarding.models import Shift
from apps.onboarding.models import GeofenceMaster
from django.db.models import F,Q,Exists,CharField,OuterRef
from django.db.models.functions import Cast
from itertools import chain
import json
import logging

logger = logging.getLogger("django")
Q = models.Q

# Import centralized JSON utility
from apps.core.json_utils import safe_json_parse_params


class PELManager(models.Manager):
    use_in_migrations = True

    def get_current_month_sitevisitorlog(self, peopleid):
        qset = self.select_related("bu", "peventtype").filter(
            ~Q(people_id=-1),
            peventtype__tacode="AUDIT",
            people_id=peopleid,
            datefor__gte=datetime.date() - timedelta(days=7),
        )
        return qset or self.none()

    def get_people_attachment(self, pelogid, db=None):
        # Define valid attachments subquery
        valid_attachments = Attachment.objects.filter(
            owner=Cast(OuterRef('uuid'), CharField())
        ).exclude(
            Q(filename__iendswith='.3gp') | 
            Q(filename__iendswith='.mp4') | 
            Q(filename__iendswith='.csv') | 
            Q(filename__iendswith='.txt')
        )

        # Build main query
        queryset = self.filter(
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
        # Return first result or none
        result = queryset.values('people_id', 'id', 'uuid').first()
        return result if result else self.none()

    def get_lat_long(self, location):
        import re

        match = re.search(r"POINT \(([-\d.]+) ([-\d.]+)\)", str(location))
        if match:
            longitude = float(match.group(1))
            latitude = float(match.group(2))
        return [longitude, latitude]

    def is_point_in_geofence(self, lat, lon, geofence):
        """
        Check if a point is within a geofence using centralized service.
        Deprecated: Use apps.core.services.geofence_service instead.
        
        Args:
            lat (float): Latitude of the point to check.
            lon (float): Longitude of the point to check.
            geofence (Polygon or tuple): Polygon object representing geofence or a tuple (center_lat, center_lon, radius_km) for a circular geofence.
        Returns:
            bool: True if the point is inside the geofence, False otherwise.
        """
        try:
            from apps.core.services.geofence_service import geofence_service
            return geofence_service.is_point_in_geofence(lat, lon, geofence, use_hysteresis=True)
        except ImportError:
            # Fallback to legacy implementation if service not available
            from math import radians, sin, cos, sqrt, atan2
            from django.contrib.gis.geos import Point, Polygon

            # Create a Point object from the lat, lon
            point = Point(lon, lat)  # Note: Point expects (longitude, latitude)

            # Case 1: Geofence is a polygon (Django GEOS Polygon object)
            if isinstance(geofence, Polygon):
                return geofence.contains(point)

            # Case 2: Geofence is circular (tuple with center lat, lon, and radius in km)
            elif isinstance(geofence, tuple) and len(geofence) == 3:
                geofence_lat, geofence_lon, radius_km = geofence

                # Calculate distance using Haversine formula
                # Convert lat/lon from degrees to radians
                lat1 = radians(lat)
                lon1 = radians(lon)
                lat2 = radians(geofence_lat)
                lon2 = radians(geofence_lon)

                # Haversine formula
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                c = 2 * atan2(sqrt(a), sqrt(1 - a))
                distance_km = 6371 * c  # Radius of Earth in kilometers

                # Check if the distance is within the geofence radius
                return distance_km <= radius_km

            # If geofence is neither a polygon nor a circular geofence, return False
            return False

    def update_fr_results(self, result, uuid, peopleid, db):
        """
        Update face recognition results with race condition protection

        Uses distributed lock + row-level locking to prevent concurrent updates
        from corrupting verification data.

        Args:
            result: Dict containing 'verified' (bool) and 'distance' (float)
            uuid: UUID of the attendance record
            peopleid: ID of the person
            db: Database alias to use

        Returns:
            bool: True if update successful, False otherwise

        Raises:
            Exception: On database or locking errors
        """
        from django.db import transaction
        from apps.core.utils_new.distributed_locks import distributed_lock

        logger.info("update_fr_results started results:%s", result)

        try:
            with distributed_lock(f"attendance_update:{uuid}", timeout=10), transaction.atomic():
                obj = self.select_for_update().filter(uuid=uuid).using(db).first()

                if not obj:
                    logger.warning(f"No attendance record found for uuid: {uuid}")
                    return False

                logger.info(
                    "Retrieved locked obj punchintime: %s punchouttime: %s startlocation: %s endlocation: %s peopleid: %s",
                    obj.punchintime,
                    obj.punchouttime,
                    obj.startlocation,
                    obj.endlocation,
                    peopleid,
                )

                extras = dict(obj.peventlogextras)
                logger.info(f"Current extras: {extras}")

                update_fields = ['peventlogextras']

                if obj.punchintime and extras.get("distance_in") is None:
                    extras["verified_in"] = bool(result["verified"])
                    extras["distance_in"] = result["distance"]
                    obj.facerecognitionin = extras["verified_in"]
                    update_fields.append('facerecognitionin')
                    logger.info("Updated punch-in verification data")

                elif obj.punchouttime and extras.get("distance_out") is None:
                    extras["verified_out"] = bool(result["verified"])
                    extras["distance_out"] = result["distance"]
                    obj.facerecognitionout = extras["verified_out"]
                    update_fields.append('facerecognitionout')
                    logger.info("Updated punch-out verification data")

                get_people = Job.objects.filter(
                    people_id=peopleid, identifier="GEOFENCE"
                ).values()

                if get_people:
                    get_geofence_data = (
                        GeofenceMaster.objects.filter(
                            id=get_people[0]["geofence_id"], enable=True
                        )
                        .exclude(id=1)
                        .values()
                    )

                    if get_geofence_data:
                        geofence_data = get_geofence_data[0]["geofence"]

                        if geofence_data:
                            start_location = obj.startlocation
                            end_location = obj.endlocation

                            if start_location:
                                start_location_arr = self.get_lat_long(start_location)
                                longitude, latitude = (
                                    start_location_arr[0],
                                    start_location_arr[1],
                                )
                                isStartLocationInGeofence = self.is_point_in_geofence(
                                    latitude, longitude, geofence_data
                                )
                                logger.info(
                                    f"Is Start Location Inside of the geofence: {isStartLocationInGeofence}"
                                )
                                extras["isStartLocationInGeofence"] = isStartLocationInGeofence

                            if end_location:
                                end_location_arr = self.get_lat_long(end_location)
                                longitude, latitude = end_location_arr[0], end_location_arr[1]
                                isEndLocationInGeofence = self.is_point_in_geofence(
                                    latitude, longitude, geofence_data
                                )
                                logger.info(
                                    f"Is End Location Inside of the geofence: {isEndLocationInGeofence}"
                                )
                                extras["isEndLocationInGeofence"] = isEndLocationInGeofence

                if obj.punchintime and obj.shift_id == 1:
                    logger.info(f"Auto-detecting shift for punchintime {obj.punchintime}")
                    punchintime = obj.punchintime
                    client_id = obj.client_id
                    site_id = obj.bu_id
                    all_shifts_under_site = Shift.objects.filter(
                        client_id=client_id, bu_id=site_id
                    )
                    logger.info(
                        f"Found {all_shifts_under_site.count()} shifts at site"
                    )
                    updated_shift_id = utils.find_closest_shift(
                        punchintime, all_shifts_under_site
                    )
                    logger.info(f"Detected shift_id: {updated_shift_id}")

                    obj.shift_id = updated_shift_id
                    update_fields.append('shift_id')

                obj.peventlogextras = extras
                obj.save(update_fields=update_fields)

                logger.info(f"Successfully updated attendance {obj.id} with FR results")
                return True

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(
                f"Error updating FR results for uuid {uuid}: {str(e)}",
                exc_info=True
            )
            raise

    def get_fr_status(self, R):
        "return fr images and status"
        qset = self.filter(id=R["id"]).values("uuid", "peventlogextras")
        if atts := Attachment.objects.filter(owner=qset[0]["uuid"]).values(
            "filepath", "filename", "attachmenttype", "datetime", "gpslocation"
        ):
            return list(chain(qset, atts))
        return list(self.none())

    def get_peopleevents_listview(self, related, fields, request):
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        qset = (
            self.select_related(*related)
            .annotate(sL=AsGeoJSON("startlocation"), eL=AsGeoJSON("endlocation"))
            .filter(
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
                datefor__gte=P["from"],
                datefor__lte=P["to"],
                peventtype__tacode__in=[
                    "SELF",
                    "SELFATTENDANCE",
                    "MARK",
                    "MRKATTENDANCE",
                ],
            )
            .exclude(id=1)
            .values(*fields)
            .order_by("-datefor")
        )
        return qset or self.none()

    def get_lastmonth_conveyance(self, request, fields, related):
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        qset = (
            self.select_related("bu", "people")
            .annotate(start=AsGeoJSON("startlocation"), end=AsGeoJSON("endlocation"))
            .filter(
                peventtype__tacode="CONVEYANCE",
                punchintime__date__gte=P["from"],
                punchintime__date__lte=P["to"],
                client_id=S["client_id"],
            )
            .exclude(endlocation__isnull=True)
            .select_related(*related)
            .values(*fields)
            .order_by("-punchintime")
        )
        return qset or self.none()

    def getjourneycoords(self, id):
        import json

        qset = (
            self.annotate(path=AsGeoJSON("journeypath"))
            .filter(id=id)
            .values(
                "path",
                "punchintime",
                "punchouttime",
                "deviceid",
                "expamt",
                "accuracy",
                "people__peoplename",
                "people__peoplecode",
                "distance",
                "duration",
                "transportmodes",
            )
        )
        for obj in qset:
            if obj["path"]:
                geodict = json.loads(obj["path"])
                coords = [
                    {"lat": lat, "lng": lng} for lng, lat in geodict["coordinates"]
                ]
                waypoints = utils.orderedRandom(coords[1:-1], k=25)
                obj["path"] = coords
                obj["waypoints"] = waypoints
                coords, waypoints = [], []
            else:
                return self.none()
        return qset or self.none()

    def get_geofencetracking(self, request):
        "List View"
        qobjs, dir, fields, length, start = utils.get_qobjs_dir_fields_start_length(
            request.GET
        )
        last8days = date.today() - timedelta(days=8)
        qset = (
            self.annotate(
                slocation=AsWKT("startlocation"),
                elocation=AsWKT("endlocation"),
            )
            .filter(
                peventtype__tacode="GEOFENCE",
                datefor__gte=last8days,
                bu_id=request.session["bu_id"],
            )
            .select_related("people", "peventtype", "geofence")
            .values(*fields)
            .order_by(dir)
        )
        total = qset.count()
        if qobjs:
            filteredqset = qset.filter(qobjs)
            fcount = filteredqset.count()
            filteredqset = filteredqset[start : start + length]
            return total, fcount, filteredqset
        qset = qset[start : start + length]
        return total, total, qset

    def get_sos_count_forcard(self, request):
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        data = self.filter(
            bu_id__in=S["assignedsites"],
            client_id=S["client_id"],
            peventtype__tacode="SOS",
            datefor__gte=pd1,
            datefor__lte=pd2,
        ).count()
        return data

    def get_sitecrisis_count_forcard(self, request):
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())

        data = self.fetch_sitecrisis_events(pd1, pd2, S).count()
        return data

    def get_frfail_count_forcard(self, request):
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        data = (
            self.filter(
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
                datefor__gte=pd1,
                datefor__lte=pd2,
                peventtype__tacode__in=[
                    "SELF",
                    "SELFATTENDANCE",
                    "MARKATTENDANCE",
                    "MARK",
                ],
            )
            .exclude(id=1)
            .count()
        )
        return data

    def get_peopleeventlog_history(
        self, mdtz, people_id, bu_id, client_id, ctzoffset, peventtypeid
    ):
        qset = (
            self.filter(
                mdtz__gte=mdtz,
                people_id=people_id,
                bu_id=bu_id,
                client_id=client_id,
                peventtype_id__in=peventtypeid,
            )
            .select_related(
                "people",
                "bu",
                "client",
                "verifiedby",
                "peventtype",
                "geofence",
                "shift",
            )
            .order_by("-datefor")
            .values(
                "uuid",
                "people_id",
                "client_id",
                "bu_id",
                "shift_id",
                "verifiedby_id",
                "geofence_id",
                "id",
                "peventtype_id",
                "punchintime",
                "punchouttime",
                "datefor",
                "distance",
                "duration",
                "expamt",
                "accuracy",
                "deviceid",
                "startlocation",
                "endlocation",
                "ctzoffset",
                "remarks",
                "facerecognitionin",
                "facerecognitionout",
                "otherlocation",
                "reference",
                "mdtz",
            )
        )
        return qset or self.none()

    def fetch_sos_events(self, start_date, end_date, session):
        return (
            self.filter(
                bu_id__in=session["assignedsites"],
                client_id=session["client_id"],
                peventtype__tacode="SOS",
                datefor__gte=start_date,
                datefor__lte=end_date,
            )
            .select_related("peventtype")
            .values(
                "id",
                "ctzoffset",
                "people__peoplename",
                "cdtz",
                "uuid",
                "people__peoplecode",
                "people__mobno",
                "people__email",
                "bu__buname",
            )
        )

    def fetch_attachments(self, uuids):
        from apps.activity.models.attachment_model import Attachment

        attachments = Attachment.objects.get_attforuuids(uuids).values(
            "owner", "filepath", "filename"
        )
        return {att["owner"]: att for att in attachments}

    def merge_with_attachments(self, events, attachments):
        for event in events:
            attachment = attachments.get(
                str(event["uuid"]), {"filepath": None, "filename": None}
            )
            yield {**event, **attachment}

    def get_sos_listview(self, request):
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        from_date, to_date = P["from"], P["to"]
        events = self.fetch_sos_events(from_date, to_date, request.session)
        uuids = [event["uuid"] for event in events]
        attachments = self.fetch_attachments(uuids)
        merged_events = list(self.merge_with_attachments(events, attachments))
        return merged_events or self.none()

    def get_people_event_log_punch_ins(self, datefor, buid, peopleid):
        type = (
            ["MARK", "MARKATTENDANCE"] if peopleid == -1 else ["SELF", "SELFATTENDANCE"]
        )
        given_date = datefor
        previous_date = given_date - timedelta(days=1)
        qset = (
            self.filter(
                datefor__range=(previous_date, given_date),
                punchouttime__isnull=True,
                bu_id=buid,
                peventtype__tacode__in=type,
            )
            .select_related(
                "client", "bu", "shift", "verifiedby", "geofence", "peventtype"
            )
            .values(
                "uuid",
                "people_id",
                "client_id",
                "bu_id",
                "shift_id",
                "verifiedby_id",
                "geofence_id",
                "id",
                "peventtype_id",
                "transportmodes",
                "punchintime",
                "punchouttime",
                "datefor",
                "distance",
                "cuser_id",
                "muser_id",
                "cdtz",
                "mdtz",
                "ctzoffset",
                "duration",
                "expamt",
                "accuracy",
                "deviceid",
                "startlocation",
                "endlocation",
                "remarks",
                "facerecognitionin",
                "facerecognitionout",
                "otherlocation",
                "reference",
                "tenant_id",
            )
            .order_by("punchintime")
        )
        if qset:
            for entry in qset:
                entry["transportmodes"] = "NONE"
        return qset or []

    def get_diversion_countorlist(self, request, count=False):
        R, S = request.GET, request.session
        pd1 = R.get("from", datetime.now().date())
        pd2 = R.get("upto", datetime.now().date())
        fields = [
            "people__peoplename",
            "start_gps",
            "end_gps",
            "reference",
            "datefor",
            "punchintime",
            "punchouttime",
            "ctzoffset",
            "id",
        ]
        qset = (
            self.select_related("people")
            .filter(
                Q(startlocation__isnull=False),
                peventtype__tacode="DIVERSION",
                datefor__gte=pd1,
                datefor__lte=pd2,
                bu_id__in=S["assignedsites"],
            )
            .annotate(
                start_gps=AsGeoJSON("startlocation"), end_gps=AsGeoJSON("endlocation")
            )
            .values(*fields)
        )
        data = list(qset) or []
        return data

    def get_sitecrisis_types(self):
        from apps.onboarding.models import TypeAssist

        qset = (
            TypeAssist.objects.filter(tatype__tacode="SITECRISIS")
            .select_related("tatype")
            .values_list("tacode", flat=True)
        )
        return qset or []

    def fetch_sitecrisis_events(self, start_date, end_date, session):
        return (
            self.filter(
                Q(startlocation__isnull=False),
                datefor__gte=start_date,
                datefor__lte=end_date,
                bu_id__in=session["assignedsites"],
                peventtype__tacode__in=self.get_sitecrisis_types(),
            )
            .select_related("peventtype")
            .annotate(gps=AsGeoJSON("startlocation"))
            .values(
                "people__peoplename",
                "people__peoplecode",
                "gps",
                "reference",
                "cdtz",
                "bu__buname",
                "bu__bucode",
                "ctzoffset",
                "people__mobno",
                "people__email",
                "uuid",
                "id",
            )
        )

    def get_sitecrisis_countorlist(self, request, count=False):
        R, S = request.GET, request.session
        P = safe_json_parse_params(R)
        fromdate, upto = P["from"], P["to"]
        events = self.fetch_sitecrisis_events(fromdate, upto, S)
        uuids = [event["uuid"] for event in events]
        attachments = self.fetch_attachments(uuids)
        merged_events = list(self.merge_with_attachments(events, attachments))
        if count:
            return len(merged_events)
        return merged_events or self.none()

    def get_sitevisited_log(self, clientid, peopleid, ctzoffset):
        seven_days_ago = (datetime.now() + timedelta(minutes=ctzoffset)) - timedelta(
            days=7
        )
        return (
            self.get_queryset()
            .filter(
                people_id=peopleid,
                client_id=clientid,
                punchouttime__lte=seven_days_ago,
                peventtype__tacode="SITEVISIT",  # assuming 'tacode' is a field in TypeAssist
            )
            .select_related("peventtype", "bu")
            .annotate(buname=F("bu__buname"), bucode=F("bu__bucode"))
            .values(
                "id",
                "bu_id",
                "punchintime",
                "punchouttime",
                "ctzoffset",
                "buname",
                "bucode",
                "otherlocation",
            )
            or self.none()
        )
