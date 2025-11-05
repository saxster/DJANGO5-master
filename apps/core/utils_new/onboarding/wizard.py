"""
Onboarding Wizard Utilities

Handles multi-step wizard form processing, state management, and
navigation for complex onboarding flows.
"""

import logging
import django.shortcuts as scts
from django.contrib import messages as msg
from django.db.utils import IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import RestrictedError

logger = logging.getLogger("django")
error_logger = logging.getLogger("error_logger")


def update_timeline_data(ids, request, update=False):
    """
    Update wizard timeline data with current selection.

    Retrieves model instances for display in timeline.
    """
    from apps.client_onboarding.models import Bt, Shift
    from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu
    from apps.peoples import models as pm

    steps = {
        "taids": TypeAssist,
        "buids": Bt,
        "shiftids": Shift,
        "peopleids": pm.People,
        "pgroupids": pm.Pgroup,
    }
    fields = {
        "buids": ["id", "bucode", "buname"],
        "taids": ["tacode", "taname", "tatype"],
        "peopleids": ["id", "peoplecode", "loginid"],
        "shiftids": ["id", "shiftname"],
        "pgroupids": ["id", "name"],
    }
    data = (
        steps[ids]
        .objects.filter(pk__in=request.session["wizard_data"][ids])
        .values(*fields[ids])
    )
    if not update:
        request.session["wizard_data"]["timeline_data"][ids] = list(data)
    else:
        request.session["wizard_data"]["timeline_data"][ids].pop()
        request.session["wizard_data"]["timeline_data"][ids] = list(data)


def update_wizard_form(wizard_data, wiz_session, request):
    """
    Process wizard form update and determine next step.

    Args:
        wizard_data: Current wizard form data
        wiz_session: Wizard session data
        request: HTTP request

    Returns:
        Redirect response to next step
    """
    resp = None
    logger.info("processing wizard is an update form")
    if wizard_data["instance_id"] not in wiz_session[wizard_data["current_ids"]]:
        wiz_session[wizard_data["current_ids"]].append(wizard_data["instance_id"])
    if wiz_session.get(wizard_data["next_ids"]):
        resp = scts.redirect(
            wizard_data["next_update_url"], pk=wiz_session[wizard_data["next_ids"]][-1]
        )
    else:
        request.session["wizard_data"].update(wiz_session)
        resp = scts.redirect(wizard_data["current_url"])
    logger.debug(f"response from update_wizard_form {resp}")
    return resp


def process_wizard_form(request, wizard_data, update=False, instance=None):
    """
    Process wizard form submission and manage state transitions.

    Handles navigation to next step or completion based on form state.

    Args:
        request: HTTP request
        wizard_data: Current wizard form data
        update: Whether this is an update operation
        instance: Model instance for update forms

    Returns:
        Redirect response
    """
    logger.info(
        "processing wizard started...",
    )
    debug_logger = logging.getLogger("debug_logger")
    debug_logger.debug("wizard_Data submitted by the view \n%s", wizard_data)
    wiz_session, resp = request.session["wizard_data"], None
    if not wizard_data["last_form"]:
        logger.info("wizard its NOT last form")
        if not update:
            logger.info("processing wizard not an update form")
            wiz_session[wizard_data["current_ids"]].append(wizard_data["instance_id"])
            request.session["wizard_data"].update(wiz_session)
            update_timeline_data(wizard_data["current_ids"], request, False)
            resp = scts.redirect(wizard_data["current_url"])
        else:
            resp = update_wizard_form(wizard_data, wiz_session, request)
            update_timeline_data(wizard_data["current_ids"], request, True)
    else:
        resp = scts.redirect("onboarding:wizard_view")
    return resp


def update_prev_step(step_url, request):
    """Update wizard session with previous step information."""
    url, ids = step_url
    session = request.session["wizard_data"]
    instance = session.get(ids)[-1] if session.get(ids) else None
    new_url = (
        url.replace("form", "update") if instance and ("update" not in url) else url
    )
    request.session["wizard_data"].update({"prev_inst": instance, "prev_url": new_url})


