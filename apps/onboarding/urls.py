from django.urls import path
from apps.onboarding import views


app_name = "onboarding"
urlpatterns = [
    path("client_form/get_caps/", views.get_caps, name="get_caps"),
    path("pop-up/ta/", views.handle_pop_forms, name="ta_popup"),
    path("super_typeassist/", views.SuperTypeAssist.as_view(), name="super_typeassist"),
    path("subscription/", views.LicenseSubscriptionView.as_view(), name="subscription"),
    path(
        "get_assignedsites/", views.GetAssignedSites.as_view(), name="get_assignedsites"
    ),
    path("get_allsites/", views.GetAllSites.as_view(), name="get_allsites"),
    path("switchsite/", views.SwitchSite.as_view(), name="switchsite"),
    path("list_of_peoples/", views.get_list_of_peoples, name="list_of_peoples"),
]
