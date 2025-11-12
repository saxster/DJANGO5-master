from django.urls import path
from .views import (
    get_caps,
    handle_pop_forms,
    SuperTypeAssist,
    GetAllSites,
    GetAssignedSites,
    SwitchSite,
    get_list_of_peoples,
    LicenseSubscriptionView,
)


app_name = "onboarding"
urlpatterns = [
    path("client_form/get_caps/", get_caps, name="get_caps"),
    path("pop-up/ta/", handle_pop_forms, name="ta_popup"),
    path("super_typeassist/", SuperTypeAssist.as_view(), name="super_typeassist"),
    path("subscription/", LicenseSubscriptionView.as_view(), name="subscription"),
    path(
        "get_assignedsites/", GetAssignedSites.as_view(), name="get_assignedsites"
    ),
    path("get_allsites/", GetAllSites.as_view(), name="get_allsites"),
    path("switchsite/", SwitchSite.as_view(), name="switchsite"),
    path("list_of_peoples/", get_list_of_peoples, name="list_of_peoples"),
]
