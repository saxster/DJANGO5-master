import logging

logger = logging.getLogger("django")
from django.http import response as rp, QueryDict
from django.template.loader import render_to_string
from django.contrib import messages as msg
import django.shortcuts as scts
from django.db.models import Q
from django.http import JsonResponse
from urllib.parse import urlencode


error_logger = logging.getLogger("error_logger")
debug_logger = logging.getLogger("debug_logger")


__all__ = [
    'clean_encoded_form_data',
    'get_clean_form_data',
    'handle_other_exception',
    'handle_does_not_exist',
    'get_filter',
    'searchValue',
    'searchValue2',
    'render_form',
    'handle_DoesNotExist',
    'handle_Exception',
    'render_form_for_delete',
    'handle_RestrictedError',
    'handle_EmptyResultSet',
    'handle_intergrity_error',
    'render_form_for_update',
    'handle_invalid_form',
    'render_grid',
    'paginate_results',
    'get_paginated_results',
    'get_paginated_results2',
]


def clean_encoded_form_data(form_data):
    """
    Fix HTML-encoded form data where field names have 'amp;' prefix.

    This handles the issue where form data is double-encoded, causing
    field names like 'amp;parent', 'amp;ctzoffset' instead of 'parent', 'ctzoffset'.

    Args:
        form_data: Either a QueryDict or string containing form data

    Returns:
        QueryDict: Cleaned QueryDict with proper field names
    """
    import logging
    logger = logging.getLogger("django")
    
    # If it's already a QueryDict with amp; prefixed keys
    if isinstance(form_data, QueryDict):
        if any(key.startswith("amp;") for key in form_data.keys()):
            cleaned = {}
            for key, value in form_data.items():
                clean_key = (
                    key[4:] if key.startswith("amp;") else key
                )  # Remove 'amp;' prefix
                cleaned[clean_key] = value
            # Create new QueryDict with cleaned data
            return QueryDict(urlencode(cleaned, doseq=True))
        return form_data

    # If it's a string, check if it needs cleaning
    elif isinstance(form_data, str):
        # SECURITY HARDENING: Guard verbose logging behind DEBUG mode
        # PRIVACY: Avoid logging raw form data that may contain PII/passwords
        from django.conf import settings

        if settings.DEBUG:
            # DEBUG mode only: Log metadata, not raw data
            logger.debug(f"clean_encoded_form_data - String length: {len(form_data)}")
            logger.debug(f"clean_encoded_form_data - Contains 'options': {'options' in form_data}")
            logger.debug(f"clean_encoded_form_data - Contains 'gracetime': {'gracetime' in form_data}")

        if "amp;" in form_data:
            # Replace all occurrences of amp; in the raw string
            form_data = form_data.replace("amp;", "")
            if settings.DEBUG:
                logger.debug(f"clean_encoded_form_data - After removing amp;: length={len(form_data)}")

        # SECURITY: Never log raw form data (may contain passwords, SSN, credit cards, etc.)
        # Original: logger.info(f"String before QueryDict: {form_data[:500]}...")
        # Removed to prevent PII leakage

        result = QueryDict(form_data)

        if settings.DEBUG:
            # DEBUG mode only: Log safe metadata
            # Filter out sensitive field names from logs
            sensitive_fields = {'password', 'passwd', 'pwd', 'secret', 'token', 'ssn', 'card', 'cvv', 'pin'}
            safe_keys = [k for k in result.keys() if not any(s in k.lower() for s in sensitive_fields)]
            logger.debug(f"clean_encoded_form_data - Safe keys: {safe_keys[:10]}")  # First 10 only

        return result

    # If neither, try to convert to QueryDict
    return QueryDict(str(form_data))


