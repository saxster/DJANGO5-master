"""
Face recognition update manager for PeopleEventlog.

Handles FR result updates with race condition protection and geofence validation.
"""
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from apps.activity.models.job_model import Job
from apps.client_onboarding.models import Shift
from apps.core_onboarding.models import GeofenceMaster
import logging

logger = logging.getLogger("django")


class FRUpdateManagerMixin:
    """
    Manager mixin for face recognition result updates.

    Provides methods for:
    - Updating FR results with distributed locks
    - Geofence validation during FR updates
    - Automatic shift detection
    """

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
        from apps.core import utils

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

                # Geofence validation
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
                            from apps.attendance.services.geospatial_service import GeospatialService

                            if obj.startlocation:
                                lon, lat = GeospatialService.extract_coordinates(obj.startlocation)
                                isStartLocationInGeofence = GeospatialService.is_point_in_geofence(
                                    lat, lon, geofence_data, use_hysteresis=True
                                )
                                logger.info(
                                    f"Is Start Location Inside of the geofence: {isStartLocationInGeofence}"
                                )
                                extras["isStartLocationInGeofence"] = isStartLocationInGeofence

                            if obj.endlocation:
                                lon, lat = GeospatialService.extract_coordinates(obj.endlocation)
                                isEndLocationInGeofence = GeospatialService.is_point_in_geofence(
                                    lat, lon, geofence_data, use_hysteresis=True
                                )
                                logger.info(
                                    f"Is End Location Inside of the geofence: {isEndLocationInGeofence}"
                                )
                                extras["isEndLocationInGeofence"] = isEndLocationInGeofence

                # Auto-detect shift if needed
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
