import graphene
import graphql_jwt
from graphql_jwt.decorators import login_required
from django.conf import settings
from apps.service.queries.ticket_queries import TicketQueries
from apps.service.queries.question_queries import QuestionQueries
from apps.service.queries.job_queries import JobQueries
from apps.service.queries.typeassist_queries import TypeAssistQueries
from apps.service.queries.workpermit_queries import WorkPermitQueries
from apps.service.queries.people_queries import PeopleQueries
from apps.service.queries.asset_queries import AssetQueries
from apps.service.queries.bt_queries import BtQueries
from apps.journal.graphql_schema import JournalWellnessQueries, JournalWellnessMutations
from apps.helpbot.graphql_schema import HelpBotQueries, HelpBotMutations
from apps.core.graphql_security import GraphQLSecurityIntrospection
from .mutations import (
    InsertRecord,
    AdhocMutation,
    LoginUser,
    LogoutUser,
    ReportMutation,
    TaskTourUpdate,
    UploadAttMutaion,
    SecureFileUploadMutation,
    SyncMutation,
    InsertJsonMutation,
)
from .types import (
    PELogType,
    TrackingType,
    TestGeoType,
)
from apps.attendance.models import PeopleEventlog, Tracking, TestGeo


class Mutation(graphene.ObjectType):
    token_auth = LoginUser.Field()
    logout_user = LogoutUser.Field()
    insert_record = InsertRecord.Field()
    update_task_tour = TaskTourUpdate.Field()
    upload_report = ReportMutation.Field()

    # DEPRECATED: Insecure upload mutation (CVSS 8.1 vulnerability)
    # Feature flag: ENABLE_LEGACY_UPLOAD_MUTATION (default: False in production)
    # This mutation has known security vulnerabilities (path traversal, filename injection)
    # and should only be enabled for backward compatibility during migration period.
    # Production deployments SHOULD disable this immediately.
    # Migration deadline: 2026-06-30
    if getattr(settings, 'ENABLE_LEGACY_UPLOAD_MUTATION', settings.DEBUG):
        upload_attachment = UploadAttMutaion.Field(
            deprecation_reason="SECURITY WARNING: Contains vulnerabilities (path traversal, filename injection). Use secure_file_upload instead. Will be removed in v2.0 (2026-06-30). Migration guide: /docs/api-migrations/file-upload-v2/"
        )

    secure_file_upload = SecureFileUploadMutation.Field()
    sync_upload = SyncMutation.Field()
    adhoc_record = AdhocMutation.Field()
    insert_json = InsertJsonMutation.Field()
    refresh_token = graphql_jwt.Refresh.Field()


class Query(
    TicketQueries,
    QuestionQueries,
    JobQueries,
    TypeAssistQueries,
    WorkPermitQueries,
    PeopleQueries,
    AssetQueries,
    BtQueries,
    JournalWellnessQueries,
    HelpBotQueries,
    graphene.ObjectType,
):
    PELog_by_id = graphene.Field(PELogType, id=graphene.Int())
    trackings = graphene.List(TrackingType)
    testcases = graphene.List(TestGeoType)
    viewer = graphene.String()
    # Security introspection field for CSRF protection (fixes CVSS 8.1 vulnerability)
    security_info = graphene.Field(GraphQLSecurityIntrospection)

    @staticmethod
    @login_required
    def resolve_PELog_by_id(info, id):
        from django.core.exceptions import PermissionDenied
        user = info.context.user

        try:
            eventlog = PeopleEventlog.objects.get(id=id)

            if not user.isadmin and eventlog.peopleid != user.id:
                raise PermissionDenied("Access denied - can only view own event logs")

            return eventlog
        except PeopleEventlog.DoesNotExist:
            raise GraphQLError("Event log not found")

    @staticmethod
    @login_required
    def resolve_trackings(info):
        from django.core.exceptions import PermissionDenied
        user = info.context.user

        if not user.isadmin:
            return Tracking.objects.filter(peopleid=user.id)

        return Tracking.objects.filter(client_id=user.client_id)

    @staticmethod
    @login_required
    def resolve_testcases(info):
        user = info.context.user

        if not user.isadmin:
            raise GraphQLError("Admin privileges required")

        return list(TestGeo.objects.filter(client_id=user.client_id))

    @login_required
    def resolve_viewer(self, info, **kwargs):
        return "validtoken" if info.context.user.is_authenticated else "tokenexpired"

    @staticmethod
    def resolve_security_info(info):
        """Resolver for GraphQL security introspection."""
        return GraphQLSecurityIntrospection()


class RootQuery(Query):
    pass


class RootMutation(Mutation, JournalWellnessMutations, HelpBotMutations):
    pass


schema = graphene.Schema(query=RootQuery, mutation=RootMutation)
