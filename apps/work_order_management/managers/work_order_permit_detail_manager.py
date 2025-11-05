from django.db.models import Q, F
from django.apps import apps
from apps.tenants.managers import TenantAwareManager
from apps.peoples.models import People
import logging

logger = logging.getLogger("django")


class WorkOrderPermitDetailManager(TenantAwareManager):
    """
    Custom manager for Work Permit detail queries, answers, and approver status.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_workpermit_details(self, request, wp_qset_id):
        S = request.session
        QuestionSet = apps.get_model("activity", "QuestionSet")
        wp_details = []
        sections_qset = QuestionSet.objects.filter(
            parent_id=wp_qset_id, enable=True
        ).order_by("seqno")
        for section in sections_qset:
            questions = section.questionsetbelonging_set.values(
                "question__quesname",
                "answertype",
                "qset_id",
                "min",
                "max",
                "options",
                "id",
                "ismandatory",
            ).order_by("seqno")
            sq = {
                "section": section.qsetname,
                "sectionID": section.seqno,
                "questions": list(questions),  # Convert QuerySet to list
            }
            wp_details.append(sq)
        return wp_details or self.none()

    def get_return_wp_details(self, qset_id):
        QuestionSet = apps.get_model("activity", "QuestionSet")
        sections_qset = QuestionSet.objects.filter(
            parent_id=qset_id, enable=True
        ).order_by("seqno")

        rwp_details = []
        for section in sections_qset:
            questions = section.questionsetbelonging_set.values(
                "question__quesname",
                "answertype",
                "qset_id",
                "min",
                "max",
                "options",
                "id",
                "ismandatory",
            ).order_by("seqno")
            sq = {
                "section": section.qsetname,
                "sectionID": section.seqno,
                "questions": list(questions),  # Convert QuerySet to list
            }
            rwp_details.append(sq)
        return rwp_details.pop(-1) or self.none()

    def get_wp_answers(self, womid):
        childwoms = self.filter(parent_id=womid).order_by("seqno")
        logger.info(f"{childwoms = }")
        wp_details = []
        for childwom in childwoms:
            sq = {
                "section": childwom.description,
                "sectionID": childwom.seqno,
                "questions": childwom.womdetails_set.values(
                    "question__quesname",
                    "answertype",
                    "answer",
                    "qset_id",
                    "min",
                    "max",
                    "options",
                    "id",
                    "ismandatory",
                ).order_by("seqno"),
            }
            wp_details.append(sq)
        return wp_details or self.none()

    def get_approver_list(self, womid):
        if womid == "None":
            return []
        obj = self.filter(id=womid).values("other_data").first()
        app_verifier_status_data = obj["other_data"]["wp_approvers"]
        return app_verifier_status_data or []

    def get_approver_verifier_status(self, womid):
        if womid == "None":
            return []
        obj = self.filter(id=womid).values("other_data").first()
        verifier_data = obj["other_data"]["wp_verifiers"]
        approver_data = obj["other_data"]["wp_approvers"]
        data = verifier_data + approver_data
        return data

    def get_wom_records_for_mobile(
        self, fromdate, todate, peopleid, workpermit, buid, clientid, parentid
    ):
        from apps.work_order_management.models import Approver

        people = People.objects.get(id=peopleid)
        workpermit_statuses = workpermit.replace(", ", ",").split(",")
        fields = [
            "cuser_id",
            "muser_id",
            "cdtz",
            "mdtz",
            "ctzoffset",
            "description",
            "uuid",
            "plandatetime",
            "expirydatetime",
            "starttime",
            "endtime",
            "gpslocation",
            "location_id",
            "asset_id",
            "workstatus",
            "workpermit",
            "priority",
            "parent_id",
            "alerts",
            "permitno",
            "approverstatus",
            "performedby",
            "ismailsent",
            "isdenied",
            "client_id",
            "bu_id",
            "approvers",
            "id",
            "verifiers",
            "verifierstatus",
            "vendor_id",
            "qset_id__qsetname",
        ]

        try:
            identifier = Approver.objects.get(
                people_id=peopleid, approverfor="{WORKPERMIT}"
            ).identifier
        except Approver.DoesNotExist:
            identifier = None

        if identifier == "APPROVER":
            qset = (
                self.select_related()
                .annotate(
                    permitno=F("other_data__wp_seqno"),
                    approverstatus=F("other_data__wp_approvers"),
                    verifierstatus=F("other_data__wp_verifiers"),
                )
                .filter(
                    Q(cuser_id=peopleid)
                    | Q(muser_id=peopleid)
                    | Q(approvers__contains=[people.peoplecode])
                    | Q(verifiers__contains=[people.peoplecode]),
                    cdtz__date__gte=fromdate,
                    cdtz__date__lte=todate,
                    workpermit__in=workpermit_statuses,
                    bu_id=buid,
                    client_id=clientid,
                    parent_id=parentid,
                    verifiers_status="APPROVED",
                    identifier="WP",
                )
                .values(*fields)
                .order_by("-cdtz")
            )
        else:
            qset = (
                self.select_related()
                .annotate(
                    permitno=F("other_data__wp_seqno"),
                    approverstatus=F("other_data__wp_approvers"),
                    verifierstatus=F("other_data__wp_verifiers"),
                )
                .filter(
                    Q(cuser_id=peopleid)
                    | Q(muser_id=peopleid)
                    | Q(approvers__contains=[people.peoplecode])
                    | Q(verifiers__contains=[people.peoplecode]),
                    cdtz__date__gte=fromdate,
                    cdtz__date__lte=todate,
                    workpermit__in=workpermit_statuses,
                    bu_id=buid,
                    client_id=clientid,
                    parent_id=parentid,
                    identifier="WP",
                )
                .values(*fields)
                .order_by("-cdtz")
            )
        return qset or self.none()
