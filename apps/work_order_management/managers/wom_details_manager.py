from django.db.models import F, Value as V, CharField
from django.db.models.functions import Concat, Cast
from django.db import models
from django.conf import settings
from apps.tenants.managers import TenantAwareManager
import logging

logger = logging.getLogger("django")


class WOMDetailsManager(TenantAwareManager):
    """
    Custom manager for WOMDetails model with tenant-aware filtering.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_wo_details(self, womid):
        if womid in [None, "None", ""]:
            return self.none()
        qset = (
            self.filter(wom_id=womid)
            .select_related("question")
            .values(
                "question__quesname",
                "answertype",
                "min",
                "max",
                "id",
                "options",
                "alerton",
                "ismandatory",
                "seqno",
                "answer",
                "alerts",
            )
            .order_by("seqno")
        )
        return qset or self.none()

    def getAttachmentJND(self, id):
        if qset := self.filter(id=id).values("uuid"):
            if atts := self.get_atts(qset[0]["uuid"]):
                return atts or self.none()
        return self.none()

    def get_atts(self, uuid):
        from apps.activity.models.attachment_model import Attachment

        if (
            atts := Attachment.objects.annotate(
                file=Concat(
                    V(settings.MEDIA_URL, output_field=models.CharField()),
                    F("filepath"),
                    V("/"),
                    Cast("filename", output_field=models.CharField()),
                )
            )
            .filter(owner=uuid)
            .values("filepath", "filename", "attachmenttype", "datetime", "id", "file")
        ):
            return atts
        return self.none()