def update_next_step(step_url, request):
    """Update wizard session with next step information."""
    url, ids = step_url
    session = request.session["wizard_data"]
    instance = session.get(ids)[-1] if session.get(ids) else None
    new_url = (
        url.replace("form", "update") if instance and ("update" not in url) else url
    )
    request.session["wizard_data"].update({"next_inst": instance, "next_url": new_url})


def update_other_info(step, request, current, formid, pk):
    """Update wizard session with current step metadata."""
    url, ids = step[current]
    session = request.session["wizard_data"]
    session["current_step"] = session["steps"][current]
    session["current_url"] = url
    session["final_url"] = step["final_step"][0]
    session["formid"] = formid
    session["del_url"] = url.replace("form", "delete")
    session["current_inst"] = pk


def update_wizard_steps(request, current, prev, next, formid, pk):
    """
    Update wizard navigation: current, previous, next, and final URLs.

    Maps step names to URL routes and updates session accordingly.
    """
    step_urls = {
        "buform": ("onboarding:wiz_bu_form", "buids"),
        "shiftform": ("onboarding:wiz_shift_form", "shiftids"),
        "peopleform": ("/people/wizard/form/", "peopleids"),
        "pgroupform": ("/people/groups/wizard/form/", "pgroupids"),
        "final_step": ("onboarding:wizard_preview", ""),
    }
    # update prev step
    update_prev_step(step_urls.get(prev, ("", "")), request)
    # update next step
    update_next_step(step_urls.get(next, ("", "")), request)
    # update other info
    update_other_info(step_urls, request, current, formid, pk)


def get_index_for_deletion(lookup, request, ids):
    """Find index of item to delete in wizard timeline data."""
    id = lookup["id"]
    data = request.session["wizard_data"]["timeline_data"][ids]
    for idx, item in enumerate(data):
        if item["id"] == int(id):
            return idx


def delete_object(
    request,
    model,
    lookup,
    ids,
    temp,
    form,
    url,
    form_name,
    jsonformname=None,
    jsonform=None,
):
    """
    Delete an object and update wizard session.

    Handles object deletion with proper error handling and session cleanup.
    """
    try:
        logger.info("Request for object delete...")
        res, obj = None, model.objects.get(**lookup)
        form = form(instance=obj)
        obj.delete()
        msg.success(request, "Entry has been deleted successfully", "alert-success")
        request.session["wizard_data"][ids].remove(int(lookup["id"]))
        request.session["wizard_data"]["timeline_data"][ids].pop(
            get_index_for_deletion(lookup, request, ids)
        )
        logger.info("Object deleted")
        res = scts.redirect(url)
    except model.DoesNotExist:
        error_logger.error("Unable to delete, object does not exist")
        msg.error(request, "Client does not exist", "alert alert-danger")
        res = scts.redirect(url)
    except RestrictedError:
        logger.warning("Unable to delete, duw to dependencies")
        msg.error(request, "Unable to delete, duw to dependencies")
        cxt = {form_name: form, jsonformname: jsonform, "edit": True}
        res = scts.render(request, temp, context=cxt)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist):
        logger.critical("something went wrong!", exc_info=True)
        msg.error(request, "[ERROR] Something went wrong", "alert alert-danger")
        cxt = {form_name: form, jsonformname: jsonform, "edit": True}
        res = scts.render(request, temp, context=cxt)
    return res


def delete_unsaved_objects(model, ids):
    """
    Delete unsaved objects from wizard session cleanup.

    Removes placeholder objects that were created but not finalized.
    """
    if ids:
        try:
            logger.info("Found unsaved objects in session going to be deleted...")
            model.objects.filter(pk__in=ids).delete()
        except (DatabaseError, IntegrityError, ObjectDoesNotExist):
            logger.critical("delete_unsaved_objects failed", exc_info=True)
            raise
        else:
            logger.info("Unsaved objects are deleted...DONE")


__all__ = [
    'update_timeline_data',
    'update_wizard_form',
    'process_wizard_form',
    'update_prev_step',
    'update_next_step',
    'update_other_info',
    'update_wizard_steps',
    'get_index_for_deletion',
    'delete_object',
    'delete_unsaved_objects',
]
