"""
Face recognition verification manager for PeopleEventlog.

Handles photo attachments and verification status queries.
"""
from django.db.models import CharField, OuterRef, Exists, Cast
from apps.activity.models.attachment_model import Attachment
from itertools import chain
import logging

logger = logging.getLogger("django")


class FaceRecognitionManagerMixin:
    """
    Manager mixin for face recognition verification operations.

    Provides methods for:
    - Retrieving FR status and attachments
    - Photo validation queries
    """

    def get_people_attachment(self, pelogid, db=None):
        """
        Optimized query to get attendance record with valid attachments
        """
        # Define valid attachments subquery with optimized exclusion pattern
        valid_attachments = Attachment.objects.filter(
            owner=Cast(OuterRef('uuid'), CharField())
        ).exclude(
            filename__iregex=r'\.(3gp|mp4|csv|txt)$'  # More efficient regex pattern
        )

        # Build main query with select_related for foreign key optimization
        queryset = (
            self.select_related('peventtype')  # Optimize peventtype lookup
            .filter(
                uuid=pelogid,
                peventtype__tacode__in=['MARK', 'SELF', 'TAKE', 'AUDIT']
            )
            .annotate(
                has_valid_attachments=Exists(valid_attachments)
            )
            .filter(has_valid_attachments=True)
        )

        # Apply database routing if specified
        if db:
            queryset = queryset.using(db)

        # Return first result or none with optimized field selection
        result = queryset.values('people_id', 'id', 'uuid').first()
        return result if result else self.none()

    def get_fr_status(self, R):
        """Return FR images and status"""
        qset = self.filter(id=R["id"]).values("uuid", "peventlogextras")
        if atts := Attachment.objects.filter(owner=qset[0]["uuid"]).values(
            "filepath", "filename", "attachmenttype", "datetime", "gpslocation"
        ):
            return list(chain(qset, atts))
        return list(self.none())