def get_clean_form_data(request):
    """
    Get cleaned form data from request.POST['formData'] or request.body if truncated.

    This function handles the SafeExceptionReporterFilter truncation issue where
    Django truncates request.POST['formData'] if it considers it sensitive.

    Args:
        request: Django HttpRequest object

    Returns:
        QueryDict: Cleaned form data
    """
    try:
        raw_data = request.POST.get("formData", "")
        
        # Check if formData was truncated by SafeExceptionReporterFilter
        if raw_data and ('[REMOVED]' in raw_data or len(raw_data) < 500):
            logger.info("Detected truncated formData, parsing from request.body")
            try:
                # Parse the raw request body to extract formData
                import urllib.parse
                raw_body = request.body.decode('utf-8')
                
                # Parse the body as form data
                parsed_body = urllib.parse.parse_qs(raw_body)
                
                # Extract the formData field
                if 'formData' in parsed_body:
                    raw_data = parsed_body['formData'][0]  # parse_qs returns lists
                    logger.info(f"Extracted formData from raw body, length: {len(raw_data)}")
                
            except (ValueError, TypeError) as body_error:
                logger.error(f"Error parsing request.body: {body_error}")
        
        return clean_encoded_form_data(raw_data)
    except (ValueError, TypeError) as e:
        logger.error(f"Error cleaning form data: {e}")
        return QueryDict()


def handle_other_exception(
    request, form, form_name, template, jsonform="", jsonform_name=""
):
    logger.critical(
        "something went wrong please follow the traceback to fix it... ", exc_info=True
    )
    msg.error(request, "[ERROR] Something went wrong", "alert-danger")
    cxt = {form_name: form, "edit": True, jsonform_name: jsonform}
    return scts.render(request, template, context=cxt)


def handle_does_not_exist(request, url):
    error_logger.error("Object does not exist", exc_info=True)
    msg.error(request, "Object does not exist", "alert-danger")
    return scts.redirect(url)


def get_filter(field_name, filter_condition, filter_value):
    # thanks to the below post
    # https://stackoverflow.com/questions/310732/in-django-how-does-one-filter-a-queryset-with-dynamic-field-lookups
    # the idea to this below logic is very similar to that in the above mentioned post
    if filter_condition.strip() == "contains":
        kwargs = {"{0}__icontains".format(field_name): filter_value}
        return Q(**kwargs)

    if filter_condition.strip() == "not_equal":
        kwargs = {"{0}__iexact".format(field_name): filter_value}
        return ~Q(**kwargs)

    if filter_condition.strip() == "starts_with":
        kwargs = {"{0}__istartswith".format(field_name): filter_value}
        return Q(**kwargs)

    if filter_condition.strip() == "equal":
        kwargs = {"{0}__iexact".format(field_name): filter_value}
        return Q(**kwargs)

    # CODE QUALITY FIX: Removed duplicate "not_equal" branch (was at line 178)
    # The condition is already handled above at line 167-169


def searchValue(objects, fields, related, model, ST):
    q_objs = Q()
    for field in fields:
        q_objs |= get_filter(field, "contains", ST)
    return model.objects.filter(q_objs).select_related(*related).values(*fields)


def searchValue2(fields, ST):
    q_objs = Q()
    for field in fields:
        q_objs |= get_filter(field, "contains", ST)
    return q_objs


def render_form(request, params, cxt):
    logger.info("%s", cxt["msg"])
    html = render_to_string(params["template_form"], cxt, request)
    data = {"html_form": html}
    return rp.JsonResponse(data, status=200)


def handle_DoesNotExist(request):
    data = {"errors": "Unable to edit object not found"}
    # BUGFIX: Use correct key 'errors' instead of 'error'
    error_logger.error("%s", data["errors"], exc_info=True)
    msg.error(request, data["errors"], "alert-danger")
    return rp.JsonResponse(data, status=404)


def handle_Exception(request, force_return=None):
    data = {"errors": "Something went wrong, Please try again!"}
    logger.critical(data["errors"], exc_info=True)
    msg.error(request, data["errors"], "alert-danger")
    if force_return:
        return force_return
    return rp.JsonResponse(data, status=404)


def render_form_for_delete(request, params, master=False):
    logger.info("render form for delete")
    from django.db.models import RestrictedError

    try:
        pk = request.GET.get("id")
        obj = params["model"].objects.get(id=pk)
        if master:
            obj.enable = False
            obj.save()
        else:
            obj.delete()
        return rp.JsonResponse({}, status=200)
    except params["model"].DoesNotExist:
        return handle_DoesNotExist(request)
    except RestrictedError:
        return handle_RestrictedError(request)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist):
        # BUGFIX: Remove params argument - handle_Exception expects (request, force_return=None)
        # Passing params (a dict) as force_return would return dict instead of HttpResponse
        return handle_Exception(request)


