from apps.peoples.models import BaseModel
import uuid
from apps.tenants.models import TenantAwareModel
from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.gis.db.models import LineStringField, PointField, PolygonField
from django.utils.translation import gettext_lazy as _
from apps.attendance.managers import PELManager
from django.contrib.postgres.fields import ArrayField
from apps.core.utils_new.error_handling import safe_property
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import TypedDict, List, Optional
import copy
import logging
from concurrency.fields import VersionField

logger = logging.getLogger(__name__)

# Create your models here.


class PEventLogExtras(TypedDict):
    """TypedDict for peventlog extras JSON structure"""
    verified_in: bool
    distance_in: Optional[float]
    verified_out: bool
    distance_out: Optional[float]
    threshold: str
    model: str
    similarity_metric: str
    verification_attempts: int
    error_logs: List[str]


def peventlog_json() -> PEventLogExtras:
    """Return validated default JSON structure for peventlogextras"""
    return {
        "verified_in": False,
        "distance_in": None,
        "verified_out": False,
        "distance_out": None,
        "threshold": "0.3",
        "model": "Facenet512",
        "similarity_metric": "cosine",
        "verification_attempts": 0,
        "error_logs": []
    }


class PELGeoJson(TypedDict):
    """TypedDict for PEL GeoJSON structure"""
    startlocation: str
    endlocation: str


def pel_geojson() -> PELGeoJson:
    return {"startlocation": "", "endlocation": ""}


############## PeopleEventlog Table ###############


