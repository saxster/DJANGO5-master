"""
Session Management Utilities

Handles user session initialization, capability management, and
session data persistence for authenticated users.
"""

import logging
from django.db.utils import IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger("django")
error_logger = logging.getLogger("error_logger")


def save_capsinfo_inside_session(people, request, admin):
    """
    Persist user capabilities in session.

    Stores capability lists for web, mobile, portlet, report, and NOC
    interfaces based on user role and client configuration.

    Args:
        people: People model instance
        request: HTTP request
        admin: Boolean indicating admin status
    """
    import apps.peoples.utils as putils
    from apps.peoples.models import Capability
    from apps.core.queries import get_query

    logger.info("save_capsinfo_inside_session... STARTED")

    if admin:
        # extracting the capabilities from client
        web, mob, portlet, report, noc = putils.create_caps_choices_for_peopleform(
            request.user.client
        )
        request.session["client_webcaps"] = list(web)
        request.session["client_mobcaps"] = list(mob)
        request.session["client_portletcaps"] = list(portlet)
        request.session["client_reportcaps"] = list(report)
        request.session["client_noccaps"] = list(noc)
        request.session["people_webcaps"] = []
        request.session["people_mobcaps"] = []
        request.session["people_reportcaps"] = []
        request.session["people_portletcaps"] = []
        request.session["people_noccaps"] = []
    else:
        caps = get_query("get_web_caps_for_client")
        # extracting capabilities from people details
        request.session["client_webcaps"] = []
        request.session["client_mobcaps"] = []
        request.session["client_portletcaps"] = []
        request.session["client_reportcaps"] = []
        request.session["people_webcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["webcapability"], cfor="WEB"
            ).values_list("capscode", "capsname")
        )
        request.session["people_mobcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["mobilecapability"], cfor="MOB"
            ).values_list("capscode", "capsname")
        )
        request.session["people_reportcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["reportcapability"], cfor="REPORT"
            ).values_list("capscode", "capsname")
        )
        request.session["people_portletcaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras["portletcapability"], cfor="PORTLET"
            ).values_list("capscode", "capsname")
        )
        request.session["people_noccaps"] = list(
            Capability.objects.filter(
                capscode__in=people.people_extras.get("noccapability", ""), cfor="NOC"
            ).values_list("capscode", "capsname")
        )
        logger.info("save_capsinfo_inside_session... DONE")


def save_user_session(request, people, ctzoffset=None):
    """
    Initialize complete user session after authentication.

    Persists user details, capabilities, permissions, and site assignments
    in session storage for request-scoped access.

    Args:
        request: HTTP request
        people: People model instance (authenticated user)
        ctzoffset: Optional timezone offset

    Raises:
        ObjectDoesNotExist: If required related objects not found
    """
    import apps.peoples.utils as putils
    from apps.peoples import models as pm
    from apps.work_order_management.models import Approver
    from django.conf import settings

    try:
        logger.info("saving user data into the session ... STARTED")
        if ctzoffset:
            request.session["ctzoffset"] = ctzoffset
        if people.is_superuser is True:
            request.session["is_superadmin"] = True
            session = request.session
            session["people_webcaps"] = session["client_webcaps"] = session[
                "people_mobcaps"
            ] = session["people_reportcaps"] = session["people_portletcaps"] = session[
                "client_mobcaps"
            ] = session[
                "client_reportcaps"
            ] = session[
                "client_portletcaps"
            ] = False
            logger.info(request.session["is_superadmin"])
            putils.save_tenant_client_info(request)
        else:
            putils.save_tenant_client_info(request)
            request.session["is_superadmin"] = people.peoplecode == "SUPERADMIN"
            request.session["is_admin"] = people.isadmin
            save_capsinfo_inside_session(people, request, people.isadmin)
            logger.info("saving user data into the session ... DONE")
        request.session["assignedsites"] = list(
            pm.Pgbelonging.objects.get_assigned_sites_to_people(people.id)
        )
        request.session["people_id"] = request.user.id
        request.session["assignedsitegroups"] = people.people_extras["assignsitegroup"]
        request.session["clientcode"] = request.user.client.bucode
        request.session["clientname"] = request.user.client.buname
        request.session["sitename"] = request.user.bu.buname
        request.session["sitecode"] = request.user.bu.bucode
        request.session["google_maps_secret_key"] = settings.GOOGLE_MAP_SECRET_KEY
        request.session["is_workpermit_approver"] = request.user.people_extras[
            "isworkpermit_approver"
        ]
        # Check if the user is an approver
        client_id = request.user.client.id
        site_id = request.user.bu.id
        is_wp_approver = Approver.objects.filter(
            client_id=client_id,
            people=request.user.id,
            approverfor__contains=["WORKPERMIT"],
        ).exists()
        is_sla_approver = Approver.objects.filter(
            client_id=client_id,
            people=request.user.id,
            approverfor__contains=["SLA_TEMPLATE"],
        ).exists()
        request.session["is_wp_approver"] = is_wp_approver
        request.session["is_sla_approver"] = is_sla_approver
    except ObjectDoesNotExist:
        error_logger.error("object not found...", exc_info=True)
        raise
    except (DatabaseError, IntegrityError, ObjectDoesNotExist):
        logger.critical(
            "something went wrong please follow the traceback to fix it... ",
            exc_info=True,
        )
        raise


__all__ = [
    'save_capsinfo_inside_session',
    'save_user_session',
]
