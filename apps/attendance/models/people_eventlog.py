"""
PeopleEventlog model - Main attendance tracking model.

Handles check-in/check-out events with geospatial validation, biometric verification,
fraud detection, and post assignment tracking.
"""
from apps.core.models import BaseModel
import uuid
from apps.tenants.models import TenantAwareModel
from django.db import models
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.gis.db.models import LineStringField, PointField
from django.utils.translation import gettext_lazy as _
from apps.attendance.managers import PELManager
from django.contrib.postgres.fields import ArrayField
from apps.core.utils_new.error_handling import safe_property
from apps.core.fields import EncryptedJSONField
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import TypedDict, List, Optional
import copy
import logging
from apps.core.exceptions.patterns import PARSING_EXCEPTIONS

from concurrency.fields import VersionField

logger = logging.getLogger(__name__)


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


class PeopleEventlog(BaseModel, TenantAwareModel):
    """
    Main attendance tracking model.

    Tracks employee check-in/check-out events with:
    - Geospatial validation (GPS coordinates, geofences)
    - Biometric verification (face recognition)
    - Post assignment tracking (Phase 2)
    - Fraud detection scoring (Phase 2.1)
    - Data retention compliance (Phase 2.3)
    """

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
        "client_onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="clients",
    )
    bu = models.ForeignKey(
        "client_onboarding.Bt",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="bus",
    )
    shift = models.ForeignKey(
        "client_onboarding.Shift", null=True, blank=True, on_delete=models.RESTRICT
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
        "core_onboarding.GeofenceMaster", null=True, blank=True, on_delete=models.RESTRICT
    )
    peventtype = models.ForeignKey(
        "core_onboarding.TypeAssist", null=True, blank=True, on_delete=models.RESTRICT
    )

    # Phase 2: Post Assignment Tracking
    post = models.ForeignKey(
        "attendance.Post",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records",
        help_text="Specific duty station worker checked into (Phase 2)",
    )
    post_assignment = models.ForeignKey(
        "attendance.PostAssignment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records",
        help_text="Reference to scheduled post assignment (Phase 2)",
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
    peventlogextras = EncryptedJSONField(
        _("peventlogextras"),
        encoder=DjangoJSONEncoder,
        default=peventlog_json,
        help_text="Encrypted JSON field for face recognition, geofence, and verification data (biometric templates)"
    )
    otherlocation = models.CharField(_("Other Location"), max_length=50, null=True)
    reference = models.CharField("Reference", max_length=55, null=True)
    geojson = models.JSONField(default=pel_geojson, null=True, blank=True)

    # Phase 1.4: Photo capture for buddy punching prevention
    checkin_photo = models.ForeignKey(
        'attendance.AttendancePhoto',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='checkin_attendance_records',
        help_text="Photo captured during clock-in"
    )
    checkout_photo = models.ForeignKey(
        'attendance.AttendancePhoto',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='checkout_attendance_records',
        help_text="Photo captured during clock-out"
    )

    # Phase 2.1: Fraud detection results
    fraud_score = models.FloatField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Fraud detection composite score (0-1)"
    )
    fraud_risk_level = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[
            ('MINIMAL', 'Minimal'),
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
            ('CRITICAL', 'Critical'),
        ],
        help_text="Fraud risk level determined by ML models"
    )
    fraud_anomalies = models.JSONField(
        default=list,
        blank=True,
        help_text="List of detected fraud anomalies with details"
    )
    fraud_analyzed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When fraud analysis was performed"
    )

    # Phase 2.3: Data retention and archival
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether record has been archived (>2 years old)"
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When record was moved to archive"
    )
    gps_purged = models.BooleanField(
        default=False,
        help_text="Whether GPS location data has been purged (>90 days)"
    )
    gps_purged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When GPS data was purged for privacy compliance"
    )

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
            except PARSING_EXCEPTIONS as e:
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
            except PARSING_EXCEPTIONS as e:
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
        verbose_name = "People Event Log"
        verbose_name_plural = "People Event Logs"
        indexes = [
            # Existing indexes
            models.Index(fields=['tenant', 'cdtz'], name='pel_tenant_cdtz_idx'),
            models.Index(fields=['tenant', 'people'], name='pel_tenant_people_idx'),
            models.Index(fields=['tenant', 'datefor'], name='pel_tenant_datefor_idx'),
            models.Index(fields=['tenant', 'bu'], name='pel_tenant_bu_idx'),

            # Shift validation query optimization indexes (Phase 1)
            models.Index(
                fields=['tenant', 'people', 'shift', 'datefor'],
                name='pel_validation_lookup_idx'
            ),
            models.Index(
                fields=['tenant', 'bu', 'datefor', 'shift'],
                name='pel_site_shift_idx'
            ),
            models.Index(
                fields=['tenant', 'people', 'punchouttime'],
                name='pel_rest_period_idx'
            ),
            models.Index(
                fields=['tenant', 'people', 'datefor', 'punchouttime'],
                name='pel_duplicate_check_idx'
            ),

            # Fraud detection and archival indexes (Enhancement Phase 2-3)
            models.Index(
                fields=['tenant', 'fraud_score'],
                name='pel_fraud_score_idx'
            ),
            models.Index(
                fields=['tenant', 'is_archived', 'datefor'],
                name='pel_archived_date_idx'
            ),
            models.Index(
                fields=['tenant', 'gps_purged'],
                name='pel_gps_purged_idx'
            ),
        ]


__all__ = ['PeopleEventlog', 'PEventLogExtras', 'PELGeoJson', 'peventlog_json', 'pel_geojson']