class PeopleEventlog(BaseModel, TenantAwareModel):
    class TransportMode(models.TextChoices):
        BIKE = ("BIKE", "Bike")
        RICKSHAW = ("RICKSHAW", "Rickshaw")
        BUS = ("BUS", "Bus")
        TRAIN = ("TRAIN", "Train")
        TRAM = ("TRAM", "Tram")
        PLANE = ("PLANE", "Plane")
        FERRY = ("FERRY", "Ferry")
        NONE = ("NONE", "NONE")
        CAR = ("CAR", "Car")
        TAXI = ("TAXI", "Taxi")
        OLA_UBER = ("OLA_UBER", "Ola/Uber")

    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        verbose_name="People",
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="clients",
    )
    bu = models.ForeignKey(
        "onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="bus",
    )
    shift = models.ForeignKey(
        "onboarding.Shift", null=True, blank=True, on_delete=models.RESTRICT
    )
    verifiedby = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="verifiedpeoples",
        verbose_name="Verified By",
    )
    geofence = models.ForeignKey(
        "onboarding.GeofenceMaster", null=True, blank=True, on_delete=models.RESTRICT
    )
    peventtype = models.ForeignKey(
        "onboarding.TypeAssist", null=True, blank=True, on_delete=models.RESTRICT
    )
    transportmodes = ArrayField(
        models.CharField(
            max_length=50,
            blank=True,
            choices=TransportMode.choices,
            default=TransportMode.NONE.value,
        ),
        default=list,
    )
    punchintime = models.DateTimeField(_("In"), null=True)
    punchouttime = models.DateTimeField(_("Out"), null=True)
    datefor = models.DateField(_("Date"), null=True)
    distance = models.FloatField(_("Distance"), null=True, blank=True)
    duration = models.IntegerField(_("Duration"), null=True, blank=True)
    expamt = models.FloatField(_("exampt"), default=0.0, null=True, blank=True)
    accuracy = models.FloatField(_("accuracy"), null=True, blank=True)
    deviceid = models.CharField(_("deviceid"), max_length=50, null=True, blank=True)
    startlocation = PointField(
        _("GPS-In"), null=True, geography=True, blank=True, srid=4326
    )
    endlocation = PointField(
        _("GPS-Out"), null=True, geography=True, blank=True, srid=4326
    )
    journeypath = LineStringField(geography=True, null=True, blank=True)
    remarks = models.CharField(_("remarks"), null=True, max_length=500, blank=True)
    facerecognitionin = models.BooleanField(
        _("Enable Face-Recognition In"), default=False, null=True, blank=True
    )
    facerecognitionout = models.BooleanField(
        _("Enable Face-Recognition Out"), default=False, null=True, blank=True
    )
    peventlogextras = models.JSONField(
        _("peventlogextras"),
        encoder=DjangoJSONEncoder,
        default=peventlog_json,
        help_text="JSON field for face recognition, geofence, and verification data"
    )
    otherlocation = models.CharField(_("Other Location"), max_length=50, null=True)
    reference = models.CharField("Reference", max_length=55, null=True)
    geojson = models.JSONField(default=pel_geojson, null=True, blank=True)

    # Optimistic locking for concurrent updates (Rule #17)
    version = VersionField()

    objects = PELManager()
    
    @property
    @safe_property(fallback_value="")
    def startlocation_display(self):
        """Returns a human-readable format of start location using geospatial service"""
        if self.startlocation:
            try:
                from apps.attendance.services.geospatial_service import GeospatialService
                lon, lat = GeospatialService.extract_coordinates(self.startlocation)
                return GeospatialService.format_coordinates(lat, lon)
            except (ImportError, ModuleNotFoundError) as e:
                logger.error(f"GeospatialService import failed for attendance {self.id}: {e}")
                return "Invalid coordinates"
            except AttributeError as e:
                logger.error(f"GeospatialService method not available for attendance {self.id}: {e}")
                return "Invalid coordinates"
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid coordinate data for attendance {self.id}: {e}")
                return "Invalid coordinates"
            except Exception as e:
                logger.exception(f"Unexpected error formatting start location for attendance {self.id}: {e}")
                return "Invalid coordinates"
        return ""

    @property
    @safe_property(fallback_value="")
    def endlocation_display(self):
        """Returns a human-readable format of end location using geospatial service"""
        if self.endlocation:
            try:
                from apps.attendance.services.geospatial_service import GeospatialService
                lon, lat = GeospatialService.extract_coordinates(self.endlocation)
                return GeospatialService.format_coordinates(lat, lon)
            except (ImportError, ModuleNotFoundError) as e:
                logger.error(f"GeospatialService import failed for attendance {self.id}: {e}")
                return "Invalid coordinates"
            except AttributeError as e:
                logger.error(f"GeospatialService method not available for attendance {self.id}: {e}")
                return "Invalid coordinates"
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid coordinate data for attendance {self.id}: {e}")
                return "Invalid coordinates"
            except Exception as e:
                logger.exception(f"Unexpected error formatting end location for attendance {self.id}: {e}")
                return "Invalid coordinates"
        return ""

    def clean(self):
        """Validate model fields including JSON schema validation"""
        super().clean()

        # Validate peventlogextras JSON structure
        if self.peventlogextras:
            try:
                from apps.attendance.validators import validate_peventlog_extras
                self.peventlogextras = validate_peventlog_extras(self.peventlogextras)
            except ValidationError as e:
                raise ValidationError({'peventlogextras': e.message})

    def save(self, *args, **kwargs):
        """Override save to ensure JSON validation"""
        self.full_clean()
        super().save(*args, **kwargs)

    def safe_update_extras(self, updates: dict, save: bool = True) -> bool:
        """
        Safely update peventlogextras with validation and race condition protection.

        Args:
            updates: Dictionary of updates to apply
            save: Whether to save the model after updates

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            # Create a copy of current extras
            current_extras = copy.deepcopy(self.peventlogextras or peventlog_json())

            # Apply updates
            current_extras.update(updates)

            # Validate the updated structure
            from apps.attendance.validators import validate_peventlog_extras
            validated_extras = validate_peventlog_extras(current_extras)

            # Update the field
            self.peventlogextras = validated_extras

            if save:
                self.save(update_fields=['peventlogextras'])

            logger.info(f"Successfully updated peventlogextras for attendance {self.id}")
            return True

        except (ValidationError, ValueError, TypeError) as e:
            logger.error(f"Failed to update peventlogextras for attendance {self.id}: {str(e)}")
            return False

    def get_face_recognition_status(self) -> dict:
        """
        Get face recognition verification status.

        Returns:
            Dictionary with verification status for punch in/out
        """
        extras = self.peventlogextras or {}
        return {
            'verified_in': extras.get('verified_in', False),
            'distance_in': extras.get('distance_in'),
            'verified_out': extras.get('verified_out', False),
            'distance_out': extras.get('distance_out'),
            'verification_attempts': extras.get('verification_attempts', 0)
        }

    def get_geofence_status(self) -> dict:
        """
        Get geofence validation status.

        Returns:
            Dictionary with geofence status for start/end locations
        """
        extras = self.peventlogextras or {}
        return {
            'start_in_geofence': extras.get('isStartLocationInGeofence'),
            'end_in_geofence': extras.get('isEndLocationInGeofence')
        }

    def increment_verification_attempts(self) -> bool:
        """
        Safely increment verification attempts counter.

        Returns:
            True if successful, False if max attempts reached
        """
        current_attempts = self.peventlogextras.get('verification_attempts', 0)

        if current_attempts >= 5:  # Max attempts from schema
            logger.warning(f"Max verification attempts reached for attendance {self.id}")
            return False

        return self.safe_update_extras({
            'verification_attempts': current_attempts + 1
        })

    def log_verification_error(self, error_message: str) -> bool:
        """
        Log verification error to the JSON field.

        Args:
            error_message: Error message to log

        Returns:
            True if logged successfully
        """
        current_logs = self.peventlogextras.get('error_logs', [])

        # Limit to last 10 error messages
        if len(current_logs) >= 10:
            current_logs = current_logs[-9:]

        current_logs.append(f"{timezone.now().isoformat()}: {error_message}")

        return self.safe_update_extras({
            'error_logs': current_logs
        })

    class Meta(BaseModel.Meta):
        db_table = "peopleeventlog"


# temporary table
class Tracking(models.Model):
    class Identifier(models.TextChoices):
        NONE = ("NONE", "None")
        CONVEYANCE = ("CONVEYANCE", "Conveyance")
        EXTERNALTOUR = ("EXTERNALTOUR", "External Tour")
        INTERNALTOUR = ("INTERNALTOUR", "Internal Tour")
        SITEVISIT = ("SITEVISIT", "Site Visit")
        TRACKING = ("TRACKING", "Tracking")

    # id           = models.BigIntegerField(primary_key = True)
    uuid = models.UUIDField(unique=True, editable=True, blank=True, default=uuid.uuid4)
    deviceid = models.CharField(max_length=40)
    gpslocation = PointField(geography=True, null=True, blank=True, srid=4326)
    receiveddate = models.DateTimeField(editable=True, null=True)
    people = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        verbose_name="People",
    )
    transportmode = models.CharField(max_length=55)
    reference = models.CharField(max_length=255, default=None)
    identifier = models.CharField(
        max_length=55, choices=Identifier.choices, default=Identifier.NONE.value
    )

    class Meta:
        db_table = "tracking"


class TestGeo(models.Model):
    # id= models.BigIntegerField(primary_key = True)
    code = models.CharField(max_length=15)
    poly = PolygonField(geography=True, null=True)
    point = PointField(geography=True, blank=True, null=True)
    line = LineStringField(geography=True, null=True, blank=True)
