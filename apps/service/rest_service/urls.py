from django.urls import path
from rest_framework.routers import DefaultRouter
from apps.service.rest_service import views
from apps.service.rest_service.mobile_views import (
    AttachmentSyncView,
    ExternalTourJobNeedSyncView,
    JobNeedDetailsSyncView,
    JobNeedSyncView,
    PgbelongingSyncView,
    PeopleEventLogHistoryView,
    PeopleEventLogPunchInsView,
    PeopleSyncView,
    QuestionSetBelongingSyncView,
    QuestionSetLogicView,
    QuestionSetSyncView,
    QuestionSyncView,
    TicketSyncView,
)

router = DefaultRouter()
router.register(r"people", viewset=views.PeopleViewset, basename="people")
router.register(r"peopleevents", viewset=views.PELViewset, basename="peopleevents")
router.register(r"bt", viewset=views.BtViewset, basename="bt")
router.register(r"shift", viewset=views.ShiftViewset, basename="shifts")
router.register(r"typeassist", viewset=views.TypeAssistViewset, basename="typeassists")
router.register(r"pgroup", viewset=views.PgroupViewset, basename="pgroups")
router.register(
    r"pgbelonging", viewset=views.PgbelongingViewset, basename="pgbelongings"
)
router.register(r"job", viewset=views.JobViewset, basename="jobs")
router.register(r"jobneed", viewset=views.JobneedViewset, basename="jobneeds")

urlpatterns = router.urls + [
    path("mobile/tickets/", TicketSyncView.as_view(), name="mobile-tickets-sync"),
    path("mobile/questions/", QuestionSyncView.as_view(), name="mobile-questions-sync"),
    path("mobile/question-sets/", QuestionSetSyncView.as_view(), name="mobile-question-sets-sync"),
    path(
        "mobile/question-set-belongings/",
        QuestionSetBelongingSyncView.as_view(),
        name="mobile-question-set-belongings-sync",
    ),
    path(
        "mobile/question-sets/logic/",
        QuestionSetLogicView.as_view(),
        name="mobile-question-sets-logic",
    ),
    path("mobile/job-needs/", JobNeedSyncView.as_view(), name="mobile-job-needs-sync"),
    path(
        "mobile/job-need-details/",
        JobNeedDetailsSyncView.as_view(),
        name="mobile-job-need-details-sync",
    ),
    path(
        "mobile/job-needs/external/",
        ExternalTourJobNeedSyncView.as_view(),
        name="mobile-external-tour-job-needs-sync",
    ),
    path("mobile/people/", PeopleSyncView.as_view(), name="mobile-people-sync"),
    path(
        "mobile/group-memberships/",
        PgbelongingSyncView.as_view(),
        name="mobile-pgbelongings-sync",
    ),
    path(
        "mobile/attendance/punches/",
        PeopleEventLogPunchInsView.as_view(),
        name="mobile-attendance-punches-sync",
    ),
    path(
        "mobile/attendance/history/",
        PeopleEventLogHistoryView.as_view(),
        name="mobile-attendance-history-sync",
    ),
    path("mobile/attachments/", AttachmentSyncView.as_view(), name="mobile-attachments-sync"),
]
