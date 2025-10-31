"""REST endpoints for mobile sync data."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied

from apps.service.rest_service.mixins import MigrationFeatureFlagMixin
from apps.service.rest_service.serializers_mobile import (
    AttachmentFilterSerializer,
    ExternalTourSyncFilterSerializer,
    JobNeedDetailsFilterSerializer,
    JobNeedSyncFilterSerializer,
    PgbelongingFilterSerializer,
    PeopleEventLogHistoryFilterSerializer,
    PeopleEventLogPunchInsFilterSerializer,
    PeopleModifiedFilterSerializer,
    QuestionSetBelongingFilterSerializer,
    QuestionSetLogicParamsSerializer,
    QuestionSetSyncFilterSerializer,
    QuestionSyncFilterSerializer,
    SelectOutputSerializer,
    TicketSyncFilterSerializer,
)
from apps.service.services import (
    fetch_attachments,
    fetch_external_tour_jobneeds,
    fetch_jobneed_details_modified_after,
    fetch_jobneeds_modified_after,
    fetch_modified_tickets,
    fetch_people_event_log_punch_ins,
    fetch_people_eventlog_history,
    fetch_people_modified_after,
    fetch_pgbelongings_modified_after,
    fetch_question_set_belongings_modified_after,
    fetch_question_set_with_logic,
    fetch_question_sets_modified_after,
    fetch_questions_modified_after,
)
from apps.peoples.models import Pgbelonging


class BaseMobileSyncView(MigrationFeatureFlagMixin, APIView):
    """Base view with feature-flag enforcement."""

    permission_classes = [IsAuthenticated]

    def _build_response(self, result):
        payload = SelectOutputSerializer.from_sync_result(result)
        serializer = SelectOutputSerializer(payload)
        return Response(serializer.data)

    def _enforce_tenant_scope(
        self,
        *,
        client_id: int | None = None,
        people_id: int | None = None,
        bu_id: int | None = None,
    ) -> None:
        """Ensure non-admin users only access their tenant scoped data."""

        user = self.request.user
        is_admin = getattr(user, "isadmin", False)

        if not is_admin:
            if client_id is not None and client_id != getattr(user, "client_id", None):
                raise PermissionDenied("Requested client scope not permitted")
            if people_id is not None and people_id != getattr(user, "id", None):
                raise PermissionDenied("Requested user scope not permitted")
            if bu_id is not None:
                user_bu_id = getattr(user, "bu_id", None)
                if user_bu_id != bu_id:
                    has_membership = Pgbelonging.objects.filter(
                        peopleid=user.id,
                        buid=bu_id,
                    ).exists()
                    if not has_membership:
                        raise PermissionDenied("Requested business unit scope not permitted")


class TicketSyncView(BaseMobileSyncView):
    """Return ticket records modified after a timestamp."""

    feature_flag_name = "rest_sync_read_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = TicketSyncFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            client_id=service_args["client_id"],
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )
        result = fetch_modified_tickets(**service_args)
        return self._build_response(result)


class QuestionSyncView(BaseMobileSyncView):
    """Return question records modified after a timestamp."""

    feature_flag_name = "rest_sync_read_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = QuestionSyncFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(client_id=service_args["client_id"])

        result = fetch_questions_modified_after(**service_args)
        return self._build_response(result)


class QuestionSetSyncView(BaseMobileSyncView):
    """Return question set records modified after a timestamp."""

    feature_flag_name = "rest_sync_read_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = QuestionSetSyncFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            client_id=service_args["client_id"],
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )

        result = fetch_question_sets_modified_after(**service_args)
        return self._build_response(result)


class QuestionSetBelongingSyncView(BaseMobileSyncView):
    """Return question set belonging records modified after a timestamp."""

    feature_flag_name = "rest_sync_read_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = QuestionSetBelongingFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            client_id=service_args["client_id"],
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )

        result = fetch_question_set_belongings_modified_after(**service_args)
        return self._build_response(result)


class QuestionSetLogicView(BaseMobileSyncView):
    """Return full conditional logic for a question set."""

    feature_flag_name = "rest_sync_read_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = QuestionSetLogicParamsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(client_id=service_args["client_id"])

        result = fetch_question_set_with_logic(**service_args)
        return self._build_response(result)


class JobNeedSyncView(BaseMobileSyncView):
    """Return job need records modified after a timestamp."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = JobNeedSyncFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            client_id=service_args["client_id"],
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )

        result = fetch_jobneeds_modified_after(**service_args)
        return self._build_response(result)


class JobNeedDetailsSyncView(BaseMobileSyncView):
    """Return job need detail records."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = JobNeedDetailsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        result = fetch_jobneed_details_modified_after(**serializer.to_service_kwargs())
        return self._build_response(result)


class ExternalTourJobNeedSyncView(BaseMobileSyncView):
    """Return external tour job needs."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = ExternalTourSyncFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            client_id=service_args["client_id"],
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )

        result = fetch_external_tour_jobneeds(**service_args)
        return self._build_response(result)


class PeopleSyncView(BaseMobileSyncView):
    """Return people records modified after a timestamp."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = PeopleModifiedFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(bu_id=service_args["bu_id"])

        result = fetch_people_modified_after(**service_args)
        return self._build_response(result)


class PeopleEventLogPunchInsView(BaseMobileSyncView):
    """Return people event log punch-in records."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = PeopleEventLogPunchInsFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )

        result = fetch_people_event_log_punch_ins(**service_args)
        return self._build_response(result)


class PgbelongingSyncView(BaseMobileSyncView):
    """Return pgbelonging records modified after a timestamp."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = PgbelongingFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )

        result = fetch_pgbelongings_modified_after(**service_args)
        return self._build_response(result)


class PeopleEventLogHistoryView(BaseMobileSyncView):
    """Return people event log history records."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = PeopleEventLogHistoryFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(
            client_id=service_args["client_id"],
            people_id=service_args["people_id"],
            bu_id=service_args["bu_id"],
        )

        result = fetch_people_eventlog_history(**service_args)
        return self._build_response(result)


class AttachmentSyncView(BaseMobileSyncView):
    """Return attachments for the current user."""

    feature_flag_name = "rest_sync_jobs_enabled"

    def get(self, request):
        self.ensure_feature_flag_enabled()
        serializer = AttachmentFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        service_args = serializer.to_service_kwargs()
        self._enforce_tenant_scope(people_id=request.user.id)

        # Force owner to current user to prevent horizontal access.
        service_args["owner"] = str(request.user.id)

        result = fetch_attachments(**service_args)
        return self._build_response(result)