def handle_RestrictedError(request):
    data = {"errors": "Unable to delete, due to dependencies"}
    logger.warning("%s", data["errors"], exc_info=True)
    msg.error(request, data["errors"], "alert-danger")
    return rp.JsonResponse(data, status=404)


def handle_EmptyResultSet(request, params, cxt):
    logger.warning("empty objects retrieved", exc_info=True)
    msg.error(request, "List view not found", "alert-danger")
    return scts.render(request, params["template_list"], cxt)


def handle_intergrity_error(name):
    msg = f"The {name} record of with these values is already exisit!"
    logger.info(msg, exc_info=True)
    return rp.JsonResponse({"errors": msg}, status=404)


def render_form_for_update(request, params, formname, obj, extra_cxt=None, FORM=None):
    if extra_cxt is None:
        extra_cxt = {}
    logger.info("render form for update")
    try:
        logger.info(f"object retrieved '{obj}'")
        F = FORM or params["form_class"](instance=obj, request=request)
        C = {formname: F, "edit": True} | extra_cxt

        html = render_to_string(params["template_form"], C, request)
        data = {"html_form": html}
        return rp.JsonResponse(data, status=200)
    except params["model"].DoesNotExist:
        return handle_DoesNotExist(request)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist):
        return handle_Exception(request)


def handle_invalid_form(request, params, cxt):
    logger.info("form is not valid")
    return rp.JsonResponse(cxt, status=404)


def render_grid(request, params, msg, objs, extra_cxt=None):
    if extra_cxt is None:
        extra_cxt = {}

    from django.core.exceptions import EmptyResultSet

    logger.info("render grid")
    try:
        logger.info("%s", msg)
        logger.info(f"objects {len(objs)} retrieved from db" if objs else "No Records!")

        logger.info("Pagination Starts" if objs else "")
        cxt = paginate_results(request, objs, params)
        logger.info("Pagination Ends" if objs else "")
        if extra_cxt:
            cxt.update(extra_cxt)
        resp = scts.render(request, params["template_list"], context=cxt)
    except EmptyResultSet:
        resp = handle_EmptyResultSet(request, params, cxt)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist):
        resp = handle_Exception(request, scts.redirect("/dashboard"))
    return resp


def paginate_results(request, objs, params):
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

    logger.info("paginate results" if objs else "")
    if request.GET:
        objs = params["filter"](request.GET, queryset=objs).qs
    filterform = params["filter"]().form
    page = request.GET.get("page", 1)
    paginator = Paginator(objs, 15)
    try:
        li = paginator.page(page)
    except PageNotAnInteger:
        li = paginator.page(1)
    except EmptyPage:
        li = paginator.page(paginator.num_pages)
    return {params["list"]: li, params["filt_name"]: filterform}


def get_paginated_results(requestData, objects, count, fields, related, model):
    """paginate the results"""

    logger.info("Pagination Start" if count else "")
    if not requestData.get("draw"):
        return {"data": []}
    if requestData["search[value]"] != "":
        objects = searchValue(
            objects, fields, related, model, requestData["search[value]"]
        )
        filtered = objects.count()
    else:
        filtered = count
    length, start = int(requestData["length"]), int(requestData["start"])
    return objects[start : start + length], filtered


def get_paginated_results2(objs, count, params, R):
    filtered = 0
    if count:
        logger.info("Pagination Start" if count else "")
        if R["serch[value]"] != "":
            objects = searchValue2(
                objs, params["fields"], params["related"], R["search[value]"]
            )
            filtered = objects.count()
        else:
            filtered = count
        length, start = int(R["length"]), int(R["start"])
        objects = objects[start : start + length]
    return JsonResponse(
        data={
            "draw": R["draw"],
            "data": list(objects),
            "recordsFiltered": filtered,
            "recordsTotal": count,
        }
    )
